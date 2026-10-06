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

        # A delivery creates only when its whole litter fits in the records
        # (the golden-child mother's: her Golden Child too); otherwise it
        # waits with the pregnancy kept. Each stock call becomes a CALL into
        # its own guard (so the creator still sees the delivery's own return
        # address, which Cause of Death's birth markers read); both guards
        # first ask the record demand at 0x456580, which calls the bounded
        # count 0x45684F (it moved from 0x456860 when it learnt to return the
        # babies still owed too; Codex, #543).
        # tests/test_slot_guards_count_records.py runs them in an emulator;
        # this pins their shape.
        expected = {
            0x2EF5F: 0x456594,
            0x2EFD0: 0x4565B0,
        }
        cave = {0x456580: bytes.fromhex(patches[0x56580]["after"]),
                0x4565B0: bytes.fromhex(patches[0x565B0]["after"])}

        def at(va, n):
            base = 0x456580 if va < 0x4565B0 else 0x4565B0
            return cave[base][va - base:va - base + n]

        for trampoline, guard in expected.items():
            with self.subTest(trampoline=hex(trampoline)):
                after = bytes.fromhex(patches[trampoline]["after"])
                self.assertEqual(len(after), 5)
                self.assertEqual(after[0], 0xE8)
                self.assertEqual(trampoline + 0x400000 + 5 + struct.unpack("<i", after[1:])[0], guard)
                call = at(guard, 5)
                self.assertEqual(call[0], 0xE8)
                self.assertEqual(guard + 5 + struct.unpack("<i", call[1:])[0], 0x456580)
        demand = at(0x456580, 5)
        self.assertEqual(0x456580 + 5 + struct.unpack("<i", demand[1:])[0], 0x45684F)

        # The bounded count: 256 records, never more (ecx = 0x100, `loop`),
        # the occupied ones in eax and the babies still owed in edx.
        self.assertNotIn(0x56860, patches, "the old sweep's place is the count's own now")
        self.assertEqual(bytes.fromhex(patches[0x5684F]["before"]), bytes(49))
        self.assertEqual(
            bytes.fromhex(patches[0x5684F]["after"]),
            bytes.fromhex("51568DB15803000031C031D231C9FEC580BED0FCFFFF00740D40833E007407837E040113560481C6"
                          "D8030000E2E25E59C3"),
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
