"""Load contract instances and the example registry; classify every reference inside an instance."""
from __future__ import annotations

import json
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
    raw: dict = field(default_factory=dict)

    def policy(self, policy_id: str, version: str) -> Optional[dict]:
        return self.policies.get(policy_id, {}).get(version)


@dataclass
class Model:
    instances: Dict[Key, Instance]
    registry: Registry
    root: Path

    def get(self, contract: str, id_: str, version: str) -> Optional[Instance]:
        return self.instances.get((contract, id_, version))

    def of(self, contract: str) -> List[Instance]:
        return [i for k, i in sorted(self.instances.items()) if k[0] == contract]

    def versions(self, contract: str, id_: str) -> List[Instance]:
        return sorted((i for k, i in self.instances.items() if k[0] == contract and k[1] == id_), key=lambda i: _vnum(i.version))


def _vnum(version: str) -> int:
    digits = "".join(c for c in version if c.isdigit())
    return int(digits) if digits else 0


def identity_of(data: dict) -> Optional[Tuple[str, str, str]]:
    contract = data.get("contract_id")
    if contract not in IDENTITY:
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
        raw=raw,
    )


def load_registry(path: Path) -> Registry:
    if not path.exists():
        return Registry()
    return registry_from_dict(json.loads(path.read_text(encoding="utf-8")))


def load_model(root: Path) -> Tuple[Model, List[Finding]]:
    """Index every contract instance below `root` (any .json whose top-level object has contract_id C01-C07)."""
    findings: List[Finding] = []
    instances: Dict[Key, Instance] = {}
    for path in sorted(root.rglob("*.json")):
        if path.name == "registry.json":
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            findings.append(Finding("ID000", "cannot read JSON: %s" % exc, rel(path)))
            continue
        if not isinstance(data, dict) or data.get("contract_id") not in CONTRACT_DEFS:
            continue
        ident = identity_of(data)
        if ident is None:
            findings.append(Finding("ID002", "instance has no readable identity (id and version)", rel(path), doc=doc_for_contract(data.get("contract_id"))))
            continue
        inst = Instance(ident[0], ident[1], ident[2], data, path)
        if inst.key in instances:
            findings.append(Finding("ID001", "duplicate identity %s (also in %s)" % (inst.label(), instances[inst.key].file), inst.file, doc=doc_for_contract(inst.contract)))
            continue
        instances[inst.key] = inst
    return Model(instances, load_registry(root / "registry.json"), root), findings


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
        if node.get("contract_id") in CONTRACT_DEFS and "id" in node and "version" in node and parts:
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
