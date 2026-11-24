# Implementation options (Azure)

[Architecture reference](README.md) · Paper: [13. Implementation options](../docs/paper/13-implementation-options.md)

Azure is one implementation example of this product-neutral architecture, not a requirement. This page lists, for each capability the architecture needs, one Azure option and the limits that the cited sources attach to it.

## Optional product mapping

Removing Azure leaves every logical contract and path intact. The first column of the table names a capability the architecture needs, without a product name. The second names one Azure option for it. A different product with an equivalent capability could fill the row, but it would need its own qualification check.

The table records product options and qualifications as the cited sources state them. They were revalidated on 17 November 2026 UTC. They are not new deployment findings. None of the following has been validated: any tenant; any configuration of region, model, tool or SDK; any permission-sync guarantee; any cost, performance, ROI or production readiness. Product capabilities change. Check the cited pages ([sources](../references/azure-sources.md)) before relying on any row.

| Capability needed | One Azure option | Qualification |
| --- | --- | --- |
| Transport | Event Grid, Event Hubs or Service Bus | Event Grid for discrete events, Event Hubs for streaming, Service Bus for work. Broker or session delivery and transactions do not guarantee exactly-once external business effects, and settlement can fail after processing. AZ01. |
| Compute and synthesis | App Service or Container Apps; Azure OpenAI via Microsoft Foundry | Validate the compatibility of region, model, tool, SDK and network. General availability (GA) of the core portal does not establish blanket SDK, runtime, model, tool or network readiness. AZ02. |
| Optional specialists | Agent Framework, or managed or code agents | The admission and authority contracts are unchanged. Named memory and runtime experiences keep their own feature-specific maturity limits. AZ02. |
| Governed records | Storage, Cosmos DB or SQL (candidates) | The application owns a versioned registry. It is not managed agent memory or state. No product is established as an evidence ledger. Do not manipulate system-managed collections directly. AZ02. |
| Retrieval | Azure AI Search | Application security filters are GA. The cited native ACL and RBAC, SharePoint ACL, Purview label and token-query features are in preview. Ordinary service and index RBAC is distinct from these. Permission synchronization depends on the source, and no universal bound on its latency has been verified. AZ03. |
| Identity and network | Entra ID, managed identities, Key Vault, VNet, Private Link, Firewall | The application enforces the source user's rights, the purpose, tenant and session isolation, and conversation ownership. A workload identity is not the source user's authority. AZ02. |
| Governance | Azure Policy and Purview, where supported | These provide the supported infrastructure, metadata, protection and compliance controls. They do not establish the truth of evidence, universal legal compliance or a mandate for human action. AZ04. |
| Operations and evaluation | Monitor, App Insights, Foundry evaluation | Support for datasets, outputs, conversations, traces and custom evaluation is specific to each feature. GA in the portal does not cover every evaluator, SDK or runtime, and rubric and custom facilities are in preview. Groundedness is not source truth, and domain oracles remain separate. AZ02 and AZ05. |

The full source URLs and passage scopes for AZ01–AZ05 are in the [Azure sources](../references/azure-sources.md), and those for REF-JSON01 are in the [guidance and standards](../references/guidance-and-standards.md).

[← Ownership and tradeoffs](ownership-and-tradeoffs.md) · [Architecture reference](README.md) · [Next: question index →](question-index.md)
