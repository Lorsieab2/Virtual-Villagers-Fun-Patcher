"""Village Solidarity's Tech screen counter in A New Home and The Lost Children (counter_vv1.inc, counter_vv2.inc).

Pins, against the stock executables, every byte the counter relies on: the splice site's six stock bytes, the
resume address right after them, that both of the draw's paths reach the site, and the first bytes of the three
game routines the counter calls (the centred text, the width and the line height).  The .inc files hold the
addresses; this test reads them from the source so the two cannot drift apart.
"""

import re
import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NATIVE = ROOT / "native" / "vvfp_village_solidarity"
EXES = {1: ROOT / "research" / "stock-executables" / "Virtual Villagers - A New Home.exe",
        2: ROOT / "research" / "stock-executables" / "Virtual Villagers - The Lost Children.exe"}
# The Tech screen draw of each game, and the stock jumps that reach the site.
DRAW = {1: 0x433B20, 2: 0x441830}
JUMPS = {1: (0x433DA8, 0x433FFD), 2: (0x441AB8, 0x441D0D)}

sys.path.insert(0, str(ROOT / "scripts"))


def _section_reader(exe: Path):
    data = exe.read_bytes()
    pe = struct.unpack_from("<I", data, 0x3C)[0]
    count = struct.unpack_from("<H", data, pe + 6)[0]
    optional = struct.unpack_from("<H", data, pe + 20)[0]
    base = struct.unpack_from("<I", data, pe + 24 + 28)[0]
    sections = []
    for i in range(count):
        at = pe + 24 + optional + 40 * i
        vsize, va, rsize, raw = struct.unpack_from("<IIII", data, at + 8)
        sections.append((base + va, max(vsize, rsize), raw))

    def read(va: int, n: int) -> bytes:
        for start, size, raw in sections:
            if start <= va < start + size:
                return data[raw + va - start: raw + va - start + n]
        raise ValueError(hex(va))
    return read


def _bytes(name: str, text: str) -> bytes:
    body = re.search(r"%s\[\d+\]\s*=\s*\{([^}]*)\}" % re.escape(name), text).group(1)
    return bytes(int(v, 16) for v in re.findall(r"0x([0-9A-Fa-f]{2})", body))


def _define(name: str, text: str) -> int:
    return int(re.search(r"#define %s (0x[0-9A-Fa-f]+)u" % name, text).group(1), 16)


def _routines(game: int, text: str) -> tuple[int, int, int]:
    body = re.search(r"sol12_game SOL_VV%d = \{([^}]*)\}" % game, text).group(1)
    return tuple(int(v, 16) for v in re.findall(r"0x([0-9A-Fa-f]+)u", body))


class CounterSitesAreStock(unittest.TestCase):
    def setUp(self):
        self.shared = (NATIVE / "counter_vv1.inc").read_text(encoding="utf-8")

    def check(self, game: int):
        text = (NATIVE / ("counter_vv%d.inc" % game)).read_text(encoding="utf-8")
        read = _section_reader(EXES[game])
        site = _define("SOL_VV%d_SITE" % game, text)
        resume = _define("SOL_VV%d_RESUME" % game, text)
        stock = _bytes("SOL12_SITE_STOCK", self.shared)
        self.assertEqual(stock, bytes.fromhex("8B8E24010000"))
        self.assertEqual(read(site, len(stock)), stock)
        self.assertEqual(resume, site + len(stock))
        # The next stock instructions: mov edx/eax, [ecx]; call [reg + 0x18] (the first widget's draw).
        self.assertIn(read(resume, 5), (bytes.fromhex("8B11FF5218"), bytes.fromhex("8B01FF5018")))
        from capstone import CS_ARCH_X86, CS_MODE_32, Cs
        for jump in JUMPS[game]:
            ins = next(Cs(CS_ARCH_X86, CS_MODE_32).disasm(read(jump, 6), jump))
            self.assertTrue(ins.mnemonic.startswith("j"), (hex(jump), ins.mnemonic))
            self.assertEqual(int(ins.op_str, 16), site)
        self.assertTrue(DRAW[game] < site)
        text_routine, width, height = _routines(game, text)
        for va, name in ((text_routine, "SOL12_TEXT_STOCK"), (width, "SOL12_WIDTH_STOCK"),
                         (height, "SOL12_HEIGHT_STOCK")):
            expect = _bytes(name, self.shared)
            self.assertEqual(read(va, len(expect)), expect, (game, hex(va)))

    def test_a_new_home(self):
        self.check(1)

    def test_the_lost_children(self):
        self.check(2)


if __name__ == "__main__":
    unittest.main()
