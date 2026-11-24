# 13. Implementation options

[← 12. Evaluation](12-evaluation.md) · [Paper contents](README.md) · [Next: start with one decision →](14-start-monday.md)

Official Azure sources, verified 17 November 2026 UTC, identify implementation options for the architecture's responsibilities. Each option has qualifications that depend on its configuration and features. The sources are not evidence that this architecture has been deployed, and they do not show that a product on its own establishes source truth, end-user permission or a legitimate human mandate.

Messaging options differ by pattern: discrete events, streaming or work queues. Broker or session delivery, settlement and transactions do not guarantee exactly-once external business effects. Compute, storage, identity, search and model hosting can implement other responsibilities, but they do not replace application ownership, admission, source-user authorization or the separate execution boundary.

Microsoft Foundry capabilities need a maturity check feature by feature, and managed memory is not an evidence ledger. Azure AI Search application security filters were identified as generally available. Native document ACL and RBAC, indexed SharePoint ACL, Purview-label and token-query features retained preview qualifications. No universal bound on permission-synchronization latency was verified.

Governance and protection controls remain limited to supported infrastructure and metadata. That the core Foundry evaluation portal is generally available does not make every evaluator or extension generally available. Groundedness is assessed against the supplied context, not against independent source truth. The [implementation options reference](../../architecture/azure-implementation-options.md) has the full option table, the verified claims, the URLs and the related qualifications.

Product capabilities change quickly. The qualifications above were verified on 17 November 2026 UTC. Later edits to this repository do not re-verify them, so check the cited pages before relying on any of them.

[← 12. Evaluation](12-evaluation.md) · [Paper contents](README.md) · [Next: start with one decision →](14-start-monday.md)
