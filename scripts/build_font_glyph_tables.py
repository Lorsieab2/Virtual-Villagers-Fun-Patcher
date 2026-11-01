"""Write data/font_glyph_tables.json: every bitmap font of the five Virtual Villagers games.

Each game draws all of its text with two LDW bitmap fonts, "ldwBurweed27" and "ldwarialbold": a white
picture with the letters' coverage in its alpha channel (Images/<name>.png) and a glyph table in the
executable's data, 20-byte entries {code, x1, y1, x2, y2} ending at code 0.  The font constructor
(ctor below) loads the picture, wraps the entries that run past the picture's width onto its next row
(A New Home and The Lost Children keep their letters in two rows), and indexes the codes 0..255; a code
with no entry draws entry 0.  The space between two letters is the box width plus `spacing` (the
constructor's third argument).

This writes the facts only -- coordinates, codes and addresses, read from the stock executables in
research/stock-executables -- never any picture.  src/vv_font_glyphs.py and the in-game companion
(native/vvfp_unicode_text) read them.
"""
from __future__ import annotations

import json
import struct
import sys
from pathlib import Path

import pefile

ROOT = Path(__file__).resolve().parents[1]
STOCK = ROOT / "research" / "stock-executables"
OUT = ROOT / "data" / "font_glyph_tables.json"
EXES = {
    "vv1": "Virtual Villagers - A New Home.exe",
    "vv2": "Virtual Villagers - The Lost Children.exe",
    "vv3": "Virtual Villagers - The Secret City.exe",
    "vv4": "Virtual Villagers - The Tree of Life.exe",
    "vv5": "Virtual Villagers - New Believers.exe",
}
# game: (font constructor, {font: (table, the construction's push of the table, spacing)})
FONTS = {
    "vv1": (0x402240, {"ldwBurweed27": (0x4862A0, 0x412714, 0), "ldwarialbold": (0x486888, 0x4127B4, 1)}),
    "vv2": (0x4024D0, {"ldwBurweed27": (0x4952C0, 0x413114, 0), "ldwarialbold": (0x4958A8, 0x413184, 1)}),
    "vv3": (0x402510, {"ldwBurweed27": (0x4A5B78, 0x4244D4, 0), "ldwarialbold": (0x4A6A80, 0x424564, 0)}),
    "vv4": (0x4027A0, {"ldwBurweed27": (0x4BB068, 0x41D8BF, 0), "ldwarialbold": (0x4BA140, 0x41D84F, 0)}),
    "vv5": (0x402730, {"ldwBurweed27": (0x4C8F08, 0x41E8DF, 0), "ldwarialbold": (0x4C7FE0, 0x41E86F, 0)}),
}
# The picture sizes the constructor wraps against (Images/<font>.png of each stock game).
SHEETS = {
    "vv1": {"ldwBurweed27": (793, 54), "ldwarialbold": (728, 40)},
    "vv2": {"ldwBurweed27": (793, 54), "ldwarialbold": (728, 40)},
    "vv3": {"ldwBurweed27": (2364, 27), "ldwarialbold": (1940, 20)},
    "vv4": {"ldwBurweed27": (2364, 27), "ldwarialbold": (1940, 20)},
    "vv5": {"ldwBurweed27": (2384, 27), "ldwarialbold": (1940, 20)},
}


def raw_entries(image: bytes, base: int, table: int) -> list[list[int]]:
    out, at = [], table - base
    while True:
        entry = list(struct.unpack_from("<5i", image, at))
        if entry[0] == 0:
            return out
        out.append(entry)
        at += 20


def normalise(entries: list[list[int]], width: int) -> list[list[int]]:
    """The constructor's own pass (A New Home 0x40235C): an entry whose right edge passes the picture's
    width moves to the start of the next row, and every later entry follows it."""
    entries = [list(e) for e in entries]
    line = entries[0][4] - entries[0][2]
    dx = dy = 0
    for e in entries:
        e[1] -= dx
        e[3] -= dx
        e[2] += dy
        e[4] += dy
        if e[3] > width:
            dx += e[1]
            dy += line + 1
            e[3] -= e[1]
            e[1] = 0
            e[2] += line + 1
            e[4] += line + 1
    for e in entries:
        e[0] &= 0xFF
    return entries


# The game's SDL_TEXTINPUT case (the event pump's `cmp eax, 0x303 / je`): `lea eax, [esp + text]` at
# `site` starts a strlen; a text of one byte is posted as message 5 (push char; push ebx; push 5; call
# at `post`), anything else jumps to `skip`.  game: (site, text offset, skip, post)
TEXT_INPUT = {
    "vv1": (0x403B9B, 0x34, 0x403C73, 0x403BBD),
    "vv2": (0x403E2B, 0x34, 0x403F03, 0x403E4D),
    "vv3": (0x40444B, 0x34, 0x404523, 0x40446D),
    "vv4": (0x404A25, 0x30, 0x404B07, 0x404A4D),
    "vv5": (0x4049B5, 0x30, 0x404A97, 0x4049DD),
}
TEXT_SITE_LEN = 7          # lea eax, [esp + text] (4) ; lea edx, [eax + 1] (3)
SDL_SLOTS = ("SDL_CreateRGBSurface", "SDL_FreeSurface", "SDL_LockSurface", "SDL_UnlockSurface")
HEADER = ROOT / "native" / "vvfp_unicode_text" / "unicode_text_tables.h"


def ctor_length(code: bytes) -> int:
    """The constructor's first whole instructions covering a 5-byte jump: A New Home .. The Secret City
    start `mov eax, fs:[0]` (6) `push -1` (2); The Tree of Life and New Believers `push -1` (2)
    `push imm32` (5).  Both are position-independent, so they run unchanged from the trampoline."""
    if code[:8] == bytes.fromhex("64A1000000006AFF"):
        return 8
    if code[:3] == bytes.fromhex("6AFF68"):
        return 7
    raise ValueError(code.hex())


def cp1252_tables() -> tuple[list[int], list[tuple[int, int, int, int]]]:
    """(byte -> UTF-16 unit, 0 when Windows-1252 leaves it undefined or it is a control) and the
    accented letters: (byte, plain letter's byte, the accent's spacing character, 1 when below)."""
    sys.path.insert(0, str(ROOT / "src"))
    import vv_font_glyphs as glyphs
    units = [0] * 256
    for ch in glyphs.PRINTABLE:
        units[glyphs.to_byte(ch)] = ord(ch)
    accents = []
    for ch in glyphs.PRINTABLE:
        parts = glyphs.decompose(ch)
        if parts:
            accents.append((glyphs.to_byte(ch), glyphs.to_byte(parts[0]), ord(glyphs.MARKS[parts[1]]),
                            1 if parts[1] in glyphs.BELOW else 0))
    return units, accents


def write_header(per_game: dict) -> None:
    units, accents = cp1252_tables()
    lines = [
        "/* Generated by scripts/build_font_glyph_tables.py from the stock executables -- do not edit.",
        "   The facts native/vvfp_unicode_text needs, the same ones src/vv_font_glyphs.py uses. */",
        "#ifndef VVFP_UNICODE_TEXT_TABLES_H",
        "#define VVFP_UNICODE_TEXT_TABLES_H",
        "",
        "/* Windows-1252: each byte's character (UTF-16), 0 = not a printable character. */",
        "static const unsigned short VG_CP1252[256] = {",
    ]
    for i in range(0, 256, 8):
        lines.append("    " + ", ".join(f"0x{u:04X}" for u in units[i:i + 8]) + ",")
    lines += ["};", "", "/* The accented letters: the letter, its plain letter, the accent drawn, below. */",
              "typedef struct vg_accent { unsigned char code, plain; unsigned short mark; unsigned char below; }"
              " vg_accent;",
              f"#define VG_ACCENT_COUNT {len(accents)}",
              "static const vg_accent VG_ACCENTS[VG_ACCENT_COUNT] = {"]
    for code, plain, mark, below in accents:
        lines.append(f"    {{0x{code:02X}, 0x{plain:02X}, 0x{mark:04X}, {below}}},")
    lines += ["};", "",
              "/* Each game: the font constructor and its first instructions (moved to the trampoline), the",
              "   two fonts' stock tables, the SDL_TEXTINPUT case and the SDL import slots. */",
              "typedef struct vg_game {",
              "    unsigned int ctor; int ctor_len; unsigned char ctor_bytes[8];",
              "    unsigned int burweed_table, arial_table; int burweed_spacing, arial_spacing;",
              "    unsigned int text_site; unsigned char text_bytes[7]; int text_offset;",
              "    unsigned int text_skip, text_post;",
              "    unsigned int sdl_create, sdl_free, sdl_lock, sdl_unlock;",
              "} vg_game;",
              "static const vg_game VG_GAMES[6] = {",
              "    {0},"]
    for game in ("vv1", "vv2", "vv3", "vv4", "vv5"):
        g = per_game[game]
        cb = ", ".join(f"0x{b:02X}" for b in g["ctor_bytes"].ljust(8, b"\0"))
        tb = ", ".join(f"0x{b:02X}" for b in g["text_bytes"])
        lines.append(
            f"    {{0x{g['ctor']:06X}u, {g['ctor_len']}, {{{cb}}}, 0x{g['burweed']:06X}u, 0x{g['arial']:06X}u, "
            f"{g['burweed_spacing']}, {g['arial_spacing']}, 0x{g['site']:06X}u, {{{tb}}}, 0x{g['offset']:X}, "
            f"0x{g['skip']:06X}u, 0x{g['post']:06X}u, " + ", ".join(f"0x{v:06X}u" for v in g["slots"]) + "},"
            f"  /* {game} */")
    lines += ["};", "", "#endif", ""]
    HEADER.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    print("wrote", HEADER.name)


def main() -> None:
    data: dict = {"_about": __doc__.strip().splitlines()[0], "games": {}}
    per_game: dict = {}
    for game, (ctor, fonts) in FONTS.items():
        pe = pefile.PE(str(STOCK / EXES[game]))
        image = pe.get_memory_mapped_image()
        base = pe.OPTIONAL_HEADER.ImageBase
        row = {"ctor": f"0x{ctor:06X}", "ctor_bytes": image[ctor - base:ctor - base + 16].hex().upper(),
               "fonts": {}}
        for font, (table, push, spacing) in fonts.items():
            assert image[push - base] == 0x68 and struct.unpack_from("<I", image, push - base + 1)[0] == table
            assert image[push - base - 2:push - base] == bytes([0x6A, spacing])
            entries = raw_entries(image, base, table)
            raw = image[table - base:table - base + 20 * (len(entries) + 1)]
            w, h = SHEETS[game][font]
            row["fonts"][font] = {
                "table": f"0x{table:06X}", "entries_count": len(entries), "spacing": spacing,
                "table_sha256": __import__("hashlib").sha256(raw).hexdigest().upper(),
                "sheet": f"Images/{font}.png", "sheet_size": [w, h],
                "entries": normalise(entries, w),
            }
        data["games"][game] = row
        site, offset, skip, post = TEXT_INPUT[game]
        text_bytes = image[site - base:site - base + TEXT_SITE_LEN]
        assert text_bytes == bytes([0x8D, 0x44, 0x24, offset, 0x8D, 0x50, 0x01]), (game, text_bytes.hex())
        row["text_input"] = {"site": f"0x{site:06X}", "stock_bytes": text_bytes.hex().upper(),
                             "text_offset": offset, "skip": f"0x{skip:06X}", "post": f"0x{post:06X}"}
        slots = {}
        for entry in pe.DIRECTORY_ENTRY_IMPORT:
            for imp in entry.imports:
                if imp.name and imp.name.decode() in SDL_SLOTS:
                    slots[imp.name.decode()] = imp.address
        n = ctor_length(image[ctor - base:ctor - base + 8])
        row["ctor_len"] = n
        per_game[game] = {
            "ctor": ctor, "ctor_len": n, "ctor_bytes": image[ctor - base:ctor - base + n],
            "burweed": fonts["ldwBurweed27"][0], "arial": fonts["ldwarialbold"][0],
            "burweed_spacing": fonts["ldwBurweed27"][2], "arial_spacing": fonts["ldwarialbold"][2],
            "site": site, "text_bytes": text_bytes, "offset": offset, "skip": skip, "post": post,
            "slots": [slots[name] for name in SDL_SLOTS],
        }
    text = json.dumps(data, indent=1)
    # One glyph entry a line.
    import re
    text = re.sub(r"\[\n\s+(-?\d+),\n\s+(-?\d+),\n\s+(-?\d+),\n\s+(-?\d+),\n\s+(-?\d+)\n\s+\]",
                  lambda m: "[" + ", ".join(m.groups()) + "]", text)
    OUT.write_text(text + "\n", encoding="utf-8", newline="\n")
    print("wrote", OUT.name)
    write_header(per_game)


if __name__ == "__main__":
    sys.exit(main())
