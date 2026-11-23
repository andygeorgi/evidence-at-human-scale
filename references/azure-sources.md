# Azure sources (AZ01–AZ05)

These are the official sources behind the optional [implementation options](../architecture/azure-implementation-options.md). They were revalidated on 17 November 2026 UTC. They describe product options and qualifications, not new deployment findings, and product capabilities change: check the pages before relying on them.

## AZ01 · Transport

Microsoft Learn, *Compare Azure messaging services*. Passage scope: Choose a candidate service; discrete events, streams and enterprise messages. Transaction source: Operations that do not enlist in transaction scopes. Settlement source: Settling receive operations. Downstream resources are not automatically in broker transactions; failed settlement can cause redelivery. No exactly-once external-effects guarantee.

- <https://learn.microsoft.com/en-us/azure/service-bus-messaging/compare-messaging-services>
- <https://learn.microsoft.com/en-us/azure/service-bus-messaging/service-bus-transactions>
- <https://learn.microsoft.com/en-us/azure/service-bus-messaging/message-transfers-locks-settlement>

## AZ02 · Application, models, storage and identity

Microsoft Azure Architecture Center, *Baseline Microsoft Foundry chat architecture*. Passage scope: Components; Alternatives; Conversation isolation; Dependency isolation; Model and tool selection. Feature maturity scope: Feature readiness at GA. Hosted agents scope: Protocols; Sessions/conversations/state store; Private networking. Application alternatives, managed state and model/tool compatibility are configuration-specific. Service-managed agent state is not an evidence ledger; end-user source rights and conversation ownership remain application responsibilities. Core portal Agents/Evaluations GA is not blanket SDK/runtime/model/tool/network readiness; Memory and named experiences retain preview limits. Baseline footer date was not captured; actual revalidation date was 17 November 2026.

- <https://learn.microsoft.com/en-us/azure/architecture/ai-ml/architecture/baseline-microsoft-foundry-chat>
- <https://learn.microsoft.com/en-us/azure/foundry/concepts/general-availability>
- <https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/hosted-agents>

## AZ03 · Document-level permissions

Microsoft Learn, *Document-level access control in Azure AI Search*. Passage scope: Approaches; Choose an approach. SharePoint source: Supported permission model; Limitations; Synchronize permissions. Token/RBAC source: Prerequisites; Limitations. Preview terms: Access and permissions. Application security filters are GA string matching with trusted user/group filters. Native POSIX ACL/RBAC scopes, indexed SharePoint ACLs, Purview-label ingestion/enforcement and token-query enforcement remain preview. Ordinary service/index RBAC is distinct.

Unique-item SharePoint refresh depends on supported successful indexer runs; inherited parent changes need explicit refresh. ADLS Gen2 ACL changes need resync; push indexing needs updates/reingestion. No universal bounded sync latency is verified. The cited SharePoint model does not support every source permission mode: guest users, public/org-wide links, Information Management policies and Entra groups nested inside SharePoint groups are unsupported. Purview labels are separate and have feature-specific prerequisites.

- <https://learn.microsoft.com/en-us/azure/search/search-document-level-access-overview>
- <https://learn.microsoft.com/en-us/azure/search/search-indexer-sharepoint-access-control-lists>
- <https://learn.microsoft.com/en-us/azure/search/search-query-access-control-rbac-enforcement>
- <https://learn.microsoft.com/en-us/azure/search/search-preview-terms>

## AZ04 · Governance

Microsoft Cloud Adoption Framework, *AI agent architecture governance*. Passage scope: Landing zones; Centralized control; Data governance; Security governance. Related unified-platform guidance: Data inventory; Compliance; Data security. Accountable owner/risk inventory includes supplemental coverage outside bounded registries. Policy/Purview govern supported infrastructure and metadata/protection/compliance scope, not evidence truth, universal access, legal compliance or human delegation authority. Delegated authentication is not human action-authority evidence.

- <https://learn.microsoft.com/en-us/azure/cloud-adoption-framework/ai-agents/architecture-governance>
- <https://learn.microsoft.com/en-us/azure/cloud-adoption-framework/data/data-governance-unified-data-platform>

## AZ05 · Evaluation

Microsoft Learn, *Evaluation overview*. Passage scope: Build an evaluation workflow; Components. Built-in evaluator scope: Categories; Evaluation levels. General-purpose scope: Introduction; Configure and run evaluators. Custom evaluator scope: Evaluator types; Limits; Endpoint evaluators. Dataset/generated-output/trace and turn/conversation support is evaluator-specific. Core portal GA does not imply every evaluator/extension GA; rubric/custom and named agent/RAG facilities retain preview qualifications. Unmarked entries were not inferred GA. Fluency/coherence is writing quality, not independent factual correctness. Groundedness compares supplied context, not source truth/authenticity. Custom scoring can implement selected tests but cannot supply authoritative domain oracles automatically.

- <https://learn.microsoft.com/en-us/azure/foundry/concepts/evaluation-overview>
- <https://learn.microsoft.com/en-us/azure/foundry/concepts/built-in-evaluators>
- <https://learn.microsoft.com/en-us/azure/foundry/concepts/evaluation-evaluators/general-purpose-evaluators>
- <https://learn.microsoft.com/en-us/azure/foundry/concepts/evaluation-evaluators/custom-evaluators>

[Sources](README.md)
