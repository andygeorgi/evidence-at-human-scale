# Contract changes

Every change to what the contracts accept or reject is recorded here, newest first. Changes to wording, examples or crosswalk metadata are recorded too, so a reader can see that they did not alter validation.

The schema file is [`schemas/contracts-v1.schema.json`](../schemas/contracts-v1.schema.json). See [Schemas](../schemas/README.md) for how it is organized.

## How to record a change

For each change give: the previous form, the new form, the reason, the compatibility impact (does any previously valid instance become invalid, or the reverse?) and the migration. Then update the validation-surface hash below. `python scripts/schema_surface_hash.py --check` fails if the hash and the schema disagree.

## v1.0.0-rc.1 (release candidate)

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

This policy is proposed for the first release; it has not been exercised yet.
