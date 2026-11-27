# 7. One interaction, several runtimes

[← 6. The decision packet](06-decision-packet.md) · [Paper contents](README.md) · [Next: 8. Uncertainty →](08-uncertainty.md)

One assistant interaction is a review contract: the Decision Owner works with the context, the versioned packets, the evidence, the limitations, the challenges and the action review in one place. The interaction need not be chat-only. It does not mean one model, one runtime or one failure domain. Several models, runtimes and services can sit behind the workspace, and any of them can be unavailable while the workspace is available. If the assistant model is unavailable, for example, the owner can still review from a qualified deterministic template ([chapter 10](10-degraded-operation.md)).

The owner should not have to reconcile one interface per agent, which is why the review is one interaction. That does not make any single model the source of truth for the task. Domain interfaces and native workflows remain available where their own authorized routes are needed.

## Start with zero specialists

Begin with the native or current workflow, deterministic grouping and templates, and simple synthesis with zero specialist agents. A specialist needs a documented task, permission or isolation need. It also needs an evaluated comparison against matched baselines (the same task, risk, scope and acceptance criteria, handled by a simpler alternative). An evidence gap can justify a task, but it cannot justify new authority. The number of specialists is not a quality metric, and basic control must not depend on any specialist.

An optional specialist has bounded inputs, a defined purpose and an output contract. Its fanout, calls, tokens, elapsed time, retries and spend are limited. These limits are set once for the whole task and are shared by its child tasks and specialists. They are not set separately for each child. A specialist's output is untrusted data that returns through admission. A deadline, a missing response or a partial result cannot enlarge authority, and a retry is not a new mandate.

The tradeoff is deliberate. A single review interaction asks the architecture to carry the contracts and limitations, so the owner does not have to infer them from many messages. The cost is explicit coordination and traceability. The proposed benefit is more inspectable context. No gain in speed, accuracy, cost or decision quality is claimed.

[← 6. The decision packet](06-decision-packet.md) · [Paper contents](README.md) · [Next: 8. Uncertainty →](08-uncertainty.md)
