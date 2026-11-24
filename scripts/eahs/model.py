"""Load contract instances and the example registry; classify every reference inside an instance."""
from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Optional, Tuple

from .findings import Finding, doc_for_contract, rel
from .schema import CONTRACT_DEFS

Key = Tuple[str, str, str]  # (contract, id, version)

IDENTITY = {
    "C01": ("identity_principal", "context_id"),
    "C02": ("identity_schema", "record_id"),
    "C03": ("identity_scope", "selection_id"),
    "C04": ("decision_context_as_of", "packet_id"),
    "C05": ("identity_binding", "proposal_id"),
    "C06": ("identity_principals", "grant_id"),
    "C07": ("identity_binding", "receipt_id"),
}

# Keys whose {record_id, version} value points at a C02 evidence record.
EVIDENCE_REF_KEYS = {
    "parent_references", "from", "to", "target", "available_record", "replacement_reference",
    "dependency_failure_reference", "authoritative_reconciliation_reference", "reference", "challenge_links",
    "record_reference",
}
# Keys whose value points at something outside the contracts (registry entries held by the domain).
EXTERNAL_REF_KEYS = {
    "permitted_kind_reference", "payload_schema_reference", "decision_reference", "authorization_reference",
    "permission_decision_reference", "authority_basis", "check_basis", "shared_accounting_reference",
    "accounting_reference", "domain_acceptance_reference", "approval_reference",
}
SUPPORT_TAGS = ("claim_reference", "payload_reference")


@dataclass
class Instance:
    contract: str
    id: str
    version: str
    data: dict
    path: Path

    @property
    def key(self) -> Key:
        return (self.contract, self.id, self.version)

    @property
    def file(self) -> str:
        return rel(self.path)

    def label(self) -> str:
        return "%s %s %s" % (self.contract, self.id, self.version)


@dataclass
class Registry:
    producers: dict = field(default_factory=dict)
    external_records: dict = field(default_factory=dict)
    policies: dict = field(default_factory=dict)
    preconditions: dict = field(default_factory=dict)
    relationship_types: list = field(default_factory=list)
    protected_terms: list = field(default_factory=list)
    target_states: list = field(default_factory=list)
    #: what each requestor may be told about a source they cannot read ("record_id@version" -> decision)
    permission_decisions: dict = field(default_factory=dict)
    #: who holds which role, which roles one person may hold together, and the log of human reviews
    accountability: dict = field(default_factory=dict)
    raw: dict = field(default_factory=dict)

    def policy(self, policy_id: str, version: str) -> Optional[dict]:
        return self.policies.get(policy_id, {}).get(version)


@dataclass
class Model:
    instances: Dict[Key, Instance]
    registry: Registry
    root: Path
    #: JSON files that were read but are not contract instances (raw exports, scenario files, responses)
    ignored: List[str] = field(default_factory=list)

    def get(self, contract: str, id_: str, version: str) -> Optional[Instance]:
        # An identity that is not text (a list or an object in a damaged reference) names nothing, and cannot be a key.
        if not isinstance(contract, str) or not isinstance(id_, str) or not isinstance(version, str):
            return None
        return self.instances.get((contract, id_, version))

    def of(self, contract: str) -> List[Instance]:
        return [i for k, i in sorted(self.instances.items()) if k[0] == contract]

    def versions(self, contract: str, id_: str) -> List[Instance]:
        return sorted((i for k, i in self.instances.items() if k[0] == contract and k[1] == id_), key=lambda i: _vnum(i.version))


def _vnum(version: str) -> int:
    digits = "".join(c for c in version if c.isdigit())
    return int(digits) if digits else 0


def is_contract_id(value) -> bool:
    """True only for a string that names one of the seven contracts. A list, a number or 'C99' is not a contract id."""
    return isinstance(value, str) and value in CONTRACT_DEFS


#: The file-name convention for contract instances (c02-GR-5521-v1.json): a file named like this is meant to be one.
CONTRACT_FILE = re.compile(r"c0[1-7]-.+\.json", re.IGNORECASE)


def json_files(root: Path) -> List[Path]:
    """Every file below the folder with a .json extension in any case, so that the answer does not depend on how the platform treats case.

    A glob for "*.json" is case-sensitive on Linux and macOS and case-insensitive on Windows, so it would leave a file named
    C02-X-V1.JSON out of the folder on one platform and not on the other.
    """
    return sorted(p for p in root.rglob("*") if p.suffix.lower() == ".json" and p.is_file())


def identity_of(data: dict) -> Optional[Tuple[str, str, str]]:
    contract = data.get("contract_id")
    if not is_contract_id(contract) or contract not in IDENTITY:
        return None
    group, id_key = IDENTITY[contract]
    block = data.get(group)
    if not isinstance(block, dict):
        return None
    ident, version = block.get(id_key), block.get("version")
    if not isinstance(ident, str) or not isinstance(version, str):
        return None
    return contract, ident, version


def registry_from_dict(raw: dict) -> Registry:
    """The registry the checks read. Raises ValueError, naming the section, when a section is not shaped as a check reads it."""
    problem = registry_problem(raw)
    if problem:
        raise ValueError(problem)
    return Registry(
        producers=raw.get("producers", {}),
        external_records=raw.get("external_records", {}),
        policies=raw.get("policies", {}),
        preconditions=raw.get("preconditions", {}),
        relationship_types=raw.get("relationship_types", []),
        protected_terms=raw.get("protected_terms", []),
        target_states=raw.get("target_states", []),
        permission_decisions=raw.get("permission_decisions", {}),
        accountability=raw.get("accountability", {}),
        raw=raw,
    )


#: The shape each section of the registry must have. A check reads these as objects and lists, so a section of another shape
#: is refused when the registry is read, with the section named, and not inside a check.
REGISTRY_SECTIONS = {
    "producers": (dict, "an object that maps each producer id to its entry"),
    "external_records": (dict, "an object that names each external record"),
    "policies": (dict, "an object that maps each policy id to its versions"),
    "preconditions": (dict, "an object that maps each condition id to its rule"),
    "relationship_types": (list, "a list of relationship type names"),
    "protected_terms": (list, "a list of terms"),
    "target_states": (list, "a list of recorded states of the target"),
    "permission_decisions": (dict, "an object that maps each decision to its entry"),
    "accountability": (dict, "an object"),
}


def _hours(value) -> bool:
    """A limit in hours that can be compared with an age: a real number (not true or false), finite and not negative."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    try:
        return math.isfinite(value) and value >= 0
    except OverflowError:
        return False


def registry_problem(raw: dict) -> Optional[str]:
    """Why the registry cannot be read as the checks need it, or None. The message names the section and what it must hold."""
    for name, (kind, meaning) in REGISTRY_SECTIONS.items():
        if name in raw and not isinstance(raw[name], kind):
            return "'%s' must be %s, and this registry holds %s" % (name, meaning, _type_name(raw[name]))
    for producer, entry in raw.get("producers", {}).items():
        if not isinstance(entry, dict) or not isinstance(entry.get("permitted_kinds"), list):
            return "producer %r must be an object with a 'permitted_kinds' list" % producer
    for policy, versions in raw.get("policies", {}).items():
        if not isinstance(versions, dict) or not all(isinstance(entry, dict) for entry in versions.values()):
            return "policy %r must be an object that maps each version to an object" % policy
        for version, entry in versions.items():
            if entry.get("type") == "freshness" and not _hours(entry.get("max_age_hours")):
                return "freshness policy %s %s needs 'max_age_hours' as a number of hours that is not negative" % (policy, version)
    for condition, rule in raw.get("preconditions", {}).items():
        if not isinstance(rule, dict):
            return "precondition %r must be an object" % condition
        if rule.get("type") == "evidence_fresh" and not _hours(rule.get("max_age_hours")):
            return "precondition %s needs 'max_age_hours' as a number of hours that is not negative" % condition
    for name in ("relationship_types", "protected_terms"):
        if not all(isinstance(item, str) for item in raw.get(name, [])):
            return "'%s' must list only strings" % name
    if not all(isinstance(item, dict) for item in raw.get("target_states", [])):
        return "'target_states' must list only objects, each with an entity_id, a time and a state"
    accountability = raw.get("accountability", {})
    roles, together, log = accountability.get("roles", {}), accountability.get("may_hold_together", []), accountability.get("review_log", [])
    if not isinstance(roles, dict) or not all(isinstance(role, dict) for role in roles.values()):
        return "'accountability.roles' must be an object that maps each role to an object"
    for role_name, role in roles.items():
        for key in ("holders", "principals"):
            if key in role and (not isinstance(role[key], list) or not all(isinstance(who, str) for who in role[key])):
                return "role %r in 'accountability.roles': '%s' must be a list of principal names (text)" % (role_name, key)
    if not isinstance(together, list) or not all(isinstance(pair, list) and all(isinstance(name, str) for name in pair) for pair in together):
        return "'accountability.may_hold_together' must be a list of lists of role names (text)"
    if not isinstance(log, list) or not all(isinstance(entry, dict) for entry in log):
        return "'accountability.review_log' must be a list of objects"
    from .gateway import parse_time   # imported here: the gateway reads the model, so the model cannot import it at the top
    for position, entry in enumerate(log):
        if not all(isinstance(entry.get(key), str) for key in ("packet", "actor", "action", "time")):
            return "entry %d of 'accountability.review_log' needs text for 'packet', 'actor', 'action' and 'time'" % (position + 1)
        if parse_time(entry["time"]) is None:
            return "entry %d of 'accountability.review_log' has a time that is not an RFC 3339 time with a zone: %r" % (position + 1, entry["time"])
    return None


def _no_constant(name):
    raise ValueError("%s is not valid JSON: write a number, a string, true, false or null" % name)


def _finite(text):
    """A fraction or exponent number, read as a double only when the double holds every digit written: other readers round the rest."""
    value = float(text)
    if value in (float("inf"), float("-inf")):
        raise ValueError("the number %s is too large to read as a number" % text[:20])
    try:
        kept = Decimal(repr(value)) == Decimal(text)
    except InvalidOperation:
        kept = False
    if not kept:
        raise ValueError("the number %s has more digits, or a smaller size, than a double keeps (a reader that uses one reads it as %r), so it would mean one thing here and another elsewhere: write it with fewer digits, or as a string" % (text[:40], value))
    return value


def _finite_int(text):
    value = int(text)
    try:
        float(value)
    except OverflowError:
        raise ValueError("the number %s... is too large to read as a number" % text[:20]) from None
    return value


def _no_repeated_key(pairs):
    seen = {}
    for key, value in pairs:
        if key in seen:
            raise ValueError("the key %r appears more than once in one object, so it is unclear which value counts" % key)
        seen[key] = value
    return seen


#: How deep a JSON document may nest. The deepest document of the examples nests 11 levels. A reader that recurses (the schema check, the
#: reference search) would run out of stack long before a document nested hundreds of levels deep had been read, so such a document is refused.
MAX_DEPTH = 40


def _nested_deeper_than(value, limit: int) -> bool:
    """True if `value` nests more than `limit` levels of objects and lists. Iterative, so that the answer itself cannot exhaust the stack."""
    stack = [(value, 1)]
    while stack:
        item, depth = stack.pop()
        if depth > limit:
            return True
        children = item.values() if isinstance(item, dict) else item if isinstance(item, list) else ()
        stack.extend((child, depth + 1) for child in children if isinstance(child, (dict, list)))
    return False


def loads_strict(text: str):
    """JSON as RFC 8259 defines it. Python also reads NaN, Infinity and -Infinity, a number too large for a float (a whole number
    as well as a fraction), a number with more digits than a double keeps (40.000000000000001 reads as 40.0, and other readers
    round it) and an object that repeats a key (the last value silently wins): other parsers do not, so a file that
    depends on them means one thing here and another elsewhere. All of them are refused (ValueError, like any other malformed
    JSON), and so is a document nested too deeply for the reader (more than MAX_DEPTH levels)."""
    try:
        value = json.loads(text, parse_constant=_no_constant, parse_float=_finite, parse_int=_finite_int, object_pairs_hook=_no_repeated_key)
    except RecursionError as exc:
        raise ValueError("the document is nested too deeply to read (more than about a thousand levels)") from exc
    if _nested_deeper_than(value, MAX_DEPTH):
        raise ValueError("the document is nested more than %d levels deep, which no contract instance, registry or stage file needs, and which the checks cannot read safely" % MAX_DEPTH)
    return value


def registry_path(root: Path) -> Path:
    """The registry file of the folder: registry.json in any letter case, so that the answer does not depend on the platform.

    Raises ValueError when two files differ only by case, because it is then unclear which one is the registry.
    """
    found = sorted(p for p in root.iterdir() if p.is_file() and p.name.lower() == "registry.json") if root.is_dir() else []
    if len(found) > 1:
        raise ValueError("%s holds more than one registry file (%s); keep one registry.json" % (root, ", ".join(p.name for p in found)))
    return found[0] if found else root / "registry.json"


def load_registry(path: Path) -> Registry:
    if not path.exists():
        return Registry()
    raw = loads_strict(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("the registry must be a JSON object")
    return registry_from_dict(raw)


def _type_name(value) -> str:
    return {list: "a list", dict: "an object", int: "a number", float: "a number", bool: "true or false", type(None): "null"}.get(type(value), type(value).__name__)


def _contract_claim_problem(path: Path, root: Path, data) -> Optional[Finding]:
    """Why a JSON file cannot be read as a contract instance although it claims to be one (or is named like one); None if there is no problem.

    A top-level ``contract_id`` is a claim to be a contract instance, so it must be valid. A file under a folder named
    ``raw`` is a source export, and its own fields are its own business, unless its name or its contract_id says otherwise.
    """
    file = rel(path)
    declared = isinstance(data, dict) and "contract_id" in data
    named_like_a_contract = bool(CONTRACT_FILE.fullmatch(path.name))
    in_raw_folder = "raw" in [part.lower() for part in path.relative_to(root).parts[:-1]]
    if declared and is_contract_id(data["contract_id"]):
        if named_like_a_contract and path.name[:3].upper() != data["contract_id"]:
            return Finding("ID005", "the file name says %s, but its contract_id is %s" % (path.name[:3].upper(), data["contract_id"]), file, doc=doc_for_contract(data["contract_id"]),
                           hint="rename the file to match its contract_id, or correct the contract_id")
        return None
    if named_like_a_contract:
        if declared:
            return _bad_contract_id(file, data["contract_id"])
        return Finding("ID005", "the file name says this is a contract instance (%s), but it %s" % (path.name[:3].upper(), "has no contract_id" if isinstance(data, dict) else "is not a JSON object"), file,
                       doc="contracts/README.md", hint="give the object a contract_id and the contract's groups, or rename the file if it is not a contract instance")
    if declared and not in_raw_folder:
        return _bad_contract_id(file, data["contract_id"])
    return None


def _bad_contract_id(file: str, value) -> Finding:
    if not isinstance(value, str):
        return Finding("ID003", "contract_id must be a string such as \"C02\"; this file has %s" % _type_name(value), file, doc="contracts/README.md",
                       hint="write the contract_id as a string, C01 to C07; if the file is not a contract instance, remove the field or move the file into a folder named raw")
    hint = "use one of C01-C07"
    if value.upper() in CONTRACT_DEFS:
        hint = "contract_id is case-sensitive: write %s" % value.upper()
    return Finding("ID004", "contract_id %r is not a contract this repository defines (C01-C07)" % value, file, doc="contracts/README.md",
                   hint=hint + "; if the file is not a contract instance, remove the field or move the file into a folder named raw")


def load_model(root: Path) -> Tuple[Model, List[Finding]]:
    """Index every contract instance below `root` (any .json whose top-level object has contract_id C01-C07).

    A file that cannot be read as JSON, one that declares an invalid contract_id, one named like a contract instance that is
    not one, an instance without a readable identity and a duplicate identity are reported as findings: they stop the model
    from being a faithful picture of the folder, so the stages that need it cannot run. Other JSON files (raw exports,
    scenario, case and response files) have no contract_id and are listed in `ignored`.
    """
    findings: List[Finding] = []
    instances: Dict[Key, Instance] = {}
    ignored: List[str] = []
    registry_error: Optional[ValueError] = None
    try:
        registry_file = registry_path(root)
    except ValueError as exc:
        registry_file, registry_error = root / "registry.json", exc
    for path in json_files(root):
        if path.parent == root and path.name.lower() == "registry.json":
            continue
        try:
            data = loads_strict(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:  # includes JSONDecodeError and UnicodeDecodeError
            findings.append(Finding("ID000", "cannot read JSON: %s" % exc, rel(path), hint="repair or remove the file; every .json file below the folder must be valid UTF-8 JSON, without NaN, Infinity or a repeated key"))
            continue
        problem = _contract_claim_problem(path, root, data)
        if problem is not None:
            findings.append(problem)
            continue
        if not isinstance(data, dict) or not is_contract_id(data.get("contract_id")):
            ignored.append(rel(path))
            continue
        ident = identity_of(data)
        if ident is None:
            findings.append(Finding("ID002", "instance has no readable identity (id and version)", rel(path), doc=doc_for_contract(data.get("contract_id")), hint="give the instance the identity group its contract requires"))
            continue
        inst = Instance(ident[0], ident[1], ident[2], data, path)
        if inst.key in instances:
            findings.append(Finding("ID001", "duplicate identity %s (also in %s)" % (inst.label(), instances[inst.key].file), inst.file, doc=doc_for_contract(inst.contract), hint="every contract, id and version may appear once"))
            continue
        instances[inst.key] = inst
    try:
        if registry_error is not None:
            raise registry_error
        registry = load_registry(registry_file)
    except (OSError, ValueError, AttributeError) as exc:
        findings.append(Finding("ID000", "cannot read the registry: %s" % exc, rel(registry_file), hint="registry.json must be a JSON object whose sections have the shape the message names, without NaN, Infinity, a number too large for a float or a repeated key; keep one registry file in the folder"))
        registry = Registry()
    return Model(instances, registry, root, ignored), findings


# ---------------------------------------------------------------------------
# Reference discovery
# ---------------------------------------------------------------------------

@dataclass
class Ref:
    kind: str          # evidence | support | contract | external | retrieval | policy
    path: str          # JSON pointer inside the instance
    record_id: str = ""
    version: str = ""
    contract: str = ""  # for kind == contract
    body: Optional[dict] = None


def _ptr(parts: Iterable) -> str:
    return "".join("/" + str(p).replace("~", "~0").replace("/", "~1") for p in parts) or "/"


def iter_refs(node, parts: Tuple = ()) -> Iterator[Ref]:
    """Yield every reference in an instance, classified by the key it hangs from."""
    if isinstance(node, dict):
        if set(node) == {"policy_id", "version"}:
            yield Ref("policy", _ptr(parts), node["policy_id"], node["version"], body=node)
            return
        if node.get("reference_type") in SUPPORT_TAGS and "record_id" in node:
            yield Ref("support", _ptr(parts), node["record_id"], node.get("version", ""), body=node)
            return
        if is_contract_id(node.get("contract_id")) and "id" in node and "version" in node and parts:
            yield Ref("contract", _ptr(parts), node["id"], node["version"], contract=node["contract_id"], body=node)
            return
        for key, value in node.items():
            here = parts + (key,)
            if isinstance(value, dict) and "record_id" in value and "version" in value and "reference_type" not in value:
                if key in EXTERNAL_REF_KEYS:
                    yield Ref("external", _ptr(here), value["record_id"], value["version"], body=value)
                elif key == "retrieval_reference":
                    yield Ref("retrieval", _ptr(here), value["record_id"], value["version"], body=value)
                elif key in EVIDENCE_REF_KEYS or key.endswith("_record"):
                    yield Ref("evidence", _ptr(here), value["record_id"], value["version"], body=value)
                else:
                    yield from iter_refs(value, here)
            elif isinstance(value, list) and key in ("parent_references", "challenge_links"):
                for i, item in enumerate(value):
                    if isinstance(item, dict) and "record_id" in item:
                        yield Ref("evidence", _ptr(here + (i,)), item["record_id"], item["version"], body=item)
            else:
                yield from iter_refs(value, here)
    elif isinstance(node, list):
        for i, item in enumerate(node):
            if isinstance(item, dict) and "record_id" in item and "version" in item and "reference_type" not in item and parts and parts[-1] in EVIDENCE_REF_KEYS:
                yield Ref("evidence", _ptr(parts + (i,)), item["record_id"], item["version"], body=item)
            else:
                yield from iter_refs(item, parts + (i,))


def claims_of(record: dict) -> dict:
    content = record.get("content", {})
    if content.get("content_type") == "claims":
        return {c["claim_id"]: c for c in content.get("claims", [])}
    return {}


def payload_of(record: dict):
    """The `value` of a typed payload, or None when the record carries claims instead."""
    content = record.get("content", {})
    if content.get("content_type") == "typed_payload":
        return content.get("payload", {}).get("value")
    return None


def payload_object_of(record: dict):
    """The whole payload object (data_type, payload_schema_reference, value): `payload_location` pointers start here."""
    content = record.get("content", {})
    if content.get("content_type") == "typed_payload":
        return content.get("payload")
    return None


def resolve_pointer(document, pointer: str):
    """Resolve an RFC 6901 JSON pointer ('/' alone names the whole document here); raise KeyError when it does not resolve.

    A pointer that does not start with '/', and a list index that is not a plain number, do not resolve.
    """
    if pointer in ("", "/"):
        return document
    if not isinstance(pointer, str) or not pointer.startswith("/"):
        raise KeyError(pointer)
    current = document
    for token in pointer[1:].split("/"):
        token = token.replace("~1", "/").replace("~0", "~")
        if isinstance(current, list):
            if not re.fullmatch(r"0|[1-9][0-9]*", token):
                raise KeyError(pointer)
            current = current[int(token)]
        elif isinstance(current, dict):
            current = current[token]
        else:
            raise KeyError(pointer)
    return current
