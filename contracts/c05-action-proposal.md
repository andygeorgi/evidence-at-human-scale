# C05 Action proposal

[Contracts](README.md) · Schema definition `#/$defs/action_proposal` · Groups C05-G01–G03

**Paper:** [9. Authority remains a separate boundary](../docs/paper/09-authority.md)
**Reference:** [action and degradation](../architecture/action-and-degradation.md)
**Figures:** F04, F05 · **Evaluation tests:** EV07, EV11, EV12 (NOT RUN)

A C05 Action proposal is the exact versioned action to consider. Advice is not approval or commit. Approval binds an exact versioned proposal within stated limits, and neither approval nor delegation substitutes for the executor's current checks.

| Group / exact type-cardinality | Emitted group and fields | Required semantics |
| --- | --- | --- |
| C05-G01 Identity/binding · Object, 1 | `identity_binding`: `proposal_id`, `version`, `context_reference`, `packet_reference` | Proposal ID/version/schema and exact C01/C04 references. |
| C05-G02 Action · Object, 1 | `action`: `action_kind`, `exact_target`, `typed_parameters`, `evidence_references`, `policy_references`, `preconditions`, `approved_empty_preconditions_justification`, `accounting` | Exact action kind/target and typed parameters; evidence/policy references 1..n; preconditions 0..n. Empty preconditions require explicit approved justification. Accounting identifies units, scope/window and exhaustion behavior as applicable to the bounded action. |
| C05-G03 Assessment · Object, 1 | `assessment`: `risk`, `expected_effects`, `limitations`, `recovery_conditions`, `status` | Risk, expected effects, limitations and recovery conditions. Status proposed, not executed. |

## What a valid C05 does not establish

A proposal's `status` can only be `proposed`. The contract has no `approved` or `executed` state: approval is a C06 delegation bound to this exact proposal, and execution is a C07 receipt. When the evidence a proposal cites is superseded, the proposal does not change; the approvals bound to it cease to be current.

## Examples

- [07 Authority and delegation](../examples/07-authority-and-delegation/README.md): a low-risk proposal covered by a bounded grant and a high-value proposal that needs an exact approval.
- [11 Late correction](../examples/11-late-correction/README.md): the proposal re-bound to the revised packet.

[← C04 Decision packet](c04-decision-packet.md) · [Contracts](README.md) · [Next: C06 Delegation →](c06-delegation.md)
