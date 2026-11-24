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

A pass shows that the synthetic examples are structurally valid and internally coherent, and that the deterministic
checks behave as documented. It does not show that any real system, model or process is accountable, safe or correct.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
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
from eahs.findings import Finding, rel  # noqa: E402
from eahs.model import Model, load_model  # noqa: E402
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


class Run:
    """One validation run over a folder: loads the schema and the model once, then evaluates the stages."""

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
        self.model: Optional[Model] = None
        self.load_findings: List[Finding] = []
        if self.schema is not None:
            self.model, self.load_findings = load_model(root)

    # ------------------------------------------------------------------ helpers
    def result(self, stage: str, status: str, evaluated: int = 0, findings: Optional[List[Finding]] = None, detail: str = "") -> StageResult:
        return StageResult(stage, TITLES[stage], status, evaluated, findings or [], detail)

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

    def read_json(self, path: Path):
        try:
            return json.loads(path.read_text(encoding="utf-8")), None
        except (OSError, ValueError) as exc:
            return None, input_finding("ID000", "cannot read JSON: %s" % exc, rel(path), "repair or remove the file")

    def bad_document(self, stage: str, path: Path, exc: Exception) -> Finding:
        return input_finding("INP002", "the %s stage cannot evaluate this document: %s: %s" % (stage, type(exc).__name__, exc), rel(path),
                             "the document lacks a structure the checks read; compare it with the example it is modelled on")

    def collect(self, stage: str, pattern: str, evaluate) -> StageResult:
        """Run `evaluate(path, data) -> (findings, count)` over every file that matches, and settle the state."""
        paths = sorted(self.root.rglob(pattern))
        if not paths:
            return self.result(stage, NOT_ASSESSED, detail="no %s found under %s: nothing was evaluated" % (pattern, rel(self.root)))
        findings: List[Finding] = []
        problems: List[Finding] = []
        count = 0
        for path in paths:
            data, problem = self.read_json(path)
            if problem is not None:
                problems.append(problem)
                continue
            try:
                found, n = evaluate(path, data)
            except DOCUMENT_ERRORS as exc:
                if self.debug:
                    raise
                problems.append(self.bad_document(stage, path, exc))
                continue
            findings += found
            count += n
        if problems:
            return self.result(stage, INPUT_ERROR, count, problems + findings, "%d file(s) could not be evaluated" % len(problems))
        if count == 0:
            return self.result(stage, NOT_ASSESSED, 0, findings, "%d %s file(s) found, but they hold nothing to evaluate" % (len(paths), pattern))
        return self.result(stage, FAIL if findings else PASS, count, findings)

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
        if self.load_findings:
            return self.result("instances", INPUT_ERROR, count, self.load_findings + findings, "%d file(s) could not be read or indexed" % len(self.load_findings))
        if count == 0:
            seen = "; %d JSON file(s) were read, but none has a contract_id C01-C07" % len(model.ignored) if model.ignored else ""
            return self.result("instances", NOT_ASSESSED, 0, [], "no contract instance found under %s%s: nothing was evaluated" % (rel(self.root), seen))
        detail = "%d contract instances validated (%s)" % (count, ", ".join("%s x%d" % kv for kv in sorted(by.items())))
        return self.result("instances", FAIL if findings else PASS, count, findings, detail)

    def stage_semantics(self) -> StageResult:
        blocked = self.blocked("semantics")
        if blocked:
            return blocked
        findings = semantics.run_all(self.model)
        count = len(self.model.instances)
        return self.result("semantics", FAIL if findings else PASS, count, findings, "%d check families ran over %d instances" % (len(semantics.ALL_CHECKS), count))

    def stage_gateway(self) -> StageResult:
        blocked = self.blocked("gateway")
        if blocked:
            return blocked

        def evaluate(path, data):
            if not isinstance(data, dict) or not isinstance(data.get("evaluations", []), list):
                raise TypeError("a gateway scenario file is an object with an 'evaluations' list")
            return check_scenario_file(self.model, data, path), len(data.get("evaluations", []))
        result = self.collect("gateway", "gateway-scenarios.json", evaluate)
        if result.status == PASS:
            result.detail = "%d stored what-if evaluations reproduce their recorded decisions" % result.evaluated
        return result

    def stage_responses(self) -> StageResult:
        blocked = self.blocked("responses")
        if blocked:
            return blocked
        kinds = {"canonical": 0, "free-form": 0}

        def evaluate(path, data):
            if not isinstance(data, dict):
                raise TypeError("a response is a JSON object")
            kinds["canonical" if is_canonical(data) else "free-form"] += 1
            return check_response(self.model, data, path), 1
        result = self.collect("responses", "response-*.json", evaluate)
        if result.status == PASS:
            result.detail = ("%d responses conform to the packets they cite (or are withdrawn): %d canonical, compared with the renderer's output; "
                             "%d free-form, held to the structural constraints only") % (result.evaluated, kinds["canonical"], kinds["free-form"])
        return result

    def stage_cases(self) -> StageResult:
        blocked = self.blocked("cases")
        if blocked:
            return blocked

        def evaluate(path, data):
            if not isinstance(data, dict) or not isinstance(data.get("cases", []), list):
                raise TypeError("an evaluation-case file is an object with a 'cases' list")
            return check_cases(self.model, self.schema, data, path)
        result = self.collect("cases", "cases.json", evaluate)
        if result.status == PASS:
            result.detail = "%d mutated cases each produced exactly the codes they declare" % result.evaluated
        return result

    # ------------------------------------------------------------------ the run
    def evaluate(self, stage: str, needed_by: str = "") -> StageResult:
        started = time.time()
        try:
            result = getattr(self, "stage_" + stage)()
        except (SchemaError,) + DOCUMENT_ERRORS as exc:
            if self.debug:
                raise
            result = self.result(stage, INPUT_ERROR, findings=[input_finding("INP002", "the %s stage could not evaluate the input: %s: %s" % (stage, type(exc).__name__, exc), "",
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
    return {"code": f.code, "message": f.message, "file": f.file, "location": f.location, "doc": f.doc, "hint": f.hint}


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
