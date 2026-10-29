"""Write data/vv<N>_original_look_feature.json: the original looks behind Change Appearance's "Reset to
original", all five games (the owner, 2026-10-28).

The behaviour lives in one companion, "VVFP Original Look.dll" (native/vvfp_original_look), started by VVFP
Startup.dll from its second word of companions (native/shared/startup_companions_2.h).  It writes nothing
into the game; the Reset buttons are the Origins Change Appearance windows', so each row brings the
game's Origins row with it.

One command after the DLL's source changes: this script builds it (scripts/build_vvfp_original_look.ps1) and
pins it by SHA-256 in all five rows.  --no-build pins what is already built.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DLL_NAME = "VVFP Original Look.dll"
DLL = ROOT / "assets" / "original_look" / DLL_NAME
GAMES = (1, 2, 3, 4, 5)

DESCRIPTION = (
    "Remembers each villager's original look -- the head, body and mask they had before any Change Appearance "
    "or island event changed them -- so Change Appearance and Change Appearance for All can put them back with "
    "Reset to original (the head look goes back to Auto too). Each villager's look is noted the first time "
    "the patcher sees them: when they are born or arrive, or, for a village you already have, the first time "
    "you play it with this patch; a look noted is never written over. For villagers changed before this "
    "patch, Repair Saves & Logs adds the original the patcher's logs prove -- the look before their earliest "
    "\"Appearance changed\" record -- and never guesses: when the logs cannot prove it, Change Appearance "
    "says the original look is not known. The looks are kept in the save's own Original Looks file, follow "
    "each villager (through deaths, reloads and renames) and are copied by Back Up Saves; Start Over clears "
    "them. **On by default.** **Requires the Origins-exclusive base, which the patcher installs "
    "automatically with it** (Change Appearance is there). **Works the same with every other patch and in "
    "every population mode.** **Not yet seen in a running game.** The companion is \"" + DLL_NAME + "\", "
    "started by VVFP Startup.dll; it changes nothing in the game itself. If it cannot be loaded, Change "
    "Appearance says the original look is not known."
)


def row(game: int, dll_sha: str) -> dict:
    return {
        "id": f"vv{game}_original_look",
        "enabled": True,
        "catalog_enabled": True,
        "catalog_hidden": False,
        "game_id": f"vv{game}",
        "name": "Original Looks for Reset to Original",
        "description": DESCRIPTION,
        "output_tag": "Original Looks",
        "dependencies": [f"vv{game}_enable_origins_exclusive_features"],
        "behavior_changes": [
            "Each villager's head, body and mask (the mask the Origins companion keeps, its VvfpMaskOf) are "
            "noted the first time the companion sees them, in the save's own \"Virtual Villagers Fun "
            "Patcher\\Save <S>\\Data\\Original Looks\\Original Looks - Save <S>.dat\" "
            "(native/vvfp_original_look/original_look_store.inc), and never written over. The companion looks "
            "at the villager records from the game's own thread between frames (a WH_GETMESSAGE hook on that "
            "thread and a thread timer, at most every 250 ms): a villager present when a village is bound is "
            "a first-run original, one who appears after is a born / arrived one.",
            "A village is bound only once its records have held still for 1.5 s; one whose file is missing or "
            "belongs to another village is kept in memory only until the game itself saves that slot again "
            "(so the title screen's seeded records are never written into a slot's file).",
            "Repair Saves & Logs (game closed) adds the originals the logs prove (src/vv_original_look.py): "
            "the Old head and Old body of each villager's earliest \"Appearance changed\" record, the mask "
            "before it when logged; where a change is seen with no record, the original is marked not known.",
            "Change Appearance's Reset to original reads it through VvfpOriginalLookGet "
            "(native/shared/original_look.h).",
        ],
        "explicit_non_changes": [
            "This row changes no executable bytes and writes nothing into the game's memory: no splice, no "
            "record byte; the companion only reads the villager records and the slot field.",
            "The save is never written; the Original Looks file is the patcher's own.",
            "A corrupt Original Looks file is moved aside intact and never read or written over; another "
            "village's file is never replaced on what is on screen alone.",
        ],
        "companion_files": [
            {"source": f"assets/original_look/{DLL_NAME}", "destination": DLL_NAME, "sha256": dll_sha},
        ],
        "patches": [],
    }


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def main() -> None:
    if "--no-build" not in sys.argv[1:]:
        subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                        str(ROOT / "scripts" / "build_vvfp_original_look.ps1")], check=True)
    digest = sha(DLL)
    for game in GAMES:
        out = ROOT / "data" / f"vv{game}_original_look_feature.json"
        out.write_text(json.dumps(row(game, digest), indent=2) + "\n", encoding="utf-8", newline="\n")
        print("wrote", out.relative_to(ROOT), digest)


if __name__ == "__main__":
    main()
