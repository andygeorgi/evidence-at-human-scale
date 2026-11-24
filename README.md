<!-- banner:start -->
<p align="center">
<picture>
<source media="(min-width: 900px) and (prefers-color-scheme:dark)" srcset="figures/banner-wide-dark.svg">
<source media="(min-width: 900px)" srcset="figures/banner-wide-light.svg">
<source media="(prefers-color-scheme: dark)" srcset="figures/banner-dark.svg">
<img src="figures/banner-light.svg" alt="Evidence at Human Scale, a reference architecture for accountable decisions in agentic systems. Three steps: versioned records, one decision packet, and a person who approves one exact proposal or holds it. Every item carries its type: record, finding, inference or proposal.">
</picture>
</p>
<!-- banner:end -->

# Evidence at Human Scale

**Reference architecture for accountable decisions in agentic systems**

*Version `v1.0.1`, 24 November 2026. Licensed under the [MIT License](LICENSE).*

## The problem, in one invoice

A supplier invoice is ready to pay, and the goods receipt disagrees with it. The accounts-payable controller has to decide whether to hold or release the payment. The material in front of them comes from several systems and two AI assistants, and part of it is missing, restricted or about to be corrected.

| | In the example |
|---|---|
| **Records that disagree** | Invoice `INV-2026-0417` says 100 units, EUR 18,400. Goods receipt `GR-5521` version 1 says 60 units received. |
| **What remains unknown** | Why they differ. Two AI summaries say "probably a receiving delay", but both read the same receipt, so they are one opinion. The treasury service did not answer, and part of the requested scope is outside the requestor's read permissions. |
| **Decision requested** | Hold the payment or release it. The controller owns the decision. |
| **What authority permits** | A standing grant lets the system place a hold. Releasing this payment needs the controller's approval of one exact proposal. |
| **After the correction** | The warehouse finds a second pallet and corrects the receipt to 100 units. The summaries, the packet and the approval built on version 1 stop being current, and the controller reviews a new packet before approving again. |

Every name, amount and system in this example is invented. [The full story](examples/README.md#the-story), with times and folders, is in the examples.

## What the architecture does about it

It gives the controller one versioned **decision packet** instead of a pile of agent output:

- **Each item says what it is.** A claim cites an exact record version. An inference is labeled as an inference. Two summaries of one receipt count as one origin.
- **What is unknown stays visible.** A conflict, a gap or an unavailable source stays in the packet with its reason, in the wording the requestor's permissions allow.
- **Authority stays separate.** A proposal is not an approval, and an approval is not execution. At commit, a gateway rechecks the grant, the evidence, the preconditions and the limits against the current state.
- **Corrections travel.** When a record is superseded, everything built on the old version, a pending approval included, stops being current.

More agents give the controller more interpretations to read. The unit of design here is the decision context rather than the agent hierarchy, and [the paper](docs/paper/README.md) argues why.

## Quickstart

```bash
python -m pip install -r requirements.txt   # one package: jsonschema
python scripts/validate_examples.py         # validate the synthetic examples
python scripts/check_all.py                 # every repository check, as CI runs them
```

You need Python 3.9 or later. It is tested on Windows and Linux (nothing in it is platform-specific, so macOS should work too), uses no network, and starts no service or model. The first command should print:

```text
Evidence at Human Scale 1.0.1: example validation
Synthetic data only. A pass is not evidence about any real system.

[1/6] Schema bundle ...           PASS          102 evaluated
[2/6] Example instances ...       PASS          37 evaluated
[3/6] Scenario semantics ...      PASS          37 evaluated
[4/6] Gateway scenarios ...       PASS          19 evaluated
[5/6] Assistant responses ...     PASS          3 evaluated
[6/6] Evaluation cases ...        PASS          37 evaluated

Result: PASS. All 6 stages passed, each after evaluating at least one item (235 items in all).
```

A stage passes only if it evaluated something. An empty folder is `NOT ASSESSED`, unreadable input is an `INPUT ERROR`, and a broken example is a `FAIL`. When a check fails, the message names a code, the file and location, and the contract page to read. The [examples guide](examples/README.md) tells you how to break something on purpose, and [`scripts/README.md`](scripts/README.md) documents every script.

## Ten-minute path

1. **Read the scenario** above, or [the story](examples/README.md#the-story) for the times.
2. **Run the Quickstart.**
3. **Inspect the decision packet** the controller reviews: [05 Decision packet](examples/05-decision-packet/README.md).
4. **Inspect the blocked action and its receipt**: [08 Blocked action](examples/08-blocked-action/README.md). A queued release is refused at commit, and the receipt shows that nothing happened.
5. **Continue into the architecture** if you want the reasons: [the paper](docs/paper/README.md), then the [architecture reference](architecture/README.md).

## Where to go next

| Goal | Where |
|---|---|
| **Read** | [The paper](docs/paper/README.md): 15 short chapters, from the problem to the first decision to build. |
| **Check the detail** | [Architecture reference](architecture/README.md) · [seven contracts](contracts/README.md) · [JSON Schema bundle](schemas/README.md). |
| **Run** | [Examples](examples/README.md): one invented supplier-payment story in 13 folders, and a command that validates it. |
| **Evaluate** | [Evaluation guide](evaluation/README.md): 12 tests, 70 fixtures and 47 parameters, defined and not yet run. |
| **Build** | [Implementation guide](docs/implementation-guide.md). |
| **See** | [Figures](figures/README.md): F01–F11, each with a caption, alt text and a text description. |
| **Look up** | [Glossary](docs/glossary.md) · [Claims and limits](docs/claims-and-limits.md) · [Sources](references/README.md). |
| **Short on time** | [Guided reading paths](docs/README.md) for architects, implementers, evaluators and anyone checking the claims. |
| **Tooling** | [`scripts/`](scripts/README.md) and their [`tests/`](tests). |

## What a pass means, and what it does not

A pass means the invented examples are structurally valid and internally coherent, and that the deterministic checks behave as documented.

It does **not** mean that any real system, model or process is accountable, safe or correct. It does not establish source truth, legal or regulatory compliance, authorization legitimacy, decision quality, human-review quality, production safety, operational readiness or business value. These checks are not the evaluation programme EV01–EV12, which has not been run, and they are not model evaluation or human-outcome evaluation.

## Status and limits

- **A reference architecture, not a deployment.** This is a reference architecture, not a production deployment or benefit claim. The contracts and synthetic examples are tested; real-world effectiveness has not been evaluated. The evaluation programme is defined and none of it has been run ([why](evaluation/README.md#which-tests-can-be-run-today)). The proposed benefit is more inspectable context, not a measured gain in speed, accuracy, cost or decision quality.
- **All example data is invented.** The buyer, the supplier, the amounts and the systems describe no real organization, person or system.
- **Case-based, not a client commission.** The design comes from an architecture engagement on a written case about a public-sector fisheries-control authority in Iceland. The authority took no part, and nothing here is a statement by, about or on behalf of it. The observations that came out of the engagement are single dated cases and one internal, AI-assisted test; none measures this architecture's benefit ([claims and limits](docs/claims-and-limits.md) gives their limits).
- **AI-assisted.** See [AI assistance](#ai-assistance).

The full statement is in [Claims and limits](docs/claims-and-limits.md).

## Citing, contributing, security

- **Cite.** [`CITATION.cff`](CITATION.cff) lets GitHub offer *Cite this repository*. Cite the release by its version.
- **Contribute.** [`CONTRIBUTING.md`](CONTRIBUTING.md) says what is welcome and how to run the checks before you open a pull request.
- **Report a security concern.** [`SECURITY.md`](SECURITY.md) explains what counts and how to report it privately.
- **Changes.** [`CHANGELOG.md`](CHANGELOG.md) lists what each release contains and its known limitations.

## License

This repository is licensed under the [MIT License](LICENSE).

## Author

Andy Georgi. This is a personal project, not an official Microsoft publication.

## AI assistance

AI assistance supported drafting, cross-checking and publication production. Andy Georgi is the author and is accountable for this repository. Anyone who reviews it contributes comments, not coauthorship. This repository was assembled with the help of an AI coding assistant (GitHub Copilot) under the author's direction: Markdown conversion, figures, examples and validation scripts.
