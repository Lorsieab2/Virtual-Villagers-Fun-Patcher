from __future__ import annotations

import hashlib
import json
import struct
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vv_fun_patcher import (  # noqa: E402
    _pe_checksum_layout,
    load_builds,
    load_patch_modes,
    load_fun_patches,
    render_patched_bytes,
)


STOCK = ROOT / "research" / "stock-executables" / "Virtual Villagers - The Tree of Life.exe"
MANIFEST = ROOT / "data" / "vv4_origins_feature.json"
BUILDER = ROOT / "scripts" / "build_vv4_origins_feature.py"
COMPANION = ROOT / "assets" / "origins" / "VVFP Origins Icons.dll"
EXPANDED = ROOT / "data" / "expanded_256.json"
FEATURE_ID = "vv4_enable_origins_exclusive_features"
RUNNING_PREFERENCE_ID = 38
MODES = (
    "collection_progression",
    "immediate_fixed",
)


class VV4OriginsFeatureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.stock_bytes = STOCK.read_bytes()
        cls.manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        cls.builder = BUILDER.read_text(encoding="utf-8")
        cls.build = next(item for item in load_builds() if item.id == "vv4")

    def test_exact_build_and_companion_identity(self) -> None:
        self.assertEqual(
            hashlib.sha256(self.stock_bytes).hexdigest().upper(),
            "6D27A429FFCA5F1F71FDD7ECA761ED1BB67E85F976494BA178B3D7BE01F1B220",
        )
        companion = self.manifest["companion_files"][0]
        self.assertEqual(
            companion["sha256"], hashlib.sha256(COMPANION.read_bytes()).hexdigest().upper()
        )

    def test_all_guards_match_stock_and_payload_is_in_zero_cave(self) -> None:
        payload_patch = next(
            item
            for item in self.manifest["patches"]
            if int(item["offset"], 0) == 0x89373
        )
        payload = bytes.fromhex(payload_patch["after"])
        self.assertLessEqual(len(payload), 0xC8D)
        self.assertEqual(self.stock_bytes[0x89373 : 0x89373 + len(payload)], b"\0" * len(payload))
        for item in self.manifest["patches"]:
            offset = int(item["offset"], 0)
            before = bytes.fromhex(item["before"])
            after = bytes.fromhex(item["after"])
            self.assertEqual(self.stock_bytes[offset : offset + len(before)], before)
            self.assertEqual(len(before), len(after))
        section_patch = next(
            item for item in self.manifest["patches"] if int(item["offset"], 0) == 0x244
        )
        self.assertEqual(section_patch["before"], "40000040")
        self.assertEqual(section_patch["after"], "40000060")
        expanded = json.loads(EXPANDED.read_text(encoding="utf-8"))
        for item in expanded["games"]["vv4"]["patches"]:
            start = int(item["offset"], 0)
            end = start + len(bytes.fromhex(item["before"]))
            self.assertTrue(end <= 0x89373 or start >= 0x89373 + len(payload))

    def test_builder_uses_corrected_pe_and_details_guards(self) -> None:
        self.assertIn('patch(0x244, bytes.fromhex("40000040")', self.builder)
        self.assertIn('bytes.fromhex("891D5C904D00891D58904D00")', self.builder)
        self.assertIn('rel32_jump(0x447A25, detail_constructor) + b"\\x90" * 7', self.builder)
        self.assertIn("0x46AD80", self.builder)
        self.assertIn("VV4_MASTER_VALUE = 0x42C80000", self.builder)
        self.assertIn("call 0x46AF00", self.builder)
        self.assertIn("0xA01C0", self.builder)

    def test_vv4_native_upgrade_contract_is_emitted(self) -> None:
        record = json.loads(
            (ROOT / "data" / "vv4_origins_village_wide_upgrades.json").read_text(
                encoding="utf-8"
            )
        )
        fields = record["record_fields"]
        self.assertEqual(fields["native_skill_writer"], "0x46AD80")
        self.assertEqual(fields["native_skill_writer_index"], "skill ordinal 0..4")
        self.assertEqual(fields["mastery_target"], "Float32 100.0")
        self.assertEqual(
            fields["native_skill_writer_value"], "Float32 delta: 100.0-current"
        )
        self.assertIn("native Float32 skill writer", record["behavior_changes"][3])

        ui = self.manifest["ui_contract"]
        self.assertEqual(ui["forbidden_helpers"], ["sub_40D8A0"])
        self.assertEqual(ui["native_factory"]["va"], "0x489F37")
        self.assertEqual(len(ui["result_helper"]["call_sites"]), 2)

        payload = bytes.fromhex(
            next(item for item in self.manifest["patches"] if item["offset"] == "0x89373")[
                "after"
            ]
        )
        self.assertIn(struct.pack("<I", 0x42C80000), payload)
        self.assertNotIn(struct.pack("<I", 0x42B40000), payload)

    def test_vv4_cure_and_running_source_guards_are_present(self) -> None:
        self.assertIn("cmp dword ptr [esi + 0x1C40], 80", self.builder)
        self.assertIn("lea eax, [esi + 0x1C34]", self.builder)
        self.assertIn("cmp dword ptr [esi + 0x1C40], 100", self.builder)
        self.assertIn("mov byte ptr [esi + 0x1C48], 0", self.builder)
        self.assertIn("inc dword ptr [0x4D6DF0]", self.builder)
        self.assertIn("je running_already", self.builder)
        self.assertIn("mov dword ptr [ecx], {RUNNING_PREFERENCE_ID}", self.builder)

    def test_composes_with_current_vv4_features_in_all_modes(self) -> None:
        patch_ids = [patch.id for patch in load_fun_patches() if patch.game_id == "vv4"]
        self.assertIn(FEATURE_ID, patch_ids)
        self.assertIn("vv4_origins_village_wide_upgrades", patch_ids)
        self.assertNotIn("vv4_full_mastery_all_stage_a_candidate", patch_ids)
        self.assertNotIn("vv4_full_heal_cure_all_candidate", patch_ids)
        for mode in MODES:
            with self.subTest(mode=mode):
                rendered, applied = render_patched_bytes(STOCK, self.build, mode, patch_ids)
                self.assertTrue(applied)
                checksum_offset, _ = _pe_checksum_layout(rendered)
                self.assertNotEqual(struct.unpack_from("<I", rendered, checksum_offset)[0], 0)
                self.assertNotEqual(bytes(rendered[0x89373 : 0x89373 + 4]), b"\0\0\0\0")

    def test_expanded_256_modes_are_removed(self) -> None:
        mode_ids = {mode.id for mode in load_patch_modes()}
        self.assertNotIn("experimental_expanded_256", mode_ids)
        self.assertNotIn("experimental_expanded_256_progression", mode_ids)


if __name__ == "__main__":
    unittest.main()
