# Changelog

Release candidates are labeled `v1.0.0-rc.N`. The label `v1.0.0` is reserved for an edition the author has accepted as final; nothing here is that yet.

## 1.0.0-rc.1: release candidate 1, 23 November 2026

The first version of this repository. It is offered for review and is not a final release.

### What it contains

- **The paper**: 15 Markdown chapters, from the overview to "Start with one decision, not a platform", with the glossary, [claims and limits](docs/claims-and-limits.md) and an [implementation guide](docs/implementation-guide.md). The [glossary](docs/glossary.md) gives one name to each concept and keeps legitimate variants apart, such as the three senses of "context".
- **The technical reference**: the [architecture reference](architecture/README.md) and 7 [contract pages](contracts/README.md), C01–C07, preserving all 41 field groups.
- **A schema bundle**: [`schemas/contracts-v1.schema.json`](schemas/contracts-v1.schema.json), a documentation-only JSON Schema (Draft 2020-12) with 38 valid and 64 invalid embedded examples. The [contract change record](contracts/CHANGES.md) pins its validation surface and says how a change to it is recorded.
- **A synthetic worked example**: 13 folders and 37 contract instances telling one invented supplier-payment story, with raw exports, a registry, stored gateway evaluations and an assistant response, and a validation command that is tested on Windows and Linux.
- **Evaluation guidance**: the [evaluation guide](evaluation/README.md), the oracles, human-outcome guidance and a catalogue of 12 tests, 12 matched baseline records, 70 fixtures and 47 domain parameters. Every status is NOT RUN or UNSET.
- **A figure set**: 11 figures and a banner, each with a caption, alt text and a text description. All are drawn SVGs, in light and dark, 360 px wide so that a phone shows them at their natural size; F02 and the banner also have a wide drawing for a large screen. F07 is drawn from a table, which is also given as text.
- **Tooling**: [`scripts/check_all.py`](scripts/check_all.py) and the checks behind it (examples, unit tests, link and anchor check, page-structure check, figure and hygiene checks), an optional external-URL check, and a GitHub Actions workflow that runs them on Ubuntu and Windows.

### Known limitations of this release candidate

- **No license has been chosen.** The repository carries no `LICENSE` file, and no permission beyond GitHub's Terms of Service is granted. The author decides.
- **No evaluation has been run.** EV01–EV12, the 70 fixtures and the 12 matched baseline records are NOT RUN; the 47 domain parameters are UNSET. The repository's own checks are deterministic checks on invented data and say nothing about a real system.
- **The paper is Markdown only.** No PDF or Word edition is included in this release candidate.
- **Accessibility has not been audited.** Every figure has alt text and a text description, and colors are always paired with a text label, but no screen-reader test, WCAG audit or PDF/UA check has been performed: NOT ASSESSED.
- **The figures were checked in one browser.** Each figure is drawn 360 px wide with no text below 13 px, and its text fits in Segoe UI, Arial and Verdana. That was measured in a desktop browser, in a phone-sized window and in a laptop-sized one. It has not been tried on a physical phone or on GitHub itself. The switch to the wide drawing of F02 and the banner depends on the `media` attribute of a `<source>` element; where a page does not apply it, the narrow drawing is shown, and says the same.
- **Reviews were AI-assisted.** No independent human review of the text is recorded here.
- **Product statements are dated.** Statements about Azure options carry their verification date, 17 November 2026, and may be out of date. Links to public records can move.
- **The example is one domain.** The supplier-payment story is invented to need no specialist knowledge. It shows the contracts at work; it is not evidence that the architecture works.

[Claims and limits](docs/claims-and-limits.md) · [README](README.md)
