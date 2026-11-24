# Review aid from packet PKT-0417 v1

*Written by: template-fallback-1. As of 2026-11-23T10:00:00Z. Status: **withdrawn**.*

> **Withdrawn.** Packet PKT-0417 v1 was invalidated at 2026-11-23T13:45:00Z because GR-5521 v1 was superseded by GR-5521 v2.

This is a review aid. It is not a decision, an approval or an instruction.

## What the sources say

- Invoice INV-2026-0417 from supplier S-1042 (supplier invoice FC-88231, dated 2026-11-22) states 100 units delivered at EUR 184.00 per unit, total EUR 18,400.00, payable by 2026-11-30. `[PC-1]`
- Purchase order PO-77231 authorizes up to 100 units at EUR 184.00 per unit, total EUR 18,400.00. `[PC-2]`
- Goods receipt GR-5521 records 60 units received on 2026-11-18. `[PC-3]`
- Three-way match M3W 2.0 on INV-2026-0417: FAIL (invoiced 100 units, received 60 units, variance 40.0%, tolerance 2%). `[PC-4]`
- Supplier S-1042 was screened against the sanctions and watch lists on 2026-11-21: no match. `[PC-5]`
- No invoice with supplier S-1042, number FC-88231 and amount EUR 18,400.00 exists in the ledger between 2025-11-24 and 2026-11-23 (exact match). `[PC-6]`
- Policy AP-4: an invoice with an open quantity or price discrepancy may be placed on payment hold by the accounts-payable team; releasing it requires a passing three-way match. `[PC-7]`

## Inferences (model-generated, not verified)

- Inference (model-generated, not verified): Model A infers: The goods receipt is probably incomplete: the 40 missing units were probably delivered on a later date and not yet scanned. Limits: Common origin: both model summaries rest on GR-5521 v1 alone; their agreement is not independent corroboration. Model output; not verified against any source. `[M01]`
- Inference (model-generated, not verified): Model B infers: The quantity difference is probably a receiving delay; the invoice quantity is consistent with the purchase order. Limits: Common origin: both model summaries rest on GR-5521 v1 alone; their agreement is not independent corroboration. Model output; not verified against any source. `[M02]`

## Conflicts nobody has resolved

- Unresolved conflict CONF-QTY: The invoice states 100 units delivered; the goods receipt records 60 units received. Materiality: decision changing. `[CONF-QTY]`

## What could not be checked

- Missing: Carrier proof of delivery for a second pallet of 40 units. No carrier or warehouse record of a second delivery exists in the readable sources. `[gap 1 (missing)]`
- Not retrieved: Open credit notes for supplier S-1042 in the last 90 days. Retrieval RETR-CREDIT-0417 completed with 0 relevant records; an empty result does not prove absence. `[gap 2 (not_retrieved)]`
- Inaccessible: Coverage is limited by access permissions; no protected source identity or content is disclosed. `[gap 3 (inaccessible)]`
- Unavailable: Treasury cash position for 2026-11-23. The cash-position service returned HTTP 503 and did not recover during the retrieval window. Nothing was read or assumed. `[gap 4 (unavailable)]`
- Checked, none found: An earlier invoice with the same supplier, number and amount. Method: DUPCHECK-EXACT-1.0 over the invoice ledger; coverage complete for: Supplier S-1042; invoice number FC-88231; amount EUR 18,400.00; 2025-11-24 to 2026-11-23. `[gap 5 (negative)]`
- Not assessed: Eligibility for the early-payment discount. No assessment was performed. `[gap 6 (not_assessed)]`
- Stale: SCR-S1042 v1 is out of date. Record is 50.0 h old at evaluation; policy allows 24 h. `[gap 7 (stale)]`

## Recommendations (for review)

- Recommendation from the withdrawn packet (not current advice; for review, not a decision): Place INV-2026-0417 on payment hold until the quantity difference is resolved. Basis: Open quantity discrepancy (CONF-QTY) between invoice and goods receipt; policy AP-4; screening is stale. Requires: A hold is within the bounded grant of the AP team; the AP controller is notified. `[REC-0417-1]`
- Recommendation from the withdrawn packet (not current advice; for review, not a decision): Release payment at the 16:00 run only if the match passes, screening is current and the invoice is held when the run starts. Basis: Policy AP-4 requires a passing three-way match; the commit-time preconditions enforce it. Requires: Exact approval by the AP controller, bound to ACT-REL-0417 v1. `[REC-0417-1B]`

## Proposed actions (none is executed or approved)

- Proposal from the withdrawn packet (not current advice; not executed or approved): ACT-HOLD-0417 v1, hold_payment on invoice INV-2026-0417. `[ACT-HOLD-0417 v1]`
- Proposal from the withdrawn packet (not current advice; not executed or approved): ACT-REL-0417 v1, release_payment on invoice INV-2026-0417. `[ACT-REL-0417 v1]`

## Obligations

- Obligation OBL-0417-REVIEW from the withdrawn packet (not current advice): due 2026-11-23T15:30:00Z, owner role:ap-controller. `[OBL-0417-REVIEW]`

## Limits of this view

- Selected sources for this invoice and supplier only; sources outside this principal's permissions and the treasury cash position are not covered. `[limits]`
