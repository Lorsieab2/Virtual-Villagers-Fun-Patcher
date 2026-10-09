"""Every release-only test (tests/conftest.py RELEASE_ONLY; the owner, 2026-10-08: "make the
potentially slow full suite tests for release-only") names a test that exists, so a rename never
quietly drops one from the release run or leaves a dead entry."""
from __future__ import annotations

import ast
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

import conftest  # noqa: E402  (tests/ is on the path under pytest)


class ReleaseOnlyListTests(unittest.TestCase):
    def test_every_entry_is_a_test_that_exists(self) -> None:
        self.assertEqual(len(conftest.RELEASE_ONLY), len(set(conftest.RELEASE_ONLY)))
        for node in conftest.RELEASE_ONLY:
            with self.subTest(node=node):
                path, cls, method = node.split("::")
                tree = ast.parse((ROOT / path).read_text(encoding="utf-8"))
                classes = {c.name: c for c in tree.body if isinstance(c, ast.ClassDef)}
                self.assertIn(cls, classes)
                self.assertIn(method, {f.name for f in classes[cls].body if isinstance(f, ast.FunctionDef)})


if __name__ == "__main__":
    unittest.main()
