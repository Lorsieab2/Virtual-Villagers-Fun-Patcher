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
        self.assertEqual(candidate["legacy_cure_containment"]["status"], "contained; command 5 is rejected before price/funds/legacy Cure, while commands 0-4 and command 7 remain bytewise on their certified paths")
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

    def test_vv1_command5_preprice_rejection_is_exact_and_preserves_command7(self) -> None:
        candidate = json.loads(
            (ROOT / "data/candidates/vv1_vv2_fullscreen_safe_candidate.json").read_text(
                encoding="utf-8"
            )
        )
        rejection = candidate["legacy_cure_containment"]["command5_preprice_rejection"]
        self.assertEqual(rejection["compare"], {"va": "0x456A8D", "before": "83FB08", "after": "83FB05"})
        self.assertEqual(rejection["branch"], {"va": "0x456A90", "before": "0F872FFFFFFF", "after": "0F842FFFFFFF"})
        self.assertEqual(rejection["target"], "0x4569C5")
        self.assertEqual(rejection["legacy_deductions"], ["0x456AD5", "0x456AB3"])
        self.assertEqual(rejection["legacy_cure"], "0x456B9D")
        # The first guard remains the certified command-0..4 split; command 7
        # is not redirected by this containment metadata.
        self.assertEqual(candidate["games"]["vv1"]["cure_guard"]["after"], "83FB05")

    def test_burial_is_counted_at_pickup_and_never_at_retirement(self) -> None:
        """The counter may hook the pickup, and only the pickup.

        The requirements define Villagers Buried as incrementing exactly once
        at the earliest successful skeleton pickup, and rule out grave
        placement, record retirement, and any site gated on memorial capacity.
        The three offsets below are the record-retirement sites -- VV3
        sub_45F3E0, VV4 sub_46EF10 and VV5 sub_46FE90 -- which remain
        forbidden and must still hold their stock bytes.

        This previously asserted that no burial detour existed at all. That
        was correct while no pickup site had been established; now that one
        has, a blanket ban would forbid the feature the requirements ask for,
        so the ban is narrowed to the sites that are actually wrong.
        """
        manifest = json.loads((ROOT / "data/statistics_features.json").read_text(encoding="utf-8"))
        forbidden_offsets = {"0x5F45B", "0x664DC", "0x6FF12"}
        # The pickup latch clear in each game -- the only permitted sites.
        permitted_pickup = {
            "0x48F65",   # VV1 sub_448600 case 20
            "0x6503B",   # VV2 sub_464CD0 case 23
            "0x62293",   # VV3 sub_461FB0 case 25
            "0x6A977",   # VV4 sub_46A4D0 case 27
            "0x73F8F",   # VV5 sub_473B30
        }
        for feature in manifest["features"]:
            for patch in feature["patches"]:
                offset = patch.get("offset")
                self.assertNotIn(offset, forbidden_offsets)
                purpose = patch.get("purpose", "").casefold()
                if "pickup" in purpose or "buried" in purpose:
                    self.assertIn(
                        offset,
                        permitted_pickup,
                        "a burial patch may only hook the pickup latch clear",
                    )
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
        # The builder now carries a burial hook. It is pinned to the pickup
        # latch clear by the test above rather than forbidden outright.
        builder = (ROOT / "scripts/build_statistics_features.py").read_text(encoding="utf-8")
        for game, hook in (
            ("vv1", "0x448F65"),
            ("vv2", "0x46503B"),
            ("vv3", "0x462293"),
            ("vv4", "0x46A977"),
            ("vv5", "0x473F8F"),
        ):
            with self.subTest(game=game):
                self.assertIn(hook.upper().replace("0X", "0x"), builder)


if __name__ == "__main__":
    unittest.main()
