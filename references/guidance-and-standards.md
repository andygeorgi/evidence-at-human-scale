# Guidance and standards (RG01, RG02, REF-JSON01)

<a id="rg01"></a>
## RG01 · Trustworthiness characteristics

- **Source:** NIST, *Artificial Intelligence Risk Management Framework (AI RMF 1.0)*, NIST AI 100-1, January 2023.
- **URL:** <https://doi.org/10.6028/NIST.AI.100-1>
- **Passage scope:** sections 3.4 Accountable and Transparent and 3.5 Explainable and Interpretable.
- **Used for:** positioning only ([chapter 2, what is new here](../docs/paper/02-engagement.md#what-is-new-here)).

<a id="rg02"></a>
## RG02 · Human oversight

- **Source:** Regulation (EU) 2024/1689 (Artificial Intelligence Act), Article 14, Human oversight.
- **URL:** <https://eur-lex.europa.eu/eli/reg/2024/1689/oj>
- **Passage scope:** Article 14(4), the abilities to interpret output, remain aware of automation bias, disregard, override or reverse output, and interrupt the system.
- **Used for:** positioning only; no applicability to a jurisdiction or system is asserted.

<a id="ref-json01"></a>
## REF-JSON01 · Structural contracts

- **Source:** JSON Schema, Draft 2020-12.
- **URLs:** <https://json-schema.org/draft/2020-12> · <https://json-schema.org/draft/2020-12/schema> · <https://json-schema.org/draft/2020-12/json-schema-core> · <https://json-schema.org/draft/2020-12/json-schema-validation>
- **Passage scope:** specification details; Draft 2020-12 documents. Metaschema: `/$schema`; `/$id`; `/$vocabulary`; `/allOf`. Core: sections 7.6 and 8.1.1. Validation: sections 3 and 7.2.
- **Qualification:** the dialect identifies encoded constraints; the metaschema includes format annotation, not automatic format assertion. Configure assertion or explicit tests. Only present assertions affect validation; structural validity cannot verify source existence, truth, permission or safe execution.
- **Used for:** the [JSON Schema bundle](../schemas/README.md).

[Sources](README.md)
