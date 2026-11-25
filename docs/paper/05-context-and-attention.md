# 5. Context and selection

[← 4. Evidence and lineage](04-evidence-and-lineage.md) · [Paper contents](README.md) · [Next: the decision packet →](06-decision-packet.md)

Context (C01) records who is asking and for what: the requesting principal, the permitted task and purpose, the relevant entities, the scope, the time and the policy constraints. The workload identity is separate from the requesting principal. Retrieval is authorized against this context before evidence enters model context. Filtering an answer after it has been produced is not enough.

This paper uses "context" in three senses and says which one it means wherever the word could be read another way. The *decision context* is the governed, versioned unit selected for one decision. The *context contract* (C01) records the request. The *model context* is what is placed in front of a model. The [glossary](../glossary.md) keeps them apart.

Selection (C03) records what the system actually considered and retained: the coverage of the authorized retrieval, the evidence selected, the exclusions, the reasons for grouping, the missingness and the constraints. A selected scope is not whole-corpus coverage. The reader must be able to tell an input that was expected but absent from one that was deliberately excluded, inaccessible or outside the retrieval scope. That applies to inputs the reader may know about. An input the reader may not know about has no entry ([chapter 8](08-uncertainty.md)).

## Attention is a budget, and mandatory items come first

The attention policy starts by preventing unnecessary output. Authorization, purpose, lifecycle and mandatory constraints are applied before any discretionary ranking or synthesis. Each item states its reasons in terms of obligation, severity, deadline, task relevance, freshness and uncertainty. A severe signal with low confidence may deserve prominence, but urgency does not make it confident.

Deduplication can merge repeated items that share an origin. It cannot turn repetition into corroboration. Progressive disclosure can move detail out of the main view only while decision-changing evidence, conflicts, uncertainty, omissions and drillback stay visible. A user's preferences can reorder permitted discretionary items. They cannot reorder obligations or change access.

When mandatory items overflow the queue, the system exposes the true authorized workload and escalates ownership. It does not silently cap the queue. A short packet fails if its brevity removes a fact that could change the decision, and a ranking budget does not excuse dropping a required signal.

The context and selection contracts make these choices inspectable. They keep the task scope, the as-of time, the policy references and the relevant versions. They do not claim to reconstruct an unlimited corpus. The [lineage, selection and disclosure reference](../../architecture/lineage-selection-disclosure.md) gives the complete treatment of selection and disclosure, and the [JSON Schema bundle](../../schemas/README.md) carries the formal structure.

[← 4. Evidence and lineage](04-evidence-and-lineage.md) · [Paper contents](README.md) · [Next: the decision packet →](06-decision-packet.md)
