# Security policy

This repository holds documentation, a JSON Schema bundle, an invented example set and a few Python scripts that check them. It runs no service, holds no real data and starts no model. Its checks make no network request, except the optional [URL check](scripts/README.md#check_urlspy), which only requests addresses written in the repository's own text.

## What to report privately

- A way to make a script run code, read or write outside the repository, or hang, by means of a crafted example, schema or case file.
- A vulnerable dependency. The only one is `jsonschema` (see [`requirements.txt`](requirements.txt)).
- A credential, personal data or private information that was committed by mistake.
- A continuous-integration workflow with more permission than it needs.

## What to report in an ordinary issue

An error in the architecture, a contract, an example or a figure, a broken link, or an unclear statement. Those are content problems, not vulnerabilities, even when they concern security: this is a reference architecture whose real-world effectiveness has not been evaluated, and its weaknesses are welcome in the open. See [claims and limits](docs/claims-and-limits.md).

## How to report

Use GitHub's private vulnerability reporting: open the repository's **Security** tab and choose **Report a vulnerability**. If that option is not available, open an issue that says you have a security concern, without any detail, and ask for a private channel.

Please send a synthetic reproducer and the smallest amount of information that lets the problem be reproduced. Do not post real records, credentials or personal data in an issue, a pull request or a report: every name, amount and identifier in this repository is invented, and your example should be too.

## What to expect

This is a single-author repository. Reports are read and answered as soon as possible, but no response time is promised, no bounty is offered and no security audit of the architecture or the scripts has taken place. Fixes go into the latest release; older ones are not patched.

## What the scripts do

- Every example, schema and case file is treated as data. The scripts parse JSON with the Python standard library and `jsonschema`, and never evaluate, import or execute file content.
- [`validate_examples.py`](scripts/validate_examples.py) and the other checks read files and write nothing. Cases that alter an example do so in memory.
- The generators write only where they say: [`build_example_data.py`](scripts/build_example_data.py) under `examples/`, [`build_catalogue.py`](scripts/build_catalogue.py) in `evaluation/catalogue/` and between markers in `evaluation/oracles.md`, [`sync_figures.py`](scripts/sync_figures.py) between figure markers in Markdown, and the figure scripts under `figures/`.
- The checks run in CI with read-only repository permission ([`validate.yml`](.github/workflows/validate.yml)).

A passing check is not a security assessment. It says nothing about whether the architecture is secure when implemented.

[Contributing](CONTRIBUTING.md) · [Claims and limits](docs/claims-and-limits.md)
