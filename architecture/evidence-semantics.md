# Evidence semantics

[Architecture reference](README.md) · Paper: [4. Evidence keeps its type and its ancestry](../docs/paper/04-evidence-and-lineage.md)

## Attributable assertions and scoped validation

Evidence is an attributable, scoped assertion, not guaranteed truth. A source record establishes what a source asserted in a specified version and scope. A deterministic finding reports a declared rule over specified inputs. An analytical result depends on its method and assumptions. A model inference establishes that a model produced an interpretation, not that the interpretation is true. A recommendation proposes what someone might do. Decision and execution records document choices and observed effects rather than validating the original observations.

| Boundary | Establishes | Does not establish |
| --- | --- | --- |
| Admission | A registered producer submitted an admissible kind and envelope | Semantic truth |
| Scoped validation | A named method, actor and time assessed an exact target/version and defined scope | Universal correctness outside that scope |
| Human review or approval | A person reviewed or authorized a bounded proposal | Validation of an inference |
| Hash or signature | Applicable integrity or origin properties | Correctness of the content |
| Read authorization | Permission for a principal, purpose and scope | Execution authority |
| Execution receipt | An attempt and its authoritative outcome state | Completion from submission alone |

The governed ProducerRegistry identifies producers, registry versions and permitted kinds. A specialist cannot declare source authority or promote its interpretation to a source assertion. C02 kinds are `source_record_assertion`, `deterministic_finding`, `analytical_result`, `model_inference`, `recommendation`, `decision_record` and `execution_record`. Kind, method, origin, scope and uncertainty must survive transformations and presentation compression.

## Normative notation and reference alternatives

In every crosswalk, 1 means exactly one required value; 0..n means a required array that may be empty; 1..n means a required nonempty array. Required singleton objects are neither null nor omitted. IDs and versions are nonempty strings. Every contract carries constant `contract_id` and required `schema_version`. References identify exact identities and versions, not an unspecified latest object.

Supporting references are tagged alternatives. `claim_reference` requires `record_id`, exact `version`, `claim_id` and original locator. `payload_reference` requires `record_id`, exact `version`, an explicit payload location/pointer and original locator. Both preserve exact scope, type and source provenance. Payload-only evidence needs no invented `claim_id`. A producer identity never substitutes for the original source/record locator and version or immutable snapshot.

A legitimately unavailable time or permitted domain value uses a tagged object: `state=known` requires a correctly typed value; `state=unknown` or `not_applicable` requires a reason. Stable IDs, kinds, policy references and required authority fields cannot use that escape hatch. Timestamp values are timezone-bearing RFC 3339 strings. Event, effective, source-update, ingestion and retrieval times remain distinct. Ingestion time never substitutes for event time. Clock basis and freshness policy/evaluation must be declared.

## Structural schema and semantic limits

The [documentation-only JSON Schema Draft 2020-12 bundle](../schemas/README.md) (`schemas/contracts-v1.schema.json`) declares root `$schema` https://json-schema.org/draft/2020-12/schema and `$id` `urn:evidence-at-human-scale:contracts:1`. Seven named `$defs` are selected by root `oneOf` through local `#/$defs` pointers. Contract-defined objects close `additionalProperties`; typed payload content has an explicit extension boundary, not unrestricted authority metadata. The dialect, metaschema, core and validation sources are REF-JSON01 in the [sources](../references/guidance-and-standards.md). The identifier differs from the one printed in earlier editions; see the [contract change log](../contracts/CHANGES.md).

Format annotation is not automatically format assertion. Configure timestamp assertion or separately test it; the [validation tooling](../scripts/README.md) does. Reference uniqueness, existence, exact-version/currentness, permission evaluation, lifecycle transitions, cross-record lineage and concurrent races need separate checks. A structurally valid declaration cannot establish source truth, current access, atomic accounting, verified no-effect outcomes or workflow safety. Free text can satisfy a schema while contradicting semantic intent.

Earlier internal receipts of the source edition reported 102 structural checks and 435 structural/schema instance checks as PASS within their recorded scopes. Those receipts are not part of this repository and are not reproduced here; they were structural/schema receipts, not runtime evidence or a new editorial acceptance result. This repository's own checks are listed in the [evaluation guide](../evaluation/README.md). The evaluation catalogue retains the concrete fixtures and unresolved parameters; no check is promoted to an architecture or deployment result.

[Architecture reference](README.md) · [Next: lineage, selection and disclosure →](lineage-selection-disclosure.md)
