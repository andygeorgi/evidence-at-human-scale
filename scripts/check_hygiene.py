#!/usr/bin/env python3
"""Scan the repository for what must not reach a public repository, and for files that do not survive a clone.

    python scripts/check_hygiene.py            # scan, exit 1 on any finding
    python scripts/check_hygiene.py --rules    # list what is looked for, and where a rule is waived
    python scripts/check_hygiene.py --json     # machine-readable result

Standard library only; works offline on Windows, macOS and Linux. It scans every file Git would include (tracked, or
untracked and not ignored), or every file under the folder when Git is not available, and it also reads file names.

A finding is a reason to look, not a verdict. If a flagged line is legitimate, change the wording; if it cannot change
(for example a quoted public source), add a narrow waiver to ``RULES`` below, with the reason, in a reviewed commit.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Tuple

REPO = Path(__file__).resolve().parents[1]
SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__", ".pytest_cache", ".mypy_cache"}
# These two files quote the very patterns they look for.
SELF_FILES = {"scripts/check_hygiene.py", "tests/test_hygiene.py"}
MAX_BYTES = 1024 * 1024


@dataclass(frozen=True)
class Rule:
    code: str
    label: str
    pattern: str
    advice: str
    ignore_match: str = ""  # a match that matches this in full is fine
    ignore_line: str = ""  # a line that matches this is fine for this rule
    waivers: Tuple[Tuple[str, str], ...] = ()  # (path prefix, regex a line must match) where the rule is waived
    on_names: bool = False  # also apply to the file path


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
    Rule("HYG104", "e-mail address", r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+",
         "Use a role link or the repository's issue tracker, not a personal address.",
         ignore_match=r"(?i:[^@]+@(?:users\.noreply\.github\.com|example\.(?:com|org|net))|git@github\.com)"),
    Rule("HYG105", "internal vocabulary",
         r"Zebracorp|Project Aurora|Internal [Uu]se [Oo]nly|(?:Highly|Strictly) Confidential|MSIP_",
         "This names the private origin of the material. Use the public wording.",
         waivers=(("references/", r"https?://[^\s>]+\.is/|Ríkisendurskoðun"),), on_names=True),
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


def _waived(rule: Rule, rel: str, line: str) -> bool:
    return any(rel.startswith(prefix) and re.search(rx, line) for prefix, rx in rule.waivers)


def apply_rule(rule: Rule, rel: str, line: str) -> Optional[str]:
    """The first match of the rule on this line that is not waived or ignored, or None."""
    if rule.ignore_line and re.search(rule.ignore_line, line):
        return None
    if _waived(rule, rel, line):
        return None
    for match in _COMPILED[rule.code].finditer(line):
        if rule.ignore_match and re.fullmatch(rule.ignore_match, match.group(0)):
            continue
        return match.group(0)
    return None


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


def read_text(path: Path) -> Optional[str]:
    """The text of a file, or None when it is binary or not UTF-8."""
    data = path.read_bytes()
    if b"\0" in data[:8192]:
        return None
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return None


def scan_file(root: Path, rel: str) -> List[Finding]:
    findings: List[Finding] = []
    path = root / rel
    if path.stat().st_size > MAX_BYTES and rel not in ALLOWED_FILES:
        findings.append(Finding("HYG202", rel, 0, "larger than 1 MiB (%d bytes); the repository is for text and small figures" % path.stat().st_size))
    if rel in SELF_FILES:
        return findings
    for rule in RULES:
        if rule.on_names:
            hit = apply_rule(rule, rel, rel)
            if hit:
                findings.append(Finding(rule.code, rel, 0, "%s in the file name. %s" % (rule.label, rule.advice), hit))
    suffix = path.suffix.lower()
    if suffix in BLOCKED_SUFFIXES and rel not in ALLOWED_FILES:
        return findings
    text = read_text(path)
    if text is None:
        findings.append(Finding("HYG203", rel, 0, "not UTF-8 text; every file here should be readable as text"))
        return findings
    for number, line in enumerate(text.split("\n"), 1):
        for rule in RULES:
            hit = apply_rule(rule, rel, line)
            if hit:
                shown = hit if rule.code != "HYG106" else "U+%04X" % ord(hit)
                findings.append(Finding(rule.code, rel, number, "%s. %s" % (rule.label, rule.advice), shown))
    return findings


def scan(root: Path = REPO, files: Optional[Sequence[str]] = None) -> Tuple[List[Finding], List[str], int]:
    """Scan; returns (findings, notices, number of files scanned)."""
    names = list(files) if files is not None else candidate_files(root)
    findings = check_names(names)
    for rel in names:
        if (root / rel).is_file():
            findings += scan_file(root, rel)
    notices = []
    if not any(n.lower() in LICENSE_NAMES for n in names if "/" not in n):
        notices.append("No LICENSE file: the license decision is still open. Nothing in this repository grants one.")
    findings.sort(key=lambda f: (f.path, f.line, f.code))
    return findings, notices, len(names)


def describe_rules() -> str:
    lines = ["Rules (a match on any line of any file, and for some rules in file names):", ""]
    for rule in RULES:
        lines.append("  %s  %s%s" % (rule.code, rule.label, "  (also file names)" if rule.on_names else ""))
        lines.append("          %s" % rule.advice)
        for prefix, rx in rule.waivers:
            lines.append("          waived under %s for lines matching: %s" % (prefix, rx))
    lines += ["", "File rules:",
              "  HYG201  blocked file type or editor/OS file (%s ...)" % ", ".join(sorted(BLOCKED_SUFFIXES)[:6]),
              "  HYG202  file larger than 1 MiB",
              "  HYG203  not UTF-8 text",
              "  HYG204  file name Windows cannot create, or a path over 200 characters",
              "  HYG205  two files that differ only by case",
              "", "Skipped: %s. Two files that quote the patterns are not read: %s." % (", ".join(sorted(SKIP_DIRS)), ", ".join(sorted(SELF_FILES)))]
    return "\n".join(lines)


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--root", default=str(REPO), help="folder to scan (default: this repository)")
    parser.add_argument("--rules", action="store_true", help="list the rules and exit")
    parser.add_argument("--json", action="store_true", help="print a machine-readable result")
    args = parser.parse_args(argv)
    if args.rules:
        print(describe_rules())
        return 0
    findings, notices, count = scan(Path(args.root).resolve())
    if args.json:
        print(json.dumps({"files": count, "findings": [f.as_dict() for f in findings], "notices": notices}, indent=2, ensure_ascii=False))
        return 1 if findings else 0
    for finding in findings:
        print(finding.format())
    for notice in notices:
        print("note: " + notice)
    if findings:
        print("\n%d finding(s) in %d file(s) scanned. Run with --rules to see what is looked for." % (len(findings), count))
        return 1
    print("Hygiene scan clean: %d files, no private link, local path, credential, e-mail address, internal term, hidden character, draft marker or claim of finality." % count)
    return 0


if __name__ == "__main__":
    sys.exit(main())
