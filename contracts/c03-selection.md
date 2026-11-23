# C03 Selection

[Contracts](README.md) · Schema definition `#/$defs/selection` · Groups C03-G01–G06

**Paper:** [5. Context governs what is selected](../docs/paper/05-context-and-attention.md); [8. Uncertainty is part of the result](../docs/paper/08-uncertainty.md)
**Reference:** [lineage, selection and disclosure](../architecture/lineage-selection-disclosure.md)
**Figures:** F02, F03, F04, F09 · **Evaluation tests:** EV03, EV04, EV05, EV06, EV09, EV10, EV12 (NOT RUN)

C03 Selection binds authorized retrieval coverage to selected evidence, exclusions, grouping reasons, missingness, and constraints. A selected scope is not whole-corpus coverage. The reader must be able to distinguish an input that was expected but absent from one deliberately excluded, inaccessible, or outside the retrieval scope.

| Group / exact type-cardinality | Emitted group and fields | Required semantics |
| --- | --- | --- |
| C03-G01 Identity/scope · Object, 1 | `identity_scope`: `selection_id`, `version`, `context_reference`, `permitted_source_scope`, `time_scope`, `as_of`, `policy_references` | Selection ID/version, exact C01 reference, permitted source/time scope, as-of and policy versions. Relevance/priority/grouping/coverage produces the manifest from authorized candidates and retrieval coverage, not before selection. |
| C03-G02 Retrieval · Array, 1..n | `retrieval`: `retrieval_unit_id`, `authorized_scope`, `authorization_reference`, `status`, `attempted_at`, `completed_at`, `reason`, `summary_visibility`, `summary` | Authorized retrieval units, status, attempted/completed times and reasons; permission-safe summaries when details cannot be disclosed. |
| C03-G03 Disposition · Array, 0..n | `disposition`: `record_reference`, `state`, `reason` | Eligible/included/excluded exact record references with explicit reasons. Empty does not imply whole-corpus absence. |
| C03-G04 Obligations · Array, 0..n | `obligations`: typed array/object | Obligation ID, policy basis, priority/deadline, owner, delivery/acknowledgement/escalation state. Acknowledgement is not resolution. |
| C03-G05 Conflicts/gaps · Object, 1 | `conflicts_gaps`: `conflicts`, `missingness` | Conflict entries and missingness entries, each 0..n: scope, referenced claims or expected evidence, materiality, reason and assessment basis. All seven canonical missingness definitions in [lineage, selection and disclosure](../architecture/lineage-selection-disclosure.md#versioned-ancestry-and-missingness) apply without conflation. |
| C03-G06 Coverage · Object, 1 | `coverage`: `#/$defs/evidence/$defs/coverage` | Declared scope, complete / partial / not-assessed status and limitations. Complete applies only to declared assessed scope. |

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

A manifest with no dispositions cannot imply whole-corpus absence, and `complete` coverage applies only to the declared assessed scope. Existence of an inaccessible source is disclosed only through a permission-safe summary.

## Examples

- [04 Selection and missingness](../examples/04-selection-and-missingness/README.md): one selection that carries all seven missingness states.

[← C02 Evidence](c02-evidence.md) · [Contracts](README.md) · [Next: C04 Decision packet →](c04-decision-packet.md)
