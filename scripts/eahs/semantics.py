"""Deterministic semantic checks for the synthetic scenario.

JSON Schema validates shape. These checks validate what shape cannot: that references resolve to the exact
version they name, that lineage is acyclic and independent of its own derivatives, that corrections invalidate
what depended on them, that each missingness label is justified, that approvals cease to be current when their
basis is superseded, and that a receipt agrees with what a gateway would have decided.

Passing proves the example set is internally coherent. It proves nothing about any real system.
"""
from __future__ import annotations

import math
import re
from collections import Counter
from decimal import Decimal, InvalidOperation
from typing import Dict, List, Optional, Set, Tuple

from .disclosure import Decision, Viewer, binding_problems, differences, gap_entry, may_know, retrieval_entry
from .findings import Finding, doc_for_contract
from .gateway import GATE_CODES, age_hours, availability_problem, evaluate_commit, freshness_max_age, is_current_at, ledger_from_receipts, parse_time, ts
from .model import Instance, Model, claims_of, iter_refs, payload_object_of, resolve_pointer, version_number as _vn

DOC_EVIDENCE = "architecture/evidence-semantics.md"
DOC_LINEAGE = "architecture/lineage-selection-disclosure.md"
DOC_ACTION = "architecture/action-and-degradation.md"
INACTIVE_PACKET_STATES = {"invalidated", "superseded"}


def _f(code: str, message: str, inst: Instance, location: str = "", doc: str = "") -> Finding:
    return Finding(code, message, inst.file, location, doc or doc_for_contract(inst.contract))


# --------------------------------------------------------------------------- references

def check_references(model: Model) -> List[Finding]:
    out: List[Finding] = []
    units = _retrieval_units(model)
    for inst in model.instances.values():
        for ref in iter_refs(inst.data):
            if ref.kind in ("evidence", "support"):
                target = model.get("C02", ref.record_id, ref.version)
                if target is None:
                    out.append(_f("REF001", "no C02 record %s %s: references name an exact version, never 'latest'" % (ref.record_id, ref.version or "(no version stated)"), inst, ref.path, DOC_EVIDENCE))
                    continue
                if ref.kind == "support":
                    out.extend(_check_support(inst, ref, target))
            elif ref.kind == "contract":
                if model.get(ref.contract, ref.record_id, ref.version) is None:
                    out.append(_f("REF004", "no %s %s %s" % (ref.contract, ref.record_id, ref.version), inst, ref.path))
            elif ref.kind == "external":
                named = "%s@%s" % (ref.record_id, ref.version)
                if named not in model.registry.external_records and model.get("C02", ref.record_id, ref.version) is None:
                    out.append(_f("REF005", "%s %s is neither a C02 record nor an entry in examples/registry.json external_records" % (ref.record_id, ref.version), inst, ref.path))
            elif ref.kind == "retrieval":
                if (ref.record_id, ref.version) not in units:
                    out.append(_f("REF006", "no completed retrieval unit %s %s in any C03 selection" % (ref.record_id, ref.version), inst, ref.path, "contracts/c03-selection.md"))
            elif ref.kind == "policy":
                if model.registry.policy(ref.record_id, ref.version) is None:
                    out.append(_f("REF007", "policy %s %s is not defined in examples/registry.json" % (ref.record_id, ref.version), inst, ref.path))
    return out


def _check_support(inst: Instance, ref, target: Instance) -> List[Finding]:
    out: List[Finding] = []
    body, t = ref.body, target.data
    if body.get("evidence_kind") != t["identity_schema"]["kind"]:
        out.append(_f("REF002", "reference says kind %s but %s %s is a %s" % (body.get("evidence_kind"), target.id, target.version, t["identity_schema"]["kind"]), inst, ref.path, DOC_EVIDENCE))
    if body.get("original_locator") != t["original_source"]:
        out.append(_f("REF002", "original_locator does not match the original source recorded in %s %s" % (target.id, target.version), inst, ref.path, DOC_EVIDENCE))
    if body.get("scope") != t["scope"]:
        out.append(_f("REF002", "scope does not match the scope recorded in %s %s" % (target.id, target.version), inst, ref.path, DOC_EVIDENCE))
    if body["reference_type"] == "claim_reference":
        if body.get("claim_id") not in claims_of(t):
            out.append(_f("REF002", "claim %r is not a claim of %s %s" % (body.get("claim_id"), target.id, target.version), inst, ref.path, DOC_EVIDENCE))
    else:
        payload = payload_object_of(t)
        if payload is None:
            out.append(_f("REF003", "%s %s has no typed payload; a payload_reference needs one" % (target.id, target.version), inst, ref.path, DOC_EVIDENCE))
        else:
            try:
                resolve_pointer(payload, body["payload_location"])
            except (KeyError, IndexError, ValueError, TypeError):
                out.append(_f("REF003", "payload pointer %s does not resolve in %s %s" % (body["payload_location"], target.id, target.version), inst, ref.path, DOC_EVIDENCE))
    return out


def _retrieval_units(model: Model) -> Set[Tuple[str, str]]:
    units: Set[Tuple[str, str]] = set()
    for sel in model.of("C03"):
        for unit in sel.data["retrieval"]:
            if unit["status"] == "completed":
                units.add((unit["retrieval_unit_id"], sel.version))
    return units


# --------------------------------------------------------------------------- lineage

def _parents(model: Model, rec: Instance) -> List[Instance]:
    out = []
    for p in rec.data["lineage"]["parent_references"]:
        parent = model.get("C02", p["record_id"], p["version"])
        if parent is not None:
            out.append(parent)
    return out


def ancestors(model: Model, rec: Instance) -> Dict[Tuple[str, str, str], Instance]:
    seen: Dict[Tuple[str, str, str], Instance] = {}
    stack = list(_parents(model, rec))
    while stack:
        cur = stack.pop()
        if cur.key in seen:
            continue
        seen[cur.key] = cur
        stack.extend(_parents(model, cur))
    return seen


def roots(model: Model, rec: Instance) -> Set[Tuple[str, str]]:
    """The records a derivation ultimately rests on (itself if it has no parents)."""
    anc = ancestors(model, rec)
    if not anc:
        return {(rec.id, rec.version)}
    return {(a.id, a.version) for a in anc.values() if not a.data["lineage"]["parent_references"]}


def check_lineage(model: Model) -> List[Finding]:
    out: List[Finding] = []
    allowed = set(model.registry.relationship_types)
    for rec in model.of("C02"):
        for i, p in enumerate(rec.data["lineage"]["parent_references"]):
            if (p["record_id"], p["version"]) == (rec.id, rec.version):
                out.append(_f("LIN004", "a record cannot be its own parent", rec, "/lineage/parent_references/%d" % i, DOC_LINEAGE))
        # cycle: the record must not be among its own ancestors
        if (("C02", rec.id, rec.version)) in ancestors(model, rec):
            out.append(_f("LIN001", "derivation ancestry must be acyclic, but %s %s is its own ancestor" % (rec.id, rec.version), rec, "/lineage", DOC_LINEAGE))
        elif rec.data["identity_schema"]["kind"] == "model_inference":
            out.extend(_check_inference_figures(model, rec))
        for i, rel in enumerate(rec.data["lineage"]["typed_relationships"]):
            if allowed and rel["relationship_type"] not in allowed:
                out.append(_f("LIN002", "relationship type %r is not one of %s" % (rel["relationship_type"], sorted(allowed)), rec, "/lineage/typed_relationships/%d" % i, DOC_LINEAGE))
            if rel["relationship_type"] == "supersession":
                older = model.get("C02", rel["to"]["record_id"], rel["to"]["version"])
                if older is not None and (older.data["lifecycle"]["state"] != "superseded" or older.data["lifecycle"].get("replacement_reference") != {"record_id": rec.id, "version": rec.version}):
                    out.append(_f("LIN003", "supersession of %s %s requires that version to be marked superseded with this record as its replacement" % (older.id, older.version), rec, "/lineage/typed_relationships/%d" % i, DOC_LINEAGE))
    return out


def _check_inference_figures(model: Model, rec: Instance) -> List[Finding]:
    """A model inference reaches no further than the records it declares it rests on: it states no figure that its ancestry does not hold.

    A summary of one goods receipt that says "40 units are missing" has compared the receipt with something it does not rest on,
    and the figure it gives is not in its sources. Each figure it states must be accounted for by a figure in the content of
    its ancestors, once for each time it is stated. This is a necessary condition on structured values: it does not show that a
    summary is faithful to its sources, and it reads no prose for meaning. A model inference that rests on nothing holds no figure.

    The text of the inference's own claims is what is read: an inference whose content is a typed payload is not. Each claim is held to the figures
    of the ancestry on its own, so a figure that the ancestry holds once may be stated once in each claim and is not used up across the claims.
    """
    out: List[Finding] = []
    held: Counter = Counter()
    for ancestor in ancestors(model, rec).values():
        held.update(_content_values(ancestor.data.get("content", {}))[0])
    sources = ", ".join("%s %s" % (a.id, a.version) for a in sorted(ancestors(model, rec).values(), key=lambda a: (a.id, a.version))) or "no record"
    content = _object_of(rec.data.get("content"))
    claims = content.get("claims") if content.get("content_type") == "claims" and isinstance(content.get("claims"), list) else []
    for i, claim in enumerate(claims):
        for number in sorted(_numbers_in(str(_object_of(claim).get("text", ""))) - held):
            out.append(_f("LIN005", "this model inference states the figure %s, which none of the records it rests on holds (%s): a derivation reaches no further than its ancestry" % (_show_number(number), sources), rec, "/content/claims/%d/text" % i, DOC_LINEAGE))
    return out


# --------------------------------------------------------------------------- kinds and methods

def check_kinds(model: Model) -> List[Finding]:
    out: List[Finding] = []
    for rec in model.of("C02"):
        d = rec.data
        kind, pid = d["identity_schema"]["kind"], d["producer_admission"]["producer_id"]
        producer = model.registry.producers.get(pid)
        if producer is None:
            out.append(_f("KIND000", "producer %s is not registered in examples/registry.json" % pid, rec, "/producer_admission/producer_id", DOC_EVIDENCE))
        elif kind not in producer["permitted_kinds"]:
            out.append(_f("KIND001", "producer %s may not submit kind %s (permitted: %s): a producer cannot promote its output to another kind" % (pid, kind, ", ".join(producer["permitted_kinds"])), rec, "/identity_schema/kind", DOC_EVIDENCE))
        method = d["method"]
        if kind == "deterministic_finding" and method["rule_version"]["state"] != "known":
            out.append(_f("KIND004", "a deterministic finding must declare the rule version it applied", rec, "/method/rule_version", DOC_EVIDENCE))
        if kind == "model_inference" and (method["model_version"]["state"] != "known" or method["prompt_version"]["state"] != "known"):
            out.append(_f("KIND004", "a model inference must declare its model and prompt versions", rec, "/method", DOC_EVIDENCE))
    for pkt in model.of("C04"):
        for i, claim in enumerate(pkt.data["supported_claims_references"]):
            for j, ref in enumerate(claim["supporting_references"]):
                if ref["evidence_kind"] == "model_inference":
                    out.append(_f("KIND002", "a model inference cannot support a 'supported claim'; list it under labeled_inferences", pkt, "/supported_claims_references/%d/supporting_references/%d" % (i, j), DOC_EVIDENCE))
    return out


# --------------------------------------------------------------------------- lifecycle and invalidation

def packet_active(pkt: Instance) -> bool:
    return pkt.data["review_version_history"]["state"] not in INACTIVE_PACKET_STATES


def check_lifecycle(model: Model) -> List[Finding]:
    out: List[Finding] = []
    for rec in model.of("C02"):
        lc = rec.data["lifecycle"]
        if lc["state"] == "superseded":
            repl = lc.get("replacement_reference")
            newer = model.get("C02", repl["record_id"], repl["version"]) if repl else None
            if newer is None or newer.id != rec.id or _vn(newer.version) <= _vn(rec.version):
                out.append(_f("LIFE001", "a superseded record must name a later version of itself as its replacement", rec, "/lifecycle/replacement_reference", DOC_LINEAGE))
        if lc["state"] == "current":
            for anc in ancestors(model, rec).values():
                if anc.data["lifecycle"]["state"] != "current":
                    out.append(_f("LIFE002", "still current, but derived from %s %s which is %s: a correction must invalidate its derivatives" % (anc.id, anc.version, anc.data["lifecycle"]["state"]), rec, "/lifecycle/state", DOC_LINEAGE))
                    break
    successors: Dict[Tuple[str, str], List[Instance]] = {}
    for pkt in model.of("C04"):
        for prior in pkt.data["review_version_history"]["prior_version_references"]:
            successors.setdefault((prior["id"], prior["version"]), []).append(pkt)
    for pkt in model.of("C04"):
        d = pkt.data
        if packet_active(pkt):
            for ref in _packet_evidence_refs(d):
                rec = model.get("C02", ref["record_id"], ref["version"])
                if rec is not None and rec.data["lifecycle"]["state"] != "current":
                    out.append(_f("LIFE003", "packet is still active but cites %s %s which is %s" % (rec.id, rec.version, rec.data["lifecycle"]["state"]), pkt, "/review_version_history/state", DOC_LINEAGE))
                    break
        if (pkt.id, pkt.version) in successors and packet_active(pkt):
            out.append(_f("LIFE004", "a newer packet version exists, so this version must be invalidated or superseded", pkt, "/review_version_history/state", DOC_LINEAGE))
    latest_grants: Dict[str, Instance] = {}
    for grant in model.of("C06"):
        cur = latest_grants.get(grant.id)
        if cur is None or _vn(grant.version) > _vn(cur.version):
            latest_grants[grant.id] = grant
    for grant in latest_grants.values():
        binding = grant.data["scope_binding"]["binding"]
        if binding["binding_type"] != "exact_proposal":
            continue
        ref = binding["proposal_reference"]
        prop = model.get("C05", ref["id"], ref["version"])
        if prop is None:
            continue
        pref = prop.data["identity_binding"]["packet_reference"]
        pkt = model.get("C04", pref["id"], pref["version"])
        if pkt is not None and not packet_active(pkt) and grant.data["limits_lifecycle"]["revocation"]["state"] != "revoked":
            out.append(_f("LIFE005", "approval relies on packet %s %s which is no longer active, so it must be revoked: a pending approval ceases to be current" % (pkt.id, pkt.version), grant, "/limits_lifecycle/revocation/state", DOC_ACTION))
    return out


def _packet_evidence_refs(d: dict) -> List[dict]:
    refs: List[dict] = []
    for c in d["supported_claims_references"]:
        refs.extend(c["supporting_references"])
    for i in d["labeled_inferences"]:
        refs.extend(i["supporting_references"])
    return refs


# --------------------------------------------------------------------------- missingness

def check_missingness(model: Model) -> List[Finding]:
    out: List[Finding] = []
    for sel in model.of("C03"):
        base = sel.data
        for i, m in enumerate(base["conflicts_gaps"]["missingness"]):
            out.extend(_check_gap(model, sel, m, "/conflicts_gaps/missingness/%d" % i, base["identity_scope"]["as_of"], base))
    for pkt in model.of("C04"):
        ref = pkt.data["decision_context_as_of"]["selection_reference"]
        sel = model.get("C03", ref["id"], ref["version"])
        if sel is None:
            continue
        gaps = pkt.data["coverage_omissions_gaps"]["missingness"]
        for i, m in enumerate(gaps):
            out.extend(_check_gap(model, pkt, m, "/coverage_omissions_gaps/missingness/%d" % i, sel.data["identity_scope"]["as_of"], sel.data))
        for i, m in enumerate(sel.data["conflicts_gaps"]["missingness"]):
            if m not in gaps:
                out.append(_f("MISS005", "the packet leaves out a gap of its selection (%s, entry %d): every gap must stay visible in the packet" % (m["state"], i), pkt, "/coverage_omissions_gaps/missingness", DOC_LINEAGE))
        for c in sel.data["conflicts_gaps"]["conflicts"]:
            if c not in pkt.data["conflicts_uncertainty"]["conflicts"]:
                out.append(_f("MISS005", "the packet leaves out conflict %s of its selection" % c["conflict_id"], pkt, "/conflicts_uncertainty/conflicts", DOC_LINEAGE))
    return out


def _check_gap(model: Model, inst: Instance, m: dict, loc: str, as_of: str, selection: dict) -> List[Finding]:
    out: List[Finding] = []
    state = m["state"]
    if state == "not_retrieved":
        unit = next((u for u in selection["retrieval"] if u["retrieval_unit_id"] == m["retrieval_reference"]["record_id"]), None)
        if unit is None or unit["status"] != "completed":
            out.append(_f("MISS001", "not_retrieved needs a COMPLETED retrieval unit in the selection: an interrupted or unperformed retrieval is not an empty result", inst, loc, DOC_LINEAGE))
        elif unit["completed_at"].get("value") != m["completed_at"]:
            out.append(_f("MISS001", "completed_at does not match the retrieval unit's completion time", inst, loc, DOC_LINEAGE))
    elif state == "negative":
        obs = m["observation_reference"]
        rec = model.get("C02", obs["record_id"], obs["version"])
        if m["coverage"]["status"] != "complete":
            out.append(_f("MISS002", "a negative needs complete coverage of its declared scope; otherwise use not_retrieved or missing", inst, loc, DOC_LINEAGE))
        if rec is not None and rec.data["scope"] != m["scope"]:
            out.append(_f("MISS002", "the negative's scope differs from the scope of the observation it relies on", inst, loc, DOC_LINEAGE))
    elif state == "stale":
        rec = model.get("C02", m["available_record"]["record_id"], m["available_record"]["version"])
        if rec is not None:
            try:
                limit = freshness_max_age(model, rec.data)
            except ValueError:
                limit = None   # a limit that cannot be read cannot show that the label is wrong
            age = age_hours(rec.data, ts(m["freshness"]["evaluated_at"]))
            if limit is not None and age is not None and age <= limit:
                out.append(_f("MISS003", "labeled stale, but the record is %.1f h old and policy allows %.0f h" % (age, limit), inst, loc, DOC_LINEAGE))
    elif state == "unavailable":
        rec = model.get("C02", m["dependency_failure_reference"]["record_id"], m["dependency_failure_reference"]["version"])
        if rec is not None and rec.data["identity_schema"]["kind"] != "source_record_assertion":
            out.append(_f("MISS004", "a dependency failure must point to an observation of the failure (a source record assertion)", inst, loc, DOC_LINEAGE))
    return out


# --------------------------------------------------------------------------- packets

def check_packets(model: Model) -> List[Finding]:
    out: List[Finding] = []
    for pkt in model.of("C04"):
        d = pkt.data
        ctx_ref, sel_ref = d["decision_context_as_of"]["context_reference"], d["decision_context_as_of"]["selection_reference"]
        sel = model.get("C03", sel_ref["id"], sel_ref["version"])
        if sel is not None:
            if sel.data["identity_scope"]["context_reference"] != ctx_ref:
                out.append(_f("PKT002", "the packet and its selection must bind the same context", pkt, "/decision_context_as_of/context_reference"))
            if sel.data["identity_scope"]["as_of"] != d["decision_context_as_of"]["as_of"]:
                out.append(_f("PKT002", "the packet and its selection must share one as-of time", pkt, "/decision_context_as_of/as_of"))
        if d["coverage_omissions_gaps"]["coverage_reference"]["selection_reference"] != sel_ref:
            out.append(_f("PKT003", "coverage must point at the packet's own selection", pkt, "/coverage_omissions_gaps/coverage_reference"))
        for i, claim in enumerate(d["supported_claims_references"]):
            out.extend(_check_claim_support(model, pkt, i, claim))
        for i, prop in enumerate(d["action_proposals"]):
            pr = model.get("C05", prop["proposal_reference"]["id"], prop["proposal_reference"]["version"])
            if pr is not None and pr.data["identity_binding"]["packet_reference"] != {"contract_id": "C04", "id": pkt.id, "version": pkt.version}:
                out.append(_f("PKT004", "the listed proposal is bound to a different packet", pkt, "/action_proposals/%d" % i, "contracts/c05-action-proposal.md"))
        out.extend(_check_corroboration(model, pkt))
    return out


#: Numbers a claim states: decimals that are not part of an identifier, a date or a time (no letter, hyphen, colon or slash touches
#: them), with a leading minus when they have one, so that -100 is not 100.
_NUMBER = re.compile(r"(?<![\w.,/:-])-?\d[\d,]*(?:\.\d+)?(?![\w:/-]|\.\d)")
#: The status vocabulary a payload can state and a claim can restate. Only these words are compared: no other prose is interpreted.
_STATUS = re.compile(r"\b(pass|fail)(?:ed|es|s|ing|ure)?\b", re.IGNORECASE)
_WORD = re.compile(r"[A-Za-z][A-Za-z0-9_]*")
#: Words that may stand between a field's name and its figure ("variance of 40.0%", "tolerance is 2%").
_BETWEEN = frozenset("of is was are were at to be equal equals about only just exactly than".split())
#: Words that may stand between a figure and the name of the field that follows it ("60 units received", "40.0 percent variance").
_UNITS = frozenset("unit units piece pieces item items percent pct eur euro euros usd".split())
_BOUNDARY = re.compile(r"[.;!?](?=\s|$)")
_TOKEN = re.compile(r"[A-Za-z][A-Za-z0-9_]*|\d+|[^\sA-Za-z0-9_]")


def _decimal(value) -> Optional[Decimal]:
    """A number exactly as written: 40.000000000000001 is not 40.0. Decimal compares by value, so 40.0 and 40 are the same number.

    A float of the payload is read by its shortest text (0.1 is 0.1, not 0.1000000000000000055...), as JSON wrote it. The reader
    refuses a number that a double cannot hold digit for digit (loads_strict), so no loaded float has been rounded on the way in.
    """
    try:
        if isinstance(value, str):
            number = Decimal(value.replace(",", ""))
        elif isinstance(value, float):
            number = Decimal(repr(value)) if math.isfinite(value) else None
        else:
            number = Decimal(value)
    except (InvalidOperation, ValueError, TypeError):
        return None
    return number if number is not None and number.is_finite() else None


def _show_number(value: Decimal) -> str:
    return "{:f}".format(value.normalize() + 0)


def _numbers_in(text: str) -> Counter:
    """Every number a text states, exactly as written, once for each time it states it."""
    found: Counter = Counter()
    for token in _NUMBER.findall(text.replace("\u2212", "-")):
        number = _decimal(token)
        if number is not None:
            found[number] += 1
    return found


def _statuses_in(text: str) -> Set[str]:
    return {m.group(1).lower() for m in _STATUS.finditer(text)}


def _content_values(node) -> Tuple[Counter, Set[str]]:
    """The numbers and status words that structured content states: each numeric leaf is one number, and string leaves are read for both."""
    numbers: Counter = Counter()
    statuses: Set[str] = set()
    stack = [node]
    while stack:
        item = stack.pop()
        if isinstance(item, bool) or item is None:
            continue
        if isinstance(item, (int, float)):
            number = _decimal(item)
            if number is not None:
                numbers[number] += 1
        elif isinstance(item, str):
            numbers.update(_numbers_in(item))
            statuses |= _statuses_in(item)
        elif isinstance(item, dict):
            stack.extend(item.values())
        elif isinstance(item, list):
            stack.extend(item)
    return numbers, statuses


def _stem(word: str) -> str:
    word = word.lower()
    return re.sub(r"(ing|ed|es|e|s|d)$", "", word) if len(word) > 4 else word


def _named_numbers(node, name: str = "") -> List[Tuple[str, Decimal]]:
    """(the name of the field, the number) for every number a payload holds; a number in a list belongs to the field that holds the list."""
    if isinstance(node, bool) or node is None:
        return []
    if isinstance(node, (int, float)):
        number = _decimal(node)
        return [] if number is None else [(name, number)]
    if isinstance(node, str):
        return [(name, n) for n in _numbers_in(node)]
    if isinstance(node, dict):
        return [pair for key, value in node.items() for pair in _named_numbers(value, str(key))]
    if isinstance(node, list):
        return [pair for value in node for pair in _named_numbers(value, name)]
    return []


def _name_words(name: str) -> List[str]:
    """The words of a field name, in order: quantity_invoiced and quantityInvoiced are "quantity", "invoiced"."""
    return re.findall(r"[A-Za-z]{3,}", re.sub(r"(?<=[a-z])(?=[A-Z])", " ", name))


def _word_before(clause: str) -> Optional[str]:
    """The word that names the figure which follows `clause`: the last word, if only white space, a colon, an equals sign, a quotation mark and filler words lie after it.

    A comma, a bracket or another figure between the word and the figure means that the word belongs to something else:
    in "60 units invoiced, 100 units received" the word "invoiced" does not name 100.
    """
    for token in reversed(_TOKEN.findall(clause[-64:])):
        if token in (":", "=", '"', "'", "`") or token.lower() in _BETWEEN:
            continue
        return token if token[0].isalpha() else None
    return None


def _word_after(rest: str) -> Optional[str]:
    """The word that names the figure which precedes `rest`: the first word that is not a unit or a filler word ("60 units received" and "60 units were received" are about "received")."""
    for token in _TOKEN.findall(rest[:64]):
        if token.lower() in _UNITS or token.lower() in _BETWEEN or token == "%":
            continue
        return token if token[0].isalpha() else None
    return None


def _named_fields(word: Optional[str], by_word: Dict[str, List[Tuple[str, Decimal]]]) -> List[Tuple[str, Decimal]]:
    """The payload fields that `word` names: those that carry it. A field's own name written out ("quantity_invoiced", "quantityInvoiced") names
    the fields that carry all of its words, so that "variance_pct" is the variance and not every field that ends in "pct". A name with a word that no
    field carries names none of them: "quantity_received" is not "quantity_invoiced" because they share "quantity"."""
    fields: Optional[List[Tuple[str, Decimal]]] = None
    for part in _name_words(word or ""):
        known = by_word.get(_stem(part))
        if known is None:
            return []
        fields = list(known) if fields is None else [pair for pair in fields if pair in known]
    return fields or []


def _index_fields(payloads: List[Tuple[object, str]]) -> Dict[str, List[Tuple[str, Decimal]]]:
    """Every numeric field of the payloads, filed under each word of its name (quantity_invoiced is filed under "quantity" and "invoiced")."""
    by_word: Dict[str, List[Tuple[str, Decimal]]] = {}
    for payload, field_name in payloads:
        for name, value in _named_numbers(payload, field_name):
            for word in _name_words(name):
                by_word.setdefault(_stem(word), []).append((name, value))
    return by_word


def _figure_words(text: str):
    """(figure, the word in front of it that could name it, the word after it that could name it) for every figure in a text."""
    text = text.replace("\u2212", "-")
    for match in _NUMBER.finditer(text):
        figure = _decimal(match.group(0))
        if figure is not None:
            yield (figure, _word_before(_BOUNDARY.split(text[max(0, match.start() - 96):match.start()])[-1]),
                   _word_after(_BOUNDARY.split(text[match.end():match.end() + 96])[0]))


def _label_findings(text: str, payloads: List[Tuple[object, str]], skip: Set[Decimal]) -> List[Tuple[Decimal, str, List[str]]]:
    """Figures in `text` that sit beside the name of a payload field and are not that field's value: (the figure, the word, the fields' values).

    "invoiced 60" is wrong when the payload's quantity_invoiced is 100, even though 60 is in the payload: the figure is tied to the
    field by the word in front of it, or, when no field's name is in front of it, by the word after it ("60 units invoiced"). A word
    names a figure only when nothing but white space, a colon, an equals sign, filler words or units lies between them, so that
    swapping "invoiced 100 units, received 60 units" into "60 units invoiced, 100 units received" is found. A field's name written
    out ("quantity_invoiced 60") names it by its own words. A figure that sits beside no field's name is not tied to anything and
    is not judged here, and a figure in `skip` has been reported already.

    `payloads` are the payloads the claim cites, each with the name of the field its pointer ends at (for a pointer to one value, such
    as /value/quantity_invoiced, that name is the field's). The fields of all of them are taken together: a figure beside a name is
    right if any cited payload holds it for a field of that name, because the prose cannot say which of them it is about.
    """
    by_word = _index_fields(payloads)
    found: List[Tuple[Decimal, str, List[str]]] = []
    for figure, before, after in _figure_words(text):
        word, fields = before, _named_fields(before, by_word)
        if not fields:
            word, fields = after, _named_fields(after, by_word)
        if fields and figure not in skip and figure not in {value for _, value in fields}:
            found.append((figure, word, ["%s is %s" % (name, _show_number(value)) for name, value in dict.fromkeys(fields)]))
    return found


def _uncited_findings(text: str, payloads: List[Tuple[object, str]], vocabulary: List[object], skip: Set[Decimal]) -> List[Tuple[Decimal, str, List[str]]]:
    """Figures in `text` that sit beside the name of a field of the cited records' payloads that the claim does not cite: (the figure, the word, the names).

    A claim that cites one value (/value/quantity_invoiced) holds that value and no other. "quantity_received 100" puts a figure beside a field the
    claim does not cite, whatever the figure is (100 is in what it does cite, as the quantity invoiced), so the claim attributes to that field a value
    that nothing it cites gives it. A name that is a field of no payload is not judged, and a figure in `skip` has been reported already.
    """
    cited, known = _index_fields(payloads), _index_fields([(payload, "") for payload in vocabulary])
    found: List[Tuple[Decimal, str, List[str]]] = []
    for figure, before, after in _figure_words(text):
        if _named_fields(before, cited) or _named_fields(after, cited):
            continue   # held against what the claim cites, by _label_findings
        for word in (before, after):
            outside = _named_fields(word, known)
            if outside:
                if figure not in skip:
                    found.append((figure, word, sorted({name for name, _ in outside})))
                break
    return found


def _field_of(pointer) -> str:
    """The name of the field a JSON pointer ends at ("/value/quantity_invoiced" is quantity_invoiced; "/value/lines/0" is lines), or "" when it ends at the payload itself."""
    for step in reversed(str(pointer).split("/")):
        if step and not step.isdigit():
            return step.replace("~1", "/").replace("~0", "~")
    return ""


def _check_claim_support(model: Model, pkt: Instance, index: int, claim: dict) -> List[Finding]:
    """Hold a supported claim to every reference that supports it, not only to a lone claim_reference.

    A claim whose references are all claim references must say exactly what they say, in the order cited (for one
    reference, exactly what that claim says). A claim that rests on a payload, alone or beside claim references, says what
    the payload holds: after the cited claims' own words are taken out, what is left states every status (pass or fail) of each
    payload it cites and at least one of its figures, states no status or figure that the payloads do not hold (once for each
    time it is stated, so a claim cannot reuse one figure to cover two), and puts no figure next to the name of a payload
    field that is not that field's value (swapping "invoiced 100, received 60" is found, and so is "60 units invoiced, 100 units
    received"). Figures are compared exactly as written, not as floats. A minus sign is part of a figure. The fields of every payload
    the claim cites are taken together, and a pointer to one value (/value/quantity_invoiced) keeps that value's name, so a figure
    beside a name is held to the value of that name in any of them.
    These are structured values, compared exactly. They are necessary conditions: a claim that passes them can still say
    something its sources do not support. Nothing here reads prose for meaning, and the schema's free-text claim cannot be made
    to say more without a structured assertion field, which v1.0.2 does not add.

    A reference that does not resolve is reported by REF001-REF003; the claim is still compared with the references that do.
    """
    out: List[Finding] = []
    loc = "/supported_claims_references/%d" % index
    quoted: List[Tuple[str, str]] = []   # (what a referenced claim says, its name)
    payloads: List[Tuple[object, str, str]] = []   # (what the pointer leads to, its name for a message, the field it ends at)
    records: List[object] = []   # the whole payload of each cited record: which fields exist, whether or not the claim cites them
    unresolved = False
    for ref in claim["supporting_references"]:
        rec = model.get("C02", ref["record_id"], ref["version"])
        if rec is None:
            unresolved = True
            continue
        if ref["reference_type"] == "claim_reference":
            source = claims_of(rec.data).get(ref.get("claim_id"))
            if source is None:
                unresolved = True
                continue
            quoted.append((source["text"], "%s %s claim %s" % (rec.id, rec.version, ref.get("claim_id"))))
        else:
            payload = payload_object_of(rec.data)
            if payload is None:
                unresolved = True
                continue
            try:
                payloads.append((resolve_pointer(payload, ref.get("payload_location", "")), "%s %s payload %s" % (rec.id, rec.version, ref.get("payload_location")), _field_of(ref.get("payload_location", ""))))
                records.append(payload)
            except (KeyError, IndexError, ValueError, TypeError):
                unresolved = True
    text = claim["text"]
    texts = [t for t, _ in quoted]
    if not payloads:
        if texts and not unresolved and text != " ".join(texts):
            cited = ", ".join(name for _, name in quoted)
            how = "exactly what they say together, in the order cited" if len(texts) > 1 else "what its record says"
            out.append(_f("PKT001", "a supported claim must say %s; the text differs from %s" % (how, cited), pkt, loc + "/text", DOC_EVIDENCE))
        return out
    remainder = text
    for said, name in quoted:
        if said in remainder:
            remainder = remainder.replace(said, " ", 1)
        else:
            out.append(_f("PKT001", "a claim that cites %s must say what it says; the text does not contain it" % name, pkt, loc + "/text", DOC_EVIDENCE))
    stated_statuses, stated_numbers = _statuses_in(remainder), _numbers_in(remainder)
    supported_numbers: Counter = Counter()
    supported_statuses: Set[str] = set()
    for payload, _, _field in payloads:
        numbers, statuses = _content_values(payload)
        supported_numbers.update(numbers)
        supported_statuses |= statuses
    wrong_statuses = stated_statuses - supported_statuses
    unaccounted = stated_numbers - supported_numbers
    cited = ", ".join(name for _, name, _field in payloads)
    for status in sorted(wrong_statuses):
        out.append(_f("PKT005", "the claim states %r, which what it cites does not hold (%s)" % (status, cited), pkt, loc + "/text", DOC_EVIDENCE))
    for number in sorted(unaccounted):
        out.append(_f("PKT005", "the claim states the figure %s%s, which what it cites does not account for (%s)" % (_show_number(number), " more than once" if unaccounted[number] > 1 else "", cited), pkt, loc + "/text", DOC_EVIDENCE))
    for payload, name, _field in payloads:
        numbers, statuses = _content_values(payload)
        if not wrong_statuses:
            for status in sorted(statuses - stated_statuses):
                out.append(_f("PKT005", "the claim does not state %r, which %s holds: a claim that rests on a payload says what it holds" % (status, name), pkt, loc + "/text", DOC_EVIDENCE))
        if numbers and not set(numbers) & set(stated_numbers):
            out.append(_f("PKT005", "the claim states none of the figures that %s holds (%s)" % (name, ", ".join(_show_number(n) for n in sorted(numbers))), pkt, loc + "/text", DOC_EVIDENCE))
    cited_leaves = [(payload, field_name) for payload, _, field_name in payloads]
    for figure, word, fields in _label_findings(remainder, cited_leaves, set(unaccounted)):
        out.append(_f("PKT005", "the claim puts the figure %s next to %r, but what it cites (%s) holds %s for it" % (_show_number(figure), word, cited, " and ".join(fields)), pkt, loc + "/text", DOC_EVIDENCE))
    for figure, word, names in _uncited_findings(remainder, cited_leaves, records, set(unaccounted)):
        out.append(_f("PKT005", "the claim puts the figure %s next to %r, which is %s of the record, but what the claim cites (%s) does not hold it: a claim that cites one value holds that value and no other" % (
            _show_number(figure), word, "the field " + names[0] if len(names) == 1 else "the fields " + ", ".join(names), cited), pkt, loc + "/text", DOC_EVIDENCE))
    return out


def _check_corroboration(model: Model, pkt: Instance) -> List[Finding]:
    """Agreement between derivations that share a root is not independent corroboration."""
    out: List[Finding] = []
    d = pkt.data

    def root_set(refs: List[dict]) -> Set[Tuple[str, str]]:
        found: Set[Tuple[str, str]] = set()
        for r in refs:
            rec = model.get("C02", r["record_id"], r["version"])
            if rec is not None:
                found |= roots(model, rec)
        return found

    inferences = d["labeled_inferences"]
    inference_roots = [root_set(i["supporting_references"]) for i in inferences]
    for a in range(len(inferences)):
        for b in range(a + 1, len(inferences)):
            shared = inference_roots[a] & inference_roots[b]
            if not shared:
                continue
            for idx in (a, b):
                if not any("common origin" in l.lower() for l in inferences[idx]["limitations"]):
                    out.append(_f("COR002", "inferences %s and %s rest on the same origin (%s); each must say so in its limitations (\"common origin\")" % (
                        inferences[a]["inference_id"], inferences[b]["inference_id"], ", ".join("%s %s" % x for x in sorted(shared))),
                        pkt, "/labeled_inferences/%d/limitations" % idx, DOC_LINEAGE))
    items = [("/supported_claims_references/%d" % i, c["text"], c["supporting_references"]) for i, c in enumerate(d["supported_claims_references"])]
    items += [("/labeled_inferences/%d" % i, c["text"], c["supporting_references"]) for i, c in enumerate(inferences)]
    for loc, text, refs in items:
        lowered = text.lower()
        claims_it = re.search(r"\b(independent(ly)?|corroborat\w*)\b", lowered) and not re.search(r"\bnot\b[^.]{0,40}\b(independent|corroborat\w*)", lowered)
        if not claims_it:
            continue
        shared = set.intersection(*[root_set([r]) or {("?", "?")} for r in refs]) if refs else set()
        if len(refs) < 2 or shared:
            out.append(_f("COR001", "describes agreement as independent corroboration, but the cited records %s" % (
                "are fewer than two" if len(refs) < 2 else "share one origin (%s)" % ", ".join("%s %s" % x for x in sorted(shared))), pkt, loc, DOC_LINEAGE))
    return out


# --------------------------------------------------------------------------- authority

GATE_CODE = re.compile(r"\b[A-Z]{3,}(?:_[A-Z]+)+\b")


def check_authority(model: Model) -> List[Finding]:
    out: List[Finding] = []
    by_id: Dict[str, List[Instance]] = {}
    for rec in model.of("C07"):
        by_id.setdefault(rec.id, []).append(rec)
    for versions in by_id.values():
        versions.sort(key=lambda i: _vn(i.version))
        first = versions[0]
        out.extend(_check_receipt(model, first, versions))
        for later in versions[1:]:
            out.extend(_check_receipt_chain(model, first, later))
        for rec in versions:
            if rec.data["outcome"]["state"] in ("completed_verified", "not_executed_verified") and rec.data["verification_recovery"]["accounting"]["state"] != "reconciled":
                out.append(_f("ACC003", "a verified outcome settles its accounting: the state must be reconciled", rec, "/verification_recovery/accounting/state", DOC_ACTION))
            out.extend(_check_verification_binding(model, rec))
    return out


def _check_verification_binding(model: Model, rec: Instance) -> List[Finding]:
    """A verified outcome, and a verified no-effect above all, is verified for this attempt, its target and its action.

    Three things stay apart. A rejection before submission is what the gateway did. A verified no-effect is what an
    authoritative check found for one attempt, one target and one action. An unknown outcome is what nobody has found out yet.
    A gateway rejection alone shows nothing about every external effect: the receipt may say `not_executed_verified` only
    from a verification made after the attempt, of the receipt's own target, for its own action. A check of another target,
    another action or an earlier moment shows nothing about this attempt.

    The labels are not enough: each record the verification cites must itself be about the receipt's target, must be an observation
    (a source record assertion: not something derived from other records or inferred by a model), must describe something
    observed at or after the attempt and at or before the verification, and must have been admitted by the time of the
    verification. A record observed before the attempt, or one the verification could not yet have had, verifies nothing.
    What the cited record SAYS is not judged: its claim is free text, so a record about the right target and the right moment
    that contradicts the receipt would pass. A structured assertion of the observed effect would let a validator check it;
    the v1 schema has no such field, and v1.0.2 does not add one.
    """
    d = rec.data
    out: List[Finding] = []
    if d["outcome"]["state"] not in ("completed_verified", "not_executed_verified"):
        return out
    binding = d["identity_binding"]
    verification = d["verification_recovery"]["verification"]
    where = "/verification_recovery/verification"
    named = [(where, verification)] + [("%s/authoritative_outcome_references/%d" % (where, i), ref) for i, ref in enumerate(verification.get("authoritative_outcome_references", []))]
    for loc, item in named:
        target, action = item.get("target"), item.get("action_reference")
        if target is not None and target != binding["target"]:
            out.append(_f("AUTH008", "a verified outcome is verified for the receipt's own target (%s %s), but this verification names %s %s" % (
                binding["target"]["entity_type"], binding["target"]["entity_id"], target.get("entity_type"), target.get("entity_id")), rec, loc + "/target", DOC_ACTION))
        if action is not None and action != binding["proposal_reference"]:
            out.append(_f("AUTH008", "a verified outcome is verified for the receipt's own action (%s %s), but this verification names %s %s" % (
                binding["proposal_reference"]["id"], binding["proposal_reference"]["version"], action.get("id"), action.get("version")), rec, loc + "/action_reference", DOC_ACTION))
    verified_at, attempted_at = parse_time(verification.get("time")), parse_time(d["outcome"]["timestamps"].get("submitted"))
    if verified_at is None or attempted_at is None:
        out.append(_f("AUTH008", "a verified outcome needs a verification time and an attempt time, to show that the check came after the attempt", rec, where + "/time", DOC_ACTION))
        return out
    if verified_at < attempted_at:
        out.append(_f("AUTH008", "the verification was made at %s, before the attempt at %s: a check made before an attempt cannot show what that attempt did" % (
            verification["time"], d["outcome"]["timestamps"]["submitted"]), rec, where + "/time", DOC_ACTION))
    for i, item in enumerate(verification.get("authoritative_outcome_references", [])):
        loc = "%s/authoritative_outcome_references/%d" % (where, i)
        ref = _object_of(item.get("reference"))
        record = model.get("C02", ref.get("record_id"), ref.get("version"))
        if record is None:
            continue   # REF001 reports a record that does not exist
        label = "%s %s" % (record.id, record.version)
        kind = _object_of(record.data.get("identity_schema")).get("kind")
        if kind != "source_record_assertion":
            out.append(_f("AUTH008", "the verification cites %s, which is a %s: a verification rests on an observation of the target (a source record assertion), not on something derived from other records or inferred by a model" % (
                label, str(kind).replace("_", " ")), rec, loc + "/reference", DOC_ACTION))
        named_entities = [e for e in _object_of(record.data.get("scope")).get("entity_references", []) if isinstance(e, dict)]
        if binding["target"] not in named_entities:
            out.append(_f("AUTH008", "the verification cites %s, which is not about the receipt's own target (%s %s): its scope names %s" % (
                label, binding["target"]["entity_type"], binding["target"]["entity_id"], ", ".join("%s %s" % (e.get("entity_type"), e.get("entity_id")) for e in named_entities) or "no entity"), rec, loc + "/reference", DOC_ACTION))
        event = _object_of(_object_of(record.data.get("times")).get("event"))
        observed = parse_time(event.get("value")) if event.get("state") == "known" else None
        if observed is None:
            out.append(_f("AUTH008", "the time that %s was observed is missing or unknown, so it cannot be shown to come from after the attempt" % label, rec, loc + "/reference", DOC_ACTION))
        elif observed < attempted_at:
            out.append(_f("AUTH008", "the verification cites %s, observed at %s, before the attempt at %s: an observation made before an attempt cannot show what that attempt did" % (
                label, event["value"], d["outcome"]["timestamps"]["submitted"]), rec, loc + "/reference", DOC_ACTION))
        elif observed > verified_at:
            out.append(_f("AUTH008", "the verification, made at %s, cites %s, observed at %s: it cannot rest on an observation made after it" % (
                verification["time"], label, event["value"]), rec, loc + "/reference", DOC_ACTION))
        unavailable = availability_problem(record, verified_at)
        if unavailable is not None:
            out.append(_f("AUTH008", "the verification, made at %s, cites a record that was not yet available to it: %s" % (verification["time"], unavailable.message), rec, loc + "/reference", DOC_ACTION))
    return out


def _object_of(value) -> dict:
    return value if isinstance(value, dict) else {}


def _entity_name(entity) -> str:
    entity = _object_of(entity)
    return "%s %s" % (entity.get("entity_type"), entity.get("entity_id"))


def _check_receipt(model: Model, first: Instance, versions: List[Instance]) -> List[Finding]:
    """What a receipt says about its attempt, against what the reference commit check decides for that attempt.

    The attempt (its proposal, its grant and its submission time) is the same in every version of a receipt, so the gateway's decision is
    worked out once, from the first version, and every version is held to it: a later version that calls an allowed attempt a rejection,
    or says that a blocked one ran, is as wrong as the first would be.
    """
    out: List[Finding] = []
    rec = first
    d = rec.data
    pref, gref = d["identity_binding"]["proposal_reference"], d["identity_binding"]["grant_reference"]
    prop, grant = model.get("C05", pref["id"], pref["version"]), model.get("C06", gref["id"], gref["version"])
    if prop is None or grant is None:
        return out
    # A receipt is for the target its proposal names. A verification can show only what happened to the receipt's own target, so a
    # receipt that names another target would carry a verified outcome for something the action never concerned.
    named, proposed = d["identity_binding"].get("target"), _object_of(prop.data["action"]).get("exact_target")
    if named != proposed:
        out.append(_f("AUTH009", "the receipt says the attempt concerned %s, but the proposal it executes names %s: a receipt is for the target of its proposal" % (_entity_name(named), _entity_name(proposed)), rec, "/identity_binding/target", DOC_ACTION))
    submitted = d["outcome"]["timestamps"]["submitted"]
    at = parse_time(submitted)
    for version in versions:
        # The attempt is the same in every version, so the submission time of every version must be one that can be compared exactly. A later version with a time
        # that cannot be read is an input that cannot be judged (INP002), the same as the first, and not a receipt that merely differs.
        stated = version.data["outcome"]["timestamps"]["submitted"]
        if parse_time(stated) is None:
            raise ValueError("%s: receipt %s %s has a submission time (%r) that is not an RFC 3339 time with a zone and at most six fractional digits, so the attempt it describes "
                             "cannot be compared with the grant and the evidence exactly. Correct the time" % (version.file, version.id, version.version, stated))
    decision = evaluate_commit(model, prop, grant, at, ledger_from_receipts(model, at, exclude_receipt_id=rec.id))
    for version in versions:
        out.extend(_check_outcome(version, decision))
    return out


def _check_outcome(rec: Instance, decision) -> List[Finding]:
    """One version of a receipt: what it says happened, against what the gateway decides for the attempt."""
    out: List[Finding] = []
    d = rec.data
    state = d["outcome"]["state"]
    reason = d["outcome"].get("reason", "")
    cited = [c for c in GATE_CODE.findall(reason) if c in GATE_CODES]
    if not decision.allow:
        if state != "not_executed_verified":
            out.append(_f("AUTH004", "the gateway would have blocked this attempt (%s) but the receipt says %s" % (", ".join(sorted(set(decision.codes))), state), rec, "/outcome/state", DOC_ACTION))
        else:
            named = set(GATE_CODE.findall(reason))   # whole names: GRANT_REVOKED_LEGACY does not name GRANT_REVOKED
            missing = sorted({c for c in decision.codes if c not in named})
            if missing:
                out.append(_f("AUTH005", "the receipt reason must name the blocking checks; missing %s" % ", ".join(missing), rec, "/outcome/reason", DOC_ACTION))
            extra = sorted({c for c in cited if c not in decision.codes})
            if extra:
                out.append(_f("AUTH007", "the receipt cites %s, but the gateway does not fail %s for this attempt (it fails %s)" % (
                    ", ".join(extra), "that check" if len(extra) == 1 else "those checks", ", ".join(sorted(set(decision.codes)))), rec, "/outcome/reason", DOC_ACTION))
    elif state == "not_executed_verified":
        if cited:
            out.append(_f("AUTH007", "the receipt cites %s, but the gateway passes this attempt" % ", ".join(cited), rec, "/outcome/reason", DOC_ACTION))
        if d["outcome"].get("no_effect_basis") == "rejection":
            # A rejection reserves nothing, so a receipt that calls an allowed attempt a rejection would free the capacity the attempt holds.
            out.append(_f("AUTH007", "the receipt says the gateway rejected this attempt before submission, but the gateway passes it: a rejection that did not happen cannot free the capacity the attempt holds", rec, "/outcome/no_effect_basis", DOC_ACTION))
    if state in ("unknown", "partial") and d["verification_recovery"]["accounting"]["state"] not in ("reserved", "conservatively_accounted"):
        out.append(_f("ACC001", "an unresolved outcome must keep its reservation or conservative accounting", rec, "/verification_recovery/accounting/state", DOC_ACTION))
    return out


def _check_receipt_chain(model: Model, first: Instance, later: Instance) -> List[Finding]:
    out: List[Finding] = []
    a, b = first.data["identity_binding"], later.data["identity_binding"]
    for key in ("proposal_reference", "grant_reference", "execution_attempt_id", "target"):
        if a[key] != b[key]:
            out.append(_f("ACC004", "a later version of a receipt must describe the same attempt (%s changed)" % key, later, "/identity_binding/" + key, DOC_ACTION))
    first_submitted, later_submitted = (_object_of(_object_of(v.data["outcome"]).get("timestamps")).get("submitted") for v in (first, later))
    first_at, later_at = parse_time(first_submitted), parse_time(later_submitted)
    # The same instant written another way (Z or +00:00, with or without a zero fraction) is the same attempt: instants are compared, not their spelling.
    same_attempt = first_at == later_at if first_at is not None and later_at is not None else first_submitted == later_submitted
    if not same_attempt:
        out.append(_f("ACC004", "a later version of a receipt must describe the same attempt (the submission time changed from %s to %s)" % (first_submitted, later_submitted), later, "/outcome/timestamps/submitted", DOC_ACTION))
    if first.data["outcome"]["state"] in ("unknown", "partial") and later.data["outcome"]["state"] == "completed_verified":
        acct = later.data["verification_recovery"]["accounting"]
        if acct["state"] != "reconciled" or "authoritative_reconciliation_reference" not in acct:
            out.append(_f("ACC002", "allowance is restored or reconciled only on authoritative reconciliation, never by timeout or lease expiry", later, "/verification_recovery/accounting", DOC_ACTION))
    return out


# --------------------------------------------------------------------------- disclosure

def check_disclosure(model: Model) -> List[Finding]:
    """SNAPSHOT VALIDATION of disclosure: stored C03/C04 outputs against the stored permission decisions.

    The primary rule is constructive. Every entry that tells the viewer a source was not readable must be exactly the entry
    the viewer projection builds from a permission decision bound to the viewer (DISC002-DISC004), and every record an
    output names must belong to the viewer's tenant and purpose (DISC005). The protected-term scan (DISC001) is a backstop
    only: a list of words cannot enumerate what an output may not say. None of this enforces authorization.
    """
    out: List[Finding] = []
    terms = [t.lower() for t in model.registry.protected_terms]
    if terms:
        import json as _json
        for inst in model.of("C03") + model.of("C04"):
            text = _json.dumps(inst.data, ensure_ascii=False).lower()
            for term in terms:
                if term in text:
                    out.append(_f("DISC001", "derived output mentions protected detail %r that this principal may not see; a summary can disclose what the record withholds" % term, inst, "", DOC_LINEAGE))
    out.extend(_check_existence_disclosure(model))
    out.extend(_check_evidence_binding(model))
    return out


def viewer_of(model: Model, inst: Instance) -> Optional[Viewer]:
    """Who a C03 selection or C04 packet is for: the requesting principal, tenant and purpose of the C01 context it names."""
    if inst.contract == "C03":
        ref = inst.data["identity_scope"]["context_reference"]
    else:
        ref = inst.data["decision_context_as_of"]["context_reference"]
    context = model.get("C01", ref["id"], ref["version"])
    if context is None:
        return None
    who, task = context.data["identity_principal"], context.data["task_purpose_entity"]
    return Viewer(who["requesting_principal"], who["tenant"], task["permitted_purpose"], tuple(task["entity_references"]))


def permitted_wording(model: Model, inst: Instance, reference: dict) -> Optional[str]:
    """The wording a bound permission decision lets this viewer see for an unreadable input, or None if nothing may be shown."""
    viewer = viewer_of(model, inst)
    raw = model.registry.permission_decisions.get("%s@%s" % (reference.get("record_id"), reference.get("version")))
    if viewer is None or raw is None:
        return None
    decision = Decision.from_registry(raw)
    return decision.permitted_disclosure if may_know(decision, viewer) and decision.disclose_existence_allowed and decision.permitted_disclosure else None


def _unreadable_entries(inst: Instance):
    """(location, kind, permission decision reference, entry) for every entry that tells the reader a source was not readable."""
    d = inst.data
    if inst.contract == "C03":
        for i, gap in enumerate(d["conflicts_gaps"]["missingness"]):
            if gap["state"] == "inaccessible":
                yield "/conflicts_gaps/missingness/%d" % i, "gap", gap["permission_decision_reference"], gap
        for i, unit in enumerate(d["retrieval"]):
            if unit["status"] == "not_permitted":
                yield "/retrieval/%d" % i, "retrieval", unit["authorization_reference"], unit
    elif inst.contract == "C04":
        for i, gap in enumerate(d["coverage_omissions_gaps"]["missingness"]):
            if gap["state"] == "inaccessible":
                yield "/coverage_omissions_gaps/missingness/%d" % i, "gap", gap["permission_decision_reference"], gap


def _check_existence_disclosure(model: Model) -> List[Finding]:
    """Permission comes before disclosure: an entry that says a source was not readable exists only if a decision bound to the viewer allows it.

    The order is the order of the projection: the decision exists, it binds to the exact requesting principal (and to the
    tenant and purpose it claims), it lets the viewer know the input exists and does not let them read it (an input they may
    read is not "inaccessible" to them), and then the entry must be exactly the generic disclosure the decision configures.
    A sibling field that says more than the decision does is a finding like a wrong summary.
    """
    out: List[Finding] = []
    decisions = model.registry.permission_decisions
    for inst in model.of("C03") + model.of("C04"):
        viewer = viewer_of(model, inst)
        for loc, kind, ref, entry in _unreadable_entries(inst):
            raw = decisions.get("%s@%s" % (ref["record_id"], ref["version"]))
            if raw is None:
                out.append(_f("DISC002", "this entry tells the reader that a source was not readable, but %s %s has no permission decision in examples/registry.json that allows saying so" % (ref["record_id"], ref["version"]), inst, loc, DOC_LINEAGE))
                continue
            decision = Decision.from_registry(raw)
            if viewer is None:
                out.append(_f("DISC004", "permission decision %s cannot be bound to the requesting principal: the output names no readable C01 context" % ref["record_id"], inst, loc, DOC_LINEAGE))
                continue
            problems = binding_problems(decision, viewer)
            if problems:
                for problem in problems:
                    out.append(_f("DISC004", "permission decision %s does not bind to this viewer, so it allows no entry: %s" % (ref["record_id"], problem), inst, loc, DOC_LINEAGE))
                continue
            if decision.read_allowed:
                out.append(_f("DISC003", "permission decision %s lets this viewer read the input, yet this entry tells the reader that it is not readable: an entry may say so only where the decision does not allow reading it" % ref["record_id"], inst, loc, DOC_LINEAGE))
                continue
            if not decision.disclose_existence_allowed and not decision.read_allowed:
                out.append(_f("DISC002", "permission decision %s withholds the existence of what it protects: no output may carry an entry for it, only the coverage limitation every output carries" % ref["record_id"], inst, loc, DOC_LINEAGE))
                continue
            expected = gap_entry(decision, viewer, ref) if kind == "gap" else retrieval_entry(decision, ref)
            for pointer, want in differences(expected, entry):
                if pointer in ("/permission_safe_summary", "/summary"):
                    out.append(_f("DISC003", "the wording shown is not the wording that permission decision %s allows" % ref["record_id"], inst, loc + pointer, DOC_LINEAGE))
                else:
                    out.append(_f("DISC003", "this entry says more or other than the generic disclosure that permission decision %s configures: the field %s must be %s" % (ref["record_id"], pointer, _show(want)), inst, loc + pointer, DOC_LINEAGE))
    out.extend(_check_read_retrievals(model, decisions))
    return out


def _check_read_retrievals(model: Model, decisions: dict) -> List[Finding]:
    """A retrieval that says it was read may not cite a permission decision that does not let the viewer read.

    The retrieval units of a selection that stand for something the viewer read (completed, failed, and so on) cite the read-scope decision that authorized them.
    When that is a decision of the registry, it must bind to the viewer and allow reading. One that withholds the existence of what it protects may not be named
    in an output at all, and one that lets the viewer know of an input and not read it belongs to the generic entry (status `not_permitted`), not to a retrieval.
    """
    out: List[Finding] = []
    for inst in model.of("C03"):
        viewer = viewer_of(model, inst)
        for i, unit in enumerate(inst.data["retrieval"]):
            unit = _object_of(unit)
            ref = unit.get("authorization_reference")
            if unit.get("status") == "not_permitted" or not isinstance(ref, dict):
                continue
            raw = decisions.get("%s@%s" % (ref.get("record_id"), ref.get("version")))
            if raw is None:
                continue   # a read-scope decision that the registry does not hold is an external record; REF005 sees whether it exists
            loc = "/retrieval/%d/authorization_reference" % i
            decision = Decision.from_registry(raw)
            problems = ["the output names no readable C01 context"] if viewer is None else binding_problems(decision, viewer)
            if problems:
                out.extend(_f("DISC004", "permission decision %s does not bind to this viewer, so it authorizes no retrieval for them: %s" % (ref.get("record_id"), problem), inst, loc, DOC_LINEAGE) for problem in problems)
            elif not decision.disclose_existence_allowed and not decision.read_allowed:
                out.append(_f("DISC002", "this retrieval unit names permission decision %s, which withholds the existence of what it protects: no output may name it" % ref.get("record_id"), inst, loc, DOC_LINEAGE))
            elif not decision.read_allowed:
                out.append(_f("DISC003", "this retrieval unit says it was %s, but permission decision %s does not let this viewer read what it protects: only the generic entry (status not_permitted) may stand for it" % (unit.get("status"), ref.get("record_id")), inst, loc, DOC_LINEAGE))
    return out


def _show(value) -> str:
    import json as _json
    return "absent" if value is None else _json.dumps(value, ensure_ascii=False)


def _check_evidence_binding(model: Model) -> List[Finding]:
    """A record an output names must belong to the viewer's tenant, and be permitted for the viewer's purpose, where the record says so."""
    out: List[Finding] = []
    for inst in model.of("C03") + model.of("C04"):
        viewer = viewer_of(model, inst)
        if viewer is None:
            continue
        seen = set()
        for ref in iter_refs(inst.data):
            if ref.kind not in ("evidence", "support") or (ref.record_id, ref.version) in seen:
                continue
            seen.add((ref.record_id, ref.version))
            record = model.get("C02", ref.record_id, ref.version)
            if record is None:
                continue
            claimed = record.data.get("disclosure_permissions", {})
            if claimed.get("tenant") and claimed["tenant"] != viewer.tenant:
                out.append(_f("DISC005", "the output names %s %s, which belongs to tenant %s, not to the tenant %s of the requesting context" % (record.id, record.version, claimed["tenant"], viewer.tenant), inst, ref.path, DOC_LINEAGE))
            elif claimed.get("purpose") and claimed["purpose"] != viewer.purpose:
                out.append(_f("DISC005", "the output names %s %s, which is permitted only for the purpose %r, not for %r" % (record.id, record.version, claimed["purpose"], viewer.purpose), inst, ref.path, DOC_LINEAGE))
    return out


# --------------------------------------------------------------------------- accountability

DOC_ROLES = "examples/README.md#conventions"


def _holders(roles: dict, role: str) -> Set[str]:
    entry = roles.get(role, {})
    return set(entry.get("holders", entry.get("principals", [])))


def _check_authority_binding(model: Model, roles: dict) -> List[Finding]:
    """Authority goes to the executor, and only the executor that holds it acts on it.

    ROLE006: the executor of a receipt is the grantee of the grant the receipt cites. ROLE007: a grantee, and the executor of
    a receipt, hold the registered executor role. ROLE008: the workload that proposes (the assistant workload of a C01
    context) is neither a grantee nor an executor: the assistant proposes, the executor receives authority.
    """
    out: List[Finding] = []
    executors = _holders(roles, "executor")
    assistants = {c.data["identity_principal"]["workload_identity"] for c in model.of("C01")}

    def role_problem(who: str, grant_or_receipt: Instance, location: str, what: str) -> None:
        if who in assistants:
            out.append(_f("ROLE008", "%s is the assistant workload that proposes actions, and it is %s: the assistant proposes, and the executor receives authority" % (who, what), grant_or_receipt, location, DOC_ROLES))
        elif roles and who not in executors:
            out.append(_f("ROLE007", "%s is %s but is not a registered executor (%s)" % (who, what, ", ".join(sorted(executors)) or "none registered"), grant_or_receipt, location, DOC_ROLES))

    for grant in model.of("C06"):
        role_problem(grant.data["identity_principals"]["grantee"], grant, "/identity_principals/grantee", "the grantee of the %s %s" % (grant.data["scope_binding"]["binding"]["binding_type"].replace("_", " "), grant.id))
    for receipt in model.of("C07"):
        binding = receipt.data["identity_binding"]
        executor, ref = binding["executor"], binding["grant_reference"]
        role_problem(executor, receipt, "/identity_binding/executor", "the executor of receipt %s" % receipt.id)
        grant = model.get("C06", ref["id"], ref["version"])
        if grant is not None and executor != grant.data["identity_principals"]["grantee"]:
            out.append(_f("ROLE006", "receipt %s was made by %s, but grant %s %s names %s as its grantee: no receipt validates under another principal's grant" % (
                receipt.id, executor, grant.id, grant.version, grant.data["identity_principals"]["grantee"]), receipt, "/identity_binding/executor", DOC_ROLES))
    return out


def check_accountability(model: Model) -> List[Finding]:
    """Requestor, Decision Owner, approver and executor stay distinct unless the registry says one person may hold two.

    An exact approval needs an approver who is not the requestor, and an earlier review of its packet by a Decision Owner.
    A packet marked reviewed names a Decision Owner as the reviewer, and the review log agrees. The assistant proposes and the
    executor receives authority: a grant names a registered executor as its grantee, never the assistant workload, and an
    execution receipt is made by the grantee of the grant it cites and by no one else. Both grant shapes (an exact approval
    and a bounded class) follow the same rule; the shape decides what the grant covers, not who may act under it.
    """
    out: List[Finding] = []
    acc = model.registry.accountability
    roles = acc.get("roles", {})
    out.extend(_check_authority_binding(model, roles))
    if not roles:
        exact = [g for g in model.of("C06") if g.data["scope_binding"]["binding"]["binding_type"] == "exact_proposal"]
        reviewed = [p for p in model.of("C04") if p.data["review_version_history"]["state"] == "reviewed"]
        grants, receipts = model.of("C06"), model.of("C07")
        if exact or reviewed or grants or receipts:
            out.append(_f("ROLE005", "the registry names no roles, so the requestor, the Decision Owner and the approver of %d exact approval(s) and %d reviewed packet(s), and the executor of %d grant(s) and %d receipt(s), cannot be checked" % (
                len(exact), len(reviewed), len(grants), len(receipts)), (exact or reviewed or grants or receipts)[0], "/", DOC_ROLES))
        return out
    approvers, owners = _holders(roles, "approver"), _holders(roles, "decision_owner")
    together = [set(pair) for pair in acc.get("may_hold_together", [])]
    log = acc.get("review_log", [])
    for grant in model.of("C06"):
        binding = grant.data["scope_binding"]["binding"]
        if binding["binding_type"] != "exact_proposal":
            continue
        who = grant.data["identity_principals"]
        issuer, issued = who["issuer"], ts(who["issuance_time"])
        if issuer not in approvers:
            out.append(_f("ROLE001", "%s issues an exact approval but is not a registered approver (%s)" % (issuer, ", ".join(sorted(approvers)) or "none"), grant, "/identity_principals/issuer", DOC_ROLES))
        ref = binding["proposal_reference"]
        proposal = model.get("C05", ref["id"], ref["version"])
        if proposal is None:
            continue
        pref = proposal.data["identity_binding"]["packet_reference"]
        packet = model.get("C04", pref["id"], pref["version"])
        if packet is None:
            continue
        cref = packet.data["decision_context_as_of"]["context_reference"]
        context = model.get("C01", cref["id"], cref["version"])
        requestor = context.data["identity_principal"]["requesting_principal"] if context is not None else None
        if requestor == issuer and {"requestor", "approver"} not in together:
            out.append(_f("ROLE002", "%s asked for the packet and also approves the action it proposes; the registry does not let one person hold the requestor and approver roles" % issuer, grant, "/identity_principals/issuer", DOC_ROLES))
        reviewed = [e for e in log if e.get("packet") == "%s %s" % (packet.id, packet.version) and e.get("action") == "reviewed" and e.get("actor") in owners and ts(e["time"]) <= issued]
        if not reviewed:
            out.append(_f("ROLE004", "no Decision Owner reviewed packet %s %s at or before the approval (%s): an approval follows the review of the packet it rests on" % (packet.id, packet.version, who["issuance_time"]), grant, "/identity_principals/issuance_time", DOC_ROLES))
    for packet in model.of("C04"):
        history = packet.data["review_version_history"]
        if history["state"] != "reviewed":
            continue
        actor, when = history["actor"].get("value"), history["time"].get("value")
        if actor not in owners:
            out.append(_f("ROLE003", "packet %s %s was reviewed by %s, who is not a Decision Owner (%s)" % (packet.id, packet.version, actor, ", ".join(sorted(owners)) or "none"), packet, "/review_version_history/actor", DOC_ROLES))
        elif not any(e.get("packet") == "%s %s" % (packet.id, packet.version) and e.get("actor") == actor and e.get("action") == "reviewed" and e.get("time") == when for e in log):
            out.append(_f("ROLE003", "the review of packet %s %s by %s at %s is not in the registry's review log" % (packet.id, packet.version, actor, when), packet, "/review_version_history", DOC_ROLES))
    return out


ALL_CHECKS = [check_references, check_lineage, check_kinds, check_lifecycle, check_missingness, check_packets, check_authority, check_disclosure, check_accountability]


def run_all(model: Model) -> List[Finding]:
    findings: List[Finding] = []
    for check in ALL_CHECKS:
        findings.extend(check(model))
    return findings
