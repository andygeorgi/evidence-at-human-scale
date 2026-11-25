# 02 Context and normalization

[← 01 Source records](../01-source-records/README.md) · [Examples](../README.md) · [Next: 03 Lineage and common origin →](../03-lineage-and-common-origin/README.md)

*Synthetic. The tenant, people, workload and decision references are invented.*

## Purpose

Before anything is selected, the interaction is bound to a context ([C01](../../contracts/c01-context.md)): who is asking, for which task and purpose, about which entities, as of when, at what risk, under which policies and with what authorization. Everything that follows (selection, packet, proposal) refers back to one exact version of this object. The reasoning is in [chapter 3](../../docs/paper/03-governed-context.md) and [chapter 5](../../docs/paper/05-context-and-attention.md).

## Files

| File | As of | What it is |
|---|---|---|
| [`c01-CTX-0417-v1.json`](c01-CTX-0417-v1.json) | 10:00 | The context for the first review. |
| [`c01-CTX-0417-v2.json`](c01-CTX-0417-v2.json) | 14:10 | The context for the review after the correction. A new version, not an edit of v1. |

## What a context binds

| Group | In this example |
|---|---|
| `identity_principal` | Tenant `tenant:calder-works`; requesting principal `person:ap-analyst-02` (the requestor); workload identity `workload:ap-assistant`. The person and the workload are separate identities: the assistant acts for the person, it is not the person. |
| `task_purpose_entity` | Task "Decide whether to release payment of invoice INV-2026-0417 (supplier S-1042)"; purpose "Accounts-payable payment-release review"; the invoice and the supplier as entities. |
| `time_risk_policy` | Interval 2025-11-24 to the as-of time; as-of 10:00 (v1) or 14:10 (v2); risk class `payment-release-medium`; policies `POL-AP-READ` v1 and `POL-AP-PAY` v3. |
| `authorization` | A reference to the read-scope decision `AUTHZ-READ-CTX-0417` (v1 or v2), the deciding actor, the time, and the restriction that sources outside the accounts-payable read scope are not readable. |

The access decision itself is not defined by the contracts. It is an external record the domain owns: see `external_records` in the [registry](../registry.json).

## Normalization: the rules that keep records comparable

The [source records example](../01-source-records/README.md) shows admission of one record. Normalization is also a set of rules every record's **scope** obeys, so that two records can be compared without guessing. Look at `scope` in any C02 file:

- **Entities and task** are named, not implied.
- **Jurisdiction** is never left blank. Here it is `not_applicable` with a reason ("Internal accounts-payable review; no external jurisdiction asserted").
- **Units** are explicit (`EUR`, `units`) or `not_applicable` with a reason.
- **Interpretation** says how the statement should be read ("Statement of a source system or analysis as recorded; not independently verified").
- **Time** is UTC with the clock basis stated.

A field that does not apply says so. A reader never has to wonder whether a blank means "no" or "forgot".

## v1 and v2

Only the as-of time and the authorization reference differ. The second context is a new object because the first one governed a selection and a packet that have since been invalidated; they still refer to v1, and that is how a reader can tell which snapshot a packet answered.

## Checks that run here

Stage 2 validates both contexts. Stage 3 checks that the policy references resolve (`REF007`) and the access decision resolves (`REF005`), and that the context, the selection and the packet built under it state one as-of time and that the selection reads no time outside the context's interval (`PKT002`). A proposal must rest on the context of its packet (`PKT006`). Related case: `CASE-PKT-02`.

## What this shows, and what it does not

- **Shows:** an interaction bound to who, what, why, when and under which rules, with a person and a workload kept apart.
- **Does not show:** how an access decision is made, how identities are federated, or that a context is sufficient for authorization. The access decision is a stand-in.

[← 01 Source records](../01-source-records/README.md) · [Examples](../README.md) · [Next: 03 Lineage and common origin →](../03-lineage-and-common-origin/README.md)
