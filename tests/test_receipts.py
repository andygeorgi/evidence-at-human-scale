"""Three outcomes stay apart, and a verified outcome is verified for one attempt, one target and one action.

Rejected before submission is what the gateway did. Verified no effect is what an authoritative check found for this attempt,
target and scope. Outcome unknown is what nobody has found out yet. A gateway rejection alone is not proof about every
external effect, so a receipt may say `not_executed_verified` only from a verification of its own target and action, made
after the attempt.
"""
import unittest

import support  # noqa: F401  (puts scripts/ on the path)

from eahs.cases import run_case

REJECTED = "C07 RCP-REL-0417-A v1"
UNKNOWN = "C07 RCP-REL-0417-B v1"
RECONCILED = "C07 RCP-REL-0417-B v2"
CHECK = "/verification_recovery/verification"


def after(target, *ops):
    """The codes the whole pipeline (schema, then semantics) reports once the operations are applied to the receipt."""
    codes, _ = run_case(support.example_model(), support.schema(), {"mutations": [{"target": target, "ops": list(ops)}]})
    return codes


def rep(path, value):
    return {"op": "replace", "path": path, "value": value}


class TheThreeOutcomes(unittest.TestCase):
    def setUp(self):
        self.model = support.example_model()
        self.rejected = self.model.get("C07", "RCP-REL-0417-A", "v1").data
        self.unknown = self.model.get("C07", "RCP-REL-0417-B", "v1").data

    def test_a_rejection_before_submission_is_a_verified_no_effect_only_through_its_own_verification(self):
        outcome, check = self.rejected["outcome"], self.rejected["verification_recovery"]["verification"]
        binding = self.rejected["identity_binding"]
        self.assertEqual((outcome["state"], outcome["no_effect_basis"]), ("not_executed_verified", "rejection"))
        self.assertEqual(check["state"], "authoritatively_verified")
        self.assertEqual((check["target"], check["action_reference"]), (binding["target"], binding["proposal_reference"]))
        self.assertEqual(check["scope"], "Declared target and action only")
        self.assertGreaterEqual(check["time"], outcome["timestamps"]["submitted"])

    def test_the_receipt_says_what_the_gateway_did_and_what_the_check_found_as_two_statements(self):
        reason = self.rejected["outcome"]["reason"]
        self.assertTrue(reason.startswith("Rejected before submission by the action gateway:"), reason)
        self.assertIn("Verified afterwards for this attempt, target and scope only", reason)

    def test_a_timeout_is_an_unknown_outcome_not_a_verified_no_effect(self):
        self.assertEqual(self.unknown["outcome"]["state"], "unknown")
        self.assertEqual(self.unknown["verification_recovery"]["verification"]["state"], "pending")
        self.assertEqual(self.unknown["verification_recovery"]["verification"]["authoritative_outcome_references"], [])
        self.assertEqual(after(UNKNOWN, rep("/outcome/state", "not_executed_verified")), ["SCH002"])


class AVerificationIsForOneAttempt(unittest.TestCase):
    def test_the_example_receipts_pass(self):
        for receipt in (REJECTED, RECONCILED):
            self.assertEqual(after(receipt), [], receipt)

    def test_a_check_of_another_target_shows_nothing_about_this_one(self):
        self.assertEqual(after(REJECTED, rep(CHECK + "/target/entity_id", "INV-2026-9999")), ["AUTH008"])

    def test_a_check_of_another_action_shows_nothing_about_this_one(self):
        self.assertEqual(after(REJECTED, rep(CHECK + "/action_reference/version", "v2")), ["AUTH008"])
        self.assertEqual(after(RECONCILED, rep(CHECK + "/action_reference", {"contract_id": "C05", "id": "ACT-HOLD-0417", "version": "v1"})), ["AUTH008"])

    def test_the_record_a_verification_cites_must_be_for_the_same_target_and_action(self):
        reference = CHECK + "/authoritative_outcome_references/0"
        self.assertEqual(after(REJECTED, rep(reference + "/target/entity_id", "INV-2026-9999")), ["AUTH008"])
        self.assertEqual(after(REJECTED, rep(reference + "/action_reference/version", "v2")), ["AUTH008"])

    def test_a_check_made_before_the_attempt_cannot_show_what_the_attempt_did(self):
        self.assertEqual(after(REJECTED, rep(CHECK + "/time", "2026-11-23T15:59:59Z")), ["AUTH008"])
        self.assertEqual(after(RECONCILED, rep(CHECK + "/time", "2026-11-23T16:00:04Z")), ["AUTH008"])

    def test_a_check_made_at_the_moment_of_the_attempt_is_not_before_it(self):
        self.assertEqual(after(REJECTED, rep(CHECK + "/time", "2026-11-23T16:00:00Z")), [])

    def test_the_finding_names_the_problem_and_where_it_is(self):
        _, findings = run_case(support.example_model(), support.schema(), {"mutations": [{"target": REJECTED, "ops": [rep(CHECK + "/target/entity_id", "INV-2026-9999")]}]})
        found = [f for f in findings if f.code == "AUTH008"]
        self.assertEqual(len(found), 1)
        self.assertIn("own target (invoice INV-2026-0417)", found[0].message)
        self.assertIn("INV-2026-9999", found[0].message)
        self.assertEqual(found[0].location, CHECK + "/target")


if __name__ == "__main__":
    unittest.main()
