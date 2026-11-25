# C07 Execution receipt

[Contracts](README.md) · Schema definition `#/$defs/execution_receipt` · Groups C07-G01–G03

**Paper:** [9. Authority remains a separate boundary](../docs/paper/09-authority.md); [10. Information can degrade without widening authority](../docs/paper/10-degraded-operation.md)
**Reference:** [action and degradation](../architecture/action-and-degradation.md)
**Figures:** F05, F06, F07 · **Evaluation tests:** EV11, EV12 (NOT ASSESSED)

A C07 Execution receipt records the verified outcome. Unknown is unresolved; partial effects count. A verified completion requires authoritative evidence of the outcome, and `not_executed_verified` (a verified no-effect) means authoritative confirmation, for this attempt, target and scope, that the action caused no business effect, not merely that a response was absent or that the gateway rejected the action.

| Group / exact type-cardinality | Emitted group and fields | Required semantics |
| --- | --- | --- |
| C07-G01 Identity/binding · Object, 1 | `identity_binding`: `receipt_id`, `version`, `proposal_reference`, `grant_reference`, `execution_attempt_id`, `executor`, `target` | Receipt ID, version and schema, proposal and grant references, execution attempt ID, executor and target. The `executor` is the `grantee` of the C06 grant that the receipt cites: no receipt validates under another principal's grant (check `ROLE006`). |
| C07-G02 Outcome · Object, 1 | `outcome`: `state`, `observed_effects`, `unresolved_conditions`, `timestamps`, `reason`, `no_effect_basis`, `no_business_effect` | One of five states: submitted, unknown, partial, completed_verified or not_executed_verified. Observed effects 0..n, unresolved conditions 0..n and timestamps. `not_executed_verified` requires authoritative confirmation of a rejection, a failure before any effect or a cancellation, with no business effect, a reason, the verification actor, method and time, and a target and action reference. A timeout is not this state. Unresolved effects stay unknown, and known partial effects are accounted separately. |
| C07-G03 Verification/recovery · Object, 1 | `verification_recovery`: `verification`, `reconciliation`, `recovery_state`, `retry_disposition`, `accounting` | Authoritative outcome references; the verification method, actor, time and scope; the reconciliation and recovery state; and the retry disposition. An unknown outcome keeps its reservation or equivalent conservative accounting. Partial effects count against cumulative limits and are reconciled or compensated under policy. Allowance is restored or reconciled only under a documented confirmed-effect policy, never on a timeout or a lease expiry alone. |

## Receipt states

The five outcome states and their required treatment are in [action and degradation](../architecture/action-and-degradation.md#receipt-interpretation-and-weaker-external-guarantees), shown as a lifecycle in Figure F06 ([chapter 9](../docs/paper/09-authority.md)).

## What a valid C07 does not establish

A receipt that says `completed_verified` is only as good as the authoritative outcome reference behind it; the schema checks that the reference is present, not that the target system is correct. The executor's own status is never outcome evidence. A gateway rejection is not a verified no-effect either: it says what the gateway did, not what happened at the target. The reference validator checks that a verified outcome is verified for the receipt's own target and action, from a check made at or after the attempt, and from records about that target (observations of it, not something derived or inferred) that were observed between the attempt and the check and had been admitted by then (check `AUTH008`), and that the receipt's own target is the target its proposal names (check `AUTH009`). It does not check that the verifying system is right, what the cited record says (its claim is free text, so a record about the right target and the right moment that contradicts the receipt would pass; a structured assertion of the observed effect would let a validator check it, and the v1 schema has none), or that nothing happened beyond the scope the verification declares.

## Examples

- [08 Blocked action](../examples/08-blocked-action/README.md): the gateway rejects an approval that is no longer current before submission, and a check of the target then supports `not_executed_verified` for that attempt.
- [09 Unknown outcome](../examples/09-unknown-outcome/README.md): `unknown` with the reservation retained, then `completed_verified` after authoritative reconciliation.

[← C06 Delegation](c06-delegation.md) · [Contracts](README.md)
