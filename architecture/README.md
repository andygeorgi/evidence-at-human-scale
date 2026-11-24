# Architecture reference

This reference holds the technical detail behind the [paper](../docs/paper/README.md): what each kind of evidence establishes, how permission limits what a requestor sees, how approval and execution stay separate, what happens when a part fails, who owns what, and which choices a domain still has to make. Each contract detail appears once, in the [contract reference](../contracts/README.md). It is not an implementation report, and it gives no assurance about any deployment.

This is a reference architecture, not a production deployment or benefit claim. The contracts and synthetic examples are tested; real-world effectiveness has not been evaluated. The evaluation tests are NOT ASSESSED. The repository's own checks on its documents and examples are a separate class of evidence (see [claims and limits](../docs/claims-and-limits.md#evidence-classes-kept-apart)). They show that the documents are consistent, and they say nothing about how the architecture performs.

## Contents

| Page | What it holds | Paper chapter |
| --- | --- | --- |
| [Evidence semantics](evidence-semantics.md) | What each kind of evidence establishes and what it does not; how the contracts write cardinality and references; what structural validation cannot check | [4. Evidence and lineage](../docs/paper/04-evidence-and-lineage.md) |
| [Lineage, selection and disclosure](lineage-selection-disclosure.md) | Versioned ancestry; the seven missingness labels; why permission is decided before disclosure; constraints before ranking; the independent mandatory path; authorization through derived outputs | [5. Context and selection](../docs/paper/05-context-and-attention.md), [8. Uncertainty](../docs/paper/08-uncertainty.md) |
| [Action and degradation](action-and-degradation.md) | Approval, commit and shared capacity; receipt states; a table of failures with the owner who recovers from each | [9. Authority](../docs/paper/09-authority.md), [10. Degraded operation](../docs/paper/10-degraded-operation.md) |
| [Ownership, parameters and tradeoffs](ownership-and-tradeoffs.md) | Who is responsible for each part; what a domain must supply and which questions are open; the tradeoff register | [11. Costs and adaptation](../docs/paper/11-costs-and-adaptation.md) |
| [Implementation options](azure-implementation-options.md) | An optional product mapping and its qualifications | [13. Implementation options](../docs/paper/13-implementation-options.md) |
| [Question index](question-index.md) | Questions mapped to chapters, reference pages, figures and evaluation tests | all |

Related references: the [contract reference](../contracts/README.md) (all 41 field groups of the seven contracts), the [evaluation oracles](../evaluation/oracles.md), the [sources](../references/README.md) and the [figures](../figures/README.md).

The reference keeps all seven contracts, C01 to C07, with their 41 field groups, and the detailed controls that the paper's figures simplify. The [JSON Schema bundle](../schemas/README.md) (Draft 2020-12) documents the contracts and checks their structure; it is not a deployable interface. The [evaluation catalogue](../evaluation/catalogue/README.md) holds the evaluation tests, the matched baseline records, the synthetic fixtures and the domain parameters.

## What a domain still needs

Before adoption, a domain needs approved owners and parameters, working authorization, defined failure routes, executed fixtures and a recorded acceptance. A record's provenance does not make it true, and a schema's shape does not make it accurate. Permission synchronization can lag, external actions can race, and attention stays finite.
