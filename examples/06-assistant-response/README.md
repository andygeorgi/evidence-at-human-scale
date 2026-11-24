# 06 Assistant response

[← 05 Decision packet](../05-decision-packet/README.md) · [Examples](../README.md) · [Next: 07 Authority and delegation →](../07-authority-and-delegation/README.md)

*Synthetic. The responses are rendered or written for this repository; no model produced them.*

## Purpose

The requestor usually meets a packet through an assistant's response. This folder shows two things:

1. A **template** can write a faithful response from a packet with no model at all. That is a fallback for when the assistant model is unavailable, and a baseline to compare a model against. See [degraded modes](../10-degraded-modes/README.md).
2. A response can be **checked against its packet** mechanically, in two different ways that answer two different questions. They are set out in [the next section](#two-validations), because the difference decides what a pass means.

The reasoning is in [chapter 7, one interaction](../../docs/paper/07-one-interaction.md) and the [implementation guide](../../docs/implementation-guide.md).

## Two validations

| | CANONICAL RESPONSE VALIDATION | STRUCTURAL FREE-TEXT VALIDATION |
|---|---|---|
| **Applies to** | A response that says a renderer wrote it (`produced_by` starts with `template`). | Every response, whoever wrote it. |
| **What it verifies** | Expected response content against a defined renderer: the response must equal what the renderer writes from its packet, statement by statement. | Named requirements and constraints: citations, figures, status words, labels, uncertainty markers, certainty, and what the response mentions. |
| **What it catches** | Any change, including a reversed conclusion that keeps the figures and the citations: a negated recommendation, a failed match reworded as passed, contradictory prose around correct fields. | The failures the constraints name. Each is listed below. |
| **What it does not do** | Verify the packet. | **Prove that the prose is semantically correct.** A sentence can satisfy every constraint and still mislead. |

A canonical response that differs fails with `RESP101`. If the difference adds or removes a negation, changes a status word or a figure, or opens or closes a conflict, it fails with `RESP102`, which names what changed. A free-form response is not compared with the renderer, because there is no single correct wording to compare with. Only a person, or a comparison with a canonical rendering, can judge what such a response means. No model-based judge is used.

## Files

| File | Written by | Validated as |
|---|---|---|
| [`response-PKT-0417-v1-template.json`](response-PKT-0417-v1-template.json) · [`.md`](response-PKT-0417-v1-template.md) | the template, from packet v1 | canonical and structural; `withdrawn`: packet v1 was invalidated at 13:45, and its advice says it is withdrawn |
| [`response-PKT-0417-v1-model-style.json`](response-PKT-0417-v1-model-style.json) | the author, by hand, to show a paraphrasing response that still conforms. **It is not model output.** | structural only; `withdrawn`, for the same reason |
| [`response-PKT-0417-v2-template.json`](response-PKT-0417-v2-template.json) · [`.md`](response-PKT-0417-v2-template.md) | the template, from packet v2 | canonical and structural; `current` |

A response is a list of statements. Each has a `kind` (`claim`, `inference`, `conflict`, `gap`, `recommendation`, `proposal`, `obligation`, `limitation`), a text, and `refs`: JSON pointers into the packet. The Markdown files are the human-readable rendering. An excerpt of the current one:

```markdown
## What the sources say

- Goods receipt GR-5521 (corrected) records 100 units received: 60 on 2026-11-18 and 40 on 2026-11-20, scanned on 2026-11-23. `[PC-3]`
- Three-way match M3W 2.0 on INV-2026-0417: PASS (invoiced 100 units, received 100 units, variance 0.0%, tolerance 2%). `[PC-4]`

## What could not be checked

- Unavailable: Treasury cash position for 2026-11-23. The cash-position service returned HTTP 503 and did not recover during the retrieval window. Nothing was read or assumed. `[gap 4 (unavailable)]`

## Proposed actions (none is executed or approved)

- Proposed (not executed or approved): ACT-REL-0417 v2, release_payment on invoice INV-2026-0417. `[ACT-REL-0417 v2]`
```

## Where the status comes from

A response never defines its own lifecycle. Whether it is `current` or `withdrawn` is read from the packet it cites: an active packet gives a `current` response, and an invalidated or superseded packet gives a `withdrawn` one, with a reason taken from the packet's own history (when it was invalidated, and which record's correction caused it). The template writes exactly that, and both validations compare the response with it. A response cannot call itself `active` or `historical`, leave its status out, or withdraw itself from an active packet. A withdrawn response carries the packet's own reason and nothing else: exactly that reason, with at most the introduction "This response was withdrawn:". Words added to a reason cannot be checked, so none are allowed, which also rules out another cause or time and a reversed supersession (the corrected receipt superseded by the old one). A withdrawn response also marks its recommendations, proposals and obligations as withdrawn, and none of its statements calls anything current or valid unless the packet items it cites do.

## What the structural constraints require

Every response is held to these. They are named, mechanical tests. None of them proves that a statement means what its packet means.

| Code | A response fails when… |
|---|---|
| `RESP001` | a statement has no text, cites nothing, cites something that does not resolve, or cites an item of the wrong kind (an inference cited as a claim) |
| `RESP002` | a claim, conflict, recommendation or inference contains a figure (with its sign) or a currency (any ISO 4217 code, or a currency sign) that is not in the packet items it cites |
| `RESP003` | an inference is not labeled as one |
| `RESP004` | it drops an inference, conflict, gap, recommendation, proposal or obligation of the packet, omits the packet's coverage limitation, or states fewer than half of the packet's supported claims (rounded up, at least one). A claim counts once however many of its parts are cited, and only when a statement that cites it keeps one of its figures and one of its words, or two of its words if it has no figure: a bare number does not state a claim |
| `RESP005` | a proposal does not say it is not executed or approved, or other wording presents an action as approved or done |
| `RESP006` | its status is not the one its packet's state requires (`withdrawn` for an invalidated or superseded packet, `current` for an active one), or its as-of time is missing or differs from the packet's |
| `RESP007` | it cites a packet that does not exist, or does not name it as a decision packet (`"contract_id": "C04"`) |
| `RESP008` | wording closes what the packet keeps open: "no conflict", "resolved", "nothing is missing", "already reviewed" |
| `RESP009` | a gap statement does not say, in words, the missingness label the packet gives that gap (a statement that is exactly the wording a permission decision allows for an input the reader may not read is not asked to) |
| `RESP010` | uncertainty is dropped: an inference with no limits or hedge, a conflict not called unresolved, a recommendation not called "for review" |
| `RESP011` | it adds certainty ("certainly", "confirmed", "verified", "proves") that the cited items do not state, in a statement or in its label |
| `RESP012` | a claim, inference, conflict, gap, recommendation, proposal or obligation uses a status word (pass, fail, stale, current, superseded, revoked, ...) that the cited items do not use, or negates one that they state plainly ("did not fail" for a failed match), or states plainly one that they negate. A figure keeps its sign: `-18,400.00` is not `18,400.00`. The label of the statement is read the same way as its text. In a withdrawn response, the words `withdrawn` and `current` on advice are its own lifecycle labels and are not compared |
| `RESP013` | a statement, or its label, names a record that the cited items do not rest on. A record is named whole (`GR-552` is not `GR-5521`), and a proposal rests on the action of the proposal its item names |
| `RESP014` | its status is missing, or is anything other than `current` or `withdrawn` |
| `RESP015` | the withdrawal reason is missing, or is not the packet's own: it is not exactly the packet's reason (the introduction "This response was withdrawn:" is the only thing that may be added), it undoes the withdrawal, it names another record or time, or it states a supersession the packet's history does not (such as the old receipt superseding the corrected one); or a response about an active packet carries a withdrawal reason |
| `RESP016` | a withdrawn response phrases a recommendation, proposal or obligation as current advice instead of saying it is withdrawn (advice that says "never withdrawn" or "not superseded" does not say so), takes the withdrawal back in words ("reinstated", "the withdrawal was lifted"), or any statement or label in it calls something current or valid (not negated) more often than the packet items it cites do |
| `RESP017` | a statement about a part of the scope the reader may not read is not exactly the wording the permission decision allows (it may start with the label "Inaccessible:", and it may not carry anything else or share its statement with another gap), its label says more than where the gap is ("gap 3", "gap 3 (inaccessible)") or the permitted wording itself, or it cites a part of the gap (its expected evidence, its scope), alone or beside the gap, instead of the gap itself; or it mentions a part whose existence no decision bound to the reader lets them know |

A response may be shorter than its packet and may paraphrase. It may not drop a conflict or a gap, and it may not add a figure. It may also state fewer of the packet's supported claims, but it has to state at least half of the packet's supported claims (rounded up, and never fewer than one), so that the claims cannot all disappear. A claim is counted once, however many of its parts a response cites, and only when a statement that cites it keeps one of its figures and one of its words (or two of its words, when it has no figure): citing a claim without stating it does not count, and neither does a bare number. That minimum is a documented limit of this reference check, `MIN_CLAIM_COVERAGE` in [`scripts/eahs/response.py`](../../scripts/eahs/response.py); it is not a finding about any model, and it does not say that the claims a response keeps are the important ones. The model-style file paraphrases the claims and groups the gaps, and still conforms. It states the one part of the scope the reader may not read in the permitted wording alone, in a statement of its own, because words added to that statement, or the words of a neighbouring gap, could carry what the reader may not know. The template renders a gap the reader may not know of not at all, and it numbers the gaps it does show in the order shown ("gap 3", "gap 4"), so that the numbering leaves no gap where one was withheld; the `refs` of each statement point into the reader's own packet. That packet is built from the inputs the reader may know about. A packet that still carries an entry for an input its reader may not know exists is not the reader's packet: snapshot validation reports it (`DISC002`), and nothing rendered from it is claimed to be safe, not even the numbers in its `refs`, which would show that an entry sits between two others. The check cannot see restricted detail that a response writes into a statement that does not cite the restricted part; that is what building the view from permitted inputs is for ([permission before disclosure](../../architecture/lineage-selection-disclosure.md#permission-comes-before-disclosure)).

## What each validation does not catch

The constraints look for specific words and patterns, so a change that avoids them passes the structural validation. Two examples from [`tests/test_response.py`](../../tests/test_response.py):

- A recommendation changed to "Do not release payment…", with the same figures and citations, passes the structural constraints. The canonical validation fails it with `RESP102`.
- A conflict statement with the sentence "Please disregard this and rely on the receipt" added passes the structural constraints. The canonical validation fails it with `RESP101`.

Both validations assume the packet is right. The canonical one also assumes the renderer is. The negative cases live in the same test file, including the six that matter most: a negated conclusion with unchanged pointers, an altered status with unchanged numbers, contradictory prose around correct fields, omitted uncertainty, unsupported certainty, and a claim attributed to the wrong source. The first response in the table above, from packet v1, is shown `withdrawn`. The packet decides that, not the response: a response from an invalidated packet cannot stay current, and a response cannot withdraw itself from an active one.

## What this shows, and what it does not

- **Shows:** that attribution, completeness and honest labeling of a response can be tested without reading it, that a response from a renderer can be held to exactly what the renderer writes, and that a no-model fallback is possible.
- **Does not show:** that a real model's response would conform, that conformance makes a response correct, or that requestors prefer it. A structural pass does not prove semantic fidelity; a canonical pass shows only that the response equals the template's output for that packet. Neither says whether the packet is right, and neither is a model evaluation.

[← 05 Decision packet](../05-decision-packet/README.md) · [Examples](../README.md) · [Next: 07 Authority and delegation →](../07-authority-and-delegation/README.md)
