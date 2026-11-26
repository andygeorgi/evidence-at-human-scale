# Evidence at Human Scale

**Reference architecture for accountable decisions in agentic systems**

When several systems and AI assistants feed one decision, the person who decides cannot easily tell what is a source record, what is a model's inference and what is missing. This repository shows, with one invented invoice, how to give that person one decision packet that keeps them apart, and how to keep advice, approval and execution separate. **[Start with the ten-minute path](#ten-minute-path).**

<!-- banner:start -->
<p align="center">
<picture>
<source media="(min-width: 900px) and (prefers-color-scheme:dark)" srcset="figures/banner-wide-dark.svg">
<source media="(min-width: 900px)" srcset="figures/banner-wide-light.svg">
<source media="(prefers-color-scheme: dark)" srcset="figures/banner-dark.svg">
<img src="figures/banner-light.svg" alt="Reference architecture for accountable decisions in agentic systems. Evidence stays distinct: goods receipt, source record; three-way match, deterministic finding; AI explanation, model inference. One decision packet: claims cite evidence, inferences remain labeled, conflicts and gaps stay visible, proposals are not actions. A person decides: approve or hold. Current evidence is rechecked before action.">
</picture>
</p>
<!-- banner:end -->

## The problem, in one invoice

A supplier invoice is ready to pay, and the goods receipt disagrees with it. The accounts-payable controller has to decide whether to hold or release the payment. The material in front of them comes from several systems and two AI assistants, and part of it is missing, restricted or about to be corrected.

- **The records disagree.** The invoice says 100 units, EUR 18,400. The goods receipt, version 1, says 60 units received.
- **The cause is unknown.** Two AI summaries offer the same explanation, a receiving delay, but both read the same receipt, so they are one opinion. The treasury service did not answer, and part of the requested scope is outside the requestor's read permissions.
- **A person decides.** The controller owns the decision: hold the payment, or release it. A bounded grant lets the system place holds, and releasing this payment needs the controller's approval of one exact proposal.
- **Then the facts change.** The warehouse finds a second pallet and corrects the receipt to 100 units. The summaries, the packet and the approval built on version 1 stop being current, and the controller reviews a new packet before approving again.

Every name, amount and system in this example is invented. [The full story](examples/README.md#the-story), with times and record numbers, is in the examples.

## What the architecture does about it

It gives the controller one versioned **decision packet** instead of a pile of agent output:

- **Each item says what it is.** A source record, a deterministic finding and a model inference are kept apart. A claim cites an exact record version, and two summaries of one receipt count as one origin.
- **What is unknown stays visible.** A conflict, a gap or an unavailable source stays in the packet with its reason, in the wording the requestor's permissions allow.
- **Authority stays separate.** A proposal is not an approval, and an approval is not execution. At commit, a gateway rechecks the grant, the evidence, the preconditions and the limits against the current state.
- **Corrections travel.** When a record is superseded, everything built on the old version, a pending approval included, stops being current.

More agents give the controller more interpretations to read. The unit of design here is the decision context rather than the agent hierarchy, and [the paper](docs/paper/README.md) argues why.

## Ten-minute path

1. **Read the problem** above, or [the story](examples/README.md#the-story) with its times.
2. **Run the [Quickstart](#quickstart)** below. One command validates the invented examples.
3. **Inspect the decision packet** the controller reviews: [example 05, the decision packet](examples/05-decision-packet/README.md).
4. **Inspect the blocked action and its receipt**: [example 08, the blocked action](examples/08-blocked-action/README.md). A queued release is refused at commit. The receipt keeps the refusal apart from the check that verified no effect for that one attempt.
5. **Continue into the architecture** if you want the reasons: [the paper](docs/paper/README.md), then the [architecture reference](architecture/README.md).

## Quickstart

```bash
python -m pip install -r requirements.txt   # one package: jsonschema
python scripts/validate_examples.py         # validate the synthetic examples
```

You need Python 3.9 or later. It is tested on Windows and Linux (nothing in it is platform-specific, so macOS should work too), uses no network, and starts no service or model. `validate_examples.py`, the second command, should print:

```text
Evidence at Human Scale 1.0.6: example validation
Synthetic data only. A pass is not evidence about any real system.

[1/6] Schema bundle ...           PASS          102 evaluated
[2/6] Example instances ...       PASS          37 evaluated
[3/6] Scenario semantics ...      PASS          37 evaluated
[4/6] Gateway scenarios ...       PASS          24 evaluated
[5/6] Assistant responses ...     PASS          3 evaluated
[6/6] Evaluation cases ...        PASS          37 evaluated

Result: PASS. All 6 stages passed, each after evaluating at least one item (240 items in all).
```

A stage passes only if it evaluated something. An empty folder is `NOT ASSESSED`, unreadable input is an `INPUT ERROR`, and a broken example is a `FAIL`. When a check fails, the message names a code, the file and location, and the contract page to read. The [examples guide](examples/README.md) tells you how to break something on purpose, and [`scripts/README.md`](scripts/README.md) documents every script.

<a id="the-smallest-useful-experiment"></a>
<a id="where-to-go-next"></a>
## Go deeper

| Goal | Where |
|---|---|
| **Read the argument** | [The paper](docs/paper/README.md): 15 short chapters, from the problem to the first decision to build. |
| **Check the detail** | [Architecture reference](architecture/README.md) · [seven contracts](contracts/README.md) · [JSON Schema bundle](schemas/README.md). |
| **Run the examples** | [Examples](examples/README.md): one invented supplier-payment story in 13 folders, and a command that validates it. |
| **Try it on your own decision** | [Implementation guide](docs/implementation-guide.md), with a template for each step. Pick one recurring decision, replay one recent case on paper and walk it through with the person who owns the decision; [chapter 14](docs/paper/14-start-monday.md) explains why to start there. |
| **Evaluate** | [Evaluation guide](evaluation/README.md): 12 tests, 70 fixtures and 47 parameters. The tests are defined and none has been run, and every parameter is UNSET. |
| **See the figures** | [Figures](figures/README.md): F01–F11, each with a caption, alt text and a text description. |
| **Look something up** | [Glossary](docs/glossary.md) · [Claims and limits](docs/claims-and-limits.md) · [Sources](references/README.md). |
| **Short on time** | [Guided reading paths](docs/README.md) for architects, implementers, evaluators and anyone checking the claims. |

<a id="status-and-limits"></a>
<a id="what-a-pass-means-and-what-it-does-not"></a>
## What this shows, and what it does not

A pass means the invented examples are structurally valid, that their records agree with one another wherever the checks compare them, and that the deterministic checks behave as documented.

It does **not** mean that any real system, model or process is accountable, safe or correct. It does not establish source truth, legal or regulatory compliance, authorization legitimacy, decision quality, human-review quality, production safety, operational readiness or business value. These checks are not the evaluation programme (the twelve evaluation tests, EV01–EV12), which has not been run, and they are not model evaluation or human-outcome evaluation.

- **A reference architecture, not a deployment.** This is a reference architecture, not a production deployment or benefit claim. The contracts and synthetic examples are tested; real-world effectiveness has not been evaluated. The evaluation programme is defined and none of it has been run ([why](evaluation/README.md#which-tests-can-be-run-today)). The proposed benefit is more inspectable context, not a measured gain in speed, accuracy, cost or decision quality.
- **All example data is invented.** The buyer, the supplier, the amounts and the systems describe no real organization, person or system.
- **Case-based, not a client commission.** The design comes from an architecture engagement on a written case about a public-sector fisheries-control authority in Iceland. The authority took no part, and nothing here is a statement by, about or on behalf of it. The observations that came out of the engagement are single dated cases and one internal, AI-assisted test; none measures this architecture's benefit ([claims and limits](docs/claims-and-limits.md) gives their limits).

The full statement is in [Claims and limits](docs/claims-and-limits.md).

## Citing, contributing, security

- **Cite.** [`CITATION.cff`](CITATION.cff) lets GitHub offer *Cite this repository*. Cite the release by its version, `v1.0.6`, 26 November 2026.
- **Contribute.** [`CONTRIBUTING.md`](CONTRIBUTING.md) says what is welcome and how to run the checks before you open a pull request.
- **Report a security concern.** [`SECURITY.md`](SECURITY.md) explains what counts and how to report it privately.
- **Changes.** [`CHANGELOG.md`](CHANGELOG.md) lists what each release contains.

## License

This repository is licensed under the [MIT License](LICENSE).

## Author

Andy Georgi. This is a personal project, not an official Microsoft publication.
