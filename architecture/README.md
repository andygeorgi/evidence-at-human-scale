# Architecture reference

The [paper](../docs/paper/README.md) carries the argument. This reference holds the technical layer behind it: evidence semantics, lineage and disclosure, accountable action and degraded operation, ownership and tradeoffs, product options and a question-to-section map. Contract details appear once, in the [contract reference](../contracts/README.md). This is neither an implementation report nor deployment assurance.

> **Systems produce evidence. AI makes it consumable. People remain accountable.**

All architecture, runtime, safety, performance, cost and human-evaluation results remain NOT RUN. Editorial inspection and structural schema checks are separate evidence classes.

## Contents

| Page | What it holds | Paper chapter |
| --- | --- | --- |
| [Evidence semantics](evidence-semantics.md) | What evidence is and is not; normative notation; reference alternatives; the limits of structural validation | [4. Evidence and lineage](../docs/paper/04-evidence-and-lineage.md) |
| [Lineage, selection and disclosure](lineage-selection-disclosure.md) | Versioned ancestry, the seven missingness labels, constraints before ranking, mandatory continuity, authorization through derivation | [5. Context and attention](../docs/paper/05-context-and-attention.md), [8. Uncertainty](../docs/paper/08-uncertainty.md) |
| [Action and degradation](action-and-degradation.md) | Approval, commit and shared capacity; receipt states; the failure-response table with recovery owners | [9. Authority](../docs/paper/09-authority.md), [10. Degraded operation](../docs/paper/10-degraded-operation.md) |
| [Ownership, parameters and tradeoffs](ownership-and-tradeoffs.md) | Responsibilities and accountable roles; domain acceptance and unresolved questions; the tradeoff register | [11. Costs and adaptation](../docs/paper/11-costs-and-adaptation.md) |
| [Implementation options](azure-implementation-options.md) | Optional product mapping, with qualifications | [13. Implementation options](../docs/paper/13-implementation-options.md) |
| [Reviewer navigation](reviewer-navigation.md) | Reviewer questions mapped to chapters, reference pages, figures and evaluation tests | all |

Related references: the [contract reference](../contracts/README.md) (all 41 field groups of the seven contracts), the [evaluation oracles](../evaluation/oracles.md) (A5), the [sources](../references/README.md) and the [figures](../figures/README.md).

## How the layers relate

The paper is the first reading layer; this reference and the contract reference are the second. They preserve C01–C07 and all 41 groups, and the detailed controls behind the simplified figures. The [JSON Schema bundle](../schemas/README.md) is a documentation-only JSON Schema Draft 2020-12 bundle; the [evaluation catalogue](../evaluation/catalogue/README.md) holds the evaluation tests, the matched baseline records, the synthetic fixtures and the domain parameters. The figures in the paper are simplified derivatives of the same architecture, not alternative specifications.

Adoption requires approved owners/parameters, implemented authorization, established failure routes, executed fixtures and recorded deployment acceptance. Provenance is not truth; schema shape is not semantic accuracy. Permission-sync lag, external races and finite attention remain.
