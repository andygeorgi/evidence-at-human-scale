import copy
import unittest

import support  # noqa: F401

from eahs.patch import apply_ops
from eahs.response import check_response, render_markdown, render_response


def codes(response, path="response.json"):
    return sorted({f.code for f in check_response(support.example_model(), response, path)})


class Rendering(unittest.TestCase):
    def setUp(self):
        self.model = support.example_model()
        self.pkt1, self.pkt2 = self.model.get("C04", "PKT-0417", "v1"), self.model.get("C04", "PKT-0417", "v2")

    def test_a_template_response_conforms_to_its_packet(self):
        self.assertEqual(codes(render_response(self.model, self.pkt2)), [])

    def test_a_response_from_an_invalidated_packet_must_be_withdrawn(self):
        self.assertEqual(codes(render_response(self.model, self.pkt1)), ["RESP006"])
        self.assertEqual(codes(render_response(self.model, self.pkt1, status="withdrawn", withdrawn_reason="invalidated")), [])

    def test_the_committed_responses_are_what_the_template_renders(self):
        committed = support.read_json("06-assistant-response/response-PKT-0417-v2-template.json")
        self.assertEqual(committed, render_response(self.model, self.pkt2))

    def test_markdown_lists_every_section_and_the_withdrawal(self):
        text = render_markdown(render_response(self.model, self.pkt1, status="withdrawn", withdrawn_reason="invalidated"))
        for heading in ("What the sources say", "Conflicts nobody has resolved", "What could not be checked", "Proposed actions (none is executed or approved)"):
            self.assertIn(heading, text)
        self.assertIn("Withdrawn.", text)


class Conformance(unittest.TestCase):
    def setUp(self):
        self.model = support.example_model()
        self.base = render_response(self.model, self.model.get("C04", "PKT-0417", "v1"), status="withdrawn", withdrawn_reason="invalidated")

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
        self.assertEqual(codes(self.mutate({"op": "replace", "path": "/statements/%d/text" % i, "value": "Both models agree on a receiving delay."})), ["RESP003"])

    def test_dropping_a_conflict_or_a_gap_is_rejected(self):
        conflict, gap = self.index("conflict"), self.index("gap", 2)
        self.assertEqual(codes(self.mutate({"op": "remove", "path": "/statements/%d" % conflict})), ["RESP004"])
        self.assertEqual(codes(self.mutate({"op": "remove", "path": "/statements/%d" % gap})), ["RESP004"])

    def test_a_proposal_worded_as_done_is_rejected(self):
        i = self.index("proposal")
        self.assertEqual(codes(self.mutate({"op": "replace", "path": "/statements/%d/text" % i, "value": "The payment hold has been executed."})), ["RESP005"])

    def test_a_response_cannot_cite_a_packet_that_does_not_exist(self):
        self.assertEqual(codes(self.mutate({"op": "replace", "path": "/packet_reference/version", "value": "v9"})), ["RESP007"])

    def test_the_model_style_illustration_conforms(self):
        self.assertEqual(codes(support.read_json("06-assistant-response/response-PKT-0417-v1-model-style.json")), [])

    def test_a_paraphrase_with_the_wrong_number_is_caught(self):
        style = copy.deepcopy(support.read_json("06-assistant-response/response-PKT-0417-v1-model-style.json"))
        style["statements"][1]["text"] = "The goods receipt shows only 65 units received."
        self.assertEqual(codes(style), ["RESP002"])


if __name__ == "__main__":
    unittest.main()
