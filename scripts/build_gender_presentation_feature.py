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
    "give them a baby with a partner you choose. In New Believers the Heathen Mommy is the exception: whatever sex the "
    "game gives her, she always has her baby and holds it, and a Heathen Mommy who was left without it is given it "
    "at her next change of action. "
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
            "The Custom Island Event's \"presentation\" change (code 23, docs/event-collection/cie-v6-binary.md 31) "
            "sets or clears it through the same companion.",
            "The birth sex: the first sex change keeps the sex the villager was born with in the same file "
            "(VvfpBornFemale; else the save's Sex Changes log). " + CONCEPTION[game][2][0].upper()
            + CONCEPTION[game][2][1:] + " is spliced: when the game's own code makes a villager born male conceive, "
            "the conception does not happen, exactly as when the village has no room (a call from outside the "
            "executable -- the Custom Island Event's pregnancy with a partner the player chooses -- is never "
            "refused). Island events and puzzles that write a pregnancy themselves are not covered.",
        ] + ([
            "New Believers' Heathen Mommy (a Heathen, role +0x1CFC 17) is never refused: the Heathen Mommy Puzzle "
            "Restoration's new-village cave (0x494620) makes her with a random sex and then her infant through the "
            "forced conception 0x465E00, so a Mommy born male has the infant and holds it as one born female does "
            "(the carried-item draw 0x4724C3 / 0x4701C0 reads no sex). The activity stop's expecting test 0x47354C is "
            "spliced too: a living Heathen Mommy with no infant (+0x1C4C 0 -- made while the guard refused a male "
            "Mommy's, or made the Mommy by a Custom Island Event) is given it there by the cave's own call (lineage 1, "
            "skill 1, value 50, \"Unknown\", head 2, body 2, forced; one infant, the twins and triplets counters put "
            "back), so the stop hands her the baby (0x47356B, SetCarrying 0x466420 with 3) as it does every expecting "
            "Heathen.",
        ] if game == 5 else []),
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
        ] + ([
            {"va": "0x47354C", "stock_bytes": "399A4C1C0000",
             "routine": "the activity stop 0x473440's expecting test (the Heathen Mommy's infant)",
             "installed_by": f"{DLL_NAME}, VvfpStartup (started by VVFP Startup.dll, second word)"}
        ] if game == 5 else []),
    }


GC_ID = "vv1_golden_child_born_female"
GC_FLAG = "VVFP Golden Child Born Female.txt"
GC_SITE = (0x43C7FB, "C7865003000001000000")
GC_DESCRIPTION = (
    "The Golden Child may be born a girl: whenever a Golden Child comes (the puzzle at the lagoon, a "
    "Golden Child's own child, or an island event), it is a boy or a girl, 50:50 -- the game's own roll for any "
    "newborn, which it makes for the Golden Child too and then sets aside -- and the name fits. The Golden Child is "
    "still drawn as the game draws the Golden Child, the same golden boy's look, and keeps every power, the age of "
    "five and the skills. The Golden Child's words in island events follow the recorded sex (she, her, girl), the "
    "Births log records it, and the game's \"The Golden Child\" message says \"No one can doubt or deny her powers!\" "
    "for a girl. **Needs \"Change Sex and Gender Presentation\": ticking this patch ticks it too, and unticking that "
    "one unticks this one.** **On in Owner's Defaults; off in the normal defaults and in Select All.** **Not yet "
    "seen in a running game** (checked by emulation of the game's own creator code). The patch adds one small file, \""
    + GC_FLAG + "\", to the patcher's folder, which tells \"" + DLL_NAME + "\" to keep the sex; the save is never "
    "written for it."
)


def gc_row(flag_sha: str) -> dict:
    """The option inside Change Sex and Gender Presentation (A New Home): the Golden Child may be born female."""
    return {
        "id": GC_ID,
        "enabled": True,
        "catalog_enabled": True,
        "catalog_hidden": False,
        "game_id": "vv1",
        "name": "The Golden Child May Be Born Female (50:50)",
        "description": GC_DESCRIPTION,
        "output_tag": "Golden Child Born Female",
        "dependencies": ["vv1_gender_presentation"],
        "behavior_changes": [
            f"\"{DLL_NAME}\" (the vv1_gender_presentation row's companion) checks at start (VvfpStartup) whether "
            f"\"{GC_FLAG}\" is in the patcher's folder (GetFileAttributesW, by full path from the executable's own; "
            "the contents are never read), and only when its draws are installed (the Golden Child's portrait and a "
            "dialog's figure are handed \"male\", option 1).",
            "When it is, the villager creator 0x43C350's last write for the Golden Child's family 0xC7 -- `mov dword "
            "[esi+0x350], 1` at 0x43C7FB, the sex field forced to a boy -- is replaced by a call: the sex the creator "
            "drew for the newborn (the sex argument 0 every Golden Child is made with: rand(100) 0-49 a boy, 50-99 a "
            "girl, 0x43C5F1, the game's own roll, made as before) is kept, and with it the name drawn from that "
            "sex's list. Every Golden Child comes from this creator: the puzzle's drop (0x4242F8), a delivery whose "
            "family is the Golden Child's (0x42EF5F), Story / Cheat Upgrades' island event.",
            "The English \"The Golden Child\" message (message 0x14A, table entry 0x489264 in the writable data) is "
            "pointed at a copy of the game's text with \"or deny her powers!\" when a Golden Child is born a girl, and "
            "back at the game's own text (0x46F650) when one is born a boy; an entry another companion has changed "
            "(a translation) is left as it is.",
        ],
        "explicit_non_changes": [
            "No executable byte is patched: the call is written at run time, only after verifying the site holds its "
            "stock bytes.",
            "The Golden Child's look, age, skills, health and powers are the game's: only the sex field is the drawn "
            "one. A Golden Child born before the patch stays a boy.",
            "The German, Spanish and French messages are the game's.",
        ],
        "evidence_status": "the creator read statically (the sex drawn at 0x43C5F1, forced at 0x43C7FB); the call "
                           "emulated on the stock executable in tests/test_golden_child_born_female.py (the sex kept, "
                           "the message's words); runtime/player confirmation pending",
        "companion_files": [
            {"source": f"assets/gender_presentation/{GC_FLAG}", "destination": GC_FLAG, "sha256": flag_sha},
        ],
        "patches": [],
        "runtime_detours": [
            {"va": f"0x{GC_SITE[0]:06X}", "stock_bytes": GC_SITE[1],
             "routine": "the villager creator 0x43C350's Golden Child block (the sex forced to a boy)",
             "installed_by": f"{DLL_NAME}, VvfpStartup (started by VVFP Startup.dll, second word), with {GC_FLAG}"},
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
    out = ROOT / "data" / f"{GC_ID}_feature.json"
    out.write_text(json.dumps(gc_row(sha(ROOT / "assets" / "gender_presentation" / GC_FLAG)), indent=2) + "\n",
                   encoding="utf-8", newline="\n")
    print("wrote", out.relative_to(ROOT))


if __name__ == "__main__":
    main()
