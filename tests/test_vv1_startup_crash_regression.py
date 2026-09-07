"""Regression coverage for the VV1 v1.34.34 startup crash."""

from __future__ import annotations

import json
import struct
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STOCK = ROOT / "research" / "stock-executables" / "Virtual Villagers - A New Home.exe"
MANIFEST = ROOT / "data" / "vv1_origins_feature.json"


class VV1StartupCrashRegressionTests(unittest.TestCase):
    def test_full_capacity_two_creation_path_is_preflighted(self) -> None:
        builds = json.loads((ROOT / "data" / "builds.json").read_text(encoding="utf-8"))
        game = next(item for item in builds["games"] if item["id"] == "vv1")
        patches = {int(item["offset"], 16): item for item in game["safety_patches"]}

        # The first creation is allowed only with two slots available; the
        # second is allowed only with one slot available. Both trampolines
        # route through separate zero-filled caves and retain the stock call
        # when the preflight succeeds. The count comes from live record flags.
        expected = {
            0x2EF5F: (0x565E0, 0xFF),
            0x2EFD0: (0x56840, 0x100),
        }
        for trampoline, (cave, threshold) in expected.items():
            with self.subTest(trampoline=hex(trampoline)):
                row = patches[trampoline]
                after = bytes.fromhex(row["after"])
                self.assertEqual(len(after), 5)
                self.assertEqual(after[0], 0xE9)
                self.assertEqual(
                    trampoline + 0x400000 + 5 + struct.unpack("<i", after[1:])[0],
                    cave + 0x400000,
                )
                cave_bytes = bytes.fromhex(patches[cave]["after"])
                self.assertEqual(cave_bytes[0], 0xE8)
                self.assertEqual(cave_bytes[5], 0x3D)
                self.assertEqual(cave_bytes[6:10], threshold.to_bytes(4, "little"))
                self.assertEqual(cave_bytes[10], 0x73)

        self.assertEqual(bytes.fromhex(patches[0x565E0]["before"]), bytes(32))
        self.assertEqual(bytes.fromhex(patches[0x56840]["before"]), bytes(32))
        self.assertEqual(bytes.fromhex(patches[0x56860]["before"]), bytes(32))
        self.assertEqual(
            bytes.fromhex(patches[0x56860]["after"]),
            bytes.fromhex("5131C08D512831C9803A0074014081C2D80300004181F90001000072EB59C3")
            + bytes(1),
        )

    def test_obsolete_backedge_detour_is_absent_from_the_manifest(self) -> None:
        """The central pin, and it must not depend on an optional fixture.

        `research/` is gitignored, so a clean checkout has no stock executable.
        Guarding this assertion behind the fixture meant the one check that
        stops the crashing detour being reintroduced was skipped in exactly the
        environment that most needs it. Review caught this on #268.
        """
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        offsets = {patch["offset"] for patch in manifest["patches"]}
        self.assertNotIn("0x24103", offsets)

    @unittest.skipUnless(STOCK.exists(), "requires the exact-build VV1 stock executable")
    def test_stock_bytes_at_the_retired_detour_site_are_unchanged(self) -> None:
        """Only this half genuinely needs the stock binary."""
        stock = STOCK.read_bytes()
        self.assertEqual(stock[0x24103 : 0x24103 + 5], bytes.fromhex("8B4E086A00"))

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
