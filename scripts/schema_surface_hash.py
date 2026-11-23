#!/usr/bin/env python3
"""Print the validation-surface hash of the contract schema bundle.

The validation surface is every validating keyword of the root and of each `$defs` entry. Annotations are left out:
`title`, `description`, `examples`, `$comment`, `default`, `deprecated`, `readOnly`, `writeOnly`, the root `$id` and
every `x-*` extension. Two bundles with the same surface accept and reject exactly the same instances, so a change
to wording, examples or crosswalk metadata does not change the hash, and a change to what validates does.

    python scripts/schema_surface_hash.py            # print the hash
    python scripts/schema_surface_hash.py --check    # fail unless it equals the value recorded in contracts/CHANGES.md
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA = REPO_ROOT / "schemas" / "contracts-v1.schema.json"
CHANGES = REPO_ROOT / "contracts" / "CHANGES.md"

ANNOTATION = {"title", "description", "examples", "$comment", "$id", "default", "deprecated", "readOnly", "writeOnly"}
NAME_MAPS = {"properties", "$defs", "definitions", "patternProperties", "dependentSchemas"}
SCHEMA_KEYS = {"items", "additionalProperties", "not", "if", "then", "else", "contains", "propertyNames", "unevaluatedProperties", "unevaluatedItems"}
SCHEMA_LISTS = {"allOf", "anyOf", "oneOf", "prefixItems"}


def surface(node):
    """The validating part of a schema node. Property names are kept even when they look like annotations."""
    if not isinstance(node, dict):
        return node
    out = {}
    for key, value in node.items():
        if key in ANNOTATION or key.startswith("x-"):
            continue
        if key in NAME_MAPS and isinstance(value, dict):
            out[key] = {name: surface(sub) for name, sub in value.items()}
        elif key in SCHEMA_KEYS:
            out[key] = surface(value)
        elif key in SCHEMA_LISTS and isinstance(value, list):
            out[key] = [surface(sub) for sub in value]
        else:
            out[key] = value
    return out


def surface_hash(schema: dict) -> str:
    canonical = json.dumps(surface(schema), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def recorded_hash() -> str:
    match = re.search(r"validation surface[^`]*`([0-9a-f]{64})`", CHANGES.read_text(encoding="utf-8"), re.I)
    return match.group(1) if match else ""


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--check", action="store_true", help="compare with the hash recorded in contracts/CHANGES.md")
    args = parser.parse_args(argv)
    actual = surface_hash(json.loads(SCHEMA.read_text(encoding="utf-8")))
    if not args.check:
        print(actual)
        return 0
    recorded = recorded_hash()
    if actual != recorded:
        print("The validation surface changed.\n  schema:   %s\n  recorded: %s\nIf the change is intended, record it in contracts/CHANGES.md "
              "(what changed, why, compatibility, migration) and update the hash there." % (actual, recorded or "(none found)"))
        return 1
    print("Validation surface unchanged: %s" % actual)
    return 0


if __name__ == "__main__":
    sys.exit(main())
