"""Picture Studio's Everything tab, A New Home: src/vv_assets_vv1.py proven against the game's own code.

* The sprite table: a scan of the whole stock executable for every call to the engine's sprite constructors
  (0x40A070, 0x409ED0, 0x40A0F0), the button constructor 0x4019B0, the font constructor 0x402080 and the sheet
  loader 0x40A530, every argument read from the code; every call must be one the table holds (or one of the
  named indirect ones), and every table entry must come from a call.  The island's tile names are taken from the
  game's own tile loop 0x4115C0, run in Unicorn.
* The cell cut: 0x409F90 run on every sheet the game's constructors built (the sheet loader 0x40A530 replaced by
  one that gives each file its real size), for every cell and past the end, against pi.Atlas.cell.
* Every composed asset: the game's own draw function run in Unicorn (tests/story_emulator.Process) on objects
  built with the game's own constructors and the state chosen, every blit it makes (0x403D70 scaled / faded,
  0x403D00 plain: sheet, source rectangle, place, scale, surface alpha) required to equal the module's plan, in
  order.  The plan is computed from the sheets' sizes alone.

The emulated classes need the stock executable, Unicorn and pefile (skipped on CI); the sprite-table scan also
needs capstone; the art test needs research/game-images.  The rest needs nothing.
"""
from __future__ import annotations

import random
import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import vv_picture_image as pi  # noqa: E402
import vv_pictures_assets as va  # noqa: E402
import vv_assets_vv1 as vv1  # noqa: E402

try:
    import pefile  # noqa: F401
    from unicorn.x86_const import UC_X86_REG_FPCW
    from story_emulator import API_STUBS, Process
    HAVE_UNICORN = True
except ImportError:                                    # CI: no Unicorn
    HAVE_UNICORN = False
try:
    import capstone  # noqa: F401
    HAVE_CAPSTONE = True
except ImportError:
    HAVE_CAPSTONE = False

EXE = ROOT / "research" / "stock-executables" / vv1.EXE_NAME
ART = ROOT / "research" / "game-images" / "Virtual Villagers - A New Home" / "Images"
EMULATOR = HAVE_UNICORN and EXE.is_file()
WHY = "the stock A New Home executable (and Unicorn) are needed"

# The size of every picture in A New Home's Images folder (152 files), and of the patcher's art.
SIZES = {
    "arrowglow.png": (100, 100), "arrowglowdown.png": (100, 100), "arrowleftglow.png": (100, 100),
    "arrowrightglow.png": (100, 100), "BambooMeterFrame1.png": (320, 30), "berry1.png": (29, 64),
    "berry2.png": (72, 39), "berry3.png": (53, 52), "berry4.png": (35, 76), "berry5.png": (51, 61),
    "berry6.png": (41, 51), "berry7.png": (48, 43), "berry8.png": (36, 27), "berry9.png": (32, 23),
    "bfg_logo.png": (168, 168), "blink.png": (100, 10), "blockage.png": (132, 59), "boulder.png": (158, 108),
    "Boxshtfeat.png": (800, 600), "breeding.jpg": (288, 80), "bubble.png": (200, 20), "building.jpg": (288, 80),
    "butterflygreen.png": (100, 125), "buy_button.png": (304, 28), "bxshtBG.jpg": (800, 600),
    "bxshtBG.png": (800, 600), "canvas_bg.jpg": (800, 600), "carrying.png": (600, 25), "Checkbox.png": (48, 32),
    "CheckboxChecked.png": (48, 32), "checkmark.png": (32, 32), "CloudBack.png": (264, 20),
    "Cloudfront.png": (228, 48), "CloudMiddle.png": (264, 24), "credits.jpg": (639, 472),
    "crops_planted.png": (40, 23), "debris.png": (200, 20), "drum.png": (23, 34), "dust.png": (270, 30),
    "dust2.png": (270, 30), "empty1.png": (388, 32), "farm_after.png": (437, 192), "farming.jpg": (288, 80),
    "female_actions00.png": (360, 650), "female_actions01.png": (360, 650), "female_bodies00.png": (640, 650),
    "female_bodies01.png": (640, 650), "female_bodies10.png": (640, 650), "female_bodies11.png": (640, 650),
    "female_heads.png": (280, 1300), "focus_circle.png": (68, 64), "food1.png": (61, 17), "food2.png": (80, 40),
    "food3.png": (79, 52), "gamewin_bg.jpg": (800, 600), "garden_restored.png": (355, 347),
    "gh_logo.png": (190, 150), "graveflowers.png": (201, 46), "graves.png": (220, 44),
    "GreenDlgTileGrid.png": (576, 64), "hand.png": (54, 54), "hand_open.png": (54, 54),
    "healthBarbulb.png": (28, 28), "help1.jpg": (639, 472), "help2.jpg": (639, 472), "help3.jpg": (639, 472),
    "help4.jpg": (639, 472), "idol_uncarved.png": (98, 145), "info_button.png": (112, 28),
    "intro1_bg.png": (800, 600), "intro2_bg.png": (800, 600), "lagoon_restored.jpg": (297, 530),
    "Lavaglow.png": (152, 268), "ldwarialbold.png": (728, 40), "ldwBurweed27.png": (793, 54),
    "ldwLogo.png": (168, 178), "leftarrow.png": (120, 36), "LoadColor.png": (8, 30), "logo1.png": (300, 172),
    "main_BG.png": (800, 600), "main_detail_button.png": (345, 52), "main_wide_button.png": (384, 32),
    "main_wide_button2.png": (388, 32), "male_actions00.png": (360, 650), "male_actions01.png": (360, 650),
    "male_bodies00.png": (640, 650), "male_bodies01.png": (640, 650), "male_bodies10.png": (640, 650),
    "male_bodies11.png": (640, 650), "male_heads.png": (280, 1300),
    **{f"MapX{x}Y{y}.jpg": (512, 512) for x in range(4) for y in range(4)},
    "medicine.jpg": (288, 80), "mgs_logo.png": (289, 39), "MS_Button_01.png": (364, 52),
    "MS_Button_02.png": (256, 50), "MS_Button_03.png": (300, 60), "MS_Button_04.png": (288, 40),
    "OrangeDlgTileGrid.png": (576, 64), "overview_bg.jpg": (800, 600), "overview_bg.png": (800, 600),
    "peep_shadow1.png": (68, 64), "ProcessedHorizBambStrip3.png": (80, 12),
    "ProcessedVertBambStrip1.png": (120, 8), "puzzle_covers.jpg": (640, 472), "puzzle_solved.jpg": (640, 472),
    "puzzles_bg.png": (800, 600), "radioblank.png": (32, 32), "radioselected.png": (32, 32),
    "rainbow.png": (500, 25), "research_button.png": (172, 28), "rightarrow.png": (120, 36),
    "ripple.png": (260, 65), "scaffolding.png": (97, 45), "science.jpg": (288, 80), "skelly.png": (240, 65),
    "sliderhandle.png": (16, 32), "smallHut.png": (179, 151), "sparklestrip.png": (250, 25),
    "sparklestrip2.png": (120, 12), "spirituality.jpg": (288, 80), "SPLASH_BG.jpg": (800, 600),
    "StatusBar.png": (16, 16), "StatusBarSliceB.png": (16, 16), "StatusBarSliceR.png": (16, 16),
    "stoolfood.png": (35, 8), "tchest.png": (71, 59), "tech_bg.jpg": (800, 600), "tech_bg.png": (800, 600),
    "temple_rebuilt.jpg": (303, 241), "tools2.png": (49, 38), "tools3.png": (89, 47),
    "ultra_wide_button.png": (1170, 32), "VD_BG.jpg": (800, 600), "VD_BG.png": (800, 600),
    "waves_proto.png": (500, 50), "WideSlider2.png": (260, 32), "yellow_sparkle.png": (300, 30),
}
GAME_FILES = sorted(SIZES, key=str.casefold)
PATCHER_SIZES = {"mask_atlas.png": (280, 800), "vvfp_grey_male_heads.png": (280, 1300),
                 "vvfp_grey_female_heads.png": (280, 1300), "golden_mushroom.png": (29, 22)}
NEVER_LOADED = {"bfg_logo.png", "buy_button.png", "bxshtBG.jpg", "canvas_bg.jpg", "Checkbox.png",
                "CheckboxChecked.png", "dust.png", "gh_logo.png", "main_wide_button.png", "mgs_logo.png",
                "overview_bg.png", "ProcessedHorizBambStrip3.png", "ProcessedVertBambStrip1.png", "StatusBar.png",
                "tech_bg.jpg", "VD_BG.jpg"}


def size_of(name: str) -> tuple[int, int]:
    for table in (SIZES, PATCHER_SIZES):
        for k, v in table.items():
            if k.casefold() == name.casefold():
                return v
    raise KeyError(name)


class SizeSource:
    """Only the pictures' sizes (a PNG header each, the JPEGs too): enough to plan, not to draw."""

    def read(self, name: str) -> bytes | None:
        try:
            w, h = size_of(name)
        except KeyError:
            return None
        return pi.PNG_MAGIC + struct.pack(">I4sII", 13, b"IHDR", w, h) + bytes(5)

    def names(self) -> list[str]:
        return list(GAME_FILES)


def f32bits(value: float) -> int:
    return struct.unpack("<I", struct.pack("<f", value))[0]


def bits_f32(value: int) -> float:
    return struct.unpack("<f", struct.pack("<I", value & 0xFFFFFFFF))[0]


def signed(value: int) -> int:
    value &= 0xFFFFFFFF
    return value - (1 << 32) if value & 0x80000000 else value


def keys(plan) -> list[tuple]:
    return [d.key() for d in plan]


NEW, DELETE = 0x44AF03, 0x44AEAE
BLIT_SCALED, BLIT_PLAIN, CELL_CUT = 0x403D70, 0x403D00, 0x409F90
FILL, TEXT, LABEL = 0x408150, 0x409160, 0x40BB30
GFX_SINGLETON = 0x48B2E8
FPCW = 0x027F
HUGE = 100000


class Engine:
    """A New Home's engine in Unicorn: the game's own constructors and draw code, the sheet loader answering each
    file with a surface of its real size, every blit recorded."""

    def __init__(self, exe: bytes) -> None:
        p = self.p = Process(exe)
        p.mu.mem_map(API_STUBS, 0x10000)
        p.api_names = {}
        slot = 0
        for entry in p._exe_pe.DIRECTORY_ENTRY_IMPORT:
            for imp in entry.imports:
                if not imp.name:
                    continue
                stub = API_STUBS + slot * 16
                slot += 1
                name = imp.name.decode()
                p.mu.mem_write(stub, b"\xC3")
                p.api_names[stub] = name
                p.mu.mem_write(imp.address, struct.pack("<I", stub))
                if name.startswith(("SDL_", "IMG_", "_FSOUND", "_FMUSIC")):
                    pop = int(name.rsplit("@", 1)[1]) if "@" in name else 0
                    p.api_handlers[name] = (lambda n: (lambda q: (0, n)))(pop)
        self.mouse = (0, 0)

        def mouse(q):
            if q.arg(0):
                q.put32(q.arg(0), self.mouse[0])
            if q.arg(1):
                q.put32(q.arg(1), self.mouse[1])
            return 0, 0
        p.api_handlers["SDL_GetMouseState"] = mouse
        self.surfaces: dict[int, str] = {}
        self.loaded: list[str] = []
        self.blits: list[pi.Draw] = []
        self.fills = 0
        self.texts = 0
        p.stub(NEW, lambda q: (q.alloc(max(q.arg(0), 4)), 0))
        p.stub(DELETE, lambda q: (0, 0))
        p.stub(vv1.SHEET_LOADER, self._sheet)
        p.stub(BLIT_SCALED, self._blit_scaled)
        p.stub(BLIT_PLAIN, self._blit_plain)
        p.stub(FILL, self._fill)
        p.stub(TEXT, self._text)
        p.stub(LABEL, lambda q: (0, 4))
        self.renderer = p.alloc(0x200)
        self.wide_clip()
        self.gfx = p.alloc(0x10)
        p.put32(self.gfx, self.renderer)
        p.put32(GFX_SINGLETON, self.gfx)
        self.camera = p.alloc(0x40)
        self._code = p.alloc(0x1000)
        self._next_code = 0

    def wide_clip(self) -> None:
        """No clipping: the renderer's clip rectangle (+0x60) and screen size (+8, +0xC) made huge."""
        self.p.write(self.renderer + 0x60, struct.pack("<iiii", -HUGE, -HUGE, HUGE, HUGE))
        self.p.put32(self.renderer + 8, HUGE)
        self.p.put32(self.renderer + 0xC, HUGE)

    def ret_stub(self, pop: int) -> int:
        at = self._code + self._next_code
        self._next_code += 16
        self.p.write(at, b"\xC3")
        self.p.stub(at, lambda q: (0, pop))
        return at

    def dummy(self, pops: dict[int, int] | None = None) -> int:
        """An object whose every vtable slot returns (slot -> bytes popped; 0 by default)."""
        vt = self.p.alloc(0x100)
        for i in range(64):
            self.p.put32(vt + 4 * i, self.ret_stub((pops or {}).get(i, 0)))
        obj = self.p.alloc(0x100)
        self.p.put32(obj, vt)
        return obj

    def cstr(self, text: str) -> int:
        at = self.p.alloc(len(text) + 1)
        self.p.write(at, text.encode() + b"\0")
        return at

    def call(self, fn: int, args=(), ecx=None, until=None) -> int:
        self.p.mu.reg_write(UC_X86_REG_FPCW, FPCW)
        if until is None:
            return self.p.call(fn, list(args), ecx=ecx)
        return self.p.call(fn, list(args), ecx=ecx, until=until)

    def sprite(self, name: str, cols: int = 1, rows: int = 1) -> int:
        obj = self.p.alloc(0x34)
        self.call(vv1.CTOR_ONE, [self.cstr(name), cols, rows], ecx=obj)
        return obj

    def whole(self, name: str) -> int:
        obj = self.p.alloc(0x34)
        self.call(vv1.CTOR_WHOLE, [self.cstr(name)], ecx=obj)
        return obj

    def grid(self, prefix: str, sheets, cols: int, rows: int) -> int:
        obj = self.p.alloc(0x34)
        self.call(vv1.CTOR_GRID, [self.cstr(prefix), self.cstr(".png"), sheets[0], sheets[1], cols, rows], ecx=obj)
        return obj

    def _sheet(self, q):
        name = q.cstring(q.arg(0))
        w, h = size_of(name)
        surface = q.alloc(0x40)
        q.put32(surface + 8, w)
        q.put32(surface + 12, h)
        self.surfaces[surface] = name
        self.loaded.append(name)
        q.put32(q.reg("ecx"), surface)
        q.write(q.reg("ecx") + 4, b"\x01")
        return q.reg("ecx"), 4

    def _blit_scaled(self, q):
        a = [q.arg(i) for i in range(10)]
        self.blits.append(pi.Draw(self.surfaces[a[0]], tuple(signed(v) for v in a[3:7]), signed(a[1]),
                                  signed(a[2]), bits_f32(a[8]), bits_f32(a[7])))
        return 0, 0x28

    def _blit_plain(self, q):
        a = [q.arg(i) for i in range(7)]
        self.blits.append(pi.Draw(self.surfaces[a[0]], tuple(signed(v) for v in a[3:7]), signed(a[1]),
                                  signed(a[2])))
        return 0, 0x1C

    def _fill(self, q):
        self.fills += 1
        return 0, 0x14

    def _text(self, q):
        self.texts += 1
        return 0, 0x14

    def take(self) -> list[pi.Draw]:
        out, self.blits = self.blits, []
        return out


_ENGINE = None


def engine() -> "Engine":
    global _ENGINE
    if _ENGINE is None:
        _ENGINE = Engine(EXE.read_bytes())
    return _ENGINE


SHEETS = va.AssetSheets(SizeSource())


class Emulated(unittest.TestCase):
    count = 0

    def same(self, plan, label: str) -> None:
        game = engine().take()
        self.assertEqual(keys(plan), keys(game), label)
        type(self).count += 1


# ------------------------------------------------------------------ the sprite table against the executable

def _scan_calls():
    """Every call in .text to each constructor: {target: [(site, [args]), ...]}, the arguments read back from the
    pushes before the call (a pushed register is resolved to the constants moved into it before; a register given
    two constants on two paths yields both)."""
    import pefile as pf
    from capstone import CS_ARCH_X86, CS_MODE_32, Cs
    pe = pf.PE(str(EXE))
    image = pe.get_memory_mapped_image()
    base = pe.OPTIONAL_HEADER.ImageBase
    text = next(s for s in pe.sections if s.Name.startswith(b".text"))
    t0, size = base + text.VirtualAddress, text.Misc_VirtualSize
    md = Cs(CS_ARCH_X86, CS_MODE_32)
    nargs = {vv1.CTOR_ONE: 3, vv1.CTOR_WHOLE: 1, vv1.CTOR_GRID: 6, vv1.CTOR_BUTTON: 6, vv1.CTOR_FONT: 3,
             vv1.SHEET_LOADER: 1}
    code = image[t0 - base:t0 - base + size]

    def cstring(va_):
        o = va_ - base
        if not 0 <= o < len(image):
            return None
        e = image.find(b"\0", o, o + 128)
        return image[o:e].decode("latin-1") if e > o else None

    def value(text_):
        try:
            return int(text_, 0)
        except ValueError:
            return None
    found = {t: [] for t in nargs}
    for i in range(len(code) - 5):
        if code[i] != 0xE8:
            continue
        site = t0 + i
        target = site + 5 + struct.unpack_from("<i", code, i + 1)[0]
        if target not in nargs:
            continue
        ins = None
        for back in range(0x60, 0, -1):
            trial = list(md.disasm(image[site - back - base:site + 5 - base], site - back))
            if trial and trial[-1].address == site:
                ins = trial
                break
        args, k = [], len(ins) - 2
        while len(args) < nargs[target] and k >= 0:
            op = ins[k]
            if op.mnemonic == "call":
                break
            if op.mnemonic == "push":
                v = value(op.op_str)
                if v is None:
                    vals = []
                    for j in range(k - 1, max(-1, k - 25), -1):
                        o2 = ins[j]
                        if o2.mnemonic == "mov" and o2.op_str.startswith(op.op_str + ","):
                            v2 = value(o2.op_str.split(",", 1)[1].strip())
                            if v2 is None:
                                break
                            vals.append(v2)
                    args.append(tuple(vals) if vals else op.op_str)
                else:
                    args.append(v)
            k -= 1
        found[target].append((site, args))

    def name_of(arg):
        if isinstance(arg, tuple):
            return tuple(cstring(a) for a in arg)
        return cstring(arg) if isinstance(arg, int) else None
    return found, name_of


@unittest.skipUnless(EMULATOR and HAVE_CAPSTONE, WHY + ", and capstone")
class SheetTableIsTheExecutables(unittest.TestCase):
    """Every constructor call of the executable is in the table, and every table entry is a call."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.calls, name_of = _scan_calls()
        cls.name_of = staticmethod(name_of)

    def test_one_sheet_calls(self) -> None:
        table = {}
        for name, cols, rows, sites in vv1.ONE_SHEETS:
            for s in sites:
                table.setdefault(s, set()).add((name, cols, rows))
        seen = set()
        for site, args in self.calls[vv1.CTOR_ONE]:
            if site in vv1.ONE_SHEET_INDIRECT:
                self.assertEqual(site, vv1.BUTTON_SHEET_SITE)
                self.assertEqual(args[1:], [3, 1], hex(site))      # the button sheet: (name, 3, 1)
                continue
            names = self.name_of(args[0])
            names = names if isinstance(names, tuple) else (names,)
            rows = args[2] if isinstance(args[2], (int, str)) else args[2][0]
            if site == 0x429872 and rows == "ebp":
                # ebp is set once at the top of 0x429700: `mov ebp, 1` at 0x42971E
                import pefile as pf
                pe = pf.PE(str(EXE))
                self.assertEqual(pe.get_memory_mapped_image()[0x2971E:0x29723], b"\xBD\x01\x00\x00\x00")
                rows = 1
            got = {(n, args[1], rows) for n in names}
            self.assertEqual(got, table.get(site), hex(site))
            seen.add(site)
        self.assertEqual(seen, set(table))
        self.assertEqual(len(self.calls[vv1.CTOR_ONE]), 73)

    def test_whole_picture_calls(self) -> None:
        table = {s: name for name, sites in vv1.WHOLE_PICTURES for s in sites}
        seen = set()
        for site, args in self.calls[vv1.CTOR_WHOLE]:
            if site in vv1.WHOLE_INDIRECT:
                continue
            self.assertEqual(self.name_of(args[0]), table.get(site), hex(site))
            seen.add(site)
        self.assertEqual(seen, set(table))
        self.assertEqual(len(self.calls[vv1.CTOR_WHOLE]), len(table) + len(vv1.WHOLE_INDIRECT))

    def test_grids_buttons_fonts_and_the_loader(self) -> None:
        grids = {site: (prefix, sheets, cols, rows) for prefix, sheets, cols, rows, site in vv1.GRIDS}
        self.assertEqual({s for s, _a in self.calls[vv1.CTOR_GRID]}, set(grids))
        for site, args in self.calls[vv1.CTOR_GRID]:
            prefix, sheets, cols, rows = grids[site]
            self.assertEqual((self.name_of(args[0]), self.name_of(args[1]), args[4], args[5]),
                             (prefix, ".png", cols, rows), hex(site))
        buttons = {}
        for name, sites in vv1.BUTTONS:
            for s in sites:
                buttons.setdefault(s, set()).add(name)
        got = {}
        for site, args in self.calls[vv1.CTOR_BUTTON]:
            names = self.name_of(args[1])
            got[site] = set(names if isinstance(names, tuple) else (names,))
        self.assertEqual(got, buttons)
        fonts = {fn: name for name, _site, fn in vv1.FONTS}
        sites = {}
        for site, args in self.calls[vv1.CTOR_FONT]:
            sites[site] = self.name_of(args[0]) + ".png"
        self.assertEqual(sorted(sites.values()), sorted(n for n, _s, _f in vv1.FONTS))
        self.assertTrue(all(any(abs(s - fn) < 0x60 for fn in fonts) for s in sites))
        # The sheet loader: called only by the font loader and the two constructors.
        self.assertEqual({s for s, _a in self.calls[vv1.SHEET_LOADER]}, {vv1.FONT_LOAD_SITE, 0x409F10, 0x40A1E2})

    def test_button_places(self) -> None:
        """The main panel's and the Tech screen's buttons are where their 0x4019B0 calls put them."""
        places: dict[str, set] = {}
        for site, args in self.calls[vv1.CTOR_BUTTON]:
            x, y = (a[0] if isinstance(a, tuple) else a for a in args[2:4])
            names = self.name_of(args[1])
            for n in (names if isinstance(names, tuple) else (names,)):
                places.setdefault(n, set()).add((x, y))
        for name, x, y in vv1.MAIN_BUTTONS + vv1.TECH_BUTTONS:
            self.assertIn((x, y), places[name], name)

    def test_every_picture_file_is_in_the_table_or_never_named(self) -> None:
        files = set()
        for spec in vv1.sheet_table():
            files.update(f.casefold() for f in spec.files())
        never = {n.casefold() for n in GAME_FILES} - files
        self.assertEqual(never, {n.casefold() for n in NEVER_LOADED})
        self.assertTrue(files <= {n.casefold() for n in GAME_FILES})


@unittest.skipUnless(EMULATOR, WHY)
class TheGamesCut(unittest.TestCase):
    """0x409F90 on every sheet the game's constructors build, against pi.Atlas.cell."""

    def test_every_cell_of_every_sprite(self) -> None:
        e = engine()
        rect = e.p.alloc(16)
        cases = 0
        for spec in vv1.sheet_table():
            if spec.atlas.grid:
                obj = e.grid(spec.name, spec.sheets, spec.cols, spec.rows)
            elif spec.whole:
                obj = e.sprite(spec.name, 1, 1)
            else:
                obj = e.sprite(spec.name, spec.cols, spec.rows)
            for row in range(spec.rows + 1):
                for col in range(spec.cols + 1):
                    e.call(CELL_CUT, [col, row, rect], ecx=obj)
                    got = struct.unpack("<iiii", e.p.read(rect, 16))
                    sheet = e.surfaces[e.p.u32(e.p.u32(obj + 4))]
                    self.assertEqual(spec.atlas.cell(size_of, col, row), (sheet, got), (spec.name, col, row))
                    cases += 1
        self.assertGreater(cases, 3000)

    def test_the_tile_loop_builds_the_tiles_in_order(self) -> None:
        e = engine()
        obj = e.p.alloc(0x300)
        e.loaded = []
        e.call(vv1.TILE_BUILDER, [], ecx=obj)
        self.assertEqual(e.loaded, vv1.tile_files())


# ------------------------------------------------------------------ the island

def _build_scene(e: "Engine"):
    scene = e.p.alloc(0x1500)
    state = e.p.alloc(0xB000)
    e.p.put32(scene + 0x1480, state)
    e.p.put32(scene + 0x147C, e.gfx)                  # 0x417280: the graphics object (0x408090)
    for off, (name, cols, rows) in vv1.SCENE_SPRITES.items():
        e.p.put32(scene + off, e.sprite(name, cols, rows))
    return scene, state


def _set_state(e: "Engine", state_va: int, state: dict, camx: int = 0, camy: int = 0) -> None:
    e.p.write(state_va, bytes(0xB000))
    e.p.put32(state_va + 8, camx)
    e.p.put32(state_va + 0xC, camy)
    for off, value in state.items():
        if off in vv1.BYTE_FIELDS:
            e.p.write(state_va + off, bytes((value & 0xFF,)))
        else:
            e.p.put32(state_va + off, value)


def _island_states():
    """States reaching every branch of 0x416380: each threshold just under, at and over, and random mixes."""
    fields = {
        vv1.S_HUT1: (0, 0x7D, 0x7E), vv1.S_HUT2: (0, 1, 0xC8, 0xC9), vv1.S_HUT3: (0, 1, 0x12C, 0x12D),
        vv1.S_FOOD: (0, 10, 11, 50, 51, 400, 401, 2000, 2001), vv1.S_BERRIES: (0, 1, 150, 151, 300, 301, 450, 451,
                                                                                600, 601, 750, 751, 900, 901, 1050,
                                                                                1051, 1300, 1301),
        vv1.S_SCIENCE: (0, 1, 2, 3), vv1.S_FARMING: (0, 1, 2, 3), vv1.S_CROPS: (0, 1, 400, 401),
        vv1.S_DEBRIS: (0, 4, 5, 14, 15, 29, 30, 44, 45, 59, 60, 74, 75, 89, 90, 104, 105, 119, 120, 149, 150),
        vv1.S_CREEK: (0, 0xAF, 0xB0), vv1.S_IDOL: (0, 1, 0x2A3, 0x2A4),
        vv1.S_TEMPLE: (0, 1, 0x7C, 0x7D, 0xFA, 0x177, 0x1F4, 0x271, 0x2EE, 0x36B), vv1.S_CHEST: (0, 1, 0x190, 0x191),
        vv1.S_LOG_A: (0, 1), vv1.S_DRUM_A: (0, 5),
    }
    flags = (vv1.S_HUT1_DONE, vv1.S_HUT2_DONE, vv1.S_HUT3_DONE, vv1.S_DEBRIS_DONE, vv1.S_BOULDER_DONE,
             vv1.S_CREEK_DONE, vv1.S_IDOL_DONE, vv1.S_TEMPLE_DONE, vv1.S_GARDEN_DONE, vv1.S_LOG_B, vv1.S_DRUM_B,
             vv1.S_FLOWERS_A, vv1.S_FLOWERS_B, vv1.S_CHEST_DONE)
    out = [{}, dict(vv1.NEW_GAME), dict(vv1.EVERYTHING_BUILT)]
    for off, values in fields.items():
        for v in values:
            out.append({off: v})
    for f in flags:
        out.append({f: 1})
    out.append({vv1.S_DEBRIS_DONE: 1, vv1.S_DEBRIS: 0})
    out.append({vv1.S_DEBRIS_DONE: 2, vv1.S_DEBRIS: 0})
    out.append({vv1.S_ITEM_COUNT: 2, vv1.S_ITEM_X: 700, vv1.S_ITEM_Y: 800, vv1.S_ITEM_KIND: 0})
    out.append({vv1.S_ITEM_COUNT: 1, vv1.S_ITEM_X: 700, vv1.S_ITEM_Y: 800, vv1.S_ITEM_KIND: 1})
    for slot in range(vv1.GRAVE_SLOTS):
        out.append({vv1.S_GRAVES + slot * vv1.GRAVE_STRIDE: 1 + slot % 5})
    rng = random.Random(1)
    for _ in range(60):
        s = {off: rng.choice(values) for off, values in fields.items()}
        s.update({f: rng.randint(0, 1) for f in flags})
        for slot in range(vv1.GRAVE_SLOTS):
            if rng.random() < 0.4:
                s[vv1.S_GRAVES + slot * vv1.GRAVE_STRIDE] = rng.randint(-3, 9)
        out.append(s)
    return out


@unittest.skipUnless(EMULATOR, WHY)
class IslandIsTheGames(Emulated):
    """0x4115C0 / 0x411550 (the tiles), 0x416380 / 0x415E60 (the objects), 0x415ED0 and 0x42A5A0 (the map)."""

    @classmethod
    def setUpClass(cls) -> None:
        e = engine()
        cls.scene, cls.state = _build_scene(e)
        cls.tiles = e.p.alloc(0x300)
        e.call(vv1.TILE_BUILDER, [], ecx=cls.tiles)
        e.take()

    def test_tiles(self) -> None:
        e = engine()
        for camx, camy in ((0, 0), (300, 1100), (-5, 7), (1248, 1448)):
            e.call(0x411550, [camx, camy], ecx=self.tiles)
            self.same(vv1.island_tiles_plan(SHEETS, camx, camy), f"tiles at {camx},{camy}")

    def test_objects_in_every_state(self) -> None:
        e = engine()
        for n, state in enumerate(_island_states()):
            camx, camy = (n * 37) % 900, (n * 53) % 1100
            _set_state(e, self.state, state, camx, camy)
            e.call(0x416380, [], ecx=self.scene)
            e.call(0x415E60, [], ecx=self.scene)
            objs = vv1.island_objects(state)
            self.same(vv1.objects_plan(SHEETS, objs, camx, camy), f"objects {state}")
            e.call(0x415ED0, [], ecx=self.scene)
            self.same(vv1.map_objects_plan(SHEETS, objs), f"map {state}")

    def test_map_screen(self) -> None:
        e = engine()
        screen = e.p.alloc(0x100)
        e.p.put32(screen + 8, e.gfx)
        e.p.put32(screen + 0x6C, e.whole("overview_bg.jpg"))
        e.p.write(screen + 0x5C, struct.pack("<iiii", -HUGE, -HUGE, HUGE, HUGE))
        e.p.put32(screen + 0x20, self.scene)
        e.p.stub(0x4388E0, lambda q: (0, 0))                 # the villagers on the map: not drawn here
        for state in (vv1.NEW_GAME, vv1.EVERYTHING_BUILT):
            _set_state(e, self.state, state)
            e.call(0x416380, [], ecx=self.scene)
            e.take()
            e.call(0x42A5A0, [], ecx=screen)
            e.wide_clip()
            self.same([vv1.whole_draw(SHEETS, "overview_bg.jpg", 0, 0)]
                      + vv1.map_objects_plan(SHEETS, vv1.island_objects(state)), "map screen")

    def test_the_module_assets_are_these_plans(self) -> None:
        """Each island asset's frames come from island_objects (proven above) through objects_plan."""
        for asset in vv1.assets(SHEETS):
            if asset.proof.startswith("emulated 0x416380"):
                self.assertTrue(asset.frames)

    @classmethod
    def tearDownClass(cls) -> None:
        print(f"\nA New Home island: {cls.count} draws by the game and the plan alike")


@unittest.skipUnless(EMULATOR, WHY)
class CreaturesAndEffectsAreTheGames(Emulated):
    def test_butterflies(self) -> None:
        e = engine()
        obj = e.p.alloc(0x200)
        e.p.put32(obj, e.sprite("butterflygreen.png", 4, 5))
        e.p.put32(obj + 0x1E4, e.gfx)
        e.p.put32(obj + 0x1E8, e.camera)
        e.p.put32(e.camera + 8, 333)
        e.p.put32(e.camera + 0xC, 444)
        rng = random.Random(2)
        for trial in range(40):
            recs = []
            for i in range(9):
                r = dict(x=rng.randint(-50, 900), y=rng.randint(-50, 700), heading=rng.choice((-3, -1, 0, 2)),
                         colour=rng.randint(0, 4), wing=rng.randint(0, 1), percent=rng.choice((50, 63, 77, 90, 100)),
                         state=rng.choice((0, 1, 2, 3)))
                b = obj + 4 + 0x34 * i
                for off, k in ((0, "x"), (4, "y"), (0x18, "heading"), (0x20, "colour"), (0x24, "wing"),
                               (0x2C, "percent"), (0x30, "state")):
                    e.p.put32(b + off, r[k])
                recs.append(r)
            for flag in (0, 1):
                e.call(0x412AB0, [flag], ecx=obj)
                cam = (333, 444) if flag else (0, 0)
                self.same([vv1.butterfly_plan(SHEETS, r["x"], r["y"], r["colour"], r["wing"], r["heading"],
                                              r["percent"], r["state"], i, *cam) for i, r in enumerate(recs)],
                          f"butterflies {flag} {recs}")

    def test_particles(self) -> None:
        e = engine()
        obj = e.p.alloc(0x3500)
        e.p.put32(obj + 0x3404, e.gfx)
        e.p.put32(obj + 0x3408, e.camera)
        e.p.put32(e.camera + 8, 120)
        e.p.put32(e.camera + 0xC, 70)
        cols = {name: c for name, c, _l in vv1.EFFECTS}
        cols["carrying.png"] = 15
        sprites = {}
        for off, name in vv1.PARTICLE_SPRITES.items():
            sprites[name] = e.sprite(name, cols[name], 1)
            e.p.put32(obj + off, sprites[name])
        rng = random.Random(3)
        names = list(vv1.PARTICLE_SPRITES.values())
        for trial in range(30):
            e.p.write(obj, bytes(0x3404))
            recs = []
            for i in range(256):
                if rng.random() < 0.2:
                    name = rng.choice(names)
                    r = dict(i=i, name=name, x=rng.randint(-20, 900), y=rng.randint(-20, 700),
                             frame=rng.randint(0, cols[name] - 1), lift=rng.randint(-30, 5),
                             fixed=rng.choice((-1, -1, rng.randint(0, cols[name] - 1))), layer=rng.randint(0, 2))
                    b = obj + 0xC + 0x34 * i
                    for off, k in ((0, "x"), (4, "y"), (8, "frame"), (0x18, "lift"), (0x1C, "fixed"),
                                   (0x24, "layer")):
                        e.p.put32(b + off, r[k])
                    e.p.write(b + 0x21, b"\x01")
                    e.p.put32(b + 0x28, sprites[name])
                    recs.append(r)
            for layer in (0, 1, 2):
                e.call(0x41AB20, [layer], ecx=obj)
                self.same([vv1.particle_plan(SHEETS, r["name"], cols[r["name"]], r["frame"], r["x"], r["y"],
                                             r["lift"], r["fixed"], layer, 120, 70)
                           for r in recs if r["layer"] == layer], f"particles layer {layer}")

    def test_the_fade_is_one_less_a_tenth_per_step(self) -> None:
        self.assertEqual(vv1.PARTICLE_FADE, pi.f32(0.1))
        self.assertEqual(vv1.particle_alpha(4), pi.f32(1.0 - 4 * pi.f32(0.1)))

    @classmethod
    def tearDownClass(cls) -> None:
        print(f"\nA New Home creatures and effects: {cls.count} draws by the game and the plan alike")


@unittest.skipUnless(EMULATOR, WHY)
class InterfaceIsTheGames(Emulated):
    def test_tech_screen(self) -> None:
        e = engine()
        obj = e.p.alloc(0x200)
        state = e.p.alloc(0xB000)
        e.p.put32(obj + 8, e.gfx)
        e.p.put32(obj + 0xC, state)
        e.p.put32(obj + 0x40, e.whole("tech_bg.png"))
        for name, off in vv1.TECH_SPRITES.items():
            e.p.put32(obj + off, e.sprite(name, 3, 1))
        for i in range(7):
            e.p.put32(obj + 0x124 + 4 * i, e.dummy())
        rng = random.Random(4)
        cases = [{n: lv for n in vv1.TECH_SPRITES} for lv in range(5)]
        cases += [{n: rng.randint(0, 4) for n in vv1.TECH_SPRITES} for _ in range(40)]
        for levels in cases:
            for stage, alpha in ((0, 0.0), (1, 0.25), (3, 0.5), (4, 0.3), (9, 1.0)):
                e.p.write(state, bytes(0xB000))
                for label, name, field, _x, _y in vv1.TECHS:
                    e.p.put32(state + field, levels[name])
                e.p.put32(obj + 0x1C, stage)
                e.p.put32(obj + 0x20, f32bits(alpha))
                e.call(0x433B20, [], ecx=obj)
                self.same(vv1.tech_screen_plan(SHEETS, levels, stage, pi.f32(alpha)), f"tech {levels} {stage}")

    def test_skill_and_health_bars(self) -> None:
        e = engine()
        obj = e.p.alloc(0x40)
        e.p.put32(obj, e.gfx)
        e.p.put32(obj + 0xC, e.whole("StatusBarSliceB.png"))
        e.p.put32(obj + 0x10, e.whole("StatusBarSliceR.png"))
        e.p.put32(obj + 0x14, e.whole("healthBarbulb.png"))
        for row in range(2, 10):
            for value in range(-5, 106):
                e.call(0x42F500, [row, value & 0xFFFFFFFF], ecx=obj)
                self.same(vv1.skill_bar_plan(SHEETS, row, value), f"bar {row} {value}")

    def test_loading_bar(self) -> None:
        e = engine()
        obj = e.p.alloc(0x40)
        e.p.put32(obj, e.gfx)
        e.p.put32(obj + 8, e.whole("BambooMeterFrame1.png"))
        e.p.put32(obj + 0xC, e.whole("LoadColor.png"))
        for pct in range(-3, 106):
            for x, y in ((0, 0), (0xF0, 0x1F4)):
                e.call(0x436FB0, [3, x, y, pct & 0xFFFFFFFF], ecx=obj)
                self.same(vv1.loading_bar_plan(SHEETS, pct, x, y), f"loading {pct}")
        for mode in (0, 1, 2):
            fills = e.fills
            e.call(0x436FB0, [mode, 10, 20, 50], ecx=obj)
            self.same([vv1.whole_draw(SHEETS, "BambooMeterFrame1.png", 10, 20)], f"mode {mode}")
            self.assertEqual(e.fills, fills + 1)

    def test_dialog_frames(self) -> None:
        e = engine()
        sizes = [(w, h) for w, h, _f in vv1.DIALOG_SIZES] + [(w, h) for w in (1, 63, 64, 65, 129, 700)
                                                             for h in (1, 64, 65, 300)]
        for name in ("GreenDlgTileGrid.png", "OrangeDlgTileGrid.png"):
            sprite = e.sprite(name, 9, 1)
            for w, h in sizes:
                grid = e.p.alloc(0x40)
                e.call(0x40C670, [sprite, w, h], ecx=grid)
                for x, y, alpha in ((0, 0, 1.0), (17, -9, 0.5)):
                    e.call(0x40C4D0, [x & 0xFFFFFFFF, y & 0xFFFFFFFF, f32bits(alpha)], ecx=grid)
                    self.same(vv1.dialog_plan(SHEETS, name, w, h, x, y, pi.f32(alpha)), f"{name} {w}x{h}")

    def test_buttons(self) -> None:
        e = engine()
        parent = e.dummy()
        for name, _sites in vv1.BUTTONS:
            for x, y in ((0, 0), (80, 403), (-4, 9)):
                outer = e.p.alloc(0x80)
                e.call(vv1.CTOR_BUTTON, [7, e.cstr(name), x & 0xFFFFFFFF, y & 0xFFFFFFFF, 0, 0], ecx=outer)
                e.take()
                inner = e.p.u32(outer + 0x10)
                self.assertEqual(e.p.read(inner + 0x28, 2), b"\x00\x01")    # built hidden and enabled
                e.p.write(inner + 0x28, b"\x01")                            # shown, as its screen shows it
                for entry, state in ((0x401620, 0), (0x401630, 1), (0x401610, 2)):
                    e.call(entry, [], ecx=outer)
                    self.same(vv1.button_plan(SHEETS, name, state, x, y), f"{name} {state}")
        del parent

    def test_cursor(self) -> None:
        e = engine()
        for name in ("hand_open.png", "hand.png"):
            sprite = e.whole(name)
            w, h = size_of(name)
            e.call(0x408240, [sprite, w // 2, h // 2], ecx=e.gfx)
            for mouse in ((0, 0), (400, 300), (13, 590)):
                e.mouse = mouse
                e.p.write(e.renderer + 0x1E, b"\x00\x01\x00")
                e.p.put32(e.renderer + 0x18, 0)
                e.p.stub(0x403830, lambda q: (0, 4))
                e.p.stub(0x403970, lambda q: (0, 0))
                e.call(0x409060, [], ecx=e.renderer)
                self.same(vv1.cursor_plan(SHEETS, name, *mouse), f"cursor {name} {mouse}")
            e.p.put32(e.renderer + 0x24, 0)

    @classmethod
    def tearDownClass(cls) -> None:
        print(f"\nA New Home interface: {cls.count} draws by the game and the plan alike")


@unittest.skipUnless(EMULATOR, WHY)
class ScreensAreTheGames(Emulated):
    def test_help_pages(self) -> None:
        e = engine()
        obj = e.p.alloc(0x200)
        e.p.put32(obj + 8, e.gfx)
        e.p.put32(obj + 0x13C, e.whole("puzzles_bg.png"))
        for i, name in enumerate(("help1.jpg", "help2.jpg", "help3.jpg", "help4.jpg", "credits.jpg")):
            e.p.put32(obj + 0x140 + 4 * i, e.whole(name))
        for page in range(-1, 7):
            e.p.put32(obj + 0x20, page & 0xFFFFFFFF)
            e.call(0x41DD00, [], ecx=obj)
            self.same(vv1.help_plan(SHEETS, page), f"help {page}")

    def test_puzzle_screen(self) -> None:
        e = engine()
        obj = e.p.alloc(0x200)
        state = e.p.alloc(0xB000)
        e.p.put32(obj + 8, e.gfx)
        e.p.put32(obj + 0xC, state)
        e.p.put32(obj + 0x134, e.whole("puzzles_bg.png"))
        e.p.put32(obj + 0x138, e.sprite("puzzle_covers.jpg", 4, 4))
        e.p.put32(obj + 0x13C, e.sprite("puzzle_solved.jpg", 4, 4))
        rng = random.Random(5)
        cases = [set(), set(range(16))] + [{i} for i in range(16)] + [
            {i for i in range(16) if rng.random() < 0.5} for _ in range(20)]
        for solved in cases:
            e.p.write(state, bytes(0xB000))
            for i in solved:
                e.p.write(state + vv1.PUZZLE_FLAGS[i], b"\x01")
            e.call(0x42D5C0, [], ecx=obj)
            self.same(vv1.puzzle_screen_plan(SHEETS, solved), f"puzzles {sorted(solved)}")

    def test_title_screen(self) -> None:
        e = engine()
        obj = e.p.alloc(0x200)
        e.p.put32(obj + 8, e.gfx)
        for off, name in ((0x80, "bxshtBG.png"), (0x84, "Boxshtfeat.png"), (0x88, "CloudBack.png"),
                          (0x8C, "CloudMiddle.png"), (0x90, "Cloudfront.png"), (0x94, "Lavaglow.png")):
            e.p.put32(obj + off, e.whole(name))
        e.p.put32(obj + 0x98, e.sprite("logo1.png", 1, 1))
        e.p.stub(0x412AB0, lambda q: (0, 4))                 # the butterflies: proven on their own
        for clouds, lava in ((vv1.TITLE_CLOUDS, vv1.TITLE_LAVA),
                             (((-250.0, 10, 799.9, 159, 0.5, 150), (33.7, 59, -0.9, 100, 640.2, 209)), pi.f32(0.05))):
            for k, (fx, fy, mx, my, bx, by) in enumerate(clouds):
                for off, v in ((0x20 + 8 * k, fx), (0x30 + 8 * k, mx), (0x40 + 8 * k, bx)):
                    e.p.put32(obj + off, f32bits(v))
                for off, v in ((0x24 + 8 * k, fy), (0x34 + 8 * k, my), (0x44 + 8 * k, by)):
                    e.p.put32(obj + off, v)
            e.p.put32(obj + 0x50, f32bits(lava))
            e.call(0x425DF0, [], ecx=obj)
            self.same(vv1.title_plan(SHEETS, tuple(tuple(pi.f32(v) if isinstance(v, float) else v for v in c)
                                                   for c in clouds), lava), "title")

    def test_loading_screen(self) -> None:
        e = engine()
        bar = e.p.alloc(0x40)
        e.p.put32(bar, e.gfx)
        e.p.put32(bar + 8, e.whole("BambooMeterFrame1.png"))
        e.p.put32(bar + 0xC, e.whole("LoadColor.png"))
        obj = e.p.alloc(0x200)
        e.p.put32(obj + 0xC, e.gfx)
        e.p.put32(obj + 0x14, bar)
        e.p.put32(obj + 0x38, e.sprite("bxshtBG.png", 1, 1))
        e.p.put32(obj + 0x3C, e.sprite("logo1.png", 1, 1))
        e.p.put32(obj + 0x40, e.sprite("ldwLogo.png", 1, 1))
        e.p.put32(obj + 0x94, e.dummy())
        for pct in (0, 25, 100):
            e.p.put32(obj + 0x90, pct)
            e.call(0x41F570, [], ecx=obj)
            self.same(vv1.loading_screen_plan(SHEETS, pct), f"loading screen {pct}")

    def test_splash_and_first_blits(self) -> None:
        e = engine()
        obj = e.p.alloc(0x400)
        e.p.put32(obj + 0xC, e.gfx)
        e.p.put32(obj + 0x20, e.whole("SPLASH_BG.jpg"))
        e.call(0x431620, [], ecx=obj)
        self.same([vv1.whole_draw(SHEETS, "SPLASH_BG.jpg", 0, 0)], "splash")
        for fn, until, gfx_off, off, name in ((0x41D5E0, 0x41D5F3, 0x10, 0x64, "gamewin_bg.jpg"),
                                              (0x41D5E0, 0x41D5F3, 0x10, 0x64, "intro1_bg.png"),
                                              (0x41EBE0, 0x41EBF6, 0x10, 0x280, "intro2_bg.png"),
                                              (0x449140, 0x44915E, 8, 0x44, "VD_BG.png")):
            obj = e.p.alloc(0x400)
            e.p.put32(obj + gfx_off, e.gfx)
            e.p.put32(obj + off, e.sprite(name, 1, 1) if name.endswith(("jpg", "bg.png")) else e.whole(name))
            e.call(fn, [], ecx=obj, until=until)
            self.same([vv1.whole_draw(SHEETS, name, 0, 0)], name)
        obj = e.p.alloc(0x400)
        e.p.put32(obj + 0xC, e.gfx)
        e.p.put32(obj + 0x2E8, e.whole("main_BG.png"))
        e.p.put32(obj + 0x350, e.dummy({2: 4}))
        e.call(0x41F9B0, [], ecx=obj, until=0x41F9F3)
        self.same([vv1.whole_draw(SHEETS, "main_BG.png", 0, 0)], "main panel")

    @classmethod
    def tearDownClass(cls) -> None:
        print(f"\nA New Home screens: {cls.count} draws by the game and the plan alike")


# ------------------------------------------------------------------ without the game

class Planning(unittest.TestCase):
    """The module on sizes alone (no game, no art)."""

    def setUp(self) -> None:
        self.sheets = va.AssetSheets(SizeSource())

    def test_every_asset_plans_and_keys_are_unique(self) -> None:
        everything = va.all_assets(1, self.sheets, vv1)
        keys_ = [a.key for a in everything]
        self.assertEqual(len(keys_), len(set(keys_)))
        for a in everything:
            self.assertIn(a.category, va.CATEGORIES, a.key)
            self.assertTrue(a.frames, a.key)
            for f in a.frames:
                self.assertTrue(f.plan, (a.key, f.label))
        cats = {a.category for a in everything}
        for c in (va.CREATURES, va.BUILDINGS, va.PUZZLES, va.PLANTS, va.SCENE, va.TECH, va.METERS, va.PANELS,
                  va.ICONS, va.CURSORS, va.EFFECTS, va.SCREENS, va.VILLAGERS, va.FONTS, va.SHEETS):
            self.assertIn(c, cats)

    def test_never_loaded_files_are_listed_unused(self) -> None:
        sheets = [a for a in va.all_assets(1, self.sheets, vv1) if a.category == va.SHEETS]
        unused = {a.label for a in sheets if a.group == "Never loaded by the game"}
        self.assertEqual({n.casefold() for n in unused}, {n.casefold() for n in NEVER_LOADED})
        self.assertTrue(all(a.unused for a in sheets if a.group == "Never loaded by the game"))

    def test_table_has_one_entry_per_cut(self) -> None:
        table = vv1.sheet_table()
        seen = [(s.name.casefold(), s.cols, s.rows, tuple(s.sheets)) for s in table]
        self.assertEqual(len(seen), len(set(seen)))
        self.assertEqual(len([s for s in table if s.name.startswith("Map")]), 16)
        self.assertIn(("main_wide_button2.png", 3, 1), [(s.name, s.cols, s.rows) for s in table])

    def test_a_missing_file_drops_only_its_assets(self) -> None:
        class Partial(SizeSource):
            def read(self, name):
                return None if name.casefold().startswith(("berry", "mapx", "tech_bg")) else super().read(name)
        assets = vv1.assets(va.AssetSheets(Partial()))
        self.assertFalse([a for a in assets if a.key in ("berries", "island", "tech:screen")])
        self.assertTrue([a for a in assets if a.key == "hut1"])

    def test_island_rules(self) -> None:
        objs = vv1.island_objects({})
        self.assertIn(("scaffolding.png", 0x35A, 0x400, -1), objs)            # hut 1 always started
        self.assertIn(("boulder.png", 0x3DD, 0x53, -1), objs)
        built = vv1.island_objects(vv1.EVERYTHING_BUILT)
        self.assertEqual([o for o in built if o[0] == "smallHut.png"],
                         [("smallHut.png", 0x332, 0x3B0, -1), ("smallHut.png", 0xE1, 0x340, -1),
                          ("smallHut.png", 0xDC, 0x418, -1)])
        self.assertEqual(len([o for o in built if o[0] == "graves.png"]), 50)
        self.assertEqual(len([o for o in built if o[0].startswith("berry")]), 9)

    def test_dialog_rule(self) -> None:
        plan = vv1.dialog_plan(self.sheets, "GreenDlgTileGrid.png", 455, 400)
        self.assertEqual(len(plan), 8 * 7)                       # ceil(455 / 64) x ceil(400 / 64)
        self.assertEqual((plan[0].rect, plan[0].x, plan[0].y), ((512, 0, 576, 64), 0, 0))
        self.assertEqual(plan[-1].rect, (384, 0, 448, 64))

    def test_bars(self) -> None:
        self.assertEqual(len(vv1.skill_bar_plan(self.sheets, 3, 100)), 16)
        self.assertEqual(len(vv1.skill_bar_plan(self.sheets, 8, 1)), 1)       # the bulb alone
        self.assertEqual(len(vv1.loading_bar_plan(self.sheets, 100)), 80)
        self.assertEqual(vv1.loading_bar_plan(self.sheets, 2), [])

    def test_patcher_art_is_shipped(self) -> None:
        text = (ROOT / "scripts" / "build_release.py").read_text(encoding="utf-8")
        for name, where in vv1.patcher_art().items():
            self.assertIsNotNone(va.read_patcher_art(where), name)
            path = where[0] if isinstance(where, tuple) else where
            self.assertIn(path.relative_to(ROOT).as_posix(), text, name)


@unittest.skipUnless(ART.is_dir(), "a copy of A New Home's Images folder in research/game-images is needed")
class TheArt(unittest.TestCase):
    def test_sizes_are_the_games(self) -> None:
        names = sorted(p.name for p in ART.iterdir() if p.is_file() and p.suffix.casefold() in (".png", ".jpg"))
        self.assertEqual(sorted(names, key=str.casefold), GAME_FILES)
        source = va.GameFolderSource(ART.parent)
        sheets = va.AssetSheets(source)
        for name in names:
            self.assertEqual(sheets.size(name), SIZES[name], name)

    def test_png_assets_draw(self) -> None:
        sheets = va.AssetSheets(va.PatcherOverlay(va.GameFolderSource(ART.parent), vv1.patcher_art()))
        drawn = 0
        for asset in vv1.assets(sheets):
            for frame in asset.frames[:2]:
                if any(d.file.casefold().endswith(".jpg") or d.file == "empty1.png" for d in frame.plan):
                    continue                          # empty1.png is clear: the title's invisible buttons
                image = va.render_frame(sheets, frame)
                self.assertIsNotNone(image.bbox(), (asset.key, frame.label))
                drawn += 1
        self.assertGreater(drawn, 60)


if __name__ == "__main__":
    unittest.main()
