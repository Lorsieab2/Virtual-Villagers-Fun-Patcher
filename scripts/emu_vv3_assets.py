"""The Secret City's stock exe in Unicorn, ready to run its draw code and record every blit.

Shared by tests/test_assets_vv3.py and the research in scripts/ (src/vv_assets_vv3.py's proofs).

Everything is the game's own code -- the resource table and its getters (0x42E9D0 / 0x42EA80 / 0x42E750 /
0x42E920), the sprite constructors (0x40AD80 whole, 0x401150 strip, 0x40AF10 / 0x40AF90 atlas), the camera
(0x42E250, 0x42E5E0 ...), the cell cut and draw wrappers -- except:
  * the picture loader 0x40B3D0 (it reads the PNG / JPEG): a surface of the stock size instead;
  * the blitter 0x404620: recorded (sheet, x, y, cell, alpha, scale, centred);
  * operator new 0x46EC93: a bump allocator.
"""
from __future__ import annotations

import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

from unicorn.x86_const import UC_X86_REG_FPCW  # noqa: E402

import vv_picture_image as pi  # noqa: E402
from story_emulator import API_STUBS, Process  # noqa: E402

EXE = ROOT / "research" / "stock-executables" / "Virtual Villagers - The Secret City.exe"
CAMERA = 0x58F6F8
RESOURCES = 0x592714            # the resource manager singleton (0x42E9D0)
BLITTER = 0x404620
LOADER = 0x40B3D0
WINDOWS_FPCW = 0x027F


def f32bits(value: float) -> int:
    return struct.unpack("<I", struct.pack("<f", value))[0]


def bitsf32(value: int) -> float:
    return struct.unpack("<f", struct.pack("<I", value & 0xFFFFFFFF))[0]


def s32(value: int) -> int:
    value &= 0xFFFFFFFF
    return value - (1 << 32) if value & 0x80000000 else value


class Emulator:
    def __init__(self, sizes, exe: Path = EXE) -> None:
        self.sizes = {k.casefold(): v for k, v in sizes.items()}
        p = self.p = Process(exe.read_bytes())
        p.mu.mem_map(API_STUBS, 0x10000)
        p.api_names = {}
        slot = 0
        for entry in p._exe_pe.DIRECTORY_ENTRY_IMPORT:
            for imp in entry.imports:
                if imp.name:
                    stub = API_STUBS + slot * 16
                    slot += 1
                    p.mu.mem_write(stub, b"\xC3")
                    p.api_names[stub] = imp.name.decode()
                    p.mu.mem_write(imp.address, struct.pack("<I", stub))
        self.names: dict[int, str] = {}
        self.loaded: list[str] = []
        self.blits: list = []
        p.stub(0x46EC93, lambda q: (q.alloc(max(q.arg(0), 4)), 0))       # operator new
        p.stub(LOADER, self._sheet)
        p.stub(BLITTER, self._blit)
        self.fills: list = []
        p.api_handlers["SDL_UpperBlit"] = self._sdl_blit
        p.api_handlers["SDL_FillRect"] = self._sdl_fill
        p.api_handlers["SDL_MapRGB"] = lambda q: ((q.arg(1) << 16) | (q.arg(2) << 8) | q.arg(3), 0)
        p.api_handlers["SDL_MapRGBA"] = lambda q: ((q.arg(4) << 24) | (q.arg(1) << 16) | (q.arg(2) << 8) | q.arg(3), 0)
        renderer = self.renderer = p.alloc(0x200)
        p.write(renderer + 0x60, struct.pack("<iiii", -20000, -20000, 20000, 20000))  # its clip rectangle
        wrapper = self.wrapper = p.alloc(16)
        p.put32(wrapper, renderer)
        p.put32(0x4B34A8, wrapper)
        self.fpu()
        self.call(0x42E250, [0, 0, f32bits(1.0)], ecx=CAMERA)            # no scroll, zoom 1.0
        self.call(0x42E9D0)                                              # the resource manager
        self.resources = p.u32(RESOURCES)

    # The static initialisers of the game's globals (0x47ACD0 - 0x47B130: mov ecx, object; call/jmp ctor),
    # as the C runtime runs them before WinMain.
    STATIC_CTORS = (
        (0x5607D8, 0x420E80), (0x560808, 0x422A30), (0x560958, 0x422D10), (0x560964, 0x422E10),
        (0x560990, 0x422EE0), (0x580A6C, 0x423A50), (0x580A88, 0x423DF0), (0x581A38, 0x423E50),
        (0x582124, 0x4241E0), (0x582158, 0x424C20), (0x5823D0, 0x4260F0), (0x582470, 0x426140),
        (0x582490, 0x4263E0), (0x5824A0, 0x4264C0), (0x5825D4, 0x4264D0), (0x582610, 0x4268E0),
        (0x582618, 0x427050), (0x582644, 0x427120), (0x582660, 0x429330), (0x583B28, 0x429A40),
        (0x58C338, 0x429C40), (0x58C548, 0x42B310), (0x58ED24, 0x42C1D0), (0x58ED5C, 0x42CA50),
        (0x58ED94, 0x42CA90), (0x58ED9C, 0x42CB10), (0x58EDB8, 0x42CEA0), (0x58F428, 0x42DE60),
        (0x58F5E8, 0x42E240), (0x593B40, 0x430050), (0x593BA0, 0x430CA0), (0x59454C, 0x430EE0),
        (0x5945A8, 0x4313C0), (0x5945BC, 0x4315F0), (0x5945D0, 0x431830), (0x594604, 0x431F50),
        (0x594614, 0x432050), (0x594620, 0x4328B0), (0x594690, 0x433010), (0x5946D8, 0x433D70),
        (0x5947E0, 0x434E30), (0x594870, 0x435100), (0x594990, 0x4355E0), (0x594AD8, 0x435BF0),
        (0x594B3C, 0x436080), (0x594BA4, 0x436430), (0x594BB8, 0x436530), (0x594BC8, 0x4367F0),
        (0x594BF8, 0x436BA0), (0x594C40, 0x437690), (0x595820, 0x4378A0), (0x595874, 0x438190),
        (0x5958A8, 0x4408F0), (0x596970, 0x453D20), (0x5973F0, 0x454CA0), (0x59E110, 0x45EE90))

    def statics(self) -> None:
        for obj, ctor in self.STATIC_CTORS:
            self.call(ctor, ecx=obj)

    def fpu(self) -> None:
        self.p.mu.reg_write(UC_X86_REG_FPCW, WINDOWS_FPCW)

    def call(self, address: int, args=(), ecx: int | None = None):
        self.fpu()
        return self.p.call(address, list(args), ecx=ecx)

    def _sheet(self, q):
        this, name = q.reg("ecx"), q.cstring(q.arg(0))
        w, h = self.sizes.get(name.casefold(), (0, 0))
        surface = q.alloc(0x40)
        q.put32(surface + 8, w)
        q.put32(surface + 12, h)
        q.put32(this, surface)
        self.names[surface] = name
        self.loaded.append(name)
        return this, 4

    def _blit(self, q):
        a = [q.arg(i) for i in range(10)]
        self.blits.append((self.names.get(a[0], hex(a[0])), s32(a[1]), s32(a[2]), tuple(s32(v) for v in a[3:7]),
                           bitsf32(a[7]), bitsf32(a[8]), a[9]))
        return 0, 0x28

    def _sdl_blit(self, q):
        """SDL_UpperBlit(src, srcrect, dst, dstrect): an unscaled opaque blit (SDL's own alpha blend)."""
        src, srect, _dst, drect = (q.arg(i) for i in range(4))
        if srect:
            sx, sy, sw, sh = struct.unpack("<iiii", q.read(srect, 16))
        else:
            sx, sy, sw, sh = 0, 0, q.u32(src + 8), q.u32(src + 12)
        dx, dy = struct.unpack("<ii", q.read(drect, 8)) if drect else (0, 0)
        self.blits.append((self.names.get(src, hex(src)), dx, dy, (sx, sy, sx + sw, sy + sh), 1.0, 1.0, 0))
        return 0, 0

    def _sdl_fill(self, q):
        rect = q.arg(1)
        r = struct.unpack("<iiii", q.read(rect, 16)) if rect else None
        self.fills.append((r, q.arg(2)))
        return 0, 0

    def take(self) -> list[tuple]:
        """The blits since the last take, as Draw.key()s (file, rect, x, y, scale, alpha byte)."""
        out = []
        for file, bx, by, rect, alpha, scale, centred in self.blits:
            assert not (centred and scale != 1.0), "a centred scaled blit: the plan does not model it"
            out.append((file.casefold(), rect, bx, by, round(scale, 6), pi.surface_alpha(alpha)))
        self.blits = []
        return out

    def resource(self, rid: int) -> int:
        """The game's own sprite for a resource id (0x42EA80: atlas, strip or whole, as the table says)."""
        return self.call(0x42EA80, [rid], ecx=self.resources)

    def draw_resource(self, rid: int, x: int, y: int, alpha: float = 1.0, percent: int = 100,
                      ui: int | None = None) -> list[tuple]:
        """0x42EB90(id, x, y, alpha, percent): the UI's draw-by-id (ecx: {resources, renderer wrapper})."""
        if ui is None:
            ui = self.p.alloc(16)
            self.p.put32(ui, self.resources)
            self.p.put32(ui + 4, self.wrapper)
        self.call(0x42EB90, [rid, x & 0xFFFFFFFF, y & 0xFFFFFFFF, f32bits(alpha), percent], ecx=ui)
        return self.take()
