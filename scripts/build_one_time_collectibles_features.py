"""Generate data/vv3_one_time_collectibles_again_feature.json and data/vv4_one_time_collectibles_again_feature.json:
"One-Time Collectibles Appear Again" (The Secret City, The Tree of Life; the owner, 2026-11-17: on in Owner's
Defaults, off everywhere else).

WHICH COLLECTIBLES APPEAR ONLY ONCE (the stock executables, research/stock-executables):
  * The Secret City: the Tablet pieces, ids 0x4C..0x57 (12).  Before a piece is put out -- by the random appearance
    (0x42D940, its roll 0x42DD6D; the test at 0x42DAF7) and by the chief's rare piece (0x42DC57) -- the game asks
    0x42D830 whether that id is "owned": for a Tablet piece, its count (the item manager + 0x10 + id x 4) above 0;
    for every other id, never.  An owned Tablet piece is refused: that appearance is lost (no retry).
  * The Tree of Life: the Mausoleum Mural pieces, ids 0x5E..0x69 (12).  The same test is 0x413C90 (callers 0x4140B4,
    the random appearance, and 0x4141DF, the ghost's): the Fish Scales, Lab Equipment and Wind Flute sets (0x46..0x51,
    0x52..0x5D, 0x6A..0x75) are never refused, any other id when its count ([ecx + id x 4 - 0x38]) is above 0.
  * A New Home has no collectibles; The Lost Children's and New Believers' pickers never ask whether a piece was found
    (their duplicates are paid as tech points).

THE PATCH.  Each test's first five bytes (`mov eax, [esp + 4]` and the next instruction's first byte) become
`xor al, al; ret 4`: no piece is ever refused, so a found Tablet or Mural piece keeps its own share of what appears
(never more: nothing is forced).  When it is picked again, the game's own duplicate path pays it (count + 1 and the
tech points for its rarity: The Secret City 0x42DF32..0x42DF79, The Tree of Life 0x41447E..0x4144F3), exactly as for
every other collection.  The ghost still never picks the Mausoleum collection itself (0x414164, its own rule).

Run after any change and re-run tests/test_one_time_collectibles.py.
"""
from __future__ import annotations

import json
from pathlib import Path

import pefile

ROOT = Path(__file__).resolve().parents[1]
STOCK = ROOT / "research" / "stock-executables"
NAME = "One-Time Collectibles Appear Again"
AFTER = "32C0C20400"    # xor al, al; ret 4

GAMES = {
    "vv3": {"exe": "Virtual Villagers - The Secret City.exe", "va": 0x42D830, "before": "8B44240483",
            "set": "Tablet", "where": "the Tablet pieces"},
    "vv4": {"exe": "Virtual Villagers - The Tree of Life.exe", "va": 0x413C90, "before": "8B4424048D",
            "set": "Mausoleum Mural", "where": "the Mausoleum Mural pieces"},
}


def description(g: dict) -> str:
    return (
        f"In the normal game each of {g['where']} appears only until it is found: once you have it, the game never "
        "puts it out again (that appearance is simply lost). With this patch a piece you already have can appear "
        "again, with the same chance as any other piece; picked up again it counts as a duplicate, which pays tech "
        "points like every other duplicate collectible. Nothing is forced: it only stops the game refusing them. "
        "**Needs no other patch.** Off by default; Owner's Defaults ticks it. **Unverified in play** (checked by "
        "emulation of the game's own test).")


def offset(pe: pefile.PE, va: int) -> int:
    return pe.get_offset_from_rva(va - pe.OPTIONAL_HEADER.ImageBase)


def feature(game: str, g: dict) -> dict:
    exe = STOCK / g["exe"]
    pe = pefile.PE(str(exe), fast_load=True)
    data = exe.read_bytes()
    at = offset(pe, g["va"])
    before = bytes.fromhex(g["before"])
    assert data[at:at + len(before)] == before, (game, data[at:at + len(before)].hex())
    return {
        "id": f"{game}_one_time_collectibles_again",
        "enabled": True,
        "catalog_enabled": True,
        "catalog_hidden": False,
        "game_id": game,
        "name": NAME,
        "description": description(g),
        "output_tag": "One-Time Collectibles Again",
        "dependencies": [],
        "conflicts": [],
        "behavior_changes": [
            f"The test whether a collectible piece is already owned (0x{g['va']:X}), asked before a piece is put out, "
            f"answers \"no\" for every id (xor al, al; ret 4), so the {g['set']} pieces, the only ones it refused, "
            "can appear again; the duplicate path pays a second one as for every other collection."
        ],
        "explicit_non_changes": [
            "Which collection and rarity is drawn, how often anything appears, the ghost's own exclusion of the "
            "Mausoleum collection (The Tree of Life), the duplicates' tech points and every other collection are "
            "unchanged.",
            "One guarded in-place edit of 5 bytes at the routine's start; no code is added and no executable space is "
            "claimed.",
        ],
        "evidence_status": ("implemented from exact-build disassembly; the test is emulated stock and patched for "
                            "every id, owned and not, in tests/test_one_time_collectibles.py; runtime/player "
                            "confirmation pending"),
        "companion_files": [],
        "patches": [{"offset": "0x%X" % at, "before": before.hex().upper(), "after": AFTER,
                     "purpose": f"the owned-piece test 0x{g['va']:X} answers never owned (xor al, al; ret 4)"}],
    }


def main() -> None:
    for game, g in GAMES.items():
        out = ROOT / "data" / f"{game}_one_time_collectibles_again_feature.json"
        out.write_text(json.dumps(feature(game, g), indent=2, ensure_ascii=False) + "\n", encoding="utf-8",
                       newline="\n")
        print("wrote", out.relative_to(ROOT))


if __name__ == "__main__":
    main()
