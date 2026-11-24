# Claims and limits

This is a reference architecture, not a production deployment or benefit claim. The contracts and synthetic examples are tested; real-world effectiveness has not been evaluated.

The repository covers accountable decisions in agentic systems. It contains a paper, a technical reference, a set of documentation contracts with machine-readable schemas, a synthetic worked example and evaluation guidance. It was informed by a case-based architecture engagement, not a client commission. See [what the engagement showed](paper/02-engagement.md).

## Evidence classes kept apart

| Class | What it is here | What it is not |
| --- | --- | --- |
| **Real public records** | Dated single cases: audit and appeal findings, a data-protection ruling and guidance. Cited with their limits. | Evidence of a systemic failure. |
| **Real internal engagement records** | The author's own working records of case research and prototype tests, AI-assisted, described but not published. | Independent evaluations. The prototype tests ran on synthetic data. |
| **Synthetic illustration** | The three paper scenarios, the 70 defined fixtures, the worked example in [`examples/`](../examples/README.md) and the late-correction illustration. | Results, deployments or customer evidence. |
| **Repository checks and editorial inspection** | Deterministic checks on invented data (schema, example, link and figure checks) and a reader's inspection of the text. | An evaluation of the architecture. A pass shows that the documents are consistent, and nothing about any real system. |
| **Not available, not claimed** | Any interview, data, approval or outcome from an authority; any customer endorsement; any runtime, human, safety, cost, latency or ROI result for this architecture. | Implied by anything in the repository. |

## What is tested, and what is not evaluated

**Tested.** The schema and contract structure; the synthetic worked example; the deterministic validators; the documented failure fixtures (64 invalid schema examples and 37 mutated copies of the example set); and the repository tooling.

**Not evaluated in the real world.** Human decision quality, operational usability, organizational outcomes, production reliability, customer benefit, production cost and latency, and institutional accountability in practice.

The 12 evaluation tests and their 70 fixtures were reviewed to see whether any could be run. None can be run without an implementation to run it against, and none has been run. All are NOT ASSESSED ([why](../evaluation/README.md#which-tests-can-be-run-today)). The 47 domain parameters are UNSET.

## What is not claimed

- **No result or measured benefit.** Nothing here reports a result of using the architecture, in a model, with people, in operation or in production, and no mechanism is presented as a measured benefit. The proposed benefit is more inspectable context. No gain in speed, accuracy, cost, latency, return or decision quality is claimed. See the [evaluation guide](../evaluation/README.md).
- **No authority involvement.** The authority took no part. Nothing here is a statement by, about or on behalf of it, including any claim about its staff, systems or current practice.
- **No claim that structural checks prove more than structure.** Schema validity and the example checks do not establish source truth, factual correctness, legal or regulatory compliance, authorization legitimacy, decision quality, human-review quality, production safety, operational readiness or business value. All of these are NOT ASSESSED.
- **No truth certification.** The architecture does not establish that sources are true, does not decide or approve, and does not set domain policy, thresholds or safe states.
- **No accessibility conformance claim.** The figure checks are automated checks on the files: alt text, descriptions and drawing limits. They are not an accessibility assessment. Formal accessibility is NOT ASSESSED, and usability on a phone has not been tested with people or devices. See [the figure guide](../figures/README.md).
- **No relicensing of cited material.** The [MIT License](../LICENSE) covers what the author wrote. The public sources that the repository cites keep their own terms ([sources](../references/README.md)).
- **No new product facts.** Product statements are dated 17 November 2026 UTC and qualified in the [implementation options](../architecture/azure-implementation-options.md). They are not deployment findings.

## Known limitations

- The zero-specialist recommendation rests on one internal, AI-assisted test within a single case-based engagement, plus the architecture's own reasoning ([chapter 2](paper/02-engagement.md)). That test is not statistical evidence.
- No delivery engagement outside the originating case is cited, so the paper does not claim repeated observation across customers.
- Human-outcome measures are not yet defined (open question OQ06). The [human-outcome evaluation guide](../evaluation/human-outcome-evaluation.md) lists what a study must define. It reports no result and recommends no threshold.

## Statuses used

| Status | Meaning |
| --- | --- |
| RUN / PASS, RUN / FAIL | Executed, with the command, the input and the output recorded. |
| NOT RUN | Executable with what exists, and not performed. |
| NOT ASSESSED | The evidence, environment or participants the evaluation needs do not exist. An empty denominator is also NOT ASSESSED, never a pass. |
| UNSET | The design of the evaluation is undefined, or a domain parameter has no value yet. |
| unverified | A requirement has not been checked against its authoritative source. |
| unresolved | An open question that needs an owner's decision. |
