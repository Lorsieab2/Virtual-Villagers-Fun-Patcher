"""The release zip ships every src module the patcher imports.

scripts/build_release.py packages an explicit file list. The first v1.35.59
build left out src/patcher_files.py, which vv_fun_patcher imports at the top:
the patcher in the zip stopped at once with ModuleNotFoundError, although every
test run from the repository passed. This guard follows the imports of the
patcher and its window (including imports inside functions) through src/ and
fails if any module they reach is not packaged.
"""

from __future__ import annotations

import ast
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
ENTRY_POINTS = ("vv_fun_patcher", "vv_fun_patcher_gui")


def packaged() -> set[str]:
    """The entries of the real FILES list, parsed from the AST.

    A whole-file search would also accept a path left in a comment (such as a
    commented-out entry), so only active list elements count. `utf-8-sig`
    because build_release.py carries a BOM, which ast.parse rejects.
    """
    tree = ast.parse((ROOT / "scripts" / "build_release.py").read_text(encoding="utf-8-sig"))
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id == "FILES" for t in node.targets)
            and isinstance(node.value, (ast.List, ast.Tuple, ast.Set))
        ):
            return {
                e.value
                for e in node.value.elts
                if isinstance(e, ast.Constant) and isinstance(e.value, str)
            }
    raise AssertionError("no FILES list literal found in scripts/build_release.py")


def local_imports(module: str) -> set[str]:
    tree = ast.parse((SRC / f"{module}.py").read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            names.add(node.module.split(".")[0])
    return {name for name in names if (SRC / f"{name}.py").exists()}


def reachable() -> set[str]:
    seen: set[str] = set()
    todo = list(ENTRY_POINTS)
    while todo:
        module = todo.pop()
        if module in seen:
            continue
        seen.add(module)
        todo.extend(local_imports(module) - seen)
    return seen


class ReleaseShipsEveryImportedModule(unittest.TestCase):
    def test_every_imported_src_module_is_packaged(self) -> None:
        modules = {f"src/{name}.py" for name in reachable()}
        self.assertIn("src/patcher_files.py", modules)
        missing = sorted(modules - packaged())
        self.assertEqual(missing, [], "src modules the patcher imports but the release leaves out")


if __name__ == "__main__":
    unittest.main()
