"""A not_retrieved entry rests on one completed retrieval unit of the selection that holds it, and that unit was attempted, completed and had completed by the selection's as-of time, in that order.

A retrieval unit is named by its id and by the version of the selection that lists it. An entry of a selection, or of a packet bound to that selection, must name that
selection's own version and a unit that the selection lists once and completed. It does not rest on a unit of another selection, even one with the same name, and it does not rest on a
run that finished after the cutoff or that is said to have finished before it started. Times are compared as instants and not as written.
"""
import unittest

import support  # noqa: F401  (puts scripts/ on the path)

from eahs import semantics
from eahs.cases import mutate_model

UNIT = "RETR-CREDIT-0417"
SEL = {"v1": "C03 SEL-0417 v1", "v2": "C03 SEL-0417 v2"}
PKT = {"v1": "C04 PKT-0417 v1", "v2": "C04 PKT-0417 v2"}
CODES = ("REF006", "MISS001", "MISS005")


def rep(target, path, value):
    return {"target": target, "ops": [{"op": "replace", "path": path, "value": value}]}


def add(target, path, value):
    return {"target": target, "ops": [{"op": "add", "path": path, "value": value}]}


def _position(items, wanted):
    return next(i for i, item in enumerate(items) if wanted(item))


def unit_at(version):
    return _position(support.example_model().get("C03", "SEL-0417", version).data["retrieval"], lambda u: u["retrieval_unit_id"] == UNIT)


def gap_at(version):
    return _position(support.example_model().get("C03", "SEL-0417", version).data["conflicts_gaps"]["missingness"], lambda m: m["state"] == "not_retrieved")


def packet_gap_at(version):
    return _position(support.example_model().get("C04", "PKT-0417", version).data["coverage_omissions_gaps"]["missingness"], lambda m: m["state"] == "not_retrieved")


def retrieval(version, completed=None, entry_completed=None, reference=None, in_selection=True, in_packet=True):
    """The mutations that change the credit-note retrieval of one snapshot: the completion time of the unit in the selection, and the entry that rests on it, in the selection and in the packet."""
    out = []
    if completed is not None:
        out.append(rep(SEL[version], "/retrieval/%d/completed_at" % unit_at(version), {"state": "known", "value": completed}))
    places = []
    if in_selection:
        places.append((SEL[version], "/conflicts_gaps/missingness/%d" % gap_at(version)))
    if in_packet:
        places.append((PKT[version], "/coverage_omissions_gaps/missingness/%d" % packet_gap_at(version)))
    for target, base in places:
        if entry_completed is not None:
            out.append(rep(target, base + "/completed_at", entry_completed))
        if reference is not None:
            out.append(rep(target, base + "/retrieval_reference/" + reference[0], reference[1]))
    return out


def found(*mutations):
    """(code, file name, location) of each finding about retrieval, in the references, the missingness and the packets."""
    model, _ = mutate_model(support.example_model(), list(mutations))
    findings = semantics.check_references(model) + semantics.check_missingness(model)
    return sorted((f.code, f.file.replace("\\", "/").rsplit("/", 1)[-1], f.location) for f in findings if f.code in CODES)


def entries(version, code, in_selection=True, in_packet=True):
    """The findings that an entry of the first or second snapshot gets, as the places where it stands. A reference that does not resolve is found at the reference, a label that is not justified at the entry."""
    suffix = "/retrieval_reference" if code == "REF006" else ""
    places = []
    if in_selection:
        places.append((code, "c03-SEL-0417-%s.json" % version, "/conflicts_gaps/missingness/%d%s" % (gap_at(version), suffix)))
    if in_packet:
        places.append((code, "c04-PKT-0417-%s.json" % version, "/coverage_omissions_gaps/missingness/%d%s" % (packet_gap_at(version), suffix)))
    return sorted(places)


class TheStoredEntriesRestOnTheirOwnSelection(unittest.TestCase):
    def test_nothing_is_found_in_the_stored_set(self):
        self.assertEqual(found(), [])

    def test_each_entry_names_its_own_selections_version_and_a_unit_that_selection_lists_once_and_completed(self):
        model = support.example_model()
        for version in ("v1", "v2"):
            selection = model.get("C03", "SEL-0417", version)
            for gaps in (selection.data["conflicts_gaps"]["missingness"], model.get("C04", "PKT-0417", version).data["coverage_omissions_gaps"]["missingness"]):
                entry = next(m for m in gaps if m["state"] == "not_retrieved")
                self.assertEqual(entry["retrieval_reference"], {"record_id": UNIT, "version": version})
                units = [u for u in selection.data["retrieval"] if u["retrieval_unit_id"] == UNIT]
                self.assertEqual([u["status"] for u in units], ["completed"])

    def test_the_second_selection_carries_the_earlier_run_forward_under_its_own_version(self):
        """The run finished at 09:52 and the second snapshot is as of 14:10. It lists the unit again, and its entry names the second version."""
        model = support.example_model()
        first, second = (model.get("C03", "SEL-0417", v).data["retrieval"][unit_at(v)]["completed_at"]["value"] for v in ("v1", "v2"))
        self.assertEqual((first, second), ("2026-11-23T09:52:00Z", "2026-11-23T09:52:00Z"))
        self.assertEqual(found(), [])


class TheRetrievalHadCompletedByTheCutoff(unittest.TestCase):
    """The first snapshot is as of 10:00:00Z."""

    def test_one_microsecond_after_the_cutoff_is_after_it(self):
        for stated in ("2026-11-23T10:00:00.000001Z", "2026-11-23T11:00:00.000001+01:00"):
            with self.subTest(stated):
                self.assertEqual(found(*retrieval("v1", completed=stated, entry_completed=stated)), sorted(entries("v1", "MISS001")))

    def test_the_finding_says_when_it_finished_and_what_the_cutoff_is(self):
        stated = "2026-11-23T10:00:00.000001Z"
        model, _ = mutate_model(support.example_model(), retrieval("v1", completed=stated, entry_completed=stated))
        messages = [f.message for f in semantics.check_missingness(model) if f.code == "MISS001"]
        self.assertTrue(messages)
        for part in (stated, "2026-11-23T10:00:00Z", "after"):
            self.assertIn(part, messages[0])

    def test_one_microsecond_before_the_cutoff_and_exactly_at_it_are_within_it(self):
        for stated in ("2026-11-23T09:59:59.999999Z", "2026-11-23T10:00:00Z", "2026-11-23T11:00:00+01:00", "2026-11-23T10:00:00.000000Z"):
            with self.subTest(stated):
                self.assertEqual(found(*retrieval("v1", completed=stated, entry_completed=stated)), [])

    def test_the_same_instant_written_two_ways_is_one_completion_time(self):
        """The unit says 11:00:00+01:00 and the entry says 10:00:00Z, or the other way round: they are the same instant."""
        self.assertEqual(found(*retrieval("v1", completed="2026-11-23T11:00:00+01:00", entry_completed="2026-11-23T10:00:00Z")), [])
        self.assertEqual(found(*retrieval("v1", completed="2026-11-23T10:00:00Z", entry_completed="2026-11-23T11:00:00+01:00")), [])
        self.assertEqual(found(*retrieval("v1", completed="2026-11-23T09:52:00Z", entry_completed="2026-11-23T10:52:00+01:00")), [])

    def test_another_instant_is_another_completion_time(self):
        self.assertEqual(found(*retrieval("v1", entry_completed="2026-11-23T09:52:00.000001Z")), sorted(entries("v1", "MISS001")))
        self.assertEqual(found(*retrieval("v1", entry_completed="2026-11-23T09:52:00+01:00")), sorted(entries("v1", "MISS001")))

    def test_a_completion_time_that_is_not_known_cannot_be_shown_to_come_first(self):
        unknown = {"state": "unknown", "reason": "The service did not report when it finished."}
        model, _ = mutate_model(support.example_model(), [rep(SEL["v1"], "/retrieval/%d/completed_at" % unit_at("v1"), unknown)])
        self.assertEqual([f.code for f in semantics.check_missingness(model) if f.code == "MISS001"], ["MISS001", "MISS001"])

    def test_a_completion_time_that_cannot_be_compared_exactly_is_not_trusted(self):
        finer = "2026-11-23T09:52:00.0000001Z"
        self.assertEqual({c for c, _, _ in found(*retrieval("v1", completed=finer, entry_completed=finer))}, {"MISS001"})

    def test_a_cutoff_that_cannot_be_compared_exactly_is_an_input_error_that_names_the_selection(self):
        model, _ = mutate_model(support.example_model(), [rep(SEL["v1"], "/identity_scope/as_of", "2026-11-23T10:00:00.0000001Z")])
        with self.assertRaises(ValueError) as caught:
            semantics.check_missingness(model)
        for part in ("c03-SEL-0417-v1.json", "SEL-0417 v1", "2026-11-23T10:00:00.0000001Z", "Correct the time"):
            self.assertIn(part, str(caught.exception))

    def test_the_second_snapshot_is_held_to_its_own_cutoff(self):
        """The second snapshot is as of 14:10:00Z. A run that finished at 14:10:00.000001Z is after it, whatever the first snapshot says."""
        late = "2026-11-23T14:10:00.000001Z"
        self.assertEqual(found(*retrieval("v2", completed=late, entry_completed=late)), sorted(entries("v2", "MISS001")))
        on_time = "2026-11-23T14:10:00Z"
        self.assertEqual(found(*retrieval("v2", completed=on_time, entry_completed=on_time)), [])


class TheEntryNamesTheUnitOfItsOwnSelection(unittest.TestCase):
    def test_a_first_snapshot_entry_that_names_the_identically_named_unit_of_the_second_selection_is_found(self):
        self.assertEqual(found(*retrieval("v1", reference=("version", "v2"))), entries("v1", "REF006"))

    def test_nor_is_a_genuinely_distinct_later_run_of_the_second_selection_the_run_of_the_first(self):
        """The second selection ran the retrieval again at 13:52. The first snapshot, as of 10:00, cannot rest on it, whatever name it has."""
        later = "2026-11-23T13:52:00Z"
        second = retrieval("v2", completed=later, entry_completed=later)
        self.assertEqual(found(*second), [], "the second snapshot is coherent with its own run")
        self.assertEqual(found(*second, *retrieval("v1", reference=("version", "v2"))), entries("v1", "REF006"))

    def test_a_version_that_does_not_exist_is_found(self):
        self.assertEqual(found(*retrieval("v1", reference=("version", "v9"))), entries("v1", "REF006"))

    def test_a_version_that_exists_but_is_not_that_of_the_packets_own_selection_is_found(self):
        """The packet is bound to the first selection and names the unit of the second. The second exists, but the packet's selection is the first."""
        got = found(*retrieval("v1", reference=("version", "v2"), in_selection=False))
        self.assertEqual(sorted(c for c, _, _ in got), ["MISS005", "REF006"], "the packet also differs from the gap of its selection")
        self.assertIn(("REF006", "c04-PKT-0417-v1.json", "/coverage_omissions_gaps/missingness/%d/retrieval_reference" % packet_gap_at("v1")), got)

    def test_an_entry_of_the_second_snapshot_that_names_the_first_version_is_found(self):
        self.assertEqual(found(*retrieval("v2", reference=("version", "v1"))), entries("v2", "REF006"))

    def test_a_unit_that_the_selection_does_not_list_is_found(self):
        got = found(*retrieval("v1", reference=("record_id", "RETR-NOPE-0417")))
        self.assertEqual(sorted({c for c, _, _ in got}), ["MISS001", "REF006"])

    def test_a_unit_that_the_selection_lists_twice_is_ambiguous(self):
        model = support.example_model()
        twin = dict(model.get("C03", "SEL-0417", "v1").data["retrieval"][unit_at("v1")])
        got = found(add(SEL["v1"], "/retrieval/-", twin))
        self.assertEqual([c for c, _, _ in got if c == "REF006"], ["REF006", "REF006"], "the entry of the selection and the entry of its packet")

    def test_a_unit_that_did_not_complete_is_found_in_the_entry_of_its_selection_and_of_its_packet(self):
        """The same case as CASE-MISS-03, and the same two codes."""
        got = found(rep(SEL["v1"], "/retrieval/%d/status" % unit_at("v1"), "failed"))
        self.assertEqual(sorted({c for c, _, _ in got}), ["MISS001", "REF006"])

    def test_the_finding_names_the_entry_the_reference_and_the_selection_it_belongs_to(self):
        model, _ = mutate_model(support.example_model(), retrieval("v1", reference=("version", "v2")))
        messages = [f.message for f in semantics.check_references(model) if f.code == "REF006"]
        self.assertTrue(messages)
        for part in (UNIT, "v2", "SEL-0417 v1"):
            self.assertIn(part, messages[0])


def attempted(version, value):
    """The mutation that sets when the credit-note retrieval of one snapshot was attempted. A string is a known time, and anything else is the whole time value."""
    return rep(SEL[version], "/retrieval/%d/attempted_at" % unit_at(version), {"state": "known", "value": value} if isinstance(value, str) else value)


class TheRetrievalWasAttemptedBeforeItCompleted(unittest.TestCase):
    """The unit that an empty result rests on was attempted, completed and had completed by the as-of time of its selection, in that order: attempted_at <= completed_at <= as_of.

    The first snapshot is as of 10:00:00Z, and its unit was attempted and completed at 09:52:00Z. Equality is valid at both steps, and the times are compared as instants.
    """

    COMPLETED = "2026-11-23T09:52:00Z"

    def test_a_retrieval_attempted_before_it_completed_or_when_it_completed_is_valid(self):
        for stated in ("2026-11-23T09:51:59.999999Z", "2026-11-23T09:52:00Z", "2026-11-23T09:00:00Z"):
            with self.subTest(stated):
                self.assertEqual(found(attempted("v1", stated)), [])

    def test_the_same_instant_in_another_offset_or_precision_is_the_same_instant(self):
        for stated in ("2026-11-23T10:52:00+01:00", "2026-11-23T09:52:00.000Z", "2026-11-23T09:52:00.000000+00:00", "2026-11-23T08:52:00-01:00"):
            with self.subTest(stated):
                self.assertEqual(found(attempted("v1", stated)), [])

    def test_a_retrieval_attempted_after_it_completed_is_not_a_completed_empty_result(self):
        for stated in ("2026-11-23T09:52:00.000001Z", "2026-11-23T10:52:00.000001+01:00", "2026-11-23T09:53:00Z", "2026-11-23T11:00:00Z"):
            with self.subTest(stated):
                self.assertEqual(found(attempted("v1", stated)), sorted(entries("v1", "MISS001")), "in the entry of the selection and in the entry of its packet, and in nothing else")

    def test_a_retrieval_attempted_after_the_cutoff_that_says_it_completed_before_it_is_found(self):
        self.assertEqual(found(attempted("v1", "2026-11-23T10:00:01Z")), sorted(entries("v1", "MISS001")))

    def test_a_completion_exactly_at_the_cutoff_is_valid_and_one_microsecond_after_it_is_not(self):
        """At the cutoff itself the retrieval may have started at it or earlier. A completion after it is found by the cutoff, whatever the retrieval started."""
        at_cutoff = "2026-11-23T10:00:00Z"
        for started in (self.COMPLETED, at_cutoff):
            with self.subTest("completed at the cutoff, attempted " + started):
                self.assertEqual(found(attempted("v1", started), *retrieval("v1", completed=at_cutoff, entry_completed=at_cutoff)), [])
        late = "2026-11-23T10:00:00.000001Z"
        for started in (self.COMPLETED, at_cutoff, late):
            with self.subTest("completed a microsecond after the cutoff, attempted " + started):
                self.assertEqual(found(attempted("v1", started), *retrieval("v1", completed=late, entry_completed=late)), sorted(entries("v1", "MISS001")))

    def test_both_orders_are_reported_when_both_are_wrong(self):
        late, later = "2026-11-23T10:00:01Z", "2026-11-23T10:00:02Z"
        model, _ = mutate_model(support.example_model(), [attempted("v1", later), *retrieval("v1", completed=late, entry_completed=late)])
        messages = sorted(f.message for f in semantics.check_missingness(model) if f.code == "MISS001" and f.file.endswith("c03-SEL-0417-v1.json"))
        self.assertEqual(len(messages), 2)
        self.assertTrue(any(later in m and late in m and "attempted" in m for m in messages))
        self.assertTrue(any(late in m and "2026-11-23T10:00:00Z" in m and "after the as-of time" in m for m in messages))

    def test_a_start_that_is_not_known_or_cannot_be_compared_exactly_cannot_be_shown_to_come_first(self):
        for stated in ({"state": "unknown", "reason": "The service did not report when it started."}, {"state": "not_applicable", "reason": "The retrieval was not started by a run."},
                       "2026-11-23T09:51:00.0000001Z", "not a time"):
            with self.subTest(str(stated)):
                self.assertEqual(found(attempted("v1", stated)), sorted(entries("v1", "MISS001")))

    def test_the_finding_names_the_unit_and_both_times(self):
        model, _ = mutate_model(support.example_model(), [attempted("v1", "2026-11-23T09:52:00.000001Z")])
        messages = [f.message for f in semantics.check_missingness(model) if f.code == "MISS001"]
        self.assertEqual(len(messages), 2)
        for part in (UNIT, "2026-11-23T09:52:00.000001Z", self.COMPLETED, "attempted"):
            self.assertIn(part, messages[0])

    def test_each_snapshot_is_held_to_the_unit_of_its_own_selection(self):
        """The second selection lists the unit again. A start after the completion in one of them is found in that snapshot and not in the other."""
        for version in ("v1", "v2"):
            with self.subTest(version):
                self.assertEqual(found(attempted(version, "2026-11-23T09:52:00.000001Z")), sorted(entries(version, "MISS001")))
        self.assertEqual(found(attempted("v2", "2026-11-23T09:52:00.000001Z"), attempted("v1", "2026-11-23T09:51:00Z")), sorted(entries("v2", "MISS001")))

    def test_the_wrong_version_of_the_reference_is_still_found_and_the_chronology_is_judged_in_the_selection_of_the_entry(self):
        """The entry of the first snapshot names the unit of the second selection, which was started after it completed. The first snapshot's own unit is in order: the reference is wrong, and that is all that is wrong."""
        got = found(attempted("v2", "2026-11-23T09:52:00.000001Z"), *retrieval("v1", reference=("version", "v2")))
        self.assertEqual(got, sorted(entries("v1", "REF006") + entries("v2", "MISS001")))

    def test_an_unrelated_retrieval_that_was_started_late_is_not_asked_to_be_a_completed_empty_result(self):
        """Only the unit that a not_retrieved entry rests on is held to the order. The other units of the selection are not, whatever they say."""
        other = next(i for i, u in enumerate(support.example_model().get("C03", "SEL-0417", "v1").data["retrieval"]) if u["retrieval_unit_id"] == "RETR-ERP-0417")
        self.assertEqual(found(rep(SEL["v1"], "/retrieval/%d/attempted_at" % other, {"state": "known", "value": "2026-11-23T09:46:00Z"})), [])


if __name__ == "__main__":
    unittest.main()
