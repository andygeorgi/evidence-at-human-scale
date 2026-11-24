"""Gateway scenarios: stored what-if evaluations of the reference commit check, replayed and compared with what was recorded.

A scenario entry names a proposal and a grant (by id and version), a commit time, optional in-memory overrides
(a counterfactual: "what if the revocation check had failed?") and the expected decision. An override acts on the
proposal, on the grant, or on one evidence record (`"on": "evidence"`, with a `record` that names its id and version).
Nothing is executed; the overrides never touch the committed example files.
"""
from __future__ import annotations

from dataclasses import replace
from typing import List

from .findings import Finding, describe_error, rel
from .gateway import Decision, evaluate_commit, ledger_from_receipts, ts
from .model import Instance, Model
from .patch import apply_ops

DOC = "architecture/action-and-degradation.md"


def apply_overrides(data: dict, overrides: List[dict], which: str) -> dict:
    ops = [{"op": "replace", "path": item["path"], "value": item["value"]} for item in overrides if item["on"] == which]
    return apply_ops(data, ops)


def with_evidence_overrides(model: Model, overrides: List[dict]) -> Model:
    """A copy of the model in which the evidence records named by `"on": "evidence"` overrides carry the overridden values."""
    instances = dict(model.instances)
    for item in overrides:
        if item["on"] != "evidence":
            continue
        ref = item["record"]
        key = ("C02", ref["id"], ref["version"])
        rec = instances.get(key)
        if rec is None:
            raise KeyError("scenario overrides evidence %s %s, which does not exist" % (ref["id"], ref["version"]))
        data = apply_ops(rec.data, [{"op": "replace", "path": item["path"], "value": item["value"]}])
        instances[key] = Instance(rec.contract, rec.id, rec.version, data, rec.path)
    return replace(model, instances=instances)


def evaluate_entry(model: Model, entry: dict) -> Decision:
    p_ref, g_ref = entry["proposal"], entry["grant"]
    proposal = model.get("C05", p_ref["id"], p_ref["version"])
    grant = model.get("C06", g_ref["id"], g_ref["version"])
    if proposal is None or grant is None:
        raise KeyError("scenario names %s %s or %s %s, which do not exist" % (p_ref["id"], p_ref["version"], g_ref["id"], g_ref["version"]))
    overrides = entry.get("overrides", [])
    proposal = Instance(proposal.contract, proposal.id, proposal.version, apply_overrides(proposal.data, overrides, "proposal"), proposal.path)
    grant = Instance(grant.contract, grant.id, grant.version, apply_overrides(grant.data, overrides, "grant"), grant.path)
    model = with_evidence_overrides(model, overrides)
    when = ts(entry["at"])
    ledger = ledger_from_receipts(model, when) if entry.get("ledger", "from_receipts") == "from_receipts" else []
    return evaluate_commit(model, proposal, grant, when, ledger)


def unique(codes: List[str]) -> List[str]:
    seen: List[str] = []
    for code in codes:
        if code not in seen:
            seen.append(code)
    return seen


def expectation(decision: Decision) -> dict:
    return {"decision": "ALLOW" if decision.allow else "BLOCK", "codes": unique(decision.codes), "reasons": [r.as_dict() for r in decision.reasons]}


def check_scenario_file(model: Model, data: dict, path) -> List[Finding]:
    findings: List[Finding] = []
    file = rel(path)
    for index, entry in enumerate(data.get("evaluations", [])):
        if not isinstance(entry, dict):
            findings.append(Finding("GW002", "evaluation %d is not an object, so it cannot be evaluated" % (index + 1), file, "/evaluations/%d" % index, doc=DOC,
                                    hint="write each evaluation as an object with a proposal, a grant, a time and the expected decision"))
            continue
        label = entry.get("label", "evaluation %d" % (index + 1))
        try:
            actual = expectation(evaluate_entry(model, entry))
        except (KeyError, ValueError, IndexError, TypeError, AttributeError) as exc:
            findings.append(Finding("GW002", "%s: cannot evaluate (%s)" % (label, describe_error(exc)), file, "/evaluations/%d" % index, doc=DOC,
                                    hint="check that the proposal, the grant, the time and any overrides of this evaluation exist and are well formed"))
            continue
        expected = entry.get("expect", {})
        if actual["decision"] != expected.get("decision") or actual["codes"] != expected.get("codes"):
            findings.append(Finding(
                "GW001", "%s: expected %s %s but the check now gives %s %s" % (label, expected.get("decision"), expected.get("codes"), actual["decision"], actual["codes"]),
                file, "/evaluations/%d" % index, doc=DOC))
    return findings
