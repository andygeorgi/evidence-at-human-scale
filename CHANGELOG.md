# Changelog

Release candidates are labeled `v1.0.0-rc.N`. The label `v1.0.0` is reserved for an edition the author has accepted as final; nothing here is that yet.

## 1.0.0-rc.1: release candidate 1, 23 November 2026

The first version of this repository. It is offered for review and is not a final release.

### What it contains

- **The paper**: 15 Markdown chapters, from the overview to "Start with one decision, not a platform", with the glossary, [claims and limits](docs/claims-and-limits.md) and an [implementation guide](docs/implementation-guide.md).
- **The technical reference**: the [architecture reference](architecture/README.md) and 7 [contract pages](contracts/README.md), C01–C07, preserving all 41 field groups.
- **A schema bundle**: [`schemas/contracts-v1.schema.json`](schemas/contracts-v1.schema.json), a documentation-only JSON Schema (Draft 2020-12) with 38 valid and 64 invalid embedded examples. [What changed from earlier forms](contracts/CHANGES.md): identity and annotations only; what validates did not change.
- **A synthetic worked example**: 13 folders and 37 contract instances telling one invented supplier-payment story, with raw exports, a registry, stored gateway evaluations and an assistant response, and a validation command that runs the same on Windows, macOS and Linux.
- **Evaluation guidance**: the [evaluation guide](evaluation/README.md), the oracles, human-outcome guidance and a catalogue of 12 tests, 12 matched baseline records, 70 fixtures and 47 domain parameters. Every status is NOT RUN or UNSET.
- **A figure set**: 11 figures and a banner, each with a caption, alt text and a text description, in light and dark variants, with their sources.
- **Tooling**: [`scripts/check_all.py`](scripts/check_all.py) and the checks behind it (examples, unit tests, link and anchor check, page-structure check, figure and hygiene checks), an optional external-URL check, and a GitHub Actions workflow that runs them on Ubuntu and Windows.

### Known limitations of this release candidate

- **No license has been chosen.** The repository carries no `LICENSE` file, and no permission beyond GitHub's Terms of Service is granted. The author decides.
- **No evaluation has been run.** EV01–EV12, the 70 fixtures and the 12 matched baseline records are NOT RUN; the 47 domain parameters are UNSET. The repository's own checks are deterministic checks on invented data and say nothing about a real system.
- **The paper is Markdown only.** No PDF or Word edition is included in this release candidate.
- **Accessibility has not been audited.** Every figure has alt text and a text description, and colors are always paired with a text label, but no screen-reader test, WCAG audit or PDF/UA check has been performed: NOT ASSESSED.
- **Some figures are wide.** F02, F04, F06 and the banner are drawn 1,000 to 1,280 pixels wide; on a narrow screen, tap a figure to open it full size, or read its text description.
- **Reviews were AI-assisted.** No independent human review of the text is recorded here.
- **Product statements are dated.** Statements about Azure options carry their verification date, 17 November 2026, and may be out of date. Links to public records can move.
- **The example is one domain.** The supplier-payment story is invented to need no specialist knowledge. It shows the contracts at work; it is not evidence that the architecture works.

## Known editorial questions

A readability review of release candidate 1's Word and PDF editions, done by an AI assistant and not an independent human reviewer, found 19 older consistency questions that need an author decision rather than rewording. They are carried over here **unresolved**, except where a status says otherwise, so that reviewers can see them; resolving them is the author's decision. Where a question mentions "the appendix", read the technical reference in [`architecture/`](architecture/README.md) and [`contracts/`](contracts/README.md).

| # | Question | Status in this repository |
|---|---|---|
| 1 | Is "documentation contracts" the clearest name for C01–C07? | Open |
| 2 | "Context" carries three meanings. Should they be named separately? | Open |
| 3 | "Ledger", "registry" and "ProducerRegistry" are used for related things. Are they one concept or several? | Open |
| 4 | The phrase "per child", as in "independent per-child spending" ([chapter 11](docs/paper/11-costs-and-adaptation.md)). | Open |
| 5 | The phrase "qualified information". | Open |
| 6 | Are the requestor and the accountable approver one role or two? | Open |
| 7 | The phrase "assistant-mediated admission". | Open |
| 8 | `not_assessed` (a value) and NOT ASSESSED (a status) appear together in one paragraph. | Open |
| 9 | Prose says "verified no-effect"; the receipt value is `not_executed_verified`. Should one name be used? | Open |
| 10 | The lineage trace lines had no legend. | Addressed by the redesign: figure F03 labels each relationship and has a text description. |
| 11 | The schema's URN namespace and the words "preserved source receipts". | Partly addressed: the schema bundle has a new identifier ([change record](contracts/CHANGES.md)), and the Markdown no longer contains the phrase. |
| 12 | A section mixes checks on the documents with evaluation. | Partly addressed: the [evaluation guide](evaluation/README.md) separates the repository's own checks from the unrun EV01–EV12 programme. The architecture text is unchanged. |
| 13 | The sentence on "separate evidence classes" was kept on purpose, as an evidence boundary. Should it be reworded? | Open |
| 14 | What stays constant across domains is listed with seven items in the paper and eight in the technical reference. | Open |
| 15 | The rejected alternatives are named differently in different places. | Open |
| 16 | How strongly does an unresolved parameter block a decision? | Open |
| 17 | "Can block" and "blocks" are both used. | Open |
| 18 | The lists of recovery roles differ between places. | Open |
| 19 | The flow of the paper after [Budget the whole task](docs/paper/11-costs-and-adaptation.md#budget-the-whole-task). | Open |

[Claims and limits](docs/claims-and-limits.md) · [README](README.md)
