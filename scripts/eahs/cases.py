"""Evaluation cases: mutated copies of the example set, each with the check codes it must produce.

Every case copies the (valid) example set in memory, applies a small, named mutation, runs the same schema and
semantic checks as `validate_examples.py`, and requires that the findings are exactly the codes the case declares.
The committed example files are never changed.

These are deterministic functional checks on synthetic data. They are not the EV01-EV12 evaluation programme,
which has not been run, and a passing case set says nothing about any real system.
"""
from __future__ import annotations

from typing import Dict, List, Tuple

from .findings import Finding, rel
from .model import Instance, Model
from .patch import apply_ops
from .schema import validate_instance

DOC = "evaluation/README.md"


def _parse_target(target: str) -> Tuple[str, str, str]:
    contract, ident, version = target.split()
    return contract, ident, version


def mutate_model(model: Model, mutations: List[dict]) -> Tuple[Model, List[Instance]]:
    instances: Dict = dict(model.instances)
    changed: List[Instance] = []
    for mutation in mutations:
        key = _parse_target(mutation["target"])
        base = instances[key]
        new = Instance(base.contract, base.id, base.version, apply_ops(base.data, mutation["ops"]), base.path)
        instances[key] = new
        changed.append(new)
    return Model(instances, model.registry, model.root), changed


def run_case(model: Model, schema: dict, case: dict) -> Tuple[List[str], List[Finding]]:
    from . import semantics
    mutated, changed = mutate_model(model, case["mutations"])
    schema_findings: List[Finding] = []
    for inst in changed:
        schema_findings += validate_instance(schema, inst.data, inst.file)
    if schema_findings:
        return sorted({f.code for f in schema_findings}), schema_findings
    findings = semantics.run_all(mutated)
    return sorted({f.code for f in findings}), findings


def check_cases(model: Model, schema: dict, data: dict, path) -> Tuple[List[Finding], int]:
    problems: List[Finding] = []
    file = rel(path)
    cases = data.get("cases", [])
    seen = set()
    for case in cases:
        case_id = case.get("case_id", "?")
        if case_id in seen:
            problems.append(Finding("CASE002", "duplicate case id %s" % case_id, file, doc=DOC))
        seen.add(case_id)
        try:
            codes, _ = run_case(model, schema, case)
        except (KeyError, IndexError, ValueError, TypeError) as exc:
            problems.append(Finding("CASE003", "%s: the mutation could not be applied (%s)" % (case_id, exc), file, doc=DOC))
            continue
        if codes != sorted(case["expect"]):
            problems.append(Finding("CASE001", "%s: expected %s but the checks produced %s" % (case_id, sorted(case["expect"]), codes), file, doc=DOC))
    return problems, len(cases)
