"""Temporal integrity at commit: a decision uses only what was available and valid at the attempt.

The reference check separates five times. The business event time says when something happened. The admission time
says when the system could first rely on a record of it. Freshness compares the event time with the attempt. The
lifecycle state applies from its effective time. A revocation observation counts from the time it was made. A time
that equals the attempt time was reached when the attempt was made. A time that is missing or unknown blocks.
"""
import unittest

import support  # noqa: F401  (puts scripts/ on the path)

from eahs import semantics
from eahs.cases import mutate_model
from eahs.gateway import GATE_CODES, evaluate_commit, ledger_from_receipts, parse_time, ts

HOLD, HOLD_GRANT = ("ACT-HOLD-0417", "v1"), ("GRT-CLASS-HOLD", "v1")
RELEASE_B, APPROVAL_B = ("ACT-REL-0417", "v2"), ("GRT-APPR-0417-B", "v1")
RELEASE_A, APPROVAL_A = ("ACT-REL-0417", "v1"), ("GRT-APPR-0417-A", "v1")
UNKNOWN = {"state": "unknown", "reason": "The producing system did not record this time."}


def replace(target, path, value):
    return {"target": target, "ops": [{"op": "replace", "path": path, "value": value}]}


def unique(codes):
    return list(dict.fromkeys(codes))


def decide(proposal, grant, at, *mutations, ledger=False):
    """The reference decision at `at`, with in-memory mutations applied to a copy of the example set."""
    model, _ = mutate_model(support.example_model(), list(mutations))
    p, g = model.get("C05", *proposal), model.get("C06", *grant)
    entries = ledger_from_receipts(model, ts(at)) if ledger else []
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


class TheAttemptTime(unittest.TestCase):
    def test_a_missing_or_naive_attempt_time_is_refused_rather_than_guessed(self):
        model = support.example_model()
        proposal, grant = model.get("C05", *HOLD), model.get("C06", *HOLD_GRANT)
        for at in (None, parse_time("2026-11-23T10:03:00Z").replace(tzinfo=None)):
            with self.assertRaises(ValueError):
                evaluate_commit(model, proposal, grant, at, [])


class ParsingTimes(unittest.TestCase):
    def test_rfc3339_with_a_zone_is_accepted(self):
        for text in ("2026-11-23T10:03:00Z", "2026-11-23t10:03:00z", "2026-11-23T10:03:00.5Z", "2026-11-23T12:03:00+02:00", "2026-11-23T10:03:00.123456789-00:00"):
            with self.subTest(text):
                self.assertIsNotNone(parse_time(text))
        self.assertEqual(parse_time("2026-11-23T12:03:00+02:00"), parse_time("2026-11-23T10:03:00Z"))

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
