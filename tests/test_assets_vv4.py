"""Picture Studio "Everything", The Tree of Life: src/vv_assets_vv4.py proven against the stock executable.

* The sprite table: vv_assets_vv4.TABLE is the exe's own 305-entry table at 0x4C07C8 (the registry's lookup
  0x44C8A0 scans 0x4C07C8 - 0x4C40F8); every call of the engine's picture constructors (0x40A840, 0x40AB10,
  0x40ABA0, 0x401010) and of the font loader (0x4023B0) is one the module knows; every picture name the exe holds
  is in sheet_table().
* The cut: every frame of every sprite the game's registry builds (its own constructors run in Unicorn, only the
  file reader 0x40B050 answered with each file's real size) drawn by the game's 0x44CEC0 must be
  vv_picture_image.Atlas.cell's.
* The composed assets: the game's draw code runs down to its blits (0x404CB0 / 0x404C40 recorded) and every blit
  must be the plan's, in order (Draw.key()): buttons 0x401200, the Tech screen 0x43E640, the bars 0x44D070, the
  loading meter 0x44DB10, the island map 0x46FCE0 + 0x46FE10, the huts 0x42FF80, the fonts 0x4027A0 (the glyph
  table it leaves), the Golden Mushroom through 0x44C640; the screens' fixed art from the exe's own call
  arguments.
* Without the exe or the pictures: the pure rules (the font wrap, the bar counts, the table's shape, the patcher
  art the release ships).

The emulated checks need research/stock-executables, research/game-images (the sizes) and Unicorn; they skip in CI.
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
import vv_assets_vv4 as a4  # noqa: E402

EXE = ROOT / "research" / "stock-executables" / "Virtual Villagers - The Tree of Life.exe"
ART = ROOT / "research" / "game-images" / "Virtual Villagers - The Tree of Life"

try:
    import pefile
    from unicorn.x86_const import UC_X86_REG_FPCW
    from story_emulator import API_STUBS, Process
    HAVE_UNICORN = True
except ImportError:                     # CI without Unicorn
    HAVE_UNICORN = False
try:
    import pefile  # noqa: F811
    HAVE_PEFILE = True
except ImportError:
    HAVE_PEFILE = False

HAVE_ART = (ART / "Images").is_dir()
EMULATED = HAVE_UNICORN and EXE.is_file() and HAVE_ART
CAMERA = 0x4DB9F8


def f32bits(v: float) -> int:
    return struct.unpack("<I", struct.pack("<f", v))[0]


def bitsf(v: int) -> float:
    return struct.unpack("<f", struct.pack("<I", v & 0xFFFFFFFF))[0]


def s32(v: int) -> int:
    return v - (1 << 32) if v & 0x80000000 else v


def keys(plan) -> list:
    return [d.key() for d in plan]


_SHEETS = None


def sheets() -> va.AssetSheets:
    """The game's pictures (sizes and pixels from research/game-images) with the patcher's art over them."""
    global _SHEETS
    if _SHEETS is None:
        _SHEETS = va.AssetSheets(va.PatcherOverlay(pi.FolderSource(ART), a4.patcher_art()))
    return _SHEETS


class Image:
    """The exe as mapped: its bytes by address."""

    def __init__(self) -> None:
        pe = pefile.PE(str(EXE))
        self.base = pe.OPTIONAL_HEADER.ImageBase
        self.img = pe.get_memory_mapped_image()
        self.text = next(s for s in pe.sections if s.Name.rstrip(b"\0") == b".text")

    def read(self, va_: int, n: int) -> bytes:
        return self.img[va_ - self.base:va_ - self.base + n]

    def u32(self, va_: int) -> int:
        return struct.unpack("<I", self.read(va_, 4))[0]

    def cstr(self, va_: int) -> str:
        raw = self.read(va_, 256)
        return raw[:raw.find(b"\0")].decode("latin-1")

    def calls_to(self, target: int) -> list[int]:
        """Every `call rel32` (E8) in .text whose target is `target`."""
        start = self.base + self.text.VirtualAddress
        code = self.read(start, self.text.Misc_VirtualSize)
        out = []
        for m in re.finditer(b"\xE8", code):
            at = m.start()
            if at + 5 > len(code):
                continue
            rel = struct.unpack_from("<i", code, at + 1)[0]
            if start + at + 5 + rel == target:
                out.append(start + at)
        return out


class TreeOfLife:
    """The stock exe in Unicorn: the game's own sprite registry and constructors, with only the file reader
    (0x40B050: a sheet's surface from its file) answered here with each picture's real size, operator new
    and sprintf answered, and every blit (0x404CB0 scaled / faded, 0x404C40 plain) recorded."""

    def __init__(self) -> None:
        self.p = p = Process(EXE.read_bytes())
        p.mu.mem_map(API_STUBS, 0x10000)
        p.api_names = {}
        slot = 0
        for entry in p._exe_pe.DIRECTORY_ENTRY_IMPORT:
            for imp in entry.imports:
                if not imp.name:
                    continue
                stub = API_STUBS + slot * 16
                slot += 1
                p.mu.mem_write(stub, b"\xC3")
                p.api_names[stub] = imp.name.decode()
                p.mu.mem_write(imp.address, struct.pack("<I", stub))
        self.surfaces: dict[int, str] = {}
        self.blits: list = []
        p.stub(0x470C5C, lambda q: (q.alloc(max(q.arg(0), 4)), 0))       # operator new
        p.stub(0x470B7B, lambda q: (0, 0))                               # free
        p.stub(0x40B050, self._sheet)                                    # a sheet's surface from its file
        p.stub(0x40AF70, lambda q: (1, 0))                               # the file is there
        p.stub(0x404CB0, self._blit)
        p.stub(0x404C40, self._plain)
        p.stub(0x4716DB, self._sprintf)
        for other in (0x404770, 0x404830, 0x4046F0, 0x404280):           # no other blitter may be reached
            p.stub(other, self._unexpected(other))
        self.registry = p.alloc(0x40)
        p.put32(self.registry, p.alloc(0x40))
        p.stub(0x44CCF0, lambda q: (self.registry, 0))                   # the registry object (0x44CB40's)
        self.gfx = p.alloc(0x100)
        self.wrap = p.alloc(0x10)
        p.put32(self.wrap, self.gfx)
        p.put32(0x4CB928, self.wrap)                                     # 0x408130: the graphics
        p.put32(self.registry + 4, self.wrap)
        p.write(self.gfx + 0x60, struct.pack("<iiii", -100000, -100000, 100000, 100000))   # no clipping
        self.call(0x44C3E0, [0, 0, f32bits(1.0)], ecx=CAMERA)            # the camera at rest, zoom 1

    @staticmethod
    def _unexpected(at):
        def fn(q):
            raise AssertionError(f"the draw reached the blitter {at:#x}, which this test does not record")
        return fn

    def _sheet(self, q):
        this, name = q.reg("ecx"), q.cstring(q.arg(0))
        try:
            w, h = sheets().size(name)
        except pi.PictureError:
            w = h = 0
        surface = 0
        if w:
            surface = q.alloc(0x40)
            q.put32(surface + 8, w)
            q.put32(surface + 12, h)
            self.surfaces[surface] = name
        q.put32(this, surface)
        q.write(this + 4, bytes([1 if name.casefold().endswith(".png") else 0]))
        return this, 4

    def _record(self, surface, x, y, rect, scale, alpha):
        self.blits.append((self.surfaces.get(surface, hex(surface)).casefold(), rect, s32(x), s32(y), scale, alpha))

    def _blit(self, q):
        a = [q.arg(i) for i in range(10)]
        self._record(a[0], a[1], a[2], tuple(s32(v) for v in a[3:7]), round(bitsf(a[8]), 6),
                     pi.surface_alpha(bitsf(a[7])))
        return 0, 0x28

    def _plain(self, q):
        a = [q.arg(i) for i in range(7)]
        self._record(a[0], a[1], a[2], tuple(s32(v) for v in a[3:7]), 1.0, 255)
        return 0, 0x1C

    def _sprintf(self, q):
        buf, fmt = q.arg(0), q.cstring(q.arg(1))
        k = [2]

        def one(m):
            v = q.arg(k[0])
            k[0] += 1
            return q.cstring(v) if m.group(2) == "s" else ("%" + m.group(1) + "d") % s32(v)
        out = re.sub(r"%([0-9]*)([sdi])", one, fmt)
        q.write(buf, out.encode("latin-1") + b"\0")
        return len(out), 0

    def call(self, addr: int, args, ecx=None) -> int:
        self.p.mu.reg_write(UC_X86_REG_FPCW, 0x027F)          # Windows runs the x87 at 53 bits
        return self.p.call(addr, list(args), ecx=ecx, limit=5_000_000)

    def run(self, addr: int, args, ecx=None) -> list:
        self.blits = []
        self.call(addr, args, ecx)
        return list(self.blits)

    def frame(self, sid: int, frame: int, x: int, y: int) -> list:
        """0x44CEC0(id, frame, x, y, 1.0, 100): the registry builds the sprite (first use) and draws a frame."""
        return self.run(0x44CEC0, [sid, frame, x, y, f32bits(1.0), 100], self.registry)


_GAME = None


def game() -> TreeOfLife:
    global _GAME
    if _GAME is None:
        _GAME = TreeOfLife()
    return _GAME


# ------------------------------------------------------------------------------------------- the exe's tables

@unittest.skipUnless(HAVE_PEFILE and EXE.is_file(), "the vanilla The Tree of Life is needed")
class TheExesSprites(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.x = Image()

    def test_the_table_is_the_exes(self) -> None:
        x = self.x
        self.assertEqual(len(a4.TABLE), (0x4C40F8 - a4.TABLE_AT) // a4.TABLE_STRIDE)
        for i, row in enumerate(a4.TABLE):
            at = a4.TABLE_AT + i * a4.TABLE_STRIDE
            sid, name, cols, rows, suffix, across, down = (x.u32(at + 4 * k) for k in range(7))
            self.assertEqual(row, (sid, x.cstr(name), cols, rows, x.cstr(suffix) if suffix else "", across, down), i)
        # the registry's lookup bound: cmp eax, 0x4C40F8 (0x44C8D1)
        self.assertEqual(x.read(0x44C8D1, 5), b"\x3D" + struct.pack("<I", 0x4C40F8))

    def test_every_constructor_call_is_known(self) -> None:
        x = self.x
        known = {
            0x40A840: {0x40AB3D, 0x42079B, 0x4207E0, 0x4458FF, 0x4466A4, 0x4466EB, 0x446732, 0x446779, 0x44CC25,
                       0x46FD6C},
            0x40AB10: {0x401021, 0x401788, 0x445934, 0x44CADE},
            0x40ABA0: {0x44CA99},
            0x401010: {0x44C957, 0x44CA1F},
            0x4023B0: {0x41D869, 0x41D8D9},
        }
        for target, sites in known.items():
            self.assertEqual(set(x.calls_to(target)), sites, hex(target))
        # the named ones push their picture's name: push imm32 (68 xx xx xx xx) just before
        named = {0x42079B: "menu_logo.png", 0x4207E0: "loading_logo.png", 0x4458FF: "puzzles_bg.jpg",
                 0x4466A4: "SPLASH_BG.JPG", 0x4466EB: "SPLASH1_BG.JPG", 0x446732: "SPLASH2_BG.JPG",
                 0x446779: "SPLASH3_BG.JPG"}
        for site, name in named.items():
            raw = x.read(site - 0x40, 0x40)                                     # the name's address, loaded
            refs = [struct.unpack_from("<I", raw, k)[0] for k in range(len(raw) - 3)]
            self.assertIn(name, [x.cstr(r) for r in refs if x.base <= r < x.base + len(x.img)], hex(site))
        raw = x.read(0x445934 - 16, 16)                                         # push 4; push 4; push name
        at = raw.rfind(b"\x6A\x04\x6A\x04\x68")
        self.assertNotEqual(at, -1)
        self.assertEqual(x.cstr(struct.unpack_from("<I", raw, at + 5)[0]), "puzzle_covers.png")
        for site, (font, picture, table, _g) in zip((0x41D869, 0x41D8D9), a4.FONTS):
            raw = x.read(site - 0x1C, 12)                                       # push 0; push table; push name
            self.assertEqual(raw[:3], b"\x6A\x00\x68", font)
            self.assertEqual(struct.unpack_from("<I", raw, 3)[0], table, font)
            self.assertEqual(raw[7], 0x68, font)
            self.assertEqual(x.cstr(struct.unpack_from("<I", raw, 8)[0]), font)
            self.assertEqual(picture, font + x.cstr(0x48A6A0))
        # the map tiles' name and the font picture's suffix
        self.assertEqual(x.cstr(0x4AB3D8), "%sX%01dY%01d.jpg")
        self.assertEqual(x.cstr(x.u32(0x4C9ECC)), "Map")
        self.assertEqual(x.cstr(0x48A6A0), ".png")

    def test_every_picture_name_in_the_exe_is_built(self) -> None:
        x = self.x
        listed = {s.name.casefold() for s in a4.sheet_table()} | {f.casefold() for s in a4.sheet_table() for f in s.files()}
        data = x.img
        names = set()
        for m in re.finditer(rb"[\x20-\x7e]{3,}\x00", data):
            text = m.group()[:-1].decode("latin-1").lstrip("@")
            if re.search(r"\.(png|jpg)$", text, re.I) and "%" not in text and text.casefold() != ".png":
                names.add(text)
        self.assertTrue(names)
        missing = sorted(n for n in names if n.casefold() not in listed)
        self.assertEqual(missing, [])

    def test_strip_requests(self) -> None:
        """Every call of 0x44CB60 (the registry's strips) with a constant id (push id; mov ecx, reg) is in
        STRIP_REQUESTS, and nothing else is; the two calls with a computed id are known."""
        x = self.x
        found: dict = {}
        computed = []
        for call in x.calls_to(0x44CB60):
            raw = x.read(call - 7, 7)
            mov = raw[-2] == 0x8B and raw[-1] >= 0xC0
            body = raw[:-2] if mov else raw
            if body[-2] == 0x6A:
                found.setdefault(body[-1], []).append(call)
            elif body[-5] == 0x68:
                found.setdefault(struct.unpack_from("<I", body, len(body) - 4)[0], []).append(call)
            else:
                computed.append(call)
        self.assertEqual({k: tuple(sorted(v)) for k, v in found.items()},
                         {k: tuple(sorted(v)) for k, v in a4.STRIP_REQUESTS.items()})
        self.assertEqual(sorted(computed), [0x41A035, 0x43ECA7])

    def test_the_fonts_tables_are_the_exes(self) -> None:
        x = self.x
        for font, picture, at, table in a4.FONTS:
            raw = x.read(at, len(table) * 4 + 4)
            self.assertEqual(struct.unpack(f"<{len(table)}i", raw[:-4]), tuple(table), font)
            self.assertEqual(struct.unpack("<i", raw[-4:])[0], 0, font)            # the 0 that ends it

    def test_tech_rows_and_screen_arguments(self) -> None:
        x = self.x
        for k, (sid, rx, ry, _label) in enumerate(a4.TECH_ROWS):
            self.assertEqual(struct.unpack("<4i", x.read(a4.TECH_ROW_TABLE + 16 * k, 16)), (sid, rx, ry, 1), k)
        self.assertEqual(x.read(0x43E80F, 6), b"\x81\xC5" + struct.pack("<I", a4.TECH_STEP))   # add ebp, 0x84
        self.assertEqual(struct.unpack("<2i", x.read(0x4BDC80, 8)), a4.SCAFFOLD_PLACES[0])
        self.assertEqual(struct.unpack("<2i", x.read(0x4BDC88, 8)), a4.SCAFFOLD_PLACES[1])

        def push(v: int) -> bytes:
            return (b"\x6A" + struct.pack("<b", v)) if -128 <= v < 128 else (b"\x68" + struct.pack("<i", v))

        def before(end: int, code: bytes) -> int:
            """The address the push `code` starts at: ending at `end`, or before up to 8 bytes of movs (8B / 89
            ...: mov ecx, edi; mov [esp + n], edi; mov esi, ecx; mov ecx, [esi + n]), never another push."""
            for gap in (0, 2, 4, 6, 8):
                start = end - gap - len(code)
                if x.read(start, len(code)) == code and (gap == 0 or x.read(end - gap, 1) in (b"\x8B", b"\x89")):
                    return start
            raise AssertionError(f"{code.hex()} not just before {end:#x}")
        for key, _label, _fn, draws, _note in a4.SCREENS:
            for sid, sx, sy, call in draws:
                self.assertEqual(x.read(call, 1), b"\xE8")
                rel = struct.unpack("<i", x.read(call + 1, 4))[0]
                self.assertEqual(call + 5 + rel, 0x44CDB0, (key, hex(call)))
                at = before(call, push(sid))                                     # 0x44CDB0(id, x, y, ...)
                at = before(at, push(sx))
                at = before(at, push(sy))
                self.assertIn(b"\x6A\x64", x.read(at - 12, 12), (key, hex(call)))   # push 100 (percent), alpha 1


# ------------------------------------------------------------------------------------------- emulated

@unittest.skipUnless(EMULATED, "the vanilla The Tree of Life, its pictures and Unicorn are needed")
class TheGamesCutIsTheAtlas(unittest.TestCase):
    def test_every_frame_of_every_sprite(self) -> None:
        g, s = game(), sheets()
        n = 0
        for sid, name, *_r in a4.TABLE:
            spec = a4.sprite_spec(sid)
            if name == "No Graphic" or not all(s.has(f) for f in spec.files()):
                continue
            total = 1 if spec.whole else spec.cols * spec.rows
            for frame in range(total):
                row, col = divmod(frame, spec.cols)
                want = va.whole_plan(s, name, 10, 20) if spec.whole else va.cell_plan(s, spec.atlas, col, row, 10, 20)
                self.assertEqual(g.frame(sid, frame, 10, 20), [want.key()], (sid, name, frame))
                n += 1
        self.assertGreater(n, 5000)

    def test_every_table_sprite_with_its_files_is_listed(self) -> None:
        s = sheets()
        listed = va.source_sheet_assets(s, a4.sheet_table(), pi_names())
        built = [a for a in listed if a.group != "Never loaded by the game"]
        for spec in a4.sheet_table():
            if all(s.has(f) for f in spec.files()):
                self.assertTrue(any(a.key == f"sheet:{spec.name}:{spec.cols}x{spec.rows}" for a in built), spec.name)


@unittest.skipUnless(EMULATED, "the vanilla The Tree of Life, its pictures and Unicorn are needed")
class ComposedMatchTheGame(unittest.TestCase):
    def test_buttons(self) -> None:
        g, s = game(), sheets()
        p = g.p
        n = 0
        for sid in a4.strip_ids(3):
            if not s.has(a4.SPRITES[sid][0]):
                continue
            strip = g.call(0x44CB60, [sid], ecx=g.registry)                 # the registry's strip (0x44C8F0)
            impl = p.alloc(0x80)
            p.write(impl + 0x28, b"\x01\x01")                                # shown, enabled
            p.write(impl + 0x10, struct.pack("<4i", 120, 230, 400, 300))
            p.put32(impl + 0x3C, strip)
            for state in range(3):
                self.assertEqual(g.run(0x401200, [state], impl), keys(a4.button_plan(s, sid, state, 120, 230)),
                                 (sid, state))
                n += 1
            # the button's own dispatch (0x401540) picks the state from [impl + 0x30]
            btn = p.alloc(0x40)
            vt = 0x48A5E0
            p.put32(btn, vt)
            p.write(btn + 8, b"\x01")
            p.put32(btn + 0x10, impl)
            for state in range(3):
                p.put32(impl + 0x30, state)
                self.assertEqual(g.run(0x401540, [], btn), keys(a4.button_plan(s, sid, state, 120, 230)))
        self.assertGreaterEqual(n, 3 * 25)

    def _tech(self, carving, levels):
        g, p = game(), game().p
        state = {"carving": carving, "levels": list(levels)}
        p.stub(0x41FE70, lambda q: (0x4D8BF8, 0))
        p.stub(0x41F570, lambda q: (state["carving"], 0))
        p.stub(0x41E1C0, lambda q: (state["levels"][q.arg(0)], 4))
        # after its art the screen sets the camera, draws the villager queue and its dialog: not part of this
        p.stub(0x44C3E0, lambda q: (0, 0xC))
        for at in (0x41D5F0, 0x44C420, 0x46ABC0):
            p.stub(at, lambda q: (0, 0))
        p.stub(0x40D3E0, lambda q: (0, 4))
        screen = p.alloc(0x200)
        for row in range(6):
            p.write(screen + 0x84 + row * 0xC, struct.pack("<3f", 1.0, 1.0, 1.0))   # every piece faded in
        try:
            return g.run(0x43E640, [], screen)
        finally:
            for at in (0x41FE70, 0x41F570, 0x41E1C0, 0x44C3E0, 0x41D5F0, 0x44C420, 0x46ABC0, 0x40D3E0):
                p.stubs.pop(at, None)

    def test_tech_screen(self) -> None:
        s = sheets()
        import itertools
        cases = [(c, (n,) * 6) for c in range(7) for n in range(4)]
        cases += [(2, (1, 2, 3, 0, 1, 2)), (3, (3, 0, 0, 1, 0, 2)), (5, (0, 3, 1, 2, 3, 0))]
        cases += [(1, tuple(v)) for v in itertools.islice(itertools.product(range(4), repeat=6), 0, 4096, 97)]
        for carving, levels in cases:
            got = self._tech(carving, levels)
            self.assertEqual(got, keys(a4.tech_screen_plan(s, carving, levels)), (carving, levels))
            # the carving and each bar are the screen's own blits, in order
            n = len(a4.carving_plan(s, carving))
            self.assertEqual(got[1:1 + n], keys(a4.carving_plan(s, carving)))
            at = 1 + n
            for row in range(6):
                bar = keys(a4.tech_row_plan(s, row, levels[row]))
                self.assertEqual(got[at:at + len(bar)], bar, (row, levels))
                at += len(bar)

    def test_details_bars(self) -> None:
        g, s = game(), sheets()
        bars = g.p.alloc(0x20)
        g.p.stub(0x41FE70, lambda q: (0x4D8BF8, 0))                     # the game (kept, never drawn from)
        try:
            g.call(0x44D020, [], ecx=bars)                              # the bars' own sprites (0x44D020)
        finally:
            g.p.stubs.pop(0x41FE70, None)
        for kind in range(3, 9):
            for v in (-5, 0, 1, 2, 10, 25, 33, 50, 64, 75, 99, 100, 140):
                for y in (0, 37):
                    self.assertEqual(g.run(0x44D070, [kind, v, y], bars), keys(a4.bar_plan(s, v, kind, y)),
                                     (kind, v, y))

    def test_loading_meter(self) -> None:
        g, s = game(), sheets()
        meter = g.p.alloc(0x20)
        g.call(0x44DAD0, [], ecx=meter)
        fills = []
        g.p.stub(0x408210, lambda q: (fills.append(q.arg(0)) or 0, 0x14))
        try:
            for v in list(range(-3, 103)) + [300]:
                self.assertEqual(g.run(0x44DB10, [3, 240, 500, v], meter), keys(a4.loading_bar_plan(s, v, 240, 500)), v)
            self.assertEqual(fills, [])
            frame = keys([va.whole_plan(s, a4.SPRITES[a4.BAMBOO][0], 240, 500)])
            for kind in (0, 1, 2):
                for v in (0, 50, 100):
                    fills.clear()
                    self.assertEqual(g.run(0x44DB10, [kind, 240, 500, v], meter), frame, kind)
                    self.assertEqual(len(fills), 1)                       # the fill, then the frame over it
        finally:
            g.p.stubs.pop(0x408210, None)

    def test_island_map(self) -> None:
        g, s = game(), sheets()
        if not all(s.has(a4.MAP_TILE.format(x=x, y=y)) for x in range(4) for y in range(4)):
            self.skipTest("the map tiles are needed")
        tiles = g.p.alloc(0x200)
        g.call(0x46FCE0, [], ecx=tiles)
        self.assertEqual(g.run(0x46FE10, [0, 0, 0, 0, 2048, 2048], tiles), keys(a4.map_plan(s)))
        # scrolled, the same tiles move with the camera
        moved = [(d.file.casefold(), d.rect, d.x - 300, d.y - 100, 1.0, 255) for d in a4.map_plan(s)
                 if d.y - 100 <= 600 and d.y - 100 + 512 >= 0 and d.x - 300 <= 800 and d.x - 300 + 512 >= 0]
        self.assertEqual(g.run(0x46FE10, [300, 100, 0, 0, 800, 600], tiles), moved)

    def test_dialogs(self) -> None:
        g, s = game(), sheets()
        p = g.p
        x = Image()
        self.assertEqual((x.u32(0x4CBB78), x.u32(0x4CBB74)), a4.DIALOG_MARGIN)
        cases = [(sid, w, h) for sid, w, h, _l in a4.DIALOGS]
        cases += [(sid, w, h) for sid in (152, 153) for w in (1, 63, 64, 65, 128, 129, 777) for h in (1, 64, 65, 300)]
        for sid, w, h in cases:
            grid = g.call(0x44CB70, [sid], ecx=g.registry)
            dialog = p.alloc(0x40)
            g.call(0x40DC70, [grid, w, h], ecx=dialog)                    # the tiled background's own setup
            for at in ((0, 0), (33, 44)):
                self.assertEqual(g.run(0x40DAB0, [*at, f32bits(1.0)], dialog),
                                 keys(a4.dialog_plan(s, sid, w, h, *at)), (sid, w, h, at))

    def test_huts(self) -> None:
        g, s = game(), sheets()
        p = g.p
        for sid, _label in a4.HUTS:
            hut = p.alloc(0x100)
            p.put32(hut + 0x28, 640)
            p.put32(hut + 0x2C, 410)
            p.put32(hut + 0x64, g.call(0x44CD90, [a4.SCAFFOLDING], ecx=g.registry))
            p.put32(hut + 0x68, g.call(0x44CB70, [sid], ecx=g.registry))
            atlas = a4.sprite_atlas(sid)
            for part in range(2 + atlas.cols * atlas.rows):
                self.assertEqual(g.run(a4.HUT_DRAW, [part << 24], hut),
                                 keys(a4.hut_part_plan(s, sid, part, 640, 410)), (sid, part))

    def test_fonts(self) -> None:
        g, s = game(), sheets()
        for font, picture, at, table in a4.FONTS:
            obj = g.p.alloc(0x420)
            name = g.p.alloc(0x40)
            g.p.write(name, font.encode() + b"\0")
            g.call(0x4027A0, [name, at, 0], ecx=obj)
            got = []
            for k in range(len(table) // 5):
                e = struct.unpack("<5i", g.p.read(at + 20 * k, 20))
                got.append((e[0] & 0xFF if e[0] < 0 else e[0], e[1:]))
            self.assertEqual(got, a4.font_glyphs(table, s.size(picture)[0]), font)
            self.assertIn(picture, g.surfaces.values())

    def test_golden_mushroom(self) -> None:
        g, s = game(), sheets()
        if not s.has(a4.GOLDEN):
            self.skipTest("the patcher's golden_mushroom.png is needed")
        name = g.p.alloc(0x40)
        g.p.write(name, a4.GOLDEN.encode() + b"\0")
        golden = g.p.alloc(0x40)
        g.call(0x40AB10, [name, 1, 1], ecx=golden)                        # the companion's own build
        for x, y in ((100, 50), (0, 0), (1500, 900)):
            got = g.run(0x44C640, [golden, x + a4.GOLDEN_DX, y + a4.GOLDEN_DY, 0, f32bits(1.0)], CAMERA)
            self.assertEqual(got, keys(a4.golden_plan(s, x, y)))
        source = (ROOT / "native" / "vvfp_golden_mushroom" / "vvfp_golden_mushroom.c").read_text(encoding="utf-8")
        self.assertIn(f"LATER_STUB(vv4, 0x4CC9E8, 0x44C645u, {a4.GOLDEN_DX}, {a4.GOLDEN_DY})", source)
        self.assertIn(f"#define LATER_FRAME {a4.GOLDEN_FRAME}", source)


# ------------------------------------------------------------------------------------------- no exe needed

class Blank:
    """Made-up pictures: each name's size from `sizes` (PNG headers only)."""

    def __init__(self, sizes) -> None:
        self.sizes = {k.casefold(): v for k, v in sizes.items()}

    def read(self, name):
        size = self.sizes.get(name.casefold())
        if size is None:
            return None
        png = pi.Image(1, 1).to_png()
        return png[:16] + struct.pack(">II", *size) + png[24:]

    def names(self):
        return list(self.sizes)


class Rules(unittest.TestCase):
    def test_table_shape(self) -> None:
        self.assertEqual(len(a4.TABLE), 305)
        ids = [r[0] for r in a4.TABLE]
        self.assertEqual(len(ids), len(set(ids)))
        specs = a4.sheet_table()
        seen = set()
        for spec in specs:
            key = (spec.name.casefold(), spec.cols, spec.rows, tuple(spec.sheets), spec.whole)
            self.assertNotIn(key, seen)
            seen.add(key)
            self.assertTrue(spec.where)
        self.assertEqual(sum(1 for s in specs if s.name.startswith("MapX")), 16)
        self.assertIn("ldwarialbold.png", {s.name for s in specs})
        firestrip = [s for s in specs if s.name == "firestrip.png"]
        self.assertEqual(len(firestrip), 1)
        self.assertIn("sprite 250", firestrip[0].where)
        self.assertIn("sprite 275", firestrip[0].where)

    def test_cuts(self) -> None:
        self.assertTrue(a4.sprite_spec(47).atlas == pi.Atlas("btn_done.png", 3, 1))   # rows 0: a strip
        self.assertTrue(a4.sprite_spec(178).whole)                                    # 0 x 0: whole
        self.assertEqual(a4.sprite_spec(277).atlas, pi.Atlas("female_bodies", 32, 30, (2, 3)))
        self.assertEqual(a4.sprite_spec(3).atlas, pi.Atlas("leaf_grid.png", 1, 2))

    def test_font_wrap(self) -> None:
        table = (65, 0, 0, 10, 12, 66, 10, 0, 25, 12, 67, 25, 0, 31, 12, -3, 31, 0, 40, 12)
        self.assertEqual(a4.font_glyphs(table, 100), [(65, (0, 0, 10, 12)), (66, (10, 0, 25, 12)),
                                                    (67, (25, 0, 31, 12)), (253, (31, 0, 40, 12))])
        self.assertEqual(a4.font_glyphs(table, 30), [(65, (0, 0, 10, 12)), (66, (10, 0, 25, 12)),
                                                   (67, (0, 13, 6, 25)), (253, (6, 13, 15, 25))])

    def test_bar_and_loading_counts(self) -> None:
        s = va.AssetSheets(Blank({"StatusBarSliceB.png": (4, 16), "StatusBarSliceR.png": (14, 16),
                                  "LoadColor.png": (8, 30), "BambooMeterFrame1.png": (320, 30)}))
        self.assertEqual(len(a4.bar_plan(s, 100, 3)), 64)
        self.assertEqual(len(a4.bar_plan(s, 50, 3)), 32)
        self.assertEqual(len(a4.bar_plan(s, 1, 3)), 0)
        self.assertEqual(len(a4.bar_plan(s, 2, 8)), 1)
        self.assertEqual(len(a4.loading_bar_plan(s, 100)), 80)
        self.assertEqual(len(a4.loading_bar_plan(s, 2)), 0)
        self.assertEqual(len(a4.loading_bar_plan(s, 3)), 2)

    def test_patcher_art_ships(self) -> None:
        release = (ROOT / "scripts" / "build_release.py").read_text(encoding="utf-8")
        for name, path in a4.patcher_art().items():
            if isinstance(path, tuple):
                path = path[0]
            self.assertTrue(path.is_file(), name)
            rel = path.relative_to(ROOT).as_posix()
            self.assertIn(f'"{rel}"', release, rel)
        dll = ROOT / "assets" / "origins" / "VVFP VV4 Origins Icons.dll"
        self.assertIn('"assets/origins/VVFP VV4 Origins Icons.dll"', release)
        data = dll.read_bytes()
        for name, (_dll, kind, ident) in a4.origins_icon_resources().items():
            png = pi.pe_resource(data, kind, ident)
            self.assertIsNotNone(png, name)
            self.assertTrue(png.startswith(pi.PNG_MAGIC), name)
            size = int(name.rsplit("_", 1)[1][:-4])
            self.assertEqual(struct.unpack(">II", png[16:24])[0] in (size, size - 1, size + 1), True, name)

    def test_assets_without_pictures_are_empty_and_tolerated(self) -> None:
        s = va.AssetSheets(Blank({}))
        self.assertEqual(a4.assets(s), [])

    def test_plans_on_blank_sheets(self) -> None:
        sizes = {}
        for spec in a4.sheet_table():
            for f in spec.files():
                sizes[f] = (64 * max(1, spec.cols), 32 * max(1, spec.rows))
        sizes.update({a4.GOLDEN: (29, 22), a4.MASK_FILE: (520, 725), a4.BIG_MASK_FILE: (240, 500),
                      a4.MASK_PREVIEW: (100, 100)})
        s = va.AssetSheets(Blank(sizes))
        assets = a4.assets(s)
        cats = {a.category for a in assets}
        for cat in (va.TECH, va.METERS, va.PANELS, va.SCREENS, va.SCENE, va.FONTS, va.BUILDINGS, va.PATCHER,
                    va.COLLECTIBLES, va.CREATURES, va.EFFECTS):
            self.assertIn(cat, cats)
        self.assertEqual(len({a.key for a in assets}), len(assets))
        for a in assets:
            self.assertIn(a.category, va.CATEGORIES)
            self.assertTrue(a.frames, a.key)
            self.assertTrue(a.proof, a.key)
            if a.patcher:
                self.assertTrue(all(d.file in sizes for f in a.frames for d in f.plan))
        tech = next(a for a in assets if a.key == "tech:screen")
        self.assertEqual(len(tech.frames), 4)
        everything = va.all_assets(4, s, a4)
        self.assertTrue(any(a.category == va.SHEETS for a in everything))


@unittest.skipUnless(HAVE_ART, "the game's pictures (research/game-images) are needed")
class WithTheGamesPictures(unittest.TestCase):
    def test_every_frame_renders(self) -> None:
        s = sheets()
        n = 0
        for asset in a4.assets(s):
            for frame in asset.frames[:4]:
                image = va.render_frame(s, frame)
                self.assertGreater(image.width * image.height, 0, (asset.key, frame.label))
                n += 1
        self.assertGreater(n, 200)

    def test_unused_files(self) -> None:
        s = sheets()
        listed = va.source_sheet_assets(s, a4.sheet_table(), pi_names())
        unused = sorted(a.label for a in listed if a.group == "Never loaded by the game")
        self.assertEqual(unused, sorted(a4.UNUSED_FILES))


def pi_names() -> list[str]:
    return sorted(p.name for p in (ART / "Images").iterdir() if p.suffix.casefold() in va.PICTURE_EXTENSIONS)


if __name__ == "__main__":
    unittest.main()
