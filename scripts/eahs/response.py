"""Render an assistant response from a decision packet, and check any response against the packet it cites.

Two kinds of validation are demonstrated, on synthetic data. They answer different questions and must not be confused.

CANONICAL RESPONSE VALIDATION. A deterministic renderer can write the response from a packet with no model at all (a
fallback when the assistant model is unavailable, and a baseline to compare a model against). A response that says it
came from that renderer (``produced_by`` starts with ``template``) is compared statement by statement with what the
renderer produces from its packet. Any difference fails, and a difference that adds or removes a negation, changes a
status word or changes a figure is reported as a change of meaning (RESP102). This verifies the response's content
against a defined template. It does not verify the packet.

STRUCTURAL FREE-TEXT VALIDATION. A response written by a model or a person is checked against named constraints:
every statement cites packet items of the right kind; its figures and currencies, its status words (pass, fail, stale,
revoked, ...) and the record identifiers it names all appear in the items it cites; an inference is labeled and keeps
a limitation; a conflict stays open and a gap keeps its missingness label; a recommendation says it is for review; a
proposal is not worded as done; certainty is not added; and every conflict, gap, recommendation, proposal and obligation
of the packet is mentioned. These constraints catch specific, named failures. They do NOT show that the prose is
semantically correct: a sentence can satisfy every constraint and still mislead. Where the response is not canonical,
only a person, or a comparison with a canonical rendering, can judge what it means.

Neither validation shows that the packet is right, and neither says anything about how a real model would behave.
"""
from __future__ import annotations

import re
from typing import Dict, List

from .findings import Finding, rel
from .model import Instance, Model, resolve_pointer

DOC = "docs/implementation-guide.md"
DOC_EVIDENCE = "architecture/evidence-semantics.md"
DOC_RESPONSE = "examples/06-assistant-response/README.md"

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
CURRENCY = re.compile(r"\b(EUR|USD|GBP|ISK|NOK|SEK|DKK|CHF|JPY)\b")

#: Statement kinds on which each structural constraint is applied.
STATUS_CHECKED = ("claim", "conflict", "gap")
IDENTIFIER_CHECKED = ("claim", "inference", "conflict", "gap", "recommendation", "obligation")

#: Status words a statement may use only if the items it cites use them too: a failed match may not become a passed one.
STATUS_WORDS = {
    "pass": re.compile(r"\bpass(?:es|ed|ing)?\b", re.I),
    "fail": re.compile(r"\bfail(?:s|ed|ing|ure)?\b", re.I),
    "stale": re.compile(r"\bstale\b|\bout of date\b", re.I),
    "current": re.compile(r"\bcurrent\b", re.I),
    "superseded": re.compile(r"\bsuperseded\b", re.I),
    "invalidated": re.compile(r"\binvalidated\b", re.I),
    "revoked": re.compile(r"\brevoked\b", re.I),
    "withdrawn": re.compile(r"\bwithdrawn\b", re.I),
}
NEGATION = re.compile(r"\b(?:no|not|never|none|nothing|nobody|neither|nor|without|cannot)\b|n't\b", re.I)
#: Certainty a statement may add only if the items it cites already say it (a source may say "confirmed"; a model may not).
CERTAINTY = re.compile(r"\b(?:certain(?:ly)?|definite(?:ly)?|undoubted(?:ly)?|guarantee[sd]?|proven|proves?|conclusive(?:ly)?|beyond (?:any )?doubt|without (?:a )?doubt|no doubt|obviously|clearly|confirmed|(?<!not )verified|safe to (?:pay|release))\b", re.I)
#: Wording that closes what the packet keeps open.
CLOSES_CONFLICT = re.compile(r"\bno (?:longer )?(?:a )?(?:material )?conflicts?\b|\bnot (?:a )?conflicts?\b|\bconflicts? (?:is|are|was|were|has been|have been) (?:now )?(?:resolved|settled|closed|reconciled|cleared)\b|\b(?:resolved|reconciled|settled) conflicts?\b|\bsources (?:agree|are consistent)\b|\bno (?:material )?(?:discrepanc\w+|differences?)\b", re.I)
DENIES_GAP = re.compile(r"\bnothing (?:is|was) missing\b|\bno (?:gaps?|omissions?|missing (?:evidence|information))\b|\b(?:fully|completely|entirely) (?:covered|checked|assessed)\b|\ball (?:sources|checks|evidence) (?:were|was|have been) (?:checked|covered|available|retrieved)\b", re.I)
CLOSES_OBLIGATION = re.compile(r"\bno (?:review|obligation|action) (?:is )?(?:required|needed|due)\b|\balready (?:done|met|completed|satisfied|reviewed)\b|\bwaived\b", re.I)
#: Markers a statement must keep so that the uncertainty of what it cites is not lost.
KEEPS_CONFLICT_OPEN = re.compile(r"\bunresolved\b|\bnot (?:yet )?(?:been )?resolved\b|\bnobody has resolved\b|\bdisagree\w*\b|\bdiffer(?:s|ed|ent|ing)?\b|\bcontradict\w*\b|\bstill open\b", re.I)
KEEPS_INFERENCE_LIMITED = re.compile(r"not verified|unverified|model-generated|\blimits?:|\blimitations?\b|common origin|one origin|\bprobabl\w+|\bpossibl\w+|\bmight\b|\bmay\b|\bsuggest\w*|\bappears?\b|\binfers?\b", re.I)
KEEPS_RECOMMENDATION_OPEN = re.compile(r"for review|not a decision", re.I)
#: The words that say each missingness label. A gap statement must use the words of every label it cites.
STATE_WORDS = {
    "missing": re.compile(r"\bmissing\b|\bnot obtained\b|\bno (?:carrier |warehouse )?(?:record|evidence)\b|\bnot (?:been )?(?:received|found)\b", re.I),
    "not_retrieved": re.compile(r"\bnot retrieved\b|\bno relevant\b|\breturned nothing\b|\bempty result\b|\bretrieval\b", re.I),
    "inaccessible": re.compile(r"\binaccessible\b|\bpermissions?\b|\baccess\b", re.I),
    "unavailable": re.compile(r"\bunavailable\b|\bnot available\b|\bdid not (?:answer|respond|recover)\b|\bcould not (?:be )?(?:read|reached|provide)\b", re.I),
    "negative": re.compile(r"\bnone found\b|\bfound nothing\b|\bno (?:match|such|duplicate)\b|\bnot found\b|\bchecked\b", re.I),
    "not_assessed": re.compile(r"\bnot assessed\b|\bno assessment\b|\bwas not (?:assessed|performed)\b", re.I),
    "stale": re.compile(r"\bstale\b|\bout of date\b|\btoo old\b|\bolder than\b", re.I),
}
IDENTIFIER = re.compile(r"\b[A-Z][A-Z0-9]*(?:-[A-Z0-9][A-Za-z0-9.]*)+\b")


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


def _free_text_findings(kind: str, text: str, label: str, cited_text: str, pointers: List[str], packet: dict, file: str, loc: str) -> List[Finding]:
    """The named constraints of structural free-text validation, for one statement.

    Each constraint is a specific, mechanical test. None of them proves that the statement means what its packet means.
    """
    out: List[Finding] = []
    if not cited_text:
        return out
    lowered = cited_text.lower()
    if kind in FIGURE_CHECKED:
        for code in sorted({m.group(0) for m in CURRENCY.finditer(text)} - {m.group(0) for m in CURRENCY.finditer(cited_text)}):
            out.append(Finding("RESP002", "the currency %s does not appear in the cited packet items" % code, file, loc, DOC_EVIDENCE))
    if kind in STATUS_CHECKED:
        for name, pattern in STATUS_WORDS.items():
            if pattern.search(text) and not pattern.search(cited_text):
                out.append(Finding("RESP012", "the status word %r is not in the items this statement cites: rewording may not change a status" % name, file, loc, DOC_RESPONSE))
    for match in CERTAINTY.finditer(text):
        if match.group(0).lower() not in lowered:
            out.append(Finding("RESP011", "adds certainty (%r) that the cited items do not state" % match.group(0), file, loc, DOC_RESPONSE))
    if kind in IDENTIFIER_CHECKED:
        for ident in sorted(set(IDENTIFIER.findall(text))):
            if ident not in cited_text and ident not in label:
                out.append(Finding("RESP013", "names %s, which the cited packet items do not rest on: a statement may not attribute its content to another record" % ident, file, loc, DOC_RESPONSE))
    if kind == "conflict":
        if CLOSES_CONFLICT.search(text):
            out.append(Finding("RESP008", "wording closes a conflict that the packet keeps open", file, loc, DOC_RESPONSE))
        if not KEEPS_CONFLICT_OPEN.search(text):
            out.append(Finding("RESP010", "a conflict statement must say that the conflict is unresolved", file, loc, DOC_RESPONSE))
    elif kind == "gap":
        if DENIES_GAP.search(text):
            out.append(Finding("RESP008", "wording denies or closes a gap that the packet keeps open", file, loc, DOC_RESPONSE))
        for pointer in pointers:
            try:
                state = resolve_pointer(packet, pointer).get("state")
            except (KeyError, IndexError, ValueError, TypeError, AttributeError):
                continue
            pattern = STATE_WORDS.get(state)
            if pattern is not None and not pattern.search(text):
                out.append(Finding("RESP009", "the packet labels this gap %s, but the statement does not say so in words" % state, file, loc, DOC_RESPONSE))
    elif kind == "inference":
        if not KEEPS_INFERENCE_LIMITED.search(text):
            out.append(Finding("RESP010", "an inference must keep its limits: say that it is not verified, name its limits or hedge it", file, loc, DOC_RESPONSE))
    elif kind == "recommendation":
        if not KEEPS_RECOMMENDATION_OPEN.search(text):
            out.append(Finding("RESP010", "a recommendation must say that it is for review and not a decision", file, loc, DOC_RESPONSE))
    elif kind == "obligation":
        if CLOSES_OBLIGATION.search(text):
            out.append(Finding("RESP008", "wording closes an obligation that the packet keeps open", file, loc, DOC_RESPONSE))
    return out


def check_structural(model: Model, response: dict, path) -> List[Finding]:
    """STRUCTURAL FREE-TEXT VALIDATION: named constraints on any response. It does not prove that the prose is correct."""
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
        resolved: List[str] = []
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
            resolved.append(r)
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
        findings += _free_text_findings(kind, text, str(st.get("label", "")), " ".join(subtree), resolved, d, file, loc)
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


# ---------------------------------------------------------------------------------------------- canonical validation
def is_canonical(response: dict) -> bool:
    """A response that says a deterministic renderer wrote it is held to that renderer's output."""
    return str(response.get("produced_by", "")).startswith("template")


def meaning_changes(expected: str, actual: str) -> List[str]:
    """What a difference between two renderings does to the meaning: negation, status words, figures, certainty, open or closed."""
    changes: List[str] = []
    negations = (len(NEGATION.findall(expected)), len(NEGATION.findall(actual)))
    if negations[0] != negations[1]:
        changes.append("negation (%d, expected %d)" % (negations[1], negations[0]))
    said = lambda text: sorted(name for name, pattern in STATUS_WORDS.items() if pattern.search(text))  # noqa: E731
    if said(expected) != said(actual):
        changes.append("status words %s, expected %s" % (said(actual) or "none", said(expected) or "none"))
    if figures(expected) != figures(actual):
        changes.append("figures")
    if bool(KEEPS_CONFLICT_OPEN.search(expected)) != bool(KEEPS_CONFLICT_OPEN.search(actual)) or bool(CLOSES_CONFLICT.search(actual)):
        changes.append("open or resolved")
    if sorted(m.group(0).lower() for m in CERTAINTY.finditer(expected)) != sorted(m.group(0).lower() for m in CERTAINTY.finditer(actual)):
        changes.append("certainty")
    return changes


def _short(text: str, limit: int = 120) -> str:
    return text if len(text) <= limit else text[:limit - 3] + "..."


def check_canonical(model: Model, response: dict, packet: Instance, file: str) -> List[Finding]:
    """CANONICAL RESPONSE VALIDATION: the response must equal what the renderer writes from its packet.

    A statement that differs fails (RESP101). A difference that adds or removes a negation, changes a status word or a
    figure, or opens or closes a conflict is reported as a change of meaning (RESP102).
    """
    out: List[Finding] = []
    expected = render_response(model, packet, produced_by=str(response.get("produced_by", "template-fallback-1")),
                               status=str(response.get("status", "current")), withdrawn_reason=str(response.get("status_reason", "")))
    for key in ("response_id", "synthetic", "packet_reference", "as_of", "produced_by", "status", "status_reason"):
        if response.get(key) != expected.get(key):
            out.append(Finding("RESP101", "%s differs from the canonical rendering: expected %r, found %r" % (key, expected.get(key), response.get(key)), file, "/" + key, DOC_RESPONSE))
    by_key = {(s["kind"], s["label"]): s for s in expected["statements"]}
    seen = set()
    for i, st in enumerate(response.get("statements", [])):
        loc = "/statements/%d" % i
        key = (st.get("kind"), st.get("label"))
        canonical = by_key.get(key)
        if canonical is None or key in seen:
            out.append(Finding("RESP101", "the %s statement %r is not in the canonical rendering of this packet" % key, file, loc, DOC_RESPONSE))
            continue
        seen.add(key)
        if st.get("text") != canonical["text"]:
            changes = meaning_changes(canonical["text"], str(st.get("text", "")))
            code = "RESP102" if changes else "RESP101"
            lead = "the statement changes what the packet requires (%s)" % "; ".join(changes) if changes else "the statement differs from the canonical rendering"
            out.append(Finding(code, "%s. Canonical: %s | Found: %s" % (lead, _short(canonical["text"]), _short(str(st.get("text", "")))), file, loc + "/text", DOC_RESPONSE))
        if st.get("refs") != canonical["refs"]:
            out.append(Finding("RESP101", "the citations differ from the canonical rendering: expected %s, found %s" % (canonical["refs"], st.get("refs")), file, loc + "/refs", DOC_RESPONSE))
    for key in by_key:
        if key not in seen:
            out.append(Finding("RESP101", "the canonical rendering has a %s statement %r that the response omits" % key, file, "/statements", DOC_RESPONSE))
    order = [(s.get("kind"), s.get("label")) for s in response.get("statements", []) if (s.get("kind"), s.get("label")) in by_key]
    if not out and order != [(s["kind"], s["label"]) for s in expected["statements"]]:
        out.append(Finding("RESP101", "the statements are in a different order from the canonical rendering", file, "/statements", DOC_RESPONSE))
    return out


def check_response(model: Model, response: dict, path) -> List[Finding]:
    """Validate a response: structural constraints for every response, and the canonical comparison when it claims to be rendered."""
    findings = check_structural(model, response, path)
    if is_canonical(response):
        ref = response.get("packet_reference", {})
        packet = model.get("C04", ref.get("id"), ref.get("version"))
        if packet is not None:
            findings += check_canonical(model, response, packet, rel(path))
    return findings
