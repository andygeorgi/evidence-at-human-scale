"""Reference commit-time check for the synthetic examples.

This is a small, pure function that shows the questions an action gateway must ask at commit. It is not an
implementation of a gateway: it has no state of its own, no concurrency control and no connection to a target.

Every decision is made as of the attempt (`attempted_at`). Information counts only if it was available then:
evidence admitted at or before the attempt, and a revocation observation made at or before it. A time that is
missing, tagged unknown or malformed never passes. The attempt is blocked, and the reason names the time to supply.
Equality counts as available: a time equal to `attempted_at` was reached when the attempt was made.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from fractions import Fraction
from typing import Dict, Iterable, List, Optional, Tuple

from .model import Instance, Model, claims_of, payload_of, resolve_pointer, version_number as _vn

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


def same_instant(first, second) -> bool:
    """Whether two timestamps name the same instant, however each is written: 10:00:00Z, 11:00:00+01:00 and 10:00:00.000+00:00 are one instant.

    A time that cannot be compared exactly (see `parse_time`) is the same as another only when the two are written alike.
    """
    a, b = parse_time(first), parse_time(second)
    return a == b if a is not None and b is not None else first == second


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
    quantity: float     # a number; infinity stands for an attempt whose amount could not be read, which counts without limit
    state: str          # consumed | reserved
    start: Optional[datetime]   # None: the attempt's time is unknown, so the entry counts in every window (the conservative reading)
    receipt: str = ""


def action_quantity(proposal: dict, units: str) -> Optional[float]:
    """Quantity a proposal would consume in `units` (EUR from the amount parameter; one per action for counted units).

    None when the proposal states no readable amount in EUR: a limit in EUR cannot then be checked, and the check blocks. An amount
    is readable when it is one number that is finite and not negative. A negative amount would give capacity back to the limit
    instead of using it, a parameter that is stated twice leaves it unclear which amount counts, and neither is guessed. The amount
    is returned as it is written (an integer stays an integer), so that nothing is rounded before it is compared.
    """
    if units == "EUR":
        amounts = [p.get("value") for p in _list(_object(proposal.get("action")).get("typed_parameters")) if isinstance(p, dict) and p.get("name") == "amount_eur"]
        if len(amounts) != 1 or isinstance(amounts[0], bool) or not isinstance(amounts[0], (int, float)):
            return None
        amount = amounts[0]
        if isinstance(amount, float) and not math.isfinite(amount):
            return None
        return amount if amount >= 0 else None
    return 1.0


def _exact(value) -> Fraction:
    """A finite number as it was written: an integer exactly, any other number by its shortest decimal text, so that 0.1 and 0.2 add up to 0.3
    and a number beyond the 53 bits of a double is not rounded."""
    return Fraction(value) if isinstance(value, int) else Fraction(Decimal(repr(value)))


def _plain(value: Optional[Fraction]):
    """A sum as the plain number a reader expects: an integer when it is one, infinity when it was without limit (None)."""
    if value is None:
        return float("inf")
    if value.denominator == 1:
        return int(value)
    try:
        return float(value)
    except OverflowError:
        return int(value)


def _used(entries: List["LedgerEntry"]) -> Optional[Fraction]:
    """What the entries hold together, exactly. None when one of them is without limit (an attempt whose amount could not be read)."""
    total = Fraction(0)
    for entry in entries:
        if isinstance(entry.quantity, float) and math.isinf(entry.quantity):
            return None
        total += _exact(entry.quantity)
    return total


def _over(used: Optional[Fraction], qty, cap) -> bool:
    """Whether what is already used (None: without limit) plus this amount is more than the cap, compared exactly."""
    if isinstance(cap, float) and math.isinf(cap):
        return cap < 0
    if used is None:
        return True
    return used + _exact(qty) > _exact(cap)


def _object(value) -> dict:
    return value if isinstance(value, dict) else {}


def _list(value) -> list:
    return value if isinstance(value, list) else []


def _record(model: Model, ref) -> Optional[Instance]:
    ref = _object(ref)
    record_id, version = ref.get("record_id"), ref.get("version")
    if not isinstance(record_id, str) or not isinstance(version, str):
        return None
    return model.get("C02", record_id, version)


def availability_problem(record: Instance, at: datetime, moment: str = "the attempt") -> Optional[Reason]:
    """Why the record could not be relied on at `at` because it had not been admitted by then, or None if it was available.

    A record is available from the later of its admission time and its ingestion time. The business event it
    describes does not matter here: an event is not known to the system until a record of it has been admitted.
    `moment` names what `at` is in the messages: the attempt of a commit check, or the as-of time of a decision packet.
    """
    label = "%s %s" % (record.id, record.version)
    admission, times = _object(record.data.get("producer_admission")), _object(record.data.get("times"))
    if admission.get("admission_status") != "admitted":
        return Reason("EVIDENCE_NOT_YET_ADMITTED", "%s has admission status %r, not 'admitted'" % (label, admission.get("admission_status")))
    stamps = [("admitted", admission.get("admission_time")), ("ingested", times.get("ingestion"))]
    late = [(name, value) for name, value in stamps if parse_time(value) is not None and parse_time(value) > at]
    if late:
        return Reason("EVIDENCE_NOT_YET_ADMITTED", "%s was %s at %s, after %s" % (label, late[0][0], late[0][1], moment))
    unknown = [name for name, value in stamps if parse_time(value) is None]
    if unknown:
        return Reason("EVIDENCE_TIME_UNKNOWN", "the time %s was %s is missing or unknown, so it cannot be shown to have been available at %s" % (label, unknown[0], moment))
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
    """The longest age, in hours, that the record's freshness policy allows; None when the policy that applies to the record is not one of freshness.

    Raises ValueError when the record cannot be shown to be fresh: it names no freshness policy (C02 requires one), the policy it
    names is not in the registry, or the policy states no limit that can be read. None of that is the same as no limit.
    """
    ref = _object(_object(_object(record.get("times")).get("freshness")).get("policy_reference"))
    policy_id, version = ref.get("policy_id"), ref.get("version")
    if not isinstance(policy_id, str) or not isinstance(version, str):
        raise ValueError("the record names no freshness policy (a policy id and a version)")
    policy = _object(_object(model.registry.policies.get(policy_id)).get(version))
    if not policy:
        raise ValueError("the freshness policy %s %s that the record names is not in the registry" % (policy_id, version))
    kind = policy.get("type")
    if not isinstance(kind, str) or not kind.strip():
        raise ValueError("the policy %s %s states no kind (its 'type' is missing or is not text), so it cannot be told whether it limits the age of a record" % (policy_id, version))
    if kind != "freshness":
        return None
    value = policy.get("max_age_hours")
    try:
        limit = None if isinstance(value, bool) or not isinstance(value, (int, float)) else float(value)
    except OverflowError:
        limit = None
    if limit is None or limit != limit or limit < 0 or limit == float("inf"):
        raise ValueError("freshness policy %s %s states no limit in hours that can be read" % (policy_id, version))
    return limit


def event_time(record: dict) -> Optional[datetime]:
    """The business event time a record states, or None when it is not known, or not a time that can be compared exactly."""
    event = _object(_object(record.get("times")).get("event"))
    return parse_time(event.get("value")) if event.get("state") == "known" else None


def age_hours(record: dict, at: datetime) -> Optional[float]:
    """Hours between the record's business event time and `at`, or None if the event time is not known or lies after `at`.

    An event that has not happened by `at` gives no age: a negative age would read as fresher than fresh.
    """
    occurred = event_time(record)
    if occurred is None or occurred > at:
        return None
    return (at - occurred).total_seconds() / 3600.0


def evidence_refs(proposal: dict, grant: dict) -> List[dict]:
    refs = _list(_object(proposal.get("action")).get("evidence_references")) + _list(_object(grant.get("scope_binding")).get("evidence_constraints"))
    seen, out = set(), []
    for r in refs:
        r = _object(r)
        key = (repr(r.get("record_id")), repr(r.get("version")))   # repr: a reference that is not text must still be told apart, and cannot be hashed as it is
        if key not in seen:
            seen.add(key)
            out.append(r)
    return out


def _target_state(model: Model, entity: str, at: datetime) -> dict:
    """The latest recorded state of the target at or before `at`.

    An entry for the target whose time cannot be read cannot be placed before the attempt or after it: it could be the state that
    holds at the attempt, so the state at the attempt cannot be established, and nothing is returned. The older state is not used instead.
    """
    latest, latest_at = {}, None
    for item in map(_object, model.registry.target_states):
        if item.get("entity_id") != entity:
            continue
        seen = parse_time(item.get("at"))
        if seen is None:
            return {}
        if seen <= at and (latest_at is None or seen >= latest_at):
            latest, latest_at = _object(item.get("state")), seen
    return latest


def _target_permitted(target: dict, permitted: List[dict]) -> bool:
    """Exact match, or the explicit wildcard entity_id '*' for the same entity type (a convention of this reference check)."""
    return any(isinstance(p, dict) and (p == target or (p.get("entity_id") == "*" and p.get("entity_type") == target.get("entity_type"))) for p in permitted)


def _issued(grant: Instance) -> Optional[datetime]:
    return parse_time(_object(grant.data.get("identity_principals")).get("issuance_time"))


def grant_in_force(model: Model, grant_id: str, at: datetime, current: Optional[Instance] = None) -> Optional[Instance]:
    """The latest version of a grant that had been issued by `at`. A version with no known issuance time is not in force.

    `current` is the grant that is being evaluated: where a what-if has changed it (an override of its issuance time), its own version
    is read as it stands, and not as it is stored.
    """
    versions = [current if current is not None and g.version == current.version else g for g in model.versions("C06", grant_id)]
    issued = [g for g in versions if _issued(g) is not None and _issued(g) <= at]
    return issued[-1] if issued else None


def _window(limit: dict) -> Optional[Tuple[datetime, datetime]]:
    """The accounting window of a limit as (start, end), or None when it has no start or no end that can be read, or ends at or before its start."""
    window = _object(limit.get("accounting_window"))
    start, end = parse_time(window.get("start")), parse_time(window.get("end"))
    return None if start is None or end is None or end <= start else (start, end)


def _equal(held, wanted) -> bool:
    """Whether a value read from the target or from a record is the value a rule wants. true and false are not the numbers 1 and 0, at any depth
    (a value that is an object or a list is compared member by member)."""
    if isinstance(held, bool) or isinstance(wanted, bool):
        return held is wanted
    if isinstance(held, dict) and isinstance(wanted, dict):
        return held.keys() == wanted.keys() and all(_equal(held[key], wanted[key]) for key in held)
    if isinstance(held, list) and isinstance(wanted, list):
        return len(held) == len(wanted) and all(_equal(a, b) for a, b in zip(held, wanted))
    return held == wanted


def evaluate_commit(model: Model, proposal: Instance, grant: Instance, at: datetime, ledger: List[LedgerEntry]) -> Decision:
    """Recheck, at commit, everything an earlier approval cannot vouch for. Returns ALLOW only if every check holds.

    `at` is the attempt time. Only what was available and valid at `at` counts, and a required time that is missing or unknown blocks.
    """
    if at is None or at.tzinfo is None:
        raise ValueError("the attempt time must be a timezone-aware datetime")
    reasons: List[Reason] = []
    p, g = proposal.data, grant.data
    life, scope, action = _object(g.get("limits_lifecycle")), _object(g.get("scope_binding")), _object(p.get("action"))

    # 1. The grant itself is valid at the attempt, and a revocation observation made by then shows it unrevoked.
    # A missing part of the grant that holds a time is a time that is missing: it blocks, it does not raise.
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
    newest = grant_in_force(model, grant.id, at, current=grant)
    # Superseded means that a NEWER version is in force. When the version evaluated is itself not yet issued (GRANT_NOT_YET_VALID above), an older one is in force, and that is not a supersession.
    if newest is not None and _vn(newest.version) > _vn(grant.version):
        reasons.append(Reason("GRANT_SUPERSEDED", "grant version %s is in force; %s is no longer usable" % (newest.version, grant.version)))
    for other in model.versions("C06", grant.id):
        if other.version != grant.version and _issued(other) is None:
            reasons.append(Reason("GRANT_TIME_UNKNOWN", "grant version %s has no known issuance time, so it cannot be ruled out that it replaced %s before the attempt" % (other.version, grant.version)))

    # 2. The grant covers exactly this action. A part of the grant that is missing covers nothing.
    binding = _object(scope.get("binding"))
    if binding.get("binding_type") == "exact_proposal":
        ref = _object(binding.get("proposal_reference"))
        if (ref.get("id"), ref.get("version")) != (proposal.id, proposal.version):
            reasons.append(Reason("GRANT_NOT_BOUND", "approval is bound to %s %s, not to %s %s" % (ref.get("id"), ref.get("version"), proposal.id, proposal.version)))
    elif binding.get("binding_type") != "bounded_class":
        reasons.append(Reason("GRANT_NOT_BOUND", "the grant states no binding that this check knows (%r), so it cannot be shown to cover this action" % binding.get("binding_type")))
    action_kind, target = action.get("action_kind"), _object(action.get("exact_target"))
    if not isinstance(action_kind, str) or action_kind not in _list(scope.get("permitted_actions")):
        reasons.append(Reason("ACTION_NOT_PERMITTED", "action %s is outside the grant" % (action_kind,)))
    if not (isinstance(target.get("entity_type"), str) and isinstance(target.get("entity_id"), str)) or not _target_permitted(target, _list(scope.get("permitted_targets"))):
        reasons.append(Reason("TARGET_NOT_PERMITTED", "target %s is outside the grant" % (target.get("entity_id"),)))
    allowed_params = {x["name"]: x.get("data_type") for x in _list(scope.get("permitted_parameters")) if isinstance(x, dict) and isinstance(x.get("name"), str)}
    if not isinstance(action.get("typed_parameters"), list):
        reasons.append(Reason("PARAMETER_NOT_PERMITTED", "the proposal states no list of typed parameters (the field is missing or is not a list), so it cannot be shown that every parameter is permitted"))
    for param in map(_object, _list(action.get("typed_parameters"))):
        name, data_type = param.get("name"), param.get("data_type")
        if not isinstance(name, str) or not isinstance(data_type, str) or allowed_params.get(name) != data_type:
            reasons.append(Reason("PARAMETER_NOT_PERMITTED", "parameter %s (%s) is not permitted by the grant" % (name, data_type)))

    # 3. The evidence had been admitted by the attempt, was still current, and was fresh.
    # A proposal cites at least one record (C05), and a missing list is not an empty one: no evidence at all cannot support an action.
    if not _list(action.get("evidence_references")):
        reasons.append(Reason("EVIDENCE_UNRESOLVED", "the proposal cites no evidence (its list of evidence references is missing or empty), so nothing shows that it rests on a record"))
    if not isinstance(scope.get("evidence_constraints"), list):
        reasons.append(Reason("EVIDENCE_UNRESOLVED", "the grant states no list of evidence constraints (the field is missing or is not a list), so it cannot be shown which records it was given for"))
    for ref in evidence_refs(p, g):
        rec = _record(model, ref)
        if rec is None:
            reasons.append(Reason("EVIDENCE_UNRESOLVED", "evidence %s %s does not exist" % (ref.get("record_id"), ref.get("version"))))
            continue
        unavailable = availability_problem(rec, at)
        if unavailable is not None:
            reasons.append(unavailable)
            continue
        stale_or_gone = lifecycle_problem(rec, at)
        if stale_or_gone is not None:
            reasons.append(stale_or_gone)
        try:
            limit = freshness_max_age(model, rec.data)
        except ValueError as exc:
            reasons.append(Reason("EVIDENCE_STALE", "%s %s cannot be shown to be fresh: %s" % (rec.id, rec.version, exc)))
            continue
        if limit is not None:
            occurred, age = event_time(rec.data), age_hours(rec.data, at)
            if occurred is None:
                reasons.append(Reason("EVIDENCE_TIME_UNKNOWN", "the event time of %s %s is unknown, so its age under its freshness policy cannot be established" % (rec.id, rec.version)))
            elif age is None:
                reasons.append(Reason("EVIDENCE_TIME_UNKNOWN", "%s %s describes an event dated %s, which is after the attempt, so its age under its freshness policy cannot be established" % (
                    rec.id, rec.version, _object(_object(rec.data.get("times")).get("event")).get("value"))))
            elif age > limit:
                reasons.append(Reason("EVIDENCE_STALE", "%s %s is %.1f h old; policy allows %.0f h" % (rec.id, rec.version, age, limit)))

    # 4. Preconditions hold, judged only on evidence that was usable at the attempt. A rule that cannot be read is not satisfied.
    # A missing list is not an empty one. An empty list is allowed only with the approved justification that C05 requires for it.
    refs = evidence_refs(p, g)
    preconditions = action.get("preconditions")
    if not isinstance(preconditions, list):
        reasons.append(Reason("PRECONDITION_UNDEFINED", "the proposal states no list of preconditions (the field is missing or is not a list), so it cannot be shown that nothing needed checking"))
    elif not preconditions:
        why = _object(action.get("approved_empty_preconditions_justification"))
        approved_at = parse_time(why.get("approved_at"))
        if not all(isinstance(why.get(key), str) and why.get(key).strip() for key in ("reason", "approved_by")):
            reasons.append(Reason("PRECONDITION_UNDEFINED", "the proposal lists no preconditions and states no approved justification for that (a reason and who approved it), so it cannot be shown that nothing needed checking"))
        elif approved_at is None:
            reasons.append(Reason("PRECONDITION_UNDEFINED", "the justification for listing no preconditions has an approval time (approved_at) that is missing or unknown, so it cannot be shown to have been approved by the attempt"))
        elif approved_at > at:
            reasons.append(Reason("PRECONDITION_UNDEFINED", "the justification for listing no preconditions was approved at %s, after the attempt, so it could not vouch for it" % why["approved_at"]))
    for pre in map(_object, _list(preconditions)):
        condition_id = pre.get("condition_id")
        rule = _object(model.registry.preconditions.get(condition_id)) if isinstance(condition_id, str) else {}
        if not rule:
            reasons.append(Reason("PRECONDITION_UNDEFINED", "no rule is defined for %s" % condition_id))
            continue
        ok = False
        try:
            if rule.get("type") == "evidence_payload_equals":
                for ref in refs:
                    rec = _record(model, ref)
                    if rec and rec.id.startswith(rule["record_prefix"]) and usable_at(rec, at):
                        try:
                            ok = _equal(resolve_pointer(payload_of(rec.data), rule["pointer"]), rule["equals"])
                        except (KeyError, IndexError, TypeError, ValueError):
                            ok = False
            elif rule.get("type") == "evidence_fresh":
                for ref in refs:
                    rec = _record(model, ref)
                    if rec and rec.id.startswith(rule["record_prefix"]) and usable_at(rec, at):
                        age = age_hours(rec.data, at)
                        ok = age is not None and age <= float(rule["max_age_hours"])
            elif rule.get("type") == "target_state_equals":
                # A state that does not hold the key says nothing about it: a missing key is not a value (null) that a rule could ask for.
                state = _target_state(model, rule["entity_id"], at)
                ok = rule["key"] in state and _equal(state[rule["key"]], rule["equals"])
        except (KeyError, TypeError, ValueError, OverflowError, AttributeError):
            ok = False
        if not ok:
            reasons.append(Reason("PRECONDITION_FAILED", "%s is not satisfied: %s" % (condition_id, pre.get("condition"))))

    # 5. Per-action and cumulative limits, counting consumed and reserved capacity. A limit that cannot be read cannot be shown to hold.
    per_action, cumulative = life.get("per_action_limits"), life.get("cumulative_limits")
    if not isinstance(per_action, list):
        reasons.append(Reason("PER_ACTION_LIMIT", "the grant lists no per-action limits, so none can be checked"))
        per_action = []
    for limit in map(_object, per_action):
        units, cap = limit.get("units"), limit.get("quantity")
        if _window(limit) is None:
            reasons.append(Reason("GRANT_TIME_UNKNOWN", "the accounting window of the %s per-action limit has a start or an end that is missing, unknown or out of order, so the limit cannot be shown to apply as it was granted" % units))
        qty = action_quantity(p, units) if isinstance(units, str) else None
        if qty is None or not _is_quantity(cap):
            reasons.append(Reason("PER_ACTION_LIMIT", "the per-action limit in %s cannot be checked: the proposal states no readable amount in that unit (one number that is finite and not negative), or the limit states no readable unit or quantity" % units))
        elif _over(Fraction(0), qty, cap):
            reasons.append(Reason("PER_ACTION_LIMIT", "%s %s exceeds the per-action limit of %s %s" % (_fmt(qty), units, _fmt(cap), units)))
    reserve = None
    if not isinstance(ledger, list):
        reasons.append(Reason("CUMULATIVE_LIMIT", "the capacity already used is not given as a list of ledger entries, so it cannot be established"))
        ledger = []
    if not isinstance(cumulative, list):
        reasons.append(Reason("GRANT_TIME_UNKNOWN", "the grant lists no cumulative limits, so no accounting window can be read and the capacity already used cannot be established"))
        cumulative = []
    for limit in map(_object, cumulative):
        units, cap, scope_name = limit.get("units"), limit.get("quantity"), limit.get("accounting_scope")
        qty = action_quantity(p, units) if isinstance(units, str) else None
        window = _window(limit)
        if window is None:
            reasons.append(Reason("GRANT_TIME_UNKNOWN", "the accounting window of the %s limit has a start or an end that is missing, unknown or out of order, so the capacity already used in it cannot be established" % units))
            continue
        window_start, window_end = window
        if qty is None or not _is_quantity(cap) or not isinstance(scope_name, str):
            reasons.append(Reason("CUMULATIVE_LIMIT", "the cumulative limit in %s cannot be checked: the proposal states no readable amount in that unit (one number that is finite and not negative), or the limit states no readable unit, quantity or scope" % units))
            continue
        # Only what the ledger held by the attempt counts: an entry that starts after it is information from the future, whatever else it says.
        # An entry whose start cannot be read cannot be shown to be early, and an entry that counts and whose quantity cannot be read cannot be
        # shown to be small, so each blocks instead of being guessed.
        applicable = [e for e in ledger if not isinstance(e, LedgerEntry) or (e.grant_id == grant.id and e.accounting_scope == scope_name and e.units == units)]
        if not all(isinstance(e, LedgerEntry) and _start_readable(e) for e in applicable):
            reasons.append(Reason("CUMULATIVE_LIMIT", "a ledger entry for the %s limit has a start that cannot be read, so it cannot be shown to come before the attempt and the capacity already used in the window cannot be established" % units))
            continue
        counting = [e for e in applicable if e.start is None or (window_start <= e.start < window_end and e.start <= at)]
        if not all(_is_quantity(e.quantity) and e.quantity >= 0 for e in counting):
            reasons.append(Reason("CUMULATIVE_LIMIT", "a ledger entry that counts for the %s limit has a quantity that cannot be read, so the capacity already used in the window cannot be established" % units))
            continue
        used = _used(counting)
        if _over(used, qty, cap):
            reasons.append(Reason("CUMULATIVE_LIMIT", "%s already counted plus %s would exceed %s %s in the window" % (_fmt(float("inf") if used is None else used), _fmt(qty), _fmt(cap), units)))
        else:
            reserve = {"units": units, "quantity": qty, "counted_before": _plain(used)}
    allow = not reasons
    return Decision(allow, reasons, reserve if allow else None)


def _is_quantity(value) -> bool:
    """A quantity a limit can state: a number that is not true or false and not NaN."""
    return isinstance(value, (int, float)) and not isinstance(value, bool) and value == value


def _start_readable(entry: "LedgerEntry") -> bool:
    """A ledger entry can be placed in time only if its start is a time with a zone, or is None (unknown: it counts in every window)."""
    return entry.start is None or (isinstance(entry.start, datetime) and entry.start.tzinfo is not None)


def _fmt(x) -> str:
    """A number as the check compared it (as written, see `_exact`): an integer in full, any other with two decimals, worked out on the exact value and not on the
    nearest double of it (a double cannot hold the second decimal of 100000000000000.1). A sum that is a `Fraction` is shown the same way."""
    try:
        if isinstance(x, float) and not math.isfinite(x):
            return str(x)
        exact = x if isinstance(x, Fraction) else _exact(x)
        if exact.denominator == 1:
            return str(int(exact))
        cents = round(exact * 100)
        return "%s%d.%02d" % ("-" if cents < 0 else "", abs(cents) // 100, abs(cents) % 100)
    except (OverflowError, ValueError):
        return "a number too large to show"


#: The outcomes that close an attempt. A later ordinary version of the same receipt may repeat one of them and may not leave it.
TERMINAL_OUTCOMES = ("completed_verified", "not_executed_verified")


def _outcome_state(receipt: Instance):
    return _object(receipt.data.get("outcome")).get("state")


def regressive_receipt_versions(model: Model) -> List[Tuple[Instance, Instance]]:
    """(the version, the earlier version whose verified outcome it leaves) for each version of a receipt that goes back from a verified outcome.

    The versions of one receipt are read in the order of their numbers. The first version that is `completed_verified` or `not_executed_verified`
    closes the attempt: a later version may say the same, and one that says anything else (submitted, unknown, partial, or the other verified outcome) leaves it.
    What the unresolved states do among themselves is not judged here. No correction of a verified outcome is defined for these ordinary versions.
    """
    by_id: Dict[str, List[Instance]] = {}
    for rec in model.of("C07"):
        by_id.setdefault(rec.id, []).append(rec)
    found: List[Tuple[Instance, Instance]] = []
    for versions in by_id.values():
        closed: Optional[Instance] = None
        for rec in sorted(versions, key=lambda r: _vn(r.version)):
            if closed is None:
                closed = rec if _outcome_state(rec) in TERMINAL_OUTCOMES else None
            elif _outcome_state(rec) != _outcome_state(closed):
                found.append((rec, closed))
    return found


def receipt_known_at(receipt: dict, first_version: bool = False) -> Optional[datetime]:
    """When this version of a receipt became known.

    The first version of a receipt records the attempt itself, and an attempt holds its reservation from the moment it is submitted,
    so it is known from its submission time, even when the version that is stored also carries a later verification. A later
    version is known from its authoritative verification time, otherwise from its submission time.

    None when that time is missing or cannot be compared exactly: such a receipt is counted as already known (see the ledger).
    """
    ver = _object(_object(receipt.get("verification_recovery")).get("verification"))
    if ver.get("state") == "authoritatively_verified" and not first_version:
        return parse_time(ver.get("time"))
    return parse_time(_object(_object(receipt.get("outcome")).get("timestamps")).get("submitted"))


def attempt_receipt_ids(model: Model, proposal: Instance, grant: Instance, at: datetime) -> List[str]:
    """The receipts that record this very attempt: they cite this proposal and this grant, and the attempt was submitted at `at`.

    Replaying an attempt must not charge it against itself, so a replay leaves these out of the ledger and nothing else. Two receipts
    that record attempts of the same proposal under the same grant at the same instant leave the replay unable to tell which of them is
    its own, and the other one must count: it raises ValueError (a replay that guessed would free capacity another attempt holds).
    """
    found: List[str] = []
    for rec in model.of("C07"):
        binding = _object(rec.data.get("identity_binding"))
        p_ref, g_ref = _object(binding.get("proposal_reference")), _object(binding.get("grant_reference"))
        submitted = parse_time(_object(_object(rec.data.get("outcome")).get("timestamps")).get("submitted"))
        if (p_ref.get("id"), p_ref.get("version")) == (proposal.id, proposal.version) and (g_ref.get("id"), g_ref.get("version")) == (grant.id, grant.version) \
                and submitted is not None and submitted == at and rec.id not in found:
            found.append(rec.id)
    if len(found) > 1:
        raise ValueError("%s receipts (%s) record an attempt of %s %s under %s %s at the same moment, so a replay cannot tell which one is its own and which one must count "
                         "against the limit. Give each attempt its own time, or correct the receipts" % (len(found), ", ".join(found), proposal.id, proposal.version, grant.id, grant.version))
    return found


def _capacity_held(receipt: dict, before: datetime) -> Optional[str]:
    """How this version of a receipt holds capacity at `before`: "consumed", "reserved", or None when it holds none.

    Capacity comes back only through an authoritative verification that is already available at `before`, in whichever version of
    the receipt it is stated: a verification whose time cannot be read, or lies after `before`, gives nothing back. A rejection by
    the gateway never reserved any. A cancellation, or a failure before any effect, keeps its reservation until the verification
    that shows no effect, so a version that already carries a later verification still holds it until then. An outcome that is
    not yet known to be complete or to have had no effect holds capacity as reserved.
    """
    outcome = _object(receipt.get("outcome"))
    state = outcome.get("state")
    verification = _object(_object(receipt.get("verification_recovery")).get("verification"))
    verified_at = parse_time(verification.get("time")) if verification.get("state") == "authoritatively_verified" else None
    pending = verified_at is None or verified_at > before
    if state == "not_executed_verified":
        if outcome.get("no_effect_basis") == "rejection":
            return None
        return "reserved" if pending else None
    if state == "completed_verified":
        return "reserved" if pending else "consumed"
    return "reserved"


def ledger_from_receipts(model: Model, before: datetime, exclude_receipt_id: str = "", exclude_receipt_ids: Iterable[str] = ()) -> List[LedgerEntry]:
    """Capacity already used or held at `before`: for each attempt, the latest receipt version already known then.

    A receipt known at exactly `before` counts, like any time equal to the attempt: it was available. The only receipt that
    does not count is the attempt's own, which a replay names (`exclude_receipt_id`, or `attempt_receipt_ids` for several): an
    attempt must not be charged against itself. An attempt is known from its submission, so a receipt that already carries its
    verification still holds its reservation until that verification is available (see `_capacity_held`). A receipt whose time
    is unknown cannot be shown to come after `before`, so it is counted: capacity is never freed by a time that cannot be read.

    A version that goes back from a verified outcome of an earlier version (see `regressive_receipt_versions`) is not the latest state of the attempt:
    the replay keeps the verified outcome, so that a completed attempt is never read as unresolved again. The validator reports the history (`ACC005`).
    """
    excluded = set(exclude_receipt_ids) | ({exclude_receipt_id} if exclude_receipt_id else set())
    first: Dict[str, int] = {}
    for rec in model.of("C07"):
        first[rec.id] = min(first.get(rec.id, _vn(rec.version)), _vn(rec.version))
    regressive = {later.key for later, _ in regressive_receipt_versions(model)}
    latest: Dict[str, Instance] = {}
    for rec in model.of("C07"):
        known = receipt_known_at(rec.data, first_version=_vn(rec.version) == first[rec.id])
        if rec.id in excluded or rec.key in regressive or (known is not None and known > before):
            continue
        cur = latest.get(rec.id)
        if cur is None or _vn(rec.version) > _vn(cur.version):
            latest[rec.id] = rec
    entries: List[LedgerEntry] = []
    for rec in latest.values():
        d = rec.data
        submitted = parse_time(_object(_object(d.get("outcome")).get("timestamps")).get("submitted"))
        binding = _object(d.get("identity_binding"))
        grant_ref, proposal_ref = _object(binding.get("grant_reference")), _object(binding.get("proposal_reference"))
        grant = model.get("C06", grant_ref.get("id"), grant_ref.get("version")) if isinstance(grant_ref.get("id"), str) and isinstance(grant_ref.get("version"), str) else None
        proposal = model.get("C05", proposal_ref.get("id"), proposal_ref.get("version")) if isinstance(proposal_ref.get("id"), str) and isinstance(proposal_ref.get("version"), str) else None
        if grant is None or proposal is None:
            continue
        held = _capacity_held(d, before=before)
        if held is None:
            continue
        counted = set()
        for limit in map(_object, _list(_object(grant.data.get("limits_lifecycle")).get("cumulative_limits"))):
            scope = limit.get("accounting_scope")
            if not isinstance(scope, str) or not isinstance(limit.get("units"), str):
                continue
            # One entry for each attempt, scope and unit, however many windows the grant states for them: every window is applied to the entry
            # when its limit is evaluated, and a second entry would count the same attempt twice in each of them.
            if (scope, limit["units"]) in counted:
                continue
            counted.add((scope, limit["units"]))
            # An attempt whose amount cannot be read cannot be shown to have used less than everything: it is counted without limit.
            qty = action_quantity(proposal.data, limit["units"])
            entries.append(LedgerEntry(grant.id, scope, limit["units"], float("inf") if qty is None else qty, held, submitted, rec.id))
    return entries
