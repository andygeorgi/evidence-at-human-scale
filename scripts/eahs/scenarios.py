"""Gateway scenarios: stored what-if evaluations of the reference commit check, replayed and compared with what was recorded.

A scenario entry names a proposal and a grant (by id and version), a commit time, optional in-memory overrides
(a counterfactual: "what if the revocation check had failed?") and the expected decision. An override acts on the
proposal, on the grant, or on one evidence record (`"on": "evidence"`, with a `record` that names its id and version).
Nothing is executed; the overrides never touch the committed example files.
"""
from __future__ import annotations

from dataclasses import replace
from typing import List, Optional

from .findings import DescribedIndexError, DescribedKeyError, DescribedTypeError, Finding, InputProblem, describe_error, rel
from .gateway import Decision, attempt_receipt_ids, evaluate_commit, ledger_from_receipts, parse_time, ts
from .model import Instance, Model
from .patch import apply_ops, pointer_problem

DOC = "architecture/action-and-degradation.md"


def apply_overrides(data: dict, overrides: List[dict], which: str) -> dict:
    out = apply_ops(data, [])   # a copy: the stored record is never changed
    for position, item in enumerate(overrides, 1):
        if item["on"] != which:
            continue
        try:
            out = apply_ops(out, [{"op": "replace", "path": item["path"], "value": item["value"]}])
        except (DescribedKeyError, DescribedIndexError, DescribedTypeError) as exc:
            raise type(exc)("override %d (on %s), %s" % (position, which, exc)) from None
        except ValueError as exc:
            raise ValueError("override %d (on %s), %s" % (position, which, exc)) from None
    return out


def with_evidence_overrides(model: Model, overrides: List[dict]) -> Model:
    """A copy of the model in which the evidence records named by `"on": "evidence"` overrides carry the overridden values."""
    instances = dict(model.instances)
    for position, item in enumerate(overrides, 1):
        if item["on"] != "evidence":
            continue
        ref = item["record"]
        key = ("C02", ref["id"], ref["version"])
        rec = instances.get(key)
        if rec is None:
            raise DescribedKeyError("override %d (on evidence) names %s %s, which does not exist" % (position, ref["id"], ref["version"]))
        try:
            data = apply_ops(rec.data, [{"op": "replace", "path": item["path"], "value": item["value"]}])
        except (DescribedKeyError, DescribedIndexError, DescribedTypeError) as exc:
            raise type(exc)("override %d (on evidence %s %s), %s" % (position, ref["id"], ref["version"], exc)) from None
        except ValueError as exc:
            raise ValueError("override %d (on evidence %s %s), %s" % (position, ref["id"], ref["version"], exc)) from None
        instances[key] = Instance(rec.contract, rec.id, rec.version, data, rec.path)
    return replace(model, instances=instances)


def evaluate_entry(model: Model, entry: dict) -> Decision:
    p_ref, g_ref = entry["proposal"], entry["grant"]
    proposal = model.get("C05", p_ref["id"], p_ref["version"])
    grant = model.get("C06", g_ref["id"], g_ref["version"])
    if proposal is None or grant is None:
        missing = [name for name, found in (("proposal %s %s" % (p_ref["id"], p_ref["version"]), proposal), ("grant %s %s" % (g_ref["id"], g_ref["version"]), grant)) if found is None]
        raise DescribedKeyError("the scenario names %s, which %s not exist" % (" and ".join(missing), "does" if len(missing) == 1 else "do"))
    overrides = entry.get("overrides", [])
    proposal = Instance(proposal.contract, proposal.id, proposal.version, apply_overrides(proposal.data, overrides, "proposal"), proposal.path)
    grant = Instance(grant.contract, grant.id, grant.version, apply_overrides(grant.data, overrides, "grant"), grant.path)
    model = with_evidence_overrides(model, overrides)
    when = ts(entry["at"])
    ledger = ledger_from_receipts(model, when, exclude_receipt_ids=attempt_receipt_ids(model, proposal, grant, when)) if entry.get("ledger", "from_receipts") == "from_receipts" else []
    return evaluate_commit(model, proposal, grant, when, ledger)


def unique(codes: List[str]) -> List[str]:
    seen: List[str] = []
    for code in codes:
        if code not in seen:
            seen.append(code)
    return seen


def expectation(decision: Decision) -> dict:
    return {"decision": "ALLOW" if decision.allow else "BLOCK", "codes": unique(decision.codes), "reasons": [r.as_dict() for r in decision.reasons]}


LEDGER_MODES = ("from_receipts", "empty")
OVERRIDE_TARGETS = ("proposal", "grant", "evidence")


def _override_problem(name: str, position: int, item) -> str:
    where = "%s, override %d" % (name, position + 1)
    if not isinstance(item, dict):
        return "%s is not an object" % where
    if item.get("on") not in OVERRIDE_TARGETS:
        return "%s acts on %r, which is not one of %s: an override that names no target would be ignored" % (where, item.get("on"), ", ".join(OVERRIDE_TARGETS))
    if not isinstance(item.get("path"), str) or "value" not in item:
        return "%s needs a 'path' (a JSON pointer) and a 'value'" % where
    problem = pointer_problem(item["path"])
    if problem:
        return "%s has the path %r, which is not a JSON pointer: %s" % (where, item["path"], problem)
    if item["on"] == "evidence":
        record = item.get("record")
        if not (isinstance(record, dict) and isinstance(record.get("id"), str) and isinstance(record.get("version"), str)):
            return "%s acts on evidence, so it needs a 'record' with the id and the version of that record" % where
    return ""


def _entry_problem(index: int, entry) -> str:
    """Why an evaluation cannot be run because of its shape, or an empty string. A row that is not shaped like an evaluation is
    malformed input, not an evaluation that failed: there is nothing to evaluate. Nothing a row says may be ignored silently."""
    if not isinstance(entry, dict):
        return "evaluation %d is not an object" % (index + 1)
    name = entry["label"] if isinstance(entry.get("label"), str) and entry["label"].strip() else "evaluation %d" % (index + 1)
    for key in ("proposal", "grant"):
        ref = entry.get(key)
        if not (isinstance(ref, dict) and isinstance(ref.get("id"), str) and isinstance(ref.get("version"), str)):
            return "%s has no %r reference with an id and a version" % (name, key)
    if not isinstance(entry.get("at"), str):
        return "%s has no commit time 'at'" % name
    if parse_time(entry["at"]) is None:
        return "%s has a commit time 'at' (%r) that is not an RFC 3339 time with a zone, so the moment of the attempt cannot be established" % (name, entry["at"])
    if entry.get("ledger", "from_receipts") not in LEDGER_MODES:
        return "%s names the ledger %r, which this check does not know (use %s): another value would count no capacity at all" % (name, entry.get("ledger"), " or ".join(LEDGER_MODES))
    overrides = entry.get("overrides", [])
    if not isinstance(overrides, list):
        return "%s has an 'overrides' that is not a list" % name
    for position, item in enumerate(overrides):
        problem = _override_problem(name, position, item)
        if problem:
            return problem
    expect = entry.get("expect")
    if not (isinstance(expect, dict) and expect.get("decision") in ("ALLOW", "BLOCK") and isinstance(expect.get("codes"), list) and all(isinstance(code, str) for code in expect["codes"])):
        return "%s has no 'expect' object with its decision (ALLOW or BLOCK) and the list of codes (text) it must produce" % name
    return ""


SCENARIO_HINT = ("write each evaluation as an object with a proposal and a grant (each with an id and a version), a commit time 'at' and an 'expect' object; "
                 "nothing in this file was evaluated")


def rows_problem(data) -> Optional[InputProblem]:
    """The first evaluation of a scenario file that cannot be run because of its shape, as the input problem to report, or None.

    Nothing about the model is needed to see that, so a file whose rows are malformed is reported also when the model cannot be built. A document that is not an
    object with a list of evaluations is one too: a caller that reaches this check with such a document is told so, and is not left to fail on the first row.
    """
    evaluations = data.get("evaluations") if isinstance(data, dict) else None
    if not isinstance(evaluations, list):
        return InputProblem("a scenario file must be an object with an 'evaluations' list, and this document has none", SCENARIO_HINT)
    for index, entry in enumerate(evaluations):
        reason = _entry_problem(index, entry)
        if reason:
            return InputProblem(reason, SCENARIO_HINT)
    return None


def check_scenario_file(model: Model, data: dict, path) -> List[Finding]:
    findings: List[Finding] = []
    file = rel(path)
    problem = rows_problem(data)
    if problem is not None:
        raise problem
    evaluations = data["evaluations"]
    for index, entry in enumerate(evaluations):
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
