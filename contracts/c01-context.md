# C01 Context

[Contracts](README.md) · Schema definition `#/$defs/context` · Groups C01-G01–G04

**Paper:** [3. The reference architecture](../docs/paper/03-governed-context.md); [5. Context and selection](../docs/paper/05-context-and-attention.md); [9. Authority remains a separate boundary](../docs/paper/09-authority.md)
**Reference:** [lineage, selection and disclosure](../architecture/lineage-selection-disclosure.md); [action and degradation](../architecture/action-and-degradation.md)
**Figures:** F02, F03, F05 · **Evaluation tests:** EV06, EV07, EV08 (NOT ASSESSED)

C01 Context identifies the requesting principal, permitted task and purpose, relevant entities, scope, time, and policy constraints. The workload identity is separate. Retrieval is authorized for that context before evidence enters model context, not merely filtered after an answer has been produced.

| Group / exact type-cardinality | Emitted group and fields | Required semantics |
| --- | --- | --- |
| C01-G01 Identity/principal · Object, 1 | `identity_principal`: `context_id`, `version`, `tenant`, `requesting_principal`, `workload_identity` | Context ID/version, contract/schema versions, tenant and requesting principal; workload identity remains separate. |
| C01-G02 Task/purpose/entity · Object, 1 | `task_purpose_entity`: `task`, `permitted_purpose`, `entity_references` | Task and permitted purpose; entity references 1..n; no unspecified blanket purpose. |
| C01-G03 Time/risk/policy · Object, 1 | `time_risk_policy`: `time_interval`, `as_of`, `risk_class`, `policy_references` | Time interval/as-of, risk class, applicable policy references 1..n and exact versions. |
| C01-G04 Authorization · Object, 1 | `authorization`: `#/$defs/evidence/$defs/authorization_check` | Read-scope decision reference, actor/time/version and restrictions; not execution permission. |

## What a valid C01 does not establish

A context records the read-scope decision that applied when the packet was built. It is not execution permission, and it does not make later views, cache serves or history access authorized: those are rechecked at the time they happen.

## Examples

- [02 Context and normalization](../examples/02-context-and-normalization/README.md): the context for the worked decision (`CTX-0417`).

[Contracts](README.md) · [Next: C02 Evidence →](c02-evidence.md)
