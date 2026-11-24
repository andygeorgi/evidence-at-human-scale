#!/usr/bin/env python3
"""Generate the synthetic example data (contract instances, registry and raw exports) from one scenario definition.

The committed files under examples/ are the source of truth for readers; this script exists so that maintainers
can regenerate them consistently and so that CI can confirm the committed files match the definition.

    python scripts/build_example_data.py            # rewrite examples/
    python scripts/build_example_data.py --check    # fail if committed files differ from a fresh build

Everything here is invented. No name, amount, date or identifier refers to a real person, supplier or system.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from eahs import REPO_ROOT  # noqa: E402

EXAMPLES = REPO_ROOT / "examples"
TENANT = "tenant:calder-works"
SV = "1"

# ----------------------------------------------------------------------------- timeline (UTC, 2026-11-23 unless noted)
T_GR1_EVENT = "2026-11-18T14:05:00Z"
T_INV_EVENT = "2026-11-23T07:30:00Z"
T_PO_EVENT = "2026-11-10T09:00:00Z"
T_SCR1_EVENT = "2026-11-21T08:00:00Z"
T_DUP_EVENT = "2026-11-23T09:50:00Z"
T_MON_EVENT = "2026-11-23T09:58:00Z"
T_ASOF1 = "2026-11-23T10:00:00Z"
T_HOLD_SUBMIT = "2026-11-23T10:03:00Z"
T_HOLD_OBS = "2026-11-23T10:03:20Z"
T_APPR_A = "2026-11-23T10:40:00Z"
T_CHANGE = "2026-11-23T14:30:00Z"
T_SCR2_EVENT = "2026-11-23T13:30:00Z"
T_GR2_ADMIT = "2026-11-23T13:40:00Z"
T_INVALIDATE = "2026-11-23T13:45:00Z"
T_ASOF2 = "2026-11-23T14:10:00Z"
T_APPR_B = "2026-11-23T15:20:00Z"
T_RUN_A = "2026-11-23T16:00:00Z"
T_RUN_B = "2026-11-23T16:00:05Z"
T_BANK = "2026-11-23T16:07:00Z"
T_RECON = "2026-11-23T16:20:00Z"
T_REVIEW_1 = "2026-11-23T10:35:00Z"   # the controller reviews packet v1, before the first approval at 10:40
T_REVIEW_2 = "2026-11-23T15:10:00Z"   # the controller reviews packet v2, before the second approval at 15:20

# ----------------------------------------------------------------------------- people and permissions
ANALYST = "person:ap-analyst-02"        # the requestor: asks the assistant for a packet and reads it
CONTROLLER = "person:ap-controller-01"  # holds role:ap-controller: the Decision Owner and the approver
PERMISSION_LIMIT_ID = "AUTHZ-READ-LIMIT-0417"      # may be disclosed as a coverage limitation, in these words only
PERMISSION_WITHHELD_ID = "AUTHZ-READ-WITHHELD-0417"  # existence may not be disclosed: no output mentions it
COVERAGE_LIMIT_WORDING = "Coverage is limited by access permissions; no protected source identity or content is disclosed."
# A time that was not recorded, written the way the contracts write a legitimately unknown time.
UNKNOWN_TIME = {"state": "unknown", "reason": "The producing system did not record this time."}


# ----------------------------------------------------------------------------- small constructors
def known(v):
    return {"state": "known", "value": v}


def na(reason):
    return {"state": "not_applicable", "reason": reason}


def unk(reason):
    return {"state": "unknown", "reason": reason}


def ent(kind, ident):
    return {"entity_type": kind, "entity_id": ident}


def pol(pid, v="v1"):
    return {"policy_id": pid, "version": v}


def rref(rid, v="v1"):
    return {"record_id": rid, "version": v}


def cref(contract, ident, v):
    return {"contract_id": contract, "id": ident, "version": v}


INV_ENT, SUP_ENT = ent("invoice", "INV-2026-0417"), ent("supplier", "S-1042")
SCOPE_NA_JURISDICTION = na("Internal accounts-payable review; no external jurisdiction asserted.")


def scope(task, units=None, interp="Statement of a source system or analysis as recorded; not independently verified."):
    return {
        "entity_references": [INV_ENT, SUP_ENT],
        "task": task,
        "jurisdiction": SCOPE_NA_JURISDICTION,
        "units": known(units) if units else na("No unit applies to this statement."),
        "interpretation": known(interp),
    }


TASK = "Decide whether to release payment of invoice INV-2026-0417 (supplier S-1042)"
FRESH = {"POL-FRESH-SCREEN": 24.0, "POL-FRESH-RECORDS": 720.0, "POL-FRESH-REFERENCE": 8760.0}


def hours_between(a, b):
    from eahs.gateway import ts
    return (ts(b) - ts(a)).total_seconds() / 3600.0


def freshness(policy_id, event, evaluated_at):
    age = hours_between(event, evaluated_at)
    ok = age <= FRESH[policy_id]
    return {
        "policy_reference": pol(policy_id),
        "evaluated_at": evaluated_at,
        "state": "within_policy" if ok else "fails_policy",
        "basis": "Record is %.1f h old at evaluation; policy allows %.0f h." % (age, FRESH[policy_id]),
    }


def src(source_id, locator, version):
    return {"source_id": source_id, "record_locator": locator, "original_version": version}


def method(source_id, producer_id, rule=None, model=None, prompt=None, tool=None, analytic=None):
    reason = "Not applicable to this producer."
    pick = lambda x: known(x) if x else na(reason)  # noqa: E731
    return {
        "source_id": source_id, "producer_id": producer_id,
        "rule_version": pick(rule), "model_version": pick(model), "prompt_version": pick(prompt),
        "tool_version": pick(tool), "analytical_version": pick(analytic),
    }


def content_hash(content):
    return "sha256:" + hashlib.sha256(json.dumps(content, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def claims(*items):
    return {"content_type": "claims", "claims": [{"claim_id": cid, "text": text, "supporting_references": sup} for cid, text, sup in items]}


def payload(schema_id, value):
    return {"content_type": "typed_payload", "payload": {"data_type": "object", "payload_schema_reference": rref(schema_id), "value": value}}


def support(rec, claim_id=None, pointer=None):
    """A supporting reference to a record in this scenario (claim_reference or payload_reference)."""
    base = {
        "record_id": rec["identity_schema"]["record_id"], "version": rec["identity_schema"]["version"],
        "original_locator": rec["original_source"], "scope": rec["scope"],
        "evidence_kind": rec["identity_schema"]["kind"],
    }
    if pointer is not None:
        return dict(base, reference_type="payload_reference", payload_location=pointer)
    return dict(base, reference_type="claim_reference", claim_id=claim_id)


def evidence(rid, v, kind, producer, content, *, event, ingestion, source, scope_, method_, task=TASK, freshness_policy="POL-FRESH-RECORDS",
             parents=(), relationships=(), uncertainty=("unquantified", "Source assertion; accuracy is not independently established."),
             limits=(), validation=(), lifecycle=None, integrity=None, retrieval=None, coverage="Single record; no claim about other records."):
    lc = lifecycle or {"state": "current", "effective_time": ingestion, "reason": "Initial admitted version."}
    return {
        "contract_id": "C02", "schema_version": SV,
        "identity_schema": {"record_id": rid, "version": v, "kind": kind},
        "producer_admission": {
            "producer_id": producer, "registry_version": "producer-registry-v1",
            "permitted_kind_reference": rref("registered-kind-" + kind),
            "admission_status": "admitted", "admission_time": ingestion,
        },
        "content": content, "scope": scope_, "original_source": source, "method": method_,
        "times": {
            "event": known(event), "effective": known(event), "source_update": known(event), "ingestion": ingestion,
            "retrieval": known(retrieval or ingestion), "clock_basis": "UTC, source-system clock",
            "freshness": freshness(freshness_policy, event, ingestion),
        },
        "lineage": {"parent_references": [rref(p[0], p[1]) for p in parents], "typed_relationships": list(relationships)},
        "coverage_uncertainty": {"coverage_statement": coverage, "uncertainty": {"state": uncertainty[0].replace("-", "_"), "basis": uncertainty[1]}, "limitations": list(limits)},
        "validation": list(validation),
        "disclosure_permissions": {
            "tenant": TENANT, "classification": "synthetic-internal", "purpose": "Accounts-payable payment-release review",
            "disclosure_restrictions": [], "permission_policy_references": [pol("POL-AP-READ")],
        },
        "lifecycle": lc,
        "integrity": integrity or {"state": "absent", "reason": "The synthetic source supplies no hash or signature."},
    }


def hashed(content):
    return {"state": "present", "hash": content_hash(content), "algorithm": "sha-256", "origin_metadata": "Computed over the admitted content when the record was ingested."}


# ----------------------------------------------------------------------------- the registry (external references and domain rules)
def build_registry():
    permitted = {
        "producer:erp-invoices": ["source_record_assertion"], "producer:erp-purchasing": ["source_record_assertion"],
        "producer:wms-receiving": ["source_record_assertion"], "producer:policy-library": ["source_record_assertion"],
        "producer:service-monitor": ["source_record_assertion"], "producer:erp-payments": ["source_record_assertion"],
        "producer:bank-api": ["source_record_assertion"], "producer:rules-engine": ["deterministic_finding"],
        "producer:screening-service": ["deterministic_finding"], "producer:ledger-check": ["deterministic_finding"],
        "producer:agent-a": ["model_inference"], "producer:agent-b": ["model_inference"],
        "producer:analytics-ap": ["analytical_result"], "producer:change-control": ["decision_record"],
        "producer:payment-gateway": ["execution_record"],
    }
    ext = {
        "AUTHZ-READ-CTX-0417@v1": "Read-scope decision for the first context (principal, purpose, scope).",
        "AUTHZ-READ-CTX-0417@v2": "Read-scope decision for the revised context.",
        PERMISSION_LIMIT_ID + "@v1": "Permission decision: part of the requested scope is not readable by this principal; a coverage limitation may be disclosed.",
        PERMISSION_WITHHELD_ID + "@v1": "Permission decision: a source that this principal may not read, and whose existence may not be disclosed to them.",
        "BASIS-AP-POLICY-V3@v1": "Authority basis: accounts-payable policy v3 delegates holds to the AP team.",
        "BASIS-AP-CONTROLLER-APPROVAL@v1": "Authority basis: the AP controller may approve payment releases.",
        "REVCHK-GRT-CLASS-HOLD@v1": "Latest revocation check for the hold grant.",
        "REVCHK-GRT-APPR-0417-A@v1": "Latest revocation check for the first exact approval (revoked at 13:45).",
        "ACCT-CHARGE-HOLD-0417@v1": "Allowance charge recorded for the hold.",
        "ACCT-CHARGE-REL-0417-B@v1": "Allowance charge recorded for the second release.",
        "REVCHK-GRT-CLASS-LOWVAL@v1": "Latest revocation check for the low-value release grant v1.",
        "REVCHK-GRT-CLASS-LOWVAL@v2": "Latest revocation check for the low-value release grant v2.",
        "REVCHK-GRT-APPR-0417-B@v1": "Latest revocation check for the second exact approval.",
        "ACCT-AP-HOLDS@v1": "Shared accounting ledger for holds.",
        "ACCT-AP-PAYMENTS@v1": "Shared accounting ledger for payment releases.",
        "SCHEMA-M3W-RESULT@v1": "Payload schema of a three-way-match result.",
        "ACCEPT-AP-BANK-INTERFACE@v1": "Domain owner's acceptance of the weaker guarantees at the bank interface.",
    }
    for kind in ("source_record_assertion", "deterministic_finding", "analytical_result", "model_inference", "decision_record", "execution_record"):
        ext["registered-kind-%s@v1" % kind] = "Registered evidence kind %s." % kind
    return {
        "synthetic": True,
        "description": "Domain registry for the synthetic supplier-payment scenario: registered producers, external references that the "
                       "contracts name but do not define, domain policies, commit-time precondition rules, and the target system's state. "
                       "All content is invented.",
        "producers": {k: {"permitted_kinds": v} for k, v in sorted(permitted.items())},
        "external_records": dict(sorted(ext.items())),
        "policies": {
            "POL-AP-READ": {"v1": {"type": "read_purpose", "summary": "Accounts-payable staff may read records of an invoice under review."}},
            "POL-AP-PAY": {"v3": {"type": "payment_policy", "summary": "Payment release needs a passing three-way match, current screening and an approval or a bounded grant."}},
            "POL-FRESH-SCREEN": {"v1": {"type": "freshness", "max_age_hours": 24, "summary": "Supplier screening must be at most 24 hours old when payment is released."}},
            "POL-FRESH-RECORDS": {"v1": {"type": "freshness", "max_age_hours": 720, "summary": "Ordinary source records are fresh for 30 days."}},
            "POL-FRESH-REFERENCE": {"v1": {"type": "freshness", "max_age_hours": 8760, "summary": "Policy and reference documents are fresh for one year."}},
            "POL-RESERVATION": {"v1": {"type": "reservation", "summary": "A reservation is held until authoritative reconciliation."}},
            "POL-RECOVERY-AP": {"v1": {"type": "recovery", "summary": "Unknown or partial outcomes go to AP reconciliation."}},
            "POL-CONFIRMED-EFFECT": {"v1": {"type": "confirmed_effect", "summary": "Allowance is restored only on authoritative reconciliation."}},
        },
        "preconditions": {
            "PRE-INVOICE-OPEN": {"type": "target_state_equals", "entity_id": "INV-2026-0417", "key": "status", "equals": "open"},
            "PRE-INVOICE-HELD": {"type": "target_state_equals", "entity_id": "INV-2026-0417", "key": "status", "equals": "held"},
            "PRE-MATCH-PASS": {"type": "evidence_payload_equals", "record_prefix": "M3W-", "pointer": "/result", "equals": "PASS"},
            "PRE-SCREEN-FRESH": {"type": "evidence_fresh", "record_prefix": "SCR-", "max_age_hours": 24},
        },
        "relationship_types": ["contradiction", "supersession", "validation", "invalidation"],
        "protected_terms": ["bank-detail", "bank detail", "BA-S1042", "bank account", "investigation file", "vendor master", "vendor-master"],
        "permission_decisions": {
            PERMISSION_LIMIT_ID + "@v1": {
                "principal": ANALYST, "read_allowed": False, "disclose_existence_allowed": True, "permitted_disclosure": COVERAGE_LIMIT_WORDING,
                "summary": "Part of the requested scope is not readable by this principal. The policy lets an output say that coverage is limited by permissions, in the words given here, and nothing else about it.",
            },
            PERMISSION_WITHHELD_ID + "@v1": {
                "principal": ANALYST, "read_allowed": False, "disclose_existence_allowed": False, "permitted_disclosure": "",
                "summary": "An investigation file that this principal may not read, and whose existence may not be disclosed to them. No output carries an entry, a count, a state or an age for it; it adds nothing to the coverage statement that every output carries.",
            },
        },
        "accountability": {
            "policy_reference": "POL-AP-PAY@v3",
            "summary": "Four roles stay distinct. The AP controller is both the Decision Owner and the approver, and the policy says so; the requestor holds neither role for their own request.",
            "roles": {
                "requestor": {"principals": [ANALYST], "meaning": "Asks the assistant for a packet and reads it. Requests the evaluation; neither reviews on the owner's behalf nor approves."},
                "decision_owner": {"role": "role:ap-controller", "holders": [CONTROLLER], "meaning": "Reviews the evidence and owns the release decision (the accountable reviewer)."},
                "approver": {"role": "role:ap-controller", "holders": [CONTROLLER], "meaning": "Issues the exact approval of one proposal version."},
                "executor": {"principals": ["workload:payment-executor"], "meaning": "Performs the authorized action after the commit check."},
            },
            "may_hold_together": [["decision_owner", "approver"]],
            "review_log": [
                {"packet": "PKT-0417 v1", "action": "reviewed", "actor": CONTROLLER, "time": T_REVIEW_1},
                {"packet": "PKT-0417 v2", "action": "reviewed", "actor": CONTROLLER, "time": T_REVIEW_2},
            ],
        },
        "target_states": [
            {"entity_id": "INV-2026-0417", "at": T_INV_EVENT, "state": {"status": "open"}},
            {"entity_id": "INV-2026-0417", "at": T_HOLD_OBS, "state": {"status": "held"}},
            {"entity_id": "INV-2026-0417", "at": T_RECON, "state": {"status": "paid"}},
        ],
    }


# ----------------------------------------------------------------------------- C02 evidence records
class Scenario:
    def __init__(self):
        self.files = []          # (folder, filename, data)
        self.rec = {}            # (id, version) -> C02 dict

    def add(self, folder, data, name=None):
        c = data["contract_id"].lower()
        ident = {
            "C01": lambda d: (d["identity_principal"]["context_id"], d["identity_principal"]["version"]),
            "C02": lambda d: (d["identity_schema"]["record_id"], d["identity_schema"]["version"]),
            "C03": lambda d: (d["identity_scope"]["selection_id"], d["identity_scope"]["version"]),
            "C04": lambda d: (d["decision_context_as_of"]["packet_id"], d["decision_context_as_of"]["version"]),
            "C05": lambda d: (d["identity_binding"]["proposal_id"], d["identity_binding"]["version"]),
            "C06": lambda d: (d["identity_principals"]["grant_id"], d["identity_principals"]["version"]),
            "C07": lambda d: (d["identity_binding"]["receipt_id"], d["identity_binding"]["version"]),
        }[data["contract_id"]](data)
        if data["contract_id"] == "C02":
            self.rec[ident] = data
        self.files.append((folder, name or "%s-%s-%s.json" % (c, ident[0], ident[1]), data))
        return data


def build_evidence(S: Scenario):
    F1, F3, F4, F7, F8, F9, F11, F12 = ("01-source-records", "03-lineage-and-common-origin", "04-selection-and-missingness",
                                        "07-authority-and-delegation", "08-blocked-action", "09-unknown-outcome", "11-late-correction", "12-controlled-change")
    inv = S.add(F1, evidence(
        "INV-2026-0417", "v1", "source_record_assertion", "producer:erp-invoices",
        claims(("c1", "Invoice INV-2026-0417 from supplier S-1042 (supplier invoice FC-88231, dated 2026-11-22) states 100 units delivered at EUR 184.00 per unit, total EUR 18,400.00, payable by 2026-11-30.", [])),
        event=T_INV_EVENT, ingestion="2026-11-23T07:31:00Z", source=src("src:erp-invoices", "erp:invoice/FC-88231", "rev-3"),
        scope_=scope(TASK, "EUR"), method_=method("src:erp-invoices", "producer:erp-invoices", tool="erp-export-4.2")))
    po = S.add(F1, evidence(
        "PO-77231", "v1", "source_record_assertion", "producer:erp-purchasing",
        claims(("c1", "Purchase order PO-77231 authorizes up to 100 units at EUR 184.00 per unit, total EUR 18,400.00.", [])),
        event=T_PO_EVENT, ingestion="2026-11-10T09:01:00Z", source=src("src:erp-purchasing", "erp:po/77231", "rev-1"),
        scope_=scope(TASK, "EUR"), method_=method("src:erp-purchasing", "producer:erp-purchasing", tool="erp-export-4.2")))
    S.add(F1, evidence(
        "AP-POLICY-4", "v1", "source_record_assertion", "producer:policy-library",
        claims(("c1", "Policy AP-4: an invoice with an open quantity or price discrepancy may be placed on payment hold by the accounts-payable team; releasing it requires a passing three-way match.", [])),
        event="2026-01-15T09:00:00Z", ingestion="2026-01-15T09:05:00Z", source=src("src:policy-library", "policy:AP-4", "2026.1"),
        scope_=scope("Accounts-payable policy that bounds the hold and release actions"), method_=method("src:policy-library", "producer:policy-library", tool="policy-portal-1.0"),
        freshness_policy="POL-FRESH-REFERENCE", coverage="Policy text as published; not a statement about how it is applied."))
    gr1_val = [{"validation_id": "V-GR-5521-01", "version": "v1", "target": rref("GR-5521", "v1"), "method": "Pallet count re-scanned at the dock",
                "actor": "person:warehouse-supervisor-03", "time": "2026-11-18T14:20:00Z", "scope": "Pallet P-1 only (60 units)",
                "outcome": "count_confirmed", "limitations": ["Does not validate any later delivery or the invoice."]}]
    gr1 = S.add(F1, evidence(
        "GR-5521", "v1", "source_record_assertion", "producer:wms-receiving",
        claims(("c1", "Goods receipt GR-5521 records 60 units received on 2026-11-18.", [])),
        event=T_GR1_EVENT, ingestion="2026-11-18T14:06:00Z", source=src("src:wms-receiving", "wms:receipt/5521", "rev-1"),
        scope_=scope(TASK, "units"), method_=method("src:wms-receiving", "producer:wms-receiving", tool="wms-scan-2.9"), validation=gr1_val,
        lifecycle={"state": "superseded", "effective_time": T_GR2_ADMIT, "reason": "Corrected by a later scan of the second delivery.", "replacement_reference": rref("GR-5521", "v2")}))
    # --- lineage: deterministic finding and two summaries sharing one root
    m3w1_payload = {"rule": "M3W", "rule_version": "2.0", "invoice_id": "INV-2026-0417", "quantity_invoiced": 100,
                    "quantity_received": 60, "tolerance_pct": 2, "variance_pct": 40.0, "result": "FAIL"}
    m3w_val = [{"validation_id": "V-M3W-0417-01", "version": "v1", "target": rref("M3W-0417", "v1"), "method": "Independent recomputation of the arithmetic",
                "actor": "person:ap-analyst-02", "time": "2026-11-23T09:40:00Z", "scope": "Arithmetic of the variance only; not the correctness of the input records",
                "outcome": "arithmetic_confirmed", "limitations": ["Does not validate the goods receipt or the invoice."]}]
    S.add(F3, evidence(
        "M3W-0417", "v1", "deterministic_finding", "producer:rules-engine", payload("SCHEMA-M3W-RESULT", m3w1_payload),
        event="2026-11-23T09:35:00Z", ingestion="2026-11-23T09:36:00Z", source=src("src:rules-engine", "rules:m3w/INV-2026-0417", "run-1"),
        scope_=scope(TASK, "units"), method_=method("src:rules-engine", "producer:rules-engine", rule="M3W-2.0", tool="rules-engine-7.1"),
        parents=[("INV-2026-0417", "v1"), ("PO-77231", "v1"), ("GR-5521", "v1")], validation=m3w_val,
        uncertainty=("rule-output", "Reports the declared rule over the stated inputs; the inputs are not independently verified."),
        lifecycle={"state": "superseded", "effective_time": "2026-11-23T13:51:00Z", "reason": "Its input GR-5521 v1 was superseded; recomputed as v2, admitted at 13:51.", "replacement_reference": rref("M3W-0417", "v2")},
        coverage="One invoice; rule M3W 2.0 with a 2% quantity tolerance."))
    sum_a = S.add(F3, evidence(
        "SUM-A-0417", "v1", "model_inference", "producer:agent-a",
        claims(("c1", "The goods receipt is probably incomplete: the 40 missing units were probably delivered on a later date and not yet scanned.", [support(gr1, "c1")])),
        event="2026-11-23T09:41:00Z", ingestion="2026-11-23T09:42:00Z", source=src("src:agent-a", "agent:summary/A/INV-2026-0417", "run-1"),
        scope_=scope(TASK, interp="Interpretation produced by a model; not a source assertion."),
        method_=method("src:agent-a", "producer:agent-a", model="model-x-2026-09", prompt="prompt-summary-3"),
        parents=[("GR-5521", "v1")], uncertainty=("model-generated", "Interpretation produced by a model; not verified against any source."),
        limits=["Rests on goods receipt GR-5521 v1 alone."],
        lifecycle={"state": "withdrawn", "effective_time": T_INVALIDATE, "reason": "Its basis GR-5521 v1 was superseded."}))
    sum_b = S.add(F3, evidence(
        "SUM-B-0417", "v1", "model_inference", "producer:agent-b",
        claims(("c1", "The quantity difference is probably a receiving delay; the invoice quantity is consistent with the purchase order.", [support(gr1, "c1")])),
        event="2026-11-23T09:43:00Z", ingestion="2026-11-23T09:44:00Z", source=src("src:agent-b", "agent:summary/B/INV-2026-0417", "run-1"),
        scope_=scope(TASK, interp="Interpretation produced by a model; not a source assertion."),
        method_=method("src:agent-b", "producer:agent-b", model="model-y-2026-08", prompt="prompt-summary-3"),
        parents=[("GR-5521", "v1")], uncertainty=("model-generated", "Interpretation produced by a model; not verified against any source."),
        limits=["Rests on goods receipt GR-5521 v1 alone."],
        lifecycle={"state": "withdrawn", "effective_time": T_INVALIDATE, "reason": "Its basis GR-5521 v1 was superseded."}))
    # --- supporting observations for the selection
    scr1 = S.add(F4, evidence(
        "SCR-S1042", "v1", "deterministic_finding", "producer:screening-service",
        claims(("c1", "Supplier S-1042 was screened against the sanctions and watch lists on 2026-11-21: no match.", [])),
        event=T_SCR1_EVENT, ingestion="2026-11-21T08:01:00Z", source=src("src:screening", "screening:S-1042/2026-11-21", "run-88"),
        scope_=scope("Supplier screening for payment release", interp="Result of a screening run on the stated date."),
        method_=method("src:screening", "producer:screening-service", rule="SCREEN-LISTS-2026-11-21", tool="screening-svc-3.4"),
        freshness_policy="POL-FRESH-SCREEN", uncertainty=("rule-output", "Reports the screening run as executed on its date."),
        lifecycle={"state": "superseded", "effective_time": T_SCR2_EVENT, "reason": "Re-screened on 2026-11-23.", "replacement_reference": rref("SCR-S1042", "v2")}))
    S.add(F4, evidence(
        "DUP-0417", "v1", "deterministic_finding", "producer:ledger-check",
        claims(("c1", "No invoice with supplier S-1042, number FC-88231 and amount EUR 18,400.00 exists in the ledger between 2025-11-24 and 2026-11-23 (exact match).", [])),
        event=T_DUP_EVENT, ingestion="2026-11-23T09:51:00Z", source=src("src:erp-ledger", "ledger:dupcheck/FC-88231", "run-1"),
        scope_=scope("Duplicate-invoice check", "EUR", "Exact match on supplier, invoice number and amount within the stated window."),
        method_=method("src:erp-ledger", "producer:ledger-check", rule="DUPCHECK-EXACT-1.0", tool="ledger-query-2.2"),
        uncertainty=("rule-output", "Exact-match rule; near-duplicates are out of scope."), coverage="Complete for the declared window and the exact-match rule."))
    S.add(F4, evidence(
        "MON-TREASURY-0001", "v1", "source_record_assertion", "producer:service-monitor",
        claims(("c1", "The treasury cash-position service returned HTTP 503 at 2026-11-23T09:58:00Z and did not recover during the retrieval window.", [])),
        event=T_MON_EVENT, ingestion="2026-11-23T09:59:00Z", source=src("src:service-monitor", "monitor:incident/TRS-0001", "rev-1"),
        scope_=scope("Availability of the treasury cash-position service", interp="Monitor observation of a dependency failure."),
        method_=method("src:service-monitor", "producer:service-monitor", tool="monitor-5.0")))
    S.add(F3, evidence(
        "ANL-S1042-OTD", "v1", "analytical_result", "producer:analytics-ap",
        claims(("c1", "Supplier S-1042 delivered on or before the promised date in 23 of 25 deliveries over the last 12 months (92%).", [])),
        event="2026-11-23T09:30:00Z", ingestion="2026-11-23T09:31:00Z", source=src("src:analytics-ap", "analytics:otd/S-1042", "run-12"),
        scope_=scope("Supplier delivery reliability", interp="Share of deliveries received by the promised date over 12 months."),
        method_=method("src:analytics-ap", "producer:analytics-ap", analytic="OTD-1.1", tool="analytics-9.0"),
        uncertainty=("small-sample", "n=25 deliveries; the rate is indicative only."), limits=["Counts only deliveries with a promised date."]))
    # --- late correction
    gr2_content = claims(("c1", "Goods receipt GR-5521 (corrected) records 100 units received: 60 on 2026-11-18 and 40 on 2026-11-20, scanned on 2026-11-23.", []))
    S.add(F11, evidence(
        "GR-5521", "v2", "source_record_assertion", "producer:wms-receiving", gr2_content,
        event="2026-11-20T09:30:00Z", ingestion=T_GR2_ADMIT, source=src("src:wms-receiving", "wms:receipt/5521", "rev-2"),
        scope_=scope(TASK, "units"), method_=method("src:wms-receiving", "producer:wms-receiving", tool="wms-scan-2.9"),
        relationships=[
            {"from": rref("GR-5521", "v2"), "to": rref("GR-5521", "v1"), "relationship_type": "supersession", "asserted_by": "person:warehouse-supervisor-03"},
            {"from": rref("GR-5521", "v2"), "to": rref("M3W-0417", "v1"), "relationship_type": "invalidation", "asserted_by": "workload:lineage-service"},
            {"from": rref("GR-5521", "v2"), "to": rref("SUM-A-0417", "v1"), "relationship_type": "invalidation", "asserted_by": "workload:lineage-service"},
            {"from": rref("GR-5521", "v2"), "to": rref("SUM-B-0417", "v1"), "relationship_type": "invalidation", "asserted_by": "workload:lineage-service"},
        ],
        retrieval=T_GR2_ADMIT, integrity=hashed(gr2_content),
        coverage="Corrects the earlier version; the second delivery was received on 2026-11-20 and scanned late."))
    m3w2_payload = dict(m3w1_payload, quantity_received=100, variance_pct=0.0, result="PASS")
    S.add(F11, evidence(
        "M3W-0417", "v2", "deterministic_finding", "producer:rules-engine", payload("SCHEMA-M3W-RESULT", m3w2_payload),
        event="2026-11-23T13:50:00Z", ingestion="2026-11-23T13:51:00Z", source=src("src:rules-engine", "rules:m3w/INV-2026-0417", "run-2"),
        scope_=scope(TASK, "units"), method_=method("src:rules-engine", "producer:rules-engine", rule="M3W-2.0", tool="rules-engine-7.1"),
        parents=[("INV-2026-0417", "v1"), ("PO-77231", "v1"), ("GR-5521", "v2")],
        uncertainty=("rule-output", "Reports the declared rule over the stated inputs; the inputs are not independently verified."),
        coverage="One invoice; rule M3W 2.0 with a 2% quantity tolerance. The earlier output under the same rule stays as version 1."))
    S.add(F11, evidence(
        "SCR-S1042", "v2", "deterministic_finding", "producer:screening-service",
        claims(("c1", "Supplier S-1042 was screened against the sanctions and watch lists on 2026-11-23: no match.", [])),
        event=T_SCR2_EVENT, ingestion="2026-11-23T13:31:00Z", source=src("src:screening", "screening:S-1042/2026-11-23", "run-97"),
        scope_=scope("Supplier screening for payment release", interp="Result of a screening run on the stated date."),
        method_=method("src:screening", "producer:screening-service", rule="SCREEN-LISTS-2026-11-23", tool="screening-svc-3.4"),
        freshness_policy="POL-FRESH-SCREEN", uncertainty=("rule-output", "Reports the screening run as executed on its date.")))
    # --- controlled change
    S.add(F12, evidence(
        "CHG-LOWVAL-0001", "v1", "decision_record", "producer:change-control",
        claims(("c1", "On 2026-11-23 the AP controller lowered the per-payment limit of the low-value release class from EUR 5,000 to EUR 2,500, effective 2026-11-23T14:30:00Z, following the quarterly payment-risk review.", [])),
        event=T_CHANGE, ingestion="2026-11-23T14:31:00Z", source=src("src:change-control", "change:CHG-LOWVAL-0001", "rev-1"),
        scope_=scope("Change control for the low-value release class", "EUR", "Record of a decision: it documents a choice and validates no observation."),
        method_=method("src:change-control", "producer:change-control", tool="change-portal-2.0"),
        uncertainty=("not-applicable", "A decision record documents a choice; it asserts no observation.")))
    # --- authoritative outcome records for receipts
    S.add(F7, evidence(
        "ERP-HOLD-QUERY-0417", "v1", "source_record_assertion", "producer:erp-payments",
        claims(("c1", "ERP invoice status query at 2026-11-23T10:03:30Z: invoice INV-2026-0417 has payment block B-1 set (status held).", [])),
        event="2026-11-23T10:03:30Z", ingestion="2026-11-23T10:03:31Z", source=src("src:erp-payments", "erp:invoice-status/INV-2026-0417", "q-1"),
        scope_=scope("Authoritative state of the invoice after the hold"), method_=method("src:erp-payments", "producer:erp-payments", tool="erp-query-4.2")))
    S.add(F8, evidence(
        "ERP-PAYMENTS-QUERY-0417-A", "v1", "source_record_assertion", "producer:erp-payments",
        claims(("c1", "ERP payments query at 2026-11-23T16:00:20Z: no payment instruction exists for invoice INV-2026-0417.", [])),
        event="2026-11-23T16:00:20Z", ingestion="2026-11-23T16:00:21Z", source=src("src:erp-payments", "erp:payments/INV-2026-0417", "q-2"),
        scope_=scope("Authoritative state of payments for the invoice"), method_=method("src:erp-payments", "producer:erp-payments", tool="erp-query-4.2")))
    bank_content = claims(("c1", "Bank statement line 42 of 2026-11-23: payment PAY-88421 of EUR 18,400.00 to supplier S-1042 booked at 2026-11-23T16:07:00Z.", []))
    S.add(F9, evidence(
        "BANK-STMT-0042", "v1", "source_record_assertion", "producer:bank-api", bank_content,
        event=T_BANK, ingestion=T_RECON, source=src("src:bank-api", "bank:statement/2026-11-23/42", "v1"),
        scope_=scope("Authoritative booking of the payment", "EUR"), method_=method("src:bank-api", "producer:bank-api", tool="bank-api-1.8"),
        integrity=hashed(bank_content), retrieval=T_RECON))
    S.add(F9, evidence(
        "EXE-REL-0417-B", "v1", "execution_record", "producer:payment-gateway",
        claims(("c1", "Payment instruction PF-20261123-01 for INV-2026-0417 (EUR 18,400.00) was submitted at 2026-11-23T16:00:05Z; the outcome was verified against bank statement line 42.", [support(S.rec[("BANK-STMT-0042", "v1")], "c1")])),
        event=T_RECON, ingestion="2026-11-23T16:21:00Z", source=src("src:payment-gateway", "gateway:execution/ATT-REL-0417-B-1", "v1"),
        scope_=scope("Record of an execution attempt and its verified outcome", "EUR", "Documents observed effects; validates no earlier observation."),
        method_=method("src:payment-gateway", "producer:payment-gateway", tool="gateway-3.1"), parents=[("BANK-STMT-0042", "v1")],
        uncertainty=("verified-outcome", "Outcome verified against an authoritative bank record.")))


# ----------------------------------------------------------------------------- C01 contexts
def context(ctx_id, v, as_of, interval_start, restrictions):
    return {
        "contract_id": "C01", "schema_version": SV,
        "identity_principal": {
            "context_id": ctx_id, "version": v, "tenant": TENANT,
            "requesting_principal": ANALYST, "workload_identity": "workload:ap-assistant",
        },
        "task_purpose_entity": {
            "task": TASK, "permitted_purpose": "Accounts-payable payment-release review", "entity_references": [INV_ENT, SUP_ENT],
        },
        "time_risk_policy": {
            "time_interval": {"start": interval_start, "end": as_of}, "as_of": as_of, "risk_class": "payment-release-medium",
            "policy_references": [pol("POL-AP-READ"), pol("POL-AP-PAY", "v3")],
        },
        "authorization": {
            "decision_reference": rref("AUTHZ-READ-CTX-0417", v), "actor": "policy-engine:read-scope", "time": as_of, "version": v,
            "restrictions": restrictions,
        },
    }


# ----------------------------------------------------------------------------- C03 selections
def unit(uid, authz, status, attempted, completed, reason, summary, scope_text, visibility="detailed"):
    return {
        "retrieval_unit_id": uid, "authorized_scope": scope_text, "authorization_reference": rref(authz, "v1"),
        "status": status, "attempted_at": attempted, "completed_at": completed, "reason": reason,
        "summary_visibility": visibility, "summary": summary,
    }


def at(value):
    return known(value)


def disposition(rec, state, reason):
    return {"record_reference": rref(rec["identity_schema"]["record_id"], rec["identity_schema"]["version"]), "state": state, "reason": reason}


def gap_scope(task, units=None):
    return scope(task, units)


def build_selection(S, version, as_of):
    """SEL-0417: v1 at 10:00 (all seven missingness labels) and v2 at 14:10 (after the correction)."""
    v2 = version == "v2"
    R = S.rec
    inv, po, pol4 = R[("INV-2026-0417", "v1")], R[("PO-77231", "v1")], R[("AP-POLICY-4", "v1")]
    gr = R[("GR-5521", "v2" if v2 else "v1")]
    m3w = R[("M3W-0417", "v2" if v2 else "v1")]
    scr = R[("SCR-S1042", "v2" if v2 else "v1")]
    dup = R[("DUP-0417", "v1")]
    ctx = cref("C01", "CTX-0417", version)
    t0 = "2026-11-23T13:50:00Z" if v2 else "2026-11-23T09:45:00Z"
    units = [
        unit("RETR-ERP-0417", "AUTHZ-READ-CTX-0417", "completed", at(t0), at(t0), "Retrieved by entity and period.", "Invoice INV-2026-0417 and purchase order PO-77231 retrieved.", "ERP invoices and purchase orders for supplier S-1042"),
        unit("RETR-WMS-0417", "AUTHZ-READ-CTX-0417", "completed", at(t0), at(t0), "Retrieved by purchase order.", "Goods receipt %s %s retrieved." % ("GR-5521", gr["identity_schema"]["version"]), "Warehouse receipts for PO-77231"),
        unit("RETR-POLICY-0417", "AUTHZ-READ-CTX-0417", "completed", at(t0), at(t0), "Retrieved by policy identifier.", "Accounts-payable policy AP-4 retrieved.", "Policy library: AP-4"),
        unit("RETR-SCREEN-0417", "AUTHZ-READ-CTX-0417", "completed", at(t0), at(t0), "Retrieved the latest screening result for the supplier.", "Screening result SCR-S1042 %s retrieved." % scr["identity_schema"]["version"], "Supplier screening for S-1042"),
        unit("RETR-LEDGER-0417", "AUTHZ-READ-CTX-0417", "completed", at("2026-11-23T09:51:00Z"), at("2026-11-23T09:51:00Z"), "Exact-match duplicate query over the declared window.", "Duplicate check DUP-0417 retrieved.", "Invoice ledger, 2025-11-24 to 2026-11-23"),
        unit("RETR-CREDIT-0417", "AUTHZ-READ-CTX-0417", "completed", at("2026-11-23T09:52:00Z"), at("2026-11-23T09:52:00Z"), "Credit-note ledger query for supplier S-1042, last 90 days.", "The credit-note ledger query completed and returned no relevant records.", "Credit-note ledger for supplier S-1042"),
        unit("RETR-TREASURY-0417", "AUTHZ-READ-CTX-0417", "failed", at("2026-11-23T09:58:00Z"), {"state": "unknown", "reason": "The service returned HTTP 503; the retrieval did not complete."}, "Dependency unavailable.", "Cash-position service unavailable; nothing was read.", "Treasury cash-position service"),
        unit("RETR-SCOPE-0417", PERMISSION_LIMIT_ID, "not_permitted", {"state": "not_applicable", "reason": "Not attempted: outside this principal's permissions."}, {"state": "not_applicable", "reason": "Not attempted: outside this principal's permissions."}, "Permission decision applies to this principal.", COVERAGE_LIMIT_WORDING, "Outside this principal's read scope", visibility="permission_safe"),
        unit("RETR-DERIVED-0417", "AUTHZ-READ-CTX-0417", "completed", at("2026-11-23T09:44:00Z" if not v2 else "2026-11-23T13:55:00Z"), at("2026-11-23T09:44:00Z" if not v2 else "2026-11-23T13:55:00Z"), "Derived records for the invoice.", "Three-way match result %s %s%s retrieved." % ("M3W-0417", m3w["identity_schema"]["version"], "" if v2 else "; model summaries SUM-A-0417 and SUM-B-0417 retrieved"), "Derived records for INV-2026-0417"),
    ]
    for u in units:
        if u["authorization_reference"]["record_id"] == "AUTHZ-READ-CTX-0417":
            u["authorization_reference"]["version"] = version
    disp = [
        disposition(inv, "included", "The document under review."),
        disposition(po, "included", "States the ordered quantity and price."),
        disposition(gr, "included", "States the received quantity."),
        disposition(m3w, "included", "Deterministic comparison of invoice, order and receipt."),
        disposition(scr, "included", "Supplier screening required for payment release."),
        disposition(dup, "included", "Rules out a duplicate invoice."),
        disposition(pol4, "included", "Policy that bounds hold and release."),
        disposition(R[("ANL-S1042-OTD", "v1")], "excluded", "Delivery reliability is not a payment-release criterion under POL-AP-PAY v3; the record remains retrievable."),
    ]
    if v2:
        for old, why in (
            (("GR-5521", "v1"), "Superseded by GR-5521 v2."),
            (("M3W-0417", "v1"), "Superseded by M3W-0417 v2; its input was corrected."),
            (("SCR-S1042", "v1"), "Superseded by SCR-S1042 v2."),
            (("SUM-A-0417", "v1"), "Withdrawn: its only basis, GR-5521 v1, was superseded."),
            (("SUM-B-0417", "v1"), "Withdrawn: its only basis, GR-5521 v1, was superseded."),
        ):
            disp.append(disposition(R[old], "excluded", why))
        for u in units:
            if u["retrieval_unit_id"] in ("RETR-LEDGER-0417", "RETR-CREDIT-0417", "RETR-TREASURY-0417", "RETR-SCOPE-0417", "RETR-POLICY-0417"):
                u["reason"] += " Carried over from SEL-0417 v1."
    else:
        disp.append(disposition(R[("SUM-A-0417", "v1")], "included", "Model summary, labeled as an inference."))
        disp.append(disposition(R[("SUM-B-0417", "v1")], "included", "Model summary, labeled as an inference."))
    gaps = missingness_entries(S, version, as_of, scr, dup)
    conflicts = [] if v2 else [{
        "conflict_id": "CONF-QTY", "scope": scope(TASK, "units"),
        "claim_references": [support(inv, "c1"), support(gr, "c1")],
        "materiality": "decision_changing",
        "reason": "The invoice states 100 units delivered; the goods receipt records 60 units received.",
        "assessment_basis": "Two source assertions from different systems. Neither is treated as correct; there is no majority or latest-wins resolution.",
    }]
    return {
        "contract_id": "C03", "schema_version": SV,
        "identity_scope": {
            "selection_id": "SEL-0417", "version": version, "context_reference": ctx,
            "permitted_source_scope": "ERP invoices, purchase orders and payments; warehouse receipts; policy library; supplier screening; invoice ledger; treasury service; derived records for INV-2026-0417",
            "time_scope": {"start": "2025-11-24T00:00:00Z", "end": as_of}, "as_of": as_of,
            "policy_references": [pol("POL-AP-READ"), pol("POL-AP-PAY", "v3")],
        },
        "retrieval": units,
        "disposition": disp,
        "obligations": [{
            "obligation_id": "OBL-0417-REVIEW", "policy_basis": pol("POL-AP-PAY", "v3"), "priority": "high",
            "deadline": "2026-11-23T15:30:00Z", "owner": "role:ap-controller", "delivery_state": "delivered",
            "acknowledgement_state": "acknowledged" if v2 else "pending", "escalation_state": "not_escalated",
        }],
        "conflicts_gaps": {"conflicts": conflicts, "missingness": gaps},
        "coverage": {
            "declared_scope": "Invoice INV-2026-0417 and supplier S-1042 for the payment-release question only",
            "status": "partial",
            "limitations": ["Not a whole-corpus assessment.", "Sources outside this principal's permissions are not covered.", "The treasury cash position was not read."],
        },
    }


def missingness_entries(S, version, as_of, scr, dup):
    v2 = version == "v2"
    gaps = [
        {
            "state": "missing", "scope": gap_scope("Carrier proof of delivery for the second pallet", "units"),
            "expected_evidence": "Carrier proof of delivery for a second pallet of 40 units",
            "materiality": "supporting_detail" if v2 else "supports_resolution_of_conflict",
            "reason": known("No carrier or warehouse record of a second delivery exists in the readable sources."),
            "assessment_basis": "Expected under the receiving procedure for a multi-pallet order and not present in any source in scope. Search coverage is not established, so this is recorded as missing, not as a negative.",
        },
        {
            "state": "not_retrieved", "scope": gap_scope("Open credit notes for supplier S-1042", "EUR"),
            "expected_evidence": "Open credit notes for supplier S-1042 in the last 90 days",
            "materiality": "could_change_payable_amount",
            "reason": known("Retrieval RETR-CREDIT-0417 completed and returned no relevant records."),
            "assessment_basis": "A completed retrieval with an empty result does not prove there are none: it covered the credit-note ledger only, not disputes held elsewhere.",
            "retrieval_reference": rref("RETR-CREDIT-0417", version), "retrieval_completed": True, "relevant_record_count": 0,
            "completed_at": "2026-11-23T09:52:00Z",
        },
        {
            "state": "inaccessible", "scope": gap_scope("Part of the requested scope that this principal may not read"),
            "expected_evidence": "Evidence in the requested scope that this principal may not read",
            "materiality": "unknown",
            "reason": known("Part of the requested scope is outside this principal's read permissions."),
            "assessment_basis": "Permission decision %s applies. It allows a coverage limitation and nothing else: no source, type, count, state or age is disclosed." % PERMISSION_LIMIT_ID,
            "permission_decision_reference": rref(PERMISSION_LIMIT_ID, "v1"),
            "permission_safe_summary": COVERAGE_LIMIT_WORDING,
        },
        {
            "state": "unavailable", "scope": gap_scope("Treasury cash position for the payment date", "EUR"),
            "expected_evidence": "Treasury cash position for 2026-11-23",
            "materiality": "informs_timing_not_validity",
            "reason": known("The cash-position service returned HTTP 503 and did not recover during the retrieval window."),
            "assessment_basis": "Dependency failure recorded in MON-TREASURY-0001 v1. No cash position was read or assumed.",
            "dependency_failure_reference": rref("MON-TREASURY-0001", "v1"),
        },
        {
            "state": "negative", "scope": dup["scope"],
            "expected_evidence": "An earlier invoice with the same supplier, number and amount",
            "materiality": "could_block_payment",
            "reason": known("The exact-match duplicate check found no earlier invoice in the declared window."),
            "assessment_basis": "Complete coverage of the declared window and of the exact-match rule; near-duplicates are out of scope.",
            "observation_reference": support(dup, "c1"), "method": "DUPCHECK-EXACT-1.0 over the invoice ledger", "time": T_DUP_EVENT,
            "coverage": {"declared_scope": "Supplier S-1042; invoice number FC-88231; amount EUR 18,400.00; 2025-11-24 to 2026-11-23", "status": "complete", "limitations": ["Exact match only."]},
        },
        {
            "state": "not_assessed", "scope": gap_scope("Early-payment discount eligibility", "EUR"),
            "expected_evidence": "Eligibility for the early-payment discount",
            "materiality": "outside_decision",
            "reason": known("Not part of the release decision; no assessment was requested."),
            "assessment_basis": "No rule or model was run for this question in this selection.",
            "assessment_performed": False,
        },
    ]
    if not v2:
        gaps.append({
            "state": "stale", "scope": scr["scope"],
            "expected_evidence": "Supplier screening no older than 24 hours",
            "materiality": "decision_changing",
            "reason": known("The available screening result is older than the 24-hour policy."),
            "assessment_basis": "SCR-S1042 v1 was produced on 2026-11-21 and fails POL-FRESH-SCREEN v1 at the as-of time.",
            "available_record": rref("SCR-S1042", "v1"),
            "freshness": freshness("POL-FRESH-SCREEN", T_SCR1_EVENT, as_of),
        })
    return gaps


# ----------------------------------------------------------------------------- C04 packets
def claim_text(rec, claim_id="c1"):
    return rec["content"]["claims"][[c["claim_id"] for c in rec["content"]["claims"]].index(claim_id)]["text"]


def method_of(rec):
    return copy.deepcopy(rec["method"])


def build_packet(S, version, as_of, selection):
    v2 = version == "v2"
    R = S.rec
    inv, po, pol4, dup = R[("INV-2026-0417", "v1")], R[("PO-77231", "v1")], R[("AP-POLICY-4", "v1")], R[("DUP-0417", "v1")]
    gr = R[("GR-5521", "v2" if v2 else "v1")]
    m3w = R[("M3W-0417", "v2" if v2 else "v1")]
    scr = R[("SCR-S1042", "v2" if v2 else "v1")]
    m3w_payload = m3w["content"]["payload"]["value"]
    sel_data = selection
    claims_ = [
        ("PC-1", claim_text(inv), [support(inv, "c1")]),
        ("PC-2", claim_text(po), [support(po, "c1")]),
        ("PC-3", claim_text(gr), [support(gr, "c1")]),
        ("PC-4", "Three-way match M3W 2.0 on INV-2026-0417: %s (invoiced %d units, received %d units, variance %.1f%%, tolerance %d%%)." % (
            m3w_payload["result"], m3w_payload["quantity_invoiced"], m3w_payload["quantity_received"], m3w_payload["variance_pct"], m3w_payload["tolerance_pct"]),
         [support(m3w, pointer="/value/result")]),
        ("PC-5", claim_text(scr), [support(scr, "c1")]),
        ("PC-6", claim_text(dup), [support(dup, "c1")]),
        ("PC-7", claim_text(pol4), [support(pol4, "c1")]),
    ]
    inferences = []
    if not v2:
        sa, sb = R[("SUM-A-0417", "v1")], R[("SUM-B-0417", "v1")]
        shared = "Common origin: both model summaries rest on GR-5521 v1 alone; their agreement is not independent corroboration."
        inferences = [
            {"inference_id": "M01", "text": "Model A infers: " + claim_text(sa), "kind": "model_inference", "supporting_references": [support(sa, "c1")],
             "method": method_of(sa), "limitations": [shared, "Model output; not verified against any source."]},
            {"inference_id": "M02", "text": "Model B infers: " + claim_text(sb), "kind": "model_inference", "supporting_references": [support(sb, "c1")],
             "method": method_of(sb), "limitations": [shared, "Model output; not verified against any source."]},
        ]
    if v2:
        recs = [{
            "recommendation_id": "REC-0417-2", "text": "Release payment of INV-2026-0417 at the 16:00 run under an exact approval.",
            "basis": "The corrected receipt matches the invoice quantity, the three-way match passes and supplier screening is current.",
            "uncertainty": {"state": "unquantified", "basis": "The sources now agree; the corrected receipt is itself a source assertion and the treasury cash position is still unknown."},
            "accountable_review_requirement": "The AP controller decides; the approval must be bound to ACT-REL-0417 v2.",
        }]
        proposals = [cref("C05", "ACT-REL-0417", "v2")]
        reasons = [{"item_id": "gap:unavailable", "reason": "The treasury cash position is unknown; payment timing is not checked against cash."}]
        history = {"state": "reviewed", "actor": known(CONTROLLER), "time": known(T_REVIEW_2),
                   "prior_version_references": [cref("C04", "PKT-0417", "v1")], "challenge_links": []}
        uncertainty = {"state": "unquantified", "basis": "The source records agree after the correction; the correction is itself a source assertion."}
        summary = "Selected sources for this invoice and supplier only; sources outside this principal's permissions and the treasury cash position are not covered."
    else:
        recs = [
            {"recommendation_id": "REC-0417-1", "text": "Place INV-2026-0417 on payment hold until the quantity difference is resolved.",
             "basis": "Open quantity discrepancy (CONF-QTY) between invoice and goods receipt; policy AP-4; screening is stale.",
             "uncertainty": {"state": "unquantified", "basis": "The cause of the difference is not established."},
             "accountable_review_requirement": "A hold is within the bounded grant of the AP team; the AP controller is notified."},
            {"recommendation_id": "REC-0417-1B", "text": "Release payment at the 16:00 run only if the match passes, screening is current and the invoice is held when the run starts.",
             "basis": "Policy AP-4 requires a passing three-way match; the commit-time preconditions enforce it.",
             "uncertainty": {"state": "unquantified", "basis": "Whether the receipt will be corrected by 16:00 is not known."},
             "accountable_review_requirement": "Exact approval by the AP controller, bound to ACT-REL-0417 v1."},
        ]
        proposals = [cref("C05", "ACT-HOLD-0417", "v1"), cref("C05", "ACT-REL-0417", "v1")]
        reasons = [{"item_id": "CONF-QTY", "reason": "Decision-changing conflict between invoice and goods receipt; it must be resolved or accepted by a person before release."},
                   {"item_id": "gap:stale", "reason": "Supplier screening is older than the 24-hour policy."}]
        history = {"state": "invalidated", "actor": known("workload:lineage-service"), "time": known(T_INVALIDATE),
                   "prior_version_references": [], "challenge_links": [rref("GR-5521", "v2")]}
        uncertainty = {"state": "unquantified", "basis": "Source records conflict and the cause is not established."}
        summary = "Selected sources for this invoice and supplier only; sources outside this principal's permissions and the treasury cash position are not covered."
    return {
        "contract_id": "C04", "schema_version": SV,
        "decision_context_as_of": {
            "packet_id": "PKT-0417", "version": version, "context_reference": cref("C01", "CTX-0417", version),
            "selection_reference": cref("C03", "SEL-0417", version), "as_of": as_of,
        },
        "supported_claims_references": [{"claim_id": cid, "text": text, "supporting_references": sup} for cid, text, sup in claims_],
        "labeled_inferences": inferences,
        "recommendations": recs,
        "conflicts_uncertainty": {"conflicts": copy.deepcopy(sel_data["conflicts_gaps"]["conflicts"]), "uncertainty": uncertainty},
        "coverage_omissions_gaps": {
            "coverage_reference": {"selection_reference": cref("C03", "SEL-0417", version), "location": "/coverage"},
            "visible_scoped_limitation_summary": summary,
            "missingness": copy.deepcopy(sel_data["conflicts_gaps"]["missingness"]),
        },
        "priority_mandatory_obligations": {
            "item_level_reasons": reasons,
            "obligation_references": [{"obligation_id": "OBL-0417-REVIEW", "selection_reference": cref("C03", "SEL-0417", version)}],
        },
        "action_proposals": [{"proposal_reference": p, "status": "proposed"} for p in proposals],
        "review_version_history": history,
    }


# ----------------------------------------------------------------------------- C05 proposals
DAY = {"start": "2026-11-23T00:00:00Z", "end": "2026-11-24T00:00:00Z"}


def param(name, dtype, value):
    return {"name": name, "data_type": dtype, "value": value}


def accounting(units, scope_id, behavior):
    return {"units": units, "accounting_scope": scope_id, "accounting_window": dict(DAY), "exhaustion_behavior": behavior}


def build_proposal(pid, v, packet_v, action_kind, params, evidence_refs, policies, preconditions, acct, assessment):
    return {
        "contract_id": "C05", "schema_version": SV,
        "identity_binding": {
            "proposal_id": pid, "version": v,
            "context_reference": cref("C01", "CTX-0417", packet_v), "packet_reference": cref("C04", "PKT-0417", packet_v),
        },
        "action": {
            "action_kind": action_kind, "exact_target": dict(INV_ENT), "typed_parameters": params,
            "evidence_references": evidence_refs, "policy_references": policies, "preconditions": preconditions, "accounting": acct,
        },
        "assessment": dict(assessment, status="proposed"),
    }


PRE = {
    "PRE-INVOICE-OPEN": ("Invoice INV-2026-0417 is open (not already held or paid).", pol("POL-AP-PAY", "v3")),
    "PRE-MATCH-PASS": ("A current three-way match result for the invoice is PASS.", pol("POL-AP-PAY", "v3")),
    "PRE-SCREEN-FRESH": ("Supplier screening is at most 24 hours old.", pol("POL-FRESH-SCREEN")),
    "PRE-INVOICE-HELD": ("The invoice is held: release proceeds only from the controlled hold state.", pol("POL-AP-PAY", "v3")),
}


def preconditions(*ids):
    return [{"condition_id": i, "condition": PRE[i][0], "policy_reference": PRE[i][1]} for i in ids]


def build_proposals(S):
    R = S.rec
    inv, po, dup = R[("INV-2026-0417", "v1")], R[("PO-77231", "v1")], R[("DUP-0417", "v1")]
    out = {}
    gr1, m31 = R[("GR-5521", "v1")], R[("M3W-0417", "v1")]
    out["hold"] = build_proposal(
        "ACT-HOLD-0417", "v1", "v1", "hold_payment",
        [param("reason_code", "string", "QTY-MISMATCH"), param("block_code", "string", "B-1")],
        [support(inv, "c1"), support(gr1, "c1"), support(m31, pointer="/value/result")],
        [pol("POL-AP-PAY", "v3")], preconditions("PRE-INVOICE-OPEN"),
        accounting("holds", "tenant:calder-works/GRT-CLASS-HOLD", "Reject beyond the daily hold allowance."),
        {"risk": "low: reversible administrative block", "expected_effects": ["Payment block B-1 is set on invoice INV-2026-0417; no funds move."],
         "limitations": ["Does not resolve the quantity discrepancy."], "recovery_conditions": ["Remove block B-1 when the discrepancy is resolved."]})
    for v, pv, gr_, m3w_, scr_, acct_scope in (("v1", "v1", R[("GR-5521", "v1")], R[("M3W-0417", "v1")], R[("SCR-S1042", "v1")], "GRT-APPR-0417-A"),
                                               ("v2", "v2", R[("GR-5521", "v2")], R[("M3W-0417", "v2")], R[("SCR-S1042", "v2")], "GRT-APPR-0417-B")):
        out["rel" + v] = build_proposal(
            "ACT-REL-0417", v, pv, "release_payment",
            [param("amount_eur", "number", 18400), param("currency", "string", "EUR"), param("payment_run", "string", "RUN-2026-11-23-1600")],
            [support(inv, "c1"), support(po, "c1"), support(gr_, "c1"), support(m3w_, pointer="/value/result"), support(scr_, "c1"), support(dup, "c1")],
            [pol("POL-AP-PAY", "v3"), pol("POL-FRESH-SCREEN")], preconditions("PRE-MATCH-PASS", "PRE-SCREEN-FRESH", "PRE-INVOICE-HELD"),
            accounting("EUR", "tenant:calder-works/" + acct_scope, "Reject beyond the approved amount."),
            {"risk": "medium: irreversible once the bank accepts the instruction",
             "expected_effects": ["EUR 18,400.00 is paid to supplier S-1042 in the 16:00 payment run."],
             "limitations": ["Release is conditional on the commit-time preconditions; it does not assert that they hold now."],
             "recovery_conditions": ["If the outcome is unknown, no retry until authoritative reconciliation against the bank statement."]})
    return out


# ----------------------------------------------------------------------------- C06 grants
def limit(limit_id, quantity, units, scope_id, behavior):
    return {"limit_id": limit_id, "quantity": quantity, "units": units, "accounting_scope": scope_id, "accounting_window": dict(DAY), "exhaustion_behavior": behavior}


CONFIRMED = {
    "policy_reference": pol("POL-CONFIRMED-EFFECT"), "authoritative_reconciliation_required": True,
    "timeout_alone_restores_allowance": False, "lease_expiry_alone_restores_allowance": False, "partial_effects_remain_charged": True,
}


def atomic(shared, enforcement):
    if enforcement == "shared_atomic":
        return {
            "shared_accounting_reference": rref(shared), "enforcement": "shared_atomic", "reservation_expiry_policy": pol("POL-RESERVATION"),
            "unknown_outcome_policy": "retain_reservation", "confirmed_effect_policy": copy.deepcopy(CONFIRMED),
            "weaker_guarantees": [], "race_windows": [], "residual_risk": [],
            "unattended_operation_constraint": "No constraint beyond the limits of the grant.",
        }
    return {
        "shared_accounting_reference": rref(shared), "enforcement": "unsupported", "reservation_expiry_policy": pol("POL-RESERVATION"),
        "unknown_outcome_policy": "retain_reservation", "confirmed_effect_policy": copy.deepcopy(CONFIRMED),
        "weaker_guarantees": ["The AP allowance ledger and the bank interface cannot be updated in one atomic step."],
        "race_windows": ["Between the local reservation and the bank's acceptance of the instruction."],
        "residual_risk": ["A bank-side effect can exist while the ledger still shows only a reservation."],
        "unattended_operation_constraint": "Unattended release is limited to the exact approved amount; unknown outcomes stop retries until reconciliation.",
        "domain_acceptance_reference": rref("ACCEPT-AP-BANK-INTERFACE"),
    }


def build_grant(gid, v, issuer, grantee, issued, basis, actions, targets, params, purpose, binding, evidence_constraints, policy_constraints,
                expiry, revocation, per_action, cumulative, atomic_block, notifications, recovery):
    return {
        "contract_id": "C06", "schema_version": SV,
        "identity_principals": {"grant_id": gid, "version": v, "issuer": issuer, "grantee": grantee, "tenant": TENANT, "issuance_time": issued, "authority_basis": basis},
        "scope_binding": {
            "permitted_actions": actions, "permitted_targets": targets, "permitted_parameters": params, "purpose": purpose,
            "binding": binding, "evidence_constraints": evidence_constraints, "policy_constraints": policy_constraints,
        },
        "limits_lifecycle": {
            "expiry": expiry, "revocation": revocation, "per_action_limits": per_action, "cumulative_limits": cumulative,
            "atomic_reservation_accounting": atomic_block, "notifications": notifications, "recovery": recovery,
        },
    }


def revocation(state, check_id, by, checked_at):
    return {"state": state, "check_basis": rref(check_id), "checked_by": by, "checked_at": checked_at}


def permitted_release_params(amount_constraint, run_constraint):
    return [
        {"name": "amount_eur", "data_type": "number", "constraint": amount_constraint, "policy_reference": pol("POL-AP-PAY", "v3")},
        {"name": "currency", "data_type": "string", "constraint": "EUR only", "policy_reference": pol("POL-AP-PAY", "v3")},
        {"name": "payment_run", "data_type": "string", "constraint": run_constraint, "policy_reference": pol("POL-AP-PAY", "v3")},
    ]


def build_grants(S, proposals):
    R = S.rec
    pol4 = R[("AP-POLICY-4", "v1")]
    out = {}
    out["hold"] = build_grant(
        "GRT-CLASS-HOLD", "v1", "role:ap-controller", "workload:ap-assistant", "2026-11-23T07:45:00Z", rref("BASIS-AP-POLICY-V3"),
        ["hold_payment"], [{"entity_type": "invoice", "entity_id": "*"}],
        [{"name": "reason_code", "data_type": "string", "constraint": "An AP hold reason code (QTY-MISMATCH, PRICE-MISMATCH, DUPLICATE-SUSPECTED)", "policy_reference": pol("POL-AP-PAY", "v3")},
         {"name": "block_code", "data_type": "string", "constraint": "Payment block B-1 only", "policy_reference": pol("POL-AP-PAY", "v3")}],
        "Place invoices on payment hold pending review",
        {"binding_type": "bounded_class", "class_id": "CLASS-AP-HOLD", "class_version": "1", "bounds": "Reversible payment holds on open invoices; no funds move; at most 20 holds per day."},
        [support(pol4, "c1")], [pol("POL-AP-PAY", "v3")], "2026-11-24T00:00:00Z",
        revocation("not_revoked", "REVCHK-GRT-CLASS-HOLD", "workload:grant-service", "2026-11-23T07:45:00Z"),
        [limit("LIM-HOLD-PER", 1, "holds", "tenant:calder-works/GRT-CLASS-HOLD", "Reject beyond one hold per action.")],
        [limit("LIM-HOLD-DAY", 20, "holds", "tenant:calder-works/GRT-CLASS-HOLD", "Reject beyond the daily hold allowance.")],
        atomic("ACCT-AP-HOLDS", "shared_atomic"),
        [{"recipient": "role:ap-controller", "condition": "Any hold is placed under this class", "channel": "ap-review-queue"}],
        {"owner": "role:ap-controller", "policy_reference": pol("POL-RECOVERY-AP"), "conditions": ["Hold not confirmed by an ERP status query within 10 minutes."]})

    def approval(gid, issued, proposal, revoked_state, check_id, checked_by, checked_at, scope_id):
        refs = copy.deepcopy(proposal["action"]["evidence_references"])
        return build_grant(
            gid, "v1", "person:ap-controller-01", "workload:payment-executor", issued, rref("BASIS-AP-CONTROLLER-APPROVAL"),
            ["release_payment"], [dict(INV_ENT)], permitted_release_params("Exactly 18,400 EUR, the approved amount", "RUN-2026-11-23-1600 only"),
            "Release payment of INV-2026-0417 at the 16:00 payment run",
            {"binding_type": "exact_proposal", "proposal_reference": cref("C05", proposal["identity_binding"]["proposal_id"], proposal["identity_binding"]["version"])},
            refs, [pol("POL-AP-PAY", "v3"), pol("POL-FRESH-SCREEN")], "2026-11-23T17:00:00Z",
            revocation(revoked_state, check_id, checked_by, checked_at),
            [limit("LIM-%s-EUR" % gid[-1], 18400, "EUR", "tenant:calder-works/" + gid, "Reject beyond the approved amount.")],
            [limit("LIM-%s-CUM" % gid[-1], 18400, "EUR", "tenant:calder-works/" + gid, "Reject beyond the approved amount: one execution only.")],
            atomic("ACCT-AP-PAYMENTS", "unsupported"),
            [{"recipient": "person:ap-controller-01", "condition": "The approval is revoked or the action is blocked at commit", "channel": "ap-review-queue"}],
            {"owner": "role:ap-reconciliation", "policy_reference": pol("POL-RECOVERY-AP"), "conditions": ["Outcome unknown or partial: reconcile against the bank statement before any retry."]})

    out["appr_a"] = approval("GRT-APPR-0417-A", T_APPR_A, proposals["relv1"], "revoked", "REVCHK-GRT-APPR-0417-A", "workload:lineage-service", T_INVALIDATE, "A")
    out["appr_b"] = approval("GRT-APPR-0417-B", T_APPR_B, proposals["relv2"], "not_revoked", "REVCHK-GRT-APPR-0417-B", "workload:grant-service", T_APPR_B, "B")

    def lowval(v, issued, basis, amount):
        return build_grant(
            "GRT-CLASS-LOWVAL", v, "role:ap-controller", "workload:ap-assistant", issued, basis,
            ["release_payment"], [{"entity_type": "invoice", "entity_id": "*"}],
            permitted_release_params("At most the per-action limit of this class", "Any scheduled payment run on the same day"),
            "Release low-value payments with a passing three-way match",
            {"binding_type": "bounded_class", "class_id": "CLASS-AP-LOWVAL-RELEASE", "class_version": v[1:],
             "bounds": "Release of payments up to EUR %s per payment and EUR 25,000 per day for invoices with a passing three-way match." % format(amount, ",")},
            [support(pol4, "c1")], [pol("POL-AP-PAY", "v3")], "2026-11-24T00:00:00Z",
            revocation("not_revoked", "REVCHK-GRT-CLASS-LOWVAL", "workload:grant-service", issued),
            [limit("LIM-LOWVAL-PER", amount, "EUR", "tenant:calder-works/GRT-CLASS-LOWVAL", "Reject any payment above the per-payment limit.")],
            [limit("LIM-LOWVAL-DAY", 25000, "EUR", "tenant:calder-works/GRT-CLASS-LOWVAL", "Reject beyond the daily allowance.")],
            atomic("ACCT-AP-PAYMENTS", "unsupported"),
            [{"recipient": "role:ap-controller", "condition": "Any payment is released under this class", "channel": "ap-review-queue"}],
            {"owner": "role:ap-reconciliation", "policy_reference": pol("POL-RECOVERY-AP"), "conditions": ["Outcome unknown or partial: reconcile against the bank statement before any retry."]})

    out["lowval1"] = lowval("v1", "2026-11-23T07:45:00Z", rref("BASIS-AP-POLICY-V3"), 5000)
    out["lowval2"] = lowval("v2", T_CHANGE, rref("CHG-LOWVAL-0001"), 2500)
    # the bounded grants' revocation checks are named per version
    out["lowval2"]["limits_lifecycle"]["revocation"]["check_basis"] = rref("REVCHK-GRT-CLASS-LOWVAL", "v2")
    out["lowval1"]["limits_lifecycle"]["revocation"]["check_basis"] = rref("REVCHK-GRT-CLASS-LOWVAL", "v1")
    return out


# ----------------------------------------------------------------------------- C07 receipts
def action_ref(prop):
    ib = prop["identity_binding"]
    return cref("C05", ib["proposal_id"], ib["version"])


def verified(S, evid, version, aref, method_text, actor, when, scope_text):
    rec = S.rec[(evid, version)]
    return {
        "state": "authoritatively_verified",
        "authoritative_outcome_references": [{"reference": rref(evid, version), "original_locator": copy.deepcopy(rec["original_source"]), "target": dict(INV_ENT), "action_reference": aref}],
        "method": method_text, "actor": actor, "time": when, "scope": scope_text, "target": dict(INV_ENT), "action_reference": aref,
    }


def settled(recon_id, recon_v="v1", shared="ACCT-AP-PAYMENTS"):
    return {
        "state": "reconciled", "shared_accounting_reference": rref(shared), "known_partial_effects_charged": True,
        "confirmed_effect_policy": copy.deepcopy(CONFIRMED), "authoritative_reconciliation_reference": rref(recon_id, recon_v),
    }


def open_accounting(shared="ACCT-AP-PAYMENTS"):
    return {"state": "reserved", "shared_accounting_reference": rref(shared), "known_partial_effects_charged": True, "confirmed_effect_policy": copy.deepcopy(CONFIRMED)}


def receipt(rid, v, prop, grant, attempt, executor, outcome, vr):
    return {
        "contract_id": "C07", "schema_version": SV,
        "identity_binding": {
            "receipt_id": rid, "version": v, "proposal_reference": action_ref(prop),
            "grant_reference": cref("C06", grant["identity_principals"]["grant_id"], grant["identity_principals"]["version"]),
            "execution_attempt_id": attempt, "executor": executor, "target": dict(INV_ENT),
        },
        "outcome": outcome, "verification_recovery": vr,
    }


def build_receipts(S, proposals, grants, block_codes):
    out = {}
    hold, rel1, rel2 = proposals["hold"], proposals["relv1"], proposals["relv2"]
    recon_done = {"state": "complete", "owner": "role:ap-reconciliation", "policy_reference": pol("POL-RECOVERY-AP")}
    out["hold"] = receipt(
        "RCP-HOLD-0417", "v1", hold, grants["hold"], "ATT-HOLD-0417-1", "workload:payment-executor",
        {"state": "completed_verified",
         "observed_effects": [{"effect_id": "EFF-HOLD-0417", "description": "Payment block B-1 set on invoice INV-2026-0417.", "target": dict(INV_ENT), "action_reference": action_ref(hold),
                               "quantity": 1, "units": "holds", "observed_at": T_HOLD_OBS, "accounting_reference": rref("ACCT-CHARGE-HOLD-0417")}],
         "unresolved_conditions": [], "timestamps": {"submitted": T_HOLD_SUBMIT, "observed": known(T_HOLD_OBS)}},
        {"verification": verified(S, "ERP-HOLD-QUERY-0417", "v1", action_ref(hold), "ERP invoice-status query", "workload:verifier", "2026-11-23T10:04:00Z", "Declared target and action only"),
         "reconciliation": dict(recon_done), "recovery_state": "none_required", "retry_disposition": "not_applicable_completed",
         "accounting": settled("ERP-HOLD-QUERY-0417", shared="ACCT-AP-HOLDS")})
    out["rel_a"] = receipt(
        "RCP-REL-0417-A", "v1", rel1, grants["appr_a"], "ATT-REL-0417-A-1", "workload:payment-executor",
        {"state": "not_executed_verified", "observed_effects": [], "unresolved_conditions": [],
         "timestamps": {"submitted": T_RUN_A, "observed": known("2026-11-23T16:00:20Z")},
         "reason": "Blocked at commit by the action gateway: %s. No payment instruction was sent." % ", ".join(block_codes),
         "no_effect_basis": "rejection", "no_business_effect": True},
        {"verification": verified(S, "ERP-PAYMENTS-QUERY-0417-A", "v1", action_ref(rel1), "ERP payments query", "workload:verifier", "2026-11-23T16:00:25Z", "Declared target and action only"),
         "reconciliation": dict(recon_done), "recovery_state": "none_required", "retry_disposition": "new_proposal_and_approval_required",
         "accounting": settled("ERP-PAYMENTS-QUERY-0417-A")})
    out["rel_b1"] = receipt(
        "RCP-REL-0417-B", "v1", rel2, grants["appr_b"], "ATT-REL-0417-B-1", "workload:payment-executor",
        {"state": "unknown", "observed_effects": [],
         "unresolved_conditions": ["The bank interface timed out after submission; whether the instruction was accepted is not known."],
         "timestamps": {"submitted": T_RUN_B, "observed": {"state": "unknown", "reason": "The bank interface timed out; no response was received."}}},
        {"verification": {"state": "pending", "reason": "Await authoritative reconciliation against the bank statement.", "authoritative_outcome_references": []},
         "reconciliation": {"state": "required", "owner": "role:ap-reconciliation", "policy_reference": pol("POL-RECOVERY-AP")},
         "recovery_state": "awaiting_authoritative_reconciliation", "retry_disposition": "blocked_pending_reconciliation",
         "accounting": open_accounting()})
    out["rel_b2"] = receipt(
        "RCP-REL-0417-B", "v2", rel2, grants["appr_b"], "ATT-REL-0417-B-1", "workload:payment-executor",
        {"state": "completed_verified",
         "observed_effects": [{"effect_id": "EFF-REL-0417-B", "description": "Payment PAY-88421 of EUR 18,400.00 booked for supplier S-1042.", "target": dict(INV_ENT), "action_reference": action_ref(rel2),
                               "quantity": 18400, "units": "EUR", "observed_at": T_BANK, "accounting_reference": rref("ACCT-CHARGE-REL-0417-B")}],
         "unresolved_conditions": [], "timestamps": {"submitted": T_RUN_B, "observed": known(T_BANK)}},
        {"verification": verified(S, "BANK-STMT-0042", "v1", action_ref(rel2), "Bank statement line match", "role:ap-reconciliation", T_RECON, "Declared target and action only"),
         "reconciliation": {"state": "reconciled", "owner": "role:ap-reconciliation", "policy_reference": pol("POL-RECOVERY-AP")},
         "recovery_state": "resolved", "retry_disposition": "not_applicable_completed",
         "accounting": settled("BANK-STMT-0042")})
    return out


# ----------------------------------------------------------------------------- assembly
FOLDERS = {
    "source": "01-source-records", "context": "02-context-and-normalization", "lineage": "03-lineage-and-common-origin",
    "selection": "04-selection-and-missingness", "packet": "05-decision-packet", "response": "06-assistant-response",
    "authority": "07-authority-and-delegation", "blocked": "08-blocked-action", "unknown": "09-unknown-outcome",
    "degraded": "10-degraded-modes", "correction": "11-late-correction", "change": "12-controlled-change", "cases": "13-evaluation-cases",
}


def place(S, folder_key, data):
    S.add(FOLDERS[folder_key], data)


# ----------------------------------------------------------------------------- raw exports (what the source systems emit)
def raw_exports():
    return {
        "01-source-records/raw/erp-invoice-FC-88231.json": {
            "synthetic": True, "system": "erp (synthetic)", "export": "invoice", "revision": 3, "document": "INV-2026-0417",
            "supplier_invoice_no": "FC-88231", "supplier": "S-1042", "purchase_order": "PO-77231",
            "invoice_date": "2026-11-22", "due_date": "2026-11-30", "status": "OPEN",
            "lines": [{"line": 1, "quantity": "100", "unit_price": "184.00", "amount": "18400.00", "currency": "EUR"}],
            "total": "18400.00", "last_changed": "2026-11-23T08:30:00+01:00",
        },
        "01-source-records/raw/erp-purchase-order-77231.json": {
            "synthetic": True, "system": "erp (synthetic)", "export": "purchase_order", "revision": 1, "document": "PO-77231",
            "supplier": "S-1042", "status": "APPROVED", "created": "2026-11-10T10:00:00+01:00",
            "lines": [{"line": 1, "quantity_ordered": "100", "unit_price": "184.00", "currency": "EUR"}], "total": "18400.00",
        },
        "01-source-records/raw/wms-receipt-5521-rev1.json": {
            "synthetic": True, "system": "wms (synthetic)", "export": "goods_receipt", "revision": 1, "receipt": "5521",
            "purchase_order": "PO-77231", "supplier": "S-1042", "scans": [{"pallet": "P-1", "units": 60, "scanned_at": "2026-11-18T15:05:00+01:00", "scanner": "dock-3"}],
            "total_units": 60, "recorded_at": "2026-11-18T15:06:00+01:00",
        },
        "01-source-records/raw/wms-receipt-5521-rev2.json": {
            "synthetic": True, "system": "wms (synthetic)", "export": "goods_receipt", "revision": 2, "receipt": "5521",
            "purchase_order": "PO-77231", "supplier": "S-1042",
            "scans": [{"pallet": "P-1", "units": 60, "scanned_at": "2026-11-18T15:05:00+01:00", "scanner": "dock-3"},
                      {"pallet": "P-2", "units": 40, "scanned_at": "2026-11-23T14:35:00+01:00", "scanner": "dock-3", "physically_received": "2026-11-20T10:30:00+01:00"}],
            "total_units": 100, "recorded_at": "2026-11-23T14:40:00+01:00",
        },
    }


# ----------------------------------------------------------------------------- assembly
CONTEXT_RESTRICTIONS = ["Sources outside the accounts-payable read scope are not readable by this principal."]


def in_memory_model(S, registry):
    from eahs.model import Instance, Model, identity_of, registry_from_dict
    instances = {}
    for folder, name, data in S.files:
        ident = identity_of(data)
        inst = Instance(ident[0], ident[1], ident[2], data, Path(folder) / name)
        instances[inst.key] = inst
    return Model(instances, registry_from_dict(registry), Path("."))


def build_instances():
    from eahs.gateway import evaluate_commit, ts
    registry = build_registry()
    S = Scenario()
    build_evidence(S)
    place(S, "context", context("CTX-0417", "v1", T_ASOF1, "2025-11-24T00:00:00Z", CONTEXT_RESTRICTIONS))
    place(S, "context", context("CTX-0417", "v2", T_ASOF2, "2025-11-24T00:00:00Z", CONTEXT_RESTRICTIONS))
    sel1, sel2 = build_selection(S, "v1", T_ASOF1), build_selection(S, "v2", T_ASOF2)
    place(S, "selection", sel1)
    place(S, "correction", sel2)
    place(S, "packet", build_packet(S, "v1", T_ASOF1, sel1))
    place(S, "correction", build_packet(S, "v2", T_ASOF2, sel2))
    props = build_proposals(S)
    place(S, "packet", props["hold"])
    place(S, "packet", props["relv1"])
    place(S, "correction", props["relv2"])
    grants = build_grants(S, props)
    place(S, "authority", grants["hold"])
    place(S, "authority", grants["appr_a"])
    place(S, "correction", grants["appr_b"])
    place(S, "change", grants["lowval1"])
    place(S, "change", grants["lowval2"])
    model = in_memory_model(S, registry)

    def evaluate(prop_key, grant_key, when):
        from eahs.model import Instance
        p, g = props[prop_key], grants[grant_key]
        pi = model.get("C05", p["identity_binding"]["proposal_id"], p["identity_binding"]["version"])
        gi = model.get("C06", g["identity_principals"]["grant_id"], g["identity_principals"]["version"])
        return evaluate_commit(model, pi, gi, ts(when), [])

    hold_decision = evaluate("hold", "hold", T_HOLD_SUBMIT)
    assert hold_decision.allow, "the hold must pass the gateway: %s" % hold_decision.codes
    b_decision = evaluate("relv2", "appr_b", T_RUN_B)
    assert b_decision.allow, "job B must pass the gateway: %s" % b_decision.codes
    a_decision = evaluate("relv1", "appr_a", T_RUN_A)
    assert not a_decision.allow, "job A must be blocked"
    codes = []
    for c in a_decision.codes:
        if c not in codes:
            codes.append(c)
    receipts = build_receipts(S, props, grants, codes)
    place(S, "authority", receipts["hold"])
    place(S, "blocked", receipts["rel_a"])
    place(S, "unknown", receipts["rel_b1"])
    place(S, "unknown", receipts["rel_b2"])
    return S, registry, in_memory_model(S, registry)


# ----------------------------------------------------------------------------- gateway scenarios (stored what-if evaluations)
def entry(label, why, at_, proposal, grant, overrides=None, ledger="from_receipts"):
    e = {"label": label, "why": why, "at": at_, "proposal": {"id": proposal[0], "version": proposal[1]}, "grant": {"id": grant[0], "version": grant[1]}}
    if overrides:
        e["overrides"] = overrides
    e["ledger"] = ledger
    return e


def scenario_files(model):
    from eahs.scenarios import evaluate_entry, expectation
    A, B, HOLD = ("GRT-APPR-0417-A", "v1"), ("GRT-APPR-0417-B", "v1"), ("GRT-CLASS-HOLD", "v1")
    REL1, REL2, HOLDP = ("ACT-REL-0417", "v1"), ("ACT-REL-0417", "v2"), ("ACT-HOLD-0417", "v1")
    amount = lambda value: [{"on": "proposal", "path": "/action/typed_parameters/0/value", "value": value}]  # noqa: E731
    specs = {
        "07-authority-and-delegation/gateway-scenarios.json": {
            "scenario_id": "GW-AUTHORITY-0417",
            "title": "What a bounded grant does and does not cover",
            "evaluations": [
                entry("Hold at 10:03 under the standing hold grant", "The hold is inside the class: permitted action, any invoice, permitted parameters, allowance unused.", T_HOLD_SUBMIT, HOLDP, HOLD),
                entry("A second hold of the same invoice at 10:10", "The first hold already moved the invoice out of the open state, so the precondition no longer holds.", "2026-11-23T10:10:00Z", HOLDP, HOLD),
                entry("The hold grant used to release a payment", "A grant covers exactly what it names. Release is not a hold, and its parameters are not the grant's parameters.", "2026-11-23T10:45:00Z", REL1, HOLD),
                entry("A hold on a purchase order, which the class does not cover", "The class covers invoices. A different kind of target is outside it, even for the same action.", T_HOLD_SUBMIT, HOLDP, HOLD,
                      [{"on": "proposal", "path": "/action/exact_target/entity_type", "value": "purchase_order"}]),
                entry("A precondition that nobody defined", "A precondition with no rule cannot be shown to hold, so the action does not proceed.", T_HOLD_SUBMIT, HOLDP, HOLD,
                      [{"on": "proposal", "path": "/action/preconditions/0/condition_id", "value": "PRE-UNDEFINED-9"}]),
                entry("An attempt timed before the grant was issued", "Everything the attempt rests on comes later than the attempt: the grant's issuance, its revocation check and the evidence admitted afterwards. Nothing that happens after an attempt can authorize it.", "2026-11-23T05:59:00Z", HOLDP, HOLD),
                entry("A hold at 09:30, before the match result was admitted", "The hold rests on the match result, which was admitted at 09:36. At 09:30 the gateway could not rely on it, however correct it later proved to be.", "2026-11-23T09:30:00Z", HOLDP, HOLD),
                entry("A hold at 10:03 when the only revocation check was made at 10:04", "A check that says the grant is unrevoked cannot authorize an attempt made before the check was recorded.", T_HOLD_SUBMIT, HOLDP, HOLD,
                      [{"on": "grant", "path": "/limits_lifecycle/revocation/checked_at", "value": "2026-11-23T10:04:00Z"}]),
            ],
        },
        "08-blocked-action/gateway-scenarios.json": {
            "scenario_id": "GW-BLOCKED-0417",
            "title": "The queued release is blocked at commit",
            "evaluations": [
                entry("Job A at the 16:00 run", "The approval was revoked, and the evidence it relied on has been superseded; each reason is independent.", T_RUN_A, REL1, A),
                entry("Counterfactual: job A had its approval not been revoked", "Revocation is only one protection: the superseded and stale evidence still blocks the action.", T_RUN_A, REL1, A,
                      [{"on": "grant", "path": "/limits_lifecycle/revocation/state", "value": "not_revoked"}]),
                entry("Approval A presented for the corrected proposal", "An approval is bound to one exact proposal version. It cannot be carried over to the corrected proposal.", "2026-11-23T16:00:10Z", REL2, A),
            ],
        },
        "09-unknown-outcome/gateway-scenarios.json": {
            "scenario_id": "GW-UNKNOWN-0417",
            "title": "No blind retry while the outcome is unknown",
            "evaluations": [
                entry("Job B at the 16:00 run", "Every check passes, so the gateway allows the action and reserves the allowance.", T_RUN_B, REL2, B),
                entry("A retry at 16:10 while the outcome is unknown", "The reservation from the unknown attempt still counts: a timeout does not restore the allowance.", "2026-11-23T16:10:00Z", REL2, B),
                entry("A retry at 16:30 after reconciliation", "The payment is confirmed: the allowance is consumed and the invoice is no longer held.", "2026-11-23T16:30:00Z", REL2, B),
            ],
        },
        "10-degraded-modes/gateway-scenarios.json": {
            "scenario_id": "GW-DEGRADED-0417",
            "title": "The commit check fails closed when it cannot be sure",
            "evaluations": [
                entry("Revocation state cannot be established", "If the check cannot show that the grant is unrevoked, the action does not proceed.", T_RUN_B, REL2, B,
                      [{"on": "grant", "path": "/limits_lifecycle/revocation/state", "value": "check_unavailable"}], ledger="empty"),
                entry("An evidence record named by the proposal cannot be resolved", "Evidence that cannot be resolved is not evidence that is current.", T_RUN_B, REL2, B,
                      [{"on": "proposal", "path": "/action/evidence_references/3/version", "value": "v9"}], ledger="empty"),
                entry("The run starts after the approval has expired", "An approval is time-bound; a delayed executor does not extend it.", T_RUN_B, REL2, B,
                      [{"on": "grant", "path": "/limits_lifecycle/expiry", "value": "2026-11-23T16:00:00Z"}], ledger="empty"),
                entry("The time of the revocation check is not known", "A check that cannot be placed before the attempt cannot show the grant was unrevoked then.", T_RUN_B, REL2, B,
                      [{"on": "grant", "path": "/limits_lifecycle/revocation/checked_at", "value": UNKNOWN_TIME}], ledger="empty"),
                entry("The admission time of a cited record is not known", "Evidence that cannot be shown to have been admitted by the attempt is not evidence the gateway may rely on.", T_RUN_B, REL2, B,
                      [{"on": "evidence", "record": {"id": "M3W-0417", "version": "v2"}, "path": "/producer_admission/admission_time", "value": UNKNOWN_TIME}], ledger="empty"),
                entry("The issuance time of the approval is not known", "A grant that cannot be shown to have been issued by the attempt is not usable.", T_RUN_B, REL2, B,
                      [{"on": "grant", "path": "/identity_principals/issuance_time", "value": UNKNOWN_TIME}], ledger="empty"),
            ],
        },
        "12-controlled-change/gateway-scenarios.json": {
            "scenario_id": "GW-CHANGE-0417",
            "title": "A lowered limit takes effect at the next commit check",
            "evaluations": [
                entry("EUR 4,200 at 14:20, before the change", "Within the original EUR 5,000 limit of version 1.", "2026-11-23T14:20:00Z", REL2, ("GRT-CLASS-LOWVAL", "v1"), amount(4200)),
                entry("The same payment at 14:40 with the old version presented", "Version 2 has been in force since 14:30; version 1 can no longer be used.", "2026-11-23T14:40:00Z", REL2, ("GRT-CLASS-LOWVAL", "v1"), amount(4200)),
                entry("The same payment at 14:40 under version 2", "EUR 4,200 exceeds the new per-payment limit of EUR 2,500.", "2026-11-23T14:40:00Z", REL2, ("GRT-CLASS-LOWVAL", "v2"), amount(4200)),
                entry("EUR 2,000 at 14:40 under version 2", "A smaller payment still fits inside the new class.", "2026-11-23T14:40:00Z", REL2, ("GRT-CLASS-LOWVAL", "v2"), amount(2000)),
            ],
        },
    }
    for path, spec in specs.items():
        spec["synthetic"] = True
        spec["note"] = "Stored what-if evaluations of the reference commit check. Overrides are applied in memory only; nothing is executed."
        for e in spec["evaluations"]:
            e["expect"] = expectation(evaluate_entry(model, e))
    return specs


# ----------------------------------------------------------------------------- assistant responses
def response_files(model):
    from eahs.response import render_markdown, render_response
    pkt1, pkt2 = model.get("C04", "PKT-0417", "v1"), model.get("C04", "PKT-0417", "v2")
    withdrawn = "Packet PKT-0417 v1 was invalidated at %s because GR-5521 v1 was superseded by GR-5521 v2." % T_INVALIDATE
    r1 = render_response(model, pkt1, status="withdrawn", withdrawn_reason=withdrawn)
    r2 = render_response(model, pkt2)
    style = {
        "response_id": "RESP-0417-v1-model-style", "synthetic": True,
        "packet_reference": {"contract_id": "C04", "id": "PKT-0417", "version": "v1"}, "as_of": T_ASOF1,
        "produced_by": "illustration-written-by-the-maintainers (not model output)", "status": "withdrawn", "status_reason": withdrawn,
        "statements": [
            {"kind": "claim", "label": "PC-1", "text": "The invoice asks for EUR 18,400.00: 100 units at EUR 184.00.", "refs": ["/supported_claims_references/0"]},
            {"kind": "claim", "label": "PC-3", "text": "The goods receipt shows only 60 units received.", "refs": ["/supported_claims_references/2"]},
            {"kind": "claim", "label": "PC-4", "text": "The automated three-way match fails: the variance between invoiced and received quantity is 40.0%, against a tolerance of 2%.", "refs": ["/supported_claims_references/3"]},
            {"kind": "conflict", "label": "CONF-QTY", "text": "The invoice and the goods receipt disagree on quantity (100 against 60) and nobody has resolved it yet.", "refs": ["/conflicts_uncertainty/conflicts/0"]},
            {"kind": "inference", "label": "M01, M02", "text": "Inference (model-generated, not verified): both model summaries suggest a receiving delay, but they share one origin, the goods receipt, so they do not corroborate each other.", "refs": ["/labeled_inferences/0", "/labeled_inferences/1"]},
            {"kind": "gap", "label": "gaps 1-7", "text": "Several things could not be checked: no record of a second delivery; credit notes (the query returned nothing, which does not prove there are none); part of the requested scope that is outside your read permissions; the treasury cash position (service unavailable); early-payment discount (not assessed); and supplier screening is stale. A duplicate check found nothing in its declared window.",
             "refs": ["/coverage_omissions_gaps/missingness/%d" % i for i in range(7)]},
            {"kind": "recommendation", "label": "REC-0417-1, REC-0417-1B", "text": "Recommendation (for review, not a decision): hold the invoice now; release at the 16:00 run only if the match passes, screening is current and the invoice is held.", "refs": ["/recommendations/0", "/recommendations/1"]},
            {"kind": "proposal", "label": "ACT-HOLD-0417 v1, ACT-REL-0417 v1", "text": "Proposed (not executed or approved): a payment hold and a conditional release at the 16:00 run.", "refs": ["/action_proposals/0", "/action_proposals/1"]},
            {"kind": "obligation", "label": "OBL-0417-REVIEW", "text": "Obligation OBL-0417-REVIEW: the AP controller must review before 15:30.", "refs": ["/priority_mandatory_obligations/obligation_references/0"]},
            {"kind": "limitation", "label": "limits", "text": "This covers selected sources for this invoice and supplier only.", "refs": ["/coverage_omissions_gaps/visible_scoped_limitation_summary"]},
        ],
    }
    folder = FOLDERS["response"]
    return {
        folder + "/response-PKT-0417-v1-template.json": r1,
        folder + "/response-PKT-0417-v1-template.md": render_markdown(r1),
        folder + "/response-PKT-0417-v1-model-style.json": style,
        folder + "/response-PKT-0417-v2-template.json": r2,
        folder + "/response-PKT-0417-v2-template.md": render_markdown(r2),
    }


# ----------------------------------------------------------------------------- evaluation cases (mutated copies with expected check codes)
def case(case_id, family, title, why, expect, *mutations):
    return {"case_id": case_id, "family": family, "title": title, "why": why, "expect": sorted(expect),
            "mutations": [{"target": t, "ops": ops} for t, ops in mutations]}


def rep(path, value):
    return {"op": "replace", "path": path, "value": value}


def case_file(S):
    R = S.rec
    sum_a = R[("SUM-A-0417", "v1")]
    stale_gap = {
        "state": "stale", "scope": R[("SCR-S1042", "v2")]["scope"], "expected_evidence": "Supplier screening no older than 24 hours",
        "materiality": "decision_changing", "reason": known("Labeled stale in error."), "assessment_basis": "Counterfactual: the record is under one hour old.",
        "available_record": rref("SCR-S1042", "v2"),
        "freshness": dict(freshness("POL-FRESH-SCREEN", T_SCR2_EVENT, T_ASOF2), state="fails_policy"),
    }
    leak = "Vendor bank account change history is not readable by this principal."
    more_than_permitted = "Coverage is limited by access permissions; one source was not read."
    rejected_hold = {
        "state": "not_executed_verified", "observed_effects": [], "unresolved_conditions": [],
        "timestamps": {"submitted": T_HOLD_SUBMIT, "observed": known(T_HOLD_OBS)},
        "reason": "Blocked at commit: PRECONDITION_FAILED.", "no_effect_basis": "rejection", "no_business_effect": True,
    }
    cases = [
        case("CASE-SCH-01", "schema", "A required group is removed", "Every contract group is required; a record without a lifecycle is not an evidence record.", ["SCH002"],
             ("C02 GR-5521 v1", [{"op": "remove", "path": "/lifecycle"}])),
        case("CASE-SCH-02", "schema", "A timestamp without a time zone", "Timestamps must be complete RFC 3339 date-times; a bare local time is ambiguous.", ["SCH002"],
             ("C02 INV-2026-0417 v1", [rep("/times/ingestion", "2026-11-23T07:31:00")])),
        case("CASE-SCH-03", "schema", "An outcome state outside the vocabulary", "A receipt has five outcome states; 'probably done' is not one of them.", ["SCH002"],
             ("C07 RCP-REL-0417-B v1", [rep("/outcome/state", "probably_done")])),
        case("CASE-SCH-04", "schema", "A timeout that restores the allowance", "An unknown outcome must keep its reservation; claiming reconciliation without an authoritative reference is not allowed.", ["SCH002"],
             ("C07 RCP-REL-0417-B v1", [rep("/verification_recovery/accounting/state", "reconciled")])),
        case("CASE-REF-01", "references", "A reference names a version that does not exist", "References name an exact version, never 'latest'; a missing version cannot be resolved.", ["REF001"],
             ("C04 PKT-0417 v2", [rep("/supported_claims_references/2/supporting_references/0/version", "v3")])),
        case("CASE-REF-02", "references", "A reference changes the original locator", "A reference must carry the original locator of the record it names, so a reader can go back to the source.", ["REF002"],
             ("C04 PKT-0417 v2", [rep("/supported_claims_references/0/supporting_references/0/original_locator/record_locator", "erp:invoice/FC-99999")])),
        case("CASE-REF-03", "references", "A payload pointer that points nowhere", "A payload reference must resolve inside the typed payload it names.", ["REF003"],
             ("C04 PKT-0417 v2", [rep("/supported_claims_references/3/supporting_references/0/payload_location", "/value/outcome")])),
        case("CASE-REF-04", "references", "A packet lists a proposal that does not exist", "Contract-to-contract references must resolve to the exact version.", ["REF004"],
             ("C04 PKT-0417 v2", [rep("/action_proposals/0/proposal_reference/version", "v9")])),
        case("CASE-REF-05", "references", "A policy that is not defined", "Policy references name a policy and version the domain has defined.", ["REF007"],
             ("C05 ACT-REL-0417 v2", [rep("/action/policy_references/0/policy_id", "POL-AP-PAY-DRAFT")])),
        case("CASE-LIN-01", "lineage", "A derivation that cycles back to itself", "Derivation ancestry must be acyclic; a record cannot rest on something that rests on it.", ["LIN001"],
             ("C02 GR-5521 v1", [rep("/lineage/parent_references", [rref("M3W-0417", "v1")])])),
        case("CASE-LIN-02", "lineage", "A relationship type outside the vocabulary", "Typed relationships use the domain's declared vocabulary (contradiction, supersession, validation, invalidation).", ["LIN002"],
             ("C02 GR-5521 v2", [rep("/lineage/typed_relationships/0/relationship_type", "superseded_by")])),
        case("CASE-LIN-03", "lineage", "A supersession the older record does not acknowledge", "If a newer version supersedes an older one, the older one must say so and name its replacement.", ["LIN003"],
             ("C02 GR-5521 v1", [rep("/lifecycle", {"state": "current", "effective_time": "2026-11-18T14:06:00Z", "reason": "Initial admitted version."})])),
        case("CASE-KIND-01", "kinds", "A producer submits a kind it is not registered for", "A producer cannot promote its output to another kind: an ERP export is not a model inference, and the reverse.", ["KIND001"],
             ("C02 INV-2026-0417 v1", [rep("/producer_admission/producer_id", "producer:agent-a")])),
        case("CASE-KIND-02", "kinds", "A model inference cited as a supported claim", "Model inferences are listed and labeled as inferences; they never support a 'supported claim'.", ["KIND002"],
             ("C04 PKT-0417 v1", [rep("/supported_claims_references/1/text", claim_text(sum_a)), rep("/supported_claims_references/1/supporting_references/0", support(sum_a, "c1"))])),
        case("CASE-COR-01", "corroboration", "Two inferences share one origin and do not say so", "Agreement between derivations that share a root is not independent corroboration; each must say it has a common origin.", ["COR002"],
             ("C04 PKT-0417 v1", [rep("/labeled_inferences/0/limitations", ["Model output; not verified against any source."])])),
        case("CASE-COR-02", "corroboration", "Agreement presented as independent corroboration", "A claim of independent corroboration needs at least two records with different origins.", ["COR001"],
             ("C04 PKT-0417 v1", [rep("/labeled_inferences/0/text", "Independently corroborated: the goods receipt is probably incomplete.")])),
        case("CASE-LIFE-01", "lifecycle", "A late correction that does not reach a derived record", "When a record is superseded, every derivation that rests on it must stop being current.", ["LIFE002"],
             ("C02 M3W-0417 v1", [rep("/lifecycle", {"state": "current", "effective_time": "2026-11-23T09:36:00Z", "reason": "Initial admitted version."})])),
        case("CASE-LIFE-02", "lifecycle", "A newer packet exists but the old one still looks active", "A packet that cites superseded records, or has a newer version, must not stay active.", ["LIFE003", "LIFE004"],
             ("C04 PKT-0417 v1", [rep("/review_version_history", {"state": "reviewed", "actor": known(CONTROLLER), "time": known(T_REVIEW_1), "prior_version_references": [], "challenge_links": []})])),
        case("CASE-LIFE-03", "lifecycle", "A pending approval survives the invalidation of its basis", "An approval cannot outlive the packet it relied on: when the basis is invalidated, the approval is revoked.", ["LIFE005"],
             ("C06 GRT-APPR-0417-A v1", [rep("/limits_lifecycle/revocation/state", "not_revoked")])),
        case("CASE-MISS-01", "missingness", "Labeled stale although it is fresh", "A stale label must be justified by the freshness policy; a fresh record cannot be called stale.", ["MISS003"],
             ("C03 SEL-0417 v2", [{"op": "add", "path": "/conflicts_gaps/missingness/-", "value": stale_gap}]),
             ("C04 PKT-0417 v2", [{"op": "add", "path": "/coverage_omissions_gaps/missingness/-", "value": stale_gap}])),
        case("CASE-MISS-02", "missingness", "A negative without complete coverage", "'Checked and none found' needs complete coverage of its declared scope; otherwise it is only 'not retrieved' or 'missing'.", ["MISS002"],
             ("C03 SEL-0417 v1", [rep("/conflicts_gaps/missingness/4/coverage/status", "partial")]),
             ("C04 PKT-0417 v1", [rep("/coverage_omissions_gaps/missingness/4/coverage/status", "partial")])),
        case("CASE-MISS-03", "missingness", "An empty result from a retrieval that never completed", "'Not retrieved' means a completed retrieval returned nothing; an interrupted retrieval is not an empty result.", ["MISS001", "REF006"],
             ("C03 SEL-0417 v1", [rep("/retrieval/5/status", "failed")])),
        case("CASE-MISS-04", "missingness", "The packet drops a gap its selection recorded", "Every gap in the selection must stay visible in the packet.", ["MISS005"],
             ("C04 PKT-0417 v1", [{"op": "remove", "path": "/coverage_omissions_gaps/missingness/2"}])),
        case("CASE-PKT-01", "packets", "A supported claim that says more than its record", "A supported claim says what its record says, no more.", ["PKT001"],
             ("C04 PKT-0417 v2", [rep("/supported_claims_references/2/text", "Goods receipt GR-5521 records 100 units received on 2026-11-18.")])),
        case("CASE-PKT-02", "packets", "A packet and its selection disagree on the as-of time", "The packet and its selection are one snapshot: they must share the as-of time.", ["PKT002"],
             ("C04 PKT-0417 v2", [rep("/decision_context_as_of/as_of", "2026-11-23T14:11:00Z")])),
        case("CASE-AUTH-01", "authority", "A receipt says the action ran although the gateway would have blocked it", "A receipt must agree with what the commit check decides at the time of the attempt.", ["AUTH004"],
             ("C07 RCP-REL-0417-A v1", [rep("/outcome/state", "completed_verified")])),
        case("CASE-AUTH-02", "authority", "A rejection that does not say why", "A not-executed receipt must name the blocking checks.", ["AUTH005"],
             ("C07 RCP-REL-0417-A v1", [rep("/outcome/reason", "Rejected.")])),
        case("CASE-AUTH-03", "authority", "A receipt cites a check that does not fail", "A rejection that cites a check the gateway passes is wrong, or the check has been changed since.", ["AUTH007"],
             ("C07 RCP-HOLD-0417 v1", [rep("/outcome", rejected_hold)])),
        case("CASE-AUTH-04", "authority", "A grant that no longer covers the target", "An attempt outside the grant's targets must be blocked; a receipt that says otherwise disagrees with the grant.", ["AUTH004"],
             ("C06 GRT-APPR-0417-B v1", [rep("/scope_binding/permitted_targets/0/entity_id", "INV-2026-9999")])),
        case("CASE-ACC-01", "accounting", "A later receipt version that describes a different attempt", "Versions of one receipt describe the same attempt; a different attempt needs its own receipt.", ["ACC004"],
             ("C07 RCP-REL-0417-B v2", [rep("/identity_binding/execution_attempt_id", "ATT-REL-0417-B-2")])),
        case("CASE-ACC-02", "accounting", "A verified outcome whose accounting is still only reserved", "A reservation becomes settled only on authoritative reconciliation.", ["ACC002", "ACC003"],
             ("C07 RCP-REL-0417-B v2", [rep("/verification_recovery/accounting", open_accounting())])),
        case("CASE-DISC-01", "disclosure", "A summary that names what the principal may not see", "A permission-safe summary must not name the withheld detail; a derived output can disclose what its source withholds. The summary also departs from the words the decision permits.", ["DISC001", "DISC003"],
             ("C03 SEL-0417 v1", [rep("/conflicts_gaps/missingness/2/permission_safe_summary", leak)]),
             ("C04 PKT-0417 v1", [rep("/coverage_omissions_gaps/missingness/2/permission_safe_summary", leak)])),
        case("CASE-DISC-02", "disclosure", "An entry for a source whose existence the permission decision withholds", "Permission comes before disclosure: if the decision does not let the requestor know the source exists, no output may carry an entry for it.", ["DISC002"],
             ("C03 SEL-0417 v1", [rep("/conflicts_gaps/missingness/2/permission_decision_reference/record_id", PERMISSION_WITHHELD_ID), rep("/retrieval/7/authorization_reference/record_id", PERMISSION_WITHHELD_ID)]),
             ("C04 PKT-0417 v1", [rep("/coverage_omissions_gaps/missingness/2/permission_decision_reference/record_id", PERMISSION_WITHHELD_ID)])),
        case("CASE-DISC-03", "disclosure", "A coverage limitation that says more than the decision permits", "Where the decision lets the requestor know that coverage is limited, the output uses its words and adds nothing: not a count, a name, a type or a state.", ["DISC003"],
             ("C03 SEL-0417 v1", [rep("/conflicts_gaps/missingness/2/permission_safe_summary", more_than_permitted), rep("/retrieval/7/summary", more_than_permitted)]),
             ("C04 PKT-0417 v1", [rep("/coverage_omissions_gaps/missingness/2/permission_safe_summary", more_than_permitted)])),
        case("CASE-ROLE-01", "roles", "The requestor approves their own request", "The requestor and the approver are distinct roles. A person who asked for the packet may not approve the action it proposes unless the policy says one person may hold both.", ["ROLE001", "ROLE002"],
             ("C06 GRT-APPR-0417-B v1", [rep("/identity_principals/issuer", ANALYST)])),
        case("CASE-ROLE-02", "roles", "The requestor is recorded as the reviewer of a packet", "A packet is reviewed by the Decision Owner, who owns the decision. The person who asked for it reviews nothing on the owner's behalf.", ["ROLE003"],
             ("C04 PKT-0417 v2", [rep("/review_version_history/actor/value", ANALYST)])),
        case("CASE-ROLE-03", "roles", "An approval that comes before the review of its packet", "An exact approval follows the Decision Owner's review of the packet it rests on.", ["ROLE004"],
             ("C06 GRT-APPR-0417-B v1", [rep("/identity_principals/issuance_time", "2026-11-23T15:00:00Z")])),
    ]
    return {
        "synthetic": True,
        "note": "Each case copies the example set in memory, applies the mutation and requires exactly the listed codes. These are deterministic functional checks on synthetic data; they are not the EV01-EV12 evaluation programme, which has not been run.",
        "cases": cases,
    }


def dumps(data):
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"


def build_files():
    """Return {path relative to examples/: bytes} for every generated file."""
    S, registry, model = build_instances()
    files = {"registry.json": dumps(registry).encode("utf-8")}
    for folder, name, data in S.files:
        files["%s/%s" % (folder, name)] = dumps(data).encode("utf-8")
    for rel_path, data in raw_exports().items():
        files[rel_path] = dumps(data).encode("utf-8")
    for rel_path, data in scenario_files(model).items():
        files[rel_path] = dumps(data).encode("utf-8")
    for rel_path, data in response_files(model).items():
        files[rel_path] = (dumps(data) if isinstance(data, dict) else data).encode("utf-8")
    files[FOLDERS["cases"] + "/cases.json"] = dumps(case_file(S)).encode("utf-8")
    return files


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--check", action="store_true", help="compare a fresh build with the committed files and fail on any difference")
    parser.add_argument("--out", type=Path, default=EXAMPLES, help="target directory (default: examples/)")
    args = parser.parse_args(argv)
    files = build_files()
    if args.check:
        problems = []
        for rel_path, content in sorted(files.items()):
            target = args.out / rel_path
            if not target.exists():
                problems.append("missing: %s" % rel_path)
            elif target.read_bytes() != content:
                problems.append("differs: %s" % rel_path)
        committed = {p.relative_to(args.out).as_posix() for p in args.out.rglob("*.json")} if args.out.exists() else set()
        for extra in sorted(committed - set(files)):
            problems.append("unexpected (not produced by the builder): %s" % extra)
        if problems:
            print("Example data is out of date. Run `python scripts/build_example_data.py` and review the diff.")
            for p in problems:
                print("  " + p)
            return 1
        print("Example data matches the builder (%d generated files)." % len(files))
        return 0
    for rel_path, content in sorted(files.items()):
        target = args.out / rel_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
    print("Wrote %d files under %s" % (len(files), args.out))
    return 0


if __name__ == "__main__":
    for _stream in (sys.stdout, sys.stderr):  # a legacy console code page must not break the output
        getattr(_stream, "reconfigure", lambda **_: None)(encoding="utf-8", errors="replace")
    sys.exit(main())



