# C02 Evidence

[Contracts](README.md) · Schema definition `#/$defs/evidence` · Groups C02-G01–G13

**Paper:** [4. Evidence keeps its type and its ancestry](../docs/paper/04-evidence-and-lineage.md)
**Reference:** [evidence semantics](../architecture/evidence-semantics.md); [lineage, selection and disclosure](../architecture/lineage-selection-disclosure.md)
**Figures:** F02, F03 · **Evaluation tests:** EV01, EV02, EV03, EV07, EV12 (NOT ASSESSED)

C02 Evidence has a stable identity and immutable version, registered producer and permitted kind, source locator, scope, timing, method, and relevant qualifications. Admission establishes admissibility of the envelope and kind. Scoped validation records who assessed which target, by which method, when, and within what scope. Neither establishes universal correctness.

| Group / exact type-cardinality | Emitted group and fields | Required semantics |
| --- | --- | --- |
| C02-G01 Identity/schema · Object, 1 | `identity_schema`: `record_id`, `version`, `kind` | `record_id`, `version`, `contract_id=C02`, `schema_version` and registered kind. Stable identity; immutable version. |
| C02-G02 Producer/admission · Object, 1 | `producer_admission`: `producer_id`, `registry_version`, `permitted_kind_reference`, `admission_status`, `admission_time` | Producer ID, registry version, permitted-kind reference, admission status/time. Admission never establishes truth. |
| C02-G03 Content · Object, 1 | `content`: `#/$defs/evidence/$defs/content` | Explicitly discriminated nonempty claims array or typed payload; each claim has ID/text and kind remains visible. A claim ID identifies one claim within one exact version of the record (check `REF008`): the same ID in another record or in another version is another claim. Supporting references discriminate `claim_reference` and `payload_reference`; payload-only records need no invented `claim_id`. |
| C02-G04 Scope · Object, 1 | `scope`: `#/$defs/evidence/$defs/scope` | Entity references 1..n; task, jurisdiction, units and interpretation each present. Explicit unknown/not_applicable only where permitted. |
| C02-G05 Original source · Object, 1 | `original_source`: `#/$defs/evidence/$defs/source_locator` | Exact source/record locator and original version or immutable snapshot; producer identity is not a substitute. `claim_reference` retains `record_id`, exact version, `claim_id`, original locator; `payload_reference` retains `record_id`, exact version, explicit payload location/pointer, original locator. Both retain the scope, type and source provenance. |
| C02-G06 Method · Object, 1 | `method`: `#/$defs/evidence/$defs/method` | Source and producer identities, and the versions of the applicable rule, model, prompt, tool or analytical method. Each version is explicitly known, or inapplicable with a reason. |
| C02-G07 Times · Object, 1 | `times`: `event`, `effective`, `source_update`, `ingestion`, `retrieval`, `clock_basis`, `freshness` | Distinct event, effective, source-update, ingestion and retrieval times; clock basis and freshness policy/evaluation. Never substitute ingestion for event time. |
| C02-G08 Lineage · Object, 1 | `lineage`: `parent_references`, `typed_relationships` | Parent references 0..n; typed relationships 0..n, each with endpoints, relationship type and `asserted_by`. |
| C02-G09 Coverage/uncertainty · Object, 1 | `coverage_uncertainty`: `coverage_statement`, `uncertainty`, `limitations` | Scoped coverage statement, uncertainty state/basis, limitations 0..n. No unsupported probability or completeness claim. |
| C02-G10 Validation · Array, 0..n | `validation`: typed array/object | Separate validation records: ID/version, target version, method, actor, time, scope, outcome and limitations. Empty means none, not validated. |
| C02-G11 Disclosure/permissions · Object, 1 | `disclosure_permissions`: `tenant`, `classification`, `purpose`, `disclosure_restrictions`, `permission_policy_references` | Tenant, classification, purpose, restrictions and permission-policy references/version. Effective access requires current checks. |
| C02-G12 Lifecycle · Object, 1 | `lifecycle`: `state`, `effective_time`, `reason`, `replacement_reference` | One of current, superseded, withdrawn, revoked or expired, with an effective time, a reason and a replacement reference where applicable. |
| C02-G13 Integrity · Object, 1 | `integrity`: typed array/object | State, plus whatever hash, signature, algorithm and origin metadata is available. Absence of integrity evidence is explicit. |

The seven evidence kinds are `source_record_assertion`, `deterministic_finding`, `analytical_result`, `model_inference`, `recommendation`, `decision_record` and `execution_record`. A `model_inference` is never relabeled as a source assertion, and a superseded record names its `replacement_reference`.

**Lineage.** A parent reference names an input the record was derived from, at an exact version. A `source_record_assertion` is an original and names none (check `LIN007`). A parent had been admitted and ingested when its child was admitted, and equality counts (check `LIN008`). At commit, a derived record is relied on only while each parent it declares, at any depth, is current at the attempt ([C06](c06-delegation.md)). A typed `supersession` goes from the record that holds it to the older version it replaces, and a record does not supersede itself (check `LIN009`); the older version records the replacement (checks `LIN003` and `LIFE001`). Two source assertions that declare the same source system, record locator and immutable version (an original version or a snapshot) are one origin when corroboration is counted, whatever their record ids are, and nothing else is matched (checks `COR001`, `COR002`). These checks compare the records of the set with one another. They do not judge what a derivation means, and an input that a record does not declare as a parent is not seen.

**Versions.** The schema accepts any non-empty version name, and a record is always found by its exact version: `v1` and `v01` are two names. Where an order is needed (the grant in force, the latest receipt, a replacement that must be later), the reference reads it from the numbers in the names (`v2` before `v10`, and `v1.2` is the numbers 1 and 2) and does not guess where that gives none. Two names with the same numbers, or a name with no number, among the versions of one record are a finding (check `LIFE006`). A domain that needs more should name its versions so that their order is unambiguous.

## What a valid C02 does not establish

Admission establishes that a registered producer submitted an admissible kind and envelope, not semantic truth. A hash or signature establishes integrity or origin properties, not the correctness of the content. Reference existence, exact-version currentness, lineage across records and lifecycle transitions need separate checks; the [example checks](../scripts/README.md) perform them on the synthetic scenario.

## Examples

- [01 Source records](../examples/01-source-records/README.md): raw system exports and the C02 source assertions normalized from them.
- [03 Lineage and common origin](../examples/03-lineage-and-common-origin/README.md): a deterministic finding, two summaries that share one root, and a scoped validation.
- [04 Selection and missingness](../examples/04-selection-and-missingness/README.md): the observation, stale and dependency-failure records behind the gaps.
- [11 Late correction](../examples/11-late-correction/README.md): a superseding version and its invalidated derivatives.

[← C01 Context](c01-context.md) · [Contracts](README.md) · [Next: C03 Selection →](c03-selection.md)
