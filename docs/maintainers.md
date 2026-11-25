# Maintaining this repository

Notes for the maintainer. They are not part of the reading path; the [contributing guide](../CONTRIBUTING.md) is the way in for everyone else.

## Generated files

The rebuild commands are in the [contributing guide](../CONTRIBUTING.md#change-examples-the-catalogue-and-figures). `sync_figures.py` writes each figure into the pages that show it, between `<!-- figure:Fxx:start -->` and `<!-- figure:Fxx:end -->`, the README banner between `<!-- banner:start -->` and `<!-- banner:end -->`, and the gallery of the [figures page](../figures/README.md) between `<!-- gallery:start -->` and `<!-- gallery:end -->`. Never edit what lies between markers. The limits a drawing has to keep, and the reasons for them, are in the comments of [`scripts/check_figures.py`](../scripts/check_figures.py) and [`scripts/sync_figures.py`](../scripts/sync_figures.py).

## Checks

```bash
python scripts/check_all.py            # every check, as continuous integration runs them
python scripts/check_all.py --history  # also scan the whole Git history (needs a full clone)
```

[`validate.yml`](../.github/workflows/validate.yml) runs the checks, history scan included, on Ubuntu and Windows with Python 3.9 and 3.14 on each, and the optional URL check once a week. The [scripts guide](../scripts/README.md) describes each check.

## The hygiene scan

`scripts/check_hygiene.py` looks for what must not reach a public repository: private links, local paths, credentials, private vocabulary, confidentiality labels, the name of the authority outside the public records that quote it, hidden characters, draft markers and files that do not belong. `python scripts/check_hygiene.py --rules` lists every rule, and the script's own documentation explains its pins and exceptions.

The list of private terms is not kept in the repository. The scan reads it from a Git-ignored file named `.hygiene-private-terms` in the repository folder, or from the environment variable `EAHS_PRIVATE_TERMS`, which holds a path to such a file. Continuous integration has no list, so a maintainer who has one runs `python scripts/check_hygiene.py --history` with it before every release. History is not rewritten for a residue that is known and not sensitive: the answer is a narrow exception for that path and that line, in a reviewed commit.

## Releasing a version

1. Set the version and the date in `scripts/eahs/__init__.py`, `CITATION.cff`, the README (the citation line and the expected output), the examples guide (the expected output), the title page of the [paper](paper/README.md) and `schemas/README.md`, and add an entry to `CHANGELOG.md` and one to `contracts/CHANGES.md`. `tests/test_release_metadata.py` fails if one of them disagrees. A change to what the schema accepts also needs its new surface hash in `contracts/CHANGES.md`; `python scripts/schema_surface_hash.py --check` confirms it.
2. Run `python scripts/check_all.py --history` with the private term list.
3. Merge into `main` with a merge commit, tag that commit `vMAJOR.MINOR.PATCH` with an annotated tag, and publish a release from the changelog entry. A published tag, release or commit is never moved or rewritten.
