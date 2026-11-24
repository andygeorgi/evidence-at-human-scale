"""Load contract instances and the example registry; classify every reference inside an instance."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
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


def load_registry(path: Path) -> Registry:
    if not path.exists():
        return Registry()
    raw = json.loads(path.read_text(encoding="utf-8"))
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
    for path in sorted(root.rglob("*.json")):
        if path.name == "registry.json":
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:  # includes JSONDecodeError and UnicodeDecodeError
            findings.append(Finding("ID000", "cannot read JSON: %s" % exc, rel(path), hint="repair or remove the file; every .json file below the folder must be valid UTF-8 JSON"))
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
        registry = load_registry(root / "registry.json")
    except (OSError, ValueError, AttributeError) as exc:
        findings.append(Finding("ID000", "cannot read the registry: %s" % exc, rel(root / "registry.json"), hint="registry.json must be a JSON object"))
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
    """Resolve an RFC 6901 JSON pointer; raise KeyError when it does not resolve."""
    if pointer in ("", "/"):
        return document
    current = document
    for token in pointer.lstrip("/").split("/"):
        token = token.replace("~1", "/").replace("~0", "~")
        if isinstance(current, list):
            current = current[int(token)]
        elif isinstance(current, dict):
            current = current[token]
        else:
            raise KeyError(pointer)
    return current
