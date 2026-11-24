# Examples

One synthetic story, told in thirteen folders. It walks a single decision through the [reference architecture](../architecture/README.md): a supplier invoice that should be paid, a goods receipt that disagrees with it, two assistants that appear to agree, a correction that arrives after an approval, a payment whose outcome is unknown, and a limit that is lowered between a proposal and its payment run.

**Everything here is invented.** The buyer (Calder Works), the supplier (Fenwick Components, `S-1042`), the invoice, the amounts, the dates, the people and the systems do not describe any real organization, person or system. The examples illustrate the [contracts](../contracts/README.md) and give the repository's checks something to run on. They are not evidence that the architecture works. See [Claims and limits](../docs/claims-and-limits.md).

## Run the checks

Python 3.9 or later and one package:

```bash
python -m pip install -r requirements.txt
python scripts/validate_examples.py
```

Expected output:

```text
Evidence at Human Scale 1.0.1: example validation
Synthetic data only. A pass is not evidence about any real system.

[1/6] Schema bundle ...           PASS          102 evaluated
[2/6] Example instances ...       PASS          37 evaluated
[3/6] Scenario semantics ...      PASS          37 evaluated
[4/6] Gateway scenarios ...       PASS          19 evaluated
[5/6] Assistant responses ...     PASS          3 evaluated
[6/6] Evaluation cases ...        PASS          37 evaluated

Result: PASS. All 6 stages passed, each after evaluating at least one item (235 items in all).
```

It is tested on Windows and Linux; nothing in it is platform-specific, so macOS should work too. Add `--verbose` to see what each stage covered, `--only schema,semantics` to run some stages, `--skip cases` to leave one out, or `--json` for a machine-readable result.

A stage passes only if it evaluated something. Run the command on an empty folder and it reports `NOT ASSESSED` and exits with 3; JSON it cannot read is an `INPUT ERROR` (exit 2); a broken example is a `FAIL` (exit 1). Exit code 0 means every stage that ran passed. [`scripts/README.md`](../scripts/README.md#validate_examplespy) has the five states.

| Stage | What it checks |
|---|---|
| Schema bundle | The schema is valid JSON Schema (Draft 2020-12) and its 38 valid and 64 invalid embedded examples behave as labeled. |
| Example instances | Every contract instance in this folder validates against its contract. |
| Scenario semantics | What a schema cannot say: references resolve to the exact version they name, derivation is acyclic, a correction reaches everything built on the corrected record, each missingness label is justified, a pending approval ends when its basis is invalidated, a receipt agrees with what the commit check decides, a summary does not disclose what a record withholds, an output mentions an unreadable source only if its permission decision allows it, and the requestor, the decision owner and the approver stay distinct. |
| Gateway scenarios | 19 stored what-if evaluations of the reference commit check reproduce their recorded decisions, and between them they exercise every reason code. |
| Assistant responses | Each stored response meets the structural constraints (it cites packet items, takes its figures from them, labels inferences, keeps conflicts open and gaps labeled, words proposals as proposals, and is withdrawn when its packet is), and a response written by the template equals what the template renders. |
| Evaluation cases | 37 mutated copies of this example set each produce exactly the check codes they declare. |

If a check fails, the message names a code, the file and location, and the contract page to read. Try it: change a timestamp in any file to `2026-11-23T07:31:00` (no time zone) and run the command again.

### What a pass means, and what it does not

A pass means the synthetic examples are structurally valid, internally coherent, and that the deterministic checks behave as documented. It does not mean any real system, model or process is accountable, safe or correct. These are deterministic functional checks. They are **not** the [EV01–EV12 evaluation programme](../evaluation/README.md), which has not been run, and they are not model evaluation, human-outcome evaluation or production evidence.

## The story

All times are UTC on 2026-11-23 unless stated.

| Time | What happens | Folder |
|---|---|---|
| 11-18 14:05 | Goods receipt `GR-5521` v1 records 60 units for purchase order `PO-77231` (100 ordered) | [01](01-source-records/README.md) |
| 07:30 | Invoice `INV-2026-0417` arrives: 100 units at EUR 184.00, total EUR 18,400.00 | [01](01-source-records/README.md) |
| 07:45 | The controller issues two standing class grants for the day's payment work: place payment holds, and release low-value payments | [07](07-authority-and-delegation/README.md) · [12](12-controlled-change/README.md) |
| 09:35 | The three-way match `M3W-0417` v1 fails: 100 units invoiced against 60 received, a variance of 40% against a tolerance of 2% | [03](03-lineage-and-common-origin/README.md) |
| 09:41–09:44 | Two model summaries both say "probably a receiving delay". Both rest on `GR-5521` v1 alone | [03](03-lineage-and-common-origin/README.md) |
| 09:45–09:59 | Retrieval for the review. The treasury service returns HTTP 503. Part of the requested scope is outside the requestor's read permissions | [04](04-selection-and-missingness/README.md) |
| 10:00 | Context `CTX-0417` v1, selection `SEL-0417` v1 and decision packet `PKT-0417` v1 are produced for the requestor. A first response is written from the packet | [02](02-context-and-normalization/README.md) · [05](05-decision-packet/README.md) · [06](06-assistant-response/README.md) |
| 10:03 | A payment hold is placed on the invoice under a standing class grant. The receipt says `completed_verified` | [07](07-authority-and-delegation/README.md) |
| 10:35 | The controller, who owns the decision, reviews packet v1 | [11](11-late-correction/README.md) |
| 10:40 | The controller gives an exact approval for a conditional release at the 16:00 payment run | [07](07-authority-and-delegation/README.md) |
| 13:30 | Supplier screening is re-run (`SCR-S1042` v2) | [11](11-late-correction/README.md) |
| 13:40 | The warehouse scans the second pallet it received on 11-20. `GR-5521` v2 supersedes v1: 100 units received | [11](11-late-correction/README.md) |
| 13:45 | Both summaries and the packet built on v1 stop being current, and the first approval is revoked. The match result is recomputed and replaced at 13:51 | [11](11-late-correction/README.md) |
| 14:10 | Context v2, selection v2, packet v2 and proposal v2 are produced from the corrected record | [11](11-late-correction/README.md) |
| 14:30 | The controller lowers the per-payment limit of a low-value release class from EUR 5,000 to EUR 2,500 | [12](12-controlled-change/README.md) |
| 15:10 | The controller reviews packet v2 | [11](11-late-correction/README.md) |
| 15:20 | A second exact approval, bound to proposal v2 | [11](11-late-correction/README.md) |
| 16:00:00 | The queued release under the first approval is blocked at commit. Receipt `not_executed_verified` | [08](08-blocked-action/README.md) |
| 16:00:05 | The release under the second approval passes the commit check. The bank interface times out. Receipt `unknown`, allowance reserved | [09](09-unknown-outcome/README.md) |
| 16:07 · 16:20 | The bank books the payment. Reconciliation against the bank statement upgrades the receipt to `completed_verified` | [09](09-unknown-outcome/README.md) |

The [degraded modes](10-degraded-modes/README.md) folder replays the commit check with parts of its input missing. The [evaluation cases](13-evaluation-cases/README.md) break the story on purpose, 37 ways.

## Folder map

The set holds 37 contract instances: 19 evidence records (C02), 2 contexts (C01), 2 selections (C03), 2 decision packets (C04), 3 action proposals (C05), 5 grants and approvals (C06) and 4 execution receipts (C07). Around them are the raw system exports, the registry, the stored what-if evaluations, the responses and the evaluation cases.

| Folder | What it shows | Contracts | Figures |
|---|---|---|---|
| [01 Source records](01-source-records/README.md) | Raw system exports and the evidence records normalized from them | C02 | F02 |
| [02 Context and normalization](02-context-and-normalization/README.md) | Who is asking, for what, as of when, with which restrictions | C01 | F02 · F11 |
| [03 Lineage and common origin](03-lineage-and-common-origin/README.md) | A derived finding, two summaries that share one origin, scoped validation | C02 | F03 |
| [04 Selection and missingness](04-selection-and-missingness/README.md) | One selection that carries all seven missingness labels, a conflict and an obligation | C02 · C03 | F09 |
| [05 Decision packet](05-decision-packet/README.md) | The packet the decision owner reviews, and two proposals that are not executed | C04 · C05 | F04 |
| [06 Assistant response](06-assistant-response/README.md) | A response written from the packet, a response checker, a model-free fallback | (C04) | F04 |
| [07 Authority and delegation](07-authority-and-delegation/README.md) | A standing class grant, an exact approval, the receipt of a hold | C05 · C06 · C07 | F05 |
| [08 Blocked action](08-blocked-action/README.md) | A queued release refused at commit; the receipt that proves nothing happened | C07 | F05 · F06 |
| [09 Unknown outcome](09-unknown-outcome/README.md) | A timeout, a reserved allowance, no blind retry, reconciliation | C07 | F06 |
| [10 Degraded modes](10-degraded-modes/README.md) | The commit check fails closed when it cannot be sure | C06 · C07 | F07 |
| [11 Late correction](11-late-correction/README.md) | A superseding record, invalidated derivatives, a revised packet and a new approval | C02–C06 | F10 |
| [12 Controlled change](12-controlled-change/README.md) | A lowered limit takes effect at the next commit check | C02 · C06 | F05 |
| [13 Evaluation cases](13-evaluation-cases/README.md) | 37 mutated copies with the check codes each must produce | all | F11 |

[Figures](../figures/README.md) F01–F11 are described in the gallery.

## Conventions

- **Files.** Contract instances are named `<contract>-<id>-<version>.json`, for example `c02-INV-2026-0417-v1.json`. Every instance carries `contract_id` and `schema_version`.
- **Snapshots, not event logs.** Each file shows its record as it stands at the end of the day. `GR-5521` v1 therefore shows `superseded`, packet v1 shows `invalidated` and the first approval shows `revoked`. The timestamps inside each record say when each state began. A real store would append the changes as history. Where a past event matters to a check, such as who reviewed a packet before it was invalidated, [`registry.json`](registry.json) keeps its `review_log`.
- **Then and now.** A decision is judged by what was visible when it was made, and the end-of-day file is a later projection. The controller who reviewed packet v1 at 10:35 saw it as `awaiting_review`, resting on `GR-5521` v1, which was then the current receipt. The correction at 13:40 changed what is current from that point on. It did not make the 10:40 approval wrong when it was given; it ended it. Read the timestamps to rebuild what was visible at the time.
- **Versions.** A reference always names an exact version. A newer version never replaces an older one; it supersedes it. A version's content never changes; only its lifecycle state does (for example from `current` to `superseded`).
- **People.** Four roles recur, and the registry names who holds each (`accountability`). The **requestor** (`person:ap-analyst-02`, an AP analyst) asks the assistant for a packet and reads it. The **decision owner**, the accountable reviewer, is the AP controller (`person:ap-controller-01`, who holds `role:ap-controller`): the controller owns the review obligation, reviews each packet and owns the release decision. The **approver** issues the exact approval of one proposal version; here that is the controller too, and the registry says so explicitly, because the example's policy lets one person hold the decision-owner and approver roles together. It does not let the requestor hold either role for their own request. The **executor** is `workload:payment-executor`. Standing class grants are issued in the name of the role, exact approvals by its holder. A different domain's policy might require a separate approver; the checks (`ROLE001`–`ROLE004`) read the registry, not this convention.
- **Registry.** [`registry.json`](registry.json) is the domain's side of the story: registered producers and the evidence kinds each may submit, the external records the contracts name but do not define (access decisions, authority bases, accounting references), the policies with their freshness limits, the commit-time precondition rules, the relationship vocabulary, the terms this requestor may not see, who holds which role and the log of reviews, what each permission decision lets an output say, and the state of the target system over time. It is domain configuration, not part of the contracts.
- **Generated data.** The JSON is generated from one definition by [`scripts/build_example_data.py`](../scripts/build_example_data.py). `python scripts/build_example_data.py --check` fails if a committed file differs from a fresh build, so an edit by hand shows up. The READMEs are written by hand.

## Reading the paper's abstract notation

The paper uses short labels in its figures and text. In this story:

| Paper | Here |
|---|---|
| `S01/v1`, a source record with a quantity | `GR-5521` v1, the goods receipt (60 units) |
| `S02/v1`, a conflicting source record | `INV-2026-0417` v1, the invoice (100 units) |
| `M01`, `M02`, two summaries that share one root | `SUM-A-0417` v1, `SUM-B-0417` v1, listed in the packet as inferences `M01` and `M02` |
| `V01/v1`, a scoped validation | `V-M3W-0417-01` and `V-GR-5521-01`, inside the records they assess |
| `S01/v2`, the correction | `GR-5521` v2 |
| `P01` | `PKT-0417` v1, then v2 |
| the Decision Owner | the controller, `person:ap-controller-01` (see *Conventions*) |
