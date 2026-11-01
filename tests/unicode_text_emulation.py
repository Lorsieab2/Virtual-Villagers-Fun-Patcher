"""Run a published build's fonts and typing in unicorn, with "VVFP Unicode Text.dll" installed.

The build is started as the game starts it (tests/startup_emulation.py: the stub, VVFP Startup.dll, the
companion's VvfpStartup), then the game's own code is called as the game calls it:

  * the font wrapper the game's resource object calls for each font (A New Home 0x402080: new, the
    ldwFontImpl constructor, then the detoured font constructor) with the stock picture name and table;
    the game's file check, operator new and picture loader are answered here (the picture is the stock
    PNG from research/game-images, as an SDL surface), so the constructor's own code and the companion's
    whole letter-making run as machine code;
  * the game's text width routine (A New Home 0x402160) and text draw routine (0x409160), whose
    SDL_UpperBlit calls are recorded;
  * the event pump's SDL_TEXTINPUT case, from its detoured first instruction to the post or the skip,
    and the stock text box's character handler with what was posted.

Windows' own GDI answers the companion's GDI calls (the real GetGlyphOutlineW), so the letters it makes
are compared with src/vv_font_glyphs.py's.  The registry and the Fonts folders are answered as empty, so
Burweed ICG is never found: the result is the no-Burweed letters (FontGlyphs(use_burweed=False)).
"""
from __future__ import annotations

import ctypes
import re
import struct
import sys
from ctypes import wintypes
from pathlib import Path

import capstone
from unicorn import UC_HOOK_CODE
from unicorn.x86_const import UC_X86_REG_EAX, UC_X86_REG_EBX, UC_X86_REG_ECX, UC_X86_REG_EIP, UC_X86_REG_ESP

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import startup_emulation as se  # noqa: E402

GAME_NAMES = {"vv1": "A New Home", "vv2": "The Lost Children", "vv3": "The Secret City",
              "vv4": "The Tree of Life", "vv5": "New Believers"}
IMAGES = {g: ROOT / "research" / "game-images" / f"Virtual Villagers - {n}" / "Images" for g, n in GAME_NAMES.items()}
ARENA = 0x30000000            # the game-side heap this module hands out
ARENA_SIZE = 0x04000000
RETURN = 0x0BAD0000
MD = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)


# ---------------------------------------------------------------------------------------------------
# Windows GDI, for real

class _RealGdi:
    def __init__(self) -> None:
        g = ctypes.WinDLL("gdi32")
        self.g = g
        g.CreateCompatibleDC.restype = wintypes.HDC
        g.CreateCompatibleDC.argtypes = [wintypes.HDC]
        g.CreateFontW.restype = wintypes.HFONT
        g.CreateFontW.argtypes = [ctypes.c_int] * 5 + [wintypes.DWORD] * 8 + [wintypes.LPCWSTR]
        g.SelectObject.restype = wintypes.HGDIOBJ
        g.SelectObject.argtypes = [wintypes.HDC, wintypes.HGDIOBJ]
        g.DeleteObject.argtypes = [wintypes.HGDIOBJ]
        g.GetTextFaceW.argtypes = [wintypes.HDC, ctypes.c_int, wintypes.LPWSTR]
        g.GetGlyphIndicesW.argtypes = [wintypes.HDC, wintypes.LPCWSTR, ctypes.c_int, ctypes.c_void_p,
                                       wintypes.DWORD]
        g.GetGlyphIndicesW.restype = wintypes.DWORD
        g.GetGlyphOutlineW.argtypes = [wintypes.HDC, wintypes.UINT, wintypes.UINT, ctypes.c_void_p,
                                       wintypes.DWORD, ctypes.c_void_p, ctypes.c_void_p]
        g.GetGlyphOutlineW.restype = wintypes.DWORD
        self.dc = g.CreateCompatibleDC(None)
        self.handles: dict[int, int] = {}
        self.next = 0x00F00010


GDI: _RealGdi | None = None


def _gdi() -> _RealGdi:
    global GDI
    if GDI is None:
        GDI = _RealGdi()
    return GDI


def _wstr(mu, va: int, limit: int = 512) -> str:
    raw = bytes(mu.mem_read(va, limit * 2))
    end = next((i for i in range(0, len(raw), 2) if raw[i:i + 2] == b"\0\0"), len(raw))
    return raw[:end].decode("utf-16-le")


def _wput(mu, va: int, text: str) -> None:
    mu.mem_write(va, text.encode("utf-16-le") + b"\0\0")


class Heap:
    def __init__(self, mu) -> None:
        self.mu = mu
        self.next = ARENA
        mu.mem_map(ARENA, ARENA_SIZE)

    def alloc(self, n: int, zero: bool = True) -> int:
        at = self.next
        self.next = (self.next + max(n, 1) + 15) & ~15
        if self.next > ARENA + ARENA_SIZE:
            raise MemoryError("emulated heap exhausted")
        if zero:
            self.mu.mem_write(at, b"\0" * max(n, 1))
        return at


def _register(machine_ref: dict) -> None:
    """The imports the companion and the game make after WinMain, answered here."""

    def m():
        return machine_ref["machine"]

    def heap_alloc(mc, arg, ret):
        ret(mc.font_heap.alloc(arg(2)))

    def gdi_call(fn):
        def handler(mc, arg, ret):
            ret(fn(mc, arg))
        return handler

    def create_dc(mc, arg):
        return 0x00DC0001

    def create_font(mc, arg):
        g = _gdi()
        values = [struct.unpack("<i", struct.pack("<I", arg(i)))[0] for i in range(5)] + [arg(i) for i in range(5, 13)]
        face = _wstr(mc.mu, arg(13), 64)
        real = g.g.CreateFontW(*values, face)
        fake = g.next
        g.next += 4
        g.handles[fake] = real
        mc.gdi_log.append(("CreateFontW", face, values[0], values[4]))
        return fake

    def select(mc, arg):
        g = _gdi()
        g.g.SelectObject(g.dc, g.handles.get(arg(1), 0))
        return 1

    def delete(mc, arg):
        g = _gdi()
        real = g.handles.pop(arg(0), None)
        if real:
            g.g.DeleteObject(real)
        return 1

    def text_face(mc, arg):
        g = _gdi()
        buf = ctypes.create_unicode_buffer(max(arg(1), 1))
        n = g.g.GetTextFaceW(g.dc, arg(1), buf)
        _wput(mc.mu, arg(2), buf.value)
        return n

    def indices(mc, arg):
        g = _gdi()
        text = bytes(mc.mu.mem_read(arg(1), 2 * arg(2))).decode("utf-16-le")
        out = (ctypes.c_ushort * max(arg(2), 1))()
        r = g.g.GetGlyphIndicesW(g.dc, text, arg(2), out, arg(4))
        mc.mu.mem_write(arg(3), bytes(out)[:2 * arg(2)])
        return r

    def outline(mc, arg):
        g = _gdi()
        gm = ctypes.create_string_buffer(20)
        mat = ctypes.create_string_buffer(bytes(mc.mu.mem_read(arg(6), 16)), 16)
        size = arg(4)
        buf = ctypes.create_string_buffer(size) if size else None
        r = g.g.GetGlyphOutlineW(g.dc, arg(1), arg(2), gm, size, buf, mat)
        mc.mu.mem_write(arg(3), gm.raw)
        if buf is not None and r not in (0, 0xFFFFFFFF):
            mc.mu.mem_write(arg(5), buf.raw[:size])
        return r

    def none(value):
        return lambda mc, arg: value

    def copy_w(mc, arg):
        _wput(mc.mu, arg(0), _wstr(mc.mu, arg(1)))
        return arg(0)

    def cat_w(mc, arg):
        _wput(mc.mu, arg(0), _wstr(mc.mu, arg(0)) + _wstr(mc.mu, arg(1)))
        return arg(0)

    def copyn_w(mc, arg):
        _wput(mc.mu, arg(0), _wstr(mc.mu, arg(1))[: max(arg(2) - 1, 0)])
        return arg(0)

    def cmp_w(mc, arg):
        a, b = _wstr(mc.mu, arg(0)), _wstr(mc.mu, arg(1))
        return ((a > b) - (a < b)) & 0xFFFFFFFF

    def cmpi_w(mc, arg):
        a, b = _wstr(mc.mu, arg(0)).casefold(), _wstr(mc.mu, arg(1)).casefold()
        return ((a > b) - (a < b)) & 0xFFFFFFFF

    def compare_w(mc, arg):
        def text(va, n):
            if n == 0xFFFFFFFF:
                return _wstr(mc.mu, va, 1024)
            return bytes(mc.mu.mem_read(va, 2 * n)).decode("utf-16-le", "surrogatepass")
        a, b = text(arg(2), arg(3)), text(arg(4), arg(5))
        if arg(1) & 1:                      # NORM_IGNORECASE
            a, b = a.casefold(), b.casefold()
        return 2 + ((a > b) - (a < b))

    def len_w(mc, arg):
        return len(_wstr(mc.mu, arg(0)))

    # SDL, called through the game's own import slots (cdecl).
    def sdl_create(mc, arg):
        return mc.new_surface(arg(1), arg(2), arg(4), arg(5), arg(6), arg(7))

    def sdl_free(mc, arg):
        mc.freed.append(arg(0))
        return 0

    def sdl_blit(mc, arg):
        src, srect, dst, drect = arg(0), arg(1), arg(2), arg(3)
        rect = struct.unpack("<4i", mc.mu.mem_read(srect, 16)) if srect else None
        to = struct.unpack("<4i", mc.mu.mem_read(drect, 16)) if drect else None
        mc.blits.append((src, rect, dst, to))
        return 0

    table = {
        "GetProcessHeap": (0, lambda mc, arg, ret: ret(0x00EE0000)),
        "HeapAlloc": (12, heap_alloc),
        "HeapFree": (12, lambda mc, arg, ret: ret(1)),
        "CreateCompatibleDC": (4, gdi_call(create_dc)),
        "CreateFontW": (56, gdi_call(create_font)),
        "SelectObject": (8, gdi_call(select)),
        "DeleteObject": (4, gdi_call(delete)),
        "GetTextFaceW": (12, gdi_call(text_face)),
        "GetGlyphIndicesW": (20, gdi_call(indices)),
        "GetGlyphOutlineW": (28, gdi_call(outline)),
        "AddFontResourceExW": (12, gdi_call(none(0))),
        "GetEnvironmentVariableW": (12, gdi_call(none(0))),
        "RegOpenKeyExW": (20, gdi_call(none(2))),
        "RegEnumValueW": (32, gdi_call(none(259))),
        "RegCloseKey": (4, gdi_call(none(0))),
        "FindFirstFileW": (8, gdi_call(none(0xFFFFFFFF))),
        "FindNextFileW": (8, gdi_call(none(0))),
        "FindClose": (4, gdi_call(none(1))),
        "GetFileSize": (8, gdi_call(none(0xFFFFFFFF))),
        "ReadFile": (20, gdi_call(none(0))),
        "CompareStringOrdinal": (20, gdi_call(none(1))),
        "lstrcpyW": (8, gdi_call(copy_w)),
        "lstrcatW": (8, gdi_call(cat_w)),
        "lstrcpynW": (12, gdi_call(copyn_w)),
        "lstrcmpW": (8, gdi_call(cmp_w)),
        "lstrcmpiW": (8, gdi_call(cmpi_w)),
        "lstrlenW": (4, gdi_call(len_w)),
        "VirtualFree": (12, gdi_call(none(1))),
        "SDL_CreateRGBSurface": (0, gdi_call(sdl_create)),
        "SDL_FreeSurface": (0, gdi_call(sdl_free)),
        "SDL_LockSurface": (0, gdi_call(none(0))),
        "SDL_UnlockSurface": (0, gdi_call(none(0))),
        "SDL_UpperBlit": (0, gdi_call(sdl_blit)),
        # v1.35.89's long names: the Documents folder is answered as missing, so no file is read or written.
        "SHGetSpecialFolderPathW": (16, gdi_call(none(0))),
        "CreateFileW": (28, gdi_call(none(0xFFFFFFFF))),
        "wsprintfW": (0, gdi_call(none(0))),
        "wsprintfA": (0, gdi_call(none(0))),
        "CompareStringW": (24, gdi_call(compare_w)),
    }
    se.EXTRA_IMPORTS.update(table)


# ---------------------------------------------------------------------------------------------------
# The game's routines, found in the stock code


def _calls(image: bytes, start: int, n: int) -> list:
    return list(MD.disasm(image[start - 0x400000:start - 0x400000 + n], start))


def _function_end(image: bytes, start: int) -> int:
    for ins in MD.disasm(image[start - 0x400000:start - 0x400000 + 0x1000], start):
        if ins.mnemonic == "ret":
            return ins.address
    raise AssertionError(hex(start))


class Routines:
    """Every address the emulation enters or answers, found from the stock code."""

    def __init__(self, game: str, image: bytes, tables: dict) -> None:
        g = tables["games"][game]
        self.ctor = int(g["ctor"], 16)
        self.fonts = {font: int(v["table"], 16) for font, v in g["fonts"].items()}
        # The construction site: push spacing; push table; push name; ...; call wrapper.
        self.wrapper, self.names = {}, {}
        for font, table in self.fonts.items():
            at = image.find(b"\x68" + struct.pack("<I", table))
            ins = _calls(image, 0x400000 + at, 64)
            self.names[font] = struct.unpack_from("<I", image, at + 6)[0]
            self.wrapper[font] = int(next(i for i in ins if i.mnemonic == "call").op_str, 16)
        # Inside the constructor: the file check (call; add esp, 4; test al, al), operator new (push 8;
        # call) and the picture loader (the next call).
        ins = _calls(image, self.ctor, 0x220)
        for k, i in enumerate(ins):
            if i.mnemonic == "call" and ins[k + 1].op_str == "esp, 4" and ins[k + 2].op_str == "al, al":
                self.exists = int(i.op_str, 16)
                break
        for k, i in enumerate(ins):
            if i.mnemonic == "push" and i.op_str == "8" and ins[k + 1].mnemonic == "call":
                self.new = int(ins[k + 1].op_str, 16)
                self.load = int(next(j for j in ins[k + 2:] if j.mnemonic == "call").op_str, 16)
                break
        # The text routines: the wrapper that centres text (push ebx; mov ebx, [ecx]; push esi; mov esi,
        # [esp+..]) calls the width routine, then the draw routine.
        m = re.search(rb"\x53\x8b\x19\x56\x8b\x74\x24", image)
        centred = 0x400000 + m.start()
        calls = [int(i.op_str, 16) for i in _calls(image, centred, 120) if i.mnemonic == "call"]
        self.width, self.draw = calls[0], calls[1]
        draw = _calls(image, self.draw, 0x260)
        targets = [i for i in draw if i.mnemonic == "call" and i.op_str.startswith("0x")]
        self.colour = int(targets[0].op_str, 16)
        self.clip = None
        for k, i in enumerate(draw):
            if i in targets and draw[k + 1].op_str == "al, al" and int(i.op_str, 16) != self.colour:
                self.clip = int(i.op_str, 16)
                break
        t = g["text_input"]
        self.text_site, self.text_skip, self.text_post = (int(t["site"], 16), int(t["skip"], 16),
                                                          int(t["post"], 16))
        self.text_offset = t["text_offset"]
        # The text box's character handler: its 0x20..0xFF filter, the function around it.
        f = re.search(rb"\x83\xfa\x1f\x7e.\x81\xfa\xff\x00\x00\x00", image, re.S)
        self.filter = 0x400000 + f.start()
        start = max(image.rfind(b"\x8a\x41\x25", 0, f.start()),       # mov al, [ecx + 0x25]
                    image.rfind(b"\x80\x79\x25\x00", 0, f.start()))   # cmp byte [ecx + 0x25], 0
        self.box_handler = 0x400000 + start
        after = _calls(image, self.filter, 0x60)
        self.box_done = next(i.address for i in after if i.mnemonic == "call")


# ---------------------------------------------------------------------------------------------------
# The machine


class FontRun:
    """One published build after WinMain is reached, with its fonts built."""

    def __init__(self, game: str, mode: str, selection, tables: dict) -> None:
        from test_startup_loader import run
        ref: dict = {}
        _register(ref)
        machine, _result, _features, _before, _shipped = run(game, mode, tuple(selection))
        self.game, self.m = game, machine
        ref["machine"] = machine
        mu = machine.mu
        machine.font_heap = Heap(mu)
        machine.gdi_log, machine.freed, machine.blits = [], [], []
        machine.new_surface = self._new_surface
        image = bytes(mu.mem_read(0x400000, machine.exe_end - 0x400000))
        self.r = Routines(game, image, tables)
        mu.mem_map(RETURN, 0x1000)
        mu.hook_add(UC_HOOK_CODE, self._answer)
        self.pictures: dict[str, int] = {}

    # -- SDL surfaces -----------------------------------------------------------------------------
    def _new_surface(self, w: int, h: int, rmask: int, gmask: int, bmask: int, amask: int,
                     pixels: bytes | None = None) -> int:
        heap = self.m.font_heap
        fmt = heap.alloc(0x28)

        def shift(mask):
            return (mask & -mask).bit_length() - 1 if mask else 0

        self.m.mu.mem_write(fmt, struct.pack("<IIBBH4I8B", 0x16362004, 0, 32, 4, 0, rmask, gmask, bmask, amask,
                                             0, 0, 0, 0, shift(rmask), shift(gmask), shift(bmask), shift(amask)))
        pix = heap.alloc(w * h * 4, zero=pixels is None)
        if pixels is not None:
            self.m.mu.mem_write(pix, pixels)
        surface = heap.alloc(0x40)
        self.m.mu.mem_write(surface, struct.pack("<IIiiiI", 0, fmt, w, h, w * 4, pix))
        return surface

    def surface(self, va: int) -> tuple[int, int, int, bytes, int, int]:
        flags, fmt, w, h, pitch, pix = struct.unpack("<IIiiiI", self.m.mu.mem_read(va, 24))
        amask, = struct.unpack("<I", self.m.mu.mem_read(fmt + 0x18, 4))
        ashift = self.m.mu.mem_read(fmt + 0x23, 1)[0]
        return w, h, pitch, bytes(self.m.mu.mem_read(pix, pitch * h)), amask, ashift

    def _picture(self, path: str) -> int:
        from vv_picture_image import decode_png
        name = path.replace("/", "\\").split("\\")[-1]
        stem = name.split(".")[0]
        img = decode_png((IMAGES[self.game] / f"{stem}.png").read_bytes())
        raw = bytearray()
        d = img.data
        for i in range(0, len(d), 4):
            raw += struct.pack("<I", (d[i + 3] << 24) | (d[i] << 16) | (d[i + 1] << 8) | d[i + 2])
        return self._new_surface(img.width, img.height, 0x00FF0000, 0x0000FF00, 0x000000FF, 0xFF000000, bytes(raw))

    # -- the game's routines the emulation answers --------------------------------------------------
    def _answer(self, mu, address, size, user_data) -> None:
        r = self.r
        if address not in (r.exists, r.new, r.load) and address != r.clip:
            return
        esp = mu.reg_read(UC_X86_REG_ESP)
        ret_to, a1 = struct.unpack("<II", mu.mem_read(esp, 8))
        pop = 0
        if address == r.exists:
            value = 1
        elif address == r.new:
            value = self.m.font_heap.alloc(a1)
        elif address == r.load:                         # thiscall(picture; path), ret 4
            this = mu.reg_read(UC_X86_REG_ECX)
            path = bytes(mu.mem_read(a1, 260)).split(b"\0")[0].decode("latin-1")
            surface = self._picture(path)
            self.pictures[path] = surface
            mu.mem_write(this, struct.pack("<I", surface) + b"\x01")
            value, pop = this, 4
        else:                                           # clipping: everything is on screen
            value, pop = 1, 12
        mu.reg_write(UC_X86_REG_EAX, value)
        mu.reg_write(UC_X86_REG_ESP, esp + 4 + pop)
        mu.reg_write(UC_X86_REG_EIP, ret_to)

    def _call(self, entry: int, ecx: int, *args: int, count: int = 400_000_000) -> int:
        mu = self.m.mu
        esp = se.STACK_TOP - 0x20000 - 4 * len(args)
        mu.mem_write(esp, struct.pack("<I" + "I" * len(args), RETURN, *args))
        mu.reg_write(UC_X86_REG_ESP, esp)
        mu.reg_write(UC_X86_REG_ECX, ecx)
        mu.reg_write(UC_X86_REG_EBX, 0)
        self.m.stop_at = RETURN
        self.m.error = None
        mu.emu_start(entry, RETURN, count=count)
        if self.m.error:
            raise AssertionError(self.m.error)
        if mu.reg_read(UC_X86_REG_EIP) != RETURN:
            raise AssertionError(f"stopped at {mu.reg_read(UC_X86_REG_EIP):#x}")
        return mu.reg_read(UC_X86_REG_EAX)

    # -- what the tests do ---------------------------------------------------------------------------
    def build_font(self, font: str, spacing: int) -> int:
        """The game's own construction of `font`; returns the outer font object."""
        outer = self.m.font_heap.alloc(0x40)
        self._call(self.r.wrapper[font], outer, self.r.names[font], self.r.fonts[font], spacing)
        return outer

    def impl(self, outer: int) -> int:
        return struct.unpack("<I", self.m.mu.mem_read(outer + 4, 4))[0]

    def width(self, outer: int, text: bytes) -> int:
        buf = self.m.font_heap.alloc(len(text) + 1)
        self.m.mu.mem_write(buf, text + b"\0")
        value = self._call(self.r.width, outer, buf, 0x3F800000)
        return struct.unpack("<i", struct.pack("<I", value))[0]

    def glyph_rect(self, impl: int, code: int) -> tuple[int, int, int, int]:
        mu = self.m.mu
        vtable = struct.unpack("<I", mu.mem_read(impl, 4))[0]
        lookup = struct.unpack("<I", mu.mem_read(vtable + 4, 4))[0]
        rect = self.m.font_heap.alloc(16)
        signed = code - 256 if code >= 0x80 else code              # the callers' movsx
        self._call(lookup, impl, signed & 0xFFFFFFFF, rect)
        return struct.unpack("<4i", mu.mem_read(rect, 16))

    def draw(self, outer: int, text: bytes, x: int, y: int) -> list:
        """The game's text draw: (text, x, y, colour, font) on a graphics object whose target is a
        screen-sized surface; returns the SDL_UpperBlit calls (source, rect, target, position)."""
        mu = self.m.mu
        screen = self._new_surface(1024, 768, 0x00FF0000, 0x0000FF00, 0x000000FF, 0xFF000000)
        ctx = self.m.font_heap.alloc(0x400)
        mu.mem_write(ctx + 0x30, struct.pack("<I", screen))
        mu.mem_write(ctx + 0x5C, struct.pack("<I", outer))
        wrapper = self.m.font_heap.alloc(16)
        mu.mem_write(wrapper, struct.pack("<I", ctx))
        buf = self.m.font_heap.alloc(len(text) + 1)
        mu.mem_write(buf, text + b"\0")
        self.m.blits = []
        self._call(self.r.draw, ctx, buf, x, y, 0xFFFFFFFF, outer)
        return list(self.m.blits)

    def type_text(self, utf8: bytes) -> tuple[str, int | None]:
        """SDL_TEXTINPUT with `utf8`: ("post", the character pushed) or ("skip", None)."""
        mu = self.m.mu
        r = self.r
        esp = se.STACK_TOP - 0x30000
        frame = bytearray(0x100)
        frame[r.text_offset:r.text_offset + len(utf8) + 1] = utf8 + b"\0"
        mu.mem_write(esp, bytes(frame))
        mu.reg_write(UC_X86_REG_ESP, esp)
        mu.reg_write(UC_X86_REG_EBX, 0)
        mu.reg_write(UC_X86_REG_EAX, 0x1234)
        stops = {r.text_post, r.text_skip}
        hit = {}

        def stop(uc, address, size, user):
            if address in stops:
                hit["at"] = address
                uc.emu_stop()

        h = mu.hook_add(UC_HOOK_CODE, stop)
        try:
            self.m.stop_at = None
            mu.emu_start(r.text_site, 0, count=200_000)
        finally:
            mu.hook_del(h)
        if hit.get("at") == r.text_skip:
            assert mu.reg_read(UC_X86_REG_ESP) == esp
            return "skip", None
        assert hit.get("at") == r.text_post, hit
        sp = mu.reg_read(UC_X86_REG_ESP)
        assert sp == esp - 12
        message, zero, char = struct.unpack("<3I", mu.mem_read(sp, 12))
        assert (message, zero) == (5, 0)
        return "post", char

    def box_type(self, chars: list[int], limit: int = 27) -> bytes:
        """The stock text box's character handler, fed each posted character; returns its text."""
        mu = self.m.mu
        r = self.r
        box = self.m.font_heap.alloc(0x80)
        flag = self.m.font_heap.alloc(0x20)
        text = self.m.font_heap.alloc(64)
        mu.mem_write(box + 0x1C, struct.pack("<I", flag))
        mu.mem_write(flag + 8, b"\x01")
        mu.mem_write(box + 0x25, b"\x01")                        # focused
        mu.mem_write(box + 0x28, struct.pack("<i", limit))       # the box's limit
        mu.mem_write(box + 0x30, struct.pack("<I", text))
        for ch in chars:
            # The whole handler, to its return (it tells the screen the text changed, as in the game).
            self._call(r.box_handler, box, 5, 0, ch, count=2_000_000)
        return bytes(mu.mem_read(text, 64)).split(b"\0")[0]
