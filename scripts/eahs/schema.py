"""Load the contract schema and validate instances against it with a Draft 2020-12 engine.

Timestamp assertion is configured explicitly: the schema declares `format: date-time`, and a format
annotation alone does not validate anything, so a strict RFC 3339 checker is registered here.
"""
from __future__ import annotations

import calendar
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional

from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import best_match

from . import REPO_ROOT
from .findings import Finding, doc_for_contract, rel

SCHEMA_PATH = REPO_ROOT / "schemas" / "contracts-v1.schema.json"
CONTRACT_DEFS = {
    "C01": "context",
    "C02": "evidence",
    "C03": "selection",
    "C04": "decision_packet",
    "C05": "action_proposal",
    "C06": "delegation",
    "C07": "execution_receipt",
}

_RFC3339 = re.compile(r"^(\d{4})-(\d{2})-(\d{2})[Tt](\d{2}):(\d{2}):(\d{2})(\.\d+)?([Zz]|[+-]\d{2}:\d{2})$")


def is_rfc3339(value) -> bool:
    """True only for a complete, timezone-bearing RFC 3339 date-time with a valid calendar date."""
    if not isinstance(value, str):
        return True  # `format` only constrains strings
    m = _RFC3339.match(value)
    if not m:
        return False
    year, month, day, hour, minute, second = (int(m.group(i)) for i in range(1, 7))
    if not 1 <= month <= 12 or not 1 <= day <= calendar.monthrange(year, month)[1]:
        return False
    if hour > 23 or minute > 59 or second > 60:
        return False
    zone = m.group(8)
    if zone not in ("Z", "z"):
        zh, zm = int(zone[1:3]), int(zone[4:6])
        if zh > 23 or zm > 59:
            return False
    return True


def format_checker() -> FormatChecker:
    checker = FormatChecker(formats=())
    checker.checks("date-time")(is_rfc3339)
    return checker


def load_schema(path: Optional[Path] = None) -> dict:
    with open(path or SCHEMA_PATH, "r", encoding="utf-8") as handle:
        return json.load(handle)


def check_schema_itself(schema: dict) -> List[Finding]:
    """The bundle must itself be a valid Draft 2020-12 schema."""
    try:
        Draft202012Validator.check_schema(schema)
    except Exception as exc:  # noqa: BLE001 - report whatever the engine says
        return [Finding("SCH000", "schema is not a valid Draft 2020-12 schema: %s" % exc, rel(SCHEMA_PATH), doc="schemas/README.md")]
    return []


def _wrapper(schema: dict, definition: str) -> dict:
    return {"$schema": schema["$schema"], "$defs": schema["$defs"], "$ref": "#/$defs/%s" % definition}


_VALIDATORS: dict = {}


def validator_for(schema: dict, contract_id: str) -> Draft202012Validator:
    key = (id(schema), contract_id)
    if key not in _VALIDATORS:
        _VALIDATORS[key] = Draft202012Validator(_wrapper(schema, CONTRACT_DEFS[contract_id]), format_checker=format_checker())
    return _VALIDATORS[key]


def _pointer(parts: Iterable) -> str:
    out = ""
    for p in parts:
        out += "/" + str(p).replace("~", "~0").replace("/", "~1")
    return out or "/"


def _group_hint(schema: dict, contract_id: str, parts: list) -> str:
    """Name the contract group an error sits in (for example C02-G07 Times) using the schema's crosswalk."""
    if not parts:
        return ""
    for row in schema.get("x-contract-crosswalk", []):
        if row.get("contract_id") == contract_id and row.get("schema_group") == parts[0]:
            return "%s %s" % (row.get("mapping_id"), row.get("group_name"))
    return ""


def _shown_error(error):
    """For a failed oneOf/anyOf, report the alternative the instance was aiming at.

    An alternative whose fixed property (const or enum, such as "state": "known") does not match was never the one
    meant, so its complaints (a missing "reason", say) only mislead. If every alternative is ruled out, report as before.
    """
    if not error.context:
        return error
    by_alternative: dict = {}
    for item in error.context:
        by_alternative.setdefault(item.relative_schema_path[0], []).append(item)
    aimed = []
    for items in by_alternative.values():
        ruled_out = any(i.validator in ("const", "enum") and len(i.relative_path) <= 1 for i in items)
        if not ruled_out:
            aimed += items
    return best_match(aimed or list(error.context)) or error


def validate_instance(schema: dict, instance, file: str = "", contract_id: Optional[str] = None) -> List[Finding]:
    """Validate one contract instance; return one Finding per distinct problem (empty list means structurally valid)."""
    cid = contract_id or (instance.get("contract_id") if isinstance(instance, dict) else None)
    if cid not in CONTRACT_DEFS:
        return [Finding("SCH001", "contract_id is missing or not one of C01-C07 (got %r)" % (cid,), file, doc="contracts/README.md")]
    findings: List[Finding] = []
    for error in sorted(validator_for(schema, cid).iter_errors(instance), key=lambda e: [str(p) for p in e.absolute_path]):
        shown = _shown_error(error)
        parts = list(error.absolute_path)
        detail = shown.message
        if len(detail) > 220:
            detail = detail[:217] + "..."
        hint = _group_hint(schema, cid, parts)
        where = _pointer(parts)
        message = detail if not hint else "%s [%s]" % (detail, hint)
        findings.append(Finding("SCH002", message, file, where, doc_for_contract(cid)))
    return findings


@dataclass
class ExampleResult:
    case_id: str
    contract_id: str
    expected_valid: bool
    ok: bool
    detail: str = ""


def check_embedded_examples(schema: dict) -> List[ExampleResult]:
    """The bundle documents 38 valid and 64 invalid instances; each must behave as labeled."""
    results: List[ExampleResult] = []
    index = schema.get("x-valid-example-index", [])
    for position, instance in enumerate(schema.get("examples", [])):
        meta = index[position] if position < len(index) else {"case_id": "valid-%d" % position, "contract_id": instance.get("contract_id")}
        problems = validate_instance(schema, instance, contract_id=meta.get("contract_id"))
        results.append(ExampleResult(meta["case_id"], meta.get("contract_id", "?"), True, not problems, "; ".join(p.message for p in problems[:2])))
    for entry in schema.get("x-documentation-examples", []):
        problems = validate_instance(schema, entry["instance"], contract_id=entry.get("contract_id"))
        results.append(ExampleResult(entry["case_id"], entry.get("contract_id", "?"), False, bool(problems), "" if problems else "accepted but should be rejected"))
    return results
