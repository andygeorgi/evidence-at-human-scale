# Ownership, domain parameters and tradeoffs

[Architecture reference](README.md) · Paper: [11. Costs and adaptation](../docs/paper/11-costs-and-adaptation.md)

Each responsibility in the architecture belongs to an owner role with a required output. This page lists those responsibilities and what a domain must supply before the architecture can be used. It also lists the open questions with the stage by which each must be answered, and it records the tradeoffs: the boundaries the design chose, the alternatives it rejected and what each choice costs.

## Responsibility, minimal inventory and retention

| Responsibility | Owner | Required output and boundary |
| --- | --- | --- |
| Source and admission | Source and registry owners | Producer inventory, permitted kinds, typed provenance, immutable versions, quarantine |
| Authorized context | Information-access owner | Principal and purpose checks before retrieval; authorized coverage |
| Relevance and coverage | Domain-policy and ranking owner | Reasons, obligations, the included or excluded disposition of each item, visible gaps |
| Bounded synthesis | Synthesis owner | Typed candidate packet, valid source references, declared partial completion |
| Release and review | Disclosure owners and Decision Owners | Current authorization to release and to view; evidence inspection and challenge |
| Mandatory continuity | Obligation and escalation owners | Independent deterministic routing; acknowledgement kept distinct from resolution |
| Action | Approver, gateway and target owners | Bounded grants, current checks at commit, shared limits, authoritative receipt |
| Feedback and retention | Lifecycle and retention owners | Invalidation of derivatives and approvals; permitted history |

Keep an inventory of every source, model and tool, with its owner, purpose, version, risk, permissions, dependencies, evaluation and change history, and retirement state. Release approval, regression evaluation, retirement and independent challenge are lifecycle duties, not features of a model. Evaluate each control at the boundary where it applies. Do not assume it from an upstream check.

A review is meaningful when it shows the Decision Owner the facts that could change the decision, the uncertainty, the omissions, any dissent and the available recourse, and leaves enough time to scrutinize them. It must address privacy and automation bias, support drillback and show the scope of the verification. An approval button, or the presence of a person, proves neither safety nor lawful authority.

Retain only what is minimally appropriate: the authorized source scope, the selected and excluded context, the claim graph, the packet, the observed decision and action, the grant, the receipt and the relevant versions. Do not capture hidden reasoning. Retention and deletion rules limit how much history is preserved, and a view of history still requires current permission. A correction or a challenge is handled as feedback under the lifecycle owner. It is not automatic truth, and it is not an automatic training signal. Telemetry must preserve privacy and remain compatible with the records kept for accountability.

## Domain acceptance and unresolved questions

Every deployment keeps the same parts: the seven contracts, selection and lineage, the controls on information flow, limits on calls, time and spend for the whole task, one review interaction, the notification route that does not depend on the assistant, a separate gateway for actions, the degraded modes and an assurance plan. Domain owners supply the ontology, source authority, rules, severity, mandatory obligations, expected evidence, freshness, uncertainty, jurisdiction, current action authority, safe states, retention, and the thresholds and methods for outcomes. There is no universal legal policy, severity scale or safe state. Every unresolved value stays UNSET. This reference supplies no approval, no name of an operational owner and no domain parameter.

The [domain parameter catalogue](../evaluation/catalogue/README.md) records, for each parameter, its ID, name, required type, units and scope, rationale and the tests that use it. Every parameter is UNSET, and the catalogue gives none of them an approval, an owner or a value. An unresolved parameter does not block publication of the architecture. It does block the deployment decision or operation that depends on it. Domain owners approve obligations, rules, permissions and safe states. A domain may adapt the vocabulary. It may not change the canonical IDs or the epistemic distinctions.

These questions are open. Each has an owner role and a stage by which it must be answered:

| Open question | Owner role | Required evidence and impact | Stage and status |
| --- | --- | --- | --- |
| OQ01 Domain thresholds | Domain and risk | Approved task and risk thresholds, and gold oracles | Before dependent deployment; unresolved |
| OQ02 Safe states | Safety and operations | An authorized native or manual route, and failure acceptance | Before operation; unresolved |
| OQ03 Retention | Privacy and retention | Lawful scope, duration, deletion and history-view rules | Before collection; unresolved |
| OQ04 Verification | Domain and target | Authoritative methods, target scope, and evidence of an outcome or of no effect | Before the dependent release or action; unresolved |
| OQ05 Source authority | Source and domain | Authority ordering and scoped supersession basis | Before the conflict policy is used; unresolved |
| OQ06 Human review | Decision and governance | Actual inspection, dissent, recourse and adequate scrutiny | Before domain acceptance; NOT ASSESSED |
| OQ07 External races | Gateway and target | Atomicity support, race windows, shared capacity and reconciliation | Before unattended action; NOT ASSESSED |

## Full tradeoff register

| Selected boundary | Rejected alternative | Reason and cost |
| --- | --- | --- |
| Governed decision context | Generalized customer solution | Reuses the evidence, selection and action boundaries; domain parameters still require approval. |
| Source-first admission | Agent-first architecture | Attribution precedes interpretation; adds envelope and lifecycle work. |
| Zero specialists initially | Default multi-agent debate | Avoids unjustified work and correlated agreement; specialists need a documented admission case. |
| One interaction contract | Agent-specific user experiences | Unifies inspection without collapsing runtimes; routing stays orchestration's duty. |
| Explicit partial coverage | Completeness theater | Exposes omissions and uncertainty; increases visible review effort. |
| Independent mandatory route | Model-only prioritization | Obligations survive a model outage; workload and escalation stay visible. |
| Separate action gateway | Convenient autonomous execution | Separates advice from authority checks; adds the administration of bounded automation. |
| Bounded grants | Unrestricted delegation | Limits purpose, effects and cumulative allowance; requires shared accounting and reconciliation. |
| Current boundary checks | Cache-only trust | Rechecks revocation, freshness and disclosure; incurs synchronization and checking costs. |
| Lineage-aware conflicts | Majority/latest wins | Preserves common origin and authority conflict; supersession must be explicit. |
| Documentation contracts | Universal deployable stack | No turnkey assurance; implementation and domain expertise remain necessary. |

These mechanisms are deliberate. They are not measured benefits. Reconsidering a rejected alternative needs evidence matched on task and risk, declared denominators, domain acceptance, and accountability boundaries that stay in place. Colocating components physically may be efficient. It does not merge their responsibilities or remove their checks.

The three scenarios in [chapter 11](../docs/paper/11-costs-and-adaptation.md) show the same boundaries in different domains. No contract or path depends on any one of them. The engagement observations explain why particular boundaries exist ([chapter 2](../docs/paper/02-engagement.md); sources in the [references](../references/README.md)). The synthetic [examples](../examples/README.md) and the checks that run on them illustrate and test the documentation contracts. Neither the observations nor the examples and checks are evidence that the architecture works. No customer data or customer approval is offered as evidence for the architecture's claims, and neither is any implementation, repository, infrastructure-as-code, accelerator or deployment of this architecture.

[← Action and degradation](action-and-degradation.md) · [Architecture reference](README.md) · [Next: implementation options →](azure-implementation-options.md)
