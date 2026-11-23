"""The structure check: one H1, no skipped heading levels, no empty table headers, no generic link text."""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import support  # noqa: F401  (puts scripts/ on the path)

import check_structure as structure


def codes(text, rel="docs/page.md"):
    return sorted({p.split("STR")[1][:3] for p in structure.check_page(rel, text)})


class Rules(unittest.TestCase):
    def test_a_well_formed_page_has_no_problems(self):
        text = "# Title\n\n## One\n\n### Sub\n\n## Two\n\nSee the [glossary](glossary.md).\n\n| A | B |\n|---|---|\n| 1 | 2 |\n"
        self.assertEqual(structure.check_page("docs/page.md", text), [])

    def test_exactly_one_h1(self):
        self.assertEqual(codes("## No title\n"), ["001"])
        self.assertEqual(codes("# One\n\n# Two\n"), ["001"])

    def test_headings_do_not_skip_a_level_going_down(self):
        self.assertEqual(codes("# T\n\n#### Deep\n"), ["002"])
        self.assertEqual(codes("# T\n\n## A\n\n### B\n\n## C\n"), [])

    def test_generic_link_text(self):
        for text in ("[here](a.md)", "[Click here](a.md)", "[this link](a.md)", "[read more](a.md)"):
            self.assertEqual(codes("# T\n\n" + text + "\n"), ["003"], text)
        self.assertEqual(codes("# T\n\n![here](a.svg)\n"), [])

    def test_an_empty_table_header(self):
        self.assertEqual(codes("# T\n\n| | |\n|---|---|\n| a | b |\n"), ["004"])

    def test_code_and_comments_are_ignored(self):
        text = "# T\n\n```md\n#### not a heading\n[here](x.md)\n```\n\n<!-- ### nor this -->\n"
        self.assertEqual(structure.check_page("docs/page.md", text), [])

    def test_templates_are_exempt(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".github" / "ISSUE_TEMPLATE").mkdir(parents=True)
            (root / ".github" / "ISSUE_TEMPLATE" / "a.md").write_text("**no heading**\n", encoding="utf-8")
            (root / "README.md").write_text("# Home\n", encoding="utf-8")
            problems, _ = structure.check(root.resolve())
            self.assertEqual(problems, [])


class TheRepository(unittest.TestCase):
    def test_passes(self):
        done = subprocess.run([sys.executable, str(support.SCRIPTS / "check_structure.py")], capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)


if __name__ == "__main__":
    unittest.main()
