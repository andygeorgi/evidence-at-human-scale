# The paper

**Evidence at Human Scale: Reference Architecture for Accountable Decisions in Agentic Systems**
Andy Georgi · version 1.0.8 · 27 November 2026

The paper argues that the unit of design for an agentic system is the decision context, not the agent hierarchy: the outputs selected for one decision and released as one versioned decision packet. Each chapter can be read on its own. It links to the contract or reference page that holds the detail and, where one exists, to a worked example. For the argument in short form, read the [ten-minute path](../../README.md#ten-minute-path); to run something first, start with the [examples](../../examples/README.md).

| # | Chapter | Takeaway |
| --- | --- | --- |
| 0 | [Overview](00-overview.md) | The problem in one decision, what the architecture does about it, and what the paper claims and does not claim. |
| 1 | [The scarce resource is human attention](01-human-attention.md) | What a person who must decide still has to know: the source, the scope, the omissions and who owns the decision. More agents, shorter summaries and more automation do not supply it. |
| 2 | [What the engagement showed](02-engagement.md) | Seven dated observations from public records and the author's prototype work, each with its limits and the design decision it informed. |
| 3 | [The reference architecture](03-governed-context.md) | The architecture as nine steps from sources to review, with a separate route for mandatory notifications and a separate route for actions. |
| 4 | [Evidence keeps its type and its ancestry](04-evidence-and-lineage.md) | What each kind of record establishes, how a reference leads back to the exact version used, and why two summaries of one record are not corroboration. |
| 5 | [Context and selection](05-context-and-attention.md) | Why retrieval is authorized before anything reaches a model, and how material is ranked, grouped and shortened without losing an obligation or a conflict. |
| 6 | [The decision packet](06-decision-packet.md) | What the decision packet contains, and what stays reachable however short it is: the sources, the conflicts, the gaps and the difference between a proposal and an approval. |
| 7 | [One interaction, several runtimes](07-one-interaction.md) | Why reviewing in one place does not require a single model or runtime, and why to start with no specialist agents, adding one only for a documented need. |
| 8 | [Uncertainty is part of the result](08-uncertainty.md) | Seven labels for an input that is absent, such as `missing`, `inaccessible` and `stale`, and why they stay separate. Permission comes first: an input the reader may not know exists shows nothing. |
| 9 | [Authority remains a separate boundary](09-authority.md) | Reading, synthesis, approval and execution are separate permissions. An approval is not execution: at commit the gateway checks the current state again. |
| 10 | [Information can degrade without widening authority](10-degraded-operation.md) | What the reader sees when a source is stale or does not answer, or the model is unavailable, and why execution stays closed whenever authority is invalid or uncertain. |
| 11 | [Costs and adaptation](11-costs-and-adaptation.md) | What the design costs in engineering and operations, which alternatives it rejected, what a task's budget has to cover and what a domain has to supply. |
| 12 | [Evaluate simpler baselines before multi-agent value](12-evaluation.md) | How the design would be compared with simpler baselines on matched tasks. The tests are defined, and none has been run. |
| 13 | [Implementation options](13-implementation-options.md) | Which Azure services and features could implement the architecture's responsibilities, with each product fact dated and qualified. |
| 14 | [Starting with one decision](14-start-monday.md) | Five things to do before writing agent code, one late correction walked through, and the decisions that stay with named people. |

Routes by purpose are in the [guided reading paths](../README.md). The terms are defined in the [glossary](../glossary.md); the boundaries of what is claimed are in [claims and limits](../claims-and-limits.md).
