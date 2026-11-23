# Ownership, domain parameters and tradeoffs

[Architecture reference](README.md) · Paper: [11. The design's costs are deliberate](../docs/paper/11-costs-and-adaptation.md)

## Responsibility, minimal inventory and retention

| Responsibility | Accountable role | Required output / boundary |
| --- | --- | --- |
| Source/admission | Source and registry owners | Producer inventory, permitted kinds, typed provenance, immutable versions, quarantine |
| Authorized context | Information-access owner | Principal/purpose checks before retrieval; authorized coverage |
| Relevance/coverage | Domain-policy/ranking owner | Reasons, obligations, included/excluded disposition, visible gaps |
| Bounded synthesis | Synthesis owner | Typed candidate packet, valid source references, declared partial completion |
| Release/review | Disclosure and decision owners | Current release/view authorization; evidence inspection and challenge |
| Mandatory continuity | Obligation and escalation owners | Independent deterministic routing; acknowledgement distinct from resolution |
| Action | Authority issuer, gateway and target owners | Bounded grants, current commit checks, shared limits, authoritative receipt |
| Feedback/retention | Lifecycle and retention owners | Invalidation of derivatives/approvals; permitted history |

Inventory each source, model and tool by owner, purpose, version, risk, permissions, dependencies, evaluation/change history and retirement state. Release approval, regression evaluation, retirement and independent challenge are lifecycle duties, not model-owned features. Controls are evaluated at each relevant boundary, not assumed from an upstream check.

Meaningful review exposes decision-changing facts, uncertainty, omissions, dissent and recourse, with adequate scrutiny time. It addresses privacy and automation bias, supports drillback and shows verification scope; an approval button or human presence alone proves neither safety nor lawful authority. Retain only minimally appropriate authorized source scope, selected/excluded context, claim graph, packet, observed decision/action, grant, receipt and relevant versions. Do not capture hidden reasoning. Retention/deletion constrain historical preservation, and history views still require current permission. Corrections and challenges are governed feedback, not automatic truth or training signals. Privacy-preserving telemetry must remain compatible with accountable records.

## Domain acceptance and unresolved questions

The architecture retains contracts, selection/lineage, information-flow boundaries, one review experience, bounded orchestration, separate gateway, degraded modes and assurance plan. Domain owners supply ontology, source authority, rules, severity, mandatory obligations, expected evidence, freshness, uncertainty, jurisdiction, current action authority, safe states, retention and outcome thresholds/methods. There is no universal legal policy, severity scale or safe state. All unresolved values remain UNSET; this reference supplies no approval, operational owner name or domain parameter.

The [domain parameter catalogue](../evaluation/catalogue/README.md) records required ID, owner, typed value or explicit unresolved state, units/scope, rationale, authority, version/effective time, fixture mapping and resolution stage. Unresolved parameters do not block architecture publication, but block dependent deployment decisions. Domain owners approve obligations, rules, permissions and safe states. Vocabulary may adapt; canonical IDs and epistemic distinctions do not.

| Open question | Owner role | Required evidence / impact | Stage / status |
| --- | --- | --- | --- |
| OQ01 Domain thresholds | Domain/risk | Approved task/risk thresholds and gold oracles | Before dependent deployment; unresolved |
| OQ02 Safe states | Safety/operations | Authorized native/manual route and failure acceptance | Before operation; unresolved |
| OQ03 Retention | Privacy/retention | Lawful scope, duration, deletion and history-view rules | Before collection; unresolved |
| OQ04 Verification | Domain/target | Authoritative methods, target scope, outcome/no-effect evidence | Before dependent release/action; unresolved |
| OQ05 Source authority | Source/domain | Authority ordering and scoped supersession basis | Before conflict-policy use; unresolved |
| OQ06 Human review | Decision/governance | Actual inspection, dissent, recourse and adequate scrutiny | Before domain acceptance; NOT RUN |
| OQ07 External races | Gateway/target | Atomicity support, race windows, shared capacity and reconciliation | Before unattended action; NOT RUN |
| OQ08 Disclosure and publication requirements of a venue | Author | Applicable disclosure, submission and publication rules of any venue beyond this repository (the repository states its AI assistance in the README) | Before any submission to a venue; unverified |

## Full tradeoff register

| Selected boundary | Rejected alternative | Reason and cost |
| --- | --- | --- |
| Governed decision context | Generalized customer solution | Reuses evidence/selection/action boundaries; domain parameters still require approval. |
| Source-first admission | Agent-first architecture | Attribution precedes interpretation; adds envelope/lifecycle work. |
| Zero specialists initially | Default multi-agent debate | Avoids unjustified work and correlated agreement; specialists need a documented admission case. |
| One interaction contract | Agent-specific user experiences | Unifies inspection without collapsing runtimes; routing stays orchestration's duty. |
| Explicit partial coverage | Completeness theater | Exposes omissions/uncertainty; increases visible review effort. |
| Independent mandatory route | Model-only prioritization | Obligations survive model outage; workload/escalation stay visible. |
| Separate action gateway | Convenient autonomous execution | Separates advice from authority checks; adds bounded-automation administration. |
| Bounded grants | Unrestricted delegation | Limits purpose, effects and cumulative allowance; requires shared accounting/reconciliation. |
| Current boundary checks | Cache-only trust | Rechecks revocation/freshness/disclosure; incurs synchronization/checking costs. |
| Lineage-aware conflicts | Majority/latest wins | Preserves common origin and authority conflict; supersession must be explicit. |
| Documentation contracts | Universal deployable stack | No turnkey assurance; implementation/domain expertise remain necessary. |

These are deliberate mechanisms, not measured benefits. Reconsideration needs matched task/risk evidence, declared denominators, domain acceptance and maintained accountability boundaries. Physical colocation may be efficient, but does not collapse responsibilities or remove checks. The three scenarios in [chapter 11](../docs/paper/11-costs-and-adaptation.md) remain equal-weight illustrations. The fisheries illustration is removable without changing any core contract/path. Engagement observations explain why particular boundaries exist ([chapter 2](../docs/paper/02-engagement.md); sources in the [references](../references/README.md)); they are not evidence that the architecture works. No customer data or approval, and no implementation, repository, infrastructure-as-code, accelerator or deployment of this architecture, is offered as evidence for its claims. The synthetic [examples](../examples/README.md) and the checks that run on them illustrate and test the documentation contracts; they are not evidence that the architecture works either.

[← Action and degradation](action-and-degradation.md) · [Architecture reference](README.md) · [Next: implementation options →](azure-implementation-options.md)
