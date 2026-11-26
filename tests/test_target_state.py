"""The recorded state of a target at the attempt does not depend on the order of the records.

The state that holds at an attempt is the one recorded at the latest instant at or before it. Records are read as instants, and every record made at that instant counts: where they agree,
that is the state, and where they disagree about a key, the key is unresolved and a precondition that asks for it is not satisfied, whichever record came first. A later record that is
unambiguous supersedes an earlier disagreement, and a record made after the attempt is ignored.
"""
import copy
import dataclasses
import itertools
import unittest

import support  # noqa: F401  (puts scripts/ on the path)

from eahs.gateway import evaluate_commit, ts

HOLD, HOLD_GRANT = ("ACT-HOLD-0417", "v1"), ("GRT-CLASS-HOLD", "v1")
ATTEMPT = "2026-11-23T10:03:00Z"
ENTITY = "INV-2026-0417"


def state(at, **fields):
    return {"entity_id": ENTITY, "at": at, "state": fields}


def decide(states, at=ATTEMPT, **rule):
    """The decision on the hold, which requires the invoice to be open, when the registry holds `states`. `rule` changes what the precondition asks for (a key and a value)."""
    model = support.example_model()
    registry = copy.deepcopy(model.registry)
    registry.target_states = copy.deepcopy(states)
    if rule:
        registry.preconditions["PRE-INVOICE-OPEN"] = dict(registry.preconditions["PRE-INVOICE-OPEN"], **rule)
    model = dataclasses.replace(model, registry=registry)
    return evaluate_commit(model, model.get("C05", *HOLD), model.get("C06", *HOLD_GRANT), ts(at), [])


def in_every_order(states, **kwargs):
    """The distinct decisions (allow, codes) over every order of the records."""
    return {(d.allow, tuple(d.codes)) for d in (decide(list(order), **kwargs) for order in itertools.permutations(states))}


BLOCKED, ALLOWED = {(False, ("PRECONDITION_FAILED",))}, {(True, ())}


class TheStoredStateStillDecides(unittest.TestCase):
    def test_the_stored_records_decide_by_their_times(self):
        stored = support.example_model().registry.target_states
        self.assertEqual(decide(stored, "2026-11-23T10:03:00Z").codes, [], "open at 10:03:00")
        self.assertEqual(decide(stored, "2026-11-23T10:10:00Z").codes, ["PRECONDITION_FAILED"], "held at 10:10")

    def test_one_current_record_decides_and_a_later_one_is_ignored(self):
        self.assertEqual(in_every_order([state("2026-11-23T07:30:00Z", status="open"), state("2026-11-23T10:03:20Z", status="held")]), ALLOWED)


class RecordsMadeAtOneInstantAreReadTogether(unittest.TestCase):
    AT = "2026-11-23T10:00:00Z"

    def test_an_open_and_a_held_record_of_one_instant_block_in_both_orders(self):
        both = [state(self.AT, status="open"), state(self.AT, status="held")]
        self.assertEqual(in_every_order(both), BLOCKED)

    def test_the_same_instant_written_with_another_offset_is_the_same_instant(self):
        for other in ("2026-11-23T11:00:00+01:00", "2026-11-23T10:00:00.000Z", "2026-11-23T09:00:00-01:00"):
            with self.subTest(other):
                self.assertEqual(in_every_order([state(self.AT, status="open"), state(other, status="held")]), BLOCKED)

    def test_a_conflict_exactly_at_the_attempt_blocks(self):
        self.assertEqual(in_every_order([state(ATTEMPT, status="open"), state(ATTEMPT, status="held")]), BLOCKED)

    def test_a_conflict_one_microsecond_before_the_attempt_blocks(self):
        self.assertEqual(in_every_order([state("2026-11-23T10:02:59.999999Z", status="open"), state("2026-11-23T10:02:59.999999Z", status="held")]), BLOCKED)

    def test_a_conflict_one_microsecond_after_the_attempt_is_not_yet_a_record(self):
        late = "2026-11-23T10:03:00.000001Z"
        self.assertEqual(in_every_order([state("2026-11-23T07:30:00Z", status="open"), state(late, status="open"), state(late, status="held")]), ALLOWED)

    def test_the_finding_names_the_key_and_the_values_that_disagree(self):
        message = decide([state(self.AT, status="open"), state(self.AT, status="held")]).reasons[0].message
        for part in ("PRE-INVOICE-OPEN", "disagree", "status", "open", "held", self.AT):
            self.assertIn(part, message)

    def test_identical_duplicates_are_not_a_conflict(self):
        self.assertEqual(in_every_order([state(self.AT, status="open"), state(self.AT, status="open")]), ALLOWED)
        self.assertEqual(in_every_order([state(self.AT, status="open"), state("2026-11-23T11:00:00+01:00", status="open")]), ALLOWED)
        self.assertEqual(in_every_order([state(self.AT, status="held"), state(self.AT, status="held")]), BLOCKED)

    def test_records_of_one_instant_that_state_different_keys_are_one_state(self):
        self.assertEqual(in_every_order([state(self.AT, status="open"), state(self.AT, owner="role:ap-controller")]), ALLOWED)

    def test_a_disagreement_about_another_key_does_not_matter_for_the_key_that_is_asked(self):
        both = [state(self.AT, status="open", owner="role:a"), state(self.AT, status="open", owner="role:b")]
        self.assertEqual(in_every_order(both), ALLOWED)
        self.assertEqual(in_every_order(both, key="owner", equals="role:a"), BLOCKED)
        self.assertEqual(in_every_order(both, key="owner", equals="role:b"), BLOCKED)

    def test_true_and_one_are_two_values_so_they_disagree(self):
        both = [state(self.AT, flag=True), state(self.AT, flag=1)]
        self.assertEqual(in_every_order(both, key="flag", equals=True), BLOCKED)
        self.assertEqual(in_every_order(both, key="flag", equals=1), BLOCKED)

    def test_a_record_of_another_target_at_that_instant_is_not_part_of_it(self):
        elsewhere = {"entity_id": "INV-OTHER", "at": self.AT, "state": {"status": "held"}}
        self.assertEqual(in_every_order([state(self.AT, status="open"), elsewhere]), ALLOWED)


class ALaterRecordSupersedesAnEarlierDisagreement(unittest.TestCase):
    def test_an_earlier_conflict_followed_by_a_later_unambiguous_record_takes_the_later_value(self):
        disagreement = [state("2026-11-23T09:00:00Z", status="open"), state("2026-11-23T09:00:00Z", status="held")]
        self.assertEqual(in_every_order([*disagreement, state("2026-11-23T10:00:00Z", status="open")]), ALLOWED)
        self.assertEqual(in_every_order([*disagreement, state("2026-11-23T10:00:00Z", status="held")]), BLOCKED)

    def test_the_decision_that_follows_a_later_record_does_not_speak_of_a_disagreement_that_no_longer_holds(self):
        disagreement = [state("2026-11-23T09:00:00Z", status="open"), state("2026-11-23T09:00:00Z", status="held")]
        message = decide([*disagreement, state("2026-11-23T10:00:00Z", status="held")]).reasons[0].message
        self.assertNotIn("disagree", message)

    def test_a_record_that_follows_the_attempt_does_not_supersede_a_disagreement_that_holds_at_it(self):
        disagreement = [state("2026-11-23T09:00:00Z", status="open"), state("2026-11-23T09:00:00Z", status="held")]
        self.assertEqual(in_every_order([*disagreement, state("2026-11-23T10:03:00.000001Z", status="open")]), BLOCKED)


if __name__ == "__main__":
    unittest.main()
