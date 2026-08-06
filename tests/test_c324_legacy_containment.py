from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class C324LegacyContainmentTests(unittest.TestCase):
    def test_vv1_cure_guard_and_metadata_are_fail_closed(self) -> None:
        candidate = json.loads(
            (ROOT / "data/candidates/vv1_vv2_fullscreen_safe_candidate.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(candidate["legacy_cure_containment"]["full_heal_status"], "pending; no replacement is enabled or catalog-visible")
        self.assertFalse(candidate["enabled"])
        self.assertFalse(candidate["catalog_enabled"])
        self.assertTrue(candidate["catalog_hidden"])
        self.assertTrue(candidate["expanded_rejected"])
        self.assertEqual(candidate["games"]["vv1"]["cure_guard"], {"va": "0x456A88", "before": "83FB06", "after": "83FB05"})
        self.assertEqual(candidate["companion"]["parent_sha256"], "2ED1100E7F2EA5B8E522C2DE11F6B00CA8A02B968319C251365E9EFD634BCAF9")
        self.assertEqual(candidate["companion"]["candidate_sha256"], "846BA4EDF29E52689883A6E20DBF5CB92244DBB52531D7573EDAFF6C9C91543D")
        self.assertEqual(candidate["companion"]["resource_201_items"], 41)
        self.assertTrue(candidate["companion"]["resource_202_unchanged"])

    def test_vv1_guard_preimage_and_replacement_are_exact(self) -> None:
        candidate = json.loads(
            (ROOT / "data/candidates/vv1_vv2_fullscreen_safe_candidate.json").read_text(
                encoding="utf-8"
            )
        )
        guard = candidate["games"]["vv1"]["cure_guard"]
        self.assertEqual(guard["va"], "0x456A88")
        self.assertEqual(guard["before"], "83FB06")
        self.assertEqual(guard["after"], "83FB05")

    def test_burial_detours_are_absent_and_stock_guards_remain(self) -> None:
        manifest = json.loads((ROOT / "data/statistics_features.json").read_text(encoding="utf-8"))
        forbidden_offsets = {"0x5F45B", "0x664DC", "0x6FF12"}
        for feature in manifest["features"]:
            for patch in feature["patches"]:
                self.assertNotIn(patch.get("offset"), forbidden_offsets)
                self.assertNotIn("buried", patch.get("purpose", "").casefold())
        expected = {
            "Virtual Villagers - The Secret City.exe": (0x5F45B, "881EE9B8010000"),
            "Virtual Villagers - The Tree of Life.exe": (0x664DC, "885EFD385EFD"),
            "Virtual Villagers - New Believers.exe": (0x6FF12, "889ED41C0000"),
        }
        for name, (offset, guard) in expected.items():
            stock = (ROOT / "research/stock-executables" / name).read_bytes()
            self.assertEqual(stock[offset : offset + len(bytes.fromhex(guard))], bytes.fromhex(guard))

    def test_exporters_and_vv2_elders_remain_documented(self) -> None:
        source = (ROOT / "native/statistics_export/statistics_export.c").read_text(encoding="utf-8")
        docs = (ROOT / "docs/village-statistics-export-research.md").read_text(encoding="utf-8")
        self.assertIn("Oldest Villager", source)
        self.assertIn("Village Elders", source)
        self.assertIn("VV2 `state+0x2E514` is **Village Elders**", docs)
        self.assertIn("Memorial migration", docs)
        self.assertIn("ON HOLD", docs)
        self.assertNotIn("burial_hook_va", (ROOT / "scripts/build_statistics_features.py").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
