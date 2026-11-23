"""Gateway scenarios: stored what-if evaluations of the reference commit check, replayed and compared with what was recorded.

A scenario entry names a proposal and a grant (by id and version), a commit time, optional in-memory overrides
(a counterfactual: "what if the revocation check had failed?") and the expected decision. Nothing is executed;
the overrides never touch the committed example files.
"""
from __future__ import annotations

from typing import List

from .findings import Finding, rel
from .gateway import Decision, evaluate_commit, ledger_from_receipts, ts
from .model import Instance, Model
from .patch import apply_ops

DOC = "architecture/action-and-degradation.md"


def apply_overrides(data: dict, overrides: List[dict], which: str) -> dict:
    ops = [{"op": "replace", "path": item["path"], "value": item["value"]} for item in overrides if item["on"] == which]
    return apply_ops(data, ops)


def evaluate_entry(model: Model, entry: dict) -> Decision:
    p_ref, g_ref = entry["proposal"], entry["grant"]
    proposal = model.get("C05", p_ref["id"], p_ref["version"])
    grant = model.get("C06", g_ref["id"], g_ref["version"])
    if proposal is None or grant is None:
        raise KeyError("scenario names %s %s or %s %s, which do not exist" % (p_ref["id"], p_ref["version"], g_ref["id"], g_ref["version"]))
    overrides = entry.get("overrides", [])
    proposal = Instance(proposal.contract, proposal.id, proposal.version, apply_overrides(proposal.data, overrides, "proposal"), proposal.path)
    grant = Instance(grant.contract, grant.id, grant.version, apply_overrides(grant.data, overrides, "grant"), grant.path)
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
    for entry in data.get("evaluations", []):
        label = entry.get("label", "?")
        try:
            actual = expectation(evaluate_entry(model, entry))
        except (KeyError, ValueError, IndexError, TypeError) as exc:
            findings.append(Finding("GW002", "%s: cannot evaluate (%s)" % (label, exc), file, doc=DOC))
            continue
        expected = entry.get("expect", {})
        if actual["decision"] != expected.get("decision") or actual["codes"] != expected.get("codes"):
            findings.append(Finding(
                "GW001", "%s: expected %s %s but the check now gives %s %s" % (label, expected.get("decision"), expected.get("codes"), actual["decision"], actual["codes"]),
                file, doc=DOC))
    return findings
