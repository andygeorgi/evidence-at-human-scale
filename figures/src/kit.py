"""A small drawing toolkit for the figures: text that wraps to a width, cards, connectors and bands. No dependencies.

Every figure in the text is drawn on a narrow canvas (360 px) so that it is readable on a phone at its natural size, and a
figure's height follows from its content. Text is measured with the widest advance of each character in Segoe UI, Arial and
Verdana, so a label that fits here also fits in each of those fonts and in the narrower ones that a reader's system substitutes.
"""
from __future__ import annotations

from html import escape
from typing import List, Optional, Sequence, Tuple

PALETTES = {
    "light": {
        "bg": "#ffffff", "text": "#1b1f24", "muted": "#57606a", "line": "#57606a", "band": "#f6f8fa", "band_stroke": "#d0d7de",
        "src": ("#E8F1FB", "#2F6DB5", "#0B2540"), "sel": ("#E4F4F6", "#1E7F8C", "#06323A"), "pkt": ("#E6F4EA", "#2E7D4F", "#0F2E1B"),
        "own": ("#EFE9F7", "#6A4BA1", "#24133F"), "warn": ("#FFF1D6", "#A15F00", "#3D2500"), "stop": ("#FBE4E4", "#B3261E", "#3D0A07"),
        "note": ("#F4F4F4", "#6F6F6F", "#222222"),
    },
    "dark": {
        "bg": "#0d1117", "text": "#e6edf3", "muted": "#9da7b3", "line": "#8b949e", "band": "#161b22", "band_stroke": "#30363d",
        "src": ("#12304F", "#58A6FF", "#CDE4FF"), "sel": ("#0F3A40", "#39C5CF", "#CFF6F9"), "pkt": ("#12361F", "#56D364", "#D2F8DB"),
        "own": ("#2D2150", "#A371F7", "#E6DAFF"), "warn": ("#4A3200", "#E3B341", "#FFEBC2"), "stop": ("#4D1511", "#F85149", "#FFD8D3"),
        "note": ("#21262D", "#8b949e", "#e6edf3"),
    },
}
FONT = "-apple-system, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif"
KINDS = ("src", "sel", "pkt", "own", "warn", "stop", "note")

# The advance of each character, in em, taken as the widest of Segoe UI, Arial and Verdana (regular, then bold).
_REGULAR = (
    (0.269, "'\u2019"), (0.275, "il"), (0.345, "j"), (0.352, " f"), (0.364, ",.\u00b7"), (0.394, "!"), (0.395, "t"), (0.421, "I"), (0.427, "r"),
    (0.455, "()-/:;[\\]|"), (0.459, "\"\u201c\u201d"), (0.5, "J"), (0.521, "cs"), (0.526, "z"), (0.557, "?L"), (0.592, "kvxy"), (0.596, "e"),
    (0.601, "a"), (0.607, "o"), (0.611, "F"), (0.617, "T"), (0.624, "bdgpq"), (0.633, "hnu"), (0.635, "{}"), (0.636, "$*0123456789_`\u2013"),
    (0.667, "EPY"), (0.684, "ASV"), (0.686, "BXZ"), (0.693, "K"), (0.723, "CR"), (0.732, "U"), (0.749, "N"), (0.75, "\u2713"), (0.752, "H"),
    (0.771, "D"), (0.778, "G"), (0.788, "OQ"), (0.801, "&"), (0.819, "#+<=>^w~\u00d7\u2260"), (0.898, "M"), (0.973, "m"), (0.989, "W"),
    (1.0, "\u2014\u2026\u2192"), (1.016, "@"), (1.077, "%"),
)
_BOLD = (
    (0.333, "'\u2019"), (0.342, " il"), (0.362, ",.\u00b7"), (0.403, "!:;j"), (0.423, "f"), (0.456, "t"), (0.48, "-"), (0.498, "r"),
    (0.544, "()[]|"), (0.546, "I"), (0.557, "J"), (0.588, "\"\u201c\u201d"), (0.589, "c"), (0.594, "s"), (0.597, "z"), (0.617, "?"), (0.638, "L"),
    (0.65, "v"), (0.651, "Fy"), (0.665, "e"), (0.668, "a"), (0.669, "x"), (0.671, "k"), (0.682, "T"), (0.684, "E"), (0.687, "o"), (0.69, "/\\"),
    (0.692, "Z"), (0.7, "bdgpq"), (0.711, "$*0123456789S_`{}\u2013"), (0.713, "hnu"), (0.724, "C"), (0.733, "P"), (0.737, "Y"), (0.75, "\u2713"),
    (0.762, "B"), (0.764, "VX"), (0.771, "K"), (0.777, "A"), (0.783, "R"), (0.812, "G"), (0.813, "U"), (0.831, "D"), (0.838, "H"), (0.847, "N"),
    (0.851, "OQ"), (0.863, "&"), (0.868, "#+<=>^~\u00d7\u2260"), (0.958, "M"), (0.976, "@"), (0.98, "w"), (1.0, "\u2014\u2192"), (1.049, "\u2026"),
    (1.059, "m"), (1.129, "W"), (1.272, "%"),
)


def _table(groups) -> dict:
    return {ch: width for width, chars in groups for ch in chars}


_WIDTHS = {False: _table(_REGULAR), True: _table(_BOLD)}
UNKNOWN_EM = 0.75  # a character that is not in the table is assumed to be wide
SAFETY = 1.01  # kerning and rounding


def text_w(s: str, size: float, bold: bool = False) -> float:
    """The width a string is assumed to need, in px."""
    table = _WIDTHS[bool(bold)]
    return sum(table.get(c, UNKNOWN_EM) for c in s) * size * SAFETY


def _greedy(paragraph: str, size: float, bold: bool, maxw: float) -> List[str]:
    lines: List[str] = []
    cur = ""
    for word in paragraph.split(" "):
        trial = word if not cur else cur + " " + word
        if cur and text_w(trial, size, bold) > maxw:
            lines.append(cur)
            cur = word
        else:
            cur = trial
    lines.append(cur)
    return lines


def wrap(s: str, size: float, bold: bool, maxw: float, balance: bool = True) -> List[str]:
    """Word wrap. An explicit newline always breaks. A single word wider than maxw stays whole. With `balance`, each paragraph is
    set in the narrowest width that still takes the same number of lines, so that no line is left with one short word."""
    lines: List[str] = []
    for paragraph in s.split("\n"):
        wrapped = _greedy(paragraph, size, bold, maxw)
        if balance and len(wrapped) > 1:
            low = max(text_w(word, size, bold) for word in paragraph.split(" "))
            high = maxw
            while high - low > 0.5:
                middle = (low + high) / 2
                if len(_greedy(paragraph, size, bold, middle)) == len(wrapped):
                    high = middle
                else:
                    low = middle
            wrapped = _greedy(paragraph, size, bold, high)
        lines += wrapped
    return lines


def _lum(hex_color: str) -> float:
    rgb = [int(hex_color[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def contrast(a: str, b: str) -> float:
    """WCAG contrast ratio of two #rrggbb colors."""
    hi, lo = sorted((_lum(a), _lum(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


class Box:
    __slots__ = ("x", "y", "w", "h")

    def __init__(self, x: float, y: float, w: float, h: float):
        self.x, self.y, self.w, self.h = x, y, w, h

    cx = property(lambda self: self.x + self.w / 2)
    cy = property(lambda self: self.y + self.h / 2)
    right = property(lambda self: self.x + self.w)
    bottom = property(lambda self: self.y + self.h)


class Fig:
    HEAD, BODY, SMALL = 15, 14, 13

    def __init__(self, theme: str, title: str, desc: str, width: int = 360, margin: int = 10, height: Optional[int] = None):
        self.theme, self.p = theme, PALETTES[theme]
        self.title, self.desc = title, desc
        self.w, self.m, self.fixed_h = width, margin, height
        self.parts: List[str] = []
        self.y = float(margin)  # the flow cursor
        self.maxy = 0.0
        self.slots: List[dict] = []  # every text with the width it was given, for the layout check

    # ------------------------------------------------------------------------------------------ low level
    @property
    def inner(self) -> float:
        return self.w - 2 * self.m

    def _grow(self, y: float) -> None:
        self.maxy = max(self.maxy, y)

    def rect(self, x, y, w, h, kind, rx=8, sw=1.6, dash=False) -> None:
        fill, stroke, _ = self.p[kind]
        self.parts.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="%s" fill="%s" stroke="%s" stroke-width="%s"%s/>' % (
            x, y, w, h, rx, fill, stroke, sw, ' stroke-dasharray="5 4"' if dash else ""))
        self._grow(y + h)

    def text(self, x, y, lines, size=14, bold=False, fill=None, anchor="start", leading=None, maxw=None) -> None:
        leading = leading or size * 1.32
        lines = [lines] if isinstance(lines, str) else list(lines)
        for i, line in enumerate(lines):
            self.slots.append({"x": x, "anchor": anchor, "maxw": maxw, "size": size, "bold": bold, "text": line})
            self.parts.append('<text x="%.1f" y="%.1f" font-size="%s" text-anchor="%s"%s fill="%s">%s</text>' % (
                x, y + i * leading, size, anchor, ' font-weight="700"' if bold else "", fill or self.p["text"], escape(line)))
        self._grow(y + (len(lines) - 1) * leading + size * 0.4)

    def para(self, x, y, w, s, size=14, bold=False, fill=None, anchor="start", leading=None) -> float:
        """Wrapped text in a block whose top-left is (x, y) and whose width is w; returns its height."""
        leading = leading or size * 1.32
        lines = wrap(s, size, bold, w)
        ax = x if anchor == "start" else (x + w / 2 if anchor == "middle" else x + w)
        self.text(ax, y + size * 0.95, lines, size, bold, fill, anchor, leading, maxw=w)
        return len(lines) * leading

    def path(self, points: Sequence[Tuple[float, float]], dashed=False, head=True, sw=1.8, small=False) -> None:
        """A line through points, with an arrowhead at its end. `small` draws a smaller head, for a short connector between cards."""
        d = "M" + " L".join("%.1f %.1f" % p for p in points)
        marker = "arrs" if small else "arr"
        self.parts.append('<path d="%s" fill="none" stroke="%s" stroke-width="%s"%s%s/>' % (
            d, self.p["line"], sw, ' stroke-dasharray="5 4"' if dashed else "", ' marker-end="url(#%s)"' % marker if head else ""))
        for _, py in points:
            self._grow(py)

    def badge(self, cx, cy, n, kind, r=12) -> None:
        stroke = self.p[kind][1]
        self.parts.append('<circle cx="%.1f" cy="%.1f" r="%s" fill="%s" stroke="%s" stroke-width="1.6"/>' % (cx, cy, r, stroke, stroke))
        self.text(cx, cy + 4.6, str(n), 13, True, self.p["bg"], "middle", maxw=2 * r)
        self._grow(cy + r)

    def dot(self, cx, cy, kind, r=6) -> None:
        self.parts.append('<circle cx="%.1f" cy="%.1f" r="%s" fill="%s" stroke="%s" stroke-width="1.6"/>' % (cx, cy, r, self.p[kind][0], self.p[kind][1]))

    def pill(self, x, y, s, kind="note", size=13, bold=True, pad_x=8) -> Box:
        """A small rounded label whose width follows its text; x is its left edge."""
        w, h = text_w(s, size, bold) + 2 * pad_x, size + 10
        self.rect(x, y, w, h, kind, rx=h / 2, sw=1.4)
        self.text(x + w / 2, y + h / 2 + size * 0.34, s, size, bold, self.p[kind][2], "middle", maxw=w)
        return Box(x, y, w, h)

    def chip(self, x, y, w, s, kind="note", size=13, h=None, bold=True) -> Box:
        """A small rounded label of a given width, with its text centered."""
        h = h or size + 13
        self.rect(x, y, w, h, kind, rx=8, sw=1.4)
        self.text(x + w / 2, y + h / 2 + size * 0.34, s, size, bold, self.p[kind][2], "middle", maxw=w - 8)
        return Box(x, y, w, h)

    def check(self, x, y, size=12) -> None:
        """A small square with a tick, drawn rather than typed, so it never depends on a font."""
        stroke = self.p["warn"][1]
        self.parts.append('<rect x="%.1f" y="%.1f" width="%s" height="%s" rx="2.5" fill="none" stroke="%s" stroke-width="1.6"/>' % (x, y, size, size, stroke))
        self.parts.append('<path d="M%.1f %.1f L%.1f %.1f L%.1f %.1f" fill="none" stroke="%s" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>' % (
            x + size * 0.22, y + size * 0.52, x + size * 0.43, y + size * 0.74, x + size * 0.8, y + size * 0.26, stroke))

    # ------------------------------------------------------------------------------------------ cards and flow
    def card(self, kind, head=None, body=(), x=None, w=None, y=None, size=None, pad=10, align="start", badge=None, tag=None,
             dash=False, min_h=0, dry=False, gap=0):
        """A filled box with a bold head and wrapped body lines. With y omitted the card is placed at the flow cursor, which
        then moves below it (plus `gap`). A body item is a string, or a (string, "small") pair. With dry=True nothing is
        drawn and the height is returned."""
        size = size or self.HEAD
        flow = y is None
        x = self.m if x is None else x
        w = self.inner if w is None else w
        y = self.y if y is None else y
        left = pad + (30 if badge is not None else 0)
        tag_w = text_w(tag[0], 13, True) + 16 if tag else 0
        body_w = w - left - pad
        head_w = body_w - (tag_w + 6 if tag else 0)
        centered = align == "middle"
        if centered:
            head_w = body_w = w - 2 * pad
        color = self.p[kind][2]
        head_lines: List[str] = []
        for part in ([head] if isinstance(head, str) else list(head or [])):
            head_lines += wrap(part, size, True, head_w)
        items = []
        for item in ([body] if isinstance(body, str) else list(body)):
            text, style = item if isinstance(item, tuple) else (item, "body")
            fs = self.SMALL if style == "small" else self.BODY
            items.append((wrap(text, fs, False, body_w), fs))
        head_h = len(head_lines) * size * 1.25
        body_h = sum(len(lines) * fs * 1.32 for lines, fs in items) + 3 * max(0, len(items) - 1)
        h = max(min_h, pad + head_h + (4 if head_lines and items else 0) + body_h + pad)
        if dry:
            return h
        self.rect(x, y, w, h, kind, dash=dash)
        cy = y + pad
        tx = x + w / 2 if centered else x + left
        anchor = "middle" if centered else "start"
        if badge is not None:
            self.badge(x + pad + 11, y + pad + 11, badge, kind)
        if tag:
            self.pill(x + w - pad - tag_w, y + pad - 2, tag[0], tag[1])
        if head_lines:
            self.text(tx, cy + size * 0.93, head_lines, size, True, color, anchor, size * 1.25, maxw=head_w)
            cy += head_h + (4 if items else 0)
        for lines, fs in items:
            self.text(tx, cy + fs * 0.95, lines, fs, False, color, anchor, fs * 1.32, maxw=body_w)
            cy += len(lines) * fs * 1.32 + 3
        if flow:
            self.y = y + h + gap
        return Box(x, y, w, h)

    def down(self, h=26, x=None, label=None, dashed=False, head=True) -> None:
        """A vertical connector from the flow cursor, which moves down by h."""
        self.arrow(self.w / 2 if x is None else x, self.y, self.y + h, label, dashed, head)
        self.y += h

    def arrow(self, x, y1, y2, label=None, dashed=False, head=True, label_dx=10) -> None:
        self.path([(x, y1), (x, y2 - (1 if head else 0))], dashed=dashed, head=head)
        if label:
            width = self.w - self.m - (x + label_dx)
            lines = wrap(label, 13, False, width)
            self.text(x + label_dx, (y1 + y2) / 2 + 4.6 - (len(lines) - 1) * 13 * 1.32 / 2, lines, 13, False, self.p["muted"], "start", maxw=width)

    def band_start(self) -> dict:
        return {"idx": len(self.parts), "y": self.y}

    def band_end(self, token, x=None, w=None, pad=10, dash=False) -> Box:
        """Draw a band behind everything drawn since band_start(): its rect is inserted at the recorded position."""
        x = self.m if x is None else x
        w = self.inner if w is None else w
        top, bottom = token["y"], self.y + pad
        stroke = self.p["line"] if dash else self.p["band_stroke"]
        rect = '<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="12" fill="%s" stroke="%s" stroke-width="1.2"%s/>' % (
            x, top, w, bottom - top, self.p["band"], stroke, ' stroke-dasharray="5 4"' if dash else "")
        self.parts.insert(token["idx"], rect)
        self._grow(bottom)
        self.y = bottom
        return Box(x, top, w, bottom - top)

    def band(self, x, y, w, h) -> None:
        """A band at fixed coordinates."""
        self.parts.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="12" fill="%s" stroke="%s" stroke-width="1.2"/>' % (
            x, y, w, h, self.p["band"], self.p["band_stroke"]))
        self._grow(y + h)

    def divider(self, y, label, kind="note") -> None:
        """A rule across the canvas with a labeled pill in the middle."""
        pill_w = text_w(label, 15, True) + 28
        self.path([(self.m, y), (self.w - self.m, y)], head=False, sw=1.4)
        self.rect(self.w / 2 - pill_w / 2, y - 15, pill_w, 30, kind, rx=15, sw=1.6)
        self.text(self.w / 2, y + 5.5, label, 15, True, self.p[kind][2], "middle", maxw=pill_w)

    # ------------------------------------------------------------------------------------------ output
    @property
    def height(self) -> int:
        if self.fixed_h:
            return self.fixed_h
        return int(-(-(self.maxy + self.m) // 1))

    def svg(self) -> str:
        h = self.height
        head = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d" width="%d" height="%d" role="img" aria-labelledby="t d" font-family="%s">\n'
                '<title id="t">%s</title>\n<desc id="d">%s</desc>\n'
                '<defs><marker id="arr" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse">'
                '<path d="M0 0 L10 5 L0 10 z" fill="%s"/></marker>'
                '<marker id="arrs" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="5.5" markerHeight="5.5" orient="auto-start-reverse">'
                '<path d="M0 0 L10 5 L0 10 z" fill="%s"/></marker></defs>\n<rect width="%d" height="%d" fill="%s"/>\n') % (
            self.w, h, self.w, h, FONT, escape(self.title), escape(self.desc), self.p["line"], self.p["line"], self.w, h, self.p["bg"])
        return head + "\n".join(self.parts) + "\n</svg>\n"
