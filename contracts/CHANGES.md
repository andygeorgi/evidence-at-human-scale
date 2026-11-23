# Contract changes

Every change to what the contracts accept or reject is recorded here, newest first. Changes to wording, examples or crosswalk metadata are recorded too, so a reader can see that they did not alter validation.

The schema file is [`schemas/contracts-v1.schema.json`](../schemas/contracts-v1.schema.json). See [Schemas](../schemas/README.md) for how it is organized.

## How to record a change

For each change give: the previous form, the new form, the reason, the compatibility impact (does any previously valid instance become invalid, or the reverse?) and the migration. Then update the validation-surface hash below. `python scripts/schema_surface_hash.py --check` fails if the hash and the schema disagree.

## v1.0.0-rc.1 (release candidate)

First public candidate. The definitions were carried over from an earlier review draft that was never published, so there is no public migration. Before release, only identity and annotations were normalized. **What validates did not change.**

| # | Change | Previous form | New form | Why | Compatibility | Migration |
|---|---|---|---|---|---|---|
| 1 | Schema identity: `$id`, `title`, `description` | An identifier, title and description that named the review draft they came from | `$id` `urn:evidence-at-human-scale:contracts:1`; a title and description that describe the contracts | A public schema needs an identity that is stable and about the contracts | None for instances: an instance never contains `$id`. A consumer that registered the old identifier must register the new one | Use the new `$id` |
| 2 | `$defs` descriptions (7) | Descriptions that pointed at sections of the review draft | Self-contained descriptions of each contract | A reader of the schema should not need a document that is not public | None: annotation | None |
| 3 | `x-documentation.source` and `reference_metadata` | Build-time provenance fields | Trimmed to what a reader needs | Remove build traceability | None: annotation | None |
| 4 | `violated_requirement` in the 64 invalid examples | Each began with a section number of the review draft | Each reads as a self-contained requirement | Same reason as 2 | None: the invalid examples are rejected for the same reasons | None |
| 5 | `x-contract-crosswalk` (41 rows) | Fields `spec_group`, `spec_type_cardinality`, `required_semantics_verbatim`, `diagram_links`, `spec_section`, `page_slots` | Fields `group_name`, `type_cardinality`, `required_semantics`, `figure_links`; the section and page fields are removed; figure links point at the redesigned [figures](../figures/README.md) F01–F11 | The crosswalk is public documentation | None: annotation. A reader of the crosswalk must use the new field names | Use the new names |
| 6 | `x-must-semantic-crosswalk` | 70 entries of private build traceability | Removed | Not useful outside the build | None: annotation | None |

### Validation surface

| | |
|---|---|
| File | `schemas/contracts-v1.schema.json` |
| SHA-256 of the file | `cda846c6af5ceb83deec6a98eee91db4a9797e07c93b3a189abacc72f686a96e` (741,225 bytes) |
| Validation surface SHA-256 | `48dc0402cc4957d1f3e8583ee408159dcb787cbafdb655708b5c7f5ec69860a3` |
| Embedded examples | 38 valid instances accepted; 64 invalid instances rejected |

The validation surface is every validating keyword of the root and of each `$defs` entry, leaving out `title`, `description`, `examples`, `$comment`, the root `$id` and every `x-*` annotation. The surface hash was identical before and after the changes in the table. The file is larger than before only because it is now pretty-printed; the hash of the file is expected to change whenever anything in it changes, the hash of the surface only when what validates changes.

## Versioning policy (proposed)

- A change that alters what validates gets a new row here and a new `schema_version` in instances when it is not backward compatible.
- A change to `$id` is made only for an incompatible change: `…:contracts:2`.
- Annotation-only changes get a row here and keep the validation-surface hash.

This policy is proposed for the first release; it has not been exercised yet.
