# Action and degradation

[Architecture reference](README.md) · Paper: [9. Authority](../docs/paper/09-authority.md) · [10. Degraded operation](../docs/paper/10-degraded-operation.md)

Approval, commit and execution are separate steps with separate checks. An approval authorizes one exact proposal, or a bounded grant covers a predefined class of actions. At commit, the executor rechecks the current state and the shared limits, and an authoritative verification confirms the outcome. This page also gives the receipt states, the weaker guarantees of external targets, and a table of failures with the owner who recovers from each.

## Approval, commit and shared capacity

An approval authorizes one exact, versioned proposal within stated limits. A valid bounded grant may authorize a predefined class of actions without a fresh approval for each action, but only within its current scope and lifecycle. A missing response is not an approval, and a deadline cannot enlarge a grant. Permission to read and to synthesize is not permission to execute. No path lets synthesis trigger execution directly.

The authority figure (Figure F05, [chapter 9](../docs/paper/09-authority.md)) separates the requestor and the approver, the read-authorized context service, the workload or orchestration service, the executor (the action gateway) and the authoritative target. One person may hold more than one role only where the domain's policy explicitly allows it. A revocation also reaches the checks that run before commit. At commit, the executor rechecks the following against the current state:

- the current permission, and whether it has been revoked;
- the evidence;
- the policy;
- the state of the target;
- the per-action limits;
- the cumulative limits, including consumed and reserved capacity.

A proposal and a grant each state their units, their accounting scope and window, and what happens when the limit is exhausted. An upstream check or an earlier approval does not excuse this check at the current boundary.

Where supported, the executor checks the conditions, reserves or consumes shared capacity, and commits as one atomic operation. Reservation and accounting must stay atomic across concurrent executions. An atomic check of the target's version does not, by itself, stop a grant limit from being overspent. An unknown outcome keeps its reservation, or an equivalent conservative accounting, until authoritative reconciliation. A timeout or a lease expiry cannot restore the allowance, because that would allow duplicate or over-limit actions. Known partial effects are charged against the cumulative limits, and they are reconciled or compensated under policy.

## Receipt interpretation and weaker external guarantees

| Receipt state | Interpretation and required treatment |
| --- | --- |
| `submitted` | An attempt was submitted. Business completion is not established. Obtain an authoritative verification of the outcome. |
| `unknown` | The effects are unresolved. Keep the reservation or a conservative accounting, and reconcile with the authoritative target. Do not retry blindly. |
| `partial` | Some effects are known, and others are unresolved. Charge the known effects against the cumulative limits. Assign responsibility for notification, reconciliation and compensation. |
| `completed_verified` | Authoritative outcome references establish the verified effects, within the declared method, actor, time and scope. Submission alone is not enough. |
| `not_executed_verified` | Terminal only after an authoritative rejection, a failure before any effect, or a cancellation with no business effect. It requires a reason, the verifier, the method and the time, and a reference to the target and the action. A timeout is not evidence of no effect. |

Allowance is reconciled or restored only under a documented confirmed-effect policy that rests on authoritative reconciliation. That includes the terminal outcome `not_executed_verified` (a verified no-effect). Define when a reservation expires and how it is reconciled, but never treat expiry as evidence that nothing happened. Unresolved effects stay unknown. Known partial effects stay accounted for separately.

An external target may not take part in the atomic checks and the business commit. For such a target, document the weaker guarantees, the race windows, how reservation and reconciliation behave, and the residual risk. Do not imply that the business effect is atomic. Local idempotency is not exactly-once execution. If shared atomic enforcement of grant limits is not supported, declare that limitation and disable any unattended operation that the domain has not accepted. Software rollback cannot undo an irreversible business effect.

## Full failure response and recovery ownership

Whether information is available and whether authority is valid are separate questions. Figure F07 ([chapter 10](../docs/paper/10-degraded-operation.md)) shows how they combine:

- Current, sufficient evidence and valid authority: normal review, and an action that is checked separately.
- Partial or stale evidence: only an explicitly limited view, and no action that depends on freshness.
- Unavailable evidence: no action that depends on that evidence. A permitted native or manual fallback remains possible.
- Invalid or unavailable authority, in any information state: no execution and no bypass.

| Failure | Visible response and authority treatment | Recovery owner |
| --- | --- | --- |
| Source failure | Mark unavailable or partial; block unsupported evidence-dependent action | Source/registry owner |
| Model failure | Use a qualified deterministic template or a permitted native or manual route | Synthesis owner |
| Malformed record | Quarantine; do not silently admit it or repair its authority | Admission owner |
| Authorization or policy failure | No new protected disclosure or execution; no bypass | Access/policy owner |
| Gateway failure | No authority bypass; a submitted attempt may need reconciliation | Gateway/target owner |
| Stale historical view | Show version and limitation only under current viewing permission | Lifecycle/access owner |
| Deadline or budget exhausted | Explicit partial completion and scope; mandatory routes stay in place | Orchestration/obligation owner |
| Action timeout | Unknown effects; keep capacity reserved conservatively; no blind retry | Executor/reconciliation owner |
| Late correction or challenge | Reassess lineage; invalidate derivatives, caches and pending approvals | Lifecycle owner |
| Mandatory-channel failure | Escalate through the designated, authorized native or manual routes | Escalation owner |

**Worked examples:** [blocked action](../examples/08-blocked-action/README.md) · [unknown outcome](../examples/09-unknown-outcome/README.md) · [degraded modes](../examples/10-degraded-modes/README.md) · [late correction](../examples/11-late-correction/README.md).

[← Lineage, selection and disclosure](lineage-selection-disclosure.md) · [Architecture reference](README.md) · [Next: ownership and tradeoffs →](ownership-and-tradeoffs.md)
