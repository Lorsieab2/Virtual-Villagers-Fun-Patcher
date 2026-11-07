"""Fix Vanilla Bugs (The Tree of Life, New Believers): a Nursery School lesson's tie on the top skill is broken at random.

The lesson (VV5 0x425F80-0x4260AD, VV4 0x4203F3-0x420521) gives the whole lesson to a child's top skill, found by
the shared routine VV5 0x4755C0 / VV4 0x46AC20.  That routine takes a skill whenever it is above the whole number of
the one taken so far, so among skills with the same whole number the LAST one with any fraction wins: Devotion
(VV5) or Building (VV4).  A child whose skills are all below 1 -- every newborn, and every Heathen child, who never
ages -- has its lessons go to Devotion / Building 85% to 99% of the time (tests/test_game_mechanics_nursery.py).

The fix touches only the Nursery lesson: its one call of the routine (VV5 0x42602F, VV4 0x4204A8; the routine has
nine other callers, left as they are) goes to the tie-breaker instead: 14 pieces in the int3 padding between
functions (VV5 0x4264C3 to 0x4295FB, VV4 0x420313 to 0x42397B; an int3 left on each side, never a branch target, no
other row uses them), chained by jumps.  (.text's zero tail is no place for it: in The Tree of Life other rows claim
every byte of it, and in New Believers the free part is kept zero where the Origins dead code was removed,
tests/test_vv5_origins_dead_code_removed.py.)  The tie-breaker calls
the stock routine first: -1 (no skill above 0) is returned as before, so the lesson's own rand(6) / rand(5) still
draws.  Otherwise the stock pick's whole number is the highest whole number among the skills (a later skill is
taken only when it is above the whole number of the one taken so far), and the tie-breaker returns one of the
skills with that whole number (the game's own float-to-int, 0x47C9B0 / 0x471630), each equally likely, by
reservoir sampling with the game's RNG (the k-th tied skill replaces the pick when rand(k) is 0; 0x403660 /
0x4036D0).  The 50 test, the 50-in-100 roll, the spread, the
amounts and every other caller are the base game's.
"""
from __future__ import annotations

import functools
import random
import sys
import unittest
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

STOCK_DIR = ROOT / "research" / "stock-executables"
NAMES = {"vv4": "The Tree of Life", "vv5": "New Believers"}
BASE = 0x400000

# (file offset, stock bytes, fixed bytes); in both exes a .text file offset equals its RVA.
FIXES = {
    "vv5": (
        (0x2602F, bytes.fromhex("E88CF50400"), bytes.fromhex("E88F040000")),
        (0x264C3, b"\xcc" * 10, bytes.fromhex("6089CE6A00E966020000")),
        (0x26733, b"\xcc" * 10, bytes.fromhex("E888EE0400E936050000")),
        (0x26C73, b"\xcc" * 12, bytes.fromhex("8944241C83F8FFE964030000")),
        (0x26FE3, b"\xcc" * 11, bytes.fromhex("0F840F260000E9B5040000")),
        (0x274A3, b"\xcc" * 8, bytes.fromhex("D90486E937040000")),
        (0x278E2, b"\xcc" * 12, bytes.fromhex("E8C950050089C3E913060000")),
        (0x27F01, b"\xcc" * 12, bytes.fromhex("31ED31FFD904BEE905130000")),
        (0x29212, b"\xcc" * 12, bytes.fromhex("E89937050039D8E934010000")),
        (0x29352, b"\xcc" * 13, bytes.fromhex("0F856E0200004555E944010000")),
        (0x294A3, b"\xcc" * 11, bytes.fromhex("E8B8A1FDFF59EB38909090")),
        (0x294E3, b"\xcc" * 7, bytes.fromhex("85C0E9A8000000")),
        (0x29592, b"\xcc" * 11, bytes.fromhex("753290909090EB28909090")),
        (0x295C2, b"\xcc" * 13, bytes.fromhex("897C241C4783FF06EB26909090")),
        (0x295F2, b"\xcc" * 10, bytes.fromhex("0F8C0DE9FFFF61C20400")),
    ),
    "vv4": (
        (0x204A8, bytes.fromhex("E873A70400"), bytes.fromhex("E866FEFFFF")),
        (0x20313, b"\xcc" * 10, bytes.fromhex("6089CE6A00E956050000")),
        (0x20873, b"\xcc" * 10, bytes.fromhex("E8A8A30400E966020000")),
        (0x20AE3, b"\xcc" * 12, bytes.fromhex("8944241C83F8FFE934050000")),
        (0x21023, b"\xcc" * 11, bytes.fromhex("0F844F290000E965030000")),
        (0x21393, b"\xcc" * 8, bytes.fromhex("D90486E9B8040000")),
        (0x21853, b"\xcc" * 12, bytes.fromhex("E8D8FD040089C3E933040000")),
        (0x21C92, b"\xcc" * 12, bytes.fromhex("31ED31FFD904BEE913060000")),
        (0x222B1, b"\xcc" * 12, bytes.fromhex("E87AF3040039D8E905130000")),
        (0x235C2, b"\xcc" * 13, bytes.fromhex("0F85CF0200004555E933010000")),
        (0x23702, b"\xcc" * 13, bytes.fromhex("E8C9FFFDFF5985C0E944010000")),
        (0x23853, b"\xcc" * 11, bytes.fromhex("754290909090EB38909090")),
        (0x23893, b"\xcc" * 10, bytes.fromhex("897C241C47E9A5000000")),
        (0x23942, b"\xcc" * 8, bytes.fromhex("83FF05EB2B909090")),
        (0x23972, b"\xcc" * 10, bytes.fromhex("0F8C1EE3FFFF61C20400")),
    ),
}
# Every caller of the top-skill routine in the stock exe; only the Nursery lesson's is redirected.
CALLERS = {
    "vv5": (0x42602F, 0x442E8B, 0x44B951, 0x44B961, 0x464CEF, 0x467D45, 0x467D54, 0x46E0E9, 0x46E0F8, 0x46F303),
    "vv4": (0x4204A8, 0x4402EA, 0x448341, 0x448351, 0x45D4EF, 0x4609B5, 0x4609C4, 0x465069, 0x465078, 0x465A43),
}
TOP = {"vv5": 0x4755C0, "vv4": 0x46AC20}


def nursery_tie_fixes(game: str) -> tuple:
    """The (file offset, stock bytes, fixed bytes) this fix adds to <game>_fix_vanilla_bugs."""
    return FIXES.get(game, ())


def _have(game: str) -> bool:
    return (STOCK_DIR / f"Virtual Villagers - {NAMES[game]}.exe").is_file()


@functools.lru_cache(maxsize=None)
def _stock(game: str) -> bytes:
    return (STOCK_DIR / f"Virtual Villagers - {NAMES[game]}.exe").read_bytes()


class Manifest(unittest.TestCase):
    def test_the_row_carries_the_fix(self) -> None:
        from vv_fun_patcher import load_fun_patches
        for game in FIXES:
            row = next(p for p in load_fun_patches() if p.id == f"{game}_fix_vanilla_bugs").raw
            pinned = [(int(p["offset"], 16), bytes.fromhex(p["before"]), bytes.fromhex(p["after"]))
                      for p in row["patches"]]
            self.assertEqual(pinned[-len(FIXES[game]):], list(FIXES[game]))
            self.assertIn("a tie is broken at random", row["description"])


class StockBytes(unittest.TestCase):
    def test_stock_bytes_and_the_only_redirected_caller(self) -> None:
        import pefile
        for game, fixes in FIXES.items():
            if not _have(game):
                self.skipTest("stock executables are not available")
            raw = _stock(game)
            pe = pefile.PE(data=raw, fast_load=True)
            text = pe.sections[0]
            for offset, before, after in fixes:
                self.assertEqual(raw[offset:offset + len(before)], before)
                self.assertEqual(len(before), len(after))
                self.assertEqual(pe.get_offset_from_rva(offset), offset)
            for offset, before, _ in fixes[1:]:   # pieces inside the padding between functions, an int3 each side
                self.assertEqual(before, b"\xcc" * len(before))
                self.assertEqual((raw[offset - 1], raw[offset + len(before)]), (0xCC, 0xCC))
                self.assertLess(offset, text.PointerToRawData + text.Misc_VirtualSize)
            image = pe.get_memory_mapped_image()
            found = []
            for i in range(text.VirtualAddress, text.VirtualAddress + text.Misc_VirtualSize - 5):
                if image[i] == 0xE8 and (BASE + i + 5 + int.from_bytes(image[i + 1:i + 5], "little", signed=True)
                                         ) & 0xFFFFFFFF == TOP[game]:
                    found.append(BASE + i)
            self.assertEqual(tuple(found), CALLERS[game])


class Emulated(unittest.TestCase):
    """The game's own lesson, stock and with the fix, in unicorn (tests/nursery_emulation.py)."""

    def setUp(self) -> None:
        import nursery_emulation as ne
        self.ne = ne

    def _games(self):
        return ((self.ne.VV5, "vv5"), (self.ne.VV4, "vv4"))

    def test_a_tie_is_drawn_each_equally_likely(self) -> None:
        for game, gid in self._games():
            if not _have(gid):
                self.skipTest("stock executables are not available")
            n = game.skills
            picked = Counter()
            e = self.ne.Nursery(game, patched=FIXES[gid])
            e.villager(0, age=600, skills=[100.0] * n, job=8)
            rng = random.Random(7)
            for _ in range(600):
                e.villager(1, age=0, skills=[12.5] * n)                 # all tied at 12
                draws = []
                k = 0
                for _skill in range(n):                                 # reservoir: rand(1), rand(2), ... rand(n)
                    k += 1
                    draws.append(rng.randrange(k))
                e.lesson([0, 0] + draws)
                s = e.skills(1)
                picked[max(range(n), key=lambda i: s[i])] += 1
            self.assertEqual(set(picked), set(range(n)))
            for count in picked.values():
                self.assertGreater(count, 600 / n * 0.7)
                self.assertLess(count, 600 / n * 1.3)

    def test_the_highest_whole_number_still_wins(self) -> None:
        for game, gid in self._games():
            n = game.skills
            e = self.ne.Nursery(game, patched=FIXES[gid])
            e.villager(0, age=600, skills=[100.0] * n, job=8)
            e.villager(1, age=0, skills=[3.9] + [4.0] + [3.99] * (n - 2))   # only Parenting has a whole 4
            asked = e.lesson([0, 0, 0])
            self.assertEqual(asked, [1, 100, 1])                             # one tied skill: rand(1)
            self.assertGreater(e.skills(1)[1], 4.0)
            e.villager(2, age=0, skills=[0.0] * n)                           # nothing above 0: the lesson's draw
            e.villager(1, age=0, skills=[60.0] * n)                          # top at 50 or more: nothing
            asked = e.lesson([0, 0] + [0] * n + [n - 1])
            self.assertEqual(asked, [1, 100] + list(range(1, n + 1)) + [n])
            self.assertEqual(e.skills(1), [60.0] * n)
            self.assertGreater(e.skills(2)[n - 1], 0.0)

    def test_children_from_zero_spread_over_every_skill(self) -> None:
        """The page's numbers: 400 children from 0 with a teacher at 100 in every skill, 30 age units each, every
        roll from random.Random(1) as the game asks for it.  Stock gives the last skill 85-99% of them
        (tests/test_game_mechanics_nursery.py); fixed, each skill about 1 in n."""
        import vv_game_mechanics_nursery as nursery
        expect = {"vv5": (85, 62, 57), "vv4": (90, 80, 87)}
        for game, gid in self._games():
            n = game.skills
            last = []
            for speed in (3, 6, 10):
                rng = random.Random(1)
                e = self.ne.Nursery(game, speed=speed, patched=FIXES[gid])
                trained = Counter()
                for _ in range(400):
                    e.villager(0, age=600, skills=[100.0] * n, job=8)
                    e.villager(1, age=0, skills=[0.0] * n)
                    for _tick in range(30):
                        e.rolls_from(rng)
                    s = e.skills(1)
                    trained[max(range(n), key=lambda i: (s[i], i))] += 1
                self.assertEqual(set(trained), set(range(n)), (gid, speed))
                self.assertTrue(all(400 / n * 0.6 < c < 400 / n * 1.6 for c in trained.values()), (gid, trained))
                last.append(trained[n - 1])
            self.assertEqual(tuple(last), expect[gid])
            a, b, c = expect[gid]
            text = " ".join(f.text for f in nursery.lines(_Never(), 5 if gid == "vv5" else 4))
            self.assertIn(f"{a}, {b} and {c} of them on Fast, Normal and Slow", text)


class _Never:
    def has(self, _feature):
        return None

if __name__ == "__main__":
    unittest.main()
