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


class CommandLine(unittest.TestCase):
    def test_validate_examples_passes_on_the_committed_examples(self):
        done = subprocess.run([sys.executable, str(support.SCRIPTS / "validate_examples.py")], capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("All 6 stages passed.", done.stdout)

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
            done = subprocess.run([sys.executable, str(support.SCRIPTS / "validate_examples.py"), "--examples", str(copy)], capture_output=True, text=True)
        self.assertEqual(done.returncode, 1)
        self.assertIn("FAIL", done.stdout)
        self.assertIn("SCH002", done.stdout)
        self.assertIn("read: contracts/c02-evidence.md", done.stdout)


if __name__ == "__main__":
    unittest.main()
