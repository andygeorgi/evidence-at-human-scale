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


def after_all(*mutations):
    """The codes the whole pipeline reports once every mutation (each a target and its operations) is applied."""
    codes, _ = run_case(support.example_model(), support.schema(), {"mutations": list(mutations)})
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
        # The verification, the record it cites and that record's admission all happen at the moment of the attempt.
        record = "C02 ERP-PAYMENTS-QUERY-0417-A v1"
        at = "2026-11-23T16:00:00Z"
        codes, _ = run_case(support.example_model(), support.schema(), {"mutations": [
            {"target": REJECTED, "ops": [rep(CHECK + "/time", at)]},
            {"target": record, "ops": [rep("/times/event/value", at), rep("/times/ingestion", at), rep("/producer_admission/admission_time", at)]}]})
        self.assertEqual(codes, [])


class AReceiptIsForItsProposalsTarget(unittest.TestCase):
    """A verification can show only what happened to the receipt's own target, so the receipt's target must be the one its proposal names."""

    ELSEWHERE = {"entity_type": "invoice", "entity_id": "INV-2026-9999"}

    def test_a_receipt_whose_every_target_field_agrees_on_another_invoice_is_still_refused(self):
        """The receipt, its verification, the reference it cites and the record that reference points to all name INV-2026-9999. Only the proposal says otherwise."""
        mutations = [{"target": REJECTED, "ops": [rep("/identity_binding/target", self.ELSEWHERE), rep(CHECK + "/target", self.ELSEWHERE),
                                                  rep(CHECK + "/authoritative_outcome_references/0/target", self.ELSEWHERE)]},
                     {"target": "C02 ERP-PAYMENTS-QUERY-0417-A v1", "ops": [rep("/scope/entity_references", [self.ELSEWHERE])]}]
        codes, findings = run_case(support.example_model(), support.schema(), {"mutations": mutations})
        self.assertEqual(codes, ["AUTH009"])
        self.assertEqual(len(findings), 1)
        self.assertIn("INV-2026-9999", findings[0].message)
        self.assertIn("INV-2026-0417", findings[0].message)
        self.assertEqual(findings[0].location, "/identity_binding/target")

    def test_the_other_receipts_name_their_proposals_target_and_any_other_is_found(self):
        self.assertEqual(after_all(), [])
        self.assertIn("AUTH009", after("C07 RCP-HOLD-0417 v1", rep("/identity_binding/target", self.ELSEWHERE)))
        self.assertIn("AUTH009", after("C07 RCP-REL-0417-B v1", rep("/identity_binding/target", self.ELSEWHERE)))

    def test_a_target_of_another_kind_is_another_target(self):
        supplier = {"entity_type": "supplier", "entity_id": "S-1042"}
        self.assertIn("AUTH009", after(REJECTED, rep("/identity_binding/target", supplier)))

    def test_a_later_version_cannot_move_to_another_target_either(self):
        """The first version is held to its proposal, and each later version to the first, so the chain cannot drift."""
        self.assertIn("ACC004", after(RECONCILED, rep("/identity_binding/target", self.ELSEWHERE)))


class ARejectionIsARejectionOnlyIfTheGatewayRejected(unittest.TestCase):
    """A rejection reserves nothing. A receipt that calls an attempt the gateway allows a rejection would free the capacity that attempt holds."""

    def findings(self, basis):
        from eahs import semantics
        from eahs.cases import mutate_model
        mutations = [{"target": "C07 RCP-HOLD-0417 v1", "ops": [rep("/outcome/state", "not_executed_verified"),
                                                                 {"op": "add", "path": "/outcome/no_effect_basis", "value": basis}, {"op": "add", "path": "/outcome/reason", "value": "Not executed."}]}]
        model, _ = mutate_model(support.example_model(), mutations)
        return [f for f in semantics.check_authority(model) if f.code == "AUTH007"]

    def test_a_rejection_that_the_gateway_would_not_have_made_is_found(self):
        found = self.findings("rejection")
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].location, "/outcome/no_effect_basis")
        self.assertIn("passes it", found[0].message)

    def test_a_cancellation_or_a_failure_before_any_effect_does_not_claim_a_rejection(self):
        for basis in ("cancellation", "failed_before_effect"):
            with self.subTest(basis):
                self.assertEqual(self.findings(basis), [])

    def test_the_stored_rejection_is_one_the_gateway_would_have_made(self):
        from eahs import semantics
        self.assertEqual([f for f in semantics.check_authority(support.example_model()) if f.code in ("AUTH004", "AUTH005", "AUTH007")], [])


class TheRecordsAVerificationCites(unittest.TestCase):
    """The labels of a verification are not enough: the record it cites must be about the target and must come from after the attempt."""

    RECORD = "C02 ERP-PAYMENTS-QUERY-0417-A v1"   # observed 16:00:20, admitted 16:00:21; the attempt is at 16:00:00 and the verification at 16:00:25

    def record(self, *ops):
        return after_all({"target": self.RECORD, "ops": list(ops)})

    def test_an_observation_made_before_the_attempt_cannot_show_what_the_attempt_did(self):
        self.assertEqual(self.record(rep("/times/event/value", "2026-11-23T15:59:59Z")), ["AUTH008"])

    def test_an_observation_at_exactly_the_attempt_time_or_the_verification_time_is_allowed(self):
        self.assertEqual(self.record(rep("/times/event/value", "2026-11-23T16:00:00Z")), [])
        self.assertEqual(self.record(rep("/times/event/value", "2026-11-23T16:00:21Z")), [])

    def test_a_verification_cannot_rest_on_an_observation_made_after_it(self):
        codes, findings = run_case(support.example_model(), support.schema(), {"mutations": [
            {"target": self.RECORD, "ops": [rep("/times/event/value", "2026-11-23T16:00:26Z"), rep("/times/ingestion", "2026-11-23T16:00:21Z")]}]})
        self.assertEqual(codes, ["AUTH008"])
        self.assertIn("cannot rest on an observation made after it", [f.message for f in findings if f.code == "AUTH008"][0])

    def test_a_record_the_verification_could_not_yet_have_is_refused(self):
        for label, op in (("admitted later", rep("/producer_admission/admission_time", "2026-11-23T16:00:26Z")), ("ingested later", rep("/times/ingestion", "2026-11-23T16:00:26Z")),
                          ("not admitted", rep("/producer_admission/admission_status", "quarantined"))):
            with self.subTest(label):
                self.assertEqual(self.record(op), ["AUTH008"])

    def test_an_observation_with_no_known_time_cannot_be_shown_to_come_from_after_the_attempt(self):
        unknown = {"state": "unknown", "reason": "The source did not record it."}
        self.assertEqual(self.record(rep("/times/event", unknown)), ["AUTH008"])
        self.assertEqual(after_all({"target": self.RECORD, "ops": [rep("/times/event/value", "later")]}), ["SCH002"])

    def test_a_record_about_another_invoice_verifies_nothing_about_this_one(self):
        elsewhere = [{"entity_type": "invoice", "entity_id": "INV-2026-9999"}]
        codes, findings = run_case(support.example_model(), support.schema(), {"mutations": [{"target": self.RECORD, "ops": [rep("/scope/entity_references", elsewhere)]}]})
        self.assertIn("AUTH008", codes)
        self.assertIn("not about the receipt's own target", [f.message for f in findings if f.code == "AUTH008"][0])

    def test_the_other_verified_receipts_cite_records_from_after_their_attempts(self):
        self.assertEqual(after_all(), [])
        for record, change in (("C02 ERP-HOLD-QUERY-0417 v1", rep("/times/event/value", "2026-11-23T10:02:59Z")), ("C02 BANK-STMT-0042 v1", rep("/times/event/value", "2026-11-23T16:00:04Z"))):
            with self.subTest(record):
                self.assertEqual(after_all({"target": record, "ops": [change]}), ["AUTH008"])

    def test_a_verification_rests_on_an_observation_and_not_on_something_derived_or_inferred(self):
        from eahs import semantics
        from eahs.cases import mutate_model
        for kind in ("deterministic_finding", "model_inference"):
            with self.subTest(kind):
                model, _ = mutate_model(support.example_model(), [{"target": self.RECORD, "ops": [rep("/identity_schema/kind", kind)]}])
                found = [f for f in semantics.check_authority(model) if f.code == "AUTH008"]
                self.assertEqual(len(found), 1, [f.message for f in found])
                self.assertIn("source record assertion", found[0].message)

    def test_what_the_cited_record_says_is_not_judged_and_the_documents_say_so(self):
        """A record about the right target and the right moment that says the opposite passes: its claim is free text. The limit is stated, not hidden."""
        from eahs import semantics
        self.assertIn("What the cited record SAYS is not judged", semantics._check_verification_binding.__doc__)
        for page in ("contracts/c07-execution-receipt.md", "examples/08-blocked-action/README.md", "architecture/action-and-degradation.md"):
            self.assertIn("what the cited record says", (support.REPO / page).read_text(encoding="utf-8").lower().replace("\n", " "), page)

    def test_the_finding_names_the_problem_and_where_it_is(self):
        _, findings = run_case(support.example_model(), support.schema(), {"mutations": [{"target": REJECTED, "ops": [rep(CHECK + "/target/entity_id", "INV-2026-9999")]}]})
        found = [f for f in findings if f.code == "AUTH008"]
        self.assertEqual(len(found), 1)
        self.assertIn("own target (invoice INV-2026-0417)", found[0].message)
        self.assertIn("INV-2026-9999", found[0].message)
        self.assertEqual(found[0].location, CHECK + "/target")


if __name__ == "__main__":
    unittest.main()
