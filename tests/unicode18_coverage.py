"""Which source of the companions' fallback chain draws each Unicode 18.0 character (tests/test_unicode18.py).

The chain (native/vvfp_unicode_text/runtime_glyphs.inc, rg_chain):
  1. the game's own font (its bitmap letters) and 2. the patcher-made letters (src/vv_font_glyphs.py: every
     printable Windows-1252 character);
  3. the player's Windows fonts (RG_CHAIN's faces that are installed);
  4. the bundled open fonts (assets/unicode_fonts: GNU Unifont, Unifont Upper);
  5. Last Resort (assets/unicode_fonts/LastResortHE-Regular.ttf): a block placeholder;
  6. the companion's own drawn box with the code point (anything Last Resort's cmap does not map).
A font "has" a character when its cmap maps it to a glyph other than .notdef.  Cmap formats 4, 12 and 13
are read with struct, from the font files themselves.
"""
from __future__ import annotations

import os
import re
import struct
import winreg
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FONTS = ROOT / "assets" / "unicode_fonts"
RUNTIME = ROOT / "native" / "vvfp_unicode_text" / "runtime_glyphs.inc"


def _tables(data: bytes, base: int) -> dict:
    n = struct.unpack_from(">H", data, base + 4)[0]
    out = {}
    for k in range(n):
        tag, _cs, off, ln = struct.unpack_from(">4sIII", data, base + 12 + 16 * k)
        out[tag] = (off, ln)
    return out


def _cmap_ranges(data: bytes, base: int = 0) -> list[tuple[int, int]]:
    """[(first, last)] of every code point the font's best Unicode cmap maps to a glyph other than 0."""
    off, _ln = _tables(data, base)[b"cmap"]
    n = struct.unpack_from(">H", data, off + 2)[0]
    subs = {}
    for k in range(n):
        plat, enc, so = struct.unpack_from(">HHI", data, off + 4 + 8 * k)
        fmt = struct.unpack_from(">H", data, off + so)[0]
        subs[(plat, enc, fmt)] = off + so
    for key in ((3, 10, 13), (0, 6, 13), (3, 10, 12), (0, 4, 12), (0, 6, 12), (3, 1, 4), (0, 3, 4), (3, 0, 4)):
        if key in subs:
            at = subs[key]
            fmt = key[2]
            break
    else:
        return []
    out: list[tuple[int, int]] = []
    if fmt in (12, 13):
        groups = struct.unpack_from(">I", data, at + 12)[0]
        for g in range(groups):
            a, b, gid = struct.unpack_from(">III", data, at + 16 + 12 * g)
            if fmt == 13:
                if gid:
                    out.append((a, b))
            else:
                if gid == 0:            # the first maps to .notdef (rare): drop it
                    a += 1
                if a <= b:
                    out.append((a, b))
        return out
    segx2 = struct.unpack_from(">H", data, at + 6)[0]
    seg = segx2 // 2
    ends = struct.unpack_from(f">{seg}H", data, at + 14)
    starts = struct.unpack_from(f">{seg}H", data, at + 16 + segx2)
    deltas = struct.unpack_from(f">{seg}h", data, at + 16 + 2 * segx2)
    ro_at = at + 16 + 3 * segx2
    ros = struct.unpack_from(f">{seg}H", data, ro_at)
    for i in range(seg):
        a, b = starts[i], ends[i]
        if a == 0xFFFF:
            continue
        if ros[i] == 0:
            cps = [c for c in range(a, b + 1) if (c + deltas[i]) & 0xFFFF]
        else:
            cps = []
            for c in range(a, b + 1):
                gat = ro_at + 2 * i + ros[i] + 2 * (c - a)
                gid = struct.unpack_from(">H", data, gat)[0]
                if gid and (gid + deltas[i]) & 0xFFFF:
                    cps.append(c)
        for c in cps:
            if out and out[-1][1] == c - 1:
                out[-1] = (out[-1][0], c)
            else:
                out.append((c, c))
    return out


def _family(data: bytes, base: int) -> set[str]:
    off, _ln = _tables(data, base)[b"name"]
    _f, count, strings = struct.unpack_from(">HHH", data, off)
    names = set()
    for r in range(count):
        plat, _enc, _lang, nid, ln, so = struct.unpack_from(">HHHHHH", data, off + 6 + 12 * r)
        if nid in (1, 16):
            raw = data[off + strings + so:off + strings + so + ln]
            names.add(raw.decode("utf-16-be" if plat in (0, 3) else "latin-1", "replace").casefold())
    return names


class Coverage:
    def __init__(self, ranges) -> None:
        self.firsts = [a for a, _ in ranges]
        self.lasts = [b for _, b in ranges]

    def __contains__(self, cp: int) -> bool:
        import bisect
        i = bisect.bisect_right(self.firsts, cp) - 1
        return i >= 0 and cp <= self.lasts[i]


def font_file_coverage(path: Path) -> list[tuple[set[str], Coverage]]:
    data = path.read_bytes()
    bases = [0]
    if data[:4] == b"ttcf":
        n = struct.unpack_from(">I", data, 8)[0]
        bases = list(struct.unpack_from(f">{n}I", data, 12))
    return [(_family(data, b), Coverage(_cmap_ranges(data, b))) for b in bases]


def chain_faces() -> list[str]:
    """RG_CHAIN's Windows faces, in order (runtime_glyphs.inc)."""
    text = RUNTIME.read_text(encoding="utf-8")
    body = re.search(r"RG_CHAIN\[\] = \{(.*?)\};", text, re.S).group(1)
    return re.findall(r'L"([^"]+)"', body)


def bundled_faces() -> list[str]:
    text = RUNTIME.read_text(encoding="utf-8")
    body = re.search(r"RG_BUNDLED\[\] = \{(.*?)\};", text, re.S)
    return re.findall(r'L"([^"]+)"', body.group(1)) if body else []


@lru_cache(maxsize=1)
def windows_font_files() -> dict[str, Path]:
    """Every installed font file: the system and the per-user Fonts folders."""
    out = {}
    folders = [Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"]
    if os.environ.get("LOCALAPPDATA"):
        folders.append(Path(os.environ["LOCALAPPDATA"]) / "Microsoft" / "Windows" / "Fonts")
    for folder in folders:
        if folder.is_dir():
            for p in folder.iterdir():
                if p.suffix.lower() in (".ttf", ".otf", ".ttc"):
                    out[p.name.casefold()] = p
    return out


def face_coverage(face: str) -> Coverage | None:
    """The union of the cmaps of every installed file whose family is `face`, or None."""
    want = face.casefold()
    ranges = []
    for p in windows_font_files().values():
        try:
            for fams, cov in font_file_coverage(p):
                if want in fams:
                    ranges += list(zip(cov.firsts, cov.lasts))
        except (struct.error, KeyError, OSError):
            continue
    if not ranges:
        return None
    ranges.sort()
    merged = []
    for a, b in ranges:
        if merged and a <= merged[-1][1] + 1:
            merged[-1] = (merged[-1][0], max(merged[-1][1], b))
        else:
            merged.append((a, b))
    return Coverage(merged)


def bundled_coverage() -> list[tuple[str, Coverage]]:
    out = []
    for p in sorted(FONTS.glob("*.otf")) + sorted(FONTS.glob("unifont*.ttf")):
        for fams, cov in font_file_coverage(p):
            out.append((p.name, cov))
    return out


def last_resort_coverage() -> Coverage:
    return font_file_coverage(FONTS / "LastResortHE-Regular.ttf")[0][1]
