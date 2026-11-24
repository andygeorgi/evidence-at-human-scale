# Implementation guide: start with one decision

[Paper chapter 14](paper/14-start-monday.md) gives five things to do before writing any agent code. This guide turns each into a short working checklist with a template, the contract it maps to and the worked example that shows it. The templates are suggestions for doing the five steps, not part of the contracts.

> **Start small on purpose.** You do not need the full contract set, a platform or a specialist agent on Monday. You need one recurring, consequential decision in which people already struggle to absorb the available evidence.

## Choose the decision

Good candidates have all of these: the decision recurs; people already struggle to absorb the available evidence; an identifiable person is accountable for it; actions can follow from it; and you can replay a recent case. Poor candidates: decisions that have no accountable owner, evidence that is not available to the people who decide, or actions you cannot verify afterwards.

## Step 1 · Write the decision card

**Maps to:** [C01 Context](../contracts/c01-context.md), [C05](../contracts/c05-action-proposal.md), [C06](../contracts/c06-delegation.md). **Example:** [02 Context](../examples/02-context-and-normalization/README.md), [07 Authority](../examples/07-authority-and-delegation/README.md).

| Field | Your entry |
| --- | --- |
| Decision question | |
| Who asks for the packet (the requestor) | |
| Decision Owner (reviews the packet and owns the decision) | |
| Actions that could follow | |
| Who may **read** which evidence, for which purpose | |
| Who may **approve** which actions | |
| Who may **execute** which actions | |

Check: request, review, approve and execute are separate roles, and read, approve and execute are three separate columns of people or services. One person may hold more than one role only where your policy says so; write that down, as the worked example does for its controller. A service identity never grants the requestor rights to every underlying source or the assistant permission to perform every action. A human name in a workflow is not meaningful review; the owner needs time, evidence to inspect, a way to dissent and recourse.

## Step 2 · Inventory the sources and mark the mandatory signals

**Maps to:** [C02 Evidence](../contracts/c02-evidence.md), [C03 Selection](../contracts/c03-selection.md). **Example:** [01 Source records](../examples/01-source-records/README.md).

| Source | Producer | Evidence kind | Version / identity | Owner | Freshness requirement | Mandatory signal? | Deterministic notification route |
| --- | --- | --- | --- | --- | --- | --- | --- |
| | | `source_record_assertion` / `deterministic_finding` / `analytical_result` | | | | yes / no | route that does not depend on the assistant |

Check: every row has an owner and a freshness requirement (or an explicit "unresolved"). Every mandatory signal has a route that works with the assistant switched off. Acknowledgement is receipt, not resolution: keep tracking the obligation.

## Step 3 · Draft the first view of the decision packet

**Maps to:** [C04 Decision packet](../contracts/c04-decision-packet.md). **Example:** [05 Decision packet](../examples/05-decision-packet/README.md), [06 Assistant response](../examples/06-assistant-response/README.md), [04 Missingness](../examples/04-selection-and-missingness/README.md).

Draft it on paper or in a document first. Decide what the reader may know before you decide what is missing. For each input the packet could mention, in this order:

1. May the reader's principal know that the input exists? If not, the packet shows nothing about it: no entry, no state, no count.
2. If the reader may know it exists but may not read it, say so in the wording the permission decision allows, and nothing more.
3. Only for what the reader may know about, classify it: available, missing, stale, conflicting, not assessed or unavailable.
4. Show what the reader is authorized to see.

Then keep five headings, in this order, and never merge them:

1. **Supported claims**, each with the exact record version and claim identifier it rests on.
2. **Labeled inferences**, each marked as an interpretation with its method and limits.
3. **Recommendations** and their basis, clearly not instructions.
4. **Conflicts and gaps**, using the seven labels: `missing`, `not_retrieved`, `inaccessible`, `unavailable`, `negative`, `not_assessed`, `stale` ([how to choose one](paper/08-uncertainty.md)).
5. **Proposed actions**, marked "not executed".

Then walk it through a recent case with the Decision Owner. Ask: what would have changed the decision, and is it visible on the first screen? Two agents that restate one source are one source ([lineage](../architecture/lineage-selection-disclosure.md)).

## Step 4 · Put a gateway in front of every consequential action

**Maps to:** [C05](../contracts/c05-action-proposal.md), [C06](../contracts/c06-delegation.md), [C07 Execution receipt](../contracts/c07-execution-receipt.md). **Example:** [08 Blocked action](../examples/08-blocked-action/README.md), [09 Unknown outcome](../examples/09-unknown-outcome/README.md).

The gateway is a separate step, not a feature of the assistant. At commit it rechecks, and records the result of, each of:

- [ ] the grant or approval is current: not revoked, not expired, bound to this exact proposal version or inside its action class;
- [ ] the evidence the proposal cites is still current (not superseded, withdrawn or revoked) and meets its freshness requirement;
- [ ] policy and preconditions hold;
- [ ] the target is in the state the proposal assumed;
- [ ] the per-action limit and the cumulative limit hold, **including consumed and reserved capacity**.

After the attempt, verify the outcome against the authoritative target, not against the executor's own status. Keep the five receipt states apart: `submitted`, `unknown`, `partial`, `completed_verified`, `not_executed_verified`. An unknown outcome keeps its reservation and is reconciled before any retry. A timeout is never evidence that nothing happened.

## Step 5 · Compare simpler baselines on the same fixed cases

**Maps to:** [evaluation guide](../evaluation/README.md), [oracles](../evaluation/oracles.md), [human-outcome evaluation](../evaluation/human-outcome-evaluation.md).

Run three arms on the same fixed cases before you consider any specialist agent:

1. the current workflow;
2. a deterministic template (grouping and fixed layout, no model);
3. a simple synthesis with zero specialists.

Record, for each arm and case: omissions against a gold list, the evidence the owner actually inspected, time and cost, each with its declared denominator. Declare B_time and B_cost first and write the comparison down before you run it. Do not measure fluency or the number of agents. A specialist is justified only by a documented task, permission or isolation need and a matched comparison. The evaluation guide defines 12 tests and their fixtures, and none has been run, so your first run would be the first.

## What to leave out on Monday

The full contract set; specialist agents; autonomous action; any claim that the architecture works. The paper states the same limit: [where the architecture stops](paper/14-start-monday.md#where-the-architecture-stops).

## Check yourself

Run the worked example, then break it on purpose:

```bash
python scripts/validate_examples.py
```

Open one file in [`examples/`](../examples/README.md), change a version number in a reference or delete a required field, and run the command again. The failure message names the file, the check and the page that explains it.
