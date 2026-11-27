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

## Ten-minute path

The path has five steps and takes about ten minutes. It starts with one invoice and ends with what you can do on Monday. You can read it without leaving this page. The links in steps 1 to 4 lead to optional detail, and step 5 ends with where to go next.

<a id="the-problem-in-one-invoice"></a>
## 1. The problem, in one invoice

A supplier invoice is ready to pay, and the goods receipt disagrees with it. The invoice says 100 units, EUR 18,400; version 1 of the receipt says 60 units were received. The accounts-payable controller has to decide whether to hold the payment or release it, working from several systems and two AI assistants, and part of that material is missing, restricted or about to be corrected.

The two AI summaries offer the same explanation, a receiving delay, but both read the same receipt, so they are one opinion. The treasury service did not answer, and part of the requested scope lies outside the requestor's read permissions, so the analyst who asked for the review may not read it. The controller owns the decision. The system can place holds under a bounded grant, but releasing this payment needs the controller's approval of one exact proposal.

Later the warehouse finds a second pallet and corrects the receipt to 100 units. Everything built on version 1 stops being current, and the controller has to review the corrected material before approving again.

Every name, amount and system in this example is invented. The examples tell the [full story](examples/README.md#the-story), with times and record numbers.

<a id="what-the-architecture-does-about-it"></a>
## 2. The architecture's answer: one decision packet

The architecture gives the controller one versioned **decision packet** instead of a pile of agent output. In the packet, a source record, a deterministic finding and a model inference stay distinct from one another. Each establishes something different: a source record shows what its source asserted, a deterministic finding shows what a declared rule produces from stated inputs, and a model inference shows only that an interpretation was produced, not that it is true. Every claim cites an exact record version. Conflicts, gaps and unavailable sources remain visible, each with its reason and in the wording the requestor's permissions allow.

A proposal is not an approval, and an approval is not execution. Before an action is carried out, at commit, a gateway rechecks the grant or approval, the evidence, the preconditions and the limits against the current state. A correction to a record invalidates what was derived from the earlier version and revokes a pending approval.

More agents can give the controller more interpretations to read. The unit of design here is the decision context, meaning the outputs selected for one decision and released as one packet, rather than the agent hierarchy. [The paper](docs/paper/README.md), which you can skip for now, argues why.

## 3. What the controller reviews

The controller reviews the decision packet, a versioned review object that holds supported claims, labeled inferences, conflicts, gaps, recommendations and proposals. Its first view should state the task and the as-of time, show the information that could change the decision, and show where the basis is weak or incomplete. From there the controller can follow a claim back to the original evidence, inspect a conflicting account, challenge a claim and review a revised version.

In the example, version 1 of the packet was produced at 10:00 and holds:

| Part of the packet | What this one holds |
|---|---|
| Supported claims | Seven, among them the invoice, the goods receipt (60 units) and the failed three-way match, which is a deterministic finding. Each cites an exact record version. |
| Labeled inferences | Two, one for each AI summary. Each states its method and its limits, including that the two share one origin. Neither is a supported claim. |
| Conflicts and gaps | The quantity conflict, with its cause not established, and seven labeled gaps. They include the treasury service that did not answer, a screening that is out of date and the part of the scope the requestor may not read. |
| Recommendations | The advice: hold the invoice, and release at 16:00 only if the three-way match passes, the supplier screening is current and the invoice is on hold. |
| Action proposals | The exact actions that would carry that advice out, the hold and the release, each marked proposed and not executed. |

Every claim in this packet can be traced to a source. The example leaves open whether a reader finds such a packet readable or quicker than the current process, and whether its size is right: a real packet would be much larger, and usability is an open evaluation question. The repository's check that a claim agrees with its source is mechanical. It compares statuses and figures and does not read free text for meaning, so passing it does not show that a claim means what its source means. The [full packet](examples/05-decision-packet/README.md) has every reference and the checks that run on it.

## 4. Who decides, and what stays separate

Four decisions remain with named people, and the architecture makes none of them: whether a source record is true (the source owner), what the evidence means for this case and what to do (the Decision Owner), whether one exact proposal goes ahead (the approver), and policy, thresholds, safe states and source authority (the domain owners). The controller in the example is both the Decision Owner and the approver, which the example's policy allows. Approving an action and carrying it out are separate steps, and a gateway checks the second one again at commit.

The controller reviewed version 1 of the packet at 10:35 and gave an exact approval at 10:40 for a conditional release of the payment at the 16:00 payment run. The warehouse corrected the goods receipt at 13:40. At 13:45 the packet and the summaries stopped being current, and the approval was revoked.

When the 16:00 payment run started, the gateway rechecked the queued release and refused it at commit. It found four independent reasons: the approval had been revoked, the evidence the proposal cites had been superseded, the screening it cites was 56 hours old against a 24-hour policy, and a precondition failed because the proposal cites neither a current passing match result nor a current fresh screening. By 14:10 the corrected goods receipt matched the invoice, yet the old approval remained unusable. It was given for a proposal built on evidence that has since been replaced, and a new proposal needs a new approval.

The execution receipt, the gateway's record of an attempt, keeps what the gateway did apart from what is known about the target. A refusal before submission says only that the gateway submitted nothing: another route, system or person could still have paid the invoice. Here an authoritative check of the target, made after the attempt, found no effect for this attempt, target and scope, so the receipt records a verified no effect (`not_executed_verified`).

The commit check here is a small reference function with no state, no concurrency control and no connection to a target, so it is not an implementation of a gateway. The example does not show that a real system would notice the correction in time, or that blocking is the right business outcome. Nor is it an argument that approvals are unnecessary: the gateway can only refuse what it can check. The [full blocked action](examples/08-blocked-action/README.md) lists all 21 commit-time reason codes.

<a id="the-smallest-useful-experiment"></a>
## 5. What to do on Monday

You can start without building the full contract set, the seven record formats the architecture defines. Pick one recurring, consequential decision in which people already struggle to absorb the available evidence. Before you write any agent code:

- write down the decision question, the accountable Decision Owner and the actions that could follow, and record separately who may read, who may approve and who may execute;
- inventory the sources behind the decision by producer, evidence kind, version, owner and freshness requirement, mark the mandatory signals, and give them a deterministic notification route that does not depend on the assistant;
- draft the first view of the decision packet, with supported claims that cite exact references, labeled inferences, conflicts and the labeled gaps that apply, and walk a recent case through it with the Decision Owner;
- put a gateway in front of every consequential action to recheck it at commit, and verify the execution receipt against the authoritative target rather than the executor's own status;
- run the current workflow, a deterministic template and a simple synthesis with no specialist agents on the same fixed cases, and record omissions, evidence actually inspected, time and cost, each with a declared denominator, before you consider any specialist agent.

Optional: [paper chapter 14](docs/paper/14-start-monday.md) gives the reasoning for each of these five actions.

### Where the path ends

- **What you can now explain.** Why a decision packet distinguishes source records, deterministic findings and model inference, what the person who decides reviews, and why approval and execution are separate steps.
- **What is reusable.** By design, every deployment keeps the same parts, including the seven contracts (context, evidence, selection, decision packet, action proposal, delegation and execution receipt) and a separate gateway for actions ([the full list](docs/paper/11-costs-and-adaptation.md#what-stays-fixed-and-what-a-domain-supplies)). The domain supplies the parameters, such as source authority, freshness, safe states, thresholds and who can approve or execute.
- **What is implemented.** A JSON Schema bundle for the contracts, validators and a reference commit check, exercised by tests on one invented example. The [Quickstart](#quickstart) runs the example checks.
- **What remains a reference pattern.** The gateway: the commit check in step 4 is only a small reference function. Permission-bound output, which shows a reader only what their permissions allow, is a reference projection, not an authorization service. The architecture is not a production deployment, and its real-world effectiveness has not been evaluated ([claims and limits](docs/claims-and-limits.md)).
- **Best first step.** Pick one recurring decision and replay one recent case on paper with the person who owns it, which covers the first three actions above. The [implementation guide](docs/implementation-guide.md) has a template for each of them.

## Quickstart

You do not need this for the path above. Two commands validate the invented examples on your machine.

```bash
python -m pip install -r requirements.txt   # one package: jsonschema
python scripts/validate_examples.py         # validate the synthetic examples
```

You need Python 3.9 or later. The repository is tested on Windows and Linux (nothing in it is platform-specific, so macOS should work too). The checks use no network and start no service or model. `validate_examples.py`, the second command, should print:

```text
Evidence at Human Scale 1.0.7: example validation
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

A pass means that the invented examples are structurally valid, that their records agree with one another wherever the checks compare them, and that the deterministic checks behave as documented. It says nothing about any real system, model or process. The checks are not the evaluation programme (the twelve evaluation tests, EV01–EV12, all NOT ASSESSED), and they are not model evaluation or human-outcome evaluation. [Claims and limits](docs/claims-and-limits.md) lists what a pass does not establish.

This is a reference architecture, not a production deployment or benefit claim. The contracts and synthetic examples are tested; real-world effectiveness has not been evaluated. The evaluation programme is defined and none of it has been run ([why](evaluation/README.md#which-tests-can-be-run-today)). The proposed benefit is more inspectable context, not a measured gain in speed, accuracy, cost or decision quality.

All example data is invented: the buyer, the supplier, the amounts and the systems describe no real organization, person or system.

The design comes from an architecture engagement on a written case about a public-sector fisheries-control authority in Iceland, not from a client commission. The authority took no part, and nothing here is a statement by, about or on behalf of it. The observations that came out of the engagement are single dated cases and one internal, AI-assisted test, and none of them measures this architecture's benefit ([claims and limits](docs/claims-and-limits.md) gives their limits).

## Citing, contributing, security

- **Cite.** [`CITATION.cff`](CITATION.cff) lets GitHub offer *Cite this repository*. Cite the release by its version, `v1.0.7`, 26 November 2026.
- **Contribute.** [`CONTRIBUTING.md`](CONTRIBUTING.md) says what is welcome and how to run the checks before you open a pull request.
- **Report a security concern.** [`SECURITY.md`](SECURITY.md) explains what counts and how to report it privately.
- **Changes.** [`CHANGELOG.md`](CHANGELOG.md) lists what each release contains.

## License

This repository is licensed under the [MIT License](LICENSE).

## Author

Andy Georgi. This is a personal project, not an official Microsoft publication.
