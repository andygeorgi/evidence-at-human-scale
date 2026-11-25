"""Evaluation cases: mutated copies of the example set, each with the check codes it must produce.

Every case copies the (valid) example set in memory, applies a small, named mutation, runs the same schema and
semantic checks as `validate_examples.py`, and requires that the findings are exactly the codes the case declares.
The committed example files are never changed.

These are deterministic functional checks on synthetic data. They are not the EV01-EV12 evaluation programme,
which has not been run, and a passing case set says nothing about any real system.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from .findings import DescribedIndexError, DescribedKeyError, DescribedTypeError, Finding, InputProblem, describe_error, rel
from .model import Instance, Model
from .patch import apply_ops, pointer_problem
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
        base = instances.get(key)
        if base is None:
            raise DescribedKeyError("%s is not in the example set, so it cannot be changed" % mutation["target"])
        try:
            data = apply_ops(base.data, mutation["ops"])
        except (DescribedKeyError, DescribedIndexError, DescribedTypeError, ValueError) as exc:
            raise type(exc)("%s, %s" % (mutation["target"], exc)) from None
        new = Instance(base.contract, base.id, base.version, data, base.path)
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


OPERATIONS = ("replace", "add", "remove")


def _mutation_problem(name: str, position: int, mutation) -> str:
    """Why a mutation cannot be applied because of its shape, or an empty string. A target that does not exist is a finding of the case (CASE003), not a shape."""
    where = "%s, mutation %d" % (name, position + 1)
    if not isinstance(mutation, dict):
        return "%s is not an object" % where
    target = mutation.get("target")
    if not isinstance(target, str) or len(target.split()) != 3:
        return "%s has no 'target' of the form \"C05 ACT-REL-0417 v2\" (a contract, an id and a version)" % where
    ops = mutation.get("ops")
    if not isinstance(ops, list) or not ops:
        return "%s has no 'ops' list of operations" % where
    for number, op in enumerate(ops):
        if not isinstance(op, dict) or op.get("op") not in OPERATIONS or not isinstance(op.get("path"), str):
            return "%s, operation %d needs an 'op' (one of %s) and a 'path' (a JSON pointer)" % (where, number + 1, ", ".join(OPERATIONS))
        if op["op"] != "remove" and "value" not in op:
            return "%s, operation %d (%s) needs a 'value'" % (where, number + 1, op["op"])
        problem = pointer_problem(op["path"])
        if problem:
            return "%s, operation %d has the path %r, which is not a JSON pointer: %s" % (where, number + 1, op["path"], problem)
    return ""


def _case_problem(index: int, case) -> str:
    """Why a case cannot be run because of its shape, or an empty string. Every part the case is judged by must be there: nothing is assumed."""
    if not isinstance(case, dict):
        return "case %d is not an object" % (index + 1)
    name = case.get("case_id")
    if not isinstance(name, str) or not name.strip():
        return "case %d has no 'case_id' (a text that names it)" % (index + 1)
    expect = case.get("expect")
    if not isinstance(expect, list) or not all(isinstance(code, str) for code in expect):
        return "%s has no 'expect' list of the codes (text) it must produce" % name
    mutations = case.get("mutations")
    if not isinstance(mutations, list):
        return "%s has no 'mutations' list" % name
    if not mutations:
        return "%s has no mutation: a case that changes nothing is not a mutated copy, and the unchanged example set is what the instance stage already checks" % name
    for position, mutation in enumerate(mutations):
        problem = _mutation_problem(name, position, mutation)
        if problem:
            return problem
    return ""


CASES_HINT = ("give every case a case_id, an 'expect' list of codes (a [] means the case must produce no finding) and a non-empty 'mutations' list of {target, ops}; "
              "nothing in this file was evaluated")


def rows_problem(data) -> Optional[InputProblem]:
    """The first case of a case file that cannot be run because of its shape, as the input problem to report, or None.

    Nothing about the model is needed to see that, so a file whose rows are malformed is reported also when the model cannot be built. A document that is not an
    object with a list of cases is one too: a caller that reaches this check with such a document is told so, and is not left to fail on the first row.
    """
    cases = data.get("cases") if isinstance(data, dict) else None
    if not isinstance(cases, list):
        return InputProblem("a case file must be an object with a 'cases' list, and this document has none", CASES_HINT)
    for index, case in enumerate(cases):
        reason = _case_problem(index, case)
        if reason:
            return InputProblem(reason, CASES_HINT)
    return None


def check_cases(model: Model, schema: dict, data: dict, path) -> Tuple[List[Finding], int]:
    problems: List[Finding] = []
    file = rel(path)
    problem = rows_problem(data)
    if problem is not None:
        raise problem
    cases = data["cases"]
    seen = set()
    for case in cases:
        case_id = case.get("case_id", "?")
        if case_id in seen:
            problems.append(Finding("CASE002", "duplicate case id %s" % case_id, file, doc=DOC))
        seen.add(case_id)
        try:
            codes, _ = run_case(model, schema, case)
        except (KeyError, IndexError, ValueError, TypeError) as exc:
            problems.append(Finding("CASE003", "%s: the mutation could not be applied (%s)" % (case_id, describe_error(exc)), file, doc=DOC))
            continue
        if codes != sorted(case["expect"]):
            problems.append(Finding("CASE001", "%s: expected %s but the checks produced %s" % (case_id, sorted(case["expect"]), codes), file, doc=DOC))
    return problems, len(cases)
