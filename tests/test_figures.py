"""The figure checks: that a drawing is readable at a phone's width, that the drawing helpers keep text inside its box, and that every figure is complete and in sync."""
import json
import sys
import unittest

import support  # noqa: F401  (puts scripts/ on the path)

sys.path.insert(0, str(support.REPO / "figures" / "src"))

import check_figures as figs  # noqa: E402
import kit  # noqa: E402
import svg_figures  # noqa: E402
import sync_figures  # noqa: E402


def svg_of(width=360, size=14, extra=""):
    fig = kit.Fig("light", "A title", "A description", width=width)
    fig.card("src", "Head", ["Some body text"])
    fig.text(20, 100, "x", size)
    return fig.svg().replace("</svg>", extra + "</svg>")


class DrawingChecks(unittest.TestCase):
    def test_a_good_drawing_has_no_problems(self):
        self.assertEqual(figs.drawing_problems("F00", "F00.svg", svg_of(), wide=False), [])
        self.assertEqual(figs.drawing_problems("F00", "F00-wide.svg", svg_of(width=880), wide=True), [])

    def test_a_default_drawing_must_be_narrow_and_a_wide_one_wide(self):
        self.assertIn("at most 380 px", "\n".join(figs.drawing_problems("F00", "F00.svg", svg_of(width=500), wide=False)))
        self.assertIn("800 to 900 px", "\n".join(figs.drawing_problems("F00", "F00-wide.svg", svg_of(width=360), wide=True)))

    def test_text_below_the_smallest_size_is_rejected(self):
        found = "\n".join(figs.drawing_problems("F00", "F00.svg", svg_of(size=11), wide=False))
        self.assertIn("smallest allowed is 13", found)

    def test_a_drawing_that_some_viewers_draw_without_text_or_that_runs_code_is_rejected(self):
        for extra in ("<foreignObject><div>x</div></foreignObject>", "<script>1</script>", '<a href="https://example.org/x">x</a>'):
            self.assertTrue(figs.drawing_problems("F00", "F00.svg", svg_of(extra=extra), wide=False), extra)

    def test_a_drawing_without_a_title_and_description_is_rejected(self):
        found = figs.drawing_problems("F00", "F00.svg", svg_of().replace("<title", "<tit").replace("<desc", "<des"), wide=False)
        self.assertEqual(len(found), 1)
        self.assertIn("<title> and <desc>", found[0])


class Toolkit(unittest.TestCase):
    def test_wrapped_text_fits_its_width(self):
        text = "The quick brown fox jumps over the lazy dog and keeps going for a good while"
        for size, bold in ((13, False), (15, True)):
            for width in (120, 200, 300):
                lines = kit.wrap(text, size, bold, width)
                self.assertEqual(" ".join(lines), text)
                for line in lines:
                    self.assertLessEqual(kit.text_w(line, size, bold), width, line)

    def test_a_word_wider_than_the_line_stays_whole_and_an_explicit_break_is_kept(self):
        self.assertEqual(kit.wrap("Acknowledgement", 14, True, 20), ["Acknowledgement"])
        self.assertEqual(kit.wrap("one\ntwo three", 14, False, 500), ["one", "two three"])

    def test_bold_is_wider_and_every_printable_character_has_a_width(self):
        self.assertGreater(kit.text_w("Receipt", 14, True), kit.text_w("Receipt", 14, False))
        for code in range(32, 127):
            for bold in (False, True):
                self.assertIn(chr(code), kit._WIDTHS[bold], (chr(code), bold))

    def test_every_text_fits_the_width_it_was_given_and_the_canvas(self):
        for key in svg_figures.FIGURES:
            fig = svg_figures.draw(key, "light")
            for slot in fig.slots:
                width = kit.text_w(slot["text"], slot["size"], slot["bold"])
                if slot["maxw"] is not None:
                    self.assertLessEqual(width, slot["maxw"] + 0.5, (key, slot["text"]))
                left = {"start": slot["x"], "middle": slot["x"] - width / 2, "end": slot["x"] - width}[slot["anchor"]]
                self.assertGreaterEqual(left, 0, (key, slot["text"]))
                self.assertLessEqual(left + width, fig.w, (key, slot["text"]))
                self.assertGreaterEqual(slot["size"], figs.MIN_FONT, (key, slot["text"]))

    def test_the_palettes_have_the_contrast_that_text_and_shapes_need(self):
        for theme, p in kit.PALETTES.items():
            for name in kit.KINDS:
                fill, stroke, ink = p[name]
                self.assertGreaterEqual(kit.contrast(ink, fill), 4.5, (theme, name, "text on fill"))
                self.assertGreaterEqual(kit.contrast(p["bg"], stroke), 4.5, (theme, name, "number on a badge"))
                self.assertGreaterEqual(kit.contrast(stroke, p["band"]), 3, (theme, name, "outline on a band"))
            for back in ("bg", "band"):
                self.assertGreaterEqual(kit.contrast(p["muted"], p[back]), 4.5, (theme, "muted text on " + back))
                self.assertGreaterEqual(kit.contrast(p["text"], p[back]), 4.5, (theme, "text on " + back))
                self.assertGreaterEqual(kit.contrast(p["line"], p[back]), 3, (theme, "lines on " + back))

    def test_a_drawing_is_deterministic_and_the_light_and_dark_ones_have_the_same_text(self):
        self.assertEqual(svg_figures.render_all(), svg_figures.render_all())
        for key in svg_figures.FIGURES:
            light, dark = svg_figures.draw(key, "light"), svg_figures.draw(key, "dark")
            self.assertEqual([s["text"] for s in light.slots], [s["text"] for s in dark.slots], key)
            self.assertEqual((light.w, light.height), (dark.w, dark.height), key)

    def test_a_card_grows_with_its_text(self):
        short = kit.Fig("light", "t", "d").card("src", "Head", ["one"], dry=True)
        long = kit.Fig("light", "t", "d").card("src", "Head", ["word " * 60], dry=True)
        self.assertGreater(long, short)


class Metadata(unittest.TestCase):
    def test_every_figure_is_complete_and_used_in_a_page_that_exists(self):
        figures, banner = sync_figures.load()
        self.assertEqual([f["id"] for f in figures], ["F%02d" % n for n in range(1, 12)])
        for fig in figures:
            for key in figs.REQUIRED:
                self.assertTrue(fig.get(key), (fig["id"], key))
            for page in fig["used_in"]:
                self.assertTrue((support.REPO / page).is_file(), (fig["id"], page))
        self.assertTrue(banner)

    def test_the_drawn_files_are_the_ones_the_metadata_names(self):
        figures, banner = sync_figures.load()
        named = set()
        for fig in figures + [banner]:
            for group in ("images", "wide"):
                for rel in (fig.get(group) or {}).values():
                    self.assertTrue((support.REPO / rel).is_file(), rel)
                    named.add(support.REPO / rel)
        drawn = {support.REPO / "figures" / name for name in svg_figures.render_all()}
        self.assertEqual(named, drawn)

    def test_a_figure_with_a_wide_drawing_sets_no_display_width(self):
        figures, banner = sync_figures.load()
        for fig in figures + [banner]:
            self.assertFalse(fig.get("wide") and fig.get("display_width"), fig.get("id", "banner"))

    def test_no_figure_reports_a_result(self):
        text = json.dumps(sync_figures.load()[0]).lower()
        for phrase in ("we measured", "improved by", "% faster", "significantly better", "outperforms"):
            self.assertNotIn(phrase, text)

    def test_the_data_of_a_figure_drawn_from_a_table_must_match_its_columns(self):
        table = {"columns": ["a", "b"], "rows": [["1", "2"], ["3", "4"]], "execution_kinds": ["pkt", "stop"], "notes": ["n"]}
        self.assertEqual(figs.table_problems("F00", table), [])
        self.assertIn("match the columns", figs.table_problems("F00", dict(table, rows=[["1"], ["3", "4"]]))[0])
        self.assertIn("execution_kinds", figs.table_problems("F00", dict(table, execution_kinds=["pkt"]))[0])
        self.assertIn("notes", figs.table_problems("F00", dict(table, notes=[]))[0])

    def test_the_table_behind_f07_is_in_the_page_as_its_text_alternative(self):
        fig = next(f for f in sync_figures.load()[0] if f["id"] == "F07")
        block = sync_figures.block(support.REPO / "docs" / "paper" / "10-degraded-operation.md", fig)
        self.assertIn("| Information state | What the reader sees | Review | Execution |", block)
        self.assertIn("**Closed**", block)
        self.assertLess(block.index("<details>"), block.index("| Information state |"), "the table belongs to the text description")

    def test_no_page_uses_mermaid_and_the_whole_check_passes(self):
        self.assertEqual(figs.mermaid_problems(), [])
        self.assertEqual(figs.check(), [])


class Pictures(unittest.TestCase):
    FIG = {"alt": 'A "quoted" alt', "images": {"light": "figures/F01-light.svg", "dark": "figures/F01-dark.svg"}}

    def test_a_picture_without_a_wide_drawing_has_one_source_and_the_given_width(self):
        html = sync_figures.picture(support.REPO / "README.md", self.FIG, 400)
        self.assertEqual(html.count("<source"), 1)
        self.assertIn('media="(prefers-color-scheme: dark)" srcset="figures/F01-dark.svg"', html)
        self.assertIn('<img src="figures/F01-light.svg" alt="A &quot;quoted&quot; alt" width="400">', html)

    def test_a_wide_drawing_is_chosen_first_and_the_default_stays_the_fallback(self):
        fig = dict(self.FIG, wide={"light": "figures/F01-wide-light.svg", "dark": "figures/F01-wide-dark.svg"})
        html = sync_figures.picture(support.REPO / "README.md", fig)
        sources = [line for line in html.splitlines() if line.startswith("<source")]
        self.assertEqual(len(sources), 3)
        self.assertIn("(min-width: 900px) and (prefers-color-scheme: dark)", sources[0])
        self.assertIn('media="(min-width: 900px)" srcset="figures/F01-wide-light.svg"', sources[1])
        self.assertIn("(prefers-color-scheme: dark)", sources[2])
        self.assertNotIn("width=", html.split("<img")[1], "an <img> width would also shrink the wide drawing")
        self.assertIn('<img src="figures/F01-light.svg"', html)


if __name__ == "__main__":
    unittest.main()
