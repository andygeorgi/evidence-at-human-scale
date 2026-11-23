# Glossary

Terms are used as the [paper](paper/README.md) and the [contracts](../contracts/README.md) use them. Where a word has more than one meaning in the sources, each meaning is listed and kept apart.

| Term | Meaning |
| --- | --- |
| **Accountable approver** | The person who authorizes an exact proposal or issues a bounded grant (C06 `issuer`). The architecture separates the requestor and the accountable approver as roles; whether one person may hold both is a domain decision that this repository does not settle. |
| **Acknowledgement** | A record that a mandatory notification was received. It is receipt, not resolution; the obligation remains tracked. |
| **Admission** | The step at which a registered producer's record enters the registry. It establishes that the envelope and kind are admissible, never that the content is true. |
| **Authoritative target** | The system whose own state decides what actually happened. A receipt is verified against it, not against the executor's status. |
| **B_time, B_cost** | The task time budget (critical path) and the cost budget (full task lifecycle) declared before deployment. |
| **Bounded grant** | A C06 delegation that authorizes a predefined action class within explicit scope, limits and lifecycle, without a fresh approval for each instance. |
| **Claim reference / payload reference** | The two tagged alternatives for pointing at evidence. A claim reference names the exact record version and claim ID; a payload reference names the exact version and an explicit payload location and never invents a claim ID. |
| **Commit** | The moment an action takes effect. The executor rechecks current permission and revocation, evidence, policy, target state and per-action and cumulative limits at commit; approval does not replace those checks. |
| **Common origin** | Two derivations that share a root record. Their agreement is not independent corroboration. |
| **Confirmed-effect policy** | The documented policy under which allowance may be restored: only on authoritative reconciliation, never on timeout or lease expiry alone. |
| **Context** | Three meanings, kept apart. *Decision context*: the governed, versioned unit of information selected for one decision. *C01 Context*: the contract that records the requesting principal, task, purpose, entities, time and policy. *Model context*: what is placed in front of a model, which must only contain evidence the principal was already authorized to read. |
| **Control plane** | The set of controls that constrain every stage and path: identity, authorization, purpose, domain policy, source/model/tool inventory, freshness, budgets and delegation. |
| **Decision Owner** | The person accountable for the decision. |
| **Decision packet** | The C04 versioned review object bound to an exact context and selection. It separates supported claims, labeled inferences, recommendations, conflicts, uncertainty, gaps, obligations and unexecuted proposals. It is not an action authorization. |
| **Deterministic finding** | A C02 record that reports a declared rule, at a stated version, over stated inputs. |
| **Domain parameter** | A value the domain owner must supply (source authority, freshness, safe states, thresholds and so on). An unresolved parameter blocks the decision that depends on it. |
| **Evidence** | An attributable, scoped assertion, not guaranteed truth. |
| **Evidence ledger** | The durable record of admitted evidence versions. In this architecture that role belongs to the governed registry; a decision packet is not a substitute for it, and a product's managed memory is not one. |
| **EV01–EV12** | The twelve evaluation tests defined for the architecture. All are NOT RUN. See the [oracles](../evaluation/oracles.md). |
| **Fixture** | A synthetic test case with fixed inputs, an explicit expected oracle, an accountable owner, metrics and a gate. The 70 defined fixtures are NOT RUN. |
| **Governed decision context** | The reusable unit of the architecture: authorized, attributable outputs selected for a defined task, synthesized within limits and released as a versioned decision packet. |
| **Independent mandatory path** | The deterministic route from the registry through detection and an authorized notification and queue to acknowledgement or escalation. It has no LLM availability dependency. |
| **Lineage** | The directed, acyclic derivation ancestry of a record, plus separately typed relationships (contradiction, supersession, validation, invalidation), each naming the asserting actor. |
| **Missingness labels** | The seven states that must not collapse: `missing`, `not_retrieved`, `inaccessible`, `unavailable`, `negative`, `not_assessed`, `stale`. See [chapter 8](paper/08-uncertainty.md). |
| **Model inference** | A C02 record establishing that a model produced an interpretation, not that the interpretation is true. |
| **Native safety controls** | Existing deterministic safety controls that keep their established authorized routes outside assistant-mediated admission. |
| **NOT RUN** | Execution was not attempted. |
| **NOT ASSESSED** | In evaluation and publication, insufficient declared assessment coverage. It is never an automatic pass. Not to be confused with the source-level label `not_assessed`, which means a check or assessment was not performed. |
| **Oracle** | The explicit expected result of an evaluation test or fixture. |
| **Registry (governed)** | The store that retains admitted immutable record versions. The *ProducerRegistry* is the governed list of producers, registry versions and permitted evidence kinds. |
| **Requestor** | The principal who asks for the context (C01 `requesting_principal`). |
| **Scoped validation** | A validation record naming who assessed which exact target, by which method, when and within what scope. It does not establish universal correctness. |
| **Selection manifest** | The C03 record of what the system actually considered and retained, with coverage, exclusions, grouping reasons and missingness. |
| **Specialist** | An optional agent that receives an authorized, bounded task and returns results only through admission. The zero-specialist baseline is a complete architecture. |
| **Supersession / invalidation** | A correction supersedes an earlier record version and invalidates affected derivatives, packets, caches and pending approvals. |
| **UNSET** | A domain parameter with no approved value. |
| **Unknown outcome** | A C07 state in which effects remain unresolved. Reservation or conservative accounting is kept until authoritative reconciliation, and there is no blind retry. |
