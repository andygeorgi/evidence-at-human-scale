# Evaluation catalogue

[← Evaluation guide](../README.md) · [Evaluation oracles](../oracles.md)

The evaluation programme as four tables. **No row has a result.** A test, fixture or baseline is NOT ASSESSED, because running it needs things that do not exist yet. A parameter is UNSET, because nobody has given it a value. A count in this catalogue (70 fixtures, 47 parameters) counts things that are defined, never things that passed.

The JSON files are the source. The CSV files and the test sections of the [oracles page](../oracles.md) are generated from them.

| Table | Rows | One row is | JSON | CSV |
|---|---|---|---|---|
| Evaluation tests | 12 | A test, EV01 to EV12: its name, a summary, the contracts it exercises and its status | [json](evaluation-tests.json) | [csv](evaluation-tests.csv) |
| Fixtures | 70 | A synthetic fixture, `FX01-01` to `FX12-05`: the fixed input, the perturbation applied to it, the expected oracle, the metric, the gate and the contracts it touches | [json](fixtures.json) | [csv](fixtures.csv) |
| Matched baselines | 12 | One measure compared against one simpler baseline, BASE-01 to BASE-12 (four measures, three baselines). A comparison framework, not an achieved benefit. | [json](matched-baselines.json) | [csv](matched-baselines.csv) |
| Domain parameters | 47 | A threshold, budget, limit or policy that a domain has to set before the tests that use it can run, `DP001` to `DP047` | [json](domain-parameters.json) | [csv](domain-parameters.csv) |

## Stated once, true of every row

The tables hold only what differs from row to row. These statements apply to all of them.

- **Status.** Every test, fixture and baseline is `NOT ASSESSED`, and every parameter is `UNSET`. The [status words](../README.md#status-words) define the five states. A test needs an implementation to run against, domain-approved parameters and an owner. None exists, so NOT RUN, which would mean that the test could be run and was not, does not apply.
- **Owner.** No owner is assigned to any test, fixture, baseline or parameter. Each needs an accountable owner before it is run.
- **Denominators.** Every denominator is declared before scoring, includes every attempted case and is greater than zero. An empty or unlabelled denominator is NOT ASSESSED, never a pass. This holds for ratio gates and for zero-event gates, which count only over adversarial opportunities that were attempted.
- **Gates.** `gate_mode` is `ratio` (every assessed case comes out as prescribed: 100%) or `zero` (no prohibited event). A gate is a target for a finite synthetic fixture, not a claim about production.
- **Limits of a fixture.** A fixture is a definition, not an executed test and not a production policy. The schema examples it starts from are structural illustrations. Whoever runs a fixture supplies the permission, lineage, race, authority and outcome oracles it needs.
- **Baselines.** The domain threshold for every comparison is UNSET. No benefit, return, latency or cost is inferred, and a comparison would report its sample size and uncertainty.
- **Parameters.** Each needs a versioned domain policy, workload evidence and an approval record before it has a value, and it would also carry a version, an effective time, an owner and its authority basis. Until then the decisions that depend on it are blocked. Publication of the reference architecture is not. The repository does not promote an illustrative value to a default.

## Reading the tables

**Evaluation tests.** The oracle of a test is the list of the `expected_oracle` of its fixtures, and its metrics are theirs, so neither is repeated. `contracts` is the union of its fixtures'.

**Fixtures.** `input_definition` and `perturbation_or_adversarial_opportunity` name the instances they use inside [`schemas/contracts-v1.schema.json`](../../schemas/contracts-v1.schema.json) by array index, for example `examples[7]` or `x-documentation-examples[9]`, together with the fixed controls the fixture adds. `contracts` lists the contracts of those schema examples and any contract the fixture text names. The script recomputes it, so it cannot claim more than the fixture contains. The contract pages and the schema's `x-contract-crosswalk` answer a different question: which tests exercise a contract as their subject. The two lists are not meant to match.

**Matched baselines.** `measure` is what is compared, `comparison_baseline` is what it is compared with, and `metric` defines the measure.

**Domain parameters.** `used_by` lists the tests that cannot run until the parameter has a value. `BASE` stands for the matched baselines. The parameters a test needs are the ones whose `used_by` names it.

## When a row is run

A row leaves NOT ASSESSED only when something was actually run. Its status becomes `RUN / PASS` or `RUN / FAIL`, and it gets a `run` record with the `command`, the `input` and the `output`. The check refuses a RUN status without that record, and a record on a row that was not run. A test is `RUN / PASS` only if every one of its fixtures is, and one failed fixture cannot be hidden behind a test that says otherwise.

## Using them

```python
import json

fixtures = json.load(open("evaluation/catalogue/fixtures.json", encoding="utf-8"))
ev11 = [f["fixture_id"] for f in fixtures if f["evaluation_id"] == "EV11"]
print(len(ev11), ev11[:3])          # 14 ['FX11-01', 'FX11-02', 'FX11-03']
assert all(f["status"] == "NOT ASSESSED" for f in fixtures)
```

## Where the content comes from

The tests and fixtures were written for this repository's contracts, and the schema's embedded examples are the fixed instances they refer to. Nothing in the catalogue is computed by running the repository's checks. The one test that reads it, [`tests/test_catalogue.py`](../../tests/test_catalogue.py), confirms the row counts, the states, the cross-references and that no row carries a result. The open questions of the architecture are in the [ownership, parameters and tradeoffs reference](../../architecture/ownership-and-tradeoffs.md).

[← Evaluation guide](../README.md) · [Evaluation oracles](../oracles.md)
