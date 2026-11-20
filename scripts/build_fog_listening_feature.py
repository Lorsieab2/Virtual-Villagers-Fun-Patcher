"""Write New Believers' "Fog of Doom Lets Red and Orange Heathens Listen" row (the owner, 2026-11-19: "the Fog of Doom can allow
villagers to be dropped on red/yellow heathens to convert them like they can the blue ones"; "for heathens, they work
only when the heathen's faith is lower than -10. at -10 or above only the Earthquake power can convert them"; the drop
starts the game's own listening, which raises Faith as for a blue Heathen; only the cast Fog of Doom God Power, never
natural weather; off by default, on in Owner's Defaults, as every new option).

The companion "VVFP Fog Listening.dll" (native/vvfp_fog_listening) splices the drop handler's mask test at run time.
tests/test_vv5_fog_listening.py proves it by emulation of the stock executable.

One command after the DLL's source changes: this script builds it (scripts/build_vvfp_fog_listening.ps1) and pins it
by SHA-256.  --no-build pins what is already built.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROW_ID = "vv5_fog_of_doom_every_heathen_listens"
NAME = "Fog of Doom Lets Red and Orange Heathens Listen"
DLL_NAME = "VVFP Fog Listening.dll"
DLL = ROOT / "assets" / "fog_listening" / DLL_NAME
OUT = ROOT / "data" / f"{ROW_ID}_feature.json"
INSTALLED_BY = f"{DLL_NAME}, VvfpStartup (started by VVFP More Companions.dll, third word)"

SITE = (0x443D4D, "389EED1C00000F85D4020000389EEE1C00000F85C8020000",
        "the drop handler 0x443BF0's mask test (an adult dropped on a Heathen who is not the Heathen Doctor): `cmp "
        "byte [esi+0x1CED], bl / jne 0x44402D / cmp byte [esi+0x1CEE], bl / jne 0x44402D`. A Heathen in neither mask "
        "goes on at 0x443D65 as before; one in the orange or red mask goes on at 0x443D65 (the stock listening path) "
        "when the game's thick-fog test 0x476260 on the weather 0x710948 answers yes and the Heathen's Faith "
        "(+0x1CF0) is below -10, else at 0x44402D (the stock end of the drop)")


def description() -> str:
    return (
        "**Needs the Fog of Doom God Power** (400 Divine Energy). While the Fog of Doom's thick fog is over the "
        "island, you can drop a believer of 14 or more on a Heathen in an orange or red mask, and they listen just "
        "as a blue-masked Heathen does: the believer is \"Explaining the truth\", and when the believer's Devotion "
        "check passes the Heathen is \"Listening\" and their Faith rises by 3 (4 at Devotion 50 or more, 5 at 88 "
        "or more); then they cannot be preached to for 2 real-life hours, as in the normal game. **Only a Heathen "
        "whose Faith is below -10 listens.** **From Faith -10 up, only the Earthquake God Power reaches them** (as "
        "in the normal game, it raises every Heathen's Faith by 2 to 8). The first time one of a village's "
        "Heathens turns a drop away for this, a popup (in the game's own popup window with its OK, no title) "
        "says \"The fog hides you, but <name> still won't listen. Something stronger may stir them.\" (with "
        "Guardians of Isola Rewrite: \"... <name> is still wary. Perhaps another approach may convince them.\"): "
        "once per village, never again there even after quitting, until Start Over begins a new village. **Needs "
        "Story / Cheat Upgrades (on by default) for the popup: that patch's DLL shows it, when no other popup or "
        "island event is showing or on its way.** A Heathen joins the tribe the normal "
        "game's way, when their Faith rises above 0. **Only the Fog of Doom God Power counts: natural fog, a "
        "Tempest and every other weather do nothing.** Blue-masked Heathens are unchanged (they already listen in "
        "the normal game). The Chief, purple-masked Heathens and the Heathen Mommy are puzzle Heathens and never listen this way. **Works the same with every other patch and in every "
        "population mode.** **Not yet seen in a running game** (checked by emulation of the stock executable). "
        "The companion is \"VVFP Fog Listening.dll\"; it never writes a save, only one small file in the save's "
        "own patcher folder that marks the message as shown."
    )


def row(dll_sha: str) -> dict:
    va, stock, what = SITE
    return {
        "id": ROW_ID,
        "enabled": True,
        "catalog_enabled": True,
        "catalog_hidden": False,
        "game_id": "vv5",
        "name": NAME,
        "description": description(),
        "output_tag": "Fog Listening",
        "dependencies": [],
        "behavior_changes": [
            "The drop handler 0x443BF0: an adult (age 280 age units or more) dropped on a Heathen (+0x1CEC) who is "
            "not the Heathen Doctor (role 12) and wears the orange (+0x1CED) or red (+0x1CEE) mask, which the stock "
            "game turns away at 0x44402D, is given the stock blue-mask path 0x443D65 -- the Heathen action 6 "
            "(\"Waiting for someone\"), the dropped villager action 0x27 (\"Explaining the truth\") -- when the "
            "weather 0x710948's thick-fog test 0x476260 answers yes (fog on, +0x500C, and thickness +0x5010 at "
            "least 2: only the Fog of Doom God Power, 0x41FB60, sets it to 4; every fog starts at 1, 0x475EDC) and "
            "the Heathen's Faith (+0x1CF0) is below -10.",
            "The sermon's end is the stock work event 0x468DA0, unchanged: roles 12-17 refuse, the 2-hour wait "
            "(+0x1CF4) refuses, the preacher's Devotion check 0x46B270(5); on success the Heathen's action 0x29 "
            "(\"Listening\"), the wait set, Faith +3 (+1 at Devotion 50, +1 more at 88) through 0x468020, and the "
            "Faith setter 0x467F90's own conversion 0x4668B0 above 0.",
            "The notice: when the thick-fog test answers yes and the Faith limit turns an orange or red Heathen away "
            "(without vv5_fog_of_doom_no_restrictions), no notice is waiting, and the slot's file \"Virtual Villagers "
            "Fun Patcher\\Save <S>\\Data\\Fog of Doom\\Fog of Doom Notice - Save <S>.dat\" "
            "(native/shared/per_save_data.h; the slot from the save manager [0x4DACE0]+0x17D80) is not there, a "
            "notice is kept waiting with the Heathen's whole name (+0x1B9C, long_name.h). \"VVFP Story Upgrades.dll\" "
            "(story_fog_notice.inc) asks VvfpFogNoticePending every frame and shows it as Popup When Believers Become "
            "Heathens' popup is shown (story_notice_arm: the island-event notice, armed only when the event slot is "
            "free and the game's trigger shows it at once; not counted, not logged, the next island event keeps its "
            "time), with no title (an empty title string; New Believers draws the title apart from the text), "
            "with the owner's words through VVFP Translations.dll (the Guardians of "
            "Isola words when the game's string 0x48 says \"left the tribe\"); once armed, VvfpFogNoticeTaken makes "
            "the file. Start Over deletes the save's folder (native/shared/save_reset.c) and VvfpStoryVillageReset "
            "drops a waiting notice (VvfpFogNoticeVillageReset), so a new village is told again; a waiting notice of "
            "another slot is dropped.",
        ],
        "needs_on": [
            {"id": "vv5_story_cheat_upgrades",
             "for": "the popup, which that patch's DLL shows (without it the drop is still turned away, with no "
                    "popup)"},
        ],
        "explicit_non_changes": [
            "No executable byte is patched: the companion splices the one site at run time, only after verifying its "
            "stock bytes; registers and flags are as they were at both places it goes on.",
            "The Earthquake God Power (0x41F6E0) is unchanged: it already raises every living villager's Faith by 2 "
            "to 8 but the six special roles, Heathens of every mask included (0x41F79F), so from Faith -10 up it is "
            "the one way left to a Heathen in the orange or red mask.",
            "Blue-masked Heathens, the drop's other branches, the work event's odds, Faith and wait, the "
            "conversion, logs, last names, masks and statistics are the game's own (and the other patches' own).",
            "Nothing is written to a save or a villager record; the one file is the notice's mark.",
        ],
        "companion_files": [
            {"source": f"assets/fog_listening/{DLL_NAME}", "destination": DLL_NAME, "sha256": dll_sha},
        ],
        "patches": [],
        "runtime_detours": [
            {"va": f"0x{va:X}", "stock_bytes": stock, "written_bytes": "E9XXXXXXXX" + "90" * (len(stock) // 2 - 5),
             "routine": what, "installed_by": INSTALLED_BY},
        ],
    }


# No Restrictions on Fog of Doom Conversions (the owner, 2026-11-19; off by default and in Select All; on in Owner's
# Defaults: the owner, 2026-11-20): the same companion, told by the row's one file in the patcher's folder,
# drops the Faith condition.
FREE_ID = "vv5_fog_of_doom_no_restrictions"
FREE_NAME = "No Restrictions on Fog of Doom Conversions"
FREE_FLAG = "VVFP Fog Listening No Restrictions.txt"
FREE_FILE = ROOT / "assets" / "fog_listening" / FREE_FLAG
FREE_OUT = ROOT / "data" / f"{FREE_ID}_feature.json"
# The owner's own text, word for word.
FREE_OWNER_TEXT = (
    "No restrictions on Fog of Doom Conversions: red and yellow heathens can be talked to, and the -10 faith limit "
    "requiring Earthquakes is removed. Those heathens can now be talked to like any other blue heathen and eventually "
    "converted, as long as Fog of Doom is active.")


def free_description() -> str:
    return (
        f"**Needs \"{NAME}\": ticking this patch ticks it too, and unticking that one unticks this one.** "
        + FREE_OWNER_TEXT + " (\"Yellow\" is the game's orange mask.) Natural fog and every other weather still do "
        "nothing; the listening, the Faith it gives and the conversion are the normal game's, as for a blue-masked "
        "Heathen. The Chief, purple-masked Heathens and the Heathen Mommy are puzzle Heathens and never listen this way. **Off by default; on in Owner's Defaults; off in Select All.** **Not yet seen in a running game** (checked by emulation of the stock "
        f"executable). The patch adds one small file, \"{FREE_FLAG}\", to the patcher's folder, which tells "
        f"\"{DLL_NAME}\" to leave out the Faith limit."
    )


def free_row(flag_sha: str) -> dict:
    return {
        "id": FREE_ID,
        "enabled": True,
        "catalog_enabled": True,
        "catalog_hidden": False,
        "game_id": "vv5",
        "name": FREE_NAME,
        "description": free_description(),
        "output_tag": "Fog Listening No Restrictions",
        "dependencies": [ROW_ID],
        "behavior_changes": [
            f"With its file \"{FREE_FLAG}\" in the patcher's folder when the game starts, \"{DLL_NAME}\" "
            "(read once, at its VvfpStartup) leaves out the Faith condition: a Heathen in the orange or red mask "
            "takes the stock listening path 0x443D65 whenever the game's thick-fog test 0x476260 answers yes, "
            "whatever their Faith (+0x1CF0).",
        ],
        "explicit_non_changes": [
            "Natural fog, a Tempest and every other weather still never count: the thick-fog test is unchanged.",
            "The work event 0x468DA0 (roles 12-17, the 2-hour wait, the Devotion check, Faith +3 to +5) and the "
            "conversion are the game's own; the Earthquake is unchanged.",
            "No code of its own and no executable byte: the file is all the row ships.",
        ],
        "companion_files": [
            {"source": f"assets/fog_listening/{FREE_FLAG}", "destination": FREE_FLAG, "sha256": flag_sha},
        ],
        "patches": [],
    }


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def main() -> None:
    if "--no-build" not in sys.argv[1:]:
        subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                        str(ROOT / "scripts" / "build_vvfp_fog_listening.ps1")], check=True)
    OUT.write_text(json.dumps(row(sha(DLL)), indent=2) + "\n", encoding="utf-8", newline="\n")
    print("wrote", OUT.relative_to(ROOT))
    FREE_OUT.write_text(json.dumps(free_row(sha(FREE_FILE)), indent=2) + "\n", encoding="utf-8", newline="\n")
    print("wrote", FREE_OUT.relative_to(ROOT))


if __name__ == "__main__":
    main()
