# Lineage, selection and disclosure

[Architecture reference](README.md) · Paper: [4. Evidence and lineage](../docs/paper/04-evidence-and-lineage.md) · [5. Context and attention](../docs/paper/05-context-and-attention.md) · [8. Uncertainty](../docs/paper/08-uncertainty.md)

## Versioned ancestry and missingness

In the lineage figure (Figure F03, [chapter 4](../docs/paper/04-evidence-and-lineage.md)), M01/v1 (Agent A) and M02/v1 (Agent B) both inherit source record S01/v1 and feed P01/v1. Their agreement is common-origin interpretation, not independent corroboration. S02/v1 supplies a conflicting source assertion. S01/v2 corrects and supersedes S01/v1, invalidating affected derivatives. V01/v1 is a scoped validation record linked only to its actual target and scope. Directed derivation ancestry is acyclic; dashed contradiction, supersession, validation and invalidation annotations are not ancestry. Every relationship identifies its asserting actor.

| Canonical label | Required distinction |
| --- | --- |
| `missing` | Expected input not obtained; reason may be unknown. |
| `not_retrieved` | Completed scoped retrieval returned no relevant record. Not evidence of absence. |
| `inaccessible` | Current principal lacks permission. Reason or existence is disclosed only when permitted. |
| `unavailable` | Source or dependency could not provide data; distinct from permission denial. |
| `negative` | Explicit adequately scoped observation reports absence, with method, time and coverage. |
| `not_assessed` | A check or assessment was not performed. |
| `stale` | Available record fails the applicable freshness requirement. |

Evaluation/publication NOT ASSESSED separately means insufficient declared assessment coverage, not a source negative. Retrieval silence cannot become proof of absence. A manifest with no dispositions cannot imply whole-corpus absence. Authorized coverage must describe the assessed scope and limitations without exposing protected names, counts, relationships or existence.

The schema requires different evidence for each label (for example, a completed retrieval reference for `not_retrieved`, an observation reference and coverage for `negative`, a permission decision for `inaccessible`). A [worked packet](../examples/04-selection-and-missingness/README.md) carries all seven.

## Constraints before ranking, mandatory continuity

Authorization, purpose, lifecycle and mandatory constraints precede discretionary ranking, grouping and synthesis. Item-level reasons identify obligation, severity, deadline, task relevance, freshness and uncertainty. Severe low-confidence signals may need prominence; urgency never means confidence. Preferences can alter permitted discretionary ordering, not obligations or access.

Presentation may deduplicate common-origin material, but not portray correlated agreement as corroboration. Material conflicts remain unless domain policy establishes explicit scoped supersession. Neither majority nor newer timestamp settles an authority conflict automatically. Progressive disclosure preserves decision-changing evidence, conflict, uncertainty, omissions and drillback. The decision packet is a versioned review object, not a truth certificate or execution control.

The independent mandatory path runs from governed records through deterministic detection, authorized notification and queueing, then acknowledgement or escalation. Acknowledgement records receipt, not resolution; the obligation remains tracked. Overflow exposes the true authorized workload and escalates ownership, rather than silently capping it. Deadlines do not wait for synthesis. Native deterministic safety controls may operate outside assistant-mediated admission through their established authorized routes. When the mandatory channel itself fails, designated authorized native/manual safety routes must receive escalation.

## Authorization through derivation and lifecycle

Separate the requestor, read-authorized context service, workload/orchestration identity and executor. Workload identity does not grant source-user permissions or establish conversation ownership. Filter before model access, rather than retrieve as a superuser and rely on redaction. Permitted task and purpose are enforceable access inputs, not informal prompt context.

Source content, tool responses and model outputs are untrusted data. They cannot modify permissions, controls, priorities, mandatory obligations or executable instructions. Indirect prompt injection must fail at enforceable boundaries. Screening is defense in depth, not the authority boundary. A summary, inferred relationship, count, manifest or limitation can disclose protected existence even if the raw record is withheld; projection applies to all derived outputs.

Isolate tenant, user, purpose, session, cache and log contexts. Recheck disclosure, authorization and freshness on release, every later view, cache serve and historical view, including revocation. A released or cached summary is not an enduring grant. Removing a citation but retaining its revealing inference is insufficient. Source corrections, revocations, late evidence and challenges trigger lineage reassessment and invalidate affected packets, caches and pending approvals. Feedback must reach action preconditions, not only the displayed summary. Revised current views stay distinct from permitted retained history; approved packets never change silently.

[← Evidence semantics](evidence-semantics.md) · [Architecture reference](README.md) · [Next: action and degradation →](action-and-degradation.md)
