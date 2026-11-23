# 14. Start with one decision, not a platform

[← 13. Implementation options](13-implementation-options.md) · [Paper contents](README.md)

## Adoption depends on evidence, not a polished paper

Adoption requires approved owners and parameters, implemented authorization, established failure and continuity routes, executed fixtures, and recorded deployment acceptance. Unresolved source authority, shared accounting, external-effect guarantees, synchronization, thresholds, or safe states block dependent operations. A published paper is not operational approval.

## On Monday: five things before any agent code

An architect can start applying this design on Monday without building the full contract set. Choose one recurring, consequential decision in which people already struggle to absorb the available evidence. Before writing any agent code, do five things.

1. Write down the decision question, the accountable Decision Owner and the actions that could follow, and record separately who may read, who may approve and who may execute.
2. Inventory the sources behind that decision by producer, evidence kind, version, owner and freshness requirement. Mark the mandatory signals and give them a deterministic notification route that does not depend on the assistant.
3. Draft the first view of the decision packet: supported claims with exact references, labeled inferences, conflicts, and the missingness labels that apply. Walk it through a recent case with the Decision Owner.
4. Put a gateway in front of every consequential action. It rechecks permission, evidence, policy, target state and limits at commit, and its receipt is verified against the authoritative target, not the executor's own status.
5. Run the current workflow, a deterministic template and a zero-specialist synthesis on the same fixed fixtures. Record omissions, evidence actually inspected, time and cost with declared denominators before considering any specialist agent.

The [implementation guide](../implementation-guide.md) turns each step into a short working checklist with the matching contract, example and evaluation material.

## What good looks like: one late correction

This illustration was not run. Take the sequence behind EN02, without any claim about the authority's systems. A fee decision rests on version 1 of a landing record; months later, version 2 corrects the landing date. The correction is admitted as new C02 evidence that supersedes version 1. Lineage shows that the decision packet (C04) and any pending approval of an action proposal (C05) depend on version 1, so both are invalidated and the case returns to reassessment. The Decision Owner sees which claim changed, the superseded and current records, and the decision that relied on them. Whether to reopen remains the owner's call; the architecture surfaces the conflict and does not decide. If a new action is approved, the gateway rechecks permission and evidence at commit, and the execution receipt (C07) is verified against the authoritative target system. Evaluation test EV12 is defined to check this behavior; it remains NOT RUN.

The same shape is available as data. The repository's [synthetic late-correction example](../../examples/README.md) walks a corrected record through the contracts and checks the result with deterministic repository tests. Those checks run on invented data; they are not the EV12 evaluation test, which remains NOT RUN, and they say nothing about any real system.

<!-- figure:F10:start -->
<!-- figure:F10:end -->

## Where the architecture stops

The architecture ends where accountability begins. It admits, selects, synthesizes, checks and presents evidence; it can carry a proposed action to a gateway and verify the outcome. It does not establish that sources are true, it does not decide or approve, and it does not set domain policy, thresholds or safe states. Those remain with named people and domain owners, and an unresolved parameter blocks the decision that depends on it.

## Technical scrutiny and sources

The [architecture reference](../../architecture/README.md) and the [contract reference](../../contracts/README.md) form the second reading layer; the [reviewer navigation](../../architecture/reviewer-navigation.md) maps questions to sections. The [JSON Schema bundle](../../schemas/README.md) is a documentation-only JSON Schema Draft 2020-12 bundle, and the [evaluation catalogue](../../evaluation/catalogue/README.md) holds the evaluation tests, fixtures and parameters. The figures in this paper are simplified derivatives of the same architecture, not alternative specifications. Every cited source, its passage scope and its limits are listed in the [sources](../../references/README.md).

[← 13. Implementation options](13-implementation-options.md) · [Paper contents](README.md)
