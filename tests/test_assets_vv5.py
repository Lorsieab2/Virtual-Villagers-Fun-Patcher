"""Picture Studio's Everything tab, New Believers: src/vv_assets_vv5.py proven against the game's own code.

* The sprite table: DESCRIPTORS is the stock executable's table 0x4CEFB8, record for record; every call of the
  engine's sprite constructors (whole 0x40AD50, cells 0x40B010, grid 0x40B0A0, strip 0x401000) and of the font
  constructor 0x402360 is either the table's getter or one of the sites sheet_table() lists (or a name the game's
  Images folder does not have); the font glyph tables are the exe's.
* Unused: no picture of UNUSED_FILES is named anywhere in the executable, and every other picture of the game's
  Images folder is built by a sprite of sheet_table().
* Every frame: the game's sprite draw 0x44FC70 is run in Unicorn for every table sprite with a picture and every
  one of its frames (the villager sheets' thousands of cells included); its one blit must be the plan's.
* The tech screen 0x440F80, the skill bars 0x4500E0 (every kind, values -100..100), the Divine Energy bar 0x450380
  (caps, energies and costs), the dialog boxes 0x40E160 / 0x40DFA0 (both colours, many sizes) and the island map's
  loader 0x47ABE0: each run in Unicorn, every blit (sheet, cell, place, scale, surface alpha) in order must be the
  plan's (vv_picture_image.Draw.key()).

The emulated checks need the stock executable (research/stock-executables), Unicorn and pefile, and the game's
pictures (research/game-images, never committed); they skip without them, as on CI.  The rest need nothing.
"""
from __future__ import annotations

import re
import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import vv_picture_image as pi  # noqa: E402
import vv_pictures_assets as va  # noqa: E402
import vv_assets_vv5 as v5  # noqa: E402

EXE = ROOT / "research" / "stock-executables" / "Virtual Villagers - New Believers.exe"
GAME = ROOT / "research" / "game-images" / "Virtual Villagers - New Believers"
IMAGES = GAME / "Images"
HAVE_IMAGES = IMAGES.is_dir()

try:
    import pefile
    import unicorn  # noqa: F401
    HAVE_UNICORN = True
except ImportError:  # pragma: no cover - CI may lack them
    HAVE_UNICORN = False
EMULATED = HAVE_UNICORN and EXE.is_file() and HAVE_IMAGES
WHY = "the stock New Believers executable, its pictures (research/), Unicorn and pefile are needed"

TABLE, RECORD, RECORDS = 0x4CEFB8, 0x30, 341
CTOR_WHOLE, CTOR_CELLS, CTOR_GRID, CTOR_STRIP, CTOR_FONT = 0x40AD50, 0x40B010, 0x40B0A0, 0x401000, 0x402360
SPRITE_DRAW, BLITTER = 0x44FC70, 0x404C40


def _f(v: float) -> int:
    return struct.unpack("<I", struct.pack("<f", v))[0]


def _u2f(u: int) -> float:
    return struct.unpack("<f", struct.pack("<I", u & 0xFFFFFFFF))[0]


def _s32(u: int) -> int:
    u &= 0xFFFFFFFF
    return u - (1 << 32) if u & 0x80000000 else u


def keys(plan) -> list[tuple]:
    return [d.key() for d in plan]


class Exe:
    """The stock executable, mapped (read only)."""

    def __init__(self) -> None:
        pe = pefile.PE(data=EXE.read_bytes())
        self.image = pe.get_memory_mapped_image()
        self.base = pe.OPTIONAL_HEADER.ImageBase
        text = [s for s in pe.sections if s.Name.startswith(b".text")][0]
        self.text_start = self.base + text.VirtualAddress
        self.text = self.image[text.VirtualAddress:text.VirtualAddress + text.Misc_VirtualSize]

    def dword(self, va_: int) -> int:
        return struct.unpack_from("<I", self.image, va_ - self.base)[0]

    def int(self, va_: int) -> int:
        return struct.unpack_from("<i", self.image, va_ - self.base)[0]

    def cstr(self, va_: int) -> str:
        at = va_ - self.base
        return self.image[at:self.image.index(b"\0", at)].decode("latin-1")

    def calls_to(self, target: int) -> list[int]:
        out, i = [], 0
        while True:
            i = self.text.find(b"\xE8", i)
            if i < 0 or i + 5 > len(self.text):
                return out
            if self.text_start + i + 5 + struct.unpack_from("<i", self.text, i + 1)[0] == target:
                out.append(self.text_start + i)
            i += 1

    def pushed_string_before(self, site: int, back: int = 16) -> str | None:
        """The string a `push imm32` in the few bytes before a call names (None when there is none)."""
        window = self.image[site - back - self.base:site - self.base]
        for m in reversed(list(re.finditer(rb"\x68(....)", window, re.S))):
            target = struct.unpack("<I", m.group(1))[0]
            if self.base < target < self.base + len(self.image):
                try:
                    text = self.cstr(target)
                except ValueError:
                    continue
                if text.casefold().endswith((".png", ".jpg")):
                    return text
        return None


def table_records(exe: Exe) -> list[tuple]:
    out = []
    for k in range(RECORDS):
        at = TABLE + k * RECORD
        ident = exe.dword(at)
        name, cols, rows, suffix, across, down = struct.unpack_from("<IiiIii", exe.image, at + 4 - exe.base)
        out.append((ident, exe.cstr(name), cols, rows, across if suffix else 0, down if suffix else 0,
                    exe.cstr(suffix) if suffix else ""))
    return out


# ------------------------------------------------------------------ what needs nothing (CI)

class Rules(unittest.TestCase):
    def test_table_shape(self) -> None:
        self.assertEqual(len(v5.DESCRIPTORS), RECORDS)
        self.assertEqual(len({r[0] for r in v5.DESCRIPTORS}), RECORDS)
        specs = v5.sheet_table()
        self.assertEqual(len({(s.name.casefold(), s.cols, s.rows, tuple(s.sheets), s.whole) for s in specs}),
                         len(specs))
        grid = [s for s in specs if s.atlas.grid]
        self.assertEqual({s.name for s in grid}, {"female_heads", "female_bodies", "female_actions", "male_heads",
                                                    "male_bodies", "male_actions", "bigheads"})

    def test_spec_rules(self) -> None:
        """0x44FA40: rows > 0 cells (or a grid with a suffix), rows 0 and columns > 0 a strip, else whole."""
        self.assertIsNone(v5.spec_of((0, "No Graphic", 0, 0, 0, 0)))
        self.assertTrue(v5.spec_of((1, "hand_open.png", 0, 0, 0, 0)).whole)
        strip = v5.spec_of((0x75, "popup_button1.png", 3, 0, 0, 0))
        self.assertEqual((strip.cols, strip.rows, strip.whole), (3, 1, False))
        cells = v5.spec_of((0xE8, "carrying.png", 13, 7, 0, 0))
        self.assertEqual((cells.cols, cells.rows), (13, 7))
        grid = v5.spec_of((0xFA, "female_bodies", 32, 30, 2, 3))
        self.assertEqual(grid.files()[:3], ["female_bodies00.png", "female_bodies10.png", "female_bodies01.png"])

    def test_slices(self) -> None:
        self.assertEqual(v5.skill_slices(100), (64, 32))
        self.assertEqual(v5.skill_slices(1), (0, 0))
        self.assertEqual(v5.skill_slices(2), (1, 0))
        self.assertEqual(v5.skill_slices(-100), (-64, -32))
        self.assertEqual(v5.skill_slices(500), (64, 32))
        self.assertEqual(v5.energy_slices(1000, 1000, 0), (1000, 93, 93, 0))
        self.assertEqual(v5.energy_slices(5, 5, 0)[0], 10)
        self.assertEqual(v5.energy_slices(100, 50, 25), (100, 9, 4, 2))

    def test_assets_tolerate_no_pictures(self) -> None:
        sheets = va.AssetSheets(None)
        self.assertEqual(v5.assets(sheets), [])
        self.assertEqual(va.source_sheet_assets(sheets, v5.sheet_table(), files=[]), [])

    def test_fonts_and_names(self) -> None:
        for which in (0, 1):
            glyphs = v5.font_glyphs(which)
            self.assertEqual(len(glyphs), 190)
            self.assertTrue(all(left < right for _c, left, right in glyphs))
        self.assertEqual(v5.map_tile(3, 1), "LargeMap3X1Y.jpg")
        art = v5.patcher_art()
        self.assertEqual([n for n, w in art.items() if va.read_patcher_art(w) is None], [])

    def test_patcher_art_ships(self) -> None:
        """Only art the release ships (scripts/build_release.py): the mushroom and the masks by name, the Origins
        icons inside the shipped VV5 Origins DLL (native/vv5_task9_origins/vv5_task9_origins.rc)."""
        release = (ROOT / "scripts" / "build_release.py").read_text(encoding="utf-8")
        for name in ("assets/golden_mushroom/golden_mushroom.png", "assets/vv5_bighead_masks/bigheads_masks.png",
                     "data/candidates/VVFP VV5 Task9 Origins Icons.dll"):
            self.assertIn(name, release)
        rc = (ROOT / "native" / "vv5_task9_origins" / "vv5_task9_origins.rc").read_text(encoding="utf-8")
        for stem, _label in v5.ORIGINS_ICONS:
            self.assertIn(f"assets/origins/{stem}.ico", rc)
        stub = (ROOT / "native" / "vvfp_golden_mushroom" / "vvfp_golden_mushroom.c").read_text(encoding="utf-8")
        self.assertIn("LATER_STUB(vv5, 0x4DC808, 0x44F385u, 7, 1)", stub)


# ------------------------------------------------------------------ read from the executable

@unittest.skipUnless(HAVE_UNICORN and EXE.is_file(), "the stock New Believers executable and pefile are needed")
class ExecutableFacts(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.exe = Exe()

    def test_descriptors_are_the_table(self) -> None:
        records = table_records(self.exe)
        self.assertEqual([r[:6] for r in records], [tuple(d) for d in v5.DESCRIPTORS])
        self.assertEqual({r[6] for r in records if r[6]}, {v5.GRID_SUFFIX})
        # the getter 0x44F760 searches 0x4CEFB8 .. 0x4D3068 (345 slots): the 4 after the 341 records are empty
        self.assertIn(b"\x3d\x68\x30\x4d\x00", self.exe.image[0x44F791 - self.exe.base:0x44F798 - self.exe.base])
        self.assertEqual((0x4D3068 - TABLE) // RECORD, RECORDS + 4)
        for k in range(RECORDS, RECORDS + 4):
            self.assertEqual(self.exe.dword(TABLE + k * RECORD + 4), 0, k)

    def test_every_constructor_call_is_accounted_for(self) -> None:
        """Every call of the sprite and font constructors, in the whole executable."""
        engine = {  # the table's getters, the constructors' own calls, and the button class (a strip it is given)
            0x44F817, 0x44F8DF, 0x44F959, 0x44F99E, 0x44FAE5, 0x40B03D, 0x401011, 0x401738}
        named = {name.casefold() for name, _c, _r, _w in v5.DIRECT}
        absent = {"menu_logo.png", "loading_logo.png", "splash1_bg.jpg", "splash2_bg.jpg", "splash3_bg.jpg"}
        seen = set()
        for ctor in (CTOR_WHOLE, CTOR_CELLS, CTOR_GRID, CTOR_STRIP):
            for site in self.exe.calls_to(ctor):
                if site in engine:
                    continue
                if site == 0x47AC6C:                                            # the map's tiles
                    continue
                name = self.exe.pushed_string_before(site)
                self.assertIsNotNone(name, hex(site))
                self.assertIn(name.casefold(), named | absent, hex(site))
                seen.add(name.casefold())
        self.assertEqual(seen, named | absent)
        self.assertEqual(self.exe.calls_to(CTOR_FONT), [0x41E889, 0x41E8F9])
        self.assertEqual([self.exe.cstr(self.exe.dword(a)) for a in (0x41E875, 0x41E8E5)],
                         ["ldwarialbold", "ldwBurweed27"])
        self.assertEqual(self.exe.image[0x4956B4 - self.exe.base:0x4956B9 - self.exe.base], b".png\0")
        # the puzzle covers' cut and the map's name pattern
        self.assertEqual(self.exe.image[0x448AE9 - self.exe.base:0x448AED - self.exe.base], b"\x6a\x04\x6a\x04")
        self.assertEqual(self.exe.cstr(0x4B8ED8), "%s%01dX%01dY.jpg")
        self.assertEqual(self.exe.cstr(self.exe.dword(0x4D96B4)), v5.MAP_PREFIX)

    def test_font_glyph_tables(self) -> None:
        for which, (_name, _label, height, table) in enumerate(v5.FONTS_TABLE):
            at, got = int(table, 16), []
            while True:
                code, left, top, right, bottom = struct.unpack_from("<5i", self.exe.image, at - self.exe.base)
                if code == 0:
                    break
                self.assertEqual((top, bottom), (0, height))
                got.append((code, left, right))
                at += 20
            self.assertEqual(got, v5.font_glyphs(which))

    def test_draw_constants(self) -> None:
        e = self.exe
        self.assertEqual([(e.dword(0x4CD220 + 16 * k), e.int(0x4CD224 + 16 * k), e.int(0x4CD228 + 16 * k))
                          for k in range(6)], [line[:3] for line in v5.TECH_LINES])
        self.assertEqual(tuple(e.int(0x49A19C + 4 * k) for k in range(11)), v5.POWER_COSTS)
        self.assertEqual(tuple((e.int(0x4CD300 + 8 * k), e.int(0x4CD304 + 8 * k)) for k in range(11)),
                         v5.POWER_SPOTS)
        self.assertEqual(struct.unpack_from("<f", e.image, 0x498938 - e.base)[0], v5.OFF_BACK_ALPHA)
        # the 13 callers of 0x4500E0 pass kinds 3-8 and 11 (never 9 or 10)
        kinds = set()
        for site in e.calls_to(0x4500E0):
            window = e.image[site - 16 - e.base:site - e.base]
            m = re.search(rb"\x6a(.)\xe8....\x8b\xc8$", window, re.S)
            self.assertIsNotNone(m, hex(site))
            kinds.add(m.group(1)[0])
        self.assertEqual(kinds, {3, 4, 5, 6, 7, 8, 11})
        self.assertEqual(len(e.calls_to(0x4500E0)), 13)
        # the only references to the dialog padding globals are reads in 0x40DF20 / 0x40DF80, both 0 in the file
        for g in (0x4DB334, 0x4DB338):
            self.assertEqual(e.dword(g), 0)

    def test_unused_files_are_never_named(self) -> None:
        strings = {m.group(1).decode("latin-1").casefold()
                   for m in re.finditer(rb"(?<=[\x00@])([\x20-\x7e]{3,120})\x00", bytes(self.exe.image))}
        for name in v5.UNUSED_FILES:
            self.assertNotIn(name.casefold(), strings, name)
            self.assertNotIn(name.casefold().rsplit(".", 1)[0], strings, name)
            self.assertNotIn(name.casefold(), {r[1].casefold() for r in v5.DESCRIPTORS})

    @unittest.skipUnless(HAVE_IMAGES, "the game's pictures are needed")
    def test_every_picture_is_built_or_unused(self) -> None:
        built = {n.casefold() for spec in v5.sheet_table() for n in spec.files()}
        unused = {n.casefold() for n in v5.UNUSED_FILES}
        pictures = [p.name for p in IMAGES.iterdir() if p.suffix.casefold() in va.PICTURE_EXTENSIONS]
        self.assertGreater(len(pictures), 400)
        for name in pictures:
            self.assertTrue((name.casefold() in built) != (name.casefold() in unused), name)


# ------------------------------------------------------------------ the game's draws, in Unicorn

if EMULATED:
    import test_pictures_vv5 as tp

    class Emu(tp.Game):
        """New Believers in Unicorn (tests/test_pictures_vv5.Game) with pictures of their real sizes (PNG and
        JPEG), every blit recorded: the software blitter 0x404C40 and SDL_UpperBlit (the strips' path)."""

        def __init__(self) -> None:
            super().__init__()
            p = self.p
            renderer, wrapper = p.alloc(0x100), p.alloc(0x10)
            p.put32(wrapper, renderer)
            p.put32(0x4DB0E8, wrapper)                                   # 0x4080C0's renderer
            p.write(renderer + 0x60, struct.pack("<iiii", 0, 0, 4000, 4000))   # its clip
            self.blits: list[tuple] = []
            self.loaded: list[str] = []
            p.stub(BLITTER, self._blit)
            p.api_handlers["SDL_UpperBlit"] = self._sdl_blit
            p.api_handlers["SDL_MapRGB"] = lambda q: (0, 0)
            p.api_handlers["SDL_FillRect"] = self._fill
            self.world = p.alloc(0x18000)                                # the village manager 0x425950 returns
            p.stub(0x425950, lambda q: (self.world, 0))
            self.mgr = p.call(0x44FBB0)                                  # the sprite manager {table, renderer}

        def _img_load(self, q):
            path = IMAGES / Path(q.cstring(q.arg(0)).replace("\\", "/")).name
            w, h = va.picture_size(pi._read_from(IMAGES, path.name))
            s = self.surface(w, h)
            self.surfaces[s] = path.name
            self.loaded.append(path.name)
            return s, 0

        def _sprintf(self, q):
            fmt, k = q.cstring(q.arg(1)), 2
            out = []
            for piece in re.split(r"(%[0-9]*[sd])", fmt):
                if piece.startswith("%"):
                    v = q.arg(k)
                    k += 1
                    out.append(q.cstring(v) if piece.endswith("s") else f"{_s32(v):{piece[1:-1] or ''}d}")
                else:
                    out.append(piece)
            text = "".join(out).encode("latin-1") + b"\0"
            q.write(q.arg(0), text)
            return len(text) - 1, 0

        def _blit(self, q):
            rect = tuple(_s32(q.arg(k)) for k in range(3, 7))
            self.blits.append((self.surfaces[q.arg(0)].casefold(), rect, _s32(q.arg(1)), _s32(q.arg(2)),
                               round(_u2f(q.arg(8)), 6), pi.surface_alpha(_u2f(q.arg(7)))))
            return 0, 0x28

        def _sdl_blit(self, q):
            p = self.p
            src, srect, drect = q.arg(0), q.arg(1), q.arg(3)
            x, y, w, h = struct.unpack("<iiii", p.read(srect, 16))
            dx, dy = struct.unpack("<ii", p.read(drect, 8))
            self.blits.append((self.surfaces[src].casefold(), (x, y, x + w, y + h), dx, dy, 1.0, 255))
            return 0, 0

        def _fill(self, q):
            rect = q.arg(1)
            self.fills.append(struct.unpack("<iiii", self.p.read(rect, 16)) if rect else None)
            return 0, 0

        def run(self, fn: int, args=(), ecx: int = 0) -> list[tuple]:
            """The blits of one call; the screen fills it makes (a colour, not a picture) go to .fills."""
            self.blits, self.fills = [], []
            self.p.call(fn, list(args), ecx=ecx)
            return self.blits


def _plan_keys(plan) -> list[tuple]:
    out = []
    for d in plan:
        k = d.key()
        out.append((k[0],) + k[1:])
    return out


@unittest.skipUnless(EMULATED, WHY)
class DrawsMatchTheGame(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.g = Emu()
        cls.sheets = va.AssetSheets(va.GameFolderSource(GAME))

    def test_every_frame_of_every_sprite(self) -> None:
        """0x44FC70 (id, frame, 0, 0, 1.0, 100) for every table sprite with a picture, every frame."""
        g, count = self.g, 0
        for rec in v5.DESCRIPTORS:
            spec = v5.spec_of(rec)
            if spec is None or not all(self.sheets.has(n) for n in spec.files()):
                continue
            for frame in range(v5.cell_count(rec)):
                got = g.run(SPRITE_DRAW, [rec[0], frame, 0, 0, _f(1.0), 100], ecx=g.mgr)
                self.assertEqual(got, [v5._cell(self.sheets, rec, frame).key()], (hex(rec[0]), rec[1], frame))
                count += 1
        self.assertGreater(count, 5000)

    def test_tech_screen(self) -> None:
        g, p = self.g, self.g.p
        screen = p.alloc(0x200)
        for k in range(18):
            p.write(screen + 0x84 + 4 * k, struct.pack("<f", 1.0))      # every bar's fade finished
        p.write(screen + 0xCC, struct.pack("<f", 1.0))                  # the icons' fade
        p.put32(screen + 0x40, p.alloc(0x40))
        levels = [0] * 6
        p.stub(0x423600, lambda q: (levels[q.arg(0)], 4))              # levels bought on a line
        for fn, pop in ((0x44F0F0, 12), (0x41DB20, 0), (0x44F130, 0), (0x46F5B0, 0), (0x40D8D0, 4)):
            p.stub(fn, lambda q, pop=pop: (0, pop))                     # camera, cursor and text after the screen
        cases = 0
        for lv in ((0,) * 6, (1,) * 6, (2,) * 6, (3,) * 6, (3, 2, 1, 0, 1, 2), (0, 3, 0, 3, 0, 3)):
            for cap in (0, 9, 10, 24, 25, 99, 100, 150, 300, 499, 500, 700, 800, 1000):
                levels[:] = lv
                p.put32(g.world + 0x17D60, cap)
                got = g.run(0x440F80, ecx=screen)
                self.assertEqual(g.fills, [(0, 0, 1024, 768)])                 # 0x408110: the screen cleared first
                self.assertEqual(got, keys(v5.tech_screen_plan(self.sheets, lv, cap)), (lv, cap))
                cases += 1
        self.assertEqual(cases, 84)

    def test_tech_icon_fades(self) -> None:
        """While an icon fades in, its backing and icon share the fade's alpha (+0.02 a frame up to 1.0)."""
        g, p = self.g, self.g.p
        screen = p.alloc(0x200)
        p.put32(screen + 0x40, p.alloc(0x40))
        p.stub(0x423600, lambda q: (0, 4))
        for fn, pop in ((0x44F0F0, 12), (0x41DB20, 0), (0x44F130, 0), (0x46F5B0, 0), (0x40D8D0, 4)):
            p.stub(fn, lambda q, pop=pop: (0, pop))
        p.put32(g.world + 0x17D60, 1000)
        for start in (0.0, 0.3, 0.5, 0.97, 0.99):
            p.write(screen + 0xCC, struct.pack("<f", start))
            got = g.run(0x440F80, ecx=screen)
            fade = struct.unpack("<f", p.read(screen + 0xCC, 4))[0]
            self.assertEqual(fade, min(1.0, pi.f32(pi.f32(start) + 0.02)))
            want = [v5._cell(self.sheets, v5.descriptor(v5.TECH_BG), 0).key()]
            for power, (x, y) in enumerate(v5.POWER_SPOTS):
                want += keys(v5.power_icon_plan(self.sheets, power, True, x, y, fade))
            self.assertEqual(got, want, start)

    def test_skill_bars(self) -> None:
        g = self.g
        meter = g.p.call(0x450530)
        cases = 0
        for kind in (3, 4, 5, 6, 7, 8, 9, 10, 11):
            for value in (-150, -100, -99, -51, -7, -4, -1, 0, 1, 2, 3, 4, 7, 25, 33, 50, 64, 75, 99, 100, 101):
                for y in (0, 37):
                    got = g.run(0x4500E0, [kind, value & 0xFFFFFFFF, y], ecx=meter)
                    self.assertEqual(got, keys(v5.skill_bar_plan(self.sheets, kind, value, y)), (kind, value, y))
                    cases += 1
        self.assertEqual(cases, 378)

    def test_divine_energy_bar(self) -> None:
        g = self.g
        meter = g.p.call(0x450530)
        cases = 0
        for cap in (0, 5, 10, 11, 99, 100, 372, 400, 650, 999, 1000, 1500):
            for energy in (0, 1, 3, 4, 50, 99, 100, 200, 333, 400, 999, 1000):
                for cost in (0, 10, 150, 800):
                    got = g.run(0x450380, [0x269, 0xC, cap, energy, cost], ecx=meter)
                    self.assertEqual(got, keys(v5.energy_bar_plan(self.sheets, cap, energy, cost)), (cap, energy, cost))
                    cases += 1
        self.assertEqual(cases, 576)

    def test_hud_backing(self) -> None:
        """The HUD's backing: 0x4431E8 draws sprite 0x11 through 0x44FEF0 at (0x266, 0xA), alpha 1, 100%."""
        g = self.g
        got = g.run(0x44FEF0, [v5.MANA_BG, 0x266, 0xA, _f(1.0), 100], ecx=g.mgr)
        self.assertEqual(got, [v5._cell(self.sheets, v5.descriptor(v5.MANA_BG), 0, 0x266, 0xA).key()])
        exe = Exe()
        self.assertEqual(exe.image[0x4431D9 - exe.base:0x4431E8 - exe.base],
                         b"\x6a\x64\x51\xd9\x1c\x24\x6a\x0a\x68\x66\x02\x00\x00\x6a\x11")
        self.assertEqual(exe.image[0x443210 - exe.base:0x443217 - exe.base], b"\x6a\x0c\x68\x69\x02\x00\x00")

    def test_dialog_boxes(self) -> None:
        g, p = self.g, self.g.p
        cases = 0
        for ident, _colour in v5.DIALOGS:
            sprite = p.call(0x44FA30, [ident], ecx=g.mgr)
            for w, h in v5.DIALOG_SIZES + ((1, 1), (64, 64), (65, 65), (128, 100), (300, 129), (1024, 768)):
                for x, y, alpha in ((0, 0, 1.0), (100, 37, 1.0), (5, 9, 0.5)):
                    frame = p.alloc(0x40)
                    p.call(0x40E160, [sprite, w, h], ecx=frame)
                    got = g.run(0x40DFA0, [x, y, _f(alpha)], ecx=frame)
                    self.assertEqual(got, keys(v5.dialog_plan(self.sheets, ident, w, h, x, y, alpha)), (ident, w, h))
                    cases += 1
        self.assertEqual(cases, 60)

    def test_island_map(self) -> None:
        """0x47ABE0 builds the 25 tiles by its name pattern and stores each at (512 X, 512 Y)."""
        g, p = self.g, self.g.p
        obj = p.alloc(0x400)
        g.loaded = []
        p.call(0x47ABE0, ecx=obj)
        self.assertEqual(g.loaded, [v5.map_tile(x, y) for x, y in v5.MAP_TILES])
        places = []
        for x, y in v5.MAP_TILES:
            at = obj + x * 0x3C + y * 0xC
            self.assertNotEqual(p.u32(at), 0)
            places.append((_s32(p.u32(at + 4)), _s32(p.u32(at + 8))))
        self.assertEqual(places, [(d.x, d.y) for d in v5.map_plan(self.sheets)])


@unittest.skipUnless(HAVE_IMAGES, "the game's pictures are needed")
class Pictures(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.sheets = va.AssetSheets(va.PatcherOverlay(va.GameFolderSource(GAME), v5.patcher_art()))
        cls.assets = va.all_assets(5, cls.sheets, v5)

    def test_listing(self) -> None:
        keys_ = [a.key for a in self.assets]
        self.assertEqual(len(keys_), len(set(keys_)))
        self.assertTrue(all(a.category in va.CATEGORIES for a in self.assets))
        cats = {a.category for a in self.assets}
        for cat in (va.TECH, va.METERS, va.PANELS, va.SCENE, va.FONTS, va.PATCHER, va.UNUSED, va.CREATURES,
                    va.BUILDINGS, va.PUZZLES, va.COLLECTIBLES, va.PLANTS, va.VILLAGERS, va.EFFECTS, va.SCREENS,
                    va.CURSORS, va.ICONS, va.SHEETS):
            self.assertIn(cat, cats)
        self.assertTrue(all(a.unused for a in self.assets if a.category == va.UNUSED))
        self.assertTrue(all(a.patcher for a in self.assets if a.category == va.PATCHER))

    def test_some_pictures_render(self) -> None:
        by_key = {a.key: a for a in self.assets}
        for key in ("meter:energy", "dialog:76", "patcher:golden", "font:0", "sprite:107", "meter:skill:3"):
            image = va.render_frame(self.sheets, by_key[key].frames[-1])
            self.assertIsNotNone(image.bbox(), key)
        screen = va.render_frame(self.sheets, by_key["tech:screen"].frames[3])
        self.assertEqual((screen.width, screen.height), (1024, 768))


if __name__ == "__main__":
    unittest.main()
