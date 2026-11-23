# 13 Evaluation cases

[← 12 Controlled change](../12-controlled-change/README.md) · [Examples](../README.md)

*Synthetic. Each case is a deliberately broken copy of the example set.*

## Purpose

The other folders show the architecture's rules being obeyed. This one shows them being **caught**. Each case copies the example set in memory, makes one small, named change, runs the same checks as `python scripts/validate_examples.py`, and requires that the findings are **exactly** the codes the case declares: no fewer (the check missed it) and no more (the check is too eager). The committed example files are never changed.

These are deterministic functional checks on synthetic data. They are **not** the [EV01–EV12 evaluation programme](../../evaluation/README.md), which has not been run, and passing them says nothing about a real system. See [how the two relate](../../evaluation/README.md#how-the-example-checks-relate-to-ev01ev12).

## Files

| File | What it is |
|---|---|
| [`cases.json`](cases.json) | 32 cases. Each has an id, a family, a title, a reason, the codes it must produce and one or more mutations. A mutation names an instance (`C04 PKT-0417 v2`) and a list of operations (`replace`, `add`, `remove`) at JSON-pointer paths. |

## How it works

1. Load the example set; it has no findings (the first five stages pass).
2. Apply a case's mutations to a deep copy, in memory.
3. If the changed instance no longer matches its schema, the case yields the schema code (`SCH002`) and the semantic checks are skipped, because they assume valid shapes. Otherwise all semantic checks run.
4. Compare the set of codes with the case's `expect`. A difference is a finding (`CASE001`).

To try your own, add a case to `scripts/build_example_data.py` (`case_file`) and run `python scripts/build_example_data.py` and `python scripts/validate_examples.py --only cases`.

## The cases

### Schema

| Case | Mutation | Expect | Why |
|---|---|---|---|
| `CASE-SCH-01` | A required group is removed | `SCH002` | Every contract group is required; a record without a lifecycle is not an evidence record. |
| `CASE-SCH-02` | A timestamp without a time zone | `SCH002` | Timestamps must be complete RFC 3339 date-times; a bare local time is ambiguous. |
| `CASE-SCH-03` | An outcome state outside the vocabulary | `SCH002` | A receipt has five outcome states; "probably done" is not one of them. |
| `CASE-SCH-04` | A timeout that restores the allowance | `SCH002` | An unknown outcome must keep its reservation; claiming reconciliation without an authoritative reference is not allowed. |

### References

| Case | Mutation | Expect | Why |
|---|---|---|---|
| `CASE-REF-01` | A reference names a version that does not exist | `REF001` | References name an exact version, never "latest"; a missing version cannot be resolved. |
| `CASE-REF-02` | A reference changes the original locator | `REF002` | A reference must carry the original locator of the record it names, so a reader can go back to the source. |
| `CASE-REF-03` | A payload pointer that points nowhere | `REF003` | A payload reference must resolve inside the typed payload it names. |
| `CASE-REF-04` | A packet lists a proposal that does not exist | `REF004` | Contract-to-contract references must resolve to the exact version. |
| `CASE-REF-05` | A policy that is not defined | `REF007` | Policy references name a policy and version the domain has defined. |

### Lineage

| Case | Mutation | Expect | Why |
|---|---|---|---|
| `CASE-LIN-01` | A derivation that cycles back to itself | `LIN001` | Derivation ancestry must be acyclic; a record cannot rest on something that rests on it. |
| `CASE-LIN-02` | A relationship type outside the vocabulary | `LIN002` | Typed relationships use the domain's declared vocabulary (contradiction, supersession, validation, invalidation). |
| `CASE-LIN-03` | A supersession the older record does not acknowledge | `LIN003` | If a newer version supersedes an older one, the older one must say so and name its replacement. |

### Kinds

| Case | Mutation | Expect | Why |
|---|---|---|---|
| `CASE-KIND-01` | A producer submits a kind it is not registered for | `KIND001` | A producer cannot promote its output to another kind: an ERP export is not a model inference, and the reverse. |
| `CASE-KIND-02` | A model inference cited as a supported claim | `KIND002` | Model inferences are listed and labeled as inferences; they never support a "supported claim". |

### Corroboration

| Case | Mutation | Expect | Why |
|---|---|---|---|
| `CASE-COR-01` | Two inferences share one origin and do not say so | `COR002` | Agreement between derivations that share a root is not independent corroboration; each must say it has a common origin. |
| `CASE-COR-02` | Agreement presented as independent corroboration | `COR001` | A claim of independent corroboration needs at least two records with different origins. |

### Lifecycle

| Case | Mutation | Expect | Why |
|---|---|---|---|
| `CASE-LIFE-01` | A late correction that does not reach a derived record | `LIFE002` | When a record is superseded, every derivation that rests on it must stop being current. |
| `CASE-LIFE-02` | A newer packet exists but the old one still looks active | `LIFE003`, `LIFE004` | A packet that cites superseded records, or has a newer version, must not stay active. |
| `CASE-LIFE-03` | A pending approval survives the invalidation of its basis | `LIFE005` | An approval cannot outlive the packet it relied on: when the basis is invalidated, the approval is revoked. |

### Missingness

| Case | Mutation | Expect | Why |
|---|---|---|---|
| `CASE-MISS-01` | Labeled stale although it is fresh | `MISS003` | A stale label must be justified by the freshness policy; a fresh record cannot be called stale. |
| `CASE-MISS-02` | A negative without complete coverage | `MISS002` | "Checked and none found" needs complete coverage of its declared scope; otherwise it is only "not retrieved" or "missing". |
| `CASE-MISS-03` | An empty result from a retrieval that never completed | `MISS001`, `REF006` | "Not retrieved" means a completed retrieval returned nothing; an interrupted retrieval is not an empty result. |
| `CASE-MISS-04` | The packet drops a gap its selection recorded | `MISS005` | Every gap in the selection must stay visible in the packet. |

### Packets

| Case | Mutation | Expect | Why |
|---|---|---|---|
| `CASE-PKT-01` | A supported claim that says more than its record | `PKT001` | A supported claim says what its record says, no more. |
| `CASE-PKT-02` | A packet and its selection disagree on the as-of time | `PKT002` | The packet and its selection are one snapshot: they must share the as-of time. |

### Authority

| Case | Mutation | Expect | Why |
|---|---|---|---|
| `CASE-AUTH-01` | A receipt says the action ran although the gateway would have blocked it | `AUTH004` | A receipt must agree with what the commit check decides at the time of the attempt. |
| `CASE-AUTH-02` | A rejection that does not say why | `AUTH005` | A not-executed receipt must name the blocking checks. |
| `CASE-AUTH-03` | A receipt cites a check that does not fail | `AUTH007` | A rejection that cites a check the gateway passes is wrong, or the check has been changed since. |
| `CASE-AUTH-04` | A grant that no longer covers the target | `AUTH004` | An attempt outside the grant's targets must be blocked; a receipt that says otherwise disagrees with the grant. |

### Accounting

| Case | Mutation | Expect | Why |
|---|---|---|---|
| `CASE-ACC-01` | A later receipt version that describes a different attempt | `ACC004` | Versions of one receipt describe the same attempt; a different attempt needs its own receipt. |
| `CASE-ACC-02` | A verified outcome whose accounting is still only reserved | `ACC002`, `ACC003` | A reservation becomes settled only on authoritative reconciliation. |

### Disclosure

| Case | Mutation | Expect | Why |
|---|---|---|---|
| `CASE-DISC-01` | A summary that names what the principal may not see | `DISC001` | A permission-safe summary must not name the withheld detail; a derived output can disclose what its source withholds. |

## Two cases that produce two codes

- `CASE-LIFE-02` fires `LIFE003` (the packet is still active but cites superseded records) and `LIFE004` (a newer version exists): two rules, one mistake.
- `CASE-MISS-03` fires `MISS001` and `REF006`: a failed retrieval makes the `not_retrieved` label unjustified, and also leaves the label's retrieval reference with nothing to point at.

## What this shows, and what it does not

- **Shows:** that each named rule can be broken on purpose and is noticed, that the checks are not silently permissive, and that they do not complain about things that are fine.
- **Does not show:** that the rules are the right ones, that they are complete, or that a real implementation would catch these mistakes. Several families of failure are not represented at all, among them prompt injection, obligation overload and concurrency races.

[← 12 Controlled change](../12-controlled-change/README.md) · [Examples](../README.md)
