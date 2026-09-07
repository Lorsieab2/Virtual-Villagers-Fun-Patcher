"""Regression coverage for the VV1 v1.34.34 startup crash."""

from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STOCK = ROOT / "research" / "stock-executables" / "Virtual Villagers - A New Home.exe"
MANIFEST = ROOT / "data" / "vv1_origins_feature.json"


class VV1StartupCrashRegressionTests(unittest.TestCase):
    @unittest.skipUnless(STOCK.exists(), "requires the exact-build VV1 stock executable")
    def test_obsolete_backedge_detour_is_absent_and_stock_bytes_remain(self) -> None:
        stock = STOCK.read_bytes()
        self.assertEqual(stock[0x24103 : 0x24103 + 5], bytes.fromhex("8B4E086A00"))

        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        offsets = {patch["offset"] for patch in manifest["patches"]}
        self.assertNotIn("0x24103", offsets)

    def test_active_all_pose_hooks_remain_installed(self) -> None:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        offsets = {patch["offset"] for patch in manifest["patches"]}
        for offset in ("0x377B8", "0x913C", "0x37798", "0x38900"):
            self.assertIn(offset, offsets)

    def test_generator_has_no_obsolete_backedge_or_list_plumbing(self) -> None:
        source = (ROOT / "scripts" / "build_vv1_origins_feature.py").read_text(
            encoding="utf-8"
        )
        for token in (
            "MASK_BACKEDGE_DETOUR",
            "MASK_LIST_COUNT_VA",
            "MASK_IDX_LIST_VA",
            "mask_backedge_hook_code",
        ):
            self.assertNotIn(token, source)


if __name__ == "__main__":
    unittest.main()
