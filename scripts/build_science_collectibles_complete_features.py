"""Generate data/vv4_science_collectibles_complete_feature.json and data/vv5_science_collectibles_complete_feature.json:
"Science Collectibles Only Count When Complete" (The Tree of Life, New Believers).

The owner (2026-11-07): "Science Collectibles don't alter research gain until fully complete - you need all 12 science
collectibles to have an effect on research/tech point gain. Only affects the gains from science collectibles, fire
gain and research tech are not affected." -- then "Same for VV5."

THE STOCK BONUS.  A successful research step adds the researcher's points, then a collectible bonus, then the fire's
+1 (10.01% while it burns):
  * The Tree of Life (0x464E5D..0x464E82): owned = 0x413B90(0x52, 1, 1, 1) on 0x4CC838, the Lab Equipment pieces
    found (ids 0x52..0x5D, 12 of them; 0x413B90 counts the 12-piece set that holds the id).  If owned > 0, rand(owned)
    more (0x4036D0), i.e. 0 to owned - 1.  It is the only reader of set 0x52 apart from the collections screen
    (0x43C429).
  * New Believers (0x46DE4D..0x46DE77): owned = 0x413F50(0x50, 1, 1, 1) on 0x4DBFC8, the pieces of the second
    collectible set (ids 0x50..0x67, 24 of them: the set whose duplicates pay tech points); then rand(owned / 2)
    more (0x403660; rand(0) -- 0 or 1 owned -- is the stock call too and gives 0), i.e. 0 to owned / 2 - 1.  Its
    only other readers (0x43EB9B, 0x443B99) are screens.

THE PATCH.  The bonus counts only a complete set; with it complete the bonus is the stock one (0 to 11 in both games).
  * VV4: the 4 bytes after the count, "test eax,eax / jle +0x14", become "cmp al,12 / jne +0x14": anything but 12
    pieces skips the bonus (the count is 0..12, so al is the whole count); 12 goes on to the stock rand(12).
  * VV5: the 9 bytes "test eax,eax / je / cdq / sub eax,edx / sar eax,1" (owned / 2) become "cmp eax,24 / sete al /
    imul eax,eax,12": 12 with all 24 pieces (the stock 24 / 2), else 0, and rand(0) is the stock call's own 0.  The
    count is 0..24, so the upper bytes of eax are already 0 for sete.
The research points, the Purify Tree's glow (x3, before the bonus), the fire's +1, catch-up and every other use of the
collections (the population room, the screens, the duplicates' tech points) are unchanged.

Run after any change and re-run tests/test_science_collectibles_complete.py.
"""
from __future__ import annotations

import json
from pathlib import Path

import pefile

ROOT = Path(__file__).resolve().parents[1]
STOCK = ROOT / "research" / "stock-executables"
NAME = "Science Collectibles Only Count When Complete"

GAMES = {
    "vv4": {
        "exe": "Virtual Villagers - The Tree of Life.exe",
        "va": 0x464E6F,
        "before": "85C07E14",       # test eax,eax / jle 0x464E87
        "after": "3C0C7514",        # cmp al,12 / jne 0x464E87
        "set": "the Lab Equipment collection (12 pieces)",
        "all": 12,
        "stock": "0 to (pieces found - 1)",
    },
    "vv5": {
        "exe": "Virtual Villagers - New Believers.exe",
        "va": 0x46DE5F,
        "before": "85C0740599" "2BC2D1F8",   # test eax,eax / je 0x46DE68 / cdq / sub eax,edx / sar eax,1
        "after": "83F818" "0F94C0" "6BC00C",  # cmp eax,24 / sete al / imul eax,eax,12
        "set": "the second collectible set (24 pieces, the one whose duplicates pay tech points)",
        "all": 24,
        "stock": "0 to (half the pieces found - 1)",
    },
}


def description(g: dict) -> str:
    return (
        "**Needs no other patch.** Makes tech points come slower, so the game is harder; off by default. In the base "
        f"game every piece of {g['set']} you find makes research bring more tech points: each successful research "
        f"adds a random {g['stock']} more. With this patch those pieces add nothing until the collection is "
        f"complete: with all {g['all']} found, research gets the normal bonus (0 to 11 more). The researcher's own "
        "points, the Purify Tree's glow, the fire's extra point, the tech points a duplicate piece pays and "
        "everything else the collection does are unchanged."
    )


def offset(pe: pefile.PE, va: int) -> int:
    return pe.get_offset_from_rva(va - pe.OPTIONAL_HEADER.ImageBase)


def feature(game: str, g: dict) -> dict:
    exe = STOCK / g["exe"]
    pe = pefile.PE(str(exe), fast_load=True)
    data = exe.read_bytes()
    at = offset(pe, g["va"])
    before = bytes.fromhex(g["before"])
    assert data[at:at + len(before)] == before, (game, data[at:at + len(before)].hex())
    after = bytes.fromhex(g["after"])
    assert len(after) == len(before)
    if game == "vv4":
        changes = [
            "The research bonus (0x464E5D..0x464E82): the Lab Equipment count 0x413B90(0x52) is followed by "
            "cmp al,12 / jne (stock test eax,eax / jle), so fewer than 12 pieces add nothing and 12 add the stock "
            "rand(12), 0 to 11.",
        ]
        purpose = ("the research bonus after the Lab Equipment count (0x464E6F): skip it unless all 12 pieces are "
                   "found (stock: skip only with none)")
    else:
        changes = [
            "The research bonus (0x46DE4D..0x46DE77): the second set's count 0x413F50(0x50) becomes 12 when all 24 "
            "pieces are found and 0 otherwise (stock: the count / 2), so the bonus rand(...) is 0 to 11 with the set "
            "complete and the stock rand(0), 0, before.",
        ]
        purpose = ("the research bonus after the second set's count (0x46DE5F): 12 with all 24 pieces, else 0 "
                   "(stock: the count / 2)")
    return {
        "id": f"{game}_science_collectibles_complete",
        "enabled": True,
        "catalog_enabled": True,
        "catalog_hidden": False,
        "game_id": game,
        "name": NAME,
        "description": description(g),
        "output_tag": "Science Collectibles When Complete",
        "behavior_changes": changes,
        "explicit_non_changes": [
            "The researcher's points, the Purify Tree's glow, the fire's +1, catch-up's research, the duplicates' "
            "tech points, the population room and the collections screens are unchanged.",
            f"One guarded in-place edit of {len(after)} bytes; no code is added and no executable space is claimed.",
        ],
        "evidence_status": (
            "implemented from exact-build disassembly; the bonus for every piece count is emulated stock and patched "
            "in tests/test_science_collectibles_complete.py; runtime/player confirmation pending"),
        "companion_files": [],
        "patches": [{"offset": "0x%X" % at, "before": before.hex().upper(), "after": after.hex().upper(),
                     "purpose": purpose}],
    }


def main() -> None:
    for game, g in GAMES.items():
        out = ROOT / "data" / f"{game}_science_collectibles_complete_feature.json"
        out.write_text(json.dumps(feature(game, g), indent=2, ensure_ascii=False) + "\n", encoding="utf-8",
                       newline="\n")
        print("wrote", out.relative_to(ROOT))


if __name__ == "__main__":
    main()
