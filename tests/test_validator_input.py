"""Every intended input is evaluated or explicitly rejected. Nothing disappears silently, and nothing crashes.

A top-level contract_id is a claim to be a contract instance, so it must be a string that names C01-C07. A file named like a
contract instance must be one. A stage file (gateway scenarios, evaluation cases, responses) must hold the collection the stage
evaluates: a missing collection is an input error, and an explicitly empty one evaluates nothing. Raw source exports are not
contract instances and stay usable. A schema-only run does not index the folder at all.
"""
import json
import shutil
import unittest
from unittest import mock

import support  # noqa: F401  (puts scripts/ on the path)

import validate_examples as ve
from eahs.status import FAIL, INPUT_ERROR, NOT_ASSESSED, PASS, SKIPPED, overall

from test_validator_states import Scratch as _Scratch, cli, states


def stage(results, name):
    return next(r for r in results if r.stage == name)


class Scratch(_Scratch):
    def fresh(self):
        """A clean copy of the example set, also when a test makes several (one for each sub-case)."""
        if self.root.exists():
            shutil.rmtree(self.root)
        return self.copy()

    def run_stage(self, name):
        """One stage and the prerequisite it needs, which is much cheaper than the whole run."""
        return stage(ve.run(self.root, only={name}), name)


class Actionable:
    """Mixin: every diagnostic of an INPUT ERROR names the file, the stage, the problem and what to do."""

    def assert_actionable(self, result, file_part=""):
        self.assertTrue(result.findings, "an INPUT ERROR must say why")
        for f in result.findings:
            self.assertEqual(f.stage, result.stage, f.code)
            self.assertTrue(f.hint, "%s has no recovery action" % f.code)
            self.assertTrue(f.message)
        if file_part:
            self.assertTrue(any(file_part in f.file for f in result.findings), [f.file for f in result.findings])


class TheDeclaredContractId(Scratch, Actionable):
    def stray(self, content, name="01-source-records/stray.json"):
        self.fresh()
        self.write(name, content if isinstance(content, str) else json.dumps(content))
        return self.run_stage("instances")

    def test_a_list_is_an_input_error_and_does_not_crash(self):
        instances = self.stray({"contract_id": []})
        self.assertEqual(instances.status, INPUT_ERROR)
        self.assertEqual([f.code for f in instances.findings], ["ID003"])
        self.assert_actionable(instances, "stray.json")
        self.assertIn("a list", instances.findings[0].message)

    def test_every_other_non_string_is_an_input_error_too(self):
        for label, value in (("object", {"id": "C02"}), ("number", 2), ("null", None), ("boolean", True)):
            with self.subTest(label):
                instances = self.stray({"contract_id": value})
                self.assertEqual((instances.status, [f.code for f in instances.findings]), (INPUT_ERROR, ["ID003"]))

    def test_an_unknown_contract_id_is_rejected_and_does_not_disappear(self):
        instances = self.stray({"contract_id": "C99", "anything": 1})
        self.assertEqual((instances.status, [f.code for f in instances.findings]), (INPUT_ERROR, ["ID004"]))
        self.assertIn("C99", instances.findings[0].message)
        self.assert_actionable(instances, "stray.json")

    def test_a_wrong_case_is_named_in_the_fix(self):
        instances = self.stray({"contract_id": "c02"})
        self.assertEqual([f.code for f in instances.findings], ["ID004"])
        self.assertIn("write C02", instances.findings[0].hint)

    def test_the_rest_of_the_folder_is_still_evaluated(self):
        instances = self.stray({"contract_id": []})
        self.assertEqual(instances.evaluated, 37)

    def test_the_command_exits_with_input_error_and_no_traceback(self):
        self.fresh()
        self.write("stray.json", json.dumps({"contract_id": []}))
        done = cli("--examples", str(self.root))
        self.assertEqual(done.returncode, 2, done.stdout + done.stderr)
        self.assertNotIn("Traceback", done.stderr)
        self.assertNotIn("TypeError", done.stdout + done.stderr)
        self.assertIn("ID003", done.stdout)
        self.assertIn("stage: instances", done.stdout)
        self.assertIn("fix:", done.stdout)

    def test_the_json_result_names_the_stage_of_every_finding(self):
        self.fresh()
        self.write("stray.json", json.dumps({"contract_id": "C99"}))
        data = json.loads(cli("--examples", str(self.root), "--json").stdout)
        findings = [f for s in data["stages"] for f in s["findings"]]
        self.assertTrue(findings)
        self.assertTrue(all(f["stage"] for f in findings), findings)

    def test_every_stage_that_needs_the_model_is_blocked_not_passed(self):
        self.fresh()
        self.write("stray.json", json.dumps({"contract_id": []}))
        results = ve.run(self.root)
        self.assertEqual(states(results), {"schema": PASS, "instances": INPUT_ERROR, "semantics": NOT_ASSESSED, "gateway": NOT_ASSESSED, "responses": NOT_ASSESSED, "cases": NOT_ASSESSED})
        self.assertEqual(overall(results), INPUT_ERROR)


class AFileNamedLikeAContractInstance(Scratch, Actionable):
    def test_an_empty_object_is_rejected(self):
        self.fresh()
        self.write("01-source-records/c02-EMPTY-v1.json", "{}")
        instances = self.run_stage("instances")
        self.assertEqual((instances.status, [f.code for f in instances.findings]), (INPUT_ERROR, ["ID005"]))
        self.assertIn("has no contract_id", instances.findings[0].message)
        self.assert_actionable(instances, "c02-EMPTY-v1.json")

    def test_something_that_is_not_an_object_is_rejected(self):
        for label, content in (("list", "[]"), ("number", "7"), ("string", '"C02"')):
            with self.subTest(label):
                self.fresh()
                self.write("01-source-records/c03-X-v1.json", content)
                instances = self.run_stage("instances")
                self.assertEqual([f.code for f in instances.findings], ["ID005"])
                self.assertIn("not a JSON object", instances.findings[0].message)

    def test_a_name_and_a_contract_id_that_disagree_are_rejected(self):
        self.fresh()
        self.edit_json("01-source-records/c02-GR-5521-v1.json", lambda d: d.update(contract_id="C03"))
        instances = self.run_stage("instances")
        self.assertEqual([f.code for f in instances.findings], ["ID005"])
        self.assertIn("C02", instances.findings[0].message)
        self.assertIn("C03", instances.findings[0].message)

    def test_an_invalid_contract_id_in_such_a_file_names_the_value(self):
        self.fresh()
        self.write("01-source-records/c02-BAD-v1.json", json.dumps({"contract_id": 2}))
        self.assertEqual([f.code for f in self.run_stage("instances").findings], ["ID003"])

    def test_a_zero_byte_file_is_rejected_too(self):
        self.fresh()
        self.write("01-source-records/c02-ZERO-v1.json", "")
        instances = self.run_stage("instances")
        self.assertEqual([f.code for f in instances.findings], ["ID000"])
        self.assert_actionable(instances, "c02-ZERO-v1.json")


class RawSourceExports(Scratch):
    def test_the_committed_raw_exports_are_read_as_non_contract_input(self):
        instances = stage(ve.run(support.EXAMPLES, only={"instances"}), "instances")
        self.assertEqual(instances.status, PASS)
        self.assertIn("4 other JSON file(s) declare no contract_id and were read as non-contract input", instances.detail)

    def test_a_raw_export_may_carry_any_fields_including_a_business_contract_id(self):
        self.fresh()
        self.write("01-source-records/raw/erp-supplier-contract.json", json.dumps({"contract_id": "K-7788", "supplier": "S-1042"}))
        self.write("01-source-records/raw/erp-number.json", json.dumps({"contract_id": 7788}))
        instances = self.run_stage("instances")
        self.assertEqual((instances.status, instances.findings), (PASS, []))

    def test_a_json_file_with_no_contract_id_anywhere_is_not_an_instance_and_not_an_error(self):
        self.fresh()
        self.write("notes/scratch.json", json.dumps({"hello": "world"}))
        instances = self.run_stage("instances")
        self.assertEqual(instances.status, PASS)
        self.assertIn("5 other JSON file(s)", instances.detail)

    def test_a_business_contract_id_outside_a_raw_folder_is_not_ignored(self):
        self.fresh()
        self.write("notes/supplier.json", json.dumps({"contract_id": "K-7788"}))
        instances = self.run_stage("instances")
        self.assertEqual((instances.status, [f.code for f in instances.findings]), (INPUT_ERROR, ["ID004"]))
        self.assertIn("raw", instances.findings[0].hint)

    def test_a_contract_instance_in_a_raw_folder_is_still_a_contract_instance(self):
        self.fresh()
        source = json.loads((self.root / "01-source-records" / "c02-PO-77231-v1.json").read_text(encoding="utf-8"))
        source["identity_schema"]["record_id"] = "PO-RAW-1"
        self.write("01-source-records/raw/c02-PO-RAW-1-v1.json", json.dumps(source))
        self.assertEqual(self.run_stage("instances").evaluated, 38)

    def test_a_folder_of_only_raw_exports_evaluates_nothing(self):
        self.empty()
        self.write("raw/a.json", json.dumps({"x": 1}))
        results = ve.run(self.root)
        self.assertEqual(stage(results, "instances").status, NOT_ASSESSED)
        self.assertEqual(overall(results), NOT_ASSESSED)


class TheScenarioFiles(Scratch, Actionable):
    NAME = "08-blocked-action/gateway-scenarios.json"

    def gateway(self, change=None, content=None):
        self.fresh()
        if content is not None:
            (self.root / self.NAME).write_text(content, encoding="utf-8")
        elif change is not None:
            self.edit_json(self.NAME, change)
        return self.run_stage("gateway")

    def test_a_missing_evaluations_list_is_an_input_error_not_an_empty_file(self):
        gateway = self.gateway(lambda d: d.pop("evaluations"))
        self.assertEqual(gateway.status, INPUT_ERROR)
        self.assertEqual([f.code for f in gateway.findings], ["INP002"])
        self.assertIn("no 'evaluations' list", gateway.findings[0].message)
        self.assert_actionable(gateway, "gateway-scenarios.json")

    def test_an_empty_object_is_an_input_error(self):
        gateway = self.gateway(content="{}")
        self.assertEqual((gateway.status, [f.code for f in gateway.findings]), (INPUT_ERROR, ["INP002"]))

    def test_an_evaluations_value_that_is_not_a_list_is_an_input_error(self):
        gateway = self.gateway(lambda d: d.update(evaluations="none"))
        self.assertEqual(gateway.status, INPUT_ERROR)
        self.assertIn("must be a list", gateway.findings[0].message)

    def test_a_file_that_is_not_an_object_is_an_input_error(self):
        gateway = self.gateway(content="[]")
        self.assertEqual(gateway.status, INPUT_ERROR)
        self.assertIn("must be a JSON object", gateway.findings[0].message)

    def test_an_explicitly_empty_list_evaluates_nothing_and_says_so(self):
        self.fresh()
        for path in self.root.rglob("gateway-scenarios.json"):
            path.write_text(json.dumps({"evaluations": []}), encoding="utf-8")
        gateway = self.run_stage("gateway")
        self.assertEqual((gateway.status, gateway.evaluated), (NOT_ASSESSED, 0))
        self.assertIn("explicitly empty", gateway.detail)

    def test_one_empty_file_among_good_ones_passes_but_is_named(self):
        gateway = self.gateway(lambda d: d.update(evaluations=[]))
        self.assertEqual(gateway.status, PASS)
        self.assertEqual(gateway.evaluated, 24 - 3)
        self.assertIn("08-blocked-action", gateway.detail)
        self.assertIn("explicitly empty", gateway.detail)

    def test_a_valid_file_and_a_broken_one_together_are_an_input_error_that_still_counts_the_valid_ones(self):
        self.fresh()
        self.write("10-degraded-modes/gateway-scenarios.json", "{}")
        gateway = self.run_stage("gateway")
        self.assertEqual(gateway.status, INPUT_ERROR)
        self.assertEqual(gateway.evaluated, 24 - 6)

    def test_an_evaluation_that_is_not_an_object_is_an_input_error_that_names_it(self):
        for label, row in (("a string", "not an object"), ("null", None), ("a number", 7), ("a list", [1]), ("a boolean", False)):
            with self.subTest(label):
                gateway = self.gateway(lambda d: d["evaluations"].append(row))
                self.assertEqual((gateway.status, [f.code for f in gateway.findings]), (INPUT_ERROR, ["INP002"]))
                self.assertIn("evaluation 4 is not an object", gateway.findings[0].message)
                self.assert_actionable(gateway, "gateway-scenarios.json")

    def test_a_row_that_is_not_an_object_is_not_counted_as_evaluated(self):
        """The file that holds it is rejected as a whole: it is not reported as three evaluations that passed and one that failed."""
        clean = self.gateway(lambda d: None)
        rejected = self.gateway(lambda d: d["evaluations"].append(None))
        self.assertEqual(clean.status, PASS)
        self.assertEqual(rejected.evaluated, clean.evaluated - 3)

    def test_a_row_without_a_part_it_cannot_be_evaluated_without_is_an_input_error_that_names_the_part(self):
        for part, remove in (("'proposal' reference", lambda d: d["evaluations"][0].pop("proposal")), ("'grant' reference", lambda d: d["evaluations"][0]["grant"].pop("version")),
                             ("commit time 'at'", lambda d: d["evaluations"][0].pop("at")), ("'expect' object", lambda d: d["evaluations"][0].update(expect=[]))):
            with self.subTest(part):
                gateway = self.gateway(remove)
                self.assertEqual((gateway.status, [f.code for f in gateway.findings]), (INPUT_ERROR, ["INP002"]))
                self.assertIn(part, gateway.findings[0].message)
                self.assert_actionable(gateway, "gateway-scenarios.json")

    def test_an_evaluation_that_names_a_proposal_that_does_not_exist_names_the_problem_in_words(self):
        gateway = self.gateway(lambda d: d["evaluations"][0]["proposal"].update(id="ACT-NONE"))
        self.assertEqual([f.code for f in gateway.findings], ["GW002"])
        self.assertNotIn("KeyError", gateway.findings[0].message)

    def test_a_ledger_mode_the_check_does_not_know_is_an_input_error_and_not_an_empty_ledger(self):
        """Any other value used to count no capacity at all and pass."""
        for label, value in (("an object", {}), ("another word", "none"), ("null", None), ("a number", 3), ("a list", ["from_receipts"])):
            with self.subTest(label):
                gateway = self.gateway(lambda d: d["evaluations"][0].update(ledger=value))
                self.assertEqual((gateway.status, [f.code for f in gateway.findings]), (INPUT_ERROR, ["INP002"]))
                self.assertIn("ledger", gateway.findings[0].message)
                self.assert_actionable(gateway, "gateway-scenarios.json")

    def test_both_ledger_modes_the_stored_evaluations_use_are_read(self):
        for mode in ("from_receipts", "empty"):
            with self.subTest(mode):
                self.assertEqual(self.gateway(lambda d: d["evaluations"][0].update(ledger=mode)).status in (PASS, FAIL), True)

    def test_an_override_that_acts_on_nothing_is_an_input_error_and_is_not_silently_ignored(self):
        bad = (("a target that does not exist", [{"on": "neither", "path": "/x", "value": 1}]), ("no target", [{"path": "/x", "value": 1}]),
               ("no path", [{"on": "grant", "value": 1}]), ("no value", [{"on": "grant", "path": "/x"}]), ("not an object", ["grant"]),
               ("evidence without its record", [{"on": "evidence", "path": "/x", "value": 1}]),
               ("evidence with a record that has no version", [{"on": "evidence", "path": "/x", "value": 1, "record": {"id": "M3W-0417"}}]))
        for label, overrides in bad:
            with self.subTest(label):
                gateway = self.gateway(lambda d: d["evaluations"][0].update(overrides=overrides))
                self.assertEqual((gateway.status, [f.code for f in gateway.findings]), (INPUT_ERROR, ["INP002"]))
                self.assertIn("override 1", gateway.findings[0].message)
                self.assert_actionable(gateway, "gateway-scenarios.json")
        self.assertEqual(self.gateway(lambda d: d["evaluations"][0].update(overrides="grant")).status, INPUT_ERROR, "overrides that are not a list")

    def test_an_expected_result_without_a_decision_or_codes_is_an_input_error_and_not_a_failure(self):
        for label, expect in (("empty", {}), ("an unknown decision", {"decision": "MAYBE", "codes": []}), ("no codes", {"decision": "ALLOW"}), ("codes that are not a list", {"decision": "ALLOW", "codes": "x"}),
                              ("a code that is not text", {"decision": "BLOCK", "codes": [7]})):
            with self.subTest(label):
                gateway = self.gateway(lambda d: d["evaluations"][0].update(expect=expect))
                self.assertEqual((gateway.status, [f.code for f in gateway.findings]), (INPUT_ERROR, ["INP002"]))
                self.assertIn("'expect' object", gateway.findings[0].message)

    def test_a_commit_time_that_is_not_a_time_is_an_input_error(self):
        for value in ("yesterday", "2026-11-23T10:03:00", "", 7):
            with self.subTest(repr(value)):
                gateway = self.gateway(lambda d: d["evaluations"][0].update(at=value))
                self.assertEqual((gateway.status, [f.code for f in gateway.findings]), (INPUT_ERROR, ["INP002"]))
                self.assertIn("'at'", gateway.findings[0].message)

    def test_the_file_name_is_matched_without_regard_to_case(self):
        self.fresh()
        (self.root / "08-blocked-action" / "gateway-scenarios.json").rename(self.root / "08-blocked-action" / "Gateway-Scenarios.JSON")
        gateway = self.run_stage("gateway")
        self.assertEqual((gateway.status, gateway.evaluated), (PASS, 24))

    def test_an_upper_case_extension_is_not_a_reason_to_leave_a_file_out(self):
        """A glob for *.json is case-sensitive on Linux and macOS and not on Windows, so the folder must be read the same way on all of them."""
        from eahs.model import json_files, load_model
        self.fresh()
        target = self.root / "01-source-records" / "c02-INV-2026-0417-v1.json"
        target.rename(target.with_suffix(".JSON"))
        (self.root / "Notes").mkdir()
        for name in ("a.Json", "b.txt", "c.json.bak"):
            (self.root / "Notes" / name).write_text("{}", encoding="utf-8")
        found = sorted(p.relative_to(self.root).as_posix() for p in json_files(self.root))
        self.assertIn("01-source-records/c02-INV-2026-0417-v1.JSON", found)
        self.assertIn("Notes/a.Json", found)
        self.assertNotIn("Notes/b.txt", found)
        self.assertNotIn("Notes/c.json.bak", found)
        model, problems = load_model(self.root)
        self.assertEqual(problems, [])
        self.assertIn(("C02", "INV-2026-0417", "v1"), model.instances)


class TheCaseFiles(Scratch, Actionable):
    NAME = "13-evaluation-cases/cases.json"

    def cases(self, change):
        self.fresh()
        self.edit_json(self.NAME, change)
        return self.run_stage("cases")

    def test_a_missing_cases_list_is_an_input_error(self):
        cases = self.cases(lambda d: d.pop("cases"))
        self.assertEqual((cases.status, [f.code for f in cases.findings]), (INPUT_ERROR, ["INP002"]))
        self.assertIn("no 'cases' list", cases.findings[0].message)
        self.assert_actionable(cases, "cases.json")

    def test_an_explicitly_empty_list_is_not_assessed(self):
        cases = self.cases(lambda d: d.update(cases=[]))
        self.assertEqual((cases.status, cases.evaluated), (NOT_ASSESSED, 0))
        self.assertIn("explicitly empty", cases.detail)

    def test_a_case_without_its_expected_codes_is_named(self):
        cases = self.cases(lambda d: d["cases"][2].pop("expect"))
        named = json.loads((self.root / self.NAME).read_text(encoding="utf-8"))["cases"][2]["case_id"]
        self.assertEqual(cases.status, INPUT_ERROR)
        self.assertIn(named, cases.findings[0].message)
        self.assertIn("'expect'", cases.findings[0].message)
        self.assert_actionable(cases, "cases.json")

    def test_a_case_that_is_not_an_object_is_named_by_position(self):
        cases = self.cases(lambda d: d["cases"].insert(0, 7))
        self.assertEqual(cases.status, INPUT_ERROR)
        self.assertIn("case 1 is not an object", cases.findings[0].message)

    def test_an_empty_object_is_an_input_error(self):
        self.fresh()
        (self.root / self.NAME).write_text("{}", encoding="utf-8")
        self.assertEqual(self.run_stage("cases").status, INPUT_ERROR)

    def test_a_case_with_no_name_and_no_mutation_is_an_input_error_and_not_a_pass(self):
        """{"cases": [{"expect": [], "mutations": []}]} used to pass: it evaluated the unchanged example set and counted it as a case."""
        self.fresh()
        (self.root / self.NAME).write_text(json.dumps({"cases": [{"expect": [], "mutations": []}]}), encoding="utf-8")
        cases = self.run_stage("cases")
        self.assertEqual((cases.status, cases.evaluated, [f.code for f in cases.findings]), (INPUT_ERROR, 0, ["INP002"]))
        self.assertIn("case_id", cases.findings[0].message)
        self.assert_actionable(cases, "cases.json")

    def test_every_part_a_case_is_judged_by_must_be_there(self):
        bad = (("no case_id", lambda c: c.pop("case_id"), "case_id"), ("an empty case_id", lambda c: c.update(case_id="  "), "case_id"), ("a case_id that is not text", lambda c: c.update(case_id=5), "case_id"),
               ("no mutation", lambda c: c.update(mutations=[]), "no mutation"), ("expect that is not a list of text", lambda c: c.update(expect=[1]), "'expect'"),
               ("a mutation that is not an object", lambda c: c.update(mutations=["x"]), "mutation 1 is not an object"),
               ("a mutation with no target", lambda c: c["mutations"][0].pop("target"), "no 'target'"), ("a target of the wrong form", lambda c: c["mutations"][0].update(target="C05"), "no 'target'"),
               ("a mutation with no operations", lambda c: c["mutations"][0].update(ops=[]), "no 'ops'"), ("an operation that does not exist", lambda c: c["mutations"][0]["ops"][0].update(op="move"), "operation 1"),
               ("an operation with no path", lambda c: c["mutations"][0]["ops"][0].pop("path"), "operation 1"),
               ("a replacement with no value", lambda c: c["mutations"][0]["ops"][0].update(op="replace") or c["mutations"][0]["ops"][0].pop("value", None), "needs a 'value'"))
        for label, damage, message in bad:
            with self.subTest(label):
                cases = self.cases(lambda d: damage(d["cases"][2]))
                self.assertEqual((cases.status, [f.code for f in cases.findings]), (INPUT_ERROR, ["INP002"]))
                self.assertIn(message, cases.findings[0].message)
                self.assert_actionable(cases, "cases.json")

    def test_a_target_that_does_not_exist_is_still_a_finding_of_the_case_and_not_a_shape(self):
        cases = self.cases(lambda d: d["cases"][2]["mutations"][0].update(target="C05 ACT-NONE v1"))
        self.assertEqual((cases.status, [f.code for f in cases.findings]), (FAIL, ["CASE003"]))


class TheResponseFiles(Scratch, Actionable):
    NAME = "06-assistant-response/response-PKT-0417-v2-template.json"

    def responses(self, change=None, content=None):
        self.fresh()
        if content is not None:
            (self.root / self.NAME).write_text(content, encoding="utf-8")
        else:
            self.edit_json(self.NAME, change)
        return self.run_stage("responses")

    def test_a_response_with_no_statements_list_is_an_input_error(self):
        responses = self.responses(lambda d: d.pop("statements"))
        self.assertEqual((responses.status, [f.code for f in responses.findings]), (INPUT_ERROR, ["INP002"]))
        self.assertIn("no 'statements' list", responses.findings[0].message)
        self.assert_actionable(responses, "response-PKT-0417-v2-template.json")

    def test_an_empty_object_is_an_input_error(self):
        self.assertEqual(self.responses(content="{}").status, INPUT_ERROR)

    def test_a_response_with_an_explicitly_empty_statements_list_is_evaluated_and_fails(self):
        responses = self.responses(lambda d: d.update(statements=[]))
        self.assertEqual(responses.status, FAIL)
        self.assertEqual(responses.evaluated, 3)
        self.assertIn("RESP004", {f.code for f in responses.findings})

    def test_a_file_that_is_not_an_object_is_an_input_error(self):
        responses = self.responses(content="[1, 2, 3]")
        self.assertEqual(responses.status, INPUT_ERROR)
        self.assertIn("must be a JSON object", responses.findings[0].message)


class MalformedAndZeroByteFiles(Scratch, Actionable):
    def test_a_malformed_or_zero_byte_stage_file_is_rejected_where_the_folder_is_indexed_and_blocks_the_rest(self):
        for name, dependent in (("gateway-scenarios.json", "gateway"), ("cases.json", "cases"), ("response-broken.json", "responses")):
            for label, content in (("malformed", '{"evaluations": [1, 2'), ("zero bytes", "")):
                with self.subTest("%s %s" % (name, label)):
                    self.fresh()
                    self.write("99-extra/" + name, content)
                    results = ve.run(self.root, only={"instances", dependent})
                    instances = stage(results, "instances")
                    self.assertEqual(instances.status, INPUT_ERROR)
                    self.assertEqual(instances.findings[0].code, "ID000")
                    self.assert_actionable(instances, name)
                    self.assertEqual(stage(results, dependent).status, NOT_ASSESSED)
                    self.assertEqual(overall(results), INPUT_ERROR)


class StrictJson(Scratch, Actionable):
    """JSON as RFC 8259 defines it. Python also reads NaN, Infinity, a number too large for a float and a repeated key (the
    last value wins), and other parsers do not, so such a file would mean one thing here and another elsewhere."""

    BAD = (("NaN", '{"evaluations": [], "x": NaN}'), ("Infinity", '{"evaluations": [], "x": Infinity}'), ("-Infinity", '{"x": -Infinity}'),
           ("a number too large for a float", '{"x": 1e999}'), ("a whole number too large for a float", '{"x": 1%s}' % ("0" * 400)),
           ("a number with more digits than a double keeps", '{"x": 40.000000000000001}'), ("a number too small for a double", '{"x": 1e-400}'),
           ("a number with an exponent no reader holds", '{"x": 1e-9999999999999999999999}'),
           ("a repeated key", '{"evaluations": [], "evaluations": [1]}'), ("a repeated key in a nested object", '{"evaluations": [{"a": 1, "a": 2}]}'))

    def test_each_is_an_input_error_in_a_stage_file_and_blocks_the_stages_that_need_the_model(self):
        for label, content in self.BAD:
            with self.subTest(label):
                self.fresh()
                self.write("99-extra/gateway-scenarios.json", content)
                results = ve.run(self.root, only={"instances", "gateway"})
                instances = stage(results, "instances")
                self.assertEqual((instances.status, instances.findings[0].code), (INPUT_ERROR, "ID000"))
                self.assert_actionable(instances, "gateway-scenarios.json")
                self.assertEqual(stage(results, "gateway").status, NOT_ASSESSED)

    def test_each_is_an_input_error_in_a_contract_instance_and_a_raw_export(self):
        for label, content in self.BAD:
            for name in ("01-source-records/c02-X-v1.json", "01-source-records/raw/export.json"):
                with self.subTest("%s in %s" % (label, name)):
                    self.fresh()
                    self.write(name, content)
                    instances = self.run_stage("instances")
                    self.assertEqual((instances.status, [f.code for f in instances.findings]), (INPUT_ERROR, ["ID000"]))

    def test_each_is_an_input_error_in_the_registry_and_names_it(self):
        for label, content in self.BAD:
            with self.subTest(label):
                self.fresh()
                (self.root / "registry.json").write_text(content, encoding="utf-8")
                instances = self.run_stage("instances")
                self.assertEqual(instances.status, INPUT_ERROR)
                self.assert_actionable(instances, "registry.json")

    def test_a_response_is_read_strictly_too(self):
        self.fresh()
        self.write("06-assistant-response/response-broken.json", '{"contract_id": "C04", "contract_id": "C05"}')
        results = ve.run(self.root, only={"instances", "responses"})
        self.assertEqual(stage(results, "instances").status, INPUT_ERROR)
        self.assertEqual(stage(results, "responses").status, NOT_ASSESSED)

    def test_the_command_reports_the_file_and_does_not_crash(self):
        self.fresh()
        self.write("99-extra/gateway-scenarios.json", '{"evaluations": [], "x": NaN}')
        done = cli("--examples", str(self.root))
        self.assertEqual(done.returncode, 2, done.stdout + done.stderr)
        self.assertNotIn("Traceback", done.stderr)
        self.assertIn("NaN", done.stdout)
        self.assertIn("gateway-scenarios.json", done.stdout)

    def test_a_reader_that_runs_out_of_stack_is_an_input_error_not_a_traceback(self):
        """How deep a document can be before the reader gives up depends on the platform, so the reader is made to give up."""
        from eahs import model as model_module
        out_of_stack = mock.Mock(loads=mock.Mock(side_effect=RecursionError("stack")))
        with mock.patch.object(model_module, "json", out_of_stack):
            with self.assertRaises(ValueError) as caught:
                model_module.loads_strict("[]")
        self.assertIn("nested too deeply", str(caught.exception))
        self.fresh()
        with mock.patch.object(model_module, "json", out_of_stack):
            instances = self.run_stage("instances")
        self.assertEqual(instances.status, INPUT_ERROR)
        self.assertEqual({f.code for f in instances.findings}, {"ID000"})
        self.assertIn("nested too deeply", instances.findings[0].message)

    def test_ordinary_numbers_still_read(self):
        from eahs.model import loads_strict
        self.assertEqual(loads_strict('{"a": 1, "b": -2.5, "c": 1e3, "d": [true, false, null], "e": {"a": 1}}'), {"a": 1, "b": -2.5, "c": 1000.0, "d": [True, False, None], "e": {"a": 1}})
        self.assertEqual(loads_strict('[0.1, 1e-7, 0.30000000000000004, -0.0, 18400.00, 40.0, 0.5000000000000000000000, 5e-324, 1.7976931348623157e308]'),
                         [0.1, 1e-07, 0.30000000000000004, -0.0, 18400.0, 40.0, 0.5, 5e-324, 1.7976931348623157e308])

    def test_a_number_that_a_double_cannot_hold_digit_for_digit_says_what_to_do(self):
        """40.000000000000001 reads as 40.0 here and may read as something else elsewhere, and a claim that states 40.0 would then pass for it."""
        from eahs.model import loads_strict
        for text in ("40.000000000000001", "0.1000000000000000055", "1e-400", "123456789012345678901234567890.0"):
            with self.subTest(text):
                with self.assertRaises(ValueError) as caught:
                    loads_strict('{"variance": %s}' % text)
                self.assertIn("more digits", str(caught.exception))
                self.assertIn("write it with fewer digits, or as a string", str(caught.exception))


class ADocumentNestedTooDeeplyIsRefusedWhereItIsRead(Scratch, Actionable):
    """A document nested hundreds of levels deep exhausted the stack of the checks that recurse (the schema check, the search for references) and ended in a traceback.
    It is refused when it is read, with the file named, and no check ever sees it."""

    INSTANCE = "01-source-records/c02-INV-2026-0417-v1.json"

    def deepen(self, depth):
        self.fresh()
        path = self.root / "03-lineage-and-common-origin" / "c02-M3W-0417-v1.json"
        text = path.read_text(encoding="utf-8")
        data = json.loads(text)
        data["content"]["payload"]["value"]["nested"] = "DEEP"
        path.write_text(json.dumps(data).replace('"DEEP"', "[" * depth + "7" + "]" * depth), encoding="utf-8")

    def test_the_depth_limit_is_far_above_anything_the_examples_need_and_far_below_the_stack(self):
        from eahs.model import MAX_DEPTH, loads_strict
        self.assertGreaterEqual(MAX_DEPTH, 3 * 11, "the deepest document of the examples nests 11 levels")
        self.assertEqual(loads_strict("[" * (MAX_DEPTH - 1) + "]" * (MAX_DEPTH - 1)), loads_strict("[" * (MAX_DEPTH - 1) + "]" * (MAX_DEPTH - 1)))
        with self.assertRaises(ValueError) as caught:
            loads_strict("[" * (MAX_DEPTH + 1) + "]" * (MAX_DEPTH + 1))
        self.assertIn("nested more than %d levels" % MAX_DEPTH, str(caught.exception))

    def test_a_document_nested_six_hundred_levels_deep_is_an_input_error_that_names_the_file(self):
        self.deepen(600)
        results = ve.run(self.root, only={"semantics"})
        instances, semantics_stage = stage(results, "instances"), stage(results, "semantics")
        self.assertEqual((instances.status, [f.code for f in instances.findings]), (INPUT_ERROR, ["ID000"]))
        self.assert_actionable(instances, "c02-M3W-0417-v1.json")
        self.assertIn("nested more than", instances.findings[0].message)
        self.assertEqual(semantics_stage.status, NOT_ASSESSED)

    def test_the_command_exits_2_with_a_result_and_no_traceback(self):
        self.deepen(600)
        done = cli("--examples", str(self.root), "--only", "semantics", "--json")
        self.assertEqual(done.returncode, 2, done.stdout + done.stderr)
        self.assertNotIn("Traceback", done.stderr)
        self.assertNotIn("RecursionError", done.stdout + done.stderr)
        self.assertEqual(json.loads(done.stdout)["status"], INPUT_ERROR)

    def test_a_document_just_inside_the_limit_is_read_and_does_not_crash_a_check(self):
        from eahs.model import MAX_DEPTH
        self.deepen(MAX_DEPTH - 12)
        for result in ve.run(self.root, only={"semantics"}):
            self.assertIn(result.status, (PASS, FAIL, INPUT_ERROR, NOT_ASSESSED, SKIPPED), result.stage)
        done = cli("--examples", str(self.root), "--only", "semantics")
        self.assertNotIn("Traceback", done.stderr)

    def test_a_recursion_error_raised_by_a_check_is_an_input_error_and_not_a_traceback(self):
        """The depth limit is the protection; this is the net under it, for a platform with a smaller stack."""
        self.fresh()

        def check_references(model):
            raise RecursionError("stack")
        with mock.patch.object(ve.semantics, "ALL_CHECKS", [check_references]):
            semantics_stage = self.run_stage("semantics")
        self.assertEqual(semantics_stage.status, INPUT_ERROR)
        self.assertIn("nested too deeply", semantics_stage.findings[0].message)
        self.assertTrue(semantics_stage.findings[0].file, "the diagnostic names where to look")


class TheRegistryFile(Scratch, Actionable):
    def test_a_registry_in_another_letter_case_is_still_the_registry(self):
        self.fresh()
        (self.root / "registry.json").rename(self.root / "REGISTRY.JSON")
        results = ve.run(self.root, only={"instances", "semantics", "gateway"})
        self.assertEqual({r.stage: r.status for r in results if r.stage in ("instances", "semantics", "gateway")}, {"instances": PASS, "semantics": PASS, "gateway": PASS})

    def test_a_registry_in_another_letter_case_is_read_strictly_too(self):
        self.fresh()
        (self.root / "registry.json").rename(self.root / "Registry.JSON")
        (self.root / "Registry.JSON").write_text('{"permission_decisions": NaN}', encoding="utf-8")
        instances = self.run_stage("instances")
        self.assertEqual(instances.status, INPUT_ERROR)
        self.assert_actionable(instances, "Registry.JSON")

    def test_two_registries_that_differ_only_by_case_are_refused_rather_than_one_chosen(self):
        from eahs.model import registry_path
        self.fresh()
        (self.root / "Registry.JSON").write_text("{}", encoding="utf-8")
        if len([p for p in self.root.iterdir() if p.name.lower() == "registry.json"]) < 2:
            self.skipTest("this file system does not tell the two names apart")
        with self.assertRaises(ValueError):
            registry_path(self.root)
        instances = self.run_stage("instances")
        self.assertEqual(instances.status, INPUT_ERROR)
        self.assertIn("more than one registry", instances.findings[0].message)


class ARegistrySectionOfTheWrongShape(Scratch, Actionable):
    """A section that a check reads as an object or a list is refused when the registry is read, with the registry and the section
    named, and not found out inside a check, where the diagnostic could not say which file was at fault."""

    def registry_with(self, edit):
        self.fresh()
        path = self.root / "registry.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        edit(data)
        path.write_text(json.dumps(data), encoding="utf-8")

    def freshness_policy(self):
        data = json.loads((self.root / "registry.json").read_text(encoding="utf-8"))
        return next((pid, version) for pid, versions in data["policies"].items() for version, policy in versions.items() if policy.get("type") == "freshness")

    def test_each_is_one_diagnostic_that_names_the_registry_and_the_section(self):
        cases = (
            ("producers", lambda d: d.update(producers=[]), "'producers' must be an object"),
            ("a producer without its kinds", lambda d: d["producers"].update({"producer:x": {}}), "permitted_kinds"),
            ("policies", lambda d: d.update(policies=["POL"]), "'policies' must be an object"),
            ("a policy that is not an object of versions", lambda d: d["policies"].update({"POL-X": []}), "policy 'POL-X'"),
            ("preconditions", lambda d: d.update(preconditions=None), "'preconditions' must be an object"),
            ("a precondition that is not an object", lambda d: d["preconditions"].update({"PRE-X": 3}), "precondition 'PRE-X'"),
            ("target states", lambda d: d.update(target_states={}), "'target_states' must be a list"),
            ("a target state that is not an object", lambda d: d["target_states"].append("open"), "'target_states' must list only objects"),
            ("protected terms", lambda d: d.update(protected_terms=[1]), "'protected_terms' must list only strings"),
            ("accountability", lambda d: d.update(accountability=[]), "'accountability' must be an object"),
            ("roles", lambda d: d["accountability"].update(roles=[]), "'accountability.roles'"),
            ("a role whose holders are not names", lambda d: d["accountability"]["roles"]["decision_owner"].update(holders=[[]]), "role 'decision_owner'"),
            ("a role whose principals are not a list", lambda d: d["accountability"]["roles"]["executor"].update(principals="workload:payment-executor"), "role 'executor'"),
            ("roles that may be held together, as numbers", lambda d: d["accountability"].update(may_hold_together=[[1, 2]]), "'accountability.may_hold_together'"),
            ("a review log entry without its actor", lambda d: d["accountability"]["review_log"][0].pop("actor"), "entry 1 of 'accountability.review_log'"),
            ("a review log entry with a time that is not a time", lambda d: d["accountability"]["review_log"][0].update(time="after lunch"), "not an RFC 3339 time"),
            ("a review log", lambda d: d["accountability"].update(review_log={}), "'accountability.review_log'"),
        )
        for label, edit, message in cases:
            with self.subTest(label):
                self.registry_with(edit)
                results = ve.run(self.root, only={"instances", "semantics"})
                instances = stage(results, "instances")
                self.assertEqual(instances.status, INPUT_ERROR)
                self.assertEqual([f.code for f in instances.findings], ["ID000"])
                self.assert_actionable(instances, "registry.json")
                self.assertIn(message, instances.findings[0].message)
                self.assertEqual(stage(results, "semantics").status, NOT_ASSESSED)

    def test_a_freshness_limit_that_is_not_a_number_of_hours_is_refused_at_the_registry(self):
        self.fresh()
        pid, version = self.freshness_policy()
        for label, value in (("text", "soon"), ("true", True), ("null", None), ("negative", -1), ("a list", [])):
            with self.subTest(label):
                self.registry_with(lambda d: d["policies"][pid][version].update(max_age_hours=value))
                instances = self.run_stage("instances")
                self.assertEqual((instances.status, [f.code for f in instances.findings]), (INPUT_ERROR, ["ID000"]))
                self.assertIn("max_age_hours", instances.findings[0].message)
                self.assert_actionable(instances, "registry.json")

    def test_a_limit_too_large_for_a_float_is_refused_when_the_registry_is_read(self):
        self.fresh()
        pid, version = self.freshness_policy()
        path = self.root / "registry.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data["policies"][pid][version]["max_age_hours"] = "HUGE"
        path.write_text(json.dumps(data).replace('"HUGE"', "1" + "0" * 400), encoding="utf-8")
        instances = self.run_stage("instances")
        self.assertEqual((instances.status, [f.code for f in instances.findings]), (INPUT_ERROR, ["ID000"]))
        self.assertIn("too large", instances.findings[0].message)
        self.assert_actionable(instances, "registry.json")

    def test_the_command_exits_with_input_error_and_no_traceback(self):
        self.registry_with(lambda d: d.update(producers=[]))
        done = cli("--examples", str(self.root))
        self.assertEqual(done.returncode, 2, done.stdout + done.stderr)
        self.assertNotIn("Traceback", done.stderr)
        self.assertIn("registry.json", done.stdout)
        self.assertIn("'producers' must be an object", done.stdout)

    def test_the_example_registry_and_an_empty_one_are_readable(self):
        from eahs.model import registry_from_dict, registry_problem
        self.assertIsNone(registry_problem(json.loads((support.EXAMPLES / "registry.json").read_text(encoding="utf-8"))))
        self.assertEqual(registry_from_dict({}).producers, {})


class ASchemaOnlyRun(Scratch):
    """The schema bundle does not depend on the folder, so a schema-only run does not index it."""

    def test_the_folder_is_never_indexed(self):
        self.fresh()
        self.write("stray.json", json.dumps({"contract_id": []}))
        with mock.patch.object(ve, "load_model", side_effect=AssertionError("the folder was indexed")):
            results = ve.run(self.root, only={"schema"})
        self.assertEqual(states(results), {"schema": PASS, "instances": SKIPPED, "semantics": SKIPPED, "gateway": SKIPPED, "responses": SKIPPED, "cases": SKIPPED})

    def test_files_the_model_could_not_index_do_not_disturb_it(self):
        self.fresh()
        self.write("a.json", "")
        self.write("b.json", '{"cut off')
        self.write("c02-X-v1.json", "{}")
        self.write("d.json", json.dumps({"contract_id": ["C02"]}))
        done = cli("--examples", str(self.root), "--only", "schema")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("Result: PASS for the stages that ran", done.stdout)
        self.assertNotIn("Traceback", done.stderr)

    def test_a_stage_that_does_need_the_folder_does_index_it(self):
        self.fresh()
        self.write("stray.json", json.dumps({"contract_id": []}))
        done = cli("--examples", str(self.root), "--only", "semantics")
        self.assertEqual(done.returncode, 2, done.stdout + done.stderr)
        self.assertIn("ID003", done.stdout)


class PartialRunsOnABrokenFolder(Scratch):
    def test_an_option_that_names_no_stage_is_refused_not_read_as_all_stages(self):
        self.fresh()
        for args in (("--only", ""), ("--only", ","), ("--only", " , "), ("--skip", ""), ("--skip", ",")):
            with self.subTest(args):
                done = cli("--examples", str(self.root), *args)
                self.assertEqual(done.returncode, 2, done.stdout + done.stderr)
                self.assertIn("names no stage", done.stderr)
                self.assertNotIn("Traceback", done.stderr)
                self.assertNotIn("Result: PASS", done.stdout)

    def test_no_selection_of_stages_raises(self):
        self.fresh()
        self.write("stray.json", json.dumps({"contract_id": []}))
        self.write("08-blocked-action/gateway-scenarios.json", "{}")
        for only in ("schema", "instances", "semantics", "gateway", "responses", "cases", "gateway,cases", "schema,responses"):
            with self.subTest(only):
                done = cli("--examples", str(self.root), "--only", only)
                self.assertIn(done.returncode, (0, 1, 2, 3), done.stdout + done.stderr)
                self.assertNotIn("Traceback", done.stderr)
                self.assertNotIn("Error:", done.stderr)

    def test_everything_skipped_is_not_assessed_on_a_broken_folder_too(self):
        self.fresh()
        self.write("stray.json", json.dumps({"contract_id": []}))
        done = cli("--examples", str(self.root), "--skip", ",".join(ve.STAGES))
        self.assertEqual(done.returncode, 3, done.stdout + done.stderr)
        self.assertNotIn("ID003", done.stdout)


class NothingEvaluable(Scratch):
    def test_stage_files_with_nothing_in_them_leave_every_dependent_stage_not_assessed(self):
        self.fresh()
        for path in list(self.root.rglob("gateway-scenarios.json")):
            path.write_text(json.dumps({"evaluations": []}), encoding="utf-8")
        self.edit_json("13-evaluation-cases/cases.json", lambda d: d.update(cases=[]))
        results = ve.run(self.root, only={"gateway", "cases"})
        self.assertEqual(states(results)["gateway"], NOT_ASSESSED)
        self.assertEqual(states(results)["cases"], NOT_ASSESSED)
        self.assertEqual(overall(results), NOT_ASSESSED)

    def test_a_missing_registry_is_one_diagnostic_naming_the_file_and_the_stage(self):
        self.fresh()
        (self.root / "registry.json").unlink()
        gateway = self.run_stage("gateway")
        self.assertEqual([(f.code, f.stage) for f in gateway.findings], [("INP003", "gateway")])
        self.assertIn("registry.json", gateway.findings[0].file)
        self.assertTrue(gateway.findings[0].hint)


if __name__ == "__main__":
    unittest.main()
