"""Reference commit-time check for the synthetic examples.

This is a small, pure function that shows the questions an action gateway must ask at commit. It is not an
implementation of a gateway: it has no state of its own, no concurrency control and no connection to a target.

Every decision is made as of the attempt (`attempted_at`). Information counts only if it was available then:
evidence admitted at or before the attempt, and a revocation observation made at or before it. A time that is
missing, tagged unknown or malformed never passes. The attempt is blocked, and the reason names the time to supply.
Equality counts as available: a time equal to `attempted_at` was reached when the attempt was made.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from .model import Instance, Model, claims_of, payload_of, resolve_pointer

# The same shape as the schema's date-time pattern: a zone designator is required. ASCII digits only: \d would also match the digits of other scripts.
_RFC3339 = re.compile(r"(\d{4})-(\d{2})-(\d{2})[Tt](\d{2}):(\d{2}):(\d{2})(?:\.(\d+))?(?:([Zz])|([+-])(\d{2}):(\d{2}))", re.ASCII)


def parse_time(value) -> Optional[datetime]:
    """An aware datetime for an RFC 3339 timestamp, or None if it cannot be compared exactly.

    None means missing, tagged unknown, malformed, without a zone, with a zone offset that is not a real offset (hours 00-23, minutes
    00-59), or finer than a microsecond: a time is compared to the microsecond, and a fraction beyond that which is not zero would be
    rounded down, so that an observation made after the attempt could look as if it had been made at it. A time that cannot be
    compared exactly is not trusted.
    """
    if not isinstance(value, str):
        return None
    match = _RFC3339.fullmatch(value)
    if match is None:
        return None
    year, month, day, hour, minute, second = (int(match.group(i)) for i in range(1, 7))
    fraction = match.group(7) or ""
    if fraction[6:].strip("0"):
        return None
    micro = int(fraction[:6].ljust(6, "0"))
    try:
        zone = timezone.utc
        if match.group(9):
            offset_hours, offset_minutes = int(match.group(10)), int(match.group(11))
            if offset_hours > 23 or offset_minutes > 59:
                return None
            offset = timedelta(hours=offset_hours, minutes=offset_minutes)
            zone = timezone(offset if match.group(9) == "+" else -offset)
        return datetime(year, month, day, hour, minute, second, micro, tzinfo=zone)
    except ValueError:
        return None


def ts(value: str) -> datetime:
    """Parse an RFC 3339 timestamp into an aware datetime. Raises ValueError for anything else."""
    parsed = parse_time(value)
    if parsed is None:
        raise ValueError("%r is not an RFC 3339 timestamp with a time zone" % (value,))
    return parsed


@dataclass
class Reason:
    code: str
    message: str

    def as_dict(self) -> dict:
        return {"code": self.code, "message": self.message}


GATE_CODES = (
    "GRANT_REVOKED", "REVOCATION_NOT_YET_OBSERVED", "REVOCATION_TIME_UNKNOWN", "REVOCATION_UNVERIFIED",
    "GRANT_EXPIRED", "GRANT_NOT_YET_VALID", "GRANT_TIME_UNKNOWN", "GRANT_SUPERSEDED", "GRANT_NOT_BOUND",
    "ACTION_NOT_PERMITTED", "TARGET_NOT_PERMITTED", "PARAMETER_NOT_PERMITTED",
    "EVIDENCE_UNRESOLVED", "EVIDENCE_NOT_YET_ADMITTED", "EVIDENCE_TIME_UNKNOWN", "EVIDENCE_NOT_CURRENT", "EVIDENCE_STALE",
    "PRECONDITION_UNDEFINED", "PRECONDITION_FAILED", "PER_ACTION_LIMIT", "CUMULATIVE_LIMIT",
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
    start: Optional[datetime]   # None: the attempt's time is unknown, so the entry counts in every window (the conservative reading)
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


def _object(value) -> dict:
    return value if isinstance(value, dict) else {}


def availability_problem(record: Instance, at: datetime) -> Optional[Reason]:
    """Why the record could not be relied on at `at` because it had not been admitted by then, or None if it was available.

    A record is available from the later of its admission time and its ingestion time. The business event it
    describes does not matter here: an event is not known to the system until a record of it has been admitted.
    """
    label = "%s %s" % (record.id, record.version)
    admission, times = _object(record.data.get("producer_admission")), _object(record.data.get("times"))
    if admission.get("admission_status") != "admitted":
        return Reason("EVIDENCE_NOT_YET_ADMITTED", "%s has admission status %r, not 'admitted'" % (label, admission.get("admission_status")))
    stamps = [("admitted", admission.get("admission_time")), ("ingested", times.get("ingestion"))]
    late = [(name, value) for name, value in stamps if parse_time(value) is not None and parse_time(value) > at]
    if late:
        return Reason("EVIDENCE_NOT_YET_ADMITTED", "%s was %s at %s, after the attempt" % (label, late[0][0], late[0][1]))
    unknown = [name for name, value in stamps if parse_time(value) is None]
    if unknown:
        return Reason("EVIDENCE_TIME_UNKNOWN", "the time %s was %s is missing or unknown, so it cannot be shown to have been available at the attempt" % (label, unknown[0]))
    return None


def lifecycle_problem(record: Instance, at: datetime) -> Optional[Reason]:
    """Why the record was not current in its lifecycle at `at`, or None if its lifecycle allowed use.

    A non-current state (superseded, withdrawn, revoked, expired) applies from its effective time. The record has
    one time per lifecycle state, so it cannot separate when a change took effect from when it became known:
    blocking from the effective time is the conservative reading.
    """
    label = "%s %s" % (record.id, record.version)
    lifecycle = _object(record.data.get("lifecycle"))
    state, effective = lifecycle.get("state"), parse_time(lifecycle.get("effective_time"))
    if effective is None:
        return Reason("EVIDENCE_TIME_UNKNOWN", "the time %s took lifecycle state %r is missing or unknown, so its state at the attempt cannot be established" % (label, state))
    if state == "current":
        if effective > at:
            return Reason("EVIDENCE_NOT_CURRENT", "%s became current at %s, after the attempt" % (label, lifecycle["effective_time"]))
        return None
    if effective > at:
        return None
    return Reason("EVIDENCE_NOT_CURRENT", "%s was %s at %s" % (label, state, lifecycle["effective_time"]))


def is_current_at(record: Instance, at: datetime) -> bool:
    """A record is current at `at` unless a non-current lifecycle state had already taken effect. Unknown times are not current."""
    return lifecycle_problem(record, at) is None


def usable_at(record: Instance, at: datetime) -> bool:
    """A record can support a precondition at `at` only if it had been admitted and was still current."""
    return availability_problem(record, at) is None and lifecycle_problem(record, at) is None


def freshness_max_age(model: Model, record: dict) -> Optional[float]:
    ref = record["times"]["freshness"]["policy_reference"]
    policy = model.registry.policy(ref["policy_id"], ref["version"])
    if policy and policy.get("type") == "freshness":
        return float(policy["max_age_hours"])
    return None


def age_hours(record: dict, at: datetime) -> Optional[float]:
    """Hours between the record's business event time and `at`, or None if the event time is not known."""
    event = _object(_object(record.get("times")).get("event"))
    occurred = parse_time(event.get("value")) if event.get("state") == "known" else None
    if occurred is None:
        return None
    return (at - occurred).total_seconds() / 3600.0


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
    """The latest recorded state of the target at or before `at`. An entry with no usable time is not an observation."""
    latest, latest_at = {}, None
    for item in model.registry.target_states:
        seen = parse_time(item.get("at"))
        if item.get("entity_id") == entity and seen is not None and seen <= at and (latest_at is None or seen >= latest_at):
            latest, latest_at = item["state"], seen
    return latest


def _target_permitted(target: dict, permitted: List[dict]) -> bool:
    """Exact match, or the explicit wildcard entity_id '*' for the same entity type (a convention of this reference check)."""
    return any(p == target or (p["entity_id"] == "*" and p["entity_type"] == target["entity_type"]) for p in permitted)


def _issued(grant: Instance) -> Optional[datetime]:
    return parse_time(_object(grant.data.get("identity_principals")).get("issuance_time"))


def grant_in_force(model: Model, grant_id: str, at: datetime) -> Optional[Instance]:
    """The latest version of a grant that had been issued by `at`. A version with no known issuance time is not in force."""
    issued = [g for g in model.versions("C06", grant_id) if _issued(g) is not None and _issued(g) <= at]
    return issued[-1] if issued else None


def evaluate_commit(model: Model, proposal: Instance, grant: Instance, at: datetime, ledger: List[LedgerEntry]) -> Decision:
    """Recheck, at commit, everything an earlier approval cannot vouch for. Returns ALLOW only if every check holds.

    `at` is the attempt time. Only what was available and valid at `at` counts, and a required time that is missing or unknown blocks.
    """
    if at is None or at.tzinfo is None:
        raise ValueError("the attempt time must be a timezone-aware datetime")
    reasons: List[Reason] = []
    p, g = proposal.data, grant.data
    life, scope = g["limits_lifecycle"], g["scope_binding"]

    # 1. The grant itself is valid at the attempt, and a revocation observation made by then shows it unrevoked.
    rev = _object(life.get("revocation"))
    observed_at = parse_time(rev.get("checked_at"))
    if observed_at is None:
        reasons.append(Reason("REVOCATION_TIME_UNKNOWN", "the time of the revocation check (state %r) is missing or unknown, so it cannot be shown to precede the attempt" % rev.get("state")))
    elif observed_at > at:
        reasons.append(Reason("REVOCATION_NOT_YET_OBSERVED", "the only revocation check on record (%r at %s) came after the attempt, so it cannot show that grant %s %s was unrevoked then" % (rev.get("state"), rev["checked_at"], grant.id, grant.version)))
    elif rev.get("state") == "revoked":
        reasons.append(Reason("GRANT_REVOKED", "grant %s %s was revoked at %s" % (grant.id, grant.version, rev["checked_at"])))
    elif rev.get("state") != "not_revoked":
        reasons.append(Reason("REVOCATION_UNVERIFIED", "revocation state is %r, so the grant cannot be shown to be unrevoked" % rev.get("state")))
    expiry, issued = parse_time(life.get("expiry")), _issued(grant)
    if expiry is None:
        reasons.append(Reason("GRANT_TIME_UNKNOWN", "the grant's expiry is missing or unknown, so it cannot be shown to be unexpired at the attempt"))
    elif expiry <= at:
        reasons.append(Reason("GRANT_EXPIRED", "grant expired at %s" % life["expiry"]))
    if issued is None:
        reasons.append(Reason("GRANT_TIME_UNKNOWN", "the grant's issuance time is missing or unknown, so it cannot be shown to have been issued by the attempt"))
    elif issued > at:
        reasons.append(Reason("GRANT_NOT_YET_VALID", "grant issued after the attempt"))
    newest = grant_in_force(model, grant.id, at)
    if newest is not None and newest.version != grant.version:
        reasons.append(Reason("GRANT_SUPERSEDED", "grant version %s is in force; %s is no longer usable" % (newest.version, grant.version)))
    for other in model.versions("C06", grant.id):
        if other.version != grant.version and _issued(other) is None:
            reasons.append(Reason("GRANT_TIME_UNKNOWN", "grant version %s has no known issuance time, so it cannot be ruled out that it replaced %s before the attempt" % (other.version, grant.version)))

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

    # 3. The evidence had been admitted by the attempt, was still current, and was fresh.
    for ref in evidence_refs(p, g):
        rec = _record(model, ref)
        if rec is None:
            reasons.append(Reason("EVIDENCE_UNRESOLVED", "evidence %s %s does not exist" % (ref["record_id"], ref["version"])))
            continue
        unavailable = availability_problem(rec, at)
        if unavailable is not None:
            reasons.append(unavailable)
            continue
        stale_or_gone = lifecycle_problem(rec, at)
        if stale_or_gone is not None:
            reasons.append(stale_or_gone)
        limit = freshness_max_age(model, rec.data)
        if limit is not None:
            age = age_hours(rec.data, at)
            if age is None:
                reasons.append(Reason("EVIDENCE_TIME_UNKNOWN", "the event time of %s %s is unknown, so its age under its freshness policy cannot be established" % (rec.id, rec.version)))
            elif age > limit:
                reasons.append(Reason("EVIDENCE_STALE", "%s %s is %.1f h old; policy allows %.0f h" % (rec.id, rec.version, age, limit)))

    # 4. Preconditions hold, judged only on evidence that was usable at the attempt.
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
                if rec and rec.id.startswith(rule["record_prefix"]) and usable_at(rec, at):
                    try:
                        ok = resolve_pointer(payload_of(rec.data), rule["pointer"]) == rule["equals"]
                    except (KeyError, IndexError, TypeError, ValueError):
                        ok = False
        elif rule["type"] == "evidence_fresh":
            for ref in refs:
                rec = _record(model, ref)
                if rec and rec.id.startswith(rule["record_prefix"]) and usable_at(rec, at):
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
        window = _object(limit.get("accounting_window"))
        window_start, window_end = parse_time(window.get("start")), parse_time(window.get("end"))
        if window_start is None or window_end is None or window_end <= window_start:
            reasons.append(Reason("GRANT_TIME_UNKNOWN", "the accounting window of the %s limit has a start or an end that is missing, unknown or out of order, so the capacity already used in it cannot be established" % limit.get("units")))
            continue
        used = sum(
            e.quantity for e in ledger
            if e.grant_id == grant.id and e.accounting_scope == limit["accounting_scope"] and e.units == limit["units"]
            and (e.start is None or window_start <= e.start < window_end)
        )
        if used + qty > limit["quantity"]:
            reasons.append(Reason("CUMULATIVE_LIMIT", "%s already counted plus %s would exceed %s %s in the window" % (_fmt(used), _fmt(qty), _fmt(limit["quantity"]), limit["units"])))
        else:
            reserve = {"units": limit["units"], "quantity": qty, "counted_before": used}
    allow = not reasons
    return Decision(allow, reasons, reserve if allow else None)


def _fmt(x: float) -> str:
    return ("%d" % x) if float(x).is_integer() else ("%.2f" % x)


def receipt_known_at(receipt: dict) -> Optional[datetime]:
    """When this version of a receipt became known: its authoritative verification time, otherwise its submission time.

    None when that time is missing or cannot be compared exactly: such a receipt is counted as already known (see the ledger).
    """
    ver = _object(_object(receipt.get("verification_recovery")).get("verification"))
    if ver.get("state") == "authoritatively_verified":
        return parse_time(ver.get("time"))
    return parse_time(_object(_object(receipt.get("outcome")).get("timestamps")).get("submitted"))


def ledger_from_receipts(model: Model, before: datetime, exclude_receipt_id: str = "") -> List[LedgerEntry]:
    """Capacity already used or held at `before`: for each attempt, the latest receipt version already known then.

    A receipt known at exactly `before` is not counted: replaying an attempt (a stored evaluation, or its own receipt)
    must not charge the attempt against itself, and a commit serializes its reservation with the one it follows.
    A receipt whose time is unknown cannot be shown to come after `before`, so it is counted: capacity is never freed by a time
    that cannot be read.
    """
    latest: Dict[str, Instance] = {}
    for rec in model.of("C07"):
        known = receipt_known_at(rec.data)
        if rec.id == exclude_receipt_id or (known is not None and known >= before):
            continue
        cur = latest.get(rec.id)
        if cur is None or _vn(rec.version) > _vn(cur.version):
            latest[rec.id] = rec
    entries: List[LedgerEntry] = []
    for rec in latest.values():
        d = rec.data
        submitted = parse_time(_object(_object(d.get("outcome")).get("timestamps")).get("submitted"))
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
