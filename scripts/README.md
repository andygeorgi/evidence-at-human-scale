# Scripts

Everything here is plain Python 3.9 or later. The checks use the standard library and one package, `jsonschema` ([`requirements.txt`](../requirements.txt)). They are tested on Windows and Linux (nothing in them is platform-specific), need no network (except one optional check) and never evaluate or execute file content. See the [security policy](../SECURITY.md).

```bash
python -m pip install -r requirements.txt
python scripts/check_all.py
```

## Run everything

[`check_all.py`](check_all.py) runs the checks below in order, the way continuous integration does, and prints one line for each. It shows a check's own output only when that check fails, or with `--verbose`. Exit code 0 means every check that ran passed. A run that leaves checks out with `--only` or `--skip` ends with `PASS for the checks that ran` and says how many it skipped and that its result says nothing about them. A run that skips every check checked nothing: it reports `NOT ASSESSED` and exits with 3.

```bash
python scripts/check_all.py                  # all checks
python scripts/check_all.py --list           # name them
python scripts/check_all.py --only links,hygiene
python scripts/check_all.py --skip tests
python scripts/check_all.py --history        # also scan the whole Git history (needs a full clone)
```

| Check | Script | What a pass shows |
|---|---|---|
| `examples` | `validate_examples.py` | The synthetic examples validate: schema, instances, scenario semantics, gateway scenarios, responses and evaluation cases. |
| `tests` | `python -m unittest discover -s tests` | The unit tests pass, including the checks that the documents' counts match the data. |
| `example-data` | `build_example_data.py --check` | The committed example JSON is exactly what its builder writes. |
| `catalogue` | `build_catalogue.py --check` | The evaluation catalogue's CSV files and the test sections of the oracles page are what its JSON writes, and its tables agree: statuses, run records, references and contracts. |
| `schema-hash` | `schema_surface_hash.py --check` | The schema's validation surface is unchanged since it was recorded. |
| `links` | `check_links.py --orphans` | Relative links, anchors, images and alt text resolve, and every page is linked from another. |
| `structure` | `check_structure.py` | Every page has one H1, no skipped heading levels, no empty table headers and no generic link text. |
| `figures` | `check_figures.py` | Every figure has its metadata, alt text and description, each drawing stays within set width and font-size limits, and the documents are in sync. An automated check on the files: it is not an accessibility assessment and does not show that a figure is usable on a phone. |
| `svg` | `figures/src/svg_figures.py --check` | The SVGs are what their generator draws. |
| `hygiene` | `check_hygiene.py` | No private link, local path, credential, e-mail address, internal term or unfinished marker, and no file that would not survive a clone. |

A pass says the repository is consistent with itself. It says nothing about any real system ([README](../README.md#what-this-shows-and-what-it-does-not)).

## The scripts

### validate_examples.py

The documented command. It validates the [examples](../examples/README.md) in six stages: the schema bundle, the example instances, scenario semantics, the stored gateway evaluations, the stored assistant responses and the evaluation cases.

```bash
python scripts/validate_examples.py                  # everything
python scripts/validate_examples.py --verbose        # the detail line of every stage
python scripts/validate_examples.py --only schema,semantics
python scripts/validate_examples.py --skip cases     # everything except the evaluation cases
python scripts/validate_examples.py --json           # machine-readable result
python scripts/validate_examples.py --examples DIR   # another folder with the same layout
```

Every stage ends in one of five states. A stage passes only if it evaluated at least one item, so an empty folder, or a stage with nothing to look at, is never reported as a success.

| State | Meaning |
|---|---|
| `PASS` | At least one relevant item was evaluated and every required check passed. |
| `FAIL` | Evaluated content breaks a rule. Each finding names a code, the file and location, and the page to read. |
| `SKIPPED` | The stage was left out on purpose, with `--only` or `--skip`. |
| `NOT ASSESSED` | The input the stage needs does not exist, so nothing was evaluated: an empty folder, or a stage without its input files. |
| `INPUT ERROR` | The input is malformed or incomplete and cannot support the stage: JSON that does not parse, a document the checks cannot read, a folder that does not exist. The diagnostic names the file and says how to fix it. |

The exit code is 0 for `PASS`, 1 for `FAIL`, 2 for `INPUT ERROR` (and when the command itself cannot run, for example because `jsonschema` is missing) and 3 for `NOT ASSESSED`. When stages disagree, `INPUT ERROR` outranks `FAIL`, and `FAIL` outranks `NOT ASSESSED`. A run in which nothing passed and nothing failed, such as one that skips every stage, is `NOT ASSESSED`. A run that skips some stages and passes the rest ends with `PASS for the stages that ran`, counts the skipped stages and says that the result says nothing about them; its `--json` result has `"passed": false` and `"complete": false` (`passed` is true only when every stage ran and passed, and `status` is the state of the stages that ran) and lists the `skipped_stages`.

The instance stage comes first: the other four stages read the model it checks. A stage you select pulls it in (the output says so), and the stages that depend on it are `NOT ASSESSED` when it fails, never `PASS`. A normal invalid-input condition produces a diagnostic, not a traceback; `--debug` shows the traceback if you want it. Each diagnostic names the file, the stage, the problem and what to do about it. The [codes](#check-codes) are listed below.

**How input is judged.** Every input is evaluated or explicitly rejected; none disappears.

| Input | Result |
|---|---|
| A top-level `contract_id` that is not a string, or that names no contract (`C99`, or `c02` in the wrong case) | `INPUT ERROR` (`ID003`, `ID004`). A `contract_id` claims the file is a contract instance, so it must be valid. |
| A file named like a contract instance (`c02-….json`) that has no `contract_id`, is not a JSON object, or names another contract than its file name | `INPUT ERROR` (`ID005`) |
| A stage file without the list its stage evaluates: `evaluations` (gateway scenarios), `cases` (evaluation cases) or `statements` (a response) | `INPUT ERROR` (`INP002`): a missing list is never read as an empty one |
| A row of a gateway-scenario or case file that is not shaped like an evaluation: not an object, or without its proposal, grant, commit time (that is a time) or expected result (a decision and its codes), or with a ledger mode or an override target that no check knows, which would be ignored (a scenario); or without a `case_id`, its expected codes or at least one mutation, or with a mutation that has no target or no operations (a case) | `INPUT ERROR` (`INP002`) that names the row. The file is rejected as a whole, so the row is not counted as evaluated and nothing in that file is reported as passed or failed. A well-formed row that names a record that does not exist is a `FAIL` (`GW002`, `CASE003`). |
| A gateway-scenario or case file whose list is explicitly empty | It evaluates nothing. The stage is `NOT ASSESSED` if nothing else was evaluated, and otherwise passes and names the empty file in its detail. |
| A raw source export: a JSON file with no `contract_id`, or any file under a folder named `raw` | Read as non-contract input and not validated as an instance. The instance stage says how many there were. |
| `--only schema` | The schema bundle is checked and the folder is never indexed, so a malformed file in it cannot disturb the run. |
| `--only` or `--skip` with no stage name (`--only ""`, `--only ,`) | Refused with exit code 2: an empty selection is not read as "every stage". |
| JSON that Python reads and other readers do not: `NaN`, `Infinity`, a number too large for a float (a whole number as well as a fraction), an object that repeats a key, or a document nested more than 40 levels deep (the examples need 11) | `INPUT ERROR` (`ID000`) that names the file. |
| A `registry.json` section that is not shaped as the checks read it (`producers` as a list, a freshness limit that is not a number of hours, the holders of a role that are not names, a review-log entry without its actor or with a time that is not a time, and so on) | `INPUT ERROR` (`ID000`) that names `registry.json` and the section. |

### build_example_data.py

Writes the example data (contract instances, registry, raw exports, stored evaluations, responses and cases) from the one scenario defined in the script. `--check` writes nothing and fails if any committed file differs from a fresh build, so a hand edit shows up. `--out DIR` builds somewhere else.

### build_catalogue.py

Writes the CSV copies of the [evaluation catalogue](../evaluation/catalogue/README.md) and the test sections of the [oracles page](../evaluation/oracles.md) from the catalogue's JSON tables, which are the source. `--check` writes nothing. It fails when a copy differs from what the JSON would write, and when the tables contradict one another: a status that is not one of the five defined states, a RUN status without a `run` record (command, input, output), a test that is `RUN / PASS` although one of its fixtures is not, a reference to a test that does not exist, or a `contracts` list that is not what the fixture's own references name.

### schema_surface_hash.py

Prints a hash of the schema's *validation surface*: every keyword that can change what validates, and none of the titles and descriptions. `--check` compares it with the hash recorded in [`contracts/CHANGES.md`](../contracts/CHANGES.md). A change to what validates therefore cannot pass unnoticed. See [`schemas/README.md`](../schemas/README.md).

### check_links.py

Checks every Markdown file for broken relative links, broken heading anchors (by GitHub's rules), missing images, and images without alt text. A path must match in case, so a link that works on Windows or macOS but not on Linux counts as broken. Links inside code are ignored. `--orphans` also lists pages nothing links to (folder READMEs and `.github/` are exempt), and `check_all.py` uses it; `--external` prints the external URLs it found.

### check_structure.py

Checks the structure a screen-reader user navigates by, on every Markdown page: exactly one H1 (`STR001`), no heading level skipped going down (`STR002`), no link text that says nothing out of context, such as "here" (`STR003`), and no table with an empty header row (`STR004`). Code and HTML comments are ignored. It does not replace an accessibility audit; see the [limitations](../CHANGELOG.md#known-limitations).

### check_figures.py, sync_figures.py and the figure sources

The [figures](../figures/README.md) have one source of truth, [`figures/figures.json`](../figures/figures.json) plus the files in `figures/src/`.

- `sync_figures.py` writes the figure blocks into the pages that use them, between `<!-- figure:Fxx:start -->` and `<!-- figure:Fxx:end -->` markers, the banner in the README (below its first paragraph, so that the title and the first paragraph come first on a narrow screen), between `<!-- banner:start -->` and `<!-- banner:end -->`, and the gallery. `--check` writes nothing and fails if one of them is out of date.
- `check_figures.py` checks that every figure has a caption, alt text, a long description and a place in the documents, that every picture exists and has a title and a description, that a default drawing is at most 380 px wide and a wide drawing 800 to 900 px, that no text is smaller than 13 px, that no document contains a Mermaid block, and that the blocks are in sync.
- `figures/src/svg_figures.py` draws every figure and the banner, in light and dark, with the helpers in `figures/src/kit.py`. It is deterministic. `--check` fails if a committed SVG differs. It takes the title and the description inside each file from `figures/figures.json`. It needs nothing beyond Python.

### check_hygiene.py

A pre-publication scan for what must not reach a public repository: private or tenant links, local paths, credentials, e-mail addresses, vocabulary that names the material's private origin, confidentiality-label wording, the name of the authority that the paper discusses, hidden or direction-changing characters, draft markers, claims of finality, Office, PDF, archive and key files, oversized files, and file names that do not survive a clone on Windows or macOS (reserved names, case-only duplicates, paths over 200 characters). It also notes when no license file exists. `--rules` lists every rule and the pinned lines; `--json` prints a machine-readable result.

**The authority's name is allowed in one place only.** The paper discusses a public authority and cites public records whose own titles and addresses contain its name. The name may appear on exactly those lines, quoted as the record gives it, and nowhere else: not in prose, a heading, example data, a file name, a commit message or a figure's metadata. The scanner enforces this without repeating the name. It knows the name as a digest, so a word matches by its first letters in any case and inflection, and it works in continuous integration, which has no private list. A match is excused only on a line pinned in `PUBLIC_SOURCE_LINES` in the script: the file and the SHA-256 of the whole line. A line that differs by one character, the same line in another file, or the same word anywhere else is a finding. `python scripts/check_hygiene.py --pin references/public-records.md:10` prints the entry for one line. Add one only in a reviewed commit, and only when the whole line is a public record's own title or address; `tests/test_hygiene.py` checks that the pins are exactly the lines that name the authority.

**The scanner and its tests are scanned too.** The two files have to quote the patterns they look for, so a rule that reads them finds its own words. No whole file is exempt. `QUOTED_LINES` in the script excuses one rule on one exact line of one exact file, pinned by the SHA-256 of the whole line (the script cannot list the samples themselves, because they would be matches). A line that differs by a character, text added to a pinned line or beside it, the same line in another file, and any other rule on the pinned line are findings, so a private term, the authority's name, a link, a path, a label, a credential or an address pasted into either file is found like anywhere else. `python scripts/check_hygiene.py --pin-quoted tests/test_hygiene.py:10` prints the digest and the rules for one line. `tests/test_hygiene.py` checks that every line the two files quote is pinned, and that every pin is a line of the current file or of an earlier version, which the history scan judges too.

**A denial excuses the claim it negates and no other.** A claim of finality (HYG108) is excused only by a denial that stands directly in front of it, separated at most by a few filler words (the, a, this, here, is, yet and the like), in the same sentence: "not the final version" does not excuse a later claim in the next sentence or after a comma, and a denial followed by an unrelated clause excuses nothing.

**The whole history.** `--history` also reads everything that a push of the whole history would publish: every file version that any commit added or changed, at each path that held it (reported as `path @ commit`), the path names in every commit, every commit message, every author and committer, and every ref, under the same rules. A term that was removed from the tree is still in an old commit, and a commit message or an author's address is published with it. A file version is judged by its blob and its path together, because what a path allows (a pinned line, a quoted line, a blocked file type) belongs to that path: content that one path excused is judged again at the next path that held it. Each blob is read once. The scan needs Git and the whole history, and takes a few seconds. A shallow clone is refused, because most of its history is missing and a scan of it would pass on commits it never read. `check_all.py --history` runs it with the other checks, and continuous integration does so on a full checkout (`fetch-depth: 0`); a download without `.git` or a shallow clone fails it instead of passing. A maintainer also runs `python scripts/check_hygiene.py --history`, with the private term list, before every push. Nothing in the history is rewritten for residue that is known and not sensitive: if a scan ever finds one, the decision is a narrow exception for that path and that line, in a reviewed commit.

**The private term list is not in this repository.** A list of the names that identify the private origin of the material would publish them, so `check_hygiene.py` reads it from outside: one regular expression per line, in a file named `.hygiene-private-terms` in the repository folder (Git ignores that name, and `HYG207` fails if a file of that name is among the files to publish or anywhere in the history, at any path and in any letter case; the scanner never reads such a file, so no finding can print what it holds) or in the environment variable `EAHS_PRIVATE_TERMS`, which holds a path to such a file or the lines themselves. Continuous integration has no list, and none is kept in the workflow or in the repository's settings, so it cannot scan for private terms; a maintainer who has one runs the scan locally before every release. Without a list the scan still runs and says that the private-term scan is off; it then looks for confidentiality-label wording and for the authority's name only.

### check_urls.py

Requests every external URL the repository cites and reports the broken ones. It is the only script that uses the network, and it is **not** part of `check_all.py`: a publisher can block a script or be down for reasons that say nothing about this repository. It runs weekly in continuous integration, as an advisory job.

```bash
python scripts/check_urls.py --list      # the complete inventory of cited URLs and where each is cited; no network
python scripts/check_urls.py             # request each; exit 1 if any is broken
python scripts/check_urls.py --strict    # also fail on refused or unreachable
```

*Broken* means 404 or 410, a name that does not resolve, a refused connection or an invalid certificate. *Refused* means 401, 403, 429 or 999: many publishers block scripts, so open the link in a browser. *Unreachable* means a timeout or a server error: try again later.

### The eahs library

`scripts/eahs/` is the library behind the validation command. It is importable on its own.

| Module | Role |
|---|---|
| `schema.py` | Loads the bundle, validates an instance against its contract, checks the embedded examples, and checks RFC 3339 timestamps strictly. |
| `model.py` | Loads the examples into a model keyed by contract, id and version, with the registry. It reads JSON strictly, finds `registry.json` in any letter case, checks a `contract_id` before it is used as a key, and reports a file it cannot index instead of skipping it. |
| `semantics.py` | The checks a schema cannot make: references, lineage, lifecycle, missingness, the packet, authority and accounting, disclosure, accountability. |
| `gateway.py` | The reference commit check: given a proposal, a grant, an attempt time and the receipts known so far, it allows or blocks and says why. It uses only what was available and valid at the attempt, and blocks when a time it needs is missing or unknown. |
| `scenarios.py` | Replays the stored gateway evaluations, including counterfactual overrides of the proposal, the grant or one evidence record, and compares them with the recorded decisions. |
| `response.py` | Renders a response from a packet (a model-free fallback) and validates a stored response two ways: **canonical** validation compares it with the renderer's output, and **structural** validation checks named constraints. The structural validation does not prove that prose is semantically correct. A response's status and withdrawal reason come from its packet (`trusted_lifecycle`), never from the response. |
| `disclosure.py` | The viewer projection of Figure F09 as code: it binds a permission decision to the requesting principal, asks the permission questions first and builds the entry from the decision, not from the restricted input. The example builder and the tests use it. It is not an authorization service. |
| `status.py` | The five states a stage can end in (`PASS`, `FAIL`, `SKIPPED`, `NOT ASSESSED`, `INPUT ERROR`) and how they combine. |
| `cases.py`, `patch.py` | Applies the evaluation cases' mutations in memory and compares the codes the checks produce with the codes each case declares. |
| `findings.py` | A finding: a code, a message, where it happened, what to fix and where to read about it. |

## Check codes

Each finding has a code. The page named in a finding explains the rule. The [evaluation cases](../examples/13-evaluation-cases/README.md) make twelve of the families fire on purpose (every family except `RESP`, `GW`, `CASE`, `ID` and `INP`, which belong to the response and scenario stages, to the case runner itself and to unreadable input).

| Code | Meaning |
|---|---|
| `ID000`–`ID005` | Input that cannot be indexed: a file that is not valid JSON (this includes `NaN`, `Infinity`, a number too large for a float and an object that repeats a key, which other JSON readers do not accept), a `registry.json` with a section that is not shaped as the checks read it, two registry files that differ only by letter case, an identity that is duplicated, an instance without a readable identity, a `contract_id` that is not a string or names no contract, a file named like a contract instance that is not one. These make the instance stage an `INPUT ERROR`. |
| `INP001`–`INP003` | Input that cannot support a stage: a folder or the schema bundle that cannot be read, a document the checks cannot evaluate (including a stage file that lacks the list the stage evaluates, and a row of a scenario or case file that is not shaped like an evaluation), or a `registry.json` that the stage needs and the folder does not have. These make the stage an `INPUT ERROR`. |
| `SCH000`–`SCH003` | The schema bundle is invalid; `contract_id` is missing or not C01–C07; an instance does not match its contract; an embedded example does not behave as labeled. |
| `REF001`–`REF007` | A reference does not name an existing exact version, names the wrong kind, points at a missing payload, is neither a record nor a registered external record, names a retrieval that did not complete, or names an undefined policy. |
| `LIN001`–`LIN005` | Derivation ancestry has a cycle; a relationship type is not in the vocabulary; a supersession is not mirrored by the superseded version; a record is its own parent; a model inference states a figure that none of the records it rests on holds (`LIN005`). |
| `KIND000`, `KIND001`, `KIND002`, `KIND004` | A producer is not registered or submits a kind it may not; a model inference is cited as a supported claim; a finding or inference omits the versions that produced it. |
| `COR001`, `COR002` | Agreement is called independent corroboration although the records share an origin; inferences on one origin do not say so. |
| `LIFE001`–`LIFE005` | A superseded record has no replacement; a current record rests on a superseded one; a packet cites a record that is not current; a newer packet leaves an older one active; an approval outlives its packet. |
| `MISS001`–`MISS005` | A missingness label is not justified: not retrieved without a completed retrieval, a negative without complete coverage, stale when fresh, unavailable without an observed failure, or a gap dropped from the packet. |
| `PKT001`–`PKT005` | A supported claim differs from what the claims it cites say (one reference, or several said together in the order cited); the packet and its selection bind different contexts; coverage points elsewhere; a listed proposal is bound to another packet; a claim that rests on a payload, alone or beside claim references, leaves out the payload's status or all of its figures, states a status or a figure the payload does not hold, or puts a figure after a payload field's name that is not that field's value. |
| `AUTH004`, `AUTH005`, `AUTH007` | A receipt disagrees with the reference commit check: it executed what would be blocked, omits the blocking reasons, or cites a block that would not occur (including a receipt that calls an attempt the gateway allows a rejection, which would free the capacity that attempt holds). |
| `AUTH008` | A verified outcome is not verified for its own attempt: the verification (or a record it cites) names another target or another action than the receipt, or was made before the attempt; or a record it cites is not an observation of the receipt's target, was observed before the attempt or after the verification, or had not been admitted by the verification. A gateway rejection alone is not a verified no-effect. |
| `AUTH009` | A receipt is for another target than its proposal names. A verification can show only what happened to the receipt's own target, so the receipt's target must be the proposal's exact target (later versions are held to the first by `ACC004`). |
| `ACC001`–`ACC004` | Accounting is wrong: an unresolved outcome released its reservation, allowance was restored without authoritative reconciliation, a verified outcome is not reconciled, or a later receipt describes another attempt. |
| `DISC001`–`DISC005` | A derived output discloses detail the reader may not see: a protected term (`DISC001`, a backstop scan); an entry about an unreadable source although its permission decision withholds its existence or there is none (`DISC002`); an entry that is not exactly the generic disclosure its decision configures, in its wording or in any sibling field (`DISC003`); a decision that does not bind to the requesting principal, tenant or purpose of the context (`DISC004`); a named record that belongs to another tenant or purpose (`DISC005`). |
| `ROLE001`–`ROLE008` | The roles are not kept apart, or cannot be checked: an exact approval from someone who is not an approver, or from the requestor of the packet; a packet reviewed by someone who is not a Decision Owner; an approval with no earlier review of its packet by a Decision Owner; a registry that names no roles although the folder holds approvals, reviewed packets, grants or receipts; a receipt made by someone other than the grantee of the grant it cites (`ROLE006`); a grantee or executor that is not a registered executor (`ROLE007`); the assistant workload as a grantee or an executor (`ROLE008`). |
| `RESP001`–`RESP017` | A stored response breaks a structural constraint: an unknown statement kind, a statement with no text, an uncited or mis-cited statement, a figure or currency the packet lacks, an unlabeled inference, a dropped conflict, gap, recommendation or obligation, supported claims that are cited but not stated, an action worded as done, a status that is not the one the packet's state requires (a response cannot define its own lifecycle), a missing packet, a conflict or gap closed in words, a missingness label not said, dropped uncertainty, added certainty, a changed status word, a statement that names a record it does not rest on, a missing or unknown status, a withdrawal reason that is not the packet's own (it must be exactly the packet's reason, with at most the introduction "This response was withdrawn:", and may not reverse or invent a supersession), a statement in a withdrawn response that reads as current advice, or a statement about an input the reader may not read that is not exactly the permitted wording (or mentions one the reader may not know exists). |
| `RESP101`, `RESP102` | A response that says a renderer wrote it differs from the renderer's output (`RESP101`), and the difference adds or removes a negation, changes a status word or a figure, or opens or closes a conflict (`RESP102`). |
| `GW001`, `GW002` | A stored gateway evaluation no longer gives its recorded decision, or cannot be evaluated. |
| `CASE001`–`CASE003` | An evaluation case produces other codes than it declares, repeats an id, or has a mutation that cannot be applied. |
| `HYG101`–`HYG108`, `HYG201`–`HYG207` | The [hygiene](#check_hygienepy) rules; see `check_hygiene.py --rules`. |
| `STR001`–`STR004` | The [structure](#check_structurepy) rules: one H1, no skipped heading level, no generic link text, no empty table header. |

The twenty-one reason codes of the commit check itself (for example `GRANT_REVOKED`, `EVIDENCE_NOT_YET_ADMITTED`, `CUMULATIVE_LIMIT`) are explained in [example 08](../examples/08-blocked-action/README.md#the-commit-time-reason-codes) and exercised by the stored evaluations in examples [07](../examples/07-authority-and-delegation/README.md), [08](../examples/08-blocked-action/README.md), [09](../examples/09-unknown-outcome/README.md), [10](../examples/10-degraded-modes/README.md) and [12](../examples/12-controlled-change/README.md).

## Tests

```bash
python -m unittest discover -s tests
```

The tests in [`tests/`](../tests) cover the schema bundle and the surface hash; the five validation states and what the command does with an empty folder, a partial stage selection and malformed input (a contract id that is not a string, an unknown contract, a missing or an empty collection, zero-byte JSON, and valid and invalid files mixed); the semantic checks (the unmutated example set has no findings, every evaluation case produces exactly its declared codes, and every check family is exercised by a case); supported claims held to every reference they cite and to the status and figures of a payload; permission before disclosure, including that an unauthorized requestor's view is the same with and without a restricted record; the distinct roles of requestor, Decision Owner, approver and executor, and that an execution receipt names the grantee of its grant; the gateway story and its as-of checks (evidence admitted after the attempt, a revocation observed after it, a time that is missing or unknown, and the equality boundary); the three outcomes of a receipt and the binding of a verification to its own attempt, target and action; the canonical and structural response validations and their adversarial cases, including a lifecycle that the packet and not the response decides and the minimum coverage of a free-form response; the catalogue (counts, the five states and the rule that a run needs its command, input and output, no field repeated, contracts derived from each fixture's own references, and generated copies that agree with the JSON); the counts the documents state, the code table above and the reason-code table in example 08; the Quickstart output in the README; wording that was removed on purpose; and the hygiene and URL scripts. They use only the standard library.

[Examples](../examples/README.md) · [Contributing](../CONTRIBUTING.md)
