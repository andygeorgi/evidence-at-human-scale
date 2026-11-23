# 08 Blocked action

[← 07 Authority and delegation](../07-authority-and-delegation/README.md) · [Examples](../README.md) · [Next: 09 Unknown outcome →](../09-unknown-outcome/README.md)

*Synthetic. The payment run, the approval and the gateway decision are invented.*

## Purpose

An approval is a statement made at one moment. By the time the action runs, the evidence it rested on may have been corrected. This folder shows the release that was approved at 10:40 being **refused at 16:00**, and the receipt that proves nothing happened. The reasoning is in [chapter 9](../../docs/paper/09-authority.md) and [action and degradation](../../architecture/action-and-degradation.md).

## Files

| File | What it is |
|---|---|
| [`c07-RCP-REL-0417-A-v1.json`](c07-RCP-REL-0417-A-v1.json) | The receipt of job A: `not_executed_verified`. |
| [`c02-ERP-PAYMENTS-QUERY-0417-A-v1.json`](c02-ERP-PAYMENTS-QUERY-0417-A-v1.json) | The authoritative ERP query: no payment instruction exists for the invoice. |
| [`gateway-scenarios.json`](gateway-scenarios.json) | Three stored evaluations: the block, a counterfactual and a mis-bound approval. |

## What happened at 16:00:00

Job A was queued at 10:40 under approval `GRT-APPR-0417-A` for proposal `ACT-REL-0417` v1. When the payment run started, the gateway re-checked everything an approval cannot vouch for and blocked the action with four independent reasons:

| Code | Why it fired |
|---|---|
| `GRANT_REVOKED` | The approval was revoked at 13:45, when the packet it relied on was invalidated. |
| `EVIDENCE_NOT_CURRENT` | The goods receipt v1, the match result v1 and the screening v1 that the proposal cites have all been superseded. |
| `EVIDENCE_STALE` | The screening is 56 hours old against a 24-hour policy. |
| `PRECONDITION_FAILED` | No *current* passing match result and no *current* fresh screening are among the evidence the proposal cites. |

The business situation had in fact been fixed by 14:10: the corrected receipt matches the invoice. The approval is still not usable. **It was given for a proposal built on evidence that has since been replaced, and a new proposal needs a new approval.** That is the point of the example.

## The receipt

[`c07-RCP-REL-0417-A-v1.json`](c07-RCP-REL-0417-A-v1.json) records:

- `outcome.state` `not_executed_verified`, with `no_effect_basis` `rejection`, `no_business_effect` `true`, no observed effects and no unresolved conditions.
- `outcome.reason`: "Blocked at commit by the action gateway: GRANT_REVOKED, EVIDENCE_NOT_CURRENT, EVIDENCE_STALE, PRECONDITION_FAILED. No payment instruction was sent." The receipt must name the blocking checks.
- `verification`: **authoritatively verified**, by an ERP payments query that shows no payment instruction for the invoice. A receipt that says "not executed" is only as good as the check that nothing happened.
- `accounting`: `reconciled`. Nothing was reserved or charged, and the authoritative query is the reference.
- `retry_disposition`: `new_proposal_and_approval_required`.

## The commit-time reason codes

All sixteen codes of the reference commit check, and where each is shown:

| Code | The check fails when… | Shown in |
|---|---|---|
| `GRANT_REVOKED` | the grant was revoked at or before the attempt | here |
| `REVOCATION_UNVERIFIED` | the revocation state is neither `not_revoked` nor `revoked`: the check cannot show the grant is unrevoked | [10](../10-degraded-modes/README.md) |
| `GRANT_EXPIRED` | the grant's expiry has passed | [10](../10-degraded-modes/README.md) |
| `GRANT_NOT_YET_VALID` | the grant was issued after the attempt | [07](../07-authority-and-delegation/README.md) |
| `GRANT_SUPERSEDED` | a newer version of the grant is in force | [12](../12-controlled-change/README.md) |
| `GRANT_NOT_BOUND` | an exact approval is bound to a different proposal version | here |
| `ACTION_NOT_PERMITTED` | the action kind is not among the grant's | [07](../07-authority-and-delegation/README.md) |
| `TARGET_NOT_PERMITTED` | the target is outside the grant (exact, or `*` for the same type) | [07](../07-authority-and-delegation/README.md) |
| `PARAMETER_NOT_PERMITTED` | a parameter's name or type is not permitted | [07](../07-authority-and-delegation/README.md) |
| `EVIDENCE_UNRESOLVED` | a cited record does not exist | [10](../10-degraded-modes/README.md) |
| `EVIDENCE_NOT_CURRENT` | a cited record had been superseded, withdrawn, revoked or expired | here |
| `EVIDENCE_STALE` | a cited record is older than its freshness policy | here |
| `PRECONDITION_UNDEFINED` | a precondition has no defined rule | [07](../07-authority-and-delegation/README.md) |
| `PRECONDITION_FAILED` | a named precondition does not hold at commit | here, [07](../07-authority-and-delegation/README.md), [09](../09-unknown-outcome/README.md) |
| `PER_ACTION_LIMIT` | the action exceeds the per-action limit | [12](../12-controlled-change/README.md) |
| `CUMULATIVE_LIMIT` | what is already consumed or reserved, plus this action, exceeds the cumulative limit | [09](../09-unknown-outcome/README.md) |

The check returns every reason it finds, not the first. It is a small reference function; a real gateway needs state, concurrency control and a connection to the target, none of which are modelled.

## The three stored evaluations

| What is attempted | Decision | Codes | Why |
|---|---|---|---|
| Job A at 16:00 | BLOCK | `GRANT_REVOKED`, `EVIDENCE_NOT_CURRENT`, `EVIDENCE_STALE`, `PRECONDITION_FAILED` | As above. |
| Counterfactual: job A had its approval **not** been revoked | BLOCK | `EVIDENCE_NOT_CURRENT`, `EVIDENCE_STALE`, `PRECONDITION_FAILED` | Revocation is only one protection. The superseded and stale evidence blocks the action on its own. |
| Approval A presented for the corrected proposal | BLOCK | `GRANT_REVOKED`, `GRANT_NOT_BOUND`, `EVIDENCE_NOT_CURRENT`, `EVIDENCE_STALE` | An approval is bound to one exact proposal version. It cannot be carried over. |

## Checks that run here

Stage 3 recomputes the commit decision for the receipt and requires agreement: a receipt that says the action ran although the gateway would have blocked it (`AUTH004`), a rejection that does not name its reasons (`AUTH005`), a rejection that cites a check which does not fail (`AUTH007`), and a verified outcome whose accounting is not settled (`ACC003`). Related cases: `CASE-AUTH-01`, `CASE-AUTH-02`, `CASE-AUTH-03`, `CASE-LIFE-03`.

## What this shows, and what it does not

- **Shows:** an approval that stops being current when its basis changes, an action refused with named reasons, and a receipt that proves a negative.
- **Does not show:** that a real system would notice the correction in time, or that blocking is the right business outcome. It is also not an argument that approvals are unnecessary: the gateway can only refuse what it can check.

[← 07 Authority and delegation](../07-authority-and-delegation/README.md) · [Examples](../README.md) · [Next: 09 Unknown outcome →](../09-unknown-outcome/README.md)
