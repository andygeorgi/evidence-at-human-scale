import copy
import unittest
from collections import Counter

import support  # noqa: F401

from eahs import semantics
from eahs.cases import check_cases, mutate_model
from eahs.gateway import evaluate_commit, ledger_from_receipts, ts
from eahs.patch import apply_ops
from eahs.scenarios import evaluate_entry, expectation


class ProvenanceTeaching(unittest.TestCase):
    """Example 03 teaches ancestry, so nothing a summary says may reach beyond the records it declares it rests on."""

    def summaries(self):
        model = support.example_model()
        found = [r for r in model.of("C02") if r.data["identity_schema"]["kind"] == "model_inference"]
        self.assertEqual(sorted(r.id for r in found), ["SUM-A-0417", "SUM-B-0417"])
        return model, found

    @staticmethod
    def lin005(model):
        return [f for f in semantics.check_lineage(model) if f.code == "LIN005"]

    def test_no_summary_states_a_figure_its_ancestry_does_not_hold(self):
        model, found = self.summaries()
        self.assertEqual(self.lin005(model), [])
        for rec in found:
            held = Counter()
            for ancestor in semantics.ancestors(model, rec).values():
                held.update(semantics._content_values(ancestor.data["content"])[0])
            for claim in rec.data["content"]["claims"]:
                self.assertEqual(sorted(semantics._numbers_in(claim["text"]) - held), [], "%s states a figure that %s does not hold" % (rec.id, sorted(a.id for a in semantics.ancestors(model, rec).values())))

    def test_the_validator_finds_a_summary_that_reaches_beyond_its_ancestry(self):
        for text in ("Goods receipt GR-5521 records 60 units received, 40 units fewer than the invoice.", "The receipt records 60 units and the supplier is owed EUR 18,400.00."):
            with self.subTest(text):
                model, _ = mutate_model(support.example_model(), [{"target": "C02 SUM-A-0417 v1", "ops": [{"op": "replace", "path": "/content/claims/0/text", "value": text}]}])
                found = self.lin005(model)
                self.assertEqual(len(found), 1)
                self.assertIn("GR-5521 v1", found[0].message)
                self.assertEqual(found[0].location, "/content/claims/0/text")

    def test_a_summary_may_state_a_figure_its_ancestry_holds_but_not_more_often_than_it_does(self):
        model, _ = mutate_model(support.example_model(), [{"target": "C02 SUM-A-0417 v1", "ops": [{"op": "replace", "path": "/content/claims/0/text", "value": "The receipt records 60 units, only 60 units."}]}])
        self.assertEqual([f.message.split(",")[0] for f in self.lin005(model)], ["this model inference states the figure 60"])
        model, _ = mutate_model(support.example_model(), [{"target": "C02 SUM-A-0417 v1", "ops": [{"op": "replace", "path": "/content/claims/0/text", "value": "The receipt records 60 units."}]}])
        self.assertEqual(self.lin005(model), [])

    def test_a_summary_that_rests_on_nothing_holds_no_figure(self):
        model, _ = mutate_model(support.example_model(), [{"target": "C02 SUM-A-0417 v1", "ops": [
            {"op": "replace", "path": "/lineage/parent_references", "value": []}, {"op": "replace", "path": "/lineage/typed_relationships", "value": []},
            {"op": "replace", "path": "/content/claims/0/text", "value": "The receipt records 60 units."}]}])
        found = self.lin005(model)
        self.assertEqual(len(found), 1)
        self.assertIn("no record", found[0].message)

    def test_no_summary_compares_with_a_record_it_does_not_rest_on(self):
        model, found = self.summaries()
        for rec in found:
            self.assertEqual({a.id for a in semantics.ancestors(model, rec).values()}, {"GR-5521"})
            said = " ".join(c["text"] for c in rec.data["content"]["claims"]).lower()
            for outside in ("invoice", "purchase order", "three-way"):
                self.assertNotIn(outside, said, "%s names %s, which is not among its sources" % (rec.id, outside))
            self.assertIn("Makes no comparison with the invoice or the purchase order: they are not among its sources.", rec.data["coverage_uncertainty"]["limitations"])

    def test_the_shared_root_is_kept(self):
        model, found = self.summaries()
        self.assertEqual([semantics.roots(model, rec) for rec in found], [{("GR-5521", "v1")}] * 2)


class Baseline(unittest.TestCase):
    def test_the_unmutated_example_set_has_no_findings(self):
        self.assertEqual([f.format() for f in semantics.run_all(support.example_model())], [])

    def test_every_evaluation_case_produces_exactly_its_declared_codes(self):
        problems, count = check_cases(support.example_model(), support.schema(), support.read_json("13-evaluation-cases/cases.json"), support.EXAMPLES / "13-evaluation-cases" / "cases.json")
        self.assertEqual([p.format() for p in problems], [])
        self.assertGreaterEqual(count, 30)

    def test_every_check_family_is_exercised_by_a_case(self):
        declared = {code for case in support.read_json("13-evaluation-cases/cases.json")["cases"] for code in case["expect"]}
        needed = {"SCH002", "REF001", "REF002", "REF003", "REF004", "REF007", "LIN001", "LIN002", "LIN003", "KIND001", "KIND002", "COR001", "COR002",
                  "LIFE002", "LIFE003", "LIFE004", "LIFE005", "MISS001", "MISS002", "MISS003", "MISS005", "PKT001", "PKT002", "AUTH004", "AUTH005",
                  "AUTH007", "ACC002", "ACC003", "ACC004", "DISC001"}
        self.assertEqual(sorted(needed - declared), [])


class GatewayStory(unittest.TestCase):
    """The scenario the examples tell, stated as assertions so that a change to the check shows up here."""

    def evaluate(self, proposal, grant, at, overrides=None, ledger="from_receipts"):
        entry = {"proposal": {"id": proposal[0], "version": proposal[1]}, "grant": {"id": grant[0], "version": grant[1]}, "at": at, "ledger": ledger}
        if overrides:
            entry["overrides"] = overrides
        return expectation(evaluate_entry(support.example_model(), entry))

    def test_the_queued_release_is_blocked_after_the_correction(self):
        result = self.evaluate(("ACT-REL-0417", "v1"), ("GRT-APPR-0417-A", "v1"), "2026-11-23T16:00:00Z")
        self.assertEqual(result["decision"], "BLOCK")
        self.assertEqual(result["codes"], ["GRANT_REVOKED", "EVIDENCE_NOT_CURRENT", "EVIDENCE_STALE", "PRECONDITION_FAILED"])

    def test_the_corrected_release_passes(self):
        self.assertEqual(self.evaluate(("ACT-REL-0417", "v2"), ("GRT-APPR-0417-B", "v1"), "2026-11-23T16:00:05Z")["decision"], "ALLOW")

    def test_an_unknown_outcome_keeps_its_reservation_so_a_retry_is_blocked(self):
        result = self.evaluate(("ACT-REL-0417", "v2"), ("GRT-APPR-0417-B", "v1"), "2026-11-23T16:10:00Z")
        self.assertEqual(result["codes"], ["CUMULATIVE_LIMIT"])

    def test_the_reservation_is_not_released_by_the_passage_of_time(self):
        result = self.evaluate(("ACT-REL-0417", "v2"), ("GRT-APPR-0417-B", "v1"), "2026-11-23T16:19:59Z")
        self.assertIn("CUMULATIVE_LIMIT", result["codes"])

    def test_failing_closed_when_revocation_cannot_be_established(self):
        result = self.evaluate(("ACT-REL-0417", "v2"), ("GRT-APPR-0417-B", "v1"), "2026-11-23T16:00:05Z",
                               [{"on": "grant", "path": "/limits_lifecycle/revocation/state", "value": "check_unavailable"}], ledger="empty")
        self.assertEqual(result["codes"], ["REVOCATION_UNVERIFIED"])

    def test_a_lowered_limit_applies_at_the_next_commit_check(self):
        amount = [{"on": "proposal", "path": "/action/typed_parameters/0/value", "value": 4200}]
        before = self.evaluate(("ACT-REL-0417", "v2"), ("GRT-CLASS-LOWVAL", "v1"), "2026-11-23T14:20:00Z", amount)
        after = self.evaluate(("ACT-REL-0417", "v2"), ("GRT-CLASS-LOWVAL", "v2"), "2026-11-23T14:40:00Z", amount)
        self.assertEqual((before["decision"], after["codes"]), ("ALLOW", ["PER_ACTION_LIMIT"]))

    def test_a_ledger_built_from_receipts_ignores_attempts_not_yet_known(self):
        model = support.example_model()
        self.assertEqual([e.grant_id for e in ledger_from_receipts(model, ts("2026-11-23T16:00:04Z"))], ["GRT-CLASS-HOLD"], "the release was submitted at 16:00:05")
        self.assertEqual([e.grant_id for e in ledger_from_receipts(model, ts("2026-11-23T16:00:05Z"))], ["GRT-CLASS-HOLD", "GRT-APPR-0417-B"], "a reservation at the attempt time was available")
        self.assertEqual([e.grant_id for e in ledger_from_receipts(model, ts("2026-11-23T16:00:05Z"), exclude_receipt_id="RCP-REL-0417-B")], ["GRT-CLASS-HOLD"], "except the attempt's own")

    def test_the_decision_has_reasons_a_person_can_read(self):
        model = support.example_model()
        proposal, grant = model.get("C05", "ACT-REL-0417", "v1"), model.get("C06", "GRT-APPR-0417-A", "v1")
        decision = evaluate_commit(model, proposal, grant, ts("2026-11-23T16:00:00Z"), [])
        self.assertTrue(all(len(r.message) > 20 for r in decision.reasons))


class Patch(unittest.TestCase):
    def test_replace_add_remove_do_not_touch_the_original(self):
        doc = {"a": [1, 2, {"b": "x"}], "c": {"d": 1}}
        original = copy.deepcopy(doc)
        out = apply_ops(doc, [{"op": "replace", "path": "/a/2/b", "value": "y"}, {"op": "add", "path": "/a/-", "value": 9}, {"op": "remove", "path": "/c/d"}])
        self.assertEqual(out, {"a": [1, 2, {"b": "y"}, 9], "c": {}})
        self.assertEqual(doc, original)

    def test_a_bad_path_fails_instead_of_silently_doing_nothing(self):
        with self.assertRaises(KeyError):
            apply_ops({"a": 1}, [{"op": "replace", "path": "/missing", "value": 1}])


if __name__ == "__main__":
    unittest.main()
