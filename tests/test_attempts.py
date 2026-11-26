"""One execution attempt is one entry of the ledger, whatever the receipts that describe it are called.

An execution attempt has an identity, `execution_attempt_id`. The versions of one receipt describe one attempt. Two receipts that claim the same attempt describe it twice, so they are a finding,
the ledger holds the attempt once, and the replay of the attempt leaves out every receipt of it, not only the ones that match it by proposal, grant and time. Different attempts remain different,
and each holds its own capacity.
"""
import copy
import unittest

import support  # noqa: F401  (puts scripts/ on the path)

from eahs import semantics
from eahs.gateway import attempt_receipt_ids, evaluate_commit, ledger_from_receipts, ts
from eahs.model import Instance, Model
from eahs.scenarios import evaluate_entry

B, TWIN = "RCP-REL-0417-B", "RCP-REL-0417-B2"
ATTEMPT = "ATT-REL-0417-B-1"
RELEASE, GRANT = ("ACT-REL-0417", "v2"), ("GRT-APPR-0417-B", "v1")
LATER = "2026-11-23T16:30:00Z"


def with_twin(new_id=TWIN, attempt=ATTEMPT, submitted=None, versions=("v1", "v2"), edit=None, base=None):
    """The example set with a second chain of receipts that copies the corrected release's receipt: another receipt id, the attempt `attempt` and the submission time `submitted`."""
    base = base or support.example_model()
    instances = dict(base.instances)
    for source in versions:
        stored = base.get("C07", B, source)
        data = copy.deepcopy(stored.data)
        data["identity_binding"]["receipt_id"] = new_id
        data["identity_binding"]["execution_attempt_id"] = attempt
        if submitted is not None:
            data["outcome"]["timestamps"]["submitted"] = submitted
        if edit:
            edit(source, data)
        instances[("C07", new_id, source)] = Instance("C07", new_id, source, data, stored.path.with_name(stored.path.name.replace(B, new_id, 1)))
    return Model(instances, base.registry, base.root)


def with_cap(model, cap):
    grant = model.get("C06", *GRANT)
    data = copy.deepcopy(grant.data)
    data["limits_lifecycle"]["cumulative_limits"][0]["quantity"] = cap
    instances = dict(model.instances)
    instances[("C06",) + GRANT] = Instance("C06", GRANT[0], GRANT[1], data, grant.path)
    return Model(instances, model.registry, model.root)


def entries(model, at, grant="GRT-APPR-0417-B"):
    return [(e.receipt, e.state, e.quantity) for e in ledger_from_receipts(model, ts(at)) if e.grant_id == grant]


def duplicates(model):
    return sorted((f.file.replace("\\", "/").rsplit("/", 1)[-1], f.location) for f in semantics.check_authority(model) if f.code == "ACC007")


class TheStoredAttemptsAreEachOnTheirOwn(unittest.TestCase):
    def test_no_attempt_is_claimed_twice(self):
        self.assertEqual(duplicates(support.example_model()), [])
        ids = [r.data["identity_binding"]["execution_attempt_id"] for r in support.example_model().of("C07")]
        self.assertEqual(len(set(ids)), 3)

    def test_the_versions_of_one_receipt_are_one_entry(self):
        self.assertEqual(entries(support.example_model(), "2026-11-23T16:10:00Z"), [(B, "reserved", 18400)])
        self.assertEqual(entries(support.example_model(), LATER), [(B, "consumed", 18400)])


class TwoReceiptsThatClaimOneAttemptAreFound(unittest.TestCase):
    def test_a_second_receipt_for_the_same_attempt_id_with_another_submission_time_is_found_in_both(self):
        model = with_twin(submitted="2026-11-23T16:00:06Z")
        self.assertEqual(duplicates(model), [("c07-RCP-REL-0417-B-v1.json", "/identity_binding/execution_attempt_id"), ("c07-RCP-REL-0417-B2-v1.json", "/identity_binding/execution_attempt_id")])

    def test_the_finding_names_the_attempt_and_the_other_receipt(self):
        messages = [f.message for f in semantics.check_authority(with_twin(submitted="2026-11-23T16:00:06Z")) if f.code == "ACC007"]
        self.assertEqual(len(messages), 2)
        self.assertIn(TWIN, messages[0])
        self.assertIn(B, messages[1])
        for message in messages:
            self.assertIn(ATTEMPT, message)

    def test_receipts_that_disagree_about_the_proposal_the_grant_or_the_target_are_found_and_say_so(self):
        def elsewhere(source, data):
            binding = data["identity_binding"]
            binding["proposal_reference"] = {"contract_id": "C05", "id": "ACT-REL-0417", "version": "v1"}
            binding["grant_reference"] = {"contract_id": "C06", "id": "GRT-APPR-0417-A", "version": "v1"}
            binding["target"] = {"entity_type": "invoice", "entity_id": "INV-2026-9999"}
        model = with_twin(edit=elsewhere)
        self.assertEqual([loc for _, loc in duplicates(model)], ["/identity_binding/execution_attempt_id"] * 2)
        messages = [f.message for f in semantics.check_authority(model) if f.code == "ACC007"]
        for part in ("proposal", "grant", "target"):
            self.assertIn(part, messages[0])

    def test_a_chain_whose_versions_name_two_attempts_is_not_a_second_receipt_for_the_attempt(self):
        """The later version of one receipt that names another attempt is ACC004. It is one receipt, and no other receipt claims either attempt."""
        base = support.example_model()
        stored = base.get("C07", B, "v2")
        data = copy.deepcopy(stored.data)
        data["identity_binding"]["execution_attempt_id"] = "ATT-REL-0417-B-2"
        instances = dict(base.instances)
        instances[("C07", B, "v2")] = Instance("C07", B, "v2", data, stored.path)
        model = Model(instances, base.registry, base.root)
        self.assertEqual(duplicates(model), [])
        self.assertIn("ACC004", [f.code for f in semantics.check_authority(model)])

    def test_different_attempt_ids_are_different_attempts(self):
        self.assertEqual(duplicates(with_twin(attempt="ATT-REL-0417-B-2", submitted="2026-11-23T16:00:06Z")), [])


class OneAttemptHoldsCapacityOnce(unittest.TestCase):
    def test_a_second_receipt_for_one_attempt_does_not_reserve_it_twice(self):
        model = with_twin(submitted="2026-11-23T16:00:06Z", versions=("v1",))
        self.assertEqual(len(entries(model, "2026-11-23T16:10:00Z")), 1)
        self.assertEqual(entries(model, "2026-11-23T16:10:00Z")[0][1:], ("reserved", 18400))

    def test_nor_does_it_consume_it_twice(self):
        model = with_twin(submitted="2026-11-23T16:00:06Z")
        self.assertEqual(len(entries(model, LATER)), 1)
        self.assertEqual(entries(model, LATER)[0][1:], ("consumed", 18400))

    def test_the_attempt_is_not_double_counted_against_a_cap_that_fits_it_once(self):
        """With a cap of 36,800, one attempt of 18,400 and a second action of 18,400 fit. Two copies of the one attempt would not."""
        model = with_cap(with_twin(submitted="2026-11-23T16:00:06Z"), 36800)
        decision = evaluate_commit(model, model.get("C05", *RELEASE), model.get("C06", *GRANT), ts(LATER), ledger_from_receipts(model, ts(LATER)))
        self.assertNotIn("CUMULATIVE_LIMIT", decision.codes)

    def test_two_copies_that_disagree_hold_the_larger_and_the_more_conservative_of_them_once(self):
        def smaller(source, data):
            data["outcome"]["state"] = "unknown"
            data["outcome"]["unresolved_conditions"] = ["Not known."]
            data["outcome"]["observed_effects"] = []
        model = with_twin(submitted="2026-11-23T16:00:06Z", edit=smaller)
        found = entries(model, LATER)
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0][1:], ("reserved", 18400), "one copy says consumed and the other says unknown: the attempt is held as reserved")

    def test_genuinely_different_attempts_hold_their_own_capacity(self):
        model = with_twin(attempt="ATT-REL-0417-B-2", submitted="2026-11-23T16:00:06Z", versions=("v1",))
        self.assertEqual([quantity for _, _, quantity in entries(model, "2026-11-23T16:10:00Z")], [18400, 18400])

    def test_separate_pending_attempts_use_up_the_cap_together(self):
        model = with_cap(with_twin(attempt="ATT-REL-0417-B-2", submitted="2026-11-23T16:00:06Z", versions=("v1",)), 36800)
        decision = evaluate_commit(model, model.get("C05", *RELEASE), model.get("C06", *GRANT), ts("2026-11-23T16:10:00Z"), ledger_from_receipts(model, ts("2026-11-23T16:10:00Z")))
        self.assertIn("CUMULATIVE_LIMIT", decision.codes)


class TheAttemptBeingReplayedIsLeftOutByItsIdentity(unittest.TestCase):
    def test_the_replay_leaves_out_every_receipt_of_the_attempt_and_not_only_those_that_match_it_by_time(self):
        model = with_twin(submitted="2026-11-23T16:00:04Z")
        proposal, grant = model.get("C05", *RELEASE), model.get("C06", *GRANT)
        self.assertEqual(attempt_receipt_ids(model, proposal, grant, ts("2026-11-23T16:00:05Z")), [B, TWIN])

    def test_the_stored_scenario_of_the_corrected_release_is_still_allowed_when_a_copy_was_submitted_just_before_it(self):
        """The copy is submitted at 16:00:04 and would hold the whole limit by 16:00:05 if it counted as another attempt."""
        model = with_twin(submitted="2026-11-23T16:00:04Z")
        entry = {"proposal": {"id": RELEASE[0], "version": RELEASE[1]}, "grant": {"id": GRANT[0], "version": GRANT[1]}, "at": "2026-11-23T16:00:05Z", "ledger": "from_receipts"}
        decision = evaluate_entry(model, entry)
        self.assertEqual((decision.allow, decision.codes), (True, []))

    def test_the_authority_check_does_not_find_the_attempt_blocked_by_its_own_copy(self):
        codes = [f.code for f in semantics.check_authority(with_twin(submitted="2026-11-23T16:00:04Z"))]
        self.assertNotIn("AUTH004", codes)
        self.assertEqual(codes.count("ACC007"), 2)

    def test_two_different_attempts_at_one_moment_are_still_ambiguous_for_the_replay(self):
        model = with_twin(attempt="ATT-REL-0417-B-2", submitted="2026-11-23T16:00:05Z", versions=("v1",))
        with self.assertRaises(ValueError) as refused:
            attempt_receipt_ids(model, model.get("C05", *RELEASE), model.get("C06", *GRANT), ts("2026-11-23T16:00:05Z"))
        self.assertIn("cannot tell which one is its own", str(refused.exception))

    def test_two_receipts_of_one_attempt_at_one_moment_are_not_ambiguous(self):
        model = with_twin(submitted="2026-11-23T16:00:05Z", versions=("v1",))
        self.assertEqual(attempt_receipt_ids(model, model.get("C05", *RELEASE), model.get("C06", *GRANT), ts("2026-11-23T16:00:05Z")), [B, TWIN])


if __name__ == "__main__":
    unittest.main()
