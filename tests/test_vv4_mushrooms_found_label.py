"""The Tree of Life's statistics log names +0x14 "Mushrooms Found".

The exporter printed it as "Collectibles Found", but only mushroom pickups
increment it (writer 0x414665 on the mushroom award path; collectible pickups
0x46/0x50/0x60/0x75 emulated, none touch it), and the game's own string for
the statistic is "Mushrooms Found" (sm.xml, eCrabsFound).  The owner: "fix
the label".  The shipped DLL is a prebuilt binary, so it is checked too.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "native" / "statistics_export" / "statistics_export.c"
DLL = ROOT / "assets" / "statistics" / "VVFP Statistics Export.dll"


class TreeOfLifeLabelTests(unittest.TestCase):
    def test_the_source_labels_vv4_mushrooms_found(self):
        text = SOURCE.read_text(encoding="utf-8")
        block = text[text.index("game_id == GAME_VV4"):]
        block = block[:block.index("0x850u")]
        block = re.sub(r"/\*.*?\*/", "", block, flags=re.S)   # code, not comments
        labels = re.findall(r'"([^"]+ Found)"', block)
        self.assertEqual(labels, ["Mushrooms Found"])

    def test_the_shipped_dll_says_mushrooms_not_collectibles(self):
        data = DLL.read_bytes()
        self.assertIn(b"Mushrooms Found\0", data)
        self.assertNotIn(b"Collectibles Found", data)


if __name__ == "__main__":
    unittest.main()
