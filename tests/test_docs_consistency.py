"""Numbers that the documents state must be the numbers in the data, and the stored gateway evaluations must cover every reason code."""
import json
import re
import unittest

import support  # noqa: F401  (puts scripts/ on the path)

from eahs.gateway import GATE_CODES
from eahs.schema import check_embedded_examples

REPO = support.REPO


def text(relative):
    return (REPO / relative).read_text(encoding="utf-8")


def scenario_entries():
    entries = []
    for path in sorted(support.EXAMPLES.glob("*/gateway-scenarios.json")):
        entries += json.loads(path.read_text(encoding="utf-8"))["evaluations"]
    return entries


def case_count():
    return len(json.loads(text("examples/13-evaluation-cases/cases.json"))["cases"])


def catalogue_count(name):
    return len(json.loads(text("evaluation/catalogue/%s.json" % name)))


class GatewayCoverage(unittest.TestCase):
    def test_the_stored_evaluations_exercise_every_reason_code(self):
        used = {code for entry in scenario_entries() for code in entry["expect"]["codes"]}
        self.assertEqual(sorted(set(GATE_CODES) - used), [], "reason codes with no stored evaluation")

    def test_the_stored_evaluations_name_no_unknown_code(self):
        used = {code for entry in scenario_entries() for code in entry["expect"]["codes"]}
        self.assertEqual(sorted(used - set(GATE_CODES)), [])

    def test_every_evaluation_has_a_label_and_a_decision(self):
        labels = [entry["label"] for entry in scenario_entries()]
        self.assertEqual(len(labels), len(set(labels)))
        for entry in scenario_entries():
            self.assertIn(entry["expect"]["decision"], ("ALLOW", "BLOCK"), entry["label"])

    def test_the_reason_code_index_links_exactly_the_examples_whose_stored_evaluations_expect_the_code(self):
        """The 'Shown in' column of the index in Example 08 sends a reader to a scenario that shows the code, so it must not name one that does not or leave one out."""
        where = {}
        for path in sorted(support.EXAMPLES.glob("*/gateway-scenarios.json")):
            for entry in json.loads(path.read_text(encoding="utf-8"))["evaluations"]:
                for code in entry["expect"]["codes"]:
                    where.setdefault(code, set()).add(path.parent.name[:2])
        listed = {}
        for line in text("examples/08-blocked-action/README.md").splitlines():
            match = re.match(r"\| `([A-Z_]+)` \|.*\| ([^|]+) \|$", line)
            if match and match.group(1) in GATE_CODES:
                shown = set(re.findall(r"\[(\d\d)\]", match.group(2)))
                listed[match.group(1)] = shown | ({"08"} if "here" in match.group(2) else set())
        self.assertEqual(sorted(listed), sorted(GATE_CODES), "every code has a row")
        self.assertEqual({code: shown for code, shown in listed.items() if shown != where[code]}, {}, "the examples named in the table are the ones whose scenarios expect the code")


class StatedCounts(unittest.TestCase):
    """Each row is (file, pattern with one number in group 1, name of the quantity). Every match must equal the quantity."""

    def quantities(self):
        embedded = check_embedded_examples(support.schema())
        valid = sum(1 for r in embedded if r.expected_valid)
        return {
            "gateway": len(scenario_entries()),
            "cases": case_count(),
            "valid examples": valid,
            "invalid examples": len(embedded) - valid,
            "embedded examples": len(embedded),
            "instances": len(support.example_model().instances),
            "tests": catalogue_count("evaluation-tests"),
            "baselines": catalogue_count("matched-baselines"),
            "fixtures": catalogue_count("fixtures"),
            "parameters": catalogue_count("domain-parameters"),
        }

    CLAIMS = [
        ("examples/README.md", r"(\d+) stored what-if evaluations", "gateway"),
        ("examples/README.md", r"(\d+) mutated copies", "cases"),
        ("examples/README.md", r"break the story on purpose, (\d+) ways", "cases"),
        ("examples/13-evaluation-cases/README.md", r"\| (\d+) cases\.", "cases"),
        ("schemas/README.md", r"(\d+) valid instances", "valid examples"),
        ("schemas/README.md", r"(\d+) invalid instances", "invalid examples"),
        ("evaluation/README.md", r"(\d+) valid and \d+ invalid embedded examples", "valid examples"),
        ("evaluation/README.md", r"\d+ valid and (\d+) invalid embedded examples", "invalid examples"),
        ("evaluation/README.md", r"the (\d+) embedded examples", "embedded examples"),
        ("evaluation/README.md", r"The (\d+) fixtures of the", "fixtures"),
        ("evaluation/README.md", r"(\d+) tests, \d+ synthetic fixtures, \d+ matched baseline records and \d+ domain parameters", "tests"),
        ("evaluation/README.md", r"\d+ tests, (\d+) synthetic fixtures, \d+ matched baseline records and \d+ domain parameters", "fixtures"),
        ("evaluation/README.md", r"\d+ tests, \d+ synthetic fixtures, (\d+) matched baseline records and \d+ domain parameters", "baselines"),
        ("evaluation/README.md", r"\d+ tests, \d+ synthetic fixtures, \d+ matched baseline records and (\d+) domain parameters", "parameters"),
        ("evaluation/README.md", r"All (\d+) are UNSET", "parameters"),
        ("evaluation/README.md", r"## Preconditions: (\d+) parameters", "parameters"),
        ("architecture/evidence-semantics.md", r"bundle's (\d+) embedded examples", "embedded examples"),
        ("architecture/evidence-semantics.md", r"\((\d+) valid, \d+ invalid\)", "valid examples"),
        ("architecture/evidence-semantics.md", r"\(\d+ valid, (\d+) invalid\)", "invalid examples"),
        ("architecture/evidence-semantics.md", r"and the (\d+) synthetic example instances", "instances"),
        ("evaluation/catalogue/README.md", r"\| Evaluation tests \| (\d+) \|", "tests"),
        ("evaluation/catalogue/README.md", r"\| Matched baselines \| (\d+) \|", "baselines"),
        ("evaluation/catalogue/README.md", r"\| Fixtures \| (\d+) \|", "fixtures"),
        ("evaluation/catalogue/README.md", r"\| Domain parameters \| (\d+) \|", "parameters"),
    ]

    def test_every_stated_count_matches_the_data(self):
        expected = self.quantities()
        wrong = []
        for relative, pattern, name in self.CLAIMS:
            found = re.findall(pattern, text(relative))
            if not found:
                wrong.append("%s: no statement matching %r (was a sentence reworded?)" % (relative, pattern))
            wrong += ["%s: says %s for %s, the data has %d" % (relative, number, name, expected[name]) for number in found if int(number) != expected[name]]
        self.assertEqual(wrong, [])

    def test_the_instance_breakdown_in_the_examples_readme_matches_the_data(self):
        from collections import Counter
        by_contract = Counter(key[0] for key in support.example_model().instances)
        sentence = "The set holds %d contract instances: %d evidence records (C02), %d contexts (C01), %d selections (C03), %d decision packets (C04), %d action proposals (C05), %d grants and approvals (C06) and %d execution receipts (C07)." % (
            sum(by_contract.values()), by_contract["C02"], by_contract["C01"], by_contract["C03"], by_contract["C04"], by_contract["C05"], by_contract["C06"], by_contract["C07"])
        self.assertIn(sentence, text("examples/README.md"))

    def test_the_root_readme_and_changelog_describe_the_repository_as_it_is(self):
        chapters = len(list((REPO / "docs" / "paper").glob("[0-9][0-9]-*.md")))
        contracts = len(list((REPO / "contracts").glob("c0[1-7]-*.md")))
        folders = len([p for p in support.EXAMPLES.iterdir() if p.is_dir()])
        figures = json.loads(text("figures/figures.json"))["figures"]
        q = self.quantities()
        readme, changelog = text("README.md"), text("CHANGELOG.md")
        self.assertIn("%d short chapters" % chapters, readme)
        self.assertIn("%d folders" % folders, readme)
        self.assertIn("%d tests, %d fixtures and %d parameters" % (q["tests"], q["fixtures"], q["parameters"]), readme)
        self.assertIn("%d Markdown chapters" % chapters, changelog)
        self.assertIn("%d [contract pages]" % contracts, changelog)
        self.assertIn("%d folders and %d contract instances" % (folders, q["instances"]), changelog)
        self.assertIn("%d valid and %d invalid embedded examples" % (q["valid examples"], q["invalid examples"]), changelog)
        self.assertIn("%d tests, %d matched baseline records, %d fixtures and %d domain parameters" % (q["tests"], q["baselines"], q["fixtures"], q["parameters"]), changelog)
        self.assertIn("%d figures and a banner" % len(figures), changelog)
        self.assertEqual((chapters, contracts, folders, len(figures)), (15, 7, 13, 11))


class CodeReference(unittest.TestCase):
    """The code table in scripts/README.md must name every code the checks can produce, and no code that does not exist."""

    FAMILIES = r"ID|INP|SCH|REF|LIN|KIND|COR|LIFE|MISS|PKT|AUTH|ACC|DISC|ROLE|RESP|GW|CASE|HYG|STR"

    def codes_in_scripts(self):
        found = set()
        for path in list((REPO / "scripts" / "eahs").glob("*.py")) + [REPO / "scripts" / "validate_examples.py", REPO / "scripts" / "check_hygiene.py", REPO / "scripts" / "check_structure.py"]:
            found |= set(re.findall(r"\b(?:%s)\d{3}\b" % self.FAMILIES, path.read_text(encoding="utf-8")))
        return found

    def codes_in_table(self):
        covered = set()
        section = text("scripts/README.md").split("## Check codes", 1)[1].split("\n## ", 1)[0]
        for line in section.splitlines():
            if not line.startswith("| `"):
                continue
            cell = line.split("|")[1]
            for first, last in re.findall(r"`((?:%s)\d{3})`(?:\u2013`((?:%s)\d{3})`)?" % (self.FAMILIES, self.FAMILIES), cell):
                if last:
                    family, start, end = re.match(r"([A-Z]+)(\d{3})", first).group(1), int(first[-3:]), int(last[-3:])
                    covered |= {"%s%03d" % (family, n) for n in range(start, end + 1)}
                else:
                    covered.add(first)
        return covered

    def test_every_code_the_scripts_can_produce_is_in_the_table(self):
        missing = sorted(self.codes_in_scripts() - self.codes_in_table())
        self.assertEqual(missing, [], "add these codes to the table in scripts/README.md")

    def test_the_table_names_no_code_that_does_not_exist(self):
        invented = sorted(self.codes_in_table() - self.codes_in_scripts())
        self.assertEqual(invented, [])

    def test_the_commit_reason_codes_are_all_explained_in_example_08(self):
        page = text("examples/08-blocked-action/README.md")
        self.assertEqual([c for c in GATE_CODES if "`%s`" % c not in page], [])


class AffiliationDisclosure(unittest.TestCase):
    """One personal-project statement in the README, one Azure neutrality statement on the Azure page, and no statement of an employer."""

    PERSONAL = "This is a personal project, not an official Microsoft publication."
    NEUTRALITY = "Azure is one implementation example of this product-neutral architecture, not a requirement."

    def prose_files(self):
        for path in sorted(REPO.rglob("*")):
            if path.is_file() and ".git" not in path.relative_to(REPO).parts and path.suffix in (".md", ".cff", ".yml"):
                yield path

    def where(self, phrase):
        return [p.relative_to(REPO).as_posix() for p in self.prose_files() if phrase in p.read_text(encoding="utf-8")]

    def test_no_page_states_the_authors_employer(self):
        self.assertEqual(self.where("employed by Microsoft"), [])
        self.assertEqual(self.where("works at Microsoft"), [])
        self.assertEqual(self.where("Microsoft employee"), [])

    def test_the_readme_says_once_that_this_is_a_personal_project(self):
        self.assertEqual(self.where(self.PERSONAL), ["README.md"])
        self.assertEqual(text("README.md").count(self.PERSONAL), 1)

    def test_the_azure_page_says_once_that_azure_is_one_example(self):
        self.assertEqual(self.where(self.NEUTRALITY), ["architecture/azure-implementation-options.md"])
        self.assertEqual(text("architecture/azure-implementation-options.md").count(self.NEUTRALITY), 1)

    def test_the_citation_file_carries_no_employer(self):
        self.assertNotIn("Microsoft", text("CITATION.cff"))
        self.assertNotRegex(text("CITATION.cff"), r"(?im)^\s*affiliation\s*:")

    def test_the_azure_table_names_each_capability_without_a_product_name(self):
        table = text("architecture/azure-implementation-options.md").split("| Capability needed |", 1)[1].split("\n\n", 1)[0]
        rows = [line.split("|")[1].strip() for line in table.splitlines()[2:] if line.startswith("|")]
        self.assertGreaterEqual(len(rows), 8)
        self.assertEqual([r for r in rows if re.search(r"Azure|Microsoft|Foundry|Entra|Purview|Cosmos", r)], [])


class OneVocabulary(unittest.TestCase):
    """Each concept has one name, a list that appears twice is the same list, and no page carries an authoring backlog."""

    def test_no_page_carries_an_authoring_backlog(self):
        banned = ("editorial question", "consistency question", "need an author decision", "known editorial")
        found = []
        for path in sorted(REPO.rglob("*.md")):
            if ".git" in path.parts:
                continue
            body = path.read_text(encoding="utf-8").lower()
            found += [(str(path.relative_to(REPO)), phrase) for phrase in banned if phrase in body]
        self.assertEqual(found, [])

    def test_what_stays_constant_across_domains_is_one_list(self):
        listed = ("the seven contracts, selection and lineage, the controls on information flow, limits on calls, time and spend for the whole task, "
                  "one review interaction, the notification route that does not depend on the assistant, a separate gateway for actions, "
                  "the degraded modes and an assurance plan")
        for page in ("docs/paper/11-costs-and-adaptation.md", "architecture/ownership-and-tradeoffs.md"):
            self.assertIn(listed, text(page), page)

    def test_the_paper_names_the_rejected_alternatives_as_the_register_does(self):
        register = text("architecture/ownership-and-tradeoffs.md").split("## Full tradeoff register", 1)[1]
        names = [line.split("|")[2].strip() for line in register.splitlines() if line.startswith("| ") and not line.startswith(("| Selected", "| ---"))]
        self.assertEqual(len(names), 11)
        chapter = text("docs/paper/11-costs-and-adaptation.md").lower()
        self.assertEqual([name for name in names if name.lower() not in chapter], [])

    def test_the_recovery_owners_in_the_paper_are_the_owners_in_the_failure_table(self):
        table = text("architecture/action-and-degradation.md").split("## Full failure response and recovery ownership", 1)[1]
        owners = [line.split("|")[3] for line in table.splitlines() if line.startswith("| ") and not line.startswith(("| Failure", "| ---"))]
        words = {w.lower() for owner in owners for w in re.split(r"[/ ]", owner) if w and w.lower() != "owner"}
        chapter = text("docs/paper/10-degraded-operation.md")
        sentence = chapter[chapter.index("Recovery belongs to"):].split("\n", 1)[0].lower()
        self.assertGreater(len(words), 8)
        self.assertEqual(sorted(w for w in words if w not in sentence), [])

    def test_the_glossary_defines_the_terms_that_were_ambiguous(self):
        glossary = text("docs/glossary.md")
        for term in ("Approver", "Child task", "Context", "Documentation contract", "Evidence class", "Evidence ledger",
                     "Qualified", "Recovery owner", "Registry (governed)", "Requestor", "`not_executed_verified`"):
            self.assertIn("| **%s** |" % term, glossary, term)

    def test_the_requestor_and_the_approver_are_never_one_field(self):
        schema = support.schema()
        context, delegation = json.dumps(schema["$defs"]["context"]), json.dumps(schema["$defs"]["delegation"])
        self.assertIn('"requesting_principal"', context)
        self.assertIn('"issuer"', delegation)
        self.assertNotIn('"requesting_principal"', delegation)
        self.assertNotIn('"issuer"', context)


class RetiredWording(unittest.TestCase):
    """Wording that was removed on purpose stays removed. The change records name some of it, so they are exempt."""

    RETIRED = (
        "Author's architecture specification",
        "supplementary assets",
        "illustration is removable",
        "evaluation workbook",
        "convenience ratios",
        "Disclosure and publication requirements of a venue",
        "ends where accountability begins",
        "employed by Microsoft",
        "Systems produce evidence. AI makes it consumable",
        "architecture proposition",
        "No evaluation has been run",
        "no independent human review is recorded",
        "accountable approver",
        "Reviewer navigation",
        "reviewer-navigation",
        "a governed context",
        "context and attention",
        "Complexity must earn its place",
        "Adapt the domain, not the architecture",
        "Why more output, compression and automation",
        "standing grant",
        "standing class",
        "documentation only",
        "method/actor/time/scope",
    )
    EXEMPT = ("CHANGELOG.md", "contracts/CHANGES.md")

    def scanned(self):
        for path in sorted(REPO.rglob("*")):
            relative = path.relative_to(REPO).as_posix()
            if not path.is_file() or ".git" in path.relative_to(REPO).parts or relative.startswith("tests/") or relative in self.EXEMPT:
                continue
            if path.suffix in (".md", ".json", ".py", ".cff", ".yml", ".csv", ".svg", ".txt"):
                yield relative, path.read_text(encoding="utf-8")

    def test_no_retired_wording_returns(self):
        found = []
        for relative, body in self.scanned():
            found += [(relative, phrase) for phrase in self.RETIRED if phrase.lower() in body.lower()]
        self.assertEqual(found, [])

    def test_each_role_has_one_name(self):
        # The roles are "requestor" and "Decision Owner" in every page, message and data file.
        found = []
        for relative, body in self.scanned():
            found += [(relative, "requester") for _ in re.finditer("requester", body, re.I)][:1]
            found += [(relative, "decision owner") for _ in re.finditer("decision owner", body)][:1]
        self.assertEqual(found, [])


class EngagementWithoutScale(unittest.TestCase):
    """The engagement is described by what it showed and by its limits, not by its scale.

    The two pages that describe it state no count of agents, vessels, records or values, and no ratio. The test cannot know which
    numbers would be private, so it allows only dates, identifiers and the numbers of headings and observations, and no number
    word attached to something that is counted.
    """

    PAGES = ("docs/paper/02-engagement.md", "references/engagement-records.md")
    MONTH = r"(?:January|February|March|April|May|June|July|August|September|October|November|December)"
    NUMBER_WORD = r"(?:one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|dozens?|hundreds?|thousands?)"
    COUNTED = r"(?:agents?|specialists?|vessels?|boats?|records?|values?|controls?|cases?|licen[cs]es?|landings?)"

    def prose(self, page):
        body = text(page)
        body = re.sub(r"^\[\u2190.*$", "", body, flags=re.M)  # the navigation line
        body = re.sub(r"\]\([^)]*\)", "]", body)  # link targets
        body = re.sub(r"\b[A-Z]{1,3}\d{2,3}\b", "", body)  # identifiers such as EN01, IN04, C02, EV12, RG01
        body = re.sub(r"\b\d{1,2} %s \d{4}\b|\b%s \d{4}\b" % (self.MONTH, self.MONTH), "", body)  # dates
        body = re.sub(r"^#+ \d+\. ", "", body, flags=re.M)  # numbered headings
        return re.sub(r"\b(?:observations? \d+(?:, \d+)*(?: and \d+)?|chapter \d+)\b", "", body)

    def test_the_pages_state_no_figure_beyond_dates_and_identifiers(self):
        for page in self.PAGES:
            self.assertEqual(re.findall(r"\d+", self.prose(page)), [], page)

    def test_the_pages_count_nothing_in_words_either(self):
        counted = re.compile(r"\b%s\b(?:\s+[\w-]+){0,2}?\s+%s\b" % (self.NUMBER_WORD, self.COUNTED), re.I)
        for page in self.PAGES:
            self.assertEqual([m.group(0) for m in counted.finditer(self.prose(page))], [], page)

    def test_the_check_notices_what_it_is_for(self):
        counted = re.compile(r"\b%s\b(?:\s+[\w-]+){0,2}?\s+%s\b" % (self.NUMBER_WORD, self.COUNTED), re.I)
        for sentence in ("The test covered eleven proposed agents.", "Nine autonomous agents were tested.", "Only ten carry case records.", "Twelve such values came from controls."):
            self.assertTrue(counted.search(sentence), sentence)
        for sentence in ("Eight observations shaped the design.", "A ten-minute status window.", "One internal test within a single case-based engagement."):
            self.assertFalse(counted.search(sentence), sentence)


def excerpt_differences(excerpt, actual, path="$"):
    """Where `excerpt` says something `actual` does not. A list may show only its first items, and "…" matches anything."""
    if excerpt == "…":
        return []
    if isinstance(excerpt, dict):
        if not isinstance(actual, dict):
            return [path]
        found = []
        for key, value in excerpt.items():
            found += [path + "." + key] if key not in actual else excerpt_differences(value, actual[key], path + "." + key)
        return found
    if isinstance(excerpt, list):
        if not isinstance(actual, list) or len(excerpt) > len(actual):
            return [path]
        return [d for i, value in enumerate(excerpt) for d in excerpt_differences(value, actual[i], "%s[%d]" % (path, i))]
    return [] if excerpt == actual else [path]


class ContractPageExcerpts(unittest.TestCase):
    PAGE = "contracts/c06-delegation.md"

    def test_the_c06_page_names_every_commit_reason_code(self):
        self.assertEqual([c for c in GATE_CODES if "`%s`" % c not in text(self.PAGE)], [])

    def test_the_abridged_c06_instance_is_an_excerpt_of_the_real_file(self):
        block = re.search(r"```json\n(.*?)\n```", text(self.PAGE), re.S)
        self.assertIsNotNone(block, "the page has lost its abridged instance")
        excerpt = json.loads(block.group(1))
        actual = json.loads(text("examples/07-authority-and-delegation/c06-GRT-APPR-0417-A-v1.json"))
        self.assertEqual(excerpt_differences(excerpt, actual), [])

    def test_the_excerpt_check_notices_a_changed_value(self):
        self.assertEqual(excerpt_differences({"a": {"b": 1}}, {"a": {"b": 2}}), ["$.a.b"])
        self.assertEqual(excerpt_differences({"a": ["…"]}, {"a": [1, 2]}), [])
        self.assertEqual(excerpt_differences({"a": [1, 2, 3]}, {"a": [1, 2]}), ["$.a"])


if __name__ == "__main__":
    unittest.main()
