# 5. Context governs what is selected

[← 4. Evidence and lineage](04-evidence-and-lineage.md) · [Paper contents](README.md) · [Next: the decision packet →](06-decision-packet.md)

C01 Context identifies the requesting principal, permitted task and purpose, relevant entities, scope, time, and policy constraints. The workload identity is separate. Retrieval is authorized for that context before evidence enters model context, not merely filtered after an answer has been produced. Selection then records what the system actually considered and retained.

C03 Selection binds authorized retrieval coverage to selected evidence, exclusions, grouping reasons, missingness, and constraints. A selected scope is not whole-corpus coverage. The reader must be able to distinguish an input that was expected but absent from one deliberately excluded, inaccessible, or outside the retrieval scope.

## Attention is a governed budget

Attention policy begins by preventing unnecessary production. Authorization, purpose, lifecycle, and mandatory constraints come before discretionary ranking and synthesis. Item-level reasons expose obligation, severity, deadline, task relevance, freshness, and uncertainty. A severe low-confidence signal may deserve prominence; urgency is not confidence.

Deduplication can reduce repeated presentation by common origin, but cannot relabel repetition as corroboration. Progressive disclosure can move detail out of the main view only when decision-changing evidence, conflict, uncertainty, omissions, and drillback remain visible. User preferences may reorder permitted discretionary items, not obligations or access.

Mandatory overflow exposes the true authorized workload and escalates ownership rather than silently capping the queue. A short packet is not successful if its brevity removes a fact that could change the decision. Likewise, a ranking budget does not excuse discarding a required signal. Finite attention must be managed, not treated as a reason to hide obligations.

The context and selection contracts make these choices inspectable. They preserve task scope, as-of information, policy references, and relevant versions rather than claiming to reconstruct an unlimited corpus. The [lineage, selection and disclosure reference](../../architecture/lineage-selection-disclosure.md) supplies the complete selection and disclosure treatment; the [JSON Schema bundle](../../schemas/README.md) carries the formal structure.

[← 4. Evidence and lineage](04-evidence-and-lineage.md) · [Paper contents](README.md) · [Next: the decision packet →](06-decision-packet.md)
