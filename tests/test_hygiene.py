"""The hygiene scanner must find what it claims to find, leave legitimate text alone, and the repository itself must pass it."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import support  # noqa: F401  (puts scripts/ on the path)

import check_hygiene as hyg


def codes_for(files, terms=()):
    """Scan a throwaway folder holding {relative path: text or bytes}; return the sorted set of finding codes.

    ``terms`` is the private term list. The tests never depend on the environment of whoever runs them.
    """
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        for name, content in files.items():
            target = root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            if isinstance(content, bytes):
                target.write_bytes(content)
            else:
                target.write_text(content, encoding="utf-8")
        findings, _notices, _count = hyg.scan(root, private_terms=list(terms))
    return sorted({f.code for f in findings})


def codes_for_text(text, name="docs/page.md", terms=()):
    return codes_for({name: text}, terms)


SYNTHETIC_TERMS = ("Zebracorp", r"Project Aurora\b")


class TheRepository(unittest.TestCase):
    def test_passes_its_own_scan(self):
        findings, _notices, count = hyg.scan(support.REPO)
        self.assertGreater(count, 100)
        self.assertEqual([f.format() for f in findings], [])

    def test_git_ignores_the_private_term_list(self):
        if not (support.REPO / ".git").exists():
            self.skipTest("not a git checkout")
        try:
            done = subprocess.run(["git", "-C", str(support.REPO), "check-ignore", "-q", hyg.PRIVATE_TERMS_FILE])
        except OSError:
            self.skipTest("git is not available")
        self.assertEqual(done.returncode, 0, "add %s to .gitignore: the list names the private origin of the material" % hyg.PRIVATE_TERMS_FILE)

    def test_no_file_is_committed_with_windows_line_endings(self):
        if not (support.REPO / ".git").exists():
            self.skipTest("not a git checkout")
        done = subprocess.run(["git", "-C", str(support.REPO), "ls-files", "--eol"], capture_output=True, text=True)
        if done.returncode != 0:
            self.skipTest("git is not available")
        crlf = [line.split("\t")[-1] for line in done.stdout.splitlines() if line.startswith("i/crlf") or line.split()[0] == "i/mixed"]
        self.assertEqual(crlf, [], ".gitattributes asks for LF; run git add --renormalize .")


class Detection(unittest.TestCase):
    def test_private_and_tenant_links(self):
        for text in ("see https://contoso-my.sharepoint.com/personal/x/doc", "https://1drv.ms/w/s!abc", "https://dev.azure.com/org/project"):
            self.assertEqual(codes_for_text(text), ["HYG101"], text)

    def test_local_paths(self):
        for text in ("C:\\Users\\someone\\notes.md", "/Users/someone/work/notes", "/home/someone/work/notes", "OneDrive - Contoso", "\\\\server\\share\\file", "file:///tmp/x"):
            self.assertEqual(codes_for_text(text), ["HYG102"], text)

    def test_generic_home_folders_are_not_local_paths(self):
        for text in ("/home/runner/work/repo", "/home/your-user/evidence-at-human-scale", "https://example.org/Users/x/y"):
            self.assertEqual(codes_for_text(text), [], text)

    def test_credentials(self):
        samples = ("ghp_" + "a" * 36, "AKIA" + "A" * 16, "-----BEGIN " + "RSA PRIVATE KEY-----", 'password = "hunter2hunter2"', "https://x.example/f?sig=" + "A" * 30)
        for text in samples:
            self.assertIn("HYG103", codes_for_text(text), text)

    def test_email_addresses(self):
        self.assertEqual(codes_for_text("write to someone@contoso.com"), ["HYG104"])
        for text in ("12345+someone@users.noreply.github.com", "name@example.com", "git@github.com:owner/repo.git"):
            self.assertEqual(codes_for_text(text), [], text)

    def test_internal_vocabulary_is_found_in_text_and_in_names(self):
        self.assertEqual(codes_for_text("This came from Zebracorp's notes.", terms=SYNTHETIC_TERMS), ["HYG105"])
        self.assertEqual(codes_for_text("The Project Aurora kickoff.", terms=SYNTHETIC_TERMS), ["HYG105"])
        self.assertEqual(codes_for({"docs/Zebracorp_notes.md": "plain text"}, SYNTHETIC_TERMS), ["HYG105"])
        self.assertEqual(codes_for_text("This came from Zebracorp's notes."), [], "with no list, nothing is private")

    def test_confidentiality_labels_are_found_without_any_list(self):
        for text in ("Internal Use Only", "marked Highly Confidential", "MSIP_Label_abc_Enabled=true"):
            self.assertEqual(codes_for_text(text), ["HYG105"], text)

    def test_the_citation_waiver_is_narrow(self):
        cited = "- **URL:** <https://www.stjornarradid.is/gogn/urskurdir/Akvordun-Zebracorp/>"
        self.assertEqual(codes_for({"references/public-records.md": cited}, SYNTHETIC_TERMS), [])
        self.assertEqual(codes_for({"references/public-records.md": "We worked with Zebracorp."}, SYNTHETIC_TERMS), ["HYG105"])
        self.assertEqual(codes_for({"docs/page.md": cited}, SYNTHETIC_TERMS), ["HYG105"])

    def test_hidden_characters(self):
        for text in ("a\u202eb", "\ufeffhello", "zero\u200bwidth"):
            self.assertEqual(codes_for_text(text), ["HYG106"], repr(text))

    def test_draft_markers(self):
        for text in ("TODO: write this", "to be decided: TBD", "Lorem ipsum dolor", "[insert name here]"):
            self.assertEqual(codes_for_text(text), ["HYG107"], text)

    def test_claims_of_finality_but_not_their_denial(self):
        for text in ("This is the final version.", "The canonical paper is here.", "officially published today"):
            self.assertEqual(codes_for_text(text), ["HYG108"], text)
        for text in ("This is a release candidate, not a final version.", "Nothing here is the canonical release."):
            self.assertEqual(codes_for_text(text), [], text)


class PrivateTerms(unittest.TestCase):
    """The list of private terms lives outside the repository, so the scanner must find it and must never publish it."""

    def test_terms_come_from_the_folder_file_and_from_the_environment(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / hyg.PRIVATE_TERMS_FILE).write_text("# a comment\n\nZebracorp\n  Project Aurora\\b  \n", encoding="utf-8")
            self.assertEqual(hyg.load_private_terms(root, environ={}), ["Zebracorp", r"Project Aurora\b"])
            self.assertEqual(hyg.load_private_terms(root, environ={hyg.PRIVATE_TERMS_ENV: "Borealis\nQuartz"}), ["Borealis", "Quartz", "Zebracorp", r"Project Aurora\b"])
            listing = root / "elsewhere.txt"
            listing.write_text("Borealis\n", encoding="utf-8")
            empty = root / "empty"
            self.assertEqual(hyg.load_private_terms(empty, environ={hyg.PRIVATE_TERMS_ENV: str(listing)}), ["Borealis"])
            self.assertEqual(hyg.load_private_terms(empty, environ={}), [])

    def test_a_list_in_the_folder_is_used_but_is_itself_a_finding(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "page.md").write_text("Notes from Zebracorp.\n", encoding="utf-8")
            (root / hyg.PRIVATE_TERMS_FILE).write_text("Zebracorp\n", encoding="utf-8")
            findings, _, _ = hyg.scan(root)
        self.assertEqual(sorted((f.code, f.path) for f in findings), [("HYG105", "page.md"), ("HYG207", hyg.PRIVATE_TERMS_FILE)])

    def test_a_scan_without_a_list_says_so(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "page.md").write_text("A page.\n", encoding="utf-8")
            self.assertTrue(any("private terms is off" in n for n in hyg.scan(Path(tmp), private_terms=[])[1]))
            self.assertFalse(any("private terms is off" in n for n in hyg.scan(Path(tmp), private_terms=["Zebracorp"])[1]))

    def test_an_invalid_term_is_reported_and_the_others_still_work(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "page.md").write_text("Notes from Zebracorp.\n", encoding="utf-8")
            findings, _, _ = hyg.scan(Path(tmp), private_terms=["(unclosed", "Zebracorp"])
        self.assertEqual(sorted(f.code for f in findings), ["HYG105", "HYG206"])
        self.assertIn("number 1", next(f.message for f in findings if f.code == "HYG206"))


class Files(unittest.TestCase):
    def test_blocked_types_and_editor_files(self):
        self.assertEqual(codes_for({"docs/report.docx": b"PK\x03\x04\x00\x00", "docs/paper.pdf": b"%PDF-1.7\n\x00"}), ["HYG201"])
        self.assertEqual(codes_for({".DS_Store": "x"}), ["HYG201"])
        self.assertEqual(codes_for({".env.local": "A=1"}), ["HYG201"])
        self.assertEqual(codes_for({".env.example": "A=1"}), [])

    def test_a_large_file(self):
        self.assertEqual(codes_for({"docs/big.md": "word " * 250000}), ["HYG202"])

    def test_not_text(self):
        self.assertEqual(codes_for({"data/blob.bin": b"\x00\x01\x02binary"}), ["HYG203"])
        self.assertEqual(codes_for({"data/latin1.md": b"caf\xe9"}), ["HYG203"])

    def test_names_that_do_not_survive_a_clone(self):
        found = {(f.code, f.path) for f in hyg.check_names(["a/CON.md", "a/trailing.md.", "x/y<z.md", "a/Readme.md", "a/README.md", "a/" + "n" * 210])}
        self.assertIn(("HYG204", "a/CON.md"), found)
        self.assertIn(("HYG204", "a/trailing.md."), found)
        self.assertIn(("HYG204", "x/y<z.md"), found)
        self.assertIn(("HYG205", "a/README.md"), found)
        self.assertTrue(any(code == "HYG204" and len(path) > 200 for code, path in found))

    def test_a_missing_license_is_a_notice_not_a_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "README.md").write_text("A page.\n", encoding="utf-8")
            findings, notices, _ = hyg.scan(Path(tmp), private_terms=[])
            self.assertEqual(findings, [])
            self.assertEqual(len([n for n in notices if "LICENSE" in n]), 1)
            (Path(tmp) / "LICENSE").write_text("A license text.\n", encoding="utf-8")
            self.assertEqual([n for n in hyg.scan(Path(tmp), private_terms=[])[1] if "LICENSE" in n], [])


class CommandLine(unittest.TestCase):
    def run_cli(self, root, *extra):
        return subprocess.run([sys.executable, str(support.SCRIPTS / "check_hygiene.py"), "--root", str(root)] + list(extra), capture_output=True, text=True, encoding="utf-8")

    def test_exit_codes_and_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "page.md").write_text("A clean page.\n", encoding="utf-8")
            done = self.run_cli(root)
            self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
            self.assertIn("Hygiene scan clean", done.stdout)
            (root / "page.md").write_text("Contact someone@contoso.com\n", encoding="utf-8")
            done = self.run_cli(root)
            self.assertEqual(done.returncode, 1)
            self.assertIn("page.md:1  HYG104", done.stdout)
            data = json.loads(self.run_cli(root, "--json").stdout)
            self.assertEqual([f["code"] for f in data["findings"]], ["HYG104"])

    def test_rules_listing(self):
        done = self.run_cli(support.REPO, "--rules")
        self.assertEqual(done.returncode, 0)
        for code in ("HYG101", "HYG108", "HYG205", "HYG206", "HYG207"):
            self.assertIn(code, done.stdout)
        self.assertIn("--history", done.stdout)

    def test_output_is_utf8_even_when_the_console_uses_a_legacy_code_page(self):
        """The rules text holds letters (an accented i, an eth) that a legacy Windows code page cannot print."""
        import os
        env = dict(os.environ, PYTHONIOENCODING="cp437", PYTHONUTF8="0")
        done = subprocess.run([sys.executable, str(support.SCRIPTS / "check_hygiene.py"), "--rules"], capture_output=True, env=env)
        self.assertEqual(done.returncode, 0, done.stderr.decode("utf-8", "replace"))
        self.assertIn("R\u00edkisendursko\u00f0un", done.stdout.decode("utf-8"))


class Speed(unittest.TestCase):
    def test_a_long_unbroken_run_of_characters_is_not_quadratic_for_the_e_mail_rule(self):
        """A rendered SVG can hold tens of thousands of characters with no separator; the scan must not slow to a crawl on them."""
        import time
        text = "@" + "a1-" * 40000 + "\n"
        start = time.perf_counter()
        codes_for_text(text, name="figures/x.svg")
        self.assertLess(time.perf_counter() - start, 5)


NOREPLY = ("Test Author", "1+test@users.noreply.github.com")


def git(root, *args, who=NOREPLY):
    env = dict(os.environ, GIT_AUTHOR_NAME=who[0], GIT_AUTHOR_EMAIL=who[1], GIT_COMMITTER_NAME=who[0], GIT_COMMITTER_EMAIL=who[1])
    done = subprocess.run(["git", "-C", str(root), "-c", "commit.gpgsign=false"] + list(args), capture_output=True, env=env)
    if done.returncode:
        raise RuntimeError("git %s failed: %s" % (" ".join(args), done.stderr.decode("utf-8", "replace")))


class History(unittest.TestCase):
    """The whole history is published by a push, so a term that was removed from the tree is still a finding in an old commit."""

    def repository(self, steps):
        """A throwaway repository. A step is (message, {path: text, bytes or None to delete}, who)."""
        tmp = tempfile.TemporaryDirectory()
        root = Path(tmp.name)
        git(root, "init", "-q")
        git(root, "symbolic-ref", "HEAD", "refs/heads/main")
        for message, files, who in steps:
            for name, content in files.items():
                target = root / name
                if content is None:
                    target.unlink()
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(content if isinstance(content, bytes) else content.encode("utf-8"))
            git(root, "add", "-A")
            git(root, "commit", "-q", "-m", message, who=who)
        self.addCleanup(tmp.cleanup)
        return root

    def setUp(self):
        try:
            subprocess.run(["git", "--version"], capture_output=True, check=True)
        except (OSError, subprocess.CalledProcessError):
            self.skipTest("git is not available")

    def test_a_term_that_was_removed_from_the_tree_is_still_found_in_the_history(self):
        root = self.repository([("add a page", {"docs/page.md": "Zebracorp wrote this\n"}, NOREPLY), ("remove the term", {"docs/page.md": "A clean page\n"}, NOREPLY)])
        head, _, _ = hyg.scan(root, private_terms=list(SYNTHETIC_TERMS))
        history, _, counts = hyg.scan_history(root, private_terms=list(SYNTHETIC_TERMS))
        self.assertEqual(head, [], "the tree itself is clean")
        self.assertEqual([f.code for f in history], ["HYG105"])
        self.assertRegex(history[0].path, r"^docs/page\.md @ [0-9a-f]{7}$")
        self.assertEqual((counts["commits"], counts["file_versions"]), (2, 2))

    def test_a_blocked_file_that_was_committed_and_removed_is_found(self):
        root = self.repository([("add a report", {"docs/report.docx": b"PK\x03\x04\x00\x00"}, NOREPLY), ("remove it", {"docs/report.docx": None}, NOREPLY)])
        history, _, _ = hyg.scan_history(root, private_terms=[])
        self.assertEqual(sorted({f.code for f in history}), ["HYG201"])

    def test_commit_messages_and_identities_are_scanned_and_each_identity_is_reported_once(self):
        stranger = ("Someone", "someone@contoso.com")
        root = self.repository([
            ("see C:\\Users\\someone\\notes for Zebracorp", {"a.md": "x\n"}, stranger),
            ("a second commit by the same person", {"a.md": "y\n"}, stranger),
            ("a fine commit", {"a.md": "z\n"}, NOREPLY)])
        history, _, _ = hyg.scan_history(root, private_terms=list(SYNTHETIC_TERMS))
        self.assertEqual(sorted({f.code for f in history}), ["HYG102", "HYG104", "HYG105"])
        by_where = [f.path.split(" ", 2)[-1] for f in history if f.code == "HYG104"]
        self.assertEqual(sorted(by_where), ["author", "committer"], "the address is reported once as author and once as committer, not once per commit")
        self.assertTrue(any(f.code == "HYG102" and f.path.endswith("message") for f in history))

    def test_a_noreply_address_a_clean_message_and_a_clean_tree_pass(self):
        root = self.repository([("add a page", {"docs/page.md": "A clean page\n"}, NOREPLY), ("edit it\n\nCo-authored-by: Copilot App <223556219+Copilot@users.noreply.github.com>", {"docs/page.md": "Another\n"}, NOREPLY)])
        history, notices, counts = hyg.scan_history(root, private_terms=[])
        self.assertEqual([f.format() for f in history], [])
        self.assertEqual(counts["commits"], 2)
        self.assertEqual(notices, [])

    def test_a_tag_is_reported_as_something_a_push_would_publish(self):
        root = self.repository([("add a page", {"docs/page.md": "A clean page\n"}, NOREPLY)])
        git(root, "tag", "-a", "v0", "-m", "a tag about Zebracorp")
        history, notices, _ = hyg.scan_history(root, private_terms=list(SYNTHETIC_TERMS))
        self.assertEqual([f.code for f in history], ["HYG105"])
        self.assertTrue(history[0].path.startswith("ref refs/tags/v0"))
        self.assertTrue(any("refs/tags/v0" in n for n in notices))

    def test_a_folder_that_is_not_a_repository_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(hyg.HistoryError):
                hyg.scan_history(Path(tmp), private_terms=[])

    def test_the_command_line_scans_the_history_on_request(self):
        root = self.repository([("add a page", {"docs/page.md": "Zebracorp wrote this\n"}, NOREPLY), ("remove the term", {"docs/page.md": "A clean page\n"}, NOREPLY)])
        env_terms = dict(os.environ, EAHS_PRIVATE_TERMS="Zebracorp")
        base = [sys.executable, str(support.SCRIPTS / "check_hygiene.py"), "--root", str(root)]
        plain = subprocess.run(base, capture_output=True, text=True, encoding="utf-8", env=env_terms)
        self.assertEqual(plain.returncode, 0, plain.stdout + plain.stderr)
        deep = subprocess.run(base + ["--history"], capture_output=True, text=True, encoding="utf-8", env=env_terms)
        self.assertEqual(deep.returncode, 1, deep.stdout + deep.stderr)
        self.assertIn("HYG105", deep.stdout)
        data = json.loads(subprocess.run(base + ["--history", "--json"], capture_output=True, text=True, encoding="utf-8", env=env_terms).stdout)
        self.assertEqual(data["history"]["commits"], 2)
        with tempfile.TemporaryDirectory() as empty:
            outside = subprocess.run([sys.executable, str(support.SCRIPTS / "check_hygiene.py"), "--root", empty, "--history"], capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(outside.returncode, 2)


if __name__ == "__main__":
    unittest.main()
