# Contract changes

Every change to what the contracts accept or reject is recorded here, newest first. Changes to wording, examples or crosswalk metadata are recorded too, so a reader can see that they did not alter validation.

The schema file is [`schemas/contracts-v1.schema.json`](../schemas/contracts-v1.schema.json). See [Schemas](../schemas/README.md) for how it is organized.

## How to record a change

For each change give: the previous form, the new form, the reason, the compatibility impact (does any previously valid instance become invalid, or the reverse?) and the migration. Then update the validation-surface hash below. `python scripts/schema_surface_hash.py --check` fails if the hash and the schema disagree.

## v1.0.1

Annotation-only. No previously valid instance becomes invalid, and none that was invalid becomes valid, so there is nothing to migrate. The validation-surface hash is unchanged.

| Change | Previous form | New form | Reason |
|---|---|---|---|
| Definition of the `inaccessible` missingness label (the enum description, the canonical definition and the values in the embedded examples) | "Current principal lacks permission; reason/existence disclosed only when permitted." | "Current principal may know the input exists but may not read it; shown only in the wording the permission decision allows." | Permission is decided before anything about an input is shown, so the label applies only where the requester may know that the input exists. |
| Definition of the `not_assessed` missingness label (same places) | "Check/assessment not performed; distinct from evaluation/publication NOT ASSESSED (insufficient assessment coverage)." | "Check or assessment of the input was not performed. Not the evaluation status NOT ASSESSED." | The evaluation statuses were redefined; the meaning of the label did not change. |
| `x-documentation.source.source_type` | "Author's architecture specification, not published" | "Architecture documentation of this repository" | Wording about how the source was prepared was removed. |
| `x-documentation.architecture_evaluation_status`, `x-contract-crosswalk[].architectural_status` (41 entries) and one note in `x-documentation.external_checks` | `NOT RUN` | `NOT ASSESSED` | The architecture has not been evaluated, and what an evaluation needs does not exist. |

### Validation surface

| Property | Value |
|---|---|
| File | `schemas/contracts-v1.schema.json` |
| SHA-256 of the file | `3f8fa1cf782788066bcc02f38d8c068603c0254797c60fbcb137b05e8400538e` (741,575 bytes) |
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

This policy was proposed with the first release (v1.0.0). The only change since, in v1.0.1, was annotation-only.
