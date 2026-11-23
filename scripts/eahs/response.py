"""Render an assistant response from a decision packet, and check any response against the packet it cites.

Two ideas are demonstrated, both on synthetic data:

* A deterministic template can write a faithful response from a packet with no model at all (a fallback when the
  assistant model is unavailable, and a baseline to compare a model against).
* A response can be checked mechanically for the properties the architecture asks of it: every statement cites
  packet items, figures come from those items, inferences are labeled, every conflict, gap, recommendation and
  proposal in the packet is mentioned, proposals are not worded as decisions, and a response is not presented as
  current when its packet has been invalidated.

A response that passes shows only that it is attributable and complete with respect to the packet. It does not
show that the packet is right, and it says nothing about how a real model would behave.
"""
from __future__ import annotations

import re
from typing import Dict, List

from .findings import Finding, rel
from .model import Instance, Model, resolve_pointer

DOC = "docs/implementation-guide.md"
DOC_EVIDENCE = "architecture/evidence-semantics.md"

KIND_PREFIX = {
    "claim": "/supported_claims_references/",
    "inference": "/labeled_inferences/",
    "conflict": "/conflicts_uncertainty/conflicts/",
    "gap": "/coverage_omissions_gaps/missingness/",
    "recommendation": "/recommendations/",
    "proposal": "/action_proposals/",
    "obligation": "/priority_mandatory_obligations/obligation_references/",
    "limitation": "/coverage_omissions_gaps/visible_scoped_limitation_summary",
}
REQUIRED_COVERAGE = ("inference", "conflict", "gap", "recommendation", "proposal", "obligation")
FIGURE_CHECKED = ("claim", "inference", "conflict", "recommendation")
DECISION_WORDING = re.compile(r"\b(has|have|had|was|were|been|is|are)\s+(now\s+)?(approved|executed|released|paid|sent|submitted)\b", re.I)
FIGURE = re.compile(r"\d[\d,.:/-]*\d|\d")


def figures(text: str) -> set:
    return {m.rstrip(".,:-/") for m in FIGURE.findall(text)}


def _strings(node) -> List[str]:
    if isinstance(node, str):
        return [node]
    if isinstance(node, dict):
        return [s for v in node.values() for s in _strings(v)]
    if isinstance(node, list):
        return [s for v in node for s in _strings(v)]
    return []


def _tv(value: dict) -> str:
    return value.get("value") or value.get("reason") or ""


def gap_text(g: dict) -> str:
    state, expected = g["state"], g["expected_evidence"]
    if state == "missing":
        return "Missing: %s. %s" % (expected, _tv(g["reason"]))
    if state == "not_retrieved":
        return "Not retrieved: %s. Retrieval %s completed with %d relevant records; an empty result does not prove absence." % (
            expected, g["retrieval_reference"]["record_id"], g["relevant_record_count"])
    if state == "inaccessible":
        return "Inaccessible: %s" % g["permission_safe_summary"]
    if state == "unavailable":
        return "Unavailable: %s. %s Nothing was read or assumed." % (expected, _tv(g["reason"]))
    if state == "negative":
        return "Checked, none found: %s. Method: %s; coverage %s for: %s." % (expected, g["method"], g["coverage"]["status"], g["coverage"]["declared_scope"])
    if state == "not_assessed":
        return "Not assessed: %s. No assessment was performed." % expected
    if state == "stale":
        return "Stale: %s %s is out of date. %s" % (g["available_record"]["record_id"], g["available_record"]["version"], g["freshness"]["basis"])
    return "%s: %s" % (state, expected)


def render_response(model: Model, packet: Instance, produced_by: str = "template-fallback-1", status: str = "current", withdrawn_reason: str = "") -> dict:
    d = packet.data
    statements: List[dict] = []

    def add(kind: str, label: str, text: str, pointer: str) -> None:
        statements.append({"kind": kind, "label": label, "text": text, "refs": [pointer]})

    for i, c in enumerate(d["supported_claims_references"]):
        add("claim", c["claim_id"], c["text"], "%s%d" % (KIND_PREFIX["claim"], i))
    for i, inf in enumerate(d["labeled_inferences"]):
        add("inference", inf["inference_id"], "Inference (model-generated, not verified): %s Limits: %s" % (inf["text"], " ".join(inf["limitations"])), "%s%d" % (KIND_PREFIX["inference"], i))
    for i, c in enumerate(d["conflicts_uncertainty"]["conflicts"]):
        add("conflict", c["conflict_id"], "Unresolved conflict %s: %s Materiality: %s." % (c["conflict_id"], c["reason"], c["materiality"].replace("_", " ")), "%s%d" % (KIND_PREFIX["conflict"], i))
    for i, g in enumerate(d["coverage_omissions_gaps"]["missingness"]):
        add("gap", "gap %d (%s)" % (i + 1, g["state"]), gap_text(g), "%s%d" % (KIND_PREFIX["gap"], i))
    for i, r in enumerate(d["recommendations"]):
        add("recommendation", r["recommendation_id"], "Recommendation (for review, not a decision): %s Basis: %s Requires: %s" % (r["text"], r["basis"], r["accountable_review_requirement"]), "%s%d" % (KIND_PREFIX["recommendation"], i))
    for i, p in enumerate(d["action_proposals"]):
        ref = p["proposal_reference"]
        prop = model.get("C05", ref["id"], ref["version"])
        what = "%s on %s %s" % (prop.data["action"]["action_kind"], prop.data["action"]["exact_target"]["entity_type"], prop.data["action"]["exact_target"]["entity_id"]) if prop else "an action"
        add("proposal", "%s %s" % (ref["id"], ref["version"]), "Proposed (not executed or approved): %s %s, %s." % (ref["id"], ref["version"], what), "%s%d" % (KIND_PREFIX["proposal"], i))
    for i, o in enumerate(d["priority_mandatory_obligations"]["obligation_references"]):
        sel = model.get("C03", o["selection_reference"]["id"], o["selection_reference"]["version"])
        ob = next((x for x in sel.data["obligations"] if x["obligation_id"] == o["obligation_id"]), None) if sel else None
        text = "Obligation %s: due %s, owner %s." % (o["obligation_id"], ob["deadline"], ob["owner"]) if ob else "Obligation %s." % o["obligation_id"]
        add("obligation", o["obligation_id"], text, "%s%d" % (KIND_PREFIX["obligation"], i))
    add("limitation", "limits", d["coverage_omissions_gaps"]["visible_scoped_limitation_summary"], KIND_PREFIX["limitation"])
    out = {
        "response_id": "RESP-%s-%s-%s" % (packet.id.split("-")[-1], packet.version, "template" if produced_by.startswith("template") else "model"),
        "synthetic": True,
        "packet_reference": {"contract_id": "C04", "id": packet.id, "version": packet.version},
        "as_of": d["decision_context_as_of"]["as_of"],
        "produced_by": produced_by,
        "status": status,
        "statements": statements,
    }
    if status != "current":
        out["status_reason"] = withdrawn_reason
    return out


def render_markdown(response: dict) -> str:
    ref = response["packet_reference"]
    order = [("claim", "What the sources say"), ("inference", "Inferences (model-generated, not verified)"), ("conflict", "Conflicts nobody has resolved"),
             ("gap", "What could not be checked"), ("recommendation", "Recommendations (for review)"), ("proposal", "Proposed actions (none is executed or approved)"),
             ("obligation", "Obligations"), ("limitation", "Limits of this view")]
    lines = ["# Review aid from packet %s %s" % (ref["id"], ref["version"]), "",
             "*Written by: %s. As of %s. Status: **%s**.*" % (response["produced_by"], response["as_of"], response["status"])]
    if response.get("status_reason"):
        lines += ["", "> **Withdrawn.** %s" % response["status_reason"]]
    lines += ["", "This is a review aid. It is not a decision, an approval or an instruction."]
    for kind, title in order:
        items = [s for s in response["statements"] if s["kind"] == kind]
        if not items:
            continue
        lines += ["", "## " + title, ""]
        for s in items:
            lines.append("- %s `[%s]`" % (s["text"], s["label"]))
    return "\n".join(lines) + "\n"


def check_response(model: Model, response: dict, path) -> List[Finding]:
    from .semantics import packet_active
    file = rel(path)
    findings: List[Finding] = []
    ref = response.get("packet_reference", {})
    packet = model.get("C04", ref.get("id"), ref.get("version"))
    if packet is None:
        return [Finding("RESP007", "the response cites packet %s %s, which does not exist" % (ref.get("id"), ref.get("version")), file, "/packet_reference", DOC)]
    d = packet.data
    if response.get("status") == "current" and not packet_active(packet):
        findings.append(Finding("RESP006", "presented as current, but packet %s %s has been invalidated: the response must be withdrawn" % (packet.id, packet.version), file, "/status", DOC))
    if response.get("as_of") and response["as_of"] != d["decision_context_as_of"]["as_of"]:
        findings.append(Finding("RESP006", "the response's as-of time differs from the packet's", file, "/as_of", DOC))
    cited: Dict[str, set] = {k: set() for k in KIND_PREFIX}
    for i, st in enumerate(response.get("statements", [])):
        loc = "/statements/%d" % i
        kind, refs, text = st.get("kind"), st.get("refs", []), st.get("text", "")
        if kind not in KIND_PREFIX:
            findings.append(Finding("RESP001", "unknown statement kind %r" % kind, file, loc, DOC))
            continue
        if not refs:
            findings.append(Finding("RESP001", "a statement must cite the packet items it rests on: this one cites nothing (%s)" % text[:60], file, loc, DOC_EVIDENCE))
            continue
        subtree: List[str] = []
        for r in refs:
            if not r.startswith(KIND_PREFIX[kind]):
                findings.append(Finding("RESP001", "a %s statement cannot rest on %s (that is not a %s item)" % (kind, r, kind), file, loc, DOC_EVIDENCE))
                continue
            try:
                node = resolve_pointer(d, r)
            except (KeyError, IndexError, ValueError, TypeError):
                findings.append(Finding("RESP001", "%s does not resolve in the packet" % r, file, loc, DOC_EVIDENCE))
                continue
            cited[kind].add(r)
            subtree += _strings(node)
        if kind in FIGURE_CHECKED and subtree:
            extra = figures(text) - figures(" ".join(subtree))
            if extra:
                findings.append(Finding("RESP002", "figures %s do not appear in the cited packet items" % ", ".join(sorted(extra)), file, loc, DOC_EVIDENCE))
        if kind == "inference" and not text.lower().startswith("inference"):
            findings.append(Finding("RESP003", "an inference must be labeled as one (start with \"Inference\")", file, loc, DOC_EVIDENCE))
        if kind == "proposal" and "not executed" not in text.lower():
            findings.append(Finding("RESP005", "a proposal must say it is not executed or approved", file, loc, "contracts/c05-action-proposal.md"))
        if kind not in ("claim", "conflict") and DECISION_WORDING.search(text):
            findings.append(Finding("RESP005", "wording presents an action as approved or done, which the packet does not support", file, loc, "contracts/c05-action-proposal.md"))
    sections = {
        "inference": len(d["labeled_inferences"]), "conflict": len(d["conflicts_uncertainty"]["conflicts"]), "gap": len(d["coverage_omissions_gaps"]["missingness"]),
        "recommendation": len(d["recommendations"]), "proposal": len(d["action_proposals"]), "obligation": len(d["priority_mandatory_obligations"]["obligation_references"]),
    }
    for kind in REQUIRED_COVERAGE:
        for i in range(sections[kind]):
            pointer = "%s%d" % (KIND_PREFIX[kind], i)
            if pointer not in cited[kind]:
                findings.append(Finding("RESP004", "the packet's %s item %d is not mentioned: a response may be shorter than its packet but may not drop a %s" % (kind, i + 1, kind), file, "/statements", DOC))
    if KIND_PREFIX["limitation"] not in cited["limitation"]:
        findings.append(Finding("RESP004", "the response does not state the packet's coverage limitation", file, "/statements", DOC))
    return findings
