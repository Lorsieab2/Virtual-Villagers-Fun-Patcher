"""A failed Barrel dispatch must not leave the three-child override armed.

`BARREL_ROOM_CHECK` arms the one-shot immediately before dispatch, but the
event construction after it (`call 0x44AF03`) can still return zero.  That left
the flag armed with no dispatch, and because the delivery recheck retries on a
later tick, a persistent construction failure re-armed it every tick rather
than once.  Whichever barrel arrived next -- natural or purchased -- then
silently inherited the three-child override.

The consequence favours the player, which is why it was recorded rather than
rushed into v1.34.31.  It is fixed here because the `.vv1mc` slot the room
check owns had 182 of its 256 bytes free and the fix is 12.

These tests pin the two halves that can rot independently:

* the construction-failure path must reach a disarm that clears the flag;
* the *no-room* path must NOT, because nothing was armed on it -- clearing
  there would be harmless today but would hide a future ordering mistake.
"""

import json
import struct
import unittest
from pathlib import Path

try:
    import capstone
except ImportError:  # pragma: no cover - exercised only without capstone
    capstone = None

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "data" / "vv1_origins_feature.json"

MAIN_HELPER = 0x8B710
MAIN_HELPER_VA = 0x48D710
ROOM_CHECK = 0x8EB00
ROOM_CHECK_VA = 0x490B00
DISARM = 0x8EB80
DISARM_VA = 0x490B80
UPGRADE_FLAG = 0x48D708
PENDING = 0x48D700
CONSTRUCTOR = 0x44AF03
# The room check and the disarm stub share one 0x100 reservation, which ends
# exactly where vv1_birth_control's composition overlay begins (0x8EC00).
RESERVATION_END = 0x8EC00


def _rows():
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    found = {}
    stack = [data]
    while stack:
        item = stack.pop()
        if isinstance(item, dict):
            offset, after = item.get("offset"), item.get("after")
            if isinstance(offset, str) and isinstance(after, str):
                found.setdefault(int(offset, 0), after)
            stack.extend(item.values())
        elif isinstance(item, list):
            stack.extend(item)
    return found


def _disasm(blob, va):
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    return list(md.disasm(bytes.fromhex(blob), va))


@unittest.skipIf(capstone is None, "requires capstone")
class BarrelDisarmOnFailureTests(unittest.TestCase):
    def setUp(self):
        self.rows = _rows()
        for offset in (MAIN_HELPER, ROOM_CHECK, DISARM):
            self.assertIn(offset, self.rows, f"{offset:#x} is not emitted")
        self.main = _disasm(self.rows[MAIN_HELPER], MAIN_HELPER_VA)
        self.disarm = _disasm(self.rows[DISARM], DISARM_VA)

    # -- placement ---------------------------------------------------------

    def test_disarm_stub_stays_inside_the_shared_reservation(self):
        end = DISARM + len(self.rows[DISARM]) // 2
        self.assertLessEqual(
            end,
            RESERVATION_END,
            "the disarm stub runs into vv1_birth_control's composition overlay",
        )

    def test_disarm_stub_does_not_overlap_the_room_check(self):
        room_end = ROOM_CHECK + len(self.rows[ROOM_CHECK]) // 2
        self.assertLessEqual(room_end, DISARM)

    def test_main_helper_still_fits_its_cave(self):
        self.assertLessEqual(
            len(self.rows[MAIN_HELPER]) // 2,
            0x80,
            "the helper would run into EQUAL_DIVISION_CORE",
        )

    # -- the stub ----------------------------------------------------------

    def test_disarm_clears_the_override_flag(self):
        clears = [
            i
            for i in self.disarm
            if i.mnemonic == "mov"
            and hex(UPGRADE_FLAG) in i.op_str.lower()
            and i.op_str.rstrip().endswith(", 0")
        ]
        self.assertEqual(len(clears), 1, "the stub must clear the one-shot")

    def test_disarm_resumes_at_the_helpers_shared_restore(self):
        """Derived from the assembled helper, never restated by hand."""
        blob = bytes.fromhex(self.rows[MAIN_HELPER])
        popad = blob.rindex(b"\x61")
        self.assertEqual(
            blob[popad + 1],
            0xE9,
            "the last popad is not the one before the tail jmp",
        )
        expected = MAIN_HELPER_VA + popad
        jumps = [i for i in self.disarm if i.mnemonic == "jmp"]
        self.assertEqual(len(jumps), 1)
        self.assertEqual(
            int(jumps[0].op_str, 16),
            expected,
            "the stub resumes somewhere other than the shared restore",
        )

    # -- the wiring --------------------------------------------------------

    def _branch_after(self, call_target):
        call = next(
            i
            for i in self.main
            if i.mnemonic == "call" and i.op_str == hex(call_target)
        )
        return next(
            i
            for i in self.main
            if i.address > call.address and i.mnemonic in {"je", "jz"}
        )

    def test_construction_failure_routes_through_the_disarm(self):
        branch = self._branch_after(CONSTRUCTOR)
        target = int(branch.op_str, 16)
        tail = [i for i in self.main if i.address >= target]
        self.assertTrue(tail, "the failure branch leaves the helper")
        self.assertEqual(
            tail[0].mnemonic,
            "jmp",
            "construction failure must reach the disarm, not fall into popad",
        )
        self.assertEqual(int(tail[0].op_str, 16), DISARM_VA)

    def test_no_room_path_does_not_disarm(self):
        """Nothing was armed on that path; clearing there would mask an
        ordering mistake rather than fix one."""
        branch = self._branch_after(ROOM_CHECK_VA)
        target = int(branch.op_str, 16)
        tail = [i for i in self.main if i.address >= target]
        self.assertEqual(
            tail[0].mnemonic,
            "popal",
            "the no-room refusal must land straight on the shared restore",
        )

    def test_no_room_path_still_leaves_the_token_pending(self):
        branch = self._branch_after(ROOM_CHECK_VA)
        tail = [i for i in self.main if i.address >= int(branch.op_str, 16)]
        cleared = [
            i
            for i in tail
            if i.mnemonic == "mov" and hex(PENDING) in i.op_str.lower()
        ]
        self.assertEqual(cleared, [], "a held barrel must stay queued")

    def test_the_two_refusal_paths_are_distinct(self):
        """They were the same label before this fix; if they collapse back,
        construction failure silently stops disarming again."""
        self.assertNotEqual(
            int(self._branch_after(CONSTRUCTOR).op_str, 16),
            int(self._branch_after(ROOM_CHECK_VA).op_str, 16),
        )


if __name__ == "__main__":
    unittest.main()
