"""No class in the patcher's windows defines a method twice.

A second `def _under` in the Family Tree Maker (2026-10-08, the glow colour fix) silently replaced
the first, and every right-click menu on the tree failed: Python keeps the later definition and
says nothing.  This catches any such pair in every source file."""
from __future__ import annotations

import ast
import collections
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class NoDuplicateMethodsTests(unittest.TestCase):
    def test_no_class_defines_a_method_twice(self) -> None:
        found = []
        for path in sorted((ROOT / "src").glob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    names = collections.Counter(
                        f.name for f in node.body if isinstance(f, (ast.FunctionDef, ast.AsyncFunctionDef))
                        and not any(isinstance(d, ast.Attribute) and d.attr in ("setter", "deleter")
                                    for d in f.decorator_list))
                    found += [f"{path.name}: {node.name}.{name}" for name, n in names.items() if n > 1]
        self.assertEqual(found, [])


if __name__ == "__main__":
    unittest.main()
