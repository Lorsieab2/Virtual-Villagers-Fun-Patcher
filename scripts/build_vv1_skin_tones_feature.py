"""Write data/vv1_skin_tones_feature.json: Skin Tones for A New Home (a DRAFT; the owner, 2026-11-06: "per villager
with inheritance", "inherited and chosen", "Try it in one game first"; the automatic recolours of draft PR #707 were
rejected -- "meh. I'll do it myself." -- so this row swaps in the owner's hand-made sheets and recolours nothing).

The behaviour lives in one companion, "VVFP Skin Tones.dll" (native/vvfp_skin_tones), started by VVFP Startup.dll
from its second word of companions.  The heads are drawn through Grey Hair at 55's engine-entry swap
(native/vv1_grey_hair), births reach it through the Origins companion's Vv1Born, conceptions through the parentage
log's conception hook.  No art is shipped: the owner's sheets go in the game's Images\\vvfp_skin\\<tone>\\ folder
(docs/skin-tones-art-guide.md).  tests/test_vv1_skin_tones.py proves it by emulation of the stock executable and,
for the per-save file and the tone rules, native/vvfp_skin_tones/skin_tone_harness.c on real files.

One command after the DLL's source changes: this script builds it (scripts/build_vvfp_skin_tones.ps1) and pins it by
SHA-256.  --no-build pins what is already built.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROW_ID = "vv1_skin_tones"
NAME = "Skin Tones (Draft)"
DLL_NAME = "VVFP Skin Tones.dll"
DLL = ROOT / "assets" / "skin_tones" / DLL_NAME
OUT = ROOT / "data" / "vv1_skin_tones_feature.json"
INSTALLED_BY = f"{DLL_NAME}, VvfpStartup (started by VVFP Startup.dll, second word)"
ORIGINS = "vv1_enable_origins_exclusive_features"
GREY_HAIR = "vv1_grey_hair"

SLOTS = {0x3DFE4: "female_bodies", 0x3DFE8: "male_bodies", 0x3DFEC: "female_actions", 0x3DFF0: "male_actions"}
REGS = {0: "eax", 1: "ecx", 2: "edx"}
ROUTINES = {"details": "the Details portrait 0x437340", "dialog": "a dialog's villager figure 0x4375F0",
            "village": "the village 0x437790", "map": "the map 0x4388E0"}

# The 35 reads of the body and action sheets (native/vvfp_skin_tones/vvfp_skin_tones.c SITES):
# (va, destination register, gameobj slot, routine).
READS = (
    (0x4373B8, 2, 0x3DFE8, "details"), (0x437441, 1, 0x3DFE4, "details"),
    (0x4374C0, 0, 0x3DFE8, "details"), (0x437513, 2, 0x3DFE4, "details"),
    (0x437679, 1, 0x3DFE8, "dialog"), (0x4376D5, 1, 0x3DFE4, "dialog"),
    (0x437723, 1, 0x3DFE8, "dialog"), (0x437744, 1, 0x3DFE4, "dialog"),
    (0x437A8E, 1, 0x3DFF0, "village"), (0x437AED, 2, 0x3DFE8, "village"),
    (0x437B2D, 2, 0x3DFF0, "village"), (0x437C62, 2, 0x3DFF0, "village"),
    (0x437D08, 2, 0x3DFEC, "village"), (0x437E38, 2, 0x3DFE8, "village"),
    (0x437F3E, 2, 0x3DFE4, "village"), (0x438210, 1, 0x3DFF0, "village"),
    (0x438286, 1, 0x3DFEC, "village"), (0x438327, 1, 0x3DFF0, "village"),
    (0x43837D, 1, 0x3DFEC, "village"), (0x43853F, 1, 0x3DFF0, "village"),
    (0x438593, 1, 0x3DFEC, "village"), (0x438723, 1, 0x3DFE8, "village"),
    (0x438777, 1, 0x3DFE4, "village"),
    (0x438A07, 0, 0x3DFF0, "map"), (0x438AAE, 1, 0x3DFF0, "map"),
    (0x438B05, 1, 0x3DFE8, "map"), (0x438B7B, 1, 0x3DFE4, "map"),
    (0x438CDC, 0, 0x3DFF0, "map"), (0x438D6A, 1, 0x3DFEC, "map"),
    (0x438E36, 0, 0x3DFF0, "map"), (0x438EA3, 0, 0x3DFEC, "map"),
    (0x439002, 0, 0x3DFF0, "map"), (0x439087, 1, 0x3DFEC, "map"),
    (0x439170, 1, 0x3DFE8, "map"), (0x4391EA, 1, 0x3DFE4, "map"),
)


def stock_bytes(reg: int, slot: int) -> str:
    """`mov reg, [esi+slot]`: 8B, mod 10 / reg / rm esi, disp32."""
    return f"8B{0x86 | (reg << 3):02X}" + slot.to_bytes(4, "little").hex().upper()


DESCRIPTION = (
    "**A draft for the owner: not for a release, and the art is not included.** "
    "**Needs Enable Origins-Exclusive Features (Change Appearance and the birth hook) and Grey Hair at 55 (which "
    "draws every head), which the patcher installs automatically with it.** "
    "**Needs Write Births and Conceptions Log to Text File on for the father's tone**: with that patch off a baby "
    "takes its mother's tone. "
    "Gives every A New Home villager a skin tone of their own. Founders, Start Over's new villagers, everyone who "
    "joins from outside and everyone already in your village when you install it get a random tone; a baby gets "
    "the tone halfway between its mother's and its father's, as they were when it was conceived (a half step "
    "toward the mother's), never a random one; twins share one. Change Appearance has a Skin tone row (with a "
    "preview, Random, Undo changes and Reset to original), and Change Appearance for All a row for every "
    "villager; a tone change costs the window's usual price and is written in the Births and Conceptions log as "
    "\"Appearance changed\". Tone 0 is the game's own art. The other tones are pictures you draw: put each "
    "tone's sheets in the game folder's Images\\vvfp_skin\\<tone>\\ folder (1, 2, 3, ...), under the game's own "
    "file names and sizes (male_heads.png, female_bodies00.png, male_actions01.png and so on, and Grey Hair's "
    "vvfp_grey_male_heads.png and vvfp_grey_female_heads.png); docs\\skin-tones-art-guide.md lists them. The "
    "number of tone folders is the number of tones (eight until the first folder exists). A sheet that is "
    "missing or not the game's size is drawn from the game's own art, so nothing breaks before the art exists. "
    "Each villager's tone is kept in 'Skin Tones - Save <slot>.dat' in the save slot's 'Virtual Villagers Fun "
    "Patcher\\Save <slot>\\Data\\Skin Tones' folder beside the saves, never in the save; it follows the villager "
    "through renames and reloads, and Start Over deletes it. **Show Parents' small parent figures and the "
    "Family Tree keep the game's own skin.** **Not yet seen in a running game** (checked by emulation of the "
    "stock executable). The companion is \"" + DLL_NAME + "\", started by VVFP Startup.dll."
)


def row(dll_sha: str) -> dict:
    return {
        "id": ROW_ID,
        "enabled": True,
        "catalog_enabled": True,
        "catalog_hidden": False,
        "game_id": "vv1",
        "name": NAME,
        "description": DESCRIPTION,
        "output_tag": "Skin Tones",
        "dependencies": [ORIGINS, GREY_HAIR],
        "behavior_changes": [
            "Every draw of a villager's body or action from male_bodies / female_bodies / male_actions / "
            "female_actions -- the 35 reads of gameobj+0x3DFE4 / +0x3DFE8 / +0x3DFEC / +0x3DFF0 in the Details "
            "portrait 0x437340, a dialog's villager figure 0x4375F0, the village 0x437790 and the map 0x4388E0 -- "
            "takes that villager's skin tone's sheet of the same name from Images\\vvfp_skin\\<tone>\\ (the same "
            "cells, built once by the game's own constructors 0x40A070 / 0x40A0F0), or the game's own sheet for "
            "tone 0 or a sheet that is missing or not the stock size.",
            "Every head is drawn through Grey Hair at 55's engine-entry swap (0x408AF0 / 0x408740), which asks this "
            "companion for the villager's tone's young or grey head sheet (Vv1SkinToneSheetFor / "
            "Vv1SkinToneGreySheetFor); Show Parents asks the same for the child it draws again over its parents.",
            "Each villager's tone is kept in 'Skin Tones - Save <slot>.dat' (the patcher's own per-save file, "
            "following the villager by name, sex and family through renames and the load's record packing; another "
            "village's file is never replaced; Start Over deletes it).",
            "A founder or an arrival -- any living villager first seen with no tone once the roster has settled, "
            "and every villager of a save the row is first installed on -- gets a random tone 0..N from the "
            "companion's own generator (never the game's rand()).",
            "A conception (the parentage log's hook, Vv1SkinToneConceived) keeps the mother's and the father's "
            "tones against the mother; a birth (the Origins birth hook's Vv1Born: live play, the load-time "
            "catch-up, Time Warp, twins and triplets, a golden-child mother's extra child, the Golden Child puzzle) "
            "gives the baby the midpoint of those tones, a half step toward the mother's, or the mother's own tone "
            "when none were kept.",
            "Change Appearance gains a Skin tone row (< name >, Random) with a preview from the owner's sheet, "
            "Undo changes and Reset to original (the tone at birth or first sight); Change Appearance for All gains "
            "a Skin tone (every villager) row: Leave as is, Random (each villager), or one tone.  A change is "
            "charged like any change and written as an \"Appearance changed\" record with \"Old skin tone\" and "
            "\"New skin tone\" lines after the mask lines.",
        ],
        "explicit_non_changes": [
            "No executable byte is patched: the companion verifies the 35 reads and the four routines' register "
            "set-ups and writes its detours at run time through the shared all-or-none writer; a different build "
            "installs nothing and every villager keeps the game's own art.",
            "Nothing is recoloured: every tone but 0 is the owner's own picture, and no picture is shipped with "
            "this row.  The game's own sheets are never changed.",
            "No villager record byte is written: the head, body and every other field stay what they were, so the "
            "logs, genetics and the Origins masks read the same values as before.",
            "Show Parents' small parent figures, the Family Tree Maker and Picture Studio keep the game's own skin.",
        ],
        "companion_files": [
            {"source": f"assets/skin_tones/{DLL_NAME}", "destination": DLL_NAME, "sha256": dll_sha},
        ],
        "patches": [],
        "runtime_detours": [
            {
                "va": f"0x{va:06X}",
                "stock_bytes": stock_bytes(reg, slot),
                "written_bytes": "E9XXXXXXXX90",
                "routine": f"{ROUTINES[where]}, the read of {SLOTS[slot]} (mov {REGS[reg]}, [esi+0x{slot:X}]): the "
                           "companion does the read itself and puts that villager's skin tone's sheet in the "
                           "register (the game's own when tone 0 or no sheet), then on at the next instruction",
                "installed_by": INSTALLED_BY,
            }
            for va, reg, slot, where in READS
        ],
    }


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def main() -> None:
    if "--no-build" not in sys.argv[1:]:
        subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                        str(ROOT / "scripts" / "build_vvfp_skin_tones.ps1")], check=True)
    OUT.write_text(json.dumps(row(sha(DLL)), indent=2) + "\n", encoding="utf-8", newline="\n")
    print("wrote", OUT.relative_to(ROOT), sha(DLL))


if __name__ == "__main__":
    main()
