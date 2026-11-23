# Glossary

Terms are used as the [paper](paper/README.md) and the [contracts](../contracts/README.md) use them. Where a word has more than one meaning in the sources, each meaning is listed and kept apart.

| Term | Meaning |
| --- | --- |
| **Accountable approver** | The person who authorizes an exact proposal or issues a bounded grant (C06 `issuer`). The requestor and the accountable approver are distinct roles in the model, and no contract treats them as the same. One person may hold both only where the domain's policy explicitly permits it; the separation of roles is a domain parameter (DP022, UNSET). |
| **Acknowledgement** | A record that a mandatory notification was received. It is receipt, not resolution; the obligation remains tracked. |
| **Admission** | The step at which a registered producer's record enters the registry. It establishes that the envelope and kind are admissible, never that the content is true. *Assistant-mediated admission* is admission through the assistant workspace and the governed registry; existing native safety controls keep their own authorized routes outside it. |
| **Authoritative target** | The system whose own state decides what actually happened. A receipt is verified against it, not against the executor's status. |
| **B_time, B_cost** | The task time budget (critical path) and the cost budget (full task lifecycle) declared before deployment. |
| **Bounded grant** | A C06 delegation that authorizes a predefined action class within explicit scope, limits and lifecycle, without a fresh approval for each instance. |
| **C01–C07** | The seven contracts: C01 Context, C02 Evidence, C03 Selection, C04 Decision packet, C05 Action proposal, C06 Delegation and C07 Execution receipt. See the [contracts](../contracts/README.md). |
| **Child task** | A task or specialist that the orchestration starts for part of a larger task. Calls, tokens, time, retries and spend are limited once, across the whole task, and shared by its child tasks; they are not set independently for each child. |
| **Claim reference / payload reference** | The two tagged alternatives for pointing at evidence. A claim reference names the exact record version and claim ID; a payload reference names the exact version and an explicit payload location and never invents a claim ID. |
| **Commit** | The moment an action takes effect. The executor rechecks current permission and revocation, evidence, policy, target state and per-action and cumulative limits at commit; approval does not replace those checks. |
| **Common origin** | Two derivations that share a root record. Their agreement is not independent corroboration. |
| **Confirmed-effect policy** | The documented policy under which allowance may be restored: only on authoritative reconciliation, never on timeout or lease expiry alone. |
| **Context** | Three meanings, kept apart. *Decision context*: the governed, versioned unit of information selected for one decision. *C01 Context*: the contract that records the requesting principal, task, purpose, entities, time and policy. *Model context*: what is placed in front of a model, which must only contain evidence the principal was already authorized to read. |
| **Control plane** | The set of controls that constrain every stage and path: identity, authorization, purpose, domain policy, source/model/tool inventory, freshness, budgets and delegation. |
| **Decision Owner** | The person accountable for the decision. |
| **Decision packet** | The C04 versioned review object bound to an exact context and selection. It separates supported claims, labeled inferences, recommendations, conflicts, uncertainty, gaps, obligations and unexecuted proposals. It is not an action authorization. |
| **Deterministic finding** | A C02 record that reports a declared rule, at a stated version, over stated inputs. |
| **Documentation contract** | One of the seven contracts C01–C07. It states what a unit of information must carry and how it is referenced, in prose and in the schema bundle. It is documentation, not a deployable interface: the schema checks structure only, and implementation and domain expertise remain necessary. |
| **Domain parameter** | A value the domain owner must supply (source authority, freshness, safe states, thresholds and so on). An unresolved parameter blocks the deployment decision or operation that depends on it. It does not block publication of the reference architecture, and it never licenses an assistant to invent a value. |
| **EN01–EN05** | The five public records the paper cites, all from Icelandic public authorities. Each is a dated, single source, not evidence of a systemic failure. See the [public records](../references/public-records.md). |
| **Evidence** | An attributable, scoped assertion, not guaranteed truth. |
| **Evidence class** | The kind of support a statement has: a real public record, an internal engagement record, a synthetic illustration, a repository check, or something that is not available. Classes are kept apart; one is never presented as another. See [claims and limits](claims-and-limits.md#evidence-classes-kept-apart). |
| **Evidence ledger** | The role of keeping a durable record of admitted evidence versions. In this architecture the governed registry plays that role, so there is one store, not two; a decision packet is not a substitute for it, and a product's managed memory is not one. |
| **EV01–EV12** | The twelve evaluation tests defined for the architecture. All are NOT RUN. See the [oracles](../evaluation/oracles.md). |
| **Executor** | The component that performs an approved action, also called the action gateway. At commit it rechecks permission, evidence, preconditions and limits against the current state before it submits the action. Its own status is never evidence of the outcome: only the authoritative target decides that. |
| **Field group** | A numbered part of a contract, written like `C03-G05` (contract 3, group 5). The seven contracts have 41 field groups. |
| **Fixture** | A synthetic test case with fixed inputs, an explicit expected oracle, an accountable owner, metrics and a gate. The 70 defined fixtures are NOT RUN. |
| **Governed decision context** | The reusable unit of the architecture: authorized, attributable outputs selected for a defined task, synthesized within limits and released as a versioned decision packet. |
| **IN01–IN04** | The author's four internal engagement records, which are not published. None measures the benefit of this architecture. See the [engagement records](../references/engagement-records.md). |
| **Independent mandatory path** | The deterministic route from the registry through detection and an authorized notification and queue to acknowledgement or escalation. It has no LLM availability dependency. |
| **Lineage** | The directed, acyclic derivation ancestry of a record, plus separately typed relationships (contradiction, supersession, validation, invalidation), each naming the asserting actor. |
| **Matched baseline** | A simpler way of doing the same work, against which the architecture has to be compared: the native or current workflow, deterministic grouping and templates, or simple synthesis with zero specialists, matched on task, risk, scope and acceptance criteria. The catalogue defines 12 matched baseline records. All are NOT RUN. |
| **Missingness labels** | The seven states that must not collapse: `missing`, `not_retrieved`, `inaccessible`, `unavailable`, `negative`, `not_assessed`, `stale`. See [chapter 8](paper/08-uncertainty.md). |
| **Model inference** | A C02 record establishing that a model produced an interpretation, not that the interpretation is true. |
| **Native safety controls** | Existing deterministic safety controls that keep their established authorized routes outside assistant-mediated admission (see *Admission*). |
| **NOT RUN** | Execution was not attempted. |
| **NOT ASSESSED** | In evaluation and publication, insufficient declared assessment coverage. It is never an automatic pass. Not to be confused with the source-level label `not_assessed`, which means a check or assessment was not performed. |
| **`not_executed_verified`** | The C07 receipt state for a *verified no-effect*: authoritative confirmation, by rejection, failure before effect or cancellation, that the action caused no business effect. A timeout or a missing response is never this state. This is the one name for it; "verified no-effect" is only its plain-language gloss. |
| **Oracle** | The explicit expected result of an evaluation test or fixture. |
| **Qualified** | Two senses, kept apart. *Qualified information* is information that is available but carries an explicit limitation: stale, partial, or from a source that did not answer. It supports a limited review with its limits visible, and never a clean negative. A *qualified deterministic template* is a fallback, with no model in it, that has been checked and accepted for use when the assistant model is unavailable. |
| **Recovery owner** | The named owner who acts on a failure. The [failure table](../architecture/action-and-degradation.md#full-failure-response-and-recovery-ownership) assigns one failure by failure; no other page keeps a separate list. |
| **RG01, RG02** | The two guidance and standards sources the paper cites for positioning only: the NIST AI Risk Management Framework and Article 14 of the EU AI Act. See [guidance and standards](../references/guidance-and-standards.md). |
| **Registry (governed)** | The store that retains admitted immutable record versions. The *ProducerRegistry* is a different thing: the governed list of producers, registry versions and permitted evidence kinds, not a second store of records. |
| **Requestor** | The principal who asks for the context (C01 `requesting_principal`). A different role from the accountable approver. |
| **Scoped validation** | A validation record naming who assessed which exact target, by which method, when and within what scope. It does not establish universal correctness. |
| **Selection manifest** | The C03 record of what the system actually considered and retained, with coverage, exclusions, grouping reasons and missingness. |
| **Specialist** | An optional agent that receives an authorized, bounded task and returns results only through admission. The zero-specialist baseline is a complete architecture. |
| **Supersession / invalidation** | A correction supersedes an earlier record version and invalidates affected derivatives, packets, caches and pending approvals. |
| **UNSET** | A domain parameter with no approved value. |
| **Unknown outcome** | A C07 state in which effects remain unresolved. Reservation or conservative accounting is kept until authoritative reconciliation, and there is no blind retry. |
