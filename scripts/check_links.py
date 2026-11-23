#!/usr/bin/env python3
"""Check the repository's Markdown for broken relative links, broken anchors, missing images and images without alt text.

    python scripts/check_links.py              # check everything, exit 1 on any problem
    python scripts/check_links.py --orphans    # also list Markdown pages nothing links to
    python scripts/check_links.py --external   # also print the external URLs found (checked by check_urls.py)

It works offline. It follows GitHub's rules for heading anchors, requires an exact-case match for every path (a link
that works on Windows or macOS but not on Linux is a broken link), and ignores links inside code.
"""
from __future__ import annotations

import argparse
import os
import re
import sys
import unicodedata
from pathlib import Path
from typing import Dict, List, Set, Tuple
from urllib.parse import unquote, urlsplit

REPO = Path(__file__).resolve().parents[1]
SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__", ".pytest_cache"}
LINK = re.compile(r"(!?)\[([^\]]*)\]\(\s*(<[^>]+>|[^)\s]+)(?:\s+(?:\"[^\"]*\"|'[^']*'))?\s*\)")
REF_DEF = re.compile(r"^\s{0,3}\[([^\]]+)\]:\s*(\S+)", re.M)
HTML_ATTR = re.compile(r"<(img|a|source|video|audio)\b([^>]*)>", re.I)
ATTR = re.compile(r"(\w[\w-]*)\s*=\s*(\"[^\"]*\"|'[^']*')")
HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
EXPLICIT_ANCHOR = re.compile(r"<(?:a|h[1-6]|div|span)\b[^>]*\b(?:id|name)\s*=\s*[\"']([^\"']+)[\"']", re.I)
FENCE = re.compile(r"^\s{0,3}(`{3,}|~{3,})")


def md_files(root: Path) -> List[Path]:
    out = []
    for base, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        out += [Path(base) / f for f in files if f.lower().endswith(".md")]
    return sorted(out)


def strip_code(text: str) -> str:
    """Blank out fenced code blocks and inline code, keeping line numbers."""
    lines, out, fence = text.split("\n"), [], None
    for line in lines:
        m = FENCE.match(line)
        if fence:
            if m and m.group(1)[0] == fence[0] and len(m.group(1)) >= len(fence):
                fence = None
            out.append("")
            continue
        if m:
            fence = m.group(1)
            out.append("")
            continue
        out.append(re.sub(r"`[^`\n]*`", lambda mm: " " * len(mm.group(0)), line))
    return "\n".join(out)


def slug(heading: str) -> str:
    text = re.sub(r"!\[([^\]]*)\]\([^)]*\)", r"\1", heading)
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = text.replace("`", "")
    text = re.sub(r"[*~]+", "", text)
    text = re.sub(r"(?<!\w)_+|_+(?!\w)", "", text)
    text = unicodedata.normalize("NFC", text).strip().lower()
    text = re.sub(r"[^\w\- ]", "", text, flags=re.UNICODE)
    return text.replace(" ", "-")


_ANCHORS: Dict[Path, Set[str]] = {}


def anchors_of(path: Path) -> Set[str]:
    if path in _ANCHORS:
        return _ANCHORS[path]
    found: Set[str] = set()
    seen: Dict[str, int] = {}
    text = path.read_text(encoding="utf-8", errors="replace")
    for line in strip_code(text).split("\n"):
        m = HEADING.match(line)
        if m:
            base = slug(m.group(2))
            n = seen.get(base, 0)
            seen[base] = n + 1
            found.add(base if n == 0 else "%s-%d" % (base, n))
    found.update(EXPLICIT_ANCHOR.findall(text))
    _ANCHORS[path] = found
    return found


def exact_case_exists(path: Path, root: Path = REPO) -> bool:
    """True when every component of `path` below `root` matches the on-disk spelling exactly. `path` must not be resolved."""
    try:
        rel = path.relative_to(root)
    except ValueError:
        return path.exists()
    cur = root
    for part in rel.parts:
        try:
            names = os.listdir(cur)
        except OSError:
            return False
        if part not in names:
            return False
        cur = cur / part
    return True


def targets_in(text: str) -> List[Tuple[int, str, str, str]]:
    """(line, kind, target, alt) for every link, image and HTML reference outside code."""
    body = strip_code(text)
    out: List[Tuple[int, str, str, str]] = []
    for m in LINK.finditer(body):
        line = body.count("\n", 0, m.start()) + 1
        target = m.group(3).strip("<>")
        out.append((line, "image" if m.group(1) else "link", target, m.group(2)))
    for m in REF_DEF.finditer(body):
        line = body.count("\n", 0, m.start()) + 1
        out.append((line, "link", m.group(2).strip("<>"), ""))
    for m in HTML_ATTR.finditer(body):
        line = body.count("\n", 0, m.start()) + 1
        attrs = {k.lower(): v[1:-1] for k, v in ATTR.findall(m.group(2))}
        tag = m.group(1).lower()
        if tag == "img":
            out.append((line, "image", attrs.get("src", ""), attrs.get("alt", "") if "alt" in attrs else None))
        elif tag == "source":
            for ref in re.split(r"\s*,\s*", attrs.get("srcset", "")):
                if ref.strip():
                    out.append((line, "image", ref.split()[0], "(source)"))
        elif tag == "a" and "href" in attrs:
            out.append((line, "link", attrs["href"], ""))
        elif tag in ("video", "audio") and "src" in attrs:
            out.append((line, "link", attrs["src"], ""))
    return out


def is_external(target: str) -> bool:
    scheme = urlsplit(target).scheme
    return bool(scheme) and scheme not in ("", "file")


def check(root: Path):
    problems: List[str] = []
    external: Dict[str, List[str]] = {}
    linked: Set[Path] = set()
    files = md_files(root)
    for path in files:
        text = path.read_text(encoding="utf-8", errors="replace")
        rel = path.relative_to(root).as_posix()
        for line, kind, target, alt in targets_in(text):
            where = "%s:%d" % (rel, line)
            if not target:
                problems.append("%s: empty %s target" % (where, kind))
                continue
            if kind == "image" and alt is None:
                problems.append("%s: image %s has no alt attribute" % (where, target))
            elif kind == "image" and alt == "" and not target.startswith("http"):
                problems.append("%s: image %s has empty alt text" % (where, target))
            if is_external(target):
                if urlsplit(target).scheme in ("http", "https"):
                    external.setdefault(target, []).append(where)
                continue
            if target.startswith("#"):
                frag = unquote(target[1:])
                if frag and frag not in anchors_of(path):
                    problems.append("%s: anchor #%s not found in this page" % (where, frag))
                continue
            parts = urlsplit(target)
            if parts.path.startswith("/"):
                raw = root / unquote(parts.path).lstrip("/")
            elif parts.path:
                raw = path.parent / unquote(parts.path)
            else:
                raw = path
            # Not resolve(): on Windows it would quietly correct the letter case that is checked below.
            dest = Path(os.path.normpath(raw))
            if not dest.exists():
                problems.append("%s: %s does not exist (%s)" % (where, kind, target))
                continue
            if not exact_case_exists(dest, root):
                problems.append("%s: %s matches only with different letter case (%s); that breaks on Linux" % (where, kind, target))
                continue
            dest = dest.resolve()
            if dest.suffix.lower() == ".md":
                linked.add(dest)
            if parts.fragment and dest.suffix.lower() == ".md":
                frag = unquote(parts.fragment)
                if frag not in anchors_of(dest):
                    shown = dest.relative_to(root).as_posix() if root in dest.parents else dest.as_posix()
                    problems.append("%s: anchor #%s not found in %s" % (where, frag, shown))
    # Folder READMEs are shown when the folder is opened, and GitHub finds the files under .github by itself.
    orphans = [p for p in files if p.resolve() not in linked and p.name.lower() != "readme.md" and p.parent != root and p.resolve().relative_to(root).parts[0] != ".github"]
    return problems, external, orphans, len(files)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--root", type=Path, default=REPO, help="repository root to check")
    parser.add_argument("--orphans", action="store_true", help="also report Markdown pages that no page links to")
    parser.add_argument("--external", action="store_true", help="also print the external URLs found")
    args = parser.parse_args(argv)
    problems, external, orphans, count = check(args.root.resolve())
    for p in problems:
        print("LINK  " + p)
    if args.orphans:
        for o in orphans:
            print("ORPHAN  %s is not linked from any page" % o.relative_to(args.root.resolve()).as_posix())
    if args.external:
        for url in sorted(external):
            print("EXTERNAL  %s  (%d use%s)" % (url, len(external[url]), "" if len(external[url]) == 1 else "s"))
    if problems or (args.orphans and orphans):
        print("\n%d problem(s) in %d Markdown files." % (len(problems) + (len(orphans) if args.orphans else 0), count))
        return 1
    print("Checked %d Markdown files: relative links, anchors, images and alt text are all fine." % count)
    return 0


if __name__ == "__main__":
    sys.exit(main())
