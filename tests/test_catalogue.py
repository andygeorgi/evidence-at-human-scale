"""The evaluation catalogue is a set of definitions. No row may carry a result, and the JSON and CSV copies must agree."""
import csv
import json
import re
import unittest
from collections import Counter

import support  # noqa: F401  (puts scripts/ on the path)

CATALOGUE = support.REPO / "evaluation" / "catalogue"
COUNTS = {"evaluation-tests": 12, "matched-baselines": 12, "fixtures": 70, "domain-parameters": 47}
KEYS = {"evaluation-tests": "id", "matched-baselines": "id", "fixtures": "fixture_id", "domain-parameters": "parameter_id"}
ID_PATTERNS = {
    "evaluation-tests": r"EV(0[1-9]|1[0-2])",
    "matched-baselines": r"BASE-(0[1-9]|1[0-2])",
    "fixtures": r"FX(0[1-9]|1[0-2])-\d\d",
    "domain-parameters": r"DP\d{3}",
}


def load(name):
    return json.loads((CATALOGUE / (name + ".json")).read_text(encoding="utf-8"))


def csv_rows(name):
    with open(CATALOGUE / (name + ".csv"), encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def cell(value):
    """How the exporter writes a JSON value into a CSV cell."""
    if value is None:
        return ""
    if isinstance(value, list):
        return " | ".join(str(item) for item in value)
    return str(value)


class Shape(unittest.TestCase):
    def test_row_counts(self):
        for name, count in COUNTS.items():
            self.assertEqual(len(load(name)), count, name)

    def test_ids_are_unique_and_well_formed(self):
        for name, pattern in ID_PATTERNS.items():
            ids = [row[KEYS[name]] for row in load(name)]
            self.assertEqual(len(ids), len(set(ids)), name)
            for value in ids:
                self.assertRegex(value, "^" + pattern + "$", name)

    def test_every_fixture_belongs_to_a_test_and_the_counts_agree(self):
        tests = {row["id"]: row for row in load("evaluation-tests")}
        per_test = Counter(row["evaluation_id"] for row in load("fixtures"))
        self.assertEqual(set(per_test), set(tests))
        for test_id, row in tests.items():
            self.assertEqual(row["fixture_count"], per_test[test_id], test_id)
        for row in load("fixtures"):
            self.assertEqual(row["fixture_id"][2:4], row["evaluation_id"][2:4], row["fixture_id"])


class NoResults(unittest.TestCase):
    def test_every_status_says_nothing_was_run(self):
        for name in ("evaluation-tests", "matched-baselines"):
            for row in load(name):
                self.assertEqual((row["status"], row["observed_status"]), ("NOT RUN", "NOT RUN"), (name, row["id"]))
        for row in load("fixtures"):
            self.assertEqual((row["status"], row["observed_gate_status"]), ("NOT RUN", "NOT RUN"), row["fixture_id"])

    def test_every_parameter_is_unset_and_not_assessed(self):
        for row in load("domain-parameters"):
            state = (row["value_state"], row["acceptance_state"], row["typed_value"], row["effective_time_utc"])
            self.assertEqual(state, ("UNSET", "NOT ASSESSED", None, None), row["parameter_id"])

    def test_no_row_claims_evidence_of_a_run(self):
        for name in ("evaluation-tests", "matched-baselines"):
            for row in load(name):
                self.assertRegex(row["evidence"], r"^No .* supplied", row["id"])
        for row in load("fixtures"):
            self.assertTrue(row["actual_run_evidence"].startswith("No execution attempted"), row["fixture_id"])

    def test_no_row_reports_a_pass_or_a_measurement(self):
        status_words = re.compile(r"\b(PASSED|PASS|FAILED|MET|ACHIEVED|ACCEPTED)\b")
        for name in COUNTS:
            for row in load(name):
                for field in ("status", "observed_status", "observed_gate_status", "value_state", "acceptance_state"):
                    if field in row:
                        self.assertIsNone(status_words.search(str(row[field])), (name, field, row[field]))


class JsonAndCsvAgree(unittest.TestCase):
    def test_same_rows_in_the_same_order(self):
        for name in COUNTS:
            rows, table = load(name), csv_rows(name)
            self.assertEqual(len(rows), len(table), name)
            self.assertEqual(list(rows[0]), list(table[0]), name)
            for row, line in zip(rows, table):
                self.assertEqual({key: cell(value) for key, value in row.items()}, line, (name, line.get(KEYS[name])))


if __name__ == "__main__":
    unittest.main()
