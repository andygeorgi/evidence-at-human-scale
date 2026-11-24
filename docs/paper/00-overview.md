# Overview

[Paper contents](README.md) · [Next: the scarce resource is human attention →](01-human-attention.md)

A supplier invoice says 100 units, and the goods receipt says 60. The accounts-payable controller, who owns the decision, has to hold the payment or release it. The material comes from several systems and from two AI assistants. Their summaries both say "probably a receiving delay", but both assistants read the same receipt, so the summaries are one opinion. The treasury service did not answer. Part of the requested scope is outside the read permissions of the requestor, the person who asked for it. Later the warehouse finds a second pallet and corrects the receipt to 100 units. Everything built on the first version stops being current.

Agentic systems can increase information production faster than people can increase their attention. More agents can create more interpretations for the controller to read, and more summaries can merely move the bottleneck. The controller is the Decision Owner, the person accountable for the decision. They still have to see what matters, what supports it, what is uncertain and what they are entitled to decide. A fluent answer that blurs those distinctions is not a decision context.

The architecture gives the controller one versioned decision packet instead of a pile of agent output. A claim in the packet cites an exact record version, and an inference is labeled as an inference. Two summaries of one receipt count as one origin. A conflict, a gap or an unavailable source stays in the packet with its reason, in the wording the requestor's permissions allow. A proposal is not an approval, and an approval is not execution. At commit, a gateway rechecks the grant, the evidence, the preconditions and the limits against the current state. When the receipt is corrected, the summaries, the packet and any pending approval built on the first version stop being current.

The reusable unit of the architecture is the decision context, not the agent hierarchy. It consists of authorized, attributable outputs selected for a defined task, synthesized within limits and released as a versioned decision packet. The Decision Owner reviews that packet in one interaction, with its lineage, uncertainty and access restrictions still attached. Mandatory obligations and consequential execution each keep an independent path.

The design comes from a case-based architecture engagement on a public-sector fisheries-control authority in Iceland. Public audit findings and appeal rulings in that domain showed how decisions built on records and automated flags can go wrong. The engagement's own prototype tests on synthetic data showed similar risks for model output. [What the engagement showed](02-engagement.md) maps each observation to the design decision it informed, and [Starting with one decision](14-start-monday.md) gives the first practical steps.

This is a reference architecture, not a production deployment or benefit claim. The contracts and synthetic examples are tested; real-world effectiveness has not been evaluated. The evaluation tests in [chapter 12](12-evaluation.md) are defined, and none has been run. The [architecture reference](../../architecture/README.md) and the [contract reference](../../contracts/README.md) hold the full controls; this paper gives the argument and says what the controls are for.

## How the paper is organized

| Question | Chapter |
| --- | --- |
| What is the problem, and why do more agents not solve it? | [1. The scarce resource is human attention](01-human-attention.md) |
| Where does the design come from? | [2. What the engagement showed](02-engagement.md) |
| What is the architecture? | [3. The reference architecture](03-governed-context.md) |
| What does each piece of evidence carry with it? | [4. Evidence keeps its type and its ancestry](04-evidence-and-lineage.md) |
| What reaches the person, and what is left out? | [5. Context and selection](05-context-and-attention.md) · [6. The decision packet](06-decision-packet.md) · [7. One interaction, several runtimes](07-one-interaction.md) |
| How does the design show what is missing? | [8. Uncertainty is part of the result](08-uncertainty.md) |
| Who may read, approve and execute? | [9. Authority remains a separate boundary](09-authority.md) |
| What happens when something fails? | [10. Information can degrade without widening authority](10-degraded-operation.md) |
| What does it cost, and what must a domain supply? | [11. Costs and adaptation](11-costs-and-adaptation.md) |
| How would it be evaluated? | [12. Evaluate simpler baselines before multi-agent value](12-evaluation.md) |
| Which products could implement it? | [13. Implementation options](13-implementation-options.md) |
| What should I do on Monday? | [14. Starting with one decision](14-start-monday.md) |

The [guided reading paths](../README.md) suggest shorter routes, and the [glossary](../glossary.md) defines the terms used throughout.

[Paper contents](README.md) · [Next: the scarce resource is human attention →](01-human-attention.md)
