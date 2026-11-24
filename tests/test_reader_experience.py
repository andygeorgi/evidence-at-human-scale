"""The public reader experience: a human name comes before a machine identifier, the first screen says what this is, why it
matters and what to do next, one path leads in, and the reference surfaces keep the identifiers that make them quick to look up."""
import html
import json
import re
import unittest

import support  # noqa: F401  (puts scripts/ on the path)

REPO = support.REPO
FIGURES = REPO / "figures"

#: The abstract labels of the schema's examples and the evaluation fixtures, and the identifiers of a contract, a test and a group.
ABSTRACT_LABEL = re.compile(r"\b(?:S0[12]|D01|V01|P01)\b|\bM0[12]/v\d\b")
MACHINE_ID = re.compile(r"\b(?:C0[1-7]|EV\d\d|DP\d{3}|AUTH\d{3}|G0\d)\b")
ID_FIRST_LABEL = re.compile(r"^(?:C0[1-7]|G0\d|EV\d\d|S0\d|M0\d|P01|V01|D01)(?:/v\d)?\b")
ID_FIRST_LINK = re.compile(r"\[(?:C0[1-7]|EV\d\d|G0\d)\s+[A-Za-z]")
CLAIM = "This is a reference architecture, not a production deployment or benefit claim. The contracts and synthetic examples are tested; real-world effectiveness has not been evaluated."


def text(relative):
    return (REPO / relative).read_text(encoding="utf-8")


def pages(*patterns):
    found = []
    for pattern in patterns:
        found += sorted(path.relative_to(REPO).as_posix() for path in REPO.glob(pattern))
    return found


def without_generated_blocks(markdown):
    return re.sub(r"<!-- (figure:\w+|banner):start -->.*?<!-- \1:end -->", "", markdown, flags=re.S)


def svg_words(name):
    svg = (FIGURES / name).read_text(encoding="utf-8")
    return [html.unescape(node) for node in re.findall(r"<text\b[^>]*>(.*?)</text>", svg, flags=re.S)]


def first_screen():
    """What a reader sees before the first section heading, without the banner."""
    body = without_generated_blocks(text("README.md"))
    return body.split("\n## ", 1)[0]


class TheFirstScreen(unittest.TestCase):
    def test_it_says_what_this_is_why_it_matters_and_what_to_do_next(self):
        screen = first_screen()
        self.assertTrue(screen.startswith("\n# Evidence at Human Scale") or screen.lstrip().startswith("# Evidence at Human Scale"))
        self.assertIn("Reference architecture for accountable decisions in agentic systems", screen)
        self.assertIn("cannot easily tell what is a source record, what is a model's inference and what is missing", screen, "the practical problem")
        self.assertIn("one decision packet that keeps them apart", screen, "the architecture's response")
        self.assertIn("[Start with the ten-minute path](#ten-minute-path)", screen, "the next action")

    def test_it_holds_no_version_code_identifier_or_process_language(self):
        screen = first_screen()
        self.assertEqual(re.findall(r"\bv?\d+\.\d+\.\d+\b", screen), [])
        self.assertEqual(MACHINE_ID.findall(screen) + ABSTRACT_LABEL.findall(screen), [])
        for word in ("candidate", "changelog", "release notes", "pull request", "disclaimer"):
            self.assertNotIn(word, screen.lower())

    def test_it_repeats_no_status_block_and_offers_one_path(self):
        screen = first_screen()
        self.assertNotIn("not a production deployment", screen)
        self.assertEqual(screen.count("](#"), 1, "one way in, not several")

    def test_the_one_path_has_its_steps_and_the_quickstart_it_sends_to(self):
        readme = text("README.md")
        self.assertEqual(readme.count("## Ten-minute path"), 1)
        self.assertEqual(readme.count("## Quickstart"), 1)
        self.assertLess(readme.index("## Ten-minute path"), readme.index("## Quickstart"))
        path = readme.split("## Ten-minute path", 1)[1].split("\n## ", 1)[0]
        self.assertIn("(#quickstart)", path)
        self.assertEqual(len(re.findall(r"(?m)^\d\. ", path)), 5)

    def test_the_problem_keeps_its_anchor_and_names_its_things_before_their_numbers(self):
        problem = text("README.md").split("## The problem, in one invoice", 1)[1].split("\n## ", 1)[0]
        for phrase in ("invoice", "goods receipt", "AI summaries", "treasury service", "requestor's read permissions", "corrects the receipt"):
            self.assertIn(phrase, problem)
        self.assertEqual(MACHINE_ID.findall(problem) + re.findall(r"\bINV-\d|GR-\d", problem), [])

    def test_the_version_and_date_are_given_where_a_citation_needs_them(self):
        from eahs import __version__
        cite = text("README.md").split("## Citing, contributing, security", 1)[1].split("\n## ", 1)[0]
        self.assertIn("`v%s`" % __version__, cite)


class TheBanner(unittest.TestCase):
    NAMES = [("banner-light.svg"), ("banner-dark.svg"), ("banner-wide-light.svg"), ("banner-wide-dark.svg")]
    CONCEPTS = ("Evidence stays distinct", "Goods receipt", "source record", "Three-way match", "deterministic finding", "AI explanation", "model inference",
                "One decision packet", "Claims", "cite evidence", "Inferences", "remain labeled", "Conflicts and gaps", "stay visible", "Proposals", "are not actions",
                "A person decides", "Approve", "Hold")

    def test_it_explains_in_human_words_and_is_understood_without_an_identifier(self):
        for name in self.NAMES:
            words = " | ".join(svg_words(name))
            for concept in self.CONCEPTS:
                self.assertIn(concept, words, "%s: %s" % (name, concept))
            self.assertIn("Current evidence is rechecked", words)
            self.assertEqual(ABSTRACT_LABEL.findall(words) + MACHINE_ID.findall(words), [], name)
            self.assertNotRegex(words, r"(?i)ai-powered|trusted ai|microsoft|copilot")

    def test_the_concept_comes_before_the_kind_in_the_order_the_reader_meets_them(self):
        words = svg_words("banner-wide-light.svg")
        order = [words.index(w) for w in ("Evidence stays distinct", "One decision packet", "A person decides")]
        self.assertEqual(order, sorted(order))
        self.assertLess(words.index("Goods receipt"), words.index("source record"))

    def test_the_readme_alt_text_says_the_same_in_words(self):
        alt = re.search(r'<img src="figures/banner-light.svg" alt="([^"]+)"', text("README.md")).group(1)
        for concept in ("goods receipt", "three-way match", "AI explanation", "source record", "deterministic finding", "model inference", "claims cite evidence", "proposals are not actions"):
            self.assertIn(concept, alt)
        self.assertEqual(ABSTRACT_LABEL.findall(alt) + MACHINE_ID.findall(alt), [])

    def test_no_drawing_leads_with_an_identifier_before_its_concept(self):
        for path in sorted(FIGURES.glob("*.svg")):
            for word in svg_words(path.name):
                self.assertNotRegex(word.strip(), ID_FIRST_LABEL, "%s: %r puts an identifier before its concept" % (path.name, word))


class HumanNamesBeforeIdentifiers(unittest.TestCase):
    PRIMARY = pages("README.md", "docs/paper/[0-9]*.md", "docs/implementation-guide.md", "architecture/README.md", "examples/*/README.md", "examples/README.md")

    def test_no_link_in_a_first_read_page_leads_with_an_identifier(self):
        found = [(page, hit) for page in self.PRIMARY for hit in ID_FIRST_LINK.findall(without_generated_blocks(text(page)))]
        self.assertEqual(found, [])

    def test_the_abstract_labels_do_not_reach_the_paper_the_readme_or_the_first_use_examples(self):
        found = []
        for page in pages("README.md", "docs/paper/*.md", "examples/0[1-9]-*/README.md", "examples/1*/README.md"):
            found += [(page, hit) for hit in ABSTRACT_LABEL.findall(text(page))]
        self.assertEqual(found, [])

    def test_a_figure_names_its_things_in_words_and_puts_an_identifier_after_them(self):
        with open(FIGURES / "figures.json", encoding="utf-8") as handle:
            figures = json.load(handle)["figures"]
        for figure in figures:
            for key in ("caption", "alt"):
                self.assertEqual(ABSTRACT_LABEL.findall(figure[key]), [], "%s %s" % (figure["id"], key))
                self.assertNotRegex(figure[key], r"\bG0\d\b", "%s %s: a group is named, not numbered" % (figure["id"], key))

    def test_the_receipt_states_are_named_in_words_before_their_values(self):
        for name in ("F06-light.svg", "F06-dark.svg"):
            words = svg_words(name)
            for human, value in (("Outcome unknown", "unknown \u00b7"), ("Partly verified", "partial \u00b7"), ("Completed and verified", "completed_verified"), ("Verified no effect", "not_executed_verified")):
                self.assertLess(words.index(human), next(i for i, w in enumerate(words) if w.startswith(value)), "%s: %s" % (name, human))
            self.assertEqual([w for w in words if w.strip() in ("unknown", "partial", "completed_verified", "not_executed_verified")], [], "%s: no card or chip is headed by a state value alone" % name)
        figure = next(f for f in json.loads(text("figures/figures.json"))["figures"] if f["id"] == "F06")
        self.assertLess(figure["alt"].index("Outcome unknown"), len(figure["alt"]))
        self.assertNotRegex(figure["alt"], r"completed_verified|not_executed_verified", "the alt text is in words")
        self.assertIn("completed_verified", figure["caption"], "the stable values stay in the caption, after the words")
        self.assertLess(figure["caption"].index("a verified no-effect"), figure["caption"].index("not_executed_verified"))

    def test_the_story_table_keeps_the_record_numbers_after_the_names(self):
        story = text("examples/README.md").split("## The story", 1)[1].split("## Folder map", 1)[0]
        self.assertIn("Goods receipt `GR-5521` v1", story)
        self.assertIn("Invoice `INV-2026-0417` arrives", story)

    def test_a_table_of_a_first_use_example_names_a_record_before_its_identifier(self):
        starts_with_an_identifier = re.compile(r"^\|\s*`[A-Z]{2,5}-[A-Z0-9-]+`")
        for page in ("examples/04-selection-and-missingness/README.md", "examples/05-decision-packet/README.md", "examples/11-late-correction/README.md"):
            self.assertEqual([line[:70] for line in text(page).split("\n") if starts_with_an_identifier.match(line)], [], page)
        packet = text("examples/05-decision-packet/README.md")
        self.assertIn("Hold the invoice (`REC-0417-1`)", packet)
        self.assertLess(packet.index("Hold the invoice (`REC-0417-1`)"), packet.index("`REC-0417-1B`"))

    def test_the_abstract_labels_are_explained_where_the_reference_material_uses_them(self):
        page = text("examples/README.md").split("## Reading the abstract labels in the reference material", 1)[1]
        for label in ("`S01/v1`", "`S02/v1`", "`V01/v1`", "`P01`"):
            self.assertIn(label, page)
        self.assertLess(page.index("The goods receipt"), page.index("`S01/v1`"), "the story's name comes first in the table")


class OneVoiceOnTheStatus(unittest.TestCase):
    def test_the_full_standing_claim_is_at_the_entry_and_on_the_claims_page_only(self):
        found = [page for page in pages("*.md", "*/*.md", "*/*/*.md", "*/*/*/*.md") if CLAIM in text(page) and page != "CHANGELOG.md"]
        self.assertEqual(found, ["README.md", "docs/claims-and-limits.md"])

    def test_a_secondary_page_links_to_the_claims_page_instead_of_repeating_it(self):
        for page, anchor in (("architecture/README.md", "claims-and-limits.md#evidence-classes-kept-apart"), ("evaluation/README.md", "claims-and-limits.md"),
                             ("docs/paper/00-overview.md", "claims-and-limits.md")):
            self.assertIn(anchor, text(page), page)

    def test_a_limit_that_changes_what_a_page_means_stays_on_the_page(self):
        self.assertIn("not a production deployment", text("evaluation/README.md"))
        self.assertIn("real-world effectiveness has not been evaluated", text("docs/paper/00-overview.md"))
        self.assertIn("None of it has been run", text("evaluation/README.md"))


class DeepLinksOfEarlierReleasesKeepWorking(unittest.TestCase):
    """A page was reorganized for the reader, but a link to a section of v1.0.1 still lands on the section that replaced it."""

    LEGACY = {
        "README.md": ("status-and-limits", "what-a-pass-means-and-what-it-does-not", "the-smallest-useful-experiment", "where-to-go-next"),
        "docs/paper/00-overview.md": ("how-the-paper-is-organized",),
        "examples/07-authority-and-delegation/README.md": ("the-commit-check-six-times",),
        "examples/10-degraded-modes/README.md": ("the-three-fail-closed-evaluations",),
        "examples/README.md": ("reading-the-papers-abstract-notation",),
    }

    def test_each_renamed_or_merged_section_of_the_previous_release_still_has_its_anchor(self):
        for page, anchors in self.LEGACY.items():
            lines = text(page).split("\n")
            for anchor in anchors:
                self.assertIn('<a id="%s"></a>' % anchor, lines, "%s#%s" % (page, anchor))

    def test_an_anchor_sits_directly_above_the_heading_that_replaced_its_section(self):
        for page, anchors in self.LEGACY.items():
            if page == "docs/paper/00-overview.md":
                continue  # the chapter has no sections now: its anchor stands in front of the paragraph that points to the other routes
            lines = text(page).split("\n")
            for anchor in anchors:
                index = lines.index('<a id="%s"></a>' % anchor)
                following = [line for line in lines[index + 1:index + 4] if not line.startswith("<a id=")]
                self.assertTrue(following and following[0].startswith("## "), "%s#%s" % (page, anchor))

    def test_no_other_anchor_of_the_previous_release_was_lost(self):
        """Every other section anchor of v1.0.1 is still a heading of the same page, so that the list above is the whole list."""
        import subprocess
        try:
            tags = subprocess.run(["git", "-C", str(REPO), "tag", "--list", "v1.0.1"], capture_output=True, text=True, encoding="utf-8").stdout.split()
        except OSError:
            self.skipTest("git is not available")
        if "v1.0.1" not in tags:
            self.skipTest("the v1.0.1 tag is not in this checkout")

        def slug(heading):
            heading = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", re.sub(r"<[^>]+>", "", heading))
            return re.sub(r"[^\w\- ]", "", re.sub(r"[`*_]", "", heading).strip().lower()).replace(" ", "-")

        def anchors(markdown):
            found, fenced = set(), False
            for line in markdown.split("\n"):
                if line.startswith("```"):
                    fenced = not fenced
                elif not fenced:
                    heading = re.match(r"^#{1,6}\s+(.*?)\s*#*\s*$", line)
                    found.update([slug(heading.group(1))] if heading else [])
                    found.update(re.findall(r'<a\s+(?:id|name)="([^"]+)"', line))
            return found

        listing = subprocess.run(["git", "-C", str(REPO), "ls-tree", "-r", "--name-only", "v1.0.1"], capture_output=True, text=True, encoding="utf-8").stdout.split("\n")
        lost = {}
        for page in (name for name in listing if name.endswith(".md") and (REPO / name).is_file()):
            earlier = subprocess.run(["git", "-C", str(REPO), "show", "v1.0.1:" + page], capture_output=True, text=True, encoding="utf-8").stdout
            gone = anchors(earlier) - anchors(text(page))
            if gone:
                lost[page] = sorted(gone)
        self.assertEqual(lost, {})


class ReferenceSurfacesKeepTheirIdentifiers(unittest.TestCase):
    def test_a_contract_page_and_the_contract_index_stay_identifier_first(self):
        index = text("contracts/README.md")
        for number, name in (("01", "Context"), ("02", "Evidence"), ("03", "Selection"), ("04", "Decision packet"), ("05", "Action proposal"), ("06", "Delegation"), ("07", "Execution receipt")):
            self.assertIn("[C%s %s]" % (number, name), index)
            page = next((REPO / "contracts").glob("c%s-*.md" % number))
            self.assertTrue(page.read_text(encoding="utf-8").startswith("# C%s %s\n" % (number, name)), page.name)

    def test_the_catalogue_and_the_oracles_keep_every_test_identifier(self):
        tests = json.loads(text("evaluation/catalogue/evaluation-tests.json"))
        self.assertEqual(sorted(entry["id"] for entry in tests), ["EV%02d" % n for n in range(1, 13)])
        for number in range(1, 13):
            self.assertIn("EV%02d" % number, text("evaluation/oracles.md"))

    def test_the_stable_identifiers_of_the_example_data_are_unchanged(self):
        for name in ("01-source-records/c02-GR-5521-v1.json", "05-decision-packet/c04-PKT-0417-v1.json", "08-blocked-action/c07-RCP-REL-0417-A-v1.json"):
            self.assertTrue((support.EXAMPLES / name).is_file(), name)
        self.assertIn('"contract_id": "C04"', text("examples/05-decision-packet/c04-PKT-0417-v1.json"))

    def test_the_diagnostic_codes_are_still_the_codes_of_the_reference_tables(self):
        scripts = text("scripts/README.md")
        for code in ("`AUTH008`", "`PKT005`", "`DISC005`", "`ROLE008`", "`RESP017`", "`ID005`"):
            self.assertIn(code, scripts)


if __name__ == "__main__":
    unittest.main()
