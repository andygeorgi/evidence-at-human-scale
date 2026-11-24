import copy
import unittest
from pathlib import Path

import support  # noqa: F401

from eahs.cases import mutate_model
from eahs.patch import apply_ops
from eahs.response import check_canonical, check_response, check_structural, is_canonical, render_markdown, render_response, trusted_lifecycle


def codes(response, path="response.json"):
    """Codes from STRUCTURAL FREE-TEXT VALIDATION alone: the constraints every response must meet."""
    return sorted({f.code for f in check_structural(support.example_model(), response, path)})


def canonical_codes(response, path="response.json"):
    """Codes from the full check, including the comparison with the renderer's output for a response that claims to be rendered."""
    return sorted({f.code for f in check_response(support.example_model(), response, path)})


class Rendering(unittest.TestCase):
    def setUp(self):
        self.model = support.example_model()
        self.pkt1, self.pkt2 = self.model.get("C04", "PKT-0417", "v1"), self.model.get("C04", "PKT-0417", "v2")

    def test_a_template_response_conforms_to_its_packet(self):
        self.assertEqual(codes(render_response(self.model, self.pkt2)), [])
        self.assertEqual(canonical_codes(render_response(self.model, self.pkt2)), [])

    def test_a_response_from_an_invalidated_packet_is_withdrawn_by_the_renderer_itself(self):
        response = render_response(self.model, self.pkt1)
        self.assertEqual((response["status"], codes(response)), ("withdrawn", []))
        self.assertEqual(response["status_reason"], "Packet PKT-0417 v1 was invalidated at 2026-11-23T13:45:00Z because GR-5521 v1 was superseded by GR-5521 v2.")

    def test_the_committed_responses_are_what_the_template_renders(self):
        committed = support.read_json("06-assistant-response/response-PKT-0417-v2-template.json")
        self.assertEqual(committed, render_response(self.model, self.pkt2))
        withdrawn = support.read_json("06-assistant-response/response-PKT-0417-v1-template.json")
        self.assertEqual(withdrawn, render_response(self.model, self.pkt1))

    def test_markdown_lists_every_section_and_the_withdrawal(self):
        text = render_markdown(render_response(self.model, self.pkt1))
        for heading in ("What the sources say", "Conflicts nobody has resolved", "What could not be checked", "Proposed actions (none is executed or approved)"):
            self.assertIn(heading, text)
        self.assertIn("Withdrawn.", text)


class Conformance(unittest.TestCase):
    def setUp(self):
        self.model = support.example_model()
        self.base = render_response(self.model, self.model.get("C04", "PKT-0417", "v1"))

    def mutate(self, *ops):
        return apply_ops(self.base, list(ops))

    def index(self, kind, nth=0):
        return [i for i, s in enumerate(self.base["statements"]) if s["kind"] == kind][nth]

    def test_a_statement_without_a_reference_is_rejected(self):
        i = self.index("claim")
        self.assertEqual(codes(self.mutate({"op": "replace", "path": "/statements/%d/refs" % i, "value": []})), ["RESP001"])

    def test_a_reference_that_does_not_resolve_is_rejected(self):
        i = self.index("claim")
        self.assertEqual(codes(self.mutate({"op": "replace", "path": "/statements/%d/refs" % i, "value": ["/supported_claims_references/99"]})), ["RESP001"])

    def test_an_inference_cannot_hide_behind_a_claim_reference(self):
        i = self.index("claim")
        self.assertEqual(codes(self.mutate({"op": "replace", "path": "/statements/%d/refs" % i, "value": ["/labeled_inferences/0"]})), ["RESP001"])

    def test_an_invented_figure_is_rejected(self):
        i = self.index("claim")
        self.assertEqual(codes(self.mutate({"op": "replace", "path": "/statements/%d/text" % i, "value": "The invoice asks for EUR 21,400.00."})), ["RESP002"])

    def test_an_unlabelled_inference_is_rejected(self):
        i = self.index("inference")
        text = "Both models agree on a receiving delay."
        # Unlabeled and also stripped of its limits: both named failures are reported.
        self.assertEqual(codes(self.mutate({"op": "replace", "path": "/statements/%d/text" % i, "value": text})), ["RESP003", "RESP010"])
        hedged = "Both models probably agree on a receiving delay, but they share one origin."
        self.assertEqual(codes(self.mutate({"op": "replace", "path": "/statements/%d/text" % i, "value": hedged})), ["RESP003"])

    def test_dropping_a_conflict_or_a_gap_is_rejected(self):
        conflict, gap = self.index("conflict"), self.index("gap", 2)
        self.assertEqual(codes(self.mutate({"op": "remove", "path": "/statements/%d" % conflict})), ["RESP004"])
        self.assertEqual(codes(self.mutate({"op": "remove", "path": "/statements/%d" % gap})), ["RESP004"])

    def test_a_proposal_worded_as_done_is_rejected(self):
        i = self.index("proposal")
        self.assertEqual(codes(self.mutate({"op": "replace", "path": "/statements/%d/text" % i, "value": "The withdrawn payment hold has been executed."})), ["RESP005"])

    def test_a_response_cannot_cite_a_packet_that_does_not_exist(self):
        self.assertEqual(codes(self.mutate({"op": "replace", "path": "/packet_reference/version", "value": "v9"})), ["RESP007"])

    def test_the_model_style_illustration_conforms(self):
        self.assertEqual(codes(support.read_json("06-assistant-response/response-PKT-0417-v1-model-style.json")), [])

    def test_a_paraphrase_with_the_wrong_number_is_caught(self):
        style = copy.deepcopy(support.read_json("06-assistant-response/response-PKT-0417-v1-model-style.json"))
        style["statements"][2]["text"] = "The goods receipt shows only 65 units received."
        found = codes(style)
        self.assertIn("RESP002", found)
        # The wrong figure also means that the statement no longer states its claim, so the claim does not count.
        self.assertEqual(found, ["RESP002", "RESP004"])


class CanonicalValidation(unittest.TestCase):
    """A response that says a renderer wrote it must equal what the renderer writes from its packet."""

    def setUp(self):
        self.model = support.example_model()
        self.packet = self.model.get("C04", "PKT-0417", "v2")
        self.response = render_response(self.model, self.packet)

    def findings(self, response):
        return check_canonical(self.model, response, self.packet, "response.json")

    def test_the_renderer_output_is_canonical_and_the_committed_template_responses_are_too(self):
        self.assertEqual(self.findings(self.response), [])
        for name in ("response-PKT-0417-v1-template.json", "response-PKT-0417-v2-template.json"):
            self.assertTrue(is_canonical(support.read_json("06-assistant-response/" + name)), name)
        self.assertFalse(is_canonical(support.read_json("06-assistant-response/response-PKT-0417-v1-model-style.json")))

    def test_any_changed_word_fails_and_names_both_texts(self):
        changed = copy.deepcopy(self.response)
        changed["statements"][0]["text"] = changed["statements"][0]["text"].replace("states", "claims")
        found = self.findings(changed)
        self.assertEqual([f.code for f in found], ["RESP101"])
        self.assertIn("Canonical:", found[0].message)
        self.assertIn("Found:", found[0].message)

    def test_a_dropped_added_or_reordered_statement_fails(self):
        dropped = copy.deepcopy(self.response)
        del dropped["statements"][3]
        self.assertEqual([f.code for f in self.findings(dropped)], ["RESP101"])
        added = copy.deepcopy(self.response)
        added["statements"].append({"kind": "claim", "label": "PC-9", "text": "All is well.", "refs": ["/supported_claims_references/0"]})
        self.assertEqual([f.code for f in self.findings(added)], ["RESP101"])
        reordered = copy.deepcopy(self.response)
        reordered["statements"][0], reordered["statements"][1] = reordered["statements"][1], reordered["statements"][0]
        self.assertEqual([f.code for f in self.findings(reordered)], ["RESP101"])

    def test_changed_citations_fail_even_when_the_text_is_right(self):
        changed = copy.deepcopy(self.response)
        changed["statements"][0]["refs"] = ["/supported_claims_references/1"]
        self.assertEqual([f.code for f in self.findings(changed)], ["RESP101"])

    def test_a_changed_as_of_time_or_response_id_fails(self):
        changed = copy.deepcopy(self.response)
        changed["as_of"] = "2026-11-23T10:00:00Z"
        changed["response_id"] = "RESP-0417-v2-model"
        self.assertEqual(sorted(f.location for f in self.findings(changed)), ["/as_of", "/response_id"])

    def test_a_field_the_renderer_does_not_write_fails_at_the_top_and_in_a_statement(self):
        extra = copy.deepcopy(self.response)
        extra["decision"] = "release the payment"
        self.assertEqual([(f.code, f.location) for f in self.findings(extra)], [("RESP101", "/decision")])
        extra = copy.deepcopy(self.response)
        extra["statements"][0]["verdict"] = "approved"
        self.assertEqual([(f.code, f.location) for f in self.findings(extra)], [("RESP101", "/statements/0/verdict")])


class Adversarial(unittest.TestCase):
    """Responses whose figures and citations are right and whose meaning is not.

    Every change below fails canonical validation. A free-form response is held only to the named structural
    constraints, so each test says which constraint catches the change; the last two tests show what the
    constraints do not catch.
    """

    def setUp(self):
        self.model = support.example_model()
        self.v1 = render_response(self.model, self.model.get("C04", "PKT-0417", "v1"))
        self.v2 = render_response(self.model, self.model.get("C04", "PKT-0417", "v2"))

    def reword(self, response, kind, label, text):
        changed = copy.deepcopy(response)
        for statement in changed["statements"]:
            if statement["kind"] == kind and label in statement["label"]:
                statement["text"] = text(statement["text"]) if callable(text) else text
                return changed
        raise AssertionError((kind, label))

    def test_a_negated_conclusion_with_unchanged_pointers(self):
        changed = self.reword(self.v1, "conflict", "CONF-QTY", "There is no conflict: the invoice (100 units) and the goods receipt (60 units) have been reconciled.")
        self.assertIn("RESP008", codes(changed))
        self.assertIn("RESP102", canonical_codes(changed))

    def test_a_negated_recommendation_passes_the_structural_constraints_and_fails_the_canonical_comparison(self):
        changed = self.reword(self.v2, "recommendation", "REC-0417-2", lambda t: t.replace("Release payment", "Do not release payment"))
        self.assertEqual(codes(changed), [])
        self.assertEqual(canonical_codes(changed), ["RESP102"])

    def test_an_altered_status_with_unchanged_numbers(self):
        changed = self.reword(self.v1, "claim", "PC-4", lambda t: t.replace("FAIL", "PASS"))
        self.assertEqual(codes(changed), ["RESP012"])
        self.assertIn("RESP102", canonical_codes(changed))

    def test_a_stale_record_reworded_as_current(self):
        changed = self.reword(self.v1, "gap", "stale", "Current: SCR-S1042 v1 is up to date. Record is 50.0 h old at evaluation; policy allows 24 h.")
        self.assertIn("RESP009", codes(changed))
        self.assertIn("RESP012", codes(changed))
        self.assertTrue({"RESP101", "RESP102"} & set(canonical_codes(changed)))

    def test_prose_that_contradicts_correct_fields_is_caught_when_it_uses_the_named_words(self):
        changed = self.reword(self.v1, "conflict", "CONF-QTY", lambda t: t + " In fact the conflict is resolved and there is nothing to review.")
        self.assertIn("RESP008", codes(changed))
        self.assertIn("RESP102", canonical_codes(changed))

    def test_other_contradictory_prose_passes_the_structural_constraints_and_fails_the_canonical_comparison(self):
        changed = self.reword(self.v1, "conflict", "CONF-QTY", lambda t: t + " Please disregard this and rely on the receipt.")
        self.assertEqual(codes(changed), [])
        self.assertEqual(canonical_codes(changed), ["RESP101"])

    def test_omitted_uncertainty(self):
        changed = self.reword(self.v1, "inference", "M01", "Inference: the goods receipt is incomplete; further units were delivered on a later date.")
        self.assertEqual(codes(changed), ["RESP010"])
        self.assertTrue({"RESP101", "RESP102"} & set(canonical_codes(changed)))

    def test_some_limits_dropped_passes_the_structural_constraints_and_fails_the_canonical_comparison(self):
        changed = self.reword(self.v1, "inference", "M01", lambda t: t.split(" Limits:")[0])
        self.assertEqual(codes(changed), [])
        self.assertTrue({"RESP101", "RESP102"} & set(canonical_codes(changed)))

    def test_unsupported_certainty(self):
        changed = self.reword(self.v1, "inference", "M02", "Inference: the quantity difference is certainly a receiving delay, and both models confirmed it.")
        self.assertEqual(codes(changed).count("RESP011"), 1)
        self.assertEqual(sum(1 for f in check_structural(self.model, changed, "r.json") if f.code == "RESP011"), 2)

    def test_certainty_the_source_itself_states_is_not_added_certainty(self):
        self.assertEqual(codes(self.v1), [])

    def test_mismatched_source_interpretation_a_claim_attributed_to_another_record(self):
        changed = self.reword(self.v1, "claim", "PC-3", "Bank statement BANK-STMT-0042 records 60 units received on 2026-11-18.")
        self.assertIn("RESP013", codes(changed))
        self.assertTrue({"RESP101", "RESP102"} & set(canonical_codes(changed)))

    def test_mismatched_source_interpretation_a_claim_in_another_currency(self):
        changed = self.reword(self.v1, "claim", "PC-1", lambda t: t.replace("EUR", "USD"))
        self.assertEqual(codes(changed), ["RESP002"])

    def test_a_gap_denied_or_a_closed_obligation_is_caught(self):
        gap = self.reword(self.v1, "gap", "missing", "Nothing is missing: the carrier proof of delivery for a second pallet of 40 units was found.")
        self.assertIn("RESP008", codes(gap))
        obligation = self.reword(self.v1, "obligation", "OBL-0417-REVIEW", "Obligation OBL-0417-REVIEW: already reviewed, owner role:ap-controller.")
        self.assertIn("RESP008", codes(obligation))


class TheLifecycleComesFromThePacket(unittest.TestCase):
    """A response cannot define its own lifecycle: the trusted packet state decides, and the response can only agree."""

    def setUp(self):
        self.model = support.example_model()
        self.pkt1, self.pkt2 = self.model.get("C04", "PKT-0417", "v1"), self.model.get("C04", "PKT-0417", "v2")
        self.v1 = render_response(self.model, self.pkt1)
        self.v2 = render_response(self.model, self.pkt2)

    def changed(self, response, **fields):
        out = copy.deepcopy(response)
        for key, value in fields.items():
            if value is MISSING:
                out.pop(key, None)
            else:
                out[key] = value
        return out

    def test_the_trusted_lifecycle_is_read_from_the_packet(self):
        self.assertEqual(trusted_lifecycle(self.model, self.pkt2), ("current", ""))
        status, reason = trusted_lifecycle(self.model, self.pkt1)
        self.assertEqual(status, "withdrawn")
        self.assertEqual(reason, "Packet PKT-0417 v1 was invalidated at 2026-11-23T13:45:00Z because GR-5521 v1 was superseded by GR-5521 v2.")

    def test_the_renderer_takes_no_status_from_its_caller(self):
        for argument in ({"status": "current"}, {"withdrawn_reason": "fine"}):
            with self.assertRaises(TypeError):
                render_response(self.model, self.pkt1, **argument)

    def test_the_correct_withdrawn_v1_and_the_correct_current_v2_are_accepted(self):
        for response in (self.v1, self.v2, support.read_json("06-assistant-response/response-PKT-0417-v1-model-style.json")):
            self.assertEqual(codes(response), [])
        self.assertEqual(canonical_codes(self.v1), [])
        self.assertEqual(canonical_codes(self.v2), [])

    def test_a_response_about_an_invalidated_packet_cannot_be_current(self):
        response = self.changed(self.v1, status="current")
        self.assertIn("RESP006", codes(response))
        self.assertIn("RESP101", canonical_codes(response))
        self.assertIn("the packet's state decides", next(f.message for f in check_structural(self.model, response, "r.json") if f.code == "RESP006"))

    def test_a_response_cannot_call_itself_active_historical_or_anything_else(self):
        for word in ("active", "historical", "valid", "CURRENT", "Current", " current", "archived", ""):
            with self.subTest(repr(word)):
                self.assertIn("RESP014", codes(self.changed(self.v1, status=word)))
                self.assertIn("RESP014", codes(self.changed(self.v2, status=word)))

    def test_a_status_that_is_not_text_is_refused(self):
        for value in (None, 1, ["current"], {"state": "current"}):
            with self.subTest(repr(value)):
                self.assertIn("RESP014", codes(self.changed(self.v1, status=value)))

    def test_a_missing_status_is_refused_not_assumed(self):
        for response in (self.v1, self.v2):
            self.assertIn("RESP014", codes(self.changed(response, status=MISSING)))
            self.assertIn("RESP101", canonical_codes(self.changed(response, status=MISSING)))

    def test_a_response_cannot_withdraw_itself_from_an_active_packet(self):
        response = self.changed(self.v2, status="withdrawn", status_reason="Packet PKT-0417 v2 was invalidated at 2026-11-23T14:10:00Z.")
        found = [f for f in check_structural(self.model, response, "r.json") if f.code == "RESP006"]
        self.assertEqual(len(found), 1)
        self.assertIn("cannot withdraw itself", found[0].message)

    def test_a_current_response_carries_no_withdrawal_reason(self):
        self.assertIn("RESP015", codes(self.changed(self.v2, status_reason="Packet PKT-0417 v2 is fine.")))

    def test_a_missing_as_of_time_is_refused(self):
        self.assertIn("RESP006", codes(self.changed(self.v2, as_of=MISSING)))

    def test_a_withdrawn_response_must_give_the_reason(self):
        self.assertIn("RESP015", codes(self.changed(self.v1, status_reason=MISSING)))
        self.assertIn("RESP015", codes(self.changed(self.v1, status_reason="")))
        self.assertIn("RESP015", codes(self.changed(self.v1, status_reason=["invalidated"])))

    def test_a_contradictory_withdrawal_reason_is_refused(self):
        contradictions = [
            "Packet PKT-0417 v1 was never invalidated: GR-5521 v1 was superseded by GR-5521 v2.",
            "Packet PKT-0417 v1 was invalidated at 2026-11-23T13:45:00Z, but it remains valid and current.",
            "Packet PKT-0417 v1 is still current although it was invalidated.",
            "Packet PKT-0417 v1 was invalidated and then reinstated at 2026-11-23T13:45:00Z.",
            "Packet PKT-0417 v1 was invalidated; the withdrawal was lifted.",
            "Packet PKT-0417 v1 was not withdrawn: it was invalidated in error.",
        ]
        for reason in contradictions:
            with self.subTest(reason):
                self.assertIn("RESP015", codes(self.changed(self.v1, status_reason=reason)))

    def test_a_withdrawal_reason_that_gives_another_packet_state_cause_or_time_is_refused(self):
        wrong = {
            "another packet": "Packet PKT-0418 v1 was invalidated at 2026-11-23T13:45:00Z because GR-5521 v1 was superseded by GR-5521 v2.",
            "another version": "Packet PKT-0417 v2 was invalidated at 2026-11-23T13:45:00Z because GR-5521 v1 was superseded by GR-5521 v2.",
            "another event": "Packet PKT-0417 v1 was retired at 2026-11-23T13:45:00Z because GR-5521 v1 was superseded by GR-5521 v2.",
            "another cause": "Packet PKT-0417 v1 was invalidated at 2026-11-23T13:45:00Z because PO-77231 v1 was superseded by PO-77231 v2.",
            "another time": "Packet PKT-0417 v1 was invalidated at 2026-11-23T09:00:00Z because GR-5521 v1 was superseded by GR-5521 v2.",
        }
        for label, reason in wrong.items():
            with self.subTest(label):
                self.assertIn("RESP015", codes(self.changed(self.v1, status_reason=reason)))

    def test_the_whole_reason_is_the_packets_own_apart_from_one_fixed_introduction(self):
        trusted = trusted_lifecycle(self.model, self.pkt1)[1]
        for reason in (trusted, "This response was withdrawn: " + trusted, trusted.replace(" because ", "   because\n").replace("Packet PKT-0417 v1", "Packet PKT-0417   v1")):
            with self.subTest(reason[:40]):
                self.assertEqual(codes(self.changed(self.v1, status_reason=reason, produced_by="an-assistant-model")), [])

    def test_a_sentence_added_to_the_reason_is_refused_even_when_nothing_can_show_it_false(self):
        trusted = trusted_lifecycle(self.model, self.pkt1)[1]
        for extra in ("Read the new packet instead.", "The invoice was paid on 2026-11-23.", "Nobody needs to review it.", "Note that GR-5521 v1 was replaced by GR-5521 v2."):
            for label, reason in (("after", trusted + " " + extra), ("before", extra + " " + trusted), ("in the introduction", "This response was withdrawn. " + extra + " " + trusted)):
                with self.subTest("%s %s" % (label, extra)):
                    found = [f for f in check_structural(self.model, self.changed(self.v1, status_reason=reason, produced_by="an-assistant-model"), "r.json") if f.code == "RESP015"]
                    self.assertTrue(found)
                    self.assertTrue(any("exactly the packet's own reason" in f.message for f in found), [f.message for f in found])

    def test_a_paraphrase_that_leaves_out_part_of_the_packets_reason_is_refused(self):
        reason = "Packet PKT-0417 v1 was invalidated because the goods receipt GR-5521 was superseded."
        found = [f for f in check_structural(self.model, self.changed(self.v1, status_reason=reason, produced_by="an-assistant-model"), "r.json") if f.code == "RESP015"]
        self.assertEqual(len(found), 1)
        self.assertIn("exactly the packet's own reason", found[0].message)

    def test_a_supersession_in_the_wrong_direction_is_refused(self):
        trusted = trusted_lifecycle(self.model, self.pkt1)[1]
        reasons = {
            "only the reversal": "Packet PKT-0417 v1 was invalidated at 2026-11-23T13:45:00Z because GR-5521 v2 was superseded by GR-5521 v1.",
            "the reversal after the true reason": trusted + " GR-5521 v2 was superseded by GR-5521 v1.",
            "the reversal before the true reason": "GR-5521 v2 was superseded by GR-5521 v1. " + trusted,
            "the reversal with another verb": trusted + " GR-5521 v2 has been replaced by GR-5521 v1.",
            "a supersession nobody recorded": trusted + " PO-77231 v1 was superseded by PO-77231 v2.",
        }
        for label, reason in reasons.items():
            with self.subTest(label):
                self.assertIn("RESP015", codes(self.changed(self.v1, status_reason=reason, produced_by="an-assistant-model")))
        reversed_only = [f for f in check_structural(self.model, self.changed(self.v1, status_reason=reasons["only the reversal"]), "r.json") if f.code == "RESP015"]
        self.assertTrue(any("reverse or invent a supersession" in f.message for f in reversed_only), [f.message for f in reversed_only])

    def test_a_true_direction_added_to_the_reason_is_still_an_addition(self):
        trusted = trusted_lifecycle(self.model, self.pkt1)[1]
        self.assertIn("RESP015", codes(self.changed(self.v1, status_reason=trusted + " Note that GR-5521 v1 was replaced by GR-5521 v2.", produced_by="an-assistant-model")))

    def test_advice_phrased_as_current_in_a_withdrawn_response_is_refused(self):
        for kind in ("recommendation", "proposal", "obligation"):
            with self.subTest(kind):
                response = copy.deepcopy(self.v1)
                statement = next(s for s in response["statements"] if s["kind"] == kind)
                statement["text"] = {"recommendation": "Recommendation (for review, not a decision): hold the invoice now.",
                                     "proposal": "Proposed (not executed or approved): release_payment on invoice INV-2026-0417.",
                                     "obligation": "Obligation OBL-0417-REVIEW: due 2026-11-23T15:30:00Z, owner role:ap-controller."}[kind]
                found = [f for f in check_structural(self.model, response, "r.json") if f.code == "RESP016"]
                self.assertEqual(len(found), 1)
                self.assertIn("withdrawn", found[0].message)

    def test_advice_that_names_the_withdrawal_and_still_calls_itself_current_is_refused(self):
        for phrase in ("This is current advice.", "This recommendation is still valid.", "It remains active.", "The advice is in force.", "It is up to date.", "Currently this applies."):
            for kind, lead in (("recommendation", "Recommendation from the withdrawn packet (for review, not a decision): hold the invoice. "),
                               ("proposal", "Proposal from the withdrawn packet (not executed or approved): a payment hold. "),
                               ("obligation", "Obligation OBL-0417-REVIEW from the withdrawn packet: review before 15:30. ")):
                with self.subTest("%s: %s" % (kind, phrase)):
                    response = copy.deepcopy(self.v1)
                    next(s for s in response["statements"] if s["kind"] == kind)["text"] = lead + phrase
                    found = [f for f in check_structural(self.model, response, "r.json") if f.code == "RESP016"]
                    self.assertEqual(len(found), 1, [f.message for f in found])
                    self.assertIn("calls something current or valid", found[0].message)

    def test_saying_that_the_advice_is_not_current_is_not_calling_it_current(self):
        for phrase in ("This is not current advice.", "It is no longer valid.", "It is not yet active and never was in force.", "Not current."):
            with self.subTest(phrase):
                response = copy.deepcopy(self.v1)
                next(s for s in response["statements"] if s["kind"] == "recommendation")["text"] = "Recommendation from the withdrawn packet (for review, not a decision): hold the invoice. " + phrase
                self.assertEqual([f for f in check_structural(self.model, response, "r.json") if f.code == "RESP016"], [])

    def test_no_kind_of_statement_in_a_withdrawn_response_may_call_something_current_that_its_items_do_not(self):
        for kind in ("claim", "inference", "conflict", "gap", "limitation"):
            with self.subTest(kind):
                response = copy.deepcopy(self.v1)
                statement = next(s for s in response["statements"] if s["kind"] == kind)
                statement["text"] += " This is current."
                self.assertIn("RESP016", [f.code for f in check_structural(self.model, response, "r.json")])

    def test_words_that_the_packet_items_themselves_use_are_not_added_currency(self):
        response = support.read_json("06-assistant-response/response-PKT-0417-v1-model-style.json")
        text = next(s for s in response["statements"] if s["label"].startswith("REC-0417-1"))["text"]
        self.assertIn("screening is current", text)
        self.assertEqual([f for f in check_structural(self.model, response, "r.json") if f.code == "RESP016"], [])

    def test_the_same_advice_is_fine_in_a_current_response(self):
        self.assertEqual([f for f in check_structural(self.model, self.v2, "r.json") if f.code == "RESP016"], [])

    def test_the_lifecycle_follows_the_packet_when_the_packet_changes(self):
        # Invalidate v2 in the trusted data: the same response, unchanged, is no longer acceptable as current.
        model, _ = mutate_model(self.model, [{"target": "C04 PKT-0417 v2", "ops": [{"op": "replace", "path": "/review_version_history/state", "value": "invalidated"}]}])
        found = {f.code for f in check_structural(model, self.v2, "r.json")}
        self.assertIn("RESP006", found)
        # And re-activating v1 in the trusted data makes its withdrawn response the inconsistent one.
        model, _ = mutate_model(self.model, [{"target": "C04 PKT-0417 v1", "ops": [{"op": "replace", "path": "/review_version_history/state", "value": "reviewed"}]}])
        self.assertIn("RESP006", {f.code for f in check_structural(model, self.v1, "r.json")})

    def test_malformed_responses_are_findings_not_crashes(self):
        for response in (self.changed(self.v2, packet_reference="PKT-0417"), self.changed(self.v2, statements=[1, "x", None]),
                         self.changed(self.v2, statements=[{"kind": "claim", "text": 5, "refs": "x"}])):
            with self.subTest(repr(response)[:60]):
                self.assertTrue(canonical_codes(response))


MISSING = object()


class CoverageAndStatusConsistency(unittest.TestCase):
    """Free text stays tied to its packet: its supported claims cannot all disappear, and a status cannot change in any kind of statement."""

    def setUp(self):
        self.model = support.example_model()
        self.v1 = render_response(self.model, self.model.get("C04", "PKT-0417", "v1"))
        self.v2 = render_response(self.model, self.model.get("C04", "PKT-0417", "v2"))

    def only_claims(self, response, keep):
        out = copy.deepcopy(response)
        claims = [s for s in out["statements"] if s["kind"] == "claim"]
        out["statements"] = [s for s in out["statements"] if s["kind"] != "claim"] + claims[:keep]
        return out

    def test_the_minimum_is_documented_and_is_half_of_the_claims_rounded_up(self):
        from eahs.response import MIN_CLAIM_COVERAGE
        self.assertEqual(MIN_CLAIM_COVERAGE, 0.5)
        import eahs.response as module
        self.assertIn("MIN_CLAIM_COVERAGE", module.__doc__)
        readme = (support.EXAMPLES / "06-assistant-response" / "README.md").read_text(encoding="utf-8")
        self.assertIn("half of the packet's supported claims", readme)

    def test_a_response_that_states_none_of_its_packets_claims_is_refused(self):
        for response in (self.v1, self.v2):
            found = [f for f in check_structural(self.model, self.only_claims(response, 0), "r.json") if f.code == "RESP004"]
            self.assertEqual(len(found), 1)
            self.assertIn("states 0 of the packet's 7 supported claims", found[0].message)

    def test_the_least_it_may_state_is_four_of_seven(self):
        self.assertEqual([f.code for f in check_structural(self.model, self.only_claims(self.v1, 3), "r.json")], ["RESP004"])
        self.assertEqual(codes(self.only_claims(self.v1, 4)), [])
        self.assertEqual(codes(self.only_claims(self.v2, 4)), [])

    def test_a_packet_with_no_claims_asks_for_none(self):
        model, _ = mutate_model(self.model, [{"target": "C04 PKT-0417 v2", "ops": [{"op": "replace", "path": "/supported_claims_references", "value": []}]}])
        packet = model.get("C04", "PKT-0417", "v2")
        response = render_response(model, packet)
        self.assertEqual([s for s in response["statements"] if s["kind"] == "claim"], [])
        self.assertEqual([f.code for f in check_structural(model, response, "r.json") if f.code == "RESP004"], [])

    def test_the_free_form_illustration_states_enough_of_the_claims(self):
        style = support.read_json("06-assistant-response/response-PKT-0417-v1-model-style.json")
        self.assertGreaterEqual(len([s for s in style["statements"] if s["kind"] == "claim"]), 4)
        self.assertEqual(codes(style), [])

    def test_four_parts_of_one_claim_are_one_claim(self):
        parts = ["/supported_claims_references/0/text", "/supported_claims_references/0/claim_id",
                 "/supported_claims_references/0/supporting_references/0/record_id", "/supported_claims_references/0/supporting_references/0/version"]
        claim_text = next(s for s in self.v1["statements"] if s["kind"] == "claim")["text"]
        response = copy.deepcopy(self.only_claims(self.v1, 0))
        response["statements"] += [{"kind": "claim", "label": "PC-1 part %d" % i, "text": claim_text, "refs": [pointer]} for i, pointer in enumerate(parts)]
        found = [f for f in check_structural(self.model, response, "r.json") if f.code == "RESP004"]
        self.assertEqual(len(found), 1)
        self.assertIn("states 1 of the packet's 7 supported claims", found[0].message)

    def test_one_claim_cited_twice_counts_once(self):
        response = copy.deepcopy(self.only_claims(self.v1, 3))
        first = next(s for s in response["statements"] if s["kind"] == "claim")
        response["statements"].append(dict(first, label="PC-1 again"))
        self.assertEqual([f.code for f in check_structural(self.model, response, "r.json")], ["RESP004"])

    def test_a_statement_that_cites_a_claim_but_does_not_state_it_does_not_count(self):
        response = copy.deepcopy(self.v1)
        for statement in response["statements"]:
            if statement["kind"] == "claim":
                statement["text"] = "Noted."
        found = [f for f in check_structural(self.model, response, "r.json") if f.code == "RESP004"]
        self.assertEqual(len(found), 1)
        self.assertIn("states 0 of the packet's 7", found[0].message)

    def test_a_statement_with_no_text_is_refused_and_does_not_count(self):
        for text in ("", "   ", "\n\t"):
            with self.subTest(repr(text)):
                response = copy.deepcopy(self.v1)
                for statement in response["statements"]:
                    if statement["kind"] == "claim":
                        statement["text"] = text
                found = {f.code for f in check_structural(self.model, response, "r.json")}
                self.assertEqual(found, {"RESP001", "RESP004"})

    def test_a_claim_without_a_figure_counts_when_two_of_its_words_are_kept(self):
        from eahs.response import quantities, states_claim
        claim = "Supplier S-1042 was screened against the sanctions and watch lists on 2026-11-21: no match."
        self.assertEqual(quantities(claim), set())
        self.assertTrue(states_claim(claim, "The supplier was screened against the sanctions lists and nothing matched."))
        self.assertFalse(states_claim(claim, "Screened."))
        self.assertFalse(states_claim(claim, "The goods receipt shows 60 units."))

    def test_a_claim_with_figures_counts_when_one_of_them_is_kept(self):
        from eahs.response import states_claim
        claim = "Goods receipt GR-5521 records 60 units received on 2026-11-18."
        self.assertTrue(states_claim(claim, "Only 60 units arrived."))
        self.assertTrue(states_claim("The invoice states EUR 18,400.00 for 100 units.", "The invoice asks for 18400 euros."))
        self.assertFalse(states_claim(claim, "Only 65 units arrived."))
        self.assertFalse(states_claim(claim, "The goods receipt GR-5521 records the units."))

    def test_a_bare_number_does_not_state_a_claim(self):
        from eahs.response import states_claim
        claim = "Goods receipt GR-5521 records 60 units received on 2026-11-18."
        for statement in ("60", "60 60 60", "60.", "EUR 60", "Noted: 60", "60 %"):
            with self.subTest(statement):
                self.assertFalse(states_claim(claim, statement))

    def test_a_response_whose_claims_are_bare_numbers_states_none_of_them(self):
        from eahs.response import quantities
        for base in (self.v1, self.v2):
            response = copy.deepcopy(base)
            for statement in response["statements"]:
                if statement["kind"] == "claim":
                    held = sorted(quantities(statement["text"]))
                    statement["text"] = ("%g" % held[0]) if held else "Noted."
            found = [f for f in check_structural(self.model, response, "r.json") if f.code == "RESP004"]
            self.assertEqual(len(found), 1)
            self.assertIn("states 0 of the packet's 7", found[0].message)

    def test_a_status_cannot_be_negated_into_its_opposite(self):
        match = "(invoiced 100 units, received %d units, variance %s%%, tolerance 2%%)"
        cases = (
            (self.v1, "The three-way match did not fail " + match % (60, "40.0"), "fail"),
            (self.v1, "The three-way match never failed " + match % (60, "40.0"), "fail"),
            (self.v1, "No failure in the three-way match " + match % (60, "40.0"), "fail"),
            (self.v1, "The three-way match didn't fail " + match % (60, "40.0"), "fail"),
            (self.v2, "The three-way match did not pass " + match % (100, "0.0"), "pass"),
            (self.v2, "The three-way match has never passed " + match % (100, "0.0"), "pass"),
        )
        for base, text, name in cases:
            with self.subTest(text[:48]):
                response = copy.deepcopy(base)
                next(s for s in response["statements"] if s["label"] == "PC-4")["text"] = text
                found = [f for f in check_structural(self.model, response, "r.json") if f.code == "RESP012"]
                self.assertEqual(len(found), 1, [f.message for f in found])
                self.assertIn(repr(name), found[0].message)
                self.assertIn("negates", found[0].message)

    def test_a_status_the_items_negate_cannot_be_stated_plainly(self):
        model, _ = mutate_model(self.model, [{"target": "C04 PKT-0417 v2", "ops": [{"op": "replace", "path": "/supported_claims_references/3/text",
                                                                                      "value": "Three-way match M3W 2.0 on INV-2026-0417 did not pass (invoiced 100 units, received 100 units, variance 0.0%, tolerance 2%)."}]}])
        found = [f for f in check_structural(model, self.v2, "r.json") if f.code == "RESP012"]
        self.assertEqual(len(found), 1, [f.message for f in found])
        self.assertIn("only negated", found[0].message)

    def test_a_negation_that_belongs_to_something_else_is_not_a_negated_status(self):
        for text in ("Not verified: the three-way match PASS (invoiced 100 units, received 100 units, variance 0.0%, tolerance 2%).",
                     "The invoice was not paid, and the three-way match PASS (invoiced 100 units, received 100 units, variance 0.0%, tolerance 2%)."):
            with self.subTest(text[:40]):
                response = copy.deepcopy(self.v2)
                next(s for s in response["statements"] if s["label"] == "PC-4")["text"] = text
                self.assertEqual([f.code for f in check_structural(self.model, response, "r.json") if f.code == "RESP012"], [])

    def test_a_status_word_in_the_label_is_held_to_the_same_rule_as_the_text(self):
        for label, code, part in (("Match PASS", "RESP012", "label"), ("PC-3 (did not fail)", "RESP012", "label"), ("Confirmed receipt", "RESP011", "label")):
            with self.subTest(label):
                response = copy.deepcopy(self.v1)
                next(s for s in response["statements"] if s["label"] == "PC-3")["label"] = label
                found = [f for f in check_structural(self.model, response, "r.json") if f.code == code]
                self.assertTrue(found, label)
                self.assertTrue(any(part in f.message for f in found), [f.message for f in found])

    def test_a_label_that_says_what_the_cited_item_says_is_fine(self):
        response = copy.deepcopy(self.v1)
        next(s for s in response["statements"] if s["label"] == "PC-4")["label"] = "Match FAIL"
        self.assertEqual([f.code for f in check_structural(self.model, response, "r.json")], [])

    def test_a_withdrawn_response_cannot_call_a_label_current(self):
        response = copy.deepcopy(self.v1)
        next(s for s in response["statements"] if s["label"] == "PC-3")["label"] = "Current receipt"
        found = [f for f in check_structural(self.model, response, "r.json") if f.code == "RESP016"]
        self.assertTrue(any("label" in f.message for f in found), [f.message for f in found])

    def test_identifiers_dates_and_times_are_not_quantities(self):
        from eahs.response import quantities
        self.assertEqual(quantities("INV-2026-0417 from S-1042, FC-88231, dated 2026-11-22T13:45:00Z, due by 15:30; 100 units at EUR 184.00, total EUR 18,400.00, 40.0% over 2%."),
                         {100.0, 184.0, 18400.0, 40.0, 2.0})

    def test_a_status_cannot_change_in_any_kind_of_statement(self):
        for kind in ("claim", "inference", "conflict", "gap", "recommendation", "proposal", "obligation"):
            with self.subTest(kind):
                response = copy.deepcopy(self.v1)
                statement = next(s for s in response["statements"] if s["kind"] == kind)
                statement["text"] += " It has been revoked."
                found = [f for f in check_structural(self.model, response, "r.json") if f.code == "RESP012"]
                self.assertEqual(len(found), 1, kind)
                self.assertIn("'revoked'", found[0].message)

    def test_a_status_the_cited_item_states_is_not_a_change(self):
        response = copy.deepcopy(self.v2)
        statement = next(s for s in response["statements"] if s["kind"] == "recommendation")
        self.assertIn("passes", statement["text"])
        self.assertEqual([f.code for f in check_structural(self.model, response, "r.json") if f.code == "RESP012"], [])

    def test_a_failed_match_restated_as_passed_in_a_recommendation_is_found(self):
        response = copy.deepcopy(self.v1)
        statement = next(s for s in response["statements"] if s["label"] == "REC-0417-1B")
        statement["text"] = statement["text"].replace("only if the match passes", "because the match failed and so it is safe")
        self.assertIn("RESP012", codes(response))

    def test_the_lifecycle_labels_of_a_withdrawn_response_are_not_a_change_of_status(self):
        self.assertEqual([f.code for f in check_structural(self.model, self.v1, "r.json") if f.code == "RESP012"], [])
        advice = [s for s in self.v1["statements"] if s["kind"] in ("recommendation", "proposal", "obligation")]
        self.assertTrue(all("withdrawn" in s["text"].lower() for s in advice))

    def test_a_very_long_statement_is_read_in_one_pass(self):
        import time
        response = copy.deepcopy(self.v1)
        next(s for s in response["statements"] if s["kind"] == "recommendation")["text"] += " This is current. " * 20000 + " 12 " * 20000
        start = time.perf_counter()
        self.assertIn("RESP016", [f.code for f in check_structural(self.model, response, "r.json")])
        self.assertLess(time.perf_counter() - start, 10)


class ADamagedResponseIsAFindingNotAnError(unittest.TestCase):
    """Random damage to a stored response (a part removed, or replaced by another kind of value) gives findings. It never ends the check in an error."""

    VALUES = (None, "x", "", [], {}, -1, 0, True, 1.5, {"a": 1}, [1, 2], "current", "withdrawn", "Inference: x", 10 ** 50, ["/supported_claims_references/0"], "/supported_claims_references/0")

    @staticmethod
    def paths(node, prefix=()):
        yield prefix
        for key, value in (node.items() if isinstance(node, dict) else enumerate(node) if isinstance(node, list) else ()):
            yield from ADamagedResponseIsAFindingNotAnError.paths(value, prefix + (key,))

    def damaged(self, data, rng):
        data = copy.deepcopy(data)
        path = rng.choice([p for p in self.paths(data) if p])
        parent = data
        for key in path[:-1]:
            parent = parent[key]
        if rng.random() < 0.34:
            del parent[path[-1]]
        else:
            parent[path[-1]] = rng.choice(self.VALUES)
        return data

    def test_five_hundred_damaged_responses_each_give_findings(self):
        import random
        model = support.example_model()
        bases = [render_response(model, model.get("C04", "PKT-0417", v)) for v in ("v1", "v2")] + [support.read_json("06-assistant-response/response-PKT-0417-v1-model-style.json")]
        for seed in range(500):
            rng = random.Random(seed)
            response = rng.choice(bases)
            for _ in range(rng.randint(1, 3)):
                response = self.damaged(response, rng)
            try:
                check_response(model, response, "r.json")
            except Exception as exc:  # noqa: BLE001
                self.fail("seed %d: %s: %s" % (seed, type(exc).__name__, exc))

    def test_statements_that_are_not_a_list_are_one_finding(self):
        model = support.example_model()
        response = render_response(model, model.get("C04", "PKT-0417", "v2"))
        for value in (None, 5, "text", {"kind": "claim"}):
            with self.subTest(repr(value)):
                response["statements"] = value
                self.assertIn("RESP001", {f.code for f in check_response(model, response, "r.json")})

    def test_a_packet_reference_that_is_not_text_names_no_packet(self):
        model = support.example_model()
        response = render_response(model, model.get("C04", "PKT-0417", "v2"))
        for value in ([], {}, ["PKT-0417"], 7):
            with self.subTest(repr(value)):
                response["packet_reference"] = {"contract_id": "C04", "id": value, "version": "v2"}
                self.assertEqual([f.code for f in check_response(model, response, "r.json")], ["RESP007"])


class ClaimBoundary(unittest.TestCase):
    """What each validation promises. The documents must say the same, and the code must not promise more."""

    def setUp(self):
        self.model = support.example_model()
        self.v2 = render_response(self.model, self.model.get("C04", "PKT-0417", "v2"))

    def test_a_response_that_does_not_say_it_was_rendered_is_not_compared_with_the_renderer(self):
        reversed_free_form = copy.deepcopy(self.v2)
        reversed_free_form["produced_by"] = "an-assistant-model"
        for statement in reversed_free_form["statements"]:
            if statement["kind"] == "recommendation":
                statement["text"] = statement["text"].replace("Release payment", "Do not release payment")
        self.assertEqual(canonical_codes(reversed_free_form), [])
        reversed_template = copy.deepcopy(reversed_free_form)
        reversed_template["produced_by"] = "template-fallback-1"
        self.assertEqual(canonical_codes(reversed_template), ["RESP102"])

    def test_the_documents_name_both_validations_and_deny_that_the_structural_one_proves_meaning(self):
        text = (support.EXAMPLES / "06-assistant-response" / "README.md").read_text(encoding="utf-8")
        for phrase in ("CANONICAL RESPONSE VALIDATION", "STRUCTURAL FREE-TEXT VALIDATION", "does not prove"):
            self.assertIn(phrase, text)
        scripts = (support.SCRIPTS / "README.md").read_text(encoding="utf-8")
        for phrase in ("canonical", "structural", "does not prove"):
            self.assertIn(phrase, scripts.lower() if phrase != "does not prove" else scripts)

    def test_the_module_does_not_claim_semantic_fidelity_for_free_form_text(self):
        import eahs.response as response
        self.assertIn("do NOT show that the prose is\nsemantically correct", response.__doc__)


if __name__ == "__main__":
    unittest.main()
