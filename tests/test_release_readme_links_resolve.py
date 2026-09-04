"""Every `docs/...` path the README points at must ship in the release.

The README told readers to see `docs/duplicate-purchase-guards.md` for the
Barrel of Babies reasoning, but `scripts/build_release.py` did not package that
file. An extracted release therefore carried a README linking to a document
that was not in the bundle -- the same broken-link defect recorded on #55/#57,
arriving by a different route: there the doc was deleted, here it was never
added to FILES.

Naming one file would only fix today's instance, so this derives the list from
the README itself. Any future `docs/...` reference is covered automatically.
"""

import ast
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
BUILD_RELEASE = ROOT / "scripts" / "build_release.py"

# `docs/foo.md` in backticks, or a markdown link to the same.
PATTERNS = (
    re.compile(r"`(docs/[A-Za-z0-9._\-/]+\.md)`"),
    re.compile(r"\]\((docs/[A-Za-z0-9._\-/]+\.md)\)"),
)


def referenced_docs():
    text = README.read_text(encoding="utf-8")
    found = set()
    for pattern in PATTERNS:
        found.update(pattern.findall(text))
    return sorted(found)


def packaged_files():
    """The real `FILES` collection, parsed from the module's AST.

    An earlier version searched the whole source for a quoted pathname, which
    review correctly called out: a path left behind in a comment or diagnostic
    satisfies that search even after the entry is gone from `FILES`. Confirmed
    by experiment -- replacing the entry with a comment quoting the same path
    made the old assertion pass while the file was genuinely unpackaged.

    `utf-8-sig` because this file carries a BOM, which `ast.parse` rejects.
    """
    tree = ast.parse(BUILD_RELEASE.read_text(encoding="utf-8-sig"))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        if not any(
            isinstance(t, ast.Name) and t.id == "FILES" for t in node.targets
        ):
            continue
        if not isinstance(node.value, (ast.List, ast.Tuple, ast.Set)):
            continue
        return {
            e.value
            for e in node.value.elts
            if isinstance(e, ast.Constant) and isinstance(e.value, str)
        }
    raise AssertionError("no FILES list literal found in scripts/build_release.py")


class ReleaseReadmeLinksTests(unittest.TestCase):
    def test_readme_references_some_docs(self):
        """Guard the guard: if the extraction silently matched nothing, the
        packaging assertion below would pass vacuously."""
        self.assertTrue(
            referenced_docs(),
            "no docs/ references found in README; the link check is inert",
        )

    def test_every_referenced_doc_exists_in_the_repo(self):
        for rel in referenced_docs():
            with self.subTest(doc=rel):
                self.assertTrue(
                    (ROOT / rel).exists(),
                    f"README references {rel}, which does not exist",
                )

    def test_every_referenced_doc_is_packaged_in_the_release(self):
        release = packaged_files()
        self.assertTrue(release, "FILES parsed as empty; the check would be inert")
        for rel in referenced_docs():
            with self.subTest(doc=rel):
                self.assertIn(
                    rel,
                    release,
                    f"README references {rel} but scripts/build_release.py "
                    "does not package it, so the shipped README links to a "
                    "file the bundle does not contain",
                )


if __name__ == "__main__":
    unittest.main()
