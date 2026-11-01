"""Every Virtual Villagers bitmap font, and the letters the patcher makes for it.

Shared by the in-game companion "VVFP Unicode Text.dll" (native/vvfp_unicode_text, which runs the same
steps in C) and by the patcher's own windows (the Picture Studio Text tool), so a letter looks the same in
both.

THE FONTS.  Each game draws every word with two LDW bitmap fonts (data/font_glyph_tables.json):

    "ldwBurweed27"  the story, menu and button font: Burweed, 27-pixel lines;
    "ldwarialbold"  the small font of the Details, Tech and log screens: Arial Bold, 20-pixel lines.

The picture (Images/<font>.png) is pure white; each letter is its alpha (anti-aliased coverage) and the
game tints it when it draws.  A New Home and The Lost Children's fonts hold only A-Z, a-z, 0-9 and
! " ' , . ? / ` : - and the space; The Secret City, The Tree of Life and New Believers add the Latin-1
letters and signs (The Secret City from U+00A2, the others from U+00A1).  A code with no letter draws the
font's first letter (A New Home's 'A', the later games' '!').

THE MISSING LETTERS.  For every printable Windows-1252 character a font lacks (`missing`), `glyph`
makes one, in this order:

  1. NBSP draws as the space, the soft hyphen as '-' (when the font has them).
  2. The font's own typeface, when it is installed: "Burweed ICG" for ldwBurweed27 (a commercial font;
     the patcher never ships it -- install it for the best-matching accents), "Arial" Bold for
     ldwarialbold (part of Windows).  The letter is drawn by Windows (GDI, 65 grey levels) at the size
     whose 'H' is exactly as tall as the bitmap's 'H', thickened a pixel at a time while it is lighter
     than the bitmap's 'H', and set on the bitmap's baseline.
  3. A letter with an accent (e with acute, S with caron, ...) whose plain letter the font has (or has
     been given): the bitmap's own plain letter, with the accent drawn by the stand-in typeface below at
     the same size, centred above it (below it for the cedilla).  An i loses its dot first.
  4. Anything else is drawn whole by the stand-in typeface: "Comic Sans MS" Bold for Burweed (the nearest
     hand-lettered face Windows ships), Arial Bold for Arial; then Segoe UI Bold and Segoe UI Symbol.

  A letter taller than the line (a capital with an accent) has its part above the baseline squeezed into
  the line, as the later games' own accented capitals are.  Each letter's box is its ink plus the font's
  usual left and right margins, and the game advances by the box width plus the font's spacing.

Everything is whole-number arithmetic so the C companion produces the very same pixels.

NOTHING OF THE GAME IS SHIPPED.  The base letters come from the player's own game pictures, the typefaces
from the player's own Windows; the patcher ships only these rules and the coordinates in
data/font_glyph_tables.json.

INTERFACE (stable; the Picture Studio Text tool uses it):

    GAMES -> ("vv1", ..., "vv5")
    fonts(game) -> ("ldwBurweed27", "ldwarialbold")
    metrics(game, font, images_dir) -> FontMetrics
    glyph(game, font, char, images_dir) -> Glyph | None      (None: not a Windows-1252 character)
    missing(game, font) -> str                                (the characters the stock font lacks)
    coverage(game, font, images_dir) -> {char: source}
    text_width(game, font, text, images_dir) -> int          (the game's own measure)
    render_text(game, font, text, images_dir, colour=(255, 255, 255)) -> vv_picture_image.Image (RGBA)

    FontGlyphs(game, font, images_dir, use_burweed=True)     (the same, for one font; use_burweed=False
                                                             leaves an installed Burweed ICG out)
    Glyph: .char, .mask (Mask: .w, .h, .px row-major alpha 0..255), .source, .image(colour)
    FontMetrics: .line, .baseline, .cap_top, .x_top, .left, .right, .spacing

Nothing here needs Pillow: pictures are vv_picture_image.Image (pure Python).

`images_dir` is the game's own Images folder (or any folder holding its two font pictures).
"""
from __future__ import annotations

import json
import sys
import unicodedata
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TABLES = ROOT / "data" / "font_glyph_tables.json"

GAMES = ("vv1", "vv2", "vv3", "vv4", "vv5")
FONTS = ("ldwBurweed27", "ldwarialbold")
INK = 32            # alpha at or above this counts as ink when measuring
ACCENT_GAP = 1      # rows between a letter and its accent

# Typefaces: (face, weight).  TRUE faces are the bitmaps' own designs; a stand-in is the nearest face
# Windows itself ships; the chain draws what neither has.
TRUE_FACE = {"ldwBurweed27": ("Burweed ICG", 400), "ldwarialbold": ("Arial", 700)}
STAND_IN = {"ldwBurweed27": ("Comic Sans MS", 700), "ldwarialbold": ("Arial", 700)}
CHAIN = (("Segoe UI", 700), ("Segoe UI Symbol", 400))

# The accents a Windows-1252 letter can carry, as the spacing character drawn for each.
MARKS = {
    "̀": "`", "́": "´", "̂": "ˆ", "̃": "˜", "̈": "¨",
    "̊": "˚", "̧": "¸", "̌": "ˇ",
}
BELOW = {"̧"}


def _cp1252_printable() -> str:
    out = []
    for b in range(0x20, 0x100):
        if b == 0x7F:
            continue
        try:
            out.append(bytes([b]).decode("cp1252"))
        except UnicodeDecodeError:
            continue
    return "".join(out)


PRINTABLE = _cp1252_printable()


def decompose(ch: str) -> tuple[str, str] | None:
    """(plain letter, combining accent) for a Windows-1252 letter with one accent the patcher draws."""
    d = unicodedata.normalize("NFD", ch)
    if len(d) == 2 and d[1] in MARKS:
        return d[0], d[1]
    return None


# ---------------------------------------------------------------------------------------------------
# The tables


@lru_cache(maxsize=1)
def _tables() -> dict:
    return json.loads(TABLES.read_text(encoding="utf-8"))["games"]


def fonts(game: str) -> tuple[str, ...]:
    if game not in GAMES:
        raise KeyError(game)
    return FONTS


def entries(game: str, font: str) -> list[list[int]]:
    """The stock glyph entries after the constructor's row wrap: [code, x1, y1, x2, y2]."""
    return _tables()[game]["fonts"][font]["entries"]


def spacing(game: str, font: str) -> int:
    return _tables()[game]["fonts"][font]["spacing"]


def to_byte(ch: str) -> int | None:
    try:
        b = ch.encode("cp1252")
    except UnicodeEncodeError:
        return None
    return b[0] if len(b) == 1 else None


def missing(game: str, font: str) -> str:
    have = {e[0] for e in entries(game, font)}
    return "".join(ch for ch in PRINTABLE if to_byte(ch) not in have)


# ---------------------------------------------------------------------------------------------------
# Alpha masks: plain lists of rows, values 0..255


@dataclass
class Mask:
    w: int
    h: int
    px: list[int] = field(default_factory=list)          # row-major, w*h

    @classmethod
    def blank(cls, w: int, h: int) -> "Mask":
        return cls(w, h, [0] * (w * h))

    def at(self, x: int, y: int) -> int:
        return self.px[y * self.w + x] if 0 <= x < self.w and 0 <= y < self.h else 0

    def ink(self) -> tuple[int, int, int, int] | None:
        """(left, top, right, bottom) inclusive of the cells at or above INK; None when empty."""
        cols = [x for x in range(self.w) if any(self.px[y * self.w + x] >= INK for y in range(self.h))]
        rows = [y for y in range(self.h) if any(self.px[y * self.w + x] >= INK for x in range(self.w))]
        if not cols:
            return None
        return cols[0], rows[0], cols[-1], rows[-1]

    def crop(self, l: int, t: int, r: int, b: int) -> "Mask":
        out = Mask.blank(r - l + 1, b - t + 1)
        for y in range(out.h):
            for x in range(out.w):
                out.px[y * out.w + x] = self.at(l + x, t + y)
        return out

    def total(self) -> int:
        return sum(self.px)


@dataclass
class FontMetrics:
    game: str
    font: str
    line: int          # the line (box) height
    baseline: int      # rows from the box top to the baseline (the row under 'H')
    cap_top: int       # first ink row of 'H'
    x_top: int         # first ink row of 'x'
    left: int          # the usual left margin of a letter inside its box
    right: int         # the usual right margin
    spacing: int       # added to every box width when advancing


@dataclass
class Glyph:
    char: str
    mask: Mask         # the box: mask.w is the box width, mask.h the line height
    source: str        # "game", "alias", "ttf:<face>", "composed:<face>", "stand-in:<face>"

    @property
    def advance_box(self) -> int:
        return self.mask.w

    def image(self, colour=(255, 255, 255)):
        """The letter as a vv_picture_image.Image (straight RGBA), tinted `colour` as the game tints."""
        from vv_picture_image import Image
        data = bytearray()
        for a in self.mask.px:
            data += bytes((colour[0], colour[1], colour[2], a))
        return Image(self.mask.w, self.mask.h, data)


# ---------------------------------------------------------------------------------------------------
# The sheet


class Sheet:
    def __init__(self, game: str, font: str, images_dir: Path):
        from vv_picture_image import decode_png
        img = decode_png((Path(images_dir) / f"{font}.png").read_bytes())
        self.w, self.h = img.width, img.height
        self.alpha = list(img.data[3::4])
        self.entries: dict[int, list[int]] = {}
        for e in entries(game, font):
            self.entries.setdefault(e[0], e)          # the game's index takes a code's first entry
        self.first = entries(game, font)[0]

    def box(self, code: int) -> Mask | None:
        e = self.entries.get(code)
        if e is None:
            return None
        _, x1, y1, x2, y2 = e
        m = Mask.blank(x2 - x1, y2 - y1)
        for y in range(m.h):
            for x in range(m.w):
                sx, sy = x1 + x, y1 + y
                m.px[y * m.w + x] = self.alpha[sy * self.w + sx] if 0 <= sx < self.w and 0 <= sy < self.h else 0
        return m


def _median(values: list[int]) -> int:
    values = sorted(values)
    return values[(len(values) - 1) // 2] if values else 0


def _measure(game: str, font: str, sheet: Sheet) -> FontMetrics:
    h = sheet.box(ord("H"))
    x = sheet.box(ord("x"))
    hi, xi = h.ink(), x.ink()
    lefts, rights = [], []
    for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz":
        m = sheet.box(ord(c))
        if m is None:
            continue
        ink = m.ink()
        if ink is None:
            continue
        lefts.append(ink[0])
        rights.append(m.w - 1 - ink[2])
    line = sheet.first[4] - sheet.first[2]
    return FontMetrics(game, font, line, hi[3] + 1, hi[1], xi[1], _median(lefts), _median(rights),
                       spacing(game, font))


# ---------------------------------------------------------------------------------------------------
# Windows' own drawing of a typeface (GDI GetGlyphOutlineW, GGO_GRAY8_BITMAP)


class _Gdi:
    GGO_GRAY8_BITMAP = 6
    GGI_MARK_NONEXISTING_GLYPHS = 1

    def __init__(self) -> None:
        import ctypes
        from ctypes import wintypes
        self.ct = ctypes
        self.gdi = ctypes.WinDLL("gdi32", use_last_error=True)
        self.gdi.CreateCompatibleDC.restype = wintypes.HDC
        self.gdi.CreateCompatibleDC.argtypes = [wintypes.HDC]
        self.gdi.CreateFontW.restype = wintypes.HFONT
        self.gdi.CreateFontW.argtypes = [ctypes.c_int] * 5 + [wintypes.DWORD] * 8 + [wintypes.LPCWSTR]
        self.gdi.SelectObject.restype = wintypes.HGDIOBJ
        self.gdi.SelectObject.argtypes = [wintypes.HDC, wintypes.HGDIOBJ]
        self.gdi.GetTextFaceW.argtypes = [wintypes.HDC, ctypes.c_int, wintypes.LPWSTR]

        class POINT(ctypes.Structure):
            _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

        class GLYPHMETRICS(ctypes.Structure):
            _fields_ = [("gmBlackBoxX", wintypes.UINT), ("gmBlackBoxY", wintypes.UINT),
                        ("gmptGlyphOrigin", POINT), ("gmCellIncX", ctypes.c_short),
                        ("gmCellIncY", ctypes.c_short)]

        class FIXED(ctypes.Structure):
            _fields_ = [("fract", wintypes.WORD), ("value", ctypes.c_short)]

        class MAT2(ctypes.Structure):
            _fields_ = [("eM11", FIXED), ("eM12", FIXED), ("eM21", FIXED), ("eM22", FIXED)]

        self.GLYPHMETRICS, self.MAT2, self.FIXED = GLYPHMETRICS, MAT2, FIXED
        self.gdi.GetGlyphOutlineW.restype = wintypes.DWORD
        self.gdi.GetGlyphOutlineW.argtypes = [wintypes.HDC, wintypes.UINT, wintypes.UINT,
                                              ctypes.POINTER(GLYPHMETRICS), wintypes.DWORD, ctypes.c_void_p,
                                              ctypes.POINTER(MAT2)]
        self.gdi.GetGlyphIndicesW.argtypes = [wintypes.HDC, wintypes.LPCWSTR, ctypes.c_int,
                                              ctypes.POINTER(wintypes.WORD), wintypes.DWORD]
        self.dc = self.gdi.CreateCompatibleDC(None)
        self.fonts: dict = {}
        self.present: dict = {}

    def _select(self, face: str, weight: int, ppem: int) -> bool:
        key = (face, weight, ppem)
        font = self.fonts.get(key)
        if font is None:
            font = self.gdi.CreateFontW(-ppem, 0, 0, 0, weight, 0, 0, 0, 1, 0, 0, 4, 0, face)
            self.fonts[key] = font
        self.gdi.SelectObject(self.dc, font)
        return True

    def has_face(self, face: str, weight: int) -> bool:
        if face not in self.present:
            self._select(face, weight, 20)
            buf = self.ct.create_unicode_buffer(64)
            self.gdi.GetTextFaceW(self.dc, 64, buf)
            self.present[face] = buf.value.casefold() == face.casefold()
        return self.present[face]

    def has_char(self, face: str, weight: int, ch: str) -> bool:
        if not self.has_face(face, weight):
            return False
        self._select(face, weight, 20)
        out = (self.ct.c_ushort * 1)()
        self.gdi.GetGlyphIndicesW(self.dc, ch, 1, out, self.GGI_MARK_NONEXISTING_GLYPHS)
        return out[0] != 0xFFFF

    def raster(self, face: str, weight: int, ppem: int, ch: str) -> tuple[Mask, int] | None:
        """(the black box's coverage 0..255, rows from its top to the baseline); None when empty."""
        self._select(face, weight, ppem)
        gm = self.GLYPHMETRICS()
        one, zero = self.FIXED(0, 1), self.FIXED(0, 0)
        mat = self.MAT2(one, zero, zero, one)
        size = self.gdi.GetGlyphOutlineW(self.dc, ord(ch), self.GGO_GRAY8_BITMAP, self.ct.byref(gm), 0, None,
                                         self.ct.byref(mat))
        if size in (0, 0xFFFFFFFF):
            return None
        buf = (self.ct.c_ubyte * size)()
        self.gdi.GetGlyphOutlineW(self.dc, ord(ch), self.GGO_GRAY8_BITMAP, self.ct.byref(gm), size, buf,
                                  self.ct.byref(mat))
        w, h = gm.gmBlackBoxX, gm.gmBlackBoxY
        pitch = (w + 3) & ~3
        m = Mask.blank(w, h)
        for y in range(h):
            for x in range(w):
                v = buf[y * pitch + x]
                m.px[y * w + x] = (v * 255 + 32) // 64 if v < 64 else 255
        return m, gm.gmptGlyphOrigin.y


def ttf_family(data: bytes) -> str | None:
    """The family name (name ID 1) of a TrueType / OpenType file: the Windows (3, 1) record, else the
    Macintosh (1, 0) one.  None when the file is not one."""
    import struct
    try:
        if data[:4] == b"ttcf":
            data_off = struct.unpack_from(">I", data, 12)[0]
        else:
            data_off = 0
        num = struct.unpack_from(">H", data, data_off + 4)[0]
        for i in range(num):
            tag, _, off, length = struct.unpack_from(">4sIII", data, data_off + 12 + 16 * i)
            if tag != b"name":
                continue
            _, count, strings = struct.unpack_from(">HHH", data, off)
            found = {}
            for k in range(count):
                pid, eid, lang, nid, ln, so = struct.unpack_from(">6H", data, off + 6 + 12 * k)
                if nid != 1:
                    continue
                raw = data[off + strings + so:off + strings + so + ln]
                if pid == 3 and eid in (0, 1) and (lang == 0x409 or "w" not in found):
                    found["w"] = raw.decode("utf-16-be", "replace")
                elif pid == 1 and eid == 0 and "m" not in found:
                    found["m"] = raw.decode("latin-1")
            return found.get("w") or found.get("m")
    except (struct.error, IndexError):
        return None
    return None


def font_files(word: str) -> list[Path]:
    """Installed font files whose registered name or file name holds `word` (any case): the per-user and
    the system font lists in the registry, then the per-user and system Fonts folders."""
    import os
    out: list[Path] = []
    folders = [Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "Windows" / "Fonts",
               Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"]
    try:
        import winreg
        for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
            try:
                key = winreg.OpenKey(hive, r"Software\Microsoft\Windows NT\CurrentVersion\Fonts")
            except OSError:
                continue
            with key:
                i = 0
                while True:
                    try:
                        name, value, _ = winreg.EnumValue(key, i)
                    except OSError:
                        break
                    i += 1
                    if word.casefold() in str(name).casefold() and isinstance(value, str):
                        p = Path(value)
                        out.append(p if p.is_absolute() else folders[1] / p)
    except ImportError:
        pass
    for folder in folders:
        try:
            out.extend(sorted(p for p in folder.iterdir() if word.casefold() in p.name.casefold()
                              and p.suffix.lower() in (".ttf", ".otf", ".ttc")))
        except OSError:
            pass
    seen, unique = set(), []
    for p in out:
        k = str(p).casefold()
        if k not in seen and p.is_file():
            seen.add(k)
            unique.append(p)
    return unique


@lru_cache(maxsize=1)
def _gdi() -> _Gdi | None:
    if sys.platform != "win32":
        return None
    try:
        gdi = _Gdi()
    except (OSError, AttributeError):
        return None
    # Burweed ICG: used only when the player has it.  A file in a Fonts folder that Windows has not
    # registered is added for this process alone (FR_PRIVATE), never installed.
    gdi.burweed = None
    for path in font_files("Burweed"):
        try:
            family = ttf_family(path.read_bytes())
        except OSError:
            continue
        if not family:
            continue
        if not gdi.has_face(family, 400):
            gdi.gdi.AddFontResourceExW.argtypes = [gdi.ct.c_wchar_p, gdi.ct.c_uint, gdi.ct.c_void_p]
            if gdi.gdi.AddFontResourceExW(str(path), 0x10, None) <= 0:
                continue
            gdi.present.pop(family, None)
            gdi.fonts = {k: v for k, v in gdi.fonts.items() if k[0] != family}
        if gdi.has_face(family, 400):
            gdi.burweed = family
            break
    return gdi


# ---------------------------------------------------------------------------------------------------
# Making a letter


def _embolden(m: Mask) -> Mask:
    out = Mask.blank(m.w + 1, m.h)
    for y in range(m.h):
        for x in range(out.w):
            out.px[y * out.w + x] = max(m.at(x, y), m.at(x - 1, y))
    return out


class _Face:
    """One typeface fitted to one bitmap font: its size and how much it is thickened."""

    def __init__(self, gdi: _Gdi, face: str, weight: int, metrics: FontMetrics, sheet_h: Mask):
        self.gdi, self.face, self.weight = gdi, face, weight
        cap = metrics.baseline - metrics.cap_top
        self.ppem, self.bold = 0, 0
        best = None
        for ppem in range(6, 81):
            r = gdi.raster(face, weight, ppem, "H")
            if r is None:
                continue
            diff = abs(r[0].h - cap)
            if best is None or diff < best[0]:
                best = (diff, ppem)
            if r[0].h >= cap:
                break
        if best is None:
            return
        self.ppem = best[1]
        target = sheet_h.total()
        r = gdi.raster(face, weight, self.ppem, "H")
        m = r[0]
        while self.bold < 2 and m.total() * 100 < target * 85:
            m = _embolden(m)
            self.bold += 1

    def draw(self, ch: str) -> tuple[Mask, int] | None:
        if self.ppem == 0:
            return None
        r = self.gdi.raster(self.face, self.weight, self.ppem, ch)
        if r is None:
            return None
        m, above = r
        for _ in range(self.bold):
            m = _embolden(m)
        return m, above


def _fit(canvas: Mask, top: int, metrics: FontMetrics) -> Mask:
    """`canvas` rows start at line row `top` (may be negative); return the line box (metrics.line rows),
    the part above the baseline squeezed into the line when it starts above row 0, the rest clipped."""
    line, base = metrics.line, metrics.baseline
    out = Mask.blank(canvas.w, line)
    if top >= 0:
        for y in range(line):
            for x in range(canvas.w):
                out.px[y * canvas.w + x] = canvas.at(x, y - top)
        return out
    src_rows = base - top                # canvas rows 0 .. src_rows-1 are above the baseline
    for r in range(base):
        lo = r * src_rows // base
        hi = max(lo + 1, ((r + 1) * src_rows + base - 1) // base)
        for x in range(canvas.w):
            out.px[r * canvas.w + x] = max(canvas.at(x, y) for y in range(lo, hi))
    for y in range(base, line):
        for x in range(canvas.w):
            out.px[y * canvas.w + x] = canvas.at(x, y - top)
    return out


def _place(ink: Mask, top: int, metrics: FontMetrics) -> Mask:
    """A whole drawn letter in its box: margins on both sides, set at row `top`."""
    canvas = Mask.blank(metrics.left + ink.w + metrics.right, ink.h)
    for y in range(ink.h):
        for x in range(ink.w):
            canvas.px[y * canvas.w + metrics.left + x] = ink.px[y * ink.w + x]
    return _fit(canvas, top, metrics)


class FontGlyphs:
    """Every letter of one game font, made once."""

    def __init__(self, game: str, font: str, images_dir: Path, use_burweed: bool = True):
        """use_burweed=False leaves an installed Burweed ICG out, as on a machine without it."""
        self.game, self.font = game, font
        self.use_burweed = use_burweed
        self.sheet = Sheet(game, font, images_dir)
        self.metrics = _measure(game, font, self.sheet)
        self.gdi = _gdi()
        self.cache: dict[str, Glyph | None] = {}
        self.faces: dict[tuple[str, int], _Face | None] = {}

    def _true(self) -> tuple[str, int] | None:
        """The bitmap's own typeface when the player has it."""
        if self.gdi is None:
            return None
        if self.font == "ldwBurweed27":
            burweed = getattr(self.gdi, "burweed", None) if self.use_burweed else None
            return (burweed, 400) if burweed else None
        return TRUE_FACE[self.font]

    def _face(self, face: str, weight: int) -> _Face | None:
        key = (face, weight)
        if key not in self.faces:
            ok = self.gdi is not None and self.gdi.has_face(face, weight)
            self.faces[key] = _Face(self.gdi, face, weight, self.metrics, self.sheet.box(ord("H"))) if ok else None
        return self.faces[key]

    def _whole(self, face: str, weight: int, ch: str) -> Mask | None:
        f = self._face(face, weight)
        if f is None or not self.gdi.has_char(face, weight, ch):
            return None
        drawn = f.draw(ch)
        if drawn is None:
            return None
        ink, above = drawn
        return _place(ink, self.metrics.baseline - above, self.metrics)

    def _compose(self, ch: str) -> tuple[Mask, str] | None:
        parts = decompose(ch)
        if parts is None:
            return None
        plain, accent = parts
        base_glyph = self.glyph(plain)
        if base_glyph is None:
            return None
        face, weight = self._true() or STAND_IN[self.font]
        f = self._face(face, weight)
        if f is None:
            face, weight = STAND_IN[self.font]
            f = self._face(face, weight)
        if f is None or not self.gdi.has_char(face, weight, MARKS[accent]):
            return None
        drawn = f.draw(MARKS[accent])
        if drawn is None:
            return None
        mark = drawn[0]
        mi = mark.ink()
        if mi is None:
            return None
        mark = mark.crop(*mi)
        m = self.metrics
        base = Mask(base_glyph.mask.w, base_glyph.mask.h, list(base_glyph.mask.px))
        if plain in "ij":                     # the dot goes; the accent takes its place
            for y in range(m.x_top):
                for x in range(base.w):
                    base.px[y * base.w + x] = 0
        bi = base.ink()
        if bi is None:
            return None
        if accent in BELOW:
            mark_top = m.baseline
        else:
            letter_top = bi[1]
            mark_top = letter_top - ACCENT_GAP - mark.h
        mark_left = (bi[0] + bi[2] + 1) // 2 - mark.w // 2
        left_pad = max(0, -mark_left)
        width = max(base.w + left_pad, left_pad + mark_left + mark.w)
        top = min(0, mark_top)
        bottom = max(base.h, mark_top + mark.h)
        canvas = Mask.blank(width, bottom - top)
        for y in range(base.h):
            for x in range(base.w):
                canvas.px[(y - top) * width + x + left_pad] = base.px[y * base.w + x]
        for y in range(mark.h):
            for x in range(mark.w):
                i = (mark_top + y - top) * width + mark_left + left_pad + x
                canvas.px[i] = max(canvas.px[i], mark.px[y * mark.w + x])
        return _fit(canvas, top, m), f"composed:{face}"

    def _make(self, ch: str) -> Glyph | None:
        code = to_byte(ch)
        if code is None:
            return None
        own = self.sheet.box(code)
        if own is not None:
            return Glyph(ch, own, "game")
        if ch == " " and self.sheet.box(0x20) is not None:
            return Glyph(ch, self.sheet.box(0x20), "alias")
        if ch == "­" and self.sheet.box(ord("-")) is not None:
            return Glyph(ch, self.sheet.box(ord("-")), "alias")
        if self.gdi is None:
            return None
        true = self._true()
        if true is not None:
            m = self._whole(true[0], true[1], ch)
            if m is not None:
                return Glyph(ch, m, f"ttf:{true[0]}")
        composed = self._compose(ch)
        if composed is not None:
            return Glyph(ch, composed[0], composed[1])
        for face, weight in (STAND_IN[self.font],) + CHAIN:
            m = self._whole(face, weight, ch)
            if m is not None:
                return Glyph(ch, m, f"stand-in:{face}")
        return None

    def text_width(self, text: str) -> int:
        """The width the game measures (A New Home 0x402160): each letter's box plus the font's spacing,
        less one spacing at the end; a character the font cannot show measures as its first letter."""
        first = self.sheet.first
        total = 0
        for ch in text:
            g = self.glyph(ch)
            total += (g.mask.w if g else first[3] - first[1]) + self.metrics.spacing
        return total - self.metrics.spacing if total else 0

    def glyph(self, ch: str) -> Glyph | None:
        if ch not in self.cache:
            self.cache[ch] = None          # a letter never builds on itself
            self.cache[ch] = self._make(ch)
        return self.cache[ch]


_loaded: dict[tuple[str, str, str], FontGlyphs] = {}


def _font(game: str, font: str, images_dir) -> FontGlyphs:
    key = (game, font, str(Path(images_dir).resolve()))
    if key not in _loaded:
        _loaded[key] = FontGlyphs(game, font, Path(images_dir))
    return _loaded[key]


def metrics(game: str, font: str, images_dir) -> FontMetrics:
    return _font(game, font, images_dir).metrics


def glyph(game: str, font: str, char: str, images_dir) -> Glyph | None:
    return _font(game, font, images_dir).glyph(char)


def coverage(game: str, font: str, images_dir) -> dict[str, str]:
    f = _font(game, font, images_dir)
    return {ch: (g.source if g else "none") for ch in PRINTABLE for g in (f.glyph(ch),)}


def text_width(game: str, font: str, text: str, images_dir) -> int:
    """The width the game measures (FontGlyphs.text_width)."""
    return _font(game, font, images_dir).text_width(text)


def render_text(game: str, font: str, text: str, images_dir, colour=(255, 255, 255)):
    """`text` as the game draws it on one line: a vv_picture_image.Image, clear where nothing is drawn."""
    from vv_picture_image import Image
    f = _font(game, font, images_dir)
    width = max(1, text_width(game, font, text, images_dir) + f.metrics.spacing)
    img = Image.new(width, f.metrics.line)
    x = 0
    for ch in text:
        g = f.glyph(ch) or Glyph(ch, f.sheet.box(f.sheet.first[0]), "game")
        img.draw(g.image(colour), x, 0)
        x += g.mask.w + f.metrics.spacing
    return img
