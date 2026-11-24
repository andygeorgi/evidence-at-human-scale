#!/usr/bin/env python3
"""Run every repository check, in one command, the way continuous integration does.

    python scripts/check_all.py               # run everything, show only what fails
    python scripts/check_all.py --verbose     # show each check's own output
    python scripts/check_all.py --history     # also scan the whole Git history for hygiene (needs the whole history)
    python scripts/check_all.py --list        # name the checks
    python scripts/check_all.py --only links,hygiene
    python scripts/check_all.py --skip tests

Each check is also a script you can run alone. The external URL check is not included: it needs the network and a
publisher can fail it for reasons that say nothing about this repository (run ``python scripts/check_urls.py``).
Continuous integration runs ``--history`` on a full checkout. A download without ``.git`` or a shallow clone has no whole
history, so ``--history`` fails there instead of passing on commits it never read.
Exit code 0 means every check that ran passed, 1 that a check failed, and 3 that nothing ran. A run that leaves checks
out says how many and that its result says nothing about them.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from eahs import __version__  # noqa: E402

# (name, what it shows, command after the interpreter)
CHECKS: Tuple[Tuple[str, str, Tuple[str, ...]], ...] = (
    ("examples", "the synthetic examples validate: schema, instances, semantics, gateway, responses and cases", ("scripts/validate_examples.py",)),
    ("tests", "the unit tests pass", ("-m", "unittest", "discover", "-s", "tests")),
    ("example-data", "the committed example JSON is exactly what its builder writes", ("scripts/build_example_data.py", "--check")),
    ("catalogue", "the evaluation catalogue's copies are what its JSON writes, and its tables agree", ("scripts/build_catalogue.py", "--check")),
    ("schema-hash", "the schema's validation surface is unchanged since it was recorded", ("scripts/schema_surface_hash.py", "--check")),
    ("links", "relative links, anchors, images and alt text resolve, and every page is linked from another", ("scripts/check_links.py", "--orphans")),
    ("structure", "every page has one H1, no skipped heading levels, no empty table headers and no generic link text", ("scripts/check_structure.py",)),
    ("figures", "every figure has its metadata, alt text and description, each drawing stays within set limits, and the documents are in sync", ("scripts/check_figures.py",)),
    ("svg", "the SVGs are what their generator draws", ("figures/src/svg_figures.py", "--check")),
    ("hygiene", "no private link, local path, credential, e-mail address, internal term or unfinished marker", ("scripts/check_hygiene.py",)),
)


def run(name: str, command: Sequence[str]) -> Tuple[bool, float, str]:
    started = time.time()
    # A pipe on Windows defaults to a legacy code page; ask the child for UTF-8 and read it as UTF-8.
    env = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
    done = subprocess.run([sys.executable] + list(command), cwd=str(REPO), capture_output=True, text=True, encoding="utf-8", errors="replace", env=env)
    return done.returncode == 0, time.time() - started, (done.stdout + done.stderr).strip()


def select(only: Optional[str], skip: Optional[str]) -> List[Tuple[str, str, Tuple[str, ...]]]:
    names = [c[0] for c in CHECKS]
    wanted = [n.strip() for n in only.split(",")] if only else names
    dropped = [n.strip() for n in skip.split(",")] if skip else []
    unknown = [n for n in wanted + dropped if n not in names]
    if unknown:
        raise SystemExit("Unknown check(s): %s. Known: %s" % (", ".join(unknown), ", ".join(names)))
    return [c for c in CHECKS if c[0] in wanted and c[0] not in dropped]


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--list", action="store_true", help="name the checks and exit")
    parser.add_argument("--only", help="comma-separated check names to run")
    parser.add_argument("--skip", help="comma-separated check names to leave out")
    parser.add_argument("--verbose", "-v", action="store_true", help="print each check's own output, not only the output of failures")
    parser.add_argument("--history", action="store_true", help="also scan the whole Git history in the hygiene check (fails on a shallow clone or a download without .git)")
    args = parser.parse_args(argv)
    if args.list:
        for name, what, command in CHECKS:
            print("%-13s %s\n%-13s python %s" % (name, what, "", " ".join(command)))
        return 0
    chosen = select(args.only, args.skip)
    if args.history:
        if "hygiene" not in [name for name, _, _ in chosen]:
            raise SystemExit("--history belongs to the hygiene check, which was not selected, so no history would be scanned.")
        chosen = [(name, what, command + ("--history",) if name == "hygiene" else command) for name, what, command in chosen]
    print("Evidence at Human Scale %s: repository checks\n" % __version__)
    if not chosen:
        print("Result: NOT ASSESSED. Every check was skipped, so nothing was checked.")
        return 3
    failures = []
    for index, (name, what, command) in enumerate(chosen, 1):
        ok, seconds, output = run(name, command)
        print("[%d/%d] %-13s %s  (%.1f s)" % (index, len(chosen), name, "PASS" if ok else "FAIL", seconds))
        if args.verbose or not ok:
            print("\n".join("        " + line for line in output.splitlines()) + "\n")
        if not ok:
            failures.append(name)
    left_out = len(CHECKS) - len(chosen)
    if failures:
        print("\n%d of %d checks failed: %s" % (len(failures), len(chosen), ", ".join(failures)))
        return 1
    if left_out:
        print("\nPASS for the checks that ran: %d of %d passed. %d check(s) were skipped and not run, so this result says nothing about them." % (len(chosen), len(CHECKS), left_out))
        return 0
    print("\nAll %d checks passed. A pass says the repository is consistent; it says nothing about any real system." % len(chosen))
    return 0


if __name__ == "__main__":
    for _stream in (sys.stdout, sys.stderr):  # a legacy console code page must not break the output
        getattr(_stream, "reconfigure", lambda **_: None)(encoding="utf-8", errors="replace")
    sys.exit(main())
