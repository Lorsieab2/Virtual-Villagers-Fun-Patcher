"""New Believers' Fix Vanilla Bugs: The Last Heathen's hovel cover sits on the map tiles, in the owner's art.

Once project 25 (CConvertLastHeathenPuzzle, The Last Heathen) is done, 0x4370E0 draws image 0x1B (the image table
entry at 0x4CF768: id 0x1B, name "hovel_cover.png" at 0x49D5E0) through 0x44F320 at a top-left (x, y): at 100% the
draw queue blits it unscaled (0x408B70 -> 0x407F10 -> 0x407E70), so (x, y) is the picture's top-left corner.  The
stock (0x6A9, 0x5B3) = (1705, 1459) leaves it 3 pixels right of and 6 pixels above where it meets the island's
LargeMap tiles (512 x 512 each, at (512 X, 512 Y)); the fix draws it at (0x6A6, 0x5B9) = (1702, 1465).

The owner redrew the picture (634 x 286 RGBA, assets/vv5_fix_vanilla_bugs/vvfp_hovel.png).  The row ships it as
Images/vvfp_hovel.png and renames the table's name in place ("hovel_cover.png" -> "vvfp_hovel.png", NUL padded), as
The Secret City's hospital sheet does; the game's own hovel_cover.png is never touched.  Replacing the art later is
the one file plus its size and SHA-256 in the row.

Nothing else draws image 0x1B: its only load is at 0x4370C8 (0x44FC50 into the object's +0x10), read only by the
draw at 0x43710E; the name string has one reference, the table entry.
"""
from __future__ import annotations

import hashlib
import json
import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

STOCK = ROOT / "research" / "stock-executables" / "Virtual Villagers - New Believers.exe"
ART = ROOT / "assets" / "vv5_fix_vanilla_bugs" / "vvfp_hovel.png"
BASE = 0x400000
FEATURE = "vv5_fix_vanilla_bugs"

NAME = (0x9D5E0, b"hovel_cover.png\0", b"vvfp_hovel.png\0\0")
Y = (0x370F5, bytes.fromhex("B9B3050000"), bytes.fromhex("B9B9050000"))
X = (0x370FF, bytes.fromhex("B8A9060000"), bytes.fromhex("B8A6060000"))
HOVEL_FIXES = (NAME, Y, X)


def hovel_fixes() -> tuple:
    """The (file offset, stock bytes, fixed bytes) this fix adds to vv5_fix_vanilla_bugs."""
    return HOVEL_FIXES


def _row() -> dict:
    data = json.loads((ROOT / "data" / "builds.json").read_text(encoding="utf-8"))
    return next(p for p in data["fun_patches"] if p["id"] == FEATURE)


class Manifest(unittest.TestCase):
    def test_the_edits_and_the_shipped_art(self) -> None:
        row = _row()
        pinned = {(int(p["offset"], 16), bytes.fromhex(p["before"]), bytes.fromhex(p["after"])) for p in row["patches"]}
        self.assertTrue(set(HOVEL_FIXES) <= pinned)
        art = next(c for c in row["companion_files"] if c["destination"] == "Images/vvfp_hovel.png")
        self.assertEqual(art["source"], "assets/vv5_fix_vanilla_bugs/vvfp_hovel.png")
        data = ART.read_bytes()
        self.assertEqual(art["size"], len(data))
        self.assertEqual(art["sha256"], hashlib.sha256(data).hexdigest().upper())
        self.assertEqual(struct.unpack(">II", data[16:24]), (634, 286))      # the PNG header's width and height
        self.assertEqual(data[25], 6)                                         # RGBA
        self.assertEqual(NAME[2].rstrip(b"\0").decode(), "vvfp_hovel.png")
        from patcher_files import stays_in_place
        self.assertTrue(stays_in_place("Images/vvfp_hovel.png"))


@unittest.skipUnless(STOCK.is_file(), "stock executables are not available")
class StockCode(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        import pefile
        cls.raw = STOCK.read_bytes()
        cls.img = pefile.PE(data=cls.raw, fast_load=True).get_memory_mapped_image()

    def test_stock_bytes(self) -> None:
        for offset, before, after in HOVEL_FIXES:
            self.assertEqual(self.raw[offset:offset + len(before)], before)
            self.assertEqual(len(before), len(after))

    def test_the_draw(self) -> None:
        at = lambda va, n: self.img[va - BASE:va - BASE + n]  # noqa: E731
        self.assertEqual(at(0x4370E3, 2), bytes.fromhex("6A19"))                     # project 25 done
        self.assertEqual(at(0x43710E, 5), b"\xE8" + struct.pack("<i", 0x44F320 - 0x437113))
        self.assertEqual(at(0x4370C8, 2), bytes.fromhex("6A1B"))                     # image 0x1B's only load
        self.assertEqual(struct.unpack_from("<II", self.img, 0x4CF768 - BASE), (0x1B, 0x49D5E0))

    def test_the_name_has_one_reader(self) -> None:
        pat = struct.pack("<I", 0x49D5E0)
        refs, i = [], self.img.find(pat)
        while i >= 0:
            refs.append(BASE + i)
            i = self.img.find(pat, i + 1)
        self.assertEqual(refs, [0x4CF76C])
        loads, i = [], self.raw.find(b"\x6A\x1B")
        while i >= 0:                       # push 0x1B followed (within 4 bytes) by the image getter 0x44FC50
            if self.raw[i + 2:i + 4] == b"\x8B\xC8" and self.raw[i + 4] == 0xE8:
                target = BASE + i + 9 + struct.unpack_from("<i", self.raw, i + 5)[0]
                if target == 0x44FC50:
                    loads.append(BASE + i)
            i = self.raw.find(b"\x6A\x1B", i + 1)
        self.assertEqual(loads, [0x4370C8])


if __name__ == "__main__":
    unittest.main()
