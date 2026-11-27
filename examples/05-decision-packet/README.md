# 05 Decision packet

[← 04 Selection and missingness](../04-selection-and-missingness/README.md) · [Examples](../README.md) · [Next: 06 Assistant response →](../06-assistant-response/README.md)

*Synthetic. The packet, its recommendations and its proposals are invented.*

## Purpose

A decision packet ([C04](../../contracts/c04-decision-packet.md)) is what the Decision Owner reviews, and what the requestor meets through the assistant. It is bound to one exact context and selection, presents supported claims with the evidence behind each, keeps inferences separate and labeled, shows conflicts, uncertainty and gaps, and lists action proposals that are **proposed, not executed**. A packet is a review object, not an approval, an instruction or a truth certificate. See [chapter 6](../../docs/paper/06-decision-packet.md).

<!-- figure:F04:start -->
**Figure F04.** A decision packet (C04) has nine groups, among them supported claims, labeled inferences, conflicts, gaps, obligations and action proposals that are not executed. Tags show which groups point to evidence records, the selection manifest and action proposal records.

<p align="center">
<picture>
<source media="(prefers-color-scheme: dark)" srcset="../../figures/F04-dark.svg">
<img src="../../figures/F04-light.svg" alt="The Decision Owner reviews a decision packet (C04) of nine groups. Tags show that the groups for claims, inferences and conflicts point to evidence records (C02), the groups for coverage and obligations to the selection manifest (C03), and the group for action proposals to action proposal records (C05). A band below names the three contracts that the tags point to." width="400">
</picture>
</p>

<details>
<summary>Text description of Figure F04</summary>

At the top, the Decision Owner reviews, challenges and decides. Below is one decision packet (C04) with nine groups. The first binds the packet to one context, selection and as-of time, and everything below is bound to them. Supported claims each cite an exact record version. Labeled inferences carry method and limits. They are never claims. Recommendations carry the accountable review requirement. Conflicts and uncertainty stay visible and are never settled by majority. Coverage, omissions and gaps use seven missingness labels. Obligations carry priority and mandatory items. Action proposals are proposed and not executed. The review and version history keeps revised versions distinguishable. A tag on a group names what it points to. Supported claims, labeled inferences and conflicts point to evidence records (C02), by exact version, claim or payload pointer, original locator, scope, method and lifecycle. Coverage and obligations point to the selection manifest (C03), which records what was retrieved, kept, excluded and missing. Action proposals point to action proposal records (C05), with evidence, preconditions and accounting. A band under the packet shows the three contracts that the tags name.

[All figures and their descriptions](../../figures/README.md#f04-anatomy-of-a-decision-packet)

</details>
<!-- figure:F04:end -->

## Reading the packet

This table is the human view: what a reader needs from the first version of the packet (`PKT-0417` v1), group by group. The JSON files, listed [below](#files), are the self-contained snapshots that it summarizes ([why both](../../contracts/README.md#json-snapshots-and-human-views)).

| Group | What the first version holds |
|---|---|
| Context and as-of time (G01) | Exact references to the context (`CTX-0417` v1) and the selection (`SEL-0417` v1); as-of 2026-11-23T10:00:00Z, the time that the context and the selection state too. |
| Supported claims (G02) | Seven claims: the invoice, the order, the receipt (60 units), the match result (**FAIL**), the screening, the duplicate check and the policy (`PC-1` to `PC-7`). Each cites an exact record version and claim, or a payload location. A claim that cites a claim says exactly what it says. The match result rests on the whole payload, so its status and every figure in it are checked against that payload. |
| Labeled inferences (G03) | Two, one for each AI summary (`M01`, `M02`). Neither is a supported claim. Each states its method and its limitations, including **common origin**. |
| Recommendations (G04) | Hold the invoice (`REC-0417-1`). Release at 16:00 only if the match passes, screening is current and the invoice is held (`REC-0417-1B`). Each names the accountable review requirement. |
| Conflicts and uncertainty (G05) | The quantity conflict (`CONF-QTY`) carried over from the selection, with the uncertainty "unquantified: the cause is not established". |
| Coverage, omissions, gaps (G06) | The seven gaps of the selection, unchanged, and a visible limitation summary. |
| Obligations (G07) | Why the quantity conflict and the stale screening come first, and a reference to the review obligation (`OBL-0417-REVIEW`), the one obligation of the selection. |
| Action proposals (G08) | The hold and the release, each `proposed`. |
| Review and version history (G09) | `invalidated` at 13:45, with a challenge link to the correction. This is the end-of-day snapshot; at 10:00 it was `awaiting_review`. |

## The proposals

A proposal ([C05](../../contracts/c05-action-proposal.md)) names an exact action, an exact target, typed parameters, the evidence it relies on (exact versions), the policies, the preconditions that must hold **at commit**, the accounting (units and window) and an assessment of risk, effects, limitations and recovery.

- **The hold** relies on the invoice, the goods receipt and the failing match. It does not rely on the screening, so stale screening cannot block a hold. It is covered by a bounded grant (see the [authority and delegation example](../07-authority-and-delegation/README.md)).
- **The release** was proposed while the match was failing. That is deliberate: a proposal can be conditional, and its three preconditions (`PRE-MATCH-PASS`, `PRE-SCREEN-FRESH`, `PRE-INVOICE-HELD`) are re-evaluated at the moment of execution, not at approval time. It needs an exact approval (see the [authority and delegation example](../07-authority-and-delegation/README.md)), and it is blocked at 16:00 because the evidence it cites has been superseded (see the [blocked action example](../08-blocked-action/README.md)).

## Files

| File | What it is |
|---|---|
| [`c04-PKT-0417-v1.json`](c04-PKT-0417-v1.json) | The packet, as a snapshot at the end of the day; it was produced at 10:00. |
| [`c05-ACT-HOLD-0417-v1.json`](c05-ACT-HOLD-0417-v1.json) | Proposal: place a payment hold on the invoice (low risk, reversible). |
| [`c05-ACT-REL-0417-v1.json`](c05-ACT-REL-0417-v1.json) | Proposal: release EUR 18,400.00 at the 16:00 run, **conditional** on three commit-time preconditions. |

## Checks that run here

| Code | Rule | Case that breaks it |
|---|---|---|
| `PKT001` | A claim that cites claims says exactly what they say, in the order cited: for one reference, exactly what that claim says | `CASE-PKT-01` |
| `PKT002` | The packet and its selection bind one context, and the context, the selection and the packet state one as-of time (compared as instants, not as written); the selection reads no time outside the interval of its context | `CASE-PKT-02`, `tests/test_snapshot.py` |
| `PKT003` | Coverage points at the packet's own selection | (checked on the whole set) |
| `PKT004` | A listed proposal is bound to this packet | (checked on the whole set) |
| `PKT005` | A claim that rests on a payload says what the payload holds: it states every pass or fail status and at least one figure of it, no other status or figure, and no figure beside the name of a payload field (such as "invoiced") that is not that field's value | `tests/test_claims.py` |
| `PKT006` | A proposal is bound to the context of the packet that it is bound to | `tests/test_snapshot.py` |
| `PKT007` | A packet cites only records that were available at its as-of time, and none that is derived from an input that was not | `tests/test_snapshot.py`, `tests/test_lineage_integrity.py` |
| `PKT008` | A packet lists only obligations that its selection holds, each once | `tests/test_obligations.py` |
| `PKT009` | A packet carries every obligation of its selection | `tests/test_obligations.py` |
| `KIND002` | A model inference is never a supported claim | `CASE-KIND-02` |
| `COR001` / `COR002` | No independent corroboration without independence | `CASE-COR-02`, `CASE-COR-01` |
| `LIFE003` / `LIFE004` | A packet that cites superseded records, or has a newer version, is not active | `CASE-LIFE-02` |

**One snapshot.** The context, the selection and the packet state one as-of time, and the selection reads no time outside the interval of its context. A packet cites only records that were available at its as-of time: the rule of the commit check, applied at the packet's own time. A record admitted exactly then was available, and so is a derived record only when the records it declares as its parents were. A later correction does not make an earlier packet wrong, and a challenge link may name evidence that came after. A packet carries every obligation of its selection, once, and a proposal rests on the context of its packet. These decision-time checks are separate from the commit-time checks of the [blocked action example](../08-blocked-action/README.md).

**Every reference counts.** A claim cannot escape these checks by citing a payload or by citing several references. Each supporting reference is validated for its record, kind, locator, scope, claim and pointer (`REF001`–`REF003`), a claim that cites several claims must say them all together, and a claim that cites a payload, alone or beside claims, is compared with it as structured values: after the cited claims' own words are taken out, what is left must state the payload's pass or fail status and at least one of its figures, and no figure or status the payload lacks. A figure that follows the name of a payload field ("invoiced 60" where the payload holds 100) must be that field's value, and a minus sign is part of a figure. The comparison is deliberately narrow: it checks the status and the figures, compared exactly, and it does not read prose for meaning. It does not show that a claim is true, or that a sentence that passes means what its sources mean. A claim could say more only with a structured assertion beside its free text, which would change the schema. This reference implementation deliberately leaves that capability outside its current scope.

## What this shows, and what it does not

- **Shows:** a packet whose every claim can be followed to a source, where inference, conflict, gap and proposal are visible and separate.
- **Does not show:** that a reader finds this readable, that it is faster than the current process, or that the packet is the right size. A real packet would be much larger, and its usability is an open evaluation question.

[← 04 Selection and missingness](../04-selection-and-missingness/README.md) · [Examples](../README.md) · [Next: 06 Assistant response →](../06-assistant-response/README.md)
