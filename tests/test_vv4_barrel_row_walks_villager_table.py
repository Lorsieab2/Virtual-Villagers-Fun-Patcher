"""The Tree of Life's Barrel row must count free slots in the VILLAGER table.

The Tech menu's pending-rows routine marks the Barrel of Babies row "no room"
(state bit 0x2000000) unless three villager slots are free, counting unburied
remains and pregnancies as occupants. The slots live in the static villager
manager at 0x50E568: occupied byte at manager+0x1D08 (record +0x44, flag
+0x1CC4), stride 0x2E3C, 150 records -- the layout the stock population counter
0x467610 walks with ECX = 0x50E568.

The walk used to start at the WORLD singleton [0x4CB51C] + 0x1D08 instead, a
different 0x171C8-byte heap object. Its answer therefore depended on three
bytes of the world rather than on the villagers. Measured live on a HutTest
copy of v1.35.53: with 149 of 150 slots occupied (one free) the walk read three
zero bytes in the world, the row stayed "Buy", and the purchased barrel
delivered ONE child (population 4 -> 5).

These tests EXECUTE the shipped bytes from the tracked manifest under Unicorn
with a controlled villager table and world, so they check what the routine
answers, not which instructions it contains. Each case is run with the world
filled with zeros AND with 0xFF, so a walk that reads anything but the villager
table cannot pass both.
"""

import json
import pathlib
import re
import unittest

try:
    from unicorn import UC_ARCH_X86, UC_MODE_32, Uc
    from unicorn.x86_const import UC_X86_REG_EAX, UC_X86_REG_ESP
except ImportError:  # pragma: no cover - exercised only without unicorn
    Uc = None

ROOT = pathlib.Path(__file__).resolve().parents[1]
BUILDER = ROOT / "scripts" / "build_vv4_origins_feature.py"
MANIFEST = ROOT / "data" / "vv4_origins_feature.json"

MANAGER = 0x50E568
OCCUPIED_OFFSET = 0x1D08
STRIDE = 0x2E3C
RECORDS = 150
WORLD_SINGLETON = 0x4CB51C
WORLD = 0x02000000
# Large enough that a walk which wrongly starts in the world never faults here:
# a fault would end the run before the answer is read, and the point is the
# ANSWER the old walk gave, which in the game it gave without faulting.
WORLD_SPAN = 0x200000
STACK = 0x00100000
RETURN_SENTINEL = 0x00090000
NO_ROOM = 0x2000000


def _constant(name):
    text = BUILDER.read_text(encoding="utf-8")
    match = re.search(r"^%s\s*=\s*(0x[0-9A-Fa-f]+)\b" % name, text, re.M)
    if match is None:
        raise AssertionError("%s is not a plain literal in the builder" % name)
    return int(match.group(1), 16)


def _routine():
    rows_file = _constant("PENDING_ROWS_FILE_OFFSET")
    rows_va = _constant("SHR_STOCK_VA") + (rows_file - 0xCC000)
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    for patch in manifest.get("patches", []):
        if int(patch["offset"], 0) == rows_file and patch.get("after"):
            return rows_va, bytes.fromhex(patch["after"])
    raise AssertionError(
        "no VV4 patch carries file offset %#x: the pending-rows routine is "
        "not in the shipped manifest" % rows_file
    )


def _run(occupied, world_fill, past_end_free=False):
    """Run the shipped routine; return the state word it hands back."""
    rows_va, code = _routine()
    uc = Uc(UC_ARCH_X86, UC_MODE_32)
    uc.mem_map(0x400000, 0x400000)  # image, villager manager, .shr page
    uc.mem_map(WORLD, WORLD_SPAN)
    uc.mem_map(STACK, 0x10000)
    uc.mem_map(RETURN_SENTINEL, 0x1000)
    uc.mem_write(rows_va, code)
    uc.mem_write(WORLD_SINGLETON, WORLD.to_bytes(4, "little"))
    uc.mem_write(WORLD, bytes([world_fill]) * WORLD_SPAN)
    # Nothing queued: no purchased island event, an empty shared countdown and
    # no armed barrel, so only the free-slot walk can set a barrel bit.
    uc.mem_write(WORLD + 0x170E0, b"\0\0\0\0")
    uc.mem_write(_constant("ISLAND_PURCHASED_VA"), b"\0")
    uc.mem_write(_constant("BARREL_ARMED_VA"), b"\0")
    # Slots -1 and RECORDS are outside the table. Marked occupied, a walk that
    # starts one record early or late cannot borrow a free slot from beyond
    # the array; marked free (past_end_free), a walk that runs one record past
    # the end finds a slot that does not exist.
    for k in range(-1, RECORDS + 1):
        if 0 <= k < RECORDS:
            flag = b"\1" if k in occupied else b"\0"
        else:
            flag = b"\0" if (past_end_free and k == RECORDS) else b"\1"
        uc.mem_write(MANAGER + OCCUPIED_OFFSET + k * STRIDE, flag)
    esp = STACK + 0x8000
    uc.mem_write(esp, RETURN_SENTINEL.to_bytes(4, "little"))
    uc.reg_write(UC_X86_REG_ESP, esp)
    uc.reg_write(UC_X86_REG_EAX, 0)
    uc.emu_start(rows_va, RETURN_SENTINEL, count=200000)
    return uc.reg_read(UC_X86_REG_EAX)


@unittest.skipIf(Uc is None, "requires unicorn")
class VV4BarrelRowWalksVillagerTableTests(unittest.TestCase):
    def _assert_answer(self, occupied, expect_no_room, why, past_end_free=False):
        for fill in (0x00, 0xFF):
            with self.subTest(world_fill=fill):
                state = _run(set(occupied), fill, past_end_free)
                self.assertEqual(
                    bool(state & NO_ROOM), expect_no_room,
                    "%s (world bytes %#04x): state %#x" % (why, fill, state),
                )

    def test_one_free_slot_is_no_room(self):
        self._assert_answer(
            range(RECORDS - 1), True,
            "149 of 150 villager slots are occupied, so a barrel's three "
            "children cannot fit, yet the row does not say 'no room'",
        )

    def test_full_table_is_no_room(self):
        self._assert_answer(
            range(RECORDS), True,
            "every villager slot is occupied, yet the row does not say 'no room'",
        )

    def test_two_free_slots_scattered_is_no_room(self):
        occupied = set(range(RECORDS)) - {0, 77}
        self._assert_answer(
            occupied, True,
            "only two villager slots are free, yet the row does not say "
            "'no room'",
        )

    def test_the_walk_stops_at_the_last_record(self):
        occupied = set(range(RECORDS)) - {10, 20}
        self._assert_answer(
            occupied, True,
            "only two villager slots are free, but the walk counted the "
            "free-looking byte one record past the table as a third",
            past_end_free=True,
        )

    def test_three_free_slots_at_the_end_is_room(self):
        self._assert_answer(
            range(RECORDS - 3), False,
            "the last three villager slots are free, yet the row says "
            "'no room' -- the walk does not reach the end of the table",
        )

    def test_three_free_slots_at_the_start_is_room(self):
        self._assert_answer(
            range(3, RECORDS), False,
            "the first three villager slots are free, yet the row says "
            "'no room' -- the walk does not start at the first record",
        )

    def test_small_village_is_room(self):
        self._assert_answer(
            range(6), False,
            "a six-villager village has 144 free slots, yet the row says "
            "'no room'",
        )


if __name__ == "__main__":
    unittest.main()
