"""Fix Vanilla Bugs: a word wider than its box no longer hangs the game or vanishes ("VVFP Long Words.dll", The Lost Children, The
Secret City, The Tree of Life, New Believers).

The stock line layout never places a word wider than its box: the justified paragraph (VV3 0x40A0C0, VV4 0x409C30,
VV5 0x409F00) drops a line's only word and tries it again for ever, and the line fit (VV2 0x4022B0, VV3 0x4022F0,
VV4 0x402550, VV5 0x402500) backs a line with no space off to nothing and returns one letter on: the word loses its
letters one empty line each until the rest of it fits (a tip with a run of empty lines).  A New Home has neither
routine.

Proofs, in EMULATION of each published build with the game's own fonts (tests/scrolling_popups_emulation.py: the
startup chain with the game's Fix Vanilla Bugs row, which ships and starts the companion):
  * with the sites written back to the stock bytes, on a text with such a word the stock justified paragraph never
    finishes (stopped by an instruction limit) and the stock line fit gives empty lines and loses the word's first letters;
  * with the companion they finish: the justified paragraph draws the long word on a line of its own at its full width
    (wider than the box) and goes on; the line fit gives it a line of its own, whole, and the next call goes on after
    it;
  * every text without such a word is laid out byte for byte (line fit) and blit for blit (justified paragraph) as the
    stock routines lay it out;
  * the rows: the companion pinned in the four Fix Vanilla Bugs rows, its sites holding their stock bytes, no other row
    touching them, and all or none (a changed site installs nothing).
The live effect in a running game is NOT verified here.
"""
from __future__ import annotations

import hashlib
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import vv_fun_patcher as patcher  # noqa: E402

try:
    import pefile
    import unicorn  # noqa: F401
    from story_emulator import Process
    HAVE_EMULATOR = True
except ImportError:  # pragma: no cover
    HAVE_EMULATOR = False

NAMES = {1: "A New Home", 2: "The Lost Children", 3: "The Secret City", 4: "The Tree of Life", 5: "New Believers"}
STOCK = {g: ROOT / "research" / "stock-executables" / f"Virtual Villagers - {n}.exe" for g, n in NAMES.items()}
IMAGES = ROOT / "research" / "game-images"
HAVE_STOCK = all(p.is_file() for p in STOCK.values())
HAVE_IMAGES = all((IMAGES / f"Virtual Villagers - {n}" / "Images").is_dir() for n in NAMES.values())
DLL_NAME = "VVFP Long Words.dll"
DLL = ROOT / "assets" / "long_words" / DLL_NAME
GAMES = (2, 3, 4, 5)
JUSTIFY = {3: 0x40A0C0, 4: 0x409C30, 5: 0x409F00}
LINEFIT = {2: 0x4022B0, 3: 0x4022F0, 4: 0x402550, 5: 0x402500}
# The sites: (va, stock bytes the companion replaces).
SITES = {
    2: [(0x4023E5, "803E207415")],
    3: [(0x40A2DC, "3BC8897C2414"), (0x402425, "803E207415")],
    4: [(0x409E4D, "3BC8897C2418"), (0x402686, "803E207416")],
    5: [(0x40A11D, "3BC8897C2418"), (0x402636, "803E207416")],
}
WORD = b"Supercalifragilisticexpialidociously-Kalahuna-Wewehimanukalawehi"
WIDE_TEXTS = (
    WORD,
    b"Your tribe meets " + WORD + b" by the shore. He stays.",
    b"Short words first, then " + WORD + b" " + WORD + b"\nand a new line.",
)
NORMAL_TEXTS = (
    b"Your villagers find a basket of fruit washed up on the shore. Everyone eats well tonight.",
    b"A storm blows through the village.\n\nThe huts hold, but the garden is flattened. Rebuild it soon!",
    b"One, two, three... 1,000 coconuts? Who knew the island held so many?",
    b"Tight fit tight fit tight fit tight fit tight fit tight fit tight fit tight fit tight fit tight",
    b"",
)
BOX = 300


def row(game: int) -> dict:
    return next(p.raw for p in patcher.load_fun_patches() if p.id == f"vv{game}_fix_vanilla_bugs")


class TheRows(unittest.TestCase):
    def test_the_fix_vanilla_bugs_rows_ship_and_pin_the_companion(self) -> None:
        digest = hashlib.sha256(DLL.read_bytes()).hexdigest().upper()
        self.assertIn(DLL_NAME, patcher.STARTUP_LOADER_COMPANIONS_2)
        for game in GAMES:
            with self.subTest(game=game):
                r = row(game)
                files = {f["destination"]: f["sha256"] for f in r["companion_files"]}
                self.assertEqual(files.get(DLL_NAME), digest)
                detours = [(int(d["va"], 16), d["stock_bytes"]) for d in r["runtime_detours"]
                           if DLL_NAME in d["installed_by"]]
                self.assertEqual(detours, SITES[game])
                self.assertIn("wider than", r["description"])
        self.assertNotIn(DLL_NAME, {f["destination"] for f in row(1)["companion_files"]})

    def test_the_c_table_holds_the_same_sites(self) -> None:
        source = (ROOT / "native" / "vvfp_long_words" / "vvfp_long_words.c").read_text(encoding="utf-8")
        for game in GAMES:
            for va, stock in SITES[game]:
                self.assertIn(f"0x{va:X}u", source)
                written = ", ".join(f"0x{b:02X}" for b in bytes.fromhex(stock))
                self.assertIn("{" + written, source)

    @unittest.skipUnless(HAVE_EMULATOR and HAVE_STOCK, "needs pefile and the stock executables")
    def test_every_site_holds_its_stock_bytes_and_no_other_row_claims_it(self) -> None:
        for game in GAMES:
            pe = pefile.PE(str(STOCK[game]), fast_load=True)
            image = pe.get_memory_mapped_image()
            for va, stock in SITES[game]:
                self.assertEqual(image[va - 0x400000:va - 0x400000 + len(stock) // 2].hex().upper(), stock, hex(va))
            for p in patcher._load_fun_patch_records():
                if p.raw.get("game_id") != f"vv{game}":
                    continue
                for d in p.raw.get("runtime_detours", []) or []:
                    if DLL_NAME in d.get("installed_by", ""):
                        continue
                    va, n = int(str(d["va"]), 0), len(bytes.fromhex(d["stock_bytes"]))
                    for site, stock in SITES[game]:
                        self.assertFalse(va < site + len(stock) // 2 and site < va + n, (p.id, hex(va)))

    @unittest.skipUnless(HAVE_EMULATOR and HAVE_STOCK, "needs unicorn and the stock executables")
    def test_all_or_none(self) -> None:
        for game in GAMES:
            p = Process(STOCK[game].read_bytes(), DLL)
            p.export("VvfpStartup", game, 0)
            self.assertEqual(p.export("VvfpLongWordsInstalled"), 1)
            for va, stock in SITES[game]:
                with self.subTest(game=game, site=hex(va)):
                    data = bytearray(STOCK[game].read_bytes())
                    pe = pefile.PE(data=bytes(data), fast_load=True)
                    data[pe.get_offset_from_rva(va - 0x400000)] ^= 0xFF
                    p = Process(bytes(data), DLL)
                    p.export("VvfpStartup", game, 0)
                    self.assertEqual(p.export("VvfpLongWordsInstalled"), 0)
                    for other, other_stock in SITES[game]:
                        if other != va:
                            self.assertEqual(p.read(other, len(other_stock) // 2).hex().upper(), other_stock)
        p = Process(STOCK[1].read_bytes(), DLL)
        p.export("VvfpStartup", 1, 0)
        self.assertEqual(p.export("VvfpLongWordsInstalled"), 0)


@unittest.skipUnless(HAVE_EMULATOR and HAVE_STOCK and HAVE_IMAGES, "needs unicorn, the stock executables and images")
class TheLayout(unittest.TestCase):
    runs: dict = {}

    @classmethod
    def setUpClass(cls) -> None:
        import scrolling_popups_emulation as spe
        for game in GAMES:
            cls.runs[game] = spe.Dialog(f"vv{game}", selection=(f"vv{game}_fix_vanilla_bugs",))

    @classmethod
    def tearDownClass(cls) -> None:
        cls.runs.clear()

    def stock(self, d, game):
        """The sites written back to the game's own bytes (the game without the companion); returns an undo."""
        saved = [(va, bytes(d.mu.mem_read(va, len(stock) // 2))) for va, stock in SITES[game]]
        for va, stock in SITES[game]:
            d.mu.mem_write(va, bytes.fromhex(stock))
        d.mu.ctl_flush_tb()                   # code already translated must not run the old bytes

        def undo():
            for va, data in saved:
                d.mu.mem_write(va, data)
            d.mu.ctl_flush_tb()
        return undo

    def linefit(self, d, game, text: bytes, width: int = BOX, count: int = 2_000_000) -> list[bytes]:
        """Every line the line fit gives `text`, calling it from where the last call stopped (as the tips do)."""
        src = d._cstr(text)
        out = d.m.font_heap.alloc(0x400)
        para = d.m.font_heap.alloc(4)
        lines, at = [], src
        for _ in range(200):
            if d.mu.mem_read(at, 1) == b"\0":
                return lines
            d.mu.mem_write(out, b"\xAA" * 0x400)
            nxt = d.run._call(LINEFIT[game], d.font, at, out, 0xC8, width, para, 0, 0x3F800000, count=count)
            lines.append(bytes(d.mu.mem_read(out, 0x100)).split(b"\0")[0])
            self.assertNotEqual(nxt, at, "the line fit made no progress")
            at = nxt
        self.fail("more than 200 lines")

    def justify(self, d, game, text: bytes, measure: int = 0, count: int = 5_000_000):
        d.m.blits = []
        height = d.run._call(JUSTIFY[game], d.holder, d._cstr(text), 40, 50, BOX, 0, d.font, measure, count=count)
        return height, list(d.m.blits)

    def test_installed(self) -> None:
        for game, d in self.runs.items():
            with self.subTest(game=game):
                dll = next(m for k, m in d.m.modules.items() if "long words" in k)
                self.assertEqual(d.run._call(dll.exports["VvfpLongWordsInstalled"], 0), 1)

    def test_the_stock_routines_lose_or_hang_on_a_wide_word(self) -> None:
        for game, d in self.runs.items():
            with self.subTest(game=game):
                undo = self.stock(d, game)
                try:
                    # the line fit: one empty line per letter of the word, and the word lost
                    lines = self.linefit(d, game, WIDE_TEXTS[1], count=2_000_000)
                    self.assertNotIn(WORD, lines)
                    self.assertGreaterEqual(lines.count(b""), 10)       # until the rest of it fits the line
                    if game in JUSTIFY:
                        with self.assertRaises(Exception):
                            self.justify(d, game, WIDE_TEXTS[1], measure=1, count=3_000_000)
                finally:
                    undo()

    def test_the_line_fit_gives_the_word_a_line_of_its_own(self) -> None:
        for game, d in self.runs.items():
            with self.subTest(game=game):
                self.assertEqual(self.linefit(d, game, WORD), [WORD])
                lines = self.linefit(d, game, WIDE_TEXTS[1])
                self.assertIn(WORD, lines)
                self.assertEqual(b" ".join(lines).split(), WIDE_TEXTS[1].split())
                lines = self.linefit(d, game, WIDE_TEXTS[2])
                self.assertEqual(lines.count(WORD), 2)

    def test_the_justified_paragraph_lays_the_word_out_at_full_width(self) -> None:
        for game, d in self.runs.items():
            if game not in JUSTIFY:
                continue
            with self.subTest(game=game):
                line_h, _ = self.justify(d, game, b"X", measure=1)
                height, blits = self.justify(d, game, WIDE_TEXTS[1])
                self.assertEqual(height, self.justify(d, game, WIDE_TEXTS[1], measure=1)[0])
                rows = sorted({b[3][1] for b in blits})
                self.assertEqual(height, len(rows) * line_h)
                # the long word: a line of its own, from the box's left, wider than the box
                widest = max(rows, key=lambda y: max(b[3][0] + b[1][2] for b in blits if b[3][1] == y))
                own = [b for b in blits if b[3][1] == widest]
                self.assertEqual(min(b[3][0] for b in own), 40)
                self.assertGreater(max(b[3][0] + b[1][2] for b in own), 40 + BOX)
                self.assertGreater(rows.index(widest), 0)              # after "Your tribe meets"
                self.assertLess(rows.index(widest), len(rows) - 1)     # before "by the shore. He stays."

    def test_text_without_a_wide_word_is_laid_out_as_before(self) -> None:
        for game, d in self.runs.items():
            with self.subTest(game=game):
                fixed_lines = [self.linefit(d, game, t) for t in NORMAL_TEXTS]
                fixed_blits = [self.justify(d, game, t) for t in NORMAL_TEXTS] if game in JUSTIFY else []
                undo = self.stock(d, game)
                try:
                    self.assertEqual([self.linefit(d, game, t) for t in NORMAL_TEXTS], fixed_lines)
                    if game in JUSTIFY:
                        stock = [self.justify(d, game, t) for t in NORMAL_TEXTS]
                        self.assertEqual([(h, [(b[1], b[3]) for b in bl]) for h, bl in stock],
                                         [(h, [(b[1], b[3]) for b in bl]) for h, bl in fixed_blits])
                finally:
                    undo()


if __name__ == "__main__":
    unittest.main()
