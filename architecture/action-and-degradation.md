# Action and degradation

[Architecture reference](README.md) · Paper: [9. Authority](../docs/paper/09-authority.md) · [10. Degraded operation](../docs/paper/10-degraded-operation.md)

## Approval, commit and shared capacity

Approval authorizes an exact versioned proposal within stated limits. A valid bounded grant may authorize a predefined action class without fresh per-action approval, but only within its current scope and lifecycle. No response is not approval. A deadline cannot enlarge a grant. Reading and synthesis authority do not authorize execution. There is no synthesis-to-execution bypass.

The authority figure (Figure F05, [chapter 9](../docs/paper/09-authority.md)) separates the requestor and the approver, the read-authorized context service, the workload or orchestration service, the executor (action gateway) and the authoritative target. Revocation reaches precommit checks. At commit, recheck current permission and revocation, evidence, policy, target state and per-action and cumulative limits, including consumed and reserved capacity. Proposal and grant identify units, accounting scope and window, and exhaustion behavior. An upstream check or earlier approval does not excuse this current boundary check.

Where supported, the executor atomically checks conditions, reserves or consumes shared capacity and commits. Reservation/accounting must be atomic across concurrent execution. An atomic target-version check alone does not prevent grant-limit overspend. Unknown outcomes retain their reservation or equivalent conservative accounting until authoritative reconciliation. Timeout or lease expiry cannot restore allowance and allow duplicate or over-limit actions. Known partial effects are charged against cumulative limits and reconciled or compensated under policy.

## Receipt interpretation and weaker external guarantees

| Receipt state | Interpretation and required treatment |
| --- | --- |
| `submitted` | An attempt was submitted; business completion is not established. Obtain authoritative outcome verification. |
| `unknown` | Effects remain unresolved. Keep reservation or conservative accounting; reconcile with the authoritative target. No blind retry. |
| `partial` | Some effects are known and others remain unresolved. Charge known effects against cumulative limits; assign notification, reconciliation and compensation responsibility. |
| `completed_verified` | Authoritative outcome references establish the verified effects within declared method/actor/time/scope. Submission alone is insufficient. |
| `not_executed_verified` | Terminal only after authoritative rejection, failed-before-effect or cancellation with no business effect. Require reason, verifier/method/time and target/action reference. Timeout is not no-effect evidence. |

Allowance is reconciled or restored only under documented confirmed-effect policy grounded in authoritative reconciliation, including the `not_executed_verified` terminal outcome (a verified no-effect). Define reservation expiry and reconciliation, but never treat expiry as evidence of no effect. Unresolved effects remain unknown; known partial effects remain separately accounted.

External targets may not participate in atomic checks and business commit. Document weaker guarantees, race windows, reservation/reconciliation behavior and residual risk; do not imply atomic business effects. Local idempotency is not exactly-once execution. If shared atomic grant-limit enforcement is unsupported, declare the limitation and disable unattended operations beyond domain acceptance. Software rollback cannot undo irreversible business effects.

## Full failure response and recovery ownership

Information availability and authority validity are separate axes. Current sufficient evidence with valid authority permits normal review and a separately checked action. Partial/stale evidence permits only an explicitly limited view and blocks freshness-dependent action. Unavailable evidence blocks evidence-dependent action; permitted native/manual fallback remains possible. Invalid/unavailable authority means no execution and no bypass in every information state. Figure F07 ([chapter 10](../docs/paper/10-degraded-operation.md)) shows this separation.

| Failure | Visible response / authority treatment | Recovery owner |
| --- | --- | --- |
| Source failure | Mark unavailable or partial; block unsupported evidence-dependent action | Source/registry owner |
| Model failure | Use qualified deterministic template or permitted native/manual route | Synthesis owner |
| Malformed record | Quarantine; do not silently admit or repair authority | Admission owner |
| Authorization/policy failure | No new protected disclosure or execution; no bypass | Access/policy owner |
| Gateway failure | No authority bypass; a submitted attempt may need reconciliation | Gateway/target owner |
| Stale historical view | Show version/limitation only under current viewing permission | Lifecycle/access owner |
| Deadline/budget exhausted | Explicit partial completion and scope; preserve mandatory routes | Orchestration/obligation owner |
| Action timeout | Unknown effects; retain conservative capacity; no blind retry | Executor/reconciliation owner |
| Late correction/challenge | Reassess lineage; invalidate derivatives, caches and pending approvals | Lifecycle owner |
| Mandatory-channel failure | Escalate through designated authorized native/manual routes | Escalation owner |

**Worked examples:** [blocked action](../examples/08-blocked-action/README.md) · [unknown outcome](../examples/09-unknown-outcome/README.md) · [degraded modes](../examples/10-degraded-modes/README.md) · [late correction](../examples/11-late-correction/README.md).

[← Lineage, selection and disclosure](lineage-selection-disclosure.md) · [Architecture reference](README.md) · [Next: ownership and tradeoffs →](ownership-and-tradeoffs.md)
