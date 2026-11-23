#!/usr/bin/env python3
"""Validate the synthetic example set: schemas, scenario semantics, gateway scenarios, responses and evaluation cases.

    python scripts/validate_examples.py              # everything
    python scripts/validate_examples.py --verbose    # list every check that ran
    python scripts/validate_examples.py --json       # machine-readable result
    python scripts/validate_examples.py --only schema,semantics

Exit code 0 means every stage passed; 1 means at least one finding; 2 means the tool itself could not run.

A pass shows that the synthetic examples are structurally valid and internally coherent, and that the deterministic
checks behave as documented. It does not show that any real system, model or process is accountable, safe or correct.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

try:
    import jsonschema  # noqa: F401
except ImportError:  # pragma: no cover - environment problem, not a validation result
    sys.stderr.write("This command needs one third-party package: pip install -r requirements.txt\n")
    sys.exit(2)

from eahs import REPO_ROOT, __version__  # noqa: E402
from eahs import semantics  # noqa: E402
from eahs.cases import check_cases  # noqa: E402
from eahs.findings import Finding, rel  # noqa: E402
from eahs.model import load_model  # noqa: E402
from eahs.response import check_response  # noqa: E402
from eahs.scenarios import check_scenario_file  # noqa: E402
from eahs.schema import check_embedded_examples, check_schema_itself, load_schema, validate_instance  # noqa: E402

STAGES = ["schema", "instances", "semantics", "gateway", "responses", "cases"]


def run(root: Path, only, verbose: bool):
    results = []   # (stage, title, findings, detail)
    schema = load_schema()

    def stage(name, title, fn):
        if only and name not in only:
            return
        start = time.time()
        findings, detail = fn()
        results.append({"stage": name, "title": title, "findings": findings, "detail": detail, "seconds": round(time.time() - start, 2)})

    def stage_schema():
        findings = check_schema_itself(schema)
        valid = invalid = 0
        if not findings:
            for r in check_embedded_examples(schema):
                valid += r.expected_valid
                invalid += (not r.expected_valid)
                if not r.ok:
                    findings.append(Finding("SCH003", "embedded example %s (%s) does not behave as labelled: %s" % (r.case_id, "valid" if r.expected_valid else "invalid", r.detail), rel(Path(schema.get("$id", ""))) or "schemas/contracts-v1.schema.json", doc="schemas/README.md"))
        return findings, "bundle is a valid Draft 2020-12 schema; %d valid and %d invalid embedded examples behave as labelled" % (valid, invalid)

    model, load_findings = load_model(root)
    state = {"schema_ok": True}

    def stage_instances():
        findings = list(load_findings)
        for inst in model.instances.values():
            findings += validate_instance(schema, inst.data, inst.file)
        state["schema_ok"] = not findings
        by = {}
        for inst in model.instances.values():
            by[inst.contract] = by.get(inst.contract, 0) + 1
        return findings, "%d contract instances validated (%s)" % (len(model.instances), ", ".join("%s x%d" % kv for kv in sorted(by.items())))

    def stage_semantics():
        if not state["schema_ok"]:
            return [], "skipped: fix the schema findings first (semantic checks assume structurally valid instances)"
        findings = semantics.run_all(model)
        return findings, "%d checks families ran over %d instances" % (len(semantics.ALL_CHECKS), len(model.instances))

    def stage_gateway():
        if not state["schema_ok"]:
            return [], "skipped: fix the schema findings first"
        findings, count = [], 0
        for path in sorted(root.rglob("gateway-scenarios.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            count += len(data.get("evaluations", []))
            findings += check_scenario_file(model, data, path)
        return findings, "%d stored what-if evaluations reproduce their recorded decisions" % count

    def stage_responses():
        if not state["schema_ok"]:
            return [], "skipped: fix the schema findings first"
        findings, count = [], 0
        for path in sorted(root.rglob("response-*.json")):
            findings += check_response(model, json.loads(path.read_text(encoding="utf-8")), path)
            count += 1
        return findings, "%d responses conform to the packets they cite (or are withdrawn)" % count

    def stage_cases():
        if not state["schema_ok"]:
            return [], "skipped: fix the schema findings first"
        findings, count = [], 0
        for path in sorted(root.rglob("cases.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            problems, n = check_cases(model, schema, data, path)
            findings += problems
            count += n
        return findings, "%d mutated cases each produced exactly the codes they declare" % count

    stage("schema", "Schema bundle", stage_schema)
    stage("instances", "Example instances", stage_instances)
    stage("semantics", "Scenario semantics", stage_semantics)
    stage("gateway", "Gateway scenarios", stage_gateway)
    stage("responses", "Assistant responses", stage_responses)
    stage("cases", "Evaluation cases", stage_cases)
    return results


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--examples", type=Path, default=REPO_ROOT / "examples", help="directory to validate (default: examples/)")
    parser.add_argument("--only", default="", help="comma-separated stages: " + ", ".join(STAGES))
    parser.add_argument("--verbose", action="store_true", help="show the detail line of every stage")
    parser.add_argument("--json", action="store_true", help="print a machine-readable result instead of text")
    args = parser.parse_args(argv)
    only = {s.strip() for s in args.only.split(",") if s.strip()}
    unknown = only - set(STAGES)
    if unknown:
        parser.error("unknown stage(s): %s" % ", ".join(sorted(unknown)))
    if not args.examples.exists():
        sys.stderr.write("No examples directory at %s\n" % args.examples)
        return 2
    results = run(args.examples, only, args.verbose)
    failed = sum(1 for r in results if r["findings"])
    if args.json:
        print(json.dumps({
            "version": __version__, "passed": failed == 0,
            "stages": [{"stage": r["stage"], "title": r["title"], "passed": not r["findings"], "detail": r["detail"],
                        "findings": [{"code": f.code, "message": f.message, "file": f.file, "location": f.location, "doc": f.doc} for f in r["findings"]]} for r in results],
        }, indent=2))
        return 1 if failed else 0
    print("Evidence at Human Scale %s: example validation" % __version__)
    print("Synthetic data only. A pass is not evidence about any real system.\n")
    for i, r in enumerate(results, 1):
        mark = "PASS" if not r["findings"] else "FAIL"
        print("[%d/%d] %-22s %s" % (i, len(results), r["title"] + " ...", mark))
        if r["findings"]:
            print("        %d finding(s):" % len(r["findings"]))
        elif args.verbose:
            print("        " + r["detail"])
        for f in r["findings"]:
            print("      - " + f.format().replace("\n", "\n        "))
    print()
    if failed:
        print("FAILED: %d of %d stages reported findings. Each finding names the contract page to read." % (failed, len(results)))
        return 1
    print("All %d stages passed." % len(results))
    return 0


if __name__ == "__main__":
    sys.exit(main())
