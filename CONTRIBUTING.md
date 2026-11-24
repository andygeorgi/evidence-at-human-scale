# Contributing

Thank you for reading this closely. This repository is a reference architecture, and careful criticism is the most useful contribution. Be courteous: argue with the text, not the person.

## License

This repository is licensed under the [MIT License](LICENSE). Under GitHub's Terms of Service, a contribution to a repository that carries a license is made under that license. For anything beyond a small fix, please **open an issue** first, so that the change can be agreed before you write it. A fix to a typo, a broken link or a wrong count is fine as a pull request.

## What is welcome

- **Corrections.** A factual error, a broken link, a wrong count, an unclear sentence, a term used two ways.
- **Challenges to the architecture.** A case it does not handle, a contract field that cannot be implemented, a failure mode it misses. Open an issue with the smallest example that shows it.
- **Better examples and checks.** A synthetic case that breaks a check, or that a check should catch and does not.
- **Tooling fixes.** Something that fails on your platform.

## What needs discussion first

- A new contract, or a change to what a contract, a check code or the schema means. These change what the paper claims.
- Any result, benchmark or measurement. No evaluation test has been run: EV01–EV12 are NOT ASSESSED. A contribution that reports a result has to say who ran what, on which data and against which denominators, and it records the command, the input and the output, as the [evaluation guide](evaluation/README.md) describes. It is reviewed as evidence, not as documentation.
- Real data of any kind. Never. Every name, amount and identifier here is invented; yours must be too.

## Ground rules

1. **Do not turn NOT ASSESSED into a result.** A status changes only when the test was run and the command, input and output are recorded in the row.
2. **Keep the evidence classes apart.** Real public records, the author's engagement records, synthetic illustration and "not available" are different things ([claims and limits](docs/claims-and-limits.md)).
3. **Edit the source, not the output.** The example JSON is written by [`scripts/build_example_data.py`](scripts/build_example_data.py); the catalogue's CSV files and the test sections of the oracles page by [`scripts/build_catalogue.py`](scripts/build_catalogue.py) from the catalogue's JSON; the figure blocks in the Markdown, the README banner and the gallery by [`scripts/sync_figures.py`](scripts/sync_figures.py) from [`figures/figures.json`](figures/figures.json); the figure SVGs by [`figures/src/svg_figures.py`](figures/src/svg_figures.py). A check fails if a generated file is edited by hand.
4. **Write plainly, in American spelling.** Names that already exist, such as "catalogue" and "programme", stay as they are.
5. **Say what a figure or an example does not show.** Each example page ends with that.

## Run the checks

```bash
python -m pip install -r requirements.txt
python scripts/check_all.py
```

It needs Python 3.9 or later. Continuous integration runs it on Ubuntu and Windows, with Python 3.9 and 3.14 on each (Python 3.9 on Ubuntu 24.04, the newest Ubuntu image that still has a build of it); nothing in it is platform-specific, so macOS should work too. Each check can also run alone; [`scripts/README.md`](scripts/README.md) lists them. If you change a count, a code or a status, a check tells you which sentence in the documents to update.

## Pull requests

- Keep each one small and focused, and say which checks you ran.
- Use the prefixes the history uses: `docs:`, `feat:`, `fix:`, `test:`, `chore:`.
- Do not add Office files, PDFs, archives, images of text or other binaries; the hygiene check rejects them.
- If you used an AI assistant, say so in the pull request, as this repository does in its [README](README.md#ai-assistance).

[Security policy](SECURITY.md) · [Changelog](CHANGELOG.md)
