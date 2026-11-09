"""Skin Tones (A New Home; a DRAFT, not for a release): each villager drawn from the owner's own sheets for its skin
tone ("VVFP Skin Tones.dll", native/vvfp_skin_tones; the owner, 2026-11-06).

THE DRAWS, in an emulator on the stock executable with the DLL started, a village in the game's own records, the
owner's sheets answered by the test (PNG headers only) and every engine draw's sprite recorded:
* the 35 body and action reads are spliced (jmp + nop) and run through the game's own code to the engine draw;
* a villager of tone 0 is drawn from the game's own sheet; a villager of tone 3 from the tone-3 sheet of the same
  kind -- built once, by the game's own constructors, from Images\\vvfp_skin\\3\\<the game's file name> (a grid
  of four or two files for the bodies and actions);
* a sheet that is missing, of another size, or that the game does not load as 40 x 65 cells falls back to the
  game's own; a tone above the folders falls back too;
* the villager drawn is the one the loop names (the village's draw order, the map's pointer, EDI's record);
* Vv1SkinToneSheetFor / Vv1SkinToneGreySheetFor, which Grey Hair at 55 and Show Parents ask, answer the same;
* the number of tones is the folders 1, 2, 3 ... present, eight with none;
* all or nothing: one changed byte anywhere the DLL checks and nothing is written.

GREY HAIR ASKS IT: "VVFP VV1 Grey Hair.dll" in the emulator with a stand-in Skin Tones module: a young head is the
sheet Vv1SkinToneSheetFor gives, a grey head the one Vv1SkinToneGreySheetFor gives, and without the module
nothing changes.

BIRTHS: the Origins companion's Vv1Born hands every birth to Vv1SkinToneBorn, with the parentage companion in the
game or not.

THE FILE AND THE RULES (founders and arrivals random once the roster settles, babies the midpoint of their parents'
tones at conception toward the mother's, twins, no father, Change Appearance's choice, following the villager,
another village's file, a broken file, Start Over): native/vvfp_skin_tones/skin_tone_harness.c on real files.

The live effect in a running game is NOT verified here.
"""
from __future__ import annotations

import functools
import hashlib
import json
import re
import struct
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT / "scripts"))

import vv_fun_patcher as patcher  # noqa: E402

try:
    import pefile
    from unicorn import UC_HOOK_CODE

    from head_look_emulation import Disk
    from story_emulator import STACK_TOP, Process

    HAVE_EMULATOR = True
except ImportError:  # pragma: no cover - environment dependent
    HAVE_EMULATOR = False
    STACK_TOP = 0

DLL = ROOT / "assets" / "skin_tones" / "VVFP Skin Tones.dll"
GREY_DLL = ROOT / "assets" / "vv1_grey_hair" / "VVFP VV1 Grey Hair.dll"
ORIGINS_DLL = ROOT / "assets" / "origins" / "VVFP VV1 Origins Icons.dll"
FEATURE = ROOT / "data" / "vv1_skin_tones_feature.json"
ROW_ID = "vv1_skin_tones"

STRIDE, COUNT = 0x3D8, 256
REC_PRESENT, REC_AGE, REC_SEX, REC_FAMILY, REC_NAME = 0x28, 0x348, 0x350, 0x36C, 0x370
DRAW_ORDER = 0x3DBDC
RECORDS_PTR, MANAGER, SLOT_FIELD = 0x48B614, 0x48AEDC, 0xABE4
ALLOC, CTOR, GRID_CTOR = 0x44AF03, 0x40A070, 0x40A0F0
ENGINES = {0x408AF0: 0x408AF7, 0x408740: 0x408747}
GAMEOBJ_SIZE = 0x3E100
GAME_DIR = "C:\\Games\\Village"

# The six sheets the game holds: gameobj slot -> (the game's file name or grid prefix, grid, file size).
KINDS = {
    0x3DFF4: ("female_heads.png", (1, 1), (280, 1300)),
    0x3DFF8: ("male_heads.png", (1, 1), (280, 1300)),
    0x3DFE4: ("female_bodies", (2, 2), (640, 650)),
    0x3DFE8: ("male_bodies", (2, 2), (640, 650)),
    0x3DFEC: ("female_actions", (1, 2), (360, 650)),
    0x3DFF0: ("male_actions", (1, 2), (360, 650)),
}
GREY = {True: ("vvfp_grey_male_heads.png", (280, 1300)), False: ("vvfp_grey_female_heads.png", (280, 1300))}

EDI, VILLAGE, MAP = "edi", "village", "map"
# (read, destination register, gameobj slot, where the villager is) -- native/vvfp_skin_tones/vvfp_skin_tones.c
READS = (
    (0x4373B8, "edx", 0x3DFE8, EDI), (0x437441, "ecx", 0x3DFE4, EDI), (0x4374C0, "eax", 0x3DFE8, EDI),
    (0x437513, "edx", 0x3DFE4, EDI), (0x437679, "ecx", 0x3DFE8, EDI), (0x4376D5, "ecx", 0x3DFE4, EDI),
    (0x437723, "ecx", 0x3DFE8, EDI), (0x437744, "ecx", 0x3DFE4, EDI),
    (0x437A8E, "ecx", 0x3DFF0, VILLAGE), (0x437AED, "edx", 0x3DFE8, VILLAGE), (0x437B2D, "edx", 0x3DFF0, VILLAGE),
    (0x437C62, "edx", 0x3DFF0, VILLAGE), (0x437D08, "edx", 0x3DFEC, VILLAGE), (0x437E38, "edx", 0x3DFE8, VILLAGE),
    (0x437F3E, "edx", 0x3DFE4, VILLAGE), (0x438210, "ecx", 0x3DFF0, VILLAGE), (0x438286, "ecx", 0x3DFEC, VILLAGE),
    (0x438327, "ecx", 0x3DFF0, VILLAGE), (0x43837D, "ecx", 0x3DFEC, VILLAGE), (0x43853F, "ecx", 0x3DFF0, VILLAGE),
    (0x438593, "ecx", 0x3DFEC, VILLAGE), (0x438723, "ecx", 0x3DFE8, VILLAGE), (0x438777, "ecx", 0x3DFE4, VILLAGE),
    (0x438A07, "eax", 0x3DFF0, MAP), (0x438AAE, "ecx", 0x3DFF0, MAP), (0x438B05, "ecx", 0x3DFE8, MAP),
    (0x438B7B, "ecx", 0x3DFE4, MAP), (0x438CDC, "eax", 0x3DFF0, MAP), (0x438D6A, "ecx", 0x3DFEC, MAP),
    (0x438E36, "eax", 0x3DFF0, MAP), (0x438EA3, "eax", 0x3DFEC, MAP), (0x439002, "eax", 0x3DFF0, MAP),
    (0x439087, "ecx", 0x3DFEC, MAP), (0x439170, "ecx", 0x3DFE8, MAP), (0x4391EA, "ecx", 0x3DFE4, MAP),
)


@functools.lru_cache(maxsize=None)
def _build():
    return {b.id: b for b in patcher.load_builds()}["vv1"]


def stock_path() -> Path:
    return ROOT / "inputs" / "vv1-stock-copy" / _build().input_name


@functools.lru_cache(maxsize=None)
def stock_exe() -> bytes:
    return stock_path().read_bytes()


def have() -> bool:
    return HAVE_EMULATOR and stock_path().is_file() and DLL.is_file()


def png_header(width: int, height: int) -> bytes:
    return (b"\x89PNG\r\n\x1a\n" + struct.pack(">I", 13) + b"IHDR" + struct.pack(">II", width, height)
            + b"\x08\x06\x00\x00\x00")


def tone_files(tone: int, *, size=None, skip=()) -> dict[str, bytes]:
    """Every sheet of a tone, as the owner would make it: {file name in the tone's folder: PNG header}."""
    files = {}
    for name, (across, down), (w, h) in KINDS.values():
        names = [name] if (across, down) == (1, 1) else [f"{name}{x}{y}.png" for y in range(down) for x in range(across)]
        for leaf in names:
            files[leaf] = png_header(*(size or (w, h)))
    for leaf, (w, h) in GREY.values():
        files[leaf] = png_header(*(size or (w, h)))
    return {k: v for k, v in files.items() if k not in skip}


class Stop(Exception):
    pass


class Game:
    """The executable with "VVFP Skin Tones.dll" started, a village in the game's own records, the owner's sheets on
    an emulated disk (`tones`: tone -> {file: bytes}), the game's constructors answered and every engine draw's
    sprite recorded."""

    def __init__(self, exe: bytes | None = None, *, tones=None, cells=(40, 65), folders=None, start=True):
        self.p = p = Process(exe if exe is not None else stock_exe(), DLL)
        self.disk = Disk(p)
        p.tick = 1_000_000
        self.cells = cells
        self.built: list[tuple[str, tuple]] = []
        tones = {3: tone_files(3)} if tones is None else tones
        self.disk.folders.update({f"{GAME_DIR}\\Images".lower(), f"{GAME_DIR}\\Images\\vvfp_skin".lower()})
        for tone in (folders if folders is not None else range(1, max(tones, default=0) + 1)):
            self.disk.folders.add(f"{GAME_DIR}\\Images\\vvfp_skin\\{tone}".lower())
        for tone, files in tones.items():
            for leaf, data in files.items():
                self.disk.files[f"{GAME_DIR}\\Images\\vvfp_skin\\{tone}\\{leaf}".lower()] = data
        p.stub(ALLOC, lambda p: (p.alloc(p.arg(0)), 0))
        p.stub(CTOR, self._ctor)
        p.stub(GRID_CTOR, self._grid)
        self.scratch = p.alloc(0x2000)
        self.game = p.alloc(GAMEOBJ_SIZE)
        for field in range(0x3DF00, 0x3E040, 4):
            p.put32(self.game + field, self.scratch)
        p.put32(self.scratch, self.scratch + 0x100)
        self.stock = {slot: p.alloc(0x34) for slot in KINDS}
        for slot, sprite in self.stock.items():
            p.put32(self.game + slot, sprite)
        p.put32(RECORDS_PTR, self.game)
        manager = p.alloc(SLOT_FIELD + 0x100)
        p.put32(MANAGER, manager)
        p.put32(manager + SLOT_FIELD, 1)
        self.draws: list[int] = []
        for resume in ENGINES.values():
            p.stub(resume, self._draw)
        if start:
            p.export("VvfpStartup", 1, 0)

    # -- the game's routines -------------------------------------------------------------------------------------
    def _ctor(self, p):
        this = p.reg("ecx")
        self.built.append((p.cstring(p.arg(0)), (p.arg(1), p.arg(2))))
        p.put32(this + 0x10, self.cells[0])
        p.put32(this + 0x14, self.cells[1])
        return this, 0xC

    def _grid(self, p):
        this = p.reg("ecx")
        self.built.append((p.cstring(p.arg(0)), (p.cstring(p.arg(1)), p.arg(2), p.arg(3), p.arg(4), p.arg(5))))
        p.put32(this + 0x10, self.cells[0])
        p.put32(this + 0x14, self.cells[1])
        return this, 0x18

    def _draw(self, p):
        self.draws.append(p.u32(p.reg("esp") + 0x14))
        p.mu.emu_stop()
        p.set_reg("esp", p.reg("esp") + 0x10)
        return 0, 0x1C

    # -- the village ---------------------------------------------------------------------------------------------
    def record(self, index: int) -> int:
        return self.game + index * STRIDE

    def villager(self, index: int, name: str, *, male: bool, age: int = 600, family: int = 0) -> int:
        rec = self.record(index)
        p = self.p
        p.write(rec + REC_PRESENT, b"\x01")
        p.write(rec + REC_NAME, name.encode() + b"\0")
        p.put32(rec + REC_SEX, 1 if male else 2)
        p.put32(rec + REC_AGE, age)
        p.put32(rec + REC_FAMILY, family or 100 + index)
        return rec

    def later(self) -> None:
        self.p.tick += 1000

    def set_tone(self, index: int, tone: int) -> int:
        self.later()
        return self.p.export("Vv1SkinToneSet", self.record(index), tone)

    def tone(self, index: int) -> int:
        self.later()
        value = self.p.export("Vv1SkinToneGet", self.record(index))
        return value - (1 << 32) if value >= 1 << 31 else value

    def run_read(self, va: int, where: str, index: int, *, slot: int = 7) -> tuple[int, int]:
        """Run the game from the read at `va` for record `index` to the engine draw it feeds.  Returns (the
        register the read filled, the sprite drawn)."""
        p = self.p
        self.later()
        for reg in ("eax", "ebx", "ecx", "edx"):
            p.set_reg(reg, self.scratch)
        p.set_reg("esi", self.game)
        if where == EDI:
            p.set_reg("edi", self.record(index))
        elif where == VILLAGE:
            p.put32(self.game + DRAW_ORDER + 4 * slot, index)
            p.set_reg("edi", slot)
        else:
            p.put32(self.game + DRAW_ORDER + 4 * slot, index)
            p.set_reg("ebp", self.game + DRAW_ORDER + 4 * slot)
        p.set_reg("esp", STACK_TOP - 0x4000)
        reg = next(r for v, r, _, _ in READS if v == va)
        filled: list[int] = []
        hook = p.mu.hook_add(UC_HOOK_CODE, lambda mu, address, size, data: filled.append(p.reg(reg)),
                             begin=va + 6, end=va + 6)
        before = len(self.draws)
        try:
            p.mu.emu_start(va, 0, count=20_000_000)
        finally:
            p.mu.hook_del(hook)
        if len(self.draws) != before + 1 or len(filled) != 1:
            raise AssertionError(f"the read at {va:#x} reached no engine draw (stopped at {p.reg('eip'):#x})")
        return filled[0], self.draws[-1]


def _skip():
    return unittest.skipUnless(have(), "unicorn/pefile, the stock A New Home or the DLL is missing")


@_skip()
class TheDraws(unittest.TestCase):
    def test_installs_35_detours(self):
        g = Game()
        self.assertEqual(g.p.export("Vv1SkinToneInstalled"), 1)
        for va, *_ in READS:
            self.assertEqual(g.p.read(va, 1), b"\xE9", hex(va))
            self.assertEqual(g.p.read(va + 5, 1), b"\x90", hex(va))
        for entry in ENGINES:                                   # the engine entries stay Grey Hair's
            self.assertEqual(g.p.read(entry, 3), b"\x83\xEC\x10")

    def test_each_read_draws_the_villagers_tone(self):
        g = Game()
        g.villager(42, "Kai", male=True)
        g.villager(43, "Ana", male=False)
        self.assertEqual(g.set_tone(42, 0), 1)
        self.assertEqual(g.set_tone(43, 3), 1)
        toned: dict[int, int] = {}
        for va, reg, slot, where in READS:
            with self.subTest(read=hex(va)):
                rec_before = g.p.read(g.record(42), STRIDE)
                filled, sprite = g.run_read(va, where, 42)
                self.assertEqual(sprite, g.stock[slot])            # tone 0: the game's own sheet
                self.assertEqual(filled, g.stock[slot])
                filled, sprite = g.run_read(va, where, 43)
                self.assertNotIn(sprite, set(g.stock.values()) | {g.scratch})
                self.assertEqual(filled, sprite)                   # the register the read fills
                self.assertEqual(g.p.u32(sprite + 0x10), 40)
                self.assertEqual(toned.setdefault(slot, sprite), sprite)   # one sheet per kind, kept
                self.assertEqual(g.p.read(g.record(42), STRIDE), rec_before)   # no record byte written
        self.assertEqual(len(set(toned.values())), 4)
        names = sorted(name for name, _ in g.built)
        self.assertEqual(names, ["vvfp_skin\\3\\female_actions", "vvfp_skin\\3\\female_bodies",
                                 "vvfp_skin\\3\\male_actions", "vvfp_skin\\3\\male_bodies"])
        grids = {name: args for name, args in g.built}
        self.assertEqual(grids["vvfp_skin\\3\\male_bodies"], (".png", 2, 2, 32, 20))      # as 0x43C10F builds it
        self.assertEqual(grids["vvfp_skin\\3\\female_actions"], (".png", 1, 2, 9, 20))    # as 0x43C14F builds it

    def test_the_villager_drawn_is_the_one_the_loop_names(self):
        g = Game()
        g.villager(3, "Toned", male=True)
        g.villager(200, "Plain", male=True)
        g.set_tone(3, 3)
        g.set_tone(200, 0)
        for va, reg, slot, where in READS:
            if where == EDI:
                continue
            with self.subTest(read=hex(va)):
                self.assertEqual(g.run_read(va, where, 200, slot=3)[1], g.stock[slot])
                self.assertNotEqual(g.run_read(va, where, 3, slot=200)[1], g.stock[slot])

    def test_a_missing_or_wrong_sheet_is_the_games_own(self):
        cases = {
            "missing": {3: tone_files(3, skip=("male_bodies01.png", "female_actions00.png"))},
            "wrong size": {3: tone_files(3, size=(281, 650))},
            "no folder": {},
        }
        for what, tones in cases.items():
            g = Game(tones=tones, folders=[1, 2, 3])
            g.villager(5, "Kai", male=True)
            g.villager(6, "Ana", male=False)
            g.set_tone(5, 3)
            g.set_tone(6, 3)
            with self.subTest(case=what):
                self.assertEqual(g.run_read(0x4373B8, EDI, 5)[1], g.stock[0x3DFE8])       # male bodies
                self.assertEqual(g.run_read(0x437D08, VILLAGE, 6)[1], g.stock[0x3DFEC])   # female actions
                if what == "missing":
                    self.assertNotEqual(g.run_read(0x437441, EDI, 6)[1], g.stock[0x3DFE4])  # its other sheets
        g = Game(cells=(0, 0))
        g.villager(5, "Kai", male=True)
        g.set_tone(5, 3)
        self.assertEqual(g.run_read(0x4373B8, EDI, 5)[1], g.stock[0x3DFE8])
        self.assertEqual(g.run_read(0x4373B8, EDI, 5)[1], g.stock[0x3DFE8])
        self.assertEqual(len(g.built), 1)                                                  # tried once, never again
        g = Game()
        g.villager(5, "Kai", male=True)
        self.assertEqual(g.set_tone(5, 7), 1)                                              # no tone-7 sheets
        self.assertEqual(g.run_read(0x4373B8, EDI, 5)[1], g.stock[0x3DFE8])

    def test_the_sheets_are_opened_from_the_games_images_folder(self):
        g = Game()
        opened = []
        g.p.api_handlers["CreateFileW"], inner = (lambda p: (opened.append(p.wstring(p.arg(0))), inner(p))[1],
                                                  g.p.api_handlers["CreateFileW"])
        g.villager(5, "Kai", male=True)
        g.set_tone(5, 3)
        g.run_read(0x4374C0, EDI, 5)
        images = [path for path in opened if "\\Images\\" in path]
        self.assertEqual(images, [f"{GAME_DIR}\\Images\\vvfp_skin\\3\\male_bodies{xy}.png"
                                  for xy in ("00", "10", "01", "11")])

    def test_grey_hair_and_show_parents_ask_the_same(self):
        g = Game()
        rec = g.villager(9, "Kai", male=True)
        g.set_tone(9, 3)
        sheet_for, grey_for = g.p.exports["Vv1SkinToneSheetFor"], g.p.exports["Vv1SkinToneGreySheetFor"]
        body = g.p.call(sheet_for, [g.game, rec, g.stock[0x3DFE8]])
        self.assertNotEqual(body, g.stock[0x3DFE8])
        self.assertEqual(g.run_read(0x4373B8, EDI, 9)[1], body)                       # the sheet the read gives
        head = g.p.call(sheet_for, [g.game, rec, g.stock[0x3DFF8]])
        self.assertNotIn(head, (g.stock[0x3DFF8], body))
        self.assertIn(("vvfp_skin\\3\\male_heads.png", (7, 20)), g.built)
        grey = g.p.alloc(0x34)
        toned_grey = g.p.call(grey_for, [rec, 1, grey])
        self.assertNotIn(toned_grey, (grey, head))
        self.assertIn(("vvfp_skin\\3\\vvfp_grey_male_heads.png", (7, 20)), g.built)
        self.assertEqual(g.p.call(sheet_for, [g.game, rec, g.scratch]), g.scratch)   # not a villager sheet
        self.assertEqual(g.p.call(sheet_for, [g.game, rec + 4, g.stock[0x3DFF8]]), g.stock[0x3DFF8])
        g.set_tone(9, 0)
        self.assertEqual(g.p.call(sheet_for, [g.game, rec, g.stock[0x3DFF8]]), g.stock[0x3DFF8])
        self.assertEqual(g.p.call(grey_for, [rec, 1, grey]), grey)

    def test_the_tones_are_the_folders(self):
        self.assertEqual(Game(tones={}, folders=[]).p.export("Vv1SkinToneCount"), 8)
        self.assertEqual(Game(tones={}, folders=[1, 2, 3]).p.export("Vv1SkinToneCount"), 3)
        self.assertEqual(Game(tones={}, folders=[1, 2, 4, 5]).p.export("Vv1SkinToneCount"), 2)
        self.assertEqual(Game(tones={}, folders=range(1, 21)).p.export("Vv1SkinToneCount"), 15)
        g = Game(tones={}, folders=[1, 2])
        g.villager(1, "Kai", male=True)
        self.assertEqual(g.set_tone(1, 15), 1)                   # a tone above the folders is kept...
        self.assertEqual(g.run_read(0x4373B8, EDI, 1)[1], g.stock[0x3DFE8])   # ...and drawn as the game's own

    def test_founders_are_given_random_tones_through_the_draws(self):
        g = Game(tones={}, folders=[])
        for i in range(30):
            g.villager(i, f"Kai{i}", male=bool(i & 1))
        self.assertEqual(g.tone(0), -1)                            # not before the roster has settled
        for _ in range(8):
            g.run_read(0x437AED, VILLAGE, 1)
        tones = [g.tone(i) for i in range(30)]
        self.assertTrue(all(0 <= t <= 8 for t in tones), tones)
        self.assertGreaterEqual(len(set(tones)), 4)
        path = (f"C:\\Docs\\LDW\\Game\\Virtual Villagers Fun Patcher\\Save 1\\Data\\Skin Tones\\"
                f"Skin Tones - Save 1.dat").lower()
        self.assertEqual(len(g.disk.files[path]), 12 + 256 * 12)

    def test_without_the_dll_every_villager_is_the_games_own(self):
        p = Process(stock_exe(), None)
        for va, *_ in READS:
            self.assertEqual(p.read(va, 1), b"\x8B")


@_skip()
class AllOrNothing(unittest.TestCase):
    def test_one_changed_byte_installs_nothing(self):
        pe = pefile.PE(data=stock_exe())
        base = pe.OPTIONAL_HEADER.ImageBase
        checked = [va for va, *_ in READS[::7]] + [0x4391EA + 5, 0x437347, 0x43737D, 0x437604, 0x437796,
                                                   0x4388D4, 0x4388EB, 0x4392BC]
        for va in checked:
            exe = bytearray(stock_exe())
            exe[pe.get_offset_from_rva(va - base)] ^= 0xFF
            g = Game(bytes(exe))
            with self.subTest(va=hex(va)):
                self.assertEqual(g.p.export("Vv1SkinToneInstalled"), 0)
                for site, *_ in READS:
                    if not site <= va < site + 6:
                        self.assertEqual(g.p.read(site, 1), b"\x8B")

    def test_another_game_installs_nothing(self):
        g = Game(start=False)
        for game in (2, 3, 4, 5):
            g.p.export("VvfpStartup", game, 0)
            self.assertEqual(g.p.export("Vv1SkinToneInstalled"), 0)


# ---- Grey Hair at 55 asks it for every head -----------------------------------------------------------------

def _grey():
    import test_vv1_grey_hair as grey
    return grey


@unittest.skipUnless(have() and GREY_DLL.is_file(), "the emulator, the stock A New Home or Grey Hair is missing")
class GreyHairAsksIt(unittest.TestCase):
    """Grey Hair's DLL with a stand-in "VVFP Skin Tones.dll": its two exports answer sheets the test made."""

    def _game(self, with_skin: bool):
        grey = _grey()
        g = grey.Game()
        p = g.p
        module, young_fn, grey_fn = p.alloc(16), p.alloc(16), p.alloc(16)
        self.asked: list[tuple] = []
        self.toned_young, self.toned_grey = p.alloc(0x34), p.alloc(0x34)

        def young(p):
            self.asked.append(("young", p.arg(0), p.arg(1), p.arg(2)))
            return self.toned_young, 12

        def grey_sheet(p):
            self.asked.append(("grey", p.arg(0), p.arg(1), p.arg(2)))
            return self.toned_grey, 12

        p.stub(young_fn, young)
        p.stub(grey_fn, grey_sheet)
        p.api_handlers["GetModuleHandleA"] = lambda p: (
            module if with_skin and p.cstring(p.arg(0)) == "VVFP Skin Tones.dll" else 0, 4)
        p.api_handlers["GetProcAddress"] = lambda p: (
            {"Vv1SkinToneSheetFor": young_fn, "Vv1SkinToneGreySheetFor": grey_fn}.get(p.cstring(p.arg(1)), 0)
            if p.arg(0) == module else 0, 8)
        return grey, g

    def test_a_young_head_is_the_tones(self):
        grey, g = self._game(True)
        rec = g.villager(4, age=600, head=3, male=True)
        filled, entry, sprite = g.run_read(0x437405, grey.EDI, 4)
        self.assertEqual(filled, g.young[True])                    # the masks still see the young sheet
        self.assertEqual(sprite, self.toned_young)
        self.assertEqual(self.asked[-1], ("young", g.game, rec, g.young[True]))

    def test_a_grey_head_is_the_tones(self):
        grey, g = self._game(True)
        rec = g.villager(4, age=1500, head=3, male=False)
        filled, entry, sprite = g.run_read(0x43748E, grey.EDI, 4)
        self.assertEqual(sprite, self.toned_grey)
        self.assertEqual(self.asked[-1][0:3], ("grey", rec, 0))
        self.assertNotIn(self.asked[-1][3], (g.young[True], g.young[False]))     # Grey Hair's own grey sheet

    def test_show_parents_gets_the_same(self):
        grey, g = self._game(True)
        rec = g.villager(4, age=600, head=3, male=True)
        sheet_for = g.p.exports["Vv1GreyHairSheetFor"]
        self.assertEqual(g.p.call(sheet_for, [g.game, rec, g.young[True]]), self.toned_young)
        self.assertEqual(g.p.call(sheet_for, [g.game, rec, g.scratch]), g.scratch)

    def test_without_skin_tones_nothing_changes(self):
        grey, g = self._game(False)
        g.villager(4, age=600, head=3, male=True)
        self.assertEqual(g.run_read(0x437405, grey.EDI, 4)[2], g.young[True])
        g.villager(4, age=1500, head=3, male=True)
        sprite = g.run_read(0x437405, grey.EDI, 4)[2]
        self.assertNotIn(sprite, (g.young[True], self.toned_grey))
        self.assertEqual(self.asked, [])


# ---- births reach it ----------------------------------------------------------------------------------------

@unittest.skipUnless(HAVE_EMULATOR and stock_path().is_file() and ORIGINS_DLL.is_file(), "no emulator or Origins DLL")
class BirthsReachIt(unittest.TestCase):
    def test_vv1born_hands_every_birth_to_skin_tones(self):
        for with_skin in (True, False):
            p = Process(stock_exe(), ORIGINS_DLL)
            module, born = p.alloc(16), p.alloc(16)
            seen = []
            p.stub(born, lambda p: (seen.append((p.arg(0), p.arg(1))), 1)[1:] + (8,))
            p.api_handlers["GetModuleHandleA"] = lambda p: (
                module if with_skin and p.cstring(p.arg(0)) == "VVFP Skin Tones.dll" else 0, 4)
            p.api_handlers["GetProcAddress"] = lambda p: (
                born if p.arg(0) == module and p.cstring(p.arg(1)) == "Vv1SkinToneBorn" else 0, 8)
            p.api_handlers.setdefault("GetModuleHandleW", lambda p: (0x400000 if p.arg(0) == 0 else 0, 4))
            child, mother = p.alloc(STRIDE), p.alloc(STRIDE)
            p.export("Vv1Born", child, mother)               # the parentage companion is not in this game
            with self.subTest(with_skin=with_skin):
                self.assertEqual(seen, [(child, mother)] if with_skin else [])


# ---- the file and the rules, on real files ---------------------------------------------------------------------

class TheFileAndTheRules(unittest.TestCase):
    def test_the_harness_on_real_files(self):
        """native/vvfp_skin_tones/skin_tone_harness.c: random founders and arrivals, babies, twins, no father,
        Change Appearance, following the villager, copies, another village's file, a broken file, Start Over."""
        script = ROOT / "scripts" / "build_skin_tone_harness.ps1"
        result = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script)],
                                capture_output=True, text=True, timeout=600)
        if result.returncode != 0 and "cl.exe" in (result.stderr + result.stdout) and "not recognized" in (
                result.stderr + result.stdout):
            self.skipTest("the compiler is not installed")
        self.assertEqual(result.returncode, 0, result.stdout[-4000:] + result.stderr[-2000:])
        self.assertIn("failures: 0", result.stdout)
        self.assertGreaterEqual(result.stdout.count("[PASS]"), 60)


# ---- the other companions' side, in their sources ----------------------------------------------------------------

class TheOtherCompanions(unittest.TestCase):
    def read(self, relative: str) -> str:
        return (ROOT / relative).read_text(encoding="utf-8")

    def test_conceptions_reach_it_from_the_parentage_logs_hook(self):
        source = self.read("native/parentage_export/parentage_export.c")
        self.assertIn('GetModuleHandleA("VVFP Skin Tones.dll")', source)
        self.assertIn('"Vv1SkinToneConceived"', source)
        branch = source[source.index("} else if (g->father_kind == FATHER_BY_CAPTURE) {"):]
        self.assertIn("vv1_skin_bridge(mother, father);", branch[:branch.index("if (father == NULL)")])

    def test_show_parents_draws_the_childs_body_in_its_tone(self):
        source = self.read("native/vv1_parentage/vv1_parentage.c")
        self.assertIn('"Vv1SkinToneSheetFor"', source)
        self.assertRegex(source, r"void \*atlas = vv1_body_sheet\(gameobj, rec,")

    def test_change_appearance_keeps_and_logs_the_tone(self):
        source = self.read("native/vv1_origins_icons/vv1_origins_icons.c")
        ok = source[source.index("The skin tone (\"VVFP Skin Tones.dll\"'s own file), kept like the head look"):]
        self.assertIn("appearance_tone_api.set(appearance_state.villager, appearance_tone)", ok[:900])
        self.assertIn("Old skin tone: %s\\n  New skin tone: %s\\n", source)
        self.assertIn("forall_tone_api.set_many(forall_tone_record, forall_tone_value, forall_tone_count)", source)
        self.assertIn("vv1_skin_born(child, mother);", source)
        # The Lost Children's companion compiles this file too: none of it reaches its build.
        self.assertIn("#if !defined(VV_STORY_GAME) || VV_STORY_GAME == 1", source)

    def test_start_over_deletes_the_file(self):
        source = self.read("native/shared/save_reset.c")
        self.assertIn('#define SKIN_TONES_FORMAT DATA_FORMAT("Skin Tones", "Skin Tones")', source)
        vv1 = source[source.index("/* VV1 */"):source.index("/* VV2 */")]
        self.assertIn("SKIN_TONES_FORMAT", vv1)


# ---- the row ----------------------------------------------------------------------------------------------------

class TheRow(unittest.TestCase):
    def setUp(self):
        self.row = json.loads(FEATURE.read_text(encoding="utf-8"))

    def test_the_row(self):
        self.assertEqual(self.row["id"], ROW_ID)
        self.assertEqual(self.row["game_id"], "vv1")
        self.assertEqual(self.row["dependencies"], ["vv1_enable_origins_exclusive_features", "vv1_grey_hair"])
        self.assertEqual(self.row["patches"], [])
        self.assertEqual(len(self.row["runtime_detours"]), 35)
        self.assertEqual({int(d["va"], 16) for d in self.row["runtime_detours"]}, {va for va, *_ in READS})
        files = self.row["companion_files"]
        self.assertEqual(files, [{"source": "assets/skin_tones/VVFP Skin Tones.dll",
                                  "destination": "VVFP Skin Tones.dll",
                                  "sha256": hashlib.sha256(DLL.read_bytes()).hexdigest().upper()}])
        description = self.row["description"]
        self.assertIn("**Needs Enable Origins-Exclusive Features", description)
        self.assertIn("Grey Hair at 55", description)
        self.assertIn("Images\\vvfp_skin\\<tone>\\", description)
        self.assertIn("not for a release", description)

    def test_the_row_is_what_its_builder_writes(self):
        import build_vv1_skin_tones_feature as builder
        self.assertEqual(builder.row(hashlib.sha256(DLL.read_bytes()).hexdigest().upper()), self.row)

    def test_detour_stock_bytes_are_the_executables(self):
        if not stock_path().is_file():
            self.skipTest("no stock A New Home")
        pe = pefile.PE(data=stock_exe()) if HAVE_EMULATOR else None
        if pe is None:
            self.skipTest("no pefile")
        for d in self.row["runtime_detours"]:
            va = int(d["va"], 16)
            offset = pe.get_offset_from_rva(va - pe.OPTIONAL_HEADER.ImageBase)
            self.assertEqual(stock_exe()[offset:offset + 6].hex().upper(), d["stock_bytes"], d["va"])

    def test_started_from_the_second_word_and_released(self):
        self.assertEqual(patcher.STARTUP_LOADER_COMPANIONS_2[-1], "VVFP Skin Tones.dll")
        header = (ROOT / "native" / "shared" / "startup_companions_2.h").read_text(encoding="utf-8")
        self.assertIn('"VVFP Skin Tones.dll"', header)
        release = (ROOT / "scripts" / "build_release.py").read_text(encoding="utf-8")
        self.assertIn('"assets/skin_tones/VVFP Skin Tones.dll"', release)
        self.assertIn('"data/vv1_skin_tones_feature.json"', release)

    def test_the_bit_is_set_when_the_row_ships(self):
        bit = 1 << patcher.STARTUP_LOADER_COMPANIONS_2.index("VVFP Skin Tones.dll")
        features = patcher._attach_automatic_companions("vv1", patcher._selected_fun_patches(_build(), ["vv1_grey_hair", ROW_ID]))
        self.assertEqual(patcher._startup_loader_mask_2(features) & bit, bit)

    def test_the_guide_and_the_art_guide(self):
        import vv_how_to_use
        guide = vv_how_to_use.guide(vv_how_to_use.patch_key(ROW_ID), "Skin Tones (Draft)")
        self.assertLessEqual(len(guide.lines), vv_how_to_use.MAX_LINES)
        self.assertTrue(all(len(line) <= vv_how_to_use.MAX_LINE_CHARS for line in guide.lines))
        self.assertLessEqual(sum(len(line) for line in guide.lines), vv_how_to_use.MAX_GUIDE_CHARS)
        art = (ROOT / "docs" / "skin-tones-art-guide.md").read_text(encoding="utf-8")
        for name, (across, down), (w, h) in KINDS.values():
            self.assertIn(name, art)
            self.assertIn(f"{w} x {h}", art)
        self.assertIn("vvfp_grey_male_heads.png", art)
        self.assertIn("Images\\vvfp_skin\\1\\", art)


if __name__ == "__main__":
    unittest.main()
