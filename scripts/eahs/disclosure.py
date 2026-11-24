"""Permission before disclosure: the viewer projection of Figure F09, written as code.

Three different things are easy to confuse. This repository does the first and the third, as a reference on invented data, and
not the second:

* SNAPSHOT VALIDATION checks a stored output (a C03 selection or a C04 packet) against the stored permission decisions. It
  runs over a snapshot that already exists, after the fact (``semantics.check_disclosure``).
* AUTHORIZATION ENFORCEMENT decides, when a request arrives, who may know that an input exists and who may read it. Nothing
  here enforces anything: a permission decision in the example registry stands for its result.
* VIEWER PROJECTION builds what one viewer is shown from authorized inputs only. This module is a reference for it.

The repository validator is therefore not an authorization service. A pass of the snapshot validation says that the stored
outputs agree with the stored decisions; it does not say that a real system would ask the same questions or enforce them.

The projection is built in a fixed order, and the order is the point:

1. Bind the decision to the viewer. A decision must name the exact requesting principal of the C01 context, and the tenant
   and the permitted purpose wherever it claims them. A decision that does not bind is no decision: the input has no entry.
2. May the viewer know that the input exists? If not, nothing about it is shown. It adds nothing to the output except the
   one coverage statement that every output carries, whether or not anything is withheld. Its count, its category, its
   freshness, its materiality and whether an investigation is open change nothing the viewer sees.
3. May the viewer read it? If not, and its existence may be disclosed, the entry is exactly the generic disclosure the
   decision configures: every field of the entry comes from the decision and none from the input.
4. Only for an input the viewer may read is it classified (stale, not assessed, unavailable, missing, negative, not
   retrieved), and only then is anything about its state shown.

Classifying first ("it is stale") and filtering afterwards would tell a viewer that a record exists, and how old it is, before
anyone asked whether they may know. Checking one safe field and leaving its siblings (a materiality, a reason, a scope) to
free text would let the siblings say what the safe field does not. So the projection is constructed, field by field, from
what the decision permits. It is not a filter over the full record and it is not a list of forbidden words.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, List, Mapping, Optional, Sequence, Tuple

NO_ENTRY = "no entry"
#: The questions in the order they are asked. The first two are about permission and come before any classification.
DECISION_ORDER = (NO_ENTRY, "inaccessible", "stale", "not_assessed", "unavailable", "missing", "negative", "not_retrieved")


@dataclass(frozen=True)
class Viewer:
    """Who an output is for: the requesting principal, tenant and permitted purpose of the C01 context, and the entities it names."""
    principal: str
    tenant: str = ""
    purpose: str = ""
    entities: Tuple[Mapping[str, Any], ...] = ()


@dataclass(frozen=True)
class Decision:
    """A permission decision, as the registry stores it.

    `permitted_view` is the complete generic disclosure for an input the viewer may know about but may not read: every
    viewer-facing value of its entry, so that no field of the entry is taken from the input itself.
    """
    principal: str = ""
    tenant: str = ""
    purpose: str = ""
    read_allowed: bool = False
    disclose_existence_allowed: bool = False
    permitted_disclosure: str = ""
    permitted_view: Mapping[str, Any] = field(default_factory=dict)

    @classmethod
    def from_registry(cls, raw: Any) -> "Decision":
        """A decision from its registry entry. Anything missing or malformed reads as 'not permitted'."""
        raw = raw if isinstance(raw, dict) else {}
        view = raw.get("permitted_view")
        return cls(
            principal=raw["principal"] if isinstance(raw.get("principal"), str) else "",
            tenant=raw["tenant"] if isinstance(raw.get("tenant"), str) else "",
            purpose=raw["purpose"] if isinstance(raw.get("purpose"), str) else "",
            read_allowed=raw.get("read_allowed") is True,
            disclose_existence_allowed=raw.get("disclose_existence_allowed") is True,
            permitted_disclosure=raw["permitted_disclosure"] if isinstance(raw.get("permitted_disclosure"), str) else "",
            permitted_view=view if isinstance(view, dict) else {},
        )


def binding_problems(decision: Optional[Decision], viewer: Viewer) -> List[str]:
    """Why a decision does not bind to this viewer (empty if it does). Binding comes first: an unbound decision permits nothing."""
    if decision is None:
        return ["there is no permission decision for this input"]
    problems: List[str] = []
    if not decision.principal:
        problems.append("the decision names no principal, so it cannot be bound to the requesting principal")
    elif decision.principal != viewer.principal:
        problems.append("the decision is for principal %s, not for the requesting principal %s" % (decision.principal, viewer.principal))
    if decision.tenant and decision.tenant != viewer.tenant:
        problems.append("the decision is for tenant %s, not for tenant %s" % (decision.tenant, viewer.tenant or "(none)"))
    if decision.purpose and decision.purpose != viewer.purpose:
        problems.append("the decision is for the purpose %r, not for %r" % (decision.purpose, viewer.purpose))
    return problems


def may_know(decision: Optional[Decision], viewer: Viewer) -> bool:
    """May the viewer know that the input exists? Only a decision that binds to the viewer can say yes."""
    return not binding_problems(decision, viewer) and (decision.read_allowed or decision.disclose_existence_allowed)


def may_read(decision: Optional[Decision], viewer: Viewer) -> bool:
    return may_know(decision, viewer) and decision.read_allowed


# ---------------------------------------------------------------------------------------------------- the generic entries
def gap_entry(decision: Decision, viewer: Viewer, decision_reference: Mapping[str, Any]) -> dict:
    """The C03/C04 missingness entry for an input the viewer may know about but may not read: nothing in it comes from the input.

    The entities are the ones the viewer's own request named. Every other value is the decision's.
    """
    view = decision.permitted_view.get("gap", {})
    scope = view.get("scope", {})
    return {
        "state": "inaccessible",
        "scope": {"entity_references": [dict(e) for e in viewer.entities], "task": scope.get("task"), "jurisdiction": scope.get("jurisdiction"),
                  "units": scope.get("units"), "interpretation": scope.get("interpretation")},
        "expected_evidence": view.get("expected_evidence"),
        "materiality": view.get("materiality"),
        "reason": view.get("reason"),
        "assessment_basis": view.get("assessment_basis"),
        "permission_decision_reference": dict(decision_reference),
        "permission_safe_summary": decision.permitted_disclosure,
    }


def retrieval_entry(decision: Decision, decision_reference: Mapping[str, Any]) -> dict:
    """The C03 retrieval unit for a part of the scope the viewer may not read: its wording and its fields come from the decision."""
    view = decision.permitted_view.get("retrieval", {})
    return {
        "retrieval_unit_id": view.get("retrieval_unit_id"),
        "authorized_scope": view.get("authorized_scope"),
        "authorization_reference": dict(decision_reference),
        "status": "not_permitted",
        "attempted_at": view.get("attempted_at"),
        "completed_at": view.get("completed_at"),
        "reason": view.get("reason"),
        "summary_visibility": "permission_safe",
        "summary": decision.permitted_disclosure,
    }


def differences(expected: Any, actual: Any, pointer: str = "") -> List[Tuple[str, Any]]:
    """Where `actual` is not exactly `expected`: (JSON pointer, the value expected there). Extra and missing fields both count."""
    if isinstance(expected, dict) and isinstance(actual, dict):
        found: List[Tuple[str, Any]] = []
        for key in expected:
            if key not in actual:
                found.append((pointer + "/" + str(key), expected[key]))
            else:
                found.extend(differences(expected[key], actual[key], pointer + "/" + str(key)))
        found.extend((pointer + "/" + str(key), None) for key in actual if key not in expected)
        return found
    return [] if expected == actual else [(pointer or "/", expected)]


# ---------------------------------------------------------------------------------------------------- what the viewer is shown
@dataclass(frozen=True)
class ExpectedInput:
    """One input a task expected: everything the system knows about it, and the decision that governs it for this viewer.

    The facts (its name, category, count, materiality, open state, freshness and the rest) are exactly what the projection
    must not let through unless the viewer may read the input.
    """
    name: str
    decision: Optional[Decision] = None
    category: str = ""
    source_type: str = ""
    record_count: int = 0
    materiality: str = "unknown"
    open_state: str = ""
    record_available: bool = False
    record_fresh: bool = True
    check_performed: bool = True
    source_answered: bool = True
    retrieval_completed: bool = True
    absence_observed_with_complete_coverage: bool = False
    decision_reference: Mapping[str, Any] = field(default_factory=lambda: {"record_id": "AUTHZ-READ-LIMIT-0417", "version": "v1"})


@dataclass(frozen=True)
class Entry:
    label: str
    text: str
    #: every viewer-facing field of the entry, as canonical JSON: two views are identical only if all of it is
    fields: str = ""


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False)


def classify(item: ExpectedInput, viewer: Viewer) -> str:
    """The label the viewer sees for an expected input, asking the questions in order. NO_ENTRY means nothing is shown."""
    if not may_know(item.decision, viewer):
        return NO_ENTRY
    if not may_read(item.decision, viewer):
        return "inaccessible"
    if item.record_available and not item.record_fresh:
        return "stale"
    if not item.check_performed:
        return "not_assessed"
    if not item.source_answered:
        return "unavailable"
    if not item.retrieval_completed:
        return "missing"
    if item.absence_observed_with_complete_coverage:
        return "negative"
    return "not_retrieved"


def disclose(item: ExpectedInput, viewer: Viewer) -> Optional[Entry]:
    """What the viewer is told about one input, or None.

    An unreadable input is described by its decision's generic disclosure and nothing else. Only a readable input's own
    facts reach the entry, and they are the ones the viewer is permitted to see.
    """
    label = classify(item, viewer)
    if label == NO_ENTRY:
        return None
    if label == "inaccessible":
        return Entry(label, item.decision.permitted_disclosure, canonical(gap_entry(item.decision, viewer, item.decision_reference)))
    shown = {"label": label, "input": item.name, "category": item.category, "source_type": item.source_type, "materiality": item.materiality,
             "record_count": item.record_count, "open_state": item.open_state}
    return Entry(label, "%s: %s" % (label, item.name), canonical(shown))


def project(items: Sequence[ExpectedInput], viewer: Viewer, coverage_statement: str) -> List[Entry]:
    """The viewer's view of a task: an entry for each input they may know about, then the coverage statement every output carries."""
    return [entry for entry in (disclose(item, viewer) for item in items) if entry is not None] + [Entry("coverage", coverage_statement, canonical({"coverage": coverage_statement}))]
