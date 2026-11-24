# Implementation options (Azure)

[Architecture reference](README.md) · Paper: [13. Azure is an implementation option, not the thesis](../docs/paper/13-implementation-options.md)

## Optional product mapping, not architecture

Azure is one implementation example of this product-neutral architecture, not a requirement.

Removing Azure leaves every logical contract and path intact. The first column of the table names the capability the architecture needs, in product-neutral terms; the second names one Azure option for it. A different product with an equivalent capability could fill the row, and it would need its own qualification check. The following preserves source-scoped product options and qualifications revalidated on 17 November 2026 UTC, not new deployment findings. No tenant, region/model/tool/SDK configuration, permission-sync guarantee, cost, performance, ROI or production readiness has been validated. Product capabilities change; check the cited pages ([sources](../references/azure-sources.md)) before relying on any row.

| Capability needed | One Azure option | Qualification |
| --- | --- | --- |
| Transport | Event Grid / Event Hubs / Service Bus | Discrete events / streaming / work respectively. Broker/session delivery and transactions do not guarantee exactly-once external business effects; settlement can fail after processing. AZ01. |
| Compute/synthesis | App Service / Container Apps; Azure OpenAI via Microsoft Foundry | Validate region/model/tool/SDK/network compatibility. Core portal GA does not establish blanket hosted-runtime maturity. AZ02. |
| Optional specialists | Agent Framework or managed/code agents | Admission/authority contracts unchanged. Named memory/runtime experiences retain feature-specific maturity limits. AZ02. |
| Governed records | Storage / Cosmos DB / SQL candidates | Application-owned versioned registry, not managed agent memory/state. No product evidence ledger established; do not manipulate system-managed collections directly. AZ02. |
| Retrieval | Azure AI Search | Application security filters GA; cited native ACL/RBAC, SharePoint ACL, Purview-label and token-query features preview. Ordinary service/index RBAC differs. Source-specific permission synchronization; no universal bounded latency verified. AZ03. |
| Identity/network | Entra ID / managed identities / Key Vault / VNet / Private Link / Firewall | Application enforces source-user rights, purpose, tenant/session isolation and conversation ownership. Workload identity is not source-user authority. AZ02. |
| Governance | Azure Policy / Purview where supported | Supported infrastructure/metadata/protection/compliance controls, not evidence truth, universal legal compliance or human action mandate. AZ04. |
| Operations/evaluation | Monitor / App Insights / Foundry evaluation | Dataset/output/conversation/trace/custom support is feature-specific. Portal GA does not cover every evaluator/SDK/runtime; rubric/custom facilities preview. Groundedness is not source truth; domain oracles remain separate. AZ02/AZ05. |

The full source URLs and passage scopes for AZ01–AZ05 and REF-JSON01 are on the [sources](../references/azure-sources.md) pages.

[← Ownership and tradeoffs](ownership-and-tradeoffs.md) · [Architecture reference](README.md) · [Next: question index →](question-index.md)
