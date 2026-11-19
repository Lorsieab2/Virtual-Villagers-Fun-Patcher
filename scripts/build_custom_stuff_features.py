"""Write data/vv<N>_custom_stuff_feature.json: "Custom Stuff: Your Own Names", all five games (the owner, 2026-11-19).

The row ships "VVFP Custom Names.dll" (native/vvfp_custom_names), started by VVFP Startup.dll from its second word of
companions (native/shared/startup_companions_2.h).  The player's lists are made in the patcher's Custom Stuff window
(src/vv_custom_stuff_window.py) and copied into "<game>\\Virtual Villagers Fun Patcher Files\\Custom Stuff\\" after
every build and whenever the window saves (src/vv_custom_stuff.py apply_library).  The owner's rule: custom items are
additions treated exactly like the game's own -- every first name equally likely, custom last names in the pool
wherever "VVFP Last Names.dll" draws, founders included.  On by default (it adds content; with empty lists the game
names villagers exactly as before).

One command after the DLL's source changes: this script builds it (scripts/build_vvfp_custom_names.ps1) and pins it
by SHA-256 in all five rows.  --no-build pins what is already built.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DLL_NAME = "VVFP Custom Names.dll"
DLL = ROOT / "assets" / "custom_names" / DLL_NAME
GAMES = (1, 2, 3, 4, 5)

# (naming routine, its stock first instruction, the push of the first-name roll's bound, stock bound, bound with
# Fix Vanilla Bugs) -- vvfp_custom_names.c SITES.
NAMING = {
    1: (0x43B950, "81ECC4060000", 0x43C645, 100, 101),
    2: (0x44B710, "81EC24080000", 0x44CCF1, 123, 125),
    3: (0x45C670, "81EC24070000", 0x45C677, 123, 125),
    4: (0x465DA0, "81EC9C090000", 0x465DB5, 183, 185),
    5: (0x46F680, "81EC9C090000", 0x46F695, 183, 185),
}

DESCRIPTION = (
    "Adds your own first names and last names to the game's, made in the patcher's **Custom Stuff...** window "
    "(Tools tab). Your names are additions: the game's own names always stay, and every name is treated the same. "
    "**First names:** whenever the game names a new villager, your names for that sex are in the same pool as the "
    "game's own, every name equally likely (with {stock} names of the game's and 20 of yours, each comes up 1 time "
    "in {stock_plus}). **Last names:** your last names join the game's list of 50 wherever Villagers Have Last Names "
    "draws one -- a new village's founders, \"Random last name from the list\", and (New Believers) the Heathens' "
    "family names -- every name equally likely; children then take their parents' last names by your rule as "
    "always. A name is one word, at most 10 letters (first names) or 12 (last names), with no numbers-only Roman "
    "numerals and no %; the window checks every name and says why one is refused. **On by default:** with no names "
    "of your own the game names villagers exactly as before. **Needs no other patch for first names; your last "
    "names need Villagers Have Last Names.** **Works the same with every other patch and in every population "
    "mode.** Villagers who already have names keep them; a name is the text the game saves anyway, so it stays if "
    "this patch is later removed. **Not yet seen in a running game.** The companion is \"" + DLL_NAME + "\", "
    "started by VVFP Startup.dll; your lists are copied to the game's \"Virtual Villagers Fun Patcher Files\\Custom "
    "Stuff\" folder, and saves are never written by it."
)


def row(game: int, dll_sha: str) -> dict:
    routine, prologue, bound, stock, fixed = NAMING[game]
    return {
        "id": f"vv{game}_custom_stuff",
        "enabled": True,
        "catalog_enabled": True,
        "catalog_hidden": False,
        "game_id": f"vv{game}",
        "name": "Custom Stuff: Your Own Names",
        "description": DESCRIPTION.format(stock=fixed, stock_plus=fixed + 20),
        "output_tag": "Custom Stuff",
        "dependencies": [],
        "behavior_changes": [
            f"After the naming routine 0x{routine:06X} writes a first name drawn from S of the game's names (S the "
            f"bound pushed at 0x{bound:06X}: {stock}, or {fixed} with Fix Vanilla Bugs, read at run time), the "
            "companion gives one of the player's C names for the villager's sex instead with chance C / (S + C), each "
            "equally likely, so every name is 1 in (S + C). Called by VVFP Last Names.dll's wrapper before it adds a "
            "last name; when the routine still holds its stock first instruction (Last Names not in the game) the "
            "companion detours it itself.",
            "VVFP Last Names.dll adds the player's last names to its list of 50 wherever it draws: a founder's last "
            "name is one of the player's with chance C / (50 + C) (else the family's, as before), \"Random last name "
            "from the list\" and the village rule's fallback draw from all 50 + C, and New Believers' four Heathen "
            "family names are chosen among all 50 + C.",
            "The player's lists: \"Virtual Villagers Fun Patcher Files\\Custom Stuff\\First Names - Male.txt\", "
            "\"First Names - Female.txt\" and \"Last Names.txt\" (UTF-8, one name per line), read once as the game "
            "opens; a name that is not one word, holds '%', a control byte or only Roman-numeral letters, or is longer "
            "than 10 (first) / 12 (last) bytes is skipped; one outside Windows-1252 only when the game draws UTF-8.",
        ],
        "explicit_non_changes": [
            "No executable byte is patched: the companion's only site, when it needs one, is the naming routine's first "
            "instruction, verified first (with the roll's push); otherwise nothing is installed.",
            "The game's own names, villagers who already have names, sexes, looks and families are unchanged; the save "
            "format is unchanged.",
            "A birth's last name still comes from its parents by the Last Names rule; the family number's name stays "
            "the fallback.",
        ],
        "evidence_status": "static exact-build verification of the naming routines, the first-name roll bound and "
                           "the sex field each routine reads; the companion's draw tested on its own exports "
                           "(tests/test_custom_stuff.py); runtime/player confirmation pending",
        "companion_files": [
            {"source": f"assets/custom_names/{DLL_NAME}", "destination": DLL_NAME, "sha256": dll_sha},
        ],
        "patches": [],
        "runtime_detours": [
            {"va": f"0x{routine:06X}", "stock_bytes": prologue,
             "routine": "the villager naming routine (only when VVFP Last Names.dll has not detoured it)",
             "installed_by": f"{DLL_NAME}, VvfpStartup (started by VVFP Startup.dll, second word)"},
        ],
    }


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def main() -> None:
    if "--no-build" not in sys.argv[1:]:
        subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                        str(ROOT / "scripts" / "build_vvfp_custom_names.ps1")], check=True)
    digest = sha(DLL)
    for game in GAMES:
        out = ROOT / "data" / f"vv{game}_custom_stuff_feature.json"
        out.write_text(json.dumps(row(game, digest), indent=2) + "\n", encoding="utf-8", newline="\n")
        print("wrote", out.relative_to(ROOT), digest)


if __name__ == "__main__":
    main()
