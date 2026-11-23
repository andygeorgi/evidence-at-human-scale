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
        ("evaluation/README.md", r"All (\d+) are \*\*UNSET\*\*", "parameters"),
        ("evaluation/README.md", r"## Preconditions: (\d+) parameters", "parameters"),
        ("evaluation/oracles.md", r"lists the (\d+) tests", "tests"),
        ("evaluation/oracles.md", r"the (\d+) matched baseline records", "baselines"),
        ("evaluation/oracles.md", r"the (\d+) concrete synthetic fixtures", "fixtures"),
        ("evaluation/oracles.md", r"the (\d+) unresolved domain parameters", "parameters"),
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

    def test_the_editorial_questions_are_counted_the_same_everywhere(self):
        table = text("CHANGELOG.md").split("## Known editorial questions", 1)[1]
        rows = [line for line in table.splitlines() if re.match(r"\| \d+ \|", line)]
        open_rows = [line for line in rows if line.rstrip().endswith("| Open |")]
        self.assertEqual((len(rows), len(open_rows)), (19, 16))
        self.assertIn("found %d older consistency questions" % len(rows), text("CHANGELOG.md"))
        self.assertIn("Sixteen are still open", text("CHANGELOG.md"))
        self.assertIn("Nineteen older consistency questions need an author decision rather than editing; %d are still open" % len(open_rows), text("README.md"))

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

    FAMILIES = r"SCH|REF|LIN|KIND|COR|LIFE|MISS|PKT|AUTH|ACC|DISC|RESP|GW|CASE|HYG|STR"

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


if __name__ == "__main__":
    unittest.main()
