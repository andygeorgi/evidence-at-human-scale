# C04 Decision packet

[Contracts](README.md) · Schema definition `#/$defs/decision_packet` · Groups C04-G01–G09

**Paper:** [6. The decision packet](../docs/paper/06-decision-packet.md)
**Reference:** [evidence semantics](../architecture/evidence-semantics.md); [lineage, selection and disclosure](../architecture/lineage-selection-disclosure.md)
**Figures:** F02, F04 · **Evaluation tests:** EV01, EV03, EV04, EV05, EV06, EV07, EV10, EV12 (NOT ASSESSED)

C04 Decision packet is a versioned review object bound to the exact context and selection manifest. It presents supported claims with evidence references, separately labeled inferences, recommendations, conflicts, uncertainty, missingness, limitations, and review requirements. It is not an action authorization and it is not an evidence ledger substitute.

| Group / exact type-cardinality | Emitted group and fields | Required semantics |
| --- | --- | --- |
| C04-G01 Decision context/as-of · Object, 1 | `decision_context_as_of`: `packet_id`, `version`, `context_reference`, `selection_reference`, `as_of` | Packet ID, version and schema, exact C01 and C03 references, and the as-of time. Selected scope is not whole-corpus coverage. |
| C04-G02 Supported claims/references · Array, 0..n | `supported_claims_references`: `claim_id`, `text`, `supporting_references` | Claim ID/text and supporting-reference alternatives 1..n. `claim_reference` requires `record_id`, exact version, `claim_id` and original locator. `payload_reference` requires `record_id`, exact version, explicit payload location or pointer and original locator. Both retain the scope, type and source provenance, and no payload claim ID is invented. Every reference is validated, and the text is held to all of them: a claim that cites claims says exactly what they say, and a claim that cites a payload (alone or beside claims) states the payload's pass or fail status and at least one of its figures, no status or figure it does not hold, and each figure beside the name of a payload field as that field's value (checks `PKT001`, `PKT005`). These checks do not interpret prose. |
| C04-G03 Labeled inferences · Array, 0..n | `labeled_inferences`: `inference_id`, `text`, `kind`, `supporting_references`, `method`, `limitations` | Inference ID, text and kind; support tagged as `claim_reference` or `payload_reference`; method and limitations. An inference is never relabeled as a source assertion. |
| C04-G04 Recommendations · Array, 0..n | `recommendations`: `recommendation_id`, `text`, `basis`, `uncertainty`, `accountable_review_requirement` | Recommendation ID/text, basis, uncertainty and accountable review requirement. |
| C04-G05 Conflicts/uncertainty · Object, 1 | `conflicts_uncertainty`: `conflicts`, `uncertainty` | Conflict entries 0..n and uncertainty state/basis. Material expected conflicts remain visible. |
| C04-G06 Coverage/omissions/gaps · Object, 1 | `coverage_omissions_gaps`: `coverage_reference`, `visible_scoped_limitation_summary`, `missingness` | C03 coverage reference, visible scoped limitation summary, explicit missingness 0..n. Use all seven definitions in [lineage, selection and disclosure](../architecture/lineage-selection-disclosure.md#versioned-ancestry-and-missingness); keep apart denial and unavailability, a completed retrieval and a missing observation, a scoped negative and an absence, not_assessed and a freshness failure. |
| C04-G07 Priority/mandatory obligations · Object, 1 | `priority_mandatory_obligations`: `item_level_reasons`, `obligation_references` | Item-level reasons and obligation references 0..n. Urgency remains separate from confidence. |
| C04-G08 Action proposal, not executed · Array, 0..n | `action_proposals`: `proposal_reference`, `status` | C05 references with explicit proposal status. Not approval or execution. |
| C04-G09 Review/history · Object, 1 | `review_version_history`: `state`, `actor`, `time`, `prior_version_references`, `challenge_links` | Review state, actor and time where applicable; prior version references 0..n; challenge links 0..n. A review is not a validation of truth. |

## What a valid C04 does not establish

A packet is a versioned review object, not a truth certificate or execution control. Brevity is acceptable only while decision-changing evidence, conflict, uncertainty, omissions and drillback remain visible. A challenged packet is not overwritten: affected lineage is reassessed and revised versions stay distinguishable through `prior_version_references`. `review_version_history` shows the state of the packet when the snapshot was taken. A later invalidation changes that state; it does not erase that a review happened earlier. The worked example keeps its reviews in a separate `review_log`, in [`registry.json`](../examples/registry.json).

## Examples

- [05 Decision packet](../examples/05-decision-packet/README.md): a complete packet with supported claims, labeled inferences, a conflict, all seven gap states and two unexecuted proposals.
- [06 Assistant response](../examples/06-assistant-response/README.md): the packet as a reader sees it, and a deterministic template fallback.
- [11 Late correction](../examples/11-late-correction/README.md): the revised packet that supersedes it.

[← C03 Selection](c03-selection.md) · [Contracts](README.md) · [Next: C05 Action proposal →](c05-action-proposal.md)
