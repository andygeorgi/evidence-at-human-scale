"""The link checker must find what it claims to find, and leave alone what GitHub resolves."""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import support  # noqa: F401  (puts scripts/ on the path)

import check_links as links


def problems_for(files, orphans=False):
    """Check a throwaway folder holding {relative path: text}; return (problems, orphans)."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp).resolve()
        for name, content in files.items():
            target = root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8") if isinstance(content, str) else target.write_bytes(content)
        links._ANCHORS.clear()
        found, _external, orphan_list, _count = links.check(root)
        return found, [o.relative_to(root).as_posix() for o in orphan_list]


class Slugs(unittest.TestCase):
    def test_github_rules(self):
        self.assertEqual(links.slug("Approval is not commit"), "approval-is-not-commit")
        self.assertEqual(links.slug("`check_urls.py`"), "check_urlspy")
        self.assertEqual(links.slug("1. What it is, and isn't"), "1-what-it-is-and-isnt")
        self.assertEqual(links.slug("Known limitations of this release candidate"), "known-limitations-of-this-release-candidate")
        self.assertEqual(links.slug("[Linked](x.md) *heading*"), "linked-heading")

    def test_repeated_headings_get_numeric_suffixes(self):
        with tempfile.TemporaryDirectory() as tmp:
            page = Path(tmp) / "a.md"
            page.write_text("# Same\n\n## Same\n\n## Same\n", encoding="utf-8")
            links._ANCHORS.clear()
            self.assertEqual(links.anchors_of(page), {"same", "same-1", "same-2"})


class Detection(unittest.TestCase):
    def test_a_clean_set_of_pages_has_no_problems(self):
        found, _ = problems_for({
            "README.md": "# Home\n\nSee [guide](docs/guide.md#setup) and [top](#home) and ![diagram](img/d.svg \"t\").\n",
            "docs/guide.md": "# Guide\n\n## Setup\n\nBack to [home](../README.md).\n",
            "img/d.svg": "<svg/>",
        })
        self.assertEqual(found, [])

    def test_missing_files_and_anchors(self):
        found, _ = problems_for({
            "README.md": "[gone](nope.md) [bad anchor](docs/guide.md#nowhere) [bad local](#missing)\n",
            "docs/guide.md": "# Guide\n",
        })
        text = "\n".join(found)
        self.assertIn("link does not exist (nope.md)", text)
        self.assertIn("anchor #nowhere not found in docs/guide.md", text)
        self.assertIn("anchor #missing not found in this page", text)

    def test_a_path_that_differs_only_by_case_is_a_problem(self):
        found, _ = problems_for({"README.md": "[x](Docs/Guide.md)\n", "docs/guide.md": "# Guide\n"})
        self.assertEqual(len(found), 1)

    def test_images_need_a_target_and_alt_text(self):
        found, _ = problems_for({
            "README.md": "![](a.svg) ![fine](b.svg) ![x](missing.svg)\n<img src=\"a.svg\">\n<picture><source srcset=\"gone.svg\"><img src=\"b.svg\" alt=\"ok\"></picture>\n",
            "a.svg": "<svg/>",
            "b.svg": "<svg/>",
        })
        text = "\n".join(found)
        self.assertIn("empty alt text", text)
        self.assertIn("image does not exist (missing.svg)", text)
        self.assertIn("has no alt attribute", text)
        self.assertIn("image does not exist (gone.svg)", text)

    def test_code_is_ignored(self):
        found, _ = problems_for({"README.md": "```md\n[x](nowhere.md)\n```\n\nInline `[y](nowhere.md)` too.\n"})
        self.assertEqual(found, [])

    def test_reference_style_links_and_html_anchors(self):
        found, _ = problems_for({
            "README.md": "[ref][r]\n\n[r]: missing.md\n\n<a href=\"gone.md\">x</a> <a id=\"mark\"></a> [ok](#mark)\n",
        })
        text = "\n".join(found)
        self.assertIn("link does not exist (missing.md)", text)
        self.assertIn("link does not exist (gone.md)", text)
        self.assertNotIn("#mark", text)

    def test_external_links_are_not_requested(self):
        found, _ = problems_for({"README.md": "[site](https://example.org/x) <https://example.org/y>\n"})
        self.assertEqual(found, [])

    def test_root_relative_links_resolve_from_the_repository_root(self):
        found, _ = problems_for({"docs/a.md": "[home](/README.md) [bad](/nope.md)\n", "README.md": "[a](docs/a.md)\n"})
        self.assertEqual(len(found), 1)
        self.assertIn("nope.md", found[0])


class Orphans(unittest.TestCase):
    def test_pages_nothing_links_to_are_reported_but_readmes_root_and_github_are_exempt(self):
        _, orphans = problems_for({
            "README.md": "[a](docs/a.md)\n",
            "docs/a.md": "# A\n",
            "docs/lonely.md": "# Lonely\n",
            "docs/README.md": "# Folder\n",
            "CHANGELOG.md": "# Root file\n",
            ".github/pull_request_template.md": "## Template\n",
        })
        self.assertEqual(orphans, ["docs/lonely.md"])


class TheRepository(unittest.TestCase):
    def test_has_no_broken_link_and_no_orphan(self):
        done = subprocess.run([sys.executable, str(support.SCRIPTS / "check_links.py"), "--orphans"], capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)


if __name__ == "__main__":
    unittest.main()
