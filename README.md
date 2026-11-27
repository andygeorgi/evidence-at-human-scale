# Evidence at Human Scale

**Reference architecture for accountable decisions in agentic systems**

When several systems and AI assistants feed one decision, the person who decides cannot easily tell what is a source record, what is a model's inference and what is missing. This repository shows, with one invented invoice, how to give that person one decision packet that keeps them apart, and how to keep advice, approval and execution separate. **[Start with the ten-minute path](#ten-minute-path).**

## Ten-minute path

The path has five steps and takes about ten minutes. It starts with one invoice and ends with a first step you can take on Monday. You can read it without leaving this page; the links lead to optional detail.

<a id="the-problem-in-one-invoice"></a>
## 1. The problem, in one invoice

A supplier invoice is ready to pay, and the goods receipt disagrees with it. The invoice says 100 units, EUR 18,400; version 1 of the receipt says 60 units were received. The accounts-payable controller has to decide whether to hold the payment or release it, working from several systems and two AI assistants, with some material missing or restricted.

The two AI summaries suggest a receiving delay, but both read the same receipt, so they do not provide independent corroboration. The treasury service did not answer, and part of the requested scope lies outside the requestor's read permissions, so the analyst who asked for the review may not read it. The controller still owns the decision.

Every name, amount and system in this example is invented. The examples tell the [full story](examples/README.md#the-story), with times and record numbers.

<a id="what-the-architecture-does-about-it"></a>
## 2. The architecture's answer: one decision packet

The architecture gives the controller one versioned **decision packet** instead of a pile of agent output. In this case, the warehouse receipt says 60 units were received: a **source record**. The declared three-way-match rule finds that invoice and receipt do not match: a **deterministic finding**. An AI summary suggests a receiving delay: a **model inference**.

Keeping these distinct lets the controller see what each establishes. A source record shows what its source asserted. A deterministic finding shows what the declared rule produced from stated inputs. A model inference establishes that an interpretation was produced, not that the interpretation is true. Every claim cites an exact record version. Conflicts, gaps and unavailable sources remain visible, each with its reason and in the wording the requestor's permissions allow.

The packet carries proposals for action; approval and execution remain separate steps. Before an action is carried out, at commit, a gateway rechecks the grant or approval, the evidence, the preconditions and the limits against the current state.

More agents can give the controller more interpretations to read. The unit of design here is the decision context, meaning the outputs selected for one decision and released as one packet, rather than the agent hierarchy. [The paper](docs/paper/README.md), which you can skip for now, argues why.

## 3. What the controller reviews

The controller reviews the decision packet, a versioned review object that holds supported claims, labeled inferences, conflicts, gaps, recommendations and proposals. Its first view should state the task and the as-of time, show the information that could change the decision, and show where the basis is weak or incomplete. From there the controller can follow a claim back to the original evidence, inspect a conflicting account, challenge a claim and review a revised version.

In the example, version 1 of the packet was produced at 10:00:

| Part of the packet | What the controller can see |
|---|---|
| Supported claims | The invoice says 100 units, the receipt says 60, and the three-way match fails. These are among seven supported claims, each citing an exact record version; the match result is a deterministic finding. |
| Labeled inferences | The two AI summaries share the same underlying receipt, so they do not amount to two independent corroborations. Both are labeled model inferences, each with its method and limits; neither is a supported claim. |
| Conflicts and gaps | The quantity conflict remains unresolved: its cause is not established. Seven labeled gaps show what is missing or unavailable, including the treasury service that did not answer, out-of-date screening and part of the scope the requestor may not read. |
| Recommendations | The advice: hold the invoice, and release at 16:00 only if the three-way match passes, the supplier screening is current and the invoice is on hold. |
| Action proposals | The hold and release are exact proposals for carrying out that advice. Both are marked proposed and not executed; the recommendation does not authorize them. |

Every claim in this packet can be traced to a source. The example leaves open whether a reader finds such a packet readable or quicker than the current process, and whether its size is right: a real packet would be much larger, and usability is an open evaluation question. The repository's check that a claim agrees with its source is mechanical. It compares statuses and figures and does not read free text for meaning, so passing it does not show that a claim means what its source means. The [full packet](examples/05-decision-packet/README.md) has every reference and the checks that run on it.

## 4. Who decides, and what stays separate

Four decisions remain with named people, and the architecture makes none of them: whether a source record is true (the source owner), what the evidence means for this case and what to do (the Decision Owner), whether one exact proposal goes ahead (the approver), and policy, thresholds, safe states and source authority (the domain owners). The controller in the example is both the Decision Owner and the approver, which the example's policy allows. The system can place holds under a bounded grant, but releasing this payment needs the controller's approval of one exact proposal.

The controller reviewed version 1 of the packet at 10:35 and gave an exact approval at 10:40 for a conditional release at the 16:00 payment run: the three-way match must pass, the supplier screening must be current and the invoice must be on hold.

Later the warehouse found a second pallet and at 13:40 corrected the goods receipt from 60 to 100 units. At 13:45 the dependent packet and summaries stopped being current, and the approval was revoked. By 14:10 the corrected receipt supported a passing match and a revised packet, but the old approval remained unusable. It was bound to a proposal built on replaced evidence; the new proposal needed a new approval.

When the 16:00 payment run started, the gateway rechecked the queued release under the old approval and refused it at commit. It found four independent reasons: the approval had been revoked, the evidence the proposal cites had been superseded, the screening it cites was 56 hours old against a 24-hour policy, and a precondition failed because the proposal cites neither a current passing match result nor a current fresh screening.

The execution receipt records what happened to this attempt. Refusal before submission means the gateway submitted nothing; it does not prove that nobody else changed the target. A separate authoritative target check after the attempt found no effect for this attempt, target and scope.

The commit check is a small stateless reference function, not a production gateway. The example does not show that a real system would notice the correction in time or that blocking is the right business outcome. Nor is it an argument that approvals are unnecessary: the gateway can only refuse what it can check. The [full blocked action](examples/08-blocked-action/README.md) explains the receipt, all 21 reason codes and the deeper execution and concurrency limitations.

<a id="the-smallest-useful-experiment"></a>
## 5. What to do on Monday

Pick one recurring, consequential decision and replay one recent case on paper with its Decision Owner, the person accountable for it. Choose a decision where people already struggle to absorb the available evidence. You do not need agent code or the full contract set to begin.

Write down the decision question, who owns it and the evidence actually used. Mark important information that was missing or inaccessible, and the actions that could follow. Record separately who may read, who may approve and who may execute, so the approval and execution boundaries are clear.

For the wider implementation sequence, [paper chapter 14](docs/paper/14-start-monday.md) explains the five actions before agent code; the [implementation guide](docs/implementation-guide.md) provides working templates. Those are optional next steps, not Monday's whole assignment.

### Where the path ends

The invoice shows why evidence types stay distinct, what the Decision Owner reviews and why approval must be checked again before execution. The reusable design keeps seven contracts (context, evidence, selection, decision packet, action proposal, delegation and execution receipt) and a separate action gateway. Each domain supplies source authority, freshness, safe states, thresholds and who may approve or execute ([what stays fixed and what a domain supplies](docs/paper/11-costs-and-adaptation.md#what-stays-fixed-and-what-a-domain-supplies)).

What you can run here is the JSON Schema bundle, validators and reference commit check, exercised by tests on one invented example; the [Quickstart](#quickstart) runs those checks. A production gateway remains a reference pattern. Permission-bound output is a reference projection that shows only what the reader's permissions allow, not an authorization service. The [limits below](#what-this-shows-and-what-it-does-not) explain what has not been evaluated. To start, pick one recurring decision and replay one recent case on paper with its Decision Owner.

## Quickstart

You do not need this for the path above. Two commands validate the invented examples on your machine.

```bash
python -m pip install -r requirements.txt   # one package: jsonschema
python scripts/validate_examples.py         # validate the synthetic examples
```

You need Python 3.9 or later. The repository is tested on Windows and Linux (nothing in it is platform-specific, so macOS should work too). The checks use no network and start no service or model. `validate_examples.py`, the second command, should print:

```text
Evidence at Human Scale 1.0.8: example validation
Synthetic data only. A pass is not evidence about any real system.

[1/6] Schema bundle ...           PASS          102 evaluated
[2/6] Example instances ...       PASS          37 evaluated
[3/6] Scenario semantics ...      PASS          37 evaluated
[4/6] Gateway scenarios ...       PASS          24 evaluated
[5/6] Assistant responses ...     PASS          3 evaluated
[6/6] Evaluation cases ...        PASS          37 evaluated

Result: PASS. All 6 stages passed, each after evaluating at least one item (240 items in all).
```

A stage passes only if it evaluated something, and a failing check names its code, the file and the contract page to read. The [examples guide](examples/README.md#run-the-checks) has the exit states and how to break something on purpose, and [`scripts/README.md`](scripts/README.md) documents every script.

<a id="where-to-go-next"></a>
## Go deeper

The path ends with step 5. Everything below is optional depth.

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

| Goal | Where |
|---|---|
| **Read the argument** | [The paper](docs/paper/README.md): 15 short chapters, from the problem to the first decision to build. |
| **Check the detail** | [Architecture reference](architecture/README.md) · [seven contracts](contracts/README.md) · [JSON Schema bundle](schemas/README.md). |
| **Run the examples** | [Examples](examples/README.md): one invented supplier-payment story in 13 folders, and a command that validates it. |
| **Evaluate** | [Evaluation guide](evaluation/README.md): 12 tests, 70 fixtures and 47 parameters. The tests are defined and none has been run, and every parameter is UNSET. |
| **See the figures** | [Figures](figures/README.md): F01–F11, each with a caption, alt text and a text description. |
| **Look something up** | [Glossary](docs/glossary.md) · [Claims and limits](docs/claims-and-limits.md) · [Sources](references/README.md). |
| **Follow a route for your role** | [Guided reading paths](docs/README.md) for architects, implementers, evaluators and anyone checking the claims. |

<a id="status-and-limits"></a>
<a id="what-a-pass-means-and-what-it-does-not"></a>
## What this shows, and what it does not

A pass means that the invented examples are structurally valid, that their records agree wherever the checks compare them, and that the deterministic checks behave as documented. Synthetic examples are not evidence about real systems, models or processes. Contract and example validation is not the evaluation programme, model evaluation or human-outcome evaluation. EV01–EV12 remain NOT ASSESSED; none has been run ([why](evaluation/README.md#which-tests-can-be-run-today)). Formal accessibility is also NOT ASSESSED.

This is a reference architecture, not a production deployment or benefit claim. The contracts and synthetic examples are tested; real-world effectiveness has not been evaluated. The proposed benefit is more inspectable context; no gain in speed, accuracy, cost or decision quality has been measured.

All example data is invented: the buyer, the supplier, the amounts and the systems describe no real organization, person or system.

The design comes from an architecture engagement on a written case about a public-sector fisheries-control authority in Iceland, not from a client commission. The authority took no part, and nothing here is a statement by, about or on behalf of it. The engagement's observations are single dated cases and one internal, AI-assisted test; none measures this architecture's benefit. [Claims and limits](docs/claims-and-limits.md) gives the full boundaries.

## Citing, contributing, security

- **Cite.** [`CITATION.cff`](CITATION.cff) lets GitHub offer *Cite this repository*. Cite the release by its version, `v1.0.8`, 27 November 2026.
- **Contribute.** [`CONTRIBUTING.md`](CONTRIBUTING.md) says what is welcome and how to run the checks before you open a pull request.
- **Report a security concern.** [`SECURITY.md`](SECURITY.md) explains what counts and how to report it privately.
- **Changes.** [`CHANGELOG.md`](CHANGELOG.md) lists what each release contains.

## License

This repository is licensed under the [MIT License](LICENSE).

## Author

Andy Georgi. This is a personal project, not an official Microsoft publication.
