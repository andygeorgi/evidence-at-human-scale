# Claims and limits

This repository states what it claims and, as carefully, what it does not. Every status below is preserved as it stands.

## What the repository is

- A reference architecture and a set of documentation contracts for accountable decisions in agentic systems, with a paper, a technical reference, machine-readable schemas, a synthetic worked example and evaluation guidance.
- An **architecture proposition, not a deployment or benefit claim**. The mechanisms are deliberate; none is presented as a measured benefit.
- Informed by a case-based architecture engagement, not a client commission. See [what the engagement showed](paper/02-engagement.md).

## Evidence classes kept apart

| Class | What it is here | What it is not |
| --- | --- | --- |
| **Real public records** | Dated single cases: audit and appeal findings, a data-protection ruling and guidance. Cited with their limits. | Evidence of a systemic failure, or a statement about any authority's staff or current practice. |
| **Real internal engagement records** | The author's own working records of case research and prototype tests, AI-assisted, described but not published. | Independent evaluations. Prototype tests ran on synthetic data. |
| **Synthetic illustration** | The three paper scenarios, the 70 defined fixtures, the worked example in [`examples/`](../examples/README.md) and the late-correction illustration. | Results, deployments or customer evidence. |
| **Not available, not claimed** | Any interview, data, approval or outcome from an authority; any customer endorsement; any runtime, human, safety, cost, latency or ROI result for this architecture. | Implied by anything in the repository. |

## What is not claimed

- **No evaluation has been run.** EV01–EV12, the 70 synthetic fixtures, the 12 matched baseline records, and architecture, runtime, safety, human, performance, latency, cost and ROI evaluation are all NOT RUN. See the [evaluation guide](../evaluation/README.md).
- **No measured benefit.** The proposed benefit is more inspectable context, not a claimed improvement in speed, accuracy, cost or decision quality.
- **No authority involvement.** The authority took no part; no interview, data, approval or outcome from it forms part of this evidence, and nothing here is a statement by, about or on behalf of it.
- **No systemic claim.** Public records are single dated cases; the repository makes no claim about any authority's staff, systems or current practice.
- **No claim that structural checks prove more than structure.** Schema validity and the example checks do not establish source truth, factual correctness, legal or regulatory compliance, authorization legitimacy, decision quality, human-review quality, production safety, operational readiness or business value. All of these are NOT ASSESSED.
- **No truth certification.** The architecture does not establish that sources are true, does not decide or approve, and does not set domain policy, thresholds or safe states.
- **No unconditional accessibility or format claim.** Accessibility checks on the figures are limited to what [the figure guide](../figures/README.md) lists.
- **No new product facts.** Product statements are dated 17 November 2026 UTC and qualified in the [implementation options](../architecture/azure-implementation-options.md); they are not deployment findings.

## Known limitations

- The zero-specialist recommendation rests on one internal, AI-assisted test plus the architecture's own reasoning ([chapter 2](paper/02-engagement.md)).
- No delivery engagement outside the originating case is cited; the paper does not claim repeated observation across customers.
- Human-outcome measures are not yet defined (open question OQ06); the [human-outcome evaluation guide](../evaluation/human-outcome-evaluation.md) says what a study must define and defines no result.
- No independent human architect review of the text is recorded in this repository. Reviews that did take place were AI-assisted and are described in the [references](../references/README.md#how-this-edition-was-produced).
- The older consistency questions that need an author decision rather than editing are listed in the [changelog](../CHANGELOG.md#known-editorial-questions).

## Statuses used

| Status | Meaning |
| --- | --- |
| NOT RUN | Execution was not attempted. |
| NOT ASSESSED | Insufficient declared assessment coverage; never an automatic pass. |
| UNSET | A domain parameter has no approved value. |
| unverified | A requirement has not been checked against its authoritative source. |
| unresolved | An open question that needs an owner's decision. |
