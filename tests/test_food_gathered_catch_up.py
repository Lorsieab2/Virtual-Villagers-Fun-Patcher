"""Food Gathered counts the load-time catch-up the same way in all five games.

Every game changes its food stock through ONE routine, and that routine is
where Food Gathered is counted, so whatever food the catch-up adds is counted
exactly like food gathered in play:

* A New Home 0x41D140, The Lost Children 0x4262B0, The Secret City 0x4263F0:
  the stock routine itself adds to the game's own Food Gathered counter.
* The Tree of Life 0x41D920 and New Believers 0x41EB40: the stock routines keep
  no counter; the patch detours their `add [edi], esi` (0x41D987, 0x41EBA7)
  and counts every positive award.

No instruction anywhere else in The Tree of Life or New Believers writes the
food stock (0x4D6DD0, 0x51D34C) -- only reads and compares -- so no path,
catch-up included, can add food around the hook.

Live, 2026-10-09 (StatTest copies of the owner's V8Test saves, ~22 hours old):
The Tree of Life counted 34,170 food during the load catch-up (food 270,476 in
the save -> 285,554, tech +55k). New Believers' catch-up added nothing to count:
its food (628,379) and Tech Points Earned (640,944) were unchanged by the load
while Babies Made went 78 -> 79 -- its catch-up advances pregnancies, not work.
Food gathered in play was counted in both (VV5: 70 in a minute)."""
from __future__ import annotations

import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
STOCK = ROOT / "research" / "stock-executables"
NAMES = {1: "A New Home", 2: "The Lost Children", 3: "The Secret City", 4: "The Tree of Life",
         5: "New Believers"}


def stock(game: int) -> bytes:
    path = STOCK / f"Virtual Villagers - {NAMES[game]}.exe"
    if not path.is_file():
        raise unittest.SkipTest(f"stock executable absent: {path.name}")
    return path.read_bytes()


def at(data: bytes, va: int, size: int) -> bytes:
    pe = struct.unpack_from("<I", data, 0x3C)[0]
    count = struct.unpack_from("<H", data, pe + 6)[0]
    optional = struct.unpack_from("<H", data, pe + 20)[0]
    for i in range(count):
        o = pe + 24 + optional + i * 40
        rva, raw_size, raw = struct.unpack_from("<III", data, o + 12)
        if 0x400000 + rva <= va < 0x400000 + rva + raw_size:
            start = raw + va - 0x400000 - rva
            return data[start:start + size]
    raise AssertionError(hex(va))


class CentralFoodRoutineTests(unittest.TestCase):
    def test_the_first_three_games_count_in_the_routine_itself(self):
        # add dword ptr [ecx + <Food Gathered>], eax inside the food routine
        for game, va, code in ((1, 0x41D14A, "0181289e0000"), (2, 0x4262BA, "018104e50200"),
                               (3, 0x426401, "0105ac245800")):
            with self.subTest(game=game):
                self.assertEqual(at(stock(game), va, 6).hex(), code)

    def test_nothing_else_writes_the_food_stock_in_the_tree_of_life_or_new_believers(self):
        try:
            import capstone
        except ImportError:
            self.skipTest("capstone not installed")
        for game, food in ((4, 0x4D6DD0), (5, 0x51D34C)):
            with self.subTest(game=game):
                data = stock(game)
                md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
                md.skipdata = True
                pe = struct.unpack_from("<I", data, 0x3C)[0]
                count = struct.unpack_from("<H", data, pe + 6)[0]
                optional = struct.unpack_from("<H", data, pe + 20)[0]
                writers = []
                seen = 0
                needle = "[0x%x]" % food
                for i in range(count):
                    o = pe + 24 + optional + i * 40
                    if not struct.unpack_from("<I", data, o + 36)[0] & 0x20000000:
                        continue
                    rva, raw_size, raw = struct.unpack_from("<III", data, o + 12)
                    for ins in md.disasm(data[raw:raw + raw_size], 0x400000 + rva):
                        text = ins.op_str.lower()
                        seen += needle in text
                        first = text.split(",")[0]
                        if needle in first and ins.mnemonic not in ("cmp", "test", "push"):
                            writers.append((hex(ins.address), ins.mnemonic, text))
                self.assertGreater(seen, 20, "the scan sees the stock's own reads of the stock")
                self.assertEqual(writers, [],"the food stock is written only through the food routine")

    def test_the_patch_counts_at_the_routines_add(self):
        from vv_fun_patcher import load_builds, render_patched_bytes
        for game, hook in ((4, 0x41D987), (5, 0x41EBA7)):
            with self.subTest(game=game):
                self.assertEqual(at(stock(game), hook, 2).hex(), "0137")    # add [edi], esi
                exe = STOCK / f"Virtual Villagers - {NAMES[game]}.exe"
                build = next(b for b in load_builds() if b.id == f"vv{game}")
                data, _ = render_patched_bytes(exe, build, "collection_progression",
                                               [f"vv{game}_write_village_statistics"])
                self.assertEqual(at(bytes(data), hook, 1), b"\xE9", "the add is detoured to the counter")


if __name__ == "__main__":
    unittest.main()
