"""The VV5 Faith and Heathens group (src/vv_game_mechanics_faith_vv5.py)."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import vv_game_mechanics as gm  # noqa: E402
import vv_game_mechanics_faith_vv5 as faith  # noqa: E402

STOCK = ROOT / "inputs" / "vv5-stock-copy" / "Virtual Villagers - New Believers.exe"


def village(installed):
    return gm.Village(Path("."), 5, 1, Path("5.ldw"), gm.blank_save(5, 1.8e9), installed, 1.8e9, general=True)


class Faith(unittest.TestCase):
    def test_group_and_wording(self) -> None:
        facts = gm.general(5)
        self.assertIn(faith.FAITH, {f.group for f in facts})
        page = " ".join(f.text for f in facts).lower()
        self.assertNotIn("belief", page)                    # the game's word is Faith (the owner)
        text = " ".join(f.text for f in faith.lines(village(frozenset())))
        for words in ("37.03%", "A sick believer loses 1 more 15.01% of the time", "30 to 59", "set to 55", "70.06%"):
            self.assertIn(words, text)

    def test_heathen_mommy_only_with_its_patch(self) -> None:
        without = " ".join(f.text for f in faith.lines(village(frozenset())))
        with_it = " ".join(f.text for f in faith.lines(village(frozenset({faith.HEATHEN_MOMMY}))))
        self.assertNotIn("Heathen Mommy's puzzle", without)
        self.assertIn("Heathen Mommy's puzzle", with_it)

    def test_constants_from_the_stock_exe(self) -> None:
        try:
            import pefile
        except ImportError:
            self.skipTest("pefile is missing")
        if not STOCK.exists():
            self.skipTest("the stock VV5 exe (inputs/vv5-stock-copy) is missing")
        img = pefile.PE(str(STOCK)).get_memory_mapped_image()
        at = lambda a, n: bytes(img[a - 0x400000:a - 0x400000 + n])  # noqa: E731
        self.assertEqual(at(0x468506, 2), b"\x6a\x1e")             # rand(30) ...
        self.assertEqual(at(0x468510, 3), b"\x83\xc0\x1e")         # ... + 30: the starting Faith
        self.assertEqual(at(0x467FC7, 5), b"\xbe\x37\x00\x00\x00")  # a convert below 5 becomes 55
        self.assertEqual(at(0x468056 + 3, 3), b"\x83\xf8\x1e")      # food under 10: rand(100) < 30
        self.assertEqual(at(0x4680B6, 3), b"\x83\xf8\x0f")          # sick: rand(100) < 15
        self.assertEqual(at(0x4681D6, 3), b"\x83\xf8\x46")          # a rise above 75 skipped: rand(100) < 70


if __name__ == "__main__":
    unittest.main()
