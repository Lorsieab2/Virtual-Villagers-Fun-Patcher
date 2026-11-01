"""Build data/vv_font_tables.json: the glyph tables of every bitmap font the five games use.

Picture Studio's Text tab (src/vv_pictures_text.py) lays text out in the games' own fonts.  The pictures
(ldwarialbold.png, ldwBurweed27.png) come from the player's own game folder; the glyph tables (which cell
of the sheet each character is, numbers only, no art) are compiled into the executables.  This script reads
them from the stock executables (research/stock-executables, never shipped) and writes them as JSON, with
each font's letter spacing (the third argument its wrapper constructor pushes) and the stock sheet's size.

Every font: each game builds exactly two (docs/picture-studio-text.md "The fonts"): the font loader has two
call sites, the two wrapper constructors below.

    python scripts/build_vv_font_tables.py            # write data/vv_font_tables.json
    python scripts/build_vv_font_tables.py --check    # exit 1 when the JSON differs from the executables
"""
from __future__ import annotations

import json
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "vv_font_tables.json"
EXES = ROOT / "research" / "stock-executables"
IMAGES = ROOT / "research" / "game-images"
TITLES = {1: "A New Home", 2: "The Lost Children", 3: "The Secret City", 4: "The Tree of Life", 5: "New Believers"}
FORMAT = "Virtual Villagers Fun Patcher: game font tables"

# (font key, wrapper constructor VA, glyph table VA) per game.  The constructor pushes
# (spacing, table, name) and calls the font loader; the build checks those pushes byte for byte.
FONTS = {
    1: (("arialbold", 0x412790, 0x486888), ("burweed", 0x4126F0, 0x4862A0)),
    2: (("arialbold", 0x413160, 0x4958A8), ("burweed", 0x4130F0, 0x4952C0)),
    3: (("arialbold", 0x424540, 0x4A6A80), ("burweed", 0x4244B0, 0x4A5B78)),
    4: (("arialbold", 0x41D820, 0x4BA140), ("burweed", 0x41D890, 0x4BB068)),
    5: (("arialbold", 0x41E840, 0x4C7FE0), ("burweed", 0x41E8B0, 0x4C8F08)),
}
SHEETS = {"arialbold": "ldwarialbold.png", "burweed": "ldwBurweed27.png"}
NAMES = {"arialbold": "Arial Bold (game font)", "burweed": "Burweed (game font)"}


class Exe:
    def __init__(self, path: Path) -> None:
        import pefile
        pe = pefile.PE(str(path))
        self.base = pe.OPTIONAL_HEADER.ImageBase
        self.image = pe.get_memory_mapped_image()

    def at(self, va: int, n: int) -> bytes:
        return self.image[va - self.base:va - self.base + n]

    def i32(self, va: int) -> int:
        return struct.unpack("<i", self.at(va, 4))[0]


def spacing_pushed(exe: Exe, ctor: int, table: int, sheet: str) -> int:
    """The spacing the constructor pushes just before the table and the name: `push imm8; push table;
    push name` (6A ss 68 tttttttt 68 nnnnnnnn)."""
    code = exe.at(ctor, 0x60)
    needle = b"\x68" + struct.pack("<I", table)
    at = code.find(needle)
    if at < 2 or code[at - 2] != 0x6A or code[at + 5] != 0x68:
        raise SystemExit(f"{ctor:#x}: no push of the table {table:#x}")
    name_va = struct.unpack_from("<I", code, at + 6)[0]
    name = exe.at(name_va, 32).split(b"\0")[0].decode()
    if name + ".png" != sheet:
        raise SystemExit(f"{ctor:#x}: the name pushed is {name!r}, not {sheet!r}")
    return code[at - 1]


def entries(exe: Exe, table: int) -> list[list[int]]:
    """The table as stored: {int code, left, top, right, bottom} to the first code 0."""
    out = []
    while True:
        row = list(struct.unpack("<5i", exe.at(table + 20 * len(out), 20)))
        if row[0] == 0:
            return out
        out.append(row)


def png_size(path: Path) -> list[int]:
    head = path.read_bytes()[:24]
    return list(struct.unpack(">II", head[16:24]))


def build() -> dict:
    games = {}
    for game, fonts in FONTS.items():
        exe = Exe(EXES / f"Virtual Villagers - {TITLES[game]}.exe")
        out = []
        for key, ctor, table in fonts:
            sheet = SHEETS[key]
            out.append({
                "key": key, "name": NAMES[key], "sheet": sheet,
                "spacing": spacing_pushed(exe, ctor, table, sheet),
                "sheet_size": png_size(IMAGES / f"Virtual Villagers - {TITLES[game]}" / "Images" / sheet),
                "constructor": f"0x{ctor:06X}", "table": f"0x{table:06X}",
                "entries": entries(exe, table),
            })
        games[str(game)] = out
    return {"format": FORMAT, "version": 1, "games": games}


def dump(data: dict) -> str:
    """JSON with one glyph per line, so a diff shows the glyph that changed."""
    lines = ["{", f'  "format": {json.dumps(data["format"])},', f'  "version": {data["version"]},', '  "games": {']
    games = list(data["games"].items())
    for gi, (game, fonts) in enumerate(games):
        lines.append(f'    "{game}": [')
        for fi, font in enumerate(fonts):
            lines.append("      {")
            for k in ("key", "name", "sheet", "spacing", "sheet_size", "constructor", "table"):
                lines.append(f'        "{k}": {json.dumps(font[k])},')
            lines.append('        "entries": [')
            rows = font["entries"]
            for ri, row in enumerate(rows):
                lines.append(f"          {json.dumps(row)}{',' if ri < len(rows) - 1 else ''}")
            lines.append("        ]")
            lines.append("      }" + ("," if fi < len(fonts) - 1 else ""))
        lines.append("    ]" + ("," if gi < len(games) - 1 else ""))
    lines += ["  }", "}", ""]
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    text = dump(build())
    if "--check" in argv:
        same = OUT.is_file() and OUT.read_text(encoding="utf-8") == text
        print("data/vv_font_tables.json matches the executables" if same else "data/vv_font_tables.json differs")
        return 0 if same else 1
    OUT.write_text(text, encoding="utf-8", newline="\n")
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
