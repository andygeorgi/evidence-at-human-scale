# Scripts

Everything here is plain Python 3.9 or later. The checks use the standard library and one package, `jsonschema` ([`requirements.txt`](../requirements.txt)), need no network (except one optional check) and never evaluate or execute file content. See the [security policy](../SECURITY.md).

```bash
python -m pip install -r requirements.txt
python scripts/validate_examples.py
python scripts/check_all.py
```

## Run everything

[`check_all.py`](check_all.py) runs the checks below in order and prints one line for each. It shows a check's own output only when that check fails, or with `--verbose`. Exit code 0 means every check that ran passed. A run that leaves checks out with `--only` or `--skip` ends with `PASS for the checks that ran` and says how many it skipped and that its result says nothing about them. A run that skips every check checked nothing: it reports `NOT ASSESSED` and exits with 3.

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
| A stage file without the list its stage evaluates: `evaluations` (gateway scenarios), `cases` (evaluation cases) or `statements` (a response) | `INPUT ERROR` (`INP002`): a missing list is never read as an empty one. This is reported also when the stage cannot run because the folder holds no valid instances: a file of the wrong shape is not hidden behind `NOT ASSESSED`. |
| A row of a gateway-scenario or case file that is not shaped like an evaluation: not an object, or without its proposal, grant, commit time (that is a time) or expected result (a decision and its codes), or with a ledger mode or an override target that no check knows, which would be ignored, or with an override path that is not a JSON pointer (a scenario); or without a `case_id`, its expected codes or at least one mutation, or with a mutation that has no target or no operations, or with an operation whose path is not a JSON pointer (a case) | `INPUT ERROR` (`INP002`) that names the row. This is reported also when the stage cannot run for want of valid instances, like a missing list. The file is rejected as a whole, so the row is not counted as evaluated and nothing in that file is reported as passed or failed. A well-formed row that names a record that does not exist, or a position in a list that does not exist (`/items/7` in a list of three, an index with a leading zero or a sign, an index too large to count), is a `FAIL` (`GW002`, `CASE003`) that says what is missing: the record that does not exist (named by its target, or by its override), or the operation and the path that lead nowhere, with the step that has nothing in it. A JSON pointer starts with `/` and names every step: `limits_lifecycle/expiry` is not one, and is not read as if it were. |
| A gateway-scenario or case file whose list is explicitly empty | It evaluates nothing. The stage is `NOT ASSESSED` if nothing else was evaluated (with no registry in the folder too, because there is nothing to replay), and otherwise passes and names the empty file in its detail. |
| A raw source export: a JSON file with no `contract_id`, or a file under a folder named `raw` (which may carry a `contract_id` of its own business) | Read as non-contract input and not validated as an instance. The instance stage says how many other files there were. Two kinds of file name are reserved and win over the folder: a name like a contract instance (`c02-….json`, see above) and the names of the stage files (`gateway-scenarios.json`, `cases.json`, `response-*.json`), which their stages read wherever the file lies. A raw export must not be given one of those names, and every diagnostic about such a file (not an object, no list, a list that is not a list, a row that is not shaped like an evaluation) says to rename it. |
| `--only schema` | The schema bundle is checked and the folder is never indexed, so a malformed file in it cannot disturb the run. |
| `--only` or `--skip` with no stage name (`--only ""`, `--only ,`), or with a stage that does not exist | Refused with exit code 2: an empty selection is not read as "every stage". With `--json` the refusal is a JSON result (`INP001`, with the hint) and not only a usage message. |
| JSON that Python reads and other readers do not: `NaN`, `Infinity`, a number too large for a float (a whole number as well as a fraction), a number with more digits than a double keeps (`40.000000000000001` reads as `40.0` here, and other readers round it), an object that repeats a key, or a document nested more than 40 levels deep (the examples need 11) | `INPUT ERROR` (`ID000`) that names the file. |
| A `registry.json` section that is not shaped as the checks read it (`producers` as a list, a freshness limit that is not a number of hours, a policy without a text `type`, the holders of a role that are not names, a review-log entry without its actor or with a time that is not a time, a recorded state of the target without its entity, its time or its state, a permission decision whose view, gap, retrieval or flags have the wrong kind or whose projected parts are not text or objects as the schema wants them, and so on) | `INPUT ERROR` (`ID000`) that names `registry.json` and the section. |

### build_example_data.py

Writes the example data (contract instances, registry, raw exports, stored evaluations, responses and cases) from the one scenario defined in the script. `--check` writes nothing and fails if any committed file differs from a fresh build, so a hand edit shows up. `--out DIR` builds somewhere else.

### build_catalogue.py

Writes the CSV copies of the [evaluation catalogue](../evaluation/catalogue/README.md) and the test sections of the [oracles page](../evaluation/oracles.md) from the catalogue's JSON tables, which are the source. `--check` writes nothing. It fails when a copy differs from what the JSON would write, and when the tables contradict one another: a status that is not one of the five defined states, a RUN status without a `run` record (command, input, output), a test that is `RUN / PASS` although one of its fixtures is not, a reference to a test that does not exist, or a `contracts` list that is not what the fixture's own references name.

### schema_surface_hash.py

Prints a hash of the schema's *validation surface*: every keyword that can change what validates, and none of the titles and descriptions. `--check` compares it with the hash recorded in [`contracts/CHANGES.md`](../contracts/CHANGES.md). A change to what validates therefore cannot pass unnoticed. See [`schemas/README.md`](../schemas/README.md).

### check_links.py

Checks every Markdown file for broken relative links, broken heading anchors (by GitHub's rules), missing images, and images without alt text. A path must match in case, so a link that works on Windows or macOS but not on Linux counts as broken. Links inside code are ignored. `--orphans` also lists pages nothing links to (folder READMEs and `.github/` are exempt), and `check_all.py` uses it; `--external` prints the external URLs it found.

### check_structure.py

Checks the structure a screen-reader user navigates by, on every Markdown page: exactly one H1 (`STR001`), no heading level skipped going down (`STR002`), no link text that says nothing out of context, such as "here" (`STR003`), and no table with an empty header row (`STR004`). Code and HTML comments are ignored. It does not replace an accessibility audit; see [claims and limits](../docs/claims-and-limits.md).

### check_figures.py, sync_figures.py and the figure sources

`sync_figures.py` writes the figures into the pages that show them, and `check_figures.py` checks that every figure has its metadata, alt text and description, that every drawing stays within its limits and that the pages are in sync. The pictures are drawn by `figures/src/svg_figures.py`. To change a figure, see the [contributing guide](../CONTRIBUTING.md#change-examples-the-catalogue-and-figures).

### check_hygiene.py

A pre-publication scan for what must not reach a public repository: private or tenant links, local paths, credentials, e-mail addresses, vocabulary that names the material's private origin, confidentiality-label wording, the name of the authority that the paper discusses (allowed only on the exact lines that quote a public record's own title or address), hidden or direction-changing characters, draft markers, claims of finality, Office, PDF, archive and key files, oversized files, and file names that do not survive a clone on Windows or macOS (reserved names, case-only duplicates, paths over 200 characters). It also notes when no license file exists. `--rules` lists every rule and the pinned lines; `--json` prints a machine-readable result. With `--history` it also reads every file version, path, commit message, author, committer and ref that a push of the whole history would publish, and it refuses a shallow clone. The list of private terms is kept outside the repository, and the scanner never reads it as a file of the repository. How the pins, the exceptions and that list work is documented in the script itself.

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
| `model.py` | Loads the examples into a model keyed by contract, id and version, with the registry. It reads JSON strictly, finds `registry.json` in any letter case, checks a `contract_id` before it is used as a key, and reports a file it cannot index instead of skipping it. A version name is exact: it orders the versions of one record by the numbers in their names (`v2` before `v10`), and refuses to guess where that gives no order (`v1` and `v01`, or a name with no number). |
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
| `ID000`–`ID005` | Input that cannot be indexed: a file that is not valid JSON (this includes `NaN`, `Infinity`, a number too large for a float or with more digits than a double keeps, and an object that repeats a key, which other JSON readers do not accept), a `registry.json` with a section that is not shaped as the checks read it, two registry files that differ only by letter case, an identity that is duplicated, an instance without a readable identity, a `contract_id` that is not a string or names no contract, a file named like a contract instance that is not one. These make the instance stage an `INPUT ERROR`. |
| `INP001`–`INP003` | Input that cannot support a stage: a folder or the schema bundle that cannot be read, a document the checks cannot evaluate (including a stage file that lacks the list the stage evaluates, and a row of a scenario or case file that is not shaped like an evaluation), or a `registry.json` that the stage needs and the folder does not have (reported together with whatever else is wrong with the files of that stage). These make the stage an `INPUT ERROR`. |
| `SCH000`–`SCH003` | The schema bundle is invalid; `contract_id` is missing or not C01–C07; an instance does not match its contract; an embedded example does not behave as labeled. |
| `REF001`–`REF008` | A reference does not name an existing exact version, names the wrong kind, points at a missing payload, is neither a record nor a registered external record, names a retrieval unit that is not a completed unit of the selection its entry belongs to (the version of that selection, listed once; a unit of another selection with the same name is another run), names an undefined policy, or names a `claim_id` that more than one claim of that exact version carries (`REF008`: a `claim_id` identifies one claim within one version of a record, so the record is found as well as each reference to the repeated id; the same id in another record or another version is valid). |
| `LIN001`–`LIN009` | Derivation ancestry has a cycle; a relationship type is not in the vocabulary; a supersession is not mirrored by the superseded version; a record is its own parent; a model inference states a figure that none of the records it rests on holds (`LIN005`); a deterministic finding names no record as an input although its producer is not registered as computing over data outside the records (`LIN006`); a source record assertion, an original, names a parent (`LIN007`); a declared parent was not admitted and ingested by the time its child was admitted (`LIN008`, instants compared, equality allowed); a supersession edge does not start at the record that holds it, or ends at that record (`LIN009`). |
| `KIND000`, `KIND001`, `KIND002`, `KIND004` | A producer is not registered or submits a kind it may not; a model inference is cited as a supported claim; a finding or inference omits the versions that produced it. |
| `COR001`, `COR002` | Agreement is called independent corroboration although the records share an origin; inferences on one origin do not say so. Source records that declare the same source system, record locator and immutable version (or snapshot) are one origin, whatever their record ids are; nothing else is matched. |
| `LIFE001`–`LIFE006` | A superseded record has no replacement; a current record rests on a superseded one; a packet cites a record that is not current; a newer packet leaves an older one active; an approval outlives its packet; the versions of one record cannot be put in order, because two names have the same numbers (`v1` and `v01`) or a name has none (`LIFE006`). |
| `MISS001`–`MISS005` | A missingness label is not justified: not retrieved without a completed retrieval, or with a retrieval whose times are not in order (attempted at or before it completed, and completed by the as-of time of the selection; instants compared, equality allowed, an unreadable time is not trusted) or that completed at another instant than the entry states, a negative without complete coverage, stale when fresh, unavailable without an observed failure, or a gap dropped from the packet. |
| `PKT001`–`PKT005` | A supported claim differs from what the claims it cites say (one reference, or several said together in the order cited); the packet and its selection bind different contexts, or the context, the selection and the packet do not state one as-of time (instants are compared, and not how they are written), or the selection reads time that the interval of its context does not cover; coverage points elsewhere; a listed proposal is bound to another packet; a claim that rests on a payload, alone or beside claim references, leaves out the payload's status or all of its figures, states a status or a figure the payload does not hold, or puts a figure beside a payload field's name (in words, or as the field's own name such as `quantity_invoiced`, and also for a pointer to one value such as `/value/quantity_invoiced`) that is not that field's value in any of the payloads it cites, or beside the name of a field of the record that the claim does not cite, whatever the figure is (also a field that holds text, such as `invoice_id`, and a name written between quotation marks (straight or typographic) or backticks after its figure). A figure after a colon is stated, with its sign (`variance:-40.0`), and a colon after a digit makes a time. |
| `PKT006`–`PKT009` | A decision snapshot is not held together: a proposal is bound to another context than the packet it is bound to (`PKT006`); a packet cites a record that was not available at its as-of time, because it was admitted or ingested after it, was never admitted, or has no readable time, or because a record it cites is derived from an input that was not (`PKT007`; a challenge link names later evidence on purpose and is not a citation of this kind); a packet lists an obligation that its selection does not hold, one of another selection, one that its selection holds more than once, or the same one twice (`PKT008`); a packet leaves out an obligation of its selection (`PKT009`). |
| `AUTH004`, `AUTH005`, `AUTH007` | A receipt disagrees with the reference commit check, in any of its versions: it executed what would be blocked, omits the blocking reasons (a reason is named whole: `GRANT_REVOKED_LEGACY` does not name `GRANT_REVOKED`), or cites a block that would not occur (a check that the gateway passes for the attempt, whether the gateway blocks it for other reasons or not, and a receipt that calls an attempt the gateway allows a rejection, which would free the capacity that attempt holds). |
| `AUTH008` | A verified outcome is not verified for its own attempt: the verification (or a record it cites) names another target or another action than the receipt, or was made before the attempt; or a record it cites is not an observation of the receipt's target, was observed before the attempt or after the verification, or had not been admitted by the verification. A gateway rejection alone is not a verified no-effect. |
| `AUTH009` | A receipt is for another target than its proposal names. A verification can show only what happened to the receipt's own target, so the receipt's target must be the proposal's exact target (later versions are held to the first by `ACC004`). |
| `AUTH010` | A structured effect of a receipt is for another action than the proposal the receipt cites, or on another target than the receipt's own. The effect is not an effect of that attempt, so the ledger does not count it. |
| `ACC001`–`ACC007` | Accounting is wrong: an unresolved outcome released its reservation, allowance was restored without authoritative reconciliation, a verified outcome is not reconciled, a later receipt describes another attempt (another proposal, grant, target, attempt id or submission instant: the same instant written in another way is the same attempt), or a later version goes back from a verified outcome (`ACC005`: after `completed_verified` or `not_executed_verified` a version may repeat that outcome and may not say any other; the ledger replay keeps the verified outcome); a version that repeats a verified outcome changes or leaves out an effect that a verified version recorded (`ACC006`: action, target, quantity, unit, time or accounting record; an effect is fixed by the first verified version that states it, whichever version that is; quantities exactly, times as instants, free text not read; other effects may be added); two receipts claim one execution attempt id (`ACC007`: they are one attempt, counted once). |
| `DISC001`–`DISC005` | A derived output discloses detail the reader may not see: a protected term (`DISC001`, a backstop scan); an entry about an unreadable source although its permission decision withholds its existence or there is none (`DISC002`); an entry that is not exactly the generic disclosure its decision configures, in its wording or in any sibling field, or that calls an input unreadable although the decision lets the reader read it (`DISC003`); a decision that does not bind to the requesting principal, tenant or purpose of the context (`DISC004`); a named record that belongs to another tenant or purpose (`DISC005`). A retrieval unit that says it was read (completed, failed and so on) and cites a decision of the registry is held to it as well: a decision that withholds existence is `DISC002`, one that does not bind is `DISC004`, and one that does not let the reader read is `DISC003` (the generic entry, with the status `not_permitted`, is the only unit that may stand for what the reader may not read). |
| `ROLE001`–`ROLE008` | The roles are not kept apart, or cannot be checked: an exact approval from someone who is not an approver, or from the requestor of the packet; a packet reviewed by someone who is not a Decision Owner, or a review that the registry's review log does not record for that actor, packet and version at that instant (`ROLE003`; times are compared as instants and not as written); an approval with no earlier review of its packet by a Decision Owner; a registry that names no roles although the folder holds approvals, reviewed packets, grants or receipts; a receipt made by someone other than the grantee of the grant it cites (`ROLE006`); a grantee or executor that is not a registered executor (`ROLE007`); the assistant workload as a grantee or an executor (`ROLE008`). |
| `RESP001`–`RESP017` | A stored response breaks a structural constraint: an unknown statement kind, a statement with no text, a label that is not text, an uncited or mis-cited statement, a figure (with its sign) or a currency (any ISO 4217 code, or a currency sign) the packet lacks, an unlabeled inference, a dropped conflict, gap, recommendation or obligation, supported claims that are cited but not stated, an action worded as done, a status that is not the one the packet's state requires (a response cannot define its own lifecycle), a missing packet (or one that is not named as a decision packet, `C04`), a conflict or gap closed in words, a missingness label not said (unless the statement is exactly the permitted wording), dropped uncertainty, added certainty, a changed status word, a statement that names a record it does not rest on (in its text or its label; a record is read whole, so `GR-552` is not `GR-5521`; a proposal rests on the action of the proposal it names), a missing or unknown status, a withdrawal reason that is not the packet's own (it must be exactly the packet's reason, with at most the introduction "This response was withdrawn:", and may not reverse or invent a supersession), a statement in a withdrawn response that reads as current advice or takes the withdrawal back, a response that is not an object, or a statement about an input the reader may not read that is not exactly the permitted wording (or whose label or citation says more than where the gap is, or mentions one the reader may not know exists). |
| `RESP101`, `RESP102` | A response that says a renderer wrote it differs from the renderer's output (`RESP101`), and the difference adds or removes a negation, changes a status word or a figure, or opens or closes a conflict (`RESP102`). |
| `GW001`, `GW002` | A stored gateway evaluation no longer gives its recorded decision, or cannot be evaluated (for example when two receipts record attempts of the same proposal under the same grant at the same moment, so that a replay cannot tell which of them is its own attempt). |
| `CASE001`–`CASE003` | An evaluation case produces other codes than it declares, repeats an id, or has a mutation that cannot be applied. |
| `HYG101`–`HYG108`, `HYG201`–`HYG207` | The [hygiene](#check_hygienepy) rules; see `check_hygiene.py --rules`. |
| `STR001`–`STR004` | The [structure](#check_structurepy) rules: one H1, no skipped heading level, no generic link text, no empty table header. |

The twenty-one reason codes of the commit check itself (for example `GRANT_REVOKED`, `EVIDENCE_NOT_YET_ADMITTED`, `CUMULATIVE_LIMIT`) are explained in [example 08](../examples/08-blocked-action/README.md#the-commit-time-reason-codes) and exercised by the stored evaluations in examples [07](../examples/07-authority-and-delegation/README.md), [08](../examples/08-blocked-action/README.md), [09](../examples/09-unknown-outcome/README.md), [10](../examples/10-degraded-modes/README.md) and [12](../examples/12-controlled-change/README.md).

## Tests

```bash
python -m unittest discover -s tests
```

The tests in [`tests/`](../tests) check the checks: the validation states, the semantic checks and every code family, the stored evaluations, the reference commit check, the response validations and the counts the documents state. They use only the standard library.

[Examples](../examples/README.md) · [Contributing](../CONTRIBUTING.md)
