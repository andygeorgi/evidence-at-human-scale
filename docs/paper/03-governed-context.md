# 3. A governed context, not an agent hierarchy

[← 2. The engagement](02-engagement.md) · [Paper contents](README.md) · [Next: evidence and lineage →](04-evidence-and-lineage.md)

The logical architecture begins with sources. Registered sources, events, deterministic services, and analytics submit records or results through admission. A governed registry retains admitted immutable versions. Authorized retrieval produces candidate evidence and coverage; relevance, priority, grouping, and coverage produce a selected set and a selection manifest.

Bounded orchestration and synthesis turn that selection into a candidate decision packet. Claim, reference, and disclosure checks permit its release for review. The checks certify neither source truth nor the correctness of every interpretation. One assistant workspace lets the Decision Owner inspect, challenge, and compare the released context.

<!-- figure:F02:start -->
<!-- figure:F02:end -->

## Responsibilities, not new layers

Admission, registry, retrieval, selection, synthesis, release validation, review, and the action gateway are logical responsibilities. They may be physically colocated without collapsing their contracts. The control plane constrains every stage and path: identity, authorization, purpose, domain policy, source/model/tool inventory, freshness, budgets, and delegation. Azure products are implementation options, not logical boxes.

Optional specialists receive an authorized, bounded task. Their results return through admission; they cannot publish directly to the workspace, self-declare source authority, or widen their own permissions. The zero-specialist baseline remains a complete architecture. Removing a specialist must not remove a required control or continuity route.

The independent mandatory path runs from the registry through deterministic detection to an authorized notification and queue, then acknowledgement or escalation. Acknowledgement is receipt, not resolution. Existing native deterministic safety controls may use their established authorized routes outside assistant-mediated admission. Neither path acquires an LLM availability dependency.

The action path is separate again: an exact approved proposal or valid bounded grant reaches an executor that performs current checks and verifies outcomes. Corrections, revocations, late evidence, and challenges return to reassessment and invalidation. Figure F02 simplifies the presentation; the [architecture reference](../../architecture/README.md) carries the detailed controls behind it.

Seven documentation contracts carry these responsibilities: [C01 Context](../../contracts/c01-context.md), [C02 Evidence](../../contracts/c02-evidence.md), [C03 Selection](../../contracts/c03-selection.md), [C04 Decision packet](../../contracts/c04-decision-packet.md), [C05 Action proposal](../../contracts/c05-action-proposal.md), [C06 Delegation](../../contracts/c06-delegation.md) and [C07 Execution receipt](../../contracts/c07-execution-receipt.md). The following sections explain each; the [contract reference](../../contracts/README.md) lists all 41 field groups.

[← 2. The engagement](02-engagement.md) · [Paper contents](README.md) · [Next: evidence and lineage →](04-evidence-and-lineage.md)
