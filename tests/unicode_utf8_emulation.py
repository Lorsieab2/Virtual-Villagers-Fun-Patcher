"""Run a published build's text routines in unicorn with the v1.35.89 Unicode companions installed.

Builds on tests/unicode_text_emulation.py (the startup chain, the game's own font construction, GDI answered by
the real Windows GDI).  This adds what the UTF-8 code calls: Uniscribe (ScriptItemize, ScriptShape, ScriptPlace,
ScriptLayout, ScriptGetFontProperties) and GetFontData answered by the real usp10/gdi32 on the font the
companion selected, so the units it makes are Windows' own shaping and glyphs; and helpers that call the
game's own routines -- width, draw, the centred draw, line fitting (VV2-VV5), the counted draw and the justified
paragraph (VV3-VV5), the text box's character handler with what SDL_TEXTINPUT posts, Backspace, SetEditable,
SetText and GetText -- exactly as the game calls them, entering at the stock address (so the companion's
detour runs first, as in the game).  The Documents folder is answered as missing, so the Long Names file is
never written here: the pairs stay in memory (tests/test_unicode_utf8.py checks the file format natively).
"""
from __future__ import annotations

import ctypes
import re
import struct
import sys
from ctypes import wintypes
from pathlib import Path

from unicorn import UC_HOOK_CODE
from unicorn.x86_const import UC_X86_REG_EAX, UC_X86_REG_ECX, UC_X86_REG_EIP, UC_X86_REG_ESP

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import startup_emulation as se  # noqa: E402
import unicode_text_emulation as ute  # noqa: E402

ROUTINES_H = ROOT / "native" / "vvfp_unicode_text" / "text_routines.h"


def routines() -> dict:
    text = ROUTINES_H.read_text(encoding="utf-8")
    fields = re.search(r"unsigned int (width[^;]+);\s*unsigned int (chartype[^;]+);", text)
    names = [n.strip() for n in (fields.group(1) + "," + fields.group(2)).split(",")]
    out = {}
    for body, game in re.findall(r"\{(0x[^}]*)\},\s*/\* (vv\d) \*/", text):
        out[game] = dict(zip(names, (int(v.strip().rstrip("u"), 16) for v in body.split(","))))
    return out


class _Usp:
    def __init__(self) -> None:
        self.u = ctypes.WinDLL("usp10")
        self.caches: dict[int, ctypes.c_void_p] = {}
        self.next_cache = 0x00CA0010


USP: _Usp | None = None


def _usp() -> _Usp:
    global USP
    if USP is None:
        USP = _Usp()
    return USP


def _register_uniscribe() -> None:
    def real_dc():
        return ctypes.c_void_p(ute._gdi().dc)

    def cache(mc, va):
        u = _usp()
        fake = struct.unpack("<I", mc.mu.mem_read(va, 4))[0]
        if fake == 0 or fake not in u.caches:
            fake = u.next_cache
            u.next_cache += 4
            u.caches[fake] = ctypes.c_void_p()
            mc.mu.mem_write(va, struct.pack("<I", fake))
        return u.caches[fake]

    def itemize(mc, arg, ret):
        n, cap = arg(1), arg(2)
        text = bytes(mc.mu.mem_read(arg(0), 2 * n)).decode("utf-16-le", "surrogatepass")
        items = (ctypes.c_byte * (8 * (cap + 1)))()
        count = ctypes.c_int()
        hr = _usp().u.ScriptItemize(text, n, cap, None, None, items, ctypes.byref(count))
        if hr == 0:
            mc.mu.mem_write(arg(5), bytes(items)[:8 * (count.value + 1)])
            mc.mu.mem_write(arg(6), struct.pack("<i", count.value))
        ret(hr)

    def layout(mc, arg, ret):
        n = arg(0)
        levels = (ctypes.c_byte * max(n, 1)).from_buffer_copy(bytes(mc.mu.mem_read(arg(1), max(n, 1))))
        v2l = (ctypes.c_int * max(n, 1))()
        hr = _usp().u.ScriptLayout(n, levels, v2l, None)
        if hr == 0 and arg(2):
            mc.mu.mem_write(arg(2), bytes(v2l)[:4 * n])
        ret(hr)

    def shape(mc, arg, ret):
        n, cap = arg(3), arg(4)
        text = bytes(mc.mu.mem_read(arg(2), 2 * n)).decode("utf-16-le", "surrogatepass")
        sa = (ctypes.c_byte * 4).from_buffer_copy(bytes(mc.mu.mem_read(arg(5), 4)))
        glyphs = (ctypes.c_ushort * cap)()
        clusters = (ctypes.c_ushort * max(n, 1))()
        attrs = (ctypes.c_ushort * cap)()
        count = ctypes.c_int()
        hr = _usp().u.ScriptShape(real_dc(), ctypes.byref(cache(mc, arg(1))), text, n, cap, sa, glyphs, clusters,
                                  attrs, ctypes.byref(count))
        if hr == 0:
            k = count.value
            mc.mu.mem_write(arg(5), bytes(sa))
            mc.mu.mem_write(arg(6), bytes(glyphs)[:2 * k])
            mc.mu.mem_write(arg(7), bytes(clusters)[:2 * n])
            mc.mu.mem_write(arg(8), bytes(attrs)[:2 * k])
            mc.mu.mem_write(arg(9), struct.pack("<i", k))
        ret(hr)

    def place(mc, arg, ret):
        k = arg(3)
        glyphs = (ctypes.c_ushort * max(k, 1)).from_buffer_copy(bytes(mc.mu.mem_read(arg(2), 2 * max(k, 1))))
        attrs = (ctypes.c_ushort * max(k, 1)).from_buffer_copy(bytes(mc.mu.mem_read(arg(4), 2 * max(k, 1))))
        sa = (ctypes.c_byte * 4).from_buffer_copy(bytes(mc.mu.mem_read(arg(5), 4)))
        adv = (ctypes.c_int * max(k, 1))()
        off = (ctypes.c_int * (2 * max(k, 1)))()
        abc = (ctypes.c_int * 3)()
        hr = _usp().u.ScriptPlace(real_dc(), ctypes.byref(cache(mc, arg(1))), glyphs, k, attrs, sa, adv, off, abc)
        if hr == 0:
            mc.mu.mem_write(arg(6), bytes(adv)[:4 * k])
            mc.mu.mem_write(arg(7), bytes(off)[:8 * k])
            if arg(8):
                mc.mu.mem_write(arg(8), bytes(abc))
        ret(hr)

    def props(mc, arg, ret):
        out = (ctypes.c_byte * 16)()
        struct.pack_into("<i", out, 0, 16)
        hr = _usp().u.ScriptGetFontProperties(real_dc(), ctypes.byref(cache(mc, arg(1))), out)
        if hr == 0:
            mc.mu.mem_write(arg(2), bytes(out))
        ret(hr)

    def font_data(mc, arg, ret):
        g = ute._gdi()
        g.g.GetFontData.restype = wintypes.DWORD
        g.g.GetFontData.argtypes = [wintypes.HDC, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD]
        size = arg(4)
        if size == 0 or arg(3) == 0:
            ret(g.g.GetFontData(g.dc, arg(1), arg(2), None, 0))
            return
        buf = ctypes.create_string_buffer(size)
        r = g.g.GetFontData(g.dc, arg(1), arg(2), buf, size)
        if r not in (0xFFFFFFFF,):
            mc.mu.mem_write(arg(3), buf.raw[:r])
        ret(r)

    def cstr(mc, va):
        return bytes(mc.mu.mem_read(va, 4096)).split(b"\0")[0]

    def cmp_a(mc, arg, ret):
        a, b = cstr(mc, arg(0)), cstr(mc, arg(1))
        ret((a > b) - (a < b))

    def none(value):
        return lambda mc, arg, ret: ret(value)

    def map_rgba(mc, arg, ret):
        fmt = arg(0)
        masks = struct.unpack("<4I", mc.mu.mem_read(fmt + 0x0C, 16))
        shifts = bytes(mc.mu.mem_read(fmt + 0x20, 4))
        value = 0
        for k, c in enumerate((arg(1) & 0xFF, arg(2) & 0xFF, arg(3) & 0xFF, arg(4) & 0xFF)):
            value |= (c << shifts[k]) & masks[k]
        ret(value)

    def compare_w(mc, arg, ret):
        def text(va, n):
            if n == 0xFFFFFFFF:
                return ute._wstr(mc.mu, va, 1024)
            return bytes(mc.mu.mem_read(va, 2 * n)).decode("utf-16-le", "surrogatepass")
        a, b = text(arg(2), arg(3)), text(arg(4), arg(5))
        if arg(1) & 1:                      # NORM_IGNORECASE
            a, b = a.casefold(), b.casefold()
        ret(2 + ((a > b) - (a < b)))

    se.EXTRA_IMPORTS.update({
        "ScriptItemize": (28, itemize),
        "ScriptLayout": (16, layout),
        "ScriptShape": (40, shape),
        "ScriptPlace": (36, place),
        "ScriptGetFontProperties": (12, props),
        "GetFontData": (20, font_data),
        "lstrcmpA": (8, cmp_a),
        "SHGetSpecialFolderPathW": (16, none(0)),
        "CreateFileW": (28, none(0xFFFFFFFF)),
        "wsprintfW": (0, none(0)),
        "CompareStringW": (24, compare_w),
        "SDL_MapRGBA": (0, map_rgba),
        "wsprintfA": (0, none(0)),
    })


class TextRun(ute.FontRun):
    """A published build with its two fonts built, and the game's text routines to call."""

    def __init__(self, game: str, selection, tables: dict) -> None:
        _register_uniscribe()
        super().__init__(game, "collection_progression", selection, tables)
        self.addr = routines()[game]
        self.fonts = {}
        for font in ("ldwBurweed27", "ldwarialbold"):
            spacing = tables["games"][game]["fonts"][font]["spacing"]
            self.fonts[font] = self.build_font(font, spacing)
        self.dll = next((m for k, m in self.m.modules.items() if "unicode" in k), None)

    # -- the companion's counters ------------------------------------------------------------------
    def export(self, name: str) -> int:
        va = self.dll.exports[name]
        return self._call(va, 0)

    # -- memory -----------------------------------------------------------------------------------
    def cstring(self, data: bytes) -> int:
        buf = self.m.font_heap.alloc(len(data) + 1)
        self.m.mu.mem_write(buf, data + b"\0")
        return buf

    def read_c(self, va: int, n: int = 4096) -> bytes:
        return bytes(self.m.mu.mem_read(va, n)).split(b"\0")[0]

    # -- the game's routines, entered at their stock addresses ---------------------------------------
    def width_of(self, font: str, text: bytes) -> int:
        return self.width(self.fonts[font], text)

    def draw_text(self, font: str, text: bytes, x: int = 100, y: int = 100, colour: int = 0xFFFFFFFF) -> list:
        mu = self.m.mu
        screen = self._new_surface(1024, 768, 0x00FF0000, 0x0000FF00, 0x000000FF, 0xFF000000)
        ctx = self.m.font_heap.alloc(0x400)
        mu.mem_write(ctx + 0x30, struct.pack("<I", screen))
        mu.mem_write(ctx + 0x5C, struct.pack("<I", self.fonts[font]))
        mu.mem_write(ctx + 0x60, struct.pack("<4i", 0, 0, 1024, 768))
        self.m.blits = []
        self._call(self.addr["draw"], ctx, self.cstring(text), x, y, colour, self.fonts[font])
        return list(self.m.blits)

    def linefit(self, font: str, text: bytes, max_width: int, max_count: int = 200) -> list[bytes]:
        """Every line the game's line fitting makes of `text` (as its dialog loop calls it)."""
        out = self.m.font_heap.alloc(max_count + 8)
        para = self.m.font_heap.alloc(4)
        src = self.cstring(text)
        lines = []
        for _ in range(500):
            if self.m.mu.mem_read(src, 1)[0] == 0:
                break
            nxt = self._call(self.addr["linefit"], self.fonts[font], src, out, max_count, max_width, para, 1,
                             0x3F800000)
            lines.append(self.read_c(out, max_count + 1))
            if nxt == src:
                break
            src = nxt
        return lines

    def nbyte(self, font: str, text: bytes, n: int) -> int:
        ctx = self.m.font_heap.alloc(0x400)
        self.m.mu.mem_write(ctx + 0x5C, struct.pack("<I", self.fonts[font]))
        value = self._call(self.addr["nbyte"], ctx, self.cstring(text), n, 0, 0, 1, 0xFFFFFFFF, self.fonts[font])
        return struct.unpack("<i", struct.pack("<I", value))[0]

    def justify_height(self, font: str, text: bytes, width: int) -> int:
        ctx = self.m.font_heap.alloc(0x400)
        self.m.mu.mem_write(ctx + 0x5C, struct.pack("<I", self.fonts[font]))
        holder = self.m.font_heap.alloc(16)
        self.m.mu.mem_write(holder, struct.pack("<I", ctx))
        return self._call(self.addr["justify"], holder, self.cstring(text), 0, 0, width, 0xFFFFFFFF,
                          self.fonts[font], 1)

    # -- a text box -----------------------------------------------------------------------------------
    def new_box(self, limit: int, text: bytes = b"") -> tuple[int, int]:
        """A text box made editable by the game's own SetEditable(1, limit), with `text`; (wrapper, box)."""
        mu = self.m.mu
        box = self.m.font_heap.alloc(0x80)
        flag = self.m.font_heap.alloc(0x20)
        wrapper = self.m.font_heap.alloc(0x20)
        mu.mem_write(wrapper + 0x10, struct.pack("<I", box))
        mu.mem_write(box + 0x1C, struct.pack("<I", flag))
        mu.mem_write(flag + 8, b"\x01")
        mu.mem_write(box + 0x25, b"\x01")
        mu.mem_write(box + 0x30, struct.pack("<I", self.cstring(text)))
        self._call(self.addr["seteditable"], box, 1, limit)
        return wrapper, box

    def box_limit(self, box: int) -> int:
        return struct.unpack("<i", self.m.mu.mem_read(box + 0x28, 4))[0]

    def box_text(self, box: int) -> bytes:
        return self.read_c(struct.unpack("<I", self.m.mu.mem_read(box + 0x30, 4))[0])

    def handler(self, box: int, message: int, p2: int) -> int:
        """The box's character handler (thiscall; message, 0, p2), from its stock entry."""
        return self._call(self.addr["handler"], box, message, 0, p2) & 0xFF

    def type_into(self, box: int, utf8: bytes) -> str:
        """SDL_TEXTINPUT with `utf8`, then what it posted handed to the box's handler, as the game does."""
        kind, char = self.type_text(utf8)
        if kind == "post":
            self.handler(box, 5, char)
        return kind

    def backspace(self, box: int) -> None:
        self.handler(box, 5, 8)

    def set_text(self, box: int, text: bytes) -> None:
        self._call(self.addr["settext"], box, self.cstring(text))

    def get_text(self, wrapper: int, size: int) -> bytes:
        buf = self.m.font_heap.alloc(size + 8)
        self.m.mu.mem_write(buf, b"\xEE" * (size + 8))
        self._call(self.addr["gettext"], wrapper, buf, size)
        return bytes(self.m.mu.mem_read(buf, size + 8))


def composite(run: TextRun, blits: list, size: tuple[int, int] = (1024, 200), background=(40, 60, 40)):
    """The blits drawn over a plain background, as RGBA bytes (alpha-blended, the source's own colours)."""
    w, h = size
    out = bytearray(bytes(background) + b"\xff") * (w * h)
    for src, rect, _dst, to in blits:
        sw, sh, pitch, pixels, amask, ashift = run.surface(src)
        x1, y1, rw, rh = rect
        dx, dy = to[0], to[1]
        for yy in range(rh):
            for xx in range(rw):
                if not (0 <= dx + xx < w and 0 <= dy + yy < h):
                    continue
                p = struct.unpack_from("<I", pixels, (y1 + yy) * pitch + (x1 + xx) * 4)[0]
                a = (p & amask) >> ashift
                if a == 0:
                    continue
                r, g, b = (p >> 16) & 0xFF, (p >> 8) & 0xFF, p & 0xFF
                o = ((dy + yy) * w + dx + xx) * 4
                for k, c in enumerate((r, g, b)):
                    out[o + k] = (c * a + out[o + k] * (255 - a)) // 255
    return bytes(out)


def save_picture(run: TextRun, blits: list, path, size=(1024, 200)) -> None:
    from vv_picture_image import Image, encode_png
    data = composite(run, blits, size)
    Path(path).write_bytes(encode_png(Image(size[0], size[1], bytearray(data))))
