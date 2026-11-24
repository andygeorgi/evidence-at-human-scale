# 11. Costs and adaptation

[← 10. Degraded operation](10-degraded-operation.md) · [Paper contents](README.md) · [Next: evaluation →](12-evaluation.md)

The design adds engineering and operating work: authorization and coverage checks, versioned state and reference management, invalidation, and a separate commit verification. Whether that work raises or lowers the total cost and latency of a task has to be measured against matched baselines, not assumed in either direction. In return, particular failures can be inspected. Residual risks remain, and the domain has to accept them.

Traceability does not remove source error, and a schema does not replace judgment. A Decision Owner can still misunderstand the evidence. Permission synchronization can lag, conflicts between authorities can persist, and an external commit can offer weaker guarantees than a local reservation. Naming these limits is more honest than letting a product's capability stand in for an end-to-end guarantee.

The tradeoff register in the [ownership, parameters and tradeoffs reference](../../architecture/ownership-and-tradeoffs.md#full-tradeoff-register) names eleven alternatives that the design rejects: a generalized customer solution, agent-first architecture, default multi-agent debate, agent-specific user experiences, completeness theater, model-only prioritization, convenient autonomous execution, unrestricted delegation, cache-only trust, majority/latest wins and a universal deployable stack. Each would obscure a boundary the design preserves. For each rejection the register gives the reason and the cost, and the same reference holds the unresolved owner and parameter requirements.

## Budget the whole task

Task cost includes retrieval, storage, telemetry, evaluation, inference, retries and operations. Token cost is only one part. Limit calls, fanout, retries, elapsed time and spend across the whole task lifecycle. When a budget is exhausted, the behavior must be explicit, such as a visible partial result or a permitted alternative, and never a silent enlargement of authority.

Observability records the declared task scope, selected and excluded coverage, consumption, deadlines, partial completion, invalidations, the delivery state of mandatory notifications and action outcomes. It does not capture hidden reasoning. Telemetry must preserve privacy while still supporting accountable records, and retention should be minimal and fit the authorized purpose.

## Adapt the domain, not the architecture

A deployment keeps the contracts, selection and lineage, information-flow controls, bounded orchestration, one review interaction, independent mandatory routes, separate action authority (the gateway), degraded modes, and an assurance plan. It supplies domain parameters: source authority, jurisdiction, obligations, severity, freshness, safe states, thresholds, risk acceptance, and who can approve or execute.

Each parameter needs an owner, a typed value or an explicit unresolved state, units and scope, a rationale, the evidence or policy behind it, its review and approval state, and the version that applies. An unresolved parameter blocks the deployment decision or operation that depends on it. It does not block publication of the reference architecture, and it never licenses an assistant to invent a value. The [domain parameter catalogue](../../evaluation/catalogue/README.md) lists the 47 parameters this architecture leaves to domain owners; all are UNSET.

## Three hypothetical illustrations

The three examples below are hypothetical and carry equal weight. They are not implementations, deployments, customer evidence, measured results or benefit claims. Each asks the same architectural questions: what is attributable, what is missing, what must reach a person independently, and what authority permits action. None adds a logical component to the architecture.

**Fisheries:** do disagreeing operational records justify an inspection? An owner would review selected observations, rule findings and labeled interpretations, each with its origin and scope visible. The packet would show the conflict and any expected input that was not obtained, and it would not invent a negative. Human review would remain separate from any action authority, while mandatory signals retain their independent authorized route.

**Security:** is an endpoint-containment proposal supported? An analyst would inspect selected signals, conflicting accounts and common-origin summaries, without treating agreement as corroboration and without revealing that a protected record exists. The packet would show gaps and limits for human review. A recommendation would not itself authorize containment. Current execution checks and conservative accounting would govern any permitted action.

**Industrial-regulatory:** does a missing or stale inspection basis permit restart under established native controls? An operator would inspect the available measurements and declared rule findings, with units, method, scope and event time preserved. The packet would show the incomplete basis and not a negative inspection result. Human review and separate authority would remain necessary, and native safety controls keep their established routes.

The fisheries question echoes the originating engagement and its demonstrator assistant. The architecture does not depend on the fisheries domain.

A fourth illustration is worked through in data instead of prose. The [synthetic supplier-payment scenario](../../examples/README.md) asks the same questions in a domain that needs no specialist knowledge. It is synthetic, belongs to no customer and is not one of the three illustrations above.

[← 10. Degraded operation](10-degraded-operation.md) · [Paper contents](README.md) · [Next: evaluation →](12-evaluation.md)
