"""Grey Hair at 55 (A New Home): a villager of 55 or more is drawn from a grey head sheet
("VVFP VV1 Grey Hair.dll", native/vv1_grey_hair; the owner, 2026-10-28).

The DLL runs in an emulator on the stock executable (and on the executables the patcher renders, in every
population mode), and the game's own code runs from each of the 29 reads of the head sheets to the draw it
feeds, where the sprite the engine is handed is read:

* age 1,099 is drawn from the young sheet, 1,100 and more from the grey sheet of the same sex, at every one
  of the 29 reads (the Details portrait, a dialog's villager figure, the village, the map), reaching the
  engine draw 0x408AF0 or 0x408740 the stock game reaches;
* the register the read fills still holds the young sheet (the Origins mask hooks look for it);
* head 19, the Golden Child's, follows the same rule (young at 1,099, grey at 1,100); the Golden Child
  himself is put back to 100 units by the game's own age tick, so in play he never turns grey;
* no byte of any villager record is written: the head value stays what it was;
* a draw of the young sheet no read announced, and a second draw after the first, stay young;
* a missing, wrong-sized or unloadable grey sheet keeps that sex young;
* all or nothing: one changed byte anywhere the DLL checks and nothing is written;
* the Origins mask hooks of a full build pass the young sheet on and the head is still drawn grey;
* Vv1GreyHairSheetFor, which Show Parents asks before drawing a child's head again over the parents, gives
  the same grey sheet for a villager drawn grey and the sprite it was given otherwise;
* the art: a sheet of the wrong size is refused, the preview strips are the sheets' column 5, and the
  release ships the companion, both sheets and the feature manifest.

The live effect in a running game is NOT verified here.
"""
from __future__ import annotations

import functools
import io
import struct
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT / "scripts"))

import vv_fun_patcher as patcher  # noqa: E402

try:
    import pefile  # noqa: F401
    from story_emulator import STACK_TOP, Process
    from unicorn import UC_HOOK_CODE

    HAVE_EMULATOR = True
except ImportError:  # pragma: no cover - environment dependent
    HAVE_EMULATOR = False
    STACK_TOP = 0

try:
    from PIL import Image

    import build_vv1_grey_hair_art as art

    HAVE_PIL = True
except ImportError:  # pragma: no cover - environment dependent
    HAVE_PIL = False

DLL = ROOT / "assets" / "vv1_grey_hair" / "VVFP VV1 Grey Hair.dll"
FEATURE = ROOT / "data" / "vv1_grey_hair_feature.json"
STRIDE, COUNT = 0x3D8, 256
MALE_HEADS, FEMALE_HEADS, DRAW_ORDER = 0x3DFF8, 0x3DFF4, 0x3DBDC
REC_AGE, REC_SEX, REC_HEAD = 0x348, 0x350, 0x360
ALLOC, CTOR = 0x44AF03, 0x40A070
ENGINES = {0x408AF0: 0x408AF7, 0x408740: 0x408747}
GAMEOBJ_SIZE = 0x3E100
INVALID = 0xFFFFFFFF

# (read, destination register, man's sheet, where the villager is, the engine draw it feeds)
EDI, VILLAGE, MAP = "edi", "village", "map"
READS = (
    (0x437405, "ecx", True, EDI, 0x408AF0), (0x43748E, "ecx", False, EDI, 0x408AF0),
    (0x4374E6, "eax", True, EDI, 0x408AF0), (0x437539, "edx", False, EDI, 0x408AF0),
    (0x4376B0, "ecx", True, EDI, 0x408AF0), (0x437735, "ecx", True, EDI, 0x408AF0),
    (0x43775D, "ecx", False, EDI, 0x408AF0),
    (0x437B9D, "edx", True, VILLAGE, 0x408AF0), (0x437D73, "edx", False, VILLAGE, 0x408AF0),
    (0x437E9B, "edx", True, VILLAGE, 0x408AF0), (0x437FA1, "edx", False, VILLAGE, 0x408AF0),
    (0x43812F, "ecx", True, VILLAGE, 0x408740), (0x438140, "ecx", False, VILLAGE, 0x408740),
    (0x438265, "ecx", True, VILLAGE, 0x408740), (0x4382D7, "ecx", False, VILLAGE, 0x408740),
    (0x43836C, "ecx", True, VILLAGE, 0x408740), (0x4383C2, "ecx", False, VILLAGE, 0x408740),
    (0x4385D9, "ecx", False, VILLAGE, 0x408740), (0x438766, "ecx", True, VILLAGE, 0x408740),
    (0x4387BA, "ecx", False, VILLAGE, 0x408740),
    (0x438BF3, "ecx", False, MAP, 0x408AF0), (0x438D23, "ecx", True, MAP, 0x408AF0),
    (0x438DDB, "eax", False, MAP, 0x408AF0), (0x438E73, "ecx", True, MAP, 0x408AF0),
    (0x438EE0, "ecx", False, MAP, 0x408AF0), (0x439052, "eax", True, MAP, 0x408AF0),
    (0x4390D7, "ecx", False, MAP, 0x408AF0), (0x4391CF, "eax", True, MAP, 0x408AF0),
    (0x439249, "eax", False, MAP, 0x408AF0),
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
    """The first 24 bytes of a PNG of that size (all the DLL reads)."""
    return (b"\x89PNG\r\n\x1a\n" + struct.pack(">I", 13) + b"IHDR" + struct.pack(">II", width, height)
            + b"\x08\x06\x00\x00\x00")


class Stop(Exception):
    pass


class Game:
    """The stock (or a rendered) executable with the DLL installed, a village in memory, the grey sheets
    answered by the test, and every engine draw's sprite recorded instead of drawn."""

    def __init__(self, exe: bytes | None = None, *, sheets=None, cells=(40, 65), dll: bool = True,
                 start: bool = True):
        self.p = Process(exe if exe is not None else stock_exe(), DLL if dll else None)
        self.sheets = {"male": png_header(280, 1300), "female": png_header(280, 1300)} if sheets is None else sheets
        self.cells = cells
        self.built: list[str] = []
        self.opened: list[str] = []
        self.handles: dict[int, bytes] = {}
        self.p.api_handlers.update(CreateFileW=self._create, ReadFile=self._read, CloseHandle=lambda p: (1, 4))
        self.p.stub(ALLOC, lambda p: (p.alloc(p.arg(0)), 0))
        self.p.stub(CTOR, self._ctor)
        self.scratch = self.p.alloc(0x2000)
        self.game = self.p.alloc(GAMEOBJ_SIZE)
        for field in range(0x3DF00, 0x3E040, 4):         # every sprite and helper pointer: somewhere harmless
            self.p.put32(self.game + field, self.scratch)
        self.young = {True: self.p.alloc(0x34), False: self.p.alloc(0x34)}
        self.p.put32(self.game + MALE_HEADS, self.young[True])
        self.p.put32(self.game + FEMALE_HEADS, self.young[False])
        self.p.put32(self.scratch, self.scratch + 0x100)  # the renderer holder's surface
        self.draws: list[tuple[int, int]] = []
        for entry, resume in ENGINES.items():
            self.p.stub(resume, functools.partial(self._draw, entry))
        if dll and start:
            self.p.export("VvfpStartup", 1, 0)

    # -- the APIs and routines the DLL reaches ----------------------------------------------------
    def _create(self, p):
        path = p.wstring(p.arg(0))
        self.opened.append(path)
        for sex, data in self.sheets.items():
            if data is not None and path.endswith(f"\\Images\\vvfp_grey_{sex}_heads.png"):
                handle = 0x500 + len(self.handles)
                self.handles[handle] = data
                return handle, 28
        return INVALID, 28

    def _read(self, p):
        data = self.handles[p.arg(0)][: p.arg(2)]
        p.write(p.arg(1), data)
        p.put32(p.arg(3), len(data))
        return 1, 20

    def _ctor(self, p):
        this = p.reg("ecx")
        self.built.append(p.cstring(p.arg(0)))
        p.put32(this + 0x08, p.arg(1))
        p.put32(this + 0x0C, p.arg(2))
        p.put32(this + 0x10, self.cells[0])
        p.put32(this + 0x14, self.cells[1])
        return this, 12

    def _draw(self, entry, p):
        # At the entry's resume the displaced `sub esp, 0x10` has run: the first argument is at esp+0x14.
        self.draws.append((entry, p.u32(p.reg("esp") + 0x14)))
        p.mu.emu_stop()
        p.set_reg("esp", p.reg("esp") + 0x10)
        return 0, 0x1C

    # -- the village -------------------------------------------------------------------------------
    def record(self, index: int) -> int:
        return self.game + index * STRIDE

    def villager(self, index: int, *, age: int, head: int, male: bool) -> int:
        rec = self.record(index)
        self.p.put32(rec + 0x28, 1)
        self.p.put32(rec + REC_AGE, age)
        self.p.put32(rec + REC_SEX, 1 if male else 2)
        self.p.put32(rec + REC_HEAD, head)
        return rec

    def run_read(self, va: int, where: str, index: int, *, slot: int = 7) -> tuple[int, int, int]:
        """Run the game from the read at `va` for record `index` (drawn `slot`-th in its loop) to the
        engine draw it feeds.  Returns (the register the read filled, the engine, the sprite drawn)."""
        p = self.p
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
        reg = next(r for v, r, _, _, _ in READS if v == va)
        filled: list[int] = []
        hook = p.mu.hook_add(UC_HOOK_CODE, lambda mu, address, size, data: filled.append(p.reg(reg)),
                             begin=va + 6, end=va + 6)
        before = len(self.draws)
        try:
            p.mu.emu_start(va, 0, count=4000)
        finally:
            p.mu.hook_del(hook)
        if len(self.draws) != before + 1 or len(filled) != 1:
            raise AssertionError(f"the read at {va:#x} reached no engine draw (stopped at {p.reg('eip'):#x})")
        entry, sprite = self.draws[-1]
        return filled[0], entry, sprite


def _skip():
    return unittest.skipUnless(have(), "unicorn/pefile, the stock A New Home or the DLL is missing")


@_skip()
class EveryRead(unittest.TestCase):
    def test_installs_31_detours(self):
        g = Game()
        self.assertEqual(g.p.export("VvfpGreyHairInstalled"), 1)
        for va, *_ in READS:
            self.assertEqual(g.p.read(va, 1), b"\xE9", hex(va))
            self.assertEqual(g.p.read(va + 5, 1), b"\x90", hex(va))
        for entry in ENGINES:
            self.assertEqual(g.p.read(entry, 1), b"\xE9")
            self.assertEqual(g.p.read(entry + 5, 2), b"\x90\x90")

    def test_1099_young_1100_grey_at_every_read(self):
        g = Game()
        for va, reg, male, where, engine in READS:
            for age, grey in ((0, False), (279, False), (1099, False), (1100, True), (1101, True), (2400, True)):
                for head in (0, 7, 18):
                    with self.subTest(read=hex(va), age=age, head=head):
                        rec = g.villager(42, age=age, head=head, male=male)
                        before = g.p.read(rec, STRIDE)
                        filled, entry, sprite = g.run_read(va, where, 42)
                        self.assertEqual(filled, g.young[male])            # the game's register: young
                        self.assertEqual(entry, engine)
                        if grey:
                            self.assertNotIn(sprite, (g.young[True], g.young[False], g.scratch))
                            self.assertEqual(g.p.u32(sprite + 0x10), 40)
                        else:
                            self.assertEqual(sprite, g.young[male])
                        self.assertEqual(g.p.read(rec, STRIDE), before)    # no record byte written
        self.assertEqual(sorted(g.built), ["vvfp_grey_female_heads.png", "vvfp_grey_male_heads.png"])

    def test_each_sex_gets_its_own_grey_sheet(self):
        g = Game()
        sprites = {}
        for va, reg, male, where, engine in READS:
            g.villager(9, age=1500, head=3, male=male)
            sprites.setdefault(male, set()).add(g.run_read(va, where, 9)[2])
        self.assertEqual(len(sprites[True]), 1)
        self.assertEqual(len(sprites[False]), 1)
        self.assertNotEqual(sprites[True], sprites[False])

    def test_head_19_follows_the_same_rule(self):
        """The owner, 2026-10-28: the Golden Child's head 19 is no exception -- young at 1,099, grey at
        1,100 -- for a man or a woman, at every read.  (The Golden Child himself never reaches 1,100.)"""
        g = Game()
        for va, reg, male, where, engine in READS:
            for age, grey in ((1099, False), (1100, True)):
                g.villager(5, age=age, head=19, male=male)
                sprite = g.run_read(va, where, 5)[2]
                with self.subTest(read=hex(va), age=age):
                    self.assertEqual(sprite == g.young[male], not grey)

    def test_the_golden_child_never_reaches_1100(self):
        """The age tick puts the Golden Child (family 199 at +0x36C) back to 100 units, shown and processed
        (0x42EB73..0x42EB8E, EBP 0xC7 from 0x42E957), so in play he is always drawn young."""
        exe = stock_exe()
        self.assertEqual(exe[0x42E957 - 0x400000:0x42E957 - 0x400000 + 5], bytes.fromhex("BDC7000000"))
        g = Game()
        p = g.p
        array = p.alloc(STRIDE * 8)
        rec = array + 3 * STRIDE
        p.put32(rec + 0x36C, 0xC7)
        p.put32(rec + REC_AGE, 1500)
        p.put32(rec + 0x34C, 1500)
        holder = p.alloc(16)
        p.put32(holder + 4, array)
        p.set_reg("esi", holder)
        p.set_reg("edi", 3 * STRIDE)
        p.set_reg("ebp", 0xC7)
        p.run(0x42EB70, 0x42EB98)
        self.assertEqual(p.u32(rec + REC_AGE), 100)
        self.assertEqual(p.u32(rec + 0x34C), 100)

    def test_the_villager_drawn_is_the_one_the_loop_names(self):
        g = Game()
        g.villager(3, age=2000, head=1, male=True)
        g.villager(200, age=100, head=1, male=True)
        for va, reg, male, where, engine in READS:
            if not male or where == EDI:
                continue
            with self.subTest(read=hex(va)):
                self.assertEqual(g.run_read(va, where, 200, slot=3)[2], g.young[True])
                self.assertNotEqual(g.run_read(va, where, 3, slot=200)[2], g.young[True])

    def test_an_unannounced_or_second_draw_stays_young(self):
        g = Game()
        g.villager(1, age=2000, head=2, male=True)
        self.assertNotEqual(g.run_read(0x437405, EDI, 1)[2], g.young[True])
        # The same sheet drawn again with no read in between: young (the remembered read is used once).
        esp = STACK_TOP - 0x4000
        g.p.set_reg("esp", esp)
        for i, value in enumerate((0, g.young[True], 120, 258, 2, 5, 100, 1)):
            g.p.put32(esp + 4 * i, value)
        g.p.set_reg("ecx", g.scratch)
        g.p.mu.emu_start(0x408AF0, 0, count=100)
        self.assertEqual(g.draws[-1], (0x408AF0, g.young[True]))

    def test_without_the_dll_every_head_is_young(self):
        g = Game(dll=False)
        for va, reg, male, where, engine in READS[::4]:
            g.villager(4, age=2000, head=2, male=male)
            self.assertEqual(g.run_read(va, where, 4)[2], g.young[male])


@_skip()
class TheArtInTheGame(unittest.TestCase):
    def _sprite(self, g, male=True):
        g.villager(2, age=1200, head=2, male=male)
        return g.run_read(0x437405 if male else 0x43748E, EDI, 2)[2]

    def test_a_missing_sheet_keeps_that_sex_young(self):
        g = Game(sheets={"male": None, "female": png_header(280, 1300)})
        self.assertEqual(self._sprite(g, True), g.young[True])
        self.assertNotEqual(self._sprite(g, False), g.young[False])
        self.assertEqual(g.built, ["vvfp_grey_female_heads.png"])

    def test_a_sheet_of_the_wrong_size_is_never_used(self):
        for width, height in ((281, 1300), (280, 1299), (560, 2600), (40, 65)):
            g = Game(sheets={"male": png_header(width, height), "female": png_header(width, height)})
            with self.subTest(size=(width, height)):
                self.assertEqual(self._sprite(g, True), g.young[True])
                self.assertEqual(self._sprite(g, False), g.young[False])
                self.assertEqual(g.built, [])
        g = Game(sheets={"male": b"GIF89a" + bytes(18), "female": png_header(280, 1300)[:20]})
        self.assertEqual(self._sprite(g, True), g.young[True])
        self.assertEqual(self._sprite(g, False), g.young[False])

    def test_a_sheet_the_game_does_not_load_as_40_by_65_is_never_used(self):
        g = Game(cells=(0, 0))
        self.assertEqual(self._sprite(g, True), g.young[True])
        self.assertEqual(self._sprite(g, True), g.young[True])
        self.assertEqual(g.built, ["vvfp_grey_male_heads.png"])           # tried once, never again

    def test_the_sheet_is_opened_from_the_games_images_folder(self):
        g = Game()
        self._sprite(g, True)
        self.assertEqual(g.opened, ["C:\\Games\\Village\\Images\\vvfp_grey_male_heads.png"])

    def test_change_appearance_asks_the_same_rule(self):
        g = Game()
        wanted = g.p.exports["Vv1GreyHairWanted"]
        for age, head, male, expect in ((1099, 3, True, 0), (1100, 3, True, 1), (1099, 19, True, 0),
                                        (1100, 19, True, 1), (1100, 19, False, 1), (3000, 6, False, 1),
                                        (50, 6, False, 0)):
            rec = g.villager(11, age=age, head=head, male=male)
            with self.subTest(age=age, head=head, male=male):
                self.assertEqual(g.p.call(wanted, [rec]), expect)
        self.assertEqual(g.built, [])                                     # asking never builds a sprite
        g = Game(sheets={"male": None, "female": None})
        self.assertEqual(g.p.call(g.p.exports["Vv1GreyHairWanted"], [g.villager(1, age=2000, head=1, male=True)]), 0)
        exe = bytearray(stock_exe())                                      # nothing installed: never grey
        exe[0x437405 - 0x400000] ^= 0xFF
        g = Game(bytes(exe))
        self.assertEqual(g.p.call(g.p.exports["Vv1GreyHairWanted"], [g.villager(1, age=2000, head=1, male=True)]), 0)

    def test_show_parents_asks_the_same_sheet(self):
        """Vv1GreyHairSheetFor(gameobj, record, sprite), which Show Parents asks before it draws a child's
        portrait head again over the parents (tests/test_vv1_grey_hair_show_parents.py runs that draw): the
        grey sheet of the young sheet's sex when the villager is drawn grey, else the sprite it was given."""
        g = Game()
        sheet_for = g.p.exports["Vv1GreyHairSheetFor"]
        greys = {}
        for male in (True, False):
            g.villager(2, age=1200, head=2, male=male)
            greys[male] = g.run_read(0x437405 if male else 0x43748E, EDI, 2)[2]
        for age, male, sprite, expect in (
                (1100, True, g.young[True], greys[True]), (1100, False, g.young[False], greys[False]),
                (1099, True, g.young[True], g.young[True]), (5000, False, g.young[False], greys[False]),
                (1100, True, g.scratch, g.scratch),                    # not a head sheet: untouched
                (1100, True, 0, 0)):
            rec = g.villager(7, age=age, head=5, male=male)
            with self.subTest(age=age, male=male, sprite=hex(sprite)):
                self.assertEqual(g.p.call(sheet_for, [g.game, rec, sprite]), expect)
        rec = g.villager(7, age=2000, head=5, male=True)
        self.assertEqual(g.p.call(sheet_for, [g.game, rec + 4, g.young[True]]), g.young[True])   # not a record
        self.assertEqual(g.p.call(sheet_for, [g.game, g.record(256), g.young[True]]), g.young[True])
        self.assertEqual(g.p.call(sheet_for, [0, rec, g.young[True]]), g.young[True])
        g = Game(sheets={"male": None, "female": None})                    # no grey sheet: the young one
        rec = g.villager(7, age=2000, head=5, male=True)
        self.assertEqual(g.p.call(g.p.exports["Vv1GreyHairSheetFor"], [g.game, rec, g.young[True]]), g.young[True])
        g = Game(start=False)                                              # nothing installed: the young one
        rec = g.villager(7, age=2000, head=5, male=True)
        self.assertEqual(g.p.call(g.p.exports["Vv1GreyHairSheetFor"], [g.game, rec, g.young[True]]), g.young[True])


@_skip()
class AllOrNothing(unittest.TestCase):
    def test_one_changed_byte_installs_nothing(self):
        pe = pefile.PE(data=stock_exe())
        base = pe.OPTIONAL_HEADER.ImageBase
        checked = [va for va, *_ in READS[:3]] + [0x439249 + 5, 0x408AF0, 0x408746, 0x408740, 0x437347,
                                                  0x43737D, 0x437604, 0x437796, 0x4388D4, 0x4388EB, 0x4392BC]
        for va in checked:
            exe = bytearray(stock_exe())
            exe[pe.get_offset_from_rva(va - base)] ^= 0xFF
            g = Game(bytes(exe))
            with self.subTest(va=hex(va)):
                self.assertEqual(g.p.export("VvfpGreyHairInstalled"), 0)
                for site, *_ in READS:
                    if not site <= va < site + 6:
                        self.assertEqual(g.p.read(site, 2)[0], 0x8B)
                for entry in ENGINES:
                    if not entry <= va < entry + 7:
                        self.assertEqual(g.p.read(entry, 3), b"\x83\xEC\x10")

    def test_another_game_installs_nothing(self):
        g = Game(start=False)
        for game in (2, 3, 4, 5):
            g.p.export("VvfpStartup", game, 0)
            self.assertEqual(g.p.export("VvfpGreyHairInstalled"), 0)


# ---- the patcher: every population mode, and beside every other patch ---------------------------------

def _closure(feature_id: str, catalog: dict, into=None, seen=None) -> list[str]:
    into = [] if into is None else into
    seen = set() if seen is None else seen
    if feature_id in seen:
        return into
    seen.add(feature_id)
    raw = catalog[feature_id].raw
    needs = [n["id"] for n in raw.get("needs_on") or [] if n["id"] in catalog]
    for dependency in list(raw.get("dependencies") or []) + needs:
        _closure(dependency, catalog, into, seen)
    if feature_id not in into:
        into.append(feature_id)
    return into


@functools.lru_cache(maxsize=None)
def _catalog() -> dict:
    return {p.id: p for p in patcher.load_fun_patches()}


def _public_vv1() -> list[str]:
    return [p.id for p in patcher.load_fun_patches()
            if p.game_id == "vv1" and not p.raw.get("catalog_hidden") and p.raw.get("catalog_enabled", True)
            and p.raw.get("enabled", True) and p.id not in patcher.ALTERNATIVE_FUN_PATCH_IDS]


@functools.lru_cache(maxsize=None)
def _rendered(mode: str, everything: bool) -> tuple[bytes, tuple[str, ...]]:
    selection = _public_vv1() if everything else _closure("vv1_grey_hair", _catalog())
    data, applied = patcher.render_patched_bytes(stock_path(), _build(), mode, list(selection))
    features = patcher._attach_automatic_companions("vv1", patcher._selected_fun_patches(_build(), list(selection)))
    patcher._finalize_published_bytes(data, _build(), features, applied)
    return bytes(data), tuple(f.id for f in features)


MODES = ("stock", "collection_progression", "immediate_fixed")


class TheRow(unittest.TestCase):
    def test_on_by_default_in_the_catalog(self):
        row = _catalog()["vv1_grey_hair"]
        self.assertEqual(row.game_id, "vv1")
        self.assertTrue(row.raw["enabled"] and row.raw["catalog_enabled"] and not row.raw["catalog_hidden"])
        self.assertNotIn("vv1_grey_hair", getattr(patcher, "DEFAULT_OFF_FUN_PATCH_IDS", ()))
        self.assertIn("**On by default.**", row.raw["description"])
        self.assertIn("**Not yet seen in a running game.**", row.raw["description"])
        self.assertEqual(row.raw["patches"], [])
        self.assertEqual(len(row.raw["runtime_detours"]), 31)
        self.assertEqual({d["va"] for d in row.raw["runtime_detours"]},
                         {f"0x{va:06X}" for va, *_ in READS} | {"0x408AF0", "0x408740"})

    def test_started_from_the_second_word(self):
        self.assertEqual(patcher.STARTUP_LOADER_COMPANIONS_2[2], "VVFP VV1 Grey Hair.dll")
        header = (ROOT / "native" / "shared" / "startup_companions_2.h").read_text(encoding="utf-8")
        self.assertLess(header.index("VVFP Appearance Rolls.dll"), header.index("VVFP VV1 Grey Hair.dll"))
        bit = 1 << patcher.STARTUP_LOADER_COMPANIONS_2.index("VVFP VV1 Grey Hair.dll")
        features = patcher._attach_automatic_companions(
            "vv1", patcher._selected_fun_patches(_build(), _closure("vv1_grey_hair", _catalog())))
        self.assertEqual(patcher._startup_loader_mask_2(features) & bit, bit)

    def test_the_pins_match_the_files(self):
        import hashlib
        for item in _catalog()["vv1_grey_hair"].raw["companion_files"]:
            with self.subTest(item=item["source"]):
                self.assertEqual(hashlib.sha256((ROOT / item["source"]).read_bytes()).hexdigest().upper(),
                                 item["sha256"])
        destinations = [i["destination"] for i in _catalog()["vv1_grey_hair"].raw["companion_files"]]
        self.assertEqual(destinations, ["VVFP VV1 Grey Hair.dll", "Images/vvfp_grey_male_heads.png",
                                        "Images/vvfp_grey_female_heads.png"])

    @unittest.skipUnless(have(), "unicorn/pefile, the stock A New Home or the DLL is missing")
    def test_installs_in_every_mode_alone_and_beside_every_other_patch(self):
        for mode in MODES:
            for everything in (False, True):
                exe, features = _rendered(mode, everything)
                with self.subTest(mode=mode, everything=everything):
                    self.assertIn("vv1_grey_hair", features)
                    g = Game(exe)
                    self.assertEqual(g.p.export("VvfpGreyHairInstalled"), 1)
                    g.villager(6, age=1300, head=8, male=False)
                    self.assertNotEqual(g.run_read(0x438140, VILLAGE, 6)[2], g.young[False])
                    g.villager(6, age=1099, head=8, male=False)
                    self.assertEqual(g.run_read(0x438140, VILLAGE, 6)[2], g.young[False])

    @unittest.skipUnless(have(), "unicorn/pefile, the stock A New Home or the DLL is missing")
    def test_through_the_origins_mask_hooks(self):
        """A full build routes the Details portrait's head calls through the Origins wrapper and the
        shared 0x409410 thunk through its village mask hook (scripts/build_vv1_origins_feature.py): the
        read still hands them the young sheet, and the head reaching the engine is grey."""
        exe, _ = _rendered("collection_progression", True)
        self.assertNotEqual(exe[0x9410:0x9415], stock_exe()[0x9410:0x9415])       # the Origins hook is in
        g = Game(exe)
        for va, where, male in ((0x437405, EDI, True), (0x437B9D, VILLAGE, True), (0x438D23, MAP, True)):
            with self.subTest(read=hex(va)):
                g.villager(12, age=1100, head=4, male=male)
                filled, engine, sprite = g.run_read(va, where, 12)
                self.assertEqual(filled, g.young[male])
                self.assertEqual(engine, 0x408AF0)
                self.assertNotEqual(sprite, g.young[male])


# ---- the art --------------------------------------------------------------------------------------------

@unittest.skipUnless(HAVE_PIL, "Pillow is missing")
class TheArt(unittest.TestCase):
    def test_a_sheet_of_the_wrong_size_is_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            for size in ((281, 1300), (280, 1299), (560, 2600), (40, 65)):
                path = Path(folder) / f"sheet_{size[0]}_{size[1]}.png"
                Image.new("RGBA", size).save(path)
                with self.subTest(size=size), self.assertRaises(ValueError):
                    art.load_sheet(path)
            path = Path(folder) / "sheet.gif"
            Image.new("RGB", (280, 1300)).save(path, format="GIF")
            with self.assertRaises(ValueError):
                art.load_sheet(path)
            path = Path(folder) / "right.png"
            Image.new("RGBA", (280, 1300)).save(path)
            self.assertEqual(art.load_sheet(path).size, (280, 1300))

    def test_the_shipped_sheets_and_the_references_are_the_stock_layout(self):
        for path in art.SHEETS.values():
            with self.subTest(path=path.name):
                self.assertEqual(art.load_sheet(path).mode, "RGBA")
        for sex, letter in (("male", "m"), ("female", "f")):
            reference = art.load_sheet(art.ART / f"young_{sex}_reference.png")
            stock = Image.open(ROOT / "native" / "vv1_origins_icons" / "appearance" / f"head_{letter}.bmp")
            self.assertEqual(art.preview_strip(reference).tobytes(), stock.convert("RGB").tobytes())

    def test_the_preview_strips_are_the_shipped_sheets(self):
        for sex, path in art.SHEETS.items():
            with self.subTest(sex=sex):
                built = Image.open(art.PREVIEWS[sex]).convert("RGB")
                self.assertEqual(built.size, (40, 1300))
                self.assertEqual(built.tobytes(), art.preview_strip(art.load_sheet(path)).tobytes())

    def test_the_release_ships_the_art(self):
        import build_release
        for name in ("assets/vv1_grey_hair/VVFP VV1 Grey Hair.dll", "assets/vv1_grey_hair/vvfp_grey_male_heads.png",
                     "assets/vv1_grey_hair/vvfp_grey_female_heads.png", "data/vv1_grey_hair_feature.json"):
            self.assertIn(name, build_release.FILES)



if __name__ == "__main__":
    unittest.main()
