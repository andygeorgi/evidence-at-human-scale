"""The URL checker: extraction and cleaning work offline, and classification is tested against a local server."""
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import support  # noqa: F401  (puts scripts/ on the path)

import check_urls as urls


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def respond(self, code, headers=()):
        self.send_response(code)
        for name, value in headers:
            self.send_header(name, value)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def route(self, head):
        path = self.path
        if path == "/ok":
            self.respond(200)
        elif path == "/moved":
            self.respond(301, [("Location", "/ok")])
        elif path == "/missing":
            self.respond(404)
        elif path == "/gone":
            self.respond(410)
        elif path == "/forbidden":
            self.respond(403)
        elif path == "/rate":
            self.respond(429)
        elif path == "/error":
            self.respond(500)
        elif path == "/no-head":
            self.respond(405 if head else 200)
        else:
            self.respond(404)

    def do_HEAD(self):
        self.route(True)

    def do_GET(self):
        self.route(False)


class Extraction(unittest.TestCase):
    def test_trailing_punctuation_and_brackets_are_not_part_of_the_url(self):
        text = "See https://a.example.test/x. Also (https://b.example.test/y), and <https://c.example.test/z>; or [t](https://d.example.test/w)."
        self.assertEqual(urls.extract(text), ["https://a.example.test/x", "https://b.example.test/y", "https://c.example.test/z", "https://d.example.test/w"])

    def test_balanced_parentheses_inside_a_url_are_kept(self):
        self.assertEqual(urls.extract("https://en.wikipedia.test/wiki/Evidence_(law)."), ["https://en.wikipedia.test/wiki/Evidence_(law)"])

    def test_placeholders_are_skipped(self):
        text = "https://example.com/a http://localhost:8000/x https://github.com/<owner>/repo https://host.test/{id}"
        self.assertEqual(urls.extract(text), [])

    def test_inventory_reads_markdown_but_not_svg_namespaces_or_json_identifiers(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "a.md").write_text("Read https://docs.example.test/page.\n", encoding="utf-8")
            (root / "b.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg"></svg>', encoding="utf-8")
            (root / "c.json").write_text('{"$id": "https://ids.example.test/schema"}', encoding="utf-8")
            self.assertEqual(urls.inventory(root), {"https://docs.example.test/page": ["a.md"]})

    def test_the_repository_cites_its_public_sources(self):
        found = urls.inventory(support.REPO)
        self.assertGreaterEqual(len(found), 20)
        self.assertTrue(all(u.startswith(("http://", "https://")) for u in found))


class Classification(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.base = "http://127.0.0.1:%d" % cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def kind(self, path):
        return urls.check_url(self.base + path, timeout=5).kind

    def test_reachable(self):
        self.assertEqual(self.kind("/ok"), "ok")
        self.assertEqual(self.kind("/moved"), "redirected")

    def test_head_refused_but_get_allowed_is_reachable(self):
        self.assertEqual(self.kind("/no-head"), "ok")

    def test_broken(self):
        self.assertEqual(self.kind("/missing"), "broken")
        self.assertEqual(self.kind("/gone"), "broken")

    def test_refused_and_unreachable_are_not_broken(self):
        self.assertEqual(self.kind("/forbidden"), "refused")
        self.assertEqual(self.kind("/rate"), "refused")
        self.assertEqual(self.kind("/error"), "unreachable")

    def test_a_name_that_does_not_resolve_is_broken(self):
        self.assertEqual(urls.check_url("http://no-such-host.invalid/", timeout=5).kind, "broken")

    def test_list_mode_makes_no_request_and_skips_placeholder_hosts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            script = str(support.SCRIPTS / "check_urls.py")
            (root / "a.md").write_text("Cited: %s/ok\n" % self.base.replace("127.0.0.1", "127.0.0.2"), encoding="utf-8")
            (root / "b.md").write_text("Local only: %s/missing\n" % self.base, encoding="utf-8")
            done = subprocess.run([sys.executable, script, "--root", str(root), "--list"], capture_output=True, text=True)
            self.assertEqual(done.returncode, 0)
            self.assertIn("a.md", done.stdout)
            self.assertNotIn("b.md", done.stdout)


if __name__ == "__main__":
    unittest.main()
