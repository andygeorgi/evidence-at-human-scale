# Contract changes

Every change to what the contracts accept or reject is recorded here, newest first. Changes to wording, examples or crosswalk metadata are recorded too, so a reader can see that they did not alter validation.

The schema file is [`schemas/contracts-v1.schema.json`](../schemas/contracts-v1.schema.json). See [Schemas](../schemas/README.md) for how it is organized.

## How to record a change

For each change give: the previous form, the new form, the reason, the compatibility impact (does any previously valid instance become invalid, or the reverse?) and the migration. Then update the validation-surface hash below. `python scripts/schema_surface_hash.py --check` fails if the hash and the schema disagree.

## v1.0.8

No change to the schema. The file, the validation surface and the 38 valid and 64 invalid embedded examples are exactly as in v1.0.7, so no instance that validated against the schema stops validating, none that was invalid becomes valid, and there is nothing to migrate. This release changed the wording and order of documents and the reader-experience tests, as the [changelog](../CHANGELOG.md) describes. No rule of the reference validator or of the reference commit check changed. `python scripts/schema_surface_hash.py --check` confirms that the surface is unchanged.

| Property | Value |
|---|---|
| File | `schemas/contracts-v1.schema.json` |
| SHA-256 of the file | `c23e10748393e8f3eab498d18b0a117fc23e14449bdb1218526ce4481035c2c3` (741,666 bytes), as in v1.0.7 |
| Validation surface SHA-256 | `48dc0402cc4957d1f3e8583ee408159dcb787cbafdb655708b5c7f5ec69860a3` (unchanged) |

## v1.0.7

No change to the schema. The file, the validation surface and the 38 valid and 64 invalid embedded examples are exactly as in v1.0.6, so no instance that validated against the schema stops validating, none that was invalid becomes valid, and there is nothing to migrate. This release changed the semantic checks of the reference validator and of the reference commit check (which are not part of the schema), the tests and the wording of documents, as the [changelog](../CHANGELOG.md) describes. The schema still accepts a version of a C02 record whose claims share one `claim_id`, because JSON Schema cannot state that a property is unique across the items of an array: the reference validator reports it (`REF008`), which needs no change to the contracts. `python scripts/schema_surface_hash.py --check` confirms that the surface is unchanged.

| Property | Value |
|---|---|
| File | `schemas/contracts-v1.schema.json` |
| SHA-256 of the file | `c23e10748393e8f3eab498d18b0a117fc23e14449bdb1218526ce4481035c2c3` (741,666 bytes), as in v1.0.6 |
| Validation surface SHA-256 | `48dc0402cc4957d1f3e8583ee408159dcb787cbafdb655708b5c7f5ec69860a3` (unchanged) |

## v1.0.6

No change to the schema. The file, the validation surface and the 38 valid and 64 invalid embedded examples are exactly as in v1.0.5, so no instance that validated against the schema stops validating, none that was invalid becomes valid, and there is nothing to migrate. This release changed the semantic checks of the reference validator and of the reference commit check (which are not part of the schema), one evaluation case, the tests and the wording of documents, as the [changelog](../CHANGELOG.md) describes. Version names stay free text, and the schema still accepts any non-empty name: the reference defines the order it reads from the numbers in the names and reports names that give none (`LIFE006`), which needs no change to the contracts. `python scripts/schema_surface_hash.py --check` confirms that the surface is unchanged.

| Property | Value |
|---|---|
| File | `schemas/contracts-v1.schema.json` |
| SHA-256 of the file | `c23e10748393e8f3eab498d18b0a117fc23e14449bdb1218526ce4481035c2c3` (741,666 bytes), as in v1.0.5 |
| Validation surface SHA-256 | `48dc0402cc4957d1f3e8583ee408159dcb787cbafdb655708b5c7f5ec69860a3` (unchanged) |

## v1.0.5

No change to the schema. The file, the validation surface and the 38 valid and 64 invalid embedded examples are exactly as in v1.0.4, so no instance that validated against the schema stops validating, none that was invalid becomes valid, and there is nothing to migrate. This release changed the semantic checks of the reference validator (which are not part of the schema), one optional key of the example registry, the tests and the wording of documents, as the [changelog](../CHANGELOG.md) describes. `python scripts/schema_surface_hash.py --check` confirms that the surface is unchanged.

| Property | Value |
|---|---|
| File | `schemas/contracts-v1.schema.json` |
| SHA-256 of the file | `c23e10748393e8f3eab498d18b0a117fc23e14449bdb1218526ce4481035c2c3` (741,666 bytes), as in v1.0.4 |
| Validation surface SHA-256 | `48dc0402cc4957d1f3e8583ee408159dcb787cbafdb655708b5c7f5ec69860a3` (unchanged) |

## v1.0.4

No change to the schema. The file, the validation surface and the 38 valid and 64 invalid embedded examples are exactly as in v1.0.3, so no previously valid instance becomes invalid, none that was invalid becomes valid, and there is nothing to migrate. This release changed the wording of documents, as the [changelog](../CHANGELOG.md) describes. `python scripts/schema_surface_hash.py --check` confirms that the surface is unchanged.

| Property | Value |
|---|---|
| File | `schemas/contracts-v1.schema.json` |
| SHA-256 of the file | `c23e10748393e8f3eab498d18b0a117fc23e14449bdb1218526ce4481035c2c3` (741,666 bytes), as in v1.0.3 |
| Validation surface SHA-256 | `48dc0402cc4957d1f3e8583ee408159dcb787cbafdb655708b5c7f5ec69860a3` (unchanged) |

## v1.0.3

No change to the schema. The file, the validation surface and the 38 valid and 64 invalid embedded examples are exactly as in v1.0.2, so no previously valid instance becomes invalid, none that was invalid becomes valid, and there is nothing to migrate. This release changed documentation and the way figures are written into it, as the [changelog](../CHANGELOG.md) describes. `python scripts/schema_surface_hash.py --check` confirms that the surface is unchanged.

| Property | Value |
|---|---|
| File | `schemas/contracts-v1.schema.json` |
| SHA-256 of the file | `c23e10748393e8f3eab498d18b0a117fc23e14449bdb1218526ce4481035c2c3` (741,666 bytes), as in v1.0.2 |
| Validation surface SHA-256 | `48dc0402cc4957d1f3e8583ee408159dcb787cbafdb655708b5c7f5ec69860a3` (unchanged) |

## v1.0.2

No change to the schema. The file, the validation surface and the 38 valid and 64 invalid embedded examples are exactly as in v1.0.1, so no previously valid instance becomes invalid, none that was invalid becomes valid, and there is nothing to migrate. This release changed the reference validators, the generated example data (which still validates), the documentation and the figures, as the [changelog](../CHANGELOG.md) describes. `python scripts/schema_surface_hash.py --check` confirms that the surface is unchanged.

| Property | Value |
|---|---|
| File | `schemas/contracts-v1.schema.json` |
| SHA-256 of the file | `c23e10748393e8f3eab498d18b0a117fc23e14449bdb1218526ce4481035c2c3` (741,666 bytes), as in v1.0.1 |
| Validation surface SHA-256 | `48dc0402cc4957d1f3e8583ee408159dcb787cbafdb655708b5c7f5ec69860a3` (unchanged) |

## v1.0.1

Annotation-only. No previously valid instance becomes invalid, and none that was invalid becomes valid, so there is nothing to migrate. The validation-surface hash is unchanged.

| Change | Previous form | New form | Reason |
|---|---|---|---|
| Definition of the `inaccessible` missingness label (the enum description, the canonical definition and the values in the embedded examples) | "Current principal lacks permission; reason/existence disclosed only when permitted." | "Current principal may know the input exists but may not read it; shown only in the wording the permission decision allows." | Permission is decided before anything about an input is shown, so the label applies only where the requestor may know that the input exists. |
| Definition of the `not_assessed` missingness label (same places) | "Check/assessment not performed; distinct from evaluation/publication NOT ASSESSED (insufficient assessment coverage)." | "Check or assessment of the input was not performed. Not the evaluation status NOT ASSESSED." | The evaluation statuses were redefined; the meaning of the label did not change. |
| `x-documentation.source.source_type` | "Author's architecture specification, not published" | "Architecture documentation of this repository" | Wording about how the source was prepared was removed. |
| `x-documentation.architecture_evaluation_status`, `x-contract-crosswalk[].architectural_status` (41 entries) and one note in `x-documentation.external_checks` | `NOT RUN` | `NOT ASSESSED` | The architecture has not been evaluated, and what an evaluation needs does not exist. |
| Root `description` | A three-sentence slogan followed by the statement about one interaction contract | The statement about one interaction contract, in plain words | The slogan was removed from the schema as it was from the documents. |
| `permission_safe_summary` in the five embedded `inaccessible` examples | "Coverage limitation; no protected source identity or existence disclosed." | "Coverage limitation; no protected source identity or content is disclosed." | An `inaccessible` entry exists only where the requestor may know that the input exists, so it cannot claim that existence is undisclosed. |
| `x-contract-crosswalk` entries for C02 `validation` and C07 `verification_recovery`: `required_semantics` and `external_check` | Lists joined by slashes, such as "verification method/actor/time/scope" | The same items written as a sentence | Plain wording. What each entry requires and what it checks did not change. |

### Validation surface

| Property | Value |
|---|---|
| File | `schemas/contracts-v1.schema.json` |
| SHA-256 of the file | `c23e10748393e8f3eab498d18b0a117fc23e14449bdb1218526ce4481035c2c3` (741,666 bytes) |
| Validation surface SHA-256 | `48dc0402cc4957d1f3e8583ee408159dcb787cbafdb655708b5c7f5ec69860a3` (unchanged) |
| Embedded examples | 38 valid instances accepted; 64 invalid instances rejected |

## v1.0.0

First public form of the contract definitions. There is nothing to migrate, and the validation surface below is the baseline against which every later change is measured.

### Validation surface

| Property | Value |
|---|---|
| File | `schemas/contracts-v1.schema.json` |
| SHA-256 of the file | `cda846c6af5ceb83deec6a98eee91db4a9797e07c93b3a189abacc72f686a96e` (741,225 bytes) |
| Validation surface SHA-256 | `48dc0402cc4957d1f3e8583ee408159dcb787cbafdb655708b5c7f5ec69860a3` |
| Embedded examples | 38 valid instances accepted; 64 invalid instances rejected |

The validation surface is every validating keyword of the root and of each `$defs` entry, leaving out `title`, `description`, `examples`, `$comment`, the root `$id` and every `x-*` annotation. The hash of the file changes whenever anything in it changes; the hash of the surface changes only when what validates changes.

## Versioning policy (proposed)

- A change that alters what validates gets a new row here and a new `schema_version` in instances when it is not backward compatible.
- A change to `$id` is made only for an incompatible change: `…:contracts:2`.
- Annotation-only changes get a row here and keep the validation-surface hash.

This policy was proposed with the first release (v1.0.0). The only changes since were annotation-only (v1.0.1), and none at all to the schema (v1.0.2, v1.0.3, v1.0.4, v1.0.5, v1.0.6, v1.0.7 and v1.0.8).
