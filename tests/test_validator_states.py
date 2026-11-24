"""A validation stage passes only after it has evaluated something. Absence of input is never a pass.

The five states (PASS, FAIL, SKIPPED, NOT ASSESSED, INPUT ERROR), how they combine, and what the command does with an
empty folder, a missing prerequisite, a partial stage selection, a malformed document and a mix of good and bad records.
"""
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from collections import Counter
from pathlib import Path

import support  # noqa: F401  (puts scripts/ on the path)

import validate_examples as ve
from eahs.schema import validate_instance
from eahs.status import EXIT_CODES, FAIL, INPUT_ERROR, NOT_ASSESSED, PASS, SKIPPED, StageResult, overall

COMMAND = str(support.SCRIPTS / "validate_examples.py")


def cli(*args):
    return subprocess.run([sys.executable, COMMAND] + list(args), capture_output=True, text=True, encoding="utf-8")


def states(results):
    return {r.stage: r.status for r in results}


class Scratch(unittest.TestCase):
    """A temporary folder, and helpers to fill it with a copy of the example set."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name) / "examples"

    def empty(self):
        self.root.mkdir(parents=True)
        return self.root

    def copy(self):
        shutil.copytree(support.EXAMPLES, self.root)
        return self.root

    def write(self, relative, text):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def edit_json(self, relative, change):
        path = self.root / relative
        data = json.loads(path.read_text(encoding="utf-8"))
        change(data)
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")


class StateModel(unittest.TestCase):
    def result(self, status):
        return StageResult("x", "X", status)

    def test_only_pass_exits_zero(self):
        self.assertEqual({s: c for s, c in EXIT_CODES.items()}, {PASS: 0, FAIL: 1, INPUT_ERROR: 2, NOT_ASSESSED: 3})

    def test_the_worst_state_wins(self):
        self.assertEqual(overall([self.result(PASS), self.result(NOT_ASSESSED)]), NOT_ASSESSED)
        self.assertEqual(overall([self.result(PASS), self.result(NOT_ASSESSED), self.result(FAIL)]), FAIL)
        self.assertEqual(overall([self.result(FAIL), self.result(INPUT_ERROR)]), INPUT_ERROR)

    def test_a_run_in_which_nothing_passed_is_not_a_pass(self):
        self.assertEqual(overall([]), NOT_ASSESSED)
        self.assertEqual(overall([self.result(SKIPPED), self.result(SKIPPED)]), NOT_ASSESSED)

    def test_skipped_stages_do_not_spoil_a_pass_but_are_not_counted_as_passes(self):
        self.assertEqual(overall([self.result(PASS), self.result(SKIPPED)]), PASS)


class TheCommittedExamples(unittest.TestCase):
    def test_every_stage_evaluates_something_and_passes(self):
        results = ve.run(support.EXAMPLES)
        self.assertEqual(states(results), {stage: PASS for stage in ve.STAGES})
        self.assertTrue(all(r.evaluated > 0 for r in results), [(r.stage, r.evaluated) for r in results])

    def test_the_counts_are_the_documented_ones(self):
        counts = {r.stage: r.evaluated for r in ve.run(support.EXAMPLES)}
        self.assertEqual(counts, {"schema": 102, "instances": 37, "semantics": 37, "gateway": 19, "responses": 3, "cases": 37})

    def test_the_command_says_what_it_evaluated(self):
        done = cli()
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("Result: PASS. All 6 stages passed, each after evaluating at least one item", done.stdout)
        self.assertIn("102 evaluated", done.stdout)


class EmptyInput(Scratch):
    def test_an_empty_examples_folder_does_not_pass(self):
        results = ve.run(self.empty())
        self.assertEqual(overall(results), NOT_ASSESSED)
        self.assertEqual(states(results)["instances"], NOT_ASSESSED)
        for stage in ("semantics", "gateway", "responses", "cases"):
            self.assertEqual(states(results)[stage], NOT_ASSESSED, stage)

    def test_the_command_exits_with_not_assessed_and_does_not_claim_success(self):
        done = cli("--examples", str(self.empty()))
        self.assertEqual(done.returncode, 3, done.stdout + done.stderr)
        self.assertIn("NOT ASSESSED", done.stdout)
        self.assertIn("nothing was evaluated", done.stdout)
        self.assertNotIn("passed", done.stdout.split("Result:")[1])
        self.assertNotIn("Traceback", done.stderr)

    def test_an_individual_example_folder_with_no_files_does_not_pass(self):
        (self.empty() / "01-nothing-here").mkdir()
        self.assertEqual(overall(ve.run(self.root)), NOT_ASSESSED)

    def test_json_that_is_not_a_contract_instance_is_not_evaluated(self):
        self.empty()
        self.write("01-notes/raw.json", json.dumps({"hello": "world"}))
        results = ve.run(self.root)
        instances = next(r for r in results if r.stage == "instances")
        self.assertEqual(instances.status, NOT_ASSESSED)
        self.assertIn("none has a contract_id", instances.detail)
        self.assertEqual(overall(results), NOT_ASSESSED)

    def test_a_zero_byte_instance_file_is_an_input_error(self):
        self.empty()
        self.write("01-empty/c02-EMPTY-v1.json", "")
        results = ve.run(self.root)
        instances = next(r for r in results if r.stage == "instances")
        self.assertEqual(instances.status, INPUT_ERROR)
        self.assertEqual(instances.findings[0].code, "ID000")
        self.assertIn("c02-EMPTY-v1.json", instances.findings[0].file)
        self.assertEqual(overall(results), INPUT_ERROR)

    def test_a_missing_folder_is_an_input_error_not_a_crash(self):
        done = cli("--examples", str(self.root / "does-not-exist"))
        self.assertEqual(done.returncode, 2)
        self.assertIn("INPUT ERROR", done.stdout)
        self.assertNotIn("Traceback", done.stderr)


class NoEvaluableRecords(Scratch):
    def test_stages_without_their_input_files_are_not_assessed_even_when_the_instances_pass(self):
        self.copy()
        for name in ("gateway-scenarios.json", "cases.json"):
            for path in list(self.root.rglob(name)):
                path.unlink()
        for path in list(self.root.rglob("response-*.json")):
            path.unlink()
        results = ve.run(self.root)
        self.assertEqual(states(results), {"schema": PASS, "instances": PASS, "semantics": PASS, "gateway": NOT_ASSESSED, "responses": NOT_ASSESSED, "cases": NOT_ASSESSED})
        self.assertEqual(overall(results), NOT_ASSESSED)

    def test_a_scenario_file_with_no_evaluations_evaluated_nothing(self):
        self.copy()
        for path in list(self.root.rglob("gateway-scenarios.json")):
            path.write_text(json.dumps({"evaluations": []}), encoding="utf-8")
        gateway = next(r for r in ve.run(self.root) if r.stage == "gateway")
        self.assertEqual((gateway.status, gateway.evaluated), (NOT_ASSESSED, 0))
        self.assertIn("nothing to evaluate", gateway.detail)

    def test_a_case_file_with_no_cases_evaluated_nothing(self):
        self.copy()
        self.edit_json("13-evaluation-cases/cases.json", lambda d: d.update(cases=[]))
        cases = next(r for r in ve.run(self.root) if r.stage == "cases")
        self.assertEqual((cases.status, cases.evaluated), (NOT_ASSESSED, 0))


class StageSelection(Scratch):
    def test_a_selected_stage_pulls_in_the_stage_it_needs(self):
        results = ve.run(support.EXAMPLES, only={"semantics"})
        by = {r.stage: r for r in results}
        self.assertEqual(states(results), {"schema": SKIPPED, "instances": PASS, "semantics": PASS, "gateway": SKIPPED, "responses": SKIPPED, "cases": SKIPPED})
        self.assertEqual(by["instances"].needed_by, "semantics")
        self.assertEqual(overall(results), PASS)

    def test_several_selected_stages_share_the_prerequisite(self):
        results = ve.run(support.EXAMPLES, only={"gateway", "responses"})
        self.assertEqual(states(results)["instances"], PASS)
        self.assertEqual(states(results)["gateway"], PASS)
        self.assertEqual(states(results)["responses"], PASS)
        self.assertEqual(states(results)["cases"], SKIPPED)

    def test_the_skip_option_cannot_remove_a_prerequisite_of_a_selected_stage(self):
        results = ve.run(support.EXAMPLES, skip={"instances"})
        self.assertEqual(states(results)["instances"], PASS)

    def test_one_stage_alone_is_a_pass_but_says_how_much_was_skipped(self):
        done = cli("--only", "schema")
        self.assertEqual(done.returncode, 0, done.stdout)
        self.assertIn("5 stage(s) were skipped and not evaluated", done.stdout)
        self.assertIn("Result: PASS for the stages that ran", done.stdout)
        self.assertIn("says nothing about them", done.stdout)
        self.assertNotIn("Result: PASS. All", done.stdout)

    def test_a_complete_run_says_so_and_a_partial_run_does_not(self):
        partial, whole = json.loads(cli("--only", "schema", "--json").stdout), json.loads(cli("--json").stdout)
        self.assertEqual((partial["status"], partial["complete"]), (PASS, False))
        self.assertEqual((whole["status"], whole["complete"]), (PASS, True))
        self.assertNotIn("stages that ran", cli().stdout)

    def test_skipping_every_stage_is_not_assessed(self):
        done = cli("--skip", ",".join(ve.STAGES))
        self.assertEqual(done.returncode, 3, done.stdout)
        self.assertIn("SKIPPED", done.stdout)
        self.assertIn("Every stage was skipped, so nothing was evaluated", done.stdout)

    def test_an_unknown_stage_name_is_refused_with_a_message(self):
        done = cli("--only", "semantic")
        self.assertEqual(done.returncode, 2)
        self.assertIn("unknown stage", done.stderr)
        self.assertNotIn("Traceback", done.stderr)

    def test_a_partial_selection_on_a_broken_folder_does_not_raise(self):
        self.empty()
        self.write("c02-X-1-v1.json", json.dumps({"contract_id": "C02", "schema_version": "1.0", "identity_schema": {"record_id": "X-1", "version": "v1", "kind": "source_record_assertion"}}))
        for stages in ("semantics", "gateway,responses", "cases"):
            done = cli("--examples", str(self.root), "--only", stages)
            self.assertEqual(done.returncode, 1, stages + done.stdout + done.stderr)
            self.assertNotIn("Traceback", done.stderr, stages)
            self.assertNotIn("KeyError", done.stdout + done.stderr, stages)
            self.assertIn("NOT ASSESSED", done.stdout, stages)
        results = ve.run(self.root, only={"semantics"})
        self.assertEqual(states(results)["instances"], FAIL)
        self.assertEqual(states(results)["semantics"], NOT_ASSESSED)


class MalformedInput(Scratch):
    def test_a_document_that_is_not_json_is_an_input_error_with_a_fix(self):
        self.empty()
        self.write("broken.json", '{"contract_id": "C02", "cut off')
        done = cli("--examples", str(self.root))
        self.assertEqual(done.returncode, 2, done.stdout + done.stderr)
        self.assertIn("INPUT ERROR", done.stdout)
        self.assertIn("broken.json", done.stdout)
        self.assertIn("fix:", done.stdout)
        self.assertNotIn("Traceback", done.stderr)

    def test_a_response_file_that_is_not_an_object_is_an_input_error(self):
        self.copy()
        self.write("06-assistant-response/response-bad.json", "[1, 2, 3]")
        responses = next(r for r in ve.run(self.root) if r.stage == "responses")
        self.assertEqual(responses.status, INPUT_ERROR)
        self.assertEqual(responses.findings[0].code, "INP002")
        self.assertIn("response-bad.json", responses.findings[0].file)

    def test_a_case_without_its_expected_codes_is_an_input_error_not_a_key_error(self):
        self.copy()
        self.edit_json("13-evaluation-cases/cases.json", lambda d: d["cases"][0].pop("expect"))
        done = cli("--examples", str(self.root), "--only", "cases")
        self.assertEqual(done.returncode, 2, done.stdout + done.stderr)
        self.assertIn("INP002", done.stdout)
        self.assertNotIn("Traceback", done.stderr)

    def test_a_registry_that_is_not_an_object_is_an_input_error(self):
        self.copy()
        self.write("registry.json", "[]")
        instances = next(r for r in ve.run(self.root) if r.stage == "instances")
        self.assertEqual(instances.status, INPUT_ERROR)

    def test_an_unexpected_shape_inside_a_stage_is_reported_not_raised(self):
        self.copy()
        self.edit_json("05-decision-packet/c04-PKT-0417-v1.json", lambda d: d.pop("labeled_inferences"))
        results = ve.run(self.root)
        self.assertEqual(states(results)["instances"], FAIL)
        self.assertEqual(states(results)["semantics"], NOT_ASSESSED)


class MixedRecords(Scratch):
    def test_one_wrong_gateway_decision_fails_the_stage_and_names_it(self):
        self.copy()
        self.edit_json("08-blocked-action/gateway-scenarios.json", lambda d: d["evaluations"][0]["expect"].update(decision="ALLOW" if d["evaluations"][0]["expect"]["decision"] == "BLOCK" else "BLOCK"))
        results = ve.run(self.root)
        gateway = next(r for r in results if r.stage == "gateway")
        self.assertEqual(gateway.status, FAIL)
        self.assertEqual([f.code for f in gateway.findings], ["GW001"])
        self.assertGreater(gateway.evaluated, 1)
        self.assertEqual(overall(results), FAIL)

    def test_one_wrong_case_fails_the_stage_and_the_others_still_count(self):
        self.copy()
        self.edit_json("13-evaluation-cases/cases.json", lambda d: d["cases"][0].update(expect=["REF001"] if d["cases"][0]["expect"] != ["REF001"] else ["LIN001"]))
        cases = next(r for r in ve.run(self.root) if r.stage == "cases")
        self.assertEqual((cases.status, cases.evaluated, [f.code for f in cases.findings]), (FAIL, 37, ["CASE001"]))

    def test_the_json_result_reports_each_stage_state_and_the_overall_state(self):
        self.copy()
        self.edit_json("08-blocked-action/gateway-scenarios.json", lambda d: d["evaluations"][0]["expect"].update(codes=["NOT_A_REAL_CODE"]))
        done = cli("--examples", str(self.root), "--json")
        self.assertEqual(done.returncode, 1)
        data = json.loads(done.stdout)
        self.assertEqual((data["status"], data["passed"], data["exit_code"]), (FAIL, False, 1))
        stages = {s["stage"]: s for s in data["stages"]}
        self.assertEqual(stages["gateway"]["status"], FAIL)
        self.assertEqual(stages["cases"]["status"], PASS)
        self.assertGreater(stages["gateway"]["evaluated"], 1)

    def test_a_valid_set_with_one_invalid_instance_fails_instances_and_blocks_the_rest(self):
        self.copy()
        self.edit_json("01-source-records/c02-INV-2026-0417-v1.json", lambda d: d["times"].update(ingestion="2026-11-23T07:31:00"))
        results = ve.run(self.root)
        self.assertEqual(states(results), {"schema": PASS, "instances": FAIL, "semantics": NOT_ASSESSED, "gateway": NOT_ASSESSED, "responses": NOT_ASSESSED, "cases": NOT_ASSESSED})
        self.assertEqual(overall(results), FAIL)


class Diagnostics(unittest.TestCase):
    def test_no_diagnostic_is_reported_twice(self):
        schema = support.schema()
        for entry in schema["x-documentation-examples"]:
            findings = validate_instance(schema, entry["instance"], entry["case_id"], entry.get("contract_id"))
            counts = Counter((f.code, f.message, f.location) for f in findings)
            self.assertEqual([k for k, v in counts.items() if v > 1], [], entry["case_id"])


if __name__ == "__main__":
    unittest.main()
