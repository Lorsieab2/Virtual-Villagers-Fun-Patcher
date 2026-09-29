"""Generate data/vv1_misc_text_fixes_feature.json -- Misc Text Fixes (A New Home).

The owner's corrections, made on a dump of the game's own string table
(sub_433970, 629 entries of id + English/German/French/Spanish pointers at
0x487208).  Each edit replaces one ENGLISH text in place: the new text and
its terminator must fit in the original text plus the zero padding after it,
which is checked here against the stock executable, and the text must be
referenced by its table slot alone (no code and no other pointer reads it
or its padding).  Nothing moves; the other languages are untouched.

Each patch is guarded by its exact stock bytes, text plus padding.
"""
from __future__ import annotations

import json
import struct
from pathlib import Path

import pefile

ROOT = Path(__file__).resolve().parents[1]
STOCK = ROOT / "research" / "stock-executables" / "Virtual Villagers - A New Home.exe"
OUT = ROOT / "data" / "vv1_misc_text_fixes_feature.json"
TABLE_VA = 0x487208
TABLE_ENTRIES = 0x275

# (string id, stock English, corrected English) -- the owner's edits.
EDITS = [
    (3, "This villager improved at farming", "This villager improved at farming."),
    (15, "The villager has improved at breeding.", "The villager has improved at parenting."),
    (21, "Food available to villagers.", "Food available to villagers"),
    (218, "Breeding", "Parenting"),
    (319, None, None),   # the Fish of Fertility popup: "breeding!" -> "parenting!"
    (477, "breeding", "parenting"),
]


def main() -> None:
    pe = pefile.PE(str(STOCK), fast_load=True)
    data = STOCK.read_bytes()
    base = pe.OPTIONAL_HEADER.ImageBase

    def off(va: int) -> int:
        return pe.get_offset_from_rva(va - base)

    table = {}
    for i in range(TABLE_ENTRIES):
        sid, english = struct.unpack_from("<2I", data, off(TABLE_VA + i * 20))
        table[sid] = english

    patches = []
    for sid, old, new in EDITS:
        va = table[sid]
        start = off(va)
        end = data.index(b"\0", start)
        stock = data[start:end].decode("latin-1")
        if sid == 319:
            old = stock
            if stock.count("success at breeding!") != 1:
                raise SystemExit("string 319 no longer holds 'success at breeding!'")
            new = stock.replace("success at breeding!", "success at parenting!")
        if stock != old:
            raise SystemExit(f"string {sid} is not the expected stock text: {stock!r}")
        slack = 0
        while data[end + 1 + slack] == 0:
            slack += 1
        room = len(stock) + 1 + slack
        encoded = new.encode("latin-1") + b"\0"
        if len(encoded) > room:
            raise SystemExit(f"string {sid}: {len(encoded)} bytes do not fit in {room}")
        # Only the table slot may point at the text, and nothing into its padding.
        if data.count(struct.pack("<I", va)) != 1:
            raise SystemExit(f"string {sid} is referenced outside its table slot")
        for k in range(1, room):
            if data.count(struct.pack("<I", va + k)):
                raise SystemExit(f"string {sid}: something points inside it at +{k}")
        before = data[start:start + room]
        after = encoded + b"\0" * (room - len(encoded))
        patches.append({
            "offset": f"0x{start:X}",
            "before": before.hex().upper(),
            "after": after.hex().upper(),
            "purpose": f"string {sid}: {old!r} -> {new!r}, in place (text + {slack} padding byte(s))",
        })

    manifest = {
        "id": "vv1_misc_text_fixes",
        "enabled": True,
        "catalog_enabled": True,
        "catalog_hidden": False,
        "game_id": "vv1",
        "name": "Misc Text Fixes",
        "description": (
            "Corrects a handful of A New Home's English texts: \"breeding\" becomes "
            "\"parenting\" wherever the game names the skill (the skill name, the "
            "improvement message and the Fish of Fertility popup), \"This villager "
            "improved at farming\" gains its full stop, and \"Food available to "
            "villagers\" loses its stray full stop."
        ),
        "output_tag": "Text Fixes",
        "behavior_changes": [p["purpose"] for p in patches],
        "explicit_non_changes": [
            "Only English texts in the game's string table change, each in place within its own storage; no pointer moves and the German, French and Spanish texts are untouched.",
            "No game logic changes.",
        ],
        "patches": patches,
    }
    OUT.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n")
    print("wrote", OUT.relative_to(ROOT), len(patches), "edits")


if __name__ == "__main__":
    main()
