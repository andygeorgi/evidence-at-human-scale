"""A packet version is judged by the versions of its own packet, and a packet rests on every C02 record it cites.

The stored set has one packet, PKT-0417, in two versions: v1 (invalidated) and v2 (reviewed), and v2 lists v1 as its prior version. A newer version never replaces an older one, it supersedes it
(the conventions of the examples), so an older version that a newer one stands after is not active. That is read from the versions that exist, in the order their names give (see
`model.version_key`), and not from what a version says about itself: a newer version that lists no prior version still stands after the older one. What a version does list as a prior version
is checked as well: it must be an earlier version of the same packet. The records behind an active packet are one set, whatever part of the packet cites them: a claim, an inference, a conflict,
or the evidence behind a gap. A challenge link is not one of them.
"""
import copy
import itertools
import unittest
from pathlib import Path

import support  # noqa: F401  (puts scripts/ on the path)

from eahs import semantics
from eahs.model import Instance, Model

PKT = "PKT-0417"
GRANT_B = "c06-GRT-APPR-0417-B-v1.json"
NOT_CURRENT = ("withdrawn", "revoked", "expired", "superseded")
INACTIVE = ("invalidated", "superseded")


def file_of(version, pid=PKT):
    return "c04-%s-%s.json" % (pid, version)


def prior(*versions, pid=PKT):
    return [{"contract_id": "C04", "id": pid, "version": version} for version in versions]


def packet(version, state="awaiting_review", prior_to=(), pid=PKT, source="v2"):
    """A copy of a stored packet as another version of it (or as another packet), with a file name of its own. It lists no proposal, so nothing else in the set rests on it."""
    stored = support.example_model().get("C04", PKT, source)
    data = copy.deepcopy(stored.data)
    data["decision_context_as_of"].update(packet_id=pid, version=version)
    history = data["review_version_history"]
    history["state"] = state
    if state == "awaiting_review":
        history["actor"] = {"state": "not_applicable", "reason": "Review not performed."}
        history["time"] = {"state": "not_applicable", "reason": "Review not performed."}
    history["prior_version_references"] = list(prior_to)
    data["action_proposals"] = []
    return Instance("C04", pid, version, data, stored.path.with_name(file_of(version, pid)))


def the_set(*added, drop=(), edit=None, reverse=False):
    """The stored set with more instances, without some, and with edits to others (`edit`: {(contract, id, version): a function that changes a copy of its data}).

    `reverse` keeps the records in the opposite order, because nothing may depend on the order in which the records were read."""
    base = support.example_model()
    instances = {key: inst for key, inst in base.instances.items() if key not in drop}
    for key, change in (edit or {}).items():
        old = instances[key]
        data = copy.deepcopy(old.data)
        change(data)
        instances[key] = Instance(old.contract, old.id, old.version, data, old.path)
    for inst in added:
        instances[inst.key] = inst
    if reverse:
        instances = dict(reversed(list(instances.items())))
    return Model(instances, base.registry, base.root)


def in_history(**fields):
    return lambda data: data["review_version_history"].update(fields)


def life(model, *codes):
    """What the lifecycle check finds, as (code, file name), in a fixed order. Only the codes named, when there are any."""
    return sorted((f.code, Path(f.file).name) for f in semantics.check_lifecycle(model) if not codes or f.code in codes)


def revoked_approval_b():
    """The second approval, revoked as the first one is: what an approval of an inactive packet has to be."""
    revoked = copy.deepcopy(support.example_model().get("C06", "GRT-APPR-0417-A", "v1").data["limits_lifecycle"]["revocation"])
    return {("C06", "GRT-APPR-0417-B", "v1"): lambda data: data["limits_lifecycle"].update(revocation=revoked)}


def settled(*added, state="superseded"):
    """The stored set in which packet v2 has been given up the way a later version requires, and the approval that rests on it has been revoked with it."""
    edit = revoked_approval_b()
    edit[("C04", PKT, "v2")] = in_history(state=state)
    return the_set(*added, edit=edit)


class TheStoredChain(unittest.TestCase):
    def test_the_stored_set_has_no_lifecycle_finding(self):
        self.assertEqual(life(support.example_model()), [])

    def test_the_older_version_is_inactive_and_the_newer_one_is_active(self):
        model = support.example_model()
        self.assertEqual([(v, semantics.packet_active(model.get("C04", PKT, v))) for v in ("v1", "v2")], [("v1", False), ("v2", True)])

    def test_the_older_version_stays_inspectable_when_it_is_not_active(self):
        model = support.example_model()
        old = model.get("C04", PKT, "v1")
        self.assertEqual((old.data["review_version_history"]["state"], len(old.data["supported_claims_references"])), ("invalidated", 7))


class ANewerVersionMakesTheOlderOneInactiveWhateverItLists(unittest.TestCase):
    """The reported case: v3 is added in awaiting_review and lists no prior version, so v2, which is still reviewed, was not found."""

    def test_a_later_version_that_lists_no_prior_version_still_stands_after_the_active_one(self):
        for later in ("v3", "v4", "v10", "v100", "v2.1"):
            with self.subTest(later):
                self.assertEqual(life(the_set(packet(later))), [("LIFE004", file_of("v2"))])

    def test_the_finding_names_the_newer_version_and_where_the_state_is_to_be_changed(self):
        found = [f for f in semantics.check_lifecycle(the_set(packet("v3"))) if f.code == "LIFE004"]
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].location, "/review_version_history/state")
        self.assertIn("a newer packet version exists, so this version must be invalidated or superseded", found[0].message)
        self.assertIn("v3", found[0].message)

    def test_the_records_are_judged_the_same_in_any_order(self):
        added = [packet("v3"), packet("v4"), packet("v10")]
        for order in itertools.permutations(added):
            for reverse in (False, True):
                with self.subTest([p.version for p in order], reverse=reverse):
                    self.assertEqual(life(the_set(*order, reverse=reverse)), [("LIFE004", file_of("v2")), ("LIFE004", file_of("v3")), ("LIFE004", file_of("v4"))])

    def test_every_older_version_that_is_active_is_found_and_the_newest_is_not(self):
        model = the_set(packet("v3", "reviewed"), packet("v4", "reviewed"), packet("v5"))
        self.assertEqual(life(model, "LIFE004"), [("LIFE004", file_of(v)) for v in ("v2", "v3", "v4")])

    def test_the_state_of_the_newer_version_is_not_what_decides(self):
        for state in ("awaiting_review", "reviewed", "invalidated"):
            with self.subTest(state):
                self.assertEqual(life(the_set(packet("v3", state)), "LIFE004"), [("LIFE004", file_of("v2"))])

    def test_declaring_the_prior_version_changes_nothing_about_the_finding(self):
        for declared in ((), ("v2",), ("v1", "v2")):
            with self.subTest(declared):
                self.assertEqual(life(the_set(packet("v3", prior_to=prior(*declared))), "LIFE004"), [("LIFE004", file_of("v2"))])

    def test_an_older_version_that_is_given_up_is_not_found_and_its_approval_has_to_follow(self):
        for state in INACTIVE:
            with self.subTest(state):
                self.assertEqual(life(settled(packet("v3"), state=state)), [])

    def test_the_approval_of_a_packet_that_is_inactive_must_be_revoked_whichever_version_made_it_so(self):
        for state in INACTIVE:
            with self.subTest(state):
                model = the_set(packet("v3"), edit={("C04", PKT, "v2"): in_history(state=state)})
                self.assertEqual(life(model), [("LIFE005", GRANT_B)])

    def test_an_approval_that_is_revoked_with_its_packet_is_not_found(self):
        self.assertEqual(life(settled(packet("v3"))), [])

    def test_a_packet_that_is_left_active_is_one_finding_and_its_approval_follows_the_declared_state(self):
        """The older version is still reviewed: that is the finding. The approval follows the state the packet declares, so it becomes a second finding only when the version is given up and the approval is not revoked."""
        self.assertEqual(life(the_set(packet("v3"))), [("LIFE004", file_of("v2"))])

    def test_one_version_needs_no_chain(self):
        model = the_set(packet("v1", "reviewed", pid="PKT-0500"))
        self.assertEqual(life(model), [])

    def test_the_versions_of_another_packet_do_not_stand_after_this_one(self):
        model = the_set(packet("v9", pid="PKT-0418"))
        self.assertEqual(life(model), [])

    def test_the_versions_are_ordered_by_their_numbers_and_not_by_their_text(self):
        """v10 stands after v2 although "v10" sorts before "v2" as text."""
        self.assertEqual(life(settled(packet("v10", "reviewed"))), [])
        self.assertEqual(life(settled(packet("v9", "reviewed"), packet("v10"))), [("LIFE004", file_of("v9"))])

    def test_a_valid_chain_of_three_has_one_active_version(self):
        model = settled(packet("v10", "reviewed", prior_to=prior("v1", "v2")))
        self.assertEqual(life(model), [])
        self.assertEqual([v for v in ("v1", "v2", "v10") if semantics.packet_active(model.get("C04", PKT, v))], ["v10"])


class NamesThatCannotBeOrderedAreNeverGuessed(unittest.TestCase):
    """v2 and v02 are two versions with one place, and latest has none: which stands after which is not known, so neither is found by the other."""

    def test_two_active_versions_with_one_place_do_not_supersede_each_other(self):
        model = the_set(packet("v02", "reviewed"))
        self.assertEqual(life(model, "LIFE004"), [])
        self.assertEqual(life(model, "LIFE006"), [("LIFE006", file_of("v02")), ("LIFE006", file_of("v2"))])

    def test_a_name_with_no_number_stands_after_nothing_and_before_nothing(self):
        model = the_set(packet("latest"))
        self.assertEqual(life(model, "LIFE004"), [])
        self.assertEqual(life(model, "LIFE006"), [("LIFE006", file_of("latest"))])

    def test_a_version_that_is_before_a_later_one_is_found_whatever_the_names_beside_it_do(self):
        """Both v2 and v02 are before v3, however they stand to each other."""
        model = the_set(packet("v02", "reviewed"), packet("v3"))
        self.assertEqual(life(model, "LIFE004"), [("LIFE004", file_of("v02")), ("LIFE004", file_of("v2"))])
        self.assertEqual(life(model, "LIFE004"), life(the_set(packet("v02", "reviewed"), packet("v3"), reverse=True), "LIFE004"))


class APriorVersionIsAnEarlierVersionOfTheSamePacket(unittest.TestCase):
    """A packet lists the versions it comes after. Each must be a C04 packet that exists, a version of this packet, and before this version in the order of the names."""

    def found(self, model):
        return [(Path(f.file).name, f.location, f.message) for f in semantics.check_lifecycle(model) if f.code == "LIFE007"]

    def test_the_stored_prior_version_is_valid(self):
        self.assertEqual(self.found(support.example_model()), [])

    def test_any_earlier_version_may_be_listed_in_any_order(self):
        for name, model in (
            ("v2 lists v1", the_set()),
            ("v10 lists v2", settled(packet("v10", "reviewed", prior_to=prior("v2")))),
            ("v3 skips v2", the_set(packet("v3", prior_to=prior("v1")), edit={("C04", PKT, "v2"): in_history(state="superseded")})),
            ("v3 lists both", the_set(packet("v3", prior_to=prior("v1", "v2")))),
            ("v3 lists both, the other way", the_set(packet("v3", prior_to=prior("v2", "v1")))),
            ("a first version lists none", the_set(packet("v1", "reviewed", pid="PKT-0500"))),
        ):
            with self.subTest(name):
                self.assertEqual(self.found(model), [])

    def test_a_version_that_comes_after_this_one_is_not_a_prior_version(self):
        found = self.found(the_set(edit={("C04", PKT, "v1"): in_history(prior_version_references=prior("v2"))}))
        self.assertEqual([(f, loc) for f, loc, _ in found], [(file_of("v1"), "/review_version_history/prior_version_references/0")])
        self.assertIn("PKT-0417 v2 comes after this version (v1)", found[0][2])

    def test_a_forward_reference_does_not_make_the_version_it_names_the_one_that_is_found(self):
        model = the_set(edit={("C04", PKT, "v1"): in_history(prior_version_references=prior("v2"))})
        self.assertEqual(life(model), [("LIFE007", file_of("v1"))])

    def test_a_version_is_not_its_own_prior_version(self):
        found = self.found(the_set(edit={("C04", PKT, "v2"): in_history(prior_version_references=prior("v1", "v2"))}))
        self.assertEqual([(f, loc) for f, loc, _ in found], [(file_of("v2"), "/review_version_history/prior_version_references/1")])
        self.assertIn("PKT-0417 v2 is this version itself", found[0][2])
        self.assertEqual(life(the_set(edit={("C04", PKT, "v2"): in_history(prior_version_references=prior("v1", "v2"))})), [("LIFE007", file_of("v2"))])

    def test_another_packet_is_not_a_prior_version(self):
        for named in ("v1", "v2"):
            with self.subTest(named):
                other = packet("v2", "invalidated", prior_to=prior(named), pid="PKT-0418")
                found = self.found(the_set(other))
                self.assertEqual([(f, loc) for f, loc, _ in found], [(file_of("v2", "PKT-0418"), "/review_version_history/prior_version_references/0")])
                self.assertIn("a version of another packet", found[0][2])
                self.assertEqual(life(the_set(other)), [("LIFE007", file_of("v2", "PKT-0418"))], "the packet it names is not found for it")

    def test_a_reference_to_a_packet_that_does_not_exist_is_a_missing_reference_and_nothing_else(self):
        """Whatever its name is, an earlier one, a later one or one that cannot be put in order with this one: a packet that is not there is `REF004`'s finding and is not judged for its order."""
        for missing in ("v0", "v9", "v02", "latest"):
            with self.subTest(missing):
                model = the_set(edit={("C04", PKT, "v2"): in_history(prior_version_references=prior("v1", missing))})
                self.assertEqual(self.found(model), [])
                self.assertEqual([(f.code, f.location) for f in semantics.check_references(model)], [("REF004", "/review_version_history/prior_version_references/1")])

    def test_a_reference_to_another_packet_that_does_not_exist_is_both_a_missing_reference_and_another_packet(self):
        model = the_set(edit={("C04", PKT, "v2"): in_history(prior_version_references=prior("v1") + prior("v1", pid="PKT-9999"))})
        self.assertEqual([(f.code, f.location) for f in semantics.check_references(model)], [("REF004", "/review_version_history/prior_version_references/1")])
        found = self.found(model)
        self.assertEqual([(name, loc) for name, loc, _ in found], [(file_of("v2"), "/review_version_history/prior_version_references/1")])
        self.assertIn("a version of another packet", found[0][2])

    def test_a_reference_that_is_not_to_a_packet_is_not_a_prior_version(self):
        stored = [{"contract_id": "C02", "id": "INV-2026-0417", "version": "v1"}]
        found = self.found(the_set(edit={("C04", PKT, "v2"): in_history(prior_version_references=prior("v1") + stored)}))
        self.assertEqual([(f, loc) for f, loc, _ in found], [(file_of("v2"), "/review_version_history/prior_version_references/1")])
        self.assertIn("C02", found[0][2])

    def test_a_damaged_entry_is_left_to_the_schema_and_does_not_stop_the_check(self):
        for damaged in ("PKT-0417 v1", None, 7, {"contract_id": "C04", "version": "v1"}, {"contract_id": "C04", "id": PKT, "version": 1}):
            with self.subTest(repr(damaged)):
                model = the_set(edit={("C04", PKT, "v2"): in_history(prior_version_references=prior("v1") + [damaged])})
                self.assertEqual(self.found(model), [])
        for contract in (["C04"], None, 7):
            with self.subTest(contract):
                entry = {"contract_id": contract, "id": PKT, "version": "v1"}
                found = self.found(the_set(edit={("C04", PKT, "v2"): in_history(prior_version_references=prior("v1") + [entry])}))
                self.assertEqual([(f, loc) for f, loc, _ in found], [(file_of("v2"), "/review_version_history/prior_version_references/1")])
                self.assertIn("not C04", found[0][2])

    def test_a_version_listed_twice_is_found_once_and_says_how_often(self):
        for times in (2, 3):
            with self.subTest(times):
                found = self.found(the_set(edit={("C04", PKT, "v2"): in_history(prior_version_references=prior(*(["v1"] * times)))}))
                self.assertEqual([(f, loc) for f, loc, _ in found], [(file_of("v2"), "/review_version_history/prior_version_references")])
                self.assertIn("PKT-0417 v1 is listed %d times" % times, found[0][2])

    def test_a_name_that_cannot_be_ordered_with_this_one_is_not_shown_to_be_earlier(self):
        for other, why in (("v02", "has the same place in the order as v2"), ("latest", "has no number")):
            with self.subTest(other):
                model = the_set(packet(other, "invalidated"), edit={("C04", PKT, "v2"): in_history(prior_version_references=prior("v1", other))})
                found = self.found(model)
                self.assertEqual([(f, loc) for f, loc, _ in found], [(file_of("v2"), "/review_version_history/prior_version_references/1")])
                for part in ("PKT-0417 %s cannot be shown to come before this version (v2)" % other, "cannot be put in order", why):
                    self.assertIn(part, found[0][2])

    def test_a_chain_that_is_wrong_is_reported_and_not_repaired(self):
        """The invalid reference is one finding, and the declared link does not make the version it names look superseded."""
        model = the_set(edit={("C04", PKT, "v2"): in_history(prior_version_references=prior("v2"))})
        self.assertEqual(life(model), [("LIFE007", file_of("v2"))])

    def test_the_findings_do_not_depend_on_the_order_of_the_list_or_of_the_records(self):
        listed = prior("v1", "v2", "v1", "v0")
        expected = None
        for order in itertools.permutations(listed):
            for reverse in (False, True):
                model = the_set(edit={("C04", PKT, "v2"): in_history(prior_version_references=list(order))}, reverse=reverse)
                got = sorted((name, message) for name, _, message in self.found(model))
                if expected is None:
                    expected = got
                self.assertEqual(got, expected, [ref["version"] for ref in order])
        self.assertEqual(len(expected), 2, "the duplicated v1 and the version v2 that is this one")


def stored_v1():
    return support.example_model().get("C04", PKT, "v1").data


def support_ref(record_id, version="v1"):
    """A claim reference as the stored packets write it, pointing at another record."""
    ref = copy.deepcopy(support.example_model().get("C04", PKT, "v2").data["supported_claims_references"][0]["supporting_references"][0])
    ref.update(record_id=record_id, version=version)
    return ref


def inference_with(record_id):
    inference = copy.deepcopy(stored_v1()["labeled_inferences"][0])
    inference["supporting_references"] = [support_ref(record_id)]
    return inference


def conflict_with(record_id):
    conflict = copy.deepcopy(stored_v1()["conflicts_uncertainty"]["conflicts"][0])
    conflict["claim_references"] = [support_ref(record_id)]
    return conflict


def stale_gap_with(record_id):
    gap = copy.deepcopy(stored_v1()["coverage_omissions_gaps"]["missingness"][6])
    gap["available_record"] = {"record_id": record_id, "version": "v1"}
    return gap


#: Where a packet cites a C02 record: (a name, a function that puts a citation of the record into packet v2, where it stands). The dependency of an unavailable gap and the observation of a negative one
#: replace what the stored packet cites there; the others add to the packet.
PLACES = (
    ("a supported claim", lambda d, rid: d["supported_claims_references"][0]["supporting_references"].append(support_ref(rid)), "/supported_claims_references/0/supporting_references/1"),
    ("a labeled inference", lambda d, rid: d["labeled_inferences"].append(inference_with(rid)), "/labeled_inferences/0/supporting_references/0"),
    ("a conflict", lambda d, rid: d["conflicts_uncertainty"]["conflicts"].append(conflict_with(rid)), "/conflicts_uncertainty/conflicts/0/claim_references/0"),
    ("the dependency failure of an unavailable gap", lambda d, rid: d["coverage_omissions_gaps"]["missingness"][3].update(dependency_failure_reference={"record_id": rid, "version": "v1"}),
     "/coverage_omissions_gaps/missingness/3/dependency_failure_reference"),
    ("the observation of a negative gap", lambda d, rid: d["coverage_omissions_gaps"]["missingness"][4].update(observation_reference=support_ref(rid)),
     "/coverage_omissions_gaps/missingness/4/observation_reference"),
    ("the record behind a stale gap", lambda d, rid: d["coverage_omissions_gaps"]["missingness"].append(stale_gap_with(rid)), "/coverage_omissions_gaps/missingness/6/available_record"),
)
CHALLENGE = ("a challenge link", lambda d, rid: d["review_version_history"]["challenge_links"].append({"record_id": rid, "version": "v1"}), "/review_version_history/challenge_links/0")


def record(record_id, state, admitted=None):
    """New C02 records for the packet to cite: `record_id` v1 copied from a stored record, in this lifecycle state (and its replacement, a v2, when it is superseded). `admitted` moves its admission time."""
    stored = support.example_model().get("C02", "MON-TREASURY-0001", "v1")
    out = []
    for version, lifecycle in (("v1", {"state": state, "effective_time": "2026-11-23T15:30:00Z", "reason": "Changed for the test."}), ("v2", {"state": "current", "effective_time": "2026-11-23T15:30:00Z", "reason": "Replaces v1."})):
        if version == "v2" and state != "superseded":
            continue
        data = copy.deepcopy(stored.data)
        data["identity_schema"].update(record_id=record_id, version=version)
        data["lifecycle"] = dict(lifecycle)
        if version == "v1" and state == "superseded":
            data["lifecycle"]["replacement_reference"] = {"record_id": record_id, "version": "v2"}
        if admitted and version == "v1":
            data["producer_admission"]["admission_time"] = admitted
        out.append(Instance("C02", record_id, version, data, stored.path.with_name("c02-%s-%s.json" % (record_id, version))))
    return out


def resting_on(place, state, record_id="BASIS-X", admitted=None):
    """The stored set in which active packet v2 cites a record in this lifecycle state at this place, and nowhere else."""
    return the_set(*record(record_id, state, admitted), edit={("C04", PKT, "v2"): lambda d: place[1](d, record_id)})


class ThePacketRestsOnEveryC02RecordItCites(unittest.TestCase):
    def test_a_record_that_is_not_current_is_found_at_every_place_a_packet_cites_one(self):
        for place in PLACES:
            for state in NOT_CURRENT:
                with self.subTest(place[0], state=state):
                    found = [f for f in semantics.check_lifecycle(resting_on(place, state))]
                    self.assertEqual([(f.code, Path(f.file).name, f.location) for f in found], [("LIFE003", file_of("v2"), "/review_version_history/state")])
                    self.assertIn("packet is still active but cites BASIS-X v1 which is %s" % state, found[0].message)

    def test_a_current_record_is_found_nowhere(self):
        for place in PLACES:
            with self.subTest(place[0]):
                self.assertEqual(life(resting_on(place, "current")), [])

    def test_a_challenge_link_is_not_what_the_packet_rests_on(self):
        for state in NOT_CURRENT:
            with self.subTest(state):
                self.assertEqual(life(resting_on(CHALLENGE, state)), [])

    def test_the_stored_unavailable_gap_rests_on_a_current_record_and_is_not_found(self):
        pkt = support.example_model().get("C04", PKT, "v2")
        gap = pkt.data["coverage_omissions_gaps"]["missingness"][3]
        self.assertEqual(gap["state"], "unavailable")
        self.assertEqual(support.example_model().get("C02", gap["dependency_failure_reference"]["record_id"], gap["dependency_failure_reference"]["version"]).data["lifecycle"]["state"], "current")
        self.assertEqual(life(support.example_model()), [])

    def test_the_stored_dependency_failure_is_found_when_that_record_is_given_up(self):
        for state in NOT_CURRENT:
            with self.subTest(state):
                model = the_set(*record("MON-TREASURY-0001", state), drop=[("C02", "MON-TREASURY-0001", "v1")])
                found = [f for f in semantics.check_lifecycle(model)]
                self.assertEqual([(f.code, Path(f.file).name) for f in found], [("LIFE003", file_of("v2"))])
                self.assertIn("MON-TREASURY-0001 v1 which is %s" % state, found[0].message)

    def test_a_packet_that_is_not_active_may_cite_records_that_are_not_current(self):
        """Packet v1 is invalidated and cites superseded and withdrawn records in its claims, its inferences, its conflict and behind a stale gap. A packet that has been given up may cite them anywhere."""
        self.assertEqual(life(support.example_model()), [])
        for place in PLACES:
            with self.subTest(place[0]):
                def cite_and_give_up(d, place=place):
                    place[1](d, "BASIS-X")
                    d["review_version_history"]["state"] = "superseded"
                model = the_set(*record("BASIS-X", "withdrawn"), edit={**revoked_approval_b(), ("C04", PKT, "v2"): cite_and_give_up})
                self.assertEqual(life(model), [])

    def test_a_packet_that_cites_several_gives_one_finding_that_names_the_same_record_in_any_order(self):
        def two(d):
            PLACES[2][1](d, "BASIS-B")
            PLACES[3][1](d, "BASIS-A")
            PLACES[5][1](d, "BASIS-C")
        records = record("BASIS-A", "withdrawn") + record("BASIS-B", "revoked") + record("BASIS-C", "expired")
        model = the_set(*records, edit={("C04", PKT, "v2"): two})
        found = [f for f in semantics.check_lifecycle(model) if f.code == "LIFE003"]
        self.assertEqual(len(found), 1)
        self.assertIn("BASIS-A v1 which is withdrawn", found[0].message)

        def reversed_arrays(d):
            two(d)
            d["coverage_omissions_gaps"]["missingness"].reverse()
            d["conflicts_uncertainty"]["conflicts"].reverse()
            d["supported_claims_references"].reverse()
        again = [f for f in semantics.check_lifecycle(the_set(*records, edit={("C04", PKT, "v2"): reversed_arrays}, reverse=True)) if f.code == "LIFE003"]
        self.assertEqual([(f.message, f.location) for f in again], [(f.message, f.location) for f in found])

    def test_lifecycle_and_availability_read_the_same_records(self):
        """A record that is both not current and admitted after the packet's as-of time is found by both checks at every place, and a challenge link by neither."""
        late = "2026-11-23T14:11:00Z"
        for place in PLACES:
            with self.subTest(place[0]):
                model = resting_on(place, "withdrawn", admitted=late)
                self.assertEqual([f.location for f in semantics._check_packet_basis_available(model, model.get("C04", PKT, "v2")) if "BASIS-X" in f.message], [place[2]])
                self.assertEqual(life(model), [("LIFE003", file_of("v2"))])
        model = resting_on(CHALLENGE, "withdrawn", admitted=late)
        self.assertEqual([f for f in semantics._check_packet_basis_available(model, model.get("C04", PKT, "v2")) if "BASIS-X" in f.message], [])
        self.assertEqual(life(model), [])


if __name__ == "__main__":
    unittest.main()
