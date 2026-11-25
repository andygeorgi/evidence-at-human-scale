"""The hygiene scanner must find what it claims to find, leave legitimate text alone, and the repository itself must pass it."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

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
STRANGER = "other" + "@fabrikam.com"  # an address that no exception covers, written so that this file does not contain it
PRIVATE_TERM = "Quill" + "feather"  # an invented private term, written so that this file does not contain it
FINAL, OFFICIAL = "fin" + "al", "offic" + "ial"  # words of a claim of finality, written so that this file does not make one


class TheRepository(unittest.TestCase):
    def test_passes_its_own_scan(self):
        findings, _notices, count = hyg.scan(support.REPO)
        self.assertGreater(count, 100)
        self.assertEqual([f.format() for f in findings], [])

    def test_the_scan_needs_no_private_list_to_hold_the_authority_boundary(self):
        """Continuous integration has no private list; the authority's name is still found there, because the scanner knows it as a digest."""
        findings, _notices, _count = hyg.scan(support.REPO, private_terms=[])
        self.assertEqual([f.format() for f in findings], [])
        self.assertTrue(hyg.NAME_STEMS and all(len(digest) == 64 for _length, digest in hyg.NAME_STEMS))
        with mock.patch.object(hyg, "PUBLIC_SOURCE_LINES", ()):
            unpinned, _notices, _count = hyg.scan(support.REPO, private_terms=[])
        self.assertTrue(unpinned and {f.code for f in unpinned} == {"HYG105"}, "the same scan, with no pin and no list, finds the name by its digest: the clean result above is not vacuous")

    SELF = ("scripts/check_hygiene.py", "tests/test_hygiene.py")

    def own_bytes(self, rel):
        return (support.REPO / rel).read_bytes()

    def test_the_two_files_that_quote_the_patterns_are_scanned_by_every_rule(self):
        """No whole file is exempt: a leak pasted into the scanner or into its tests is found like one anywhere else."""
        leaks = {
            "HYG101": b"\n# https://realcustomer." + b"share" + b"point.com/sites/secret-deal\n",
            "HYG102": b"\n/Users/" + b"anyone/notes\n",
            "HYG103": b"\nghp_" + b"a" * 36 + b"\n",
            "HYG104": b"\n" + STRANGER.encode() + b"\n",
            "HYG105": b"\n" + PRIVATE_TERM.encode() + b"\n",
            "HYG106": "\n\u202e\n".encode("utf-8"),
            "HYG107": b"\n# TO" + b"DO: resolve the deal\n",
            "HYG108": ("\nThis is the " + FINAL + " version.\n").encode(),
        }
        hyg.use_private_terms([PRIVATE_TERM])
        self.addCleanup(hyg.use_private_terms, [])
        for rel in self.SELF:
            data = self.own_bytes(rel)
            self.assertEqual([f.format() for f in hyg.scan_bytes(rel, data)], [], rel)
            for code, extra in leaks.items():
                self.assertEqual(sorted({f.code for f in hyg.scan_bytes(rel, data + extra)}), [code], "%s: %s pasted into the file must be found" % (rel, code))

    def test_a_private_link_path_or_label_of_the_same_kind_as_a_quoted_sample_is_still_found(self):
        """Pinning a quoted sample line does not excuse the same kind of text on another line, nor any addition to the pinned line."""
        hyg.use_private_terms([])
        smuggled = {
            "HYG101": b"# https://realcustomer." + b"share" + b"point.com/sites/secret-deal",
            "HYG102": b"# file:" + b"///Volumes/SecretShare/deal.pdf",
            "HYG105": b"# MSI" + b"P_Label_7f9a8b_Enabled=True",
        }
        for rel in self.SELF:
            lines = self.own_bytes(rel).split(b"\n")
            pinned = [(n, line) for n, line in enumerate(lines) for q in hyg.QUOTED_LINES if q.path == rel and hyg.line_digest(line.decode("utf-8")) in q.digests]
            self.assertTrue(pinned, rel)
            for code, text in smuggled.items():
                with self.subTest("%s %s on a new line" % (rel, code)):
                    self.assertIn(code, {f.code for f in hyg.scan_bytes(rel, b"\n".join(lines) + b"\n" + text + b"\n")})
                number, line = pinned[0]
                with self.subTest("%s %s added to a pinned line" % (rel, code)):
                    lines_added = list(lines)
                    lines_added[number] = line + b" " + text
                    self.assertTrue({f.code for f in hyg.scan_bytes(rel, b"\n".join(lines_added))} - {"HYG107"}, "text added to a pinned line voids the pin")

    def test_the_quoted_lines_are_exactly_the_lines_the_two_files_quote(self):
        """With no exception at all the two files produce exactly the listed (rule, line) pairs, so no entry is stale and no other line is hidden."""
        hyg.use_private_terms([])
        listed = {(q.path, q.rule, digest) for q in hyg.QUOTED_LINES for digest in q.digests}
        self.assertEqual({path for path, _rule, _digest in listed}, set(self.SELF))
        found = set()
        for rel in self.SELF:
            for line in self.own_bytes(rel).decode("utf-8").split("\n"):
                for rule in hyg.RULES:
                    if next(hyg.find_matches(rule, rel, line), None) is not None:
                        found.add((rel, rule.code, hyg.line_digest(line)))
        current = {(path, rule, digest) for path, rule, digest in listed}
        self.assertEqual(sorted(found - current), [], "a line quotes a pattern and is not pinned")
        for quoted in hyg.QUOTED_LINES:
            self.assertTrue(quoted.what.strip() and quoted.digests, quoted)
            for digest in quoted.digests:
                self.assertRegex(digest, r"^[0-9a-f]{64}$")

    def test_every_pin_of_a_quoted_line_is_a_line_of_the_current_file_or_of_an_earlier_version(self):
        """The table may keep pins for lines of earlier versions of a file, because the history scan judges those too, and nothing else."""
        if not (support.REPO / ".git").exists():
            self.skipTest("not a git checkout")
        if hyg._git(support.REPO, "rev-parse", "--is-shallow-repository").strip() == b"true":
            self.skipTest("a shallow clone does not hold the earlier versions")
        versions = hyg.history_versions(support.REPO, hyg.history_commits(support.REPO))
        blobs = hyg.read_blobs(support.REPO, sorted({blob for (blob, path) in versions if path in self.SELF}))
        lines = {path: set() for path in self.SELF}
        for (blob, path) in versions:
            if path in self.SELF and blob in blobs:
                lines[path].update(hyg.line_digest(line) for line in blobs[blob].decode("utf-8").split("\n"))
        for rel in self.SELF:
            lines[rel].update(hyg.line_digest(line) for line in self.own_bytes(rel).decode("utf-8").split("\n"))
        for quoted in hyg.QUOTED_LINES:
            for digest in quoted.digests:
                self.assertIn(digest, lines[quoted.path], "%s %s pins a line that no version of the file has" % (quoted.path, quoted.rule))

    def test_an_exception_belongs_to_its_path_its_rule_and_its_exact_line(self):
        sample = "Contact someone@" + "contoso.com"
        pinned = (hyg.QuotedLines("tests/test_hygiene.py", "HYG104", (hyg.line_digest(sample),), "a sample"),)
        hyg.use_private_terms([])
        with mock.patch.object(hyg, "QUOTED_LINES", pinned):
            self.assertEqual([f.code for f in hyg.scan_bytes("tests/test_hygiene.py", (sample + "\n").encode())], [])
            for elsewhere in ("tests/test_other.py", "docs/page.md", "scripts/check_hygiene.py", "x/tests/test_hygiene.py"):
                self.assertEqual([f.code for f in hyg.scan_bytes(elsewhere, (sample + "\n").encode())], ["HYG104"], elsewhere)
            for altered in (sample + " ", sample + " and " + STRANGER, "# " + sample, sample.replace("someone", "another")):
                self.assertEqual([f.code for f in hyg.scan_bytes("tests/test_hygiene.py", (altered + "\n").encode())], ["HYG104"], repr(altered))

    def test_a_pin_excuses_one_rule_of_a_line_that_two_rules_match_and_the_other_still_finds_it(self):
        """One unchanged line, matched by two rules and pinned for one of them: the pin does not reach the other rule."""
        line = "Contact someone@" + "contoso.com, marked Internal " + "Use Only"
        digest = hyg.line_digest(line)
        hyg.use_private_terms([])
        both_match = {rule.code for rule in hyg.RULES if next(hyg.find_matches(rule, "tests/test_hygiene.py", line), None) is not None}
        self.assertEqual(both_match, {"HYG104", "HYG105"}, "the sample line is one that two rules match")

        def found(pinned_rules):
            pins = tuple(hyg.QuotedLines("tests/test_hygiene.py", rule, (digest,), "a sample") for rule in pinned_rules)
            with mock.patch.object(hyg, "QUOTED_LINES", pins):
                return {f.code for f in hyg.scan_bytes("tests/test_hygiene.py", (line + "\n").encode())}

        self.assertEqual(found(()), {"HYG104", "HYG105"})
        self.assertEqual(found(("HYG104",)), {"HYG105"})
        self.assertEqual(found(("HYG105",)), {"HYG104"})
        self.assertEqual(found(("HYG104", "HYG105")), set())

    def test_the_pinned_lines_are_exactly_the_lines_that_name_the_authority(self):
        """With no pin, the scan must flag the pinned lines and nothing else; so no pin is stale, and no other line names the authority."""
        pins = hyg.PUBLIC_SOURCE_LINES
        self.assertTrue(pins)
        with mock.patch.object(hyg, "PUBLIC_SOURCE_LINES", ()):
            findings, _notices, _count = hyg.scan(support.REPO, private_terms=[])
        self.assertEqual({(f.code, f.path) for f in findings}, {("HYG105", pin.path) for pin in pins})
        flagged = []
        for finding in findings:
            text = (support.REPO / finding.path).read_text(encoding="utf-8").split("\n")
            flagged.append(hyg.line_digest(text[finding.line - 1]))
        self.assertEqual(sorted(flagged), sorted(pin.digest for pin in pins))

    def test_every_pin_is_one_line_of_one_file_and_says_what_it_is(self):
        for pin in hyg.PUBLIC_SOURCE_LINES:
            self.assertRegex(pin.digest, r"^[0-9a-f]{64}$")
            self.assertTrue(pin.what.strip(), pin.path)
            lines = (support.REPO / pin.path).read_text(encoding="utf-8").split("\n")
            matching = [line for line in lines if hyg.line_digest(line) == pin.digest]
            self.assertEqual(len(matching), 1, "%s: a pinned line must occur exactly once" % pin.path)
            self.assertRegex(matching[0], r"^- \*\*(Source|URL):\*\* ", "a pin is a public record's own title (the Source line) or address (the URL line)")

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
        for text in ("12345+someone@users.noreply.github.com", "name@example.com", "git@github.com:owner/repo.git", "GitHub <noreply@github.com>"):
            self.assertEqual(codes_for_text(text), [], text)

    def test_internal_vocabulary_is_found_in_text_and_in_names(self):
        self.assertEqual(codes_for_text("This came from Zebracorp's notes.", terms=SYNTHETIC_TERMS), ["HYG105"])
        self.assertEqual(codes_for_text("The Project Aurora kickoff.", terms=SYNTHETIC_TERMS), ["HYG105"])
        self.assertEqual(codes_for({"docs/Zebracorp_notes.md": "plain text"}, SYNTHETIC_TERMS), ["HYG105"])
        self.assertEqual(codes_for_text("This came from Zebracorp's notes."), [], "with no list, nothing is private")

    def test_confidentiality_labels_are_found_without_any_list(self):
        for text in ("Internal Use Only", "marked Highly Confidential", "MSIP_Label_abc_Enabled=true"):
            self.assertEqual(codes_for_text(text), ["HYG105"], text)

    def test_hidden_characters(self):
        for text in ("a\u202eb", "\ufeffhello", "zero\u200bwidth"):
            self.assertEqual(codes_for_text(text), ["HYG106"], repr(text))

    def test_draft_markers(self):
        for text in ("TODO: write this", "to be decided: TBD", "Lorem ipsum dolor", "[insert name here]"):
            self.assertEqual(codes_for_text(text), ["HYG107"], text)

    def test_claims_of_finality_but_not_their_denial(self):
        for text in ("This is the final version.", "The canonical paper is here.", "officially published today"):
            self.assertEqual(codes_for_text(text), ["HYG108"], text)
        for text in ("This is a first release, not a final version.", "Nothing here is the canonical release."):
            self.assertEqual(codes_for_text(text), [], text)

    def test_neither_not_only_nor_a_word_about_time_denies_a_claim(self):
        """"not only the ... version" adds to a claim, and "before" and "until" say when, not that the claim is false."""
        for text in ("This is not only the %s version." % FINAL, "It is not just the %s release." % FINAL, "It is not the only %s edition." % OFFICIAL,
                     "Wait until the %s publication." % OFFICIAL, "It comes before the %s release." % FINAL, "Until then, this is the %s edition." % OFFICIAL):
            self.assertEqual(codes_for_text(text), ["HYG108"], text)

    def test_a_denial_excuses_only_the_claim_it_negates(self):
        """A denial near one claim of finality must not excuse another claim on the same line."""
        excused = ("This is not the %s version." % FINAL, "It is never the %s release." % FINAL, "Nothing here is the %s edition." % OFFICIAL, "This isn't the %s publication." % OFFICIAL,
                   "This is not really the %s version." % FINAL, "It is not yet the %s release." % FINAL, "That is no longer the %s edition." % OFFICIAL)
        for text in excused:
            self.assertEqual(codes_for_text(text), [], text)
        found = (
            "This is not the %s version. This is the %s publication." % (FINAL, OFFICIAL),
            "This is not a draft, and it is the %s version." % FINAL,
            "No change was made; this is the %s release." % FINAL,
            "It is not %s: the %s paper is elsewhere, and this is the %s edition." % ("ready", FINAL, OFFICIAL),
            "The %s release is here, and the other is not the %s version." % (OFFICIAL, FINAL),
            "Do not forget that this is the %s release." % FINAL,
            "No one doubts that this is the %s version." % FINAL,
            "Not long ago this was the %s edition." % OFFICIAL,
            "Nothing to see here, but it is the %s publication." % OFFICIAL,
        )
        for text in found:
            self.assertEqual(codes_for_text(text), ["HYG108"], text)
        shown = [f.excerpt for f in hyg.scan_bytes("docs/page.md", (found[0] + "\n").encode())]
        self.assertEqual(shown, ["%s publication" % OFFICIAL], "only the claim that nothing negates is reported")

    def test_the_tail_of_a_longer_word_is_not_a_denial(self):
        """The text before a claim is cut at 160 characters. A cut that splits a word ("knot" cut to "not") must not turn it into a denial."""
        claim = "%s version" % OFFICIAL
        lead = "not" + " " * 153 + "the "
        self.assertEqual(len(lead), 160)
        self.assertEqual(codes_for_text(" " + lead + claim), [], "a denial just inside the text that is read excuses the claim")
        for word_start in ("k", "bla", "x_"):
            with self.subTest(word_start):
                self.assertEqual(codes_for_text(word_start + lead + claim), ["HYG108"], "the tail of %snot is not a denial" % word_start)

    def test_a_private_pattern_that_means_something_else_on_a_line_than_on_a_whole_file_is_applied_to_every_line(self):
        """\\A and \\Z mean the start and the end of the text, and a look-around can see a line ending. A pattern written for lines was tried on the whole text first,
        and a file that did not match as a whole was skipped, whichever line would have matched."""
        text = b"A first line.\nZebracorp\nA last line.\n"
        for term in (r"\AZebracorp", r"\AZebracorp\Z", r"(?<![^\n])Zebracorp(?![^\n])", r"(?<!\S)Zebracorp$"):
            with self.subTest(term):
                self.assertEqual(codes_for({"docs/page.md": text}, terms=[term]), ["HYG105"])
                self.assertEqual(codes_for({"docs/page.md": text.replace(b"\n", b"\r\n")}, terms=[term]), ["HYG105"], "with Windows line endings")
        for term in (r"\AZebracorp\Z", r"(?<![^\n])Zebracorp(?![^\n])"):
            with self.subTest("no match for " + term):
                self.assertEqual(codes_for({"docs/page.md": b"A first line.\nx Zebracorp y\n"}, terms=[term]), [], "the pattern still means the whole line")

    def test_a_private_pattern_that_switches_a_flag_off_in_a_group_is_applied_to_every_line(self):
        """(?-m:...) turns ^ and $ into the start and the end of the whole string, which is not what a line is. The pattern is tried line by line."""
        text = b"First\r\nZebracorp\r\nLast\r\n"
        for term in (r"(?-m:^Zebracorp$)", r"(?i-m:^zebracorp$)", r"(?-m:\AZebracorp\Z)"):
            with self.subTest(term):
                self.assertEqual(codes_for({"docs/page.md": text}, terms=[term]), ["HYG105"])
                self.assertEqual(codes_for({"docs/page.md": text.replace(b"\r\n", b"\n")}, terms=[term]), ["HYG105"])
                self.assertEqual(hyg.use_private_terms([term]), [])
                self.assertEqual([(f.line, f.excerpt) for f in hyg.scan_bytes("docs/page.md", text)], [(2, "Zebracorp")])
        hyg.use_private_terms([])

    def test_a_private_pattern_with_no_line_meaning_is_still_tried_on_the_whole_text_once(self):
        with mock.patch.object(hyg, "_PER_LINE", set()):
            self.assertEqual(hyg.use_private_terms([r"Zebracorp", r"\AQuartz"]), [])
            self.assertEqual(len(hyg._PER_LINE), 1, "only the pattern with \\A is tried line by line")
        hyg.use_private_terms([])

    def test_the_text_before_a_match_starts_at_a_whole_word(self):
        self.assertEqual(hyg._before("knot the x", 9, 8), " the ")      # a cut inside "knot" would leave "not the "
        self.assertEqual(hyg._before("a not the x", 10, 8), "not the ")
        self.assertEqual(hyg._before("short", 5), "short")
        self.assertEqual(hyg._before("a" * 400, 400, 160), "", "a run of word characters with no break leaves nothing to read")

    def test_a_private_pattern_anchored_to_the_line_matches_in_a_file_with_windows_line_endings(self):
        self.assertEqual(codes_for({"docs/page.md": b"Zebracorp\r\nsecond line\r\n"}, terms=[r"^Zebracorp$"]), ["HYG105"])
        self.assertEqual(codes_for({"docs/page.md": b"A line.\r\nZebracorp\r\n"}, terms=[r"^Zebracorp$", r"line\.$"]), ["HYG105"])
        self.assertEqual(codes_for({"docs/page.md": b"x Zebracorp\r\n"}, terms=[r"^Zebracorp$"]), [], "an anchored pattern still means the whole line")
        self.assertEqual(codes_for({"docs/page.md": b"Zebracorp\n"}, terms=[r"^Zebracorp$"]), ["HYG105"])


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

    def test_a_list_at_any_path_is_a_finding_and_is_never_read(self):
        """The list names the private origin of the material, so it may not be published from a subfolder either, and no finding may print it."""
        for rel in ("docs/" + hyg.PRIVATE_TERMS_FILE, "a/b/c/" + hyg.PRIVATE_TERMS_FILE, "docs/" + hyg.PRIVATE_TERMS_FILE.upper(), "docs/.Hygiene-Private-Terms"):
            with self.subTest(rel):
                with tempfile.TemporaryDirectory() as tmp:
                    target = Path(tmp) / rel
                    target.parent.mkdir(parents=True)
                    target.write_text("Zebracorp\n%s\nsomeone@" % PRIVATE_TERM + "contoso.com\n", encoding="utf-8")
                    opened, scanned = [], []
                    original = Path.read_bytes
                    with mock.patch.object(Path, "read_bytes", lambda self: opened.append(self.name) or original(self)), \
                            mock.patch.object(hyg, "scan_bytes", wraps=hyg.scan_bytes) as scan_bytes:
                        findings, _, _ = hyg.scan(Path(tmp), private_terms=["Zebracorp", PRIVATE_TERM])
                    scanned = [call.args[0] for call in scan_bytes.call_args_list]
                self.assertEqual([(f.code, f.path) for f in findings], [("HYG207", rel)])
                self.assertEqual([f.excerpt for f in findings], [""], "nothing from the list is printed")
                self.assertNotIn(target.name, opened, "the list is not opened")
                self.assertNotIn(rel, scanned, "the list is not scanned")

    def test_a_list_the_environment_names_inside_the_folder_is_a_finding_under_any_name_and_is_never_read(self):
        """A path in the environment variable may point at a file of the folder: it would be published, and the scan would print each term against itself."""
        self.addCleanup(hyg._LIST_PATHS.clear)
        for rel in ("notes/terms.txt", "TERMS.TXT", "a/b/words.md"):
            with self.subTest(rel):
                with tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp)
                    target = root / rel
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_text("# my terms\nZebracorp\n%s\n" % PRIVATE_TERM, encoding="utf-8")
                    (root / "page.md").write_text("Notes from Zebracorp.\n", encoding="utf-8")
                    opened = []
                    original = Path.read_bytes
                    with mock.patch.dict(os.environ, {hyg.PRIVATE_TERMS_ENV: str(target)}), mock.patch.object(Path, "read_bytes", lambda self: opened.append(self.name) or original(self)):
                        findings, _, _ = hyg.scan(root)
                        findings_listed, _, _ = hyg.scan(root, files=[rel, "page.md"])
                self.assertEqual(sorted((f.code, f.path) for f in findings), [("HYG105", "page.md"), ("HYG207", rel)], "the terms are used, and the list is a finding")
                self.assertEqual(sorted((f.code, f.path) for f in findings_listed), [("HYG105", "page.md"), ("HYG207", rel)])
                self.assertNotIn(target.name, opened, "the list is not read as a file of the folder")
                self.assertEqual([f.excerpt for f in findings if f.code == "HYG207"], [""], "nothing from the list is printed")
                self.assertNotIn(PRIVATE_TERM, "\n".join(f.format() for f in findings))

    def test_a_list_the_environment_names_outside_the_folder_is_not_a_file_of_it(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as elsewhere:
            listing = Path(elsewhere) / "terms.txt"
            listing.write_text("Zebracorp\n", encoding="utf-8")
            (Path(tmp) / "page.md").write_text("Notes from Zebracorp.\n", encoding="utf-8")
            with mock.patch.dict(os.environ, {hyg.PRIVATE_TERMS_ENV: str(listing)}):
                self.assertEqual(hyg.private_list_paths(Path(tmp)), [])
                findings, _, _ = hyg.scan(Path(tmp))
        self.assertEqual([(f.code, f.path) for f in findings], [("HYG105", "page.md")])

    def test_a_list_that_is_not_utf8_is_read_with_replacement_and_never_stops_the_scan(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / hyg.PRIVATE_TERMS_FILE).write_bytes(b"Zebracorp\n\xff\xfe broken\nQuartz\n")
            terms = hyg.load_private_terms(root, environ={})
            self.assertEqual(terms[0], "Zebracorp")
            self.assertEqual(terms[-1], "Quartz")
            self.assertEqual(len(terms), 3)
            listing = root / "elsewhere.txt"
            listing.write_bytes(b"Borealis\n\x80\x81\n")
            self.assertEqual(hyg.load_private_terms(root / "empty", environ={hyg.PRIVATE_TERMS_ENV: str(listing)})[0], "Borealis")

    def test_the_pin_helpers_never_print_a_line_of_a_list(self):
        self.addCleanup(hyg._LIST_PATHS.clear)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for rel in (hyg.PRIVATE_TERMS_FILE, "docs/" + hyg.PRIVATE_TERMS_FILE, "docs/.Hygiene-Private-Terms", "notes/terms.txt"):
                target = root / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text("%s\n" % PRIVATE_TERM, encoding="utf-8")
                with self.subTest(rel), mock.patch.dict(os.environ, {hyg.PRIVATE_TERMS_ENV: str(root / "notes/terms.txt")}):
                    with self.assertRaises(ValueError) as refused:
                        hyg.pin_entry(root, rel + ":1")
                    self.assertIn("private term list", str(refused.exception))
                    self.assertNotIn(PRIVATE_TERM, str(refused.exception))
                    with self.assertRaises(ValueError):
                        hyg.pin_quoted(root, rel + ":1")
            (root / "page.md").write_text("A line\n", encoding="utf-8")
            self.assertEqual(hyg.pin_entry(root, "page.md:1")[0], "A line")

    def test_a_list_at_a_nested_path_is_found_in_the_history_too(self):
        try:
            subprocess.run(["git", "--version"], capture_output=True, check=True)
        except (OSError, subprocess.CalledProcessError):
            self.skipTest("git is not available")
        nested = "docs/" + hyg.PRIVATE_TERMS_FILE
        root = History.repository(self, [("add a note", {nested: "Zebracorp\n"}, NOREPLY), ("remove it", {nested: None, "docs/page.md": "A clean page\n"}, NOREPLY)])
        head, _, _ = hyg.scan(root, private_terms=[])
        history, _, _ = hyg.scan_history(root, private_terms=[])
        self.assertEqual(head, [])
        self.assertEqual([(f.code, f.path.split(" @ ")[0]) for f in history], [("HYG207", nested)])

    def test_a_list_in_the_history_is_found_by_its_name_and_its_content_is_never_read(self):
        try:
            subprocess.run(["git", "--version"], capture_output=True, check=True)
        except (OSError, subprocess.CalledProcessError):
            self.skipTest("git is not available")
        nested = "docs/" + hyg.PRIVATE_TERMS_FILE
        root = History.repository(self, [("add a note", {nested: "ListOnly" + "Content\n"}, NOREPLY), ("remove it", {nested: None, "docs/page.md": "A clean page\n"}, NOREPLY)])
        blob = git_out(root, "rev-parse", "HEAD~1:" + nested)
        with mock.patch.object(hyg, "read_blobs", wraps=hyg.read_blobs) as reader:
            history, _, _ = hyg.scan_history(root, private_terms=["ListOnly"])
        asked = {name for call in reader.call_args_list for name in call.args[1]}
        self.assertNotIn(blob, asked, "the blob of the list is not read")
        self.assertEqual([(f.code, f.path.split(" @ ")[0], f.excerpt) for f in history], [("HYG207", nested, "")])

    def test_a_list_the_environment_names_is_found_in_the_history_under_its_own_name(self):
        try:
            subprocess.run(["git", "--version"], capture_output=True, check=True)
        except (OSError, subprocess.CalledProcessError):
            self.skipTest("git is not available")
        self.addCleanup(hyg._LIST_PATHS.clear)
        root = History.repository(self, [("add terms", {"notes/terms.txt": "ListOnly" + "Content\n"}, NOREPLY), ("add a page", {"docs/page.md": "A clean page\n"}, NOREPLY)])
        blob = git_out(root, "rev-parse", "HEAD:notes/terms.txt")
        with mock.patch.dict(os.environ, {hyg.PRIVATE_TERMS_ENV: str(root / "notes" / "terms.txt")}), mock.patch.object(hyg, "read_blobs", wraps=hyg.read_blobs) as reader:
            history, _, _ = hyg.scan_history(root)
        asked = {name for call in reader.call_args_list for name in call.args[1]}
        self.assertNotIn(blob, asked)
        self.assertEqual([(f.code, f.path.split(" @ ")[0], f.excerpt) for f in history], [("HYG207", "notes/terms.txt", "")])

    def test_a_list_the_environment_names_that_was_deleted_from_the_folder_is_still_found_in_the_history(self):
        """The list is in the history under that path whether or not the file is still in the folder, so it is recognised by the path and not by being there."""
        try:
            subprocess.run(["git", "--version"], capture_output=True, check=True)
        except (OSError, subprocess.CalledProcessError):
            self.skipTest("git is not available")
        self.addCleanup(hyg._LIST_PATHS.clear)
        root = History.repository(self, [("add terms", {"notes/terms.txt": "ListOnly" + "Content\n"}, NOREPLY), ("add a page", {"docs/page.md": "A clean page\n"}, NOREPLY)])
        blob = git_out(root, "rev-parse", "HEAD:notes/terms.txt")
        configured = str(root / "notes" / "terms.txt")
        (root / "notes" / "terms.txt").unlink()
        self.assertEqual(hyg.private_list_paths(root, {hyg.PRIVATE_TERMS_ENV: configured}), ["notes/terms.txt"])
        with mock.patch.dict(os.environ, {hyg.PRIVATE_TERMS_ENV: configured}), mock.patch.object(hyg, "read_blobs", wraps=hyg.read_blobs) as reader:
            history, _, _ = hyg.scan_history(root)
        asked = {name for call in reader.call_args_list for name in call.args[1]}
        self.assertNotIn(blob, asked, "the blob of a list that is no longer in the folder is not read either")
        self.assertEqual([(f.code, f.path.split(" @ ")[0], f.excerpt) for f in history], [("HYG207", "notes/terms.txt", "")])

    @staticmethod
    def link_to_directory(target, link):
        """A symbolic link (or, on Windows without the right to make one, a junction) to a directory; False when neither can be made."""
        try:
            os.symlink(target, link, target_is_directory=True)
            return True
        except (OSError, NotImplementedError):
            pass
        if os.name == "nt":
            done = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(target)], capture_output=True)
            return done.returncode == 0
        return False

    def test_a_list_is_found_when_the_folder_or_the_path_goes_through_a_link(self):
        """The path of the list is read as it is written and after links are resolved: a folder that is a link to elsewhere, or a path through a link, does not hide it."""
        with tempfile.TemporaryDirectory() as tmp:
            real, away = Path(tmp) / "real", Path(tmp) / "away"
            (real / "notes").mkdir(parents=True)
            away.mkdir()
            (real / "notes" / "terms.txt").write_text("Zebracorp\n", encoding="utf-8")
            if not (self.link_to_directory(real, Path(tmp) / "folder-link") and self.link_to_directory(real / "notes", away / "notes-link")):
                self.skipTest("this system cannot make a link to a directory")
            inside = {hyg.PRIVATE_TERMS_ENV: str(real / "notes" / "terms.txt")}
            self.assertEqual(hyg.private_list_paths(Path(tmp) / "folder-link", inside), ["notes/terms.txt"], "the folder is the link, and the list is named by its real path")
            through = {hyg.PRIVATE_TERMS_ENV: str(away / "notes-link" / "terms.txt")}
            self.assertEqual(hyg.private_list_paths(real, through), ["notes/terms.txt"], "the list is named through a link that leads into the folder")
            self.assertEqual(hyg.private_list_paths(Path(tmp) / "away", {hyg.PRIVATE_TERMS_ENV: str(real / "notes" / "terms.txt")}), [], "outside the folder is outside")

    def test_a_file_of_the_folder_that_is_the_list_itself_is_found_under_its_own_name(self):
        """A hard link or a copy by link is the same file as the list: it would be published and scanned against itself."""
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as elsewhere:
            listing = Path(elsewhere) / "terms.txt"
            listing.write_text("Zebracorp\n", encoding="utf-8")
            (Path(tmp) / "docs").mkdir()
            try:
                os.link(listing, Path(tmp) / "docs" / "copy.txt")
            except (OSError, NotImplementedError):
                self.skipTest("this system cannot make a hard link")
            (Path(tmp) / "docs" / "page.md").write_text("A page.\n", encoding="utf-8")
            environ = {hyg.PRIVATE_TERMS_ENV: str(listing)}
            self.assertEqual(hyg.private_list_paths(Path(tmp), environ), [])
            self.assertEqual(hyg.private_list_paths(Path(tmp), environ, names=["docs/copy.txt", "docs/page.md"]), ["docs/copy.txt"])
            self.addCleanup(hyg._LIST_PATHS.clear)
            with mock.patch.dict(os.environ, environ):
                findings, _, _ = hyg.scan(Path(tmp))
        self.assertEqual([(f.code, f.path, f.excerpt) for f in findings], [("HYG207", "docs/copy.txt", "")])

    def test_a_name_that_merely_begins_with_two_points_is_inside_the_folder(self):
        """Only a path that leaves the folder starts with the step '..'. A folder called '..notes' is inside it, and a list in it is a list in the folder."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"
            (root / "..notes").mkdir(parents=True)
            listing = root / "..notes" / "terms.txt"
            listing.write_text("Zebracorp\n", encoding="utf-8")
            environ = {hyg.PRIVATE_TERMS_ENV: str(listing)}
            self.assertEqual(hyg.private_list_paths(root, environ), ["..notes/terms.txt"])
            self.assertEqual(hyg.private_list_paths(root, {hyg.PRIVATE_TERMS_ENV: str(Path(tmp) / "terms.txt")}), [], "outside the folder is outside")
            self.assertEqual(hyg.private_list_paths(root, {hyg.PRIVATE_TERMS_ENV: str(root / ".." / "terms.txt")}), [], "a step '..' leaves the folder")

    def test_a_list_in_a_folder_that_begins_with_two_points_is_found_in_the_history_without_being_read(self):
        try:
            subprocess.run(["git", "--version"], capture_output=True, check=True)
        except (OSError, subprocess.CalledProcessError):
            self.skipTest("git is not available")
        self.addCleanup(hyg._LIST_PATHS.clear)
        root = History.repository(self, [("add terms", {"..notes/terms.txt": "ListOnly" + "Content\n"}, NOREPLY), ("add a page", {"docs/page.md": "A clean page\n"}, NOREPLY)])
        blob = git_out(root, "rev-parse", "HEAD:..notes/terms.txt")
        for present in (True, False):
            if not present:
                (root / "..notes" / "terms.txt").unlink()
            with self.subTest("the file is in the folder" if present else "the file was deleted from the folder"):
                with mock.patch.dict(os.environ, {hyg.PRIVATE_TERMS_ENV: str(root / "..notes" / "terms.txt")}), mock.patch.object(hyg, "read_blobs", wraps=hyg.read_blobs) as reader:
                    history, _, _ = hyg.scan_history(root)
                asked = {name for call in reader.call_args_list for name in call.args[1]}
                self.assertNotIn(blob, asked)
                self.assertEqual([(f.code, f.path.split(" @ ")[0], f.excerpt) for f in history], [("HYG207", "..notes/terms.txt", "")])

    def test_a_version_in_the_history_with_the_content_of_the_list_is_the_list_whatever_its_path(self):
        """A hard link that was committed is a file with the list's content. In the history only the content is there, so the version is found by it and is never read."""
        try:
            subprocess.run(["git", "--version"], capture_output=True, check=True)
        except (OSError, subprocess.CalledProcessError):
            self.skipTest("git is not available")
        self.addCleanup(hyg._LIST_PATHS.clear)
        content = "ListOnly" + "Content\nAnother" + "Term\n"
        root = History.repository(self, [("add a copy", {"docs/copy.txt": content}, NOREPLY), ("add a page", {"docs/page.md": "A clean page\n"}, NOREPLY)])
        blob = git_out(root, "rev-parse", "HEAD:docs/copy.txt")
        with tempfile.TemporaryDirectory() as elsewhere:
            listing = Path(elsewhere) / "terms.txt"
            listing.write_bytes(content.encode("utf-8"))
            for label, written in (("the same bytes", content.encode("utf-8")), ("with Windows line endings, which a repository that normalizes them stores as LF", content.replace("\n", "\r\n").encode("utf-8"))):
                with self.subTest(label):
                    listing.write_bytes(written)
                    with mock.patch.dict(os.environ, {hyg.PRIVATE_TERMS_ENV: str(listing)}), mock.patch.object(hyg, "read_blobs", wraps=hyg.read_blobs) as reader:
                        history, _, _ = hyg.scan_history(root)
                    asked = {name for call in reader.call_args_list for name in call.args[1]}
                    self.assertNotIn(blob, asked, "the version is not read")
                    self.assertEqual([(f.code, f.path.split(" @ ")[0], f.excerpt) for f in history], [("HYG207", "docs/copy.txt", "")])
                    self.assertNotIn("ListOnly", "\n".join(f.format() for f in history))

    def test_a_list_with_no_term_in_it_is_not_a_copy_of_every_empty_file(self):
        try:
            subprocess.run(["git", "--version"], capture_output=True, check=True)
        except (OSError, subprocess.CalledProcessError):
            self.skipTest("git is not available")
        self.addCleanup(hyg._LIST_PATHS.clear)
        root = History.repository(self, [("add empty files", {"docs/empty.txt": "", "docs/blank.txt": "\n\n"}, NOREPLY)])
        with tempfile.TemporaryDirectory() as elsewhere:
            for content in (b"", b"\n  \n"):
                listing = Path(elsewhere) / "terms.txt"
                listing.write_bytes(content)
                with self.subTest(repr(content)), mock.patch.dict(os.environ, {hyg.PRIVATE_TERMS_ENV: str(listing)}):
                    self.assertEqual(hyg.private_list_blobs(root), set())
                    history, _, _ = hyg.scan_history(root)
                    self.assertEqual([f for f in history if f.code == "HYG207"], [])

    def test_the_pin_helpers_refuse_a_file_that_is_the_same_file_as_the_list(self):
        """--pin and --pin-quoted print the line they are asked for. A hard link to the list is the list: nothing of it is printed."""
        self.addCleanup(hyg._LIST_PATHS.clear)
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as elsewhere:
            listing = Path(elsewhere) / "terms.txt"
            listing.write_text("%s\n" % PRIVATE_TERM, encoding="utf-8")
            (Path(tmp) / "docs").mkdir()
            try:
                os.link(listing, Path(tmp) / "docs" / "copy.txt")
            except (OSError, NotImplementedError):
                self.skipTest("this system cannot make a hard link")
            with mock.patch.dict(os.environ, {hyg.PRIVATE_TERMS_ENV: str(listing)}):
                for helper in (hyg.pin_entry, hyg.pin_quoted):
                    with self.subTest(helper.__name__):
                        with self.assertRaises(ValueError) as refused:
                            helper(Path(tmp), "docs/copy.txt:1")
                        self.assertIn("private term list", str(refused.exception))
                        self.assertNotIn(PRIVATE_TERM, str(refused.exception))

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


RECORDS = "references/public-records.md"
TITLE = "- **Source:** A National Audit Office, *Zebracorp: follow-up audit*, report to Parliament, May 2023."
ADDRESS = "- **URL:** <https://www.stjornarradid.is/gogn/urskurdir/Akvordun-Zebracorp/>"
INVENTED_NAME = (r"(?i)zebracorp\w*",)


def pins(*lines, path=RECORDS):
    return tuple(hyg.PublicSourceLine(path, hyg.line_digest(line), "a line of a test") for line in lines)


class PublicSourceBoundary(unittest.TestCase):
    """The authority's name may appear only on a line that quotes a public record's own title or address, pinned exactly.

    The tests use an invented name, because the scanner meets the real one only as a digest and no test file may repeat it.
    """

    def where(self, files, pinned=(), terms=INVENTED_NAME):
        """The (code, path, line) of every HYG105 finding in a throwaway folder, with these lines pinned."""
        with mock.patch.object(hyg, "PUBLIC_SOURCE_LINES", pinned), tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name, content in files.items():
                target = root / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content, encoding="utf-8")
            findings, _notices, _count = hyg.scan(root, private_terms=list(terms))
        return sorted((f.code, f.path, f.line) for f in findings if f.code == "HYG105")

    def test_the_name_is_accepted_in_a_pinned_public_record_title(self):
        self.assertEqual(self.where({RECORDS: TITLE + "\n"}, pins(TITLE)), [])
        self.assertEqual(self.where({RECORDS: TITLE + "\n"}), [("HYG105", RECORDS, 1)], "without the pin the same line is a finding")

    def test_the_name_is_accepted_in_a_pinned_public_url(self):
        self.assertEqual(self.where({RECORDS: ADDRESS + "\n"}, pins(ADDRESS)), [])
        self.assertEqual(self.where({RECORDS: ADDRESS + "\n"}), [("HYG105", RECORDS, 1)])

    def test_the_same_name_is_rejected_in_normal_prose(self):
        prose = "The authority, Zebracorp, registers catches and landings."
        text = "\n".join([TITLE, prose, ADDRESS]) + "\n"
        self.assertEqual(self.where({RECORDS: text}, pins(TITLE, ADDRESS)), [("HYG105", RECORDS, 2)], "the prose line beside two pinned lines is a finding")
        for name in ("docs/page.md", "README.md", "references/README.md", "docs/paper/02-engagement.md"):
            self.assertEqual(self.where({name: prose + "\n"}, pins(TITLE, ADDRESS)), [("HYG105", name, 1)], name)

    def test_the_same_name_is_rejected_in_a_heading(self):
        text = "# Public records\n\n" + TITLE + "\n\n## Zebracorp findings\n"
        self.assertEqual(self.where({RECORDS: text}, pins(TITLE)), [("HYG105", RECORDS, 5)])
        self.assertEqual(self.where({"docs/page.md": "# Zebracorp\n"}, pins(TITLE)), [("HYG105", "docs/page.md", 1)])

    def test_the_same_name_is_rejected_in_example_data(self):
        data = '{"customer": "Zebracorp", "note": "synthetic"}\n'
        path = "examples/01-source-records/c02-sample.json"
        self.assertEqual(self.where({path: data}, pins(TITLE, ADDRESS)), [("HYG105", path, 1)])
        page = "examples/01-source-records/README.md"
        self.assertEqual(self.where({page: TITLE + "\n"}, pins(TITLE)), [("HYG105", page, 1)], "a pinned line in an example page is not in the pinned file")

    def test_the_same_name_is_rejected_in_a_file_or_directory_name(self):
        for name in ("docs/Zebracorp_notes.md", "examples/zebracorp/README.md", "figures/ZEBRACORP-chart.svg"):
            self.assertEqual(self.where({name: "plain text\n"}, pins(TITLE)), [("HYG105", name, 0)], name)
        pinned_file = "references/Zebracorp-records.md"
        self.assertEqual(self.where({pinned_file: TITLE + "\n"}, pins(TITLE)), [("HYG105", pinned_file, 0), ("HYG105", pinned_file, 1)],
                         "a pin excuses a line of its own file, never a file name")

    def test_the_same_name_is_rejected_in_generated_figure_metadata(self):
        svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><title id="t">Zebracorp overview</title><desc id="d">A drawing.</desc></svg>\n'
        meta = '{"figures": [{"id": "F01", "alt": "A drawing for Zebracorp.", "description": "Three cards."}]}\n'
        self.assertEqual(self.where({"figures/F01-light.svg": svg}, pins(TITLE)), [("HYG105", "figures/F01-light.svg", 1)])
        self.assertEqual(self.where({"figures/figures.json": meta}, pins(TITLE)), [("HYG105", "figures/figures.json", 1)])

    def test_the_same_name_is_rejected_in_a_commit_message_but_not_in_a_pinned_file(self):
        try:
            subprocess.run(["git", "--version"], capture_output=True, check=True)
        except (OSError, subprocess.CalledProcessError):
            self.skipTest("git is not available")
        root = History.repository(self, [
            ("note from the meeting with Zebracorp\n\nA second paragraph.", {RECORDS: TITLE + "\n" + ADDRESS + "\n"}, NOREPLY),
            ("add a clean page", {"docs/page.md": "A clean page\n"}, NOREPLY)])
        with mock.patch.object(hyg, "PUBLIC_SOURCE_LINES", pins(TITLE, ADDRESS)):
            findings, _notices, counts = hyg.scan_history(root, private_terms=list(INVENTED_NAME))
        self.assertEqual(counts["commits"], 2)
        self.assertEqual([(f.code, f.path.split(" ", 2)[-1], f.line) for f in findings], [("HYG105", "message", 1)])
        with mock.patch.object(hyg, "PUBLIC_SOURCE_LINES", ()):
            unpinned, _notices, _counts = hyg.scan_history(root, private_terms=list(INVENTED_NAME))
        self.assertEqual(sorted(f.path.split(" ", 1)[0] for f in unpinned), ["commit", RECORDS, RECORDS], "without the pins, the two quoted lines are findings in the commit that added them")

    def test_a_pin_is_exact(self):
        pinned = pins(TITLE)
        for altered in (TITLE + " ", "  " + TITLE, TITLE.replace("May 2023", "June 2023"), TITLE.upper(), TITLE + " Zebracorp is mentioned again."):
            self.assertEqual(self.where({RECORDS: altered + "\n"}, pinned), [("HYG105", RECORDS, 1)], repr(altered))
        for other in ("references/README.md", "docs/public-records.md", "references/public-records-copy.md", "x/references/public-records.md"):
            self.assertEqual(self.where({other: TITLE + "\n"}, pinned), [("HYG105", other, 1)], other)
        self.assertEqual(self.where({RECORDS: TITLE + "\r\n"}, pinned), [], "a line ending is not part of the line")

    def test_a_pin_does_not_excuse_label_wording_or_other_rules(self):
        line = "- **Source:** Zebracorp report, Internal Use Only, see someone@contoso.com"
        with mock.patch.object(hyg, "PUBLIC_SOURCE_LINES", pins(line)), tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "references").mkdir()
            (Path(tmp) / RECORDS).write_text(line + "\n", encoding="utf-8")
            codes = sorted({f.code for f in hyg.scan(Path(tmp), private_terms=list(INVENTED_NAME))[0]})
        self.assertEqual(codes, ["HYG104", "HYG105"], "the e-mail address and the confidentiality label are findings even on a pinned line")

    def test_a_pinned_line_passes_in_every_commit_and_prose_is_found_in_the_commit_that_added_it(self):
        try:
            subprocess.run(["git", "--version"], capture_output=True, check=True)
        except (OSError, subprocess.CalledProcessError):
            self.skipTest("git is not available")
        root = History.repository(self, [
            ("add the sources", {RECORDS: "# Public records\n\n" + TITLE + "\n"}, NOREPLY),
            ("add the address", {RECORDS: "# Public records\n\n" + TITLE + "\n" + ADDRESS + "\n"}, NOREPLY),
            ("write about it", {"docs/page.md": "Zebracorp is the authority.\n"}, NOREPLY),
            ("remove the prose", {"docs/page.md": "A clean page\n"}, NOREPLY)])
        with mock.patch.object(hyg, "PUBLIC_SOURCE_LINES", pins(TITLE, ADDRESS)):
            head, _notices, _count = hyg.scan(root, private_terms=list(INVENTED_NAME))
            history, _notices, counts = hyg.scan_history(root, private_terms=list(INVENTED_NAME))
        self.assertEqual(head, [], "the tree is clean")
        self.assertEqual(counts["commits"], 4)
        self.assertEqual([f.path.split(" @ ")[0] for f in history], ["docs/page.md"], "the prose is still in the history")


class NameKnownAsDigest(unittest.TestCase):
    """The real name is in the scanner only as a digest of its first letters. An invented name shows how that works."""

    STEMS = ((9, hyg.name_stem_digest("zebracorp")),)

    def codes(self, files, pinned=()):
        with mock.patch.object(hyg, "NAME_STEMS", self.STEMS), mock.patch.object(hyg, "PUBLIC_SOURCE_LINES", pinned):
            return codes_for(files)

    def test_any_case_inflection_and_compound_is_found_without_a_private_list(self):
        for text in ("Zebracorp", "ZEBRACORP", "zebracorps", "Zebracorpian rules", "see zebra-Zebracorp-x", "Z\u00e9bracorp", "https://x.example/2023-Zebracorp-report.pdf", "Zebracorp2023"):
            self.assertEqual(self.codes({"docs/page.md": text + "\n"}), ["HYG105"], text)

    def test_other_words_are_not_found(self):
        for text in ("A zebra crossing", "corporation", "zebracor", "Zebra corp", "The Zebra Corporation"):
            self.assertEqual(self.codes({"docs/page.md": text + "\n"}), [], text)

    def test_it_is_found_in_a_file_name_and_a_pin_excuses_only_its_exact_line(self):
        self.assertEqual(self.codes({"docs/zebracorp.md": "plain\n"}), ["HYG105"])
        self.assertEqual(self.codes({RECORDS: TITLE + "\n"}, pins(TITLE)), [])
        self.assertEqual(self.codes({RECORDS: TITLE + " ...\n"}, pins(TITLE)), ["HYG105"])

    def test_with_no_stem_nothing_is_known(self):
        with mock.patch.object(hyg, "NAME_STEMS", ()):
            self.assertEqual(hyg.name_words("Zebracorp"), [])
            self.assertEqual(codes_for({"docs/page.md": "Zebracorp\n"}), [])

    def test_the_digest_ignores_case_and_accents_and_the_pin_digest_ignores_the_line_ending(self):
        self.assertEqual(hyg.name_stem_digest("Zebracorp"), hyg.name_stem_digest("ZÉBRACORP"))
        self.assertNotEqual(hyg.name_stem_digest("zebracorp"), hyg.name_stem_digest("zebracorq"))
        self.assertEqual(hyg.line_digest("a line\r\n"), hyg.line_digest("a line"))
        self.assertNotEqual(hyg.line_digest("a line "), hyg.line_digest("a line"))


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
        self.assertIn("exactly these %d lines" % len(hyg.PUBLIC_SOURCE_LINES), done.stdout)
        for pin in hyg.PUBLIC_SOURCE_LINES:
            self.assertIn(pin.digest[:12], done.stdout)
        self.assertIn("Exactly these %d lines, each for one rule in one file, are excused" % sum(len(q.digests) for q in hyg.QUOTED_LINES), done.stdout)
        for quoted in hyg.QUOTED_LINES:
            self.assertIn(quoted.path, done.stdout)
            for digest in quoted.digests:
                self.assertIn(digest[:12], done.stdout)
        self.assertIn("shallow clone is refused", done.stdout)
        self.assertNotIn("are not read: scripts/check_hygiene.py", done.stdout, "no file is exempt as a whole any more")
        self.assertNotIn("waived", done.stdout, "there is no waiver by prefix or by pattern any more, only pinned lines")

    def test_pin_prints_the_entry_for_one_line_and_refuses_what_is_not_a_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "references").mkdir()
            (root / RECORDS).write_text("one\n" + ADDRESS + "\n", encoding="utf-8")
            done = self.run_cli(root, "--pin", RECORDS + ":2")
            self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
            self.assertIn(hyg.line_digest(ADDRESS), done.stdout)
            self.assertIn('PublicSourceLine("%s"' % RECORDS, done.stdout)
            for bad in (RECORDS + ":9", RECORDS, "nowhere.md:1", "../outside.md:1", RECORDS + ":0"):
                self.assertEqual(self.run_cli(root, "--pin", bad).returncode, 2, bad)

    def test_pin_quoted_prints_the_digest_and_the_rules_that_match_the_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "tests").mkdir()
            sample = "# see https://tenant." + "share" + "point.com/x, mail someone@" + "contoso.com"
            (root / "tests" / "test_hygiene.py").write_text("one\n" + sample + "\n", encoding="utf-8")
            done = self.run_cli(root, "--pin-quoted", "tests/test_hygiene.py:2")
            self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
            self.assertIn(hyg.line_digest(sample), done.stdout)
            self.assertIn("HYG101, HYG104", done.stdout)
            for bad in ("tests/test_hygiene.py:9", "tests/test_hygiene.py", "nowhere.py:1", "../outside.py:1"):
                self.assertEqual(self.run_cli(root, "--pin-quoted", bad).returncode, 2, bad)

    def test_output_is_utf8_even_when_the_console_uses_a_legacy_code_page(self):
        """The rules text holds a typographic dash that a legacy Windows code page cannot print."""
        import os
        env = dict(os.environ, PYTHONIOENCODING="cp437", PYTHONUTF8="0")
        done = subprocess.run([sys.executable, str(support.SCRIPTS / "check_hygiene.py"), "--rules"], capture_output=True, env=env)
        self.assertEqual(done.returncode, 0, done.stderr.decode("utf-8", "replace"))
        self.assertIn("HYG201\u2013HYG207", done.stdout.decode("utf-8"))


class Speed(unittest.TestCase):
    def test_a_long_unbroken_run_of_characters_is_not_quadratic_for_the_e_mail_rule(self):
        """A rendered SVG can hold tens of thousands of characters with no separator; the scan must not slow to a crawl on them."""
        import time
        text = "@" + "a1-" * 40000 + "\n"
        start = time.perf_counter()
        codes_for_text(text, name="figures/x.svg")
        self.assertLess(time.perf_counter() - start, 5)

    def test_a_line_with_thousands_of_denied_claims_is_read_in_one_pass_and_the_one_that_is_not_denied_is_found(self):
        """Each claim of finality is judged with the few words before it, not with the whole line before it. The claims are denied, so each of them has to be judged
        before the last one is reached: a line of claims that were not denied would stop at the first."""
        import time
        line = ("not the %s publication. " % OFFICIAL) * 20000 + "the %s version\n" % FINAL
        start = time.perf_counter()
        with mock.patch.object(hyg, "_before", wraps=hyg._before) as before:
            findings = hyg.scan_bytes("docs/page.md", line.encode("utf-8"))
        self.assertEqual([(f.code, f.excerpt) for f in findings], [("HYG108", "%s version" % FINAL)])
        self.assertGreater(before.call_count, 20000, "every denied claim was judged")
        self.assertLess(time.perf_counter() - start, 5)


NOREPLY = ("Test Author", "1+test@users.noreply.github.com")


def git_out(root, *args, who=NOREPLY):
    env = dict(os.environ, GIT_AUTHOR_NAME=who[0], GIT_AUTHOR_EMAIL=who[1], GIT_COMMITTER_NAME=who[0], GIT_COMMITTER_EMAIL=who[1])
    done = subprocess.run(["git", "-C", str(root), "-c", "commit.gpgsign=false"] + list(args), capture_output=True, env=env)
    if done.returncode:
        raise RuntimeError("git %s failed: %s" % (" ".join(args), done.stderr.decode("utf-8", "replace")))
    return done.stdout.decode("utf-8", "replace").strip()


def git(root, *args, who=NOREPLY):
    git_out(root, *args, who=who)


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

    def test_a_replaced_commit_cannot_hide_what_a_push_would_publish(self):
        """`git replace` makes every Git command show a stand-in for a commit. The scan reads the originals, which are what a push publishes."""
        root = self.repository([("add a page", {"docs/page.md": "Zebracorp wrote this\n"}, NOREPLY), ("remove the term", {"docs/page.md": "A clean page\n"}, NOREPLY)])
        first = git_out(root, "rev-list", "--max-parents=0", "HEAD")
        stand_in = git_out(root, "commit-tree", git_out(root, "rev-parse", "HEAD^{tree}"), "-m", "a clean stand-in")
        git(root, "replace", first, stand_in)

        def honouring_replacements():
            return {key: value for key, value in os.environ.items() if key != "GIT_NO_REPLACE_OBJECTS"}

        with mock.patch.object(hyg, "_git_env", honouring_replacements):
            hidden, _, _ = hyg.scan_history(root, private_terms=list(SYNTHETIC_TERMS))
        self.assertEqual(hidden, [], "with replacement objects honoured, the term is hidden: the control for the check below")
        found, _, _ = hyg.scan_history(root, private_terms=list(SYNTHETIC_TERMS))
        self.assertEqual([f.code for f in found], ["HYG105"], "the original commit is read, not its stand-in")

    def test_a_character_inside_a_message_or_a_name_cannot_end_a_record_early(self):
        """Fields are framed by NUL, which no message or name can hold, so a record separator inside a field is only a character."""
        message = "head\x1fmiddle\x1etail mentions Zebracorp"
        odd = ("Some\x1fone", "some" + "one@" + "contoso.com")
        root = self.repository([("a page", {"a.md": "x\n"}, NOREPLY), (message, {"a.md": "y\n"}, odd), ("a third", {"a.md": "z\n"}, NOREPLY)])
        history, _, counts = hyg.scan_history(root, private_terms=list(SYNTHETIC_TERMS))
        self.assertEqual(counts["commits"], 3)
        self.assertEqual(sorted((f.code, f.path.split(" ", 2)[-1]) for f in history), [("HYG104", "author"), ("HYG104", "committer"), ("HYG105", "message")])

    def test_output_that_does_not_divide_into_whole_records_is_refused_not_read_as_far_as_it_goes(self):
        self.assertEqual(hyg._fields(b"a\0b\0c\0d\0", 2, "x"), [["a", "b"], ["c", "d"]])
        self.assertEqual(hyg._fields(b"", 6, "x"), [])
        for broken in (b"a\0b", b"a\0b\0c", b"a\0b\0c\0d"):
            with self.subTest(broken), self.assertRaises(hyg.HistoryError):
                hyg._fields(broken, 2, "the commits")

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

    def test_the_same_content_at_another_path_is_judged_at_that_path(self):
        """What a path excuses belongs to the path: content excused where it was first added is judged again where it is added later."""
        sample = "Contact someone@" + "contoso.com"
        text = sample + "\n"
        pinned = (hyg.QuotedLines("tests/test_hygiene.py", "HYG104", (hyg.line_digest(sample),), "a sample"),)
        root = self.repository([
            ("quote it where it is excused", {"tests/test_hygiene.py": text}, NOREPLY),
            ("copy it elsewhere", {"docs/copy.md": text}, NOREPLY),
            ("remove the copy", {"docs/copy.md": None}, NOREPLY)])
        with mock.patch.object(hyg, "QUOTED_LINES", pinned):
            history, _notices, counts = hyg.scan_history(root, private_terms=[])
        self.assertEqual([(f.code, f.path.split(" @ ")[0]) for f in history], [("HYG104", "docs/copy.md")])
        self.assertEqual((counts["file_versions"], counts["blobs"]), (2, 1), "one blob, held at two paths, is two file versions")

    def test_a_pinned_line_is_excused_only_at_its_own_path_in_the_history(self):
        root = self.repository([
            ("add the record", {RECORDS: TITLE + "\n"}, NOREPLY),
            ("copy it", {"docs/copy.md": TITLE + "\n"}, NOREPLY),
            ("remove the copy", {"docs/copy.md": None}, NOREPLY)])
        with mock.patch.object(hyg, "PUBLIC_SOURCE_LINES", pins(TITLE)):
            history, _notices, _counts = hyg.scan_history(root, private_terms=list(INVENTED_NAME))
        self.assertEqual([(f.code, f.path.split(" @ ")[0]) for f in history], [("HYG105", "docs/copy.md")])

    def test_content_that_one_path_does_not_read_is_read_at_the_other_path(self):
        """A blocked file type is reported by its name and its content is not read. The same content at an ordinary path is read."""
        text = "Contact " + STRANGER + "\n"
        root = self.repository([
            ("add it as a spreadsheet", {"docs/report.xlsx": text}, NOREPLY),
            ("add it as a page", {"docs/page.md": text}, NOREPLY),
            ("remove both", {"docs/report.xlsx": None, "docs/page.md": None}, NOREPLY)])
        history, _notices, _counts = hyg.scan_history(root, private_terms=[])
        self.assertEqual(sorted({(f.code, f.path.split(" @ ")[0]) for f in history}), [("HYG104", "docs/page.md"), ("HYG201", "docs/report.xlsx")])

    def test_each_blob_is_read_once_however_many_paths_held_it(self):
        page = "The same page\n"
        root = self.repository([("add pages", {"a.md": page, "b.md": page, "c/d.md": page}, NOREPLY), ("add another", {"e.md": "A different page\n"}, NOREPLY)])
        with mock.patch.object(hyg, "read_blobs", wraps=hyg.read_blobs) as reader:
            _findings, _notices, counts = hyg.scan_history(root, private_terms=[])
        asked = [blob for call in reader.call_args_list for blob in call.args[1]]
        self.assertEqual(len(asked), len(set(asked)), "no blob is asked for twice")
        self.assertEqual((counts["file_versions"], counts["blobs"], len(asked)), (4, 2, 2))

    def test_a_shallow_clone_is_refused_instead_of_reported_clean(self):
        source = self.repository([("one", {"a.md": "one\n"}, NOREPLY), ("two", {"a.md": "Zebracorp\n"}, NOREPLY), ("three", {"a.md": "three\n"}, NOREPLY)])
        with tempfile.TemporaryDirectory() as tmp:
            shallow = Path(tmp) / "shallow"
            subprocess.run(["git", "clone", "-q", "--depth", "1", source.as_uri(), str(shallow)], check=True, capture_output=True)
            with self.assertRaises(hyg.HistoryError) as refused:
                hyg.scan_history(shallow, private_terms=list(SYNTHETIC_TERMS))
            self.assertIn("shallow", str(refused.exception))
            done = subprocess.run([sys.executable, str(support.SCRIPTS / "check_hygiene.py"), "--root", str(shallow), "--history"], capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(done.returncode, 2, done.stdout + done.stderr)
            self.assertIn("shallow", done.stderr)
            subprocess.run(["git", "-C", str(shallow), "fetch", "-q", "--unshallow"], check=True, capture_output=True)
            whole, _notices, counts = hyg.scan_history(shallow, private_terms=list(SYNTHETIC_TERMS))
            self.assertEqual(counts["commits"], 3)
            self.assertEqual([f.code for f in whole], ["HYG105"], "with the whole history, the term that only an old commit holds is found")

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
