"""A claim reference names one claim of one exact version of a C02 record, so a claim_id identifies exactly one claim within that version.

Records and versions are separate scopes: the same claim_id in two records, or in two versions of one record, is valid. Within one version a claim_id that two claims share identifies neither of them,
and a reference to it is not resolved to whichever claim happens to be listed first or last: the record is found (REF008), and so is every reference that names the repeated id.
"""
import copy
import unittest

import support  # noqa: F401  (puts scripts/ on the path)

from eahs import semantics
from eahs.cases import mutate_model
from eahs.model import iter_refs

RECORD, FILE = "C02 GR-5521 v2", "c02-GR-5521-v2.json"
CLAIMS = "/content/claims"


def claim(claim_id="c1", text=None):
    stored = support.example_model().get("C02", "GR-5521", "v2").data["content"]["claims"][0]
    return dict(copy.deepcopy(stored), claim_id=claim_id, **({"text": text} if text else {}))


def other_text(claim_id="c1"):
    return claim(claim_id, "Goods receipt GR-5521 (corrected) records 99 units received.")


def model_with(*mutations):
    model, _ = mutate_model(support.example_model(), list(mutations))
    return model


def claims_of(target, *rows):
    return {"target": target, "ops": [{"op": "replace", "path": CLAIMS, "value": list(rows)}]}


def findings(model):
    return sorted((f.code, f.file.replace("\\", "/").rsplit("/", 1)[-1], f.location) for f in semantics.run_all(model))


def citations(model, record_id="GR-5521", version="v2", claim_id="c1"):
    """Where a claim reference names this claim of this exact version: (file, location) of each."""
    return sorted((inst.file.replace("\\", "/").rsplit("/", 1)[-1], ref.path) for inst in model.instances.values() for ref in iter_refs(inst.data)
                  if ref.kind == "support" and ref.record_id == record_id and ref.version == version and ref.body.get("claim_id") == claim_id)


def duplicate_findings(model, record_file=FILE, **which):
    """What a repeated claim_id is found as: the record, and each reference that names the repeated id."""
    return sorted([("REF008", record_file, CLAIMS)] + [("REF008", file, location) for file, location in citations(model, **which)])


class TheStoredRecordsKeepTheirClaimIds(unittest.TestCase):
    def test_every_record_that_states_claims_uses_c1_and_no_set_of_claims_repeats_an_id(self):
        model = support.example_model()
        records = [r for r in model.of("C02") if r.data["content"]["content_type"] == "claims"]
        self.assertGreater(len({r.id for r in records}), 1)
        self.assertTrue(any(r.version == "v1" for r in records) and any(r.version == "v2" for r in records))
        for record in records:
            ids = [c["claim_id"] for c in record.data["content"]["claims"]]
            self.assertEqual(len(ids), len(set(ids)), record.label())
        self.assertEqual({c["claim_id"] for r in records for c in r.data["content"]["claims"]}, {"c1"}, "the same id in every record and in every version of a record")
        self.assertEqual(findings(model), [])


class AClaimIdIdentifiesOneClaimWithinAnExactVersion(unittest.TestCase):
    def test_two_claims_with_different_ids_are_valid(self):
        self.assertEqual(findings(model_with(claims_of(RECORD, claim("c1"), claim("c2", "A second statement of the receipt.")))), [])

    def test_the_same_ids_in_other_records_and_in_other_versions_are_valid(self):
        model = model_with(claims_of("C02 GR-5521 v1", claim("c1", support.example_model().get("C02", "GR-5521", "v1").data["content"]["claims"][0]["text"]), claim("c2", "A second statement.")),
                           claims_of(RECORD, claim("c1"), claim("c2", "A second statement.")))
        self.assertEqual(findings(model), [])

    def test_a_repeated_id_is_found_whether_the_text_differs_or_not(self):
        for label, repeat in (("different text", other_text()), ("identical text", claim())):
            with self.subTest(label):
                model = model_with(claims_of(RECORD, claim(), repeat))
                self.assertEqual(findings(model), duplicate_findings(model))

    def test_the_finding_names_the_record_the_version_the_id_and_where_it_is_stated(self):
        model = model_with(claims_of(RECORD, claim(), claim("c2", "Another statement."), other_text()))
        messages = [f.message for f in semantics.check_references(model) if f.code == "REF008" and f.location == CLAIMS]
        self.assertEqual(len(messages), 1)
        for part in ("GR-5521", "v2", "c1", "0, 2"):
            self.assertIn(part, messages[0])
        self.assertNotIn("c2", messages[0])

    def test_where_the_repeat_stands_decides_nothing(self):
        first, repeat, third = claim(), other_text(), claim("c2", "Another statement.")
        results = set()
        for rows in ((first, repeat), (repeat, first), (first, third, repeat), (first, repeat, third), (repeat, first, third), (third, repeat, first)):
            model = model_with(claims_of(RECORD, *rows))
            found = findings(model)
            self.assertEqual(found, duplicate_findings(model), [r["claim_id"] for r in rows])
            results.add(tuple(found))
        self.assertEqual(len(results), 1, "the same findings, wherever the repeated claims stand")

    def test_two_repeated_ids_are_two_findings(self):
        model = model_with(claims_of(RECORD, claim(), claim("c2", "One."), claim(), claim("c2", "Two.")))
        found = [f for f in semantics.check_references(model) if f.code == "REF008" and f.location == CLAIMS]
        self.assertEqual(sorted("c1" in f.message for f in found), [False, True])
        self.assertEqual(sorted("c2" in f.message for f in found), [False, True])

    def test_an_id_that_is_not_repeated_still_resolves_in_a_record_that_repeats_another(self):
        model = model_with(claims_of(RECORD, claim(), claim("c2", "One."), claim("c2", "Two.")))
        self.assertEqual(findings(model), [("REF008", FILE, CLAIMS)])


class AReferenceToAClaimIsResolvedByItsIdAlone(unittest.TestCase):
    def packet_citation(self):
        model = support.example_model()
        return next((file, location) for file, location in citations(model) if file.startswith("c04-PKT-0417-v2") and location.startswith("/supported_claims_references"))

    def test_a_reference_to_a_unique_claim_is_unchanged(self):
        self.assertTrue(citations(support.example_model()))
        self.assertEqual(findings(support.example_model()), [])

    def test_a_reference_to_a_claim_that_does_not_exist_is_found_as_before_and_is_not_a_duplicate(self):
        _, location = self.packet_citation()
        model = model_with({"target": "C04 PKT-0417 v2", "ops": [{"op": "replace", "path": location + "/claim_id", "value": "c9"}]})
        self.assertEqual(findings(model), [("REF002", "c04-PKT-0417-v2.json", location)])

    def test_a_reference_to_a_repeated_id_is_the_failure_of_the_repeat_in_every_order_and_is_never_resolved_by_position(self):
        """The reference names c1, and two claims of GR-5521 v2 are c1: one says 100 units and the other says 99. The packet quotes the first."""
        for label, rows in (("the claim the packet quotes first", (claim(), other_text())), ("the other claim first", (other_text(), claim()))):
            with self.subTest(label):
                model = model_with(claims_of(RECORD, *rows))
                self.assertEqual(findings(model), duplicate_findings(model))
                self.assertIn(("REF008", "c04-PKT-0417-v2.json", self.packet_citation()[1]), findings(model))
                self.assertEqual([c for c, _, _ in findings(model) if c in ("REF002", "PKT001")], [], "neither a claim that is 'not a claim' nor a text that was compared with a claim picked by position")

    def test_the_same_reference_gives_the_same_failure_whichever_claim_comes_first(self):
        results = {tuple(findings(model_with(claims_of(RECORD, *rows)))) for rows in ((claim(), other_text()), (other_text(), claim()))}
        self.assertEqual(len(results), 1)


if __name__ == "__main__":
    unittest.main()
