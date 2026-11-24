# Guided reading paths

Choose a route by what you want to do. To look up a topic or a folder instead, use the tables after the paths.

## Paths

**Short path: the argument in a few pages.** [Overview](paper/00-overview.md) → [1. Human attention](paper/01-human-attention.md) → [3. The reference architecture](paper/03-governed-context.md) → [Where the architecture stops](paper/14-start-monday.md#where-the-architecture-stops).

**Architect path: the whole paper.** Read the [paper](paper/README.md) in order. Open the [worked example](../examples/README.md) after chapter 6.

**Implementer path: start building.** [Implementation guide](implementation-guide.md) → [contracts](../contracts/README.md) → [examples](../examples/README.md) (run `python scripts/validate_examples.py`) → [action and degradation](../architecture/action-and-degradation.md).

**Claims-checking path: what is claimed and what is not.** [What the engagement showed](paper/02-engagement.md) → [claims and limits](claims-and-limits.md) → [sources](../references/README.md) → [question index](../architecture/question-index.md).

**Evaluator path: how the architecture would be tested.** [Evaluation guide](../evaluation/README.md) → [oracles](../evaluation/oracles.md) → [human-outcome evaluation](../evaluation/human-outcome-evaluation.md) → [catalogue](../evaluation/catalogue/README.md).

## Topics and where to read about them

| Topic | Read |
| --- | --- |
| 1. Why human attention is the scarce resource | [Chapter 1](paper/01-human-attention.md) |
| 2. Why adding more agents can make it worse | [Chapter 1](paper/01-human-attention.md), [chapter 7](paper/07-one-interaction.md) |
| 3. The architectural thesis | [Overview](paper/00-overview.md) |
| 4. The logical reference architecture | [Chapter 3](paper/03-governed-context.md) (Figure F02) |
| 5. The evidence and context contracts | [Chapters 4–6](paper/04-evidence-and-lineage.md), [contracts](../contracts/README.md) |
| 6. Roles, approval and execution | [Chapter 9](paper/09-authority.md) |
| 7. Degraded and failure modes | [Chapter 10](paper/10-degraded-operation.md) |
| 8. How to begin implementing it | [Chapter 14](paper/14-start-monday.md), [implementation guide](implementation-guide.md) |
| 9. How to evaluate it | [Chapter 12](paper/12-evaluation.md), [evaluation guide](../evaluation/README.md) |
| 10. What it does not claim | [Claims and limits](claims-and-limits.md), [chapter 14](paper/14-start-monday.md#where-the-architecture-stops) |

## Map of the repository

| Folder | What it holds |
| --- | --- |
| [`docs/`](.) | The paper, these reading paths, the glossary, claims and limits, and the implementation guide. |
| [`architecture/`](../architecture/README.md) | The technical reference behind the paper. |
| [`contracts/`](../contracts/README.md) | One page per contract with all 41 field groups. |
| [`schemas/`](../schemas/README.md) | The machine-readable JSON Schema bundle. |
| [`examples/`](../examples/README.md) | A synthetic scenario that exercises every contract, with expected output and checks. |
| [`evaluation/`](../evaluation/README.md) | How to evaluate, the oracles, and the catalogue of tests, fixtures and parameters (all NOT ASSESSED or UNSET). |
| [`figures/`](../figures/README.md) | Every figure with its editable source, alt text and caption. |
| [`references/`](../references/README.md) | Public sources, their limits, and how internal engagement records are treated. |
| `scripts/`, `tests/` | The validation tooling and its tests. |
