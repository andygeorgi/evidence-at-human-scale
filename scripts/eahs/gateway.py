"""Reference commit-time check for the synthetic examples.

This is a small, pure function that shows the questions an action gateway must ask at commit. It is not an
implementation of a gateway: it has no state of its own, no concurrency control and no connection to a target.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from .model import Instance, Model, claims_of, payload_of, resolve_pointer


def ts(value: str) -> datetime:
    """Parse an RFC 3339 timestamp into an aware datetime."""
    text = value.strip().replace("Z", "+00:00").replace("z", "+00:00")
    parsed = datetime.fromisoformat(text)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


@dataclass
class Reason:
    code: str
    message: str

    def as_dict(self) -> dict:
        return {"code": self.code, "message": self.message}


GATE_CODES = (
    "GRANT_REVOKED", "REVOCATION_UNVERIFIED", "GRANT_EXPIRED", "GRANT_NOT_YET_VALID", "GRANT_SUPERSEDED", "GRANT_NOT_BOUND",
    "ACTION_NOT_PERMITTED", "TARGET_NOT_PERMITTED", "PARAMETER_NOT_PERMITTED", "EVIDENCE_UNRESOLVED", "EVIDENCE_NOT_CURRENT",
    "EVIDENCE_STALE", "PRECONDITION_UNDEFINED", "PRECONDITION_FAILED", "PER_ACTION_LIMIT", "CUMULATIVE_LIMIT",
)


@dataclass
class Decision:
    allow: bool
    reasons: List[Reason] = field(default_factory=list)
    reserve: Optional[dict] = None

    @property
    def codes(self) -> List[str]:
        return [r.code for r in self.reasons]

    def as_dict(self) -> dict:
        out = {"decision": "ALLOW" if self.allow else "BLOCK", "reasons": [r.as_dict() for r in self.reasons]}
        if self.reserve:
            out["reserve"] = self.reserve
        return out


@dataclass
class LedgerEntry:
    grant_id: str
    accounting_scope: str
    units: str
    quantity: float
    state: str          # consumed | reserved
    start: datetime
    receipt: str = ""


def action_quantity(proposal: dict, units: str) -> float:
    """Quantity a proposal would consume in `units` (EUR from the amount parameter; one per action for counted units)."""
    if units == "EUR":
        for p in proposal["action"]["typed_parameters"]:
            if p["name"] == "amount_eur":
                return float(p["value"])
        raise KeyError("proposal has no amount_eur parameter")
    return 1.0


def _record(model: Model, ref: dict) -> Optional[Instance]:
    return model.get("C02", ref["record_id"], ref["version"])


def is_current_at(record: Instance, at: datetime) -> bool:
    """A record is current at `at` unless a non-current lifecycle state had already taken effect."""
    lc = record.data["lifecycle"]
    if lc["state"] == "current":
        return True
    return ts(lc["effective_time"]) > at


def freshness_max_age(model: Model, record: dict) -> Optional[float]:
    ref = record["times"]["freshness"]["policy_reference"]
    policy = model.registry.policy(ref["policy_id"], ref["version"])
    if policy and policy.get("type") == "freshness":
        return float(policy["max_age_hours"])
    return None


def age_hours(record: dict, at: datetime) -> Optional[float]:
    event = record["times"]["event"]
    if event.get("state") != "known":
        return None
    return (at - ts(event["value"])).total_seconds() / 3600.0


def evidence_refs(proposal: dict, grant: dict) -> List[dict]:
    refs = list(proposal["action"]["evidence_references"])
    refs += list(grant["scope_binding"]["evidence_constraints"])
    seen, out = set(), []
    for r in refs:
        key = (r["record_id"], r["version"])
        if key not in seen:
            seen.add(key)
            out.append(r)
    return out


def _target_state(model: Model, entity: str, at: datetime) -> dict:
    latest, latest_at = {}, None
    for item in model.registry.target_states:
        if item["entity_id"] == entity and ts(item["at"]) <= at and (latest_at is None or ts(item["at"]) >= latest_at):
            latest, latest_at = item["state"], ts(item["at"])
    return latest


def _target_permitted(target: dict, permitted: List[dict]) -> bool:
    """Exact match, or the explicit wildcard entity_id '*' for the same entity type (a convention of this reference check)."""
    return any(p == target or (p["entity_id"] == "*" and p["entity_type"] == target["entity_type"]) for p in permitted)


def grant_in_force(model: Model, grant_id: str, at: datetime) -> Optional[Instance]:
    """The latest version of a grant that had been issued by `at`."""
    issued = [g for g in model.versions("C06", grant_id) if ts(g.data["identity_principals"]["issuance_time"]) <= at]
    return issued[-1] if issued else None


def evaluate_commit(model: Model, proposal: Instance, grant: Instance, at: datetime, ledger: List[LedgerEntry]) -> Decision:
    """Recheck, at commit, everything an earlier approval cannot vouch for. Returns ALLOW only if every check holds."""
    reasons: List[Reason] = []
    p, g = proposal.data, grant.data
    life, scope = g["limits_lifecycle"], g["scope_binding"]

    # 1. The grant itself is current, and the revocation check can be trusted.
    rev = life["revocation"]
    if rev["state"] == "revoked" and ts(rev["checked_at"]) <= at:
        reasons.append(Reason("GRANT_REVOKED", "grant %s %s was revoked at %s" % (grant.id, grant.version, rev["checked_at"])))
    elif rev["state"] != "not_revoked":
        reasons.append(Reason("REVOCATION_UNVERIFIED", "revocation state is %r, so the grant cannot be shown to be unrevoked" % rev["state"]))
    if ts(life["expiry"]) <= at:
        reasons.append(Reason("GRANT_EXPIRED", "grant expired at %s" % life["expiry"]))
    if ts(g["identity_principals"]["issuance_time"]) > at:
        reasons.append(Reason("GRANT_NOT_YET_VALID", "grant issued after the attempt"))
    newest = grant_in_force(model, grant.id, at)
    if newest is not None and newest.version != grant.version:
        reasons.append(Reason("GRANT_SUPERSEDED", "grant version %s is in force; %s is no longer usable" % (newest.version, grant.version)))

    # 2. The grant covers exactly this action.
    binding = scope["binding"]
    if binding["binding_type"] == "exact_proposal":
        ref = binding["proposal_reference"]
        if (ref["id"], ref["version"]) != (proposal.id, proposal.version):
            reasons.append(Reason("GRANT_NOT_BOUND", "approval is bound to %s %s, not to %s %s" % (ref["id"], ref["version"], proposal.id, proposal.version)))
    if p["action"]["action_kind"] not in scope["permitted_actions"]:
        reasons.append(Reason("ACTION_NOT_PERMITTED", "action %s is outside the grant" % p["action"]["action_kind"]))
    if not _target_permitted(p["action"]["exact_target"], scope["permitted_targets"]):
        reasons.append(Reason("TARGET_NOT_PERMITTED", "target %s is outside the grant" % p["action"]["exact_target"]["entity_id"]))
    allowed_params = {x["name"]: x["data_type"] for x in scope["permitted_parameters"]}
    for param in p["action"]["typed_parameters"]:
        if allowed_params.get(param["name"]) != param["data_type"]:
            reasons.append(Reason("PARAMETER_NOT_PERMITTED", "parameter %s (%s) is not permitted by the grant" % (param["name"], param["data_type"])))

    # 3. The evidence is still current and fresh.
    for ref in evidence_refs(p, g):
        rec = _record(model, ref)
        if rec is None:
            reasons.append(Reason("EVIDENCE_UNRESOLVED", "evidence %s %s does not exist" % (ref["record_id"], ref["version"])))
            continue
        if not is_current_at(rec, at):
            reasons.append(Reason("EVIDENCE_NOT_CURRENT", "%s %s was %s at %s" % (rec.id, rec.version, rec.data["lifecycle"]["state"], rec.data["lifecycle"]["effective_time"])))
        limit = freshness_max_age(model, rec.data)
        age = age_hours(rec.data, at)
        if limit is not None and age is not None and age > limit:
            reasons.append(Reason("EVIDENCE_STALE", "%s %s is %.1f h old; policy allows %.0f h" % (rec.id, rec.version, age, limit)))

    # 4. Preconditions hold.
    refs = evidence_refs(p, g)
    for pre in p["action"]["preconditions"]:
        rule = model.registry.preconditions.get(pre["condition_id"])
        if rule is None:
            reasons.append(Reason("PRECONDITION_UNDEFINED", "no rule is defined for %s" % pre["condition_id"]))
            continue
        ok = False
        if rule["type"] == "evidence_payload_equals":
            for ref in refs:
                rec = _record(model, ref)
                if rec and rec.id.startswith(rule["record_prefix"]) and is_current_at(rec, at):
                    try:
                        ok = resolve_pointer(payload_of(rec.data), rule["pointer"]) == rule["equals"]
                    except (KeyError, IndexError, TypeError, ValueError):
                        ok = False
        elif rule["type"] == "evidence_fresh":
            for ref in refs:
                rec = _record(model, ref)
                if rec and rec.id.startswith(rule["record_prefix"]) and is_current_at(rec, at):
                    age = age_hours(rec.data, at)
                    ok = age is not None and age <= float(rule["max_age_hours"])
        elif rule["type"] == "target_state_equals":
            ok = _target_state(model, rule["entity_id"], at).get(rule["key"]) == rule["equals"]
        if not ok:
            reasons.append(Reason("PRECONDITION_FAILED", "%s is not satisfied: %s" % (pre["condition_id"], pre["condition"])))

    # 5. Per-action and cumulative limits, counting consumed and reserved capacity.
    for limit in life["per_action_limits"]:
        qty = action_quantity(p, limit["units"])
        if qty > limit["quantity"]:
            reasons.append(Reason("PER_ACTION_LIMIT", "%s %s exceeds the per-action limit of %s %s" % (_fmt(qty), limit["units"], _fmt(limit["quantity"]), limit["units"])))
    reserve = None
    for limit in life["cumulative_limits"]:
        qty = action_quantity(p, limit["units"])
        window_start, window_end = ts(limit["accounting_window"]["start"]), ts(limit["accounting_window"]["end"])
        used = sum(
            e.quantity for e in ledger
            if e.grant_id == grant.id and e.accounting_scope == limit["accounting_scope"] and e.units == limit["units"]
            and window_start <= e.start < window_end
        )
        if used + qty > limit["quantity"]:
            reasons.append(Reason("CUMULATIVE_LIMIT", "%s already counted plus %s would exceed %s %s in the window" % (_fmt(used), _fmt(qty), _fmt(limit["quantity"]), limit["units"])))
        else:
            reserve = {"units": limit["units"], "quantity": qty, "counted_before": used}
    allow = not reasons
    return Decision(allow, reasons, reserve if allow else None)


def _fmt(x: float) -> str:
    return ("%d" % x) if float(x).is_integer() else ("%.2f" % x)


def receipt_known_at(receipt: dict) -> datetime:
    """When this version of a receipt became known: its authoritative verification time, otherwise its submission time."""
    ver = receipt["verification_recovery"]["verification"]
    if ver["state"] == "authoritatively_verified":
        return ts(ver["time"])
    return ts(receipt["outcome"]["timestamps"]["submitted"])


def ledger_from_receipts(model: Model, before: datetime, exclude_receipt_id: str = "") -> List[LedgerEntry]:
    """Capacity already used or held at `before`: for each attempt, the latest receipt version already known then."""
    latest: Dict[str, Instance] = {}
    for rec in model.of("C07"):
        if rec.id == exclude_receipt_id or receipt_known_at(rec.data) >= before:
            continue
        cur = latest.get(rec.id)
        if cur is None or _vn(rec.version) > _vn(cur.version):
            latest[rec.id] = rec
    entries: List[LedgerEntry] = []
    for rec in latest.values():
        d = rec.data
        submitted = ts(d["outcome"]["timestamps"]["submitted"])
        grant_ref = d["identity_binding"]["grant_reference"]
        grant = model.get("C06", grant_ref["id"], grant_ref["version"])
        proposal_ref = d["identity_binding"]["proposal_reference"]
        proposal = model.get("C05", proposal_ref["id"], proposal_ref["version"])
        if grant is None or proposal is None:
            continue
        state = d["outcome"]["state"]
        if state == "not_executed_verified":
            continue
        for limit in grant.data["limits_lifecycle"]["cumulative_limits"]:
            qty = action_quantity(proposal.data, limit["units"])
            held = "consumed" if state == "completed_verified" else "reserved"
            entries.append(LedgerEntry(grant.id, limit["accounting_scope"], limit["units"], qty, held, submitted, rec.id))
    return entries


def _vn(version: str) -> int:
    digits = "".join(c for c in version if c.isdigit())
    return int(digits) if digits else 0
