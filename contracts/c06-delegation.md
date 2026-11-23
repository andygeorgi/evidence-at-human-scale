# C06 Delegation

[Contracts](README.md) · Schema definition `#/$defs/delegation` · Groups C06-G01–G03

**Paper:** [9. Authority remains a separate boundary](../docs/paper/09-authority.md)
**Reference:** [action and degradation](../architecture/action-and-degradation.md)
**Figures:** F05 · **Evaluation tests:** EV07, EV11 (NOT RUN)

A C06 Delegation is a bounded grant for a predefined action class. Current rights, evidence, policy, target state and shared limits still govern commit. A grant is either bound to an exact proposal (an approval) or to a bounded class of actions, and only within its current scope and lifecycle.

| Group / exact type-cardinality | Emitted group and fields | Required semantics |
| --- | --- | --- |
| C06-G01 Identity/principals · Object, 1 | `identity_principals`: `grant_id`, `version`, `issuer`, `grantee`, `tenant`, `issuance_time`, `authority_basis` | Grant ID/version/schema, issuer, grantee, tenant, issuance time and authority basis. |
| C06-G02 Scope/binding · Object, 1 | `scope_binding`: `permitted_actions`, `permitted_targets`, `permitted_parameters`, `purpose`, `binding`, `evidence_constraints`, `policy_constraints` | Permitted actions/targets/parameters and purpose; exact proposal or bounded class; evidence and policy constraints. |
| C06-G03 Limits/lifecycle · Object, 1 | `limits_lifecycle`: `expiry`, `revocation`, `per_action_limits`, `cumulative_limits`, `atomic_reservation_accounting`, `notifications`, `recovery` | Expiry and revocation state/check basis; typed per-action/cumulative limits with units. Shared atomic reservation/accounting across concurrent execution; conservative unknown-outcome accounting until authoritative reconciliation; partial-effect accounting; notifications/recovery. |

## What a valid C06 does not establish

A grant is not a standing permission to act: at commit the executor rechecks permission and revocation, evidence, policy, target state and per-action and cumulative limits, including consumed and reserved capacity. A deadline cannot enlarge a grant, and no response is not approval. Where shared atomic enforcement is unsupported, the grant must declare the weaker guarantees, race windows and residual risk, and unattended operations stay disabled until the domain owner accepts them.

## Examples

- [07 Authority and delegation](../examples/07-authority-and-delegation/README.md): a bounded class grant and an exact approval (the second exact approval is in 11).
- [12 Controlled change](../examples/12-controlled-change/README.md): a new grant version with a lower limit, and its effect on a pending proposal.

[← C05 Action proposal](c05-action-proposal.md) · [Contracts](README.md) · [Next: C07 Execution receipt →](c07-execution-receipt.md)
