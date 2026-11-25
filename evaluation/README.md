# Evaluation guide

[Evaluation oracles](oracles.md) · [Catalogue](catalogue/README.md) · [Human-outcome evaluation](human-outcome-evaluation.md)

This guide separates what is tested from what is not evaluated, so that a passing check is not read as evidence of more than it shows. The architecture is a reference architecture, not a production deployment or benefit claim ([claims and limits](../docs/claims-and-limits.md)).

**Tested.** The schema and the structure of the contracts; the synthetic worked example; the deterministic validators and the reference commit check; the documented failure fixtures (64 invalid schema examples and 37 mutated copies of the example set); and the repository's own tooling.

**Not evaluated in the real world.** Human decision quality, operational usability, organizational outcomes, production reliability, customer benefit, production cost and latency, and institutional accountability in practice.

The evaluation programme that would examine the second list is defined in the [catalogue](catalogue/README.md): 12 tests, 70 fixtures, 12 matched baseline records and 47 domain parameters. None of it has been run.

## Which tests can be run today

All twelve tests, EV01 to EV12, were reviewed against what the repository contains. None can be run as defined, and none has been run.

Each test feeds fixed inputs to an implementation (something that produces evidence, decision packets and actions) and judges the output against an expected oracle. This repository has no such implementation. It has contract schemas, validators, a reference commit check, a response renderer and validator, and a worked example, and these check contract instances and invented data. A test also needs domain-approved parameters, and all 47 are UNSET, and an accountable owner, and none is assigned. So every test is NOT ASSESSED. NOT RUN would mean that the test could be run and was not.

Some of the repository's own checks cover the same ground as a test, as the [table below](#how-the-example-checks-relate-to-ev01ev12) shows. Running a check is not running the test. A fixture needs inputs fixed in advance, an owner, a denominator declared before scoring and a gate, and the checks have none of these. The catalogue records no check as the result of a test.

## Status words

Every status in the catalogue is one of five states.

| State | Meaning |
|---|---|
| **RUN / PASS** | Executed, with the command, the input and the output recorded, over a positive declared denominator, and the gate was met. |
| **RUN / FAIL** | Executed, with the same record, and the gate was not met. |
| **NOT RUN** | Executable with what exists, and not performed. |
| **NOT ASSESSED** | The evidence, environment or participants the evaluation needs do not exist. An empty denominator is also NOT ASSESSED, never a pass, and so is zero prohibited events over zero attempts. |
| **UNSET** | The design of the evaluation is undefined, or a domain parameter has no value yet. |

A status changes only when something was run and recorded, as [the catalogue](catalogue/README.md#when-a-row-is-run) describes. The validators in `scripts/` report their own five states (PASS, FAIL, SKIPPED, NOT ASSESSED, INPUT ERROR), defined in the [scripts guide](../scripts/README.md#validate_examplespy). NOT ASSESSED means the same in both: nothing was evaluated, because what it needs does not exist.

## Kinds of evidence

| Kind | What it can show | What it cannot show | Status today |
|---|---|---|---|
| **Schema and structural checks** | A document has the shape a contract requires, and meets its local constraints. | That it is true, that a reference resolves, that a producer is trustworthy. | **Tested.** The [schema bundle](../schemas/README.md) and its 38 valid and 64 invalid embedded examples, run by `scripts/validate_examples.py`. |
| **Deterministic functional checks** | That a documented rule can be implemented and behaves consistently on a small, fixed input. | That a real system, model or person behaves that way. | **Two parts.** (1) The repository's own checks on the [synthetic examples](../examples/README.md): tested. (2) The 70 fixtures of the EV01–EV12 programme, to be run against an implementation: NOT ASSESSED. |
| **Model evaluation** | How a particular model and prompt perform on grounded tasks, against gold answers. | Whether the architecture is worthwhile. | **NOT ASSESSED.** There is no model, prompt or gold answer set here. |
| **Human-outcome evaluation** | Whether people using the architecture inspect more evidence, decide better and carry a reasonable workload, compared with matched baselines. | Anything about the safety or correctness of the system alone. | **NOT ASSESSED.** There are no participants and no pilot. See [human-outcome evaluation](human-outcome-evaluation.md). |
| **Operational validation** | Whether it works in a real environment: latency, cost, failure behavior, change control. | Whether the outcomes are good for people. | **NOT ASSESSED.** There is no environment. |
| **Production evidence** | What actually happened in use, over time. | | **None.** |

## What this repository checks today

| Check | Command | Covers | Does not cover |
|---|---|---|---|
| Schema bundle | `python scripts/validate_examples.py` (stage 1) | The bundle is valid Draft 2020-12; the 102 embedded examples behave as labeled. | The contracts' meaning. A schema checks structure and local constraints. It does not check that a reference was retrieved correctly or that a claim is true. |
| Example instances | stage 2 | Every example validates against its contract. | |
| Scenario semantics | stage 3 | References resolve to exact versions. Lineage is acyclic, a deterministic finding names its inputs, and common origin is not counted as independence. Corrections propagate. Missingness labels are justified. A restricted record's existence is withheld. Approvals end with their basis. A decision snapshot holds together: the context, the selection and the packet state one as-of time, the packet cites only what was available then and carries every obligation of its selection. The requestor, the Decision Owner and the approver are the people the example names for those roles. Receipts agree with the commit check, and a later version of a receipt does not go back from a verified outcome. | Real data, real producers, scale. |
| Gateway scenarios | stage 4 | 24 stored what-if evaluations of the reference commit check; every reason code is exercised. | A real gateway: state, concurrency, a live target. |
| Assistant responses | stage 5 | A canonical response is compared with what its renderer produces and checked for reversed meaning. A free-form response is checked against named structural requirements: source pointers, labels, figures, uncertainty and certainty. | That free-form prose is semantically correct, and what a real model would write. |
| Evaluation cases | stage 6 | 37 mutated copies of the example set each produce exactly their declared codes. | The EV01–EV12 fixtures. |
| Upkeep checks | `python scripts/check_all.py`, and `python scripts/check_urls.py` for the cited public URLs | The unit tests, the recorded schema surface, the catalogue's copies and statuses, links and alt text, figure metadata and the hygiene scan: the repository stays consistent with itself. The cited URLs still resolve (network needed). | Whether the prose is right, that the sources say what is claimed, accessibility conformance (NOT ASSESSED) and usability on a phone (not tested with people or devices). |

All of these check the contracts, the examples and the repository's own text and tooling, on invented data. None evaluates the architecture in use.

## How the example checks relate to EV01–EV12

Some example checks cover the same failure area as an EV test, without being the test. The table names them so that the two are not confused.

| Evaluation test | Failure area | Related example checks |
|---|---|---|
| Types and source fidelity (EV01) | A producer promoting its output; a reference that does not resolve | `KIND001`, `KIND002`, `REF001`–`REF003`; cases `CASE-KIND-*`, `CASE-REF-*`; [01](../examples/01-source-records/README.md) |
| Rule reproducibility (EV02) | A rule version changing silently | Only in part: when the match result is recomputed after the correction, the earlier result stays as version 1 with its own method and inputs; the rule version itself does not change in the example. [11](../examples/11-late-correction/README.md) |
| Correlated agents (EV03) | Agreement treated as corroboration | `COR001`, `COR002`, `LIN001`–`LIN003`; [03](../examples/03-lineage-and-common-origin/README.md) |
| Conflict retention (EV04) | A conflict dropped in shortening | `MISS005`; [04](../examples/04-selection-and-missingness/README.md), [05](../examples/05-decision-packet/README.md) |
| Missingness (EV05) | A wrong or unjustified gap label | `MISS001`–`MISS005`; cases `CASE-MISS-*`; [04](../examples/04-selection-and-missingness/README.md) |
| Derived and authorised disclosure (EV06) | A summary that leaks, or a gap label that tells an unauthorized reader that a record exists | `DISC001`–`DISC005`; cases `CASE-DISC-01` to `CASE-DISC-03`; [04](../examples/04-selection-and-missingness/README.md#permission-before-disclosure). The check is a snapshot validation of stored outputs against stored decisions. It is not an authorization service, and counts, relationships and caches are not modeled. |
| Revocation (EV07) | Acting on a revoked grant or a corrected record | `GRANT_REVOKED`, `LIFE005`, `REVOCATION_UNVERIFIED`; [08](../examples/08-blocked-action/README.md), [10](../examples/10-degraded-modes/README.md). View-time revocation is not modeled. |
| Prompt injection (EV08) | Untrusted content changing controls | **No example check.** |
| Obligation overload (EV09) | Obligations dropped or silently capped | **No example check** beyond one obligation carried through a selection. |
| Degradation (EV10) | Silent substitution when something fails | [06](../examples/06-assistant-response/README.md), [10](../examples/10-degraded-modes/README.md) |
| Race, duplicate and unknown action (EV11) | A blind retry; allowance restored by a timeout | `CUMULATIVE_LIMIT`, `ACC001`–`ACC005`; [09](../examples/09-unknown-outcome/README.md). Races and concurrency are not modeled. |
| Late or corrected evidence (EV12) | A pending approval surviving a correction | `LIFE001`–`LIFE005`; [11](../examples/11-late-correction/README.md) |

## The programme

12 tests, 70 synthetic fixtures, 12 matched baseline records and 47 domain parameters. Every test, fixture and baseline is NOT ASSESSED, and every parameter is UNSET. The [oracles](oracles.md) page states what each test requires. The [catalogue](catalogue/README.md) holds the machine-readable tables.

| Topic | What the programme defines |
|---|---|
| **Tests** | Types and source fidelity (EV01) · Rule reproducibility (EV02) · Correlated agents (EV03) · Conflict retention (EV04) · Missingness (EV05) · Derived and authorised disclosure (EV06) · Revocation (EV07) · Prompt injection (EV08) · Obligation overload (EV09) · Degradation (EV10) · Race, duplicate and unknown action (EV11) · Late or corrected evidence (EV12) |
| **Gates** | 100% over a positive denominator for the ratio metrics. Zero prohibited events, counted only over adversarial opportunities that were attempted. Both are targets for finite fixtures and are not production safety guarantees. |
| **Owners** | Unassigned. The usual split: source and domain owners own fidelity and rules; lifecycle and selection owners own lineage, conflict and missingness; access and security owners own disclosure, revocation and injection; obligation and operations owners own continuity; executor and target owners own races and outcomes. |

## Matched baselines before multi-agent value

Before claiming that a specialist, an additional agent or a richer synthesis adds value, compare it with simpler baselines on matched tasks, risks, scope and acceptance criteria. Preregister the comparisons in this order:

1. the native or current workflow;
2. deterministic grouping and templates;
3. simple synthesis with zero specialists;
4. only then, optional specialists justified by a measured, matched need for permission or isolation.

<!-- figure:F08:start -->
**Figure F08.** Each step up, from the native or current workflow to optional specialists, is to be compared with the step before it on matched tasks. No evaluation result is claimed, and no comparison has been run.

<p align="center">
<picture>
<source media="(prefers-color-scheme: dark)" srcset="../figures/F08-dark.svg">
<img src="../figures/F08-light.svg" alt="Four numbered steps in order: native or current workflow, deterministic grouping and templates, simple synthesis with zero specialists, optional specialists. Arrows between them ask whether the next step is better on matched tasks, and whether there is a measured, matched need. Two cards follow: one lists the measures, the other says no evaluation result is claimed and no comparison has been run." width="400">
</picture>
</p>

<details>
<summary>Text description of Figure F08</summary>

Four numbered steps are drawn top to bottom. The first is the native or current workflow. The second is deterministic grouping and templates. The third is simple synthesis with zero specialists, which is a complete architecture on its own. The fourth is optional specialists, admitted only for a documented task, permission or isolation need. An arrow between two steps carries a question. The first two arrows ask whether the next step is better on matched tasks. The third asks whether there is a measured, matched need. A card lists the measures: correctness, omissions, evidence actually inspected, decision quality, time and workload. Fluency and how many agents agree are not measures. A last card says: No evaluation result is claimed. No comparison has been run.

[All figures and their descriptions](../figures/README.md#f08-simpler-baselines-before-specialists)

</details>
<!-- figure:F08:end -->

Measure correctness, omissions, evidence actually inspected, decision quality, time and workload. Do not measure fluency or how many agents agree. Cap fanout, calls, tokens, elapsed time, retries and spend once for the whole task. Removing the specialists must leave the architecture intact. Count cost across retrieval, storage, telemetry, evaluation, inference, retries and operations, and not only tokens. Report critical-path elapsed time separately from total work.

**No latency, cost, ROI or human-performance outcome has been measured.** The 12 matched baseline records in the catalogue are a comparison framework, not an achieved benefit.

## Preconditions: 47 parameters nobody has set

A test cannot be run until the domain has said what its thresholds, budgets and authorities are: `B_time`, `B_cost`, workload, required freshness, risk classes, action limits, safe states and 40 more. All 47 are UNSET, with the owner unassigned. That is deliberate: no illustrative value is promoted to a default. An unset parameter blocks the deployment decision or operation that depends on it. It does not block publication of the reference architecture.

## Run it yourself

```bash
python -m pip install -r requirements.txt
python scripts/validate_examples.py
python -m unittest discover -s tests
```

## What a pass does not mean

A pass of any check in this repository does not mean that the architecture works, that a system built on it would be accountable, or that a model or a person would behave as the examples do. See [Claims and limits](../docs/claims-and-limits.md).
