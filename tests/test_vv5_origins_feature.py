from __future__ import annotations

import hashlib
import json
import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vv_fun_patcher import load_builds, render_patched_bytes

STOCK = ROOT / "research/stock-executables/Virtual Villagers - New Believers.exe"
MANIFEST = ROOT / "data/vv5_origins_feature.json"
BUILDER = ROOT / "scripts/build_vv5_origins_feature.py"
EXPANDED = ROOT / "data/expanded_256.json"
FEATURE_ID = "vv5_enable_origins_exclusive_features"


class VV5OriginsFeatureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.stock = STOCK.read_bytes()
        cls.feature = json.loads(MANIFEST.read_text(encoding="utf-8"))
        cls.payload_patch = next(
            item
            for item in cls.feature["patches"]
            if int(item["offset"], 0) == 0xDB000
        )
        cls.payload = bytes.fromhex(cls.payload_patch["after"])
        cls.source = BUILDER.read_text(encoding="utf-8")

    def test_exact_build_and_companion_identity(self) -> None:
        self.assertEqual(
            hashlib.sha256(self.stock).hexdigest().upper(),
            "92946781980220E9D1A2E6C573925519934608F5215F4A0F8CE3B90088C5C65D",
        )
        companion = ROOT / self.feature["companion_files"][0]["source"]
        self.assertEqual(
            hashlib.sha256(companion.read_bytes()).hexdigest().upper(),
            self.feature["companion_files"][0]["sha256"],
        )
        self.assertEqual(
            self.feature["companion_files"][0]["sha256"],
            "6BDFE416189513E752B8C48E4065945BA5CB27379EF1C50CEDCFFB84430C3795",
        )

    def test_all_guards_match_stock_and_payload_is_isolated(self) -> None:
        for item in self.feature["patches"]:
            offset = int(item["offset"], 0)
            before = bytes.fromhex(item["before"])
            self.assertEqual(self.stock[offset : offset + len(before)], before)
            self.assertEqual(len(before), len(bytes.fromhex(item["after"])))
        self.assertEqual(len(self.payload), 0xEA4)
        self.assertEqual(
            self.stock[0xDB000 : 0xDB000 + len(self.payload)],
            b"\0" * len(self.payload),
        )
        pe = struct.unpack_from("<I", self.stock, 0x3C)[0]
        section_table = pe + 24 + struct.unpack_from("<H", self.stock, pe + 20)[0]
        shr = section_table + 3 * 40
        self.assertEqual(self.stock[shr : shr + 8].rstrip(b"\0"), b".shr")
        characteristics = struct.unpack_from("<I", self.stock, shr + 36)[0]
        self.assertFalse(characteristics & 0x20000000)
        section_patch = next(
            item
            for item in self.feature["patches"]
            if int(item["offset"], 0) == shr + 36
        )
        self.assertEqual(section_patch["before"], "400000D0")
        self.assertEqual(section_patch["after"], "400000F0")
        expanded = json.loads(EXPANDED.read_text(encoding="utf-8"))
        for item in expanded["games"]["vv5"]["patches"]:
            start = int(item["offset"], 0)
            end = start + len(bytes.fromhex(item["before"]))
            self.assertTrue(end <= 0xDB000 or start >= 0xDC000)

    def test_time_warp_is_exactly_three_displayed_years(self) -> None:
        self.assertIn("mov eax, 129600", self.source)
        self.assertIn("idiv ecx", self.source)
        self.assertIn("sub dword ptr [0x4C6250], eax", self.source)
        self.assertIn("sbb dword ptr [0x4C6254], 0", self.source)
        self.assertIn("3 displayed villager years", self.feature["description"])
        self.assertIn(b"3 displayed years", self.payload)

    def test_barrel_uses_native_index_and_dynamic_150_256_guard(self) -> None:
        self.assertIn("call 0x4944C0", self.source)
        self.assertIn("mov ecx, dword ptr [0x41F1E6]", self.source)
        self.assertIn("sub ecx, 3", self.source)
        self.assertIn("or dword ptr [0x51D388], 4", self.source)
        self.assertIn("mov esi, 30", self.source)
        self.assertIn("and dword ptr [0x51D388], 0xFFFFFFFB", self.source)
        expanded = json.loads(EXPANDED.read_text(encoding="utf-8"))
        bound = next(
            item
            for item in expanded["games"]["vv5"]["patches"]
            if int(item["offset"], 0) == 0x1F1E6
        )
        self.assertEqual(bound["before"], "96000000")
        self.assertEqual(bound["after"], "00010000")

    def test_doublers_are_save_scoped_and_exclude_event_results(self) -> None:
        self.assertIn("test dword ptr [0x51D388], 1", self.source)
        self.assertIn("test dword ptr [0x51D388], 2", self.source)
        for address in (
            "0x414D0D",
            "0x416569",
            "0x416657",
            "0x414C2E",
            "0x41511E",
            "0x416D01",
            "0x418757",
            "0x41876C",
        ):
            self.assertIn(address, self.source)
        self.assertIn("test esi, esi", self.source)
        self.assertIn("test eax, eax", self.source)

    def test_six_float_skills_and_age_companions_are_written(self) -> None:
        for offset in (7260, 7264, 7268, 7272, 7276, 7280):
            self.assertIn(
                f"mov dword ptr [edx + {offset}], 0x42B40000", self.source
            )
        self.assertIn("cmp eax, 100", self.source)
        self.assertIn("mov eax, 100", self.source)
        self.assertIn("mov eax, 360", self.source)
        self.assertIn("add dword ptr [edx + 7228], ecx", self.source)
        self.assertIn("add dword ptr [edx + 7244], ecx", self.source)

    def test_running_changes_only_selected_record_preferences(self) -> None:
        self.assertIn("lea ecx, [edx + 8028]", self.source)
        self.assertIn("lea ecx, [edx + 8040]", self.source)
        self.assertIn("mov dword ptr [ecx], 38", self.source)
        self.assertIn("mov dword ptr [ecx], -1", self.source)
        self.assertIn("all Like slots are full", self.source)
        running_block = self.source.split("running:", 1)[1].split(
            "detail_success:", 1
        )[0]
        for forbidden in ("0x17D7C", "movement", "speed"):
            self.assertNotIn(forbidden, running_block)

    def test_composes_with_every_vv5_feature_in_all_four_modes(self) -> None:
        build = next(item for item in load_builds() if item.id == "vv5")
        all_vv5 = [
            item.id
            for item in __import__("vv_fun_patcher").load_fun_patches()
            if item.game_id == "vv5"
        ]
        self.assertIn(FEATURE_ID, all_vv5)
        for mode in (
            "collection_progression",
            "immediate_fixed",
            "experimental_expanded_256",
            "experimental_expanded_256_progression",
        ):
            with self.subTest(mode=mode):
                rendered, applied = render_patched_bytes(
                    STOCK, build, mode, all_vv5
                )
                self.assertGreater(len(applied), len(self.feature["patches"]))
                self.assertEqual(
                    bytes(rendered[0xDB000 : 0xDB000 + len(self.payload)]),
                    self.payload,
                )

    def test_expanded_output_keeps_vanilla_name_and_stock_save_fallback(self) -> None:
        build = next(item for item in load_builds() if item.id == "vv5")
        rendered, _ = render_patched_bytes(
            STOCK,
            build,
            "experimental_expanded_256",
            [FEATURE_ID],
        )
        self.assertEqual(bytes(rendered[0x95794 : 0x9579D]), b"%s%d.ldw\0")
        self.assertEqual(bytes(rendered[0x25709 : 0x2570E]), bytes.fromhex("E85EEF0600"))
        cave = bytes(rendered[0x9466C : 0x9466C + 102])
        self.assertIn(bytes.fromhex("68787D0100"), cave)
        self.assertIn(bytes.fromhex("FDF3A5FC"), cave)
        self.assertIn(bytes.fromhex("B919040000"), cave)
        self.assertIn(bytes.fromhex("B9FC1C0000"), cave)


if __name__ == "__main__":
    unittest.main()
