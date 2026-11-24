# 12 Controlled change

[← 11 Late correction](../11-late-correction/README.md) · [Examples](../README.md) · [Next: 13 Evaluation cases →](../13-evaluation-cases/README.md)

*Synthetic. The class, the limits and the review are invented.*

## Purpose

Authority changes. A controller lowers a limit after a risk review. In this architecture a change to a delegation is a **new version of the grant, backed by a decision record**, and it takes effect at the next commit check. The old version stays as history and can no longer be used once the new one is in force. The reasoning is in [chapter 9](../../docs/paper/09-authority.md) and [ownership and tradeoffs](../../architecture/ownership-and-tradeoffs.md).

## Files

| File | What it is |
|---|---|
| [`c02-CHG-LOWVAL-0001-v1.json`](c02-CHG-LOWVAL-0001-v1.json) | A `decision_record`: at 14:30 the AP controller lowered the per-payment limit of the low-value release class from EUR 5,000 to EUR 2,500, following the quarterly payment-risk review. A decision record documents a choice. It validates no observation. |
| [`c06-GRT-CLASS-LOWVAL-v1.json`](c06-GRT-CLASS-LOWVAL-v1.json) | The bounded grant for low-value releases, as issued at 07:45: up to EUR 5,000 per payment and EUR 25,000 a day. |
| [`c06-GRT-CLASS-LOWVAL-v2.json`](c06-GRT-CLASS-LOWVAL-v2.json) | The new version, issued at 14:30: EUR 2,500 per payment, EUR 25,000 a day. Its authority basis is the decision record. |
| [`gateway-scenarios.json`](gateway-scenarios.json) | Four stored evaluations around the change. |

## What changed

| | v1 | v2 |
|---|---|---|
| Issued | 07:45 | 14:30 |
| Authority basis | the AP policy (an external record) | the decision record `CHG-LOWVAL-0001` v1 (a C02 record) |
| Per-payment limit | EUR 5,000 | EUR 2,500 |
| Daily limit | EUR 25,000 | EUR 25,000 |
| Class version | 1 | 2 |
| Grantee | the payment executor (the assistant proposes the payments and holds no grant) | the payment executor |
| Everything else | same actions, same targets, same parameters, same expiry | |

The change is traceable: the new grant points at the decision that justifies it, and the decision says who, when and why. Both versions name the executor as their grantee, so the new version replaces the old one for the same principal and gives the assistant no authority (`ROLE006`–`ROLE008`).

## The four stored evaluations

The evaluations use the corrected release proposal `ACT-REL-0417` v2 as a base and **override the amount in memory** to a small payment, because the low-value class only applies to small amounts. The proposal files on disk are unchanged.

| What is attempted | Decision | Codes | Why |
|---|---|---|---|
| EUR 4,200 at 14:20, before the change | ALLOW | none | Within the original EUR 5,000 limit of version 1. |
| The same payment at 14:40, version 1 presented | BLOCK | `GRANT_SUPERSEDED` | Version 2 has been in force since 14:30. Version 1 can no longer be used. |
| The same payment at 14:40, version 2 presented | BLOCK | `PER_ACTION_LIMIT` | EUR 4,200 exceeds the new per-payment limit of EUR 2,500. |
| EUR 2,000 at 14:40, version 2 | ALLOW | none | A smaller payment still fits inside the new class. |

In this reference check the limit is data on the grant, so the change needs no change to the check itself. How a real gateway picks up a new version, and how quickly, is an implementation question this example does not answer.

## Checks that run here

Stage 2 validates all three records. Stage 4 replays the four evaluations. Stage 3 resolves the authority basis of v2, which is an evidence record, and the decision record's kind and producer (`KIND001`), and checks that each version names a registered executor as its grantee (`ROLE007`).

## What this shows, and what it does not

- **Shows:** a delegation that is changed by versioning, with a justification that can be followed, and a check that applies the version in force.
- **Does not show:** who may change a delegation and how that is itself controlled, what happens to proposals already approved under the old limit, or how to coordinate a change across several gateways.

[← 11 Late correction](../11-late-correction/README.md) · [Examples](../README.md) · [Next: 13 Evaluation cases →](../13-evaluation-cases/README.md)
