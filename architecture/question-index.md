# Question index

[Architecture reference](README.md)

Start from a question and find the answer in the paper, the reference pages, the figures and the evaluation tests. All evaluation tests are NOT ASSESSED: none has been run.

| Question | Where it is answered | Figures; evaluation tests |
| --- | --- | --- |
| What is reusable and domain-specific? | Paper: [3. A governed context](../docs/paper/03-governed-context.md); [11. Adapt the domain, not the architecture](../docs/paper/11-costs-and-adaptation.md). Reference: [ownership, parameters and tradeoffs](ownership-and-tradeoffs.md). | F02; EV01–EV12 as applicable |
| Evidence versus inference? | Paper: [4. Evidence keeps its type and its ancestry](../docs/paper/04-evidence-and-lineage.md). Reference: [evidence semantics](evidence-semantics.md); contracts [C02](../contracts/c02-evidence.md) and [C04](../contracts/c04-decision-packet.md). | F03; EV01, EV02, EV03 |
| Canonical paths and controls? | Paper: [3. A governed context](../docs/paper/03-governed-context.md). Reference: [lineage, selection and disclosure](lineage-selection-disclosure.md), [action and degradation](action-and-degradation.md), [ownership](ownership-and-tradeoffs.md). | F02; EV06, EV08, EV09, EV11 |
| Agreement versus independent sources? | Paper: [4. Evidence and lineage](../docs/paper/04-evidence-and-lineage.md). Reference: [lineage, selection and disclosure](lineage-selection-disclosure.md#versioned-ancestry-and-missingness). | F03; EV03, EV04, EV12 |
| Omitted or unavailable evidence? | Paper: [5. Context governs what is selected](../docs/paper/05-context-and-attention.md); [8. Uncertainty is part of the result](../docs/paper/08-uncertainty.md). Contracts [C03](../contracts/c03-selection.md) and [C04](../contracts/c04-decision-packet.md); [lineage, selection and disclosure](lineage-selection-disclosure.md). | F03, F04, F09; EV05, EV06, EV10 |
| What reaches the decision owner? | Paper: [6. The decision packet compresses presentation](../docs/paper/06-decision-packet.md). Contract [C04](../contracts/c04-decision-packet.md); [constraints before ranking](lineage-selection-disclosure.md#constraints-before-ranking-mandatory-continuity). | F04; EV01, EV04, EV05 |
| Who reads, approves, delegates and executes? | Paper: [9. Authority remains a separate boundary](../docs/paper/09-authority.md). Contracts [C01](../contracts/c01-context.md), [C05](../contracts/c05-action-proposal.md), [C06](../contracts/c06-delegation.md), [C07](../contracts/c07-execution-receipt.md); [action and degradation](action-and-degradation.md). | F05, F06; EV06, EV07, EV11 |
| Failure, partial effects and unknown outcomes? | Paper: [10. Information can degrade without widening authority](../docs/paper/10-degraded-operation.md). Reference: [action and degradation](action-and-degradation.md). | F06, F07; EV09, EV10, EV11 |
| Targets versus achieved results? | Paper: [12. Evaluate simpler baselines before multi-agent value](../docs/paper/12-evaluation.md). [Evaluation oracles](../evaluation/oracles.md) and [evaluation guide](../evaluation/README.md). | F08; EV01–EV12 NOT ASSESSED |
| Can fisheries and Azure be removed? | Paper: [11. Adapt the domain, not the architecture](../docs/paper/11-costs-and-adaptation.md); [13. Azure is an implementation option, not the thesis](../docs/paper/13-implementation-options.md). Reference: [ownership](ownership-and-tradeoffs.md), [implementation options](azure-implementation-options.md). | Logical boundaries unchanged |
| Exact fields, schema limits and sources? | Paper: [14. Technical scrutiny and sources](../docs/paper/14-start-monday.md#technical-scrutiny-and-sources). Reference: [evidence semantics](evidence-semantics.md); all 41 groups in the [contract reference](../contracts/README.md); [sources](../references/README.md). | JSON Schema bundle and evaluation catalogue |
| Where did the design come from? | Paper: [2. What the engagement showed](../docs/paper/02-engagement.md). [Sources](../references/README.md), including the [engagement records](../references/engagement-records.md). | Engagement sources only |
| What should an architect do first? | Paper: [14. Start with one decision, not a platform](../docs/paper/14-start-monday.md); [implementation guide](../docs/implementation-guide.md). | EV01–EV12 NOT ASSESSED |

Every contract page lists, at its head, the paper chapters, reference pages, figures and evaluation tests that apply to that contract, and then describes its field groups. The prose in the paper and this reference carries the essential semantics; `schemas/contracts-v1.schema.json` carries the formal structure; the [evaluation catalogue](../evaluation/catalogue/README.md) carries the evaluation tests, fixtures and parameters. Rendered figures are derivatives of their editable sources, not independent masters.

Before adoption a domain needs approved owners and parameters, working authorization, defined failure routes, executed fixtures and a recorded acceptance. A record's provenance does not make it true, and a schema's shape does not make it accurate. Permission-sync lag, external races and finite attention remain.

[← Implementation options](azure-implementation-options.md) · [Architecture reference](README.md)
