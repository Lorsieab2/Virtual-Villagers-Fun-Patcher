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


if __name__ == "__main__":
    unittest.main()
