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

    def test_a_registry_without_roles_does_not_make_the_role_check_pass_silently(self):
        model, _ = mutate_model(self.model, [])
        model.registry = copy.deepcopy(model.registry)
        model.registry.accountability = {}
        found = semantics.check_accountability(model)
        self.assertEqual([f.code for f in found], ["ROLE005"])
        self.assertIn("cannot be checked", found[0].message)

    def test_a_folder_with_nothing_to_check_has_nothing_to_report(self):
        model, _ = mutate_model(self.model, [])
        model.registry = copy.deepcopy(model.registry)
        model.registry.accountability = {}
        model.instances = {k: v for k, v in model.instances.items() if k[0] not in ("C04", "C06", "C07")}
        self.assertEqual(semantics.check_accountability(model), [])

    def test_receipts_and_grants_with_no_roles_registered_are_not_passed_silently_either(self):
        model, _ = mutate_model(self.model, [])
        model.registry = copy.deepcopy(model.registry)
        model.registry.accountability = {}
        model.instances = {k: v for k, v in model.instances.items() if k[0] not in ("C04",)}
        found = semantics.check_accountability(model)
        self.assertEqual([f.code for f in found], ["ROLE005"])
        self.assertIn("executor of", found[0].message)

    def test_the_declared_cases_produce_exactly_their_codes(self):
        data = support.read_json("13-evaluation-cases/cases.json")
        data = dict(data, cases=[c for c in data["cases"] if c["family"] == "roles"])
        self.assertEqual(len(data["cases"]), 3)
        problems, _ = check_cases(self.model, support.schema(), data, support.EXAMPLES / "13-evaluation-cases" / "cases.json")
        self.assertEqual([p.format() for p in problems], [])


class TheExecutorReceivesAuthority(unittest.TestCase):
    """The assistant proposes, the executor receives authority, and only the grantee acts under a grant.

    Both grant shapes follow the same rule: an exact approval covers one proposal version and a bounded class covers a
    class of actions, but each names the registered executor as its grantee, and each receipt is made by that grantee.
    """

    EXECUTOR, ASSISTANT = "workload:payment-executor", "workload:ap-assistant"

    def setUp(self):
        self.model = support.example_model()

    def mutated(self, *mutations):
        model, _ = mutate_model(self.model, [{"target": t, "ops": [{"op": "replace", "path": p, "value": v}]} for t, p, v in mutations])
        return model

    def test_every_grant_of_either_shape_names_the_executor_as_its_grantee(self):
        shapes = set()
        for grant in self.model.of("C06"):
            shapes.add(grant.data["scope_binding"]["binding"]["binding_type"])
            self.assertEqual(grant.data["identity_principals"]["grantee"], self.EXECUTOR, grant.label())
        self.assertEqual(shapes, {"exact_proposal", "bounded_class"})

    def test_every_receipt_is_made_by_the_grantee_of_the_grant_it_cites(self):
        self.assertTrue(self.model.of("C07"))
        for receipt in self.model.of("C07"):
            ref = receipt.data["identity_binding"]["grant_reference"]
            grant = self.model.get("C06", ref["id"], ref["version"])
            self.assertEqual(receipt.data["identity_binding"]["executor"], grant.data["identity_principals"]["grantee"], receipt.label())

    def test_the_assistant_workload_is_the_requestors_tool_and_never_a_grantee_or_an_executor(self):
        assistants = {c.data["identity_principal"]["workload_identity"] for c in self.model.of("C01")}
        self.assertEqual(assistants, {self.ASSISTANT})
        for grant in self.model.of("C06"):
            self.assertNotIn(grant.data["identity_principals"]["grantee"], assistants)
        for receipt in self.model.of("C07"):
            self.assertNotIn(receipt.data["identity_binding"]["executor"], assistants)

    def test_the_grantee_holds_the_executor_role_the_registry_names(self):
        executors = set(self.model.registry.accountability["roles"]["executor"]["principals"])
        self.assertEqual(executors, {self.EXECUTOR})
        self.assertEqual({g.data["identity_principals"]["grantee"] for g in self.model.of("C06")}, executors)

    def test_the_two_shapes_stay_distinct(self):
        exact = self.model.get("C06", "GRT-APPR-0417-A", "v1").data["scope_binding"]["binding"]
        bounded = self.model.get("C06", "GRT-CLASS-HOLD", "v1").data["scope_binding"]["binding"]
        self.assertEqual((exact["binding_type"], bounded["binding_type"]), ("exact_proposal", "bounded_class"))
        self.assertIn("proposal_reference", exact)
        self.assertNotIn("proposal_reference", bounded)
        self.assertIn("class_id", bounded)

    def test_a_receipt_made_by_another_principal_does_not_validate_under_the_grant(self):
        for who, expected in ((self.ASSISTANT, ["ROLE006", "ROLE008"]), ("workload:other-executor", ["ROLE006", "ROLE007"]), ("person:ap-controller-01", ["ROLE006", "ROLE007"])):
            with self.subTest(who):
                model = self.mutated(("C07 RCP-HOLD-0417 v1", "/identity_binding/executor", who))
                self.assertEqual(codes_of(model), expected)

    def test_the_hold_receipt_under_the_bounded_class_and_the_release_receipt_under_an_exact_approval_are_both_held_to_it(self):
        for receipt in ("C07 RCP-HOLD-0417 v1", "C07 RCP-REL-0417-B v2"):
            self.assertIn("ROLE006", codes_of(self.mutated((receipt, "/identity_binding/executor", "workload:other-executor"))), receipt)

    def test_a_grant_to_the_assistant_workload_is_refused_for_either_shape(self):
        for grant in ("C06 GRT-CLASS-HOLD v1", "C06 GRT-APPR-0417-A v1"):
            with self.subTest(grant):
                found = [f for f in semantics.check_accountability(self.mutated((grant, "/identity_principals/grantee", self.ASSISTANT))) if f.code == "ROLE008"]
                self.assertEqual(len(found), 1)
                self.assertIn("the assistant proposes, and the executor receives authority", found[0].message)

    def test_a_grantee_that_is_not_a_registered_executor_is_refused(self):
        found = [f for f in semantics.check_accountability(self.mutated(("C06 GRT-CLASS-LOWVAL v2", "/identity_principals/grantee", "workload:unregistered"))) if f.code == "ROLE007"]
        self.assertEqual(len(found), 1)
        self.assertIn("workload:unregistered", found[0].message)

    def test_changing_the_grantee_alone_leaves_the_receipts_that_cite_the_grant_disagreeing(self):
        model = self.mutated(("C06 GRT-APPR-0417-B v1", "/identity_principals/grantee", "workload:other-executor"))
        self.assertEqual(codes_of(model), ["ROLE006", "ROLE006", "ROLE007"])

    def test_the_registry_can_register_another_executor_and_then_it_may_receive_authority(self):
        model = self.mutated(("C06 GRT-CLASS-LOWVAL v2", "/identity_principals/grantee", "workload:second-executor"))
        model.registry = copy.deepcopy(model.registry)
        model.registry.accountability["roles"]["executor"]["principals"].append("workload:second-executor")
        self.assertEqual(codes_of(model), [])

    def test_the_declared_executor_is_what_the_generator_writes(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("build_example_data", support.SCRIPTS / "build_example_data.py")
        builder = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(builder)
        self.assertEqual((builder.EXECUTOR, builder.ASSISTANT), (self.EXECUTOR, self.ASSISTANT))
        grants = builder.build_grants(*builder.build_instances()[:1], builder.build_proposals(builder.build_instances()[0]))
        self.assertEqual({g["identity_principals"]["grantee"] for g in grants.values()}, {self.EXECUTOR})


def codes_of(model):
    return sorted(f.code for f in semantics.check_accountability(model))


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
