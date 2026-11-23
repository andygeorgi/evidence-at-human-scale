# Human-outcome evaluation

[← Evaluation guide](README.md) · [Evaluation oracles](oracles.md) · [Catalogue](catalogue/README.md)

**Status: NOT RUN.** There is no human-outcome result in this repository, no pilot, and no recommended threshold.

The architecture's central claim is about people: that someone with limited attention can still be accountable for a decision, because the evidence, its gaps and its limits stay in front of them. That is a claim about human behaviour, and the checks in this repository cannot test it. This page is a **template of what a study has to define** before it can say anything. It is a list of questions to answer, not a protocol and not a prediction.

The measures named in the paper are evidence actually inspected, decision quality and workload. They still need study-specific definitions: this is open question OQ06 in the [ownership, parameters and tradeoffs reference](../architecture/ownership-and-tradeoffs.md). See [chapter 12](../docs/paper/12-evaluation.md).

## The question

State one primary question in a form that a result could contradict. For example: *under the same task, risk and time budget, do reviewers using a packet inspect the evidence behind the decision-changing items more often, and reach decisions closer to a gold standard, than reviewers using the current workflow?* Write down what result would count against the architecture. If no result could, it is not a question.

## What must be defined before data is collected

| Element | Define | Why |
|---|---|---|
| **Population** | The roles that review and approve, their experience, how they are recruited, how many | Results do not transfer to people who are not like the participants. |
| **Tasks** | Representative decisions, their risk classes, how they are sampled, how many | One easy invoice is not a decision workload. |
| **Gold standard** | For each task: the decision-changing items, expected conflicts and expected gaps, and who established them, independently of the architecture | A decision-quality measure needs an answer key (see parameters `DP016` expected evidence and `DP005` risk classes). |
| **Baselines** | The comparison ladder: native or current workflow, deterministic grouping and templates, simple synthesis with zero specialists. Matched on task, risk, scope and acceptance criteria | Without a matched baseline a difference cannot be attributed to the architecture (`DP043` human review protocol). |
| **Materials** | The exact packets, responses or screens shown, and how they were produced | A hand-written packet measures the author, not the architecture. |
| **Conditions** | The time budget (`B_time`, `DP001`), the freshness required (`DP004`), the interruptions allowed | Time pressure changes inspection. |
| **Measures** | See below | |
| **Denominators** | The number of tasks, gold items and inspection opportunities, each declared positive in advance | An empty denominator is NOT ASSESSED, never a pass. |
| **Sample and uncertainty** | How many participants and tasks, how uncertainty will be reported | No inferred benefit from a small or unrepresentative sample. |
| **Analysis plan** | Preregistered: comparisons, exclusions, handling of missing data, stopping rules | So the result is not chosen after the fact. |
| **Scoring** | Who scores, blind to condition where possible, with what rubric | Semantic judgements need explicit rubrics, not impressions. |
| **Ethics and data** | Consent, privacy, minimisation (`DP047`), whether real data is used, who may see raw records | Reviewers' behaviour is personal data. |
| **Independence** | Who runs, who analyses, who has an interest in the outcome | |
| **Reporting** | Raw counts, denominators, coverage and uncertainty; negative and null results | |

## Measures

| Measure | Define | Watch for |
|---|---|---|
| **Evidence actually inspected** | What counts as inspection (opening a source, following a reference, reading a gap) and how it is observed | Opening is not reading. A reviewer can click through without looking. |
| **Decision quality** | Agreement with the gold decision, weighted by consequence; false approvals and false holds counted separately | A faster wrong decision is not better. |
| **Omissions caught** | Gold critical items, conflicts and gaps the reviewer noticed | Reading a packet and noticing what is missing are different things. |
| **Time** | Elapsed time on the critical path, separately from total work | Time saved without decision quality is not a benefit. |
| **Workload** | A declared instrument and its scale (`DP003`) | |
| **Calibration** | Whether confidence follows correctness | Optional; declare it if used. |

## Measures that do not answer the question

- Fluency or readability of generated text.
- How many agents agree. Agreement between derivations that share a source is not corroboration.
- Reviewer satisfaction on its own.
- A groundedness score from a tool, treated as source truth.
- Approval rate. An approval without inspection is exactly the failure the architecture exists to prevent.

## Threats to validity to plan for

Learning and order effects; differences in expertise between groups; tasks that differ in difficulty between conditions; novelty of the tool; reviewers who approve by habit; a gold standard written by someone who knows the architecture; participants who guess the hypothesis; and drift in the materials between sessions.

## A reporting skeleton

Fill this in only from data that exists. Every cell is empty here.

| Item | Value |
|---|---|
| Question and what would count against it | |
| Population, number of participants | |
| Tasks and number | |
| Baselines compared | |
| Gold standard and who set it | |
| Denominators (tasks · gold items · inspection opportunities) | |
| Evidence inspected, by condition | |
| Decision quality, by condition, with uncertainty | |
| Omissions caught, by condition | |
| Time and workload, by condition | |
| Deviations from the plan | |
| Limits and what the result does not show | |

## Related

[Evaluation guide](README.md) · the 12 matched baseline records `BASE-01`–`BASE-12` and the parameters `DP001`, `DP003`, `DP004`, `DP005`, `DP012`, `DP016`, `DP019`, `DP042`, `DP043` and `DP047` in the [catalogue](catalogue/README.md).
