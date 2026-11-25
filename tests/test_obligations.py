"""A decision packet carries every mandatory obligation of its selection, once, and lists none that its selection does not hold.

The obligations of a selection are those that the reader may know of: permission comes first, so a selection lists none that it withholds.
A packet that leaves one out has lost a mandatory item, and a response made from that packet loses it too, so the response cannot be where the loss
is found. An acknowledgement is not a resolution, and the state of an obligation is not judged here.
"""
import copy
import unittest

import support  # noqa: F401  (puts scripts/ on the path)

from eahs import semantics
from eahs.cases import mutate_model, run_case
from eahs.response import check_response, render_response

SEL1 = "C03 SEL-0417 v1"
PKT1, PKT2 = "C04 PKT-0417 v1", "C04 PKT-0417 v2"
LIST = "/priority_mandatory_obligations/obligation_references"
NAME, GHOST, SECOND = "OBL-0417-REVIEW", "OBL-0417-GHOST", "OBL-0417-NOTICE"


def rep(path, value):
    return {"op": "replace", "path": path, "value": value}


def add(path, value):
    return {"op": "add", "path": path, "value": value}


def change(target, *ops):
    return {"target": target, "ops": list(ops)}


def findings(*mutations):
    """The obligation findings (code, location) once every mutation is applied."""
    model, _ = mutate_model(support.example_model(), list(mutations))
    return [(f.code, f.location) for f in semantics.check_packets(model) if f.code in ("PKT008", "PKT009")]


def messages(*mutations):
    model, _ = mutate_model(support.example_model(), list(mutations))
    return [f.message for f in semantics.check_packets(model) if f.code in ("PKT008", "PKT009")]


def stored_reference(version="v1"):
    return copy.deepcopy(support.example_model().get("C04", "PKT-0417", version).data["priority_mandatory_obligations"]["obligation_references"][0])


class TheStoredPacketsCarryTheObligationOfTheirSelection(unittest.TestCase):
    def test_each_selection_lists_the_obligation_and_its_packet_carries_it_once(self):
        model = support.example_model()
        for version in ("v1", "v2"):
            selection, packet = model.get("C03", "SEL-0417", version), model.get("C04", "PKT-0417", version)
            self.assertEqual([o["obligation_id"] for o in selection.data["obligations"]], [NAME])
            carried = packet.data["priority_mandatory_obligations"]["obligation_references"]
            self.assertEqual([(r["obligation_id"], r["selection_reference"]["id"], r["selection_reference"]["version"]) for r in carried], [(NAME, "SEL-0417", version)])
        self.assertEqual(findings(), [])


class AMandatoryObligationCannotDisappearFromAPacket(unittest.TestCase):
    def test_a_packet_that_leaves_out_the_obligation_of_its_selection_is_found(self):
        for packet in (PKT1, PKT2):
            with self.subTest(packet):
                self.assertEqual(findings(change(packet, rep(LIST, []))), [("PKT009", LIST)])
                self.assertEqual(run_case(support.example_model(), support.schema(), {"mutations": [change(packet, rep(LIST, []))]})[0], ["PKT009"])

    def test_the_finding_names_the_obligation_and_its_selection(self):
        (message,) = messages(change(PKT1, rep(LIST, [])))
        for part in (NAME, "SEL-0417 v1", "mandatory"):
            self.assertIn(part, message)

    def test_a_response_that_agrees_with_the_defective_packet_does_not_excuse_it(self):
        """A response is made from its packet, so one made from a packet that lost the obligation lost it as well, and nothing in the response shows it."""
        model, _ = mutate_model(support.example_model(), [change(PKT2, rep(LIST, []))])
        response = render_response(model, model.get("C04", "PKT-0417", "v2"))
        self.assertEqual([f.code for f in check_response(model, response, "response.json")], [])
        self.assertEqual([f.code for f in semantics.check_packets(model)], ["PKT009"])

    def test_every_obligation_of_a_selection_is_carried_and_not_only_the_first(self):
        second = copy.deepcopy(support.example_model().get("C03", "SEL-0417", "v1").data["obligations"][0])
        second["obligation_id"] = SECOND
        added = change(SEL1, add("/obligations/-", second))
        self.assertEqual(findings(added), [("PKT009", LIST)])
        self.assertIn(SECOND, messages(added)[0])
        carry_it = change(PKT1, add(LIST + "/-", {"obligation_id": SECOND, "selection_reference": {"contract_id": "C03", "id": "SEL-0417", "version": "v1"}}))
        self.assertEqual(findings(added, carry_it), [])

    def test_a_selection_with_no_obligation_and_a_packet_with_none_agree(self):
        self.assertEqual(findings(change(SEL1, rep("/obligations", [])), change(PKT1, rep(LIST, []))), [])


class APacketListsNoObligationItsSelectionDoesNotHold(unittest.TestCase):
    def test_an_obligation_that_does_not_exist_is_found(self):
        ghost = change(PKT1, rep(LIST + "/0/obligation_id", GHOST))
        self.assertEqual(findings(ghost), [("PKT008", LIST + "/0"), ("PKT009", LIST)])
        self.assertEqual(run_case(support.example_model(), support.schema(), {"mutations": [ghost]})[0], ["PKT008", "PKT009"])
        first = messages(ghost)[0]
        for part in (GHOST, "does not hold", "SEL-0417 v1"):
            self.assertIn(part, first)

    def test_an_obligation_of_another_selection_is_not_the_obligation_of_this_one(self):
        """OBL-0417-REVIEW is a real obligation, and the second selection holds it. The first packet is not bound to that selection."""
        other = change(PKT1, rep(LIST + "/0/selection_reference/version", "v2"))
        self.assertEqual(findings(other), [("PKT008", LIST + "/0"), ("PKT009", LIST)])
        self.assertIn("obligation %s of selection SEL-0417 v2" % NAME, messages(other)[0])

    def test_a_selection_that_does_not_exist_is_not_this_one_either(self):
        self.assertEqual(findings(change(PKT1, rep(LIST + "/0/selection_reference/version", "v9"))), [("PKT008", LIST + "/0"), ("PKT009", LIST)])

    def test_an_obligation_listed_twice_is_found(self):
        twice = change(PKT1, add(LIST + "/-", stored_reference()))
        self.assertEqual(findings(twice), [("PKT008", LIST + "/1")])
        self.assertIn("more than once", messages(twice)[0])

    def test_a_name_that_the_selection_holds_twice_makes_the_reference_ambiguous(self):
        again = change(SEL1, add("/obligations/-", copy.deepcopy(support.example_model().get("C03", "SEL-0417", "v1").data["obligations"][0])))
        self.assertEqual(findings(again), [("PKT008", LIST + "/0")])
        self.assertIn("ambiguous", messages(again)[0])

    def test_an_obligation_that_a_selection_with_none_does_not_hold_is_found(self):
        self.assertEqual(findings(change(SEL1, rep("/obligations", []))), [("PKT008", LIST + "/0")])


if __name__ == "__main__":
    unittest.main()
