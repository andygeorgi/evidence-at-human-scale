"""Permission comes before disclosure.

What a requestor is told about an input that is not in front of them depends on two permission questions, asked
before any state is worked out: may they know it exists, and may they read it? These tests pin the order in the
reference decision list, in Figure F09 and in the example data, and show that an unauthorized requestor gets a safe
generic response from which nothing about a restricted record can be inferred.
"""
import itertools
import json
import sys
import unittest

import support  # noqa: F401  (puts scripts/ on the path)

sys.path.insert(0, str(support.REPO / "figures" / "src"))

import svg_figures  # noqa: E402
from eahs import semantics  # noqa: E402
from eahs.cases import check_cases, mutate_model  # noqa: E402
from eahs.disclosure import DECISION_ORDER, NO_ENTRY, ExpectedInput, classify, disclose, project  # noqa: E402
from eahs.response import render_response  # noqa: E402

PERMITTED = "Coverage is limited by access permissions; no protected source identity or content is disclosed."
COVERAGE = "Selected sources for this invoice and supplier only; sources outside this principal's permissions are not covered."
FLAGS = ("record_available", "record_fresh", "check_performed", "source_answered", "retrieval_completed", "absence_observed_with_complete_coverage")


def every_state(**fixed):
    """Every combination of what the system knows about an input, for a given set of permissions."""
    for values in itertools.product((False, True), repeat=len(FLAGS)):
        yield ExpectedInput(name="the input", **fixed, **dict(zip(FLAGS, values)))


class DecisionList(unittest.TestCase):
    def test_a_requestor_who_may_not_know_it_exists_learns_nothing_whatever_its_state(self):
        for item in every_state(requestor_may_know_it_exists=False, requestor_may_read_it=False, permitted_disclosure=PERMITTED):
            self.assertEqual(classify(item), NO_ENTRY, item)
            self.assertIsNone(disclose(item))

    def test_an_input_the_requestor_may_know_about_but_not_read_is_inaccessible_whatever_its_state(self):
        shown = {disclose(item) for item in every_state(requestor_may_know_it_exists=True, requestor_may_read_it=False, permitted_disclosure=PERMITTED)}
        self.assertEqual(len(shown), 1)
        entry = shown.pop()
        self.assertEqual((entry.label, entry.text), ("inaccessible", PERMITTED))

    def test_a_stale_unreadable_record_is_not_reported_as_stale(self):
        item = ExpectedInput("vendor master", True, False, PERMITTED, record_available=True, record_fresh=False)
        self.assertEqual(classify(item), "inaccessible")
        self.assertNotIn("stale", disclose(item).text)
        self.assertNotIn("vendor master", disclose(item).text)

    def test_only_a_readable_input_is_classified_and_in_the_order_of_the_figure(self):
        readable = dict(requestor_may_know_it_exists=True, requestor_may_read_it=True)
        cases = [
            (dict(record_available=True, record_fresh=False), "stale"),
            (dict(check_performed=False), "not_assessed"),
            (dict(source_answered=False), "unavailable"),
            (dict(retrieval_completed=False), "missing"),
            (dict(absence_observed_with_complete_coverage=True), "negative"),
            (dict(), "not_retrieved"),
        ]
        for facts, label in cases:
            self.assertEqual(classify(ExpectedInput("x", **readable, **facts)), label, facts)
        both = ExpectedInput("x", **readable, record_available=True, record_fresh=False, check_performed=False)
        self.assertEqual(classify(both), "stale")

    def test_the_decision_list_and_figure_f09_ask_the_same_questions_in_the_same_order(self):
        self.assertEqual([name for _, _, name, _, _ in svg_figures.QUESTIONS] + ["not_retrieved"], list(DECISION_ORDER))
        self.assertEqual(svg_figures.QUESTIONS[0][2], "no entry")
        self.assertEqual(svg_figures.QUESTIONS[1][2], "inaccessible")


class NoExistenceLeakage(unittest.TestCase):
    def test_the_view_is_identical_with_and_without_a_restricted_record_the_requestor_may_not_know_about(self):
        known = [ExpectedInput("credit notes", True, True, retrieval_completed=True), ExpectedInput("treasury position", True, True, source_answered=False)]
        for hidden in every_state(requestor_may_know_it_exists=False, requestor_may_read_it=False, permitted_disclosure=PERMITTED):
            self.assertEqual(project(known + [hidden], COVERAGE), project(known, COVERAGE))

    def test_an_unauthorized_requestor_gets_the_generic_coverage_statement_and_nothing_else(self):
        hidden = ExpectedInput("investigation file", False, False, record_available=True, record_fresh=False)
        view = project([hidden], COVERAGE)
        self.assertEqual([(e.label, e.text) for e in view], [("coverage", COVERAGE)])
        text = json.dumps([(e.label, e.text) for e in view]).lower()
        for word in ("investigation", "stale", "exists", "restricted"):
            self.assertNotIn(word, text)

    def test_the_inaccessible_entry_carries_only_the_permitted_wording(self):
        view = project([ExpectedInput("vendor master", True, False, PERMITTED)], COVERAGE)
        self.assertEqual([(e.label, e.text) for e in view], [("inaccessible", PERMITTED), ("coverage", COVERAGE)])


class TheExampleData(unittest.TestCase):
    def setUp(self):
        self.model = support.example_model()
        self.registry = self.model.registry

    def test_each_unreadable_entry_rests_on_a_decision_that_allows_it_and_uses_its_words(self):
        for loc, ref, shown in [x for inst in self.model.of("C03") + self.model.of("C04") for x in semantics._unreadable_entries(inst)]:
            decision = self.registry.permission_decisions["%s@%s" % (ref["record_id"], ref["version"])]
            self.assertTrue(decision["disclose_existence_allowed"], loc)
            self.assertEqual(shown, decision["permitted_disclosure"], loc)

    def test_a_source_whose_existence_is_withheld_appears_in_no_output(self):
        withheld = [k for k, v in self.registry.permission_decisions.items() if not v["disclose_existence_allowed"]]
        self.assertEqual(withheld, ["AUTHZ-READ-WITHHELD-0417@v1"])
        outputs = []
        for inst in self.model.of("C01") + self.model.of("C03") + self.model.of("C04"):
            outputs.append(json.dumps(inst.data))
        for packet in self.model.of("C04"):
            outputs.append(json.dumps(render_response(self.model, packet)))
        blob = "\n".join(outputs).lower()
        for word in ("withheld", "investigation", "authz-read-withheld", "vendor master", "vendor-master"):
            self.assertNotIn(word, blob)

    def test_the_rendered_response_for_the_requestor_carries_only_the_permitted_wording_about_the_unreadable_part(self):
        for packet in self.model.of("C04"):
            statements = render_response(self.model, packet)["statements"]
            inaccessible = [s for s in statements if s["kind"] == "gap" and "(inaccessible)" in s["label"]]
            self.assertEqual([s["text"] for s in inaccessible], ["Inaccessible: " + PERMITTED])

    def test_the_identifiers_in_the_outputs_do_not_name_what_they_protect(self):
        blob = "\n".join(json.dumps(inst.data) for inst in self.model.of("C03") + self.model.of("C04"))
        for fragment in ("RESTRICTED", "DENY"):
            self.assertNotIn(fragment, blob)


class TheChecks(unittest.TestCase):
    def setUp(self):
        self.model = support.example_model()

    def run_case(self, case_id):
        data = support.read_json("13-evaluation-cases/cases.json")
        data = dict(data, cases=[c for c in data["cases"] if c["case_id"] == case_id])
        problems, count = check_cases(self.model, support.schema(), data, support.EXAMPLES / "13-evaluation-cases" / "cases.json")
        self.assertEqual(count, 1)
        return [p.format() for p in problems]

    def test_the_example_set_has_no_disclosure_findings(self):
        self.assertEqual([f.code for f in semantics.check_disclosure(self.model)], [])

    def test_an_entry_for_a_source_whose_existence_is_withheld_is_found(self):
        self.assertEqual(self.run_case("CASE-DISC-02"), [])
        mutated, _ = mutate_model(self.model, [
            {"target": "C04 PKT-0417 v1", "ops": [{"op": "replace", "path": "/coverage_omissions_gaps/missingness/2/permission_decision_reference/record_id", "value": "AUTHZ-READ-WITHHELD-0417"}]}])
        codes = [f.code for f in semantics.check_disclosure(mutated)]
        self.assertEqual(codes, ["DISC002"])

    def test_wording_beyond_the_permitted_words_is_found(self):
        self.assertEqual(self.run_case("CASE-DISC-03"), [])

    def test_an_entry_with_no_permission_decision_at_all_is_found(self):
        mutated, _ = mutate_model(self.model, [{"target": "C04 PKT-0417 v1", "ops": [{"op": "replace", "path": "/coverage_omissions_gaps/missingness/2/permission_decision_reference/record_id", "value": "AUTHZ-DOES-NOT-EXIST"}]}])
        self.assertIn("DISC002", [f.code for f in semantics.check_disclosure(mutated)])


class TheDocuments(unittest.TestCase):
    def text(self, relative):
        return (support.REPO / relative).read_text(encoding="utf-8")

    def test_the_figure_text_puts_permission_first(self):
        meta = {f["id"]: f for f in json.loads(self.text("figures/figures.json"))["figures"]}["F09"]
        self.assertIn("may not know the input exists", meta["alt"])
        self.assertLess(meta["description"].index("may the reader's principal know"), meta["description"].index("stale"))
        self.assertIn("permission", meta["caption"].lower())

    def test_the_architecture_page_states_the_order_of_operations(self):
        page = self.text("architecture/lineage-selection-disclosure.md").lower()
        self.assertIn("permission comes before disclosure", page)
        positions = [page.index(step) for step in ("may know that", "safe-disclosure policy", "classify only", "expose only")]
        self.assertEqual(positions, sorted(positions))


if __name__ == "__main__":
    unittest.main()
