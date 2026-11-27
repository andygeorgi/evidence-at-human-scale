"""The Quickstart is the first thing a reader runs, so what the documents say it prints must be what it prints."""
import os
import re
import subprocess
import sys
import unittest

import support  # noqa: F401  (puts scripts/ on the path)

from eahs import __version__

REPO = support.REPO


def run_quickstart():
    env = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
    done = subprocess.run([sys.executable, str(support.SCRIPTS / "validate_examples.py")], capture_output=True, text=True, encoding="utf-8", cwd=str(REPO), env=env)
    return done.returncode, done.stdout.strip()


def text_blocks(relative):
    return re.findall(r"```text\n(.*?)\n```", (REPO / relative).read_text(encoding="utf-8"), re.S)


class ExpectedOutput(unittest.TestCase):
    def test_the_readme_and_the_examples_guide_show_the_real_output(self):
        code, actual = run_quickstart()
        self.assertEqual(code, 0, actual)
        for page in ("README.md", "examples/README.md"):
            blocks = [block.strip() for block in text_blocks(page) if block.startswith("Evidence at Human Scale")]
            self.assertEqual(len(blocks), 1, page)
            self.assertEqual(blocks[0], actual, page)

    def test_the_output_names_the_released_version(self):
        self.assertTrue(run_quickstart()[1].startswith("Evidence at Human Scale %s: example validation" % __version__))

    def test_the_quickstart_commands_in_the_readme_exist(self):
        readme = (REPO / "README.md").read_text(encoding="utf-8")
        section = readme.split("## Quickstart", 1)[1].split("\n## ", 1)[0]
        commands = re.findall(r"^python (?!-m pip)(\S+\.py)", section, re.M)
        self.assertEqual(commands, ["scripts/validate_examples.py"])
        for command in commands:
            self.assertTrue((REPO / command).is_file(), command)
        self.assertIn("python -m pip install -r requirements.txt", section)
        self.assertTrue((REPO / "requirements.txt").is_file())

    def test_the_sentence_before_the_output_names_the_command_that_prints_it(self):
        """The output belongs to the validator, which is the second command of the block, not to the installation before it."""
        readme = (REPO / "README.md").read_text(encoding="utf-8")
        section = readme.split("## Quickstart", 1)[1].split("\n## ", 1)[0]
        lead = section.split("```text", 1)[0].rstrip().splitlines()[-1]
        self.assertTrue(lead.rstrip().endswith("should print:"), lead)
        self.assertIn("validate_examples.py", lead)
        self.assertNotIn("first command", lead)

    def test_the_ten_minute_path_leads_to_pages_that_exist(self):
        readme = (REPO / "README.md").read_text(encoding="utf-8")
        path = readme.split("## Ten-minute path", 1)[1].split("\n## Quickstart", 1)[0]
        targets = re.findall(r"\]\(([^)#]+)(?:#[^)]*)?\)", path)
        self.assertGreaterEqual(len(targets), 4)
        for target in targets:
            self.assertTrue((REPO / target).exists(), target)


if __name__ == "__main__":
    unittest.main()
