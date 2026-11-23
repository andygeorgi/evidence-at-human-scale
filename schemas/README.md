# Schemas

One file: [`contracts-v1.schema.json`](contracts-v1.schema.json), a JSON Schema (Draft 2020-12) bundle that encodes the structure of the seven [contracts](../contracts/README.md) C01–C07.

It checks **structure**. It does not check that a reference points at something that exists, that a derivation is acyclic, or that a correction reached everything built on the corrected record. Those are scenario semantics, and the [validation command](../scripts/README.md) checks them separately on the [synthetic examples](../examples/README.md).

## What is in the file

| Part | What it holds |
|---|---|
| `$defs` | Seven definitions: `context` (C01), `evidence` (C02), `selection` (C03), `decision_packet` (C04), `action_proposal` (C05), `delegation` (C06), `execution_receipt` (C07). `evidence` also holds the shared building blocks (scope, time value, missingness, supporting reference, accounting and so on) that the other contracts reference. |
| root `oneOf` | The same seven definitions, so any instance can be validated against the root. Each instance carries `contract_id` (`C01`…`C07`) and `schema_version` (`"1"`). |
| `examples` | 38 valid instances, indexed in `x-valid-example-index`. |
| `x-documentation-examples` | 64 invalid instances, each with the requirement it violates. |
| `x-contract-crosswalk` | 41 rows that map each contract group to its schema property, its constraint, its semantic requirement and the [figures](../figures/README.md) that show it. |
| `x-documentation` | Status, the seven canonical missingness definitions, and reference metadata. Annotation only. |

Everything with an `x-` prefix, every `title`, `description`, `examples` and `$comment` is annotation. It never changes what validates.

## Identity and version

| Property | Value |
|---|---|
| `$id` | `urn:evidence-at-human-scale:contracts:1` |
| Instance `schema_version` | `"1"` |
| Release | `v1.0.0-rc.1`, a release candidate |
| Validation-surface hash | recorded in [`contracts/CHANGES.md`](../contracts/CHANGES.md); recompute with `python scripts/schema_surface_hash.py` |

A change that alters what validates needs a new entry in [`contracts/CHANGES.md`](../contracts/CHANGES.md) with the previous form, the new form, the reason, the compatibility impact and the migration. The repository's checks fail if the validation surface changes without that record.

## Validate an instance

With the command line, from the repository root:

```bash
python scripts/validate_examples.py
```

That validates every example in [`examples/`](../examples/README.md) and runs the semantic checks on them.

From your own code (one dependency, `jsonschema` 4.18 or later):

```python
import json
from jsonschema import Draft202012Validator

schema = json.load(open("schemas/contracts-v1.schema.json", encoding="utf-8"))
instance = json.load(open("examples/01-source-records/c02-INV-2026-0417-v1.json", encoding="utf-8"))
errors = list(Draft202012Validator(schema).iter_errors(instance))
print("valid" if not errors else errors[0].message)
```

Timestamps are strings with `format: date-time` and also a `pattern` that requires a time zone, so a validator that ignores `format` still rejects a bare local time. A validator that asserts `format` additionally rejects impossible dates; [`scripts/eahs/schema.py`](../scripts/eahs/schema.py) turns that on.

## What a valid instance does and does not mean

A valid instance has the right shape. It does not mean the content is true, the producer is trustworthy, the reference resolves, or the system that produced it is accountable. See [Claims and limits](../docs/claims-and-limits.md).
