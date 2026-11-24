# C06 Delegation

[Contracts](README.md) · Schema definition `#/$defs/delegation` · Groups C06-G01–G03

**Paper:** [9. Authority remains a separate boundary](../docs/paper/09-authority.md)
**Reference:** [action and degradation](../architecture/action-and-degradation.md)
**Figures:** F05 · **Evaluation tests:** EV07, EV11 (NOT ASSESSED)

A C06 Delegation records what has been authorized: either an **exact approval** of one proposal version, or a **bounded grant** for a class of actions. Neither is an instruction to act. Current rights, evidence, policy, target state and shared limits still govern commit, and a grant works only within its current scope and lifecycle.

| Group / exact type-cardinality | Emitted group and fields | Required semantics |
| --- | --- | --- |
| C06-G01 Identity/principals · Object, 1 | `identity_principals`: `grant_id`, `version`, `issuer`, `grantee`, `tenant`, `issuance_time`, `authority_basis` | Grant ID, version and schema, issuer, grantee, tenant, issuance time and authority basis. The `grantee` is the executor that receives the authority and performs the action, never the assistant workload that proposes it (checks `ROLE006`–`ROLE008`). |
| C06-G02 Scope/binding · Object, 1 | `scope_binding`: `permitted_actions`, `permitted_targets`, `permitted_parameters`, `purpose`, `binding`, `evidence_constraints`, `policy_constraints` | Permitted actions, targets and parameters, and the purpose; an exact proposal or a bounded class; evidence and policy constraints. |
| C06-G03 Limits/lifecycle · Object, 1 | `limits_lifecycle`: `expiry`, `revocation`, `per_action_limits`, `cumulative_limits`, `atomic_reservation_accounting`, `notifications`, `recovery` | Expiry, and the revocation state and the basis for checking it; typed per-action and cumulative limits with units. Shared atomic reservation and accounting across concurrent execution; conservative accounting for an unknown outcome until authoritative reconciliation; accounting for partial effects; notifications and recovery. |

## Two bindings

`scope_binding.binding` has one of two shapes, told apart by `binding_type`.

| `binding_type` | Fields | Use |
| --- | --- | --- |
| `exact_proposal` | `proposal_reference`: the C05 `id` and `version` | An approval. It covers that proposal version and nothing else, so a corrected proposal needs a new approval. |
| `bounded_class` | `class_id`, `class_version`, `bounds` | A bounded grant for actions that are low-risk, reversible and within stated bounds, and may repeat inside them. |

## Values the schema fixes

| Field | Values | What they mean |
| --- | --- | --- |
| `atomic_reservation_accounting.enforcement` | `shared_atomic`, `unsupported` | `unsupported` requires at least one entry in each of `weaker_guarantees`, `race_windows` and `residual_risk`. |
| `atomic_reservation_accounting.unknown_outcome_policy` | `retain_reservation`, `equivalent_conservative_accounting` | An unknown outcome keeps its allowance counted until authoritative reconciliation. |
| `revocation.state` | a string; the reference check reads `not_revoked` and `revoked` | Only `not_revoked` shows that the grant is unrevoked, and only if `checked_at` is at or before the attempt. From `checked_at` on, `revoked` blocks as `GRANT_REVOKED`. A check recorded after the attempt blocks as `REVOCATION_NOT_YET_OBSERVED`, a check with no known time as `REVOCATION_TIME_UNKNOWN`, and any other state as `REVOCATION_UNVERIFIED`. |

## What the commit check asks of a grant

At commit, the executor asks five questions, each as of the attempt: what was available and valid at that time counts, and nothing later does. The reference check in [`scripts/eahs/gateway.py`](../scripts/eahs/gateway.py) answers them and returns every reason that applies, not only the first. Each reason code is explained in [example 08](../examples/08-blocked-action/README.md#the-commit-time-reason-codes). A required time that is missing or unknown blocks the attempt.

1. **Is the grant usable?** A revocation check made at or before the attempt (`REVOCATION_NOT_YET_OBSERVED`, `REVOCATION_TIME_UNKNOWN`) shows it is not revoked (`GRANT_REVOKED`) and its revocation state can be verified (`REVOCATION_UNVERIFIED`). It has not expired (`GRANT_EXPIRED`), it had been issued (`GRANT_NOT_YET_VALID`), no newer version is in force (`GRANT_SUPERSEDED`), and its issuance and expiry times are known (`GRANT_TIME_UNKNOWN`).
2. **Does it cover this action?** An exact approval is bound to this proposal version (`GRANT_NOT_BOUND`). The action (`ACTION_NOT_PERMITTED`), the target (`TARGET_NOT_PERMITTED`) and every parameter, by name and type (`PARAMETER_NOT_PERMITTED`), are permitted.
3. **Is the evidence still good?** Every record the proposal cites and every record in the grant's `evidence_constraints` must exist (`EVIDENCE_UNRESOLVED`), have been admitted at or before the attempt (`EVIDENCE_NOT_YET_ADMITTED`), have the times the check needs (`EVIDENCE_TIME_UNKNOWN`), be current at the time of the attempt (`EVIDENCE_NOT_CURRENT`) and be within its freshness policy (`EVIDENCE_STALE`). Evidence constraints name exact record versions, so superseding one of those records blocks the action.
4. **Do the preconditions hold?** Each precondition has a rule (`PRECONDITION_UNDEFINED`) and the rule is satisfied by evidence that was usable at the attempt (`PRECONDITION_FAILED`).
5. **Is there allowance left?** The action stays within each per-action limit (`PER_ACTION_LIMIT`) and each cumulative limit in its accounting window, counting capacity that is already consumed or reserved (`CUMULATIVE_LIMIT`).

## An instance, abridged

The exact approval in [example 07](../examples/07-authority-and-delegation/README.md), with most fields left out. `"…"` stands for content that is omitted here. The full file is [`c06-GRT-APPR-0417-A-v1.json`](../examples/07-authority-and-delegation/c06-GRT-APPR-0417-A-v1.json), and a test checks that this excerpt matches it. The revocation shown is the end-of-day state, after the 13:45 correction in [example 11](../examples/11-late-correction/README.md).

```json
{
  "contract_id": "C06",
  "identity_principals": {
    "grant_id": "GRT-APPR-0417-A",
    "version": "v1",
    "issuer": "person:ap-controller-01",
    "grantee": "workload:payment-executor",
    "issuance_time": "2026-11-23T10:40:00Z"
  },
  "scope_binding": {
    "permitted_actions": ["release_payment"],
    "permitted_targets": [{ "entity_type": "invoice", "entity_id": "INV-2026-0417" }],
    "binding": {
      "binding_type": "exact_proposal",
      "proposal_reference": { "contract_id": "C05", "id": "ACT-REL-0417", "version": "v1" }
    },
    "evidence_constraints": ["…"]
  },
  "limits_lifecycle": {
    "expiry": "2026-11-23T17:00:00Z",
    "revocation": { "state": "revoked", "checked_at": "2026-11-23T13:45:00Z" },
    "per_action_limits": [{ "limit_id": "LIM-A-EUR", "quantity": 18400, "units": "EUR" }],
    "atomic_reservation_accounting": {
      "enforcement": "unsupported",
      "unknown_outcome_policy": "retain_reservation"
    }
  }
}
```

## What a valid C06 does not establish

The `issuer` is the approver. It is a different field, and a different role, from the requestor that C01 names (`requesting_principal`): no contract treats the two as the same. Where a domain's policy explicitly permits one person to hold both, each field still records its own role. A person who reviews the decision packet, the Decision Owner, may also be the issuer where the policy says so; the record of the review stays in the packet's review history, and the issuer field names the person who approved.

A grant is not a standing permission to act: at commit the executor rechecks permission and revocation, evidence, policy, target state and per-action and cumulative limits, including consumed and reserved capacity. A deadline cannot enlarge a grant, and no response is not approval. Where shared atomic enforcement is unsupported, the grant must declare the weaker guarantees, race windows and residual risk, and unattended operations stay disabled until the domain owner accepts them.

## Examples

- [07 Authority and delegation](../examples/07-authority-and-delegation/README.md): a bounded grant and an exact approval (the second exact approval is in 11).
- [12 Controlled change](../examples/12-controlled-change/README.md): a new grant version with a lower limit, and its effect on a pending proposal.

[← C05 Action proposal](c05-action-proposal.md) · [Contracts](README.md) · [Next: C07 Execution receipt →](c07-execution-receipt.md)
