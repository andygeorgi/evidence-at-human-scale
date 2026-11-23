# 6. The decision packet compresses presentation

[← 5. Context and attention](05-context-and-attention.md) · [Paper contents](README.md) · [Next: one interaction →](07-one-interaction.md)

C04 Decision packet is a versioned review object bound to the exact context and selection manifest. It presents supported claims with evidence references, separately labeled inferences, recommendations, conflicts, uncertainty, missingness, limitations, and review requirements. It is not an action authorization and it is not an evidence ledger substitute.

<!-- figure:F04:start -->
<!-- figure:F04:end -->

## What the owner needs to see

The first view should make the task and as-of basis clear, expose decision-changing information, and show where the basis is weak or incomplete. The owner can drill back to original evidence, inspect a conflicting account, challenge a claim, and review a revised version. Compression is acceptable only while those routes remain usable.

A recommendation remains visible for consideration, not an instruction that silently executes. The packet can explain why an action may merit attention without claiming the owner has approved it or the executor has completed it. These distinct contracts preserve that boundary.

| Contract | Essential architectural meaning |
| --- | --- |
| [C04 Decision packet](../../contracts/c04-decision-packet.md) | A versioned review context tied to evidence and selection. Not action authorization. |
| [C05 Action proposal](../../contracts/c05-action-proposal.md) | The exact versioned action to consider. Advice is not approval or commit. |
| [C06 Delegation](../../contracts/c06-delegation.md) | A bounded grant for a predefined action class. Current rights, evidence, policy, target state and shared limits still govern commit. |
| [C07 Execution receipt](../../contracts/c07-execution-receipt.md) | Verified outcome. Unknown is unresolved; partial effects count. |

Meaningful review is more than a confirmation click. It requires an identifiable owner, adequate time, evidence inspection, visible dissent and recourse, and an explicit account of what the system did not obtain or assess. The design cannot make those conditions real merely by including a human name in a workflow.

A challenged packet is not overwritten into an apparently continuous truth. Its affected lineage is reassessed, revised versions become distinguishable, and pending approvals relying on invalidated evidence cease to be current. Review history survives only within permission and retention limits. The [C04 contract page](../../contracts/c04-decision-packet.md) defines all decision-packet groups in full.

**See it working:** [a complete decision packet and the assistant response rendered from it](../../examples/README.md).

[← 5. Context and attention](05-context-and-attention.md) · [Paper contents](README.md) · [Next: one interaction →](07-one-interaction.md)
