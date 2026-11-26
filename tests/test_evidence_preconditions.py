"""An evidence precondition is judged on every usable record it selects, and the order in which the evidence is listed decides nothing.

The commit check reads two lists together: the evidence a proposal cites and the evidence constraints of the grant it runs under. A precondition that reads evidence selects the cited
records whose id starts with the prefix of its rule, keeps those that were usable at the attempt, and holds only if at least one such record exists and every one of them satisfies the rule.
Records that disagree are not resolved in favour of the one that is listed first or last: the precondition is not satisfied. A record that was not usable neither satisfies the rule nor fails it;
the evidence checks refuse it for their own reason.

Every case below is decided for every arrangement of the cited records: each order, and each split of that order between the proposal and the evidence constraints of the grant.
"""
import copy
import dataclasses
import itertools
import unittest

import support  # noqa: F401  (puts scripts/ on the path)

from eahs.gateway import evaluate_commit, ts
from eahs.model import Instance, Model

RELEASE, GRANT = ("ACT-REL-0417", "v2"), ("GRT-APPR-0417-B", "v1")
ATTEMPT = "2026-11-23T16:00:05Z"
PAYLOAD, FRESH = "PRE-MATCH-PASS", "PRE-SCREEN-FRESH"
ALLOWED, REFUSED = (True, ()), (False, ("PRECONDITION_FAILED",))
STORED = {r["record_id"]: r for r in support.example_model().get("C05", *RELEASE).data["action"]["evidence_references"]}


def result(value):
    def edit(data):
        data["content"]["payload"]["value"]["result"] = value
    return edit


def without_result(data):
    del data["content"]["payload"]["value"]["result"]


def observed(when):
    def edit(data):
        data["times"]["event"] = {"state": "known", "value": when}
    return edit


def not_yet_admitted(data):
    data["producer_admission"]["admission_time"] = "2026-11-23T16:00:06Z"


def superseded(data):
    data["lifecycle"].update(state="superseded", effective_time="2026-11-23T15:59:00Z")


#: What a copy of a stored record looks like for the rule that reads it: the stored record it copies, a record the rule does not select, and the edits that make a copy satisfy the rule or fail it.
KINDS = {
    PAYLOAD: dict(prefix="M3W-T", source="M3W-0417", other="SCR-S1042", good=result("PASS"), bad=result("FAIL"), unreadable=without_result),
    FRESH: dict(prefix="SCR-T", source="SCR-S1042", other="M3W-0417", good=observed("2026-11-23T15:40:00Z"), bad=observed("2026-11-23T13:30:00Z"), unreadable=observed("unknown")),
}


def reference(record_id, like, version="v2"):
    ref = copy.deepcopy(STORED[like])
    ref["record_id"], ref["version"] = record_id, version
    return ref


def with_copies(model, copies):
    """The set with more C02 records, each a copy of a stored one under a new id: {new id: (stored id, version, edits of the copy's data)}."""
    instances = dict(model.instances)
    for new_id, (source_id, version, edits) in copies.items():
        stored = model.get("C02", source_id, version)
        data = copy.deepcopy(stored.data)
        data["identity_schema"]["record_id"] = new_id
        for edit in edits:
            edit(data)
        instances[("C02", new_id, version)] = Instance("C02", new_id, version, data, stored.path)
    return Model(instances, model.registry, model.root)


def with_age_limit(model, hours):
    """The freshness rule of the registry with a shorter limit than the freshness policy of the records, so that a record can be too old for the rule and still within its own policy."""
    registry = copy.deepcopy(model.registry)
    registry.preconditions[FRESH]["max_age_hours"] = hours
    return dataclasses.replace(model, registry=registry)


def release(model, precondition, proposal_refs, grant_refs, at=ATTEMPT):
    """The decision on the corrected release, with these evidence references in the proposal and these evidence constraints in the grant, judged on one precondition."""
    proposal, grant = model.get("C05", *RELEASE), model.get("C06", *GRANT)
    p, g = copy.deepcopy(proposal.data), copy.deepcopy(grant.data)
    p["action"]["evidence_references"] = copy.deepcopy(proposal_refs)
    g["scope_binding"]["evidence_constraints"] = copy.deepcopy(grant_refs)
    p["action"]["preconditions"] = [c for c in p["action"]["preconditions"] if c["condition_id"] == precondition]
    return evaluate_commit(model, Instance("C05", proposal.id, proposal.version, p, proposal.path), Instance("C06", grant.id, grant.version, g, grant.path), ts(at), [])


def arrangements(matching, context):
    """Every way to list the cited records: each order, with the first k of them in the proposal and the rest in the evidence constraints of the grant."""
    for order in itertools.permutations(matching):
        for k in range(len(order) + 1):
            yield tuple(r["record_id"] for r in order), k, context + list(order[:k]), context + list(order[k:])


def decisions(model, precondition, matching, context):
    """The distinct decisions over every arrangement, each with the arrangements that give it: {(allowed, sorted distinct codes): [(order, k)]}."""
    seen = {}
    for order, k, proposal_refs, grant_refs in arrangements(matching, context):
        decision = release(model, precondition, proposal_refs, grant_refs)
        seen.setdefault((decision.allow, tuple(sorted(set(decision.codes)))), []).append((order, k))
    return seen


class Scenario:
    """The records that one rule reads, as copies of a stored one, and the evidence that the rule does not select."""

    def __init__(self, precondition, rows, model=None, extra=()):
        self.precondition, self.kind = precondition, KINDS[precondition]
        copies = {}
        for i, row in enumerate(rows):
            label, edits = (row, ()) if isinstance(row, str) else row
            copies["%s%d" % (self.kind["prefix"], i)] = (self.kind["source"], "v2", (self.kind[label],) + tuple(edits))
        copies.update(dict(extra))
        self.model = with_copies(model or support.example_model(), copies)
        if precondition == FRESH:
            self.model = with_age_limit(self.model, 1)
        self.matching = [reference(record_id, self.kind["source"]) for record_id in ("%s%d" % (self.kind["prefix"], i) for i in range(len(rows)))]
        self.context = [STORED[i] for i in ("INV-2026-0417", "PO-77231", "GR-5521", "DUP-0417", self.kind["other"])]

    def decisions(self):
        return decisions(self.model, self.precondition, self.matching, self.context)


class EveryUsableRecordThatTheRuleSelectsIsJudged(unittest.TestCase):
    """The first row of each pair has the failing record first by id and the second has it last: no id order decides either, as no listing order does."""

    ROWS = [
        (("good",), ALLOWED),
        (("bad",), REFUSED),
        (("good", "good"), ALLOWED),
        (("bad", "bad"), REFUSED),
        (("good", "bad"), REFUSED),
        (("bad", "good"), REFUSED),
        (("good", "good", "bad"), REFUSED),
        (("bad", "good", "good"), REFUSED),
        (("good", "bad", "good"), REFUSED),
    ]

    def test_a_rule_that_reads_a_payload_or_an_age_is_satisfied_only_when_every_selected_record_satisfies_it(self):
        for precondition in (PAYLOAD, FRESH):
            for rows, expected in self.ROWS:
                with self.subTest(precondition, rows=rows):
                    seen = Scenario(precondition, rows).decisions()
                    self.assertEqual(set(seen), {expected}, "the decision depends on how the records are listed: %s" % seen)

    def test_the_same_record_in_the_proposal_and_in_the_grant_is_one_record(self):
        for precondition in (PAYLOAD, FRESH):
            for rows, expected in ((("good",), ALLOWED), (("bad",), REFUSED), (("good", "bad"), REFUSED)):
                with self.subTest(precondition, rows=rows):
                    scenario = Scenario(precondition, rows)
                    decision = release(scenario.model, precondition, scenario.context + scenario.matching, scenario.context + scenario.matching[::-1])
                    self.assertEqual((decision.allow, tuple(sorted(set(decision.codes)))), expected)

    def test_no_selected_record_is_not_a_satisfied_rule(self):
        for precondition in (PAYLOAD, FRESH):
            with self.subTest(precondition):
                scenario = Scenario(precondition, ("good",))
                decision = release(scenario.model, precondition, scenario.context, scenario.context)
                self.assertEqual((decision.allow, decision.codes), (False, ["PRECONDITION_FAILED"]))

    def test_a_selected_record_that_cannot_be_read_does_not_satisfy_the_rule_and_does_not_hide_one_that_does(self):
        """The rule needs a result the record does not hold, or an event time that is not known."""
        for precondition, codes in ((PAYLOAD, ("PRECONDITION_FAILED",)), (FRESH, ("EVIDENCE_TIME_UNKNOWN", "PRECONDITION_FAILED"))):
            for rows in (("unreadable",), ("good", "unreadable"), ("unreadable", "good"), ("good", "good", "unreadable")):
                with self.subTest(precondition, rows=rows):
                    seen = Scenario(precondition, rows).decisions()
                    self.assertEqual(set(seen), {(False, codes)}, seen)

    def test_the_stored_release_still_satisfies_both_rules(self):
        model, stored = support.example_model(), list(STORED.values())
        for precondition in (PAYLOAD, FRESH):
            with self.subTest(precondition):
                decision = release(model, precondition, stored, stored)
                self.assertEqual((decision.allow, decision.codes), (True, []))


class EvidenceThatTheRuleDoesNotSelectChangesNothing(unittest.TestCase):
    def test_a_cited_record_whose_id_does_not_start_with_the_prefix_is_not_read(self):
        """XM3W-T1 holds FAIL and merely contains the prefix; XM3W-T2 holds PASS. Neither is read, whichever way the rule is judged."""
        for rows, expected in ((("good",), ALLOWED), (("bad",), REFUSED)):
            with self.subTest(rows=rows):
                scenario = Scenario(PAYLOAD, rows, extra={"XM3W-T1": ("M3W-0417", "v2", (result("FAIL"),)), "XM3W-T2": ("M3W-0417", "v2", (result("PASS"),))})
                noise = [reference("XM3W-T1", "M3W-0417"), reference("XM3W-T2", "M3W-0417")]
                scenario.context = scenario.context + noise
                self.assertEqual(set(scenario.decisions()), {expected})

    def test_a_record_with_the_prefix_that_nobody_cites_is_not_read(self):
        scenario = Scenario(PAYLOAD, ("good",), extra={"M3W-U1": ("M3W-0417", "v2", (result("FAIL"),))})
        self.assertEqual(set(scenario.decisions()), {ALLOWED})
        scenario = Scenario(FRESH, ("bad",), extra={"SCR-U1": ("SCR-S1042", "v2", (observed("2026-11-23T15:40:00Z"),))})
        self.assertEqual(set(scenario.decisions()), {REFUSED})


class AgeIsJudgedAtTheLimitOfTheRule(unittest.TestCase):
    """The rule allows 1 h, and the attempt is at 16:00:05Z. A record of exactly 1 h is within the limit and one that is a microsecond older is not."""

    def expect(self, expected, stated):
        """The record at the limit is listed with a fresher one, and it is the first and the second by id in turn."""
        for first, second in (("2026-11-23T15:40:00Z", stated), (stated, "2026-11-23T15:40:00Z")):
            copies = {"SCR-T0": ("SCR-S1042", "v2", (observed(first),)), "SCR-T1": ("SCR-S1042", "v2", (observed(second),))}
            model = with_age_limit(with_copies(support.example_model(), copies), 1)
            matching = [reference(record_id, "SCR-S1042") for record_id in copies]
            context = [STORED[i] for i in ("INV-2026-0417", "PO-77231", "GR-5521", "DUP-0417", "M3W-0417")]
            seen = decisions(model, FRESH, matching, context)
            self.assertEqual(set(seen), {expected}, seen)

    def test_exactly_the_limit_is_fresh_for_the_rule_beside_a_fresher_record(self):
        for stated in ("2026-11-23T15:00:05Z", "2026-11-23T16:00:05+01:00", "2026-11-23T15:00:05.000Z"):
            with self.subTest(stated):
                self.expect(ALLOWED, stated)

    def test_a_microsecond_older_than_the_limit_is_stale_for_the_rule_beside_a_fresher_record(self):
        for stated in ("2026-11-23T15:00:04.999999Z", "2026-11-23T16:00:04.999999+01:00"):
            with self.subTest(stated):
                self.expect(REFUSED, stated)

    def test_a_microsecond_inside_the_limit_is_fresh(self):
        self.expect(ALLOWED, "2026-11-23T15:00:05.000001Z")


class ARecordThatWasNotUsableIsRefusedForItsOwnReason(unittest.TestCase):
    """A record that had not been admitted by the attempt, or that was no longer current, is refused by the evidence checks. The rule does not count it, for or against."""

    def decide(self, precondition, rows):
        return Scenario(precondition, rows).decisions()

    def test_an_unusable_record_cannot_satisfy_a_rule_that_a_usable_one_fails(self):
        for precondition in (PAYLOAD, FRESH):
            for edit, code in ((not_yet_admitted, "EVIDENCE_NOT_YET_ADMITTED"), (superseded, "EVIDENCE_NOT_CURRENT")):
                with self.subTest(precondition, code=code):
                    seen = self.decide(precondition, ("bad", ("good", (edit,))))
                    self.assertEqual(set(seen), {(False, tuple(sorted((code, "PRECONDITION_FAILED"))))}, seen)

    def test_an_unusable_record_cannot_fail_a_rule_that_a_usable_one_satisfies(self):
        for precondition in (PAYLOAD, FRESH):
            for edit, code in ((not_yet_admitted, "EVIDENCE_NOT_YET_ADMITTED"), (superseded, "EVIDENCE_NOT_CURRENT")):
                with self.subTest(precondition, code=code):
                    seen = self.decide(precondition, ("good", ("bad", (edit,))))
                    self.assertEqual(set(seen), {(False, (code,))}, seen)

    def test_only_unusable_records_leave_the_rule_with_nothing_to_judge(self):
        for precondition in (PAYLOAD, FRESH):
            with self.subTest(precondition):
                seen = self.decide(precondition, (("good", (not_yet_admitted,)), ("good", (superseded,))))
                self.assertEqual(set(seen), {(False, ("EVIDENCE_NOT_CURRENT", "EVIDENCE_NOT_YET_ADMITTED", "PRECONDITION_FAILED"))}, seen)


if __name__ == "__main__":
    unittest.main()
