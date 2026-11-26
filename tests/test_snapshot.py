"""A decision snapshot is one context, one selection and one packet, and the packet rests on what was available at its as-of time.

The context (C01), the selection built under it (C03) and the packet built on both (C04) state one as-of time, compared as instants and not as
written. The selection reads no time that its context does not cover. The packet cites only evidence that was available at its as-of time, and a
proposal (C05) rests on the context of the packet it is bound to. These are decision-time checks on the snapshot. The commit-time checks of the
gateway ask another question at another time, and a later correction does not make an earlier snapshot wrong.
"""
import unittest

import support  # noqa: F401  (puts scripts/ on the path)

from eahs import semantics
from eahs.cases import mutate_model, run_case
from eahs.gateway import same_instant

CTX1, CTX2 = "C01 CTX-0417 v1", "C01 CTX-0417 v2"
SEL1 = "C03 SEL-0417 v1"
PKT1, PKT2 = "C04 PKT-0417 v1", "C04 PKT-0417 v2"
GOODS_RECEIPT, MATCH, MONITOR = "C02 GR-5521 v2", "C02 M3W-0417 v2", "C02 MON-TREASURY-0001 v1"
ADMITTED, INGESTED = "/producer_admission/admission_time", "/times/ingestion"
CONTEXT_TIME, SELECTION_TIME, PACKET_TIME = "/time_risk_policy/as_of", "/identity_scope/as_of", "/decision_context_as_of/as_of"
CONTEXT_END, SELECTION_END = "/time_risk_policy/time_interval/end", "/identity_scope/time_scope/end"


def rep(path, value):
    return {"op": "replace", "path": path, "value": value}


def change(target, *ops):
    return {"target": target, "ops": list(ops)}


def codes(*mutations):
    """The codes the whole pipeline (schema, then semantics) reports once every mutation is applied."""
    found, _ = run_case(support.example_model(), support.schema(), {"mutations": list(mutations)})
    return found


def packet_findings(*mutations):
    model, _ = mutate_model(support.example_model(), list(mutations))
    return semantics.check_packets(model)


def where(findings):
    """(code, file name, location) of each finding, in a fixed order."""
    return sorted((f.code, f.file.replace("\\", "/").rsplit("/", 1)[-1], f.location) for f in findings)


class TheStoredSnapshotsAreCoherent(unittest.TestCase):
    def test_each_context_selection_and_packet_states_one_time_and_the_packet_rests_on_what_was_available(self):
        model = support.example_model()
        for version in ("v1", "v2"):
            context, selection, packet = model.get("C01", "CTX-0417", version), model.get("C03", "SEL-0417", version), model.get("C04", "PKT-0417", version)
            self.assertEqual(context.data["time_risk_policy"]["as_of"], selection.data["identity_scope"]["as_of"])
            self.assertEqual(selection.data["identity_scope"]["as_of"], packet.data["decision_context_as_of"]["as_of"])
        self.assertEqual(semantics.check_packets(model), [])


class AContextAndTheSnapshotBuiltUnderItStateOneTime(unittest.TestCase):
    MOVED = [rep(CONTEXT_TIME, "2026-11-23T10:01:00Z"), rep(CONTEXT_END, "2026-11-23T10:01:00Z")]

    def test_a_context_that_moves_its_as_of_time_while_its_selection_and_packet_stay_is_found(self):
        self.assertEqual(codes(change(CTX1, *self.MOVED)), ["PKT002"])
        found = packet_findings(change(CTX1, *self.MOVED))
        self.assertEqual(where(found), [("PKT002", "c03-SEL-0417-v1.json", "/identity_scope/as_of"), ("PKT002", "c04-PKT-0417-v1.json", "/decision_context_as_of/as_of")])
        for finding in found:
            for part in ("2026-11-23T10:00:00Z", "2026-11-23T10:01:00Z", "CTX-0417 v1"):
                self.assertIn(part, finding.message)

    def test_the_second_snapshot_is_held_to_the_same(self):
        moved = [rep(CONTEXT_TIME, "2026-11-23T14:11:00Z"), rep(CONTEXT_END, "2026-11-23T14:11:00Z")]
        self.assertEqual(codes(change(CTX2, *moved)), ["PKT002"])

    def test_the_as_of_time_of_the_context_alone_is_enough(self):
        self.assertEqual(codes(change(CTX1, rep(CONTEXT_TIME, "2026-11-23T10:01:00Z"))), ["PKT002"])

    def test_a_selection_that_moves_its_as_of_time_is_found_against_its_context_and_its_packet(self):
        found = packet_findings(change(SEL1, rep(SELECTION_TIME, "2026-11-23T10:01:00Z")))
        self.assertEqual(where(found), [("PKT002", "c03-SEL-0417-v1.json", "/identity_scope/as_of"), ("PKT002", "c04-PKT-0417-v1.json", "/decision_context_as_of/as_of")])

    def test_a_packet_that_moves_its_as_of_time_is_found_against_its_selection_and_its_context(self):
        found = packet_findings(change(PKT1, rep(PACKET_TIME, "2026-11-23T10:01:00Z")))
        self.assertEqual(where(found), [("PKT002", "c04-PKT-0417-v1.json", "/decision_context_as_of/as_of")] * 2)
        self.assertTrue(any("its selection SEL-0417 v1" in f.message for f in found))
        self.assertTrue(any("its context CTX-0417 v1" in f.message for f in found))

    def test_a_selection_that_reads_beyond_the_interval_of_its_context_is_found(self):
        found = packet_findings(change(SEL1, rep(SELECTION_END, "2026-11-23T10:01:00Z")))
        self.assertEqual(where(found), [("PKT002", "c03-SEL-0417-v1.json", "/identity_scope/time_scope")])
        self.assertIn("ends after the interval", found[0].message)
        found = packet_findings(change(SEL1, rep("/identity_scope/time_scope/start", "2025-11-23T00:00:00Z")))
        self.assertEqual(where(found), [("PKT002", "c03-SEL-0417-v1.json", "/identity_scope/time_scope")])
        self.assertIn("starts before the interval", found[0].message)

    def test_a_selection_may_read_less_of_the_interval_than_its_context_covers(self):
        """How much of the interval was read is a matter of coverage, which the packet states. The snapshot rule is only that nothing outside the interval was read."""
        for op in (rep("/identity_scope/time_scope/start", "2026-01-01T00:00:00Z"), rep(SELECTION_END, "2026-11-23T09:00:00Z")):
            with self.subTest(op["path"]):
                self.assertEqual(packet_findings(change(SEL1, op)), [])


class TheSameInstantWrittenAnotherWayIsOneTime(unittest.TestCase):
    SPELLINGS = ("2026-11-23T10:00:00Z", "2026-11-23T11:00:00+01:00", "2026-11-23T12:00:00+02:00", "2026-11-23T09:00:00-01:00", "2026-11-23T10:00:00.000Z", "2026-11-23T10:00:00.000000+00:00")

    def snapshot(self, context, selection, packet):
        return [change(CTX1, rep(CONTEXT_TIME, context), rep(CONTEXT_END, context)),
                change(SEL1, rep(SELECTION_TIME, selection), rep(SELECTION_END, selection)),
                change(PKT1, rep(PACKET_TIME, packet))]

    def test_one_instant_written_in_different_ways_is_one_snapshot(self):
        for i in range(len(self.SPELLINGS)):
            context, selection, packet = (self.SPELLINGS[(i + k) % len(self.SPELLINGS)] for k in range(3))
            with self.subTest(context=context, selection=selection, packet=packet):
                self.assertEqual(packet_findings(*self.snapshot(context, selection, packet)), [])
        self.assertEqual(codes(*self.snapshot(*self.SPELLINGS[1:4])), [])

    def test_another_instant_is_another_time(self):
        for other in ("2026-11-23T10:00:00+01:00", "2026-11-23T10:00:00.000001Z", "2026-11-23T09:59:59Z"):
            with self.subTest(other):
                self.assertIn("PKT002", codes(change(PKT1, rep(PACKET_TIME, other))))

    def test_the_comparison_reads_instants_and_compares_the_text_only_when_a_time_cannot_be_read(self):
        self.assertTrue(same_instant("2026-11-23T10:00:00Z", "2026-11-23T11:00:00+01:00"))
        self.assertTrue(same_instant("2026-11-23T10:00:00.000Z", "2026-11-23T10:00:00+00:00"))
        self.assertFalse(same_instant("2026-11-23T10:00:00Z", "2026-11-23T10:00:00.000001Z"))
        self.assertFalse(same_instant("2026-11-23T10:00:00Z", "2026-11-23T10:00:00+01:00"))
        finer_than_a_microsecond = "2026-11-23T10:00:00.0000001Z"
        self.assertTrue(same_instant(finer_than_a_microsecond, finer_than_a_microsecond))
        self.assertFalse(same_instant(finer_than_a_microsecond, "2026-11-23T10:00:00Z"))


class TheEvidenceAPacketRestsOnWasAvailableAtItsAsOfTime(unittest.TestCase):
    """The second packet is as of 14:10. A record it cites must have been admitted and ingested by then, and a time equal to the as-of time was reached."""

    LATE = "2026-11-23T14:11:00Z"

    def late(self, label, when=LATE, *paths):
        return change(label, *[rep(path, when) for path in (paths or (ADMITTED, INGESTED))])

    def test_support_that_became_available_after_the_cutoff_is_found(self):
        for label in (GOODS_RECEIPT, MATCH, MONITOR):
            with self.subTest(label):
                # The match result is derived from the goods receipt, so a receipt that came after the match result was admitted was not available to it either (LIN008).
                self.assertEqual(codes(self.late(label)), ["LIN008", "PKT007"] if label == GOODS_RECEIPT else ["PKT007"])

    def test_the_finding_names_the_record_the_cutoff_and_the_place_the_packet_cites_it(self):
        """The receipt is cited as a claim of its own, and the match result, which is derived from it, is cited as another: the second is found through the first."""
        found = packet_findings(self.late(GOODS_RECEIPT))
        self.assertEqual(where(found), [("PKT007", "c04-PKT-0417-v2.json", "/supported_claims_references/2/supporting_references/0"),
                                        ("PKT007", "c04-PKT-0417-v2.json", "/supported_claims_references/3/supporting_references/0")])
        for part in ("2026-11-23T14:10:00Z", "GR-5521 v2", "was admitted at 2026-11-23T14:11:00Z", "after the packet's as-of time"):
            self.assertIn(part, found[0].message)

    def test_either_time_alone_is_enough(self):
        for path, word in ((ADMITTED, "admitted"), (INGESTED, "ingested")):
            with self.subTest(word):
                found = packet_findings(self.late(GOODS_RECEIPT, self.LATE, path))
                self.assertEqual([f.code for f in found], ["PKT007", "PKT007"], "the receipt, and the match result that is derived from it")
                self.assertIn("was %s at 2026-11-23T14:11:00Z" % word, found[0].message)

    def test_a_record_available_exactly_at_the_cutoff_is_available(self):
        self.assertEqual(packet_findings(self.late(GOODS_RECEIPT, "2026-11-23T14:10:00Z")), [])
        self.assertEqual(packet_findings(self.late(GOODS_RECEIPT, "2026-11-23T15:10:00+01:00", ADMITTED), self.late(GOODS_RECEIPT, "2026-11-23T14:10:00Z", INGESTED)), [])

    def test_the_smallest_step_after_the_cutoff_is_after_it(self):
        self.assertEqual(codes(self.late(GOODS_RECEIPT, "2026-11-23T14:10:00.000001Z")), ["LIN008", "PKT007"])

    def test_support_of_an_inference_is_held_to_the_cutoff_too(self):
        found = packet_findings(change("C02 SUM-A-0417 v1", rep(ADMITTED, "2026-11-23T10:00:01Z")))
        self.assertEqual([(f.code, f.location) for f in found], [("PKT007", "/labeled_inferences/0/supporting_references/0")])

    def test_a_record_that_was_never_admitted_is_no_basis_at_any_time(self):
        found = packet_findings(change(GOODS_RECEIPT, rep("/producer_admission/admission_status", "quarantined")))
        self.assertEqual([f.code for f in found], ["PKT007", "PKT007"], "the receipt, and the match result that is derived from it")
        self.assertIn("admission status 'quarantined'", found[0].message)

    def test_a_record_whose_admission_time_cannot_be_read_cannot_be_shown_to_be_available(self):
        found = packet_findings(change(GOODS_RECEIPT, rep(ADMITTED, "unknown")))
        self.assertEqual([f.code for f in found], ["PKT007", "PKT007"], "the receipt, and the match result that is derived from it")
        self.assertIn("missing or unknown", found[0].message)

    def test_a_challenge_link_may_name_evidence_that_arrived_after_the_packet(self):
        """The first packet was invalidated by GR-5521 v2, admitted long after the packet's as-of time. The link says why the packet was challenged and is not what it rests on."""
        model = support.example_model()
        packet = model.get("C04", "PKT-0417", "v1")
        link = packet.data["review_version_history"]["challenge_links"][0]
        record = model.get("C02", link["record_id"], link["version"])
        self.assertGreater(record.data["producer_admission"]["admission_time"], packet.data["decision_context_as_of"]["as_of"])
        self.assertEqual(semantics.check_packets(model), [])

    def test_a_later_correction_does_not_make_the_earlier_packet_wrong(self):
        """The first packet rests on GR-5521 v1, which was current at its as-of time and was superseded afterwards. A packet is judged by what was available then."""
        model = support.example_model()
        self.assertEqual(model.get("C02", "GR-5521", "v1").data["lifecycle"]["state"], "superseded")
        self.assertEqual([f for f in semantics.check_packets(model) if f.file.endswith("c04-PKT-0417-v1.json")], [])

    def test_a_cutoff_that_cannot_be_read_is_an_input_error_that_names_the_packet(self):
        unreadable = "2026-11-23T10:00:00.0000001Z"
        model, _ = mutate_model(support.example_model(), [change(PKT1, rep(PACKET_TIME, unreadable))])
        with self.assertRaises(ValueError) as caught:
            semantics.check_packets(model)
        for part in ("c04-PKT-0417-v1.json", "PKT-0417 v1", unreadable, "Correct the time"):
            self.assertIn(part, str(caught.exception))


class AProposalRestsOnTheContextOfItsPacket(unittest.TestCase):
    def test_the_stored_proposals_rest_on_the_context_of_their_packets(self):
        model = support.example_model()
        for proposal in model.of("C05"):
            binding = proposal.data["identity_binding"]
            packet = model.get("C04", binding["packet_reference"]["id"], binding["packet_reference"]["version"])
            self.assertEqual(binding["context_reference"], packet.data["decision_context_as_of"]["context_reference"], proposal.label())

    def test_a_proposal_bound_to_another_version_of_the_context_than_its_packet_is_found(self):
        for target, other, packet in (("C05 ACT-REL-0417 v2", "v1", "PKT-0417 v2"), ("C05 ACT-HOLD-0417 v1", "v2", "PKT-0417 v1")):
            with self.subTest(target):
                bound_elsewhere = change(target, rep("/identity_binding/context_reference/version", other))
                self.assertEqual(codes(bound_elsewhere), ["PKT006"])
                found = packet_findings(bound_elsewhere)
                self.assertEqual([(f.code, f.location) for f in found], [("PKT006", "/identity_binding/context_reference")])
                self.assertIn(packet, found[0].message)
                self.assertIn("CTX-0417 %s" % other, found[0].message)


if __name__ == "__main__":
    unittest.main()
