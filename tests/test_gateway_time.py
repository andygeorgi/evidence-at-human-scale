"""Temporal integrity at commit: a decision uses only what was available and valid at the attempt.

The reference check separates five times. The business event time says when something happened. The admission time
says when the system could first rely on a record of it. Freshness compares the event time with the attempt. The
lifecycle state applies from its effective time. A revocation observation counts from the time it was made. A time
that equals the attempt time was reached when the attempt was made. A time that is missing or unknown blocks.
"""
import copy
import dataclasses
import unittest

import support  # noqa: F401  (puts scripts/ on the path)

from eahs import semantics
from eahs.cases import mutate_model
from eahs.gateway import GATE_CODES, LedgerEntry, attempt_receipt_ids, evaluate_commit, ledger_from_receipts, parse_time, ts

HOLD, HOLD_GRANT = ("ACT-HOLD-0417", "v1"), ("GRT-CLASS-HOLD", "v1")
RELEASE_B, APPROVAL_B = ("ACT-REL-0417", "v2"), ("GRT-APPR-0417-B", "v1")
RELEASE_A, APPROVAL_A = ("ACT-REL-0417", "v1"), ("GRT-APPR-0417-A", "v1")
UNKNOWN = {"state": "unknown", "reason": "The producing system did not record this time."}


def replace(target, path, value):
    return {"target": target, "ops": [{"op": "replace", "path": path, "value": value}]}


def remove(target, path):
    return {"target": target, "ops": [{"op": "remove", "path": path}]}


def add(target, path, value):
    return {"target": target, "ops": [{"op": "add", "path": path, "value": value}]}


def unique(codes):
    return list(dict.fromkeys(codes))


def decide(proposal, grant, at, *mutations, ledger=False):
    """The reference decision at `at`, with in-memory mutations applied to a copy of the example set.

    With `ledger`, the capacity already held comes from the receipts, except the receipt of the attempt itself (a replay never charges an attempt against itself).
    """
    model, _ = mutate_model(support.example_model(), list(mutations))
    p, g = model.get("C05", *proposal), model.get("C06", *grant)
    entries = ledger_from_receipts(model, ts(at), exclude_receipt_ids=attempt_receipt_ids(model, p, g, ts(at))) if ledger else []
    return evaluate_commit(model, p, g, ts(at), entries)


def revocation_checked_at(value, grant="C06 GRT-CLASS-HOLD v1"):
    return replace(grant, "/limits_lifecycle/revocation/checked_at", value)


def admitted_at(value, record="C02 M3W-0417 v1"):
    return replace(record, "/producer_admission/admission_time", value)


class TheStoredStory(unittest.TestCase):
    """The attempts that the examples describe keep their decisions."""

    def test_the_hold_at_10_03_is_still_allowed(self):
        decision = decide(HOLD, HOLD_GRANT, "2026-11-23T10:03:00Z", ledger=True)
        self.assertEqual((decision.allow, decision.codes), (True, []))

    def test_the_corrected_release_is_still_allowed(self):
        decision = decide(RELEASE_B, APPROVAL_B, "2026-11-23T16:00:05Z")
        self.assertEqual((decision.allow, decision.codes), (True, []))

    def test_the_queued_release_is_still_blocked_for_its_own_reasons(self):
        decision = decide(RELEASE_A, APPROVAL_A, "2026-11-23T16:00:00Z")
        self.assertEqual(unique(decision.codes), ["GRANT_REVOKED", "EVIDENCE_NOT_CURRENT", "EVIDENCE_STALE", "PRECONDITION_FAILED"])

    def test_an_expired_approval_is_still_blocked(self):
        decision = decide(RELEASE_B, APPROVAL_B, "2026-11-23T16:00:05Z", replace("C06 GRT-APPR-0417-B v1", "/limits_lifecycle/expiry", "2026-11-23T16:00:00Z"))
        self.assertEqual(decision.codes, ["GRANT_EXPIRED"])

    def test_a_retry_while_the_outcome_is_unknown_is_still_blocked(self):
        decision = decide(RELEASE_B, APPROVAL_B, "2026-11-23T16:10:00Z", ledger=True)
        self.assertEqual(decision.codes, ["CUMULATIVE_LIMIT"])

    def test_the_stored_evaluations_name_the_two_attempts_the_task_describes(self):
        entries = {e["label"]: e for e in support.read_json("07-authority-and-delegation/gateway-scenarios.json")["evaluations"]}
        early = entries["A hold at 09:30, before the match result was admitted"]
        self.assertEqual((early["at"], early["expect"]["decision"], early["expect"]["codes"]), ("2026-11-23T09:30:00Z", "BLOCK", ["EVIDENCE_NOT_YET_ADMITTED"]))
        late = entries["A hold at 10:03 when the only revocation check was made at 10:04"]
        self.assertEqual((late["at"], late["expect"]["decision"], late["expect"]["codes"]), ("2026-11-23T10:03:00Z", "BLOCK", ["REVOCATION_NOT_YET_OBSERVED"]))
        self.assertEqual(late["overrides"], [{"on": "grant", "path": "/limits_lifecycle/revocation/checked_at", "value": "2026-11-23T10:04:00Z"}])


class EvidenceAdmission(unittest.TestCase):
    def test_evidence_admitted_after_the_attempt_blocks_it(self):
        # The match result M3W-0417 v1 was admitted at 09:36.
        decision = decide(HOLD, HOLD_GRANT, "2026-11-23T09:30:00Z")
        self.assertEqual((decision.allow, decision.codes), (False, ["EVIDENCE_NOT_YET_ADMITTED"]))
        self.assertIn("M3W-0417 v1", decision.reasons[0].message)

    def test_an_event_that_happened_before_the_attempt_is_not_available_until_it_is_admitted(self):
        # The rule ran at 09:35 (the event) and its result was admitted at 09:36.
        record = support.example_model().get("C02", "M3W-0417", "v1").data
        self.assertEqual(record["times"]["event"]["value"], "2026-11-23T09:35:00Z")
        decision = decide(HOLD, HOLD_GRANT, "2026-11-23T09:35:30Z")
        self.assertEqual(decision.codes, ["EVIDENCE_NOT_YET_ADMITTED"])

    def test_admission_at_exactly_the_attempt_time_is_available(self):
        self.assertEqual(decide(HOLD, HOLD_GRANT, "2026-11-23T09:36:00Z").codes, [])

    def test_admission_one_second_after_the_attempt_is_not(self):
        self.assertEqual(decide(HOLD, HOLD_GRANT, "2026-11-23T09:35:59Z").codes, ["EVIDENCE_NOT_YET_ADMITTED"])

    def test_ingestion_after_the_attempt_blocks_even_if_admission_does_not(self):
        decision = decide(HOLD, HOLD_GRANT, "2026-11-23T10:03:00Z", replace("C02 M3W-0417 v1", "/times/ingestion", "2026-11-23T10:03:01Z"))
        self.assertEqual(decision.codes, ["EVIDENCE_NOT_YET_ADMITTED"])

    def test_a_record_that_was_not_admitted_does_not_count(self):
        decision = decide(HOLD, HOLD_GRANT, "2026-11-23T10:03:00Z", replace("C02 M3W-0417 v1", "/producer_admission/admission_status", "quarantined"))
        self.assertEqual(decision.codes, ["EVIDENCE_NOT_YET_ADMITTED"])
        self.assertIn("quarantined", decision.reasons[0].message)

    def test_a_precondition_cannot_rest_on_evidence_that_was_not_yet_admitted(self):
        decision = decide(RELEASE_B, APPROVAL_B, "2026-11-23T16:00:05Z", admitted_at("2026-11-23T16:00:06Z", "C02 M3W-0417 v2"))
        self.assertEqual(decision.codes, ["EVIDENCE_NOT_YET_ADMITTED", "PRECONDITION_FAILED"])

    def test_every_unknown_admission_time_blocks(self):
        for label, value in (("tagged unknown", UNKNOWN), ("null", None), ("empty", ""), ("no zone", "2026-11-23T09:36:00"), ("not a time", "yesterday"), ("a number", 936)):
            with self.subTest(label):
                decision = decide(HOLD, HOLD_GRANT, "2026-11-23T10:03:00Z", admitted_at(value))
                self.assertEqual((decision.allow, decision.codes), (False, ["EVIDENCE_TIME_UNKNOWN"]))

    def test_a_missing_admission_time_blocks(self):
        model, _ = mutate_model(support.example_model(), [])
        record = model.get("C02", "M3W-0417", "v1")
        data = {k: (dict(v) if isinstance(v, dict) else v) for k, v in record.data.items()}
        del data["producer_admission"]["admission_time"]
        model.instances[record.key] = type(record)(record.contract, record.id, record.version, data, record.path)
        decision = evaluate_commit(model, model.get("C05", *HOLD), model.get("C06", *HOLD_GRANT), ts("2026-11-23T10:03:00Z"), [])
        self.assertEqual(decision.codes, ["EVIDENCE_TIME_UNKNOWN"])

    def test_an_unknown_event_time_blocks_when_a_freshness_policy_applies(self):
        decision = decide(RELEASE_B, APPROVAL_B, "2026-11-23T16:00:05Z", replace("C02 SCR-S1042 v2", "/times/event", UNKNOWN))
        self.assertIn("EVIDENCE_TIME_UNKNOWN", decision.codes)
        self.assertFalse(decision.allow)


class EvidenceLifecycle(unittest.TestCase):
    """GR-5521 v1 was superseded at 13:40. Its state at an attempt depends on the attempt time only."""

    def superseded(self, at):
        decision = decide(RELEASE_A, APPROVAL_A, at)
        return [r for r in decision.reasons if r.code == "EVIDENCE_NOT_CURRENT" and r.message.startswith("GR-5521 v1")]

    def test_the_record_is_current_just_before_the_state_took_effect(self):
        self.assertEqual(self.superseded("2026-11-23T13:39:59Z"), [])

    def test_the_state_applies_at_exactly_its_effective_time(self):
        self.assertEqual(len(self.superseded("2026-11-23T13:40:00Z")), 1)

    def test_an_unknown_effective_time_blocks(self):
        decision = decide(HOLD, HOLD_GRANT, "2026-11-23T10:03:00Z", replace("C02 GR-5521 v1", "/lifecycle/effective_time", UNKNOWN))
        self.assertEqual((decision.allow, decision.codes), (False, ["EVIDENCE_TIME_UNKNOWN"]))

    def test_a_record_that_became_current_after_the_attempt_was_not_current_at_it(self):
        decision = decide(HOLD, HOLD_GRANT, "2026-11-23T10:03:00Z", replace("C02 INV-2026-0417 v1", "/lifecycle/effective_time", "2026-11-23T10:04:00Z"))
        self.assertEqual(decision.codes, ["EVIDENCE_NOT_CURRENT"])
        self.assertIn("became current", decision.reasons[0].message)


class RevocationObservation(unittest.TestCase):
    def test_a_clear_observation_recorded_after_the_attempt_cannot_authorize_it(self):
        decision = decide(HOLD, HOLD_GRANT, "2026-11-23T10:03:00Z", revocation_checked_at("2026-11-23T10:04:00Z"))
        self.assertEqual((decision.allow, decision.codes), (False, ["REVOCATION_NOT_YET_OBSERVED"]))

    def test_an_observation_at_exactly_the_attempt_time_is_available(self):
        self.assertEqual(decide(HOLD, HOLD_GRANT, "2026-11-23T10:03:00Z", revocation_checked_at("2026-11-23T10:03:00Z")).codes, [])

    def test_an_observation_one_second_after_the_attempt_is_not(self):
        decision = decide(HOLD, HOLD_GRANT, "2026-11-23T10:03:00Z", revocation_checked_at("2026-11-23T10:03:01Z"))
        self.assertEqual(decision.codes, ["REVOCATION_NOT_YET_OBSERVED"])

    def test_a_revocation_seen_later_does_not_authorize_an_earlier_attempt_either(self):
        # GRT-APPR-0417-A was revoked at 13:45. The only observation on record is later than an attempt at 11:00.
        decision = decide(RELEASE_A, APPROVAL_A, "2026-11-23T11:00:00Z")
        self.assertIn("REVOCATION_NOT_YET_OBSERVED", decision.codes)
        self.assertNotIn("GRANT_REVOKED", decision.codes)
        self.assertFalse(decision.allow)

    def test_a_revocation_observed_at_exactly_the_attempt_time_revokes(self):
        self.assertIn("GRANT_REVOKED", decide(RELEASE_A, APPROVAL_A, "2026-11-23T13:45:00Z").codes)

    def test_every_unknown_observation_time_blocks(self):
        for label, value in (("tagged unknown", UNKNOWN), ("null", None), ("empty", ""), ("no zone", "2026-11-23T07:45:00"), ("not a time", "later")):
            with self.subTest(label):
                decision = decide(HOLD, HOLD_GRANT, "2026-11-23T10:03:00Z", revocation_checked_at(value))
                self.assertEqual((decision.allow, decision.codes), (False, ["REVOCATION_TIME_UNKNOWN"]))

    def test_a_revoked_observation_with_no_time_blocks_too(self):
        decision = decide(HOLD, HOLD_GRANT, "2026-11-23T10:03:00Z", revocation_checked_at(UNKNOWN), replace("C06 GRT-CLASS-HOLD v1", "/limits_lifecycle/revocation/state", "revoked"))
        self.assertEqual(decision.codes, ["REVOCATION_TIME_UNKNOWN"])

    def test_an_unverifiable_state_still_blocks_when_its_time_is_known(self):
        decision = decide(HOLD, HOLD_GRANT, "2026-11-23T10:03:00Z", replace("C06 GRT-CLASS-HOLD v1", "/limits_lifecycle/revocation/state", "check_unavailable"))
        self.assertEqual(decision.codes, ["REVOCATION_UNVERIFIED"])


class GrantValidity(unittest.TestCase):
    def test_a_grant_issued_at_exactly_the_attempt_time_is_valid(self):
        self.assertEqual(decide(HOLD, HOLD_GRANT, "2026-11-23T10:03:00Z", replace("C06 GRT-CLASS-HOLD v1", "/identity_principals/issuance_time", "2026-11-23T10:03:00Z")).codes, [])

    def test_a_grant_issued_one_second_after_the_attempt_is_not(self):
        decision = decide(HOLD, HOLD_GRANT, "2026-11-23T10:03:00Z", replace("C06 GRT-CLASS-HOLD v1", "/identity_principals/issuance_time", "2026-11-23T10:03:01Z"))
        self.assertEqual(decision.codes, ["GRANT_NOT_YET_VALID"])

    def test_a_grant_is_expired_at_exactly_its_expiry(self):
        decision = decide(HOLD, HOLD_GRANT, "2026-11-23T10:03:00Z", replace("C06 GRT-CLASS-HOLD v1", "/limits_lifecycle/expiry", "2026-11-23T10:03:00Z"))
        self.assertEqual(decision.codes, ["GRANT_EXPIRED"])

    def test_an_unknown_expiry_or_issuance_time_blocks(self):
        for path in ("/limits_lifecycle/expiry", "/identity_principals/issuance_time"):
            with self.subTest(path):
                decision = decide(HOLD, HOLD_GRANT, "2026-11-23T10:03:00Z", replace("C06 GRT-CLASS-HOLD v1", path, UNKNOWN))
                self.assertEqual((decision.allow, decision.codes), (False, ["GRANT_TIME_UNKNOWN"]))

    def test_a_newer_version_whose_issuance_time_is_unknown_cannot_be_ruled_out(self):
        decision = decide(("ACT-REL-0417", "v2"), ("GRT-CLASS-LOWVAL", "v1"), "2026-11-23T14:20:00Z",
                          replace("C06 GRT-CLASS-LOWVAL v2", "/identity_principals/issuance_time", UNKNOWN),
                          {"target": "C05 ACT-REL-0417 v2", "ops": [{"op": "replace", "path": "/action/typed_parameters/0/value", "value": 4200}]})
        self.assertIn("GRANT_TIME_UNKNOWN", decision.codes)
        self.assertFalse(decision.allow)


class ATimeThatCannotBeComparedExactly(unittest.TestCase):
    """A time that cannot be compared to the attempt exactly is not trusted, so it blocks and names the time to supply."""

    def test_an_observation_a_hundred_nanoseconds_after_the_attempt_is_not_rounded_into_it(self):
        late = "2026-11-23T10:03:00.0000001Z"
        for label, mutation, expected in (("admission", admitted_at(late), "EVIDENCE_TIME_UNKNOWN"), ("revocation check", revocation_checked_at(late), "REVOCATION_TIME_UNKNOWN"),
                                          ("grant issuance", replace("C06 GRT-CLASS-HOLD v1", "/identity_principals/issuance_time", late), "GRANT_TIME_UNKNOWN")):
            with self.subTest(label):
                decision = decide(HOLD, HOLD_GRANT, "2026-11-23T10:03:00Z", mutation)
                self.assertEqual((decision.allow, decision.codes), (False, [expected]))

    def test_an_offset_that_is_not_real_cannot_move_a_check_before_the_attempt(self):
        decision = decide(HOLD, HOLD_GRANT, "2026-11-23T10:03:00Z", revocation_checked_at("2026-11-23T10:04:00+00:60"))
        self.assertEqual((decision.allow, decision.codes), (False, ["REVOCATION_TIME_UNKNOWN"]))

    def test_a_fraction_of_zeros_is_the_same_time(self):
        self.assertEqual(decide(HOLD, HOLD_GRANT, "2026-11-23T10:03:00Z", revocation_checked_at("2026-11-23T10:03:00.0000000Z")).codes, [])


class AccountingWindows(unittest.TestCase):
    """A window of a cumulative limit with a time that cannot be read blocks with a reason. It never raises, and it never allows."""

    WINDOW = "C06 GRT-CLASS-HOLD v1"
    START = "/limits_lifecycle/cumulative_limits/0/accounting_window/start"

    def test_an_unreadable_start_or_end_blocks_and_says_so(self):
        for end in (False, True):
            path = self.START.replace("start", "end") if end else self.START
            for label, value in (("tagged unknown", UNKNOWN), ("not a time", "bad-time"), ("no zone", "2026-11-23T00:00:00"), ("null", None)):
                with self.subTest("%s %s" % ("end" if end else "start", label)):
                    decision = decide(HOLD, HOLD_GRANT, "2026-11-23T10:03:00Z", replace(self.WINDOW, path, value))
                    self.assertEqual((decision.allow, decision.codes), (False, ["GRANT_TIME_UNKNOWN"]))
                    self.assertIn("accounting window", decision.reasons[0].message)

    def test_a_window_without_its_start_blocks_and_does_not_crash(self):
        decision = decide(HOLD, HOLD_GRANT, "2026-11-23T10:03:00Z", {"target": self.WINDOW, "ops": [{"op": "remove", "path": self.START}]})
        self.assertEqual((decision.allow, decision.codes), (False, ["GRANT_TIME_UNKNOWN"]))

    def test_a_window_that_ends_before_or_when_it_starts_cannot_count_anything_and_blocks(self):
        begin = support.example_model().get("C06", "GRT-CLASS-HOLD", "v1").data["limits_lifecycle"]["cumulative_limits"][0]["accounting_window"]["start"]
        end_path = self.START.replace("start", "end")
        for label, value in (("ends before it starts", "2026-11-22T00:00:00Z"), ("ends when it starts", begin)):
            with self.subTest(label):
                decision = decide(HOLD, HOLD_GRANT, "2026-11-23T10:03:00Z", replace(self.WINDOW, end_path, value))
                self.assertEqual((decision.allow, decision.codes), (False, ["GRANT_TIME_UNKNOWN"]))
                self.assertIn("out of order", decision.reasons[0].message)

    def test_a_receipt_whose_time_cannot_be_read_still_counts_against_the_limit(self):
        """Capacity is never freed by a time that cannot be read: the reservation is counted in every window, and the receipt cannot be shown to be the attempt's own."""
        unreadable = [replace("C07 RCP-REL-0417-B %s" % version, "/outcome/timestamps/submitted", "unreadable") for version in ("v1", "v2")]
        decision = decide(RELEASE_B, APPROVAL_B, "2026-11-23T16:00:05Z", *unreadable, ledger=True)
        self.assertIn("CUMULATIVE_LIMIT", decision.codes)
        self.assertFalse(decision.allow)


class TheLedgerFollowsTheAttempt(unittest.TestCase):
    """An attempt holds its reservation from its submission, not from the later time at which its receipt was verified."""

    def held(self, at, **exclude):
        return sorted(e.receipt for e in ledger_from_receipts(support.example_model(), ts(at), **exclude))

    def test_a_receipt_that_carries_its_verification_still_holds_its_reservation_between_submission_and_verification(self):
        # RCP-HOLD-0417 v1 was submitted at 10:03:00 and verified at 10:04:00.
        self.assertEqual(self.held("2026-11-23T10:03:30Z"), ["RCP-HOLD-0417"])
        self.assertEqual(self.held("2026-11-23T10:04:00Z"), ["RCP-HOLD-0417"])

    def test_a_reservation_made_at_exactly_the_attempt_time_counts_unless_it_is_the_attempts_own(self):
        """Equality is availability: what was reserved at the very moment of the attempt was known then. Only the attempt's own receipt is left out, and it is named."""
        self.assertEqual(self.held("2026-11-23T10:03:00Z"), ["RCP-HOLD-0417"])
        self.assertEqual(self.held("2026-11-23T10:03:00Z", exclude_receipt_id="RCP-HOLD-0417"), [])
        self.assertEqual(self.held("2026-11-23T10:03:00Z", exclude_receipt_ids=["RCP-HOLD-0417"]), [])
        self.assertEqual(self.held("2026-11-23T10:02:59Z"), [], "nothing counts before it was submitted")

    def test_naming_another_receipt_does_not_free_the_reservation_made_at_the_same_moment(self):
        model = support.example_model()
        release, approval = model.get("C05", *RELEASE_B), model.get("C06", *APPROVAL_B)
        at = ts("2026-11-23T16:00:05Z")
        other = evaluate_commit(model, release, approval, at, ledger_from_receipts(model, at, exclude_receipt_id="OTHER-ATTEMPT"))
        self.assertEqual((other.allow, other.codes), (False, ["CUMULATIVE_LIMIT"]))
        own = evaluate_commit(model, release, approval, at, ledger_from_receipts(model, at, exclude_receipt_ids=attempt_receipt_ids(model, release, approval, at)))
        self.assertEqual((own.allow, own.codes), (True, []))

    def test_the_attempts_own_receipt_is_the_one_that_cites_its_proposal_and_grant_and_was_submitted_at_its_time(self):
        model = support.example_model()
        release, approval = model.get("C05", *RELEASE_B), model.get("C06", *APPROVAL_B)
        self.assertEqual(attempt_receipt_ids(model, release, approval, ts("2026-11-23T16:00:05Z")), ["RCP-REL-0417-B"])
        self.assertEqual(attempt_receipt_ids(model, release, approval, ts("2026-11-23T16:00:06Z")), [], "another moment")
        self.assertEqual(attempt_receipt_ids(model, model.get("C05", *HOLD), model.get("C06", *HOLD_GRANT), ts("2026-11-23T16:00:05Z")), [], "another proposal and grant")

    def test_a_later_version_is_known_from_its_verification_so_the_earlier_one_holds_in_between(self):
        model = support.example_model()
        versions = {r.version: r for r in model.of("C07") if r.id == "RCP-REL-0417-B"}
        self.assertEqual(sorted(versions), ["v1", "v2"])
        between = [e for e in ledger_from_receipts(model, ts("2026-11-23T16:10:00Z")) if e.receipt == "RCP-REL-0417-B"]
        self.assertEqual([e.state for e in between], ["reserved"])
        after = [e for e in ledger_from_receipts(model, ts("2026-11-23T16:21:00Z")) if e.receipt == "RCP-REL-0417-B"]
        self.assertEqual([e.state for e in after], ["consumed"])

    def test_a_second_attempt_at_the_limit_is_blocked_while_the_first_is_not_yet_verified(self):
        # Make the hold grant allow one action in its window: a second hold at 10:03:30 must see the first one's reservation.
        one = replace("C06 GRT-CLASS-HOLD v1", "/limits_lifecycle/cumulative_limits/0/quantity", 1)
        decision = decide(HOLD, HOLD_GRANT, "2026-11-23T10:03:30Z", one, ledger=True)
        self.assertFalse(decision.allow)
        self.assertIn("CUMULATIVE_LIMIT", decision.codes)
        self.assertEqual(decide(HOLD, HOLD_GRANT, "2026-11-23T10:03:00Z", one, ledger=True).codes, [], "the attempt itself is not charged against itself")
        without = decide(HOLD, HOLD_GRANT, "2026-11-23T10:03:30Z", one, ledger=False)
        self.assertNotIn("CUMULATIVE_LIMIT", without.codes, "without the ledger nothing is counted, which is the difference this change makes")


class ACancelledAttemptHoldsItsCapacityUntilTheVerification(unittest.TestCase):
    """Capacity comes back only through a verification that is already available: not through a label, and not through a later time stored in the same receipt."""

    RECEIPT = "C07 RCP-REL-0417-B v1"

    def model_with_cancellation(self, basis):
        """Receipt B v1 as a cancelled attempt whose no effect was verified at 16:20, with its later version removed."""
        mutations = [replace(self.RECEIPT, "/outcome/state", "not_executed_verified"), add(self.RECEIPT, "/outcome/no_effect_basis", basis),
                     replace(self.RECEIPT, "/verification_recovery/verification", {"state": "authoritatively_verified", "time": "2026-11-23T16:20:00Z"})]
        model, _ = mutate_model(support.example_model(), mutations)
        return dataclasses.replace(model, instances={key: inst for key, inst in model.instances.items() if key != ("C07", "RCP-REL-0417-B", "v2")})

    def states(self, model, at):
        return [(e.receipt, e.state) for e in ledger_from_receipts(model, ts(at)) if e.receipt == "RCP-REL-0417-B"]

    def test_a_cancellation_holds_its_reservation_until_the_verification_that_shows_no_effect(self):
        model = self.model_with_cancellation("cancellation")
        self.assertEqual(self.states(model, "2026-11-23T16:10:00Z"), [("RCP-REL-0417-B", "reserved")])
        self.assertEqual(self.states(model, "2026-11-23T16:19:59Z"), [("RCP-REL-0417-B", "reserved")])
        self.assertEqual(self.states(model, "2026-11-23T16:20:00Z"), [], "a verification made at exactly the time is available")

    def test_so_does_a_failure_before_any_effect(self):
        self.assertEqual(self.states(self.model_with_cancellation("failed_before_effect"), "2026-11-23T16:10:00Z"), [("RCP-REL-0417-B", "reserved")])

    def test_a_rejection_by_the_gateway_never_reserved_anything(self):
        self.assertEqual(self.states(self.model_with_cancellation("rejection"), "2026-11-23T16:10:00Z"), [])

    def test_a_second_attempt_cannot_use_the_capacity_before_the_verification_but_can_after_it(self):
        model = self.model_with_cancellation("cancellation")
        release, approval = model.get("C05", *RELEASE_B), model.get("C06", *APPROVAL_B)
        for at, expected in (("2026-11-23T16:10:00Z", ["CUMULATIVE_LIMIT"]), ("2026-11-23T16:20:00Z", [])):
            decision = evaluate_commit(model, release, approval, ts(at), ledger_from_receipts(model, ts(at)))
            self.assertEqual([c for c in decision.codes if c == "CUMULATIVE_LIMIT"], expected, at)

    def test_a_verification_that_cannot_be_read_does_not_free_it(self):
        model = self.model_with_cancellation("cancellation")
        record = model.get("C07", "RCP-REL-0417-B", "v1")
        record.data["verification_recovery"]["verification"]["time"] = "unreadable"
        self.assertEqual(self.states(model, "2026-11-23T23:00:00Z"), [("RCP-REL-0417-B", "reserved")])

    def test_a_later_version_that_says_no_effect_does_not_free_it_either_unless_its_verification_can_be_read(self):
        """The later version is the one the ledger reads. A version that says 'cancelled' and states no verification time it can be held to gave nothing back."""
        for basis in ("cancellation", "failed_before_effect"):
            for value in ("unreadable", None, "2026-11-23T16:20:00.0000001Z", UNKNOWN):
                with self.subTest("%s, verification time %r" % (basis, value)):
                    mutations = [replace("C07 RCP-REL-0417-B v2", "/outcome/state", "not_executed_verified"), add("C07 RCP-REL-0417-B v2", "/outcome/no_effect_basis", basis),
                                 replace("C07 RCP-REL-0417-B v2", "/verification_recovery/verification/time", value)]
                    model, _ = mutate_model(support.example_model(), mutations)
                    self.assertEqual([(e.receipt, e.state) for e in ledger_from_receipts(model, ts("2026-11-23T23:00:00Z")) if e.receipt == "RCP-REL-0417-B"], [("RCP-REL-0417-B", "reserved")])
                    release, approval = model.get("C05", *RELEASE_B), model.get("C06", *APPROVAL_B)
                    decision = evaluate_commit(model, release, approval, ts("2026-11-23T16:10:00Z"), ledger_from_receipts(model, ts("2026-11-23T16:10:00Z")))
                    self.assertIn("CUMULATIVE_LIMIT", decision.codes)

    def test_a_later_version_whose_verification_can_be_read_gives_it_back_from_that_time(self):
        mutations = [replace("C07 RCP-REL-0417-B v2", "/outcome/state", "not_executed_verified"), add("C07 RCP-REL-0417-B v2", "/outcome/no_effect_basis", "cancellation")]
        model, _ = mutate_model(support.example_model(), mutations)
        held = lambda at: [e.state for e in ledger_from_receipts(model, ts(at)) if e.receipt == "RCP-REL-0417-B"]
        self.assertEqual(held("2026-11-23T16:19:59Z"), ["reserved"], "before the verification the first version, an unknown outcome, holds it")
        self.assertEqual(held("2026-11-23T16:20:00Z"), [], "at the verification it is given back")


class TheAttemptTime(unittest.TestCase):
    def test_a_missing_or_naive_attempt_time_is_refused_rather_than_guessed(self):
        model = support.example_model()
        proposal, grant = model.get("C05", *HOLD), model.get("C06", *HOLD_GRANT)
        for at in (None, parse_time("2026-11-23T10:03:00Z").replace(tzinfo=None)):
            with self.assertRaises(ValueError):
                evaluate_commit(model, proposal, grant, at, [])


class TheLedgerIsReadAsOfTheAttempt(unittest.TestCase):
    """A reservation that starts after the attempt is information from the future: it cannot change a decision already made."""

    SCOPE = "tenant:calder-works/GRT-CLASS-HOLD"

    def decide_with(self, at, *entries):
        model = support.example_model()
        return evaluate_commit(model, model.get("C05", *HOLD), model.get("C06", *HOLD_GRANT), ts(at), list(entries))

    def entry(self, start):
        return LedgerEntry("GRT-CLASS-HOLD", self.SCOPE, "holds", 20.0, "reserved", None if start is None else ts(start), "RCP-OTHER")

    def test_a_reservation_that_starts_after_the_attempt_does_not_change_it(self):
        decision = self.decide_with("2026-11-23T10:03:00Z", self.entry("2026-11-23T10:04:00Z"))
        self.assertEqual((decision.allow, decision.codes), (True, []))

    def test_a_reservation_that_started_by_the_attempt_counts(self):
        for start in ("2026-11-23T10:02:59Z", "2026-11-23T10:03:00Z"):
            with self.subTest(start):
                self.assertEqual(self.decide_with("2026-11-23T10:03:00Z", self.entry(start)).codes, ["CUMULATIVE_LIMIT"])

    def test_a_reservation_whose_start_cannot_be_read_counts_in_every_window(self):
        self.assertEqual(self.decide_with("2026-11-23T10:03:00Z", self.entry(None)).codes, ["CUMULATIVE_LIMIT"])

    def test_an_entry_that_cannot_count_is_not_read_for_its_quantity(self):
        """An entry from the future, or from another window, changes nothing, so a quantity it cannot state changes nothing either."""
        for label, start in (("from the future", "2026-11-23T10:03:00.000001Z"), ("a day later", "2026-11-24T10:03:00Z"), ("from before the window", "2026-11-22T10:00:00Z"), ("from after the window", "2026-11-24T00:00:00Z")):
            for quantity in ("unreadable", -1, float("nan"), None, True):
                with self.subTest("%s, quantity %r" % (label, quantity)):
                    entry = LedgerEntry("GRT-CLASS-HOLD", self.SCOPE, "holds", quantity, "reserved", ts(start), "RCP-OTHER")
                    decision = self.decide_with("2026-11-23T10:03:00Z", entry)
                    self.assertEqual((decision.allow, decision.codes), (True, []))

    def test_an_entry_that_counts_and_cannot_state_its_quantity_blocks(self):
        entry = LedgerEntry("GRT-CLASS-HOLD", self.SCOPE, "holds", "unreadable", "reserved", ts("2026-11-23T10:03:00Z"), "RCP-OTHER")
        self.assertEqual(self.decide_with("2026-11-23T10:03:00Z", entry).codes, ["CUMULATIVE_LIMIT"])


class AGrantOrAProposalMissingAPart(unittest.TestCase):
    """A part of the grant or the proposal that is missing is a check that cannot pass. It blocks with a reason from the table, and never raises."""

    GRANT = "C06 GRT-CLASS-HOLD v1"
    PROPOSAL = "C05 ACT-HOLD-0417 v1"

    def blocked(self, *mutations, proposal=HOLD, grant=HOLD_GRANT):
        decision = decide(proposal, grant, "2026-11-23T10:03:00Z", *mutations)
        self.assertFalse(decision.allow)
        self.assertTrue(set(decision.codes) <= set(GATE_CODES))
        return unique(decision.codes)

    def test_a_grant_without_its_limits_and_lifecycle_blocks(self):
        codes = self.blocked(remove(self.GRANT, "/limits_lifecycle"))
        self.assertEqual(codes, ["REVOCATION_TIME_UNKNOWN", "GRANT_TIME_UNKNOWN", "PER_ACTION_LIMIT"])

    def test_a_grant_without_its_scope_covers_nothing(self):
        codes = self.blocked(remove(self.GRANT, "/scope_binding"))
        self.assertEqual(codes, ["GRANT_NOT_BOUND", "ACTION_NOT_PERMITTED", "TARGET_NOT_PERMITTED", "PARAMETER_NOT_PERMITTED", "EVIDENCE_UNRESOLVED"])

    def test_a_grant_without_a_list_of_limits_cannot_show_the_limits_hold(self):
        self.assertEqual(self.blocked(remove(self.GRANT, "/limits_lifecycle/per_action_limits")), ["PER_ACTION_LIMIT"])
        self.assertEqual(self.blocked(remove(self.GRANT, "/limits_lifecycle/cumulative_limits")), ["GRANT_TIME_UNKNOWN"])

    def test_a_limit_without_a_readable_quantity_cannot_be_checked(self):
        for path, code in (("per_action_limits", "PER_ACTION_LIMIT"), ("cumulative_limits", "CUMULATIVE_LIMIT")):
            for value in ("many", None, True):
                with self.subTest(path, value=value):
                    self.assertEqual(self.blocked(replace(self.GRANT, "/limits_lifecycle/%s/0/quantity" % path, value)), [code])

    def test_a_limit_without_a_readable_unit_cannot_be_checked(self):
        for path, code in (("per_action_limits", "PER_ACTION_LIMIT"), ("cumulative_limits", "CUMULATIVE_LIMIT")):
            for label, mutation in (("missing", remove(self.GRANT, "/limits_lifecycle/%s/0/units" % path)), ("not text", replace(self.GRANT, "/limits_lifecycle/%s/0/units" % path, 3))):
                with self.subTest("%s %s" % (path, label)):
                    self.assertEqual(self.blocked(mutation), [code])

    def test_a_limit_too_large_for_a_float_is_still_compared_and_named(self):
        decision = decide(HOLD, HOLD_GRANT, "2026-11-23T10:03:00Z", replace(self.GRANT, "/limits_lifecycle/per_action_limits/0/quantity", 10 ** 400))
        self.assertEqual((decision.allow, decision.codes), (True, []))
        decision = decide(RELEASE_B, APPROVAL_B, "2026-11-23T16:00:05Z", replace("C06 GRT-APPR-0417-B v1", "/limits_lifecycle/per_action_limits/0/quantity", -10 ** 400))
        self.assertEqual(unique(decision.codes), ["PER_ACTION_LIMIT"])
        self.assertIn("exceeds the per-action limit", decision.reasons[0].message)

    def test_a_proposal_without_its_action_is_not_covered_by_the_grant(self):
        codes = self.blocked(remove(self.PROPOSAL, "/action"))
        self.assertIn("ACTION_NOT_PERMITTED", codes)
        self.assertIn("TARGET_NOT_PERMITTED", codes)

    def test_an_amount_in_euro_that_is_not_stated_blocks_with_a_limit_reason(self):
        for mutation in (replace("C05 ACT-REL-0417 v2", "/action/typed_parameters", []), remove("C05 ACT-REL-0417 v2", "/action/typed_parameters")):
            with self.subTest(mutation["ops"][0]["op"]):
                codes = self.blocked(mutation, proposal=RELEASE_B, grant=APPROVAL_B)
                self.assertIn("PER_ACTION_LIMIT", codes)
                self.assertIn("CUMULATIVE_LIMIT", codes)

    def blocked_at_the_release(self, *mutations):
        """The second release, which passes the commit check at 16:00:05 as stored, so that only the mutation can block it."""
        decision = decide(RELEASE_B, APPROVAL_B, "2026-11-23T16:00:05Z", *mutations)
        self.assertFalse(decision.allow)
        self.assertTrue(set(decision.codes) <= set(GATE_CODES))
        return unique(decision.codes)

    def test_an_amount_that_cannot_be_a_quantity_blocks_and_never_gives_capacity_back(self):
        """A negative amount used to pass both limits and reserve a negative quantity, which frees capacity for the next action. Nothing but a finite number that is not negative is an amount."""
        for value in (-18400, -1, -0.01, float("nan"), float("inf"), float("-inf"), True, "18400", None, [18400], {"eur": 18400}):
            with self.subTest(repr(value)):
                self.assertEqual(self.blocked_at_the_release(replace("C05 ACT-REL-0417 v2", "/action/typed_parameters/0/value", value)), ["PER_ACTION_LIMIT", "CUMULATIVE_LIMIT"])

    def test_an_amount_stated_twice_leaves_it_unclear_which_counts_and_blocks(self):
        for value in (18400, 1, 99999):
            with self.subTest(value):
                codes = self.blocked_at_the_release(add("C05 ACT-REL-0417 v2", "/action/typed_parameters/-", {"name": "amount_eur", "data_type": "number", "value": value}))
                self.assertEqual(codes, ["PER_ACTION_LIMIT", "CUMULATIVE_LIMIT"])

    def test_an_amount_of_zero_and_the_stored_amount_are_readable(self):
        for value in (0, 0.0, 18400, 18400.0):
            with self.subTest(value):
                decision = decide(RELEASE_B, APPROVAL_B, "2026-11-23T16:00:05Z", replace("C05 ACT-REL-0417 v2", "/action/typed_parameters/0/value", value))
                self.assertEqual((decision.allow, decision.codes), (True, []))
                self.assertEqual(decision.reserve["quantity"], float(value))

    def test_a_ledger_that_cannot_read_a_receipts_amount_counts_it_without_limit_also_when_it_is_negative(self):
        model, _ = mutate_model(support.example_model(), [replace("C05 ACT-REL-0417 v2", "/action/typed_parameters/0/value", -18400)])
        entries = [e for e in ledger_from_receipts(model, ts("2026-11-23T16:10:00Z")) if e.receipt == "RCP-REL-0417-B"]
        self.assertEqual([(e.units, e.quantity) for e in entries], [("EUR", float("inf"))])

    def test_a_ledger_built_from_receipts_never_raises_for_a_receipt_whose_amount_cannot_be_read(self):
        """The attempt's amount cannot be shown to be smaller than everything, so it is counted without limit."""
        model, _ = mutate_model(support.example_model(), [remove("C05 ACT-REL-0417 v2", "/action/typed_parameters")])
        entries = [e for e in ledger_from_receipts(model, ts("2026-11-23T16:10:00Z")) if e.receipt == "RCP-REL-0417-B"]
        self.assertEqual([(e.units, e.quantity) for e in entries], [("EUR", float("inf"))])


class AFreshnessLimitThatCannotBeRead(unittest.TestCase):
    """A freshness policy whose limit cannot be read is not 'no limit': the evidence cannot be shown to be fresh, and the attempt blocks."""

    def with_limit(self, value):
        model = support.example_model()
        registry = copy.deepcopy(model.registry)
        ref = model.get("C02", "M3W-0417", "v1").data["times"]["freshness"]["policy_reference"]
        policy = registry.policies[ref["policy_id"]][ref["version"]]
        policy["type"], policy["max_age_hours"] = "freshness", value
        return dataclasses.replace(model, registry=registry)

    def decide_on(self, model):
        return evaluate_commit(model, model.get("C05", *HOLD), model.get("C06", *HOLD_GRANT), ts("2026-11-23T10:03:00Z"), [])

    def test_a_limit_that_is_not_a_number_blocks_with_a_reason_and_does_not_raise(self):
        for value in (None, "soon", True, [], {}, float("nan"), float("inf"), -1, 10 ** 400):
            with self.subTest(repr(value)[:20]):
                decision = self.decide_on(self.with_limit(value))
                self.assertEqual((decision.allow, unique(decision.codes)), (False, ["EVIDENCE_STALE"]))
                self.assertIn("cannot be shown to be fresh", decision.reasons[0].message)

    def test_a_readable_limit_still_decides_by_age(self):
        self.assertEqual(self.decide_on(self.with_limit(10 ** 6)).codes, [])

    def test_a_record_that_names_no_freshness_policy_or_one_the_registry_does_not_hold_cannot_be_shown_to_be_fresh(self):
        """C02 requires a freshness policy on every record. Deleting the reference used to read as 'no policy applies' and lifted the limit."""
        record = "C02 M3W-0417 v1"
        stale = replace(record, "/times/event/value", "2025-11-23T09:35:00Z")
        self.assertEqual(unique(decide(HOLD, HOLD_GRANT, "2026-11-23T10:03:00Z", stale).codes), ["EVIDENCE_STALE"], "premise: a year-old record is stale under its own policy")
        for label, mutation in (("the reference is deleted", remove(record, "/times/freshness/policy_reference")), ("the policy id is not text", replace(record, "/times/freshness/policy_reference/policy_id", 7)),
                                ("the policy is not in the registry", replace(record, "/times/freshness/policy_reference/policy_id", "NO-SUCH-POLICY")),
                                ("its version is not in the registry", replace(record, "/times/freshness/policy_reference/version", "v99"))):
            with self.subTest(label):
                for mutations in ((mutation,), (stale, mutation)):
                    decision = decide(HOLD, HOLD_GRANT, "2026-11-23T10:03:00Z", *mutations)
                    self.assertEqual((decision.allow, unique(decision.codes)), (False, ["EVIDENCE_STALE"]))
                    self.assertIn("cannot be shown to be fresh", decision.reasons[0].message)

    def test_a_policy_that_is_not_one_of_freshness_sets_no_limit(self):
        model = self.with_limit(24)
        ref = model.get("C02", "M3W-0417", "v1").data["times"]["freshness"]["policy_reference"]
        model.registry.policies[ref["policy_id"]][ref["version"]]["type"] = "retention"
        self.assertEqual(self.decide_on(model).codes, [])


class AMissingListIsNotAnEmptyOne(unittest.TestCase):
    """Absence is never a pass. A proposal or a grant that leaves out a list the check reads blocks, and an empty list is allowed only where the contract allows it."""

    PROPOSAL = "C05 ACT-HOLD-0417 v1"
    GRANT = "C06 GRT-CLASS-HOLD v1"
    JUSTIFICATION = {"reason": "The domain owner approved a hold with nothing to check.", "approved_by": "role:ap-controller", "approved_at": "2026-11-23T07:45:00Z",
                     "approval_reference": {"record_id": "empty-preconditions-approval", "version": "v1"}}

    def test_a_proposal_without_its_preconditions_is_blocked_not_allowed(self):
        """At 10:10 the invoice is already held, so the hold's own precondition fails. Deleting the list must not turn that into an ALLOW."""
        self.assertEqual(decide(HOLD, HOLD_GRANT, "2026-11-23T10:10:00Z").codes, ["PRECONDITION_FAILED"])
        decision = decide(HOLD, HOLD_GRANT, "2026-11-23T10:10:00Z", remove(self.PROPOSAL, "/action/preconditions"))
        self.assertEqual((decision.allow, decision.codes), (False, ["PRECONDITION_UNDEFINED"]))
        self.assertIn("missing or is not a list", decision.reasons[0].message)

    def test_a_precondition_list_that_is_not_a_list_is_blocked_too(self):
        for value in (None, {}, "none", 0):
            with self.subTest(repr(value)):
                self.assertEqual(decide(HOLD, HOLD_GRANT, "2026-11-23T10:10:00Z", replace(self.PROPOSAL, "/action/preconditions", value)).codes, ["PRECONDITION_UNDEFINED"])

    def test_an_empty_list_needs_the_approved_justification_that_the_contract_requires(self):
        empty = replace(self.PROPOSAL, "/action/preconditions", [])
        unjustified = decide(HOLD, HOLD_GRANT, "2026-11-23T10:10:00Z", empty)
        self.assertEqual((unjustified.allow, unjustified.codes), (False, ["PRECONDITION_UNDEFINED"]))
        self.assertIn("approved justification", unjustified.reasons[0].message)
        for label, value in (("no reason", dict(self.JUSTIFICATION, reason="")), ("no approver", {k: v for k, v in self.JUSTIFICATION.items() if k != "approved_by"}), ("not an object", "approved")):
            with self.subTest(label):
                self.assertEqual(decide(HOLD, HOLD_GRANT, "2026-11-23T10:10:00Z", empty, add(self.PROPOSAL, "/action/approved_empty_preconditions_justification", value)).codes, ["PRECONDITION_UNDEFINED"])
        justified = decide(HOLD, HOLD_GRANT, "2026-11-23T10:10:00Z", empty, add(self.PROPOSAL, "/action/approved_empty_preconditions_justification", self.JUSTIFICATION))
        self.assertEqual((justified.allow, justified.codes), (True, []))

    def test_a_justification_must_have_been_approved_by_the_attempt(self):
        """An approval given after the attempt could not vouch for it, and one with no readable time cannot be shown to have been given."""
        empty = replace(self.PROPOSAL, "/action/preconditions", [])
        at = "2026-11-23T10:10:00Z"

        def decided(approved_at):
            justification = dict(self.JUSTIFICATION)
            if approved_at is not None:
                justification["approved_at"] = approved_at
            else:
                del justification["approved_at"]
            return decide(HOLD, HOLD_GRANT, at, empty, add(self.PROPOSAL, "/action/approved_empty_preconditions_justification", justification))
        for label, value in (("one second after", "2026-11-23T10:10:01Z"), ("a minute after", "2026-11-23T10:11:00Z"), ("not a time", "soon"), ("unknown", UNKNOWN), ("missing", None), ("a fraction finer than a microsecond", "2026-11-23T10:10:00.0000001Z")):
            with self.subTest(label):
                decision = decided(value)
                self.assertEqual((decision.allow, decision.codes), (False, ["PRECONDITION_UNDEFINED"]))
                self.assertIn("approv", decision.reasons[0].message)
        for label, value in (("at the attempt", "2026-11-23T10:10:00Z"), ("long before it", "2026-11-17T19:00:00Z")):
            with self.subTest(label):
                self.assertEqual(decided(value).codes, [])

    def test_a_proposal_that_cites_no_evidence_cannot_rest_on_any(self):
        for label, mutation in (("missing", remove(self.PROPOSAL, "/action/evidence_references")), ("empty", replace(self.PROPOSAL, "/action/evidence_references", [])), ("not a list", replace(self.PROPOSAL, "/action/evidence_references", None))):
            with self.subTest(label):
                decision = decide(HOLD, HOLD_GRANT, "2026-11-23T10:03:00Z", mutation)
                self.assertFalse(decision.allow)
                self.assertIn("EVIDENCE_UNRESOLVED", decision.codes)
                self.assertIn("cites no evidence", decision.reasons[0].message)

    def test_a_grant_that_states_no_list_of_evidence_constraints_is_blocked_but_an_empty_list_is_a_choice(self):
        decision = decide(HOLD, HOLD_GRANT, "2026-11-23T10:03:00Z", remove(self.GRANT, "/scope_binding/evidence_constraints"))
        self.assertEqual((decision.allow, decision.codes), (False, ["EVIDENCE_UNRESOLVED"]))
        self.assertEqual(decide(HOLD, HOLD_GRANT, "2026-11-23T10:03:00Z", replace(self.GRANT, "/scope_binding/evidence_constraints", [])).codes, [])

    def test_a_proposal_that_states_no_list_of_parameters_is_blocked(self):
        decision = decide(HOLD, HOLD_GRANT, "2026-11-23T10:03:00Z", remove(self.PROPOSAL, "/action/typed_parameters"))
        self.assertEqual((decision.allow, decision.codes), (False, ["PARAMETER_NOT_PERMITTED"]))
        self.assertEqual(decide(HOLD, HOLD_GRANT, "2026-11-23T10:03:00Z", replace(self.PROPOSAL, "/action/typed_parameters", [])).codes, [])


class AnEventThatHasNotHappenedGivesNoFreshness(unittest.TestCase):
    """A negative age would read as fresher than fresh. A record whose event is dated after the attempt cannot show that it is fresh."""

    SCREENING = "C02 SCR-S1042 v2"

    def test_an_event_dated_after_the_attempt_blocks_and_says_so(self):
        decision = decide(RELEASE_B, APPROVAL_B, "2026-11-23T16:00:05Z", replace(self.SCREENING, "/times/event/value", "2027-01-01T00:00:00Z"))
        self.assertFalse(decision.allow)
        self.assertIn("EVIDENCE_TIME_UNKNOWN", decision.codes)
        message = next(r.message for r in decision.reasons if r.code == "EVIDENCE_TIME_UNKNOWN")
        self.assertIn("after the attempt", message)
        self.assertIn("SCR-S1042 v2", message)

    def test_a_precondition_that_needs_fresh_evidence_is_not_met_by_such_a_record(self):
        decision = decide(RELEASE_B, APPROVAL_B, "2026-11-23T16:00:05Z", replace(self.SCREENING, "/times/event/value", "2027-01-01T00:00:00Z"))
        self.assertIn("PRECONDITION_FAILED", decision.codes)

    def test_an_event_at_exactly_the_attempt_time_has_happened(self):
        decision = decide(RELEASE_B, APPROVAL_B, "2026-11-23T16:00:05Z", replace(self.SCREENING, "/times/event/value", "2026-11-23T16:00:05Z"))
        self.assertEqual((decision.allow, decision.codes), (True, []))

    def test_the_age_of_an_event_that_has_not_happened_is_not_a_number(self):
        from eahs.gateway import age_hours
        record = support.example_model().get("C02", "SCR-S1042", "v2").data
        self.assertIsNone(age_hours(record, ts("2026-11-22T00:00:00Z")))
        self.assertIsNotNone(age_hours(record, ts("2026-11-23T16:00:05Z")))


class ALedgerEntryThatCannotBeReadIsNeverGuessed(unittest.TestCase):
    """The check is given entries by its caller. An applicable entry with a start or a quantity that cannot be read blocks instead of ending in an error or being counted as small."""

    SCOPE = "tenant:calder-works/GRT-CLASS-HOLD"

    def decide_with(self, *entries):
        model = support.example_model()
        return evaluate_commit(model, model.get("C05", *HOLD), model.get("C06", *HOLD_GRANT), ts("2026-11-23T10:03:00Z"), list(entries))

    def entry(self, quantity=1.0, start=None, grant="GRT-CLASS-HOLD"):
        return LedgerEntry(grant, self.SCOPE, "holds", quantity, "reserved", start, "RCP-OTHER")

    def test_an_unreadable_start_or_quantity_blocks_with_a_reason(self):
        naive = ts("2026-11-23T09:00:00Z").replace(tzinfo=None)
        for label, entry in (("a start that is text", self.entry(start="yesterday")), ("a start without a zone", self.entry(start=naive)), ("a quantity that is text", self.entry(quantity="3")),
                             ("a negative quantity", self.entry(quantity=-5)), ("not a number", self.entry(quantity=float("nan"))), ("true", self.entry(quantity=True)), ("not an entry", {"grant_id": "GRT-CLASS-HOLD"})):
            with self.subTest(label):
                decision = self.decide_with(entry)
                self.assertEqual((decision.allow, decision.codes), (False, ["CUMULATIVE_LIMIT"]))
                self.assertIn("cannot be read", decision.reasons[0].message)

    def test_an_entry_for_another_grant_is_not_read_at_all(self):
        self.assertEqual(self.decide_with(self.entry(start="yesterday", grant="GRT-OTHER")).codes, [])

    def test_a_readable_entry_with_no_start_still_counts_in_every_window_and_a_small_one_leaves_room(self):
        self.assertEqual(self.decide_with(self.entry(quantity=1)).codes, [], "1 held + 1 asked is within the 20 allowed")
        self.assertEqual(self.decide_with(self.entry(quantity=20)).codes, ["CUMULATIVE_LIMIT"])


class AStateOfTheTargetThatCannotBeDatedIsNotSkipped(unittest.TestCase):
    """A recorded state whose time cannot be read could be the state that holds at the attempt. Falling back to an older state would let an earlier state authorize it."""

    STORED = [{"entity_id": "INV-2026-0417", "at": "2026-11-23T07:30:00Z", "state": {"status": "open"}},
              {"entity_id": "INV-2026-0417", "at": "2026-11-23T10:03:20Z", "state": {"status": "held"}}]

    def hold_at(self, at, states):
        model = support.example_model()
        registry = copy.deepcopy(model.registry)
        registry.target_states = states
        model = dataclasses.replace(model, registry=registry)
        return evaluate_commit(model, model.get("C05", *HOLD), model.get("C06", *HOLD_GRANT), ts(at), [])

    def test_the_stored_states_decide_by_their_times(self):
        self.assertEqual(self.hold_at("2026-11-23T10:03:00Z", self.STORED).codes, [], "the invoice is still open at 10:03:00")
        self.assertEqual(self.hold_at("2026-11-23T10:10:00Z", self.STORED).codes, ["PRECONDITION_FAILED"], "and it is held at 10:10")

    def test_a_state_with_a_time_that_cannot_be_read_blocks_instead_of_falling_back_to_the_older_one(self):
        for value in (None, "soon", 7, "2026-11-23T10:03:20.0000001Z", UNKNOWN):
            for at in ("2026-11-23T10:03:00Z", "2026-11-23T10:10:00Z"):
                with self.subTest("%r at %s" % (value, at)):
                    states = copy.deepcopy(self.STORED)
                    states[1]["at"] = value
                    decision = self.hold_at(at, states)
                    self.assertEqual((decision.allow, decision.codes), (False, ["PRECONDITION_FAILED"]))

    def test_a_state_with_no_time_at_all_is_one_too(self):
        states = copy.deepcopy(self.STORED)
        del states[1]["at"]
        self.assertEqual(self.hold_at("2026-11-23T10:10:00Z", states).codes, ["PRECONDITION_FAILED"])

    def test_a_state_of_another_target_does_not_matter(self):
        states = copy.deepcopy(self.STORED) + [{"entity_id": "INV-OTHER", "at": None, "state": {"status": "held"}}]
        self.assertEqual(self.hold_at("2026-11-23T10:03:00Z", states).codes, [])


class ANumberTooBigForADoubleIsComparedExactlyAndNeverRaises(unittest.TestCase):
    """Quantities are compared as they are written: nothing is rounded to a double first, and a sum cannot overflow into an error."""

    SCOPE = "tenant:calder-works/GRT-CLASS-HOLD"

    def hold_with(self, *entries):
        model = support.example_model()
        return evaluate_commit(model, model.get("C05", *HOLD), model.get("C06", *HOLD_GRANT), ts("2026-11-23T10:03:00Z"), list(entries))

    def test_two_reservations_too_big_for_a_double_block_and_do_not_raise(self):
        entries = [LedgerEntry("GRT-CLASS-HOLD", self.SCOPE, "holds", 10 ** 308, "reserved", None, "RCP-X"), LedgerEntry("GRT-CLASS-HOLD", self.SCOPE, "holds", 10 ** 308, "reserved", None, "RCP-Y")]
        decision = self.hold_with(*entries)
        self.assertEqual((decision.allow, decision.codes), (False, ["CUMULATIVE_LIMIT"]))
        entries.append(LedgerEntry("GRT-CLASS-HOLD", self.SCOPE, "holds", 10 ** 400, "reserved", None, "RCP-Z"))
        self.assertEqual(self.hold_with(*entries).codes, ["CUMULATIVE_LIMIT"])

    def test_an_amount_one_above_the_limit_is_over_it_even_when_a_double_cannot_tell_them_apart(self):
        big = 2 ** 53
        mutations = [replace("C05 ACT-REL-0417 v2", "/action/typed_parameters/0/value", big + 1),
                     replace("C06 GRT-APPR-0417-B v1", "/limits_lifecycle/per_action_limits/0/quantity", big),
                     replace("C06 GRT-APPR-0417-B v1", "/limits_lifecycle/cumulative_limits/0/quantity", big)]
        self.assertEqual(float(big + 1), float(big), "the premise: a double cannot tell the two apart")
        decision = decide(RELEASE_B, APPROVAL_B, "2026-11-23T16:00:05Z", *mutations)
        self.assertEqual((decision.allow, unique(decision.codes)), (False, ["PER_ACTION_LIMIT", "CUMULATIVE_LIMIT"]))
        within = decide(RELEASE_B, APPROVAL_B, "2026-11-23T16:00:05Z", *[replace("C05 ACT-REL-0417 v2", "/action/typed_parameters/0/value", big)] + mutations[1:])
        self.assertEqual((within.allow, within.codes), (True, []))

    def test_decimal_amounts_add_up_as_they_are_written(self):
        """0.1 and 0.2 are 0.30000000000000004 as doubles, which is more than 0.3 and would have blocked an amount that is exactly the limit."""
        model, _ = mutate_model(support.example_model(), [replace("C05 ACT-REL-0417 v2", "/action/typed_parameters/0/value", 0.2),
                                                         replace("C06 GRT-APPR-0417-B v1", "/limits_lifecycle/per_action_limits/0/quantity", 0.3),
                                                         replace("C06 GRT-APPR-0417-B v1", "/limits_lifecycle/cumulative_limits/0/quantity", 0.3)])
        grant = model.get("C06", *APPROVAL_B)
        scope = grant.data["limits_lifecycle"]["cumulative_limits"][0]["accounting_scope"]
        entry = LedgerEntry("GRT-APPR-0417-B", scope, "EUR", 0.1, "reserved", None, "RCP-X")
        decision = evaluate_commit(model, model.get("C05", *RELEASE_B), grant, ts("2026-11-23T16:00:05Z"), [entry])
        self.assertEqual((decision.allow, decision.codes), (True, []))
        self.assertEqual(decision.reserve, {"units": "EUR", "quantity": 0.2, "counted_before": 0.1})
        over = evaluate_commit(model, model.get("C05", *RELEASE_B), grant, ts("2026-11-23T16:00:05Z"), [dataclasses.replace(entry, quantity=0.1000001)])
        self.assertEqual(over.codes, ["CUMULATIVE_LIMIT"])

    def test_the_amount_is_returned_as_it_is_written(self):
        from eahs.gateway import action_quantity
        proposal = {"action": {"typed_parameters": [{"name": "amount_eur", "data_type": "number", "value": 2 ** 53 + 1}]}}
        self.assertEqual(action_quantity(proposal, "EUR"), 2 ** 53 + 1)
        self.assertIsInstance(action_quantity(proposal, "EUR"), int)
        self.assertEqual(action_quantity(proposal, "holds"), 1.0)


class AnythingButAListOfEntriesIsNotALedger(unittest.TestCase):
    def test_a_ledger_that_is_not_a_list_blocks_instead_of_raising(self):
        model = support.example_model()
        for ledger in (None, {}, "empty", 0, ("a",), object()):
            with self.subTest(repr(ledger)[:20]):
                decision = evaluate_commit(model, model.get("C05", *HOLD), model.get("C06", *HOLD_GRANT), ts("2026-11-23T10:03:00Z"), ledger)
                self.assertEqual((decision.allow, decision.codes), (False, ["CUMULATIVE_LIMIT"]))
                self.assertIn("not given as a list", decision.reasons[0].message)


class AWhatIfThatChangesTheGrantIsReadAsItStands(unittest.TestCase):
    """The version of a grant that is in force is worked out from the grant that is evaluated, not from the stored copy of it."""

    ENTRY = 3   # EUR 2,000 under version 2

    def replay(self, **changes):
        from eahs.scenarios import evaluate_entry
        entry = copy.deepcopy(support.read_json("12-controlled-change/gateway-scenarios.json")["evaluations"][self.ENTRY])
        entry.update(changes)
        return evaluate_entry(support.example_model(), entry)

    def test_the_stored_entries_keep_their_decisions(self):
        self.assertEqual((self.replay().allow, self.replay().codes), (True, []))

    def test_a_version_issued_earlier_by_the_what_if_is_the_one_in_force(self):
        """Version 2 is stored as issued at 14:30. If the what-if says it was issued at 14:20, then at 14:20 it is the version in force, and version 1 is not."""
        at = "2026-11-23T14:20:00Z"
        stored = self.replay(at=at)
        self.assertIn("GRANT_NOT_YET_VALID", stored.codes, "as stored, version 2 does not exist yet at 14:20")
        moved = self.replay(at=at, overrides=self.entry_overrides() + [{"on": "grant", "path": "/identity_principals/issuance_time", "value": at},
                                                                       {"on": "grant", "path": "/limits_lifecycle/revocation/checked_at", "value": at}])
        self.assertEqual((moved.allow, moved.codes), (True, []))

    def entry_overrides(self):
        return copy.deepcopy(support.read_json("12-controlled-change/gateway-scenarios.json")["evaluations"][self.ENTRY]["overrides"])

    def test_a_version_issued_later_by_the_what_if_is_not_yet_valid_and_does_not_supersede_itself(self):
        """The version evaluated is not yet issued, so an older one is in force. That is not a supersession: the code says that a NEWER version is in force."""
        late = [{"on": "grant", "path": "/identity_principals/issuance_time", "value": "2026-11-23T14:50:00Z"},
                {"on": "grant", "path": "/limits_lifecycle/revocation/checked_at", "value": "2026-11-23T14:30:00Z"}]
        decision = self.replay(overrides=self.entry_overrides() + late)
        self.assertEqual((decision.allow, decision.codes), (False, ["GRANT_NOT_YET_VALID"]))

    def test_an_older_version_is_still_superseded_by_a_newer_one_in_force(self):
        """The stored attempt of version 1 after version 2 was issued: the newer version is in force."""
        stored = support.read_json("12-controlled-change/gateway-scenarios.json")["evaluations"]
        superseded = [entry for entry in stored if "GRANT_SUPERSEDED" in entry["expect"]["codes"]]
        self.assertTrue(superseded, "the stored evaluations show it")
        from eahs.scenarios import evaluate_entry
        for entry in superseded:
            self.assertIn("GRANT_SUPERSEDED", evaluate_entry(support.example_model(), copy.deepcopy(entry)).codes, entry["label"])


class EveryLimitHasItsAccountingWindow(unittest.TestCase):
    """The contract says that the accounting windows of its limits (each with a start and an end, in order) are known. A per-action limit has one too."""

    GRANT = "C06 GRT-CLASS-HOLD v1"
    WINDOW = "/limits_lifecycle/per_action_limits/0/accounting_window/%s"

    def test_a_per_action_window_that_cannot_be_read_or_is_out_of_order_blocks(self):
        for label, path, value in (("start tagged unknown", "start", UNKNOWN), ("start not a time", "start", "bad-time"), ("start finer than a microsecond", "start", "2026-11-23T00:00:00.0000001Z"),
                                   ("start after the end", "start", "2026-11-25T00:00:00Z"), ("end before the start", "end", "2026-11-22T00:00:00Z"), ("end null", "end", None)):
            with self.subTest(label):
                decision = decide(HOLD, HOLD_GRANT, "2026-11-23T10:03:00Z", replace(self.GRANT, self.WINDOW % path, value))
                self.assertEqual((decision.allow, decision.codes), (False, ["GRANT_TIME_UNKNOWN"]))
                self.assertIn("per-action limit", decision.reasons[0].message)

    def test_a_per_action_window_that_is_missing_blocks_and_does_not_raise(self):
        decision = decide(HOLD, HOLD_GRANT, "2026-11-23T10:03:00Z", remove(self.GRANT, "/limits_lifecycle/per_action_limits/0/accounting_window"))
        self.assertEqual((decision.allow, decision.codes), (False, ["GRANT_TIME_UNKNOWN"]))

    def test_the_stored_windows_are_readable_and_ordered(self):
        for grant in support.example_model().of("C06"):
            for limit in grant.data["limits_lifecycle"]["per_action_limits"] + grant.data["limits_lifecycle"]["cumulative_limits"]:
                self.assertIsNotNone(parse_time(limit["accounting_window"]["start"]), grant.label())
                self.assertLess(parse_time(limit["accounting_window"]["start"]), parse_time(limit["accounting_window"]["end"]), grant.label())


class ATargetStateThatLacksTheKeyIsNotNull(unittest.TestCase):
    """A state that does not hold a key says nothing about it. A rule that asks for null is not satisfied by a state that has no such key."""

    def hold_with(self, key_present, rule_equals, held=None):
        model = support.example_model()
        registry = copy.deepcopy(model.registry)
        registry.preconditions["PRE-INVOICE-OPEN"] = dict(registry.preconditions["PRE-INVOICE-OPEN"], key="hold_reference", equals=rule_equals)
        state = {"status": "open"}
        if key_present:
            state["hold_reference"] = held
        registry.target_states = [{"entity_id": "INV-2026-0417", "at": "2026-11-23T07:30:00Z", "state": state}]
        model = dataclasses.replace(model, registry=registry)
        return evaluate_commit(model, model.get("C05", *HOLD), model.get("C06", *HOLD_GRANT), ts("2026-11-23T10:03:00Z"), [])

    def test_a_missing_key_is_not_a_null_that_a_rule_can_ask_for(self):
        self.assertEqual(self.hold_with(False, None).codes, ["PRECONDITION_FAILED"])
        self.assertEqual(self.hold_with(True, None, held=None).codes, [], "a state that records null is a state that holds the key")

    def test_a_true_and_a_one_are_not_the_same_value(self):
        self.assertEqual(self.hold_with(True, True, held=True).codes, [])
        self.assertEqual(self.hold_with(True, True, held=1).codes, ["PRECONDITION_FAILED"])
        self.assertEqual(self.hold_with(True, 0, held=False).codes, ["PRECONDITION_FAILED"])

    def test_nor_inside_an_object_or_a_list(self):
        """The value a rule asks for may be an object or a list. true and 1 are told apart at every depth, and the numbers 1 and 1.0 are still the same number."""
        self.assertEqual(self.hold_with(True, {"ready": True}, held={"ready": True}).codes, [])
        self.assertEqual(self.hold_with(True, {"ready": True}, held={"ready": 1}).codes, ["PRECONDITION_FAILED"])
        self.assertEqual(self.hold_with(True, {"ready": True, "n": 1}, held={"ready": True, "n": 1.0}).codes, [])
        self.assertEqual(self.hold_with(True, {"ready": True}, held={"ready": True, "extra": 1}).codes, ["PRECONDITION_FAILED"])
        self.assertEqual(self.hold_with(True, [True, 0], held=[1, False]).codes, ["PRECONDITION_FAILED"])
        self.assertEqual(self.hold_with(True, [True, 0], held=[True, False]).codes, ["PRECONDITION_FAILED"])
        self.assertEqual(self.hold_with(True, [1, 2.0], held=[1.0, 2]).codes, [])
        self.assertEqual(self.hold_with(True, [1, 2], held=[1]).codes, ["PRECONDITION_FAILED"])
        self.assertEqual(self.hold_with(True, {"a": [{"b": True}]}, held={"a": [{"b": 1}]}).codes, ["PRECONDITION_FAILED"])

    def test_the_record_rule_tells_them_apart_inside_a_value_too(self):
        from eahs.gateway import _equal
        self.assertFalse(_equal({"matched": [1]}, {"matched": [True]}))
        self.assertTrue(_equal({"matched": [True]}, {"matched": [True]}))
        self.assertFalse(_equal([[True]], [[1]]))
        self.assertTrue(_equal(None, None))
        self.assertFalse(_equal({}, []))


class APolicyThatStatesNoKindIsNotNoPolicy(unittest.TestCase):
    """A policy without a kind cannot be told from one that limits the age of a record, so the record cannot be shown to be fresh."""

    def registry_with(self, mutate):
        model = support.example_model()
        registry = copy.deepcopy(model.registry)
        mutate(registry.policies["POL-FRESH-RECORDS"]["v1"])
        return dataclasses.replace(model, registry=registry)

    def test_a_missing_or_unreadable_kind_blocks_with_a_freshness_reason(self):
        from eahs.gateway import freshness_max_age
        for label, mutate in (("missing", lambda p: p.pop("type")), ("null", lambda p: p.update(type=None)), ("a list", lambda p: p.update(type=["freshness"])), ("empty", lambda p: p.update(type=" "))):
            with self.subTest(label):
                model = self.registry_with(mutate)
                with self.assertRaises(ValueError) as refused:
                    freshness_max_age(model, model.get("C02", "INV-2026-0417", "v1").data)
                self.assertIn("states no kind", str(refused.exception))
                decision = evaluate_commit(model, model.get("C05", *HOLD), model.get("C06", *HOLD_GRANT), ts("2026-11-23T10:03:00Z"), [])
                self.assertFalse(decision.allow)
                self.assertEqual(set(decision.codes), {"EVIDENCE_STALE"})

    def test_a_policy_that_is_explicitly_not_about_freshness_is_still_no_limit(self):
        from eahs.gateway import freshness_max_age
        model = self.registry_with(lambda p: p.update(type="read_purpose"))
        self.assertIsNone(freshness_max_age(model, model.get("C02", "INV-2026-0417", "v1").data))

    def test_the_registry_refuses_a_policy_without_a_kind_and_names_it(self):
        from eahs.model import registry_problem
        raw = copy.deepcopy(support.read_json("registry.json"))
        self.assertIsNone(registry_problem(raw))
        for label, value in (("missing", MISSING), ("null", None), ("a number", 3)):
            broken = copy.deepcopy(raw)
            if value is MISSING:
                del broken["policies"]["POL-FRESH-RECORDS"]["v1"]["type"]
            else:
                broken["policies"]["POL-FRESH-RECORDS"]["v1"]["type"] = value
            with self.subTest(label):
                self.assertIn("policy POL-FRESH-RECORDS v1 needs a 'type'", registry_problem(broken))


MISSING = object()


class OneAttemptIsCountedOnceWhateverWindowsItIsCountedIn(unittest.TestCase):
    """A grant may state several windows for one scope and unit (a day and an hour). An attempt is one entry in the ledger, and each window is applied to it."""

    GRANT = "C06 GRT-CLASS-HOLD v1"

    def hourly(self):
        model = support.example_model()
        grant = model.get("C06", *HOLD_GRANT).data["limits_lifecycle"]["cumulative_limits"][0]
        hour = dict(copy.deepcopy(grant), limit_id="LIM-HOLD-HOUR", quantity=2, accounting_window={"start": "2026-11-23T10:00:00Z", "end": "2026-11-23T11:00:00Z"})
        return add(self.GRANT, "/limits_lifecycle/cumulative_limits/-", hour)

    def test_an_attempt_makes_one_ledger_entry_for_one_scope_and_unit(self):
        model, _ = mutate_model(support.example_model(), [self.hourly()])
        entries = [e for e in ledger_from_receipts(model, ts("2026-11-23T10:03:01Z")) if e.receipt == "RCP-HOLD-0417"]
        self.assertEqual(len(entries), 1)

    def test_one_hold_and_one_more_fit_in_an_hour_that_allows_two(self):
        decision = decide(HOLD, HOLD_GRANT, "2026-11-23T10:03:01Z", self.hourly(), ledger=True)
        self.assertEqual((decision.allow, decision.codes), (True, []), "one hold already counted plus this one is two, and two are allowed")

    def test_a_third_hold_in_that_hour_is_over_the_limit(self):
        tight = replace(self.GRANT, "/limits_lifecycle/cumulative_limits/0/quantity", 20)
        model, _ = mutate_model(support.example_model(), [self.hourly(), tight])
        grant = model.get("C06", *HOLD_GRANT)
        scope = grant.data["limits_lifecycle"]["cumulative_limits"][0]["accounting_scope"]
        two = [LedgerEntry(grant.id, scope, "holds", 1.0, "reserved", ts("2026-11-23T10:01:00Z"), "RCP-X"), LedgerEntry(grant.id, scope, "holds", 1.0, "reserved", ts("2026-11-23T10:02:00Z"), "RCP-Y")]
        decision = evaluate_commit(model, model.get("C05", *HOLD), grant, ts("2026-11-23T10:03:01Z"), two)
        self.assertEqual((decision.allow, decision.codes), (False, ["CUMULATIVE_LIMIT"]))


class APerActionLimitIsComparedExactly(unittest.TestCase):
    """A float and an integer that a double cannot tell apart are different numbers, for the per-action limit as for the cumulative one."""

    def test_an_amount_written_as_a_float_is_over_a_cap_one_unit_below_it(self):
        mutations = [replace("C05 ACT-REL-0417 v2", "/action/typed_parameters/0/value", 100000000000000020.0),
                     replace("C06 GRT-APPR-0417-B v1", "/limits_lifecycle/per_action_limits/0/quantity", 100000000000000018),
                     replace("C06 GRT-APPR-0417-B v1", "/limits_lifecycle/cumulative_limits/0/quantity", 10 ** 18)]
        self.assertEqual(float(100000000000000018), float(100000000000000020.0), "the premise: a double cannot tell the two apart")
        decision = decide(RELEASE_B, APPROVAL_B, "2026-11-23T16:00:05Z", *mutations)
        self.assertEqual((decision.allow, unique(decision.codes)), (False, ["PER_ACTION_LIMIT"]))

    def test_the_message_shows_the_amounts_as_they_were_compared(self):
        """The check compares numbers as they were written. A message that printed the nearest double (100000000000000016) would show an amount below the cap it was refused for."""
        mutations = [replace("C05 ACT-REL-0417 v2", "/action/typed_parameters/0/value", 100000000000000020.0),
                     replace("C06 GRT-APPR-0417-B v1", "/limits_lifecycle/per_action_limits/0/quantity", 100000000000000018),
                     replace("C06 GRT-APPR-0417-B v1", "/limits_lifecycle/cumulative_limits/0/quantity", 10 ** 18)]
        decision = decide(RELEASE_B, APPROVAL_B, "2026-11-23T16:00:05Z", *mutations)
        self.assertIn("100000000000000020 EUR exceeds the per-action limit of 100000000000000018 EUR", [r.message for r in decision.reasons])

    def test_a_number_is_shown_in_full_when_it_is_whole_and_with_two_decimals_otherwise(self):
        from eahs.gateway import _fmt
        self.assertEqual([_fmt(x) for x in (18400, 18400.0, 0.5, 1.005, 100000000000000020.0, 10 ** 30, float("inf"))],
                         ["18400", "18400", "0.50", "1.00", "100000000000000020", "1000000000000000000000000000000", "inf"])
        self.assertEqual(_fmt(10 ** 5000), "a number too large to show", "a number beyond what Python shows as text is not turned into an error")

    def test_an_amount_at_the_cap_and_an_unbounded_cap_are_within_it(self):
        for cap in (18400, 18400.0, float("inf")):
            with self.subTest(cap):
                self.assertEqual(decide(RELEASE_B, APPROVAL_B, "2026-11-23T16:00:05Z", replace("C06 GRT-APPR-0417-B v1", "/limits_lifecycle/per_action_limits/0/quantity", cap)).codes, [])


class TwoReceiptsForOneAttemptAreAmbiguousForAReplay(unittest.TestCase):
    """A replay leaves out the attempt's own receipt. Two receipts that record attempts of the same proposal under the same grant at the same moment leave it unable to tell which one that is."""

    def with_second_attempt(self):
        from eahs.model import Instance, Model
        base = support.example_model()
        old = base.get("C07", "RCP-HOLD-0417", "v1")
        data = copy.deepcopy(old.data)
        data["identity_binding"]["receipt_id"] = "RCP-HOLD-0417-SECOND"
        data["identity_binding"]["execution_attempt_id"] = "ATT-HOLD-0417-SECOND"
        instances = dict(base.instances)
        instances[("C07", "RCP-HOLD-0417-SECOND", "v1")] = Instance(old.contract, "RCP-HOLD-0417-SECOND", "v1", data, old.path)
        return Model(instances, base.registry, base.root)

    def test_the_replay_refuses_to_guess(self):
        model = self.with_second_attempt()
        with self.assertRaises(ValueError) as refused:
            attempt_receipt_ids(model, model.get("C05", *HOLD), model.get("C06", *HOLD_GRANT), ts("2026-11-23T10:03:00Z"))
        self.assertIn("cannot tell which one is its own", str(refused.exception))
        self.assertIn("RCP-HOLD-0417-SECOND", str(refused.exception))

    def test_a_scenario_that_meets_it_is_a_finding_that_names_the_problem(self):
        from eahs.scenarios import check_scenario_file
        model = self.with_second_attempt()
        entry = {"label": "the hold again", "proposal": {"id": "ACT-HOLD-0417", "version": "v1"}, "grant": {"id": "GRT-CLASS-HOLD", "version": "v1"}, "at": "2026-11-23T10:03:00Z",
                 "expect": {"decision": "ALLOW", "codes": []}}
        findings = check_scenario_file(model, {"evaluations": [entry]}, "gateway-scenarios.json")
        self.assertEqual([f.code for f in findings], ["GW002"])
        self.assertIn("cannot tell which one is its own", findings[0].message)

    def test_one_receipt_with_several_versions_is_one_attempt(self):
        model = support.example_model()
        self.assertEqual(attempt_receipt_ids(model, model.get("C05", *RELEASE_B), model.get("C06", *APPROVAL_B), ts("2026-11-23T16:00:05Z")), ["RCP-REL-0417-B"])


class AVersionNameIsReadByItsAsciiDigitsOnly(unittest.TestCase):
    """int() refuses a digit of another script that str.isdigit() accepts ("v\u00b2"), and a version name is data."""

    def test_the_number_in_a_version_name(self):
        from eahs.model import version_number
        for name, number in (("v1", 1), ("v2", 2), ("v10", 10), ("v", 0), ("", 0), ("v1.2", 12), ("v\u00b2", 0), ("v\u0662", 0), ("v\uff12", 0), ("v\u00b23", 3)):
            with self.subTest(name):
                self.assertEqual(version_number(name), number)

    def test_a_grant_version_with_such_a_name_is_ordered_and_does_not_end_the_check(self):
        from eahs.model import Instance, Model
        base = support.example_model()
        old = base.get("C06", *HOLD_GRANT)
        data = copy.deepcopy(old.data)
        data["identity_principals"]["version"] = "v\u00b2"
        instances = dict(base.instances)
        instances[("C06", old.id, "v\u00b2")] = Instance(old.contract, old.id, "v\u00b2", data, old.path)
        model = Model(instances, base.registry, base.root)
        decision = evaluate_commit(model, model.get("C05", *HOLD), model.get("C06", *HOLD_GRANT), ts("2026-11-23T10:03:00Z"), [])
        self.assertIn(decision.allow, (True, False))
        self.assertEqual([v.version for v in model.versions("C06", old.id)], ["v\u00b2", "v1"])

    def test_a_receipt_version_with_such_a_name_does_not_end_the_ledger(self):
        from eahs.model import Instance, Model
        base = support.example_model()
        old = base.get("C07", "RCP-HOLD-0417", "v1")
        instances = dict(base.instances)
        instances[("C07", old.id, "v\u00b2")] = Instance(old.contract, old.id, "v\u00b2", copy.deepcopy(old.data), old.path)
        model = Model(instances, base.registry, base.root)
        self.assertIsInstance(ledger_from_receipts(model, ts("2026-11-23T23:00:00Z")), list)


class TheCheckNeverRaisesOnAMalformedGrantOrProposal(unittest.TestCase):
    """Random damage to the grant, the proposal, the evidence and the receipts (a part removed, replaced by another kind of value) is never an error.

    The check answers ALLOW or BLOCK. It raises only for an attempt time that is not a timezone-aware datetime.
    """

    VALUES = (None, "x", "", [], {}, -1, 0, True, False, 1.5, "2026-11-23T10:03:00Z", {"a": 1}, [1, 2], 10 ** 400, "unknown")
    TARGETS = (("C05", "ACT-HOLD-0417", "v1"), ("C06", "GRT-CLASS-HOLD", "v1"), ("C05", "ACT-REL-0417", "v2"), ("C06", "GRT-APPR-0417-B", "v1"),
               ("C02", "M3W-0417", "v1"), ("C02", "M3W-0417", "v2"), ("C07", "RCP-HOLD-0417", "v1"), ("C07", "RCP-REL-0417-B", "v1"))
    ATTEMPTS = ((("C05", "ACT-HOLD-0417", "v1"), ("C06", "GRT-CLASS-HOLD", "v1"), "2026-11-23T10:03:00Z"),
                (("C05", "ACT-REL-0417", "v2"), ("C06", "GRT-APPR-0417-B", "v1"), "2026-11-23T16:00:05Z"))

    @staticmethod
    def paths(node, prefix=()):
        yield prefix
        for key, value in (node.items() if isinstance(node, dict) else enumerate(node) if isinstance(node, list) else ()):
            yield from TheCheckNeverRaisesOnAMalformedGrantOrProposal.paths(value, prefix + (key,))

    def damaged(self, data, rng):
        data = copy.deepcopy(data)
        path = rng.choice([p for p in self.paths(data) if p])
        parent = data
        for key in path[:-1]:
            parent = parent[key]
        if rng.random() < 0.34:
            del parent[path[-1]]
        else:
            parent[path[-1]] = rng.choice(self.VALUES)
        return data

    def test_a_thousand_damaged_sets_each_give_a_decision(self):
        import random
        from eahs.model import Instance, Model
        base = support.example_model()
        for seed in range(1000):
            rng = random.Random(seed)
            instances = dict(base.instances)
            for _ in range(rng.randint(1, 3)):
                key = rng.choice(self.TARGETS)
                old = instances[key]
                instances[key] = Instance(old.contract, old.id, old.version, self.damaged(old.data, rng), old.path)
            model = Model(instances, base.registry, base.root)
            for proposal, grant, at in self.ATTEMPTS:
                try:
                    decision = evaluate_commit(model, model.get(*proposal), model.get(*grant), ts(at), ledger_from_receipts(model, ts(at)))
                except Exception as exc:  # noqa: BLE001
                    self.fail("seed %d, attempt %s: %s: %s" % (seed, proposal[1], type(exc).__name__, exc))
                self.assertIn(decision.allow, (True, False))
                self.assertTrue(set(decision.codes) <= set(GATE_CODES), decision.codes)


class ParsingTimes(unittest.TestCase):
    def test_rfc3339_with_a_zone_is_accepted(self):
        for text in ("2026-11-23T10:03:00Z", "2026-11-23t10:03:00z", "2026-11-23T10:03:00.5Z", "2026-11-23T12:03:00+02:00", "2026-11-23T10:03:00.123456000-00:00", "2026-11-23T10:03:00.0000000Z"):
            with self.subTest(text):
                self.assertIsNotNone(parse_time(text))
        self.assertEqual(parse_time("2026-11-23T12:03:00+02:00"), parse_time("2026-11-23T10:03:00Z"))
        self.assertEqual(parse_time("2026-11-23T10:03:00.0000000Z"), parse_time("2026-11-23T10:03:00Z"))

    def test_a_fraction_finer_than_a_microsecond_is_not_rounded_down_into_the_attempt(self):
        for text in ("2026-11-23T10:03:00.0000001Z", "2026-11-23T10:03:00.1234567Z", "2026-11-23T10:03:00.123456789-00:00"):
            with self.subTest(text):
                self.assertIsNone(parse_time(text))

    def test_an_offset_that_is_not_a_real_offset_is_unknown(self):
        for text in ("2026-11-23T10:04:00+00:60", "2026-11-23T10:04:00+01:75", "2026-11-23T10:04:00-24:00", "2026-11-23T10:04:00+99:99"):
            with self.subTest(text):
                self.assertIsNone(parse_time(text))
        self.assertIsNotNone(parse_time("2026-11-23T10:04:00+23:59"))

    def test_only_ascii_digits_are_digits(self):
        self.assertIsNone(parse_time("2026-11-23T10:03:00Z".replace("0", "\u0660")))
        self.assertIsNone(parse_time("\uff12\uff10\uff12\uff16-11-23T10:03:00Z"))

    def test_anything_else_is_unknown(self):
        for value in (None, "", " 2026-11-23T10:03:00Z", "2026-11-23T10:03:00Z ", "2026-11-23 10:03:00Z", "2026-11-23T10:03:00", "2026-11-23", "2026-13-23T10:03:00Z",
                      "2026-11-23T25:03:00Z", "2026-11-23T10:03:00+24:00", UNKNOWN, 7, ["2026-11-23T10:03:00Z"]):
            with self.subTest(repr(value)):
                self.assertIsNone(parse_time(value))

    def test_the_strict_parser_raises_instead_of_guessing(self):
        with self.assertRaises(ValueError):
            ts("2026-11-23T10:03:00")


class Receipts(unittest.TestCase):
    """The receipt check replays the commit decision at the receipt's own submission time, so it inherits the temporal rules."""

    def test_a_receipt_timed_before_its_evidence_was_admitted_disagrees_with_the_gateway(self):
        model, _ = mutate_model(support.example_model(), [replace("C07 RCP-HOLD-0417 v1", "/outcome/timestamps/submitted", "2026-11-23T09:30:00Z")])
        found = [f for f in semantics.check_authority(model) if f.code == "AUTH004"]
        self.assertEqual(len(found), 1)
        self.assertIn("EVIDENCE_NOT_YET_ADMITTED", found[0].message)

    def test_the_unmutated_receipts_agree_with_the_gateway(self):
        self.assertEqual([f.code for f in semantics.check_authority(support.example_model())], [])


class ReasonCodes(unittest.TestCase):
    def test_the_temporal_codes_exist(self):
        for code in ("EVIDENCE_NOT_YET_ADMITTED", "EVIDENCE_TIME_UNKNOWN", "REVOCATION_NOT_YET_OBSERVED", "REVOCATION_TIME_UNKNOWN", "GRANT_TIME_UNKNOWN"):
            self.assertIn(code, GATE_CODES)

    def test_the_reasons_say_which_time_to_supply(self):
        decision = decide(HOLD, HOLD_GRANT, "2026-11-23T10:03:00Z", admitted_at(UNKNOWN), revocation_checked_at(UNKNOWN))
        messages = " ".join(r.message for r in decision.reasons)
        self.assertIn("M3W-0417 v1 was admitted", messages)
        self.assertIn("revocation check", messages)


if __name__ == "__main__":
    unittest.main()
