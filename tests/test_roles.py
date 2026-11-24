"""The worked example keeps four roles apart, and its timeline agrees with them.

The requestor asks for a packet and reads it. The Decision Owner, the accountable reviewer, reviews the packet and owns the
decision. The approver issues the exact approval. The executor performs the action. One person holds two roles only where the
registry says the policy allows it, and no one reviews or approves on the requestor's behalf.
"""
import copy
import json
import re
import unittest

import support  # noqa: F401  (puts scripts/ on the path)

from eahs import semantics
from eahs.cases import check_cases, mutate_model
from eahs.gateway import ts

ANALYST, CONTROLLER = "person:ap-analyst-02", "person:ap-controller-01"


def codes(model):
    return sorted({f.code for f in semantics.check_accountability(model)})


class TheRegistry(unittest.TestCase):
    def setUp(self):
        self.accountability = support.example_model().registry.accountability
        self.roles = self.accountability["roles"]

    def holders(self, role):
        entry = self.roles[role]
        return set(entry.get("holders", entry.get("principals", [])))

    def test_four_roles_are_named(self):
        self.assertEqual(sorted(self.roles), ["approver", "decision_owner", "executor", "requestor"])

    def test_the_requestor_holds_neither_the_decision_owner_nor_the_approver_role(self):
        self.assertEqual(self.holders("requestor"), {ANALYST})
        self.assertEqual(self.holders("requestor") & (self.holders("decision_owner") | self.holders("approver")), set())

    def test_the_only_combination_the_policy_allows_is_decision_owner_with_approver(self):
        self.assertEqual(self.accountability["may_hold_together"], [["decision_owner", "approver"]])
        self.assertEqual(self.holders("decision_owner"), {CONTROLLER})
        self.assertEqual(self.holders("approver"), {CONTROLLER})

    def test_the_executor_is_a_workload_not_a_person(self):
        self.assertTrue(all(p.startswith("workload:") for p in self.holders("executor")))


class TheExampleSet(unittest.TestCase):
    def setUp(self):
        self.model = support.example_model()

    def test_there_are_no_role_findings(self):
        self.assertEqual(codes(self.model), [])

    def test_the_requestor_of_every_context_is_the_analyst_and_never_an_approver_or_reviewer(self):
        for context in self.model.of("C01"):
            self.assertEqual(context.data["identity_principal"]["requesting_principal"], ANALYST, context.label())
        for grant in self.model.of("C06"):
            self.assertNotEqual(grant.data["identity_principals"]["issuer"], ANALYST, grant.label())
        for packet in self.model.of("C04"):
            actor = packet.data["review_version_history"]["actor"].get("value")
            self.assertNotEqual(actor, ANALYST, packet.label())

    def test_the_second_packet_is_reviewed_by_the_decision_owner_before_the_second_approval(self):
        packet = self.model.get("C04", "PKT-0417", "v2")
        history = packet.data["review_version_history"]
        self.assertEqual((history["state"], history["actor"]["value"]), ("reviewed", CONTROLLER))
        approval = self.model.get("C06", "GRT-APPR-0417-B", "v1")
        self.assertLess(ts(history["time"]["value"]), ts(approval.data["identity_principals"]["issuance_time"]))

    def test_the_first_packet_was_reviewed_by_the_decision_owner_before_the_first_approval(self):
        log = {e["packet"]: e for e in self.model.registry.accountability["review_log"]}
        approval = self.model.get("C06", "GRT-APPR-0417-A", "v1")
        review = log["PKT-0417 v1"]
        self.assertEqual(review["actor"], CONTROLLER)
        self.assertLess(ts(review["time"]), ts(approval.data["identity_principals"]["issuance_time"]))
        self.assertEqual(approval.data["identity_principals"]["issuer"], CONTROLLER)

    def test_no_file_calls_the_requestor_a_reviewer(self):
        offenders = [str(p.relative_to(support.REPO)) for p in support.EXAMPLES.rglob("*.json") if "ap-reviewer" in p.read_text(encoding="utf-8")]
        self.assertEqual(offenders, [])


class TheChecksFireOnPurpose(unittest.TestCase):
    def setUp(self):
        self.model = support.example_model()

    def mutated(self, target, path, value):
        model, _ = mutate_model(self.model, [{"target": target, "ops": [{"op": "replace", "path": path, "value": value}]}])
        return model

    def test_the_requestor_cannot_approve_their_own_request(self):
        model = self.mutated("C06 GRT-APPR-0417-B v1", "/identity_principals/issuer", ANALYST)
        self.assertEqual(codes(model), ["ROLE001", "ROLE002"])

    def test_someone_who_is_not_an_approver_cannot_approve(self):
        model = self.mutated("C06 GRT-APPR-0417-B v1", "/identity_principals/issuer", "person:ap-clerk-07")
        self.assertEqual(codes(model), ["ROLE001"])

    def test_the_requestor_cannot_be_the_reviewer(self):
        model = self.mutated("C04 PKT-0417 v2", "/review_version_history/actor/value", ANALYST)
        self.assertEqual(codes(model), ["ROLE003"])

    def test_a_review_that_the_log_does_not_record_is_found(self):
        model = self.mutated("C04 PKT-0417 v2", "/review_version_history/time/value", "2026-11-23T15:11:00Z")
        self.assertEqual(codes(model), ["ROLE003"])

    def test_an_approval_before_the_review_is_found(self):
        model = self.mutated("C06 GRT-APPR-0417-B v1", "/identity_principals/issuance_time", "2026-11-23T15:00:00Z")
        self.assertEqual(codes(model), ["ROLE004"])

    def test_one_person_may_hold_both_roles_only_where_the_registry_says_so(self):
        model = self.mutated("C06 GRT-APPR-0417-B v1", "/identity_principals/issuer", ANALYST)
        model.registry = copy.deepcopy(model.registry)  # the example model is shared: never change its registry in place
        model.registry.accountability["may_hold_together"] = [["requestor", "approver"]]
        self.assertNotIn("ROLE002", codes(model))

    def test_the_declared_cases_produce_exactly_their_codes(self):
        data = support.read_json("13-evaluation-cases/cases.json")
        data = dict(data, cases=[c for c in data["cases"] if c["family"] == "roles"])
        self.assertEqual(len(data["cases"]), 3)
        problems, _ = check_cases(self.model, support.schema(), data, support.EXAMPLES / "13-evaluation-cases" / "cases.json")
        self.assertEqual([p.format() for p in problems], [])


class TheNarrative(unittest.TestCase):
    def text(self, relative):
        return (support.EXAMPLES / relative).read_text(encoding="utf-8")

    def test_the_conventions_name_the_four_roles_and_the_policy_that_allows_one_person_two_of_them(self):
        readme = self.text("README.md")
        people = readme.split("- **People.**", 1)[1].split("\n- **", 1)[0]
        for phrase in ("requestor", "Decision Owner", "approver", "executor", "accountable reviewer", "the registry says so explicitly"):
            self.assertIn(phrase, people)
        self.assertIn("does not let the requestor hold either role", people)

    def test_every_review_in_the_log_appears_in_the_story_before_its_approval(self):
        log = support.example_model().registry.accountability["review_log"]
        story = self.text("README.md").split("## The story", 1)[1].split("## Folder map", 1)[0]
        rows = [line for line in story.splitlines() if line.startswith("| ")]

        def index(hhmm):
            return next(i for i, r in enumerate(rows) if r.split("|")[1].strip().startswith(hhmm))
        for entry in log:
            row = rows[index(entry["time"][11:16])]
            self.assertIn("controller", row)
            self.assertIn("reviews", row)
        approvals = {"PKT-0417 v1": "10:40", "PKT-0417 v2": "15:20"}
        for entry in log:
            self.assertLess(index(entry["time"][11:16]), index(approvals[entry["packet"]]))
            self.assertIn("approval", rows[index(approvals[entry["packet"]])])

    def test_the_late_correction_page_does_not_say_the_requestor_reviewed_the_packet(self):
        page = self.text("11-late-correction/README.md")
        self.assertNotIn("The reviewer", page)
        self.assertIn("controller, as Decision Owner, reviews packet v2", page)


if __name__ == "__main__":
    unittest.main()
