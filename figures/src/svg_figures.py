#!/usr/bin/env python3
"""Draw every figure in the text, and the repository banner, as SVG.

    python figures/src/svg_figures.py            # writes figures/F01-light.svg, F01-dark.svg, ... and the banner
    python figures/src/svg_figures.py --check    # fails if the committed SVGs differ from what this script draws

No dependencies. The drawing is deterministic, so the committed files can be compared byte for byte. Each figure is drawn
twice, in a light and a dark palette, on an opaque background so it stays legible on any page. A figure is drawn 360 px wide
so that a phone shows it at its natural size; F02 and the banner also have a wide drawing (880 px) that a desktop window
shows instead. The title and the description inside each file come from figures/figures.json, so they cannot drift from the
alt text. The drawing helpers are in kit.py.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from kit import Fig, text_w, wrap  # noqa: E402

OUT = Path(__file__).resolve().parents[1]
THEMES = ("light", "dark")
WIDE = 880  # the wide drawings, for a window of at least 900 px


# ------------------------------------------------------------------------------------------------------------------ helpers
def row(c, specs, gap=10, x=None, w=None):
    """Cards side by side at the flow cursor, sharing one height. A spec is a dict: kind, head, body, weight, and any card option."""
    x0 = c.m if x is None else x
    total = c.inner if w is None else w
    weights = [s.get("weight", 1) for s in specs]
    widths = [(total - gap * (len(specs) - 1)) * wt / sum(weights) for wt in weights]
    opts = [{k: v for k, v in s.items() if k in ("size", "pad", "align", "badge", "tag", "dash")} for s in specs]
    heights = [c.card(s["kind"], s.get("head"), s.get("body", ()), x=0, w=wd, y=0, dry=True, **o) for s, wd, o in zip(specs, widths, opts)]
    h = max(heights + [s.get("min_h", 0) for s in specs])
    boxes, cx = [], x0
    for s, wd, o in zip(specs, widths, opts):
        boxes.append(c.card(s["kind"], s.get("head"), s.get("body", ()), x=cx, w=wd, y=c.y, min_h=h, **o))
        cx += wd + gap
    c.y += h
    return boxes


def header(c, x, w, title, sub_line=None):
    """The label at the top of a band: a bold line, and a lighter line under it. Moves the flow cursor below both."""
    c.y += 12
    c.y += c.para(x, c.y, w, title, 13, True, c.p["muted"])
    if sub_line:
        c.y += 2
        c.y += c.para(x, c.y, w, sub_line, 13, False, c.p["muted"])
    c.y += 8


def sub(*lines):
    """Small body lines for a card."""
    return [(line, "small") for line in lines]


def label(c, x, y, s, anchor="start", bold=False):
    """A short free label in the muted color."""
    c.text(x, y, s, 13, bold, c.p["muted"], anchor, maxw=text_w(s, 13, bold) + 1)


def fit(s, maxw, size, bold=True, least=14):
    """The largest font size, not above `size`, at which `s` fits in `maxw`."""
    while size > least and text_w(s, size, bold) > maxw:
        size -= 0.5
    return size


# ------------------------------------------------------------------------------------------------------------------ F01
def f01(c):
    c.card("src", "Information production keeps growing", "records · events · deterministic findings\nanalytical results · model interpretations", align="middle")
    c.down(48, label="authorize · select · label")
    c.card("sel", "Decision context", "keeps what could change a decision and shows its source, scope, gaps and owner", x=36, w=288, align="middle")
    c.down(48, label="one decision packet")
    c.card("own", "Decision Owner", "finite attention · accountable", x=72, w=216, align="middle")


# ------------------------------------------------------------------------------------------------------------------ F02
STEPS = [
    ("src", "Sources", "records, events, services, analytics"),
    ("src", "Admission", "registered producer, permitted kind"),
    ("src", "Registry (C02)", "admitted immutable versions"),
    ("sel", "Authorized retrieval (context C01)", "candidate evidence and coverage"),
    ("sel", "Relevance and coverage", "priority, grouping, exclusions"),
    ("sel", "Selection manifest (C03)", "retrieved, kept, excluded, missing"),
    ("pkt", "Bounded synthesis", "candidate decision packet"),
    ("pkt", "Release validation", "claim, reference, disclosure checks"),
    ("own", "Review of the packet (C04)", "the Decision Owner inspects and challenges"),
]
MANDATORY = [("Deterministic detection", None), ("Authorized notification and queue", None), ("Acknowledgement or escalation", "receipt, not resolution")]
ACTION = [("own", "Approval or grant (C06)", "an exact approval of one proposal (C05), or a bounded grant"),
          ("warn", "Executor (action gateway)", "rechecks at commit: grant, evidence, preconditions, limits"),
          ("src", "Authoritative target", None), ("pkt", "Verified receipt (C07)", None)]
REASSESS = ("Corrections, revocations, late evidence, challenges and verified outcomes arrive here. This step returns to the registry (step 3): "
            "affected derivatives, packets and pending approvals stop being current.")
CONTROL = ["identity · authorization · purpose", "domain policy · inventory · freshness", "budgets · delegation"]


def f02(c):
    mx, rail, cx = c.m, c.m + 22, c.m + 42
    cw = c.w - c.m - 10 - cx
    tok = c.band_start()
    header(c, mx + 14, c.inner - 28, "MAIN PATH", "nine steps to one review contract")
    prev = None
    for i, (kind, title, text) in enumerate(STEPS):
        box = c.card(kind, title, sub(text), x=cx, w=cw, gap=0 if i == len(STEPS) - 1 else 10)
        cy = box.y + 21
        c.badge(rail, cy, i + 1, kind)
        if prev is not None:
            c.path([(rail, prev + 13), (rail, cy - 13)])
        prev = cy
    c.band_end(tok)
    c.y += 16
    tok = c.band_start()
    header(c, mx + 14, c.inner - 28, "MANDATORY CONTINUITY PATH", "branches from step 3 · no LLM dependency")
    for i, (title, text) in enumerate(MANDATORY):
        c.card("src", title, sub(text) if text else (), x=mx + 12, w=c.inner - 24)
        if i < len(MANDATORY) - 1:
            c.down(16)
    c.y += 2
    c.band_end(tok, pad=0)
    c.y += 16
    tok = c.band_start()
    header(c, mx + 14, c.inner - 28, "ACTION PATH", "starts at step 9, the review")
    for i, (kind, title, text) in enumerate(ACTION):
        c.card(kind, title, sub(text) if text else (), x=mx + 12, w=c.inner - 24)
        if i < len(ACTION) - 1:
            c.down(16)
    c.y += 2
    c.band_end(tok, pad=0)
    c.down(30, dashed=True, label="outcome")
    c.card("warn", "Reassessment and invalidation", sub(REASSESS), dash=True)
    c.y += 16
    tok = c.band_start()
    header(c, mx + 14, c.inner - 28, "CONTROL PLANE", "constrains every stage and path")
    for line in CONTROL:
        c.y += c.para(mx + 14, c.y, c.inner - 28, line, 14, False, c.p["text"])
    c.y += 2
    c.band_end(tok, pad=4)


def f02_wide(c):
    lw, gutter = 280, 24
    mx, rail, cx = c.m, c.m + 22, c.m + 40
    cw = lw - 40 - 10
    rx = mx + lw + gutter
    rw = c.w - c.m - rx
    tok = c.band_start()
    header(c, mx + 14, lw - 28, "MAIN PATH", "nine steps to one review contract")
    boxes, prev = [], None
    for i, (kind, title, text) in enumerate(STEPS):
        box = c.card(kind, title, sub(text), x=cx, w=cw, gap=0 if i == len(STEPS) - 1 else 10)
        boxes.append(box)
        cy = box.y + 21
        c.badge(rail, cy, i + 1, kind)
        if prev is not None:
            c.path([(rail, prev + 13), (rail, cy - 13)])
        prev = cy
    main = c.band_end(tok, x=mx, w=lw)
    # a key for the colors and the lines, in the free space beside the first steps
    key_h = 118
    c.band(rx, c.m, rw, key_h)
    c.text(rx + 14, c.m + 22, "KEY", 13, True, c.p["muted"], maxw=60)
    kx, ky = rx + 14, c.m + 34
    for kind, name in (("src", "evidence and systems"), ("sel", "context and selection"), ("pkt", "packet and receipt"), ("own", "owner and authority"), ("warn", "checks and reassessment")):
        w = text_w(name, 13, True) + 18
        if kx + w > rx + rw - 14:
            kx, ky = rx + 14, ky + 30
        c.chip(kx, ky, w, name, kind)
        kx += w + 8
    c.path([(rx + 14, c.m + key_h - 14), (rx + 54, c.m + key_h - 14)], small=True)
    c.text(rx + 62, c.m + key_h - 9.4, "flow", 13, False, c.p["muted"], maxw=50)
    c.path([(rx + 120, c.m + key_h - 14), (rx + 160, c.m + key_h - 14)], dashed=True, small=True)
    c.text(rx + 168, c.m + key_h - 9.4, "return or outcome", 13, False, c.p["muted"], maxw=140)
    # the mandatory continuity path, level with the registry (step 3)
    reg = boxes[2]
    mw = (rw - 24 - 2 * 18) / 3
    mand_h = max(c.card("src", t, sub(s) if s else (), w=mw, x=0, y=0, dry=True, pad=6, size=14) for t, s in MANDATORY)
    mand_top = reg.y - 50
    c.band(rx, mand_top, rw, 50 + mand_h + 12)
    c.text(rx + 14, mand_top + 22, "MANDATORY CONTINUITY PATH", 13, True, c.p["muted"], maxw=rw - 28)
    c.text(rx + 14, mand_top + 40, "branches from step 3, the registry; no LLM dependency", 13, False, c.p["muted"], maxw=rw - 28)
    mids = [c.card("src", t, sub(s) if s else (), x=rx + 12 + i * (mw + 18), w=mw, y=reg.y, pad=6, size=14, min_h=mand_h) for i, (t, s) in enumerate(MANDATORY)]
    for a, b in zip(mids, mids[1:]):
        c.path([(a.right, a.cy), (b.x, b.cy)], small=True)
    c.path([(reg.right, reg.y + 24), (mids[0].x, reg.y + 24)])
    mand_bottom = mand_top + 50 + mand_h + 12
    # the action path, level with the review (step 9)
    aw = (rw - 24 - 3 * 18) / 4
    act_h = max(c.card(k, t, sub(s) if s else (), w=aw, x=0, y=0, dry=True, pad=6, size=14) for k, t, s in ACTION)
    act_top = main.bottom - 50 - act_h - 12
    c.band(rx, act_top, rw, 50 + act_h + 12)
    c.text(rx + 14, act_top + 22, "ACTION PATH", 13, True, c.p["muted"], maxw=rw - 28)
    c.text(rx + 14, act_top + 40, "starts at step 9, the review; a separate path", 13, False, c.p["muted"], maxw=rw - 28)
    acts = [c.card(k, t, sub(s) if s else (), x=rx + 12 + i * (aw + 18), w=aw, y=act_top + 50, pad=6, size=14, min_h=act_h) for i, (k, t, s) in enumerate(ACTION)]
    for a, b in zip(acts, acts[1:]):
        c.path([(a.right, a.cy), (b.x, b.cy)], small=True)
    c.path([(boxes[-1].right, boxes[-1].y + 24), (acts[0].x, boxes[-1].y + 24)])
    # reassessment, between the two paths: it receives the outcome and returns to the registry
    r_h = c.card("warn", "Reassessment and invalidation", sub(REASSESS), w=rw, x=0, y=0, dry=True)
    reas = c.card("warn", "Reassessment and invalidation", sub(REASSESS), x=rx, w=rw, y=(mand_bottom + act_top) / 2 - r_h / 2, dash=True)
    c.path([(acts[-1].cx, act_top), (acts[-1].cx, reas.bottom)], dashed=True)
    label(c, acts[-1].cx + 10, (reas.bottom + act_top) / 2 + 4.6, "outcome")
    back = mx + lw + gutter / 2
    c.path([(reas.x, reas.cy), (back, reas.cy), (back, reg.bottom - 14), (reg.right, reg.bottom - 14)], dashed=True)
    c.y = main.bottom + 16
    tok = c.band_start()
    c.y += 12
    c.text(mx + 14, c.y + 12.4, "CONTROL PLANE", 13, True, c.p["muted"], maxw=text_w("CONTROL PLANE", 13, True) + 1)
    c.text(mx + 14 + text_w("CONTROL PLANE", 13, True) + 8, c.y + 12.4, "constrains every stage and path", 13, False, c.p["muted"], maxw=300)
    c.y += 19
    c.y += c.para(mx + 14, c.y, c.inner - 28, " · ".join(CONTROL), 14, False, c.p["text"]) + 4
    c.band_end(tok, pad=4)


# ------------------------------------------------------------------------------------------------------------------ F03
def rel_row(c, kind, head, text, arrows, lw=112, tx=220, size=None):
    """One typed relationship: a record on the left, a dotted arrow for each assertion it makes, and what each one is about."""
    pitch = 50
    y = c.y
    h = max(c.card(kind, head, sub(*text), w=lw, x=0, y=0, dry=True, size=size), len(arrows) * pitch)
    left = c.card(kind, head, sub(*text), x=c.m + 12, w=lw, y=y, min_h=h, size=size)
    for i, (verb, target, tkind) in enumerate(arrows):
        ay = y + (h - len(arrows) * pitch) / 2 + i * pitch + 28
        c.path([(left.right + 2, ay), (tx - 4, ay)], dashed=True)
        c.text((left.right + tx) / 2, ay - 12, verb, 13, False, c.p["muted"], "middle", maxw=tx - left.right - 8)
        c.chip(tx, ay - 15, c.w - c.m - 12 - tx, target, tkind)
    c.y = y + h


def f03(c):
    mx, iw = c.m, c.inner
    tok = c.band_start()
    c.y += 14
    c.path([(mx + 14, c.y), (mx + 46, c.y)])
    c.text(mx + 54, c.y + 4.6, "Derivation: solid arrows", 13, True, c.p["muted"], maxw=iw - 70)
    c.y += 20
    c.card("src", "Goods receipt", sub("source record"), x=mx + 90, w=iw - 180, align="middle")
    c.down(20)
    cluster = c.band_start()
    c.y += 8
    c.text(mx + 22, c.y + 11, "One origin: both rest on the receipt", 13, True, c.p["muted"], maxw=iw - 44)
    c.y += 20
    row(c, [dict(kind="warn", head="AI summary A", body=sub("model inference")), dict(kind="warn", head="AI summary B", body=sub("model inference"))],
        gap=10, x=mx + 20, w=iw - 40)
    c.y += 8
    c.text(mx + iw / 2, c.y + 12, "They agree, but from one origin:", 13, False, c.p["muted"], "middle", maxw=iw - 40)
    c.text(mx + iw / 2, c.y + 30, "not independent corroboration", 13, True, c.p["text"], "middle", maxw=iw - 40)
    c.y += 40
    c.band_end(cluster, x=mx + 10, w=iw - 20, pad=0, dash=True)
    sx, sw, gap = mx + 12, 124, 22
    px = sx + sw + gap
    pw = c.w - mx - 12 - px
    c.path([(px + pw / 2, c.y), (px + pw / 2, c.y + 26)])
    c.y += 26
    s02, pkt = row(c, [dict(kind="stop", head="Invoice", body=sub("source record", "conflicting assertion"), weight=sw),
                       dict(kind="pkt", head="Decision packet", body=sub("the conflict stays visible"), weight=pw)], gap=gap, x=sx, w=sw + gap + pw)
    c.path([(s02.right, s02.cy), (pkt.x, pkt.cy)])
    c.y += 10
    c.band_end(tok, pad=0)
    c.y += 16
    tok = c.band_start()
    c.y += 14
    c.path([(mx + 14, c.y), (mx + 46, c.y)], dashed=True)
    c.text(mx + 54, c.y + 4.6, "Typed relationships: dashed arrows", 13, True, c.p["muted"], maxw=iw - 70)
    c.y += 16
    c.y += c.para(mx + 14, c.y, iw - 28, "Each is an assertion about another record, not ancestry.", 13, False, c.p["muted"]) + 8
    rel_row(c, "stop", "Invoice", ("source record",), [("contradicts", "Receipt v1", "src")], lw=100, tx=214, size=14)
    c.y += 10
    rel_row(c, "src", "Corrected receipt", ("version 2",), [("supersedes", "Receipt v1", "src"), ("invalidates", "AI summaries", "warn")], lw=100, tx=214, size=14)
    c.y += 10
    rel_row(c, "note", "Scoped validation", ("of this record only",), [("validates", "Receipt v1", "src")], lw=100, tx=214, size=14)
    c.y += 2
    c.band_end(tok, pad=8)


# ------------------------------------------------------------------------------------------------------------------ F04
PACKET = [
    ("pkt", "Context and as-of time", "one context, selection and as-of time; everything below is bound to them", None),
    ("pkt", "Supported claims", "each cites an exact record version", ("evidence", "src")),
    ("warn", "Labeled inferences", "method and limits; never claims", ("evidence", "src")),
    ("pkt", "Recommendations", "with the accountable review requirement", None),
    ("stop", "Conflicts and uncertainty", "visible, never settled by majority", ("evidence", "src")),
    ("warn", "Coverage, omissions, gaps", "seven missingness labels", ("selection", "sel")),
    ("pkt", "Obligations", "priority and mandatory items", ("selection", "sel")),
    ("own", "Action proposals", "proposed, not executed", ("proposal", "own")),
    ("pkt", "Review and version history", "revised versions stay distinguishable", None),
]


def f04(c):
    c.card("own", "Decision Owner", sub("reviews, challenges, decides"), x=c.m + 70, w=c.inner - 140, align="middle")
    c.down(24)
    tok = c.band_start()
    header(c, c.m + 14, c.inner - 28, "DECISION PACKET (C04)", "nine groups; a tag names what a group points to")
    for i, (kind, head, text, tag) in enumerate(PACKET):
        c.card(kind, head, sub(text), x=c.m + 12, w=c.inner - 24, tag=tag, gap=0 if i == len(PACKET) - 1 else 8)
    c.band_end(tok)
    c.down(28, label="tags point to")
    tok = c.band_start()
    header(c, c.m + 14, c.inner - 28, "WHAT THE TAGS POINT TO")
    c.card("src", "Evidence record (C02)", sub("by exact version, claim or payload pointer, original locator, scope, method, lifecycle"), x=c.m + 12, w=c.inner - 24, gap=8)
    c.card("sel", "Selection manifest (C03)", sub("what was retrieved, kept, excluded and missing"), x=c.m + 12, w=c.inner - 24, gap=8)
    c.card("own", "Action proposal (C05)", sub("records with evidence, preconditions, accounting"), x=c.m + 12, w=c.inner - 24)
    c.band_end(tok)


# ------------------------------------------------------------------------------------------------------------------ F05
RECHECK = ["The grant is current and not revoked", "The evidence is current and fresh", "The preconditions hold",
           "The parameters and target match", "The per-action limit holds", "The cumulative limit holds, counting consumed and reserved capacity"]


def fork(c, left_w, gap=10, h=22):
    """Two short arrows leaving the flow cursor, one above each column."""
    right_w = c.inner - left_w - gap
    c.path([(c.m + left_w / 2, c.y), (c.m + left_w / 2, c.y + h)])
    c.path([(c.m + left_w + gap + right_w / 2, c.y), (c.m + left_w + gap + right_w / 2, c.y + h)])
    c.y += h + 2


def f05(c):
    c.card("own", "The packet lists the proposal", sub("proposed, not executed"))
    stem = c.y
    c.y += 24
    boxes = row(c, [dict(kind="own", head="Exact approval (C06)", body=sub("of this proposal version, by the approver, a role distinct from the requestor")),
                    dict(kind="own", head="Bounded grant (C06)", body=sub("a grant for a class of actions already covers the proposal"))], gap=34)
    c.path([(c.w / 2, stem), (c.w / 2, stem + 12)], head=False)
    for b in boxes:
        c.path([(c.w / 2, stem + 12), (b.cx, stem + 12), (b.cx, b.y - 1)])
    label(c, c.w / 2, boxes[0].cy + 4.6, "or", anchor="middle", bold=True)
    c.y += 22
    c.divider(c.y + 14, "Approval is not commit", "warn")
    c.y += 44
    tok = c.band_start()
    header(c, c.m + 14, c.inner - 28, "RECHECK AT COMMIT", "the executor, or action gateway, checks the current state")
    for text in RECHECK:
        h = c.para(c.m + 38, c.y, c.inner - 52, text, 14)
        c.check(c.m + 16, c.y + 2)
        c.y += max(h, 17) + 8
    c.band_end(tok, pad=0)
    c.y += 14
    left_w = 190
    fork(c, left_w)
    row(c, [dict(kind="pkt", head="Every check passes", body=sub("Reserve allowance. Submit the exact action to the target. Record the outcome, or a timeout."), weight=left_w),
            dict(kind="stop", head="A check fails", body=sub("Rejected before submission. Nothing is submitted."), weight=c.inner - left_w - 10)])
    fork(c, left_w)
    c.card("pkt", "Receipt (C07)", ["After a pass: the outcome, as completed_verified, unknown, partial or not_executed_verified.", "After a failed check: the rejection and its reasons. A rejection alone is not a verified no-effect."], gap=0)
    c.down(24)
    c.card("src", "Authoritative verification", sub("against the target, for this attempt, target and scope: confirms or reconciles the outcome, or confirms that there was no effect"))


# ------------------------------------------------------------------------------------------------------------------ F06
def f06(c):
    bus, cx = c.m + 6, c.m + 24
    cw = c.w - c.m - cx
    submitted = c.card("src", "submitted", sub("every check passed, allowance reserved"), x=cx, w=cw, gap=28)
    arrows = []

    def unresolved(head, text, lead, targets):
        body, tag = sub(text, lead), ("open", "warn")
        text_h = c.card("warn", head, body, x=cx, w=cw, y=0, dry=True, size=16, tag=tag)
        box = c.card("warn", head, body, x=cx, w=cw, y=c.y, min_h=text_h + 30 * len(targets) + 2, size=16, tag=tag)
        y = box.y + text_h - 4
        for name in targets:
            c.chip(cx + 14, y, text_w(name, 13, True) + 22, name, "pkt")
            y += 30
        arrows.append(box.y + 21)
        c.y = box.bottom + 12

    def final(head, text):
        box = c.card("pkt", head, sub(text), x=cx, w=cw, size=16, gap=12, tag=("final", "pkt"))
        arrows.append(box.y + 21)

    unresolved("unknown", "timeout or no response", "Only authoritative reconciliation\nmoves it on:", ["completed_verified", "not_executed_verified"])
    unresolved("partial", "some effects verified, others not; known effects stay charged", "Reconciliation or compensation,\nunder policy, moves it on:", ["completed_verified"])
    final("completed_verified", "an authoritative outcome confirms the effect")
    final("not_executed_verified", "authoritatively verified: no effect for this attempt, target and scope")
    c.path([(submitted.x, submitted.cy), (bus, submitted.cy), (bus, arrows[-1])], head=False)
    for y in arrows:
        c.path([(bus, y), (cx - 1, y)])
    c.card("note", "Open states keep the reservation", sub("While a state is open, allowance stays reserved or charged and there is no blind retry. A timeout or lease expiry never restores allowance; only authoritative reconciliation does."))


# ------------------------------------------------------------------------------------------------------------------ F07
def f07(c):
    table = meta_table("F07")
    rule, _, then = table["notes"][0].replace("**", "").partition(". ")
    c.card("stop", rule + ".", [then], gap=12)
    ink, pad, label_w = c.p["note"][2], 10, 78
    value_x, value_w = c.m + pad + label_w, c.inner - 2 * pad - label_w
    for (state, sees, review, execution), kind in zip(table["rows"], table["execution_kinds"]):
        execution = execution.replace("**", "")
        head = wrap(state, 15, True, c.inner - 2 * pad)
        seen, reviewed = wrap(sees, 14, False, value_w), wrap(review, 14, False, value_w)
        allowed = wrap(execution, 14, execution == "Closed", value_w - 16)
        head_h, seen_h, reviewed_h, allowed_h = len(head) * 15 * 1.25, len(seen) * 14 * 1.32, len(reviewed) * 14 * 1.32, len(allowed) * 14 * 1.32 + 12
        top = c.y
        c.rect(c.m, top, c.inner, pad + head_h + 8 + seen_h + 8 + reviewed_h + 8 + allowed_h + pad, "note")
        y = top + pad
        c.text(c.m + pad, y + 15 * 0.93, head, 15, True, ink, leading=15 * 1.25, maxw=c.inner - 2 * pad)
        y += head_h + 8
        for name, lines, height in (("Sees", seen, seen_h), ("Review", reviewed, reviewed_h)):
            c.text(c.m + pad, y + 14 * 0.95, name, 13, True, ink, maxw=label_w)
            c.text(value_x, y + 14 * 0.95, lines, 14, False, ink, leading=14 * 1.32, maxw=value_w)
            y += height + 8
        c.text(c.m + pad, y + 6 + 14 * 0.95, "Execution", 13, True, ink, maxw=label_w)
        c.rect(value_x, y, value_w, allowed_h, kind, rx=6, sw=1.3)
        c.text(value_x + 8, y + 6 + 14 * 0.95, allowed, 14, execution == "Closed", c.p[kind][2], leading=14 * 1.32, maxw=value_w - 16)
        c.y = top + pad + head_h + 8 + seen_h + 8 + reviewed_h + 8 + allowed_h + pad + 10
    c.card("note", None, [note.replace("**", "") for note in table["notes"][1:]])


# ------------------------------------------------------------------------------------------------------------------ F08
def f08(c):
    steps = [("Native or current workflow", None), ("Deterministic grouping and templates", None),
             ("Simple synthesis, zero specialists", "a complete architecture on its own"),
             ("Optional specialists", "admitted only for a documented task, permission or isolation need")]
    asks = ["is the next step better on matched tasks?", "better on matched tasks?", "a measured, matched need?"]
    for i, (head, text) in enumerate(steps):
        c.card("note", head, sub(text) if text else (), badge=i + 1)
        if i < len(asks):
            c.arrow(30, c.y, c.y + 36, label=asks[i], label_dx=16)
            c.y += 36
    c.y += 22
    c.card("src", "Measure", sub("correctness · omissions · evidence actually inspected · decision quality · time · workload", "Not fluency. Not how many agents agree."), gap=12)
    c.card("warn", "No evaluation result is claimed", sub("No comparison has been run."))


# ------------------------------------------------------------------------------------------------------------------ F09
QUESTIONS = [
    ("May the reader's principal know that this input exists?", "no", "no entry", "nothing about it is shown, not even its state", "yes"),
    ("May the reader's principal read it?", "no", "inaccessible", "the permitted wording only: no name, type, count, state or age", "yes"),
    ("Is a record available but failing the freshness requirement?", "yes", "stale", "", "no"),
    ("Was the check or assessment performed?", "no", "not_assessed", "", "yes"),
    ("Did the source or dependency answer?", "no", "unavailable", "not the same as denied", "yes"),
    ("Did a scoped retrieval complete?", "no", "missing", "expected, not obtained; reason may be unknown", "yes"),
    ("Was absence observed, with method, time and complete coverage?", "yes", "negative", "an adequately scoped observation of absence", "no"),
]


def f09(c):
    ink = c.p["note"][2]
    c.card("note", None, ["An expected input is not in front of the reader"], align="middle")
    c.down(26, label="ask in order")
    left = c.m + 46
    tw = c.inner - 46 - 12
    for i, (question, answer, name, why, goes_on) in enumerate(QUESTIONS):
        kind = "pkt" if name == "negative" else "stop" if name == "no entry" else "warn"
        q_lines, w_lines = wrap(question, 14.5, False, tw), wrap(why, 13, False, tw) if why else []
        q_h, w_h = len(q_lines) * 14.5 * 1.32, len(w_lines) * 13 * 1.32
        top = c.y
        h = 10 + q_h + 8 + 26 + (8 + w_h if why else 0) + 10
        c.rect(c.m, top, c.inner, h, "note")
        c.badge(c.m + 22, top + 21, i + 1, "note")
        c.text(left, top + 10 + 14.5 * 0.95, q_lines, 14.5, False, ink, leading=14.5 * 1.32, maxw=tw)
        y = top + 10 + q_h + 8
        aw = text_w(answer, 13, True)
        c.text(left, y + 18, answer, 13, True, ink, maxw=aw + 1)
        c.path([(left + aw + 8, y + 13), (left + aw + 30, y + 13)])
        c.chip(left + aw + 38, y, text_w(name, 13, True) + 22, name, kind)
        if why:
            c.text(left, y + 26 + 8 + 13 * 0.95, w_lines, 13, False, ink, leading=13 * 1.32, maxw=tw)
        c.y = top + h
        c.down(26, label=goes_on)
    c.card("warn", "not_retrieved", sub("a completed retrieval found nothing; not evidence of absence"), gap=16)
    c.y += c.para(c.m, c.y, c.inner, "Only negative is evidence of absence.", 15, True, c.p["text"], anchor="middle") + 2
    c.y += c.para(c.m, c.y, c.inner, "Each of the other six labels says why nothing can be concluded from the missing input.", 13, False, c.p["muted"], anchor="middle") + 6
    c.y += c.para(c.m, c.y, c.inner, "The two permission questions come first: what a reader may be told is decided before any state is worked out.", 13, False, c.p["muted"], anchor="middle")


# ------------------------------------------------------------------------------------------------------------------ F10
EVENTS = [
    ("BEFORE", None, None, None),
    (None, "own", "Packet (C04) and delegation (C06)", "An approval is queued for a later run."),
    ("THE CORRECTION CASCADES", None, None, None),
    (None, "src", "Source owner", "A correction is admitted as a new version."),
    (None, "src", "Registry (C02)", "It supersedes the earlier version."),
    (None, "src", "Lineage", "Findings and summaries derived from the earlier version are invalidated, and so is the packet that rested on them."),
    (None, "pkt", "Packet (C04)", "A revised packet is produced; the prior version stays linked."),
    (None, "own", "Delegation (C06)", "The pending approval is revoked."),
    ("AT COMMIT", None, None, None),
    (None, "warn", "Executor (action gateway)", "The queued action reaches commit and is rechecked: the grant is revoked and the evidence is no longer current."),
    (None, "pkt", "Receipt (C07)", "Refused before submission, with the reasons. It is a verified no-effect only once the target has been checked."),
    (None, "note", "Next", "A new proposal on the revised packet needs a new approval."),
]


def f10(c):
    rail, cx = c.m + 10, c.m + 32
    cw = c.w - c.m - cx
    prev = None
    for phase, kind, head, text in EVENTS:
        if phase:
            c.y += 6 if prev is None else 12
            c.text(cx, c.y + 10, phase, 13, True, c.p["muted"], maxw=cw)
            c.y += 24
            continue
        box = c.card(kind, head, sub(text), x=cx, w=cw, gap=12)
        cy = box.y + 21
        if prev is not None:
            c.path([(rail, prev + 6), (rail, cy - 6)], head=False)
        c.dot(rail, cy, kind)
        prev = cy
    c.y -= 12


# ------------------------------------------------------------------------------------------------------------------ F11
CHAIN = [("sel", "Context (C01)", "who, what, why, as of when", None), ("sel", "Selection manifest (C03)", "manifest, gaps, obligations", "context"),
         ("pkt", "Decision packet (C04)", "claims, inferences, gaps", "context + selection"), ("own", "Action proposal (C05)", "proposed, not executed", "context + packet"),
         ("own", "Delegation (C06)", "exact approval or bounded class", "bound to"),
         ("pkt", "Execution receipt (C07)", "verified outcome; references one proposal and one grant", "grant")]


def f11(c):
    c02 = c.card("src", "Evidence record (C02)", sub("typed records with lineage, referenced by exact version from every later contract"), gap=22)
    bus, cx = c.m + 10, c.m + 34
    cw = c.w - c.m - 14 - cx
    boxes = []
    for kind, head, text, edge in CHAIN:
        if edge:
            c.arrow(cx + cw / 2, c.y, c.y + 30, label=edge, label_dx=12)
            c.y += 30
        boxes.append(c.card(kind, head, sub(text), x=cx, w=cw))
    c.path([(bus, c02.bottom), (bus, boxes[-1].cy)], dashed=True, head=False)
    for b in boxes[1:]:
        c.path([(bus, b.cy), (b.x - 1, b.cy)], dashed=True)
    rail = c.w - c.m - 5
    c.path([(boxes[3].right, boxes[3].cy), (rail, boxes[3].cy), (rail, boxes[5].cy), (boxes[5].right + 1, boxes[5].cy)])
    c.y += 14
    c.y += c.para(c.m, c.y, c.inner, "Solid arrows are carried forward; the line beside the delegation is the proposal that the receipt references. Dashed arrows reference an exact evidence version.", 13, False, c.p["muted"])


# ------------------------------------------------------------------------------------------------------------------ banner
BANNER_EVIDENCE = [("Goods receipt", "source record", "src"), ("Three-way match", "deterministic finding", "sel"), ("AI explanation", "model inference", "warn")]
BANNER_PACKET = [("Claims", "cite evidence", "pkt"), ("Inferences", "remain labeled", "warn"), ("Conflicts and gaps", "stay visible", "stop"), ("Proposals", "are not actions", "own")]
BANNER_DECISION = "Current evidence is rechecked before action"


def banner_row(c, x, y, w, name, what, kind, h=36, stacked=False):
    """One row of a banner panel: the concept in bold, and what it is or what it does beside it (or under it, when stacked)."""
    c.rect(x, y, w, h, kind, rx=8, sw=1.3)
    ink = c.p[kind][2]
    if stacked:
        c.text(x + 12, y + 18, name, 14, True, ink, maxw=w - 24)
        c.text(x + 12, y + 35, what, 13, False, ink, maxw=w - 24)
    else:
        aw = text_w(name, 14, True)
        c.text(x + 12, y + 23, name, 14, True, ink, maxw=aw + 1)
        c.text(x + w - 12, y + 23, what, 13, False, ink, "end", maxw=w - 24 - aw - 8)


def banner_decision(c, cx, y):
    """The choice a person makes: approve or hold. Returns the y below it."""
    approve_w, hold_w, or_w = text_w("Approve", 13, True) + 22, text_w("Hold", 13, True) + 30, 30
    left = cx - (approve_w + or_w + hold_w) / 2
    c.chip(left, y, approve_w, "Approve", "pkt", h=32)
    label(c, left + approve_w + or_w / 2, y + 21, "or", anchor="middle")
    c.chip(left + approve_w + or_w, y, hold_w, "Hold", "warn", h=32)
    return y + 32


def banner(c):
    c.text(c.w / 2, 38, "Evidence at Human Scale", fit("Evidence at Human Scale", c.inner, 24, least=20), True, c.p["text"], "middle", maxw=c.inner)
    c.y = 54
    c.y += c.para(c.m + 10, c.y, c.inner - 20, "Reference architecture for accountable decisions in agentic systems", 14, False, c.p["muted"], anchor="middle") + 10
    for i, (kind, heading, rows) in enumerate((("src", "Evidence stays distinct", BANNER_EVIDENCE), ("pkt", "One decision packet", BANNER_PACKET))):
        top = c.y
        c.rect(c.m, top, c.inner, 40 + len(rows) * 44 + 6, kind, rx=12, sw=2)
        c.text(c.w / 2, top + 28, heading, 17, True, c.p[kind][2], "middle", maxw=c.inner - 20)
        for j, (name, what, row_kind) in enumerate(rows):
            banner_row(c, c.m + 12, top + 42 + j * 44, c.inner - 24, name, what, row_kind)
        c.y = top + 40 + len(rows) * 44 + 6
        c.down(22)
    top = c.y
    c.rect(c.m, top, c.inner, 118, "own", rx=12, sw=2)
    c.text(c.w / 2, top + 28, "A person decides", 17, True, c.p["own"][2], "middle", maxw=c.inner - 20)
    below = banner_decision(c, c.w / 2, top + 46)
    c.text(c.w / 2, below + 24, BANNER_DECISION, 13, False, c.p["muted"], "middle", maxw=c.inner - 24)
    c.y = top + 118


def banner_wide(c):
    c.text(c.w / 2, 46, "Evidence at Human Scale", 34, True, c.p["text"], "middle", maxw=c.inner)
    c.text(c.w / 2, 76, "Reference architecture for accountable decisions in agentic systems", 17, False, c.p["muted"], "middle", maxw=c.inner)
    widths, gap, top, ph = [250, 288, 236], 26, 100, 224
    xs, x = [], (c.w - sum(widths) - 2 * gap) / 2
    for w in widths:
        xs.append(x)
        x += w + gap

    def heading(i, kind, s):
        size = fit(s, widths[i] - 20, 17)
        c.text(xs[i] + widths[i] / 2, top + 30, s, size, True, c.p[kind][2], "middle", maxw=widths[i] - 20)

    c.rect(xs[0], top, widths[0], ph, "src", rx=14, sw=2)
    heading(0, "src", "Evidence stays distinct")
    for i, (name, what, kind) in enumerate(BANNER_EVIDENCE):
        banner_row(c, xs[0] + 12, top + 52 + i * 54, widths[0] - 24, name, what, kind, h=46, stacked=True)
    c.rect(xs[1], top, widths[1], ph, "pkt", rx=14, sw=2)
    heading(1, "pkt", "One decision packet")
    for i, (name, what, kind) in enumerate(BANNER_PACKET):
        banner_row(c, xs[1] + 12, top + 52 + i * 42, widths[1] - 24, name, what, kind)
    cx = xs[2] + widths[2] / 2
    c.rect(xs[2], top, widths[2], ph, "own", rx=14, sw=2)
    heading(2, "own", "A person decides")
    c.parts.append('<circle cx="%.1f" cy="%.1f" r="14" fill="%s" stroke="%s" stroke-width="2"/>' % (cx, top + 74, c.p["own"][0], c.p["own"][1]))
    c.parts.append('<path d="M%.1f %.1f q0 -26 28 -26 q28 0 28 26 z" fill="%s" stroke="%s" stroke-width="2"/>' % (cx - 28, top + 116, c.p["own"][0], c.p["own"][1]))
    below = banner_decision(c, cx, top + 132)
    c.text(cx, below + 26, "Current evidence is rechecked", 13, False, c.p["muted"], "middle", maxw=widths[2] - 16)
    c.text(cx, below + 44, "before action", 13, False, c.p["muted"], "middle", maxw=widths[2] - 16)
    for a, b in [(0, 1), (1, 2)]:
        c.path([(xs[a] + widths[a] + 1, top + ph / 2), (xs[b] - 1, top + ph / 2)])
    c.y = top + ph + 14


# ------------------------------------------------------------------------------------------------------------------ build
FIGURES = {
    "F01": (f01, "F01", 360), "F02": (f02, "F02", 360), "F02-wide": (f02_wide, "F02", WIDE), "F03": (f03, "F03", 360), "F04": (f04, "F04", 360),
    "F05": (f05, "F05", 360), "F06": (f06, "F06", 360), "F07": (f07, "F07", 360), "F08": (f08, "F08", 360), "F09": (f09, "F09", 360), "F10": (f10, "F10", 360),
    "F11": (f11, "F11", 360), "banner": (banner, "banner", 360), "banner-wide": (banner_wide, "banner", WIDE),
}


def _meta():
    return json.loads((OUT / "figures.json").read_text(encoding="utf-8"))


def meta_text(meta_id):
    """The title and the description for the file itself, from figures.json."""
    data = _meta()
    if meta_id == "banner":
        return data["banner"]["title"], data["banner"]["alt"]
    fig = next(f for f in data["figures"] if f["id"] == meta_id)
    return fig["title"], fig["alt"]


def meta_table(meta_id):
    """The data of a figure that is drawn from a table, from figures.json."""
    return next(f for f in _meta()["figures"] if f["id"] == meta_id)["table"]


def draw(key, theme):
    fn, meta_id, width = FIGURES[key]
    title, desc = meta_text(meta_id)
    c = Fig(theme, title, desc, width=width)
    fn(c)
    return c


def render_all():
    return {"%s-%s.svg" % (key, theme): draw(key, theme).svg() for key in FIGURES for theme in THEMES}


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
        print("%d drawn SVGs match their source." % len(files))
        return 0
    for name, text in files.items():
        (OUT / name).write_bytes(text.encode("utf-8"))
        print("wrote figures/" + name)
    return 0


if __name__ == "__main__":
    sys.exit(main())
