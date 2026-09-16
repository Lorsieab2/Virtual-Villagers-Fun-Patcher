from __future__ import annotations

import re
import struct
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

SOURCE = ROOT / "native" / "parentage_export" / "parentage_export.c"
DLL = ROOT / "assets" / "parentage" / "VVFP Parentage Export.dll"
STOCK = ROOT / "research" / "stock-executables"

# Each game's conception routine takes the father's head and body as stack
# arguments and stores them on the MOTHER. The caller pushes body first, then
# head; x86 pushes descend, so head is the LOWER argument slot. The stored pair
# is therefore inverted relative to address order -- body four bytes BEFORE
# head -- in every game including VV2, which has always had these set.
#
# Each row is checked against the stock executable rather than restated, so a
# transcription slip cannot pass.
GAMES = {
    "vv3": {
        "exe": "Virtual Villagers - The Secret City.exe",
        # caller: mov edx,[esi+0DF4h] (body) / mov ecx,[esi+0DF0h] (head)
        "caller_body": (0x458319, "8B96F40D0000"),
        "caller_head": (0x458320, "8B8EF00D0000"),
        # storer: mov [esi+0E64h],eax (body) / mov [esi+0E68h],ecx (head)
        "store_body": (0x455B4F, "8986640E0000"),
        "store_head": (0x455B67, "898E680E0000"),
        "head_copy": 0xE68,
        "body_copy": 0xE64,
    },
    "vv4": {
        "exe": "Virtual Villagers - The Tree of Life.exe",
        "caller_body": (0x460A09, "8B96BC1B0000"),
        "caller_head": (0x460A10, "8B8EB81B0000"),
        "store_body": (0x45E850, "89862C1C0000"),
        "store_head": (0x45E868, "898E301C0000"),
        "head_copy": 0x1C30,
        "body_copy": 0x1C2C,
    },
    "vv5": {
        "exe": "Virtual Villagers - New Believers.exe",
        "caller_body": (0x467D99, "8B96BC1B0000"),
        "caller_head": (0x467DA0, "8B8EB81B0000"),
        "store_body": (0x465EA0, "89862C1C0000"),
        "store_head": (0x465EB8, "898E301C0000"),
        "head_copy": 0x1C30,
        "body_copy": 0x1C2C,
    },
}


def _va_to_file(blob: bytes, va: int) -> int:
    pe = struct.unpack_from("<I", blob, 0x3C)[0]
    nsec = struct.unpack_from("<H", blob, pe + 6)[0]
    opt = struct.unpack_from("<H", blob, pe + 20)[0]
    base = struct.unpack_from("<I", blob, pe + 24 + 28)[0]
    rva = va - base
    for i in range(nsec):
        off = pe + 24 + opt + i * 40
        vsize, vaddr, rsize, raw = struct.unpack_from("<IIII", blob, off + 8)
        if vaddr <= rva < vaddr + max(vsize, rsize):
            return raw + (rva - vaddr)
    raise AssertionError("VA %#x is not in any section" % va)


class FatherCopyOffsetsTest(unittest.TestCase):
    """VV3, VV4 and VV5 copy the father's head and body onto the mother.

    The layout table recorded them as copying nothing, which forced those three
    games down the name-scan path. That scan resolves a name against LIVING
    villagers only, so when a living villager shares a dead father's name it
    prints the wrong man's appearance -- silently, and permanently, because a
    parentage record has no second source to correct it from.
    """

    def setUp(self) -> None:
        self.text = SOURCE.read_text(encoding="utf-8")

    def _row(self, game_number: int) -> tuple[int, int]:
        """The father_head_copy / father_body_copy pair from a layout row."""
        marker = 'L"Virtual Villagers %d Parentage Log"' % game_number
        self.assertIn(marker, self.text)
        row_end = self.text.index(marker)
        row_start = self.text.rindex("{", 0, row_end)
        row = self.text[row_start:row_end]
        # ..., FATHER_BY_NAME, father, key_cap, litter, HEAD, BODY, no_villager,
        # father_key_capacity is a plain 0 in the VV2 row, not 0x0, so every
        # numeric slot has to accept both spellings.
        num = r"(?:0x[0-9A-Fa-f]+|\d+)"
        match = re.search(
            r"FATHER_BY_NAME,\s*%s,\s*%s,\s*%s,\s*(%s),\s*(%s),"
            % (num, num, num, num, num),
            row,
        )
        self.assertIsNotNone(match, "no copy pair found in the VV%d row" % game_number)
        return int(match.group(1), 16), int(match.group(2), 16)

    def test_copies_are_declared_for_vv3_vv4_vv5(self) -> None:
        for number, key in ((3, "vv3"), (4, "vv4"), (5, "vv5")):
            with self.subTest(game=key):
                head, body = self._row(number)
                self.assertEqual(head, GAMES[key]["head_copy"])
                self.assertEqual(body, GAMES[key]["body_copy"])
                self.assertNotEqual(
                    (head, body),
                    (0, 0),
                    "VV%d was recorded as copying nothing, which forces the "
                    "name scan and prints the wrong father" % number,
                )

    def test_body_sits_before_head_in_every_game(self) -> None:
        """The pair is inverted relative to address order.

        Pairing these by eye -- assuming the lower address is head because head
        is the lower address in the villager's own record -- swaps every
        father's appearance in the log. VV2 has always been stored this way,
        which is the independent corroboration.
        """
        for number in (2, 3, 4, 5):
            with self.subTest(game="vv%d" % number):
                head, body = self._row(number)
                if (head, body) == (0, 0):
                    continue
                self.assertEqual(
                    body + 4,
                    head,
                    "body must sit exactly four bytes before head",
                )

    def test_offsets_match_the_stock_executables(self) -> None:
        """Check the bytes, not the constants.

        Both halves are verified: the CALLER reads the father's head and body
        from his own record, and the STORER writes them onto the mother at the
        declared copy offsets.
        """
        for key, spec in GAMES.items():
            exe = STOCK / spec["exe"]
            if not exe.is_file():
                self.skipTest("%s is not available" % spec["exe"])
            blob = exe.read_bytes()
            with self.subTest(game=key):
                for label in ("caller_body", "caller_head", "store_body", "store_head"):
                    va, expected = spec[label]
                    off = _va_to_file(blob, va)
                    actual = blob[off:off + len(expected) // 2].hex().upper()
                    self.assertEqual(
                        actual,
                        expected.upper(),
                        "%s %s at %#x: expected %s, found %s"
                        % (key, label, va, expected.upper(), actual),
                    )

    def test_store_encodes_the_declared_copy_offset(self) -> None:
        """The displacement inside the store instruction IS the copy offset.

        This is what ties the layout row to the executable: `mov [esi+D], reg`
        encodes D as a little-endian dword at instruction byte 2.
        """
        for key, spec in GAMES.items():
            exe = STOCK / spec["exe"]
            if not exe.is_file():
                self.skipTest("%s is not available" % spec["exe"])
            blob = exe.read_bytes()
            with self.subTest(game=key):
                for label, declared in (
                    ("store_head", spec["head_copy"]),
                    ("store_body", spec["body_copy"]),
                ):
                    va, _ = spec[label]
                    off = _va_to_file(blob, va)
                    disp = struct.unpack_from("<I", blob, off + 2)[0]
                    self.assertEqual(
                        disp,
                        declared,
                        "%s %s writes +%#x but the layout row declares +%#x"
                        % (key, label, disp, declared),
                    )

    def test_shipped_dll_carries_the_offsets(self) -> None:
        """CODE PRESENT != CODE RUNNING."""
        self.assertTrue(DLL.is_file(), "%s is not built" % DLL)
        blob = DLL.read_bytes()
        for key, spec in GAMES.items():
            with self.subTest(game=key):
                for label in ("head_copy", "body_copy"):
                    self.assertIn(
                        struct.pack("<I", spec[label]),
                        blob,
                        "the shipped DLL does not carry %s %s (%#x); it was "
                        "not rebuilt from the current source"
                        % (key, label, spec[label]),
                    )


if __name__ == "__main__":
    unittest.main()
