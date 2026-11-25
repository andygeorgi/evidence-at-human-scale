# Changelog

Releases are labeled `vMAJOR.MINOR.PATCH` and tagged in Git. Each entry lists what the release contains.

## 1.0.4, 25 November 2026

A reader-facing cleanup. Nothing functional changed: the contracts, the schema, the examples, the figures, the checks and the evaluation statuses are exactly as in 1.0.3.

### What changed

- **No "AI assistance" section in the README.** The section is removed, together with the pointers to it.
- **Example 05 names no version.** The sentence about what its claim check leaves out is now version-neutral.

### Known limitations

The standing claims and limits are on the [claims and limits](docs/claims-and-limits.md) page.

## 1.0.3, 25 November 2026

A reader-experience patch. The contracts, the schema, the examples, the checks and the evaluation statuses are unchanged, so every check gives the same result as in 1.0.2.

### What changed

- **The reading path no longer explains how the repository is built.** The figures page lists each figure with its caption and description and no longer describes how the pictures are drawn and rebuilt. The pages that show a figure carry no generation note and no link to the wide drawing, the description of the architecture overview no longer says how its drawing adapts to the width of a screen, and the guides no longer repeat the platforms and Python versions the checks run on.
- **Maintainer notes are on one page.** The generated files, the checks, the hygiene scan and the steps of a release are in `docs/maintainers.md`, which no reading path links to. The [contributing guide](CONTRIBUTING.md) keeps what a contributor needs: setup, the required checks, how to change examples and figures safely, and the rules.
- **Shorter reference pages.** The scripts guide, the evaluation guide's table of repository checks and this changelog say what a reader needs and leave the implementation detail to the scripts and the tests.

### Known limitations

The standing claims and limits are on the [claims and limits](docs/claims-and-limits.md) page.

## 1.0.2, 25 November 2026

A corrective release. The contracts and the validation surface of the schema are unchanged, so everything that validated against 1.0.1 still validates.

### What changed

- **The commit check is time-consistent.** At commit, the reference gateway uses only what was available at the attempt. Evidence admitted after the attempt and a "not revoked" check made after it can no longer authorize it, and a time that is missing, unknown or cannot be compared exactly blocks. Only the capacity the ledger held by the attempt counts, a cancelled or failed attempt keeps its capacity until its verification, amounts are compared exactly as written, and anything the check cannot read blocks with a reason instead of passing or ending in an error. Business time, admission time, freshness, lifecycle state and the time of the revocation check are kept apart. Five reason codes were added (21 in all), each with a stored evaluation.
- **Every input is evaluated or rejected.** A contract id that is not a string or names no contract, a file named like a contract that is not one, and a stage file without its `evaluations`, `cases` or `statements` collection each end in a diagnostic that names the file, the stage, the problem and what to do. An explicit empty collection is reported as such, a schema-only run no longer indexes the folder, and unrelated raw exports stay usable. JSON is read strictly (`NaN`, `Infinity`, a repeated key, a number a double cannot hold and a document nested more than 40 levels are input errors). Nothing disappears silently.
- **A response cannot define its own lifecycle.** Whether a response is `current` or `withdrawn` comes from its packet and its as-of time, and a withdrawn response carries the packet's own reason. A response about an invalidated packet that says it is current, omits its status or words withdrawn advice as current now fails. A free-form response must state at least half of the packet's supported claims, and its status words, figures, currencies, record identifiers and labels are checked in every kind of statement. These are mechanical checks, not a judgment of meaning.
- **What a reader may not know cannot change what they see.** The viewer's output is built from the inputs the permission decision allows, after the decision is bound to the requesting principal, tenant and purpose. A reader who may know only that coverage is limited receives exactly the configured wording. This is snapshot validation and a reference projection, not an authorization service.
- **A claim is held to every reference.** A supported claim that cites a payload or several references is compared with all of them: it states the payload's status and its figures, each beside the right field name and none beside a field it does not cite, and nothing the payload does not hold. A model inference may not state a figure its ancestry does not hold.
- **The executor holds the authority.** The assistant proposes, and the payment executor is the grantee of every grant and the executor of every receipt. A receipt under another principal's grant fails.
- **Verified no effect is scoped.** A rejection before submission, a verified no effect for one attempt, target and scope, and an unknown outcome are three different things, in the example, the figures and the guidance. A gateway rejection alone is not proof about every external effect.
- **Teaching examples.** The two AI summaries no longer state a figure or a comparison that their ancestry does not hold, and a generated "retrieved retrieved" was fixed.
- **A calmer first read.** The README starts with the title, the problem, the architecture's response and one next step, with no version code or status block, and the banner follows the first paragraph so that a narrow screen meets the words first. The banner and the figures that led with codes now lead with the concept, and the paper and guides name a thing before its identifier. The receipt figure no longer calls four outcomes the only receipt states, the late-correction figure queues the release under the approval, and a missing gap says that nothing was found in the sources that were read and not that nothing exists. Identifiers stay in the JSON, the schema, the diagnostic codes and the reference tables, and links to the sections of 1.0.1 that were renamed still land.

### Known limitations

The standing claims and limits are on the [claims and limits](docs/claims-and-limits.md) page. The checks added in this release are mechanical: the permission-bound output is a reference projection and not an authorization service, and the response checks do not show that prose means what its packet means.

## 1.0.1, 24 November 2026

A corrective release. The contracts and the validation surface of the schema are unchanged, so everything that validated against 1.0.0 still validates.

### What changed

- **Validator correctness.** `validate_examples.py` reports five states: PASS, FAIL, SKIPPED, NOT ASSESSED and INPUT ERROR. A stage passes only if it evaluated something, so an empty examples folder, an empty example or a skipped stage is no longer a PASS. A malformed document produces a diagnostic with a fix instead of a traceback, and a stage that needs another stage says so. A run that leaves stages out ends with `PASS for the stages that ran` and says that its result says nothing about the skipped ones, and `check_all.py` does the same. A duplicated schema diagnostic was removed. The response validator now separates canonical validation, which compares a response with what its renderer produces and catches reversed meaning, from structural free-text validation, which checks named constraints and does not prove the prose is correct.
- **Corrected authorization and role semantics.** Permission is decided before anything about an input is disclosed, so a requestor who may not know that a restricted record exists cannot learn that it exists, is stale or was checked. Figure F09, example 04, the contract text and the guidance say so, and tests show that nothing leaks. The worked example keeps the requestor, the Decision Owner, the approver and the executor apart, and records that the controller holds two of the roles because the policy allows it. The packet is reviewed before the first approval, and the timeline says what was visible when.
- **Clearer onboarding.** The README starts from one invoice problem, puts the Quickstart before the architecture and offers a ten-minute path. The contract pages explain that the JSON examples are self-contained snapshots, why they repeat the metadata of the records they cite, and where the compact human view is.
- **Removal of internal and redundant material.** The evaluation catalogue no longer repeats constant, duplicated or process text. Its JSON files are the source; the CSV files and the test sections of the oracles page are generated from them, and each fixture lists the contracts it actually uses. Internal-process wording and obsolete repository attributes were removed.
- **Corrected evaluation claims.** The statement that no evaluation has been run was too broad. The contracts and synthetic examples are tested, and real-world effectiveness has not been evaluated. The evaluation tests, fixtures and baselines now use five defined states (RUN / PASS, RUN / FAIL, NOT RUN, NOT ASSESSED, UNSET). All twelve tests were reviewed: none can be run without an implementation, so all are NOT ASSESSED, where 1.0.0 listed them as NOT RUN. A row cannot claim a run without its command, input and output.
- **Prose and terminology.** Slogans, slash-heavy phrases and repeated qualifiers were rewritten, and several chapter titles now describe their subject instead of making a point. "Approver" replaces "accountable approver", the page that maps questions to chapters is now called the question index, and Figure F02 now shows that an approval and a grant are both recorded in C06 and what the gateway rechecks at commit.

### Known limitations

- **Real-world effectiveness has not been evaluated.** The 12 tests, 70 fixtures and 12 matched baseline records are NOT ASSESSED, and the 47 domain parameters are UNSET. No test was run in this release.
- **Accessibility has not been formally assessed.** The automated figure checks are not an accessibility assessment, and usability on a phone was not tested with people or devices. No screen-reader test, WCAG audit or PDF/UA check has been performed and no conformance is claimed: NOT ASSESSED.
- **The limitations listed for 1.0.0 otherwise still apply:** the paper is Markdown only, product statements are dated, and the example is one invented domain.

## 1.0.0, 24 November 2026

The first public release of this repository, under the [MIT License](LICENSE).

### What it contains

- **The paper**: 15 Markdown chapters, from the overview to "Start with one decision, not a platform", with the glossary, [claims and limits](docs/claims-and-limits.md) and an [implementation guide](docs/implementation-guide.md). The [glossary](docs/glossary.md) gives one name to each concept and keeps legitimate variants apart, such as the three senses of "context".
- **The technical reference**: the [architecture reference](architecture/README.md) and 7 [contract pages](contracts/README.md), C01–C07, preserving all 41 field groups.
- **A schema bundle**: [`schemas/contracts-v1.schema.json`](schemas/contracts-v1.schema.json), a documentation-only JSON Schema (Draft 2020-12) with 38 valid and 64 invalid embedded examples. The [contract change record](contracts/CHANGES.md) pins its validation surface and says how a change to it is recorded.
- **A synthetic worked example**: 13 folders and 37 contract instances telling one invented supplier-payment story, with raw exports, a registry, stored gateway evaluations and an assistant response, and a validation command.
- **Evaluation guidance**: the [evaluation guide](evaluation/README.md), the oracles, human-outcome guidance and a catalogue of 12 tests, 12 matched baseline records, 70 fixtures and 47 domain parameters. Every status is NOT RUN or UNSET.
- **A figure set**: 11 figures and a banner, each with a caption, alt text and a text description, in light and dark.
- **Tooling**: the validation command and the repository checks behind [`scripts/check_all.py`](scripts/check_all.py), with an optional external-URL check and a GitHub Actions workflow that runs them.
- **A license**: the [MIT License](LICENSE) covers the whole repository: the paper and other text, figures, schemas, contracts, examples, scripts and tests.

### Known limitations

- **No evaluation has been run.** EV01–EV12, the 70 fixtures and the 12 matched baseline records are NOT RUN; the 47 domain parameters are UNSET. The repository's own checks are deterministic checks on invented data and say nothing about a real system.
- **The paper is Markdown only.** No PDF or Word edition is included in this release.
- **Accessibility has not been formally assessed.** Practical structural and visual checks were performed: every figure has alt text and a text description, every page has one H1 and no skipped heading level, and colors are always paired with a text label. No screen-reader test, WCAG audit or PDF/UA check has been performed and no conformance is claimed: NOT ASSESSED.
- **Product statements are dated.** Statements about Azure options carry their verification date, 17 November 2026, and may be out of date. Links to public records can move.
- **The example is one domain.** The supplier-payment story is invented to need no specialist knowledge. It shows the contracts at work; it is not evidence that the architecture works.

[Claims and limits](docs/claims-and-limits.md) · [README](README.md)
