# C03 Selection

[Contracts](README.md) · Schema definition `#/$defs/selection` · Groups C03-G01–G06

**Paper:** [5. Context and selection](../docs/paper/05-context-and-attention.md); [8. Uncertainty is part of the result](../docs/paper/08-uncertainty.md)
**Reference:** [lineage, selection and disclosure](../architecture/lineage-selection-disclosure.md)
**Figures:** F02, F03, F04, F09 · **Evaluation tests:** EV03, EV04, EV05, EV06, EV09, EV10, EV12 (NOT ASSESSED)

C03 Selection binds authorized retrieval coverage to selected evidence, exclusions, grouping reasons, missingness, and constraints. A selected scope is not whole-corpus coverage. The reader must be able to distinguish an input that was expected but absent from one deliberately excluded, inaccessible, or outside the retrieval scope. Permission is decided first: an input the reader may not know about has no entry at all, and the missingness states below describe only inputs the reader may know about.

| Group / exact type-cardinality | Emitted group and fields | Required semantics |
| --- | --- | --- |
| C03-G01 Identity/scope · Object, 1 | `identity_scope`: `selection_id`, `version`, `context_reference`, `permitted_source_scope`, `time_scope`, `as_of`, `policy_references` | Selection ID and version, exact C01 reference, permitted source and time scope, as-of and policy versions. The as-of time is the context's, and the time scope lies within the context's time interval (check `PKT002`). Relevance, priority, grouping and coverage produce the manifest from authorized candidates and retrieval coverage, not before selection. |
| C03-G02 Retrieval · Array, 1..n | `retrieval`: `retrieval_unit_id`, `authorized_scope`, `authorization_reference`, `status`, `attempted_at`, `completed_at`, `reason`, `summary_visibility`, `summary` | Authorized retrieval units, status, attempted/completed times and reasons; permission-safe summaries when details cannot be disclosed. |
| C03-G03 Disposition · Array, 0..n | `disposition`: `record_reference`, `state`, `reason` | Exact record references that are eligible, included or excluded, each with an explicit reason. An empty list does not imply whole-corpus absence. |
| C03-G04 Obligations · Array, 0..n | `obligations`: typed array/object | Obligation ID, policy basis, priority and deadline, owner, and the delivery, acknowledgement and escalation state. An acknowledgement is not a resolution. Each obligation the selection lists is mandatory for the packet built on it, which carries all of them and no other (checks `PKT008`, `PKT009`). |
| C03-G05 Conflicts/gaps · Object, 1 | `conflicts_gaps`: `conflicts`, `missingness` | Conflict entries and missingness entries, each 0..n: scope, referenced claims or expected evidence, materiality, reason and assessment basis. All seven canonical missingness definitions in [lineage, selection and disclosure](../architecture/lineage-selection-disclosure.md#versioned-ancestry-and-missingness) apply without conflation. |
| C03-G06 Coverage · Object, 1 | `coverage`: `#/$defs/evidence/$defs/coverage` | Declared scope, a status of complete, partial or not-assessed, and limitations. Complete applies only to declared assessed scope. |

## The seven missingness entries

Each missingness state requires different supporting fields, which is what keeps the states from collapsing into one another.

| State | Additionally required by the schema |
| --- | --- |
| `missing` | none beyond the common fields (scope, expected evidence, materiality, reason, assessment basis) |
| `not_retrieved` | `retrieval_reference`, `retrieval_completed: true`, `relevant_record_count: 0`, `completed_at` |
| `inaccessible` | `permission_decision_reference`, `permission_safe_summary` |
| `unavailable` | `dependency_failure_reference` |
| `negative` | `observation_reference`, `method`, `time`, `coverage` |
| `not_assessed` | `assessment_performed: false` |
| `stale` | `available_record`, `freshness` |

## What a valid C03 does not establish

A manifest with no dispositions cannot imply whole-corpus absence, and `complete` coverage applies only to the declared assessed scope. A `not_retrieved` entry rests on one retrieval unit of its own selection. The reference names the unit by its id and by the version of the selection that lists it, and it must be listed once there and completed (check `REF006`), by the selection's as-of time and at the completion time the entry states, compared as instants (check `MISS001`). A unit of another selection with the same name is another run, and an entry of a packet is held to the selection the packet is bound to. The schema cannot decide whether a reader may know that a source exists. That decision comes from a permission decision outside the contract. It must be bound to the requesting principal of the C01 context and to that context's tenant and permitted purpose (a decision that names no tenant or no purpose binds to nobody), and it comes first: an `inaccessible` entry exists only where such a decision allows it, and every field of the entry comes from the decision, none from the source (no name, type, count, state, age or materiality). The check `DISC002` finds an entry that the decision does not allow, `DISC003` finds an entry that differs from the decision's generic disclosure in any field, wording or sibling, `DISC004` finds a decision that does not bind to the requesting principal, and `DISC005` finds a named record that belongs to another tenant or purpose.

## Examples

- [04 Selection and missingness](../examples/04-selection-and-missingness/README.md): one selection that carries all seven missingness states.

[← C02 Evidence](c02-evidence.md) · [Contracts](README.md) · [Next: C04 Decision packet →](c04-decision-packet.md)
