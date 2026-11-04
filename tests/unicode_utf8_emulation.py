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

    def wsprintf_w(mc, arg, ret):
        fmt = ute._wstr(mc.mu, arg(1), 512)
        out, k = [], 2
        for piece in re.split(r"(%d|%ls|%s)", fmt):
            if piece == "%d":
                out.append(str(struct.unpack("<i", struct.pack("<I", arg(k)))[0]))
                k += 1
            elif piece in ("%ls", "%s"):
                out.append(ute._wstr(mc.mu, arg(k), 1024))
                k += 1
            else:
                out.append(piece)
        text = "".join(out)
        ute._wput(mc.mu, arg(0), text)
        ret(len(text))

    def normalize(mc, arg, ret):
        """NormalizeString(form, src, n, dst, room), answered by Windows' own (normaliz)."""
        form, n, room = arg(0), arg(2), arg(4)
        src = (ctypes.c_wchar * max(n, 1)).from_buffer_copy(bytes(mc.mu.mem_read(arg(1), 2 * max(n, 1))))
        dst = (ctypes.c_wchar * max(room, 1))()
        k = ctypes.WinDLL("normaliz").NormalizeString(form, src, n, dst, room)
        if k > 0:
            mc.mu.mem_write(arg(3), bytes(dst)[:2 * k])
        ret(k)

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
        "wsprintfW": (0, wsprintf_w),
        # Without use_files(): no Documents folder is found, nothing is read or written.
        "GetFileAttributesExW": (12, none(0)),
        "SetFilePointerEx": (20, none(0)),
        "CompareStringW": (24, compare_w),
        "SDL_MapRGBA": (0, map_rgba),
        "wsprintfA": (0, none(0)),
        "NormalizeString": (20, normalize),
    })


class TextRun(ute.FontRun):
    """A published build with its two fonts built, and the game's text routines to call."""

    def __init__(self, game: str, selection, tables: dict) -> None:
        _register_uniscribe()
        super().__init__(game, "collection_progression", selection, tables)
        _register_uniscribe()               # after unicode_text_emulation's own answers (wsprintfW...)
        self.addr = routines()[game]
        self.fonts = {}
        for font in ("ldwBurweed27", "ldwarialbold"):
            spacing = tables["games"][game]["fonts"][font]["spacing"]
            self.fonts[font] = self.build_font(font, spacing)
        self.dll = next((m for k, m in self.m.modules.items() if "unicode" in k), None)
        self._files_installed = False

    # -- the Documents folder and the save slot (the Long Names file) ------------------------------------
    MANAGER = {"vv1": (0x48AEDC, 0xABE4), "vv2": (0x4997BC, 0x30378), "vv3": (0x4B309C, 0x12F24),
               "vv4": (0x4CB51C, 0x17114), "vv5": (0x4DACE0, 0x17D80)}      # native/shared/game_save_slot.h

    def use_files(self, slot: int = 1) -> dict:
        """Answer the file APIs from an in-memory Documents folder (startup_emulation's, D:\\Documents) and
        give the game a save manager on `slot`.  write_fault: None, "fail" (nothing written) or "short"
        (half the bytes written, half reported).  Returns the files dict (path -> bytes)."""
        m = self.m
        mu = m.mu
        if not self._files_installed:
            self._files_installed = True
            self.write_fault = None
            self.tick = 1000
            self.pos: dict[str, int] = {}
            original = m._import
            run = self

            def _import(name: str) -> None:
                sp = mu.reg_read(UC_X86_REG_ESP)

                def arg(k):
                    return struct.unpack("<I", mu.mem_read(sp + 4 + 4 * k, 4))[0]

                def ret(value, pop):
                    ret_to = struct.unpack("<I", mu.mem_read(sp, 4))[0]
                    mu.reg_write(UC_X86_REG_EAX, value & 0xFFFFFFFF)
                    mu.reg_write(UC_X86_REG_ESP, sp + 4 + pop)
                    mu.reg_write(UC_X86_REG_EIP, ret_to)

                if name == "GetTickCount":
                    ret(run.tick, 0)
                elif name == "GetFileAttributesExW":
                    path = ute._wstr(mu, arg(0), 300)
                    if path in m.files:
                        # WIN32_FILE_ATTRIBUTE_DATA: 36 bytes
                        mu.mem_write(arg(2), struct.pack("<I24sII", 0x20, b"\0" * 24, 0, len(m.files[path])))
                        run.last_error = 0
                        ret(1, 12)
                    elif any(p.lower().startswith(path.lower() + "\\") for p in m.files) or path in run.dirs:
                        mu.mem_write(arg(2), struct.pack("<I24sII", 0x10, b"\0" * 24, 0, 0))
                        ret(1, 12)
                    else:
                        run.last_error = 2
                        ret(0, 12)
                elif name == "GetLastError":
                    ret(getattr(run, "last_error", 2), 0)
                elif name == "CreateDirectoryW":
                    run.dirs.add(ute._wstr(mu, arg(0), 300))
                    ret(1, 8)
                elif name == "FindFirstFileW":
                    run.last_error = 2
                    ret(0xFFFFFFFF, 8)
                elif name == "CreateFileW":
                    path = ute._wstr(mu, arg(0), 300)
                    if arg(4) == 3 and path not in m.files:
                        run.last_error = 2
                        ret(0xFFFFFFFF, 28)
                        return
                    m._open_path = path
                    m.files.setdefault(path, b"")
                    run.pos[path] = 0
                    ret(se.FILE_HANDLE, 28)
                elif name == "GetFileSize":
                    ret(len(m.files.get(m._open_path or "", b"")), 8)
                elif name == "SetFilePointerEx":
                    run.pos[m._open_path] = arg(1)
                    ret(1, 20)
                elif name == "ReadFile":
                    data = m.files.get(m._open_path, b"")
                    at = run.pos.get(m._open_path, 0)
                    chunk = data[at:at + arg(2)]
                    mu.mem_write(arg(1), chunk)
                    run.pos[m._open_path] = at + len(chunk)
                    if arg(3):
                        mu.mem_write(arg(3), struct.pack("<I", len(chunk)))
                    ret(1, 20)
                elif name == "WriteFile" and run.write_fault:
                    data = bytes(mu.mem_read(arg(1), arg(2)))
                    kept = b"" if run.write_fault == "fail" else data[:len(data) // 2]
                    m.files[m._open_path] += kept
                    if arg(3):
                        mu.mem_write(arg(3), struct.pack("<I", len(kept)))
                    ret(0 if run.write_fault == "fail" else 1, 20)
                else:
                    original(name)

            self.dirs: set[str] = set()
            m._import = _import
        heap = m.font_heap
        address, field = self.MANAGER[self.game]
        manager = heap.alloc(field + 8)
        mu.mem_write(manager + field, struct.pack("<i", slot))
        mu.mem_write(address, struct.pack("<I", manager))
        return m.files

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
        if getattr(self, "_screen", None) is None:       # one screen for every draw: the emulated heap never frees
            self._screen = self._new_surface(1024, 768, 0x00FF0000, 0x0000FF00, 0x000000FF, 0xFF000000)
        screen = self._screen
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
