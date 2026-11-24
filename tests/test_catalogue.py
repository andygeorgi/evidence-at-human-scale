"""The evaluation catalogue is a set of definitions. No row may carry a result it did not earn, nothing may be said twice,
and the copies generated from the JSON must agree with it."""
import copy
import csv
import json
import re
import unittest
from collections import Counter

import support  # noqa: F401  (puts scripts/ on the path)
import build_catalogue as bc

CATALOGUE = support.REPO / "evaluation" / "catalogue"
COUNTS = {"evaluation-tests": 12, "matched-baselines": 12, "fixtures": 70, "domain-parameters": 47}
ID_PATTERNS = {
    "evaluation-tests": r"EV(0[1-9]|1[0-2])",
    "matched-baselines": r"BASE-(0[1-9]|1[0-2])",
    "fixtures": r"FX(0[1-9]|1[0-2])-\d\d",
    "domain-parameters": r"DP\d{3}",
}
SCHEMA = bc.load_schema()
PROCESS_WORDS = re.compile(r"workbook|rubric|supplementary|venue|clean-?up|convenience ratio|summaries removed|author's", re.I)


def tables():
    return {name: json.loads((CATALOGUE / (name + ".json")).read_text(encoding="utf-8")) for name in bc.TABLES}


def problems_in(data):
    return bc.consistency(data, SCHEMA)


class Shape(unittest.TestCase):
    def test_row_counts(self):
        for name, count in COUNTS.items():
            self.assertEqual(len(tables()[name]), count, name)

    def test_ids_are_unique_and_well_formed(self):
        for name, pattern in ID_PATTERNS.items():
            ids = [row[bc.KEY[name]] for row in tables()[name]]
            self.assertEqual(len(ids), len(set(ids)), name)
            for value in ids:
                self.assertRegex(value, "^" + pattern + "$", name)

    def test_the_tables_are_consistent_as_committed(self):
        self.assertEqual(problems_in(tables()), [])

    def test_every_test_has_fixtures_and_every_fixture_has_a_test(self):
        data = tables()
        per_test = Counter(row["evaluation_id"] for row in data["fixtures"])
        self.assertEqual(set(per_test), {row["id"] for row in data["evaluation-tests"]})

    def test_every_parameter_names_the_tests_that_use_it(self):
        data = tables()
        known = {row["id"] for row in data["evaluation-tests"]} | {"BASE"}
        used = set()
        for row in data["domain-parameters"]:
            self.assertTrue(row["used_by"], row["parameter_id"])
            self.assertTrue(set(row["used_by"]) <= known, row["parameter_id"])
            used.update(row["used_by"])
        self.assertEqual(used, known, "every test, and the baselines, needs at least one parameter")


class StatusRules(unittest.TestCase):
    """The states are defined in evaluation/README.md. A row cannot claim more than it has."""

    def fixture_run(self, data, status="RUN / PASS", record=True):
        row = data["fixtures"][0]
        row["status"] = status
        if record:
            row["run"] = {"command": "python scripts/example.py", "input": "FX01-01 as defined", "output": "exit 0"}
        return row

    def test_only_the_five_defined_states_exist(self):
        self.assertEqual(bc.STATES, ("RUN / PASS", "RUN / FAIL", "NOT RUN", "NOT ASSESSED", "UNSET"))
        data = tables()
        data["fixtures"][0]["status"] = "PASS"
        self.assertTrue(any("is not one of" in p for p in problems_in(data)))

    def test_a_run_status_needs_a_complete_run_record(self):
        data = tables()
        self.fixture_run(data, record=False)
        self.assertTrue(any("needs a run record" in p for p in problems_in(data)))
        data = tables()
        row = self.fixture_run(data)
        del row["run"]["output"]
        self.assertTrue(any("has no output" in p for p in problems_in(data)))
        data = tables()
        self.fixture_run(data)
        self.assertEqual(problems_in(data), [])

    def test_a_row_that_was_not_run_cannot_carry_a_run_record(self):
        data = tables()
        self.fixture_run(data, status="NOT ASSESSED")
        self.assertTrue(any("must not have a run record" in p for p in problems_in(data)))

    def test_a_test_cannot_pass_unless_every_fixture_did(self):
        data = tables()
        data["evaluation-tests"][0]["status"] = "RUN / PASS"
        data["evaluation-tests"][0]["run"] = {"command": "c", "input": "i", "output": "o"}
        self.assertTrue(any("not every fixture is" in p for p in problems_in(data)))

    def test_a_failed_fixture_cannot_be_hidden_by_its_test(self):
        data = tables()
        self.fixture_run(data, status="RUN / FAIL")
        self.assertTrue(any("hides a failed fixture" in p for p in problems_in(data)))

    def test_a_parameter_in_this_catalogue_is_unset(self):
        data = tables()
        data["domain-parameters"][0]["status"] = "NOT ASSESSED"
        self.assertTrue(any("is UNSET" in p for p in problems_in(data)))

    def test_no_row_reports_a_pass_or_a_measurement_without_a_run(self):
        data = tables()
        for name in bc.TABLES:
            for row in data[name]:
                if "run" not in row:
                    self.assertNotRegex(row["status"], r"PASS|FAIL", (name, row[bc.KEY[name]]))


class NothingIsSaidTwice(unittest.TestCase):
    def test_no_row_repeats_one_field_in_another(self):
        for name, rows in tables().items():
            for row in rows:
                texts = [json.dumps(v, ensure_ascii=False) for k, v in row.items() if k != "status" and v not in (None, "", [])]
                self.assertEqual(len(texts), len(set(texts)), (name, row[bc.KEY[name]]))

    def test_no_column_is_the_same_in_every_row(self):
        for name, rows in tables().items():
            for field in bc.FIELDS[name]:
                if field == "status":
                    continue
                distinct = {json.dumps(row[field], sort_keys=True) for row in rows}
                self.assertGreater(len(distinct), 1, "%s.%s is constant: say it once in the README" % (name, field))

    def test_the_fields_the_catalogue_used_to_repeat_are_gone(self):
        gone = {"dependent_decision", "measurement_plan", "observed_status", "observed_gate_status", "actual_run_evidence",
                "coverage_and_limits", "scope_and_uncertainty", "positive_denominator_definition", "fixture_family", "fixture_count"}
        for name, rows in tables().items():
            for row in rows:
                self.assertFalse(gone & set(row), (name, row[bc.KEY[name]]))

    def test_a_blanket_contract_mapping_is_not_allowed(self):
        data = tables()
        for row in data["fixtures"]:
            self.assertRegex(" ".join(row["contracts"]), r"^C0[1-7]( C0[1-7])*$", row["fixture_id"])
        sizes = Counter(len(row["contracts"]) for row in data["fixtures"])
        self.assertGreater(len(sizes), 3, "the fixtures name different numbers of contracts")
        row = data["fixtures"][0]
        row["contracts"] = ["C01", "C02", "C03", "C04", "C05", "C06", "C07"]
        self.assertTrue(any("its own references name" in p for p in problems_in(data)))

    def test_a_tests_contracts_are_those_of_its_fixtures(self):
        data = tables()
        data["evaluation-tests"][1]["contracts"] = ["C01"]
        self.assertTrue(any("its fixtures cover" in p for p in problems_in(data)))

    def test_no_authoring_process_text_remains(self):
        for name in bc.TABLES:
            for suffix in (".json", ".csv"):
                text = (CATALOGUE / (name + suffix)).read_text(encoding="utf-8")
                self.assertIsNone(PROCESS_WORDS.search(text), name + suffix)
        for path in (CATALOGUE / "README.md", support.REPO / "evaluation" / "oracles.md"):
            self.assertIsNone(PROCESS_WORDS.search(path.read_text(encoding="utf-8")), path.name)


class ContractPages(unittest.TestCase):
    """Each contract page lists the tests that exercise it as their subject, as the schema's crosswalk does. This is a narrower
    question than which contracts a fixture's inputs contain, so it is not the catalogue's `contracts` column."""

    LINE = re.compile(r"\*\*Evaluation tests:\*\* (.+?) \(([A-Z ]+)\)")

    def expand(self, text):
        found = set()
        for part in text.split(", "):
            if "\u2013" in part:
                first, last = part.split("\u2013")
                found.update("EV%02d" % n for n in range(int(first[2:]), int(last[2:]) + 1))
            else:
                found.add(part)
        return found

    def test_every_page_lists_what_the_schema_crosswalk_lists_for_its_contract(self):
        data = tables()
        known = {row["id"]: row["status"] for row in data["evaluation-tests"]}
        for number in range(1, 8):
            contract = "C%02d" % number
            page = next((support.REPO / "contracts").glob("c%02d-*.md" % number))
            match = self.LINE.search(page.read_text(encoding="utf-8"))
            self.assertIsNotNone(match, page.name)
            crosswalk = {link for entry in SCHEMA["x-contract-crosswalk"] if entry["contract_id"] == contract
                         for link in entry["fixture_links"].split("/")}
            listed = self.expand(match.group(1))
            self.assertEqual(listed, crosswalk, page.name)
            self.assertTrue(listed <= set(known), page.name)
            self.assertEqual({known[test] for test in listed}, {match.group(2)}, page.name)
            for entry in SCHEMA["x-contract-crosswalk"]:
                self.assertIn(entry["architectural_status"], {"NOT ASSESSED"}, entry["mapping_id"])


class Copies(unittest.TestCase):
    def test_the_csv_files_and_the_oracles_page_are_what_the_generator_writes(self):
        self.assertEqual(bc.problems(), [])

    def test_the_csv_holds_the_json_rows_in_the_same_order(self):
        for name, rows in tables().items():
            with open(CATALOGUE / (name + ".csv"), encoding="utf-8", newline="") as handle:
                lines = list(csv.DictReader(handle))
            self.assertEqual(len(lines), len(rows), name)
            self.assertEqual(list(lines[0]), list(bc.FIELDS[name]), name)
            for row, line in zip(rows, lines):
                self.assertEqual({k: bc.cell(row[k]) for k in bc.FIELDS[name]}, line, (name, row[bc.KEY[name]]))

    def test_the_oracles_page_lists_every_fixture_once_and_every_test_in_its_own_section(self):
        page = (support.REPO / "evaluation" / "oracles.md").read_text(encoding="utf-8")
        for row in tables()["fixtures"]:
            self.assertEqual(page.count("| %s |" % row["fixture_id"]), 1, row["fixture_id"])
        for row in tables()["evaluation-tests"]:
            self.assertEqual(len(re.findall(r"^## %s " % row["id"], page, re.M)), 1, row["id"])

    def test_a_stale_copy_is_noticed(self):
        data = tables()
        data["fixtures"][0]["expected_oracle"] += " Changed."
        wanted = bc.generated_files(data)
        self.assertNotEqual(wanted[bc.ORACLES], bc.ORACLES.read_text(encoding="utf-8"))
        self.assertNotEqual(wanted[CATALOGUE / "fixtures.csv"], (CATALOGUE / "fixtures.csv").read_text(encoding="utf-8"))

    def test_a_run_record_reaches_the_csv(self):
        data = copy.deepcopy(tables())
        row = data["fixtures"][0]
        row["status"] = "RUN / PASS"
        row["run"] = {"command": "python x.py", "input": "FX01-01", "output": "ok"}
        header = bc.csv_text("fixtures", data["fixtures"]).splitlines()[0].split(",")
        self.assertEqual(header[-3:], ["run_command", "run_input", "run_output"])


if __name__ == "__main__":
    unittest.main()
