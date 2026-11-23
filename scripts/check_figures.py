#!/usr/bin/env python3
"""Check the figures: metadata, sources, rendered pictures, accessibility and sync with the documents.

    python scripts/check_figures.py

Exit code 0 means every figure has what it needs and every block in the documents matches its source.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sync_figures  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
REQUIRED = ("id", "title", "caption", "alt", "description", "kind", "used_in")
# A classDef with one of these names would restyle Mermaid's own elements, for example the labels on arrows.
MERMAID_CLASSES = {"label", "edgelabel", "node", "nodes", "cluster", "edge", "edgepath", "edgepaths", "marker", "root", "output", "flowchart", "labelbkg", "nodelabel", "default", "note", "actor", "messagetext", "loopline", "section"}


def run_tool(args):
    env = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
    done = subprocess.run([sys.executable] + args, capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=str(REPO), env=env)
    return done.returncode, (done.stdout + done.stderr).strip()


def lint_mermaid(fid, name, text):
    """What a Mermaid source needs to be accessible and legible in both color schemes."""
    problems = []
    for needle in ("accTitle:", "accDescr:"):
        if needle not in text:
            problems.append("%s: %s has no %s" % (fid, name, needle))
    if re.search(r"^\s*(click|href)\b", text, re.M):
        problems.append("%s: %s uses click or href, which GitHub does not allow" % (fid, name))
    for line in text.splitlines():
        if line.strip().startswith("classDef") and not all(k in line for k in ("fill:", "stroke:", "color:")):
            problems.append("%s: %s has a classDef without fill, stroke and text color, which is unsafe in dark mode: %s" % (fid, name, line.strip()))
        named = re.match(r"\s*classDef\s+(\w+)", line)
        if named and named.group(1).lower() in MERMAID_CLASSES:
            problems.append("%s: %s names a class %r, which is also a CSS class Mermaid uses for its own elements; the colors would leak into edge labels and clusters" % (fid, name, named.group(1)))
    return problems


def check():
    problems = []
    figures, banner = sync_figures.load()
    ids = [f["id"] for f in figures]
    if len(ids) != len(set(ids)):
        problems.append("duplicate figure ids in figures.json")
    for fig in figures:
        fid = fig["id"]
        for key in REQUIRED:
            if not fig.get(key):
                problems.append("%s: %s is missing" % (fid, key))
        if len(fig.get("alt", "")) < 40:
            problems.append("%s: alt text is too short to describe the figure" % fid)
        if len(fig.get("alt", "")) > 420:
            problems.append("%s: alt text is long; keep it short and put detail in the description" % fid)
        if not fig.get("caption", "").endswith((".", "?")):
            problems.append("%s: caption should be a sentence ending in a full stop" % fid)
        kind = fig.get("kind")
        if kind not in ("mermaid", "svg", "table"):
            problems.append("%s: kind must be mermaid, svg or table" % fid)
            continue
        if kind == "table":
            t = fig.get("table", {})
            if not t.get("columns") or not t.get("rows") or any(len(r) != len(t["columns"]) for r in t["rows"]):
                problems.append("%s: table rows must match the columns" % fid)
            continue
        source = REPO / fig.get("source", "")
        if not source.exists():
            problems.append("%s: source %s does not exist" % (fid, fig.get("source")))
        for theme in ("light", "dark"):
            image = REPO / fig.get("images", {}).get(theme, "")
            if not image.is_file():
                problems.append("%s: %s picture is missing" % (fid, theme))
                continue
            svg = image.read_text(encoding="utf-8")
            if "<title" not in svg or "<desc" not in svg:
                problems.append("%s: %s has no <title> and <desc>" % (fid, image.name))
            if re.search(r"<script|on\w+\s*=|href=\"https?:", svg):
                problems.append("%s: %s contains a script, an event handler or an external link" % (fid, image.name))
        if kind == "mermaid" and source.exists():
            problems += lint_mermaid(fid, source.name, source.read_text(encoding="utf-8"))
    problems += ["gallery/documents: " + p for p in sync_figures.sync(check=True)]
    for label, args in (("Mermaid renders", ["figures/src/render_mermaid.py", "--check"]), ("hand-drawn SVGs", ["figures/src/svg_figures.py", "--check"])):
        code, out = run_tool(args)
        if code:
            problems.append("%s: %s" % (label, out.replace("\n", " ")))
    return problems


def main():
    problems = check()
    for p in problems:
        print("FIGURE  " + p)
    if problems:
        print("\n%d figure problem(s)." % len(problems))
        return 1
    print("Figures are complete, accessible, rendered and in sync (%d figures and a banner)." % len(sync_figures.load()[0]))
    return 0


if __name__ == "__main__":
    for _stream in (sys.stdout, sys.stderr):  # a legacy console code page must not break the output
        getattr(_stream, "reconfigure", lambda **_: None)(encoding="utf-8", errors="replace")
    sys.exit(main())
