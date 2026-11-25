#!/usr/bin/env python3
"""Keep the figures in the documents in sync with their sources.

    python scripts/sync_figures.py            # rewrite every figure block, the banner and the gallery from figures/figures.json
    python scripts/sync_figures.py --check    # fail if any of them differs from what would be written

A document places a figure with a pair of markers:

    <!-- figure:F03:start -->
    <!-- figure:F03:end -->

Everything between the markers is generated: the caption, the picture (a drawing in a light and a dark scheme) and a collapsed text
description, which for a figure drawn from a table also holds that table. The banner in README.md, below its first paragraph, sits between
<!-- banner:start --> and <!-- banner:end -->. Edit figures/figures.json and the drawing code in figures/src, never the generated block.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_links import slug  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
FIGURES = REPO / "figures"
META = FIGURES / "figures.json"
README = REPO / "README.md"
MARKER = re.compile(r"(<!-- figure:(F\d\d):start -->)(.*?)(<!-- figure:\2:end -->)", re.S)
BANNER_MARKER = re.compile(r"(<!-- banner:start -->)(.*?)(<!-- banner:end -->)", re.S)
GALLERY = FIGURES / "README.md"
GALLERY_MARKER = re.compile(r"(<!-- gallery:start -->)(.*?)(<!-- gallery:end -->)", re.S)
WIDE_MEDIA = "(min-width: 900px)"
DARK_MEDIA = "(prefers-color-scheme: dark)"
# When a reader has chosen the dark theme in GitHub's settings rather than "sync with system", GitHub's script replaces the media of
# every <source> that holds "prefers-color-scheme: dark", written with that one space, by a condition that is always true. A wide
# drawing in such a source would then be shown at every width, a phone's included. Written without the space, the condition is not
# recognised and the browser keeps applying it, together with the width.
WIDE_DARK_MEDIA = "%s and (prefers-color-scheme:dark)" % WIDE_MEDIA


def load():
    data = json.loads(META.read_text(encoding="utf-8"))
    return data["figures"], data.get("banner")


def relpath(from_file: Path, target: Path) -> str:
    return Path(os.path.relpath(target, from_file.parent)).as_posix()


def anchor(fig) -> str:
    return slug("%s %s" % (fig["id"], fig["title"]))


def picture(doc: Path, fig, width=None) -> str:
    """A centered picture. Its <img> is the default drawing in the light scheme, which is 360 px wide so that a phone shows it at its
    natural size. A source switches to the dark drawing in a dark scheme and, where the figure has a wide drawing, to that in a
    window of at least 900 px. Without a wide drawing, `width` is the size at which a large screen shows the default drawing.
    The wide dark drawing is chosen by the system's scheme (see WIDE_DARK_MEDIA); the narrow ones also follow GitHub's theme setting."""
    path = lambda rel: relpath(doc, REPO / rel)  # noqa: E731
    sources = []
    if fig.get("wide"):
        sources.append('<source media="%s" srcset="%s">' % (WIDE_DARK_MEDIA, path(fig["wide"]["dark"])))
        sources.append('<source media="%s" srcset="%s">' % (WIDE_MEDIA, path(fig["wide"]["light"])))
    sources.append('<source media="%s" srcset="%s">' % (DARK_MEDIA, path(fig["images"]["dark"])))
    alt = fig["alt"].replace('"', "&quot;")
    size = ' width="%d"' % width if width else ""
    return '<p align="center">\n<picture>\n%s\n<img src="%s" alt="%s"%s>\n</picture>\n</p>' % ("\n".join(sources), path(fig["images"]["light"]), alt, size)


def table_md(fig) -> str:
    """The data behind a figure that is drawn from a table, as a Markdown table with its notes: the text alternative to the picture."""
    t = fig["table"]
    lines = ["| " + " | ".join(t["columns"]) + " |", "|" + "---|" * len(t["columns"])]
    lines += ["| " + " | ".join(row) + " |" for row in t["rows"]]
    return "\n\n".join(["\n".join(lines)] + t.get("notes", []))


def body(doc: Path, fig) -> str:
    return picture(doc, fig, fig.get("display_width"))


def block(doc: Path, fig) -> str:
    gallery = relpath(doc, GALLERY) + "#" + anchor(fig)
    parts = ["**Figure %s.** %s" % (fig["id"], fig["caption"]), "", body(doc, fig), ""]
    parts += ["<details>", "<summary>Text description of Figure %s</summary>" % fig["id"], "", fig["description"], ""]
    if fig.get("table"):
        parts += [table_md(fig), ""]
    parts += ["[All figures and their descriptions](%s)" % gallery, "", "</details>", ""]
    return "\n".join(parts)


def title_of(path: Path) -> str:
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return path.name


def files_md(fig) -> str:
    def pair(images):
        return "[light](%s) · [dark](%s)" % (Path(images["light"]).name, Path(images["dark"]).name)
    out = pair(fig["images"])
    if fig.get("wide"):
        out += "; wide drawing: " + pair(fig["wide"])
    return out


def gallery_md(figures, banner) -> str:
    out = []
    if banner:
        out += ["### Repository banner", "", picture(GALLERY, banner), "", "**Alt text.** " + banner["alt"], "", "**Files:** %s." % files_md(banner), ""]
    for fig in figures:
        out += ["### %s %s" % (fig["id"], fig["title"]), "", picture(GALLERY, fig, fig.get("display_width")), ""]
        out += ["**Caption.** " + fig["caption"], "", "**Alt text.** " + fig["alt"], "", "**Description.** " + fig["description"], ""]
        if fig.get("table"):
            out += [table_md(fig), ""]
        used = ["[%s](%s)" % (title_of(REPO / p), relpath(GALLERY, REPO / p)) for p in fig["used_in"]]
        out += ["**Used in:** " + "; ".join(used) + ".", ""]
        out += ["**Files:** %s." % files_md(fig), ""]
    return "\n".join(out)


def sync(check: bool):
    figures, banner = load()
    by_id = {f["id"]: f for f in figures}
    problems, writes = [], {}
    for fig in figures:
        for rel in fig["used_in"]:
            doc = REPO / rel
            if not doc.exists():
                problems.append("%s: %s (named in figures.json) does not exist" % (fig["id"], rel))
                continue
            text = writes.get(doc) or doc.read_text(encoding="utf-8")
            found = [m for m in MARKER.finditer(text) if m.group(2) == fig["id"]]
            if len(found) != 1:
                problems.append("%s: %s needs exactly one marker pair for %s (found %d)" % (fig["id"], rel, fig["id"], len(found)))
                continue
            m = found[0]
            new_inner = "\n" + block(doc, fig)
            if m.group(3) != new_inner:
                problems.append("%s: the block in %s is out of date" % (fig["id"], rel))
            writes[doc] = text[:m.start(3)] + new_inner + text[m.end(3):]
    # markers for figures that figures.json does not know, or in documents it does not list
    for doc in sorted(REPO.rglob("*.md")):
        if any(part in (".git", "node_modules") for part in doc.parts):
            continue
        for m in MARKER.finditer(doc.read_text(encoding="utf-8")):
            fig = by_id.get(m.group(2))
            if fig is None:
                problems.append("%s has a marker for unknown figure %s" % (doc.relative_to(REPO).as_posix(), m.group(2)))
            elif doc.relative_to(REPO).as_posix() not in fig["used_in"]:
                problems.append("%s places %s but figures.json does not list it in used_in" % (doc.relative_to(REPO).as_posix(), m.group(2)))
    rtext = README.read_text(encoding="utf-8")
    rm = BANNER_MARKER.search(rtext)
    if rm is None:
        problems.append("README.md needs <!-- banner:start --> and <!-- banner:end --> markers around the banner")
    elif banner:
        inner = "\n" + picture(README, banner) + "\n"
        if rm.group(2) != inner:
            problems.append("the banner in README.md is out of date")
        writes[README] = rtext[:rm.start(2)] + inner + rtext[rm.end(2):]
    gtext = GALLERY.read_text(encoding="utf-8") if GALLERY.exists() else ""
    gm = GALLERY_MARKER.search(gtext)
    if gm is None:
        problems.append("figures/README.md needs <!-- gallery:start --> and <!-- gallery:end --> markers")
    else:
        inner = "\n" + gallery_md(figures, banner) + "\n"
        if gm.group(2) != inner:
            problems.append("the gallery in figures/README.md is out of date")
        writes[GALLERY] = gtext[:gm.start(2)] + inner + gtext[gm.end(2):]
    if not check:
        for doc, text in writes.items():
            if doc.read_text(encoding="utf-8") != text:
                doc.write_bytes(text.encode("utf-8"))
                print("updated " + doc.relative_to(REPO).as_posix())
        return [p for p in problems if "does not exist" in p or "marker" in p]
    return problems


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    problems = sync(args.check)
    for p in problems:
        print("FIGURE  " + p)
    if problems:
        print("\nRun python scripts/sync_figures.py to regenerate." if args.check else "")
        return 1
    print("Figure blocks, banner and gallery are in sync." if args.check else "Figure blocks, banner and gallery written.")
    return 0


if __name__ == "__main__":
    for _stream in (sys.stdout, sys.stderr):  # a legacy console code page must not break the output
        getattr(_stream, "reconfigure", lambda **_: None)(encoding="utf-8", errors="replace")
    sys.exit(main())
