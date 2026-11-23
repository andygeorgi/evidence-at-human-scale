"""The figure checks: what makes a Mermaid source legible in both color schemes, and that every figure is complete."""
import json
import unittest

import support  # noqa: F401  (puts scripts/ on the path)

import check_figures as figs
import sync_figures

GOOD = """flowchart TB
    accTitle: A title
    accDescr: A description
    A["x"]:::ok
    classDef ok fill:#fff,stroke:#000,color:#000
"""


class MermaidLint(unittest.TestCase):
    def test_a_good_source_has_no_problems(self):
        self.assertEqual(figs.lint_mermaid("F00", "F00.mmd", GOOD), [])

    def test_a_class_without_a_text_color_is_unsafe_in_dark_mode(self):
        found = figs.lint_mermaid("F00", "F00.mmd", GOOD.replace("color:#000", ""))
        self.assertEqual(len(found), 1)
        self.assertIn("dark mode", found[0])

    def test_a_class_named_like_one_of_mermaids_own_is_rejected(self):
        for name in ("label", "edgeLabel", "node", "cluster", "note"):
            found = figs.lint_mermaid("F00", "F00.mmd", GOOD.replace(":::ok", ":::" + name).replace("classDef ok", "classDef " + name))
            self.assertEqual(len(found), 1, name)
            self.assertIn("CSS class Mermaid uses", found[0])

    def test_accessibility_text_and_no_links(self):
        found = "\n".join(figs.lint_mermaid("F00", "F00.mmd", GOOD.replace("accTitle: A title\n", "").replace("accDescr: A description\n", "") + "    click A href \"x\"\n"))
        self.assertIn("accTitle:", found)
        self.assertIn("accDescr:", found)
        self.assertIn("click or href", found)

    def test_every_mermaid_source_in_the_repository_passes(self):
        figures, _banner = sync_figures.load()
        for fig in figures:
            if fig["kind"] == "mermaid":
                source = support.REPO / fig["source"]
                self.assertEqual(figs.lint_mermaid(fig["id"], source.name, source.read_text(encoding="utf-8")), [], fig["id"])


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

    def test_no_figure_reports_a_result(self):
        text = json.dumps(sync_figures.load()[0]).lower()
        for phrase in ("we measured", "improved by", "% faster", "significantly better", "outperforms"):
            self.assertNotIn(phrase, text)

    def test_the_how_made_table_lists_each_figure_under_its_kind(self):
        figures = sync_figures.load()[0]
        self.assertEqual(figs.kind_table_problems(figures), [])
        moved = [dict(f, kind="svg") if f["id"] == "F05" else f for f in figures]
        self.assertEqual(len(figs.kind_table_problems(moved)), 2, "F05 would be missing from the Mermaid row and extra in the SVG row")


if __name__ == "__main__":
    unittest.main()
