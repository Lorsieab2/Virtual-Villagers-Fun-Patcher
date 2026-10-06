"""Generate the five "Villagers Have Last Names" rows.

Every Virtual Villagers game carries a third list of 50 names beside the male
and female first names -- the list Virtual Villagers 6 and 7 later used for
villagers' last names -- which each game's naming routine copies and never
reads.  The owner: new villagers get their family's last name (the family
number 1-50 the game keeps on every villager, inherited from the mother);
villagers who already have names keep them.

Companion only ("VVFP Last Names.dll", native/vvfp_last_names): "VVFP
Startup.dll" loads it as the game opens and its VvfpStartup detours the
naming routine (see the source for the sites).  No executable byte is
patched.  The DLL is pinned by SHA-256, so re-run this after every rebuild
(scripts/build_vvfp_last_names.ps1).
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pefile

ROOT = Path(__file__).resolve().parents[1]
DLL = ROOT / "assets" / "last_names" / "VVFP Last Names.dll"
STOCK = ROOT / "research" / "stock-executables"
EXE = {
    "vv1": "Virtual Villagers - A New Home.exe",
    "vv2": "Virtual Villagers - The Lost Children.exe",
    "vv3": "Virtual Villagers - The Secret City.exe",
    "vv4": "Virtual Villagers - The Tree of Life.exe",
    "vv5": "Virtual Villagers - New Believers.exe",
}
# The naming routine, its first instruction, and the unused list it copies.
SITES = {
    "vv1": (0x43B950, 0x481BA0, "the villager name builder (thiscall array, index, out), called by the creator and the twin path"),
    "vv2": (0x44B710, 0x48FB98, "the villager name builder (thiscall array, index, out), called by the creator and the twin path"),
    "vv3": (0x45C670, 0x49DFF8, "the villager naming routine (thiscall villager, family)"),
    "vv4": (0x465DA0, 0x4AA930, "the villager naming routine (thiscall villager, family)"),
    "vv5": (0x46F680, 0x4B8450, "the villager naming routine (thiscall villager, family)"),
}
ROOM = {"vv1": 27, "vv2": 23, "vv3": 23, "vv4": 23, "vv5": 23}


def names(image: bytes, va: int) -> list[str]:
    at = va - 0x400000
    return [n.decode("ascii") for n in image[at:image.index(b"\0", at)].split(b",") if n]


def row(game: str, sha: str) -> dict:
    routine, last_list, what = SITES[game]
    pe = pefile.PE(str(STOCK / EXE[game]))
    image = pe.get_memory_mapped_image()
    last = names(image, last_list)
    assert len(last) == 50, (game, len(last))
    stock = image[routine - 0x400000: routine - 0x400000 + 6]
    assert stock[:2] == b"\x81\xEC", (game, stock.hex())
    examples = ", ".join(last[:3])
    description = (
        "Every new villager gets a last name after their first name, from the game's own list of 50 "
        f"last names ({examples} ... {last[-1]}) -- a list the game has always carried but never used, and "
        "the one Virtual Villagers 6 and 7 later used for villagers' last names. The last name is the "
        "family's: the game already gives every villager a family number from 1 to 50, and a baby takes "
        "its mother's, so children share their mother's last name. Only villagers named from now on get "
        "one: villagers who already have names keep them. The last "
        "name is part of the name the game stores, so it shows wherever the name does and stays in the save "
        "even if this patch is later removed."
        + (" The Golden Child, whose family is not one of the 50, gets no last name." if game == "vv1" else "")
        + " **Needs no other patch.**"
    )
    return {
        "id": f"{game}_last_names",
        "enabled": True,
        "catalog_enabled": True,
        "catalog_hidden": False,
        "game_id": game,
        "name": "Villagers Have Last Names",
        "description": description,
        "output_tag": "Last Names",
        "behavior_changes": [
            "A villager named by the game from now on is called \"<first name> <last name>\": the first name is "
            "the game's own pick, and the last name is name number <family - 1> of the game's unused third "
            f"list ({last_list:#X}), read from the running executable.",
            "A villager whose family is outside 1-50 gets no last name.",
            f"The whole name always fits the game's own name field: the longest pairing is far below its {ROOM[game]} "
            "characters.",
        ],
        "explicit_non_changes": [
            "No executable byte is patched: the companion detours the naming routine's first instruction at "
            "run time, after verifying it and the routine's push of the list, and changes nothing if either "
            "differs.",
            "Villagers who already have names keep them; nothing is renamed when a village is loaded.",
            "The first names, sexes, looks and families are the game's own; the save format is unchanged.",
        ],
        "evidence_status": ("static exact-build verification of the naming routines, their callers and the "
                            "unused list in each executable; runtime/player confirmation pending"),
        "companion_files": [
            {"source": "assets/last_names/VVFP Last Names.dll", "destination": "VVFP Last Names.dll", "sha256": sha},
        ],
        "runtime_detours": [
            {
                "va": f"{routine:#X}".replace("0X", "0x"),
                "stock_bytes": stock.hex().upper(),
                "routine": what,
                "installed_by": "VVFP Last Names.dll, VvfpStartup",
            }
        ],
        "patches": [],
    }


def main() -> None:
    sha = hashlib.sha256(DLL.read_bytes()).hexdigest().upper()
    for game in SITES:
        path = ROOT / "data" / f"{game}_last_names_feature.json"
        path.write_text(json.dumps(row(game, sha), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(path.name)


if __name__ == "__main__":
    main()
