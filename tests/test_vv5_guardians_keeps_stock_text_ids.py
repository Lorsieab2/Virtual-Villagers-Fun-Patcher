"""Guardians of Isola rewrites wording only; every text id stays byte-for-byte stock.

The game looks its strings up by id, and stock New Believers spells two ids
with trailing tabs -- 'eSayApprentice\\t' and 'eTTipInstruct1' followed by
five tabs -- identically in its sm.xml and in the exe's own key table. The
rewrite had dropped those tabs, so its two strings (the Devotion "Apprentice"
label and the first tutorial tip) no longer matched the key the exe asks
for. The rewrite may change what a string says, never which id it answers to.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "data" / "guardians_of_isola" / "base" / "Assets" / "sm.xml"
NEW = ROOT / "data" / "guardians_of_isola" / "new" / "Assets" / "sm.xml"
STOCK_EXE = ROOT / "research" / "stock-executables" / "Virtual Villagers - New Believers.exe"

ID = re.compile(rb'id="([^"]*)"')


class GuardiansKeepsStockTextIdsTests(unittest.TestCase):
    def test_every_id_is_the_stock_id_in_the_stock_order(self):
        self.assertEqual(ID.findall(NEW.read_bytes()), ID.findall(BASE.read_bytes()))

    def test_the_two_tabbed_ids_keep_their_tabs(self):
        ids = set(ID.findall(NEW.read_bytes()))
        self.assertIn(b"eSayApprentice\t", ids)
        self.assertIn(b"eTTipInstruct1\t\t\t\t\t", ids)
        self.assertNotIn(b"eSayApprentice", ids)
        self.assertNotIn(b"eTTipInstruct1", ids)

    @unittest.skipUnless(STOCK_EXE.is_file(), "stock VV5 executable not present")
    def test_the_exe_asks_for_the_tabbed_ids(self):
        exe = STOCK_EXE.read_bytes()
        self.assertIn(b"eSayApprentice\t\x00", exe)
        self.assertIn(b"eTTipInstruct1\t\t\t\t\t\x00", exe)


if __name__ == "__main__":
    unittest.main()
