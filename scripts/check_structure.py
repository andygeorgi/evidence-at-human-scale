#!/usr/bin/env python3
"""Check the structure of the repository's Markdown pages: the basics a screen-reader user navigates by.

    python scripts/check_structure.py              # exit 1 on any problem
    python scripts/check_structure.py --root DIR   # another folder

Rules, for every page except the GitHub issue and pull-request templates:

  STR001  exactly one H1 heading
  STR002  heading levels never skip downward (H2 then H4)
  STR003  no link text that says nothing out of context ("here", "this link", "read more")
  STR004  no table with an empty header row

Code and HTML comments are ignored. It works offline.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import List, Optional, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_links import md_files, strip_code  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
LINK_TEXT = re.compile(r"(?<!!)\[([^\]]+)\]\([^)]+\)")
GENERIC = re.compile(r"^(here|click here|this|link|this link|this page|read more|more|see more)$", re.I)
EMPTY_HEADER = re.compile(r"^\|(\s*\|)+\s*$")
DELIMITER = re.compile(r"^\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)*\|?\s*$")
EXEMPT = (".github/ISSUE_TEMPLATE/", ".github/pull_request_template.md")


def check_page(rel: str, text: str) -> List[str]:
    problems: List[str] = []
    body = re.sub(r"<!--.*?-->", lambda m: "\n" * m.group(0).count("\n"), strip_code(text), flags=re.S)
    previous = 0
    h1 = 0
    lines = body.split("\n")
    for number, line in enumerate(lines, 1):
        match = HEADING.match(line)
        if match:
            level = len(match.group(1))
            h1 += level == 1
            if previous and level > previous + 1:
                problems.append("%s:%d: STR002 heading jumps from H%d to H%d (%s)" % (rel, number, previous, level, match.group(2)[:50]))
            previous = level
        # Inline code is blanked in `body`, so a row of code cells looks empty: only a header (a row followed by the delimiter row) counts.
        following = lines[number].strip() if number < len(lines) else ""
        if EMPTY_HEADER.match(line.strip()) and DELIMITER.match(following):
            problems.append("%s:%d: STR004 table with an empty header row; name the columns" % (rel, number))
        for link in LINK_TEXT.finditer(line):
            if GENERIC.match(link.group(1).strip()):
                problems.append("%s:%d: STR003 link text %r says nothing out of context" % (rel, number, link.group(1)))
    if h1 != 1:
        problems.append("%s: STR001 has %d H1 headings; a page needs exactly one" % (rel, h1))
    return problems


def check(root: Path) -> tuple:
    problems: List[str] = []
    pages = md_files(root)
    for page in pages:
        rel = page.relative_to(root).as_posix()
        if rel.startswith(EXEMPT):
            continue
        problems += check_page(rel, page.read_text(encoding="utf-8", errors="replace"))
    return problems, len(pages)


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--root", type=Path, default=REPO, help="folder to check")
    args = parser.parse_args(argv)
    problems, count = check(args.root.resolve())
    for problem in problems:
        print(problem)
    if problems:
        print("\n%d structure problem(s) in %d Markdown files." % (len(problems), count))
        return 1
    print("Checked %d Markdown files: one H1 each, no skipped heading levels, no empty table headers, no generic link text." % count)
    return 0


if __name__ == "__main__":
    sys.exit(main())
