# 11. The design's costs are deliberate

[← 10. Degraded operation](10-degraded-operation.md) · [Paper contents](README.md) · [Next: evaluation →](12-evaluation.md)

Authorization and coverage checks, versioned state and reference management, invalidation, and separate commit verification entail engineering and operational overhead. Their effect on total task cost and latency must be evaluated against matched baselines, not assumed higher or lower. These deliberate mechanisms make particular failures inspectable while leaving residual risks for domain acceptance.

Traceability does not eliminate source error; schemas do not replace judgment; a human owner can still misunderstand evidence. Permission synchronization can lag, authority conflicts can persist, and external commits can remain weaker than local reservations. A design that names these limits is more honest than one that makes a product's capability stand in for an end-to-end guarantee.

## Budget the whole task

Task cost includes retrieval, storage, telemetry, evaluation, inference, retries, and operations. Token cost is only one component. Bound calls, fanout, retries, elapsed time, and spend across the lifecycle. Budget exhaustion must have an explicit behavior, including a visible partial result or a permitted alternative, never a silent enlargement of authority.

Observability records declared task scope, selected and excluded coverage, consumption, deadlines, partial completion, invalidations, mandatory delivery state, and action outcomes. It does not capture hidden reasoning. Telemetry must be privacy-preserving while still supporting accountable records, and retention should be minimal and appropriate to the authorized purpose.

The rejected alternatives are therefore meaningful: agent-first organization, unrestricted ranking, apparent consensus, a single model dependency, approval-only execution, and independent per-child spending all obscure a boundary the design preserves. The complete 11-row tradeoff set remains in the [ownership, parameters and tradeoffs reference](../../architecture/ownership-and-tradeoffs.md), alongside the unresolved owner and parameter requirements.

## Adapt the domain, not the architecture

A deployment keeps the evidence and selection contracts, lineage, information-flow controls, bounded orchestration, one review interaction, independent mandatory routes, and separate action authority. It supplies domain parameters: source authority, jurisdiction, obligations, severity, freshness, safe states, thresholds, risk acceptance, and who can approve or execute.

Each parameter needs an owner, typed value or explicit unresolved state, units and scope, rationale, evidence or policy, review and approval state, and relevant version. An unresolved parameter blocks the decision that depends on it. It does not license an assistant to invent a value. The [domain parameter catalogue](../../evaluation/catalogue/README.md) lists the 47 parameters this architecture leaves to domain owners; all are unresolved.

## Three parallel illustrations

The following are equally weighted hypothetical examples, not implementations, customer evidence, or measured results. Each asks the same architectural questions: what is attributable, what is missing, what must reach a person independently, and what authority permits action? None supplies a new logical component.

**Fisheries:** do disagreeing operational records justify an inspection? An owner would review selected observations, rule findings, and labeled interpretations, with each origin and scope visible. The packet would show conflict and expected input not obtained, rather than invent a negative. Human review would remain separate from any action authority, while mandatory signals retain their independent authorized route.

**Security:** is an endpoint-containment proposal supported? An analyst would inspect selected signals, conflicting accounts, and common-origin summaries, without treating agreement as corroboration or leaking protected existence. The packet would expose gaps and limits for human review. A recommendation would not itself authorize containment; current execution checks and conservative accounting would govern any permitted action.

**Industrial-regulatory:** does a missing or stale inspection basis permit restart under established native controls? An operator would inspect the available measurements and declared rule findings, preserving units, method, scope, and event time. The packet would expose the incomplete basis, not a negative inspection result. Human review and separate authority would remain necessary; native safety controls keep their established routes.

These are hypothetical questions, not deployments or benefit claims. The fisheries question echoes the originating engagement and its demonstrator assistant; the architecture does not depend on the fisheries domain.

A fourth illustration is worked through in data rather than prose: the [synthetic supplier-payment scenario](../../examples/README.md) applies the same questions to a domain that needs no specialist knowledge. It is synthetic, belongs to no customer and is not one of the three illustrations above.

[← 10. Degraded operation](10-degraded-operation.md) · [Paper contents](README.md) · [Next: evaluation →](12-evaluation.md)
