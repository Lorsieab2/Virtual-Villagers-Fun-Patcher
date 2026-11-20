"""The broken piers' holes (The Tree of Life, Fix Vanilla Bugs): "VVFP VV4 Pier Holes.dll".

The owner redrew the ten hole pictures the two broken piers of the Fishing Nets puzzle are drawn with (sprites 104 to
113, art by Lorsieab2, 2026-11-19).  They ship as separate files in the game's Images folder ("vvfp_" + the stock
name) and the companion points each hole's sprite table entry at its own name at start, so the game's own registry
builds and draws the owner's picture; a missing or wrong file leaves that hole stock.

Proven here, with the stock executable and the shipped companion in tests/story_emulator.Process:
  * each of the ten entries names its own owner's picture, and nothing else in the game's image changes;
  * the game's own registry and draw (0x44CEC0) then blit the owner's picture at the stock picture's place, cell
    and size, and every other sprite is drawn as before;
  * a missing file, a file of another size or not 8-bit RGBA leaves that hole stock (the rest still switched); with
    no file at all nothing is written; another game installs nothing;
  * the shipped pictures are the stock pictures' sizes, and the row ships them and the DLL pinned by SHA-256.
"""
from __future__ import annotations

import hashlib
import json
import re
import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

EXE = ROOT / "research" / "stock-executables" / "Virtual Villagers - The Tree of Life.exe"
STOCK_ART = ROOT / "research" / "game-images" / "Virtual Villagers - The Tree of Life" / "Images"
DLL = ROOT / "assets" / "vv4_pier_holes" / "VVFP VV4 Pier Holes.dll"
ART = ROOT / "assets" / "vv4_pier_holes"
ROW = "vv4_fix_vanilla_bugs"

try:
    import pefile  # noqa: F401
    from unicorn.x86_const import UC_X86_REG_FPCW

    from story_emulator import Process
    HAVE_EMULATOR = EXE.is_file()
except ImportError:  # pragma: no cover - environment dependent
    HAVE_EMULATOR = False

TABLE, STRIDE, COUNT = 0x4C07C8, 0x30, 305
FIRST_INDEX = 56
# In table order, ids 104 .. 113: (stock name, its address, width, height).
HOLES = (
    ("northPierHoleEast.png", 0x491940, 21, 14),
    ("southPierHoleNorthWest.png", 0x491924, 26, 32),
    ("southPierHoleEast.png", 0x49190C, 20, 29),
    ("southPierHoleSouthWest.png", 0x4918F0, 23, 37),
    ("northPierHoleMidSouth.png", 0x4918D4, 20, 12),
    ("northPierHoleMidNorth.png", 0x4918B8, 25, 24),
    ("northPierHoleSouthEast.png", 0x49189C, 25, 25),
    ("northPierHoleWest.png", 0x491884, 36, 43),
    ("southPierHoleSouthEast.png", 0x491868, 24, 38),
    ("southPierHoleNorthEast.png", 0x49184C, 20, 21),
)
IMAGES = "c:\\games\\village\\images\\"
CAMERA = 0x4DB9F8


def ours(name: str) -> str:
    return "vvfp_" + name


def png_size(data: bytes) -> tuple[int, int, int, int]:
    """(width, height, bit depth, colour type) from a PNG's IHDR."""
    assert data[:8] == b"\x89PNG\r\n\x1a\n" and data[12:16] == b"IHDR"
    return struct.unpack(">IIBB", data[16:26])


def shipped_art() -> dict[str, bytes]:
    return {ours(n): (ART / ours(n)).read_bytes() for n, *_ in HOLES}


def f32bits(v: float) -> int:
    return struct.unpack("<I", struct.pack("<f", v))[0]


def s32(v: int) -> int:
    return v - (1 << 32) if v & 0x80000000 else v


class Game:
    """The stock executable with the companion loaded: the companion's file reads answered from `files` (Images
    beside C:\\Games\\Village\\Game.exe); the game's own sprite registry and constructors run, with operator new,
    free, sprintf, the file check and the file reader (a sheet's surface: the picture's real size) answered, and
    every blit recorded by the picture it draws."""

    def __init__(self, files: dict[str, bytes] | None = None):
        self.files = shipped_art() if files is None else files
        self.p = p = Process(EXE.read_bytes(), DLL)
        self.handles: dict[int, list] = {}
        self.opened: list[str] = []
        p.api_handlers["CreateFileW"] = self._create
        p.api_handlers["ReadFile"] = self._read
        p.api_handlers["CloseHandle"] = self._close
        self.surfaces: dict[int, str] = {}
        self.blits: list = []
        p.stub(0x470C5C, lambda q: (q.alloc(max(q.arg(0), 4)), 0))       # operator new
        p.stub(0x470B7B, lambda q: (0, 0))                               # free
        p.stub(0x40B050, self._sheet)                                    # a sheet's surface from its file
        p.stub(0x40AF70, lambda q: (1, 0))                               # the file is there
        p.stub(0x404CB0, self._blit)
        p.stub(0x404C40, self._plain)
        p.stub(0x4716DB, self._sprintf)
        self.registry = p.alloc(0x40)
        p.put32(self.registry, p.alloc(0x40))
        p.stub(0x44CCF0, lambda q: (self.registry, 0))                   # the registry object
        gfx = p.alloc(0x100)
        wrap = p.alloc(0x10)
        p.put32(wrap, gfx)
        p.put32(0x4CB928, wrap)                                          # 0x408130: the graphics
        p.put32(self.registry + 4, wrap)
        p.write(gfx + 0x60, struct.pack("<iiii", -100000, -100000, 100000, 100000))   # no clipping
        self.call(0x44C3E0, [0, 0, f32bits(1.0)], ecx=CAMERA)            # the camera at rest, zoom 1

    # -- the companion's file reads ------------------------------------------------------------------------------
    def _create(self, q):
        path = q.wstring(q.arg(0))
        self.opened.append(path)
        folder, _, name = path.lower().rpartition("\\")
        match = next((k for k in self.files if k.lower() == name), None)
        if folder + "\\" != IMAGES or match is None:
            return 0xFFFFFFFF, 28
        handle = 0x100 + 4 * len(self.handles)
        self.handles[handle] = [self.files[match], 0]
        return handle, 28

    def _read(self, q):
        handle, buf, want, got = q.arg(0), q.arg(1), q.arg(2), q.arg(3)
        data, at = self.handles[handle]
        piece = data[at:at + want]
        q.write(buf, piece)
        self.handles[handle][1] = at + len(piece)
        q.put32(got, len(piece))
        return 1, 20

    def _close(self, q):
        self.handles.pop(q.arg(0), None)
        return 1, 4

    # -- the game's pictures -------------------------------------------------------------------------------------
    def _sheet(self, q):
        this, name = q.reg("ecx"), q.cstring(q.arg(0))
        data = self.files.get(name) if name.startswith("vvfp_") else (STOCK_ART / name).read_bytes()
        w, h, _, _ = png_size(data)
        surface = q.alloc(0x40)
        q.put32(surface + 8, w)
        q.put32(surface + 12, h)
        self.surfaces[surface] = name
        q.put32(this, surface)
        q.write(this + 4, b"\x01")
        return this, 4

    def _blit(self, q):
        a = [q.arg(i) for i in range(10)]
        self.blits.append((self.surfaces.get(a[0], hex(a[0])), s32(a[1]), s32(a[2]),
                           tuple(s32(v) for v in a[3:7]), a[7], a[8]))
        return 0, 0x28

    def _plain(self, q):
        a = [q.arg(i) for i in range(7)]
        self.blits.append((self.surfaces.get(a[0], hex(a[0])), s32(a[1]), s32(a[2]),
                           tuple(s32(v) for v in a[3:7]), None, None))
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

    # -- running -------------------------------------------------------------------------------------------------
    def call(self, addr: int, args, ecx=None) -> int:
        self.p.mu.reg_write(UC_X86_REG_FPCW, 0x027F)
        return self.p.call(addr, list(args), ecx=ecx, limit=5_000_000)

    def start(self, game: int = 4) -> int:
        self.p.export("VvfpStartup", game, 0)
        return self.p.export("VvfpPierHolesInstalled")

    def draw(self, sid: int, x: int = 300, y: int = 200) -> list:
        """0x44CEC0(id, frame 0, x, y, 1.0, 100): the registry builds the sprite on first use and draws it."""
        self.blits = []
        self.call(0x44CEC0, [sid, 0, x, y, f32bits(1.0), 100], self.registry)
        return list(self.blits)

    def entry(self, index: int) -> bytes:
        return self.p.read(TABLE + index * STRIDE, STRIDE)

    def image(self) -> bytes:
        base = self.p.image_base
        return self.p.read(base, self.p._exe_pe.OPTIONAL_HEADER.SizeOfImage)


@unittest.skipUnless(HAVE_EMULATOR, "needs pefile, unicorn and the stock The Tree of Life")
class Install(unittest.TestCase):
    def test_each_hole_names_its_own_picture_and_nothing_else_changes(self) -> None:
        g = Game()
        before = g.image()
        self.assertEqual(g.start(), 10)
        after = g.image()
        changed = [i for i in range(0, len(before), 4) if before[i:i + 4] != after[i:i + 4]]
        expected = [TABLE + (FIRST_INDEX + k) * STRIDE + 4 - g.p.image_base for k in range(10)]
        self.assertEqual(changed, expected)
        for k, (name, at, _, _) in enumerate(HOLES):
            stock, now = before[expected[k] - 4:expected[k] - 4 + STRIDE], g.entry(FIRST_INDEX + k)
            self.assertEqual(struct.unpack_from("<2I", stock), (104 + k, at))
            self.assertEqual(now[:4] + now[8:], stock[:4] + stock[8:])
            self.assertEqual(g.p.cstring(struct.unpack_from("<I", now, 4)[0]), ours(name))
            self.assertEqual(g.p.cstring(at), name)                       # the stock name itself is untouched

    def test_the_game_draws_the_owners_picture_in_place_of_each_stock_hole(self) -> None:
        stock, patched = Game(), Game()
        self.assertEqual(patched.start(), 10)
        for k, (name, _, w, h) in enumerate(HOLES):
            a, b = stock.draw(104 + k), patched.draw(104 + k)
            self.assertEqual(len(a), 1, name)
            self.assertEqual(a[0][0], name)
            self.assertEqual(b[0][0], ours(name))
            self.assertEqual(b[0][1:], a[0][1:], name)                    # the same place, cell, scale and alpha
            self.assertEqual(a[0][3], (0, 0, w, h), name)

    def test_every_other_sprite_is_drawn_as_before(self) -> None:
        stock, patched = Game(), Game()
        patched.start()
        for sid in (103, 114):                                            # the table's neighbours
            self.assertEqual(patched.draw(sid), stock.draw(sid))
        for k in range(10):
            self.assertEqual(stock.entry(FIRST_INDEX + k)[8:], patched.entry(FIRST_INDEX + k)[8:])


@unittest.skipUnless(HAVE_EMULATOR, "needs pefile, unicorn and the stock The Tree of Life")
class Fallback(unittest.TestCase):
    def _check(self, files: dict[str, bytes], switched: set[str]) -> None:
        g = Game(files)
        before = [g.entry(FIRST_INDEX + k) for k in range(10)]
        self.assertEqual(g.start(), len(switched))
        for k, (name, _, _, _) in enumerate(HOLES):
            if name not in switched:                                      # before the draw caches its object
                self.assertEqual(g.entry(FIRST_INDEX + k), before[k], name)
            drawn = g.draw(104 + k)[0][0]
            self.assertEqual(drawn, ours(name) if name in switched else name)

    def test_a_missing_file_draws_that_stock_hole(self) -> None:
        art = shipped_art()
        del art[ours("northPierHoleWest.png")]
        self._check(art, {n for n, *_ in HOLES} - {"northPierHoleWest.png"})

    def test_a_file_of_another_size_or_kind_draws_that_stock_hole(self) -> None:
        art = shipped_art()
        wide = bytearray(art[ours("southPierHoleEast.png")])
        wide[16:20] = struct.pack(">I", 21)                               # one pixel wider
        art[ours("southPierHoleEast.png")] = bytes(wide)
        rgb = bytearray(art[ours("northPierHoleEast.png")])
        rgb[25] = 2                                                       # RGB, no alpha
        art[ours("northPierHoleEast.png")] = bytes(rgb)
        art[ours("southPierHoleNorthEast.png")] = b"not a png at all, just text...."
        self._check(art, {n for n, *_ in HOLES}
                    - {"southPierHoleEast.png", "northPierHoleEast.png", "southPierHoleNorthEast.png"})

    def test_no_files_writes_nothing(self) -> None:
        g = Game({})
        before = g.image()
        self.assertEqual(g.start(), 0)
        self.assertEqual(g.image(), before)
        self.assertEqual(g.draw(104)[0][0], "northPierHoleEast.png")

    def test_another_game_installs_nothing(self) -> None:
        for game in (1, 2, 3, 5):
            g = Game()
            before = g.image()
            self.assertEqual(g.start(game), 0)
            self.assertEqual(g.image(), before)
            self.assertEqual(g.opened, [])

    def test_a_second_start_changes_nothing(self) -> None:
        g = Game()
        self.assertEqual(g.start(), 10)
        once = g.image()
        g.p.export("VvfpStartup", 4, 0)
        self.assertEqual(g.p.export("VvfpPierHolesInstalled"), 10)
        self.assertEqual(g.image(), once)


class ShippedFiles(unittest.TestCase):
    def test_the_owners_pictures_have_the_stock_sizes(self) -> None:
        for name, _, w, h in HOLES:
            self.assertEqual(png_size((ART / ours(name)).read_bytes()), (w, h, 8, 6), name)
            if STOCK_ART.is_dir():
                self.assertEqual(png_size((STOCK_ART / name).read_bytes())[:2], (w, h), name)

    def test_the_row_ships_the_dll_and_the_ten_pictures_pinned(self) -> None:
        builds = json.loads((ROOT / "data" / "builds.json").read_text(encoding="utf-8"))
        row = next(p for p in builds["fun_patches"] if p["id"] == ROW)
        files = {f["destination"]: f for f in row["companion_files"]}
        wanted = {"VVFP VV4 Pier Holes.dll": DLL}
        wanted.update({f"Images/{ours(n)}": ART / ours(n) for n, *_ in HOLES})
        for destination, path in wanted.items():
            self.assertIn(destination, files)
            self.assertEqual(ROOT / files[destination]["source"], path)
            self.assertEqual(files[destination]["sha256"], hashlib.sha256(path.read_bytes()).hexdigest().upper())
        self.assertIn("broken piers", row["description"])
        sites = [d for d in row["runtime_detours"] if d["installed_by"].startswith("VVFP VV4 Pier Holes.dll")]
        self.assertEqual([int(d["va"], 16) for d in sites],
                         [TABLE + (FIRST_INDEX + k) * STRIDE for k in range(10)])

    def test_the_startup_loader_starts_it(self) -> None:
        import vv_fun_patcher as patcher
        # The second word is full (32 of 32): the third word (VVFP More Companions.dll) starts it.
        self.assertIn("VVFP VV4 Pier Holes.dll", patcher.STARTUP_LOADER_COMPANIONS_3)
        self.assertNotIn("VVFP VV4 Pier Holes.dll", patcher.STARTUP_LOADER_COMPANIONS_2)
        header = (ROOT / "native" / "shared" / "startup_companions_3.h").read_text(encoding="utf-8")
        self.assertIn('"VVFP VV4 Pier Holes.dll"', header)


if __name__ == "__main__":
    unittest.main()
