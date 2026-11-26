"""Deterministic semantic checks for the synthetic scenario.

JSON Schema validates shape. These checks validate what shape cannot: that references resolve to the exact
version they name, that lineage is acyclic and independent of its own derivatives, that corrections invalidate
what depended on them, that each missingness label is justified, that approvals cease to be current when their
basis is superseded, and that a receipt agrees with what a gateway would have decided. A decision snapshot is held
together the same way: a context, the selection built under it and the packet built on both state one as-of time,
the packet rests only on what was available then and carries every obligation of its selection, and a proposal rests
on the context of its packet.

Passing shows that the example set satisfies these checks, which compare its records with one another. It does not show
that the records agree in every other respect, and it proves nothing about any real system.
"""
from __future__ import annotations

import json
import math
import re
from collections import Counter
from decimal import Decimal, InvalidOperation
from typing import Dict, List, Optional, Set, Tuple

from .disclosure import Decision, Viewer, binding_problems, differences, gap_entry, may_know, retrieval_entry
from .findings import Finding, doc_for_contract
from .gateway import (GATE_CODES, TERMINAL_OUTCOMES, age_hours, attempt_of, availability_problem, evaluate_commit, freshness_max_age, in_order, input_availability_problem, is_current_at, ledger_from_receipts,
                      parse_time, receipt_chains, regressive_receipt_versions, same_instant, same_value, ts)
from .model import IDENTITY, Instance, Model, claims_of, is_later, iter_refs, payload_object_of, resolve_pointer, version_problems

DOC_EVIDENCE = "architecture/evidence-semantics.md"
DOC_LINEAGE = "architecture/lineage-selection-disclosure.md"
DOC_ACTION = "architecture/action-and-degradation.md"
INACTIVE_PACKET_STATES = {"invalidated", "superseded"}


def _f(code: str, message: str, inst: Instance, location: str = "", doc: str = "") -> Finding:
    return Finding(code, message, inst.file, location, doc or doc_for_contract(inst.contract))


# --------------------------------------------------------------------------- references

def check_references(model: Model) -> List[Finding]:
    out: List[Finding] = []
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
                out.extend(_check_retrieval_reference(model, inst, ref))
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


def _selection_of(model: Model, inst: Instance) -> Optional[Instance]:
    """The selection that the gaps of `inst` belong to: a selection is its own, and a packet's is the one it is bound to. None for a packet whose selection does not exist (REF004 reports it) and for anything else."""
    if inst.contract == "C03":
        return inst
    if inst.contract == "C04":
        ref = _object_of(_object_of(inst.data.get("decision_context_as_of")).get("selection_reference"))
        return model.get("C03", ref.get("id"), ref.get("version"))
    return None


def _check_retrieval_reference(model: Model, inst: Instance, ref) -> List[Finding]:
    """A retrieval reference names a retrieval unit of the selection that its entry belongs to, at that selection's own version.

    A retrieval unit is named by its id and the version of the selection that lists it. The reference is resolved in the one selection that the entry is bound to
    (the selection that holds it, or the selection of the packet that holds it): another selection that lists a unit of the same name is another run, whatever it was called,
    and it is never searched for one that fits. The unit must be listed once there and must have completed. When it completed is MISS001's business, not this one's.
    """
    sel = _selection_of(model, inst)
    if sel is None:
        return []
    own = "selection %s %s" % (sel.id, sel.version)
    if ref.version != sel.version:
        why = "the entry belongs to %s, and a retrieval unit is named by the version of the selection that lists it: an entry rests on a run of its own selection and not on one of another, even one with the same name" % own
    else:
        units = [u for u in _object_of(sel.data).get("retrieval", []) if isinstance(u, dict) and u.get("retrieval_unit_id") == ref.record_id]
        if not units:
            why = "%s lists no retrieval unit of that name" % own
        elif len(units) > 1:
            why = "%s lists %d retrieval units of that name, so the reference is ambiguous" % (own, len(units))
        elif units[0].get("status") != "completed":
            why = "the retrieval unit has status %r in %s, not 'completed'" % (units[0].get("status"), own)
        else:
            return []
    return [_f("REF006", "no completed retrieval unit %s %s of its own selection: %s" % (ref.record_id, ref.version, why), inst, ref.path, "contracts/c03-selection.md")]


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


def _root_records(model: Model, rec: Instance) -> List[Instance]:
    """The records a derivation ultimately rests on: the records of its ancestry that name no parent (the record itself if it names none)."""
    anc = ancestors(model, rec)
    if not anc:
        return [rec]
    return [a for a in anc.values() if not a.data["lineage"]["parent_references"]]


def roots(model: Model, rec: Instance) -> Set[Tuple[str, str]]:
    """The records a derivation ultimately rests on (itself if it has no parents)."""
    return {(r.id, r.version) for r in _root_records(model, rec)}


def origin_of(root: Instance) -> tuple:
    """What a root record stands for as an origin, for deciding whether two derivations rest on one origin.

    A source record assertion is a wrapper of a record of a source system, and the wrapper declares which one in `original_source`: the source system, the locator of the record in it, and one immutable
    version of it, an original version or an immutable snapshot. Two wrappers that declare the same three things wrap the same source record, whatever their C02 identities are, so they are one origin.
    Only what is declared is compared, exactly and as written: another locator, another version, another source system or another way of pinning the version is another origin, and nothing is inferred
    between them. A root that is not a source record assertion, or whose declared source does not pin a version, stands for its own record. The C02 identity stays what lineage and references use.
    """
    if root.data["identity_schema"]["kind"] == "source_record_assertion":
        source = _object_of(root.data.get("original_source"))
        system, locator = source.get("source_id"), source.get("record_locator")
        if isinstance(system, str) and system and isinstance(locator, str) and locator:
            version, snapshot = source.get("original_version"), _object_of(source.get("immutable_snapshot_reference"))
            if isinstance(version, str) and version and "immutable_snapshot_reference" not in source:
                return ("source", system, locator, "original_version", version)
            if isinstance(snapshot.get("record_id"), str) and isinstance(snapshot.get("version"), str) and "original_version" not in source:
                return ("source", system, locator, "immutable_snapshot_reference", snapshot["record_id"], snapshot["version"])
    return ("record", root.id, root.version)


def origins(model: Model, rec: Instance) -> Dict[tuple, List[Instance]]:
    """The origins that a record rests on, each with the root records that stand for it (`origin_of`), in the order of their identities."""
    found: Dict[tuple, List[Instance]] = {}
    for root in sorted(_root_records(model, rec), key=lambda r: (r.id, r.version)):
        found.setdefault(origin_of(root), []).append(root)
    return found


def _origin_label(identity: tuple, wrappers: List[Instance]) -> str:
    """How a message names an origin: the record it is, or, when several records wrap one source record, that source record and the records that wrap it."""
    names = ["%s %s" % (w.id, w.version) for w in sorted(wrappers, key=lambda w: (w.id, w.version))]
    if identity[0] == "record" or len(names) < 2:
        return names[0] if len(names) == 1 else "%s %s" % identity[1:3]
    pinned = "original version %s" % identity[4] if identity[3] == "original_version" else "immutable snapshot %s %s" % identity[4:6]
    return "source record %s in %s (%s), wrapped by %s" % (identity[2], identity[1], pinned, " and ".join(names))


def _computed_over_records(model: Model, rec: Instance) -> bool:
    """Whether this record is the result of a rule applied to other records, so that it must name them as its parents.

    A deterministic finding reports what a declared rule produces from specified inputs, and those inputs are records of the set, unless its producer is
    registered as computing over data that is not a record of the set (a ledger check, a screening run): the registry says so with `"inputs": "outside_records"`.
    The registry decides, and the record cannot: a producer would otherwise be free to leave out its parents by the way it writes its content.
    A source record assertion is an original and needs no parent. No other kind is judged here, and nothing recomputes a finding from its parents.
    """
    if rec.data["identity_schema"]["kind"] != "deterministic_finding":
        return False
    producer = model.registry.producers.get(rec.data["producer_admission"]["producer_id"])
    return not (isinstance(producer, dict) and producer.get("inputs") == "outside_records")


def check_lineage(model: Model) -> List[Finding]:
    out: List[Finding] = []
    allowed = set(model.registry.relationship_types)
    for rec in model.of("C02"):
        for i, p in enumerate(rec.data["lineage"]["parent_references"]):
            if (p["record_id"], p["version"]) == (rec.id, rec.version):
                out.append(_f("LIN004", "a record cannot be its own parent", rec, "/lineage/parent_references/%d" % i, DOC_LINEAGE))
        if rec.data["identity_schema"]["kind"] == "source_record_assertion" and rec.data["lineage"]["parent_references"]:
            out.append(_f("LIN007", "a source record assertion is an original: it states what a source system recorded, so it names no parent. A parent would make it a derivation and change the origin that it is counted from "
                                    "(it names %d)" % len(rec.data["lineage"]["parent_references"]), rec, "/lineage/parent_references", DOC_LINEAGE))
        out.extend(_check_parents_available(model, rec))
        if not rec.data["lineage"]["parent_references"] and _computed_over_records(model, rec):
            out.append(_f("LIN006", "a deterministic finding reports what a rule produced from specified inputs, so it names the records it was computed from as its parents; this one names none, "
                                    "and its producer %s is not registered as computing over data outside the records" % rec.data["producer_admission"]["producer_id"], rec, "/lineage/parent_references", DOC_LINEAGE))
        # cycle: the record must not be among its own ancestors
        if (("C02", rec.id, rec.version)) in ancestors(model, rec):
            out.append(_f("LIN001", "derivation ancestry must be acyclic, but %s %s is its own ancestor" % (rec.id, rec.version), rec, "/lineage", DOC_LINEAGE))
        elif rec.data["identity_schema"]["kind"] == "model_inference":
            out.extend(_check_inference_figures(model, rec))
        for i, rel in enumerate(rec.data["lineage"]["typed_relationships"]):
            if allowed and rel["relationship_type"] not in allowed:
                out.append(_f("LIN002", "relationship type %r is not one of %s" % (rel["relationship_type"], sorted(allowed)), rec, "/lineage/typed_relationships/%d" % i, DOC_LINEAGE))
            if rel["relationship_type"] == "supersession":
                out.extend(_check_supersession_edge(rec, rel, "/lineage/typed_relationships/%d" % i))
                older = model.get("C02", rel["to"]["record_id"], rel["to"]["version"])
                if older is not None and (older.data["lifecycle"]["state"] != "superseded" or older.data["lifecycle"].get("replacement_reference") != {"record_id": rec.id, "version": rec.version}):
                    out.append(_f("LIN003", "supersession of %s %s requires that version to be marked superseded with this record as its replacement" % (older.id, older.version), rec, "/lineage/typed_relationships/%d" % i, DOC_LINEAGE))
    return out


def _check_parents_available(model: Model, rec: Instance) -> List[Finding]:
    """A declared parent is an input the record was derived from, so it was available when the record was admitted.

    A parent is available from the later of its admission and its ingestion, and equality counts (the rule of the commit check, `gateway.availability_problem`). The time compared is the admission of
    the derived record, as instants. Only the availability of a parent that exists is judged (REF001 reports one that does not), and only the parents that the record declares: an input of a producer
    that computes outside the records (`inputs: outside_records`) is not a record of the set and is not made one here. The time of the event a parent describes does not matter.
    """
    out: List[Finding] = []
    stated = rec.data["producer_admission"].get("admission_time")
    admitted = parse_time(stated)
    for i, p in enumerate(rec.data["lineage"]["parent_references"]):
        parent = model.get("C02", p["record_id"], p["version"])
        if parent is None or parent.key == rec.key:
            continue
        if admitted is None:
            out.append(_f("LIN008", "the admission time of this record (%r) cannot be compared exactly, so it cannot be shown that its parent %s %s was available when it was admitted" % (stated, parent.id, parent.version), rec, "/lineage/parent_references/%d" % i, DOC_LINEAGE))
            continue
        problem = availability_problem(parent, admitted, "this record's admission at %s" % stated)
        if problem is not None:
            out.append(_f("LIN008", "a parent is an input that the record was derived from, so it was available when the record was admitted: %s" % problem.message, rec, "/lineage/parent_references/%d" % i, DOC_LINEAGE))
    return out


def _check_supersession_edge(rec: Instance, rel: dict, loc: str) -> List[Finding]:
    """A typed supersession goes from the record that states it, the replacement, to the older version it replaces.

    The edge starts at the record that holds it, and it does not end there: a record does not supersede itself. Which version it ends at, and that the older version records this one as its replacement,
    is judged by LIN003 and LIFE001. Nothing here says when the replacement was admitted or when the older version stopped being current.
    """
    start = _object_of(rel.get("from"))
    if (start.get("record_id"), start.get("version")) != (rec.id, rec.version):
        return [_f("LIN009", "a supersession goes from the record that states it to the older version it replaces, but this edge starts at %s %s and not at %s %s" % (
            start.get("record_id"), start.get("version"), rec.id, rec.version), rec, loc + "/from", DOC_LINEAGE)]
    end = _object_of(rel.get("to"))
    if (end.get("record_id"), end.get("version")) == (rec.id, rec.version):
        return [_f("LIN009", "a record cannot supersede itself: this edge goes from %s %s to the same record" % (rec.id, rec.version), rec, loc, DOC_LINEAGE)]
    return []


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


def _check_version_order(model: Model) -> List[Finding]:
    """The versions of one record can be put in order: each name has a number, and no two names have the same numbers.

    The schema accepts any version name, and the reference reads the order of the versions of a record from the numbers in their names (see `model.version_key`), so a chain in which that order is
    not defined is a finding, and nothing guesses it: v1 and v01 are two versions with one place, and latest has none. A record with one version needs no order. A record is still found by its exact version.
    """
    out: List[Finding] = []
    chains: Dict[Tuple[str, str], List[Instance]] = {}
    for inst in model.instances.values():
        chains.setdefault((inst.contract, inst.id), []).append(inst)
    for (contract, _), versions in sorted(chains.items()):
        problems = dict(version_problems(inst.version for inst in versions))
        for inst in sorted(versions, key=lambda i: i.version):
            if inst.version in problems:
                out.append(_f("LIFE006", "version %s %s: the versions of one record are put in order by the numbers in their names, and no order is guessed" % (inst.version, problems[inst.version]),
                              inst, "/%s/version" % IDENTITY[contract][0], DOC_LINEAGE))
    return out


def check_lifecycle(model: Model) -> List[Finding]:
    out: List[Finding] = _check_version_order(model)
    for rec in model.of("C02"):
        lc = rec.data["lifecycle"]
        if lc["state"] == "superseded":
            repl = lc.get("replacement_reference")
            newer = model.get("C02", repl["record_id"], repl["version"]) if repl else None
            if newer is None or newer.id != rec.id or not is_later(newer.version, rec.version):
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
    grants_by_id: Dict[str, List[Instance]] = {}
    for grant in model.of("C06"):
        grants_by_id.setdefault(grant.id, []).append(grant)
    latest_grants: Dict[str, Instance] = {}
    for grant_id, versions in grants_by_id.items():
        chain = in_order(versions)
        if chain is not None:   # versions that cannot be put in order have no latest (LIFE006 reports them)
            latest_grants[grant_id] = chain[-1]
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
        for i, m in enumerate(sel.data["conflicts_gaps"]["missingness"]):
            out.extend(_check_gap(model, sel, sel, m, "/conflicts_gaps/missingness/%d" % i))
    for pkt in model.of("C04"):
        ref = pkt.data["decision_context_as_of"]["selection_reference"]
        sel = model.get("C03", ref["id"], ref["version"])
        if sel is None:
            continue
        gaps = pkt.data["coverage_omissions_gaps"]["missingness"]
        for i, m in enumerate(gaps):
            out.extend(_check_gap(model, pkt, sel, m, "/coverage_omissions_gaps/missingness/%d" % i))
        for i, m in enumerate(sel.data["conflicts_gaps"]["missingness"]):
            if m not in gaps:
                out.append(_f("MISS005", "the packet leaves out a gap of its selection (%s, entry %d): every gap must stay visible in the packet" % (m["state"], i), pkt, "/coverage_omissions_gaps/missingness", DOC_LINEAGE))
        for c in sel.data["conflicts_gaps"]["conflicts"]:
            if c not in pkt.data["conflicts_uncertainty"]["conflicts"]:
                out.append(_f("MISS005", "the packet leaves out conflict %s of its selection" % c["conflict_id"], pkt, "/conflicts_uncertainty/conflicts", DOC_LINEAGE))
    return out


def _check_gap(model: Model, inst: Instance, sel: Instance, m: dict, loc: str) -> List[Finding]:
    """One entry of the missingness of a selection (`inst` is the selection) or of a packet bound to it (`sel` is that selection), judged against the selection's own state."""
    out: List[Finding] = []
    state = m["state"]
    if state == "not_retrieved":
        units = [u for u in sel.data["retrieval"] if u["retrieval_unit_id"] == m["retrieval_reference"]["record_id"]]
        if len(units) != 1 or units[0]["status"] != "completed":
            out.append(_f("MISS001", "not_retrieved needs a COMPLETED retrieval unit in the selection: an interrupted or unperformed retrieval is not an empty result", inst, loc, DOC_LINEAGE))
        else:
            out.extend(_check_completion(inst, sel, units[0], m, loc))
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


def _check_completion(inst: Instance, sel: Instance, unit: dict, m: dict, loc: str) -> List[Finding]:
    """A not_retrieved entry states when the retrieval completed. That is the unit's completion time, as an instant, and it is not later than the selection's as-of time.

    A selection is a snapshot as of one time, so an empty result of a retrieval that had not completed by then cannot be part of it. The cutoff is the selection's as-of time for an entry of
    its packet too: the packet is bound to that selection and states the same time. A completion time that is not known, or that cannot be compared exactly (see `parse_time`), cannot be shown to be early.
    """
    done = unit["completed_at"].get("value") if unit["completed_at"].get("state") == "known" else None
    finished = parse_time(done)
    if finished is None:
        return [_f("MISS001", "the retrieval unit %s has no completion time that can be compared exactly (%s), so it cannot be shown to have completed by the as-of time of the selection" % (
            unit["retrieval_unit_id"], "unknown" if done is None else repr(done)), inst, loc, DOC_LINEAGE)]
    as_of = sel.data["identity_scope"]["as_of"]
    cutoff = parse_time(as_of)
    if cutoff is None:
        raise ValueError("%s: selection %s %s has an as-of time (%r) that is not an RFC 3339 time with a zone and at most six fractional digits, so the completion of its retrievals cannot be compared "
                         "with it exactly. Correct the time" % (sel.file, sel.id, sel.version, as_of))
    out: List[Finding] = []
    if finished > cutoff:
        out.append(_f("MISS001", "the retrieval unit %s completed at %s, after the as-of time %s of selection %s %s: an empty result of a retrieval that had not completed by then is not part of the snapshot" % (
            unit["retrieval_unit_id"], done, as_of, sel.id, sel.version), inst, loc, DOC_LINEAGE))
    if not same_instant(done, m["completed_at"]):
        out.append(_f("MISS001", "completed_at does not match the retrieval unit's completion time", inst, loc, DOC_LINEAGE))
    return out


# --------------------------------------------------------------------------- packets

def check_packets(model: Model) -> List[Finding]:
    """A decision packet and the snapshot it belongs to: the context it is bound to, the selection built under that context, and the packet built on both.

    The three state one as-of time and bind one context. The packet rests only on what was available at that time, carries every obligation of its selection,
    and the proposals it lists rest on its context. This is the decision-time view of a snapshot, apart from the commit-time check (`gateway.evaluate_commit`),
    which judges an attempt at the time it is made.
    """
    out: List[Finding] = []
    for sel in model.of("C03"):
        out.extend(_check_selection_context(model, sel))
    for pkt in model.of("C04"):
        d = pkt.data
        ctx_ref, sel_ref = d["decision_context_as_of"]["context_reference"], d["decision_context_as_of"]["selection_reference"]
        ctx = model.get("C01", ctx_ref["id"], ctx_ref["version"])
        sel = model.get("C03", sel_ref["id"], sel_ref["version"])
        if sel is not None and sel.data["identity_scope"]["context_reference"] != ctx_ref:
            out.append(_f("PKT002", "the packet and its selection must bind the same context", pkt, "/decision_context_as_of/context_reference"))
        out.extend(_check_packet_as_of(pkt, ctx, sel))
        out.extend(_check_packet_basis_available(model, pkt))
        out.extend(_check_obligations(pkt, sel))
        if d["coverage_omissions_gaps"]["coverage_reference"]["selection_reference"] != sel_ref:
            out.append(_f("PKT003", "coverage must point at the packet's own selection", pkt, "/coverage_omissions_gaps/coverage_reference"))
        for i, claim in enumerate(d["supported_claims_references"]):
            out.extend(_check_claim_support(model, pkt, i, claim))
        for i, prop in enumerate(d["action_proposals"]):
            pr = model.get("C05", prop["proposal_reference"]["id"], prop["proposal_reference"]["version"])
            if pr is not None and pr.data["identity_binding"]["packet_reference"] != {"contract_id": "C04", "id": pkt.id, "version": pkt.version}:
                out.append(_f("PKT004", "the listed proposal is bound to a different packet", pkt, "/action_proposals/%d" % i, "contracts/c05-action-proposal.md"))
        out.extend(_check_corroboration(model, pkt))
    out.extend(_check_proposal_contexts(model))
    return out


def _outside(inner: dict, outer: dict) -> Optional[str]:
    """How the time interval `inner` is not within `outer`, or None when it is.

    Instants are compared, not how they are written. A bound that cannot be read exactly (see `parse_time`) can be shown to lie within another only when the two
    intervals are written alike.
    """
    bounds = [parse_time(value) for value in (inner["start"], inner["end"], outer["start"], outer["end"])]
    if any(bound is None for bound in bounds):
        return None if (inner["start"], inner["end"]) == (outer["start"], outer["end"]) else "the two cannot be compared exactly"
    start_in, end_in, start_out, end_out = bounds
    return {(True, True): "it starts before the interval and ends after it", (True, False): "it starts before the interval", (False, True): "it ends after the interval"}.get((start_in < start_out, end_in > end_out))


def _check_selection_context(model: Model, sel: Instance) -> List[Finding]:
    """A selection is built under one context: it states that context's as-of time and reads no time that the context's interval does not cover."""
    scope = sel.data["identity_scope"]
    ref = scope["context_reference"]
    ctx = model.get("C01", ref["id"], ref["version"])
    if ctx is None:
        return []   # REF004 reports a context that does not exist
    stated = ctx.data["time_risk_policy"]
    out: List[Finding] = []
    if not same_instant(scope["as_of"], stated["as_of"]):
        out.append(_f("PKT002", "the selection states the as-of time %s, but its context %s %s states %s: a context and the selection built under it are one snapshot, so they state one time" % (
            scope["as_of"], ctx.id, ctx.version, stated["as_of"]), sel, "/identity_scope/as_of"))
    outside = _outside(scope["time_scope"], stated["time_interval"])
    if outside is not None:
        out.append(_f("PKT002", "the selection's time scope (%s to %s) is not within the time interval of its context %s %s (%s to %s): %s. A selection reads no time that its context does not cover" % (
            scope["time_scope"]["start"], scope["time_scope"]["end"], ctx.id, ctx.version, stated["time_interval"]["start"], stated["time_interval"]["end"], outside), sel, "/identity_scope/time_scope"))
    return out


def _check_packet_as_of(pkt: Instance, ctx: Optional[Instance], sel: Optional[Instance]) -> List[Finding]:
    """The packet states the as-of time of the selection it is bound to and of the context it is bound to, as instants and not as written."""
    as_of = pkt.data["decision_context_as_of"]["as_of"]
    out: List[Finding] = []
    if sel is not None and not same_instant(sel.data["identity_scope"]["as_of"], as_of):
        out.append(_f("PKT002", "the packet states the as-of time %s, but its selection %s %s states %s: the packet and its selection are one snapshot, so they share one as-of time" % (
            as_of, sel.id, sel.version, sel.data["identity_scope"]["as_of"]), pkt, "/decision_context_as_of/as_of"))
    if ctx is not None and not same_instant(ctx.data["time_risk_policy"]["as_of"], as_of):
        out.append(_f("PKT002", "the packet states the as-of time %s, but its context %s %s states %s: the context, the selection and the packet are one snapshot, so they share one as-of time" % (
            as_of, ctx.id, ctx.version, ctx.data["time_risk_policy"]["as_of"]), pkt, "/decision_context_as_of/as_of"))
    return out


#: The part of a packet that lists the evidence which challenged it afterwards. Those links name later evidence by design, so they are not the packet's basis.
CHALLENGE_LINKS = "/review_version_history/challenge_links"


def _check_packet_basis_available(model: Model, pkt: Instance) -> List[Finding]:
    """Every record a packet cites as the basis of what it says was available at the packet's as-of time.

    That is every exact support reference (a claim, an inference, a conflict, a negative gap) and every record behind a gap, and no challenge link.
    Availability is the rule of the commit check, applied at the packet's as-of time: from the later of the admission and the ingestion of the record, and a time equal
    to the as-of time was reached. Only availability is judged. A record superseded later was current at the cutoff, so a later correction does not make an
    earlier packet wrong, and the commit-time checks of lifecycle and freshness are not repeated here.
    """
    as_of = pkt.data["decision_context_as_of"]["as_of"]
    cutoff = parse_time(as_of)
    if cutoff is None:
        raise ValueError("%s: packet %s %s has an as-of time (%r) that is not an RFC 3339 time with a zone and at most six fractional digits, so what it rests on cannot be compared "
                         "with it exactly. Correct the time" % (pkt.file, pkt.id, pkt.version, as_of))
    out: List[Finding] = []
    seen: Set[Tuple[str, str]] = set()
    for ref in iter_refs(pkt.data):
        if ref.kind not in ("support", "evidence") or ref.path.startswith(CHALLENGE_LINKS) or (ref.record_id, ref.version) in seen:
            continue
        seen.add((ref.record_id, ref.version))
        record = model.get("C02", ref.record_id, ref.version)
        problem = None
        if record is not None:   # REF001 reports a record that does not exist
            problem = availability_problem(record, cutoff, "the packet's as-of time") or input_availability_problem(model, record, cutoff, "the packet's as-of time")
        if problem is not None:
            out.append(_f("PKT007", "the packet is as of %s, but it cites a record that was not available then: %s. A packet rests only on what was available at its as-of time" % (as_of, problem.message), pkt, ref.path, DOC_EVIDENCE))
    return out


def _check_obligations(pkt: Instance, sel: Optional[Instance]) -> List[Finding]:
    """A packet carries every obligation of its own selection, once: none is left out, none is invented, none is taken from another selection.

    An obligation the reader may not know of is not in the selection at all (permission comes first), so each obligation a selection lists is one the reader
    must see, and a packet that leaves one out has lost a mandatory item whatever a response made from the packet then says. Acknowledgement is not resolution:
    the state of an obligation is its selection's business and is not judged here.
    """
    if sel is None:
        return []   # REF004 reports a selection that does not exist
    sel_ref = pkt.data["decision_context_as_of"]["selection_reference"]
    where = "/priority_mandatory_obligations/obligation_references"
    held = Counter(o["obligation_id"] for o in sel.data["obligations"])
    carried: Counter = Counter()
    out: List[Finding] = []
    for i, ref in enumerate(pkt.data["priority_mandatory_obligations"]["obligation_references"]):
        name, named = ref["obligation_id"], ref["selection_reference"]
        here = "%s/%d" % (where, i)
        if named != sel_ref:
            out.append(_f("PKT008", "the packet lists obligation %s of selection %s %s, but it is bound to selection %s %s: a packet carries the obligations of its own selection" % (
                name, named["id"], named["version"], sel_ref["id"], sel_ref["version"]), pkt, here))
        elif held[name] == 0:
            out.append(_f("PKT008", "the packet lists obligation %s, which its selection %s %s does not hold: a packet lists no obligation that its selection lacks" % (name, sel.id, sel.version), pkt, here))
        else:
            carried[name] += 1
            if held[name] > 1:
                out.append(_f("PKT008", "the packet lists obligation %s, but its selection %s %s holds that name more than once, so the reference is ambiguous" % (name, sel.id, sel.version), pkt, here))
            if carried[name] == 2:
                out.append(_f("PKT008", "the packet lists obligation %s more than once: each obligation of the selection is carried once" % name, pkt, here))
    for name in held:
        if not carried[name]:
            out.append(_f("PKT009", "the packet leaves out obligation %s of its selection %s %s: every obligation of the selection is a mandatory item and stays in the packet" % (name, sel.id, sel.version), pkt, where))
    return out


def _check_proposal_contexts(model: Model) -> List[Finding]:
    """A proposal rests on the context of the packet it is bound to."""
    out: List[Finding] = []
    for prop in model.of("C05"):
        binding = prop.data["identity_binding"]
        ref = binding["packet_reference"]
        pkt = model.get("C04", ref["id"], ref["version"])
        if pkt is None:
            continue   # REF004 reports a packet that does not exist
        context = pkt.data["decision_context_as_of"]["context_reference"]
        if binding["context_reference"] != context:
            out.append(_f("PKT006", "the proposal is bound to context %s %s, but the packet %s %s that it is bound to rests on context %s %s: a proposal rests on the context of its packet" % (
                binding["context_reference"]["id"], binding["context_reference"]["version"], pkt.id, pkt.version, context["id"], context["version"]), prop, "/identity_binding/context_reference"))
    return out


#: Numbers a claim states: decimals that are not part of an identifier, a date or a time (no letter, hyphen, colon or slash touches
#: them), with a leading minus when they have one, so that -100 is not 100. A colon right after a digit makes a time or a ratio ("13:45"),
#: but a colon after a word is a delimiter ("variance:-40.0"), and a number after it is stated, with its sign.
_NUMBER = re.compile(r"(?<![\w.,/-])(?<!\d:)-?\d[\d,]*(?:\.\d+)?(?![\w:/-]|\.\d)")
#: The status vocabulary a payload can state and a claim can restate. Only these words are compared: no other prose is interpreted.
_STATUS = re.compile(r"\b(pass|fail)(?:ed|es|s|ing|ure)?\b", re.IGNORECASE)
_WORD = re.compile(r"[A-Za-z][A-Za-z0-9_]*")
#: Words that may stand between a field's name and its figure ("variance of 40.0%", "tolerance is 2%").
_BETWEEN = frozenset("of is was are were at to be equal equals about only just exactly than".split())
#: Words that may stand between a figure and the name of the field that follows it ("60 units received", "40.0 percent variance").
_UNITS = frozenset("unit units piece pieces item items percent pct eur euro euros usd".split())
#: The quotation marks that may stand around a field's name: straight, typographic, angle and corner quotes, and the backtick.
_QUOTES = frozenset("\"'`\u2018\u2019\u201a\u201b\u201c\u201d\u201e\u201f\u00ab\u00bb\u2039\u203a\u300c\u300d\u300e\u300f")
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
    """The words of a field name, in order: quantity_invoiced and quantityInvoiced are "quantity", "invoiced". A word of two letters counts ("invoice_id" has "id"):
    a name is read whole, and a field is named only by a name that carries all of its words."""
    return re.findall(r"[A-Za-z]{2,}", re.sub(r"(?<=[a-z])(?=[A-Z])", " ", name))


def _field_names(node) -> List[str]:
    """The name of every field a payload has, whatever it holds (a number, text, an object or a list), at any depth."""
    if isinstance(node, dict):
        return [name for key, value in node.items() for name in [str(key)] + _field_names(value)]
    if isinstance(node, list):
        return [name for value in node for name in _field_names(value)]
    return []


def _word_before(clause: str) -> Optional[str]:
    """The word that names the figure which follows `clause`: the last word, if only white space, a colon, an equals sign, a quotation mark and filler words lie after it.

    A comma, a bracket or another figure between the word and the figure means that the word belongs to something else:
    in "60 units invoiced, 100 units received" the word "invoiced" does not name 100.
    """
    for token in reversed(_TOKEN.findall(clause[-64:])):
        if token in (":", "=") or token in _QUOTES or token.lower() in _BETWEEN:
            continue
        return token if token[0].isalpha() else None
    return None


def _word_after(rest: str) -> Optional[str]:
    """The word that names the figure which precedes `rest`: the first word that is not a unit, a filler word or a quotation mark around the name
    ("60 units received", "60 units were received" and "100 units `quantity_received`" are about "received" and "quantity_received")."""
    for token in _TOKEN.findall(rest[:64]):
        if token.lower() in _UNITS or token.lower() in _BETWEEN or token in _QUOTES or token == "%":
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


def _index_names(records: List[object]) -> Dict[str, List[Tuple[str, Optional[Decimal]]]]:
    """Every field of the records, whatever it holds, filed under each word of its name: which fields exist, with no value to compare."""
    by_word: Dict[str, List[Tuple[str, Optional[Decimal]]]] = {}
    for record in records:
        for name in _field_names(record):
            for word in _name_words(name):
                filed = by_word.setdefault(_stem(word), [])
                if (name, None) not in filed:
                    filed.append((name, None))
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
    that nothing it cites gives it. This holds for every field of the record, whether it holds a number or not ("invoice_id 100"). A name that is a field
    of no payload is not judged, and a figure in `skip` has been reported already.
    """
    cited, known = _index_fields(payloads), _index_names(vocabulary)
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
                # The fields a claim can be about are those of the data the payload holds, and not the wrapper around it (its data type, its schema, its value).
                records.append(payload["value"] if isinstance(payload, dict) and "value" in payload else payload)
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
    """Agreement between derivations that share an origin is not independent corroboration.

    An origin is a root of the derivation: a record that names no parent. Wrappers that declare the same immutable source record are one origin (`origin_of`), whatever their C02 identities are.
    """
    out: List[Finding] = []
    d = pkt.data

    def origin_map(refs: List[dict]) -> Dict[tuple, List[Instance]]:
        found: Dict[tuple, List[Instance]] = {}
        for r in refs:
            rec = model.get("C02", r["record_id"], r["version"])
            if rec is not None:
                for identity, wrappers in origins(model, rec).items():
                    known = found.setdefault(identity, [])
                    known.extend(w for w in wrappers if all(w.key != other.key for other in known))
        return found

    def named(shared, *maps: Dict[tuple, List[Instance]]) -> str:
        return ", ".join(sorted(_origin_label(identity, [w for found in maps for w in found.get(identity, [])]) for identity in shared))

    inferences = d["labeled_inferences"]
    inference_origins = [origin_map(i["supporting_references"]) for i in inferences]
    for a in range(len(inferences)):
        for b in range(a + 1, len(inferences)):
            shared = inference_origins[a].keys() & inference_origins[b].keys()
            if not shared:
                continue
            for idx in (a, b):
                if not any("common origin" in l.lower() for l in inferences[idx]["limitations"]):
                    out.append(_f("COR002", "inferences %s and %s rest on the same origin (%s); each must say so in its limitations (\"common origin\")" % (
                        inferences[a]["inference_id"], inferences[b]["inference_id"], named(shared, inference_origins[a], inference_origins[b])),
                        pkt, "/labeled_inferences/%d/limitations" % idx, DOC_LINEAGE))
    items = [("/supported_claims_references/%d" % i, c["text"], c["supporting_references"]) for i, c in enumerate(d["supported_claims_references"])]
    items += [("/labeled_inferences/%d" % i, c["text"], c["supporting_references"]) for i, c in enumerate(inferences)]
    for loc, text, refs in items:
        lowered = text.lower()
        claims_it = re.search(r"\b(independent(ly)?|corroborat\w*)\b", lowered) and not re.search(r"\bnot\b[^.]{0,40}\b(independent|corroborat\w*)", lowered)
        if not claims_it:
            continue
        each = [origin_map([r]) for r in refs]
        shared = set.intersection(*[set(found) or {("record", "?", "?")} for found in each]) if refs else set()
        if len(refs) < 2 or shared:
            out.append(_f("COR001", "describes agreement as independent corroboration, but the cited records %s" % (
                "are fewer than two" if len(refs) < 2 else "share one origin (%s)" % named(shared, *each)), pkt, loc, DOC_LINEAGE))
    return out


# --------------------------------------------------------------------------- authority

GATE_CODE = re.compile(r"\b[A-Z]{3,}(?:_[A-Z]+)+\b")


def check_authority(model: Model) -> List[Finding]:
    out: List[Finding] = []
    chains = receipt_chains(model)
    out.extend(_check_attempt_identity(chains))
    leaving = {later.key: earlier for later, earlier in regressive_receipt_versions(model)}
    for receipt_id in sorted(chains):
        chain = in_order(chains[receipt_id])
        if chain is None:
            # While the order of the versions is not known (LIFE006 reports it), no version is the first and none comes after another: only what each version says on its own is judged.
            for rec in sorted(chains[receipt_id], key=lambda r: r.version):
                out.extend(_check_version(model, rec))
            continue
        first = chain[0]
        out.extend(_check_receipt(model, first, chain))
        for later in chain[1:]:
            out.extend(_check_receipt_chain(model, first, later))
            earlier = leaving.get(later.key)
            if earlier is not None:
                out.append(_f("ACC005", "this version says %s, but version %s of the receipt had already reached the verified outcome %s: a verified outcome closes the attempt, and a later version may repeat it "
                                        "but may not go back to an unresolved outcome or to the other verified one" % (later.data["outcome"]["state"], earlier.version, earlier.data["outcome"]["state"]), later, "/outcome/state", DOC_ACTION))
        out.extend(_check_verified_effects(chain))
        for rec in chain:
            out.extend(_check_version(model, rec))
    return out


def _check_version(model: Model, rec: Instance) -> List[Finding]:
    """What one version of a receipt says on its own: its accounting, what its verification rests on, and what its effects are for."""
    out: List[Finding] = []
    if rec.data["outcome"]["state"] in ("completed_verified", "not_executed_verified") and rec.data["verification_recovery"]["accounting"]["state"] != "reconciled":
        out.append(_f("ACC003", "a verified outcome settles its accounting: the state must be reconciled", rec, "/verification_recovery/accounting/state", DOC_ACTION))
    out.extend(_check_verification_binding(model, rec))
    out.extend(_check_effects_bound(rec))
    return out


def _check_effects_bound(rec: Instance) -> List[Finding]:
    """Each structured effect of a receipt is for the action and the target of that receipt, where the schema gives the effect those two bindings.

    An effect that names another action or another target is not an effect of this attempt, whatever the outcome says: the ledger does not count it (`gateway.effect_is_bound`), and the receipt
    is found here. Only the structured references are compared. What the free text of an effect says is not read.
    """
    out: List[Finding] = []
    binding = _object_of(rec.data.get("identity_binding"))
    for i, effect in enumerate(_list_of(_object_of(rec.data.get("outcome")).get("observed_effects"))):
        effect, name = _object_of(effect), "%s" % _object_of(effect).get("effect_id")
        here = "/outcome/observed_effects/%d" % i
        if not same_value(effect.get("action_reference"), binding.get("proposal_reference")) or not isinstance(effect.get("action_reference"), dict):
            out.append(_f("AUTH010", "effect %s is for %s, but the receipt is for the proposal %s: an effect is for the action of its receipt" % (
                name, _reference_name(effect.get("action_reference")), _reference_name(binding.get("proposal_reference"))), rec, here + "/action_reference", DOC_ACTION))
        if not same_value(effect.get("target"), binding.get("target")) or not isinstance(effect.get("target"), dict):
            out.append(_f("AUTH010", "effect %s is on %s, but the receipt is for the target %s: an effect is on the target of its receipt" % (
                name, _entity_name(effect.get("target")), _entity_name(binding.get("target"))), rec, here + "/target", DOC_ACTION))
    return out


def _reference_name(reference) -> str:
    reference = _object_of(reference)
    return "%s %s" % (reference.get("id"), reference.get("version"))


#: What a verified effect states that a later version of the receipt may not change: (field of the effect, how its values are compared).
EFFECT_FACTS = ("action_reference", "target", "quantity", "units", "observed_at", "accounting_reference")


def _check_verified_effects(chain: List[Instance]) -> List[Finding]:
    """An effect that a verified outcome has recorded stays as it was recorded: a later version of the receipt that repeats the verified outcome may repeat the effect and add others, not change it or leave it out.

    The first version of the receipt that is `completed_verified` or `not_executed_verified` closes the attempt (`regressive_receipt_versions`). Each of its effects is matched with the effects of a later
    version that repeats the same outcome by `effect_id`, and what it states about the action, the target, the quantity, the unit, the time it was observed and the accounting record it was charged to must be what
    it stated. Quantities are compared exactly and times as instants. An effect with another id is neither a correction nor a contradiction: no correction of a verified outcome is defined for ordinary versions.
    The free text (the description of an effect, the method of a verification) is not read, and neither is a version that is not a repeat of the verified outcome (ACC005 judges that).
    """
    out: List[Finding] = []
    closed = next((rec for rec in chain if _object_of(rec.data.get("outcome")).get("state") in TERMINAL_OUTCOMES), None)
    if closed is None:
        return out
    state = closed.data["outcome"]["state"]
    verified = {}
    for effect in map(_object_of, _list_of(closed.data["outcome"].get("observed_effects"))):
        if isinstance(effect.get("effect_id"), str):
            verified.setdefault(effect["effect_id"], effect)
    for later in chain[chain.index(closed) + 1:]:
        if _object_of(later.data.get("outcome")).get("state") != state:
            continue
        effects = [_object_of(e) for e in _list_of(later.data["outcome"].get("observed_effects"))]
        for name, effect in verified.items():
            repeats = [(j, e) for j, e in enumerate(effects) if e.get("effect_id") == name]
            if not repeats:
                out.append(_f("ACC006", "version %s repeats the verified outcome %s of version %s, but leaves out effect %s that version recorded: an effect that a verified outcome has recorded is not left out by a later version" % (
                    later.version, state, closed.version, name), later, "/outcome/observed_effects", DOC_ACTION))
            for j, repeated in repeats:
                for fact in EFFECT_FACTS:
                    same = same_instant(effect.get(fact), repeated.get(fact)) if fact == "observed_at" else same_value(effect.get(fact), repeated.get(fact))
                    if not same:
                        out.append(_f("ACC006", "version %s repeats the verified outcome %s of version %s, but changes the %s of effect %s from %s to %s: an effect that a verified outcome has recorded is not "
                                                "rewritten by a later version" % (later.version, state, closed.version, fact.replace("_", " "), name, _fact(effect.get(fact)), _fact(repeated.get(fact))),
                                      later, "/outcome/observed_effects/%d/%s" % (j, fact), DOC_ACTION))
    return out


def _fact(value) -> str:
    return json.dumps(value, sort_keys=True) if isinstance(value, (dict, list)) else str(value)


def _check_attempt_identity(chains: Dict[str, List[Instance]]) -> List[Finding]:
    """One execution attempt is described by one receipt (all of its versions): two receipts that claim the same `execution_attempt_id` describe it twice.

    The execution attempt id is the identity of the attempt, and the receipt id is not: the replay and the ledger count an attempt once, so receipts that share an attempt id are not separate attempts and
    are found in each of them, whether they agree about the proposal, the grant, the target and the time of the attempt or not. This is a statement about the receipts of the reference model: it does
    not say that nothing ran twice outside it. Versions of one receipt that name different attempts are ACC004.
    """
    out: List[Finding] = []
    claimed: Dict[str, Dict[str, List[Instance]]] = {}
    for receipt_id, versions in chains.items():
        for rec in versions:
            attempt = attempt_of(rec)
            if isinstance(attempt, str):
                claimed.setdefault(attempt, {}).setdefault(receipt_id, []).append(rec)

    def how(rec: Instance) -> dict:
        binding, outcome = _object_of(rec.data.get("identity_binding")), _object_of(rec.data.get("outcome"))
        return {"proposal": binding.get("proposal_reference"), "grant": binding.get("grant_reference"), "target": binding.get("target"), "submission time": _object_of(outcome.get("timestamps")).get("submitted")}

    def agree(name: str, first, second) -> bool:
        return same_instant(first, second) if name == "submission time" else same_value(first, second)

    for attempt, holders in sorted(claimed.items()):
        if len(holders) < 2:
            continue
        # The version that is read for a receipt is the first that carries the attempt, in the order of the versions where that is known and in the order of their names where it is not.
        read = {rid: next(rec for rec in (in_order(chains[rid]) or sorted(chains[rid], key=lambda r: r.version)) if attempt_of(rec) == attempt) for rid in holders}
        views = {rid: how(rec) for rid, rec in read.items()}
        for receipt_id in sorted(holders):
            others = [rid for rid in sorted(holders) if rid != receipt_id]
            differ = [name for name, value in views[receipt_id].items() if any(not agree(name, value, views[rid][name]) for rid in others)]
            out.append(_f("ACC007", "the execution attempt %s is also claimed by receipt %s: an attempt is one execution attempt id, so receipts that share it describe one attempt and not several; %s" % (
                attempt, " and ".join(others), "they disagree about the " + ", ".join(differ) if differ else "they agree about the proposal, the grant, the target and the time of the attempt"),
                          read[receipt_id], "/identity_binding/execution_attempt_id", DOC_ACTION))
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


def _list_of(value) -> list:
    return value if isinstance(value, list) else []


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
    submitted = d["outcome"]["timestamps"]["submitted"]
    at = parse_time(submitted)
    for version in versions:
        # The attempt is the same in every version, so the submission time of every version must be one that can be compared exactly. A later version with a time
        # that cannot be read is an input that cannot be judged (INP002), the same as the first, and not a receipt that merely differs. This is read before
        # anything is looked up, so that a reference that does not resolve cannot hide it.
        stated = version.data["outcome"]["timestamps"]["submitted"]
        if parse_time(stated) is None:
            raise ValueError("%s: receipt %s %s has a submission time (%r) that is not an RFC 3339 time with a zone and at most six fractional digits, so the attempt it describes "
                             "cannot be compared with the grant and the evidence exactly. Correct the time" % (version.file, version.id, version.version, stated))
    pref, gref = d["identity_binding"]["proposal_reference"], d["identity_binding"]["grant_reference"]
    prop, grant = model.get("C05", pref["id"], pref["version"]), model.get("C06", gref["id"], gref["version"])
    if prop is None or grant is None:
        return out
    # A receipt is for the target its proposal names. A verification can show only what happened to the receipt's own target, so a
    # receipt that names another target would carry a verified outcome for something the action never concerned.
    named, proposed = d["identity_binding"].get("target"), _object_of(prop.data["action"]).get("exact_target")
    if named != proposed:
        out.append(_f("AUTH009", "the receipt says the attempt concerned %s, but the proposal it executes names %s: a receipt is for the target of its proposal" % (_entity_name(named), _entity_name(proposed)), rec, "/identity_binding/target", DOC_ACTION))
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
    # The same instant written another way (Z or +00:00, with or without a zero fraction) is the same attempt: instants are compared, not their spelling.
    if not same_instant(first_submitted, later_submitted):
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
