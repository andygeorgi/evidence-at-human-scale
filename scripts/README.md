# Scripts

Everything here is plain Python 3.9 or later. The checks use the standard library and one package, `jsonschema` ([`requirements.txt`](../requirements.txt)). They run the same on Windows, macOS and Linux, need no network (except one optional check) and never evaluate or execute file content. See the [security policy](../SECURITY.md).

```bash
python -m pip install -r requirements.txt
python scripts/check_all.py
```

## Run everything

[`check_all.py`](check_all.py) runs the checks below in order, the way continuous integration does, and prints one line for each. It shows a check's own output only when that check fails, or with `--verbose`.

```bash
python scripts/check_all.py                  # all checks
python scripts/check_all.py --list           # name them
python scripts/check_all.py --only links,hygiene
python scripts/check_all.py --skip tests
```

| Check | Script | What a pass shows |
|---|---|---|
| `examples` | `validate_examples.py` | The synthetic examples validate: schema, instances, scenario semantics, gateway scenarios, responses and evaluation cases. |
| `tests` | `python -m unittest discover -s tests` | The unit tests pass, including the checks that the documents' counts match the data. |
| `example-data` | `build_example_data.py --check` | The committed example JSON is exactly what its builder writes. |
| `schema-hash` | `schema_surface_hash.py --check` | The schema's validation surface is unchanged since it was recorded. |
| `links` | `check_links.py --orphans` | Relative links, anchors, images and alt text resolve, and every page is linked from another. |
| `figures` | `check_figures.py` | Every figure is complete, accessible, rendered and in sync with the documents. |
| `svg` | `figures/src/svg_figures.py --check` | The hand-drawn SVGs are what their generator draws. |
| `hygiene` | `check_hygiene.py` | No private link, local path, credential, e-mail address, internal term or unfinished marker, and no file that would not survive a clone. |

A pass says the repository is consistent with itself. It says nothing about any real system ([README](../README.md#what-a-pass-means-and-what-it-does-not)).

## The scripts

### validate_examples.py

The documented command. It validates the [examples](../examples/README.md) in six stages: the schema bundle, the example instances, scenario semantics, the stored gateway evaluations, the stored assistant responses and the evaluation cases.

```bash
python scripts/validate_examples.py                  # everything
python scripts/validate_examples.py --verbose        # the detail line of every stage
python scripts/validate_examples.py --only schema,semantics
python scripts/validate_examples.py --json           # machine-readable result
python scripts/validate_examples.py --examples DIR   # another folder with the same layout
```

Exit code 0 means every stage passed, 1 means at least one finding, 2 means the command could not run (for example `jsonschema` is missing). A finding names a code, the file and location, and the page to read. The [codes](#check-codes) are listed below.

### build_example_data.py

Writes the example data (contract instances, registry, raw exports, stored evaluations, responses and cases) from the one scenario defined in the script. `--check` writes nothing and fails if any committed file differs from a fresh build, so a hand edit shows up. `--out DIR` builds somewhere else.

### schema_surface_hash.py

Prints a hash of the schema's *validation surface*: every keyword that can change what validates, and none of the titles and descriptions. `--check` compares it with the hash recorded in [`contracts/CHANGES.md`](../contracts/CHANGES.md). A change to what validates therefore cannot pass unnoticed. See [`schemas/README.md`](../schemas/README.md).

### check_links.py

Checks every Markdown file for broken relative links, broken heading anchors (by GitHub's rules), missing images, and images without alt text. A path must match in case, so a link that works on Windows or macOS but not on Linux counts as broken. Links inside code are ignored. `--orphans` also lists pages nothing links to (folder READMEs and `.github/` are exempt), and `check_all.py` uses it; `--external` prints the external URLs it found.

### check_figures.py, sync_figures.py and the figure sources

The [figures](../figures/README.md) have one source of truth, [`figures/figures.json`](../figures/figures.json) plus the files in `figures/src/`.

- `sync_figures.py` writes the figure blocks into the pages that use them, between `<!-- figure:Fxx:start -->` and `<!-- figure:Fxx:end -->` markers, and writes the gallery. `--check` writes nothing and fails if a block is out of date.
- `check_figures.py` checks that every figure has a caption, alt text, a long description and a place in the documents, that every picture exists, and that the blocks are in sync.
- `figures/src/svg_figures.py` draws F02, F04, F06 and the banner, in light and dark. It is deterministic. `--check` fails if a committed SVG differs.
- `figures/src/render_mermaid.py` renders the Mermaid sources to light and dark SVG with the Mermaid CLI and records what it rendered in `figures/render-manifest.json`. It is the only script that needs anything beyond Python (Node.js, the Mermaid CLI and a Chromium-based browser), so it is not part of `check_all.py`; `--check` compares the sources with the manifest (it fails if a rendered SVG is missing or older than its source) and needs none of them.

### check_hygiene.py

A pre-publication scan for what must not reach a public repository: private or tenant links, local paths, credentials, e-mail addresses, vocabulary that names the material's private origin, hidden or direction-changing characters, draft markers, claims of finality, Office, PDF, archive and key files, oversized files, and file names that do not survive a clone on Windows or macOS (reserved names, case-only duplicates, paths over 200 characters). It also notes that no license file exists. `--rules` lists every rule and waiver; `--json` prints a machine-readable result. A waiver is a narrow, reviewed line in the script, such as the one for cited public records.

### check_urls.py

Requests every external URL the repository cites and reports the broken ones. It is the only script that uses the network, and it is **not** part of `check_all.py`: a publisher can block a script or be down for reasons that say nothing about this repository. It runs weekly in continuous integration, as an advisory job.

```bash
python scripts/check_urls.py --list      # the URLs and where they are cited; no network
python scripts/check_urls.py             # request each; exit 1 if any is broken
python scripts/check_urls.py --strict    # also fail on refused or unreachable
```

*Broken* means 404 or 410, a name that does not resolve, a refused connection or an invalid certificate. *Refused* means 401, 403, 429 or 999: many publishers block scripts, so open the link in a browser. *Unreachable* means a timeout or a server error: try again later.

### The eahs library

`scripts/eahs/` is the library behind the validation command. It is importable on its own.

| Module | Role |
|---|---|
| `schema.py` | Loads the bundle, validates an instance against its contract, checks the embedded examples, and checks RFC 3339 timestamps strictly. |
| `model.py` | Loads the examples into a model keyed by contract, id and version, with the registry. |
| `semantics.py` | The checks a schema cannot make: references, lineage, lifecycle, missingness, the packet, authority and accounting, disclosure. |
| `gateway.py` | The reference commit check: given a proposal, a grant, a time and the receipts known so far, it allows or blocks and says why. |
| `scenarios.py` | Replays the stored gateway evaluations, including counterfactual overrides, and compares them with the recorded decisions. |
| `response.py` | Renders a response from a packet (a model-free fallback) and checks a stored response against its packet. |
| `cases.py`, `patch.py` | Applies the evaluation cases' mutations in memory and compares the codes the checks produce with the codes each case declares. |
| `findings.py` | A finding: a code, a message, where it happened and where to read about it. |

## Check codes

Each finding has a code. The page named in a finding explains the rule. The [evaluation cases](../examples/13-evaluation-cases/README.md) make eleven of the families fire on purpose (every family except `RESP`, `GW` and `CASE`, which belong to the response and scenario stages and to the case runner itself).

| Code | Meaning |
|---|---|
| `SCH000`–`SCH003` | The schema bundle is invalid; `contract_id` is missing or not C01–C07; an instance does not match its contract; an embedded example does not behave as labeled. |
| `REF001`–`REF007` | A reference does not name an existing exact version, names the wrong kind, points at a missing payload, is neither a record nor a registered external record, names a retrieval that did not complete, or names an undefined policy. |
| `LIN001`–`LIN004` | Derivation ancestry has a cycle; a relationship type is not in the vocabulary; a supersession is not mirrored by the superseded version; a record is its own parent. |
| `KIND000`, `KIND001`, `KIND002`, `KIND004` | A producer is not registered or submits a kind it may not; a model inference is cited as a supported claim; a finding or inference omits the versions that produced it. |
| `COR001`, `COR002` | Agreement is called independent corroboration although the records share an origin; inferences on one origin do not say so. |
| `LIFE001`–`LIFE005` | A superseded record has no replacement; a current record rests on a superseded one; a packet cites a record that is not current; a newer packet leaves an older one active; an approval outlives its packet. |
| `MISS001`–`MISS005` | A missingness label is not justified: not retrieved without a completed retrieval, a negative without complete coverage, stale when fresh, unavailable without an observed failure, or a gap dropped from the packet. |
| `PKT001`–`PKT004` | A supported claim differs from its record; the packet and its selection bind different contexts; coverage points elsewhere; a listed proposal is bound to another packet. |
| `AUTH004`, `AUTH005`, `AUTH007` | A receipt disagrees with the reference commit check: it executed what would be blocked, omits the blocking reasons, or cites a block that would not occur. |
| `ACC001`–`ACC004` | Accounting is wrong: an unresolved outcome released its reservation, allowance was restored without authoritative reconciliation, a verified outcome is not reconciled, or a later receipt describes another attempt. |
| `DISC001` | A derived output discloses detail the reader may not see. |
| `RESP001`–`RESP007` | A stored response uses an unknown statement kind, cites figures the packet lacks, does not label an inference, drops a conflict, gap or recommendation, words a proposal as done, is not withdrawn with its packet, or cites a missing packet. |
| `GW001`, `GW002` | A stored gateway evaluation no longer gives its recorded decision, or cannot be evaluated. |
| `CASE001`–`CASE003` | An evaluation case produces other codes than it declares, repeats an id, or has a mutation that cannot be applied. |
| `HYG101`–`HYG108`, `HYG201`–`HYG205` | The [hygiene](#check_hygienepy) rules; see `check_hygiene.py --rules`. |

The sixteen reason codes of the commit check itself (for example `GRANT_REVOKED`, `EVIDENCE_STALE`, `CUMULATIVE_LIMIT`) are explained in [example 08](../examples/08-blocked-action/README.md#the-commit-time-reason-codes) and exercised by the stored evaluations in examples [07](../examples/07-authority-and-delegation/README.md), [08](../examples/08-blocked-action/README.md), [09](../examples/09-unknown-outcome/README.md), [10](../examples/10-degraded-modes/README.md) and [12](../examples/12-controlled-change/README.md).

## Tests

```bash
python -m unittest discover -s tests
```

The tests in [`tests/`](../tests) cover the schema bundle and the surface hash; the semantic checks (the unmutated example set has no findings, every evaluation case produces exactly its declared codes, and every check family is exercised by a case); the gateway story; the response checker; the catalogue (counts, no results, JSON and CSV agree); the counts the documents state, the code table above and the reason-code table in example 08; and the hygiene and URL scripts. They use only the standard library.

[Examples](../examples/README.md) · [Contributing](../CONTRIBUTING.md)
