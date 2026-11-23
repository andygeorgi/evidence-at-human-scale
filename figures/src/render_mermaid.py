#!/usr/bin/env python3
"""Render the Mermaid figure sources to SVG (light and dark) and record what was rendered.

    python figures/src/render_mermaid.py                       # render every figures/src/F*.mmd
    python figures/src/render_mermaid.py --check               # fail if a rendered SVG is missing or older than its source
    python figures/src/render_mermaid.py --mmdc "npx --no-install mmdc" --puppeteer-config path/to/config.json

The documents embed the Mermaid source directly, which GitHub renders itself. These SVGs are for the figure gallery
and for anyone who needs a picture. They are rendered with Mermaid CLI (Node.js); this repository does not depend on
Node for anything else. The manifest in figures/render-manifest.json records the SHA-256 of each source and of each
SVG, so a changed source with a stale picture is caught by `python scripts/check_figures.py`.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

FIGURES = Path(__file__).resolve().parents[1]
SRC = FIGURES / "src"
MANIFEST = FIGURES / "render-manifest.json"
THEMES = {"light": ("default", "white"), "dark": ("dark", "#0d1117")}
FONT = "-apple-system, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif"
# Colors for what a source cannot set per node: arrow labels, notes, participants. They match the hand-drawn figures,
# keep text at 4.5:1 or better against its background, and give the sequence diagrams the same palette as the rest.
VARIABLES = {
    "light": {
        "fontFamily": FONT, "textColor": "#1B1F24", "lineColor": "#57606A", "edgeLabelBackground": "#FFFFFF",
        "noteBkgColor": "#F4F4F4", "noteBorderColor": "#777777", "noteTextColor": "#222222",
        "actorBkg": "#E8F1FB", "actorBorder": "#2F6DB5", "actorTextColor": "#0B2540", "actorLineColor": "#8C959F",
        "signalColor": "#57606A", "signalTextColor": "#1B1F24",
        "labelBoxBkgColor": "#F6F8FA", "labelBoxBorderColor": "#57606A", "labelTextColor": "#1B1F24", "loopTextColor": "#1B1F24",
        "clusterBkg": "#F6F8FA", "clusterBorder": "#D0D7DE", "titleColor": "#1B1F24",
    },
    "dark": {
        "fontFamily": FONT, "textColor": "#E6EDF3", "lineColor": "#8B949E", "edgeLabelBackground": "#30363D",
        "noteBkgColor": "#21262D", "noteBorderColor": "#8B949E", "noteTextColor": "#E6EDF3",
        "actorBkg": "#12304F", "actorBorder": "#58A6FF", "actorTextColor": "#CDE4FF", "actorLineColor": "#8B949E",
        "signalColor": "#C9D1D9", "signalTextColor": "#E6EDF3",
        "labelBoxBkgColor": "#161B22", "labelBoxBorderColor": "#8B949E", "labelTextColor": "#E6EDF3", "loopTextColor": "#E6EDF3",
        "clusterBkg": "#161B22", "clusterBorder": "#30363D", "titleColor": "#E6EDF3",
    },
}


def sha(path: Path) -> str:
    """SHA-256 of a file with line endings normalized, so a checkout on any platform hashes the same."""
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def sources():
    return sorted(SRC.glob("F*.mmd"))


def render(src: Path, theme: str, mmdc, puppeteer):
    out = FIGURES / ("%s-%s.svg" % (src.stem, theme))
    mm_theme, background = THEMES[theme]
    with tempfile.TemporaryDirectory() as tmp:
        config = Path(tmp) / "mermaid-config.json"
        config.write_text(json.dumps({"theme": mm_theme, "themeVariables": VARIABLES[theme],
                                      "sequence": {"actorFontFamily": FONT, "messageFontFamily": FONT, "noteFontFamily": FONT}}), encoding="utf-8")
        cmd = mmdc + ["-i", str(src), "-o", str(out), "-t", mm_theme, "-b", background, "-c", str(config), "-q"]
        cmd[0] = shutil.which(cmd[0]) or cmd[0]  # npx is npx.cmd on Windows
        if puppeteer:
            cmd += ["-p", str(puppeteer)]
        done = subprocess.run(cmd, capture_output=True, text=True)
    if done.returncode != 0 or not out.exists():
        raise SystemExit("mermaid-cli failed for %s (%s): %s" % (src.name, theme, (done.stderr or done.stdout).strip()))
    return out


def check():
    if not MANIFEST.exists():
        print("figures/render-manifest.json is missing. Run python figures/src/render_mermaid.py")
        return 1
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))["sources"]
    problems = []
    for src in sources():
        entry = manifest.get(src.stem)
        if entry is None:
            problems.append("%s has no manifest entry" % src.name)
            continue
        if entry["source_sha256"] != sha(src):
            problems.append("%s changed since it was rendered" % src.name)
        for theme in THEMES:
            svg = FIGURES / ("%s-%s.svg" % (src.stem, theme))
            if not svg.exists():
                problems.append("%s is missing" % svg.name)
            elif entry[theme + "_sha256"] != sha(svg):
                problems.append("%s differs from the recorded render" % svg.name)
    for stem in manifest:
        if not (SRC / (stem + ".mmd")).exists():
            problems.append("manifest lists %s, which has no source" % stem)
    if problems:
        print("Rendered Mermaid figures are out of date:\n  " + "\n  ".join(problems))
        return 1
    print("%d Mermaid figures match their rendered SVGs." % len(manifest))
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--mmdc", default="npx --yes @mermaid-js/mermaid-cli", help="command that runs Mermaid CLI")
    parser.add_argument("--puppeteer-config", type=Path, default=None, help="optional Puppeteer config (browser path, flags)")
    args = parser.parse_args(argv)
    if args.check:
        return check()
    mmdc = shlex.split(args.mmdc, posix=False) if sys.platform.startswith("win") else shlex.split(args.mmdc)
    manifest = {}
    for src in sources():
        entry = {"source_sha256": sha(src)}
        for theme in THEMES:
            entry[theme + "_sha256"] = sha(render(src, theme, mmdc, args.puppeteer_config))
        manifest[src.stem] = entry
        print("rendered %s" % src.name)
    MANIFEST.write_bytes((json.dumps({"tool": "mermaid-cli", "sources": manifest}, indent=2) + "\n").encode("utf-8"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
