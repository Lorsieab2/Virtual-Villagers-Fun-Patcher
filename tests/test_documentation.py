from __future__ import annotations

from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vv_fun_patcher import load_fun_patches  # noqa: E402


class DocumentationTests(unittest.TestCase):
    def test_readme_cli_list_mentions_every_available_fun_patch_id(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        missing = [patch.id for patch in load_fun_patches() if patch.id not in readme]
        self.assertEqual(missing, [])

    def test_how_to_use_mentions_every_available_feature_name(self) -> None:
        guide = (ROOT / "How to Use.txt").read_text(encoding="utf-8")
        missing = [patch.name for patch in load_fun_patches() if patch.name not in guide]
        self.assertEqual(missing, [])


if __name__ == "__main__":
    unittest.main()
