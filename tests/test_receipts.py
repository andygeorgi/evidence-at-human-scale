"""Three outcomes stay apart, and a verified outcome is verified for one attempt, one target and one action.

Rejected before submission is what the gateway did. Verified no effect is what an authoritative check found for this attempt,
target and scope. Outcome unknown is what nobody has found out yet. A gateway rejection alone is not proof about every
external effect, so a receipt may say `not_executed_verified` only from a verification of its own target and action, made
after the attempt.
"""
import copy
import unittest

import support  # noqa: F401  (puts scripts/ on the path)

from eahs import semantics
from eahs.cases import run_case
from eahs.gateway import ledger_from_receipts, regressive_receipt_versions, ts
from eahs.model import Instance, Model

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


class EveryVersionOfAReceiptIsHeldToTheDecision(unittest.TestCase):
    """The attempt is the same in every version, so the gateway's decision is too. The first version used to be the only one compared with it."""

    RELEASE_B = "C07 RCP-REL-0417-B v2"        # the attempt the gateway allows: completed and verified in this version
    LATER = [rep("/outcome/state", "not_executed_verified"), rep("/outcome/observed_effects", []), {"op": "add", "path": "/outcome/no_business_effect", "value": True},
             {"op": "add", "path": "/outcome/reason", "value": "Not executed."}]

    def codes(self, *ops):
        return [c for c in after(self.RELEASE_B, *ops) if c.startswith(("AUTH00", "ACC00"))]

    def test_a_later_version_that_calls_an_allowed_attempt_a_rejection_is_found(self):
        self.assertEqual(self.codes(*self.LATER, {"op": "add", "path": "/outcome/no_effect_basis", "value": "rejection"}), ["AUTH007"])

    def test_a_later_version_that_says_no_effect_for_another_reason_is_not(self):
        for basis in ("cancellation", "failed_before_effect"):
            with self.subTest(basis):
                self.assertEqual(self.codes(*self.LATER, {"op": "add", "path": "/outcome/no_effect_basis", "value": basis}), [])

    def test_a_later_version_that_cites_a_check_the_gateway_passes_is_found(self):
        reason = {"op": "add", "path": "/outcome/reason", "value": "Rejected before submission by the action gateway: GRANT_EXPIRED."}
        self.assertEqual(self.codes(*self.LATER[:-1], reason, {"op": "add", "path": "/outcome/no_effect_basis", "value": "cancellation"}), ["AUTH007"])

    def test_a_later_version_that_says_the_action_ran_when_the_gateway_blocks_it_is_found(self):
        """Receipt A is the attempt the gateway blocks (a revoked grant). A second version that says it was completed contradicts the decision."""
        import copy
        from eahs import semantics
        from eahs.model import Instance, Model
        base = support.example_model()
        first = base.get("C07", "RCP-REL-0417-A", "v1")
        data = copy.deepcopy(first.data)
        data["outcome"]["state"] = "completed_verified"
        data["identity_binding"]["receipt_version"] = "v2"
        instances = dict(base.instances)
        instances[("C07", first.id, "v2")] = Instance(first.contract, first.id, "v2", data, first.path)
        found = [(f.code, f.location) for f in semantics.check_authority(Model(instances, base.registry, base.root)) if f.code in ("AUTH004", "AUTH005", "AUTH007")]
        self.assertEqual(found, [("AUTH004", "/outcome/state")])

    def test_a_later_version_that_moves_the_attempt_in_time_describes_another_attempt(self):
        """The verification and the record it cites are held to the attempt of their own version, so moving that attempt moves the bar. The attempt does not move."""
        found = after_all({"target": self.RELEASE_B, "ops": [rep("/outcome/timestamps/submitted", "2026-11-23T16:00:04Z")]},
                          {"target": "C02 BANK-STMT-0042 v1", "ops": [rep("/times/event/value", "2026-11-23T16:00:04Z")]})
        self.assertIn("ACC004", found)

    def test_the_stored_versions_agree_with_the_first(self):
        from eahs import semantics
        self.assertEqual([f for f in semantics.check_authority(support.example_model()) if f.code in ("AUTH004", "AUTH005", "AUTH007", "ACC004")], [])


class AReceiptThatCitesACheckTheGatewayPassesIsFoundAlsoWhenTheGatewayBlocksForOtherReasons(unittest.TestCase):
    """The receipt of the queued release says why the gateway rejected it. A reason that names a check which did not fail is wrong, even though the attempt was rejected."""

    def test_an_extra_code_is_found_and_the_real_ones_are_not(self):
        from eahs import semantics
        from eahs.cases import mutate_model
        reason = "Rejected before submission by the action gateway: GRANT_REVOKED, EVIDENCE_NOT_CURRENT, EVIDENCE_STALE, PRECONDITION_FAILED, GRANT_EXPIRED."
        model, _ = mutate_model(support.example_model(), [{"target": REJECTED, "ops": [rep("/outcome/reason", reason)]}])
        found = [f for f in semantics.check_authority(model) if f.code == "AUTH007"]
        self.assertEqual(len(found), 1)
        self.assertIn("GRANT_EXPIRED", found[0].message)
        self.assertNotIn("GRANT_REVOKED", found[0].message.split("(it fails")[0])
        self.assertEqual(found[0].location, "/outcome/reason")

    def test_dropping_a_real_code_is_still_a_missing_reason_and_not_an_extra_one(self):
        reason = "Rejected before submission by the action gateway: GRANT_REVOKED, EVIDENCE_NOT_CURRENT, EVIDENCE_STALE."
        self.assertEqual(after(REJECTED, rep("/outcome/reason", reason)), ["AUTH005"])

    def test_a_required_code_is_named_whole_and_not_by_a_longer_name_that_starts_with_it(self):
        """GRANT_REVOKED_LEGACY is not GRANT_REVOKED: the receipt that writes it names no check that failed."""
        reason = "Rejected before submission by the action gateway: GRANT_REVOKED_LEGACY, EVIDENCE_NOT_CURRENT, EVIDENCE_STALE, PRECONDITION_FAILED."
        self.assertEqual(after(REJECTED, rep("/outcome/reason", reason)), ["AUTH005"])
        wrong_end = "Rejected before submission by the action gateway: GRANT_REVOKED, EVIDENCE_NOT_CURRENT_AT_ALL, EVIDENCE_STALE, PRECONDITION_FAILED."
        self.assertEqual(after(REJECTED, rep("/outcome/reason", wrong_end)), ["AUTH005"])


class TheSameInstantWrittenAnotherWayIsTheSameAttempt(unittest.TestCase):
    """A later version of a receipt describes the same attempt when it names the same instant, however the time is written. Instants are compared, not spellings."""

    LATER = "C07 RCP-REL-0417-B v2"

    def chain(self, value):
        from eahs import semantics
        from eahs.cases import mutate_model
        model, _ = mutate_model(support.example_model(), [{"target": self.LATER, "ops": [rep("/outcome/timestamps/submitted", value)]}])
        return [f.code for f in semantics.check_authority(model) if f.code == "ACC004"]

    def test_another_spelling_of_the_same_instant_is_not_another_attempt(self):
        for value in ("2026-11-23T17:00:05+01:00", "2026-11-23T16:00:05.000Z", "2026-11-23T16:00:05.000000+00:00"):
            with self.subTest(value):
                self.assertEqual(self.chain(value), [])

    def test_another_instant_is_another_attempt(self):
        for value in ("2026-11-23T16:00:06Z", "2026-11-23T16:00:05.000001Z", "2026-11-23T16:00:05+01:00"):
            with self.subTest(value):
                self.assertEqual(self.chain(value), ["ACC004"])

    def test_a_later_version_whose_time_cannot_be_compared_is_an_input_error_like_the_first(self):
        """The same damage to the first version is INP002 with the receipt named. A later version is not judged as a receipt that merely differs."""
        from eahs import semantics
        from eahs.cases import mutate_model
        for value in ("2026-11-23T16:00:05.0000001Z", "not a time", "2026-11-23T16:00:05"):
            with self.subTest(value):
                model, _ = mutate_model(support.example_model(), [{"target": self.LATER, "ops": [rep("/outcome/timestamps/submitted", value)]}])
                with self.assertRaises(ValueError) as caught:
                    semantics.check_authority(model)
                self.assertIn("RCP-REL-0417-B v2", str(caught.exception))
                self.assertIn("c07-RCP-REL-0417-B-v2.json", str(caught.exception))
                self.assertIn("Correct the time", str(caught.exception))

    def test_a_reference_that_does_not_resolve_does_not_hide_a_time_that_cannot_be_compared(self):
        """The first version cites a proposal that does not exist, so nothing can be replayed. The later version's time is still an input that cannot be judged, and is named."""
        from eahs import semantics
        from eahs.cases import mutate_model
        unresolved = {"target": "C07 RCP-REL-0417-B v1", "ops": [rep("/identity_binding/proposal_reference/version", "v9")]}
        model, _ = mutate_model(support.example_model(), [unresolved])
        self.assertEqual([f for f in semantics.check_authority(model) if f.code.startswith(("AUTH004", "AUTH005", "AUTH007", "AUTH009"))], [], "the receipt is left alone when it cannot be replayed")
        model, _ = mutate_model(support.example_model(), [unresolved, {"target": self.LATER, "ops": [rep("/outcome/timestamps/submitted", "2026-11-23T16:00:05.0000001Z")]}])
        with self.assertRaises(ValueError) as caught:
            semantics.check_authority(model)
        self.assertIn("c07-RCP-REL-0417-B-v2.json", str(caught.exception))
        self.assertIn("2026-11-23T16:00:05.0000001Z", str(caught.exception))


class AnAttemptTimeThatCannotBeComparedIsRejectedWithTheReceiptNamed(unittest.TestCase):
    """A fraction finer than a microsecond cannot be compared with the grant and the evidence exactly. The stage reports an input error that names the receipt."""

    def test_the_diagnostic_names_the_file_the_receipt_and_the_time(self):
        from eahs import semantics
        from eahs.cases import mutate_model
        model, _ = mutate_model(support.example_model(), [{"target": REJECTED, "ops": [rep("/outcome/timestamps/submitted", "2026-11-23T16:00:00.0000001Z")]}])
        with self.assertRaises(ValueError) as caught:
            semantics.check_authority(model)
        message = str(caught.exception)
        self.assertIn("c07-RCP-REL-0417-A-v1.json", message)
        self.assertIn("RCP-REL-0417-A v1", message)
        self.assertIn("2026-11-23T16:00:00.0000001Z", message)
        self.assertIn("Correct the time", message)


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


class AVerifiedOutcomeClosesTheAttempt(unittest.TestCase):
    """A later ordinary version of a receipt may repeat a verified outcome and may not go back from it. The replay of the ledger keeps the verified outcome.

    Unknown and then completed is the reconciliation of the stored receipt, and it stays valid. No correction of a verified outcome is defined for the
    ordinary versions of a receipt, so a version that says otherwise is reported and is not the state that the ledger replays.
    """

    B, A = "RCP-REL-0417-B", "RCP-REL-0417-A"
    UNRESOLVED = ("submitted", "unknown", "partial")
    BEFORE_RECONCILIATION, AFTER_RECONCILIATION, LATER = "2026-11-23T16:10:00Z", "2026-11-23T16:21:00Z", "2026-11-23T16:30:00Z"

    def with_version(self, receipt_id, copies, version, state=None):
        """The example set with one more version of a receipt: a copy of version `copies`, which says `state` when one is given."""
        base = support.example_model()
        source = base.get("C07", receipt_id, copies)
        data = copy.deepcopy(source.data)
        data["identity_binding"]["version"] = version
        if state is not None:
            data["outcome"]["state"] = state
        path = source.path.with_name(source.path.name.replace("-%s.json" % copies, "-%s.json" % version))
        instances = dict(base.instances)
        instances[("C07", receipt_id, version)] = Instance("C07", receipt_id, version, data, path)
        return Model(instances, base.registry, base.root)

    def regressions(self, model):
        return [(f.file.replace("\\", "/").rsplit("/", 1)[-1], f.location) for f in semantics.check_authority(model) if f.code == "ACC005"]

    def held(self, model, at):
        return sorted((entry.receipt, entry.state) for entry in ledger_from_receipts(model, ts(at)) if entry.receipt == self.B)

    def test_unknown_then_completed_is_the_reconciliation_and_not_a_regression(self):
        model = support.example_model()
        self.assertEqual([model.get("C07", self.B, version).data["outcome"]["state"] for version in ("v1", "v2")], ["unknown", "completed_verified"])
        self.assertEqual(self.regressions(model), [])
        self.assertEqual(regressive_receipt_versions(model), [])

    def test_the_attempt_is_reserved_until_the_verified_outcome_is_available_and_consumed_after(self):
        model = support.example_model()
        self.assertEqual(self.held(model, self.BEFORE_RECONCILIATION), [(self.B, "reserved")])
        for at in (self.AFTER_RECONCILIATION, self.LATER):
            self.assertEqual(self.held(model, at), [(self.B, "consumed")])

    def test_a_later_version_that_goes_back_to_unknown_is_found(self):
        model = self.with_version(self.B, "v1", "v3")
        self.assertEqual(self.regressions(model), [("c07-RCP-REL-0417-B-v3.json", "/outcome/state")])
        self.assertEqual([(later.version, earlier.version) for later, earlier in regressive_receipt_versions(model)], [("v3", "v2")])
        message = next(f.message for f in semantics.check_authority(model) if f.code == "ACC005")
        for part in ("this version says unknown", "version v2", "completed_verified"):
            self.assertIn(part, message)

    def test_a_history_that_goes_back_is_not_the_state_the_ledger_replays(self):
        """The third version is invalid and is reported. The replay keeps the verified outcome: the attempt stays consumed, and is not read as reserved again."""
        stored, regressive = support.example_model(), self.with_version(self.B, "v1", "v3")
        for at in (self.BEFORE_RECONCILIATION, self.AFTER_RECONCILIATION, self.LATER):
            with self.subTest(at):
                self.assertEqual(self.held(regressive, at), self.held(stored, at))
        self.assertEqual(self.held(regressive, self.LATER), [(self.B, "consumed")])
        self.assertTrue(self.regressions(regressive), "and the history is reported")

    def test_a_verified_outcome_cannot_go_back_to_an_unresolved_one(self):
        for state in self.UNRESOLVED:
            with self.subTest(state):
                self.assertEqual(self.regressions(self.with_version(self.B, "v2", "v3", state)), [("c07-RCP-REL-0417-B-v3.json", "/outcome/state")])

    def test_a_verified_no_effect_cannot_go_back_to_an_unresolved_one_either(self):
        for state in self.UNRESOLVED:
            with self.subTest(state):
                self.assertEqual(self.regressions(self.with_version(self.A, "v1", "v2", state)), [("c07-RCP-REL-0417-A-v2.json", "/outcome/state")])

    def test_one_verified_outcome_cannot_become_the_other(self):
        self.assertEqual(self.regressions(self.with_version(self.B, "v2", "v3", "not_executed_verified")), [("c07-RCP-REL-0417-B-v3.json", "/outcome/state")])
        self.assertEqual(self.regressions(self.with_version(self.A, "v1", "v2", "completed_verified")), [("c07-RCP-REL-0417-A-v2.json", "/outcome/state")])

    def test_a_later_version_may_repeat_the_verified_outcome(self):
        model = self.with_version(self.B, "v2", "v3")
        self.assertEqual(self.regressions(model), [])
        self.assertEqual(self.held(model, self.LATER), [(self.B, "consumed")])

    def test_the_stage_reports_a_regression_in_a_receipt_file_added_to_the_folder(self):
        import json
        import shutil
        import tempfile
        from pathlib import Path

        import validate_examples as ve
        from eahs.status import FAIL
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "examples"
            shutil.copytree(support.EXAMPLES, root)
            source = next(root.rglob("c07-RCP-REL-0417-B-v1.json"))
            data = json.loads(source.read_text(encoding="utf-8"))
            data["identity_binding"]["version"] = "v3"
            (source.parent / "c07-RCP-REL-0417-B-v3.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
            stage = next(result for result in ve.run(root, only={"semantics"}) if result.stage == "semantics")
        self.assertEqual((stage.status, sorted({f.code for f in stage.findings})), (FAIL, ["ACC005"]))


if __name__ == "__main__":
    unittest.main()
