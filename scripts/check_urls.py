#!/usr/bin/env python3
"""Check that the external URLs the repository cites still resolve. Needs network access; no other check depends on it.

    python scripts/check_urls.py --list           # print each URL and the files that cite it; no network
    python scripts/check_urls.py                  # request each URL once; exit 1 if any is broken
    python scripts/check_urls.py --strict         # also exit 1 when a server refuses an automated request or cannot be reached
    python scripts/check_urls.py --timeout 20 --workers 6

A URL is *broken* if the server answers 404 or 410, or the name does not resolve, or the connection is refused, or the
certificate is invalid. It is *refused* if the server answers 401, 403, 429 or 999 (many publishers block scripts; open it
in a browser), and *unreachable* on a timeout or a server error (try again later). Links are read from Markdown, YAML and
text files, so XML namespaces in SVG files and identifiers in JSON are not requested.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import socket
import ssl
import sys
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence
from urllib.parse import urlsplit

REPO = Path(__file__).resolve().parents[1]
SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__", ".pytest_cache"}
SCANNED_SUFFIXES = {".md", ".cff", ".yml", ".yaml", ".txt"}
PLACEHOLDER_HOSTS = {"example.com", "example.org", "example.net", "localhost", "127.0.0.1", "0.0.0.0"}
USER_AGENT = "evidence-at-human-scale-url-check/1.0 (link checker; run by a person or a scheduled workflow)"
URL = re.compile(r"https?://[^\s<>\"'`\[\]{}|\\^]+")
REFUSED = {401, 403, 429, 999}
BROKEN = {404, 410}


def clean(url: str) -> str:
    """Trim punctuation that belongs to the sentence, and a closing bracket that has no opening one."""
    while url:
        if url[-1] in ".,;:!?*_'\"":
            url = url[:-1]
        elif url[-1] == ")" and url.count(")") > url.count("("):
            url = url[:-1]
        else:
            break
    return url


def extract(text: str) -> List[str]:
    """Every external URL in a text, cleaned, skipping placeholders (hosts like example.com, or a URL cut off by <...>)."""
    found = []
    for match in URL.finditer(text):
        if text[match.end():match.end() + 1] in ("<", "{"):
            continue
        url = clean(match.group(0))
        parts = urlsplit(url)
        if not parts.hostname or parts.hostname.lower() in PLACEHOLDER_HOSTS:
            continue
        found.append(url)
    return found


def inventory(root: Path = REPO) -> Dict[str, List[str]]:
    """URL -> repository-relative paths that cite it."""
    cited: Dict[str, set] = {}
    for base, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for name in files:
            path = Path(base, name)
            if path.suffix.lower() not in SCANNED_SUFFIXES:
                continue
            rel = path.relative_to(root).as_posix()
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            for url in extract(text):
                cited.setdefault(url, set()).add(rel)
    return {url: sorted(paths) for url, paths in sorted(cited.items())}


@dataclass
class Result:
    url: str
    kind: str  # ok | redirected | refused | broken | unreachable
    status: int = 0
    final_url: str = ""
    detail: str = ""
    files: List[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {"url": self.url, "kind": self.kind, "status": self.status, "final_url": self.final_url, "detail": self.detail, "cited_in": self.files}


def _request(url: str, method: str, timeout: float):
    request = urllib.request.Request(url, method=method, headers={"User-Agent": USER_AGENT, "Accept": "*/*"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.geturl(), ""
    except urllib.error.HTTPError as exc:
        exc.close()
        return exc.code, url, ""
    except urllib.error.URLError as exc:
        return 0, url, str(exc.reason)
    except (socket.timeout, TimeoutError):
        return 0, url, "timed out"
    except (ssl.SSLError, ConnectionError, OSError) as exc:
        return 0, url, str(exc)


def check_url(url: str, timeout: float = 15.0) -> Result:
    """One URL: try HEAD, then GET when HEAD is refused or unsupported."""
    status, final, detail = _request(url, "HEAD", timeout)
    if status == 0 and not detail.startswith("timed out"):
        status, final, detail = _request(url, "GET", timeout)
    elif status >= 400 or status == 0:
        retry = _request(url, "GET", timeout)
        if retry[0] and (retry[0] < 400 or status == 0 or retry[0] != status):
            status, final, detail = retry
    if status == 0:
        lowered = detail.lower()
        gone = any(word in lowered for word in ("name or service not known", "getaddrinfo", "nodename nor servname", "no address associated", "certificate", "refused", "name resolution"))
        return Result(url, "broken" if gone else "unreachable", 0, "", detail or "no response")
    if status in BROKEN:
        return Result(url, "broken", status, final, "not found" if status == 404 else "gone")
    if status in REFUSED:
        return Result(url, "refused", status, final, "the server refuses automated requests, or needs a login")
    if status >= 400:
        return Result(url, "unreachable", status, final, "server error or unexpected status")
    redirected = urlsplit(final).netloc.lower() != urlsplit(url).netloc.lower() or urlsplit(final).path.rstrip("/") != urlsplit(url).path.rstrip("/")
    if urlsplit(url).netloc.lower() in ("doi.org", "dx.doi.org"):
        redirected = False  # a DOI is meant to redirect
    return Result(url, "redirected" if redirected else "ok", status, final, "now at " + final if redirected else "")


def check_all(urls: Dict[str, List[str]], timeout: float, workers: int) -> List[Result]:
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        results = list(pool.map(lambda u: check_url(u, timeout), urls))
    for result in results:
        result.files = urls[result.url]
    return results


def summarize(results: Sequence[Result]) -> str:
    counts = {kind: sum(1 for r in results if r.kind == kind) for kind in ("ok", "redirected", "refused", "broken", "unreachable")}
    return "%d URLs: %d ok, %d redirected, %d refused automated requests, %d broken, %d unreachable" % (
        len(results), counts["ok"], counts["redirected"], counts["refused"], counts["broken"], counts["unreachable"])


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--root", default=str(REPO), help="folder to read (default: this repository)")
    parser.add_argument("--list", action="store_true", help="print the URLs and where they are cited; make no request")
    parser.add_argument("--strict", action="store_true", help="also fail on refused and unreachable URLs")
    parser.add_argument("--json", action="store_true", help="print a machine-readable result")
    parser.add_argument("--timeout", type=float, default=15.0, help="seconds to wait for each request (default 15)")
    parser.add_argument("--workers", type=int, default=6, help="requests in parallel (default 6)")
    args = parser.parse_args(argv)
    urls = inventory(Path(args.root).resolve())
    if args.list:
        for url, files in urls.items():
            print("%s\n    cited in: %s" % (url, ", ".join(files)))
        print("\n%d distinct external URLs." % len(urls))
        return 0
    results = check_all(urls, args.timeout, args.workers)
    failing = {"broken"} | ({"refused", "unreachable"} if args.strict else set())
    if args.json:
        print(json.dumps([r.as_dict() for r in results], indent=2, ensure_ascii=False))
    else:
        for r in results:
            if r.kind == "ok":
                continue
            print("%-11s %s  %s\n    %s\n    cited in: %s" % (r.kind.upper(), r.status or "---", r.url, r.detail, ", ".join(r.files)))
        print(summarize(results))
    return 1 if any(r.kind in failing for r in results) else 0


if __name__ == "__main__":
    for _stream in (sys.stdout, sys.stderr):  # a legacy console code page must not break the output
        getattr(_stream, "reconfigure", lambda **_: None)(encoding="utf-8", errors="replace")
    sys.exit(main())
