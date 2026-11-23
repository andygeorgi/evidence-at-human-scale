# 06 Assistant response

[← 05 Decision packet](../05-decision-packet/README.md) · [Examples](../README.md) · [Next: 07 Authority and delegation →](../07-authority-and-delegation/README.md)

*Synthetic. The responses are rendered or written for this repository; no model produced them.*

## Purpose

The reviewer usually meets a packet through an assistant's response. This folder shows two things:

1. A **template** can write a faithful response from a packet with no model at all. That is a fallback for when the assistant model is unavailable, and a baseline to compare a model against. See [degraded modes](../10-degraded-modes/README.md).
2. Any response, whoever wrote it, can be **checked against its packet** mechanically: is each statement attributable, do its figures come from the packet, is an inference labeled, is anything the packet flagged left out?

The reasoning is in [chapter 7, one interaction](../../docs/paper/07-one-interaction.md) and the [implementation guide](../../docs/implementation-guide.md).

## Files

| File | Written by | Status |
|---|---|---|
| [`response-PKT-0417-v1-template.json`](response-PKT-0417-v1-template.json) · [`.md`](response-PKT-0417-v1-template.md) | the template, from packet v1 | `withdrawn`: packet v1 was invalidated at 13:45 |
| [`response-PKT-0417-v1-model-style.json`](response-PKT-0417-v1-model-style.json) | the maintainers, by hand, to show a paraphrasing response that still conforms. **It is not model output.** | `withdrawn`, for the same reason |
| [`response-PKT-0417-v2-template.json`](response-PKT-0417-v2-template.json) · [`.md`](response-PKT-0417-v2-template.md) | the template, from packet v2 | `current` |

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

## What the checker requires

| Code | A response fails when… |
|---|---|
| `RESP001` | a statement cites nothing, cites something that does not resolve, or cites an item of the wrong kind (an inference cited as a claim) |
| `RESP002` | a claim, conflict, recommendation or inference contains a figure that is not in the packet items it cites |
| `RESP003` | an inference is not labeled as one |
| `RESP004` | it drops an inference, conflict, gap, recommendation, proposal or obligation of the packet, or omits the packet's coverage limitation |
| `RESP005` | a proposal does not say it is not executed or approved, or other wording presents an action as approved or done |
| `RESP006` | it is `current` but its packet has been invalidated, or its as-of time differs |
| `RESP007` | it cites a packet that does not exist |

A response may be shorter than its packet and may paraphrase. It may not drop a conflict or a gap, and it may not add a figure. The model-style file paraphrases the claims and groups the gaps, and still conforms.

The negative cases for these rules live in [`tests/test_response.py`](../../tests/test_response.py). The first response in the table above, from packet v1, is shown `withdrawn`; the check requires exactly that, because a response from an invalidated packet must not stay current.

## What this shows, and what it does not

- **Shows:** that attribution, completeness and honest labeling of a response can be tested without reading it, and that a no-model fallback is possible.
- **Does not show:** that a real model's response would conform, that conformance makes a response correct, or that reviewers prefer it. The checker compares a response with its packet. It says nothing about whether the packet is right, and it is not a model evaluation.

[← 05 Decision packet](../05-decision-packet/README.md) · [Examples](../README.md) · [Next: 07 Authority and delegation →](../07-authority-and-delegation/README.md)
