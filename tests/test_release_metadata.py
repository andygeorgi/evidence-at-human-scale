"""Release metadata must agree with itself: one version everywhere, a citation file without a license or an address,
no license file while the decision is open, and a workflow that is read-only and uses only pinned official actions."""
import re
import unittest

import support  # noqa: F401  (puts scripts/ on the path)

from eahs import __version__

REPO = support.REPO


def text(relative):
    return (REPO / relative).read_text(encoding="utf-8")


class Version(unittest.TestCase):
    def test_the_same_version_is_stated_everywhere(self):
        self.assertEqual(__version__, "1.0.0-rc.1")
        self.assertIn('version: "%s"' % __version__, text("CITATION.cff"))
        self.assertIn("(%s)" % __version__, text("CITATION.cff"))
        self.assertIn("## %s:" % __version__, text("CHANGELOG.md"))
        self.assertIn("`v%s`" % __version__, text("README.md"))

    def test_the_release_date_is_the_same_in_the_changelog_and_the_citation(self):
        cff_date = re.search(r'date-released: "(\d{4})-(\d{2})-(\d{2})"', text("CITATION.cff")).groups()
        months = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
        long_date = "%d %s %s" % (int(cff_date[2]), months[int(cff_date[1]) - 1], cff_date[0])
        self.assertIn(long_date, text("CHANGELOG.md"))
        self.assertIn(long_date, text("README.md"))

    def test_it_is_called_a_release_candidate_not_a_release(self):
        self.assertIn("not a final release", text("README.md"))
        self.assertIn("not a final release", text("CHANGELOG.md"))


class Citation(unittest.TestCase):
    def test_required_keys_and_the_title_agree_with_the_readme(self):
        cff = text("CITATION.cff")
        for key in ("cff-version: 1.2.0", "message:", "title:", "authors:", "family-names: Georgi", "given-names: Andy", "date-released:", "version:"):
            self.assertIn(key, cff)
        title = re.search(r'^title: "(.+)"$', cff, re.M).group(1)
        readme = text("README.md")
        heading = re.search(r"^# (.+)$", readme, re.M).group(1)
        subtitle = re.search(r"^\*\*(.+)\*\*$", readme, re.M).group(1)
        self.assertEqual(title.lower(), ("%s: %s" % (heading, subtitle)).lower())

    def test_no_license_field_no_address_no_identifier_claiming_publication(self):
        cff = text("CITATION.cff")
        self.assertNotRegex(cff, r"(?m)^\s*license")
        self.assertNotIn("@", cff)
        self.assertNotRegex(cff, r"(?i)\bdoi\b")


class NoLicenseYet(unittest.TestCase):
    def test_there_is_no_license_file_and_the_documents_say_so(self):
        names = {p.name.lower() for p in REPO.iterdir()}
        self.assertFalse(names & {"license", "license.md", "license.txt", "copying", "copying.md", "unlicense"})
        self.assertIn("No license has been chosen yet", text("README.md"))
        self.assertIn("No license yet", text("CONTRIBUTING.md"))
        self.assertIn("No license has been chosen", text("CHANGELOG.md"))

    def test_nothing_in_the_repository_grants_a_license(self):
        for relative in ("README.md", "CONTRIBUTING.md", "CHANGELOG.md", "CITATION.cff", "SECURITY.md"):
            self.assertNotRegex(text(relative), r"(?i)\b(MIT|Apache[- ]2\.0|CC[- ]BY|GPL)\b", relative)


class Workflow(unittest.TestCase):
    def setUp(self):
        self.yml = text(".github/workflows/validate.yml")

    def test_permissions_are_read_only(self):
        self.assertRegex(self.yml, r"(?m)^permissions:\n  contents: read\n")
        self.assertNotRegex(self.yml, r"(?i)\bwrite\b")
        self.assertNotIn("pull_request_target", self.yml)
        self.assertNotIn("secrets.", self.yml)

    def test_only_official_actions_pinned_to_a_commit(self):
        uses = re.findall(r"(?m)^\s*uses:\s*(\S+)", self.yml)
        self.assertGreaterEqual(len(uses), 4)
        for action in uses:
            self.assertRegex(action, r"^actions/[a-z-]+@[0-9a-f]{40}$", action)

    def test_it_runs_on_linux_and_windows_and_checks_the_oldest_supported_python(self):
        self.assertIn("ubuntu-latest", self.yml)
        self.assertIn("windows-latest", self.yml)
        self.assertIn('"3.9"', self.yml)
        self.assertIn("scripts/check_all.py", self.yml)

    def test_every_python_runs_on_linux_and_on_windows(self):
        """Coverage must not be dropped quietly when a runner image loses a Python version: each of the four combinations stays."""
        entries = re.findall(r'(?m)^\s*- \{os: ([\w.-]+), python: "([\d.]+)"\}', self.yml)
        self.assertEqual(sorted((os_name.split("-")[0], python) for os_name, python in entries),
                         [("ubuntu", "3.14"), ("ubuntu", "3.9"), ("windows", "3.14"), ("windows", "3.9")])

    def test_the_url_check_is_advisory_and_not_run_on_pull_requests(self):
        job = self.yml.split("external-urls:", 1)[1]
        self.assertIn("continue-on-error: true", job)
        self.assertIn("github.event_name == 'schedule' || github.event_name == 'workflow_dispatch'", job)

    def test_the_documented_python_floor_matches_the_workflow(self):
        for relative in ("README.md", "CONTRIBUTING.md", "scripts/README.md", "examples/README.md"):
            self.assertIn("Python 3.9 or later", text(relative), relative)


if __name__ == "__main__":
    unittest.main()
