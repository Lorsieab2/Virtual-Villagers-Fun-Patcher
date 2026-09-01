"""VV1 and VV2 must not walk off the end of their 256-slot villager array.

Both games contain the same stock loop, which looks for a free slot and has no
bound whatsoever:

    mov  dl, [reg + STRIDE]   ; read the next slot's in-use flag
    add  reg, STRIDE
    inc  counter              ; counter = index of the slot just read
    test dl, dl               ; (or: cmp dl, bl)
    jne  <top>                ; keep going while occupied

When every slot is occupied it runs straight off the end. That is the reported
Lost Children startup crash: an access violation two slots past a 256-entry
array, reproduced on the completely UNPATCHED game, so it is a stock defect
rather than anything the patcher introduced.

There are five such loops -- two in VV1, three in VV2. Guarding only the one
that crashed first was not enough: a launch test then crashed at the sibling
site 0x44CEE0 with the identical counter value of 257.

The three VV2 loops are guarded. VV1's two are not: VV1 has no free cave
space left in .text, and VV1 has never been observed crashing here. Those two
sites are recorded in UNGUARDED_KNOWN below rather than left implicit; the
fix for them is an appended PE section, not more borrowed cave space.

The bound is 255, NOT 256, and that distinction is the whole point of this
file. After the increment the counter holds the index just READ, so continuing
means reading counter+1. Valid indices are 0..255 -- which is 256 slots -- so
the next read is safe only while counter <= 254. A bound of 256 would still
permit the read of slot 256 that faults.

VV3, VV4 and VV5 are deliberately untouched: every slot loop in those games
already ends with `cmp <counter>, 0x96 / jl`, bounding them at 150 (indices
0..149). A redundant guard there would be risk without benefit.
"""
from __future__ import annotations

import json
import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

BUILDS = json.loads((ROOT / "data" / "builds.json").read_text(encoding="utf-8"))

LAST_VALID_INDEX = 255
CAPACITY = 256
FILE_TO_VA = 0x400000

# game -> {loop top VA: (trampoline file offset, cave file offset, counter reg)}
GUARDED = {
    "vv2": {
        0x44C823: (0x4C82E, 0x73D30, "ecx"),
        0x44CEE0: (0x4CEEC, 0x73D48, "eax"),
        0x44D230: (0x4D23B, 0x73D60, "edi"),
    },
}

# Found by the same scan and structurally identical, but NOT guarded: VV1 has
# no free cave space left in .text. vv1_write_village_statistics and
# vv1_magic_fruit_alters_mortality own the region past 0x56730, and the one
# remaining gap collides in the immediate_fixed birth-control composition.
# VV1 has also never been observed crashing here. The fix is an appended PE
# section rather than borrowing more stock cave space. Recorded so it cannot
# be quietly forgotten.
UNGUARDED_KNOWN = {
    "vv1": {
        0x43C374: (0x3C37F, "ecx"),
        0x43C860: (0x3C86B, "ebp"),
    },
}
CMP_MODRM = {"eax": 0xF8, "ecx": 0xF9, "ebp": 0xFD, "edi": 0xFF}
BOUNDED_GAMES = ("vv3", "vv4", "vv5")


def patches(game_id):
    game = next(g for g in BUILDS["games"] if g["id"] == game_id)
    return {int(p["offset"], 16): p for p in game["safety_patches"]}


class SlotScanGuardTests(unittest.TestCase):
    def test_every_known_scan_site_is_guarded(self) -> None:
        for game_id, sites in GUARDED.items():
            table = patches(game_id)
            for loop_top, (tramp, cave, _reg) in sites.items():
                with self.subTest(game=game_id, loop=hex(loop_top)):
                    self.assertIn(tramp, table, "scan tail is not redirected")
                    self.assertIn(cave, table, "no guard cave for this scan")

    def test_the_trampoline_jumps_to_its_own_cave(self) -> None:
        """A jump to the wrong cave would bound the wrong loop."""
        for game_id, sites in GUARDED.items():
            table = patches(game_id)
            for loop_top, (tramp, cave, _reg) in sites.items():
                with self.subTest(game=game_id, loop=hex(loop_top)):
                    after = bytes.fromhex(table[tramp]["after"])
                    self.assertEqual(len(after), 5, "must stay exactly 5 bytes")
                    self.assertEqual(after[0], 0xE9, "must be a JMP rel32")
                    rel = struct.unpack("<i", after[1:])[0]
                    target = (tramp + FILE_TO_VA) + 5 + rel
                    self.assertEqual(target, cave + FILE_TO_VA)

    def test_the_replaced_tail_is_exactly_five_bytes(self) -> None:
        """The site only works because inc+compare+jne is JMP rel32 sized."""
        for game_id, sites in GUARDED.items():
            table = patches(game_id)
            for loop_top, (tramp, _cave, _reg) in sites.items():
                with self.subTest(game=game_id, loop=hex(loop_top)):
                    before = bytes.fromhex(table[tramp]["before"])
                    self.assertEqual(len(before), 5)
                    self.assertEqual(before[3], 0x75, "expected a JNE tail")

    def test_the_bound_is_255_not_256(self) -> None:
        """The off-by-one that would leave the crash in place.

        0..255 is already 256 slots. Comparing against 256 still lets the
        loop read slot 256, which is the byte that faults.
        """
        for game_id, sites in GUARDED.items():
            table = patches(game_id)
            for loop_top, (_tramp, cave, reg) in sites.items():
                with self.subTest(game=game_id, loop=hex(loop_top)):
                    body = bytes.fromhex(table[cave]["after"])
                    self.assertEqual(body[5], 0x81, "cmp must use the imm32 form")
                    self.assertEqual(
                        body[6], CMP_MODRM[reg],
                        "the bound must test THIS loop's counter register",
                    )
                    bound = struct.unpack("<I", body[7:11])[0]
                    self.assertEqual(bound, LAST_VALID_INDEX)
                    self.assertNotEqual(bound, CAPACITY)

    def test_the_comparison_is_not_the_sign_extended_short_form(self) -> None:
        """`83 F9 FF` would compare against -1, not 255."""
        for game_id, sites in GUARDED.items():
            table = patches(game_id)
            for loop_top, (_tramp, cave, _reg) in sites.items():
                with self.subTest(game=game_id, loop=hex(loop_top)):
                    body = bytes.fromhex(table[cave]["after"])
                    self.assertNotEqual(body[5], 0x83)

    def test_the_bound_actually_branches(self) -> None:
        """A cmp nobody acts on is not a guard.

        Replacing the conditional jump with an unconditional fallthrough
        leaves the comparison sitting in place, looking correct, while the
        loop runs off the end exactly as before.
        """
        for game_id, sites in GUARDED.items():
            table = patches(game_id)
            for loop_top, (_tramp, cave, _reg) in sites.items():
                with self.subTest(game=game_id, loop=hex(loop_top)):
                    body = bytes.fromhex(table[cave]["after"])
                    self.assertEqual(
                        body[0x0B], 0x73, "the bound must be followed by JAE"
                    )
                    taken = 0x0B + 2 + body[0x0C]
                    self.assertEqual(
                        taken, 0x12,
                        "JAE must leave the loop, not fall back into it",
                    )
                    # And the free-slot exit must branch to the same place.
                    self.assertEqual(body[0x03], 0x74, "expected JE for the free slot")
                    self.assertEqual(0x03 + 2 + body[0x04], 0x12)

    def test_the_cave_replays_the_original_increment_and_compare(self) -> None:
        """The guard adds a bound; it must not change what the loop does."""
        for game_id, sites in GUARDED.items():
            table = patches(game_id)
            for loop_top, (tramp, cave, _reg) in sites.items():
                with self.subTest(game=game_id, loop=hex(loop_top)):
                    original = bytes.fromhex(table[tramp]["before"])
                    body = bytes.fromhex(table[cave]["after"])
                    self.assertEqual(body[0:3], original[0:3])

    def test_the_cave_returns_to_the_loop_and_to_the_fallthrough(self) -> None:
        for game_id, sites in GUARDED.items():
            table = patches(game_id)
            for loop_top, (tramp, cave, _reg) in sites.items():
                with self.subTest(game=game_id, loop=hex(loop_top)):
                    body = bytes.fromhex(table[cave]["after"])
                    cave_va = cave + FILE_TO_VA
                    self.assertEqual(body[0x0D], 0xE9)
                    back = (cave_va + 0x0D) + 5 + struct.unpack("<i", body[0x0E:0x12])[0]
                    self.assertEqual(back, loop_top, "must resume the stock loop")
                    self.assertEqual(body[0x12], 0xE9)
                    out = (cave_va + 0x12) + 5 + struct.unpack("<i", body[0x13:0x17])[0]
                    self.assertEqual(
                        out, tramp + FILE_TO_VA + 5,
                        "must exit to the instruction after the replaced tail",
                    )

    def test_the_cave_overwrites_only_free_space(self) -> None:
        """A cave carved out of live code would corrupt the game."""
        for game_id, sites in GUARDED.items():
            table = patches(game_id)
            for loop_top, (_tramp, cave, _reg) in sites.items():
                with self.subTest(game=game_id, loop=hex(loop_top)):
                    before = bytes.fromhex(table[cave]["before"])
                    self.assertEqual(set(before), {0}, "cave was not empty")

    def test_guard_regions_do_not_overlap_each_other(self) -> None:
        for game_id in GUARDED:
            spans = []
            for p in next(g for g in BUILDS["games"] if g["id"] == game_id)["safety_patches"]:
                start = int(p["offset"], 16)
                spans.append((start, start + len(p["after"]) // 2))
            spans.sort()
            for (a_start, a_end), (b_start, _b_end) in zip(spans, spans[1:]):
                with self.subTest(game=game_id, at=hex(a_start)):
                    self.assertLessEqual(a_end, b_start, "safety patches overlap")

    def test_the_already_bounded_games_are_left_alone(self) -> None:
        """VV3-VV5 bound their loops at 150 in stock code; do not touch them."""
        for game_id in BOUNDED_GAMES:
            game = next(g for g in BUILDS["games"] if g["id"] == game_id)
            with self.subTest(game=game_id):
                self.assertEqual(game["villager_slots"], 150)
                for p in game["safety_patches"]:
                    self.assertNotIn("unbounded slot scan", p["purpose"])

    def test_the_guarded_games_really_do_declare_256_slots(self) -> None:
        """The bound is only correct for a 256-entry array."""
        for game_id in GUARDED:
            game = next(g for g in BUILDS["games"] if g["id"] == game_id)
            with self.subTest(game=game_id):
                self.assertEqual(game["villager_slots"], CAPACITY)
                self.assertEqual(game["absolute_maximum"], CAPACITY)


if __name__ == "__main__":
    unittest.main()
