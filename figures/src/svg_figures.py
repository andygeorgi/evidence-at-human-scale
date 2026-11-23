#!/usr/bin/env python3
"""Draw the figures that are laid out by hand rather than by Mermaid: F02, F04, F06 and the repository banner.

    python figures/src/svg_figures.py            # writes figures/F02-architecture-light.svg, ...-dark.svg and the banner
    python figures/src/svg_figures.py --check    # fails if the committed SVGs differ from what this script draws

No dependencies. The drawing is deterministic, so the committed files can be compared byte for byte. Every figure is
drawn twice, in a light and a dark palette, each on an opaque background so it stays legible on any page.
"""
from __future__ import annotations

import argparse
import sys
from html import escape
from pathlib import Path

OUT = Path(__file__).resolve().parents[1]

PALETTES = {
    "light": {
        "bg": "#ffffff", "text": "#1b1f24", "muted": "#57606a", "line": "#57606a", "band": "#f6f8fa", "band_stroke": "#d0d7de",
        "src": ("#E8F1FB", "#2F6DB5", "#0B2540"), "sel": ("#E4F4F6", "#1E7F8C", "#06323A"), "pkt": ("#E6F4EA", "#2E7D4F", "#0F2E1B"),
        "own": ("#EFE9F7", "#6A4BA1", "#24133F"), "warn": ("#FFF1D6", "#B26A00", "#3D2500"), "stop": ("#FBE4E4", "#B3261E", "#3D0A07"),
        "note": ("#F4F4F4", "#777777", "#222222"),
    },
    "dark": {
        "bg": "#0d1117", "text": "#e6edf3", "muted": "#9da7b3", "line": "#8b949e", "band": "#161b22", "band_stroke": "#30363d",
        "src": ("#12304F", "#58A6FF", "#CDE4FF"), "sel": ("#0F3A40", "#39C5CF", "#CFF6F9"), "pkt": ("#12361F", "#56D364", "#D2F8DB"),
        "own": ("#2D2150", "#A371F7", "#E6DAFF"), "warn": ("#4A3200", "#E3B341", "#FFEBC2"), "stop": ("#4D1511", "#F85149", "#FFD8D3"),
        "note": ("#21262D", "#8b949e", "#e6edf3"),
    },
}
FONT = "-apple-system, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif"


class Canvas:
    def __init__(self, width, height, theme, title, desc):
        self.w, self.h, self.p = width, height, PALETTES[theme]
        self.title, self.desc = title, desc
        self.parts = []

    def text(self, x, y, lines, size=15, bold=False, fill=None, anchor="middle", leading=None):
        leading = leading or size * 1.3
        for i, line in enumerate([lines] if isinstance(lines, str) else lines):
            self.parts.append('<text x="%.1f" y="%.1f" font-size="%s" text-anchor="%s"%s fill="%s">%s</text>' % (
                x, y + i * leading, size, anchor, ' font-weight="700"' if bold else "", fill or self.p["text"], escape(line)))

    def rect(self, x, y, w, h, kind, rx=8, stroke_w=1.6):
        fill, stroke, _ = self.p[kind]
        self.parts.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="%d" fill="%s" stroke="%s" stroke-width="%s"/>' % (x, y, w, h, rx, fill, stroke, stroke_w))

    def box(self, x, y, w, h, kind, title, sub=(), size=15, sub_size=12.5, gap=3):
        """A filled box with a bold title and smaller lines under it, centred vertically."""
        self.rect(x, y, w, h, kind)
        color = self.p[kind][2]
        titles = [title] if isinstance(title, str) else list(title)
        subs = [sub] if isinstance(sub, str) else list(sub)
        lead, slead = size * 1.25, sub_size * 1.32
        total = len(titles) * lead + ((len(subs) * slead + gap) if subs else 0)
        y0 = y + (h - total) / 2 + size * 0.92
        self.text(x + w / 2, y0, titles, size, True, color, leading=lead)
        if subs:
            self.text(x + w / 2, y0 + len(titles) * lead + gap, subs, sub_size, False, color, leading=slead)

    def band(self, x, y, w, h, label=None, label_y=22):
        self.parts.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="12" fill="%s" stroke="%s" stroke-width="1.2"/>' % (
            x, y, w, h, self.p["band"], self.p["band_stroke"]))
        if label:
            self.text(x + 14, y + label_y, label, 13, True, self.p["muted"], anchor="start")

    def path(self, points, dashed=False, head=True):
        d = "M" + " L".join("%.1f %.1f" % p for p in points)
        self.parts.append('<path d="%s" fill="none" stroke="%s" stroke-width="1.8"%s%s/>' % (
            d, self.p["line"], ' stroke-dasharray="5 4"' if dashed else "", ' marker-end="url(#arr)"' if head else ""))

    def badge(self, cx, cy, n, kind):
        stroke = self.p[kind][1]
        self.parts.append('<circle cx="%.1f" cy="%.1f" r="12" fill="%s" stroke="%s" stroke-width="1.6"/>' % (cx, cy, stroke, stroke))
        self.parts.append('<text x="%.1f" y="%.1f" font-size="13" font-weight="700" text-anchor="middle" fill="%s">%d</text>' % (cx, cy + 4.5, self.p["bg"], n))

    def svg(self):
        head = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d" width="%d" height="%d" role="img" aria-labelledby="t d" font-family="%s">\n'
                '<title id="t">%s</title>\n<desc id="d">%s</desc>\n'
                '<defs><marker id="arr" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse">'
                '<path d="M0 0 L10 5 L0 10 z" fill="%s"/></marker></defs>\n<rect width="%d" height="%d" fill="%s"/>\n') % (
            self.w, self.h, self.w, self.h, FONT, escape(self.title), escape(self.desc), self.p["line"], self.w, self.h, self.p["bg"])
        return head + "\n".join(self.parts) + "\n</svg>\n"


# ------------------------------------------------------------------------------------------------------------------ F02
def f02(theme):
    c = Canvas(1000, 738, theme, "Reference architecture: a main path of nine steps and two separate paths",
               "The main path runs from sources through admission, a registry of immutable versions, authorized retrieval, relevance and coverage, a selection "
               "manifest, bounded synthesis and release validation to review of one decision packet by the Decision Owner. A separate mandatory continuity path "
               "runs from the registry through deterministic detection and an authorized notification queue to acknowledgement or escalation. A separate action "
               "path runs from an exact approved proposal or bounded grant through an executor with current checks to an authoritative target and a verified "
               "receipt. Corrections, revocations, late evidence and challenges return to reassessment and invalidation. A control plane constrains every stage.")
    steps = [
        ("src", "Sources", "records, events, services, analytics"),
        ("src", "Admission", "registered producer, permitted kind"),
        ("src", "Registry (C02)", "admitted immutable versions"),
        ("sel", "Authorized retrieval (C01)", "candidate evidence and coverage"),
        ("sel", "Relevance and coverage", "priority, grouping, exclusions"),
        ("sel", "Selection manifest (C03)", "retrieved, kept, excluded, missing"),
        ("pkt", "Bounded synthesis", "candidate decision packet"),
        ("pkt", "Release validation", "claim, reference, disclosure checks"),
        ("own", "Review of the packet (C04)", "the Decision Owner inspects and challenges"),
    ]
    mx, mw, top, step_h, gap = 24, 330, 52, 54, 14
    bx, bw = mx + 22, mw - 22
    c.band(10, 10, 360, 656, "MAIN PATH: nine steps to one review contract")
    ys = []
    for i, (kind, title, sub) in enumerate(steps):
        y = top + i * (step_h + gap)
        ys.append(y)
        c.box(bx, y, bw, step_h, kind, title, sub)
        c.badge(mx + 11, y + step_h / 2, i + 1, kind)
        if i:
            c.path([(bx + bw / 2, ys[i - 1] + step_h), (bx + bw / 2, y)])
    # mandatory continuity path, level with the registry (step 3)
    reg_y = ys[2]
    c.band(392, reg_y - 42, 598, 112, "MANDATORY CONTINUITY PATH: no LLM dependency")
    cw, cgap = 178, 22
    cx = [406 + i * (cw + cgap) for i in range(3)]
    for x, (title, sub) in zip(cx, [(["Deterministic", "detection"], []), (["Authorized notification", "and queue"], []), (["Acknowledgement", "or escalation"], ["receipt, not resolution"])]):
        c.box(x, reg_y - 12, cw, 74, "src", title, sub, size=14, sub_size=12)
    for i in range(2):
        c.path([(cx[i] + cw, reg_y + 25), (cx[i + 1], reg_y + 25)])
    c.path([(bx + bw, reg_y + 20), (406, reg_y + 20)])
    # reassessment and invalidation, between the paths
    fy = ys[4] - 8
    c.box(392, fy, 598, 92, "warn", "Reassessment and invalidation",
          ["corrections, revocations, late evidence and challenges return here;", "affected derivatives, packets and pending approvals stop being current"], size=15, sub_size=12.5)
    c.path([(392, fy + 46), (374, fy + 46), (374, reg_y + 44), (bx + bw, reg_y + 44)], dashed=True)
    # action path, level with step 9
    ay = ys[8]
    c.band(392, ay - 58, 598, 126, "ACTION PATH")
    aw, agap = 128, 14
    ax = [420 + i * (aw + agap) for i in range(4)]
    acts = [("own", ["Exact approved", "proposal (C05) or"], ["bounded grant (C06)"]), ("warn", ["Executor:", "current checks"], ["permission, limits"]),
            ("src", ["Authoritative", "target"], []), ("pkt", ["Verified", "receipt (C07)"], [])]
    for x, (kind, title, sub) in zip(ax, acts):
        c.box(x, ay - 30, aw, 82, kind, title, sub, size=13.5, sub_size=12, gap=1)
    mid = ay - 30 + 41
    for i in range(3):
        c.path([(ax[i] + aw, mid), (ax[i + 1], mid)])
    c.path([(bx + bw, ay + step_h / 2), (ax[0] - 2, ay + step_h / 2)])
    c.text((bx + bw + ax[0]) / 2, ay + step_h / 2 - 8, "proposes", 12, False, c.p["muted"])
    c.path([(ax[3] + aw / 2, ay - 58), (ax[3] + aw / 2, fy + 92)], dashed=True)
    c.text(ax[3] + aw / 2 + 10, (ay - 58 + fy + 92) / 2 + 4, "outcome", 12, False, c.p["muted"], anchor="start")
    # control plane
    c.band(10, 684, 980, 44)
    c.text(500, 711, "CONTROL PLANE constrains every stage and path: identity · authorization · purpose · domain policy · inventory · freshness · budgets · delegation", 12.5, True, c.p["muted"])
    return c


# ------------------------------------------------------------------------------------------------------------------ F04
def f04(theme):
    c = Canvas(1000, 690, theme, "Anatomy of a decision packet",
               "The Decision Owner reviews one decision packet bound to an exact context, selection and as-of time. Its supported claims, labelled inferences and "
               "conflicts point to exact evidence records. Its coverage, omissions and obligations come from the selection manifest. Its action proposals are "
               "proposed, not executed, and point to action proposal records.")
    c.box(16, 290, 150, 80, "own", "Decision Owner", ["reviews,", "challenges, decides"], size=15, sub_size=12.5)
    c.path([(166, 330), (206, 330)])
    c.band(206, 12, 454, 666, "DECISION PACKET (C04) · one context, selection, as-of (G01)")
    rows = [
        ("pkt", "G02 Supported claims", "each cites an exact record version"),
        ("warn", "G03 Labelled inferences", "method and limits; never claims"),
        ("pkt", "G04 Recommendations", "with the accountable review requirement"),
        ("stop", "G05 Conflicts and uncertainty", "visible, never settled by majority"),
        ("stop", "G06 Coverage, omissions, gaps", "seven missingness labels"),
        ("pkt", "G07 Obligations", "priority and mandatory items"),
        ("own", "G08 Action proposals", "proposed, not executed"),
        ("pkt", "G09 Review and version history", "revised versions stay distinguishable"),
    ]
    rh, rg, ry = 66, 12, 46
    mids = []
    for i, (kind, title, sub) in enumerate(rows):
        y = ry + i * (rh + rg)
        c.box(222, y, 422, rh, kind, title, sub)
        mids.append(y + rh / 2)
    c.box(704, ry, 280, 3 * (rh + rg) + rh, "src", "Evidence records (C02)", ["exact version, claim or payload", "pointer, original locator, scope,", "method, lifecycle"])
    c.box(704, ry + 4 * (rh + rg), 280, 2 * rh + rg, "sel", "Selection manifest (C03)", ["what was retrieved, kept,", "excluded and missing"])
    c.box(704, ry + 6 * (rh + rg), 280, rh, "own", "Action proposals (C05)", ["evidence, preconditions, accounting"])
    for i in (0, 1, 3, 4, 5, 6):
        c.path([(644, mids[i]), (704, mids[i])])
    return c


# ------------------------------------------------------------------------------------------------------------------ F06
def f06(theme):
    c = Canvas(1000, 540, theme, "Receipt states and recovery",
               "An action starts as submitted after the gateway passes every check and reserves allowance. It becomes completed and verified when an authoritative "
               "outcome confirms the effect, or not executed and verified when an authoritative check confirms no business effect. With a timeout or no response it "
               "is unknown, and when only some effects are verified it is partial. While unknown or partial, allowance stays reserved or charged, there is no blind "
               "retry, and a timeout or lease expiry never restores allowance. Unknown becomes completed or not executed only through authoritative reconciliation. "
               "Partial becomes completed through reconciliation or compensation under policy.")
    c.box(380, 14, 240, 64, "src", "submitted", ["every check passed,", "allowance reserved"], size=17, sub_size=12.5)
    bus, top, bh = 122, 168, 132
    c.path([(500, 78), (500, bus)], head=False)
    c.path([(134, bus), (866, bus)], head=False)
    xs = [(24, 220), (264, 220), (516, 220), (756, 220)]
    kinds = ["warn", "warn", "pkt", "pkt"]
    titles = ["unknown", "partial", "completed_verified", "not_executed_verified"]
    subs = [["timeout or no response.", "Leaves only by", "authoritative reconciliation"],
            ["some effects verified,", "others not; known effects", "stay charged. Leaves by", "reconciliation or compensation"],
            ["authoritative outcome", "confirms the effect"],
            ["authoritatively verified:", "no business effect"]]
    for (x, w), kind, title, sub in zip(xs, kinds, titles, subs):
        c.box(x, top, w, bh, kind, title, sub, size=16 if len(title) < 12 else 14.5, sub_size=12.5)
        c.path([(x + w / 2, bus), (x + w / 2, top)])
    # partial to completed: adjacent
    c.path([(264 + 220, top + bh / 2), (516, top + bh / 2)])
    # unknown to completed and to not executed: nested arcs underneath the row
    base = top + bh
    a, b = 380 - 230, 0
    c.path([(150, base), (150, base + 38), (626, base + 38), (626, base)])
    c.path([(98, base), (98, base + 76), (866, base + 76), (866, base)])
    c.text(388, base + 58, "authoritative reconciliation", 12.5, False, c.p["muted"])
    c.text(482, base + 96, "authoritative reconciliation", 12.5, False, c.p["muted"])
    c.text(500, 478, "Amber: unresolved. Allowance stays reserved or charged, there is no blind retry,", 13.5, True, c.p["text"])
    c.text(500, 498, "and a timeout or lease expiry never restores allowance. Green: verified and terminal.", 13.5, True, c.p["text"])
    c.text(500, 522, "Allowance is restored only on authoritative reconciliation, never by assuming that silence means no effect.", 12.5, False, c.p["muted"])
    return c


# ------------------------------------------------------------------------------------------------------------------ banner
def banner(theme):
    c = Canvas(1280, 420, theme, "Evidence at Human Scale: systems produce evidence, AI makes it consumable, people remain accountable",
               "A banner in three parts. Systems produce evidence: typed records with versions and lineage. AI makes it consumable: a decision packet that "
               "separates claims from labelled inferences and shows conflicts, gaps and unexecuted proposals. People remain accountable: a person approves "
               "an exact proposal or holds it. Evidence is not inference, not recommendation, and not authority.")
    p = c.p
    c.text(640, 50, "Evidence at Human Scale", 36, True, p["text"])
    c.text(640, 82, "Reference architecture for accountable decisions in agentic systems", 18, False, p["muted"])
    for x, kind, head in [(40, "src", "Systems produce evidence"), (460, "pkt", "AI makes it consumable"), (880, "own", "People remain accountable")]:
        c.rect(x, 112, 360, 238, kind, rx=14, stroke_w=2)
        c.text(x + 180, 146, head, 21, True, p[kind][2])
    for i, (a, b, k) in enumerate([("S01/v1", "source record", "src"), ("F01/v1", "deterministic finding", "sel"), ("M01/v1", "model inference", "warn")]):
        y = 166 + i * 52
        c.rect(70, y, 300, 44, k, rx=8)
        c.text(86, y + 28, a, 16, True, p[k][2], anchor="start")
        c.text(170, y + 28, b, 15, False, p[k][2], anchor="start")
    c.text(220, 334, "typed · versioned · with lineage", 13, False, p["muted"])
    c.rect(490, 166, 300, 168, "note", rx=8)
    for i, (a, b, k) in enumerate([("Claims", "each cites its evidence", "pkt"), ("Inferences", "labelled, never claims", "warn"), ("Conflicts · gaps", "stay visible", "stop"), ("Proposals", "not executed", "own")]):
        y = 176 + i * 38
        c.rect(500, y, 280, 30, k, rx=6, stroke_w=1.2)
        c.text(510, y + 20, a, 14, True, p[k][2], anchor="start")
        c.text(770, y + 20, b, 12.5, False, p[k][2], anchor="end")
    cx = 1060
    c.parts.append('<circle cx="%d" cy="186" r="15" fill="%s" stroke="%s" stroke-width="2"/>' % (cx, p["own"][0], p["own"][1]))
    c.parts.append('<path d="M%d 232 q0 -30 30 -30 q30 0 30 30 z" fill="%s" stroke="%s" stroke-width="2"/>' % (cx - 30, p["own"][0], p["own"][1]))
    c.rect(910, 252, 140, 44, "pkt", rx=22)
    c.text(980, 280, "Approve exactly", 14.5, True, p["pkt"][2])
    c.rect(1070, 252, 140, 44, "warn", rx=22)
    c.text(1140, 280, "Hold", 14.5, True, p["warn"][2])
    c.text(1060, 326, "one exact proposal, current checks at commit", 13, False, p["muted"])
    c.path([(400, 232), (458, 232)])
    c.path([(820, 232), (878, 232)])
    c.rect(40, 366, 1200, 40, "note", rx=10, stroke_w=1.2)
    c.text(640, 393, "evidence  ≠  inference  ≠  recommendation  ≠  authority", 18, True, p["text"])
    return c


FIGURES = {"F02": f02, "F04": f04, "F06": f06, "banner": banner}


def render_all():
    out = {}
    for key, fn in FIGURES.items():
        for theme in ("light", "dark"):
            out["%s-%s.svg" % (key, theme)] = fn(theme).svg()
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--check", action="store_true", help="fail if the committed SVGs differ from a fresh drawing")
    args = parser.parse_args(argv)
    files = render_all()
    if args.check:
        bad = [n for n, text in files.items() if not (OUT / n).exists() or (OUT / n).read_bytes() != text.encode("utf-8")]
        if bad:
            print("Out of date: " + ", ".join(bad) + ". Run python figures/src/svg_figures.py")
            return 1
        print("%d hand-drawn SVGs match their source." % len(files))
        return 0
    for name, text in files.items():
        (OUT / name).write_bytes(text.encode("utf-8"))
        print("wrote figures/" + name)
    return 0


if __name__ == "__main__":
    sys.exit(main())
