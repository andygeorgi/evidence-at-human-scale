#!/usr/bin/env python3
"""Scan the repository for what must not reach a public repository, and for files that do not survive a clone.

    python scripts/check_hygiene.py            # scan, exit 1 on any finding
    python scripts/check_hygiene.py --history  # also scan every commit: each file version, path, message, author and ref
    python scripts/check_hygiene.py --rules    # list what is looked for, and which lines are pinned
    python scripts/check_hygiene.py --pin PATH:LINE  # print the pin for one line of a file (see below)
    python scripts/check_hygiene.py --json     # machine-readable result

Standard library only; works offline and is platform-neutral. It scans every file Git would include (tracked, or
untracked and not ignored), or every file under the folder when Git is not available, and it also reads file names.
With --history it also reads everything that a push of the whole history would publish: a term that was removed from the
tree is still in an old commit, and a commit message or an author's address is published with it.

A finding is a reason to look, not a verdict. If a flagged line is legitimate, change the wording. The one exception is the
name of the authority that the paper discusses: it may appear only where a public record's own title or address is quoted
exactly. Such a line is pinned in ``PUBLIC_SOURCE_LINES`` below, by the SHA-256 of the whole line, in a reviewed commit.

Private terms. The names that identify the private origin of the material cannot be listed in a public repository, because
the list would publish them. Rule HYG105 therefore reads them from outside the repository: one regular expression per
line in a file named ``.hygiene-private-terms`` in the repository folder (Git ignores that name), or in the environment
variable ``EAHS_PRIVATE_TERMS``, which holds either a path to such a file or the lines themselves. Continuous integration
has no such list, so a maintainer who has one runs the scan locally before a release. Without a list the scan still runs,
says so, and looks for confidentiality-label wording and for the authority's name, which it knows as a digest (below).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

REPO = Path(__file__).resolve().parents[1]
SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__", ".pytest_cache", ".mypy_cache"}
# These two files quote the very patterns they look for.
SELF_FILES = {"scripts/check_hygiene.py", "tests/test_hygiene.py"}
MAX_BYTES = 1024 * 1024
PRIVATE_TERMS_FILE = ".hygiene-private-terms"
PRIVATE_TERMS_ENV = "EAHS_PRIVATE_TERMS"
NO_MATCH = r"(?!)"
# Confidentiality-label wording that survives when text is copied out of a labeled document.
LABEL_MARKERS = r"Internal [Uu]se [Oo]nly|(?:Highly|Strictly) Confidential|MSIP_"

# The authority that the paper discusses may be named in one place only: the title or the address of a public record that the paper
# cites, quoted as the record gives it. The scanner enforces that in two parts, and neither part repeats the name.
#
# 1. It knows the name as a digest. A word matches when its first letters (lower-cased, without accents) have the SHA-256 digest
#    in NAME_STEMS, so inflected and compound forms match too, in any case, in text, in an address and in a file name.
# 2. It excuses a match on a line listed in PUBLIC_SOURCE_LINES, and nowhere else. A line is listed by its file and by the SHA-256 of
#    its exact text, so a line that differs by one character, the same line in another file, and the same word in prose, in a
#    heading, in data, in a file name, in a commit message or in a figure's metadata are all findings.
NAME_STEMS: Tuple[Tuple[int, str], ...] = (
    (9, "db7189bb970a0a0ae5cf9e77fb89a5cfcec4906eb682b9d2cc45232b56332e8d"),  # (number of letters, digest of those letters)
)


@dataclass(frozen=True)
class PublicSourceLine:
    """One line that may name the authority, because it quotes a public record's own title or address."""
    path: str  # the exact file, relative to the repository
    digest: str  # SHA-256 of the exact line, without its line ending
    what: str  # which record, and whether the line is its title or its address; never the name


PUBLIC_SOURCE_LINES: Tuple[PublicSourceLine, ...] = (
    PublicSourceLine("references/public-records.md", "c2a627932d4e6bb4d07e79f381a37ced5b15426d7d5d0f10a41427729c60a510", "EN01 source line: the original title of a follow-up audit report"),
    PublicSourceLine("references/public-records.md", "27a335aeefaee9cea0583074bccf08f7419b03861546a954266c2218cd31986f", "EN01 address of that report"),
    PublicSourceLine("references/public-records.md", "939c99eebb2407597ba4e4a7d129470b7c7300b061021c743fb5a9bbbc8f8a6c", "EN02 address of an appeal ruling"),
    PublicSourceLine("references/public-records.md", "71a903a6bef5c6ed9b1075001cbe92fc8c0cf60e9c5273cd4c48eea38fb12427", "EN03 address of an appeal ruling"),
    PublicSourceLine("references/public-records.md", "61d2c5cd6c39f83a29e76acbf7baf7d10528e724303dc48d02153f385f22aed5", "EN04 address of a data-protection ruling"),
)


@dataclass(frozen=True)
class Rule:
    code: str
    label: str
    pattern: str
    advice: str
    ignore_match: str = ""  # a match that matches this in full is fine
    ignore_line: str = ""  # a line that matches this is fine for this rule
    on_names: bool = False  # also apply to the file path
    needle: str = ""  # a literal that every match contains: text without it cannot match, so it is not searched


RULES: Tuple[Rule, ...] = (
    Rule("HYG101", "private or tenant link",
         r"sharepoint\.com|\.sharepoint\.|onedrive\.live\.com|1drv\.ms|teams\.microsoft\.com|outlook\.office|office365"
         r"|dev\.azure\.com|visualstudio\.com|\.corp\.microsoft\.com|\.internal\b|\baka\.ms/",
         "Replace it with a public source, or remove it.", on_names=True),
    Rule("HYG102", "local file path",
         r"\b[A-Za-z]:[\\/](?:Users|Documents and Settings|Windows|Program Files)[\\/]"
         r"|(?<![\w.~-])/Users/[A-Za-z][\w.-]*/"
         r"|(?<![\w.~-])/home/(?!(?:runner|user|you|your-user|username|name)\b)[a-z][\w.-]*/"
         r"|\\\\[\w.-]+\\[\w$.-]+|file:///|OneDrive - \w+",
         "A path on one machine means nothing to a reader. Use a repository-relative path.", on_names=True),
    Rule("HYG103", "credential or token",
         r"\bgh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{20,}|\bAKIA[0-9A-Z]{16}\b"
         r"|-----BEGIN (?:RSA |EC |OPENSSH |DSA |PGP )?PRIVATE KEY|AccountKey=[A-Za-z0-9+/=]{20,}|[?&]sig=[A-Za-z0-9%+/=]{20,}"
         r"|\beyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}"
         r"|(?i:\b(?:password|passwd|secret|api[_-]?key|token)\b\s*[:=]\s*[\"'][^\"'\s]{8,}[\"'])",
         "Remove it and rotate the credential: it must be treated as exposed."),
    Rule("HYG104", "e-mail address", r"(?<![A-Za-z0-9._%+-])[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+",
         "Use a role link or the repository's issue tracker, not a personal address.",
         ignore_match=r"(?i:[^@]+@(?:users\.noreply\.github\.com|example\.(?:com|org|net))|git@github\.com)", needle="@"),
    Rule("HYG105", "internal vocabulary, confidentiality label or the authority's name",
         LABEL_MARKERS,
         "This names the private origin of the material, carries a confidentiality label, or names the authority outside a quoted public record. Use the public wording.",
         on_names=True),
    Rule("HYG106", "hidden or direction-changing character", "[\u200b-\u200d\u2060\ufeff\u202a-\u202e\u2066-\u2069]",
         "Zero-width, byte-order-mark and bidirectional control characters can hide or reorder text. Remove it."),
    Rule("HYG107", "draft marker", r"\b(?:TODO|FIXME|XXX|TBD)\b|(?i:lorem ipsum)|\[(?:placeholder|insert|your)[^\]]*\]",
         "Resolve it before publication."),
    Rule("HYG108", "claim of finality",
         r"(?i:\b(?:final|canonical|definitive|official)\s+(?:version|release|edition|publication|paper)\b"
         r"|officially\s+(?:published|released|approved)|\bfinal\s+paper\b)",
         "This is a release candidate. Do not call it final, canonical or official.",
         ignore_line=r"(?i:\b(?:not|never|no|nothing|neither|nor|until|before|isn't)\b.{0,60}\b(?:final|canonical|definitive|official)\b)"),
)

BLOCKED_SUFFIXES = {
    ".docx", ".doc", ".docm", ".dotx", ".pptx", ".ppt", ".pptm", ".xlsx", ".xls", ".xlsm", ".pdf", ".msg", ".eml", ".pst", ".ost",
    ".zip", ".7z", ".rar", ".tar", ".gz", ".tgz", ".pfx", ".p12", ".pem", ".key", ".keystore", ".jks", ".kdbx", ".sqlite", ".db",
    ".bak", ".tmp", ".log", ".exe", ".dll", ".so", ".dylib",
}
BLOCKED_NAMES = {".ds_store", "thumbs.db", "desktop.ini", ".env"}
# Files that may break the two rules above. Empty on purpose: add a path here, in a reviewed commit, with a reason.
ALLOWED_FILES: Tuple[str, ...] = ()
WINDOWS_RESERVED = {"con", "prn", "aux", "nul"} | {"com%d" % i for i in range(1, 10)} | {"lpt%d" % i for i in range(1, 10)}
BAD_NAME_CHARS = re.compile(r'[<>:"|?*\x00-\x1f]')
LICENSE_NAMES = {"license", "license.md", "license.txt", "copying", "copying.md"}


@dataclass(frozen=True)
class Finding:
    code: str
    path: str
    line: int
    message: str
    excerpt: str = ""

    def format(self) -> str:
        where = "%s:%d" % (self.path, self.line) if self.line else self.path
        tail = "  [%s]" % self.excerpt if self.excerpt else ""
        return "%s  %s  %s%s" % (where, self.code, self.message, tail)

    def as_dict(self) -> dict:
        return {"code": self.code, "path": self.path, "line": self.line, "message": self.message, "excerpt": self.excerpt}


def _compiled(rule: Rule):
    return re.compile(rule.pattern)


_COMPILED = {rule.code: _compiled(rule) for rule in RULES}
_PRIVATE: List["re.Pattern[str]"] = []  # the patterns from the private term list, which HYG105 also looks for


def _term_lines(text: str) -> List[str]:
    return [line.strip() for line in text.splitlines() if line.strip() and not line.lstrip().startswith("#")]


def load_private_terms(root: Path = REPO, environ: Optional[Mapping[str, str]] = None) -> List[str]:
    """The private-term patterns: those in the environment variable first, then those in the file in the folder."""
    environ = os.environ if environ is None else environ
    terms: List[str] = []
    value = environ.get(PRIVATE_TERMS_ENV, "").strip()
    if value:
        try:
            from_file = "\n" not in value and Path(value).is_file()
        except OSError:
            from_file = False
        terms += _term_lines(Path(value).read_text(encoding="utf-8") if from_file else value)
    local = root / PRIVATE_TERMS_FILE
    if local.is_file():
        terms += _term_lines(local.read_text(encoding="utf-8"))
    return terms


def use_private_terms(terms: Sequence[str]) -> List[int]:
    """Make HYG105 look for these patterns as well. Returns the 1-based numbers of those that are not regular expressions."""
    _PRIVATE.clear()
    invalid = []
    for number, term in enumerate(terms, 1):
        try:
            _PRIVATE.append(re.compile(term))
        except re.error:
            invalid.append(number)
    return invalid


def _fold(word: str) -> str:
    """A word in lower case and without accents, so that 'Name', 'NAME' and an accented spelling are one word."""
    return "".join(c for c in unicodedata.normalize("NFKD", word.lower()) if not unicodedata.combining(c))


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def name_stem_digest(stem: str) -> str:
    """The digest to put in NAME_STEMS, with the number of letters, for the first letters of a name."""
    return _digest(_fold(stem))


def line_digest(line: str) -> str:
    """The digest that pins a line in PUBLIC_SOURCE_LINES: the SHA-256 of its exact text, without the line ending."""
    return _digest(line.rstrip("\r\n"))


_WORDS = re.compile(r"[^\W\d_]+")


def name_words(text: str) -> List[str]:
    """The words of a text that begin with a name the scanner knows as a digest, as they are written, each once."""
    shortest = min((length for length, _ in NAME_STEMS), default=0)
    if not shortest:
        return []
    found = []
    for word in dict.fromkeys(_WORDS.findall(text)):
        if len(word) < shortest:
            continue
        folded = _fold(word)
        if any(len(folded) >= length and _digest(folded[:length]) == stem for length, stem in NAME_STEMS):
            found.append(word)
    return found


def is_public_source_line(rel: str, line: str) -> bool:
    """True when this exact line of this exact file is pinned as a public record's own title or address."""
    digest = line_digest(line)
    return any(pin.path == rel and pin.digest == digest for pin in PUBLIC_SOURCE_LINES)


def _private_match(line: str) -> Optional[str]:
    """The first private term, or the first word of a name known as a digest, in this line."""
    for pattern in _PRIVATE:
        found = pattern.search(line)
        if found:
            return found.group(0)
    words = name_words(line)
    return words[0] if words else None


def apply_rule(rule: Rule, rel: str, line: str) -> Optional[str]:
    """The first match of the rule on this line that is not ignored, or None.

    For HYG105 a private term or a name known as a digest is excused only on a line pinned in PUBLIC_SOURCE_LINES; label wording never is.
    """
    if rule.ignore_line and re.search(rule.ignore_line, line):
        return None
    for match in _COMPILED[rule.code].finditer(line):
        if rule.ignore_match and re.fullmatch(rule.ignore_match, match.group(0)):
            continue
        return match.group(0)
    if rule.code == "HYG105":
        hit = _private_match(line)
        if hit is not None and not is_public_source_line(rel, line):
            return hit
    return None


def _may_match(rule: Rule, text: str) -> bool:
    """False only when the rule cannot match anywhere in the text, so that most files are not read line by line for every rule."""
    if rule.needle and rule.needle not in text:
        return False
    if _COMPILED[rule.code].search(text):
        return True
    return rule.code == "HYG105" and (any(pattern.search(text) for pattern in _PRIVATE) or bool(name_words(text)))


def candidate_files(root: Path) -> List[str]:
    """Repository-relative POSIX paths of everything that would be published, sorted."""
    if (root / ".git").exists():
        try:
            done = subprocess.run(["git", "-C", str(root), "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
                                  capture_output=True, check=True)
            names = [n for n in done.stdout.decode("utf-8", "replace").split("\0") if n]
            return sorted(n for n in set(names) if (root / n).is_file())
        except (OSError, subprocess.CalledProcessError):
            pass
    out = []
    for base, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for name in files:
            out.append(Path(base, name).relative_to(root).as_posix())
    return sorted(out)


def check_names(paths: Iterable[str]) -> List[Finding]:
    """File-name rules: blocked types, names that do not survive a clone, case-only duplicates."""
    findings: List[Finding] = []
    seen = {}
    for rel in paths:
        name = rel.rsplit("/", 1)[-1]
        low = name.lower()
        suffix = ("." + low.rsplit(".", 1)[-1]) if "." in low else ""
        if rel == PRIVATE_TERMS_FILE:
            findings.append(Finding("HYG207", rel, 0, "the private term list is part of what would be published, and it names the private origin of the material. Keep it out of Git (add it to .gitignore)"))
        if rel not in ALLOWED_FILES:
            if suffix in BLOCKED_SUFFIXES:
                findings.append(Finding("HYG201", rel, 0, "file type that does not belong in the repository (Office, PDF, archive, key, database, log or binary)"))
            if low in BLOCKED_NAMES or low.startswith("~$") or low.endswith(".swp") or (low.startswith(".env.") and low != ".env.example"):
                findings.append(Finding("HYG201", rel, 0, "editor, operating-system or environment file"))
        stem = low.split(".", 1)[0]
        if stem in WINDOWS_RESERVED or BAD_NAME_CHARS.search(name) or name.endswith((" ", ".")):
            findings.append(Finding("HYG204", rel, 0, "file name that Windows cannot create"))
        if len(rel) > 200:
            findings.append(Finding("HYG204", rel, 0, "path longer than 200 characters; a clone inside a deep Windows folder may fail"))
        key = rel.lower()
        if key in seen and seen[key] != rel:
            findings.append(Finding("HYG205", rel, 0, "differs only by case from %s; a clone on Windows or macOS would lose one" % seen[key]))
        seen.setdefault(key, rel)
    return findings


def decode_text(data: bytes) -> Optional[str]:
    """The text of some bytes, or None when they are binary or not UTF-8."""
    if b"\0" in data[:8192]:
        return None
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return None


def read_text(path: Path) -> Optional[str]:
    """The text of a file, or None when it is binary or not UTF-8."""
    return decode_text(path.read_bytes())


def scan_bytes(rel: str, data: bytes) -> List[Finding]:
    """The findings in one file, given its repository-relative path and its content."""
    findings: List[Finding] = []
    if len(data) > MAX_BYTES and rel not in ALLOWED_FILES:
        findings.append(Finding("HYG202", rel, 0, "larger than 1 MiB (%d bytes); the repository is for text and small figures" % len(data)))
    if rel in SELF_FILES or rel == PRIVATE_TERMS_FILE:
        return findings
    for rule in RULES:
        if rule.on_names:
            hit = apply_rule(rule, rel, rel)
            if hit:
                findings.append(Finding(rule.code, rel, 0, "%s in the file name. %s" % (rule.label, rule.advice), hit))
    suffix = PurePosixPath(rel).suffix.lower()
    if suffix in BLOCKED_SUFFIXES and rel not in ALLOWED_FILES:
        return findings
    text = decode_text(data)
    if text is None:
        findings.append(Finding("HYG203", rel, 0, "not UTF-8 text; every file here should be readable as text"))
        return findings
    active = [rule for rule in RULES if _may_match(rule, text)]
    if not active:
        return findings
    for number, line in enumerate(text.split("\n"), 1):
        for rule in active:
            hit = apply_rule(rule, rel, line)
            if hit:
                shown = hit if rule.code != "HYG106" else "U+%04X" % ord(hit)
                findings.append(Finding(rule.code, rel, number, "%s. %s" % (rule.label, rule.advice), shown))
    return findings


def scan_file(root: Path, rel: str) -> List[Finding]:
    return scan_bytes(rel, (root / rel).read_bytes())


def scan(root: Path = REPO, files: Optional[Sequence[str]] = None, private_terms: Optional[Sequence[str]] = None) -> Tuple[List[Finding], List[str], int]:
    """Scan; returns (findings, notices, number of files scanned).

    ``private_terms`` replaces the list that would otherwise be read from the environment and from the folder.
    """
    terms = load_private_terms(root) if private_terms is None else list(private_terms)
    invalid = use_private_terms(terms)
    names = list(files) if files is not None else candidate_files(root)
    findings = check_names(names)
    findings += [Finding("HYG206", PRIVATE_TERMS_FILE, 0, "private term number %d is not a valid regular expression, so it was not used" % number) for number in invalid]
    for rel in names:
        if (root / rel).is_file():
            findings += scan_file(root, rel)
    notices = []
    if not terms:
        notices.append("The scan for private terms is off: no list was found. Put one regular expression per line in %s (Git ignores it) or set %s. Only confidentiality-label wording was looked for." % (PRIVATE_TERMS_FILE, PRIVATE_TERMS_ENV))
    if not any(n.lower() in LICENSE_NAMES for n in names if "/" not in n):
        notices.append("No LICENSE file: the license decision is still open. Nothing in this repository grants one.")
    findings.sort(key=lambda f: (f.path, f.line, f.code))
    return findings, notices, len(names)


# ------------------------------------------------------------------------------------------------------------ history
class HistoryError(RuntimeError):
    """The history cannot be read: this is not a Git repository, or Git is not available."""


def _git(root: Path, *args: str, data: Optional[bytes] = None) -> bytes:
    try:
        done = subprocess.run(["git", "-C", str(root)] + list(args), capture_output=True, check=True, input=data)
    except OSError as exc:
        raise HistoryError("git is not available: %s" % exc) from exc
    except subprocess.CalledProcessError as exc:
        raise HistoryError("git %s failed: %s" % (" ".join(args[:2]), exc.stderr.decode("utf-8", "replace").strip())) from exc
    return done.stdout


def _git_each(root: Path, calls: Sequence[Sequence[str]]) -> List[bytes]:
    """The output of each of several Git commands, run side by side because starting a process is most of what each one costs."""
    with ThreadPoolExecutor(max_workers=8) as pool:
        return list(pool.map(lambda args: _git(root, *args), calls))


def history_commits(root: Path) -> List[str]:
    """Every commit reachable from any ref, oldest first."""
    if not (root / ".git").exists():
        raise HistoryError("%s is not a Git repository" % root)
    return _git(root, "rev-list", "--reverse", "--all").decode().split()


def history_versions(root: Path, commits: Sequence[str]) -> Dict[str, Tuple[str, str]]:
    """Every file version that any commit adds or changes: its blob id -> (the first commit that has it, its path there)."""
    first: Dict[str, Tuple[str, str]] = {}
    calls = [("diff-tree", "-r", "-m", "--root", "--no-commit-id", "--no-renames", "--raw", "-z", commit) for commit in commits]
    for commit, output in zip(commits, _git_each(root, calls)):
        raw = output.split(b"\0")
        for meta, path in zip(raw[0::2], raw[1::2]):
            fields = meta.lstrip(b":").split()
            if len(fields) < 5:
                continue
            mode, blob, status = fields[1], fields[3].decode(), fields[4].decode()
            if status.startswith("D") or mode == b"160000" or set(blob) == {"0"}:
                continue
            first.setdefault(blob, (commit, path.decode("utf-8", "replace")))
    return first


def read_blobs(root: Path, blobs: Sequence[str]) -> Dict[str, bytes]:
    """The content of each blob that exists."""
    out = _git(root, "cat-file", "--batch", data=("\n".join(blobs) + "\n").encode())
    found: Dict[str, bytes] = {}
    position = 0
    for blob in blobs:
        end = out.index(b"\n", position)
        header = out[position:end].split()
        if len(header) == 3 and header[1] == b"blob":
            size = int(header[2])
            found[blob] = out[end + 1:end + 1 + size]
            position = end + 1 + size + 1
        else:
            position = end + 1
    return found


def _relabel(findings: Iterable[Finding], commit: str) -> List[Finding]:
    return [Finding(f.code, "%s @ %s" % (f.path, commit[:7]), f.line, f.message, f.excerpt) for f in findings]


def scan_text(label: str, text: str) -> List[Finding]:
    """Every rule, applied to each line of a piece of text that is not a file: a commit message, an identity, a ref."""
    findings: List[Finding] = []
    for number, line in enumerate(text.split("\n"), 1):
        for rule in RULES:
            hit = apply_rule(rule, "", line)
            if hit:
                findings.append(Finding(rule.code, label, number, "%s. %s" % (rule.label, rule.advice), hit if rule.code != "HYG106" else "U+%04X" % ord(hit)))
    return findings


def history_name_findings(root: Path, commits: Sequence[str]) -> Tuple[List[Finding], int]:
    """File-name rules on the tree of every commit; returns the findings, once each, and the number of distinct paths."""
    findings: List[Finding] = []
    reported, paths = set(), set()
    calls = [("ls-tree", "-r", "--name-only", "-z", commit) for commit in commits]
    for commit, output in zip(commits, _git_each(root, calls)):
        names = [n for n in output.decode("utf-8", "replace").split("\0") if n]
        paths.update(names)
        for finding in check_names(sorted(names)):
            key = (finding.code, finding.path, finding.message)
            if key not in reported:
                reported.add(key)
                findings += _relabel([finding], commit)
    return findings, len(paths)


def history_message_findings(root: Path) -> List[Finding]:
    """The rules on every commit message, and on the name and address of every author and committer."""
    fmt = "%H%x1f%an%x1f%ae%x1f%cn%x1f%ce%x1f%B%x1e"
    findings: List[Finding] = []
    reported = set()
    for record in _git(root, "log", "--all", "--format=" + fmt).decode("utf-8", "replace").split("\x1e"):
        record = record.lstrip("\n")
        if not record:
            continue
        commit, author, author_mail, committer, committer_mail, message = record.split("\x1f", 5)
        for role, name, mail in (("author", author, author_mail), ("committer", committer, committer_mail)):
            for finding in scan_text("commit %s %s" % (commit[:7], role), "%s <%s>" % (name, mail)):
                key = (finding.code, finding.excerpt, role)
                if key not in reported:
                    reported.add(key)
                    findings.append(finding)
        findings += scan_text("commit %s message" % commit[:7], message)
    return findings


def history_ref_findings(root: Path) -> Tuple[List[Finding], List[str]]:
    """The rules on every ref name and tag message, and the refs that are not branches."""
    findings: List[Finding] = []
    others = []
    for record in _git(root, "for-each-ref", "--format=%(refname)%1f%(taggername)%1f%(taggeremail)%1f%(contents)%1e").decode("utf-8", "replace").split("\x1e"):
        record = record.lstrip("\n")
        if not record:
            continue
        ref, tagger, tagger_mail, contents = record.split("\x1f", 3)
        if not ref.startswith("refs/heads/"):
            others.append(ref)
        findings += scan_text("ref %s" % ref, "%s\n%s <%s>\n%s" % (ref, tagger, tagger_mail, contents) if tagger or contents.strip() else ref)
    return findings, others


def scan_history(root: Path = REPO, private_terms: Optional[Sequence[str]] = None) -> Tuple[List[Finding], List[str], Dict[str, int]]:
    """Scan everything that a push of the whole history would publish.

    Every file version that any commit ever added or changed is read and scanned as a file is, so a term that was removed from
    the tree but is still in an old commit is found. So are the names of all paths, every commit message, every author and
    committer, and every ref. Returns (findings, notices, counts).
    """
    use_private_terms(load_private_terms(root) if private_terms is None else list(private_terms))
    commits = history_commits(root)
    versions = history_versions(root, commits)
    findings: List[Finding] = []
    unreadable = 0
    ids = list(versions)
    for start in range(0, len(ids), 200):
        batch = ids[start:start + 200]
        blobs = read_blobs(root, batch)
        for blob in batch:
            commit, rel = versions[blob]
            if blob not in blobs:
                unreadable += 1
                continue
            findings += _relabel(scan_bytes(rel, blobs[blob]), commit)
    names, path_count = history_name_findings(root, commits)
    findings += names
    findings += history_message_findings(root)
    ref_findings, others = history_ref_findings(root)
    findings += ref_findings
    notices = []
    if unreadable:
        notices.append("%d file version(s) could not be read, so they were not scanned." % unreadable)
    if _git(root, "rev-parse", "--is-shallow-repository").strip() == b"true":
        notices.append("This is a shallow clone: only the commits that were fetched were scanned.")
    if others:
        notices.append("Refs other than branches exist (%s). Pushing them publishes what they point to." % ", ".join(others))
    findings.sort(key=lambda f: (f.path, f.line, f.code))
    return findings, notices, {"commits": len(commits), "file_versions": len(versions), "paths": path_count}


def describe_rules() -> str:
    lines = ["Rules (a match on any line of any file, and for some rules in file names):", ""]
    for rule in RULES:
        lines.append("  %s  %s%s" % (rule.code, rule.label, "  (also file names)" if rule.on_names else ""))
        lines.append("          %s" % rule.advice)
    lines += ["", "HYG105 also looks for every pattern in the private term list: one regular expression per line in %s" % PRIVATE_TERMS_FILE,
              "(Git ignores that file) or in the environment variable %s. The list is not part of the repository, because it would" % PRIVATE_TERMS_ENV,
              "publish the terms. Without a list, HYG105 looks for confidentiality-label wording and for the authority's name only.",
              "",
              "HYG105 knows the name of the authority that the paper discusses as a digest (%d name stem%s), so that this script does not repeat it." % (
                  len(NAME_STEMS), "" if len(NAME_STEMS) == 1 else "s"),
              "A word matches when its first letters, lower-cased and without accents, have that digest: any case, any inflection, in text, in an",
              "address and in a file name. The name passes on exactly these %d lines, each a public record's own title or address, pinned by file" % len(PUBLIC_SOURCE_LINES),
              "and by the SHA-256 of the whole line (the first 12 characters are shown); a line that differs by a character is not pinned:"]
    for pin in PUBLIC_SOURCE_LINES:
        lines.append("  %s  %s  %s" % (pin.path, pin.digest[:12], pin.what))
    lines += ["", "File rules (HYG201\u2013HYG207):",
              "  HYG201  blocked file type or editor/OS file (%s ...)" % ", ".join(sorted(BLOCKED_SUFFIXES)[:6]),
              "  HYG202  file larger than 1 MiB",
              "  HYG203  not UTF-8 text",
              "  HYG204  file name Windows cannot create, or a path over 200 characters",
              "  HYG205  two files that differ only by case",
              "  HYG206  an entry in the private term list is not a valid regular expression",
              "  HYG207  the private term list is among the files that would be published",
              "", "With --history, every rule above is also applied to each file version that any commit added or changed (reported as path @ commit),",
              "to the path names in every commit, to every commit message, to every author and committer, and to every ref.",
              "", "Skipped: %s. Two files that quote the patterns are not read: %s." % (", ".join(sorted(SKIP_DIRS)), ", ".join(sorted(SELF_FILES)))]
    return "\n".join(lines)


def pin_entry(root: Path, spec: str) -> Tuple[str, str]:
    """For 'path:line number', the exact line and the PUBLIC_SOURCE_LINES entry that would pin it. Raises ValueError if there is no such line."""
    path, _, number = spec.rpartition(":")
    if not path or not number.isdigit() or int(number) < 1:
        raise ValueError("expected PATH:LINE, for example references/public-records.md:10")
    target = (root / path).resolve()
    if root.resolve() not in target.parents or not target.is_file():
        raise ValueError("%s is not a file inside %s" % (path, root))
    text = read_text(target)
    if text is None:
        raise ValueError("%s is not UTF-8 text" % path)
    rows = text.split("\n")
    if int(number) > len(rows):
        raise ValueError("%s has only %d lines" % (path, len(rows)))
    line = rows[int(number) - 1].rstrip("\r")
    rel = target.relative_to(root.resolve()).as_posix()
    return line, 'PublicSourceLine("%s", "%s", "<which record, and its title or its address>"),' % (rel, line_digest(line))


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--root", default=str(REPO), help="folder to scan (default: this repository)")
    parser.add_argument("--history", action="store_true", help="also scan the whole Git history: every file version, path, commit message, author, committer and ref")
    parser.add_argument("--rules", action="store_true", help="list the rules and the pinned public-record lines, and exit")
    parser.add_argument("--pin", metavar="PATH:LINE", help="print the PUBLIC_SOURCE_LINES entry for one line of a file, and exit; add it only for a public record's own title or address")
    parser.add_argument("--json", action="store_true", help="print a machine-readable result")
    args = parser.parse_args(argv)
    if args.rules:
        print(describe_rules())
        return 0
    if args.pin:
        try:
            line, entry = pin_entry(Path(args.root), args.pin)
        except ValueError as exc:
            print("error: %s" % exc, file=sys.stderr)
            return 2
        print("The line:\n    %s\n\nTo let it name the authority, add this to PUBLIC_SOURCE_LINES in scripts/check_hygiene.py, in a reviewed commit,\n"
              "and only if the whole line is a public record's own title or address:\n    %s" % (line, entry))
        return 0
    root = Path(args.root).resolve()
    terms = load_private_terms(root)
    findings, notices, count = scan(root, private_terms=terms)
    counts = None
    if args.history:
        try:
            more, more_notices, counts = scan_history(root, private_terms=terms)
        except HistoryError as exc:
            print("error: --history needs a Git history that can be read: %s" % exc, file=sys.stderr)
            return 2
        findings = findings + more
        notices = notices + more_notices
    if args.json:
        print(json.dumps({"files": count, "private_terms": len(terms), "history": counts, "findings": [f.as_dict() for f in findings], "notices": notices}, indent=2, ensure_ascii=False))
        return 1 if findings else 0
    for finding in findings:
        print(finding.format())
    for notice in notices:
        print("note: " + notice)
    if findings:
        print("\n%d finding(s) in %d file(s) scanned%s. Run with --rules to see what is looked for." % (
            len(findings), count, " and %d commit(s)" % counts["commits"] if counts else ""))
        return 1
    internal = "internal term, " if terms else ""
    print("Hygiene scan clean: %d files, no private link, local path, credential, e-mail address, %sauthority name outside %d pinned public-record lines, confidentiality label, hidden character, draft marker or claim of finality." % (
        count, internal, len(PUBLIC_SOURCE_LINES)))
    if counts:
        print("History scan clean: %d commits, %d file versions and %d paths, with every commit message, author, committer and ref name, under the same rules." % (
            counts["commits"], counts["file_versions"], counts["paths"]))
    return 0


if __name__ == "__main__":
    for _stream in (sys.stdout, sys.stderr):  # a legacy console code page must not break the output
        getattr(_stream, "reconfigure", lambda **_: None)(encoding="utf-8", errors="replace")
    sys.exit(main())
