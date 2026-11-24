"""Write New Believers' four Heathen aging rows (the owner, 2026-11-22) and their flag files.

* "Former Villagers Keep Aging Among the Heathens" -- "villagers-converted-heathens continue to age (only applies to
  our villagers who converted into heathens)"; off by default, on in Owner's Defaults;
* "Heathen Tribe Ages, Dies and Has Children" -- "Heathen Tribe ages, dies, has children", the puzzle Heathens too
  ("PUZZLE HEATHENS TOO (IF THEY DIE ANOTHER ONE IMMEDIATELY SPAWNS IN"); off by default, on in Owner's Defaults;
* "All Heathens Leave Skeletons" -- on in Owner's Defaults, off by default;
* "Former Villagers Among the Heathens Leave Skeletons" -- off in Owner's Defaults and by default; the two skeleton
  rows exclude each other (ticking one unticks the other).

The companion "VVFP Heathen Aging.dll" (native/vvfp_heathen_aging) is started by the start-up chain's third word;
each row ships its flag file beside it, which the companion reads once at start.  tests/test_vv5_heathen_aging.py
proves it by emulation of the stock executable.

One command after the DLL's source changes: this script builds it (scripts/build_vvfp_heathen_aging.ps1) and pins it
and the flag files by SHA-256.  --no-build pins what is already built.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DLL_NAME = "VVFP Heathen Aging.dll"
FOLDER = ROOT / "assets" / "heathen_aging"
DLL = FOLDER / DLL_NAME
INSTALLED_BY = f"{DLL_NAME}, VvfpStartup (started by VVFP More Companions.dll, third word)"

FORMER_ID = "vv5_former_villagers_keep_aging"
TRIBE_ID = "vv5_heathen_tribe_ages"
BONES_FORMER_ID = "vv5_former_villager_heathens_leave_skeletons"
BONES_ALL_ID = "vv5_all_heathens_leave_skeletons"

FORMER_NAME = "Former Villagers Keep Aging Among the Heathens"
TRIBE_NAME = "Heathen Tribe Ages, Dies and Has Children"
BONES_FORMER_NAME = "Former Villagers Among the Heathens Leave Skeletons"
BONES_ALL_NAME = "All Heathens Leave Skeletons"

FLAGS = {
    FORMER_ID: "VVFP Heathen Aging Former.txt",
    TRIBE_ID: "VVFP Heathen Aging Tribe.txt",
    BONES_FORMER_ID: "VVFP Heathen Skeletons Former.txt",
    BONES_ALL_ID: "VVFP Heathen Skeletons All.txt",
}
FLAG_WORDS = {
    FORMER_ID: "makes the villagers who left the tribe for the Heathens age and die of old age",
    TRIBE_ID: "makes every Heathen age, die of old age and be replaced, and Heathen couples have children",
    BONES_FORMER_ID: "leaves a body for the believers to bury when a former villager among the Heathens dies",
    BONES_ALL_ID: "leaves a body for the believers to bury when any Heathen dies",
}
# "Heathens can be selected in Island Events/Heathen-Exclusive Events" (vv5_heathens_in_island_events, the owner
# 2026-11-23; scripts/build_island_event_content_features.py writes that row and pins this companion and this flag in
# it): island events may kill, take away or make pregnant an ordinary Heathen, and this companion carries their
# deaths, replacements and births (VvfpHeathenAgingEventGone / VvfpHeathenAgingEventPregnancy).
EVENTS_ID = "vv5_heathens_in_island_events"
EVENTS_FLAG = "VVFP Heathen Aging Events.txt"
EVENTS_NAME = "Heathens can be selected in Island Events/Heathen-Exclusive Events"
EVENTS_WORDS = ("carries the deaths, disappearances, replacements and births island events bring to the Heathens, "
                "by the Heathens' own rules")
NAMES = {FORMER_ID: FORMER_NAME, TRIBE_ID: TRIBE_NAME, BONES_FORMER_ID: BONES_FORMER_NAME,
         BONES_ALL_ID: BONES_ALL_NAME}
TAGS = {FORMER_ID: "Former Villagers Age", TRIBE_ID: "Heathen Tribe Ages", BONES_FORMER_ID: "Former Villager Skeletons",
        BONES_ALL_ID: "Heathen Skeletons"}

# (site VA, stock bytes, what the site is)
SITES = (
    (0x470077, "389EEC1C00008BF8750C",
     "the age credit 0x46FE90's faction test `cmp byte [esi+0x1CEC], bl; mov edi, eax; jne` (the Village "
     "Statistics rows' form, `jne` 38, accepted too): a believer goes on to the stock add 0x470081; an aging "
     "Heathen gets the same units added to +0x1B8C and takes the branch the executable has there (0x47008D, or "
     "0x4700B9 past the Oldest Villager maximum with the statistics); any other Heathen that branch alone"),
    (0x472CB7, "80BEB000000000741B",
     "the life tick 0x472C90's Heathen skip `cmp byte [esi+0xB0], 0; je 0x472CDB` (esi = record + 0x1C3C): an "
     "aging Heathen with a unit due gets one unit -- the believers' old-age roll (0x472FC6..0x47304A), with the "
     "tribe row its pregnancy and birth -- its processed age +1 and the pass marked not done ([esp+0x12] = 0), "
     "then 0x473359; any other Heathen the stock skip 0x472CC0"),
)

NOT_SEEN = ("**Not yet seen in a running game** (checked by emulation of the stock executable).")
SKELETON_NOTE = ("**Only matters with \"Former Villagers Keep Aging Among the Heathens\" or \"Heathen Tribe Ages, Dies "
                 "and Has Children\" ticked**: in the normal game a Heathen never ages, so never dies of old age.")


def description(row: str) -> str:
    if row == FORMER_ID:
        return (
            "A villager who leaves your tribe and becomes a Heathen -- by losing Faith (The Breaking Point), an "
            "island event such as The Spa or The Cracked Mask, a Custom Island Event, any way at all -- keeps "
            "growing older among the Heathens, as believers do: their age goes up, their hair greys at the usual "
            "age, and they can die of old age by exactly the believers' rule (each year past 55, or later with "
            "Medicine). They still never eat, starve or fall sick: only aging and old age apply. Heathens who were "
            "never your villagers (the camp's own, the puzzle Heathens) do not age. **A former villager who dies is not "
            "replaced**, so leaving your tribe never grows the camp. **What is left when they die "
            "is decided by \"All Heathens Leave Skeletons\" or \"Former Villagers Among the Heathens Leave "
            "Skeletons\"**; with neither they simply disappear from the camp, no grave. Every death goes in the "
            "Deaths log (cause: old age). **Heathens never "
            "count in the Village Statistics.** **Villagers who left before this patch are recognised by the "
            "parents on their record** (born in your village); one who never had parents there (a founder or "
            "newcomer) is recognised only if they leave after the patch is installed. " + NOT_SEEN + " The "
            "companion is \"VVFP Heathen Aging.dll\"; it keeps its own small file per save, never writes a save."
        )
    if row == TRIBE_ID:
        return (
            "Every Heathen ages, as believers do -- the camp's Heathens, villagers who left your tribe, and the "
            "puzzle Heathens too (the Heathen Doctor, the Heathen Chief, the three Heathen Masters and the Heathen "
            "Mommy) -- and can die of old age by exactly the believers' rule. They still never eat, starve or fall "
            "sick. When a camp Heathen dies, a new one joins the camp at once in the same camp role and mask; a puzzle "
            "Heathen whose puzzle is not solved yet is replaced by a new one in the same role, set up as the game "
            "sets that role up (the Heathen Mommy with her infant), so every puzzle can still be solved; a solved "
            "puzzle's Heathen never comes back. **A villager who left your tribe is not replaced when they die**, so "
            "defections never grow the camp. Heathen couples now and then have children (about once in 20 years for "
            "each woman from 14 to 45 with a man in the camp), only while at least 10 places stay free for your own "
            "village's babies; a Heathen child grows up in the camp. **Once The Last Heathen is solved no new Heathen "
            "comes from this patch at all** -- nobody is replaced and no Heathen baby is conceived or born (a "
            "pregnancy already started waits, as in the stock game) -- so the camp empties over time; and **with no "
            "Heathen alive none is ever made**. Island events, Barrel O' Babies and the other ways the game adds "
            "Heathens work as before. **What is left when a "
            "Heathen dies is decided by \"All Heathens Leave Skeletons\" or \"Former Villagers Among the Heathens "
            "Leave Skeletons\"**; with neither they simply disappear from the camp, no grave. Deaths go in the "
            "Deaths log, each replacement in the Births log's Arrived records, and each Heathen baby's conception and birth in the Births and Conceptions log, every one marked as a Heathen. "
            "**Heathens never count in the Village Statistics.** **With \"Former Villagers Keep Aging Among the "
            "Heathens\" also ticked, this covers everyone: nobody ages twice.** " + NOT_SEEN + " The companion is "
            "\"VVFP Heathen Aging.dll\"; it keeps its own small file per save, never writes a save."
        )
    if row == BONES_FORMER_ID:
        return (
            SKELETON_NOTE + " When a villager who had left your tribe dies of old age among the Heathens, they "
            "leave a skeleton like any villager: your believers bury it with \"Burying the dead\" (once The Buried "
            "Mausoleum is solved), which gives a normal grave. Other Heathens who die leave nothing. **Cannot be "
            "ticked with \"All Heathens Leave Skeletons\"**: ticking one unticks the other. The Death record says "
            "how they died; **Heathens never count in the Village Statistics.**"
        )
    return (
        SKELETON_NOTE + " Every Heathen who dies of old age leaves a skeleton like any villager: your believers "
        "bury it with \"Burying the dead\" (once The Buried Mausoleum is solved), which gives a normal grave. A "
        "puzzle Heathen's skeleton is no longer that puzzle's Heathen: the new one is. **Cannot be ticked with "
        "\"Former Villagers Among the Heathens Leave Skeletons\"**: ticking one unticks the other. The Death record "
        "says how they died; **Heathens never count in the Village Statistics.**"
    )


AGING_CHANGES = [
    "The age credit 0x46FE90 adds a living aging Heathen's units to its age +0x1B8C, as 0x46F7F0 does for a believer "
    "(0x470077); every other Heathen as the stock game (no age).",
    "The life tick 0x472C90 gives an aging Heathen one unit for each unit of its age not yet processed (+0x1C3C), "
    "live and in the load-time catch-up (through the age credit and the life tick), and after an Origins Time Warp or "
    "a Story / Cheat Upgrades time skip, which write the ages themselves and credit the Heathens this companion "
    "ages (VvfpHeathenAgingAges): at each whole year of the processed age past 1,100 + 160 x (Medicine - 1) units (the tech "
    "level read at 0x51D5D0, as 0x423600(1) reads it), rand(100) < 10 x the years over takes them -- the believers' "
    "old-age rule (0x472FC6..0x47304A). Nothing else of a believer's unit runs: no eating, starving, sickness, "
    "health, Faith drift, job or offline job ticks.",
    "A death: with a skeleton row covering them, SetHealth 0x4758B0(0, 2 Old age) makes the body the believers' "
    "\"Burying the dead\" (0x46F130, 0x473F50) buries into the Roster of the Dead 0x464C70, as a believer's; the "
    "Village Statistics' death counter 0x51D3A0 is put back; a puzzle Heathen's body gets role 0 so the role finder "
    "0x470690 finds the new one. Otherwise the activity stops (0x473440), the selection is dropped when it is "
    "theirs (0x4653D0, 0x470800), the presence byte +0x1CD4 is cleared, health untouched, and the Cause of Death "
    "companion writes the Death record (VvfpCauseDiedAmongHeathens: Old age, \"no grave (died among the Heathens: "
    "nothing was left)\"; \"... the Isolans ...\" with the Guardians of Isola Rewrite). Its replacement's Arrived record says \"Replaced a Heathen who died of old age\" or \"... lost in an island event\" (\"Replaced an Isolan ...\" with the Guardians of Isola Rewrite).",
    "The replacement, in the same tick, by the Heathen creator 0x46FD20 (Faith 1 there, so its SetFaith never runs "
    "to-a-Heathen; the stock camp's Faith written to +0x1CF0 after: -38 - rand(30), or the dead one's own when it "
    "was one of the five easy blue Faiths -5, -9, -16, -23, -30 of 0x470E60): an ordinary Heathen in the dead one's camp "
    "role (0..11) and mask (+0x1CED orange, +0x1CEE red), age 400, random sex; a former villager (no puzzle role) "
    "never replaced, and nobody once The Last Heathen (puzzle 25) is solved (the owner, 2026-11-23); a puzzle "
    "Heathen (roles 12-17) "
    "whose puzzle (1, 16, 13, 9, 5, 17: progress 0x51E008 + 8p against 0x51DF30 + 4p) is unsolved by the stock "
    "camp's own set-up of that role (0x424AC0; the Heathen Mommy's as the restored puzzle makes her, with her "
    "infant 0x465E00 forced, its father an adult Heathen man when there is one). A full table: owed until a record "
    "is free, kept in the slot's own file (each owed replacement with its role, masks and Faith), so a quit or a "
    "Change Tribe never loses or moves it; with no Heathen alive, or once The Last Heathen is solved, it is "
    "dropped. The Cause of Death companion writes its Arrived record (VvfpCauseHeathenArrived).",
    "Who turned Heathen: a living Heathen the age credit last saw as that very believer (any path: the Faith drift, "
    "island events, The Spa, The Cracked Mask, a Custom Island Event; no call site spliced), by identity (name, likes, "
    "dislikes; carried to the new identity when the likes change in place or the name changes), kept per save slot in "
    "\"Virtual Villagers Fun Patcher\\Save <S>\\Data\\Heathen Aging\\Heathen Aging - Save <S>.dat\"; one who turned "
    "before the row by the parents on the record (+0x1BC0 / +0x1BD9).",
]
TRIBE_CHANGES = [
    "Heathen babies: an aging Heathen woman (+0x1B90 1) aged 280-900 units, not expecting, not the Heathen Mommy "
    "(role 17), with a living adult Heathen man, conceives on rand(400) == 0 each unit through 0x465E00 forced "
    "(father a random adult Heathen man), only while more than 10 records are free and The Last Heathen (puzzle 25) "
    "is unsolved; the twins and triplets counters "
    "0x51D380 / 0x51D384 are put back. 40 units later (+0x1C4C + 0x28 < processed age, the stock birth's rule), once the litter still leaves 10 records free (else the birth waits, the pregnancy kept), each "
    "baby is made by 0x46FD20 at age 40, a Heathen, with the parents' names, heads and bodies on its record "
    "(+0x1BC0, +0x1BD9, +0x1BF4..+0x1C00; the head the stock birth's rule, the parents' average +-1 on 95%), then "
    "the pregnancy and the carry (0x466420(-1)) are cleared. A pregnancy from before a woman turned Heathen, and the "
    "Heathen Mommy's infant, wait for her to rejoin the tribe, as in the stock game.",
]
AGING_NON_CHANGES = [
    "No executable byte is patched: the companion splices two sites at run time, only after verifying their stock "
    "bytes, all or none; each splice makes the very instructions it replaced.",
    "A Heathen still never eats, starves, falls sick, loses health, drifts in Faith, works or uses the work system.",
    "Heathens never count in the Village Statistics: the death counter is put back, the Oldest Villager maximum "
    "skips them where the statistics rows say so, a Heathen mother's babies are not counted.",
    "Nothing is written to a save. Without the Cause of Death companion, nothing is logged.",
]
SKELETON_CHANGES = {
    BONES_FORMER_ID: ["While this file is shipped, VVFP Heathen Aging.dll lets a former villager who dies of old "
                      "age among the Heathens leave a body (SetHealth 0x4758B0(0, 2)) for the believers' burial; "
                      "any other Heathen who dies leaves nothing."],
    BONES_ALL_ID: ["While this file is shipped, VVFP Heathen Aging.dll lets every Heathen who dies of old age leave a "
                   "body (SetHealth 0x4758B0(0, 2)) for the believers' burial; a puzzle Heathen's body gets role 0."],
}


def flag_text(row: str) -> bytes:
    name, words = (EVENTS_NAME, EVENTS_WORDS) if row == EVENTS_ID else (NAMES[row], FLAG_WORDS[row])
    return (f"Virtual Villagers Fun Patcher: \"{name}\" (New Believers).\n"
            f"While this file is here, \"{DLL_NAME}\" {words}.\n"
            "The patcher adds and removes this file with the patch; nothing reads what it says.\n").encode("ascii")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def row(row_id: str) -> dict:
    flag = FLAGS[row_id]
    files = []
    aging = row_id in (FORMER_ID, TRIBE_ID)
    if aging:
        files.append({"source": f"assets/heathen_aging/{DLL_NAME}", "destination": DLL_NAME, "sha256": sha(DLL)})
    files.append({"source": f"assets/heathen_aging/{flag}", "destination": flag, "sha256": sha(FOLDER / flag)})
    conflicts = {BONES_FORMER_ID: [BONES_ALL_ID], BONES_ALL_ID: [BONES_FORMER_ID]}.get(row_id, [])
    return {
        "id": row_id,
        "enabled": True,
        "catalog_enabled": True,
        "catalog_hidden": False,
        "game_id": "vv5",
        "name": NAMES[row_id],
        "description": description(row_id),
        "output_tag": TAGS[row_id],
        "dependencies": [],
        "conflicts": conflicts,
        "behavior_changes": (AGING_CHANGES + (TRIBE_CHANGES if row_id == TRIBE_ID else [])) if aging
        else SKELETON_CHANGES[row_id],
        "explicit_non_changes": AGING_NON_CHANGES if aging else [
            "Nothing happens unless a Heathen aging row is ticked: in the stock game no Heathen dies of old age."],
        "companion_files": files,
        "patches": [],
        "runtime_detours": [
            {"va": f"0x{va:X}", "stock_bytes": stock,
             "written_bytes": "E9XXXXXXXX"
             + "90" * (len(stock) // 2 - 5),
             "routine": what, "installed_by": INSTALLED_BY}
            for va, stock, what in SITES
        ] if aging else [],
    }


def main() -> None:
    if "--no-build" not in sys.argv[1:]:
        subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                        str(ROOT / "scripts" / "build_vvfp_heathen_aging.ps1")], check=True)
    FOLDER.mkdir(parents=True, exist_ok=True)
    for row_id, flag in FLAGS.items():
        (FOLDER / flag).write_bytes(flag_text(row_id))
    (FOLDER / EVENTS_FLAG).write_bytes(flag_text(EVENTS_ID))   # its row: build_island_event_content_features.py
    for row_id in FLAGS:
        out = ROOT / "data" / f"{row_id}_feature.json"
        out.write_text(json.dumps(row(row_id), indent=2) + "\n", encoding="utf-8", newline="\n")
        print("wrote", out.relative_to(ROOT))


if __name__ == "__main__":
    main()
