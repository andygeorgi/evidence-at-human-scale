"""Permission comes before disclosure, and the viewer's output is built from what they are permitted to see.

What a viewer is told about an input that is not in front of them depends on questions asked in a fixed order: does a
permission decision bind to this exact requesting principal, tenant and permitted purpose, may they know the
input exists, may they read it. Only then is anything about the input built into their view, and only from what the decision
permits. These tests pin that order in the reference projection, in Figure F09 and in the example data, and show that nothing
about a restricted input can change what an unauthorized viewer sees.

Three things are kept apart: snapshot validation (checking a stored output against the stored decisions), authorization
enforcement (not implemented here) and viewer projection (the reference in eahs.disclosure).
"""
import copy
import dataclasses
import itertools
import json
import sys
import unittest

import support  # noqa: F401  (puts scripts/ on the path)

sys.path.insert(0, str(support.REPO / "figures" / "src"))

import svg_figures  # noqa: E402
from eahs import semantics  # noqa: E402
from eahs.cases import check_cases, mutate_model  # noqa: E402
from eahs.disclosure import (DECISION_ORDER, NO_ENTRY, Decision, ExpectedInput, Viewer, binding_problems, classify, differences, disclose,  # noqa: E402
                             gap_entry, may_know, may_read, project, retrieval_entry)
from eahs.response import check_structural, render_response  # noqa: E402

PERMITTED = "Coverage is limited by access permissions; no protected source identity or content is disclosed."
COVERAGE = "Selected sources for this invoice and supplier only; sources outside this principal's permissions are not covered."
ANALYST, TENANT, PURPOSE = "person:ap-analyst-02", "tenant:calder-works", "Accounts-payable payment-release review"
ENTITIES = ({"entity_type": "invoice", "entity_id": "INV-2026-0417"}, {"entity_type": "supplier", "entity_id": "S-1042"})
VIEWER = Viewer(ANALYST, TENANT, PURPOSE, ENTITIES)
FLAGS = ("record_available", "record_fresh", "check_performed", "source_answered", "retrieval_completed", "absence_observed_with_complete_coverage")
#: Attributes of a restricted record that must never change what an unauthorized viewer sees.
ATTRIBUTES = [dict(category=c, source_type=s, record_count=n, materiality=m, open_state=o)
               for c, s, n, m, o in (("bank details", "vendor master", 0, "unknown", ""), ("investigation", "case file", 9, "decision_changing", "open"),
                                     ("credit notes", "ledger", 1, "outside_decision", "closed"), ("contract", "contract register", 250, "could_block_payment", "open"))]


def registry_decision(name):
    return Decision.from_registry(support.example_model().registry.permission_decisions[name])


EXISTENCE_ONLY = registry_decision("AUTHZ-READ-LIMIT-0417@v1")
WITHHELD = registry_decision("AUTHZ-READ-WITHHELD-0417@v1")
READABLE = Decision(ANALYST, TENANT, PURPOSE, read_allowed=True, disclose_existence_allowed=True)


def every_state(decision, **fixed):
    """Every combination of what the system knows about an input, for a given decision."""
    for values in itertools.product((False, True), repeat=len(FLAGS)):
        for attributes in ATTRIBUTES:
            yield ExpectedInput(name="the input", decision=decision, **fixed, **dict(zip(FLAGS, values)), **attributes)


class Binding(unittest.TestCase):
    def test_a_decision_for_this_exact_principal_tenant_and_purpose_binds(self):
        self.assertEqual(binding_problems(EXISTENCE_ONLY, VIEWER), [])
        self.assertTrue(may_know(EXISTENCE_ONLY, VIEWER))

    def test_a_decision_for_another_principal_permits_nothing(self):
        for other in ("person:ap-analyst-03", "person:ap-analyst-0", "person:ap-analyst-02 ", "PERSON:AP-ANALYST-02", "person:ap-controller-01", ""):
            decision = Decision(other, TENANT, PURPOSE, False, True, PERMITTED, EXISTENCE_ONLY.permitted_view)
            with self.subTest(other):
                self.assertTrue(binding_problems(decision, VIEWER))
                self.assertFalse(may_know(decision, VIEWER))
                self.assertEqual(classify(ExpectedInput("x", decision), VIEWER), NO_ENTRY)

    def test_the_tenant_and_the_purpose_must_be_named_and_must_match(self):
        elsewhere = Decision(ANALYST, "tenant:other", PURPOSE, False, True, PERMITTED, EXISTENCE_ONLY.permitted_view)
        other_purpose = Decision(ANALYST, TENANT, "Marketing analytics", False, True, PERMITTED, EXISTENCE_ONLY.permitted_view)
        for decision in (elsewhere, other_purpose):
            self.assertFalse(may_know(decision, VIEWER))
            self.assertIsNone(disclose(ExpectedInput("x", decision), VIEWER))

    def test_a_decision_that_names_no_tenant_or_no_purpose_binds_to_nobody(self):
        for label, tenant, purpose in (("no tenant", "", PURPOSE), ("no purpose", TENANT, ""), ("neither", "", "")):
            decision = Decision(ANALYST, tenant, purpose, False, True, PERMITTED, EXISTENCE_ONLY.permitted_view)
            with self.subTest(label):
                self.assertTrue(binding_problems(decision, VIEWER))
                self.assertFalse(may_know(decision, VIEWER))
                self.assertEqual(classify(ExpectedInput("x", decision), VIEWER), NO_ENTRY)
                self.assertIsNone(disclose(ExpectedInput("x", decision), VIEWER))

    def test_a_decision_with_no_tenant_cannot_show_another_tenants_wording(self):
        decision = Decision(ANALYST, "", PURPOSE, False, True, PERMITTED, EXISTENCE_ONLY.permitted_view)
        for tenant in ("tenant:calder-works", "tenant:other", ""):
            self.assertFalse(may_know(decision, Viewer(ANALYST, tenant, PURPOSE, ENTITIES)), tenant)

    def test_a_context_that_names_no_principal_tenant_or_purpose_has_nothing_to_bind(self):
        for label, viewer in (("no principal", Viewer("", TENANT, PURPOSE)), ("no tenant", Viewer(ANALYST, "", PURPOSE)), ("no purpose", Viewer(ANALYST, TENANT, ""))):
            with self.subTest(label):
                self.assertTrue(binding_problems(EXISTENCE_ONLY, viewer))
                self.assertFalse(may_know(EXISTENCE_ONLY, viewer))
                unbound = Decision("", "", "", False, True, PERMITTED, EXISTENCE_ONLY.permitted_view)
                self.assertFalse(may_know(unbound, viewer))

    def test_each_problem_names_what_is_missing_or_different(self):
        problems = binding_problems(Decision("", "", "", False, True, PERMITTED, {}), VIEWER)
        self.assertEqual(len(problems), 3)
        for word in ("principal", "tenant", "purpose"):
            self.assertTrue(any("names no %s" % word in p for p in problems), problems)
        other = binding_problems(Decision("person:x", "tenant:other", "Marketing analytics", False, True, PERMITTED, {}), VIEWER)
        self.assertEqual(len(other), 3)

    def test_no_decision_is_no_entry(self):
        self.assertIsNone(disclose(ExpectedInput("x", None), VIEWER))
        self.assertEqual(binding_problems(None, VIEWER), ["there is no permission decision for this input"])

    def test_a_malformed_registry_entry_reads_as_not_permitted(self):
        for raw in (None, [], "yes", {"principal": ANALYST}, {"principal": ANALYST, "disclose_existence_allowed": "true"}, {"principal": 7, "read_allowed": True}):
            with self.subTest(repr(raw)):
                self.assertFalse(may_know(Decision.from_registry(raw), VIEWER))

    def test_a_decision_that_allows_reading_but_not_knowing_that_the_input_exists_contradicts_itself_and_permits_nothing(self):
        """Reading implies knowing. A decision that says otherwise fails closed: it reveals neither the input nor the fact that it exists."""
        contradictory = Decision(ANALYST, TENANT, PURPOSE, True, False, PERMITTED, EXISTENCE_ONLY.permitted_view)
        problems = binding_problems(contradictory, VIEWER)
        self.assertEqual(len(problems), 1)
        self.assertIn("contradict", problems[0])
        self.assertFalse(may_know(contradictory, VIEWER))
        self.assertFalse(may_read(contradictory, VIEWER))
        for item in every_state(contradictory):
            self.assertEqual(classify(item, VIEWER), NO_ENTRY, item)
            self.assertIsNone(disclose(item, VIEWER))
        self.assertEqual([entry.label for entry in project([ExpectedInput("x", contradictory)], VIEWER, "Coverage is limited.")], ["coverage"])

    def test_the_two_consistent_permissions_and_their_combination_still_bind(self):
        for read, existence in ((False, True), (True, True)):
            self.assertEqual(binding_problems(Decision(ANALYST, TENANT, PURPOSE, read, existence, PERMITTED, EXISTENCE_ONLY.permitted_view), VIEWER), [], (read, existence))
        self.assertTrue(may_know(Decision(ANALYST, TENANT, PURPOSE, False, True, PERMITTED, {}), VIEWER))
        self.assertFalse(may_know(Decision(ANALYST, TENANT, PURPOSE, False, False, PERMITTED, {}), VIEWER))

    def test_the_stored_decision_changed_to_a_contradiction_allows_no_entry_in_the_snapshot_validation(self):
        model = support.example_model()
        registry = copy.deepcopy(model.registry)
        registry.permission_decisions["AUTHZ-READ-LIMIT-0417@v1"].update(disclose_existence_allowed=False, read_allowed=True)
        found = [f for f in semantics.check_disclosure(dataclasses.replace(model, registry=registry)) if f.code == "DISC004"]
        self.assertTrue(found)
        self.assertIn("contradict", found[0].message)

    def test_the_example_registry_binds_every_decision_to_the_requesting_principal_of_the_context(self):
        model = support.example_model()
        for context in model.of("C01"):
            who, task = context.data["identity_principal"], context.data["task_purpose_entity"]
            viewer = Viewer(who["requesting_principal"], who["tenant"], task["permitted_purpose"])
            for name, raw in model.registry.permission_decisions.items():
                self.assertEqual(binding_problems(Decision.from_registry(raw), viewer), [], name)


class DecisionList(unittest.TestCase):
    def test_a_viewer_who_may_not_know_it_exists_learns_nothing_whatever_its_state(self):
        for item in every_state(WITHHELD):
            self.assertEqual(classify(item, VIEWER), NO_ENTRY, item)
            self.assertIsNone(disclose(item, VIEWER))

    def test_an_input_the_viewer_may_know_about_but_not_read_is_exactly_the_generic_disclosure_whatever_its_state(self):
        shown = {disclose(item, VIEWER) for item in every_state(EXISTENCE_ONLY)}
        self.assertEqual(len(shown), 1)
        entry = shown.pop()
        self.assertEqual((entry.label, entry.text), ("inaccessible", PERMITTED))
        self.assertEqual(json.loads(entry.fields), gap_entry(EXISTENCE_ONLY, VIEWER, {"record_id": "AUTHZ-READ-LIMIT-0417", "version": "v1"}))

    def test_a_stale_unreadable_record_is_not_reported_as_stale(self):
        item = ExpectedInput("vendor master", EXISTENCE_ONLY, record_available=True, record_fresh=False)
        self.assertEqual(classify(item, VIEWER), "inaccessible")
        shown = disclose(item, VIEWER)
        for word in ("stale", "vendor master"):
            self.assertNotIn(word, shown.text + shown.fields.lower())

    def test_only_a_readable_input_is_classified_and_in_the_order_of_the_figure(self):
        cases = [
            (dict(record_available=True, record_fresh=False), "stale"),
            (dict(check_performed=False), "not_assessed"),
            (dict(source_answered=False), "unavailable"),
            (dict(retrieval_completed=False), "missing"),
            (dict(absence_observed_with_complete_coverage=True), "negative"),
            (dict(), "not_retrieved"),
        ]
        for facts, label in cases:
            self.assertEqual(classify(ExpectedInput("x", READABLE, **facts), VIEWER), label, facts)
        both = ExpectedInput("x", READABLE, record_available=True, record_fresh=False, check_performed=False)
        self.assertEqual(classify(both, VIEWER), "stale")

    def test_a_readable_input_exposes_its_own_authorized_state_and_nothing_of_another_input(self):
        visible = ExpectedInput("goods receipt", READABLE, category="receipts", record_count=2, materiality="decision_changing")
        hidden = ExpectedInput("investigation file", WITHHELD, category="investigation", record_count=9, materiality="decision_changing", open_state="open")
        view = project([visible, hidden], VIEWER, COVERAGE)
        self.assertEqual([e.label for e in view], ["not_retrieved", "coverage"])
        shown = json.loads(view[0].fields)
        self.assertEqual((shown["input"], shown["category"], shown["record_count"]), ("goods receipt", "receipts", 2))
        for word in ("investigation", "open", "9"):
            self.assertNotIn(word, json.dumps(view[1:], default=str).lower())

    def test_the_decision_list_and_figure_f09_ask_the_same_questions_in_the_same_order(self):
        self.assertEqual([name for _, _, name, _, _ in svg_figures.QUESTIONS] + ["not_retrieved"], list(DECISION_ORDER))
        self.assertEqual(svg_figures.QUESTIONS[0][2], "no entry")
        self.assertEqual(svg_figures.QUESTIONS[1][2], "inaccessible")


class NoExistenceLeakage(unittest.TestCase):
    """Unauthorized mutation of a restricted record cannot alter viewer-visible output."""

    KNOWN = [ExpectedInput("credit notes", READABLE, retrieval_completed=True), ExpectedInput("treasury position", READABLE, source_answered=False)]

    def test_the_view_is_identical_with_and_without_a_restricted_record_the_viewer_may_not_know_about(self):
        baseline = project(self.KNOWN, VIEWER, COVERAGE)
        for hidden in every_state(WITHHELD):
            self.assertEqual(project(self.KNOWN + [hidden], VIEWER, COVERAGE), baseline)

    def test_how_many_restricted_records_there_are_changes_nothing(self):
        baseline = project(self.KNOWN, VIEWER, COVERAGE)
        hidden = [ExpectedInput("restricted %d" % i, WITHHELD, **ATTRIBUTES[i % len(ATTRIBUTES)]) for i in range(7)]
        for n in range(len(hidden) + 1):
            self.assertEqual(project(self.KNOWN + hidden[:n], VIEWER, COVERAGE), baseline)

    def test_a_decision_that_does_not_bind_to_the_viewer_hides_the_record_as_well_as_no_decision_does(self):
        baseline = project(self.KNOWN, VIEWER, COVERAGE)
        for decision in (Decision("person:someone-else", TENANT, PURPOSE, False, True, PERMITTED, EXISTENCE_ONLY.permitted_view),
                         Decision(ANALYST, "tenant:other", PURPOSE, True, True), None):
            for hidden in every_state(decision):
                self.assertEqual(project(self.KNOWN + [hidden], VIEWER, COVERAGE), baseline)

    def test_an_unauthorized_viewer_gets_the_generic_coverage_statement_and_nothing_else(self):
        hidden = ExpectedInput("investigation file", WITHHELD, record_available=True, record_fresh=False)
        view = project([hidden], VIEWER, COVERAGE)
        self.assertEqual([(e.label, e.text) for e in view], [("coverage", COVERAGE)])
        text = json.dumps([(e.label, e.text, e.fields) for e in view]).lower()
        for word in ("investigation", "stale", "exists", "restricted"):
            self.assertNotIn(word, text)

    def test_when_existence_alone_is_permitted_every_attribute_of_the_record_is_invisible(self):
        baseline = project(self.KNOWN + [ExpectedInput("a", EXISTENCE_ONLY)], VIEWER, COVERAGE)
        for hidden in every_state(EXISTENCE_ONLY):
            self.assertEqual(project(self.KNOWN + [hidden], VIEWER, COVERAGE), baseline)

    def test_the_inaccessible_entry_carries_only_the_decisions_own_wording(self):
        view = project([ExpectedInput("vendor master", EXISTENCE_ONLY, **ATTRIBUTES[0])], VIEWER, COVERAGE)
        self.assertEqual([(e.label, e.text) for e in view], [("inaccessible", PERMITTED), ("coverage", COVERAGE)])


class TheGenericEntries(unittest.TestCase):
    def test_the_entry_is_built_from_the_decision_and_the_requests_own_entities(self):
        entry = gap_entry(EXISTENCE_ONLY, VIEWER, {"record_id": "AUTHZ-READ-LIMIT-0417", "version": "v1"})
        self.assertEqual(entry["state"], "inaccessible")
        self.assertEqual(entry["scope"]["entity_references"], list(ENTITIES))
        self.assertEqual(entry["permission_safe_summary"], PERMITTED)
        self.assertEqual(entry["materiality"], "unknown")

    def test_the_retrieval_unit_is_built_from_the_decision(self):
        unit = retrieval_entry(EXISTENCE_ONLY, {"record_id": "AUTHZ-READ-LIMIT-0417", "version": "v1"})
        self.assertEqual((unit["status"], unit["summary"], unit["summary_visibility"]), ("not_permitted", PERMITTED, "permission_safe"))

    def test_the_comparison_names_each_field_that_differs_including_extra_and_missing_ones(self):
        expected = {"a": 1, "b": {"c": 2, "d": [1]}, "e": "x"}
        self.assertEqual(differences(expected, copy.deepcopy(expected)), [])
        self.assertEqual(sorted(differences(expected, {"a": 1, "b": {"c": 3, "d": [1, 2]}, "z": 0})), [("/b/c", 2), ("/b/d", [1]), ("/e", "x"), ("/z", None)])


class TheExampleData(unittest.TestCase):
    def setUp(self):
        self.model = support.example_model()
        self.registry = self.model.registry

    def entries(self):
        return [x for inst in self.model.of("C03") + self.model.of("C04") for x in semantics._unreadable_entries(inst)]

    def test_every_unreadable_entry_is_exactly_what_the_projection_builds_from_its_decision(self):
        self.assertTrue(self.entries())
        for inst in self.model.of("C03") + self.model.of("C04"):
            viewer = semantics.viewer_of(self.model, inst)
            for loc, kind, ref, entry in semantics._unreadable_entries(inst):
                decision = Decision.from_registry(self.registry.permission_decisions["%s@%s" % (ref["record_id"], ref["version"])])
                expected = gap_entry(decision, viewer, ref) if kind == "gap" else retrieval_entry(decision, ref)
                self.assertEqual(entry, expected, inst.label() + loc)

    def test_a_source_whose_existence_is_withheld_appears_in_no_output(self):
        withheld = [k for k, v in self.registry.permission_decisions.items() if not v["disclose_existence_allowed"]]
        self.assertEqual(withheld, ["AUTHZ-READ-WITHHELD-0417@v1"])
        outputs = [json.dumps(inst.data) for inst in self.model.of("C01") + self.model.of("C03") + self.model.of("C04")]
        outputs += [json.dumps(render_response(self.model, packet)) for packet in self.model.of("C04")]
        blob = "\n".join(outputs).lower()
        for word in ("withheld", "investigation", "authz-read-withheld", "vendor master", "vendor-master"):
            self.assertNotIn(word, blob)

    def test_the_rendered_response_carries_only_the_permitted_wording_about_the_unreadable_part(self):
        for packet in self.model.of("C04"):
            statements = render_response(self.model, packet)["statements"]
            inaccessible = [s for s in statements if s["kind"] == "gap" and "(inaccessible)" in s["label"]]
            self.assertEqual([s["text"] for s in inaccessible], ["Inaccessible: " + PERMITTED])

    def test_the_identifiers_in_the_outputs_do_not_name_what_they_protect(self):
        blob = "\n".join(json.dumps(inst.data) for inst in self.model.of("C03") + self.model.of("C04"))
        for fragment in ("RESTRICTED", "DENY"):
            self.assertNotIn(fragment, blob)

    def test_the_two_selections_say_nothing_about_the_unreadable_retrieval_beyond_the_decision(self):
        for selection in self.model.of("C03"):
            unit = next(u for u in selection.data["retrieval"] if u["status"] == "not_permitted")
            self.assertEqual(unit["reason"], "Permission decision applies to this principal.", selection.label())


class SnapshotValidation(unittest.TestCase):
    """The validator checks a stored snapshot against the stored decisions. It is not an authorization service."""

    def setUp(self):
        self.model = support.example_model()

    def run_case(self, case_id):
        data = support.read_json("13-evaluation-cases/cases.json")
        data = dict(data, cases=[c for c in data["cases"] if c["case_id"] == case_id])
        problems, count = check_cases(self.model, support.schema(), data, support.EXAMPLES / "13-evaluation-cases" / "cases.json")
        self.assertEqual(count, 1)
        return [p.format() for p in problems]

    def codes(self, *mutations):
        model, _ = mutate_model(self.model, list(mutations))
        return sorted({f.code for f in semantics.check_disclosure(model)}), model

    def gap(self, path, value, packet="C04 PKT-0417 v1"):
        return {"target": packet, "ops": [{"op": "replace", "path": "/coverage_omissions_gaps/missingness/2" + path, "value": value}]}

    def test_the_example_set_has_no_disclosure_findings(self):
        self.assertEqual([f.code for f in semantics.check_disclosure(self.model)], [])

    def test_an_entry_for_a_source_whose_existence_is_withheld_is_found(self):
        self.assertEqual(self.run_case("CASE-DISC-02"), [])
        codes, _ = self.codes(self.gap("/permission_decision_reference/record_id", "AUTHZ-READ-WITHHELD-0417"))
        self.assertIn("DISC002", codes)

    def test_wording_beyond_the_permitted_words_is_found(self):
        self.assertEqual(self.run_case("CASE-DISC-03"), [])

    def test_an_entry_with_no_permission_decision_at_all_is_found(self):
        codes, _ = self.codes(self.gap("/permission_decision_reference/record_id", "AUTHZ-DOES-NOT-EXIST"))
        self.assertIn("DISC002", codes)

    def test_a_sibling_field_that_says_more_than_the_decision_is_found_whichever_field_it_is(self):
        leaks = {
            "/materiality": "decision_changing",
            "/expected_evidence": "A change to the supplier's bank details",
            "/reason": {"state": "known", "value": "An investigation opened on 2026-11-20 restricts three records."},
            "/assessment_basis": "Three restricted records, one of them stale.",
            "/scope/task": "Supplier bank-detail change",
            "/scope/entity_references": [{"entity_type": "bank_account", "entity_id": "BA-9"}],
            "/scope/units": {"state": "known", "value": "3 records"},
        }
        for path, value in leaks.items():
            with self.subTest(path):
                codes, model = self.codes(self.gap(path, value))
                self.assertIn("DISC003", codes)
                found = [f for f in semantics.check_disclosure(model) if f.code == "DISC003" and path in f.location]
                self.assertTrue(found, [f.location for f in semantics.check_disclosure(model)])

    def test_an_extra_field_beside_the_safe_one_is_found(self):
        model, _ = mutate_model(self.model, [{"target": "C04 PKT-0417 v1", "ops": [{"op": "add", "path": "/coverage_omissions_gaps/missingness/2/open_investigations", "value": 3}]}])
        found = [f for f in semantics.check_disclosure(model) if f.code == "DISC003"]
        self.assertEqual([f.location for f in found], ["/coverage_omissions_gaps/missingness/2/open_investigations"])

    def test_the_retrieval_unit_is_held_to_the_projection_too(self):
        for path, value in (("/reason", "Restricted source last refreshed 2026-11-10."), ("/authorized_scope", "Bank-detail source"), ("/attempted_at", {"state": "known", "value": "2026-11-23T09:50:00Z"})):
            with self.subTest(path):
                codes, _ = self.codes({"target": "C03 SEL-0417 v1", "ops": [{"op": "replace", "path": "/retrieval/7" + path, "value": value}]})
                self.assertIn("DISC003", codes)

    def test_a_finding_names_the_field_and_what_it_must_be_without_repeating_the_leak(self):
        _, model = self.codes(self.gap("/materiality", "decision_changing"))
        message = next(f.message for f in semantics.check_disclosure(model) if f.code == "DISC003")
        self.assertIn('must be "unknown"', message)
        self.assertNotIn("decision_changing", message)

    def test_a_decision_for_another_principal_does_not_allow_the_entry(self):
        model, _ = mutate_model(self.model, [])
        model.registry = copy.deepcopy(model.registry)
        model.registry.permission_decisions["AUTHZ-READ-LIMIT-0417@v1"]["principal"] = "person:ap-analyst-03"
        found = [f for f in semantics.check_disclosure(model) if f.code == "DISC004"]
        self.assertEqual(len(found), 6)  # the gap and the retrieval unit of each selection, and the gap of each packet
        self.assertTrue(all("person:ap-analyst-03" in f.message for f in found))
        self.assertEqual({f.code for f in semantics.check_disclosure(model)}, {"DISC004"})

    def test_a_decision_without_a_principal_binds_to_nobody(self):
        model, _ = mutate_model(self.model, [])
        model.registry = copy.deepcopy(model.registry)
        del model.registry.permission_decisions["AUTHZ-READ-LIMIT-0417@v1"]["principal"]
        self.assertEqual({f.code for f in semantics.check_disclosure(model)}, {"DISC004"})

    def test_a_decision_for_another_tenant_or_purpose_does_not_allow_the_entry(self):
        for key, value in (("tenant", "tenant:other"), ("purpose", "Marketing analytics")):
            with self.subTest(key):
                model, _ = mutate_model(self.model, [])
                model.registry = copy.deepcopy(model.registry)
                model.registry.permission_decisions["AUTHZ-READ-LIMIT-0417@v1"][key] = value
                self.assertEqual({f.code for f in semantics.check_disclosure(model)}, {"DISC004"})

    def test_a_decision_without_a_tenant_or_a_purpose_does_not_allow_the_entry_and_no_wording_is_shown(self):
        for key in ("tenant", "purpose"):
            for how in ("absent", "empty", "not text"):
                with self.subTest("%s %s" % (key, how)):
                    model, _ = mutate_model(self.model, [])
                    model.registry = copy.deepcopy(model.registry)
                    decision = model.registry.permission_decisions["AUTHZ-READ-LIMIT-0417@v1"]
                    if how == "absent":
                        del decision[key]
                    else:
                        decision[key] = "" if how == "empty" else 7
                    found = [f for f in semantics.check_disclosure(model) if f.code == "DISC004"]
                    self.assertEqual(len(found), 6)
                    self.assertTrue(all("names no %s" % key in f.message for f in found), [f.message for f in found])
                    packet = model.get("C04", "PKT-0417", "v1")
                    self.assertIsNone(semantics.permitted_wording(model, packet, {"record_id": "AUTHZ-READ-LIMIT-0417", "version": "v1"}))
                    self.assertEqual([s for s in render_response(model, packet)["statements"] if "(inaccessible)" in s["label"]], [])

    def test_a_decision_is_bound_to_the_context_the_output_names_not_to_a_default(self):
        _, model = self.codes({"target": "C01 CTX-0417 v1", "ops": [{"op": "replace", "path": "/identity_principal/requesting_principal", "value": "person:ap-analyst-09"}]})
        found = [f for f in semantics.check_disclosure(model) if f.code == "DISC004"]
        self.assertTrue(found)
        self.assertTrue(all("v1" in f.file or "0417" in f.file for f in found))

    def test_an_output_without_a_readable_context_cannot_be_bound(self):
        _, model = self.codes({"target": "C03 SEL-0417 v1", "ops": [{"op": "replace", "path": "/identity_scope/context_reference/id", "value": "CTX-NONE"}]})
        found = [f for f in semantics.check_disclosure(model) if f.code == "DISC004"]
        self.assertTrue(found)
        self.assertIn("no readable C01 context", found[0].message)

    def test_a_record_of_another_tenant_or_purpose_may_not_be_named(self):
        for path, value, expect in (("/disclosure_permissions/tenant", "tenant:other", "tenant"), ("/disclosure_permissions/purpose", "Marketing analytics", "purpose")):
            with self.subTest(path):
                codes, model = self.codes({"target": "C02 GR-5521 v1", "ops": [{"op": "replace", "path": path, "value": value}]})
                self.assertIn("DISC005", codes)
                self.assertIn(expect, next(f.message for f in semantics.check_disclosure(model) if f.code == "DISC005"))

    def test_the_protected_term_scan_is_a_backstop_that_still_works(self):
        codes, _ = self.codes({"target": "C04 PKT-0417 v1", "ops": [{"op": "replace", "path": "/coverage_omissions_gaps/visible_scoped_limitation_summary", "value": "Includes a vendor master change."}]})
        self.assertIn("DISC001", codes)

    def test_free_text_beside_the_entries_is_outside_what_the_validator_can_judge_and_the_documents_say_so(self):
        """The limit is documented, not hidden: restricted detail in free text without a protected term passes, and two pages say that it does."""
        summary = {"target": "C04 PKT-0417 v1", "ops": [{"op": "replace", "path": "/coverage_omissions_gaps/visible_scoped_limitation_summary", "value": "Three restricted records are older than a month."}]}
        codes, _ = self.codes(summary)
        self.assertNotIn("DISC001", codes, "no protected term is used, so the backstop does not see it")
        for page in ("architecture/lineage-selection-disclosure.md", "examples/04-selection-and-missingness/README.md"):
            text = (support.REPO / page).read_text(encoding="utf-8")
            self.assertIn("free text", text, page)
            self.assertIn("DISC001", text, page)


class TheViewIsBuiltFromAuthorizedInputs(unittest.TestCase):
    """The response renderer takes its wording from the permission decision, never from the packet's own entry."""

    def setUp(self):
        self.model = support.example_model()
        self.packet = self.model.get("C04", "PKT-0417", "v1")

    def mutated(self, *ops):
        model, _ = mutate_model(self.model, [{"target": "C04 PKT-0417 v1", "ops": list(ops)}])
        return model, model.get("C04", "PKT-0417", "v1")

    def test_text_added_to_the_packet_entry_does_not_reach_the_rendered_response(self):
        model, packet = self.mutated({"op": "replace", "path": "/coverage_omissions_gaps/missingness/2/permission_safe_summary", "value": "Three restricted records are stale."})
        rendered = json.dumps(render_response(model, packet)).lower()
        self.assertNotIn("restricted", rendered)
        self.assertIn(PERMITTED.lower(), rendered)

    def test_a_gap_the_decision_does_not_let_the_viewer_know_about_is_not_rendered_at_all(self):
        model, packet = self.mutated({"op": "replace", "path": "/coverage_omissions_gaps/missingness/2/permission_decision_reference/record_id", "value": "AUTHZ-READ-WITHHELD-0417"})
        statements = render_response(model, packet)["statements"]
        self.assertEqual([s for s in statements if "(inaccessible)" in s["label"]], [])
        self.assertEqual([f.code for f in check_structural(model, render_response(model, packet), "r.json")], [])

    def test_a_withheld_gap_leaves_no_gap_in_the_numbering_and_the_text_is_the_same_as_without_it(self):
        """What the reader sees must not depend on whether a gap they may not know of exists: not the text, and not the numbers that count the gaps."""
        withheld_model, withheld = self.mutated({"op": "replace", "path": "/coverage_omissions_gaps/missingness/2/permission_decision_reference/record_id", "value": "AUTHZ-READ-WITHHELD-0417"})
        absent_model, absent = self.mutated({"op": "remove", "path": "/coverage_omissions_gaps/missingness/2"})

        def seen(model, packet):
            return [(s["kind"], s["label"], s["text"]) for s in render_response(model, packet)["statements"]]
        self.assertEqual(seen(withheld_model, withheld), seen(absent_model, absent))
        numbers = [label.split(" ")[1] for kind, label, _ in seen(withheld_model, withheld) if kind == "gap"]
        self.assertEqual(numbers, ["1", "2", "3", "4", "5", "6"])

    def test_a_response_that_mentions_such_a_gap_is_refused(self):
        model, packet = self.mutated({"op": "replace", "path": "/coverage_omissions_gaps/missingness/2/permission_decision_reference/record_id", "value": "AUTHZ-READ-WITHHELD-0417"})
        response = render_response(self.model, self.packet)
        found = [f.code for f in check_structural(model, response, "r.json")]
        self.assertEqual(found, ["RESP017"])

    def test_a_free_form_statement_about_the_unreadable_part_must_use_the_permitted_wording(self):
        response = json.loads(json.dumps(support.read_json("06-assistant-response/response-PKT-0417-v1-model-style.json")))
        gap = self.restricted_statement(response)
        self.assertEqual([f.code for f in check_structural(self.model, response, "r.json")], [])
        self.assertEqual(gap["text"], PERMITTED)
        gap["text"] = "Inaccessible: part of the scope is restricted, and an investigation file is open."
        self.assertEqual([f.code for f in check_structural(self.model, response, "r.json")], ["RESP017"])

    @staticmethod
    def restricted_statement(response):
        return next(s for s in response["statements"] if s["kind"] == "gap" and s["refs"] == ["/coverage_omissions_gaps/missingness/2"])

    def test_nothing_may_be_added_before_or_after_the_permitted_wording(self):
        for label, text in (("a figure after", PERMITTED + " Three restricted records are stale."), ("a status after", PERMITTED + " An investigation is open."), ("a count in brackets", PERMITTED + " (2 sources)"),
                            ("a note on a new line", PERMITTED + "\n\nNote: a legal hold applies."), ("a sentence before", "Several restricted sources exist. " + PERMITTED),
                            ("the wording quoted inside a longer sentence", "The reader is told: %s This was last reviewed as material." % PERMITTED)):
            with self.subTest(label):
                response = json.loads(json.dumps(support.read_json("06-assistant-response/response-PKT-0417-v1-model-style.json")))
                self.restricted_statement(response)["text"] = text
                self.assertIn("RESP017", [f.code for f in check_structural(self.model, response, "r.json")])

    def test_the_permitted_wording_may_start_with_the_missingness_label(self):
        for text in (PERMITTED, "Inaccessible: " + PERMITTED, "inaccessible:   " + PERMITTED.upper()):
            with self.subTest(text[:30]):
                response = json.loads(json.dumps(support.read_json("06-assistant-response/response-PKT-0417-v1-model-style.json")))
                self.restricted_statement(response)["text"] = text
                self.assertEqual([f.code for f in check_structural(self.model, response, "r.json")], [])

    def test_the_unreadable_part_does_not_share_a_statement_with_another_gap(self):
        response = json.loads(json.dumps(support.read_json("06-assistant-response/response-PKT-0417-v1-model-style.json")))
        statement = self.restricted_statement(response)
        statement["refs"] = ["/coverage_omissions_gaps/missingness/2", "/coverage_omissions_gaps/missingness/0"]
        statement["text"] = "Missing: carrier proof of delivery for a second pallet of 40 units. " + PERMITTED
        self.assertIn("RESP017", [f.code for f in check_structural(self.model, response, "r.json")])

    def test_the_canonical_comparison_catches_extra_detail_about_the_unreadable_part(self):
        response = render_response(self.model, self.packet)
        gap = next(s for s in response["statements"] if "(inaccessible)" in s["label"])
        gap["text"] += " Three restricted records are stale."
        from eahs.response import check_response
        self.assertTrue({"RESP101", "RESP102"} & {f.code for f in check_response(self.model, response, "r.json")})

    def test_the_label_of_a_statement_about_the_unreadable_part_names_only_its_place(self):
        """The label is shown beside the text. A label that says "Restricted: 27 named records" discloses what the text does not."""
        for label in ("Restricted: 27 named records", "restricted", "gap 3 with 27 sources", "gap 3 (stale)", "gap 3 (inaccessible) - an investigation is open", "27"):
            with self.subTest(label):
                response = json.loads(json.dumps(support.read_json("06-assistant-response/response-PKT-0417-v1-model-style.json")))
                self.restricted_statement(response)["label"] = label
                found = [f for f in check_structural(self.model, response, "r.json") if f.code == "RESP017"]
                self.assertEqual(len(found), 1, [f.message for f in found])
                self.assertIn("label", found[0].message)

    def test_the_labels_that_only_say_where_the_gap_is_or_are_the_permitted_wording_pass(self):
        for label in ("gap 3", "gap 3 (inaccessible)", "Gap 12 ( Inaccessible )", "inaccessible", PERMITTED, "Inaccessible: " + PERMITTED):
            with self.subTest(label):
                response = json.loads(json.dumps(support.read_json("06-assistant-response/response-PKT-0417-v1-model-style.json")))
                self.restricted_statement(response)["label"] = label
                self.assertEqual([f.code for f in check_structural(self.model, response, "r.json")], [])

    def test_a_citation_of_a_part_of_the_unreadable_gap_is_a_citation_of_the_gap(self):
        """A statement that cites the gap's expected evidence, not the gap, used to escape the rule: the pointer resolved to a string, not to a gap."""
        gap = "/coverage_omissions_gaps/missingness/2"
        for part in ("expected_evidence", "reason", "scope", "scope/task", "permission_decision_reference"):
            with self.subTest(part):
                response = json.loads(json.dumps(support.read_json("06-assistant-response/response-PKT-0417-v1-model-style.json")))
                response["statements"].append({"kind": "gap", "label": "restricted", "text": "There are 27 restricted records.", "refs": ["%s/%s" % (gap, part)]})
                found = [f for f in check_structural(self.model, response, "r.json") if f.code == "RESP017"]
                self.assertEqual(len(found), 2, [f.message for f in found])
                self.assertTrue(any("exactly the wording" in f.message for f in found))
                self.assertTrue(any("label" in f.message for f in found))

    def test_a_citation_of_a_part_of_a_gap_that_may_not_be_known_is_refused_too(self):
        model, _ = mutate_model(self.model, [{"target": "C04 PKT-0417 v1", "ops": [{"op": "replace", "path": "/coverage_omissions_gaps/missingness/2/permission_decision_reference/record_id", "value": "AUTHZ-READ-WITHHELD-0417"}]}])
        response = json.loads(json.dumps(support.read_json("06-assistant-response/response-PKT-0417-v1-model-style.json")))
        response["statements"] = [s for s in response["statements"] if s["refs"] != ["/coverage_omissions_gaps/missingness/2"]]
        response["statements"].append({"kind": "gap", "label": "gap 3", "text": "There are 27 restricted records.", "refs": ["/coverage_omissions_gaps/missingness/2/expected_evidence"]})
        found = [f for f in check_structural(model, response, "r.json") if f.code == "RESP017"]
        self.assertEqual(len(found), 1, [f.message for f in found])
        self.assertIn("may not be mentioned", found[0].message)

    def test_a_citation_of_a_part_of_a_readable_gap_is_unaffected(self):
        response = json.loads(json.dumps(support.read_json("06-assistant-response/response-PKT-0417-v1-model-style.json")))
        response["statements"].append({"kind": "gap", "label": "gap 1", "text": "Missing: carrier proof of delivery for a second pallet.", "refs": ["/coverage_omissions_gaps/missingness/0/expected_evidence"]})
        self.assertEqual([f for f in check_structural(self.model, response, "r.json") if f.code == "RESP017"], [])


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
        positions = [page.index(step) for step in ("bind the permission decision", "may know that", "safe-disclosure policy", "classify only", "expose only")]
        self.assertEqual(positions, sorted(positions))

    def test_the_documents_keep_snapshot_validation_enforcement_and_projection_apart_and_deny_being_an_authorization_service(self):
        page = self.text("architecture/lineage-selection-disclosure.md").lower()
        for phrase in ("snapshot validation", "authorization enforcement", "viewer projection", "not an authorization service"):
            self.assertTrue(phrase in page, "the architecture page lacks %r" % phrase)
        import eahs.disclosure as disclosure
        for phrase in ("SNAPSHOT VALIDATION", "AUTHORIZATION ENFORCEMENT", "VIEWER PROJECTION", "not an authorization service"):
            self.assertTrue(phrase in disclosure.__doc__, "the module doc lacks %r" % phrase)


if __name__ == "__main__":
    unittest.main()
