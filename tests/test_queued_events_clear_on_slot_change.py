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
