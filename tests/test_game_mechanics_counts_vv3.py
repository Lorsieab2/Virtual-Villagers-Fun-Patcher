"""The Secret City's potion recipe book in the Village counts group (src/vv_game_mechanics_counts.py)."""
from __future__ import annotations

import gzip
import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import vv_game_mechanics_counts as counts  # noqa: E402

STOCK = ROOT / "inputs" / "vv3-stock-copy" / "Virtual Villagers - The Secret City.exe"
FIXTURE = ROOT / "tests" / "fixtures" / "rename_tribe" / "vv3-huttest-1.ldw.gz"


class RecipeBook(unittest.TestCase):
    def test_the_book_is_where_the_table_says(self) -> None:
        data = gzip.decompress(FIXTURE.read_bytes())
        self.assertEqual(struct.unpack_from("<i", data, counts.VV3_BOOK + 0x64)[0], counts.VV3_RECIPES)
        self.assertEqual(len(counts.VV3_COMBOS), counts.VV3_RECIPES)

    def test_the_combinations_are_the_exes(self) -> None:
        try:
            import capstone
            import pefile
        except ImportError:
            self.skipTest("capstone or pefile is missing")
        if not STOCK.exists():
            self.skipTest("the stock Secret City exe (inputs/vv3-stock-copy) is missing")
        img = pefile.PE(str(STOCK)).get_memory_mapped_image()
        md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
        start, end = 0x4305B1, 0x430A40                  # the book's constructor: 77 calls of 0x430480
        insns = list(md.disasm(img[start - 0x400000:end - 0x400000], start))
        rows, pushes = [], []
        for i in insns:
            if i.mnemonic == "push":
                pushes.append(int(i.op_str, 0))
            elif i.mnemonic == "call" and i.op_str == "0x430480":
                a, b, c, product = pushes[-1], pushes[-2], pushes[-3], pushes[-4]
                rows.append((a, b, c, product))
                pushes = []
        self.assertEqual(tuple(rows), counts.VV3_COMBOS)

    def test_every_potion_is_the_effect_switchs(self) -> None:
        """Each product's words are what its case of the effect switch 0x4268F0 says, and its kept time is the deadline
        the case writes (600 -> 10 real-life minutes, 300 -> 5, 0 -> no time limit, none -> nothing kept)."""
        try:
            import capstone
            import pefile
        except ImportError:
            self.skipTest("capstone or pefile is missing")
        if not STOCK.exists():
            self.skipTest("the stock Secret City exe (inputs/vv3-stock-copy) is missing")
        img = pefile.PE(str(STOCK)).get_memory_mapped_image()
        base = 0x400000
        md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)

        def u32(va: int) -> int:
            return struct.unpack_from("<I", img, va - base)[0]

        def cstr(va: int) -> str:
            i = va - base
            return img[i:img.find(b"\0", i)].decode("latin1")

        says = {}                                        # the game's (id, name, text, 0) string tables
        for off in range(0x90000, len(img) - 16, 4):
            sid, name, text, zero = struct.unpack_from("<IIII", img, off)
            if zero == 0 and 0x19D <= sid <= 0x1CC and base < name < base + len(img) and base < text < base + len(img):
                if cstr(name).startswith("eSay"):
                    says.setdefault(sid, cstr(text))
        stop = {0x426B47, 0x426B90}                      # the say tail and the plain exit
        self.assertEqual(len(counts.VV3_POTIONS), 41)
        for product in range(41):
            seen, todo, ids, kept = set(), [u32(0x426E6C + 4 * product)], set(), set()
            while todo:
                va = todo.pop()
                while 0x426900 <= va < 0x426E6C and va not in seen and va not in stop:
                    seen.add(va)
                    insn = next(md.disasm(img[va - base:va - base + 16], va))
                    m, ops = insn.mnemonic, insn.op_str
                    if m == "mov" and ops.startswith("edi, 0x"):
                        ids.add(int(ops[5:], 16))
                    if m == "mov" and ops.startswith("dword ptr [ebx], "):
                        kept.add(int(ops.split(", ")[1], 0))
                    if m == "ret":
                        break
                    if m.startswith("j"):
                        target = int(ops, 16)
                        if m == "jmp":
                            va = target
                            continue
                        todo.append(target)
                    va += insn.size
            say, does = counts.VV3_POTIONS[product]
            with self.subTest(product=product):
                texts = {says[i] for i in ids}
                if say.startswith("("):
                    self.assertEqual(texts, set())
                else:
                    self.assertIn(say, texts)
                for t in texts - {say}:
                    self.assertIn(t, does)               # a second answer (the food-short heal) is quoted
                words = {600: "10 real-life minutes", 300: "5 real-life minutes", 0: "no time limit"}
                for value, phrase in words.items():
                    self.assertEqual(phrase in does, value in kept, (phrase, kept))


if __name__ == "__main__":
    unittest.main()
