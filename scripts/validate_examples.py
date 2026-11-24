#!/usr/bin/env python3
"""Validate the synthetic example set: schemas, scenario semantics, gateway scenarios, responses and evaluation cases.

    python scripts/validate_examples.py              # everything
    python scripts/validate_examples.py --verbose    # what each stage evaluated
    python scripts/validate_examples.py --json       # machine-readable result
    python scripts/validate_examples.py --only schema,semantics
    python scripts/validate_examples.py --skip cases

Every stage ends in one of five states. A stage passes only if it evaluated at least one item and every check passed.

    PASS          at least one relevant item was evaluated and every required check passed
    FAIL          evaluated content breaks a rule
    SKIPPED       the stage was left out on purpose (--only, --skip)
    NOT ASSESSED  the input the stage needs does not exist, so nothing was evaluated
    INPUT ERROR   the input is malformed or incomplete and cannot support the stage

The exit code is 0 for PASS, 1 for FAIL, 2 for INPUT ERROR (also when the command itself cannot run) and 3 for NOT ASSESSED.
A run in which nothing passed and nothing failed, for example an empty folder, is NOT ASSESSED, never PASS.

Every input is evaluated or explicitly rejected. A top-level contract_id must be a string that names C01-C07, a file named
like a contract instance must be one, and a stage file must hold the list its stage evaluates (a missing list is an input
error, an explicitly empty one evaluates nothing). Raw source exports are read as non-contract input. A schema-only run
(--only schema) does not index the folder.

A pass shows that the synthetic examples are structurally valid and internally coherent, and that the deterministic
checks behave as documented. It does not show that any real system, model or process is accountable, safe or correct.
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import sys
import time
from dataclasses import replace
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Set

sys.path.insert(0, str(Path(__file__).resolve().parent))

try:
    import jsonschema  # noqa: F401
except ImportError:  # pragma: no cover - environment problem, not a validation result
    sys.stderr.write("INPUT ERROR: this command needs one third-party package: pip install -r requirements.txt\n")
    sys.exit(2)

from jsonschema.exceptions import SchemaError  # noqa: E402

from eahs import REPO_ROOT, __version__  # noqa: E402
from eahs import semantics  # noqa: E402
from eahs.cases import check_cases  # noqa: E402
from eahs.findings import Finding, InputProblem, describe_error, rel  # noqa: E402
from eahs.model import Model, Registry, load_model  # noqa: E402
from eahs.response import check_response, is_canonical  # noqa: E402
from eahs.scenarios import check_scenario_file  # noqa: E402
from eahs.schema import check_embedded_examples, check_schema_itself, load_schema, validate_instance  # noqa: E402
from eahs.status import (EXIT_CODES, FAIL, INPUT_ERROR, NEXT_STEP, NOT_ASSESSED, PASS, SKIPPED, StageResult,  # noqa: E402
                         input_finding, overall)

STAGES = ["schema", "instances", "semantics", "gateway", "responses", "cases"]
TITLES = {"schema": "Schema bundle", "instances": "Example instances", "semantics": "Scenario semantics",
          "gateway": "Gateway scenarios", "responses": "Assistant responses", "cases": "Evaluation cases"}
#: The stages that read the model need structurally valid instances; a stage that was selected pulls its prerequisite in.
PREREQUISITES = {"semantics": "instances", "gateway": "instances", "responses": "instances", "cases": "instances"}
#: The stages that read rules from registry.json; without it they have nothing to check against.
REGISTRY_STAGES = {"semantics", "gateway", "cases"}
#: What a malformed document typically raises inside a check. These become an INPUT ERROR with a diagnostic, not a traceback.
DOCUMENT_ERRORS = (KeyError, IndexError, TypeError, ValueError, AttributeError)
#: Stage files that are neither contract instances nor raw exports: each is read by the stage named here, not by the instances stage.
STAGE_FILES = {"gateway-scenarios.json": "gateway", "cases.json": "cases", "response-*.json": "responses"}


def _kind(value) -> str:
    return {list: "a list", dict: "an object", str: "a string", int: "a number", float: "a number", bool: "true or false", type(None): "null"}.get(type(value), type(value).__name__)


def is_stage_file(name: str) -> bool:
    return any(fnmatch.fnmatch(name.lower(), pattern) for pattern in STAGE_FILES)


class Run:
    """One validation run over a folder: loads the schema once, indexes the folder only when a stage needs it, then evaluates the stages."""

    def __init__(self, root: Path, debug: bool = False):
        self.root = root
        self.debug = debug
        self.results: Dict[str, StageResult] = {}
        self.schema: Optional[dict] = None
        self.schema_problem: Optional[Finding] = None
        try:
            self.schema = load_schema()
        except (OSError, ValueError) as exc:
            self.schema_problem = input_finding("INP001", "cannot read the schema bundle: %s" % exc, "schemas/contracts-v1.schema.json",
                                                "restore schemas/contracts-v1.schema.json from the repository")
        self._indexed = False
        self._model: Optional[Model] = None
        self._load_findings: List[Finding] = []

    # ------------------------------------------------------------------ the model, indexed on first use
    def _index(self) -> None:
        """Index the folder once. A schema-only run never gets here, so a file the model cannot index cannot disturb it."""
        if self._indexed:
            return
        self._indexed = True
        if self.schema is None:
            return
        try:
            self._model, self._load_findings = load_model(self.root)
        except DOCUMENT_ERRORS as exc:
            if self.debug:
                raise
            self._model = Model({}, Registry(), self.root)
            self._load_findings = [input_finding("INP002", "the folder cannot be indexed: %s" % describe_error(exc), rel(self.root),
                                                 "look for a JSON file whose top-level structure is not an object; run with --debug for the traceback")]

    @property
    def model(self) -> Optional[Model]:
        self._index()
        return self._model

    @property
    def load_findings(self) -> List[Finding]:
        self._index()
        return self._load_findings

    # ------------------------------------------------------------------ helpers
    def result(self, stage: str, status: str, evaluated: int = 0, findings: Optional[List[Finding]] = None, detail: str = "") -> StageResult:
        """A stage's result. Every finding in it names the stage, so a diagnostic always says where it was found."""
        return StageResult(stage, TITLES[stage], status, evaluated, [replace(f, stage=f.stage or stage) for f in findings or []], detail)

    def blocked(self, stage: str) -> Optional[StageResult]:
        """A stage that reads the model cannot run unless the instances stage passed."""
        needed = PREREQUISITES.get(stage)
        if needed is None:
            return None
        if self.schema_problem is not None:
            return self.result(stage, INPUT_ERROR, findings=[self.schema_problem], detail="the schema bundle cannot be read")
        base = self.results.get(needed)
        if base is not None and base.status == PASS:
            registry = self.root / "registry.json"
            if stage in REGISTRY_STAGES and not registry.is_file():
                return self.result(stage, INPUT_ERROR, findings=[input_finding("INP003", "the registry is missing: %s does not exist" % rel(registry), rel(registry),
                                                                               "add registry.json (its layout is in examples/registry.json), or run only the stages that do not read it")],
                                   detail="the registry this stage reads does not exist")
            return None
        state = base.status if base is not None else "not run"
        return self.result(stage, NOT_ASSESSED, detail="blocked: the %s stage ended %s, and this stage needs structurally valid instances" % (needed, state))

    def files(self, pattern: str) -> List[Path]:
        """Every file below the folder whose name matches `pattern`, ignoring case, so that the answer does not depend on the platform."""
        return sorted(p for p in self.root.rglob("*.json") if fnmatch.fnmatch(p.name.lower(), pattern.lower()))

    def read_json(self, path: Path):
        try:
            return json.loads(path.read_text(encoding="utf-8")), None
        except (OSError, ValueError) as exc:
            return None, input_finding("ID000", "cannot read JSON: %s" % exc, rel(path), "repair or remove the file")

    def bad_document(self, stage: str, path: Path, exc: Exception) -> Finding:
        hint = exc.hint if isinstance(exc, InputProblem) and exc.hint else "the document lacks a structure the checks read; compare it with the example it is modelled on"
        return input_finding("INP002", "the %s stage cannot evaluate this document: %s" % (stage, describe_error(exc)), rel(path), hint)

    def collection_problem(self, stage: str, path: Path, data, collection: str, what: str) -> Optional[Finding]:
        """A stage file must be an object that holds the list the stage evaluates. A missing list is an input error; an empty one is not."""
        if not isinstance(data, dict):
            return input_finding("INP002", "the %s stage cannot evaluate this document: %s must be a JSON object with a %r list, and this file holds %s" % (stage, what, collection, _kind(data)), rel(path),
                                 "write the document as an object with a %r list" % collection)
        if collection not in data:
            return input_finding("INP002", "the %s stage cannot evaluate this document: %s has no %r list, so there is nothing to evaluate in it" % (stage, what, collection), rel(path),
                                 "add a %r list; write [] only if the file is meant to hold none" % collection)
        if not isinstance(data[collection], list):
            return input_finding("INP002", "the %s stage cannot evaluate this document: %r must be a list, and this file holds %s" % (stage, collection, _kind(data[collection])), rel(path),
                                 "make %r a list of objects" % collection)
        return None

    def collect(self, stage: str, pattern: str, evaluate, summary, collection: Optional[str] = None, what: str = "the document", empty_is_evaluated: bool = False) -> StageResult:
        """Run `evaluate(path, data) -> (findings, count)` over every file that matches, and settle the state.

        With `collection`, each file must hold that list: a file without it is an input error (it would otherwise be
        read as empty), and a file whose list is explicitly empty evaluates nothing and says so. A document that is
        itself the item evaluated (a response) is evaluated even when its list is empty, and its checks decide.
        """
        paths = self.files(pattern)
        if not paths:
            return self.result(stage, NOT_ASSESSED, detail="no %s found under %s: nothing was evaluated" % (pattern, rel(self.root)))
        findings: List[Finding] = []
        problems: List[Finding] = []
        empty: List[str] = []
        count = 0
        for path in paths:
            data, problem = self.read_json(path)
            if problem is None and collection is not None:
                problem = self.collection_problem(stage, path, data, collection, what)
            if problem is not None:
                problems.append(problem)
                continue
            if collection is not None and not data[collection] and not empty_is_evaluated:
                empty.append(rel(path))
            try:
                found, n = evaluate(path, data)
            except (InputProblem,) + DOCUMENT_ERRORS as exc:
                if self.debug and not isinstance(exc, InputProblem):
                    raise
                problems.append(self.bad_document(stage, path, exc))
                continue
            findings += found
            count += n
        note = "; %d file(s) hold an explicitly empty %r list and evaluated nothing: %s" % (len(empty), collection, ", ".join(empty)) if empty else ""
        if problems:
            return self.result(stage, INPUT_ERROR, count, problems + findings, "%d file(s) could not be evaluated%s" % (len(problems), note))
        if count == 0:
            return self.result(stage, NOT_ASSESSED, 0, findings, "%d %s file(s) found, but they hold nothing to evaluate%s" % (len(paths), pattern, note))
        result = self.result(stage, FAIL if findings else PASS, count, findings)
        if result.status == PASS:
            result.detail = summary(result) + note
        return result

    # ------------------------------------------------------------------ stages
    def stage_schema(self) -> StageResult:
        if self.schema_problem is not None:
            return self.result("schema", INPUT_ERROR, findings=[self.schema_problem], detail="the schema bundle cannot be read")
        findings = check_schema_itself(self.schema)
        if findings:
            return self.result("schema", FAIL, 0, findings, "the bundle is not a valid Draft 2020-12 schema")
        valid = invalid = 0
        for r in check_embedded_examples(self.schema):
            valid += r.expected_valid
            invalid += (not r.expected_valid)
            if not r.ok:
                findings.append(Finding("SCH003", "embedded example %s (%s) does not behave as labeled: %s" % (r.case_id, "valid" if r.expected_valid else "invalid", r.detail),
                                        "schemas/contracts-v1.schema.json", doc="schemas/README.md"))
        total = valid + invalid
        if total == 0:
            return self.result("schema", NOT_ASSESSED, 0, [], "the bundle documents no embedded examples: nothing was evaluated")
        detail = "bundle is a valid Draft 2020-12 schema; %d valid and %d invalid embedded examples behave as labeled" % (valid, invalid)
        return self.result("schema", FAIL if findings else PASS, total, findings, detail)

    def stage_instances(self) -> StageResult:
        if self.schema_problem is not None:
            return self.result("instances", INPUT_ERROR, findings=[self.schema_problem], detail="the schema bundle cannot be read")
        model = self.model
        findings: List[Finding] = []
        for inst in model.instances.values():
            findings += validate_instance(self.schema, inst.data, inst.file)
        by: Dict[str, int] = {}
        for inst in model.instances.values():
            by[inst.contract] = by.get(inst.contract, 0) + 1
        count = len(model.instances)
        raw = [p for p in model.ignored if not is_stage_file(Path(p).name)]
        if self.load_findings:
            return self.result("instances", INPUT_ERROR, count, self.load_findings + findings, "%d file(s) could not be read or indexed" % len(self.load_findings))
        if count == 0:
            seen = "; %d JSON file(s) were read, but none has a contract_id C01-C07" % len(model.ignored) if model.ignored else ""
            return self.result("instances", NOT_ASSESSED, 0, [], "no contract instance found under %s%s: nothing was evaluated" % (rel(self.root), seen))
        detail = "%d contract instances validated (%s)" % (count, ", ".join("%s x%d" % kv for kv in sorted(by.items())))
        if raw:
            detail += "; %d other JSON file(s) declare no contract_id and were read as non-contract input, not validated as instances" % len(raw)
        return self.result("instances", FAIL if findings else PASS, count, findings, detail)

    def stage_semantics(self) -> StageResult:
        blocked = self.blocked("semantics")
        if blocked:
            return blocked
        findings: List[Finding] = []
        problems: List[Finding] = []
        for check in semantics.ALL_CHECKS:
            try:
                findings += check(self.model)
            except DOCUMENT_ERRORS as exc:
                if self.debug:
                    raise
                problems.append(input_finding("INP002", "the semantics stage could not run its %r check: %s" % (check.__name__.replace("check_", ""), describe_error(exc)), "",
                                              "a document that check reads (registry.json or an instance) is not shaped as the check expects; run with --debug for the traceback"))
        count = len(self.model.instances)
        if problems:
            return self.result("semantics", INPUT_ERROR, count, problems + findings, "%d check(s) could not run" % len(problems))
        return self.result("semantics", FAIL if findings else PASS, count, findings, "%d check families ran over %d instances" % (len(semantics.ALL_CHECKS), count))

    def stage_gateway(self) -> StageResult:
        blocked = self.blocked("gateway")
        if blocked:
            return blocked

        def evaluate(path, data):
            return check_scenario_file(self.model, data, path), len(data["evaluations"])
        return self.collect("gateway", "gateway-scenarios.json", evaluate, lambda r: "%d stored what-if evaluations reproduce their recorded decisions" % r.evaluated,
                            collection="evaluations", what="a gateway scenario file")

    def stage_responses(self) -> StageResult:
        blocked = self.blocked("responses")
        if blocked:
            return blocked
        kinds = {"canonical": 0, "free-form": 0}

        def evaluate(path, data):
            kinds["canonical" if is_canonical(data) else "free-form"] += 1
            return check_response(self.model, data, path), 1
        return self.collect("responses", "response-*.json", evaluate,
                            lambda r: ("%d responses conform to the packets they cite (or are withdrawn): %d canonical, compared with the renderer's output; "
                                       "%d free-form, held to the structural constraints only") % (r.evaluated, kinds["canonical"], kinds["free-form"]),
                            collection="statements", what="a response", empty_is_evaluated=True)

    def stage_cases(self) -> StageResult:
        blocked = self.blocked("cases")
        if blocked:
            return blocked

        def evaluate(path, data):
            return check_cases(self.model, self.schema, data, path)
        return self.collect("cases", "cases.json", evaluate, lambda r: "%d mutated cases each produced exactly the codes they declare" % r.evaluated,
                            collection="cases", what="an evaluation-case file")

    # ------------------------------------------------------------------ the run
    def evaluate(self, stage: str, needed_by: str = "") -> StageResult:
        started = time.time()
        try:
            result = getattr(self, "stage_" + stage)()
        except (SchemaError, InputProblem) + DOCUMENT_ERRORS as exc:
            if self.debug and not isinstance(exc, InputProblem):
                raise
            result = self.result(stage, INPUT_ERROR, findings=[input_finding("INP002", "the %s stage could not evaluate the input: %s" % (stage, describe_error(exc)), "",
                                                                             "check the documents the stage reads; run with --debug for the traceback")],
                                 detail="the input cannot support this stage")
        result.seconds = round(time.time() - started, 2)
        result.needed_by = needed_by
        self.results[stage] = result
        return result


def plan(only: Optional[Set[str]], skip: Optional[Set[str]]) -> Dict[str, str]:
    """Which stages run, mapped to the stage that pulled them in ('' when the user chose them)."""
    chosen = [s for s in STAGES if (not only or s in only) and s not in (skip or set())]
    needed = {s: "" for s in chosen}
    for stage in chosen:
        pre = PREREQUISITES.get(stage)
        if pre and pre not in needed:
            needed[pre] = stage
    return needed


def run(root: Path, only: Optional[Set[str]] = None, skip: Optional[Set[str]] = None, debug: bool = False) -> List[StageResult]:
    """Evaluate the chosen stages (and the prerequisites they need) and return one result for each of the six stages."""
    wanted = plan(only, skip)
    session = Run(root, debug)
    results: List[StageResult] = []
    for stage in STAGES:
        if stage not in wanted:
            skipped = StageResult(stage, TITLES[stage], SKIPPED, detail="left out by --only or --skip")
            session.results[stage] = skipped
            results.append(skipped)
        else:
            results.append(session.evaluate(stage, wanted[stage]))
    return results


# ---------------------------------------------------------------------- output
def finding_json(f: Finding) -> dict:
    return {"code": f.code, "message": f.message, "file": f.file, "location": f.location, "stage": f.stage, "doc": f.doc, "hint": f.hint}


def render_json(results: List[StageResult], state: str, run_findings: Optional[List[Finding]] = None) -> str:
    complete = bool(results) and all(r.status != SKIPPED for r in results)
    return json.dumps({
        # "passed" is true only when every stage ran and passed; "status" is the state of the stages that ran
        "version": __version__, "status": state, "passed": state == PASS and complete, "complete": complete,
        "skipped_stages": [r.stage for r in results if r.status == SKIPPED], "exit_code": EXIT_CODES[state],
        "findings": [finding_json(f) for f in (run_findings or [])],
        "stages": [{"stage": r.stage, "title": r.title, "status": r.status, "passed": r.passed, "evaluated": r.evaluated, "detail": r.detail,
                    "required_by": r.needed_by, "findings": [finding_json(f) for f in r.findings]} for r in results],
    }, indent=2)


def render_text(results: List[StageResult], state: str, verbose: bool) -> str:
    out = ["Evidence at Human Scale %s: example validation" % __version__, "Synthetic data only. A pass is not evidence about any real system.", ""]
    for i, r in enumerate(results, 1):
        note = " (run because %s needs it)" % r.needed_by if r.needed_by else ""
        count = ""
        if r.status == PASS or (r.status == FAIL and r.evaluated):
            count = "  %d evaluated" % r.evaluated
        if r.status == SKIPPED:
            count = "  " + r.detail
        out.append(("[%d/%d] %-27s %-12s%s%s" % (i, len(results), r.title + " ...", r.status, count, note)).rstrip())
        if r.status in (NOT_ASSESSED, INPUT_ERROR) and r.detail:
            out.append("        " + r.detail)
        elif verbose and r.detail and r.status != SKIPPED:
            out.append("        " + r.detail)
        if r.findings:
            out.append("        %d %s:" % (len(r.findings), "finding(s)" if r.status == FAIL else "diagnostic(s)"))
            for f in r.findings:
                out.append("      - " + f.format().replace("\n", "\n        "))
    out.append("")
    states = [r.status for r in results]
    ran = [r for r in results if r.status != SKIPPED]
    if state == PASS:
        left_out = states.count(SKIPPED)
        total = sum(r.evaluated for r in results)
        passed = "%d stage%s passed" % (len(ran), "" if len(ran) == 1 else "s")
        each = "each " if len(ran) > 1 else ""
        if left_out:
            out.append("Result: PASS for the stages that ran. %s, %safter evaluating at least one item (%d items in all). %d stage(s) were skipped and not evaluated, so this result says nothing about them." % (passed, each, total, left_out))
        else:
            out.append("Result: PASS. All %d stages passed, each after evaluating at least one item (%d items in all)." % (len(ran), total))
    elif state == FAIL:
        out.append("Result: FAIL. %d of %d stages reported findings. %s" % (states.count(FAIL), len(ran), NEXT_STEP[FAIL]))
    elif state == INPUT_ERROR:
        out.append("Result: INPUT ERROR. %s" % NEXT_STEP[INPUT_ERROR])
    else:
        if not ran:
            out.append("Result: NOT ASSESSED. Every stage was skipped, so nothing was evaluated. Select at least one stage with --only, or take a stage out of --skip.")
        else:
            out.append("Result: NOT ASSESSED. %d stage(s) had no input to evaluate, so nothing could pass or fail there. %s" % (states.count(NOT_ASSESSED), NEXT_STEP[NOT_ASSESSED]))
    return "\n".join(out)


def split(value: str) -> Set[str]:
    return {s.strip() for s in value.split(",") if s.strip()}


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--examples", type=Path, default=REPO_ROOT / "examples", help="directory to validate (default: examples/)")
    parser.add_argument("--only", default="", help="comma-separated stages to run: " + ", ".join(STAGES))
    parser.add_argument("--skip", default="", help="comma-separated stages to leave out")
    parser.add_argument("--verbose", action="store_true", help="show the detail line of every stage")
    parser.add_argument("--json", action="store_true", help="print a machine-readable result instead of text")
    parser.add_argument("--debug", action="store_true", help="let an unexpected error raise, with its traceback")
    args = parser.parse_args(argv)
    only, skip = split(args.only), split(args.skip)
    unknown = (only | skip) - set(STAGES)
    if unknown:
        parser.error("unknown stage(s): %s (stages: %s)" % (", ".join(sorted(unknown)), ", ".join(STAGES)))
    if not args.examples.is_dir():
        problem = input_finding("INP001", "the examples folder cannot be read: %s is not a directory" % args.examples, str(args.examples), "pass --examples DIR with a folder that has the layout of examples/")
        if args.json:
            print(render_json([], INPUT_ERROR, [problem]))
        else:
            print("Evidence at Human Scale %s: example validation\n\n      - %s\n\nResult: INPUT ERROR. %s" % (__version__, problem.format().replace("\n", "\n        "), NEXT_STEP[INPUT_ERROR]))
        return EXIT_CODES[INPUT_ERROR]
    results = run(args.examples, only, skip, args.debug)
    state = overall(results)
    print(render_json(results, state) if args.json else render_text(results, state, args.verbose))
    return EXIT_CODES[state]


if __name__ == "__main__":
    for _stream in (sys.stdout, sys.stderr):  # a legacy console code page must not break the output
        getattr(_stream, "reconfigure", lambda **_: None)(encoding="utf-8", errors="replace")
    sys.exit(main())
