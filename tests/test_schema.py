import re
import subprocess
import sys
import unittest

import support  # noqa: F401  (puts scripts/ on the path)

from eahs.schema import check_embedded_examples, check_schema_itself, is_rfc3339, validate_instance
from schema_surface_hash import recorded_hash, surface_hash


class SchemaBundle(unittest.TestCase):
    def test_bundle_is_a_valid_draft_2020_12_schema(self):
        self.assertEqual(check_schema_itself(support.schema()), [])

    def test_embedded_examples_behave_as_labelled(self):
        results = check_embedded_examples(support.schema())
        self.assertEqual(sum(1 for r in results if r.expected_valid), 38)
        self.assertEqual(sum(1 for r in results if not r.expected_valid), 64)
        self.assertEqual([r.case_id for r in results if not r.ok], [])

    def test_validation_surface_matches_the_recorded_hash(self):
        self.assertEqual(surface_hash(support.schema()), recorded_hash())

    def test_surface_hash_ignores_annotations_but_not_constraints(self):
        schema = support.schema()
        base = surface_hash(schema)
        annotated = dict(schema, title="Another title", description="Another description")
        self.assertEqual(surface_hash(annotated), base)
        stricter = {**schema, "$defs": {**schema["$defs"], "context": {**schema["$defs"]["context"], "minProperties": 99}}}
        self.assertNotEqual(surface_hash(stricter), base)


class Timestamps(unittest.TestCase):
    def test_accepts_complete_date_times(self):
        for value in ("2026-11-23T10:00:00Z", "2026-11-23T10:00:00.250+01:00", "2026-11-23t10:00:00z", "2026-12-31T23:59:60Z"):
            self.assertTrue(is_rfc3339(value), value)

    def test_rejects_ambiguous_or_impossible_values(self):
        for value in ("2026-11-23T10:00:00", "2026-11-23", "2026-02-30T00:00:00Z", "2026-13-01T00:00:00Z", "2026-11-23T24:00:00Z", "2026-11-23T10:00:00+25:00", "yesterday"):
            self.assertFalse(is_rfc3339(value), value)

    def test_an_instance_with_a_bare_local_time_is_rejected(self):
        instance = support.read_json("01-source-records/c02-INV-2026-0417-v1.json")
        instance["times"]["ingestion"] = "2026-11-23T07:31:00"
        self.assertTrue(validate_instance(support.schema(), instance))

    def test_the_message_names_the_bad_timestamp_and_not_an_alternative_the_value_never_aimed_at(self):
        instance = support.read_json("01-source-records/c02-INV-2026-0417-v1.json")
        instance["times"]["event"]["value"] = "2026-11-23T07:31:00"
        findings = validate_instance(support.schema(), instance)
        self.assertEqual(len(findings), 1)
        self.assertIn("2026-11-23T07:31:00", findings[0].message)
        self.assertIn("date-time", findings[0].message)
        self.assertNotIn("'reason' is a required property", findings[0].message)

    def test_a_bad_timestamp_is_one_finding_even_though_the_schema_states_it_twice(self):
        # the schema gives every timestamp both `format: date-time` and a `pattern`; the examples README tells a reader to break one
        instance = support.read_json("01-source-records/c02-AP-POLICY-4-v1.json")
        instance["producer_admission"]["admission_time"] = "2026-11-23T07:31:00"
        findings = validate_instance(support.schema(), instance)
        self.assertEqual([(f.code, f.location) for f in findings], [("SCH002", "/producer_admission/admission_time")])
        self.assertIn("date-time", findings[0].message)


class Diagnostics(unittest.TestCase):
    def test_no_embedded_invalid_example_reports_the_same_finding_twice(self):
        schema = support.schema()
        for entry in schema["x-documentation-examples"]:
            findings = validate_instance(schema, entry["instance"])
            keys = [(f.code, f.message, f.location) for f in findings]
            self.assertEqual(len(keys), len(set(keys)), entry["case_id"])
            self.assertTrue(findings, "%s is documented as invalid but nothing was reported" % entry["case_id"])


class SchemaReadme(unittest.TestCase):
    """The code in schemas/README.md is documentation that a reader will paste, so it has to run."""

    def snippet(self):
        text = (support.REPO / "schemas" / "README.md").read_text(encoding="utf-8")
        blocks = re.findall(r"```python\n(.*?)\n```", text, re.S)
        self.assertEqual(len(blocks), 1)
        return blocks[0]

    def run_snippet(self, code):
        done = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, encoding="utf-8", cwd=str(support.REPO))
        return done.returncode, done.stdout.strip(), done.stderr.strip()

    def test_the_snippet_runs_from_the_repository_root_and_says_valid(self):
        code, out, err = self.run_snippet(self.snippet())
        self.assertEqual((code, out), (0, "valid"), err)

    def test_the_snippet_reports_the_first_problem_of_an_invalid_instance(self):
        # an instance that is not an evidence record at all
        broken = self.snippet().replace('instance = json.load(open("examples/01-source-records/c02-INV-2026-0417-v1.json", encoding="utf-8"))', 'instance = {"contract_id": "C02"}')
        self.assertNotEqual(broken, self.snippet())
        code, out, err = self.run_snippet(broken)
        self.assertEqual(code, 0, err)
        self.assertNotEqual(out, "valid")


class CommandLine(unittest.TestCase):
    def test_validate_examples_passes_on_the_committed_examples(self):
        done = subprocess.run([sys.executable, str(support.SCRIPTS / "validate_examples.py")], capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("Result: PASS. All 6 stages passed", done.stdout)

    def test_validate_examples_fails_loudly_on_a_broken_example(self):
        import shutil
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmp:
            copy = Path(tmp) / "examples"
            shutil.copytree(support.EXAMPLES, copy)
            target = copy / "01-source-records" / "c02-INV-2026-0417-v1.json"
            text = target.read_text(encoding="utf-8").replace('"2026-11-23T07:31:00Z"', '"2026-11-23T07:31:00"', 1)
            target.write_text(text, encoding="utf-8")
            done = subprocess.run([sys.executable, str(support.SCRIPTS / "validate_examples.py"), "--examples", str(copy)], capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(done.returncode, 1)
        self.assertIn("FAIL", done.stdout)
        self.assertIn("SCH002", done.stdout)
        self.assertIn("read: contracts/c02-evidence.md", done.stdout)


if __name__ == "__main__":
    unittest.main()
