"""A supported claim is held to every reference that supports it.

A claim that cites a payload must not state a status (pass or fail) or a figure that the payload does not hold. A claim that cites
claims must say what they say together, in the order cited. A claim that mixes both quotes each cited claim and stays within the
statuses and figures of what it cites. These are structured values compared exactly: they are necessary conditions, and none of
them reads prose for meaning. A claim that passes can still say what its sources do not support.
"""
import copy
import unittest

import support  # noqa: F401  (puts scripts/ on the path)

from eahs import semantics
from eahs.cases import mutate_model
from eahs.semantics import _numbers_in, _statuses_in

PACKET = "C04 PKT-0417 v1"
PAYLOAD_CLAIM = 3          # PC-4, the three-way match, rests on a payload_reference
GOODS_RECEIPT_CLAIM, INVOICE_CLAIM = 2, 0


def claim_findings(model, packet_id="PKT-0417", version="v1"):
    packet = model.get("C04", packet_id, version)
    return [f for f in semantics.check_packets(model) if f.file == packet.file and "/supported_claims_references/" in f.location]


def codes(model, **kwargs):
    return [(f.code, f.location.split("/")[2]) for f in claim_findings(model, **kwargs)]


def with_claim(index, text=None, references=None, packet=PACKET):
    """A copy of the example set in which one supported claim has another text, or another list of supporting references."""
    model = support.example_model()
    claim = copy.deepcopy(model.get("C04", *packet.split()[1:]).data["supported_claims_references"][index])
    if text is not None:
        claim["text"] = text
    if references is not None:
        claim["supporting_references"] = references
    mutated, _ = mutate_model(model, [{"target": packet, "ops": [{"op": "replace", "path": "/supported_claims_references/%d" % index, "value": claim}]}])
    return mutated


def reference(index, which=0, packet="PKT-0417", version="v1"):
    return copy.deepcopy(support.example_model().get("C04", packet, version).data["supported_claims_references"][index]["supporting_references"][which])


def said(index, packet="PKT-0417", version="v1"):
    return support.example_model().get("C04", packet, version).data["supported_claims_references"][index]["text"]


class TheExampleSet(unittest.TestCase):
    def test_every_existing_packet_still_passes(self):
        self.assertEqual(claim_findings(support.example_model()), [])
        self.assertEqual(claim_findings(support.example_model(), version="v2"), [])

    def test_the_payload_claim_cites_the_whole_match_result_it_summarizes(self):
        ref = reference(PAYLOAD_CLAIM)
        self.assertEqual((ref["reference_type"], ref["payload_location"]), ("payload_reference", "/value"))


class OnePayloadReference(unittest.TestCase):
    """The claim says 'FAIL (invoiced 100 units, received 60 units, variance 40.0%, tolerance 2%)' and its payload says the same."""

    def test_a_failed_match_restated_as_passed_is_found(self):
        model = with_claim(PAYLOAD_CLAIM, said(PAYLOAD_CLAIM).replace("FAIL", "PASS"))
        found = claim_findings(model)
        self.assertEqual([f.code for f in found], ["PKT005"])
        self.assertIn("'pass'", found[0].message)

    def test_a_payload_changed_from_fail_to_pass_makes_the_unchanged_claim_wrong(self):
        model, _ = mutate_model(support.example_model(), [{"target": "C02 M3W-0417 v1", "ops": [{"op": "replace", "path": "/content/payload/value/result", "value": "PASS"}]}])
        self.assertEqual([f.code for f in claim_findings(model)], ["PKT005"])

    def test_the_status_is_read_in_any_case_and_inflection(self):
        for word in ("failed", "Fail", "FAILS"):
            self.assertEqual(codes(with_claim(PAYLOAD_CLAIM, said(PAYLOAD_CLAIM).replace("FAIL", word))), [], word)
        self.assertEqual(codes(with_claim(PAYLOAD_CLAIM, said(PAYLOAD_CLAIM).replace("FAIL", "passed"))), [("PKT005", "3")])

    def test_a_changed_figure_is_found_whichever_figure_it_is(self):
        for old, new in (("100 units, received", "110 units, received"), ("60 units", "65 units"), ("40.0%", "35.0%"), ("tolerance 2%", "tolerance 5%")):
            with self.subTest(new):
                model = with_claim(PAYLOAD_CLAIM, said(PAYLOAD_CLAIM).replace(old, new))
                found = claim_findings(model)
                self.assertEqual([f.code for f in found], ["PKT005"])
                self.assertIn("figure", found[0].message)

    def test_a_payload_whose_numbers_changed_makes_the_unchanged_claim_wrong(self):
        for path, value in (("/content/payload/value/quantity_received", 65), ("/content/payload/value/variance_pct", 35.0), ("/content/payload/value/tolerance_pct", 5)):
            with self.subTest(path):
                model, _ = mutate_model(support.example_model(), [{"target": "C02 M3W-0417 v1", "ops": [{"op": "replace", "path": path, "value": value}]}])
                self.assertEqual({f.code for f in claim_findings(model)}, {"PKT005"})

    def test_a_figure_added_to_the_claim_that_the_payload_does_not_hold_is_found(self):
        model = with_claim(PAYLOAD_CLAIM, said(PAYLOAD_CLAIM).rstrip(".") + ", and 12 invoices were affected.")
        self.assertEqual(codes(model), [("PKT005", "3")])

    def test_a_pointer_that_resolves_to_less_than_the_claim_states_is_found(self):
        ref = reference(PAYLOAD_CLAIM)
        ref["payload_location"] = "/value/result"
        model = with_claim(PAYLOAD_CLAIM, references=[ref])
        self.assertEqual({f.code for f in claim_findings(model)}, {"PKT005"})

    def test_a_pointer_that_does_not_resolve_is_a_reference_finding_and_the_claim_is_not_compared_against_less(self):
        ref = reference(PAYLOAD_CLAIM)
        for pointer in ("/value/outcome", "/nothing", "/value/quantity_received/x", "value", "//value", "/value/", "~value"):
            with self.subTest(pointer):
                ref["payload_location"] = pointer
                model = with_claim(PAYLOAD_CLAIM, references=[copy.deepcopy(ref)])
                self.assertEqual(codes(model), [])
                self.assertIn("REF003", {f.code for f in semantics.check_references(model)})

    def test_a_record_with_no_payload_or_no_such_record_is_a_reference_finding_not_a_crash(self):
        ref = reference(PAYLOAD_CLAIM)
        ref["record_id"] = "INV-2026-0417"
        model = with_claim(PAYLOAD_CLAIM, references=[ref])
        self.assertEqual(codes(model), [])
        self.assertIn("REF003", {f.code for f in semantics.check_references(model)})
        ref["record_id"] = "NO-SUCH-RECORD"
        model = with_claim(PAYLOAD_CLAIM, references=[ref])
        self.assertEqual(codes(model), [])
        self.assertIn("REF001", {f.code for f in semantics.check_references(model)})


class OneClaimReference(unittest.TestCase):
    """The behaviour that exists today is kept: the claim says exactly what the cited claim says."""

    def test_a_claim_that_says_more_or_less_or_other_is_found(self):
        for text in (said(GOODS_RECEIPT_CLAIM) + " Nothing else is outstanding.", said(GOODS_RECEIPT_CLAIM).replace("60", "61"), "Goods receipt GR-5521 records 60 units."):
            with self.subTest(text):
                self.assertEqual(codes(with_claim(GOODS_RECEIPT_CLAIM, text)), [("PKT001", "2")])

    def test_the_finding_names_the_record_and_the_claim(self):
        found = claim_findings(with_claim(GOODS_RECEIPT_CLAIM, "Something else."))
        self.assertIn("GR-5521 v1 claim c1", found[0].message)


class SeveralReferences(unittest.TestCase):
    """A claim cannot escape the check by citing more than one reference."""

    def two_claims(self, first=GOODS_RECEIPT_CLAIM, second=INVOICE_CLAIM):
        return [reference(first), reference(second)]

    def test_a_valid_claim_that_says_what_two_claims_say_together_passes(self):
        text = said(GOODS_RECEIPT_CLAIM) + " " + said(INVOICE_CLAIM)
        self.assertEqual(codes(with_claim(GOODS_RECEIPT_CLAIM, text, self.two_claims())), [])

    def test_the_order_cited_is_the_order_said(self):
        text = said(INVOICE_CLAIM) + " " + said(GOODS_RECEIPT_CLAIM)
        self.assertEqual(codes(with_claim(GOODS_RECEIPT_CLAIM, text, self.two_claims())), [("PKT001", "2")])

    def test_a_fabricated_claim_with_several_references_is_found(self):
        for text in ("The goods receipt and the invoice agree on 100 units.", "Goods receipt GR-5521 records 60 units received on 2026-11-18. The invoice is correct.",
                     said(GOODS_RECEIPT_CLAIM), said(INVOICE_CLAIM)):
            with self.subTest(text):
                self.assertEqual(codes(with_claim(GOODS_RECEIPT_CLAIM, text, self.two_claims())), [("PKT001", "2")])

    def test_padding_a_true_claim_with_an_extra_reference_does_not_make_a_false_one_pass(self):
        padded = self.two_claims() + [reference(1)]
        text = said(GOODS_RECEIPT_CLAIM) + " " + said(INVOICE_CLAIM)
        self.assertEqual(codes(with_claim(GOODS_RECEIPT_CLAIM, text, padded)), [("PKT001", "2")])

    def test_every_reference_is_still_validated_not_only_the_first(self):
        stale = self.two_claims()
        stale[1]["scope"] = {"entity_references": [], "task": "another task"}
        model = with_claim(GOODS_RECEIPT_CLAIM, said(GOODS_RECEIPT_CLAIM) + " " + said(INVOICE_CLAIM), stale)
        found = [f for f in semantics.check_references(model) if f.code == "REF002" and "supporting_references/1" in f.location]
        self.assertEqual(len(found), 1)

    def test_a_claim_that_mixes_a_claim_and_a_payload_quotes_the_claim_and_stays_within_both(self):
        refs = [reference(INVOICE_CLAIM), reference(PAYLOAD_CLAIM)]
        valid = said(INVOICE_CLAIM) + " " + said(PAYLOAD_CLAIM)
        self.assertEqual(codes(with_claim(INVOICE_CLAIM, valid, refs)), [])
        self.assertEqual(codes(with_claim(INVOICE_CLAIM, valid.replace("FAIL", "PASS"), refs)), [("PKT005", "0")])
        self.assertEqual(codes(with_claim(INVOICE_CLAIM, valid.replace("variance 40.0%", "variance 4.0%"), refs)), [("PKT005", "0")])
        self.assertEqual(codes(with_claim(INVOICE_CLAIM, said(PAYLOAD_CLAIM) + " The invoice is payable.", refs)), [("PKT001", "0")])

    def test_several_payloads_support_a_claim_together_and_not_with_figures_from_neither(self):
        payloads = [reference(PAYLOAD_CLAIM), reference(PAYLOAD_CLAIM)]
        self.assertEqual(codes(with_claim(PAYLOAD_CLAIM, references=payloads)), [])
        self.assertEqual(codes(with_claim(PAYLOAD_CLAIM, said(PAYLOAD_CLAIM) + " 7 days late.", payloads)), [("PKT005", "3")])

    def test_a_reference_that_does_not_resolve_is_reported_by_its_reference_check_once(self):
        refs = self.two_claims()
        refs[1]["claim_id"] = "c9"
        model = with_claim(GOODS_RECEIPT_CLAIM, said(GOODS_RECEIPT_CLAIM) + " " + said(INVOICE_CLAIM), refs)
        self.assertEqual(codes(model), [])
        self.assertEqual([f.code for f in semantics.check_references(model) if "supported_claims_references/2" in f.location], ["REF002"])


class WhatAPayloadClaimMustSay(unittest.TestCase):
    """A claim that rests on a payload states what the payload holds: its status, at least one of its figures, and each figure beside its own field."""

    def test_a_claim_that_says_something_else_about_a_failed_match_is_found(self):
        model = with_claim(PAYLOAD_CLAIM, "The supplier has been cleared for immediate payment.")
        messages = [f.message for f in claim_findings(model)]
        self.assertEqual(len(messages), 2, messages)
        self.assertTrue(any("does not state 'fail'" in m for m in messages))
        self.assertTrue(any("states none of the figures" in m for m in messages))

    def test_a_claim_that_states_the_status_and_none_of_the_figures_is_found(self):
        found = claim_findings(with_claim(PAYLOAD_CLAIM, "The three-way match failed."))
        self.assertEqual([f.code for f in found], ["PKT005"])
        self.assertIn("none of the figures", found[0].message)

    def test_a_claim_that_states_the_figures_and_no_status_is_found(self):
        found = claim_findings(with_claim(PAYLOAD_CLAIM, "Three-way match M3W 2.0 on INV-2026-0417 (invoiced 100 units, received 60 units, variance 40.0%, tolerance 2%)."))
        self.assertEqual([f.code for f in found], ["PKT005"])
        self.assertIn("does not state 'fail'", found[0].message)

    def test_a_claim_that_restates_the_payload_in_its_own_words_passes(self):
        for text in ("The match failed: a variance of 40.0% against a tolerance of 2%, with 100 units invoiced and received 60.",
                     "FAIL. Quantity invoiced: 100. Quantity received: 60. Variance 40.0%. Tolerance 2%.",
                     "The match failed (invoiced 100, received 60, variance 40.0 percent, tolerance 2 percent)."):
            with self.subTest(text):
                self.assertEqual(codes(with_claim(PAYLOAD_CLAIM, text)), [])

    def test_swapped_figures_are_found_although_each_is_in_the_payload(self):
        swapped = said(PAYLOAD_CLAIM).replace("invoiced 100 units, received 60 units", "invoiced 60 units, received 100 units")
        found = claim_findings(with_claim(PAYLOAD_CLAIM, swapped))
        self.assertEqual([f.code for f in found], ["PKT005", "PKT005"])
        self.assertTrue(any("next to 'invoiced'" in f.message and "quantity_invoiced is 100" in f.message for f in found), [f.message for f in found])
        self.assertTrue(any("next to 'received'" in f.message and "quantity_received is 60" in f.message for f in found), [f.message for f in found])

    def test_swapping_the_order_of_figure_and_name_is_found_too(self):
        """A name in front of a figure names it only when nothing but white space, a colon or filler words lies between them."""
        for old_text, new_text in (("invoiced 100 units, received 60 units", "60 units invoiced, 100 units received"),
                                   ("invoiced 100 units, received 60 units", "60 units invoiced (100 units received)"),
                                   ("invoiced 100 units, received 60 units", "100 received, 60 invoiced"),
                                   ("variance 40.0%, tolerance 2%", "40.0% tolerance, 2% variance")):
            with self.subTest(new_text):
                found = claim_findings(with_claim(PAYLOAD_CLAIM, said(PAYLOAD_CLAIM).replace(old_text, new_text)))
                self.assertEqual([f.code for f in found], ["PKT005", "PKT005"], [f.message for f in found])

    def test_a_figure_that_follows_its_name_is_still_accepted_in_either_order(self):
        for new_text in ("100 units invoiced, 60 units received", "100 invoiced; 60 received", "invoiced: 100, received: 60", "invoiced 100 (received 60)"):
            with self.subTest(new_text):
                text = said(PAYLOAD_CLAIM).replace("invoiced 100 units, received 60 units", new_text)
                self.assertEqual(claim_findings(with_claim(PAYLOAD_CLAIM, text)), [])

    def test_a_field_name_written_out_names_its_figure_like_any_other_word(self):
        """"quantity_invoiced 60" used to be one unknown word, so the swapped figure beside it was tied to nothing and passed."""
        for old_text, new_text in (("invoiced 100 units, received 60 units", "quantity_invoiced 60, quantity_received 100"),
                                   ("invoiced 100 units, received 60 units", "quantityInvoiced=60; quantityReceived=100"),
                                   ("invoiced 100 units, received 60 units", '"quantity_invoiced": 60, "quantity_received": 100'),
                                   ("invoiced 100 units, received 60 units", "60 quantity_invoiced, 100 quantity_received"),
                                   ("variance 40.0%, tolerance 2%", "variance_pct 2, tolerance_pct 40.0"),
                                   ("variance 40.0%, tolerance 2%", "tolerance_pct 40.0 variance_pct 2")):
            with self.subTest(new_text):
                found = claim_findings(with_claim(PAYLOAD_CLAIM, said(PAYLOAD_CLAIM).replace(old_text, new_text)))
                self.assertEqual([f.code for f in found], ["PKT005", "PKT005"], [f.message for f in found])
                self.assertTrue(all("holds" in f.message for f in found), [f.message for f in found])

    def test_a_field_name_written_out_beside_its_own_figure_passes(self):
        for old_text, new_text in (("invoiced 100 units, received 60 units", "quantity_invoiced 100, quantity_received 60"),
                                   ("invoiced 100 units, received 60 units", "quantityInvoiced=100; quantityReceived=60"),
                                   ("invoiced 100 units, received 60 units", '"quantity_invoiced": 100, "quantity_received": 60'),
                                   ("variance 40.0%, tolerance 2%", "variance_pct 40.0, tolerance_pct 2")):
            with self.subTest(new_text):
                self.assertEqual(claim_findings(with_claim(PAYLOAD_CLAIM, said(PAYLOAD_CLAIM).replace(old_text, new_text))), [])

    def test_a_filler_word_between_a_figure_and_its_name_does_not_hide_a_swap(self):
        """"60 units were invoiced" is about "invoiced", as "60 units invoiced" is."""
        for new_text in ("60 units were invoiced, 100 units were received", "60 units are invoiced and 100 units are received", "60 units was invoiced, 100 units was received"):
            with self.subTest(new_text):
                text = said(PAYLOAD_CLAIM).replace("invoiced 100 units, received 60 units", new_text)
                found = claim_findings(with_claim(PAYLOAD_CLAIM, text))
                self.assertEqual([f.code for f in found], ["PKT005", "PKT005"], [f.message for f in found])
        for new_text in ("100 units were invoiced, 60 units were received", "100 units are invoiced and 60 units are received"):
            with self.subTest(new_text):
                text = said(PAYLOAD_CLAIM).replace("invoiced 100 units, received 60 units", new_text)
                self.assertEqual(claim_findings(with_claim(PAYLOAD_CLAIM, text)), [])

    def test_a_name_written_out_names_the_fields_that_carry_all_of_its_words(self):
        from eahs.semantics import _label_findings
        payload = {"quantity_invoiced": 100, "quantity_received": 60, "variance_pct": 40.0, "tolerance_pct": 2}
        held = [(payload, "")]
        found = _label_findings("quantity_invoiced 7", held, set())
        self.assertEqual([(str(figure), word, fields) for figure, word, fields in found], [("7", "quantity_invoiced", ["quantity_invoiced is 100"])])
        self.assertEqual([word for _, word, _ in _label_findings("tolerance_pct 7", held, set())], ["tolerance_pct"], "not every field that ends in pct")
        self.assertEqual(_label_findings("quantity_invoiced 100 and tolerance_pct 2 and variance_pct 40", held, set()), [])
        self.assertEqual(_label_findings("quantity_variance 7", held, set()), [], "a name that no field has is tied to nothing")

    def test_a_pointer_to_one_value_keeps_the_name_of_that_value(self):
        """A claim that cites /value/quantity_invoiced and /value/quantity_received held two bare numbers, and the names beside its figures tied to nothing."""
        refs = []
        for field in ("quantity_invoiced", "quantity_received"):
            ref = reference(PAYLOAD_CLAIM)
            ref["payload_location"] = "/value/" + field
            refs.append(ref)
        right = "The invoice shows invoiced 100 units and the goods receipt shows received 60 units."
        self.assertEqual(claim_findings(with_claim(PAYLOAD_CLAIM, right, copy.deepcopy(refs))), [])
        for swapped in ("The invoice shows invoiced 60 units and the goods receipt shows received 100 units.",
                        "The invoice shows 60 units invoiced and the goods receipt shows 100 units received.",
                        "The invoice shows quantity_invoiced 60 and the goods receipt shows quantity_received 100."):
            with self.subTest(swapped):
                found = claim_findings(with_claim(PAYLOAD_CLAIM, swapped, copy.deepcopy(refs)))
                self.assertEqual([f.code for f in found], ["PKT005", "PKT005"], [f.message for f in found])

    def test_a_claim_that_cites_some_values_may_not_put_a_figure_beside_a_field_it_does_not_cite(self):
        """The claim cites the result and the quantity invoiced (100). "quantity_received 100" uses a figure it does hold, as the value of a field it does not
        cite: the claim then attributes to that field a value that nothing it cites gives it."""
        refs = []
        for field in ("result", "quantity_invoiced"):
            ref = reference(PAYLOAD_CLAIM)
            ref["payload_location"] = "/value/" + field
            refs.append(ref)
        self.assertEqual(claim_findings(with_claim(PAYLOAD_CLAIM, "FAIL. quantity_invoiced 100.", copy.deepcopy(refs))), [])
        self.assertEqual(claim_findings(with_claim(PAYLOAD_CLAIM, "FAIL. 100 units invoiced.", copy.deepcopy(refs))), [])
        for wrong in ("FAIL. quantity_received 100.", "FAIL. 100 units received.", "FAIL. Received 100.", "FAIL. quantityReceived=100."):
            with self.subTest(wrong):
                found = claim_findings(with_claim(PAYLOAD_CLAIM, wrong, copy.deepcopy(refs)))
                self.assertEqual([f.code for f in found], ["PKT005"], [f.message for f in found])
                self.assertIn("does not hold it", found[0].message)
                self.assertIn("quantity_received", found[0].message)

    def test_a_claim_that_cites_the_whole_payload_may_name_any_of_its_fields(self):
        self.assertEqual(claim_findings(with_claim(PAYLOAD_CLAIM, "FAIL. Quantity received: 60. Quantity invoiced: 100. Variance 40.0%. Tolerance 2%.")), [])

    def test_a_field_that_holds_no_number_is_a_name_too_and_so_is_a_name_in_quotation_marks(self):
        """"invoice_id 100" puts a figure beside the name of a field that holds text, and a name written between backticks or quotation marks after its figure is the name."""
        refs = []
        for field in ("result", "quantity_invoiced"):
            ref = reference(PAYLOAD_CLAIM)
            ref["payload_location"] = "/value/" + field
            refs.append(ref)
        for wrong in ("FAIL. invoice_id 100.", "FAIL. 100 units `quantity_received`.", 'FAIL. 100 units "quantity_received".', "FAIL. 100 units 'quantity_received'.",
                      "FAIL. 100 units \u201cquantity_received\u201d.", "FAIL. 100 units \u2018quantity_received\u2019.", "FAIL. 100 units \u00abquantity_received\u00bb.", "FAIL. 100 units \u201equantity_received\u201c."):
            with self.subTest(wrong):
                found = claim_findings(with_claim(PAYLOAD_CLAIM, wrong, copy.deepcopy(refs)))
                self.assertEqual([f.code for f in found], ["PKT005"], [f.message for f in found])
                self.assertIn("does not hold it", found[0].message)
        for right in ("FAIL. 100 units `quantity_invoiced`.", 'FAIL. 100 units "quantity_invoiced".', "FAIL. quantity_invoiced 100.", "FAIL. 100 units \u201cquantity_invoiced\u201d."):
            with self.subTest(right):
                self.assertEqual(claim_findings(with_claim(PAYLOAD_CLAIM, right, copy.deepcopy(refs))), [])

    def test_a_word_that_names_the_wrapper_around_the_data_is_not_the_name_of_a_field(self):
        """A payload is a wrapper (its data type, its schema, its value) around the data a claim is about. "value", "type" and "reference" are words, and not fields of the record."""
        refs = []
        for field in ("result", "quantity_invoiced"):
            ref = reference(PAYLOAD_CLAIM)
            ref["payload_location"] = "/value/" + field
            refs.append(ref)
        for text in ("FAIL. Total value 100.", "FAIL. The data type 100.", "FAIL. Reference 100."):
            with self.subTest(text):
                self.assertEqual(claim_findings(with_claim(PAYLOAD_CLAIM, text, copy.deepcopy(refs))), [])

    def test_a_figure_after_a_colon_is_stated_with_its_sign_and_a_time_is_not_a_figure(self):
        """A colon after a digit is a time or a ratio ("13:45", "2:1"). A colon after a word is a delimiter: the number after it is stated, and a minus sign right behind it is a sign."""
        from decimal import Decimal
        self.assertEqual(dict(_numbers_in("variance:35, Total:-18, at 13:45, 2:1, T10:00:00Z")), {Decimal("35"): 1, Decimal("-18"): 1})
        for new, wrong in (("variance:35%", True), ("variance:-40.0%", True), ("variance:40.0%", False), ("variance: 40.0%", False)):
            with self.subTest(new):
                found = claim_findings(with_claim(PAYLOAD_CLAIM, said(PAYLOAD_CLAIM).replace("variance 40.0%", new)))
                self.assertEqual([f.code for f in found], ["PKT005"] if wrong else [], [f.message for f in found])

    def test_a_pointer_to_a_list_position_is_named_by_the_field_that_holds_the_list(self):
        from eahs.semantics import _field_of
        self.assertEqual(_field_of("/value/quantity_invoiced"), "quantity_invoiced")
        self.assertEqual(_field_of("/value/lines/0"), "lines")
        self.assertEqual(_field_of("/value"), "value")
        self.assertEqual(_field_of(""), "")
        self.assertEqual(_field_of("/a~1b"), "a/b")

    def test_a_claim_that_cites_two_payloads_may_state_either_ones_figure_beside_a_name(self):
        """The match said 60 units received, and its correction said 100: a claim about both is right to state both."""
        later = reference(PAYLOAD_CLAIM)
        later["version"] = "v2"
        both = ("Three-way match M3W 2.0 on INV-2026-0417: FAIL (invoiced 100 units, received 60 units, variance 40.0%, tolerance 2%), "
                "then PASS (invoiced 100 units, received 100 units, variance 0.0%, tolerance 2%).")
        refs = [reference(PAYLOAD_CLAIM), later]
        self.assertEqual(claim_findings(with_claim(PAYLOAD_CLAIM, both, copy.deepcopy(refs))), [])
        wrong = both.replace("received 60 units", "received 80 units")
        found = claim_findings(with_claim(PAYLOAD_CLAIM, wrong, copy.deepcopy(refs)))
        self.assertEqual([f.code for f in found], ["PKT005"], [f.message for f in found])
        self.assertIn("80", found[0].message)
        swapped = both.replace("invoiced 100 units, received 60 units", "invoiced 60 units, received 100 units")
        found = claim_findings(with_claim(PAYLOAD_CLAIM, swapped, copy.deepcopy(refs)))
        self.assertEqual([f.code for f in found], ["PKT005"], [f.message for f in found])
        self.assertIn("'invoiced'", found[0].message)

    def test_a_figure_that_differs_only_beyond_the_precision_of_a_float_is_a_different_figure(self):
        for new in ("40.000000000000001", "40.00000000000000001", "39.999999999999999"):
            with self.subTest(new):
                text = said(PAYLOAD_CLAIM).replace("variance 40.0%", "variance %s%%" % new)
                found = claim_findings(with_claim(PAYLOAD_CLAIM, text))
                self.assertEqual([f.code for f in found], ["PKT005"], [f.message for f in found])
                self.assertIn("does not account for", found[0].message)

    def test_the_same_number_written_differently_is_the_same_figure(self):
        for new in ("variance 40%", "variance 40.000%", "variance 40.0%", "variance +40.0%"):
            with self.subTest(new):
                self.assertEqual(claim_findings(with_claim(PAYLOAD_CLAIM, said(PAYLOAD_CLAIM).replace("variance 40.0%", new))), [])

    def test_the_variance_and_the_tolerance_cannot_trade_places(self):
        traded = said(PAYLOAD_CLAIM).replace("variance 40.0%, tolerance 2%", "variance 2%, tolerance 40.0%")
        self.assertEqual(len(claim_findings(with_claim(PAYLOAD_CLAIM, traded))), 2)

    def test_a_minus_sign_is_part_of_the_figure(self):
        self.assertEqual(sorted(_numbers_in("variance -40.0% and \u22125 and (-3) and 2026-11-18 and x-5 and 10-20").elements()), [-40.0, -5.0, -3.0])
        for old, new in (("variance 40.0%", "variance -40.0%"), ("received 60 units", "received -60 units"), ("invoiced 100 units", "invoiced \u2212100 units")):
            with self.subTest(new):
                found = claim_findings(with_claim(PAYLOAD_CLAIM, said(PAYLOAD_CLAIM).replace(old, new)))
                self.assertIn("PKT005", [f.code for f in found])
        model, _ = mutate_model(support.example_model(), [{"target": "C02 M3W-0417 v1", "ops": [{"op": "replace", "path": "/content/payload/value/variance_pct", "value": -40.0}]}])
        self.assertIn("PKT005", [f.code for f in claim_findings(model)])

    def test_a_mixed_claim_cannot_add_prose_that_ignores_the_payload(self):
        refs = [reference(INVOICE_CLAIM), reference(PAYLOAD_CLAIM)]
        for text in (said(INVOICE_CLAIM) + " The supplier has been cleared for immediate payment.", said(INVOICE_CLAIM) + " The match failed.", said(INVOICE_CLAIM)):
            with self.subTest(text[-40:]):
                found = claim_findings(with_claim(INVOICE_CLAIM, text, refs))
                self.assertTrue(found)
                self.assertEqual({f.code for f in found}, {"PKT005"})

    def test_a_mixed_claim_that_states_the_payload_passes_and_one_that_reverses_it_does_not(self):
        refs = [reference(INVOICE_CLAIM), reference(PAYLOAD_CLAIM)]
        self.assertEqual(codes(with_claim(INVOICE_CLAIM, said(INVOICE_CLAIM) + " " + said(PAYLOAD_CLAIM), refs)), [])
        swapped = said(INVOICE_CLAIM) + " " + said(PAYLOAD_CLAIM).replace("invoiced 100 units, received 60 units", "invoiced 60 units, received 100 units")
        self.assertEqual({f.code for f in claim_findings(with_claim(INVOICE_CLAIM, swapped, refs))}, {"PKT005"})

    def test_the_cited_claims_own_figures_cannot_cover_a_figure_the_payload_lacks(self):
        refs = [reference(INVOICE_CLAIM), reference(PAYLOAD_CLAIM)]
        # 18,400.00 is the invoice's figure: stated again beside the payload's own words it is not the payload's.
        text = said(INVOICE_CLAIM) + " " + said(PAYLOAD_CLAIM).replace("variance 40.0%", "variance 18,400.00%")
        self.assertIn("PKT005", [f.code for f in claim_findings(with_claim(INVOICE_CLAIM, text, refs))])

    def test_a_reference_that_does_not_resolve_does_not_stop_the_others_being_checked(self):
        bad = reference(INVOICE_CLAIM)
        bad["claim_id"] = "c9"
        model = with_claim(PAYLOAD_CLAIM, "The supplier has been cleared for immediate payment.", [reference(PAYLOAD_CLAIM), bad])
        self.assertEqual({f.code for f in claim_findings(model)}, {"PKT005"})
        self.assertIn("REF002", {f.code for f in semantics.check_references(model)})

    def test_every_packet_of_the_examples_still_says_what_its_payload_holds(self):
        self.assertEqual(claim_findings(support.example_model()), [])
        self.assertEqual(claim_findings(support.example_model(), version="v2"), [])


class WhatIsCompared(unittest.TestCase):
    def test_figures_are_numbers_that_no_identifier_date_or_time_owns_and_each_statement_counts(self):
        self.assertEqual(sorted(_numbers_in("Three-way match M3W 2.0 on INV-2026-0417: FAIL (invoiced 100 units, variance 40.0%, tolerance 2%).").elements()), [2.0, 2.0, 40.0, 100.0])
        self.assertEqual(sorted(_numbers_in("Supplier FC-88231 dated 2026-11-22 at 13:45 owes EUR 18,400.00 by 2026-11-30.").elements()), [18400.0])
        self.assertEqual(sorted(_numbers_in("PO-77231 and S-1042 and 5521").elements()), [5521.0])

    def test_figures_are_compared_as_written_not_as_floats(self):
        self.assertEqual(_numbers_in("40.0"), _numbers_in("40"))
        self.assertEqual(_numbers_in("18,400.00"), _numbers_in("18400"))
        self.assertNotEqual(_numbers_in("40.000000000000001"), _numbers_in("40.0"))
        self.assertNotEqual(_numbers_in("0.1000000000000000055"), _numbers_in("0.1"))
        from eahs.semantics import _content_values
        self.assertEqual(_content_values({"variance_pct": 40.0, "tolerance_pct": 2})[0], _numbers_in("40.0 and 2"))
        self.assertEqual(_content_values({"x": 0.1})[0], _numbers_in("0.1"))

    def test_one_figure_cannot_cover_two_statements_of_it(self):
        # The rule version 2.0 and the tolerance 2% are the same number: a payload that holds only one of them accounts for one.
        model, _ = mutate_model(support.example_model(), [{"target": "C02 M3W-0417 v1", "ops": [{"op": "replace", "path": "/content/payload/value/tolerance_pct", "value": 5}]}])
        found = claim_findings(model)
        self.assertEqual([f.code for f in found], ["PKT005"])
        self.assertIn("figure 2", found[0].message)

    def test_statuses_are_the_pass_and_fail_family_only(self):
        self.assertEqual(_statuses_in("PASS and failed, then passes; Failure"), {"pass", "fail"})
        self.assertEqual(_statuses_in("The match is current and verified"), set())

    def test_the_module_does_not_claim_to_understand_prose(self):
        doc = " ".join(semantics._check_claim_support.__doc__.split())
        self.assertIn("Nothing here reads prose for meaning", doc)
        self.assertIn("necessary conditions", doc)


class TheDocuments(unittest.TestCase):
    def text(self, relative):
        return (support.REPO / relative).read_text(encoding="utf-8")

    def test_the_code_table_and_the_packet_page_describe_the_claim_rules_and_their_limit(self):
        self.assertIn("PKT001`–`PKT005", self.text("scripts/README.md"))
        page = self.text("examples/05-decision-packet/README.md")
        for phrase in ("PKT005", "Every reference counts", "does not show that a claim is true"):
            self.assertIn(phrase, page)


if __name__ == "__main__":
    unittest.main()
