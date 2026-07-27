from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vv_fun_patcher import (  # noqa: E402
    load_builds,
    load_fun_patches,
    load_patch_modes,
    render_patched_bytes,
    resolve_fun_patch_ids,
)


class VV4BirthControlRollbackTests(unittest.TestCase):
    def test_vv1_entry_is_disabled_on_hold_and_has_no_executable_edits(self) -> None:
        manifest = json.loads((ROOT / "data" / "builds.json").read_text(encoding="utf-8"))
        entry = next(item for item in manifest["fun_patches"] if item["id"] == "vv1_birth_control")
        self.assertFalse(entry["enabled"])
        self.assertEqual(entry["patches"], [])
        self.assertIn("ON HOLD", entry["status"])
        self.assertIn("c8d268d", entry["status"])
        description = entry["description"]
        for text in (
            "food>=400 gate",
            "live instruction interiors",
            "0x56740 is not a certified cave",
            "incorrectly rejected both sexes",
            "sex/category-2 carrier-only",
            "no male ceiling",
            "0x4477AF",
            "0x446E70",
            "0x447070",
            "direct event births and pending delivery remain native",
        ):
            self.assertIn(text, description)

    def test_rejected_vv1_offsets_are_absent_from_active_and_rendered_patches(self) -> None:
        rejected = {0x3DBBE, 0x458D0, 0x447840, 0x45930}
        catalog = load_fun_patches()
        self.assertNotIn("vv1_birth_control", {patch.id for patch in catalog})
        for feature in catalog:
            edits = list(feature.raw.get("patches", []))
            for mode_edits in feature.raw.get("patch_mode_overrides", {}).values():
                edits.extend(mode_edits)
            for edit in edits:
                self.assertNotIn(int(edit["offset"], 0), rejected, feature.id)

        build = next(item for item in load_builds() if item.id == "vv1")
        source = ROOT / "research" / "stock-executables" / build.input_name
        game_patches = [patch for patch in catalog if patch.game_id == "vv1"]
        selected = resolve_fun_patch_ids(
            [patch.id for patch in game_patches],
            game_id="vv1",
            patches=game_patches,
        )
        for mode in load_patch_modes():
            with self.subTest(mode=mode.id):
                _, applied = render_patched_bytes(source, build, mode.id, selected)
                self.assertTrue(
                    rejected.isdisjoint(int(edit["offset"], 0) for edit in applied)
                )

    def test_vv1_birth_control_is_absent_from_cli_help(self) -> None:
        result = subprocess.run(
            [sys.executable, "src/vv_fun_patcher.py", "dry-run-all", "--help"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertNotIn("vv1_birth_control", result.stdout)

    def test_vv1_research_and_transparency_record_exact_rejection(self) -> None:
        research = (ROOT / "docs" / "villager-breeding-overhaul-research.md").read_text(
            encoding="utf-8"
        )
        transparency = (ROOT / "docs" / "transparency-log.md").read_text(encoding="utf-8")
        for text in (
            "c8d268d",
            "0x3DBBE",
            "food >= 400",
            "0x458D0",
            "0x45930",
            "live instruction interiors",
            "0x56740",
            "sex/category-2 carrier-only",
            "0x4477AF",
            "0x446E70",
            "0x447070",
            "Direct event-created births and pending",
        ):
            self.assertIn(text, research)
        self.assertIn("disabled historical `vv1_birth_control` entry has no executable patches", transparency)
        self.assertIn("remains ON HOLD", transparency)

    def test_vv4_entry_is_disabled_rejected_and_has_no_executable_edits(self) -> None:
        manifest = json.loads((ROOT / "data" / "builds.json").read_text(encoding="utf-8"))
        entry = next(item for item in manifest["fun_patches"] if item["id"] == "vv4_birth_control")
        self.assertFalse(entry["enabled"])
        self.assertIn("rejected/superseded", entry["status"])
        self.assertIn("untouched vanilla breeding reference", entry["status"])
        self.assertEqual(entry["patches"], [])

    def test_vv4_and_vv5_are_native_no_patch_references(self) -> None:
        builds = {item.id: item for item in load_builds()}
        self.assertEqual(builds["vv4"].size, 929792)
        self.assertEqual(
            builds["vv4"].sha256,
            "6D27A429FFCA5F1F71FDD7ECA761ED1BB67E85F976494BA178B3D7BE01F1B220",
        )
        self.assertEqual(
            builds["vv5"].sha256,
            "92946781980220E9D1A2E6C573925519934608F5215F4A0F8CE3B90088C5C65D",
        )
        self.assertEqual(builds["vv5"].size, 991232)
        ids = {p.id for p in load_fun_patches()}
        self.assertNotIn("vv4_birth_control", ids)
        self.assertNotIn("vv5_birth_control", ids)
        text = (ROOT / "docs" / "villager-breeding-overhaul-research.md").read_text(encoding="utf-8")
        for marker in ("0x460C10", "0x4689A0", "0x46A3C0", "0x470A10", "0x467D20", "0x465E00"):
            self.assertIn(marker, text)
        self.assertIn("VV5 is also a native no-patch reference", text)
        self.assertIn("No VV5 Birth Control bytes are implemented or", text)
        self.assertIn("reserved.", text)
        transparency = (ROOT / "docs" / "transparency-log.md").read_text(encoding="utf-8")
        self.assertIn("## Birth Control scope", transparency)
        self.assertIn("Birth Control implementation remains on hold only for VV1, VV2, and VV3", transparency)

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
