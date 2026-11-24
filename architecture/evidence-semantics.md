# Evidence semantics

[Architecture reference](README.md) · Paper: [4. Evidence keeps its type and its ancestry](../docs/paper/04-evidence-and-lineage.md)

Evidence is an assertion made by an identified source, in an exact version and scope. It is not guaranteed truth. This page says what each kind of record establishes, how the contracts write cardinality and references, and what the JSON Schema bundle cannot check.

## Attributable assertions and scoped validation

The kind of a C02 record decides what it establishes:

- A source record (`source_record_assertion`) establishes what a source asserted, in a specified version and scope.
- A deterministic finding (`deterministic_finding`) reports what a declared rule produces from specified inputs.
- An analytical result (`analytical_result`) depends on its method and assumptions.
- A model inference (`model_inference`) establishes that a model produced an interpretation. It does not establish that the interpretation is true.
- A recommendation (`recommendation`) proposes what someone might do.
- A decision record (`decision_record`) and an execution record (`execution_record`) document a choice and its observed effects. They do not validate the original observations.

The controls around a record each establish something specific, and nothing beyond it:

| Boundary | Establishes | Does not establish |
| --- | --- | --- |
| Admission | A registered producer submitted an admissible kind and envelope | Semantic truth |
| Scoped validation | A named actor, using a named method, assessed an exact target and version within a defined scope, at a stated time | Universal correctness outside that scope |
| Human review or approval | A person reviewed or authorized an exact proposal within stated limits | Validation of an inference |
| Hash or signature | Applicable integrity or origin properties | Correctness of the content |
| Read authorization | Permission for a principal, purpose and scope | Execution authority |
| Execution receipt | An attempt and its authoritative outcome state | Completion from submission alone |

The ProducerRegistry lists the registered producers, the registry versions and the kinds each producer may submit. It is not a second store of records: the store of admitted record versions is the governed registry. A specialist cannot declare source authority, and it cannot promote its interpretation to a source assertion. Kind, method, origin, scope and uncertainty must survive every transformation and every compressed presentation.

## Normative notation and reference alternatives

In the contract pages and in the schema's `x-contract-crosswalk`, cardinality is written as follows:

- `1` means exactly one required value.
- `0..n` means a required array that may be empty.
- `1..n` means a required array with at least one item.

Required singleton objects are neither null nor omitted. IDs and versions are nonempty strings. Every contract carries a constant `contract_id` and a required `schema_version`. A reference names an exact identity and version. It never points at an unspecified latest object.

A supporting reference takes one of these tagged forms:

- `claim_reference` requires `record_id`, an exact `version`, `claim_id` and the original locator.
- `payload_reference` requires `record_id`, an exact `version`, an explicit payload location or pointer, and the original locator.

Both preserve the exact scope, type and source provenance. Payload-only evidence needs no invented `claim_id`. A producer identity never takes the place of the original locator of the source or record and its version, or of an immutable snapshot.

A time or a permitted domain value that is legitimately unavailable is written as a tagged object. With `state=known` it carries a correctly typed value. With `state=unknown` or `state=not_applicable` it carries a reason. Stable IDs, kinds, policy references and required authority fields cannot use this form. Timestamps are RFC 3339 strings that carry a time zone. Event time, effective time, source-update time, ingestion time and retrieval time stay distinct, and ingestion time never stands in for event time. The clock basis, the freshness policy and the freshness evaluation must be declared.

## Structural schema and semantic limits

The [JSON Schema bundle](../schemas/README.md) (`schemas/contracts-v1.schema.json`) is for documentation only. It uses JSON Schema Draft 2020-12: the root `$schema` is https://json-schema.org/draft/2020-12/schema, and the `$id` is `urn:evidence-at-human-scale:contracts:1`. The root `oneOf` selects one of seven named `$defs` through local `#/$defs` pointers. Objects that a contract defines do not accept additional properties. Typed payload content has an explicit extension boundary. Authority metadata does not: arbitrary keys are not allowed there. REF-JSON01 in the [sources](../references/guidance-and-standards.md) lists the dialect, metaschema, core and validation sources. The `$id` is versioned with the contracts; see the [contract change record](../contracts/CHANGES.md).

A `format` keyword annotates a value. It asserts nothing unless the validator is configured to. Either configure the validator to assert timestamps or test them separately; the [validation tooling](../scripts/README.md) configures the assertion. The schema cannot check these, so each needs a separate check: reference uniqueness and existence, exact version and currentness, permission evaluation, lifecycle transitions, lineage across records, and concurrent races. A structurally valid declaration cannot establish source truth, current access, atomic accounting, verified no-effect outcomes or workflow safety. Free text can satisfy a schema and still contradict its intended meaning.

This repository's own checks are listed in the [evaluation guide](../evaluation/README.md). The schema bundle's 102 embedded examples (38 valid, 64 invalid) and the 37 synthetic example instances are checked by `scripts/validate_examples.py`, which adds semantic checks that a schema cannot express. These are deterministic checks on invented data. They are not runtime evidence, and no check counts as an evaluation, architecture or deployment result. The [evaluation catalogue](../evaluation/catalogue/README.md) holds the concrete fixtures and the unresolved parameters.

[Architecture reference](README.md) · [Next: lineage, selection and disclosure →](lineage-selection-disclosure.md)
