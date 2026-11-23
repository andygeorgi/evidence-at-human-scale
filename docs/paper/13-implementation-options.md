# 13. Azure is an implementation option, not the thesis

[← 12. Evaluation](12-evaluation.md) · [Paper contents](README.md) · [Next: start with one decision →](14-start-monday.md)

The logical architecture is product-independent. Official Azure sources, verified 17 November 2026 UTC, identify implementation options with configuration- and feature-specific qualifications. They are not evidence that this architecture has been deployed or that a product independently establishes source truth, end-user permission, or a legitimate human mandate.

**Disclosure.** The author is employed by Microsoft. The Azure mapping is one implementation example of the product-neutral architecture, not a requirement to use Microsoft technology. This repository is not an official Microsoft publication, and nothing in it implies Microsoft endorsement.

Messaging choices distinguish discrete events, streaming, and work queues. Broker or session delivery, settlement, and transactions do not guarantee exactly-once external business effects. Compute, storage, identity, search, and model hosting can implement responsibilities, but application ownership, admission, source-user authorization, and the separate execution boundary remain necessary.

Microsoft Foundry capabilities need feature-specific maturity checks; managed memory is not an evidence ledger. Azure AI Search application security filters were identified as generally available, while native document ACL/RBAC, indexed SharePoint ACL, Purview-label and token-query features retained preview qualifications. No universal bounded permission-synchronization latency was verified.

Governance and protection controls remain scoped to supported infrastructure and metadata. Foundry evaluation's core portal availability does not make every evaluator or extension generally available. Groundedness assesses against supplied context, not independent source truth. The [implementation options reference](../../architecture/azure-implementation-options.md) carries the full option table, verified claims, URLs, and related qualifications.

Product capabilities change quickly. The qualifications above were verified on 17 November 2026 UTC and are not re-verified by later edits to this repository; check the cited pages before relying on any of them.

[← 12. Evaluation](12-evaluation.md) · [Paper contents](README.md) · [Next: start with one decision →](14-start-monday.md)
