# 9. Authority remains a separate boundary

[← 8. Uncertainty](08-uncertainty.md) · [Paper contents](README.md) · [Next: degraded operation →](10-degraded-operation.md)

Reading, synthesis, approval, and execution are different permissions. Separate the requestor and accountable approver, read-authorized context service, workload or orchestration identity, executor or action gateway, and authoritative target verifier. A service identity never grants the requestor rights to every underlying source or the assistant permission to perform every action.

Source documents, tool responses, and model outputs are untrusted data. They cannot alter permissions, priorities, obligations, controls, or delegation. Authorization applies before model context and throughout derived disclosure: claims, summaries, relationships, counts, selection manifests, limitation messages, caches, and history can all reveal protected information.

<!-- figure:F05:start -->
<!-- figure:F05:end -->

## Approval is not commit

Approval binds an exact versioned proposal within stated limits. A valid bounded grant can authorize a predefined action class without a fresh approval for each instance, but only within its explicit scope. Neither approval nor delegation substitutes for the executor's current checks. The [action and degradation reference](../../architecture/action-and-degradation.md) retains the full proposal, grant, and receipt requirements.

At commit, the executor rechecks current permission and revocation, evidence, policy, target state, and per-action and cumulative limits, including consumed and reserved capacity. Where supported, these checks, shared reservation or consumption, and commit are atomic. An atomic target-version check alone does not prevent concurrent grant-limit overspend.

Unknown execution retains its reservation or equivalent conservative accounting until authoritative reconciliation. Timeout or lease expiry does not restore allowance. Known partial effects count against cumulative limits and require reconciliation or compensation under policy. Allowance is restored only under a documented confirmed-effect policy, not by assuming silence means no effect.

A verified completion requires authoritative evidence of the outcome. Unknown and partial outcomes remain unresolved and require reconciliation. Verified no-effect means authoritative confirmation that the action caused no business effect, not merely that a response was absent. The full terminal-state and verification requirements remain in the [action and degradation reference](../../architecture/action-and-degradation.md).

<!-- figure:F06:start -->
<!-- figure:F06:end -->

External targets may not support atomic checks and business commit. Declare the weaker guarantees, race windows, reservation and reconciliation behavior, and residual risk. Local idempotency is not exactly-once business execution. If shared atomic grant-limit enforcement is unsupported, disable unattended operations that the domain owner has not explicitly accepted; irreversible effects cannot be undone by software rollback.

**See it working:** the [worked example](../../examples/README.md) includes a bounded delegation, a proposal the delegation does not cover, a blocked action with a verified no-effect receipt, and an unknown outcome that keeps its reservation.

[← 8. Uncertainty](08-uncertainty.md) · [Paper contents](README.md) · [Next: degraded operation →](10-degraded-operation.md)
