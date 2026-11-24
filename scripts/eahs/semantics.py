"""Deterministic semantic checks for the synthetic scenario.

JSON Schema validates shape. These checks validate what shape cannot: that references resolve to the exact
version they name, that lineage is acyclic and independent of its own derivatives, that corrections invalidate
what depended on them, that each missingness label is justified, that approvals cease to be current when their
basis is superseded, and that a receipt agrees with what a gateway would have decided.

Passing proves the example set is internally coherent. It proves nothing about any real system.
"""
from __future__ import annotations

import re
from typing import Dict, List, Optional, Set, Tuple

from .disclosure import Decision, Viewer, binding_problems, differences, gap_entry, may_know, retrieval_entry
from .findings import Finding, doc_for_contract
from .gateway import GATE_CODES, age_hours, evaluate_commit, freshness_max_age, is_current_at, ledger_from_receipts, ts
from .model import Instance, Model, claims_of, iter_refs, payload_object_of, resolve_pointer

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
                    out.append(_f("REF001", "no C02 record %s %s: references name an exact version, never 'latest'" % (ref.record_id, ref.version), inst, ref.path, DOC_EVIDENCE))
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
        for i, rel in enumerate(rec.data["lineage"]["typed_relationships"]):
            if allowed and rel["relationship_type"] not in allowed:
                out.append(_f("LIN002", "relationship type %r is not one of %s" % (rel["relationship_type"], sorted(allowed)), rec, "/lineage/typed_relationships/%d" % i, DOC_LINEAGE))
            if rel["relationship_type"] == "supersession":
                older = model.get("C02", rel["to"]["record_id"], rel["to"]["version"])
                if older is not None and (older.data["lifecycle"]["state"] != "superseded" or older.data["lifecycle"].get("replacement_reference") != {"record_id": rec.id, "version": rec.version}):
                    out.append(_f("LIN003", "supersession of %s %s requires that version to be marked superseded with this record as its replacement" % (older.id, older.version), rec, "/lineage/typed_relationships/%d" % i, DOC_LINEAGE))
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


def _vn(version: str) -> int:
    digits = "".join(c for c in version if c.isdigit())
    return int(digits) if digits else 0


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
            limit = freshness_max_age(model, rec.data)
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
            refs = claim["supporting_references"]
            if len(refs) == 1 and refs[0]["reference_type"] == "claim_reference":
                rec = model.get("C02", refs[0]["record_id"], refs[0]["version"])
                src = claims_of(rec.data).get(refs[0]["claim_id"]) if rec else None
                if src is not None and src["text"] != claim["text"]:
                    out.append(_f("PKT001", "a supported claim must say what its record says; the text differs from %s %s claim %s" % (rec.id, rec.version, src["claim_id"]), pkt, "/supported_claims_references/%d/text" % i, DOC_EVIDENCE))
        for i, prop in enumerate(d["action_proposals"]):
            pr = model.get("C05", prop["proposal_reference"]["id"], prop["proposal_reference"]["version"])
            if pr is not None and pr.data["identity_binding"]["packet_reference"] != {"contract_id": "C04", "id": pkt.id, "version": pkt.version}:
                out.append(_f("PKT004", "the listed proposal is bound to a different packet", pkt, "/action_proposals/%d" % i, "contracts/c05-action-proposal.md"))
        out.extend(_check_corroboration(model, pkt))
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
        out.extend(_check_receipt(model, first))
        for later in versions[1:]:
            out.extend(_check_receipt_chain(model, first, later))
        for rec in versions:
            if rec.data["outcome"]["state"] in ("completed_verified", "not_executed_verified") and rec.data["verification_recovery"]["accounting"]["state"] != "reconciled":
                out.append(_f("ACC003", "a verified outcome settles its accounting: the state must be reconciled", rec, "/verification_recovery/accounting/state", DOC_ACTION))
    return out


def _check_receipt(model: Model, rec: Instance) -> List[Finding]:
    out: List[Finding] = []
    d = rec.data
    pref, gref = d["identity_binding"]["proposal_reference"], d["identity_binding"]["grant_reference"]
    prop, grant = model.get("C05", pref["id"], pref["version"]), model.get("C06", gref["id"], gref["version"])
    if prop is None or grant is None:
        return out
    at = ts(d["outcome"]["timestamps"]["submitted"])
    decision = evaluate_commit(model, prop, grant, at, ledger_from_receipts(model, at, exclude_receipt_id=rec.id))
    state = d["outcome"]["state"]
    if not decision.allow:
        if state != "not_executed_verified":
            out.append(_f("AUTH004", "the gateway would have blocked this attempt (%s) but the receipt says %s" % (", ".join(sorted(set(decision.codes))), state), rec, "/outcome/state", DOC_ACTION))
        else:
            reason = d["outcome"].get("reason", "")
            missing = sorted({c for c in decision.codes if c not in reason})
            if missing:
                out.append(_f("AUTH005", "the receipt reason must name the blocking checks; missing %s" % ", ".join(missing), rec, "/outcome/reason", DOC_ACTION))
    elif state == "not_executed_verified":
        cited = [c for c in GATE_CODE.findall(d["outcome"].get("reason", "")) if c in GATE_CODES]
        if cited:
            out.append(_f("AUTH007", "the receipt cites %s, but the gateway passes this attempt" % ", ".join(cited), rec, "/outcome/reason", DOC_ACTION))
    if state in ("unknown", "partial") and d["verification_recovery"]["accounting"]["state"] not in ("reserved", "conservatively_accounted"):
        out.append(_f("ACC001", "an unresolved outcome must keep its reservation or conservative accounting", rec, "/verification_recovery/accounting/state", DOC_ACTION))
    return out


def _check_receipt_chain(model: Model, first: Instance, later: Instance) -> List[Finding]:
    out: List[Finding] = []
    a, b = first.data["identity_binding"], later.data["identity_binding"]
    for key in ("proposal_reference", "grant_reference", "execution_attempt_id", "target"):
        if a[key] != b[key]:
            out.append(_f("ACC004", "a later version of a receipt must describe the same attempt (%s changed)" % key, later, "/identity_binding/" + key, DOC_ACTION))
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
    tenant and purpose it claims), it lets the viewer know the input exists, and then the entry must be exactly the generic
    disclosure the decision configures. A sibling field that says more than the decision does is a finding like a wrong summary.
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
            if not decision.disclose_existence_allowed and not decision.read_allowed:
                out.append(_f("DISC002", "permission decision %s withholds the existence of what it protects: no output may carry an entry for it, only the coverage limitation every output carries" % ref["record_id"], inst, loc, DOC_LINEAGE))
                continue
            expected = gap_entry(decision, viewer, ref) if kind == "gap" else retrieval_entry(decision, ref)
            for pointer, want in differences(expected, entry):
                if pointer in ("/permission_safe_summary", "/summary"):
                    out.append(_f("DISC003", "the wording shown is not the wording that permission decision %s allows" % ref["record_id"], inst, loc + pointer, DOC_LINEAGE))
                else:
                    out.append(_f("DISC003", "this entry says more or other than the generic disclosure that permission decision %s configures: the field %s must be %s" % (ref["record_id"], pointer, _show(want)), inst, loc + pointer, DOC_LINEAGE))
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


def check_accountability(model: Model) -> List[Finding]:
    """Requestor, Decision Owner, approver and executor stay distinct unless the registry says one person may hold two.

    An exact approval needs an approver who is not the requestor, and an earlier review of its packet by a Decision Owner.
    A packet marked reviewed names a Decision Owner as the reviewer, and the review log agrees.
    """
    out: List[Finding] = []
    acc = model.registry.accountability
    roles = acc.get("roles", {})
    if not roles:
        exact = [g for g in model.of("C06") if g.data["scope_binding"]["binding"]["binding_type"] == "exact_proposal"]
        reviewed = [p for p in model.of("C04") if p.data["review_version_history"]["state"] == "reviewed"]
        if exact or reviewed:
            out.append(_f("ROLE005", "the registry names no roles, so the requestor, the Decision Owner and the approver of %d exact approval(s) and %d reviewed packet(s) cannot be checked" % (len(exact), len(reviewed)),
                          (exact or reviewed)[0], "/", DOC_ROLES))
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
