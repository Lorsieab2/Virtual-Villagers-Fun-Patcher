"""A queued event must not follow the player into another save.

Reported: upgrades stay "Unavailable" after switching save files.

Barrel of Babies and Island Event grey their row out while the event is
pending, and that pending state lives in the EXECUTABLE's `.shr` section --
process-global, not in the save file. VV1's own manifest calls it
"process-local". So buying a Barrel in village A and then loading village B
left B's row disabled for an event belonging to another save, and the delay
counter carried over too, so the queued event could be delivered into a
village that never paid for it.

Nothing cleared it. The only writes were purchase, delivery and refusal.

The fix reuses the save-slot capture hook, which already detects a slot CHANGE
and resets the per-save mask globals; the queued-event state belongs in that
same reset. This asserts it is emitted there, in the shipped manifest bytes
rather than in the generator source, because that hook is assembled and a
source-level check would not prove the stores survived assembly.
"""
from __future__ import annotations

import json
import re
import struct
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "data" / "vv1_origins_feature.json"

# The save-slot capture cave, and the three queued-event globals it must clear.
CAVE_OFFSET = "0x8e820"   # matched case-insensitively below
BARREL_PENDING_VA = 0x0048D700
BARREL_DELAY_COUNTER_VA = 0x0048D704
BARREL_UPGRADE_FLAG_VA = 0x0048D708


def _patch_rows():
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    rows = {}

    def walk(node):
        if isinstance(node, dict):
            offset, after = node.get("offset"), node.get("after")
            if isinstance(offset, str) and isinstance(after, str):
                rows.setdefault(offset.lower(), after)
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(data)
    return rows


def _cleared_addresses(blob: bytes) -> set[int]:
    """Every absolute address the cave zeroes, byte or dword."""
    found = set()
    for match in re.finditer(rb"\xc6\x05(....)\x00", blob, re.S):
        found.add(struct.unpack("<I", match.group(1))[0])
    for match in re.finditer(rb"\xc7\x05(....)\x00\x00\x00\x00", blob, re.S):
        found.add(struct.unpack("<I", match.group(1))[0])
    return found


class QueuedEventsClearOnSlotChangeTests(unittest.TestCase):
    def setUp(self) -> None:
        rows = _patch_rows()
        self.assertIn(
            CAVE_OFFSET, rows,
            f"the save-slot capture cave {CAVE_OFFSET} is not in the manifest; "
            "this suite would otherwise pass vacuously")
        self.blob = bytes.fromhex(rows[CAVE_OFFSET])

    def test_the_cave_is_not_empty(self) -> None:
        """Guards against the whole file passing on a zero-length patch."""
        self.assertGreater(len(self.blob), 0x40, "the save-slot cave is empty")

    def test_every_queued_event_global_is_cleared(self) -> None:
        cleared = _cleared_addresses(self.blob)
        for address, name in (
            (BARREL_PENDING_VA, "Barrel pending flag"),
            (BARREL_DELAY_COUNTER_VA, "Barrel delay counter"),
            (BARREL_UPGRADE_FLAG_VA, "three-child one-shot"),
        ):
            with self.subTest(state=name):
                self.assertIn(
                    address, cleared,
                    f"the {name} at {address:#010x} is not cleared when the "
                    "player changes save slot, so a purchase made in one "
                    "village follows them into the next one -- the row reads "
                    "Unavailable, and the queued event can be delivered into a "
                    "save that never paid for it")

    def test_the_cave_still_fits_its_reservation(self) -> None:
        """It sits between 0x820 and the mask tick export name at 0x8F0."""
        self.assertLessEqual(
            len(self.blob), 0x8F0 - 0x820,
            "the save-slot capture cave has outgrown its reservation and would "
            "overlap the mask tick export name")


if __name__ == "__main__":
    unittest.main()


# --- VV2 ---------------------------------------------------------------------
# VV2's slot stub lives in the APPENDED .vvmk page, which has no manifest row at
# all -- the page is built by the stage-2 builder and appended whole. Searching
# data/vv2_origins_feature.json for these clears finds nothing even when the fix
# is present, which cost me a wrong "it did not land" conclusion once already.
# So VV2 is asserted against the RENDERED executable, which is what ships.
VV2_STOCK = ROOT / "research" / "stock-executables" / "Virtual Villagers - The Lost Children.exe"
VV2_QUEUED_GLOBALS = {
    0x0049C700: "Barrel pending flag",
    0x0049C704: "three-child one-shot",
    0x0049C708: "Barrel cue counter",
}


@unittest.skipUnless(VV2_STOCK.is_file(), "VV2 stock executable not present")
class VV2QueuedEventsClearOnSlotChangeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        import sys
        sys.path.insert(0, str(ROOT / "src"))
        import vv_fun_patcher as patcher

        build = next(b for b in patcher.load_builds() if b.id == "vv2")
        cls.image, _ = patcher.render_patched_bytes(
            VV2_STOCK, build, "immediate_fixed",
            ["vv2_origins_village_wide_upgrades"])

    def _stub(self) -> bytes:
        """The slot stub, located by FOLLOWING the detour and translating the
        target through the section table.

        Both steps matter. The stub lives in the appended `.vvmk` section, whose
        virtual address is NOT `file offset + 0x400000` -- VA 0x4B4000 maps to
        raw 0xB2000 -- so the naive subtraction lands past the end of the image
        and reads empty bytes, which looks exactly like a missing fix.
        """
        detour = self.image[0x3160:0x3166]
        self.assertEqual(detour[0], 0xE9,
                         "0x3160 is not a jmp; the save-builder detour moved")
        rel = struct.unpack("<i", detour[1:5])[0]
        target = 0x403160 + 5 + rel

        pe = struct.unpack_from("<I", self.image, 0x3C)[0]
        count = struct.unpack_from("<H", self.image, pe + 6)[0]
        opt = struct.unpack_from("<H", self.image, pe + 20)[0]
        base = struct.unpack_from("<I", self.image, pe + 52)[0]
        for index in range(count):
            entry = pe + 24 + opt + index * 40
            va = base + struct.unpack_from("<I", self.image, entry + 12)[0]
            size = struct.unpack_from("<I", self.image, entry + 8)[0]
            raw = struct.unpack_from("<I", self.image, entry + 20)[0]
            if va <= target < va + size:
                offset = raw + (target - va)
                return self.image[offset:offset + 0x50]
        self.fail(f"the detour target {target:#x} is in no section")

    def test_the_stub_is_where_the_detour_points(self) -> None:
        """Without this the byte checks below could scan unrelated padding."""
        self.assertEqual(
            self._stub()[0], 0x50,
            "the resolved slot stub does not start with `push eax`; the "
            "detour target has moved and this suite is reading the wrong "
            "bytes")

    def test_every_queued_event_global_is_cleared(self) -> None:
        cleared = _cleared_addresses(self._stub())
        for address, name in VV2_QUEUED_GLOBALS.items():
            with self.subTest(state=name):
                self.assertIn(
                    address, cleared,
                    f"VV2's {name} at {address:#010x} is not cleared on a save-"
                    "slot change, so a Barrel bought in one village leaves the "
                    "next village's row reading Unavailable")

    def test_the_clears_sit_behind_the_slot_change_compare(self) -> None:
        """They must NOT run on every save, only on a real slot change.

        The save-path builder runs on saves as well as loads. Clearing
        unconditionally would discard a legitimately pending event on every
        autosave -- a different bug in the same place.
        """
        stub = self._stub()
        compare = stub.find(b"\x3b\x05")          # cmp eax, [SLOT_VA]
        self.assertGreaterEqual(compare, 0, "no slot compare in the stub")
        first_clear = min(
            stub.find(struct.pack("<I", a)) for a in VV2_QUEUED_GLOBALS)
        self.assertGreater(
            first_clear, compare,
            "a queued-event clear runs before the slot-change compare, so it "
            "would fire on every autosave and discard a pending event")
