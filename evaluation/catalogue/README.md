# Evaluation catalogue

[← Evaluation guide](../README.md) · [Evaluation oracles](../oracles.md)

The evaluation programme as four machine-readable tables. **Every status in them is NOT RUN, NOT ASSESSED or UNSET. There are no results here.** A count in a catalogue (70 fixtures, 47 parameters) is a count of things that are defined, never of things that passed.

Each table is available as JSON (canonical) and CSV (same content; multi-line cells are joined with ` | `).

| Table | Rows | What it is | JSON | CSV |
|---|---|---|---|---|
| Evaluation tests | 12 | EV01–EV12: the expected oracle, metrics, positive denominators, normative gate, owner and prerequisites of each test | [json](evaluation-tests.json) | [csv](evaluation-tests.csv) |
| Matched baselines | 12 | BASE-01 to BASE-12: the comparison framework (four measures × three baselines). Not an achieved benefit. | [json](matched-baselines.json) | [csv](matched-baselines.csv) |
| Fixtures | 70 | The concrete synthetic fixtures `FX01-01` to `FX12-05`: input definition, perturbation or adversarial opportunity, expected oracle, metric, denominator definition, threshold and gate mode | [json](fixtures.json) | [csv](fixtures.csv) |
| Domain parameters | 47 | `DP001`–`DP047`: the thresholds, budgets, limits and policies a domain must set before a test can run. All UNSET. | [json](domain-parameters.json) | [csv](domain-parameters.csv) |

## Reading the tables

**Evaluation tests and matched baselines**: `status` and `observed_status` are `NOT RUN`. `evidence` says what exists: nothing. `owner` says the owner is unassigned. `normative_gate` is the target a run must meet, over positive denominators; it is not an outcome.

**Fixtures**: `status` and `observed_gate_status` are `NOT RUN`; `actual_run_evidence` says no execution was attempted. `gate_mode` is `ratio` (the ratio must equal `normative_threshold` = 1, that is 100%, over a positive denominator) or `zero` (a count of prohibited events must equal 0, only over positive adversarial opportunities). `input_definition` and `perturbation_or_adversarial_opportunity` refer to instances inside [`schemas/contracts-v1.schema.json`](../../schemas/contracts-v1.schema.json) by array index, for example `examples[7]`, so the instances a fixture starts from can be found in the schema, together with the fixed controls the fixture adds.

**Domain parameters**: `value_state` is `UNSET`, `typed_value` is empty, `version` is `UNSET` and `acceptance_state` is `NOT ASSESSED`. `authority_or_policy_basis` says no basis has been supplied. `fixture_mapping` lists the tests that depend on the parameter. `risk_if_unresolved`: the dependent decision is blocked; publication of the reference architecture is not.

## Using them

```python
import json

fixtures = json.load(open("evaluation/catalogue/fixtures.json", encoding="utf-8"))
ev11 = [f["fixture_id"] for f in fixtures if f["evaluation_id"] == "EV11"]
print(len(ev11), ev11[:3])          # 14 ['FX11-01', 'FX11-02', 'FX11-03']
assert all(f["status"] == "NOT RUN" for f in fixtures)
```

## Provenance

The tables are an export from the author's evaluation workbook, with references to the author's internal specification and package files removed or rewritten to repository paths, and legacy diagram identifiers replaced. Status values are preserved exactly. The repository does not regenerate the tables, and nothing here is computed by its checks. One test, [`tests/test_catalogue.py`](../../tests/test_catalogue.py), confirms the row counts and that no row carries a result. The workbook's open questions are not part of the catalogue: the open questions of the architecture are in the [ownership, parameters and tradeoffs reference](../../architecture/ownership-and-tradeoffs.md).

[← Evaluation guide](../README.md) · [Evaluation oracles](../oracles.md)
