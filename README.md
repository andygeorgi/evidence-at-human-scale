<!-- banner:start -->
<p align="center">
<picture>
<source media="(min-width: 900px) and (prefers-color-scheme:dark)" srcset="figures/banner-wide-dark.svg">
<source media="(min-width: 900px)" srcset="figures/banner-wide-light.svg">
<source media="(prefers-color-scheme: dark)" srcset="figures/banner-dark.svg">
<img src="figures/banner-light.svg" alt="Evidence at Human Scale. Systems produce evidence, AI makes it consumable, people remain accountable. Evidence is not inference, not recommendation, not authority.">
</picture>
</p>
<!-- banner:end -->

# Evidence at Human Scale

**Reference architecture for accountable decisions in agentic systems**

> **Systems produce evidence. AI makes it consumable. People remain accountable.**

*Release candidate 1 (`v1.0.0-rc.1`), 23 November 2026. Offered for review; not a final release. No license has been chosen yet: see [License](#license).*

Agentic systems can produce information faster than people can attend to it. More agents can create more interpretations, and more summaries can merely move the bottleneck. This repository proposes a different unit of design: a **governed decision context**, not an agent hierarchy. Authorized, attributable outputs are selected for a defined task, synthesized within limits and released as a versioned **decision packet** that the accountable person can inspect and challenge. Mandatory obligations and consequential execution keep their own independent paths.

It is an architecture proposition, not a deployment or a benefit claim. **No evaluation has been run.** [Status and limits](#status-and-limits) says exactly what that means.

## What is here

| Goal | Where |
|---|---|
| **Read** | [The paper](docs/paper/README.md): 15 short chapters, from the problem to "start with one decision, not a platform". |
| **Check the detail** | [Architecture reference](architecture/README.md) · [seven contracts](contracts/README.md) · [JSON Schema bundle](schemas/README.md). |
| **Run** | [Examples](examples/README.md): one invented supplier-payment story in 13 folders, and a command that validates it. |
| **Evaluate** | [Evaluation guide](evaluation/README.md): 12 tests, 70 fixtures and 47 parameters, defined, and all NOT RUN or UNSET. |
| **Build** | [Implementation guide](docs/implementation-guide.md). |
| **See** | [Figures](figures/README.md): F01–F11, each with a caption, alt text and a text description. |
| **Look up** | [Glossary](docs/glossary.md) · [Claims and limits](docs/claims-and-limits.md) · [Sources](references/README.md). |

## What you will understand, and where

| You will understand | Read |
|---|---|
| 1. The information-consumption problem | [Chapter 1](docs/paper/01-human-attention.md) |
| 2. Why adding more agents can make it worse | [Chapter 1](docs/paper/01-human-attention.md), [chapter 7](docs/paper/07-one-interaction.md) |
| 3. The architectural thesis | [Overview](docs/paper/00-overview.md) |
| 4. The logical reference architecture | [Chapter 3](docs/paper/03-governed-context.md) (Figure F02) |
| 5. The evidence and context contracts | [Chapters 4–6](docs/paper/04-evidence-and-lineage.md), [contracts](contracts/README.md) |
| 6. Authority and accountability boundaries | [Chapter 9](docs/paper/09-authority.md) |
| 7. Degraded and failure modes | [Chapter 10](docs/paper/10-degraded-operation.md) |
| 8. How to begin implementing it | [Chapter 14](docs/paper/14-start-monday.md), [implementation guide](docs/implementation-guide.md) |
| 9. How to evaluate it | [Chapter 12](docs/paper/12-evaluation.md), [evaluation guide](evaluation/README.md) |
| 10. What it explicitly does not claim | [Claims and limits](docs/claims-and-limits.md), [where the architecture stops](docs/paper/14-start-monday.md#where-the-architecture-stops) |

Short on time? [Guided reading paths](docs/README.md) give a few-page route for architects, implementers, reviewers and evaluators.

## Quickstart

```bash
python -m pip install -r requirements.txt   # one package: jsonschema
python scripts/validate_examples.py         # validate the synthetic examples
python scripts/check_all.py                 # every repository check, as CI runs them
```

You need Python 3.9 or later. It is tested on Windows and Linux (nothing in it is platform-specific, so macOS should work too), uses no network, and starts no service or model. The first command should print:

```text
Evidence at Human Scale 1.0.0-rc.1: example validation
Synthetic data only. A pass is not evidence about any real system.

[1/6] Schema bundle ...      PASS
[2/6] Example instances ...  PASS
[3/6] Scenario semantics ... PASS
[4/6] Gateway scenarios ...  PASS
[5/6] Assistant responses ... PASS
[6/6] Evaluation cases ...   PASS

All 6 stages passed.
```

When a check fails, the message names a code, the file and location, and the contract page to read. The [examples guide](examples/README.md) tells you how to try that on purpose, and [`scripts/README.md`](scripts/README.md) documents every script.

## What a pass means, and what it does not

A pass means the invented examples are structurally valid and internally coherent, and that the deterministic checks behave as documented.

It does **not** mean that any real system, model or process is accountable, safe or correct. It does not establish source truth, legal or regulatory compliance, authorization legitimacy, decision quality, human-review quality, production safety, operational readiness or business value. These checks are not the EV01–EV12 evaluation programme, which has not been run, and they are not model evaluation or human-outcome evaluation.

## Status and limits

- **No evaluation has been run.** EV01–EV12 (the twelve evaluation tests), their 70 fixtures and the 12 matched baseline records (a comparison framework of four measures against three simpler baselines) are NOT RUN, which means execution was not attempted. The 47 domain parameters are UNSET, which means no approved value exists. Nothing here reports a result of evaluating the architecture, and the proposed benefit is more inspectable context, not a measured gain in speed, accuracy, cost or decision quality.
- **All example data is invented.** The buyer, the supplier, the amounts and the systems describe no real organization, person or system.
- **Case-based, not a client commission.** The design comes from an architecture engagement on a written case about a public-sector fisheries-control authority in Iceland. The authority took no part, and nothing here is a statement by, about or on behalf of it. The observations that came out of the engagement are single dated cases and one internal, AI-assisted test; none measures this architecture's benefit ([claims and limits](docs/claims-and-limits.md) gives their limits).
- **AI-assisted and not independently reviewed by people.** See [AI assistance](#ai-assistance).
- **Affiliation.** The author is employed by Microsoft, and the optional Azure mapping is one example, not a requirement. See [Disclosure](#disclosure).

The full statement is in [Claims and limits](docs/claims-and-limits.md).

## Repository map

| Folder | What it holds |
|---|---|
| [`docs/`](docs/README.md) | The paper, guided reading paths, glossary, claims and limits, implementation guide. |
| [`architecture/`](architecture/README.md) | The technical reference behind the paper. |
| [`contracts/`](contracts/README.md) | One page per contract, C01–C07, and the change record for the schema bundle. |
| [`schemas/`](schemas/README.md) | The machine-readable JSON Schema bundle (Draft 2020-12). |
| [`examples/`](examples/README.md) | A synthetic scenario that exercises every contract. |
| [`evaluation/`](evaluation/README.md) | How to evaluate, the oracles, and the catalogue of tests, fixtures and parameters. |
| [`figures/`](figures/README.md) | Every figure with its source, alt text and description. |
| [`references/`](references/README.md) | Public sources, their limits, and how engagement records are treated. |
| [`scripts/`](scripts/README.md), [`tests/`](tests) | The validation tooling and its tests. |
| [`.github/`](.github) | The continuous-integration workflows and the issue and pull-request templates. |

## Citing, contributing, security

- **Cite.** [`CITATION.cff`](CITATION.cff) lets GitHub offer *Cite this repository*. Cite the release candidate by its version, and say that it is a candidate.
- **Contribute.** [`CONTRIBUTING.md`](CONTRIBUTING.md) says what is welcome and how to run the checks before you open a pull request.
- **Report a security concern.** [`SECURITY.md`](SECURITY.md) explains what counts and how to report it privately.
- **Changes.** [`CHANGELOG.md`](CHANGELOG.md) lists what this release candidate contains and its known limitations.

## License

**No license has been chosen yet.** Until the author adds a `LICENSE` file, no permission to copy, modify or redistribute this material is granted beyond what GitHub's Terms of Service allow for viewing and forking a public repository. The decision is open; see the [changelog](CHANGELOG.md#known-limitations-of-this-release-candidate).

## Disclosure

The author is employed by Microsoft. The Azure mapping is one implementation example of the product-neutral architecture, not a requirement to use Microsoft technology. This repository is not an official Microsoft publication, and nothing in it implies Microsoft endorsement. The mapping is in [implementation options](architecture/azure-implementation-options.md) and [chapter 13](docs/paper/13-implementation-options.md); every logical contract and path stands without it.

## AI assistance

AI assistance supported drafting, cross-checking and publication production. Andy Georgi is the author and is accountable for this repository. Anyone who reviews it contributes comments, not coauthorship. This repository was assembled with the help of an AI coding assistant (GitHub Copilot) under the author's direction: Markdown conversion, figures, examples and validation scripts. The reviews that took place were AI-assisted and are not independent human reviews.

Author: **Andy Georgi**.
