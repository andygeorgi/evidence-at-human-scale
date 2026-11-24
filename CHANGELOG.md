# Changelog

Releases are labeled `vMAJOR.MINOR.PATCH` and tagged in Git. Each entry lists what the release contains and its known limitations.

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
