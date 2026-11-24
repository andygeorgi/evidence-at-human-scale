# Changelog

Releases are labeled `vMAJOR.MINOR.PATCH` and tagged in Git. Each entry lists what the release contains and its known limitations.

## 1.0.1, 24 November 2026

A corrective release. The contracts and the validation surface of the schema are unchanged, so everything that validated against 1.0.0 still validates.

### What changed

- **Validator correctness.** `validate_examples.py` reports five states: PASS, FAIL, SKIPPED, NOT ASSESSED and INPUT ERROR. A stage passes only if it evaluated something, so an empty examples folder, an empty example or a skipped stage is no longer a PASS. A malformed document produces a diagnostic with a fix instead of a traceback, and a stage that needs another stage says so. A duplicated schema diagnostic was removed. The response validator now separates canonical validation, which compares a response with what its renderer produces and catches reversed meaning, from structural free-text validation, which checks named constraints and does not prove the prose is correct.
- **Corrected authorization and role semantics.** Permission is decided before anything about an input is disclosed, so a requester who may not know that a restricted record exists cannot learn that it exists, is stale or was checked. Figure F09, example 04, the contract text and the guidance say so, and tests show that nothing leaks. The worked example keeps the requestor, the Decision Owner, the approver and the executor apart, and records that the controller holds two of the roles because the policy allows it. The packet is reviewed before the first approval, and the timeline says what was visible when.
- **Clearer onboarding.** The README starts from one invoice problem, puts the Quickstart before the architecture and offers a ten-minute path. The contract pages explain that the JSON examples are self-contained snapshots, why they repeat the metadata of the records they cite, and where the compact human view is.
- **Removal of internal and redundant material.** The evaluation catalogue no longer repeats constant, duplicated or process text. Its JSON files are the source; the CSV files and the test sections of the oracles page are generated from them, and each fixture lists the contracts it actually uses. Internal-process wording and obsolete repository attributes were removed.
- **Corrected evaluation claims.** The statement that no evaluation has been run was too broad. The contracts and synthetic examples are tested, and real-world effectiveness has not been evaluated. The evaluation tests, fixtures and baselines now use five defined states (RUN / PASS, RUN / FAIL, NOT RUN, NOT ASSESSED, UNSET). All twelve tests were reviewed: none can be run without an implementation, so all are NOT ASSESSED, where 1.0.0 listed them as NOT RUN. A row cannot claim a run without its command, input and output.
- **Prose and terminology.** Slogans, slash-heavy phrases and repeated qualifiers were rewritten. "Approver" replaces "accountable approver", the question index replaces the reviewer navigation page, and Figure F02 now shows that an approval and a grant are both recorded in C06 and what the gateway rechecks at commit.

### Known limitations

- **Real-world effectiveness has not been evaluated.** The 12 tests, 70 fixtures and 12 matched baseline records are NOT ASSESSED, and the 47 domain parameters are UNSET. No test was run in this release.
- **Accessibility has not been formally assessed.** The automated figure checks are not an accessibility assessment, and usability on a phone was not tested with people or devices. No screen-reader test, WCAG audit or PDF/UA check has been performed and no conformance is claimed: NOT ASSESSED.
- **The limitations listed for 1.0.0 otherwise still apply:** the paper is Markdown only, the figures were checked in one browser, product statements are dated, and the example is one invented domain.

## 1.0.0, 24 November 2026

The first public release of this repository, under the [MIT License](LICENSE).

### What it contains

- **The paper**: 15 Markdown chapters, from the overview to "Start with one decision, not a platform", with the glossary, [claims and limits](docs/claims-and-limits.md) and an [implementation guide](docs/implementation-guide.md). The [glossary](docs/glossary.md) gives one name to each concept and keeps legitimate variants apart, such as the three senses of "context".
- **The technical reference**: the [architecture reference](architecture/README.md) and 7 [contract pages](contracts/README.md), C01–C07, preserving all 41 field groups.
- **A schema bundle**: [`schemas/contracts-v1.schema.json`](schemas/contracts-v1.schema.json), a documentation-only JSON Schema (Draft 2020-12) with 38 valid and 64 invalid embedded examples. The [contract change record](contracts/CHANGES.md) pins its validation surface and says how a change to it is recorded.
- **A synthetic worked example**: 13 folders and 37 contract instances telling one invented supplier-payment story, with raw exports, a registry, stored gateway evaluations and an assistant response, and a validation command that is tested on Windows and Linux.
- **Evaluation guidance**: the [evaluation guide](evaluation/README.md), the oracles, human-outcome guidance and a catalogue of 12 tests, 12 matched baseline records, 70 fixtures and 47 domain parameters. Every status is NOT RUN or UNSET.
- **A figure set**: 11 figures and a banner, each with a caption, alt text and a text description. All are drawn SVGs, in light and dark, 360 px wide so that a phone shows them at their natural size; F02 and the banner also have a wide drawing for a large screen. F07 is drawn from a table, which is also given as text.
- **Tooling**: [`scripts/check_all.py`](scripts/check_all.py) and the checks behind it (examples, unit tests, link and anchor check, page-structure check, figure and hygiene checks), a hygiene scan that can also read the whole Git history and that lets the authority's name appear only on the exact lines that quote a public record's own title or address, an optional external-URL check, and a GitHub Actions workflow that runs them on Ubuntu and Windows.
- **A license**: the [MIT License](LICENSE) covers the whole repository: the paper and other text, figures, schemas, contracts, examples, scripts and tests.

### Known limitations

- **No evaluation has been run.** EV01–EV12, the 70 fixtures and the 12 matched baseline records are NOT RUN; the 47 domain parameters are UNSET. The repository's own checks are deterministic checks on invented data and say nothing about a real system.
- **The paper is Markdown only.** No PDF or Word edition is included in this release.
- **Accessibility has not been formally assessed.** Practical structural and visual checks were performed: every figure has alt text and a text description, every page has one H1 and no skipped heading level, and colors are always paired with a text label. No screen-reader test, WCAG audit or PDF/UA check has been performed and no conformance is claimed: NOT ASSESSED.
- **The figures were checked in one browser.** Each figure is drawn 360 px wide with no text below 13 px, and its text fits in Segoe UI, Arial and Verdana. That was measured in a desktop browser, in a phone-sized window and in a laptop-sized one, on the pages as GitHub renders them and with GitHub's own script for light and dark themes. It has not been tried on a physical phone or in a signed-in GitHub browser session. The switch to the wide drawing of F02 and the banner depends on the `media` attribute of a `<source>` element; where a page does not apply it, the narrow drawing is shown, and says the same. A reader whose GitHub theme differs from the color scheme of their system may see the wide drawing in the other scheme; it stays legible.
- **Product statements are dated.** Statements about Azure options carry their verification date, 17 November 2026, and may be out of date. Links to public records can move.
- **The example is one domain.** The supplier-payment story is invented to need no specialist knowledge. It shows the contracts at work; it is not evidence that the architecture works.

[Claims and limits](docs/claims-and-limits.md) · [README](README.md)
