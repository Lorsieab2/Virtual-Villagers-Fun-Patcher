"""A Custom Island Event's "Refill the food sources" writes the stores the game's own refill events write.

Each game's refill (native/vvfp_story_upgrades/story_c<N>.inc, c<N>_refill) is pinned here to the stock code of the
events and regrowth that change the same stores, read from the stock executables:

  A New Home: berry bush world+0xA2F4 (North Wind adds to it, 0x4283B5; regrowth +30, 0x42EC0D), crops world+0xA2F8
  (North Wind 0x4283CE, the Locusts 0x427F73, a harvest -7 0x43AF0E, regrowth capped at 800 0x42F2CE).  world+0xA2FC
  is the tech points; 0xA2FC is the crops' offset in a SAVE FILE (state + 4, src/vv_game_mechanics_vv1.py FIELD).
  The Lost Children: coconuts +0x2EACC and crops +0x2EAD8 (event 0x4342DA / 0x4342F4, regrowth 0x43B9FF),
  protection +0x2EAD4 (a new village's 1000, 0x425261).
  The Secret City: 0x4340A0 sets a tree's fruit to 1000 (the beans' fertilizer calls it, 0x415AF4).
  The Tree of Life: blackberries +0x170F8 (A Closer Look 0x414B38, ceiling 1000 0x4203D9).
  New Believers: noni +0x17D58 (The River Breaks Its Banks 0x414FB5, ceiling 1000 0x425F72), crops +0x17D5C
  (0x414EC8, ceiling 800 0x4260F7).
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STOCK = ROOT / "research" / "stock-executables"
NATIVE = ROOT / "native" / "vvfp_story_upgrades"
EXES = {1: "Virtual Villagers - A New Home.exe", 2: "Virtual Villagers - The Lost Children.exe",
        3: "Virtual Villagers - The Secret City.exe", 4: "Virtual Villagers - The Tree of Life.exe",
        5: "Virtual Villagers - New Believers.exe"}

try:
    import capstone
    import pefile
    HAVE_TOOLS = True
except ImportError:  # pragma: no cover - environment dependent
    HAVE_TOOLS = False

# game: ((address, the stock instruction there), ...), and the offsets its refill must write
SITES = {
    1: (((0x4283B5, "add dword ptr [eax + 0xa2f4], edi"), (0x4283CE, "mov dword ptr [esi + 0xa2f8], eax"),
         (0x427F73, "mov dword ptr [eax + 0xa2f8], ebx"), (0x43AF0E, "add dword ptr [eax + 0xa2f8], -7"),
         (0x42F2CE, "mov dword ptr [eax + 0xa2f8], ecx"), (0x42EC0D, "add dword ptr [eax + 0xa2f4], 0x1e")),
        ("world + 0xA2F4", "world + 0xA2F8")),
    2: (((0x4342DA, "add dword ptr [eax + 0x2eacc], esi"), (0x4342F4, "mov dword ptr [ebp + 0x2ead8], eax"),
         (0x43B9FF, "add dword ptr [eax + 0x2ead8], 0x320"), (0x425261, "mov dword ptr [ebp + 0x2ead4], 0x3e8")),
        ("world + 0x2EACC", "world + 0x2EAD4", "world + 0x2EAD8")),
    3: (((0x415AF4, "call 0x4340a0"), (0x4340A8, "mov dword ptr [ecx + eax*8], 0x3e8")),
        ("0x4340A0u",)),
    4: (((0x414B38, "add dword ptr [eax + 0x170f8], 0x15e"), (0x4203D9, "cmp dword ptr [eax + 0x170f8], ecx")),
        ("world + 0x170F8",)),
    5: (((0x414FB5, "add dword ptr [eax + 0x17d58], 0xc8"), (0x414EC8, "mov dword ptr [eax + 0x17d5c], esi"),
         (0x425F72, "cmp dword ptr [eax + 0x17d58], ecx"), (0x4260F7, "cmp dword ptr [eax + 0x17d5c], ecx")),
        ("world + 0x17D58", "world + 0x17D5C")),
}


def refill_body(game: int) -> str:
    text = (NATIVE / f"story_c{game}.inc").read_text(encoding="utf-8")
    start = text.index(f"static int c{game}_refill(void) {{")
    return text[start:text.index("\n}\n", start)]


class RefillFields(unittest.TestCase):
    def test_refill_writes_the_stores_named(self) -> None:
        for game, (_, offsets) in SITES.items():
            body = refill_body(game)
            for offset in offsets:
                with self.subTest(game=game, offset=offset):
                    self.assertIn(offset, body)
        # A New Home: never the tech points
        self.assertNotRegex(refill_body(1), re.compile(r"0xA2FC", re.I))

    @unittest.skipUnless(HAVE_TOOLS and all((STOCK / n).is_file() for n in EXES.values()),
                         "needs capstone, pefile and the stock executables")
    def test_stock_events_write_the_same_stores(self) -> None:
        md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
        for game, (sites, _) in SITES.items():
            pe = pefile.PE(str(STOCK / EXES[game]))
            image = pe.get_memory_mapped_image()
            base = pe.OPTIONAL_HEADER.ImageBase
            for address, want in sites:
                with self.subTest(game=game, address=hex(address)):
                    ins = next(md.disasm(image[address - base:address - base + 16], address))
                    self.assertEqual(f"{ins.mnemonic} {ins.op_str}", want)


if __name__ == "__main__":
    unittest.main()
