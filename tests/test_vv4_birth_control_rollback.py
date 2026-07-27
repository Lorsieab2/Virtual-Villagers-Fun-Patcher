from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vv_fun_patcher import load_builds, load_fun_patches, render_patched_bytes  # noqa: E402


class VV4BirthControlRollbackTests(unittest.TestCase):
    def test_vv4_entry_is_disabled_rejected_and_has_no_executable_edits(self) -> None:
        manifest = json.loads((ROOT / "data" / "builds.json").read_text(encoding="utf-8"))
        entry = next(item for item in manifest["fun_patches"] if item["id"] == "vv4_birth_control")
        self.assertFalse(entry["enabled"])
        self.assertIn("rejected/superseded", entry["status"])
        self.assertIn("untouched vanilla breeding reference", entry["status"])
        self.assertEqual(entry["patches"], [])

    def test_vv4_birth_control_is_absent_from_catalog_and_cli_help(self) -> None:
        self.assertNotIn("vv4_birth_control", {patch.id for patch in load_fun_patches()})
        result = subprocess.run(
            [sys.executable, "src/vv_fun_patcher.py", "dry-run-all", "--help"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertNotIn("vv4_birth_control", result.stdout)

    def test_rendered_vv4_stock_bytes_do_not_apply_former_edits(self) -> None:
        build = next(item for item in load_builds() if item.id == "vv4")
        source_path = ROOT / "research" / "stock-executables" / build.input_name
        source = source_path.read_bytes()
        rendered, applied = render_patched_bytes(source_path, build, "collection_progression", [])
        former = {
            0x60E67: bytes.fromhex(
                "B8E803000039868C1B00007C0983BE901B000001742E39878C1B00007C0983BF901B000001741D"
            ),
            0x61E90: bytes.fromhex("741C6A64E83718FAFF83C40433C983F84B0F9DC1"),
        }
        for offset, expected in former.items():
            with self.subTest(offset=hex(offset)):
                self.assertEqual(source[offset : offset + len(expected)], expected)
                self.assertEqual(rendered[offset : offset + len(expected)], expected)
                self.assertFalse(any(edit["offset"] == hex(offset) for edit in applied))

    def test_vv4_research_note_marks_candidate_superseded(self) -> None:
        text = (ROOT / "docs" / "villager-breeding-overhaul-research.md").read_text(encoding="utf-8")
        self.assertIn("historical VV4 Birth Control candidate is rejected/superseded", text)
        self.assertIn("untouched vanilla Breeding and Embracing reference", text)
        self.assertIn("No VV4 executable edits are shipped or", text)
        self.assertIn("selectable.", text)


if __name__ == "__main__":
    unittest.main()
