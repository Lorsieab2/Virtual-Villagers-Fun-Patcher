"""Write data/vv<N>_gender_presentation_feature.json: "Change Sex and Gender Presentation", all five games (the owner,
2026-11-15).

The row ships "VVFP Gender Presentation.dll" (native/vvfp_gender_presentation), started by VVFP Startup.dll from its
second word of companions (native/shared/startup_companions_2.h).  With it in the game, each game's Change Appearance
window (the Origins companion's) offers "Change sex..." and the "Gender presentation: use the other sex's look"
checkbox (native/shared/gender_presentation.h); without it both are hidden.  On in Owner's Defaults only.

One command after the DLL's source changes: this script builds it (scripts/build_vvfp_gender_presentation.ps1) and
pins it by SHA-256 in all five rows.  --no-build pins what is already built.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from origins_base_text import ORIGINS_BASE_SENTENCE  # noqa: E402

DLL_NAME = "VVFP Gender Presentation.dll"
DLL = ROOT / "assets" / "gender_presentation" / DLL_NAME
SOURCE = ROOT / "native" / "vvfp_gender_presentation" / "vvfp_gender_presentation.c"
GAMES = (1, 2, 3, 4, 5)

# Each game's conception routine and the site the companion splices in it (vvfp_gender_presentation.c CONCEPTION).
CONCEPTION = {
    1: (0x43BBC3, "E8D8E5FFFF", "the room check of the conception routine 0x43BBC0"),
    2: (0x44B983, "E888F9FFFF", "the room check of the conception routine 0x44B980"),
    3: (0x455AB8, "E873A30000", "the room check of the conception routine 0x455AB0"),
    4: (0x45E7B0, "538A5C2420", "the entry of the conception routine 0x45E7B0"),
    5: (0x465E00, "538A5C2420", "the entry of the conception routine 0x465E00"),
}

# The draw routines each game's sites are in (the DLL's SITES comments; tests/test_gender_presentation.py).
ROUTINES = {
    1: "the Villager Details portrait 0x437340, a dialog's figure 0x4375F0, the village 0x437790 and the map 0x4388E0",
    2: "the Villager Details portrait 0x445540, a villager's strip figure 0x445950, the village 0x445B50 and the map "
       "0x4478E0",
    3: "the Villager Details portrait 0x4568E0, a villager's figure 0x456CA0 and the village 0x4605F0",
    4: "the villager figure 0x45F550, the portrait 0x45F7C0 and the village 0x467DA0",
    5: "the villager figure 0x466C40, the portrait 0x466EF0 and the village 0x4720E0",
}

DESCRIPTION = (
    "Adds two choices to the per-villager Change Appearance window. **Change sex...** changes the sex the game keeps "
    "for the villager (the same head and body rows; a carrying parent goes on carrying), made at once after a "
    "warning; everything the patcher keeps for the villager follows them. **Gender presentation: use the other sex's "
    "look** keeps the villager's recorded sex and draws them with the other sex's heads and bodies (the same rows) "
    "everywhere the game draws villagers: the village, the map, Villager Details and the island event pictures. The "
    "preview shows it at once; OK keeps it, Cancel and Undo changes do not; it is free. Neither is offered for the "
    "Golden Child, and story villagers keep the game's own look. The choice is kept in the save's own Gender "
    "Presentation file and follows each villager (through deaths, reloads, renames and a sex change); Back Up Saves "
    "copies it and Start Over clears it. Custom Island Events can set or clear it too (the \"presentation\" change). "
    "**Only villagers born female carry:** one born female who changed to male goes on carrying; one born male never "
    "conceives on their own, even after changing to female (Change sex says so), but a Custom Island Event can still "
    "give them a baby with a partner you choose. "
    "**On in Owner's Defaults; off in the normal defaults and in Select All.** Change Appearance is in the Origins "
    "upgrades: " + ORIGINS_BASE_SENTENCE + " **Works the same with every other patch and in every population mode.** "
    "**Not yet seen in a running game** (checked by emulation of each game's own draw code). The companion is \""
    + DLL_NAME + "\", started by VVFP Startup.dll; the save and the sex field are never written for the presentation."
)


def sites(game: int) -> list[tuple[int, str]]:
    """(va, stock bytes) of each site, read from the DLL's own table."""
    text = SOURCE.read_text(encoding="utf-8")
    body = text[text.index(f"static const gp_site VV{game}_SITES[] = {{"):]
    body = body[:body.index("};")]
    return [(int(m.group(1), 16), "".join(f"{int(x, 16):02X}" for x in m.group(2).split(",")))
            for m in re.finditer(r"\{ 0x([0-9A-F]+)u, \d, GP_\w+, R_\w+, R_\w+, \w+, \{ ([^}]*) \} \}", body)]


def row(game: int, dll_sha: str) -> dict:
    return {
        "id": f"vv{game}_gender_presentation",
        "enabled": True,
        "catalog_enabled": True,
        "catalog_hidden": False,
        "game_id": f"vv{game}",
        "name": "Change Sex and Gender Presentation",
        "description": DESCRIPTION,
        "output_tag": "Gender Presentation",
        "dependencies": [f"vv{game}_enable_origins_exclusive_features"],
        "behavior_changes": [
            "Change Appearance (the Origins companion's window) shows \"Change sex...\" and the checkbox \"Gender "
            "presentation: use the other sex's look\" only with this row's companion in the game "
            "(native/shared/gender_presentation.h); never for the Golden Child.",
            "Every read of the villager sex field inside " + ROUTINES[game] + " is spliced to the companion, which "
            "hands the game the villager's drawn sex: the other value when the villager's gender presentation is on, "
            "the field's own otherwise (a special villager, or anything that is not a villager record, always the "
            "field). Each routine then draws the villager exactly as it draws one of the other sex with the same head "
            "and body rows; nothing else that reads the sex (breeding, names, pronouns, sounds, statistics, the "
            "companions) changes.",
            "The choice is kept in \"Virtual Villagers Fun Patcher\\Save <S>\\Data\\Gender Presentation\\Gender "
            "Presentation - Save <S>.dat\" (the Head Looks' file shape, native/vvfp_head_look/head_look_store.inc, "
            "magic 'VGP1'), following each villager; Start Over deletes it (native/shared/save_reset.c).",
            "The Custom Island Event's \"presentation\" change (code 23, docs/event-collection/cie-v6-binary.md 29) "
            "sets or clears it through the same companion.",
            "The birth sex: the first sex change keeps the sex the villager was born with in the same file "
            "(VvfpBornFemale; else the save's Sex Changes log). " + CONCEPTION[game][2][0].upper()
            + CONCEPTION[game][2][1:] + " is spliced: when the game's own code makes a villager born male conceive, "
            "the conception does not happen, exactly as when the village has no room (a call from outside the "
            "executable -- the Custom Island Event's pregnancy with a partner the player chooses -- is never "
            "refused). Island events and puzzles that write a pregnancy themselves are not covered.",
        ],
        "explicit_non_changes": [
            "No executable byte is patched: the companion splices the reads at run time, only after verifying every "
            "one holds its stock bytes; all are written or none (a different build installs none, and then the "
            "checkbox is not offered).",
            "The villager record is never written for the presentation: the sex field, head and body rows stay.",
            "Change Appearance for All is not changed.",
        ],
        "evidence_status": "each game's draw routines read statically (every sex read in them is a site); the splices "
                           "emulated on the stock and rendered executables in tests/test_gender_presentation.py (the "
                           "registers and flags after each read equal the stock read of the other sex); runtime/player "
                           "confirmation pending",
        "companion_files": [
            {"source": f"assets/gender_presentation/{DLL_NAME}", "destination": DLL_NAME, "sha256": dll_sha},
        ],
        "patches": [],
        "runtime_detours": [
            {"va": f"0x{va:06X}", "stock_bytes": stock,
             "routine": "a read of the villager sex field in a villager draw routine",
             "installed_by": f"{DLL_NAME}, VvfpStartup (started by VVFP Startup.dll, second word)"}
            for va, stock in sites(game)
        ] + [
            {"va": f"0x{CONCEPTION[game][0]:06X}", "stock_bytes": CONCEPTION[game][1], "routine": CONCEPTION[game][2],
             "installed_by": f"{DLL_NAME}, VvfpStartup (started by VVFP Startup.dll, second word)"}
        ],
    }


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def main() -> None:
    if "--no-build" not in sys.argv[1:]:
        subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                        str(ROOT / "scripts" / "build_vvfp_gender_presentation.ps1")], check=True)
    digest = sha(DLL)
    for game in GAMES:
        out = ROOT / "data" / f"vv{game}_gender_presentation_feature.json"
        out.write_text(json.dumps(row(game, digest), indent=2) + "\n", encoding="utf-8", newline="\n")
        print("wrote", out.relative_to(ROOT), digest)


if __name__ == "__main__":
    main()
