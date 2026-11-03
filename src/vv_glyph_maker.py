"""Picture Studio's Text tab: make the characters a game font lacks, in that font's style.

The games draw text from white glyph sheets (ldwarialbold.png, ldwBurweed27.png) that only hold the
characters the developers needed.  src/vv_pictures_text.py lays text out in those sheets; for every
character a sheet does not have, it asks this module for a generated glyph that matches the sheet:
the same cap height, the same baseline, the sheet's own alpha levels, its fill colour and (Burweed)
its outline.  Nothing ships: no font files, no font bytes, no third-party packages.  Everything is
drawn by Windows' own GDI through ctypes, from the fonts the player's Windows already has.

Text (render_cluster, kind "system")
    A grapheme cluster is drawn with TextOutW into a 32-bit DIB section, white on black, at four
    times the size (supersampled, so the result is antialiased whatever the font's gasp table or the
    system's font smoothing says) and box-filtered down.  TextOutW goes through Uniscribe (the LPK),
    so complex scripts (Arabic, Devanagari, Thai, Hangul jamo) and combining marks are shaped.  The
    face is style.face when its cmap holds every character of the cluster, else the first of
    style.fallback_faces that does, else style.face again and GDI's own font linking.  Each face is
    sized so that its 'H' is style.cap_height pixels tall (the size is found by drawing 'H'), and
    drawn on style.baseline.  The coverage becomes alpha, quantised to style.alpha_levels; with an
    outline the coverage is dilated by a round kernel of outline_width and the outline colour is
    painted under the fill.

Emoji (render_cluster on is_emoji clusters, kind "emoji")
    Segoe UI Emoji is a COLR/CPAL colour font.  Its cmap, GSUB, COLR and CPAL tables are read from
    the installed font with GetFontData (never from a file of ours) and parsed with struct.  The
    cluster is shaped by this module's own GSUB engine (the font's ccmp feature: single, multiple,
    ligature and chaining-context lookups), because Uniscribe's ScriptShape drops the ZWJ and does
    not make ZWJ families, flags or tag flags into one glyph.  Each resulting glyph is looked up in
    the COLR version 0 base-glyph records and its layers are drawn with
    GetGlyphOutlineW(GGO_GLYPH_INDEX | GGO_GRAY8_BITMAP), tinted with CPAL palette 0 and composited
    in order (premultiplied, at four times the size, then box-filtered down).  A glyph that the
    font only colours through COLR version 1 (gradients and transforms, which this module does not
    paint) is drawn as the font's own monochrome outline in style.fill; GeneratedGlyph.colour says
    which.  Emoji are sized to style.line_height, centred on the line, and never quantised.

Marks (render_mark) are drawn alone (from their spacing forms where they have one) and placed on a
base glyph's drawn box: above marks over it, below marks under the baseline, overlays through it.

On anything but Windows, available() is False and every render function returns None.  All GDI
work is serialised by one module lock; every GDI object is freed before a call returns.
"""
from __future__ import annotations

import bisect
import ctypes
import functools
import os
import struct
import sys
import threading
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from vv_picture_image import Image

DEFAULT_FALLBACKS = ("Segoe UI", "Arial Unicode MS", "Segoe UI Symbol", "Nirmala UI", "Microsoft YaHei",
                     "Malgun Gothic", "Yu Gothic", "Ebrima", "Gadugi", "Leelawadee UI", "Microsoft Himalaya",
                     "Mongolian Baiti", "Segoe UI Historic")
EMOJI_FACE = "Segoe UI Emoji"
SUPERSAMPLE = 4
# The last steps of every chain: the open fonts the patcher bundles (assets/unicode_fonts), the same five and in
# the same order as the in-game companions' RG_BUNDLED (native/vvfp_unicode_text/runtime_glyphs.inc), so what the
# Text tool previews is what the game draws.  Loaded privately for this process (FR_PRIVATE), never installed;
# a missing file only leaves its step out.
BUNDLED_FONT_FILES = (("Noto Sans Cuneiform", "NotoSansCuneiform-Regular.otf"),
                      ("Noto Serif Tangut", "NotoSerifTangut-Regular.otf"),
                      ("Unifont", "unifont-18.0.01.otf"),
                      ("Unifont Upper", "unifont_upper-18.0.01.otf"),
                      ("Last Resort High-Efficiency", "LastResortHE-Regular.ttf"))
BUNDLED_FACES = tuple(face for face, _ in BUNDLED_FONT_FILES)
BUNDLED_FOLDER = Path(__file__).resolve().parents[1] / "assets" / "unicode_fonts"


@dataclass(frozen=True)
class GlyphStyle:
    line_height: int          # the game font's line height in px (glyph cells are this tall)
    baseline: int             # y of the baseline from the top of the line cell
    cap_height: int           # height of 'H' in px (top of H to baseline)
    x_height: int
    fill: tuple               # (r, g, b) main glyph colour (the games' sheets are white)
    outline: tuple | None     # (r, g, b) outline colour, or None when the font has no outline
    outline_width: int        # px, 0 when none
    alpha_levels: tuple | None  # the sheet's distinct alpha values (sorted) to quantise to; None = 8-bit
    face: str                 # preferred system font family, e.g. "Arial" or "Burweed ICG"
    bold: bool
    fallback_faces: tuple = DEFAULT_FALLBACKS


@dataclass
class GeneratedGlyph:
    image: Image              # RGBA, tight (an empty cluster such as a space is 0 x 0)
    left: int                 # x offset of image's left edge from the pen x
    top: int                  # y offset of image's top edge from the top of the line cell
    advance: int              # how far the pen moves (the caller adds the font's own letter spacing)
    kind: str                 # "system" (rendered from a system font) or "emoji"
    face: str                 # the system font actually used
    colour: bool = False      # True for a full-colour emoji (False: monochrome, in the fill colour)

    def copy(self) -> "GeneratedGlyph":
        return GeneratedGlyph(self.image.copy(), self.left, self.top, self.advance, self.kind, self.face,
                              self.colour)


_LOCK = threading.RLock()


# ------------------------------------------------------------------ segmentation (UAX #29, extended)

_OTHER, _CR, _LF, _CONTROL, _EXTEND, _ZWJ, _RI, _PREPEND, _SPACING, _L, _V, _T, _LV, _LVT = range(14)

_PREPEND_CPS = frozenset([0x0600, 0x0601, 0x0602, 0x0603, 0x0604, 0x0605, 0x06DD, 0x070F, 0x0890, 0x0891,
                          0x08E2, 0x0D4E, 0x110BD, 0x110CD, 0x111C2, 0x111C3])
_LINKERS = frozenset([0x094D, 0x09CD, 0x0ACD, 0x0B4D, 0x0C4D, 0x0D4D])

# Extended_Pictographic, closely enough for clustering (ZWJ sequences).
_EXT_PICT = (
    (0x00A9, 0x00A9), (0x00AE, 0x00AE), (0x203C, 0x203C), (0x2049, 0x2049), (0x2122, 0x2122),
    (0x2139, 0x2139), (0x2194, 0x2199), (0x21A9, 0x21AA), (0x231A, 0x231B), (0x2328, 0x2328),
    (0x2388, 0x2388), (0x23CF, 0x23CF), (0x23E9, 0x23F3), (0x23F8, 0x23FA), (0x24C2, 0x24C2),
    (0x25AA, 0x25AB), (0x25B6, 0x25B6), (0x25C0, 0x25C0), (0x25FB, 0x25FE), (0x2600, 0x2605),
    (0x2607, 0x2612), (0x2614, 0x2685), (0x2690, 0x2705), (0x2708, 0x2712), (0x2714, 0x2714),
    (0x2716, 0x2716), (0x271D, 0x271D), (0x2721, 0x2721), (0x2728, 0x2728), (0x2733, 0x2734),
    (0x2744, 0x2744), (0x2747, 0x2747), (0x274C, 0x274C), (0x274E, 0x274E), (0x2753, 0x2755),
    (0x2757, 0x2757), (0x2763, 0x2767), (0x2795, 0x2797), (0x27A1, 0x27A1), (0x27B0, 0x27B0),
    (0x27BF, 0x27BF), (0x2934, 0x2935), (0x2B05, 0x2B07), (0x2B1B, 0x2B1C), (0x2B50, 0x2B50),
    (0x2B55, 0x2B55), (0x3030, 0x3030), (0x303D, 0x303D), (0x3297, 0x3297), (0x3299, 0x3299),
    (0x1F000, 0x1F0FF), (0x1F10D, 0x1F10F), (0x1F12F, 0x1F12F), (0x1F16C, 0x1F171), (0x1F17E, 0x1F17F),
    (0x1F18E, 0x1F18E), (0x1F191, 0x1F19A), (0x1F1AD, 0x1F1E5), (0x1F201, 0x1F20F), (0x1F21A, 0x1F21A),
    (0x1F22F, 0x1F22F), (0x1F232, 0x1F23A), (0x1F23C, 0x1F23F), (0x1F249, 0x1F3FA), (0x1F400, 0x1F53D),
    (0x1F546, 0x1F64F), (0x1F680, 0x1F6FF), (0x1F774, 0x1F77F), (0x1F7D5, 0x1F7FF), (0x1F80C, 0x1F80F),
    (0x1F848, 0x1F84F), (0x1F85A, 0x1F85F), (0x1F888, 0x1F88F), (0x1F8AE, 0x1F8FF), (0x1F90C, 0x1F93A),
    (0x1F93C, 0x1F945), (0x1F947, 0x1FAFF), (0x1FC00, 0x1FFFD),
)

# Emoji_Presentation=Yes: shown as emoji with no FE0F.
_EMOJI_PRESENTATION = (
    (0x231A, 0x231B), (0x23E9, 0x23EC), (0x23F0, 0x23F0), (0x23F3, 0x23F3), (0x25FD, 0x25FE),
    (0x2614, 0x2615), (0x2648, 0x2653), (0x267F, 0x267F), (0x2693, 0x2693), (0x26A1, 0x26A1),
    (0x26AA, 0x26AB), (0x26BD, 0x26BE), (0x26C4, 0x26C5), (0x26CE, 0x26CE), (0x26D4, 0x26D4),
    (0x26EA, 0x26EA), (0x26F2, 0x26F3), (0x26F5, 0x26F5), (0x26FA, 0x26FA), (0x26FD, 0x26FD),
    (0x2705, 0x2705), (0x270A, 0x270B), (0x2728, 0x2728), (0x274C, 0x274C), (0x274E, 0x274E),
    (0x2753, 0x2755), (0x2757, 0x2757), (0x2795, 0x2797), (0x27B0, 0x27B0), (0x27BF, 0x27BF),
    (0x2B1B, 0x2B1C), (0x2B50, 0x2B50), (0x2B55, 0x2B55),
    (0x1F004, 0x1F004), (0x1F0CF, 0x1F0CF), (0x1F18E, 0x1F18E), (0x1F191, 0x1F19A), (0x1F1E6, 0x1F1FF),
    (0x1F201, 0x1F201), (0x1F21A, 0x1F21A), (0x1F22F, 0x1F22F), (0x1F232, 0x1F236), (0x1F238, 0x1F23A),
    (0x1F250, 0x1F251), (0x1F300, 0x1F320), (0x1F32D, 0x1F335), (0x1F337, 0x1F37C), (0x1F37E, 0x1F393),
    (0x1F3A0, 0x1F3CA), (0x1F3CF, 0x1F3D3), (0x1F3E0, 0x1F3F0), (0x1F3F4, 0x1F3F4), (0x1F3F8, 0x1F43E),
    (0x1F440, 0x1F440), (0x1F442, 0x1F4FC), (0x1F4FF, 0x1F53D), (0x1F54B, 0x1F54E), (0x1F550, 0x1F567),
    (0x1F57A, 0x1F57A), (0x1F595, 0x1F596), (0x1F5A4, 0x1F5A4), (0x1F5FB, 0x1F64F), (0x1F680, 0x1F6C5),
    (0x1F6CC, 0x1F6CC), (0x1F6D0, 0x1F6D2), (0x1F6D5, 0x1F6D7), (0x1F6DC, 0x1F6DF), (0x1F6EB, 0x1F6EC),
    (0x1F6F4, 0x1F6FC), (0x1F7E0, 0x1F7EB), (0x1F7F0, 0x1F7F0), (0x1F90C, 0x1F93A), (0x1F93C, 0x1F945),
    (0x1F947, 0x1F9FF), (0x1FA70, 0x1FA7C), (0x1FA80, 0x1FA89), (0x1FA8F, 0x1FAC6), (0x1FACE, 0x1FADC),
    (0x1FADF, 0x1FAE9), (0x1FAF0, 0x1FAF8),
)
_EXT_PICT_STARTS = [a for a, _ in _EXT_PICT]
_EMOJI_PRES_STARTS = [a for a, _ in _EMOJI_PRESENTATION]
_KEYCAP_BASES = frozenset(map(ord, "0123456789#*"))


def _in_ranges(cp: int, ranges, starts) -> bool:
    i = bisect.bisect_right(starts, cp) - 1
    return i >= 0 and ranges[i][0] <= cp <= ranges[i][1]


def _ext_pict(cp: int) -> bool:
    return _in_ranges(cp, _EXT_PICT, _EXT_PICT_STARTS)


def _gcb(cp: int) -> int:
    if cp == 0x0D:
        return _CR
    if cp == 0x0A:
        return _LF
    if cp == 0x200D:
        return _ZWJ
    if 0x1F1E6 <= cp <= 0x1F1FF:
        return _RI
    if 0x1F3FB <= cp <= 0x1F3FF or 0xE0020 <= cp <= 0xE007F or cp == 0x200C:
        return _EXTEND
    if 0x1100 <= cp <= 0x115F or 0xA960 <= cp <= 0xA97C:
        return _L
    if 0x1160 <= cp <= 0x11A7 or 0xD7B0 <= cp <= 0xD7C6:
        return _V
    if 0x11A8 <= cp <= 0x11FF or 0xD7CB <= cp <= 0xD7FB:
        return _T
    if 0xAC00 <= cp <= 0xD7A3:
        return _LV if (cp - 0xAC00) % 28 == 0 else _LVT
    if cp in _PREPEND_CPS:
        return _PREPEND
    cat = unicodedata.category(chr(cp))
    if cat in ("Mn", "Me"):
        return _EXTEND
    if cat == "Mc" or cp in (0x0E33, 0x0EB3):
        return _SPACING
    if cat in ("Cc", "Zl", "Zp", "Cf"):
        return _CONTROL
    return _OTHER


def segment(text: str) -> list[str]:
    """The extended grapheme clusters of `text` (UAX #29 rules GB3-GB13, with GB9c's Indic conjuncts)."""
    out: list[str] = []
    cur: list[str] = []
    prev = None
    ri_run = 0
    pict = None          # None, "pict" (ExtPict Extend*), "zwj" (... ZWJ)
    linker = None        # the block of a virama that may join the next consonant
    for ch in text:
        cp = ord(ch)
        p = _gcb(cp)
        join = False
        if cur:
            if prev == _CR and p == _LF:
                join = True
            elif prev in (_CR, _LF, _CONTROL) or p in (_CR, _LF, _CONTROL):
                join = False
            elif prev == _L and p in (_L, _V, _LV, _LVT):
                join = True
            elif prev in (_LV, _V) and p in (_V, _T):
                join = True
            elif prev in (_LVT, _T) and p == _T:
                join = True
            elif p in (_EXTEND, _ZWJ, _SPACING):
                join = True
            elif prev == _PREPEND:
                join = True
            elif linker is not None and (cp & ~0x7F) == linker and unicodedata.category(ch) == "Lo":
                join = True
            elif pict == "zwj" and prev == _ZWJ and _ext_pict(cp):
                join = True
            elif prev == _RI and p == _RI and ri_run % 2 == 1:
                join = True
        if not join and cur:
            out.append("".join(cur))
            cur = []
        cur.append(ch)
        ri_run = ri_run + 1 if p == _RI else 0
        if _ext_pict(cp):
            pict = "pict"
        elif pict == "pict" and p == _EXTEND:
            pass
        elif pict == "pict" and p == _ZWJ:
            pict = "zwj"
        else:
            pict = None
        if cp in _LINKERS:
            linker = cp & ~0x7F
        elif linker is not None and p in (_EXTEND, _ZWJ):
            pass
        else:
            linker = None
        prev = p
    if cur:
        out.append("".join(cur))
    return out


def is_emoji(cluster: str) -> bool:
    """True when the cluster is shown as a colour emoji (by Unicode's emoji presentation rules)."""
    cps = [ord(c) for c in cluster]
    if not cps or 0xFE0E in cps:
        return False
    first = cps[0]
    if any(0x1F1E6 <= c <= 0x1F1FF for c in cps):
        return True
    if first in _KEYCAP_BASES:
        return 0x20E3 in cps and 0xFE0F in cps
    if any(0x1F3FB <= c <= 0x1F3FF for c in cps) and (_ext_pict(first) or len(cps) == 1):
        return True
    if first == 0x1F3F4 and any(0xE0020 <= c <= 0xE007F for c in cps):
        return True
    if 0xFE0F in cps and _ext_pict(first):
        return True
    if 0x200D in cps and sum(1 for c in cps if _ext_pict(c)) >= 2:
        return True
    return _in_ranges(first, _EMOJI_PRESENTATION, _EMOJI_PRES_STARTS)


# Characters that draw nothing and need no glyph of their own in a face.
def _ignorable(cp: int) -> bool:
    return (cp in (0x200B, 0x200C, 0x200D, 0x200E, 0x200F, 0x00AD, 0x034F, 0xFEFF)
            or 0xFE00 <= cp <= 0xFE0F or 0xE0100 <= cp <= 0xE01EF or 0x2060 <= cp <= 0x2064
            or 0x180B <= cp <= 0x180F)


# ------------------------------------------------------------------ OpenType tables (struct)


class _Cmap:
    """A font's best Unicode cmap subtable (format 12 or 4)."""

    def __init__(self, data: bytes) -> None:
        self.groups: list[tuple[int, int, int]] = []       # format 12: (start, end, first glyph)
        self.starts: list[int] = []
        self.fmt4 = None
        self.many_to_one = False
        n = struct.unpack_from(">H", data, 2)[0]
        subs = {}
        for i in range(n):
            plat, enc, off = struct.unpack_from(">HHI", data, 4 + 8 * i)
            subs[(plat, enc)] = off
        for key in ((3, 10), (0, 6), (0, 4), (3, 1), (0, 3), (0, 2), (0, 1), (0, 0), (3, 0)):
            off = subs.get(key)
            if off is None:
                continue
            fmt = struct.unpack_from(">H", data, off)[0]
            if fmt not in (4, 12, 13):
                continue
            if fmt in (12, 13):
                count = struct.unpack_from(">I", data, off + 12)[0]
                self.groups = [struct.unpack_from(">III", data, off + 16 + 12 * k) for k in range(count)]
                self.starts = [g[0] for g in self.groups]
                self.many_to_one = fmt == 13       # format 13: every code point of a group has the one glyph
                return
            if fmt == 4:
                seg2 = struct.unpack_from(">H", data, off + 6)[0]
                segs = seg2 // 2
                ends = struct.unpack_from(f">{segs}H", data, off + 14)
                starts = struct.unpack_from(f">{segs}H", data, off + 16 + seg2)
                deltas = struct.unpack_from(f">{segs}h", data, off + 16 + 2 * seg2)
                ro_at = off + 16 + 3 * seg2
                ros = struct.unpack_from(f">{segs}H", data, ro_at)
                self.fmt4 = (data, ends, starts, deltas, ros, ro_at)
                self.symbol = key == (3, 0)
                return

    def glyph(self, cp: int) -> int:
        if self.groups:
            i = bisect.bisect_right(self.starts, cp) - 1
            if i >= 0:
                s, e, g = self.groups[i]
                if cp <= e:
                    return g if self.many_to_one else g + cp - s
            return 0
        if self.fmt4 is None:
            return 0
        data, ends, starts, deltas, ros, ro_at = self.fmt4
        if self.symbol and cp < 0x100:
            cp += 0xF000
        if cp > 0xFFFF:
            return 0
        i = bisect.bisect_left(ends, cp)
        if i >= len(ends) or cp < starts[i]:
            return 0
        if ros[i] == 0:
            return (cp + deltas[i]) & 0xFFFF
        at = ro_at + 2 * i + ros[i] + 2 * (cp - starts[i])
        if at + 2 > len(data):
            return 0
        g = struct.unpack_from(">H", data, at)[0]
        return (g + deltas[i]) & 0xFFFF if g else 0


class _Layout:
    """What GSUB and GPOS share: the script/feature/lookup lists, coverage and class tables, and
    (chaining) context matching.  Lookup flags are taken as 0 (no glyph skipping), which is what the
    emoji font's lookups use."""

    EXTENSION = 7

    def __init__(self, data: bytes) -> None:
        self.d = data
        _maj, _min, self.sl, self.fl, self.ll = struct.unpack_from(">HHHHH", data, 0)
        self._cov: dict[int, dict] = {}
        self._cls: dict[int, dict] = {}
        self._lookups: dict[int, tuple] = {}

    def feature_lookups(self, tags) -> list[int]:
        d = self.d
        S = self.sl
        scripts = {}
        for i in range(struct.unpack_from(">H", d, S)[0]):
            tag, off = struct.unpack_from(">4sH", d, S + 2 + 6 * i)
            scripts[tag] = S + off
        so = scripts.get(b"DFLT") or scripts.get(b"latn") or next(iter(scripts.values()), None)
        if so is None:
            return []
        dl = struct.unpack_from(">H", d, so)[0]
        if not dl:
            return []
        lo = so + dl
        _ro, req, nf = struct.unpack_from(">HHH", d, lo)
        idx = list(struct.unpack_from(f">{nf}H", d, lo + 6))
        if req != 0xFFFF:
            idx.append(req)
        F = self.fl
        lookups = set()
        for fi in idx:
            tag, off = struct.unpack_from(">4sH", d, F + 2 + 6 * fi)
            if tag in tags:
                fo = F + off
                n = struct.unpack_from(">H", d, fo + 2)[0]
                lookups.update(struct.unpack_from(f">{n}H", d, fo + 4))
        return sorted(lookups)

    def _lookup(self, li: int) -> tuple:
        got = self._lookups.get(li)
        if got is None:
            d = self.d
            lo = self.ll + struct.unpack_from(">H", d, self.ll + 2 + 2 * li)[0]
            kind, _flag, n = struct.unpack_from(">HHH", d, lo)
            subs = []
            for k in range(n):
                so = lo + struct.unpack_from(">H", d, lo + 6 + 2 * k)[0]
                t = kind
                if kind == self.EXTENSION:
                    _fmt, t, eo = struct.unpack_from(">HHI", d, so)
                    so += eo
                subs.append((t, so))
            got = self._lookups[li] = tuple(subs)
        return got

    def _coverage(self, off: int) -> dict:
        got = self._cov.get(off)
        if got is None:
            d = self.d
            fmt, n = struct.unpack_from(">HH", d, off)
            got = {}
            if fmt == 1:
                for k, g in enumerate(struct.unpack_from(f">{n}H", d, off + 4)):
                    got[g] = k
            else:
                for k in range(n):
                    s, e, c = struct.unpack_from(">HHH", d, off + 4 + 6 * k)
                    for g in range(s, e + 1):
                        got[g] = c + g - s
            self._cov[off] = got
        return got

    def _classes(self, off: int) -> dict:
        got = self._cls.get(off)
        if got is None:
            got = _class_def(self.d, off)
            self._cls[off] = got
        return got

    def _context(self, kind_chain: bool, fmt: int, so: int, glyphs: list[int], i: int):
        """Match a (chaining) context subtable at glyphs[i]: (input length, [(seq index, lookup)]) or None."""
        d = self.d
        if fmt == 3:
            at = so + 2
            back = ahead = ()
            if kind_chain:
                nb = struct.unpack_from(">H", d, at)[0]
                back = struct.unpack_from(f">{nb}H", d, at + 2)
                at += 2 + 2 * nb
                ni = struct.unpack_from(">H", d, at)[0]
                inp = struct.unpack_from(f">{ni}H", d, at + 2)
                at += 2 + 2 * ni
                na = struct.unpack_from(">H", d, at)[0]
                ahead = struct.unpack_from(f">{na}H", d, at + 2)
                at += 2 + 2 * na
                nr = struct.unpack_from(">H", d, at)[0]
                at += 2
            else:
                ni, nr = struct.unpack_from(">HH", d, at)
                inp = struct.unpack_from(f">{ni}H", d, at + 4)
                at += 4 + 2 * ni
            if i - len(back) < 0 or i + ni + len(ahead) > len(glyphs):
                return None
            for k, c in enumerate(back):
                if glyphs[i - 1 - k] not in self._coverage(so + c):
                    return None
            for k, c in enumerate(inp):
                if glyphs[i + k] not in self._coverage(so + c):
                    return None
            for k, c in enumerate(ahead):
                if glyphs[i + ni + k] not in self._coverage(so + c):
                    return None
            return ni, [struct.unpack_from(">HH", d, at + 4 * r) for r in range(nr)]
        if fmt in (1, 2) and kind_chain:
            cov = self._coverage(so + struct.unpack_from(">H", d, so + 2)[0])
            if glyphs[i] not in cov:
                return None
            if fmt == 1:
                n = struct.unpack_from(">H", d, so + 4)[0]
                if cov[glyphs[i]] >= n:
                    return None
                sets_at = so + struct.unpack_from(">H", d, so + 6 + 2 * cov[glyphs[i]])[0]
                same = _Same()
                maps = (same, same, same)
            else:
                bo, io, lo_, n = struct.unpack_from(">HHHH", d, so + 4)
                maps = (self._classes(so + bo), self._classes(so + io), self._classes(so + lo_))
                c = maps[1].get(glyphs[i], 0)
                if c >= n:
                    return None
                off = struct.unpack_from(">H", d, so + 12 + 2 * c)[0]
                if not off:
                    return None
                sets_at = so + off
            for r in range(struct.unpack_from(">H", d, sets_at)[0]):
                at = sets_at + struct.unpack_from(">H", d, sets_at + 2 + 2 * r)[0]
                nb = struct.unpack_from(">H", d, at)[0]
                back = struct.unpack_from(f">{nb}H", d, at + 2)
                at += 2 + 2 * nb
                ni = struct.unpack_from(">H", d, at)[0]
                inp = struct.unpack_from(f">{max(0, ni - 1)}H", d, at + 2)
                at += 2 + 2 * max(0, ni - 1)
                na = struct.unpack_from(">H", d, at)[0]
                ahead = struct.unpack_from(f">{na}H", d, at + 2)
                at += 2 + 2 * na
                nr = struct.unpack_from(">H", d, at)[0]
                if i - nb < 0 or i + ni + na > len(glyphs):
                    continue
                if any(maps[0].get(glyphs[i - 1 - k], 0) != v for k, v in enumerate(back)):
                    continue
                if any(maps[1].get(glyphs[i + 1 + k], 0) != v for k, v in enumerate(inp)):
                    continue
                if any(maps[2].get(glyphs[i + ni + k], 0) != v for k, v in enumerate(ahead)):
                    continue
                return ni, [struct.unpack_from(">HH", d, at + 2 + 4 * k) for k in range(nr)]
        return None


class _Same:
    """A class map that gives every glyph itself (chaining context format 1 compares glyph ids)."""

    @staticmethod
    def get(g, _default=0):
        return g


def _class_def(d: bytes, off: int) -> dict:
    fmt = struct.unpack_from(">H", d, off)[0]
    got = {}
    if fmt == 1:
        start, n = struct.unpack_from(">HH", d, off + 2)
        for k, c in enumerate(struct.unpack_from(f">{n}H", d, off + 6)):
            got[start + k] = c
    elif fmt == 2:
        n = struct.unpack_from(">H", d, off + 2)[0]
        for k in range(n):
            s, e, c = struct.unpack_from(">HHH", d, off + 4 + 6 * k)
            for g in range(s, e + 1):
                got[g] = c
    return got


class _Gsub(_Layout):
    """Glyph substitution: lookup types 1, 2, 4, 5 (format 3), 6 (formats 1-3) and 7, applied in
    lookup-list order (the emoji font's ccmp)."""

    EXTENSION = 7

    def apply(self, glyphs: list[int], lookups) -> list[int]:
        for li in lookups:
            i = 0
            while i < len(glyphs):
                hit = self._apply_at(li, glyphs, i)
                if hit is None:
                    i += 1
                else:
                    glyphs, i = hit
        return glyphs

    def _apply_at(self, li: int, glyphs: list[int], i: int, depth: int = 0):
        if depth > 8:
            return None
        for kind, so in self._lookup(li):
            hit = self._sub(kind, so, glyphs, i, depth)
            if hit is not None:
                return hit
        return None

    def _sub(self, kind: int, so: int, glyphs: list[int], i: int, depth: int):
        d = self.d
        fmt = struct.unpack_from(">H", d, so)[0]
        g = glyphs[i]
        if kind == 1:
            cov = self._coverage(so + struct.unpack_from(">H", d, so + 2)[0])
            if g not in cov:
                return None
            if fmt == 1:
                new = (g + struct.unpack_from(">h", d, so + 4)[0]) & 0xFFFF
            else:
                new = struct.unpack_from(">H", d, so + 6 + 2 * cov[g])[0]
            return glyphs[:i] + [new] + glyphs[i + 1:], i + 1
        if kind == 2:
            cov = self._coverage(so + struct.unpack_from(">H", d, so + 2)[0])
            if g not in cov:
                return None
            seq = so + struct.unpack_from(">H", d, so + 6 + 2 * cov[g])[0]
            n = struct.unpack_from(">H", d, seq)[0]
            new = list(struct.unpack_from(f">{n}H", d, seq + 2))
            return glyphs[:i] + new + glyphs[i + 1:], i + max(1, n)
        if kind == 4:
            cov = self._coverage(so + struct.unpack_from(">H", d, so + 2)[0])
            if g not in cov:
                return None
            ls = so + struct.unpack_from(">H", d, so + 6 + 2 * cov[g])[0]
            for k in range(struct.unpack_from(">H", d, ls)[0]):
                lig = ls + struct.unpack_from(">H", d, ls + 2 + 2 * k)[0]
                lg, cc = struct.unpack_from(">HH", d, lig)
                comps = list(struct.unpack_from(f">{cc - 1}H", d, lig + 4)) if cc > 1 else []
                if glyphs[i + 1:i + cc] == comps:
                    return glyphs[:i] + [lg] + glyphs[i + cc:], i + 1
            return None
        if kind in (5, 6):
            m = self._context(kind == 6, fmt, so, glyphs, i)
            if m is None:
                return None
            n_in, recs = m
            glyphs = list(glyphs)
            end = i + n_in
            for seq, li in recs:
                pos = i + seq
                if pos >= end or pos >= len(glyphs):
                    continue
                before = len(glyphs)
                hit = self._apply_at(li, glyphs, pos, depth + 1)
                if hit is not None:
                    glyphs = hit[0]
                    end += len(glyphs) - before
            return glyphs, max(i + 1, end)
        return None


class _Gpos(_Layout):
    """Glyph positioning: single (1), pair (2), mark-to-base (4), mark-to-mark (6), chaining context
    (8) and extension (9) lookups.  Positions are font units: per glyph [x offset, y offset (up),
    x advance]."""

    EXTENSION = 9

    def __init__(self, data: bytes, mark_glyphs: set) -> None:
        super().__init__(data)
        self.marks = mark_glyphs

    def apply(self, glyphs: list[int], pos: list[list[int]], lookups) -> None:
        for li in lookups:
            i = 0
            while i < len(glyphs):
                i += self._apply_at(li, glyphs, pos, i, 0) or 1

    def _apply_at(self, li, glyphs, pos, i, depth) -> int:
        """Apply lookup li at glyph i; how many glyphs it consumed (0: no match)."""
        if depth > 8:
            return 0
        for kind, so in self._lookup(li):
            n = self._pos(kind, so, glyphs, pos, i, depth)
            if n:
                return n
        return 0

    def _value(self, at: int, fmt: int):
        """(x placement, y placement, x advance, size) of a value record."""
        d = self.d
        vals = [0, 0, 0, 0]
        k = 0
        for bit in range(8):
            if fmt & (1 << bit):
                if bit < 4:
                    vals[bit] = struct.unpack_from(">h", d, at + 2 * k)[0]
                k += 1
        return vals[0], vals[1], vals[2], 2 * k

    def _anchor(self, at: int):
        return struct.unpack_from(">hh", self.d, at + 2)

    def _add(self, p, v) -> None:
        p[0] += v[0]
        p[1] += v[1]
        p[2] += v[2]

    def _pos(self, kind, so, glyphs, pos, i, depth) -> int:
        d = self.d
        fmt = struct.unpack_from(">H", d, so)[0]
        g = glyphs[i]
        if kind == 1:
            cov = self._coverage(so + struct.unpack_from(">H", d, so + 2)[0])
            if g not in cov:
                return 0
            vf = struct.unpack_from(">H", d, so + 4)[0]
            if fmt == 1:
                v = self._value(so + 6, vf)
            else:
                size = self._value(so + 8, vf)[3]
                v = self._value(so + 8 + size * cov[g], vf)
            self._add(pos[i], v)
            return 1
        if kind == 2:
            if i + 1 >= len(glyphs):
                return 0
            cov = self._coverage(so + struct.unpack_from(">H", d, so + 2)[0])
            if g not in cov:
                return 0
            vf1, vf2 = struct.unpack_from(">HH", d, so + 4)
            s1, s2 = self._value(0, vf1)[3], self._value(0, vf2)[3]
            g2 = glyphs[i + 1]
            if fmt == 1:
                ps = so + struct.unpack_from(">H", d, so + 10 + 2 * cov[g])[0]
                for r in range(struct.unpack_from(">H", d, ps)[0]):
                    at = ps + 2 + r * (2 + s1 + s2)
                    if struct.unpack_from(">H", d, at)[0] == g2:
                        self._add(pos[i], self._value(at + 2, vf1))
                        self._add(pos[i + 1], self._value(at + 2 + s1, vf2))
                        return 1
                return 0
            c1o, c2o, n1, n2 = struct.unpack_from(">HHHH", d, so + 8)
            c1, c2 = self._classes(so + c1o).get(g, 0), self._classes(so + c2o).get(g2, 0)
            if c1 >= n1 or c2 >= n2:
                return 0
            at = so + 16 + (c1 * n2 + c2) * (s1 + s2)
            self._add(pos[i], self._value(at, vf1))
            self._add(pos[i + 1], self._value(at + s1, vf2))
            return 1
        if kind in (4, 6):
            mcov_o, bcov_o, ncls, marr_o, barr_o = struct.unpack_from(">HHHHH", d, so + 2)
            mcov = self._coverage(so + mcov_o)
            if g not in mcov or i == 0:
                return 0
            if kind == 4:
                b = i - 1
                while b >= 0 and glyphs[b] in self.marks:
                    b -= 1
            else:
                b = i - 1
            if b < 0:
                return 0
            bcov = self._coverage(so + bcov_o)
            if glyphs[b] not in bcov:
                return 0
            marr = so + marr_o
            cls, ma_o = struct.unpack_from(">HH", d, marr + 2 + 4 * mcov[g])
            barr = so + barr_o
            ba_o = struct.unpack_from(">H", d, barr + 2 + 2 * (bcov[glyphs[b]] * ncls + cls))[0]
            if not ba_o:
                return 0
            mx, my = self._anchor(marr + ma_o)
            bx, by = self._anchor(barr + ba_o)
            pen = sum(pos[k][2] for k in range(b, i))
            pos[i][0] = pos[b][0] + bx - mx - pen
            pos[i][1] = pos[b][1] + by - my
            return 1
        if kind in (7, 8):
            m = self._context(kind == 8, fmt, so, glyphs, i)
            if m is None:
                return 0
            n_in, recs = m
            for seq, li in recs:
                if i + seq < len(glyphs):
                    self._apply_at(li, glyphs, pos, i + seq, depth + 1)
            return max(1, n_in)
        return 0


class _Colr:
    """COLR version 0 base glyphs and their layers, CPAL palette 0, and the version 1 base glyphs."""

    def __init__(self, colr: bytes, cpal: bytes) -> None:
        ver, nb, bo, lo, _nl = struct.unpack_from(">HHIIH", colr, 0)
        self.base: dict[int, tuple] = {}
        for k in range(nb):
            gid, first, n = struct.unpack_from(">HHH", colr, bo + 6 * k)
            self.base[gid] = tuple(struct.unpack_from(">HH", colr, lo + 4 * (first + j)) for j in range(n))
        self.v1: set[int] = set()
        if ver >= 1:
            bgl = struct.unpack_from(">I", colr, 14)[0]
            if bgl:
                n = struct.unpack_from(">I", colr, bgl)[0]
                self.v1 = {struct.unpack_from(">H", colr, bgl + 4 + 6 * k)[0] for k in range(n)}
        _v, n_entries, _np, _nrec, rec_off = struct.unpack_from(">HHHHI", cpal, 0)
        first = struct.unpack_from(">H", cpal, 12)[0]
        self.palette = []
        for k in range(n_entries):
            b, g, r, a = struct.unpack_from(">BBBB", cpal, rec_off + 4 * (first + k))
            self.palette.append((r, g, b, a))


# ------------------------------------------------------------------ Windows GDI through ctypes


class _Api:
    pass


_API: list = []


def _api():
    """The GDI functions, bound once; None on anything but a working Windows."""
    if _API:
        return _API[0]
    api = None
    if sys.platform == "win32":
        try:
            api = _bind()
        except (OSError, AttributeError):
            api = None
    _API.append(api)
    if api is not None:
        _load_bundled_fonts(api)
    return api


def _load_bundled_fonts(a) -> int:
    """Add the bundled open fonts to this process (private: never installed in Windows).  Fails open."""
    added = 0
    for _face, name in BUNDLED_FONT_FILES:
        path = BUNDLED_FOLDER / name
        try:
            if path.is_file() and a.AddFontResourceExW(str(path), 0x10, None) > 0:      # FR_PRIVATE
                added += 1
        except (OSError, AttributeError, ValueError):
            continue
    return added


def _bind() -> _Api:
    from ctypes import wintypes as W
    a = _Api()
    gdi = ctypes.WinDLL("gdi32", use_last_error=True)
    vp, i, u = ctypes.c_void_p, ctypes.c_int, ctypes.c_uint

    class BITMAPINFOHEADER(ctypes.Structure):
        _fields_ = [("biSize", W.DWORD), ("biWidth", W.LONG), ("biHeight", W.LONG), ("biPlanes", W.WORD),
                    ("biBitCount", W.WORD), ("biCompression", W.DWORD), ("biSizeImage", W.DWORD),
                    ("biXPelsPerMeter", W.LONG), ("biYPelsPerMeter", W.LONG), ("biClrUsed", W.DWORD),
                    ("biClrImportant", W.DWORD)]

    class TEXTMETRICW(ctypes.Structure):
        _fields_ = [("tmHeight", W.LONG), ("tmAscent", W.LONG), ("tmDescent", W.LONG),
                    ("tmInternalLeading", W.LONG), ("tmExternalLeading", W.LONG), ("tmAveCharWidth", W.LONG),
                    ("tmMaxCharWidth", W.LONG), ("tmWeight", W.LONG), ("tmOverhang", W.LONG),
                    ("tmDigitizedAspectX", W.LONG), ("tmDigitizedAspectY", W.LONG), ("tmFirstChar", W.WCHAR),
                    ("tmLastChar", W.WCHAR), ("tmDefaultChar", W.WCHAR), ("tmBreakChar", W.WCHAR),
                    ("tmItalic", W.BYTE), ("tmUnderlined", W.BYTE), ("tmStruckOut", W.BYTE),
                    ("tmPitchAndFamily", W.BYTE), ("tmCharSet", W.BYTE)]

    class GLYPHMETRICS(ctypes.Structure):
        _fields_ = [("gmBlackBoxX", W.UINT), ("gmBlackBoxY", W.UINT), ("gmptGlyphOrigin", W.POINT),
                    ("gmCellIncX", ctypes.c_short), ("gmCellIncY", ctypes.c_short)]

    class FIXED(ctypes.Structure):
        _fields_ = [("fract", W.WORD), ("value", ctypes.c_short)]

    class MAT2(ctypes.Structure):
        _fields_ = [("eM11", FIXED), ("eM12", FIXED), ("eM21", FIXED), ("eM22", FIXED)]

    a.BITMAPINFOHEADER, a.TEXTMETRICW, a.GLYPHMETRICS = BITMAPINFOHEADER, TEXTMETRICW, GLYPHMETRICS
    a.IDENTITY = MAT2(FIXED(0, 1), FIXED(0, 0), FIXED(0, 0), FIXED(0, 1))

    def fn(name, res, *args):
        f = getattr(gdi, name)
        f.restype, f.argtypes = res, list(args)
        setattr(a, name, f)

    fn("CreateCompatibleDC", vp, vp)
    fn("DeleteDC", W.BOOL, vp)
    fn("CreateFontW", vp, i, i, i, i, i, W.DWORD, W.DWORD, W.DWORD, W.DWORD, W.DWORD, W.DWORD, W.DWORD,
       W.DWORD, W.LPCWSTR)
    fn("SelectObject", vp, vp, vp)
    fn("DeleteObject", W.BOOL, vp)
    fn("CreateDIBSection", vp, vp, vp, u, ctypes.POINTER(vp), vp, W.DWORD)
    fn("SetTextColor", W.DWORD, vp, W.DWORD)
    fn("SetBkMode", i, vp, i)
    fn("SetTextAlign", u, vp, u)
    fn("TextOutW", W.BOOL, vp, i, i, W.LPCWSTR, i)
    fn("GdiFlush", W.BOOL)
    fn("GetTextMetricsW", W.BOOL, vp, ctypes.POINTER(TEXTMETRICW))
    fn("GetTextExtentPoint32W", W.BOOL, vp, W.LPCWSTR, i, ctypes.POINTER(W.SIZE))
    fn("GetTextFaceW", i, vp, i, W.LPWSTR)
    fn("GetFontData", W.DWORD, vp, W.DWORD, W.DWORD, vp, W.DWORD)
    fn("GetGlyphOutlineW", W.DWORD, vp, u, u, ctypes.POINTER(GLYPHMETRICS), W.DWORD, vp, ctypes.POINTER(MAT2))
    fn("AddFontResourceExW", i, W.LPCWSTR, W.DWORD, vp)
    a.dc = a.CreateCompatibleDC(None)
    if not a.dc:
        raise OSError("no memory DC")
    a.W = W
    return a


GDI_ERROR = 0xFFFFFFFF
GGO_METRICS, GGO_GRAY8_BITMAP, GGO_GLYPH_INDEX = 0, 6, 0x80
ANTIALIASED_QUALITY = 4
TA_BASELINE = 24


def available() -> bool:
    """True where glyphs can be made (Windows with GDI)."""
    with _LOCK:
        return _api() is not None


class _Font:
    """A GDI font selected into the module's DC for the duration of a with-block."""

    def __init__(self, face: str, em: int, bold: bool) -> None:
        self.face, self.em, self.bold = face, max(1, int(em)), bold

    def __enter__(self):
        a = _api()
        self.a = a
        self.font = a.CreateFontW(-self.em, 0, 0, 0, 700 if self.bold else 400, 0, 0, 0, 1, 8, 0,
                                  ANTIALIASED_QUALITY, 0, self.face)
        if not self.font:
            raise OSError("CreateFontW failed")
        self.old = a.SelectObject(a.dc, self.font)
        return a

    def __exit__(self, *exc):
        self.a.SelectObject(self.a.dc, self.old)
        self.a.DeleteObject(self.font)
        return False


def _table(a, tag: bytes) -> bytes | None:
    key = struct.unpack("<I", tag)[0]
    n = a.GetFontData(a.dc, key, 0, None, 0)
    if n in (GDI_ERROR, 0):
        return None
    buf = ctypes.create_string_buffer(n)
    if a.GetFontData(a.dc, key, 0, buf, n) != n:
        return None
    return buf.raw


def _metrics(a):
    tm = a.TEXTMETRICW()
    a.GetTextMetricsW(a.dc, ctypes.byref(tm))
    return tm


REF_EM = 256


@functools.lru_cache(maxsize=64)
def _face_info(face: str, bold: bool):
    """(actual face name, cmap, cap ratio, x ratio, ascent ratio) of an installed face, or None."""
    a = _api()
    if a is None or not face:
        return None
    with _Font(face, REF_EM, bold):
        buf = ctypes.create_unicode_buffer(128)
        a.GetTextFaceW(a.dc, 128, buf)
        if buf.value.casefold() != face.casefold():
            return None
        data = _table(a, b"cmap")
        cmap = _Cmap(data) if data else None
        tm = _metrics(a)
        ratios = []
        for ch in "Hx":
            r = None
            if cmap is not None and cmap.glyph(ord(ch)):
                gm = a.GLYPHMETRICS()
                if a.GetGlyphOutlineW(a.dc, ord(ch), GGO_METRICS, ctypes.byref(gm), 0, None,
                                      ctypes.byref(a.IDENTITY)) != GDI_ERROR:
                    r = gm.gmptGlyphOrigin.y / REF_EM
            ratios.append(r)
    return buf.value, cmap, ratios[0], ratios[1], tm.tmAscent / REF_EM


def font_installed(face: str) -> bool:
    """True when `face` (a family name such as "Burweed ICG") can be drawn.  A font that is only in the
    per-user fonts folder (%LOCALAPPDATA%\\Microsoft\\Windows\\Fonts) and not yet known to GDI is
    loaded privately for this process."""
    with _LOCK:
        if _api() is None or not face:
            return False
        if _face_info(face, False) is not None:
            return True
        if _load_user_font(face):
            _face_info.cache_clear()
            return _face_info(face, False) is not None
        return False


def _font_names(path: Path) -> set[str]:
    try:
        data = path.read_bytes()
    except OSError:
        return set()
    offsets = [0]
    if data[:4] == b"ttcf":
        n = struct.unpack_from(">I", data, 8)[0]
        offsets = list(struct.unpack_from(f">{n}I", data, 12))
    names = set()
    for base in offsets:
        try:
            n = struct.unpack_from(">H", data, base + 4)[0]
            for k in range(n):
                tag, _cs, off, _ln = struct.unpack_from(">4sIII", data, base + 12 + 16 * k)
                if tag != b"name":
                    continue
                _f, count, strings = struct.unpack_from(">HHH", data, off)
                for r in range(count):
                    plat, enc, _lang, nid, ln, so = struct.unpack_from(">HHHHHH", data, off + 6 + 12 * r)
                    if nid not in (1, 4, 16):
                        continue
                    raw = data[off + strings + so:off + strings + so + ln]
                    names.add(raw.decode("utf-16-be" if plat in (0, 3) else "latin-1", "replace").casefold())
        except struct.error:
            continue
    return names


_LOADED_USER_FONTS: set[str] = set()


def _load_user_font(face: str) -> bool:
    folder = Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "Windows" / "Fonts"
    if not os.environ.get("LOCALAPPDATA") or not folder.is_dir():
        return False
    want = face.casefold()
    a = _api()
    for path in sorted(folder.iterdir()):
        if path.suffix.lower() not in (".ttf", ".otf", ".ttc") or str(path) in _LOADED_USER_FONTS:
            continue
        if want in _font_names(path):
            if a.AddFontResourceExW(str(path), 0x10, None) > 0:      # FR_PRIVATE
                _LOADED_USER_FONTS.add(str(path))
                return True
    return False


def _has_all(info, cluster: str) -> bool:
    cmap = info[1]
    if cmap is None:
        return False
    return all(_ignorable(ord(c)) or cmap.glyph(ord(c)) for c in cluster)


def _pick_face(faces, bold: bool, cluster: str):
    for face in faces:
        info = _face_info(face, bold)
        if info is not None and _has_all(info, cluster):
            return face, info
    return None, None


# ------------------------------------------------------------------ rasterising text


def _supersample(em: int) -> int:
    return SUPERSAMPLE if em <= 48 else (2 if em <= 128 else 1)


def _round_up(v: int, m: int) -> int:
    return -(-v // m) * m


def _utf16_len(text: str) -> int:
    """The wide GDI calls count UTF-16 code units: a character past U+FFFF is two of them."""
    return len(text.encode("utf-16-le")) // 2


def _raster(text: str, face: str, em_ss: int, bold: bool, ss: int):
    """Draw `text` at em_ss pixels (supersampled by ss) and box-filter it down.  Returns
    (coverage bytearray, w, h, left, top, advance): left/top place the coverage's top-left corner
    relative to the pen and the baseline (1x pixels), advance is the 1x pen advance."""
    a = _api()
    with _Font(face, em_ss, bold):
        tm = _metrics(a)
        size = a.W.SIZE()
        a.GetTextExtentPoint32W(a.dc, text, _utf16_len(text), ctypes.byref(size))
        pad = _round_up(max(em_ss, 4), ss)
        width = _round_up(size.cx + 2 * pad, ss)
        base = _round_up(pad + tm.tmAscent, ss)
        height = _round_up(base + tm.tmDescent + pad, ss)
        bits = _dib_text(a, text, width, height, pad, base)
    if bits is None:
        return None
    cov = bits[1::4]                       # BGRA: the green channel (grey antialiasing, R = G = B)
    rows = [cov[y * width:(y + 1) * width] for y in range(height)]
    adv = round(size.cx / ss)
    box = _ink_box(rows, width)
    if box is None:
        return bytearray(), 0, 0, 0, 0, adv
    x0, y0, x1, y1 = box
    x0, y0 = x0 // ss * ss, y0 // ss * ss
    x1, y1 = _round_up(x1, ss), _round_up(y1, ss)
    w, h = (x1 - x0) // ss, (y1 - y0) // ss
    out = _downsample(rows, x0, y0, w, h, ss)
    return out, w, h, (x0 - pad) // ss, (y0 - base) // ss, adv


def _dib_text(a, text: str, width: int, height: int, x: int, y: int) -> bytes | None:
    bmi = a.BITMAPINFOHEADER()
    bmi.biSize = ctypes.sizeof(bmi)
    bmi.biWidth, bmi.biHeight, bmi.biPlanes, bmi.biBitCount = width, -height, 1, 32
    bits = ctypes.c_void_p()
    dib = a.CreateDIBSection(a.dc, ctypes.byref(bmi), 0, ctypes.byref(bits), None, 0)
    if not dib or not bits.value:
        return None
    try:
        old = a.SelectObject(a.dc, dib)
        try:
            ctypes.memset(bits, 0, width * height * 4)
            a.SetBkMode(a.dc, 1)                        # TRANSPARENT
            a.SetTextColor(a.dc, 0xFFFFFF)
            a.SetTextAlign(a.dc, TA_BASELINE)
            a.TextOutW(a.dc, x, y, text, _utf16_len(text))
            a.GdiFlush()
            return ctypes.string_at(bits, width * height * 4)
        finally:
            a.SelectObject(a.dc, old)
    finally:
        a.DeleteObject(dib)


def _ink_box(rows, width: int):
    top = bottom = None
    left, right = width, 0
    for y, row in enumerate(rows):
        s = row.lstrip(b"\0")
        if not s:
            continue
        if top is None:
            top = y
        bottom = y + 1
        left = min(left, width - len(s))
        right = max(right, len(row.rstrip(b"\0")))
    if top is None:
        return None
    return left, top, right, bottom


def _downsample(rows, x0: int, y0: int, w: int, h: int, ss: int) -> bytearray:
    out = bytearray(w * h)
    if ss == 1:
        for y in range(h):
            out[y * w:(y + 1) * w] = rows[y0 + y][x0:x0 + w]
        return out
    div = ss * ss
    half = div // 2
    for y in range(h):
        acc = [0] * w
        for k in range(ss):
            row = rows[y0 + y * ss + k]
            for x in range(w):
                s = x0 + x * ss
                acc[x] += sum(row[s:s + ss])
        o = y * w
        for x in range(w):
            out[o + x] = (acc[x] + half) // div
    return out


@functools.lru_cache(maxsize=256)
def _em_for_cap(face: str, bold: bool, cap: int, ss: int, cap_ratio: float) -> int:
    """The supersampled em size at which this face's 'H' is cap * ss pixels tall."""
    target = cap * ss
    est = max(1, round(target / cap_ratio))
    best, best_err = est, None
    for em in sorted(range(max(1, est - 3), est + 4), key=lambda e: abs(e - est)):
        r = _raster_rows_height("H", face, em, bold)
        if r is None:
            continue
        err = abs(r - target)
        if best_err is None or err < best_err:
            best, best_err = em, err
        if err == 0:
            break
    return best


def _raster_rows_height(text: str, face: str, em: int, bold: bool):
    """How many rows of `text`'s ink are at least half covered (the drawn cap height)."""
    a = _api()
    with _Font(face, em, bold):
        tm = _metrics(a)
        size = a.W.SIZE()
        a.GetTextExtentPoint32W(a.dc, text, _utf16_len(text), ctypes.byref(size))
        width, height = size.cx + 8, tm.tmAscent + tm.tmDescent + 8
        bits = _dib_text(a, text, width, height, 4, 4 + tm.tmAscent)
    if bits is None:
        return None
    cov = bits[1::4]
    return sum(1 for y in range(height) if max(cov[y * width:(y + 1) * width]) >= 128)


def _sized(face: str, info, bold: bool, cap: int, em_px: int | None):
    """(em at ss, ss) for drawing `face` with its H `cap` px tall (or at exactly em_px)."""
    if em_px is not None:
        ss = _supersample(em_px)
        return em_px * ss, ss
    _name, _cmap, cap_ratio, x_ratio, asc = info
    if cap_ratio:
        est = max(1, round(cap / cap_ratio))
        ss = _supersample(est)
        return _em_for_cap(face, bold, cap, ss, cap_ratio), ss
    ratio = (x_ratio / 0.72 * 0.716) if x_ratio else asc * 0.75
    em = max(1, round(cap / max(ratio, 0.1)))
    ss = _supersample(em)
    return em * ss, ss


def _text_coverage(cluster: str, face: str, fallbacks, bold: bool, cap: int, em_px: int | None = None):
    """(coverage, w, h, left, top_rel_baseline, advance, face used) or None."""
    faces = (face,) + tuple(f for f in fallbacks if f != face)
    faces += tuple(f for f in BUNDLED_FACES if f not in faces)          # the last steps (as in the game)
    used, info = _pick_face(faces, bold, cluster)
    primary = _face_info(face, bold)
    if used is None:
        if primary is None:
            return None
        used, info = face, primary        # GDI font linking / Uniscribe fallback
    if em_px is not None and used != face:
        cap = round(primary[2] * em_px) if primary and primary[2] else round(em_px * 0.716)
        em_px = None
    em_ss, ss = _sized(used, info, bold, cap, em_px)
    r = _raster(cluster, used, em_ss, bold, ss)
    if r is None:
        return None
    return r + (info[0],)


# ------------------------------------------------------------------ making it look like the game font


def _quantiser(levels):
    if not levels:
        return None
    levels = sorted(set(int(v) for v in levels))
    table = bytearray(256)
    for v in range(1, 256):
        table[v] = min(levels, key=lambda lv: (abs(lv - v), -lv))
    return bytes(table)


@functools.lru_cache(maxsize=32)
def _kernel(r: int):
    return tuple((dx, dy) for dy in range(-r, r + 1) for dx in range(-r, r + 1) if dx * dx + dy * dy <= r * r + r)


def _finish(cov: bytearray, w: int, h: int, style: GlyphStyle):
    """Coverage -> the game font's look.  Returns (Image, grow): the image is `grow` px bigger on
    every side than the coverage (the outline)."""
    q = _quantiser(style.alpha_levels)
    fr, fg, fb = (tuple(style.fill) + (255, 255, 255))[:3]
    if not style.outline or style.outline_width <= 0:
        img = Image(w, h)
        d = img.data
        for k in range(w * h):
            a = cov[k]
            if q is not None:
                a = q[a]
            o = 4 * k
            d[o], d[o + 1], d[o + 2], d[o + 3] = fr, fg, fb, a
        return img, 0
    r = int(style.outline_width)
    W2, H2 = w + 2 * r, h + 2 * r
    big = bytearray(W2 * H2)
    for y in range(h):
        big[(y + r) * W2 + r:(y + r) * W2 + r + w] = cov[y * w:(y + 1) * w]
    dil = bytearray(W2 * H2)
    kern = _kernel(r)
    for y in range(H2):
        for x in range(W2):
            m = 0
            for dx, dy in kern:
                xx, yy = x + dx, y + dy
                if 0 <= xx < W2 and 0 <= yy < H2:
                    v = big[yy * W2 + xx]
                    if v > m:
                        m = v
                        if m == 255:
                            break
            dil[y * W2 + x] = m
    orr, og, ob = style.outline
    img = Image(W2, H2)
    d = img.data
    for k in range(W2 * H2):
        c, o_ = big[k], dil[k]
        a = c + o_ * (255 - c) // 255
        p = 4 * k
        if a == 0:
            d[p], d[p + 1], d[p + 2], d[p + 3] = orr, og, ob, 0
            continue
        wo = o_ * (255 - c) // 255
        d[p] = (fr * c + orr * wo + a // 2) // a
        d[p + 1] = (fg * c + og * wo + a // 2) // a
        d[p + 2] = (fb * c + ob * wo + a // 2) // a
        d[p + 3] = q[a] if q is not None else a
    return img, r


# ------------------------------------------------------------------ emoji


class _Emoji:
    """Segoe UI Emoji's tables, read from the installed font with GetFontData."""

    def __init__(self) -> None:
        a = _api()
        with _Font(EMOJI_FACE, REF_EM, False):
            buf = ctypes.create_unicode_buffer(128)
            a.GetTextFaceW(a.dc, 128, buf)
            if buf.value.casefold() != EMOJI_FACE.casefold():
                raise OSError("no emoji font")
            tables = {t: _table(a, t) for t in (b"cmap", b"GSUB", b"GPOS", b"GDEF", b"COLR", b"CPAL",
                                                 b"head", b"hhea", b"hmtx")}
        for need in (b"cmap", b"head", b"hhea", b"hmtx"):
            if not tables[need]:
                raise OSError("the emoji font lacks a table")
        self.cmap = _Cmap(tables[b"cmap"])
        self.upem = struct.unpack_from(">H", tables[b"head"], 18)[0]
        n_hm = struct.unpack_from(">H", tables[b"hhea"], 34)[0]
        hmtx = tables[b"hmtx"]
        self.advances = [struct.unpack_from(">H", hmtx, 4 * k)[0] for k in range(n_hm)]
        marks: set[int] = set()
        gdef = tables[b"GDEF"]
        if gdef:
            off = struct.unpack_from(">H", gdef, 4)[0]
            if off:
                marks = {g for g, c in _class_def(gdef, off).items() if c == 3}
        self.gsub = _Gsub(tables[b"GSUB"]) if tables[b"GSUB"] else None
        self.sub_lookups = self.gsub.feature_lookups((b"ccmp", b"liga", b"rlig", b"clig")) if self.gsub else []
        self.gpos = _Gpos(tables[b"GPOS"], marks) if tables[b"GPOS"] else None
        self.pos_lookups = self.gpos.feature_lookups((b"kern", b"mark", b"mkmk", b"dist")) if self.gpos else []
        self.colr = _Colr(tables[b"COLR"], tables[b"CPAL"]) if tables[b"COLR"] and tables[b"CPAL"] else None
        self.invisible = {self.cmap.glyph(cp) for cp in (0x200D, 0xFE0E, 0xFE0F)} - {0}
        # The grinning face sets the emoji size and the line they sit on.
        ref = self.cmap.glyph(0x1F600)
        big = 1024
        with _Font(EMOJI_FACE, big, False):
            gm = a.GLYPHMETRICS()
            got = a.GetGlyphOutlineW(a.dc, ref, GGO_METRICS | GGO_GLYPH_INDEX, ctypes.byref(gm), 0, None,
                                     ctypes.byref(a.IDENTITY)) if ref else GDI_ERROR
        if got == GDI_ERROR or not gm.gmBlackBoxY:
            self.h_ratio, self.top_ratio = 0.9, 0.85
        else:
            self.h_ratio, self.top_ratio = gm.gmBlackBoxY / big, gm.gmptGlyphOrigin.y / big

    def advance(self, gid: int) -> int:
        adv = self.advances
        return adv[gid] if gid < len(adv) else (adv[-1] if adv else 0)

    def _substitute(self, cps) -> list[int]:
        gids = []
        for cp in cps:
            g = self.cmap.glyph(cp)
            if g == 0 and (_ignorable(cp) or 0xE0000 <= cp <= 0xE007F):
                continue                       # an unsupported tag or selector draws nothing
            gids.append(g)
        if self.gsub is not None:
            gids = self.gsub.apply(gids, self.sub_lookups)
        return [g for g in gids if g not in self.invisible]

    def shape(self, cluster: str):
        """(glyph ids, positions): positions are font units [x offset, y offset (up), x advance]."""
        cps = [ord(c) for c in cluster]
        gids = self._substitute(cps)
        if 0xFE0F in cps or 0xFE0E in cps:
            bare = self._substitute([c for c in cps if c not in (0xFE0E, 0xFE0F)])
            if bare and len(bare) < len(gids):
                gids = bare                    # e.g. 1 FE0F 20E3: the font's keycap ligature has no FE0F
        pos = [[0, 0, self.advance(g)] for g in gids]
        if self.gpos is not None and gids:
            self.gpos.apply(gids, pos, self.pos_lookups)
        return gids, pos


_EMOJI: list = []


def _emoji():
    if not _EMOJI:
        try:
            _EMOJI.append(_Emoji() if _api() is not None else None)
        except (OSError, struct.error, IndexError, ValueError):
            _EMOJI.append(None)
    return _EMOJI[0]


def shape_emoji(cluster: str) -> list[int] | None:
    """The Segoe UI Emoji glyph ids the cluster shapes to (one id for a supported sequence), or None."""
    with _LOCK:
        e = _emoji()
        return None if e is None else e.shape(cluster)[0]


def emoji_coverage_report() -> dict | None:
    """How many of the emoji font's colour glyphs this module paints in colour: {"v0": n, "v1": n,
    "v1_only": n} (v1_only glyphs are drawn monochrome)."""
    with _LOCK:
        e = _emoji()
        if e is None or e.colr is None:
            return None
        v0 = set(e.colr.base)
        return {"v0": len(v0), "v1": len(e.colr.v1), "v1_only": len(e.colr.v1 - v0)}


def _glyph_bitmap(a, gid: int):
    """(left, top above baseline, w, h, rows of 0-64, advance) of a glyph of the selected font."""
    gm = a.GLYPHMETRICS()
    n = a.GetGlyphOutlineW(a.dc, gid, GGO_GRAY8_BITMAP | GGO_GLYPH_INDEX, ctypes.byref(gm), 0, None,
                           ctypes.byref(a.IDENTITY))
    if n == GDI_ERROR:
        return None
    adv = gm.gmCellIncX
    if n == 0:
        return gm.gmptGlyphOrigin.x, gm.gmptGlyphOrigin.y, 0, 0, b"", adv
    buf = ctypes.create_string_buffer(n)
    if a.GetGlyphOutlineW(a.dc, gid, GGO_GRAY8_BITMAP | GGO_GLYPH_INDEX, ctypes.byref(gm), n, buf,
                          ctypes.byref(a.IDENTITY)) == GDI_ERROR:
        return None
    return gm.gmptGlyphOrigin.x, gm.gmptGlyphOrigin.y, gm.gmBlackBoxX, gm.gmBlackBoxY, buf.raw, adv


def _render_emoji(cluster: str, line_height: int, fg) -> GeneratedGlyph | None:
    e = _emoji()
    if e is None:
        return None
    gids, pos = e.shape(cluster)
    if not gids or any(g == 0 for g in gids):
        return None
    a = _api()
    em = max(1, round(max(1, line_height) / e.h_ratio))
    ss = _supersample(em)
    em_ss = em * ss
    scale = em_ss / e.upem
    fr, fg_, fb = (tuple(fg) + (255, 255, 255))[:3]
    layers = []
    pen = 0
    coloured = False
    with _Font(EMOJI_FACE, em_ss, False):
        for gid, (xo, yo, xa) in zip(gids, pos):
            parts = e.colr.base.get(gid) if e.colr is not None else None
            if parts:
                coloured = True
            else:
                parts = ((gid, 0xFFFF),)
            gx, gy = round((pen + xo) * scale), -round(yo * scale)
            for lg, pi in parts:
                bm = _glyph_bitmap(a, lg)
                if bm is None:
                    continue
                bx, by, w, h, raw, _la = bm
                if pi == 0xFFFF or e.colr is None or pi >= len(e.colr.palette):
                    colour = (fr, fg_, fb, 255)
                else:
                    colour = e.colr.palette[pi]
                if w and h:
                    layers.append((gx + bx, gy - by, w, h, raw, colour))
            pen += xa
    advance = round(pen * scale / ss)
    # The line this emoji sits on: the reference face centred on the line cell.
    base_line = round(line_height / 2 + (e.top_ratio - e.h_ratio / 2) * em)
    if not layers:
        return GeneratedGlyph(Image(0, 0), 0, 0, advance, "emoji", EMOJI_FACE, coloured)
    x0 = min(L[0] for L in layers) // ss * ss
    y0 = min(L[1] for L in layers) // ss * ss
    x1 = _round_up(max(L[0] + L[2] for L in layers), ss)
    y1 = _round_up(max(L[1] + L[3] for L in layers), ss)
    W2, H2 = x1 - x0, y1 - y0
    pr = [0.0] * (W2 * H2)
    pg = [0.0] * (W2 * H2)
    pb = [0.0] * (W2 * H2)
    pa = [0.0] * (W2 * H2)
    for lx, ly, w, h, raw, (cr, cg, cb, ca) in layers:
        pitch = (w + 3) & ~3
        ka = ca / 255.0 / 64.0
        for y in range(h):
            row = raw[y * pitch:y * pitch + w]
            base = (ly - y0 + y) * W2 + (lx - x0)
            for x, v in enumerate(row):
                if v:
                    al = v * ka
                    if al > 1.0:
                        al = 1.0
                    k = base + x
                    inv = 1.0 - al
                    pr[k] = cr * al + pr[k] * inv
                    pg[k] = cg * al + pg[k] * inv
                    pb[k] = cb * al + pb[k] * inv
                    pa[k] = al + pa[k] * inv
    w, h = W2 // ss, H2 // ss
    img = Image(w, h)
    d = img.data
    div = float(ss * ss)
    for y in range(h):
        for x in range(w):
            sr = sg = sb = sa = 0.0
            for j in range(ss):
                k = (y * ss + j) * W2 + x * ss
                for i in range(ss):
                    sr += pr[k + i]
                    sg += pg[k + i]
                    sb += pb[k + i]
                    sa += pa[k + i]
            if sa <= 0.0:
                continue
            o = 4 * (y * w + x)
            d[o] = min(255, int(sr / sa + 0.5))
            d[o + 1] = min(255, int(sg / sa + 0.5))
            d[o + 2] = min(255, int(sb / sa + 0.5))
            d[o + 3] = min(255, int(sa / div * 255 + 0.5))
    return GeneratedGlyph(img, x0 // ss, base_line + y0 // ss, advance, "emoji", EMOJI_FACE, coloured)


# ------------------------------------------------------------------ public rendering


def render_cluster(cluster: str, style: GlyphStyle) -> GeneratedGlyph | None:
    """One grapheme cluster drawn in the game font's style (see the module docstring).  None for a line
    break, an empty string, or where nothing can be drawn (no Windows, no font)."""
    if not cluster or cluster in ("\n", "\r", "\r\n"):
        return None
    try:
        with _LOCK:
            got = _render_cluster_cached(cluster, style)
    except (OSError, ValueError, struct.error, IndexError, ctypes.ArgumentError):
        return None
    return None if got is None else got.copy()


@functools.lru_cache(maxsize=2048)
def _render_cluster_cached(cluster: str, style: GlyphStyle):
    if _api() is None:
        return None
    if is_emoji(cluster):
        got = _render_emoji(cluster, style.line_height, style.fill)
        if got is not None:
            return got
    r = _text_coverage(cluster, style.face, style.fallback_faces, style.bold, style.cap_height)
    if r is None:
        return None
    cov, w, h, left, top, adv, face = r
    if not w or not h:
        return GeneratedGlyph(Image(0, 0), 0, 0, adv, "system", face)
    img, grow = _finish(cov, w, h, style)
    return GeneratedGlyph(img, left - grow, style.baseline + top - grow, adv, "system", face)


# Spacing forms of the common combining marks (drawn alone, then placed on the base).
_SPACING_FORMS = {
    0x0300: "`", 0x0301: "\u00B4", 0x0302: "\u02C6", 0x0303: "\u02DC", 0x0304: "\u00AF", 0x0305: "\u00AF",
    0x0306: "\u02D8", 0x0307: "\u02D9", 0x0308: "\u00A8", 0x030A: "\u02DA", 0x030B: "\u02DD",
    0x030C: "\u02C7", 0x0323: "\u02D9", 0x0324: "\u00A8", 0x0325: "\u02DA", 0x0327: "\u00B8",
    0x0328: "\u02DB", 0x0331: "\u00AF", 0x0332: "_", 0x0335: "-", 0x0336: "\u2014", 0x0337: "/",
    0x0338: "/",
}
_BELOW_CCC = frozenset([202, 218, 220, 222, 224, 233])


def _mark_place(mark: str) -> str:
    cp = ord(mark[0])
    if cp in (0x0335, 0x0336, 0x0337, 0x0338) or unicodedata.combining(mark[0]) == 1:
        return "overlay"
    ccc = unicodedata.combining(mark[0])
    if ccc in _BELOW_CCC or cp in (0x0323, 0x0324, 0x0325, 0x0327, 0x0328, 0x0331, 0x0332):
        return "below"
    return "above"


def render_mark(mark: str, style: GlyphStyle, base_box: tuple) -> GeneratedGlyph | None:
    """One combining mark placed on a base glyph whose drawn pixels are base_box = (left, top, right,
    bottom) relative to the pen x and the line top (right/bottom exclusive).  Above marks are centred
    over the base with one clear row above its top, below marks hang under the baseline (cedilla and
    ogonek attached to it, the ogonek at the base's right), overlays are centred through the base.
    The glyph's advance is 0."""
    if not mark:
        return None
    try:
        with _LOCK:
            got = _render_mark_cached(mark, style, tuple(int(v) for v in base_box))
    except (OSError, ValueError, struct.error, IndexError, ctypes.ArgumentError, TypeError):
        return None
    return None if got is None else got.copy()


@functools.lru_cache(maxsize=1024)
def _render_mark_cached(mark: str, style: GlyphStyle, base_box: tuple):
    if _api() is None:
        return None
    cp = ord(mark[0])
    source = _SPACING_FORMS.get(cp, mark)
    r = _text_coverage(source, style.face, style.fallback_faces, style.bold, style.cap_height)
    if (r is None or not r[1]) and source != mark:
        r = _text_coverage(mark, style.face, style.fallback_faces, style.bold, style.cap_height)
    if r is None or not r[1] or not r[2]:
        return None
    cov, w, h, _l, _t, _adv, face = r
    left, top, right, bottom = base_box
    place = _mark_place(mark)
    if place == "overlay":
        x = round((left + right - w) / 2)
        y = round((top + bottom - h) / 2)
    elif place == "below":
        attached = cp in (0x0327, 0x0328) or unicodedata.combining(mark[0]) == 202
        x = (right - w) if cp == 0x0328 else round((left + right - w) / 2)
        y = style.baseline if attached else max(bottom, style.baseline) + 1
    else:
        x = round((left + right - w) / 2)
        y = top - 1 - h
        if y < 0:
            y = top - h
    img, grow = _finish(cov, w, h, style)
    return GeneratedGlyph(img, x - grow, y - grow, 0, "system", face)


@functools.lru_cache(maxsize=64)
def _ttf_metrics_cached(face: str, pixel_size: int):
    if _api() is None or _face_info(face, False) is None:
        return None
    a = _api()
    with _Font(face, pixel_size, False):
        tm = _metrics(a)
    return tm.tmAscent + tm.tmDescent, tm.tmAscent


def ttf_metrics(face: str, pixel_size: int) -> tuple[int, int] | None:
    """(line height, baseline) in px of an installed face drawn at `pixel_size` (its em height)."""
    try:
        with _LOCK:
            if not font_installed(face):
                return None
            return _ttf_metrics_cached(face, max(1, int(pixel_size)))
    except (OSError, ValueError, ctypes.ArgumentError):
        return None


def render_ttf_text(face: str, pixel_size: int, cluster: str, colour=(255, 255, 255)) -> GeneratedGlyph | None:
    """A cluster in an installed font at `pixel_size` px (its em height), antialiased, in `colour`.
    `top` is relative to a line cell of ttf_metrics(face, pixel_size).  Characters the face lacks
    come from the default fallback faces at the face's cap height; emoji are full colour."""
    if not cluster or cluster in ("\n", "\r", "\r\n"):
        return None
    try:
        with _LOCK:
            got = _render_ttf_cached(face, max(1, int(pixel_size)), cluster, tuple(colour)[:3])
    except (OSError, ValueError, struct.error, IndexError, ctypes.ArgumentError):
        return None
    return None if got is None else got.copy()


@functools.lru_cache(maxsize=2048)
def _render_ttf_cached(face: str, pixel_size: int, cluster: str, colour: tuple):
    if not font_installed(face):
        return None
    metrics = _ttf_metrics_cached(face, pixel_size)
    if metrics is None:
        return None
    line_height, baseline = metrics
    if is_emoji(cluster):
        got = _render_emoji(cluster, line_height, colour)
        if got is not None:
            return got
    r = _text_coverage(cluster, face, DEFAULT_FALLBACKS, False, 0, em_px=pixel_size)
    if r is None:
        return None
    cov, w, h, left, top, adv, used = r
    style = GlyphStyle(line_height, baseline, 0, 0, colour, None, 0, None, face, False)
    if not w or not h:
        return GeneratedGlyph(Image(0, 0), 0, 0, adv, "system", used)
    img, _grow = _finish(cov, w, h, style)
    return GeneratedGlyph(img, left, baseline + top, adv, "system", used)


def clear_cache() -> None:
    """Forget every cached glyph and face (after the player installs a font)."""
    with _LOCK:
        for f in (_render_cluster_cached, _render_mark_cached, _render_ttf_cached, _ttf_metrics_cached,
                  _face_info, _em_for_cap):
            f.cache_clear()


__all__ = ["GlyphStyle", "GeneratedGlyph", "available", "font_installed", "segment", "is_emoji",
           "render_cluster", "render_mark", "render_ttf_text", "ttf_metrics", "shape_emoji",
           "emoji_coverage_report", "clear_cache", "DEFAULT_FALLBACKS"]
