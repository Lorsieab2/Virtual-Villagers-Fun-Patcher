"""Fix Vanilla Bugs: every default first name can be chosen (all five games).

Each game names a new villager from its own male or female list (numbered from
0) with a roll of `rand(N) + 1`: the first name could never be given, and in
The Lost Children to New Believers the last one could not either (A New Home's
creator rolls up to its last name, 100).  With Fix Vanilla Bugs the roll is
`rand(size)` with no `+ 1`, in the creator and in the twin's "the sibling's
next name" path, so names 0 to size - 1 all come up.  The naming routine
walks the chosen number of commas, and every list ends with a comma, so the
last name is read whole.
"""
from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STOCK = ROOT / "research" / "stock-executables"
sys.path.insert(0, str(ROOT / "src"))

import vv_fun_patcher as vp  # noqa: E402

try:
    import capstone
except ImportError:  # pragma: no cover
    capstone = None

# The male and the female list, as the naming routine pushes them.
LISTS = {"vv1": (0x481D28, 0x481F50), "vv2": (0x48FD20, 0x48FFC0), "vv3": (0x49E180, 0x49E428),
         "vv4": (0x4AAAB8, 0x4AAEA8), "vv5": (0x4B85D8, 0x4B89C8)}
SIZE = {"vv1": 101, "vv2": 125, "vv3": 125, "vv4": 185, "vv5": 185}
# (VA of the roll's push, VA of the instruction that added 1), per naming path.
ROLLS = {
    "vv1": [(0x43C645, 0x43C657), (0x43C645, 0x43C674), (0x43CA06, 0x43CA10)],
    "vv2": [(0x44CCF1, 0x44CCFD), (0x44CCF1, 0x44CD1A), (0x44D03F, 0x44D049)],
    "vv3": [(0x45C677, 0x45C683)],
    "vv4": [(0x465DB5, 0x465DC1)],
    "vv5": [(0x46F695, 0x46F6A1)],
}
# The twin's "next name, unless past the last one" compare.
TWIN_CAP = {"vv1": 0x43C9FB, "vv2": 0x44D034}


@unittest.skipUnless(STOCK.is_dir() and capstone is not None, "stock executables or capstone not present")
class EveryDefaultNameCanBeChosen(unittest.TestCase):
    def rendered(self, game: str, fix: bool) -> bytes:
        build = next(b for b in vp.load_builds() if b.id == game)
        selection = [f"{game}_fix_vanilla_bugs"] if fix else []
        data, _ = vp.render_patched_bytes(STOCK / build.input_name, build, "collection_progression", selection)
        return bytes(data)

    def ins(self, data: bytes, va: int):
        md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
        return next(md.disasm(data[va - 0x400000: va - 0x400000 + 16], va))

    def test_every_list_ends_with_a_comma(self):
        import pefile
        for game, lists in LISTS.items():
            pe = pefile.PE(str(STOCK / next(b for b in vp.load_builds() if b.id == game).input_name))
            image = pe.get_memory_mapped_image()
            with self.subTest(game=game):
                for at in lists:
                    text = image[at - 0x400000: image.index(b"\0", at - 0x400000)]
                    names = [n for n in text.split(b",") if n]
                    self.assertEqual(len(names), SIZE[game])
                    self.assertTrue(text.endswith(b","), "the last name is ended by a comma")

    def test_the_roll_covers_the_whole_list(self):
        for game, rolls in ROLLS.items():
            stock, fixed = self.rendered(game, False), self.rendered(game, True)
            for push, plus_one in rolls:
                with self.subTest(game=game, push=hex(push)):
                    before, after = self.ins(stock, push), self.ins(fixed, push)
                    self.assertEqual(before.mnemonic, "push")
                    self.assertLess(int(before.op_str, 16), SIZE[game], "stock: never the whole list")
                    self.assertEqual(int(after.op_str, 16), SIZE[game], "fixed: rand(size)")
                    added = self.ins(fixed, plus_one)
                    self.assertIn(self.ins(stock, plus_one).mnemonic, ("inc", "add"))
                    self.assertTrue(added.mnemonic == "nop" or added.op_str.endswith(", 0"),
                                    f"fixed: no + 1 ({added.mnemonic} {added.op_str})")

    def test_a_twin_takes_the_next_name_up_to_the_last(self):
        for game, va in TWIN_CAP.items():
            fixed = self.ins(self.rendered(game, True), va)
            with self.subTest(game=game):
                self.assertEqual(fixed.mnemonic, "cmp")
                self.assertEqual(int(fixed.op_str.split(",")[1], 16), SIZE[game] - 1)


if __name__ == "__main__":
    unittest.main()
