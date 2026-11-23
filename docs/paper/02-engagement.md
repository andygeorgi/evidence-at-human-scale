# 2. What the engagement showed

[← 1. Human attention](01-human-attention.md) · [Paper contents](README.md) · [Next: a governed context →](03-governed-context.md)

The architecture began with a case-based architecture engagement, not a client commission: the author acted as architect on a written case brief about a national fisheries-control authority in Iceland that registers catches and landings, confirms quota transfers and takes appealable enforcement decisions. The engagement combined the brief, research into the authority's public record, and prototypes the author built and tested on synthetic data, including a demonstrator assistant. The authority took no part: no interview, data, approval or outcome from it forms part of this evidence. Nothing in this repository is a statement by, about or on behalf of the authority.

Seven observations shaped the design; none measures the benefit of this architecture. Public records (EN) are dated single cases, not evidence of a systemic failure. Engagement records (IN) are the author's internal, AI-assisted working documents; the unpublished case brief is treated as unverified. Contract (C) and evaluation-test (EV) identifiers are introduced later; the [glossary](../glossary.md) lists them. Every source is described, with its limits, in the [sources](../../references/README.md).

## 1. Monitoring data can outgrow the people who must act on it

A national audit follow-up found that real-time electronic monitoring needs enough staff to process the information and respond to deviations.

- **Evidence and its limits:** EN01: audit finding, May 2023; current status unknown.
- **Design decision it informed:** Treat human attention, not data supply, as the binding constraint; design the governed decision context, not more output.

## 2. Proposed agents showed no value of their own

In the author's test of the agents that the case brief proposed, none showed evidence-backed value alone; evidence-backed value also came from controls around the agents and from platform continuity.

- **Evidence and its limits:** IN01: the author's AI-assisted agent-value test, 16 October 2026; one internal test.
- **Design decision it informed:** Start with zero specialists; admit one only for a documented task, permission or isolation need after a matched comparison (adopted in IN02).

## 3. A correction did not reach the decision built on it

A landing record was corrected months after an over-catch fee decision relied on it; the decision was not reopened, and an appeal ruling later annulled it because the fee rested on the uncorrected record.

- **Evidence and its limits:** EN02: appeal ruling, 14 April 2026; single case, later outcome unknown.
- **Design decision it informed:** Corrections invalidate affected derivatives, packets and pending approvals; feedback must reach action preconditions (contract [C02](../../contracts/c02-evidence.md), evaluation test [EV12](../../evaluation/oracles.md)).

## 4. A system flag led to a decision on the wrong basis

A catch-share cancellation began when the catch-registration system indicated under-fishing; the ruling annulled it because the decision used the wrong legal reference period.

- **Evidence and its limits:** EN03: appeal ruling, 7 November 2025; single documented case.
- **Design decision it informed:** A deterministic finding states its rule version, inputs, reference period and scope; review inspects that basis. A flag is never a decision.

## 5. Capability is not a mandate

A data-protection ruling found that drone video monitoring of a fishing vessel lacked a lawful basis under the law then in force; the regulator's AI guidance asks whether a solution without AI could achieve the same aim, possibly at lower risk.

- **Evidence and its limits:** EN04: ruling, 28 March 2023. EN05: guidance, first retrieved 16 October 2026.
- **Design decision it informed:** Purpose and permission are enforceable inputs checked before retrieval; compare non-AI baselines before adding model or agent complexity.

## 6. A reported failure was not the outcome

A deployment tool reported failure when a ten-minute status window closed, although the application had been answering health checks for about nine minutes; the tool trusted the exit code alone.

- **Evidence and its limits:** IN03: root-cause report, 6 November 2026; demonstrator infrastructure, synthetic data.
- **Design decision it informed:** An executor's status is not outcome evidence: verify against the authoritative target. Unknown stays unresolved; failure or timeout is never a verified no-effect, the `not_executed_verified` state (contract [C07](../../contracts/c07-execution-receipt.md)).

## 7. A request is not permission

In live-model tests, a request to open source records could be read as permission to switch workflows (since fixed); replies failing source or refusal checks were withheld, as designed, not repaired.

- **Evidence and its limits:** IN04: technical acceptance record, 17 November 2026; synthetic data.
- **Design decision it informed:** Requests, model output and tool output cannot widen permissions or change workflow authority; unsupported synthesis is not released as advice.

## Coverage

The demonstrator also taught a lesson about coverage (IN04, synthetic data). Its fleet view could show a whole fleet while case records existed for only part of it; the vessels without case records had to be labeled unassessed so that a fleet-scale picture would not imply a fleet-scale assessment. Coverage and missingness therefore belong to every result in this architecture. Runtime, human, cost and latency evaluation of the architecture remain NOT RUN.

## What is new here

Published guidance already sets the obligation. Trustworthy AI should be accountable, transparent, explainable and interpretable (RG01), and high-risk AI must enable the people who oversee it to interpret its output, stay aware of automation bias, and override or interrupt it (RG02). The engagement showed how the conditions for such oversight fail in practice, in record- and rule-based decisions and in a synthetic demonstrator: a correction that never reaches the decision, a rule applied over the wrong period, a status mistaken for an outcome, a picture that implies coverage it does not have. This paper contributes the contracts that make those failures visible to an accountable owner: typed evidence with lineage, seven missingness labels, a decision packet that separates claims from inferences, and an action boundary with current checks, shared accounting and verified receipts. Its sharpest recommendation, to begin with zero specialist agents, follows from the same engagement, where the proposed agents did not demonstrate value of their own in the author's internal, AI-assisted test (IN01).

[← 1. Human attention](01-human-attention.md) · [Paper contents](README.md) · [Next: a governed context →](03-governed-context.md)
