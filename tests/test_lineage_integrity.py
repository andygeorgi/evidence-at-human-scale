"""The provenance of a C02 record is explicit: what it names as its inputs is held to what lineage means.

A source record assertion is an original: it states what a source system recorded and names no parent, because a parent would change the origin it is counted from. A derived record is
built from its parents, so each parent was available when the derived record was admitted, and a packet or an action that rests on the derived record does not rest on an input that
came later. A typed supersession is an edge from the record that holds it to the older version it replaces, and it agrees with the replacement that the older version records.
"""
import unittest

import support  # noqa: F401  (puts scripts/ on the path)

from eahs import semantics
from eahs.cases import mutate_model
from eahs.gateway import evaluate_commit, ts

LIN = ("LIN001", "LIN003", "LIN004", "LIN006", "LIN007", "LIN008", "LIN009")
ADMITTED, INGESTED = "/producer_admission/admission_time", "/times/ingestion"
PARENTS = "/lineage/parent_references"
HOLD, HOLD_GRANT = ("ACT-HOLD-0417", "v1"), ("GRT-CLASS-HOLD", "v1")


def rep(target, path, value):
    return {"target": target, "ops": [{"op": "replace", "path": path, "value": value}]}


def add(target, path, value):
    return {"target": target, "ops": [{"op": "add", "path": path, "value": value}]}


def model_with(*mutations):
    model, _ = mutate_model(support.example_model(), list(mutations))
    return model


def where(findings, codes=LIN):
    return sorted((f.code, f.file.replace("\\", "/").rsplit("/", 1)[-1], f.location) for f in findings if f.code in codes)


def lineage(*mutations, codes=LIN):
    return where(semantics.check_lineage(model_with(*mutations)), codes)


def parents_of(label, *refs):
    return rep(label, PARENTS, [{"record_id": record_id, "version": version} for record_id, version in refs])


def available_at(label, when, which=(ADMITTED, INGESTED)):
    return [rep(label, path, when) for path in which]


class TheStoredRecordsKeepTheirInputs(unittest.TestCase):
    def test_no_source_assertion_names_a_parent_and_the_derived_ones_keep_theirs(self):
        model = support.example_model()
        kinds = {}
        for record in model.of("C02"):
            kinds.setdefault(record.data["identity_schema"]["kind"], []).append(bool(record.data["lineage"]["parent_references"]))
        self.assertEqual(set(kinds["source_record_assertion"]), {False})
        self.assertEqual(set(kinds["model_inference"]), {True})
        self.assertIn(True, kinds["deterministic_finding"])
        self.assertEqual(lineage(), [])

    def test_a_finding_of_a_producer_that_computes_outside_the_records_needs_no_parent_and_names_none(self):
        model = support.example_model()
        for record_id, version in (("DUP-0417", "v1"), ("SCR-S1042", "v1"), ("SCR-S1042", "v2")):
            record = model.get("C02", record_id, version)
            self.assertEqual(model.registry.producers[record.data["producer_admission"]["producer_id"]]["inputs"], "outside_records")
            self.assertEqual(record.data["lineage"]["parent_references"], [])
        self.assertEqual(lineage(), [])


class ASourceAssertionIsAnOriginalAndNamesNoParent(unittest.TestCase):
    def test_one_valid_earlier_parent_that_is_no_cycle_is_still_a_parent_and_is_found(self):
        """GR-5521 v2 is a source record assertion admitted on 23 November. The invoice is an earlier record and does not depend on it."""
        self.assertEqual(lineage(parents_of("C02 GR-5521 v2", ("INV-2026-0417", "v1"))), [("LIN007", "c02-GR-5521-v2.json", PARENTS)])

    def test_a_parent_that_is_another_source_assertion_is_found(self):
        self.assertEqual(lineage(parents_of("C02 INV-2026-0417 v1", ("PO-77231", "v1"))), [("LIN007", "c02-INV-2026-0417-v1.json", PARENTS)])

    def test_the_finding_names_the_kind_and_what_a_parent_would_change(self):
        messages = [f.message for f in semantics.check_lineage(model_with(parents_of("C02 GR-5521 v2", ("INV-2026-0417", "v1")))) if f.code == "LIN007"]
        self.assertEqual(len(messages), 1)
        for part in ("source record assertion", "original", "origin"):
            self.assertIn(part, messages[0])

    def test_a_record_that_is_its_own_parent_is_still_found_by_the_check_that_always_found_it(self):
        found = lineage(parents_of("C02 GR-5521 v1", ("GR-5521", "v1")))
        self.assertIn(("LIN004", "c02-GR-5521-v1.json", PARENTS + "/0"), found)

    def test_a_derived_record_keeps_its_parents_and_so_does_a_model_inference(self):
        self.assertEqual(lineage(parents_of("C02 M3W-0417 v2", ("INV-2026-0417", "v1"), ("PO-77231", "v1"), ("GR-5521", "v2"))), [])
        self.assertEqual(lineage(parents_of("C02 SUM-A-0417 v1", ("GR-5521", "v1"), ("INV-2026-0417", "v1"))), [])

    def test_a_record_of_another_kind_is_not_judged_by_this_rule(self):
        """An analytical result or a decision record may state its inputs, and none is required here."""
        self.assertEqual(lineage(parents_of("C02 ANL-S1042-OTD v1", ("GR-5521", "v1")), codes=("LIN007",)), [])
        self.assertEqual(lineage(parents_of("C02 CHG-LOWVAL-0001 v1", ("GR-5521", "v1")), codes=("LIN007",)), [])


class AParentWasAvailableWhenItsChildWasAdmitted(unittest.TestCase):
    """M3W-0417 v2 was admitted at 13:51:00Z. Its third parent, GR-5521 v2, was admitted and ingested at 13:40:00Z."""

    CHILD, PARENT = "C02 M3W-0417 v2", "C02 GR-5521 v2"
    THIRD = "/lineage/parent_references/2"

    def test_a_parent_admitted_one_microsecond_after_its_child_is_found(self):
        for stated in ("2026-11-23T13:51:00.000001Z", "2026-11-23T14:51:00.000001+01:00"):
            with self.subTest(stated):
                self.assertEqual(lineage(*available_at(self.PARENT, stated)), [("LIN008", "c02-M3W-0417-v2.json", self.THIRD)])

    def test_either_time_of_the_parent_alone_is_enough(self):
        for path in (ADMITTED, INGESTED):
            with self.subTest(path):
                self.assertEqual(lineage(*available_at(self.PARENT, "2026-11-23T13:52:00Z", (path,))), [("LIN008", "c02-M3W-0417-v2.json", self.THIRD)])

    def test_a_parent_admitted_exactly_when_its_child_was_is_available(self):
        for stated in ("2026-11-23T13:51:00Z", "2026-11-23T14:51:00+01:00", "2026-11-23T13:51:00.000000Z"):
            with self.subTest(stated):
                self.assertEqual(lineage(*available_at(self.PARENT, stated)), [])

    def test_a_parent_admitted_one_microsecond_before_its_child_is_available(self):
        self.assertEqual(lineage(*available_at(self.PARENT, "2026-11-23T13:50:59.999999Z")), [])

    def test_the_time_of_the_event_is_not_the_time_of_availability(self):
        """The business event in the parent may be later than the child: a record is available from its admission, and an event is not known until a record of it is admitted."""
        self.assertEqual(lineage(rep(self.PARENT, "/times/event/value", "2026-11-23T15:00:00Z")), [])

    def test_a_parent_that_was_never_admitted_was_not_available(self):
        self.assertEqual(lineage(rep(self.PARENT, "/producer_admission/admission_status", "quarantined")), [("LIN008", "c02-M3W-0417-v2.json", self.THIRD)])

    def test_a_parent_time_that_cannot_be_compared_exactly_is_not_trusted(self):
        for stated in ("not a time", "2026-11-23T13:40:00.0000001Z"):
            with self.subTest(stated):
                self.assertEqual(lineage(rep(self.PARENT, ADMITTED, stated)), [("LIN008", "c02-M3W-0417-v2.json", self.THIRD)])

    def test_a_parent_that_does_not_exist_is_a_finding_of_the_reference_check_and_not_of_this_one(self):
        missing = rep(self.CHILD, self.THIRD + "/version", "v9")
        self.assertEqual(lineage(missing), [])
        self.assertEqual([(f.code, f.location) for f in semantics.check_references(model_with(missing)) if f.code == "REF001"], [("REF001", self.THIRD)])

    def test_the_finding_names_the_parent_and_when_it_was_admitted(self):
        messages = [f.message for f in semantics.check_lineage(model_with(*available_at(self.PARENT, "2026-11-23T14:00:00Z"))) if f.code == "LIN008"]
        self.assertEqual(len(messages), 1)
        for part in ("GR-5521 v2", "2026-11-23T14:00:00Z", "2026-11-23T13:51:00Z"):
            self.assertIn(part, messages[0])


class WhatRestsOnADerivedRecordDoesNotRestOnAnInputThatCameLater(unittest.TestCase):
    """A packet or an action that cites a derived record that was available does not thereby rest on an input that was not."""

    def test_a_packet_that_cites_a_derived_record_whose_declared_input_came_after_the_cutoff_is_found(self):
        """The second packet is as of 14:10. GR-5521 v2 is cited directly as the receipt, and M3W-0417 v2 is cited as the match that was computed from it."""
        found = where([f for f in semantics.check_packets(model_with(*available_at("C02 GR-5521 v2", "2026-11-23T14:11:00Z"))) if f.file.endswith("c04-PKT-0417-v2.json")], ("PKT007",))
        self.assertEqual(found, [("PKT007", "c04-PKT-0417-v2.json", "/supported_claims_references/2/supporting_references/0"),
                                 ("PKT007", "c04-PKT-0417-v2.json", "/supported_claims_references/3/supporting_references/0")])

    def test_the_finding_names_the_derived_record_and_the_input_that_was_not_available(self):
        model = model_with(*available_at("C02 GR-5521 v2", "2026-11-23T14:11:00Z"))
        messages = [f.message for f in semantics.check_packets(model) if f.code == "PKT007" and f.location == "/supported_claims_references/3/supporting_references/0"]
        self.assertEqual(len(messages), 1)
        for part in ("M3W-0417 v2", "GR-5521 v2", "2026-11-23T14:11:00Z"):
            self.assertIn(part, messages[0])

    def test_an_input_available_exactly_at_the_cutoff_is_available(self):
        self.assertEqual(where(semantics.check_packets(model_with(*available_at("C02 GR-5521 v2", "2026-11-23T14:10:00Z"))), ("PKT007",)), [])

    def hold_at(self, at, *mutations):
        model = model_with(*mutations)
        return evaluate_commit(model, model.get("C05", *HOLD), model.get("C06", *HOLD_GRANT), ts(at), [])

    def test_an_action_that_cites_a_derived_record_whose_declared_input_came_after_the_attempt_blocks(self):
        """The hold cites the match result M3W-0417 v1 (admitted 09:36), which was computed from the invoice, the purchase order and the receipt. The purchase order is not cited."""
        self.assertEqual(self.hold_at("2026-11-23T10:03:00Z").codes, [])
        decision = self.hold_at("2026-11-23T10:03:00Z", *available_at("C02 PO-77231 v1", "2026-11-23T10:03:01Z"))
        self.assertEqual((decision.allow, decision.codes), (False, ["EVIDENCE_NOT_YET_ADMITTED"]))
        for part in ("M3W-0417 v1", "PO-77231 v1", "2026-11-23T10:03:01Z"):
            self.assertIn(part, decision.reasons[0].message)

    def test_an_input_available_exactly_at_the_attempt_was_available(self):
        self.assertEqual(self.hold_at("2026-11-23T10:03:00Z", *available_at("C02 PO-77231 v1", "2026-11-23T10:03:00Z")).codes, [])
        self.assertEqual(self.hold_at("2026-11-23T10:03:00Z", *available_at("C02 PO-77231 v1", "2026-11-23T11:03:00+01:00")).codes, [])

    def test_an_input_of_an_input_is_an_input_too(self):
        """Only the summary is cited. It is derived from the match result, which is derived from the invoice, the purchase order and the receipt, and the purchase order came late."""
        cited = rep("C05 ACT-HOLD-0417 v1", "/action/evidence_references", [{"record_id": "SUM-A-0417", "version": "v1"}])
        deeper = parents_of("C02 SUM-A-0417 v1", ("M3W-0417", "v1"))
        self.assertEqual(self.hold_at("2026-11-23T10:03:00Z", cited, deeper).codes, [])
        decision = self.hold_at("2026-11-23T10:03:00Z", cited, deeper, *available_at("C02 PO-77231 v1", "2026-11-23T10:03:01Z"))
        self.assertEqual((decision.allow, decision.codes), (False, ["EVIDENCE_NOT_YET_ADMITTED"]))
        self.assertIn("PO-77231 v1", decision.reasons[0].message)

    def test_a_declared_input_that_does_not_exist_is_the_business_of_the_reference_check(self):
        decision = self.hold_at("2026-11-23T10:03:00Z", rep("C02 M3W-0417 v1", PARENTS + "/1/version", "v9"))
        self.assertEqual(decision.codes, [])


class ASupersessionEdgeGoesFromTheNewVersionToTheOldOne(unittest.TestCase):
    """GR-5521 v2 holds the edge: from itself, to GR-5521 v1. GR-5521 v1 records v2 as its replacement."""

    NEW, OLD = "C02 GR-5521 v2", "C02 GR-5521 v1"
    EDGE = "/lineage/typed_relationships/0"

    def test_the_stored_pair_and_the_delayed_correction_patterns_are_valid(self):
        self.assertEqual(lineage(), [])
        edge = support.example_model().get("C02", "GR-5521", "v2").data["lineage"]["typed_relationships"][0]
        self.assertEqual((edge["relationship_type"], edge["from"], edge["to"]), ("supersession", {"record_id": "GR-5521", "version": "v2"}, {"record_id": "GR-5521", "version": "v1"}))

    def test_a_replacement_that_carries_an_edge_to_itself_is_found(self):
        self.assertEqual(lineage(rep(self.NEW, self.EDGE + "/to", {"record_id": "GR-5521", "version": "v2"}), codes=("LIN009",)), [("LIN009", "c02-GR-5521-v2.json", self.EDGE)])
        added = {"from": {"record_id": "GR-5521", "version": "v2"}, "to": {"record_id": "GR-5521", "version": "v2"}, "relationship_type": "supersession", "asserted_by": "person:warehouse-supervisor-03"}
        self.assertEqual(lineage(add(self.NEW, "/lineage/typed_relationships/-", added), codes=("LIN009",)), [("LIN009", "c02-GR-5521-v2.json", "/lineage/typed_relationships/4")])

    def test_an_edge_whose_from_names_the_older_record_instead_of_the_record_that_holds_it_is_found(self):
        self.assertEqual(lineage(rep(self.NEW, self.EDGE + "/from", {"record_id": "GR-5521", "version": "v1"}), codes=("LIN009",)), [("LIN009", "c02-GR-5521-v2.json", self.EDGE + "/from")])

    def test_an_edge_whose_from_names_an_unrelated_record_is_found(self):
        for other in ({"record_id": "SUM-A-0417", "version": "v1"}, {"record_id": "GR-5521", "version": "v3"}, {"record_id": "INV-2026-0417", "version": "v1"}):
            with self.subTest(other):
                self.assertEqual(lineage(rep(self.NEW, self.EDGE + "/from", other), codes=("LIN009",)), [("LIN009", "c02-GR-5521-v2.json", self.EDGE + "/from")])

    def test_an_edge_and_a_replacement_that_describe_different_pairs_are_found_as_they_always_were(self):
        """The edge says v2 replaced the match result, and the match result records v2 of its own chain as the replacement."""
        other = rep(self.NEW, self.EDGE + "/to", {"record_id": "M3W-0417", "version": "v1"})
        self.assertEqual(lineage(other, codes=("LIN003", "LIN009")), [("LIN003", "c02-GR-5521-v2.json", self.EDGE)])
        not_replaced = rep(self.OLD, "/lifecycle/replacement_reference", {"record_id": "GR-5521", "version": "v3"})
        self.assertEqual(lineage(not_replaced, codes=("LIN003", "LIN009")), [("LIN003", "c02-GR-5521-v2.json", self.EDGE)])

    def test_the_other_relationships_are_not_judged_by_this_rule(self):
        """An invalidation names the records that stopped being current, and its from is the record that holds it in the examples. No rule about it is added."""
        other = rep(self.NEW, "/lineage/typed_relationships/1/from", {"record_id": "SUM-A-0417", "version": "v1"})
        self.assertEqual(lineage(other, codes=("LIN009",)), [])

    def test_a_replacement_need_not_be_admitted_at_the_time_the_older_version_stops_being_current(self):
        """No cutover rule: the older version may stop being current before or after its replacement is admitted (13:40:00Z)."""
        for effective in ("2026-11-23T13:30:00Z", "2026-11-23T13:40:00Z", "2026-11-23T13:45:00Z"):
            with self.subTest(effective):
                self.assertEqual(lineage(rep(self.OLD, "/lifecycle/effective_time", effective)), [])

    def test_a_correction_that_is_recorded_only_by_the_older_version_stays_valid(self):
        """The match results and the screenings record their replacements in the older version and carry no typed edge."""
        model = support.example_model()
        for record_id in ("M3W-0417", "SCR-S1042"):
            self.assertEqual(model.get("C02", record_id, "v2").data["lineage"]["typed_relationships"], [])
            self.assertEqual(model.get("C02", record_id, "v1").data["lifecycle"]["replacement_reference"], {"record_id": record_id, "version": "v2"})
        self.assertEqual(lineage(), [])


if __name__ == "__main__":
    unittest.main()
