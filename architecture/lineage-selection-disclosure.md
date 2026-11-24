# Lineage, selection and disclosure

[Architecture reference](README.md) · Paper: [4. Evidence and lineage](../docs/paper/04-evidence-and-lineage.md) · [5. Context and attention](../docs/paper/05-context-and-attention.md) · [8. Uncertainty](../docs/paper/08-uncertainty.md)

A decision packet has to show where each claim comes from and what is missing, without telling the requestor anything it may not know. Records derive from one another in a versioned, acyclic graph, and a correction travels along it. Seven labels say why an input is absent, and permission is decided before any label is shown. Selection applies its constraints before it ranks. Summaries, counts and other derived outputs follow the same disclosure rules as the records they come from.

## Versioned ancestry and missingness

In the lineage figure (Figure F03, [chapter 4](../docs/paper/04-evidence-and-lineage.md)), M01/v1 (Agent A) and M02/v1 (Agent B) both derive from source record S01/v1, and both feed P01/v1. Their agreement comes from one origin. It is not independent corroboration. S02/v1 is a conflicting source assertion. S01/v2 corrects S01/v1: it supersedes that version and invalidates the affected derivatives. V01/v1 is a scoped validation record. It applies only to the target and scope it actually assessed.

Derivation ancestry is directed and acyclic. The dashed relationships in the figure (contradiction, supersession, validation and invalidation) are not ancestry. Every relationship names the actor who asserted it.

Missingness uses these canonical labels, and they must not be collapsed into one another:

| Canonical label | Required distinction |
| --- | --- |
| `missing` | An expected input was not obtained. The reason may be unknown. |
| `not_retrieved` | A completed, scoped retrieval returned no relevant record. This is not evidence of absence. |
| `inaccessible` | The requestor may know the input exists but may not read it. It is shown only in the wording the permission decision allows. |
| `unavailable` | A source or dependency could not provide the data. This is different from a permission denial. |
| `negative` | An explicit, adequately scoped observation reports absence, with its method, time and coverage. |
| `not_assessed` | A check or assessment was not performed. |
| `stale` | An available record fails the applicable freshness requirement. |

The evaluation status NOT ASSESSED is separate from the label `not_assessed`. It means that the evidence, environment or participants an evaluation needs do not exist, and it is not a negative finding about a source. A retrieval that returns nothing is not proof of absence, and a manifest with no dispositions does not imply that the record is absent from the whole corpus. The coverage statement that the requestor is authorized to see must describe the assessed scope and its limitations. It must not expose protected names, counts, relationships or existence.

The schema requires different supporting evidence for each label. For example, `not_retrieved` needs a reference to a completed retrieval, `negative` needs a reference to an observation and its coverage, and `inaccessible` needs a permission decision. The [worked selection](../examples/04-selection-and-missingness/README.md) carries all seven.

## Permission comes before disclosure

An expected input that is not in front of the requestor is handled in this order. The order is part of the design (Figure F09):

1. **Decide whether the requestor may know that the record or category exists.** If not, nothing about it appears: no entry, no state, no age, no count. The coverage statement that every output carries reads the same whether or not anything is withheld.
2. **Apply the safe-disclosure policy.** If the requestor may know that something exists but may not read it, the entry is `inaccessible`, in the wording the permission decision allows: no name, type, count, state or age.
3. **Classify only what the requestor may read** as stale, not assessed, unavailable, missing, negative or not retrieved.
4. **Expose only what the requestor is permitted to see** about each classified input.

The other order leaks. If a record is classified as stale before permission is checked, the label can reach a requestor who may not know the record exists, and the output then tells them that it exists and how old it is. A count of restricted records, the existence of a restricted investigation and the fact that a restricted evidence category was checked leak in the same way. An unauthorized requestor receives the same output whether or not the restricted record exists.

[`tests/test_disclosure.py`](../tests/test_disclosure.py) shows this for every combination of states. The [registry of the worked example](../examples/04-selection-and-missingness/README.md#permission-before-disclosure) holds one permission decision that allows a coverage limitation and one that allows nothing.

## Constraints before ranking, mandatory continuity

Selection applies authorization, purpose, lifecycle and mandatory constraints first. Only then does it do the discretionary work of ranking, grouping and synthesis. Each item carries its reasons: its obligation, severity, deadline, task relevance, freshness and uncertainty. A severe signal with low confidence may still need prominence, and urgency never stands for confidence. A user's preferences can change the order of items that are discretionary and permitted. They cannot change obligations or access.

A packet may deduplicate material that shares an origin. It may not present that agreement as corroboration. A material conflict stays visible unless the domain's policy explicitly supersedes one side, within a stated scope. Neither a majority nor a newer timestamp settles a conflict of authority automatically. A packet can move detail out of the first view only while decision-changing evidence, conflicts, uncertainty, omissions and drillback to the original evidence stay visible. The decision packet is a versioned object for review. It does not certify truth, and it does not control execution.

The independent mandatory path runs from the governed records through deterministic detection, authorized notification and queueing, to acknowledgement or escalation. An acknowledgement records receipt. It does not record resolution, and the obligation stays tracked. On overflow, the system shows the true authorized workload and escalates ownership. It does not cap the workload silently. Deadlines do not wait for synthesis. Native deterministic safety controls may keep operating on their established authorized routes, outside assistant-mediated admission (admission through the assistant workspace and the governed registry). If the mandatory channel itself fails, escalation must reach the designated authorized native or manual safety routes.

## Authorization through derivation and lifecycle

Keep these apart: the requestor, the read-authorized context service, the workload or orchestration identity, and the executor. The workload identity does not carry the source user's permissions, and it does not establish who owns the conversation. Filter before the model sees any content. Do not retrieve as a superuser and rely on redaction afterward. The permitted task and purpose are inputs to access enforcement. They are not informal context in a prompt.

Source content, tool responses and model outputs are untrusted data. They cannot change permissions, controls, priorities, mandatory obligations or executable instructions. An indirect prompt injection must fail at an enforceable boundary. Screening is defense in depth. It is not the authority boundary. A summary, an inferred relationship, a count, a manifest or a limitation can reveal that a protected record exists, even when the raw record is withheld. Every derived output must be filtered to what the requestor may see, in the same way as the raw record.

Isolate tenant, user, purpose, session, cache and log contexts from one another. Recheck disclosure, authorization and freshness at release, at every later view, whenever a cache serves a result, and in every historical view. A revocation applies at each of these points. A released or cached summary is not a standing grant. Removing a citation does not help if the inference that reveals the record stays in.

Source corrections, revocations, late evidence and challenges trigger a reassessment of lineage. They invalidate the affected packets, caches and pending approvals. The feedback must reach the preconditions of an action, not only the summary on screen. The revised current view stays distinct from the history that policy permits the system to retain, and an approved packet never changes silently.

[← Evidence semantics](evidence-semantics.md) · [Architecture reference](README.md) · [Next: action and degradation →](action-and-degradation.md)
