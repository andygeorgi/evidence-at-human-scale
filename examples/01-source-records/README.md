# 01 Source records

[← Examples](../README.md) · [Next: 02 Context and normalization →](../02-context-and-normalization/README.md)

*Synthetic. The supplier, invoice, order and receipt are invented.*

## Purpose

A source record is what a source system asserted, in a specific version and scope. It is not guaranteed truth. This folder shows the raw exports of three source systems and the evidence records ([C02](../../contracts/c02-evidence.md)) admitted from them, so you can see exactly what admission keeps, converts and adds. The reasoning is in [chapter 4 of the paper](../../docs/paper/04-evidence-and-lineage.md) and the [evidence semantics](../../architecture/evidence-semantics.md) reference.

## Files

| File | What it is |
|---|---|
| [`raw/erp-invoice-FC-88231.json`](raw/erp-invoice-FC-88231.json) | The invoice as the ERP exports it: numbers as strings, local time with an offset, status `OPEN`, revision 3. |
| [`raw/erp-purchase-order-77231.json`](raw/erp-purchase-order-77231.json) | The purchase order: 100 units at EUR 184.00. |
| [`raw/wms-receipt-5521-rev1.json`](raw/wms-receipt-5521-rev1.json) | The goods receipt as first recorded: one pallet, 60 units. |
| [`raw/wms-receipt-5521-rev2.json`](raw/wms-receipt-5521-rev2.json) | The same receipt after a late scan of a second pallet: 100 units. Admitted in the [late correction example](../11-late-correction/README.md). |
| [`c02-INV-2026-0417-v1.json`](c02-INV-2026-0417-v1.json) | Evidence record admitted from the invoice export. |
| [`c02-PO-77231-v1.json`](c02-PO-77231-v1.json) | Evidence record admitted from the purchase-order export. |
| [`c02-GR-5521-v1.json`](c02-GR-5521-v1.json) | Evidence record admitted from receipt revision 1. |
| [`c02-AP-POLICY-4-v1.json`](c02-AP-POLICY-4-v1.json) | The accounts-payable policy that bounds hold and release, as a source record from the policy library. There is no raw export for it. |

## What admission does

| In the raw export | In the evidence record | What happened |
|---|---|---|
| `"total": "18400.00"` and the line fields | one claim in `content.claims`: "…100 units delivered at EUR 184.00 per unit, total EUR 18,400.00…" | The source's assertion is kept as a scoped claim with `scope.units` = EUR. The record does not say the invoice is correct. |
| `"last_changed": "2026-11-23T08:30:00+01:00"` | `times.event` = `2026-11-23T07:30:00Z`, `times.clock_basis` = "UTC, source-system clock" | The offset is resolved to UTC at admission. Event, effective, source-update, ingestion and retrieval times are kept apart. |
| `"revision": 3`, document number | `original_source`: `record_locator` `erp:invoice/FC-88231`, `original_version` `rev-3` | The locator and the version are preserved, so a reader can go back to the source. |
| the exporting system | `producer_admission`: producer `producer:erp-invoices`, kind `source_record_assertion` | The kind comes from the [registry](../registry.json): this producer may submit source assertions and nothing else. |
| nothing | `times.freshness`: policy `POL-FRESH-RECORDS` v1, `within_policy` | Freshness is evaluated at ingestion against a named policy. |
| nothing | `integrity`: `absent`, with a reason | The synthetic source supplies no hash or signature. Absence is stated, not left blank. |
| nothing | `disclosure_permissions`: tenant, classification, purpose, policy | Who may see this record and for what. |
| nothing | `lifecycle`: `current` (shown `superseded` for the receipt, see the snapshot convention) | A record has a lifecycle, so a correction can supersede it. |

## Look at

- The receipt record carries a **scoped validation**, `V-GR-5521-01`: the pallet count was re-scanned at the dock. Its `scope` says "Pallet P-1 only (60 units)" and its limitation says it validates neither a later delivery nor the invoice. Validation belongs to the target and scope it assessed.
- Two records disagree about quantity (the invoice says 100, the receipt says 60). Neither record says so. Disagreement is found later, by [selection](../04-selection-and-missingness/README.md), and stays visible.
- The goods receipt (`GR-5521` v1) shows `lifecycle.state` = `superseded` with `replacement_reference` v2. That is the end-of-day snapshot; it became superseded at 13:40.

## Checks that run here

Stage 2 validates each file against the C02 definition. Stage 3 checks that the producer may submit this kind (`KIND001`), that every reference resolves to an exact version (`REF001`–`REF007`) and that a superseded record names its replacement (`LIFE001`, `LIN003`). Related evaluation cases: `CASE-SCH-01`, `CASE-SCH-02`, `CASE-KIND-01`, `CASE-LIN-03`.

## What this shows, and what it does not

- **Shows:** a record that carries its own origin, scope, time, method, permissions and lifecycle, and a conversion that preserves the way back to the source.
- **Does not show:** that normalization scales, that real exports are this tidy, or that any source is correct. The records are hand-shaped to be small and readable.

[← Examples](../README.md) · [Next: 02 Context and normalization →](../02-context-and-normalization/README.md)
