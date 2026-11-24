#!/usr/bin/env python3
"""Check the figures: required metadata, drawing properties and sync with the documents.

    python scripts/check_figures.py

Exit code 0 means every figure has its metadata, alt text and description, every drawing has a title and a description element and
stays within the width and font-size limits set below, and every block in the documents matches its source. These are automated
checks on the files. They are not an accessibility assessment (conformance to a standard is NOT ASSESSED), and they do not show
that a figure is usable on a phone: the limits are a proxy that was chosen to keep text from being scaled down.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sync_figures  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
REQUIRED = ("id", "title", "caption", "alt", "description", "kind", "used_in")
# A phone is about 360 to 430 px wide, and a page leaves it about 330 to 360 for a picture. A drawing wider than NARROW_MAX
# would be scaled down there, and its smallest text with it.
NARROW_MAX = 380
WIDE_RANGE = (800, 900)
# The smallest text, in drawing pixels. At the scale of a phone (about 0.9 to 1.0) it stays near 12 px.
MIN_FONT = 13
DISPLAY_WIDTH_RANGE = (300, 480)


def run_tool(args):
    env = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
    done = subprocess.run([sys.executable] + args, capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=str(REPO), env=env)
    return done.returncode, (done.stdout + done.stderr).strip()


def svg_facts(svg: str):
    """The width and height of an SVG's viewBox and its smallest font size, read from its text; None for what is not there."""
    box = re.search(r'viewBox="\s*-?[\d.]+[\s,]+-?[\d.]+[\s,]+([\d.]+)[\s,]+([\d.]+)\s*"', svg[:3000])
    sizes = [float(s) for s in re.findall(r'font-size="([\d.]+)"', svg)]
    return (float(box.group(1)) if box else None, float(box.group(2)) if box else None, min(sizes) if sizes else None)


def drawing_problems(fid, name, svg, wide):
    """What a drawing needs to carry its own title and description, and to keep its text from being scaled down where it is shown."""
    problems = []
    if "<title" not in svg or "<desc" not in svg:
        problems.append("%s: %s has no <title> and <desc>" % (fid, name))
    if re.search(r"<script|on\w+\s*=|href=\"https?:", svg):
        problems.append("%s: %s contains a script, an event handler or an external link" % (fid, name))
    if re.search(r"<foreignObject|<image\b", svg):
        problems.append("%s: %s contains a foreignObject or an embedded image, which some viewers draw without text" % (fid, name))
    width, _height, smallest = svg_facts(svg)
    if width is None:
        problems.append("%s: %s has no viewBox" % (fid, name))
        return problems
    if wide and not WIDE_RANGE[0] <= width <= WIDE_RANGE[1]:
        problems.append("%s: %s is %d px wide; a wide drawing is %d to %d px, to fit a window of 900 px or more" % ((fid, name, width) + WIDE_RANGE))
    if not wide and width > NARROW_MAX:
        problems.append("%s: %s is %d px wide; a default drawing is at most %d px, so that a phone shows it without shrinking its text" % (fid, name, width, NARROW_MAX))
    if smallest is None or smallest < MIN_FONT:
        problems.append("%s: %s has text of %s px; the smallest allowed is %s px" % (fid, name, smallest, MIN_FONT))
    return problems


def table_problems(fid, table):
    """The data of a figure drawn from a table: rows that match the columns, and one execution color and at least one note."""
    problems = []
    columns, rows = table.get("columns"), table.get("rows")
    if not columns or not rows or any(len(r) != len(columns) for r in rows):
        problems.append("%s: table rows must match the columns" % fid)
    elif len(table.get("execution_kinds", [])) != len(rows):
        problems.append("%s: table needs one execution_kinds entry per row" % fid)
    if not table.get("notes"):
        problems.append("%s: table needs its notes, the rules that hold in every row" % fid)
    return problems


def mermaid_problems():
    """Every figure is a drawn SVG: a Mermaid block would take its colors, its text size and its layout from the reader's renderer."""
    problems = []
    for doc in sorted(REPO.rglob("*.md")):
        if any(part in (".git", "node_modules") for part in doc.parts):
            continue
        if re.search(r"^\s*```+\s*mermaid", doc.read_text(encoding="utf-8"), re.M | re.I):
            problems.append("%s has a Mermaid block; draw the figure in figures/src/svg_figures.py instead" % doc.relative_to(REPO).as_posix())
    return problems


# GitHub's script reads exactly these strings, with one space after the colon, in the media of a <source>.
GITHUB_THEME_MEDIA = re.compile(r"prefers-color-scheme: (?:light|dark)")
WIDTH_CONDITION = re.compile(r"\b(?:min|max)-(?:device-)?(?:width|height)\b")
SOURCE_MEDIA = re.compile(r"<source\b[^>]*?\bmedia=\"([^\"]*)\"", re.I)


def source_media_problems(text):
    """The media of a <source> that GitHub would rewrite while it also holds a size condition.

    For a reader who chose the dark or the light theme in GitHub's settings, GitHub replaces the media of a source that holds
    `prefers-color-scheme: dark` (or light) by one that is always true, or never, and the size condition is lost. A wide drawing in
    such a source would be shown at every width. The wide source writes the scheme without the space (`prefers-color-scheme:dark`).
    """
    return [m for m in SOURCE_MEDIA.findall(text) if GITHUB_THEME_MEDIA.search(m) and WIDTH_CONDITION.search(m)]


def picture_media_problems():
    problems = []
    for doc in sorted(REPO.rglob("*.md")):
        if any(part in (".git", "node_modules") for part in doc.parts):
            continue
        for media in source_media_problems(doc.read_text(encoding="utf-8")):
            problems.append("%s: a <source> media %r holds a size and a color scheme in the form GitHub rewrites for a reader's theme setting; "
                            "write the scheme without the space after the colon" % (doc.relative_to(REPO).as_posix(), media))
    return problems


def check():
    problems = []
    figures, banner = sync_figures.load()
    ids = [f["id"] for f in figures]
    if len(ids) != len(set(ids)):
        problems.append("duplicate figure ids in figures.json")
    for fig in figures + ([dict(banner, id="banner")] if banner else []):
        fid = fig["id"]
        is_banner = fid == "banner"
        for key in REQUIRED if not is_banner else ("title", "alt", "source", "images"):
            if not fig.get(key):
                problems.append("%s: %s is missing" % (fid, key))
        if len(fig.get("alt", "")) < 40:
            problems.append("%s: alt text is too short to describe the figure" % fid)
        if len(fig.get("alt", "")) > 420:
            problems.append("%s: alt text is long; keep it short and put detail in the description" % fid)
        if not is_banner and not fig.get("caption", "").endswith((".", "?")):
            problems.append("%s: caption should be a sentence ending in a full stop" % fid)
        if fig.get("kind", "svg") != "svg":
            problems.append("%s: kind must be svg; every figure is a drawn SVG" % fid)
            continue
        if fig.get("table"):
            problems += table_problems(fid, fig["table"])
        if not (REPO / fig.get("source", "")).is_file():
            problems.append("%s: source %s does not exist" % (fid, fig.get("source")))
        for label, images, wide in (("", fig.get("images") or {}, False), ("wide ", fig.get("wide") or {}, True)):
            if wide and not images:
                continue
            sizes = []
            for theme in ("light", "dark"):
                image = REPO / images.get(theme, "")
                if not image.is_file():
                    problems.append("%s: %s%s picture is missing" % (fid, label, theme))
                    continue
                svg = image.read_text(encoding="utf-8")
                problems += drawing_problems(fid, image.name, svg, wide)
                sizes.append(svg_facts(svg)[:2])
            if len(sizes) == 2 and sizes[0] != sizes[1]:
                problems.append("%s: the %slight and dark drawings differ in size" % (fid, label))
        shown = fig.get("display_width")
        if shown is not None:
            if fig.get("wide"):
                problems.append("%s: a figure with a wide drawing must not set display_width, which would shrink the wide drawing too" % fid)
            elif not DISPLAY_WIDTH_RANGE[0] <= shown <= DISPLAY_WIDTH_RANGE[1]:
                problems.append("%s: display_width %s is outside %d to %d" % ((fid, shown) + DISPLAY_WIDTH_RANGE))
    problems += ["gallery/documents: " + p for p in sync_figures.sync(check=True)]
    problems += mermaid_problems()
    problems += picture_media_problems()
    code, out = run_tool(["figures/src/svg_figures.py", "--check"])
    if code:
        problems.append("drawn SVGs: " + out.replace("\n", " "))
    return problems


def main():
    problems = check()
    for p in problems:
        print("FIGURE  " + p)
    if problems:
        print("\n%d figure problem(s)." % len(problems))
        return 1
    print("Figures pass the automated checks: metadata, drawing limits and sync (%d figures and a banner). This is not an accessibility assessment." % len(sync_figures.load()[0]))
    return 0


if __name__ == "__main__":
    for _stream in (sys.stdout, sys.stderr):  # a legacy console code page must not break the output
        getattr(_stream, "reconfigure", lambda **_: None)(encoding="utf-8", errors="replace")
    sys.exit(main())
