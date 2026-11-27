"""Release metadata must agree with itself: one version everywhere and no pre-release label, a citation file that names the
license and carries no address or affiliation, the MIT License as the one and only license, and a workflow that is read-only
and uses only pinned official actions."""
import hashlib
import re
import unittest

import support  # noqa: F401  (puts scripts/ on the path)

from eahs import __version__

REPO = support.REPO
MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
# The SHA-256 of LICENSE: the standard MIT text for the author. A change to the license is a decision of the author's, so it is a change here too.
LICENSE_SHA256 = "132671204afb198d8c953059b8ef8a9997e696105f8e1b995ebd4f2b13e294a1"
OTHER_LICENSES = re.compile(r"(?i)\b(?:Apache[- ]2\.0|CC[- ]BY(?:[- ]\d\.\d)?|Creative Commons|A?L?GPL|MPL|dual[- ]licen[sc]ed?)\b")
UNDECIDED = re.compile(r"(?i)no license|license (?:has|had) (?:not )?been chosen|license decision|decision is open")
PRE_RELEASE = re.compile(r"(?i)release[- ]candidate|\brc[-. ]?\d\b|public repository candidate|not a final release|offered for review")


def text(relative):
    return (REPO / relative).read_text(encoding="utf-8")


def release_date():
    """The date in CITATION.cff, written as the documents write it."""
    year, month, day = re.search(r'date-released: "(\d{4})-(\d{2})-(\d{2})"', text("CITATION.cff")).groups()
    return "%d %s %s" % (int(day), MONTHS[int(month) - 1], year)


class Version(unittest.TestCase):
    def test_the_same_version_is_stated_everywhere(self):
        self.assertEqual(__version__, "1.0.9")
        cff = text("CITATION.cff")
        self.assertEqual(len(re.findall(r'(?m)^\s*version: "%s"$' % re.escape(__version__), cff)), 2, "the version of the repository and that of its preferred citation")
        self.assertIn("## %s, %s\n" % (__version__, release_date()), text("CHANGELOG.md"))
        self.assertIn("`v%s`" % __version__, text("README.md"))
        self.assertIn("`v%s`" % __version__, text("schemas/README.md"))
        self.assertIn("## v%s\n" % __version__, text("contracts/CHANGES.md"))

    def test_the_release_date_is_the_same_in_the_citation_and_the_documents(self):
        for relative in ("CHANGELOG.md", "README.md", "docs/paper/README.md"):
            self.assertIn(release_date(), text(relative), relative)

    def test_it_is_a_release_and_no_page_or_script_still_calls_it_a_candidate(self):
        self.assertRegex(__version__, r"^\d+\.\d+\.\d+$", "a release, with no pre-release label")
        found = []
        for path in sorted(REPO.rglob("*")):
            relative = path.relative_to(REPO)
            if not path.is_file() or ".git" in relative.parts or relative.parts[0] == "tests" or path.suffix not in (".md", ".cff", ".yml", ".py"):
                continue
            found += [(relative.as_posix(), hit.group(0)) for hit in PRE_RELEASE.finditer(path.read_text(encoding="utf-8"))]
        self.assertEqual(found, [])


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

    def test_it_names_the_license_and_has_no_address_identifier_or_affiliation(self):
        cff = text("CITATION.cff")
        self.assertRegex(cff, r"(?m)^license: MIT$")
        self.assertNotIn("@", cff)
        self.assertNotRegex(cff, r"(?i)\bdoi\b")
        self.assertNotRegex(cff, r"(?im)^\s*affiliation\s*:")
        self.assertNotIn("Microsoft", cff)


class MitLicense(unittest.TestCase):
    def test_the_license_file_is_the_standard_mit_text_for_the_author_and_is_unaltered(self):
        raw = (REPO / "LICENSE").read_bytes()
        body = raw.decode("utf-8")
        self.assertTrue(body.startswith("MIT License\n\nCopyright (c) 2026 Andy Georgi\n\nPermission is hereby granted, free of charge, to any person"))
        self.assertNotIn("\r", body)
        self.assertEqual(hashlib.sha256(raw).hexdigest(), LICENSE_SHA256)

    def test_it_is_the_only_license_file_so_there_is_no_second_license(self):
        found = sorted(path.relative_to(REPO).as_posix() for path in REPO.rglob("*")
                       if path.is_file() and ".git" not in path.relative_to(REPO).parts and re.match(r"(?i)(licen[sc]e|copying|notice|unlicense|patents)", path.name))
        self.assertEqual(found, ["LICENSE"])

    def test_the_readme_license_section_says_that_the_repository_is_mit_licensed(self):
        section = text("README.md").split("\n## License\n", 1)[1].split("\n## ", 1)[0]
        self.assertEqual(section.strip(), "This repository is licensed under the [MIT License](LICENSE).")

    def test_the_documents_agree_that_it_is_mit_and_none_calls_the_license_undecided_or_names_another(self):
        for relative in ("README.md", "CONTRIBUTING.md", "CHANGELOG.md"):
            self.assertIn("[MIT License](LICENSE)", text(relative), relative)
        for relative in ("README.md", "CONTRIBUTING.md", "CHANGELOG.md", "CITATION.cff", "SECURITY.md", "docs/claims-and-limits.md"):
            self.assertNotRegex(text(relative), OTHER_LICENSES, relative)
            self.assertNotRegex(text(relative), UNDECIDED, relative)


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

    def test_python_3_9_runs_on_an_image_that_still_has_a_build_of_it(self):
        """ubuntu-latest is Ubuntu 26.04, which has no Python 3.9: the job that needs 3.9 on Linux names an image that does."""
        entries = dict((python, os_name) for os_name, python in re.findall(r'(?m)^\s*- \{os: ([\w.-]+), python: "([\d.]+)"\}', self.yml) if os_name.startswith("ubuntu"))
        self.assertEqual(entries["3.9"], "ubuntu-24.04")

    def test_the_url_check_is_advisory_and_not_run_on_pull_requests(self):
        job = self.yml.split("external-urls:", 1)[1]
        self.assertIn("continue-on-error: true", job)
        self.assertIn("github.event_name == 'schedule' || github.event_name == 'workflow_dispatch'", job)

    def test_the_documented_python_floor_matches_the_workflow(self):
        for relative in ("README.md", "CONTRIBUTING.md", "scripts/README.md", "examples/README.md"):
            self.assertIn("Python 3.9 or later", text(relative), relative)

    def test_the_checks_scan_the_whole_history_on_a_full_checkout(self):
        """A shallow checkout would leave most commits unread, and the scan refuses one: the job that runs it fetches everything."""
        job = self.yml.split("jobs:", 1)[1].split("external-urls:", 1)[0]
        self.assertIn("fetch-depth: 0", job)
        self.assertIn("scripts/check_all.py --verbose --history", job)
        self.assertNotIn("fetch-depth: 1", self.yml)

    def test_no_private_term_list_is_named_in_the_workflow_or_kept_in_the_repository(self):
        for name in ("EAHS_PRIVATE_TERMS", ".hygiene-private-terms"):
            self.assertNotIn(name, self.yml)
        self.assertIn(".hygiene-private-terms", text(".gitignore"))


if __name__ == "__main__":
    unittest.main()
