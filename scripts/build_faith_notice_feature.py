"""Generate data/vv5_heathen_conversion_notice_feature.json: "Popup When Believers Become Heathens" (New Believers,
default on).

The owner (2026-11-08), playing with Faith Loss is Doubled/Gains Halved: over a catch-up every adult believer but a
nursing mother turned Heathen and nothing said why.  "When my villagers turn into heathens due to faith decreases:
the bottom bar should say "a villager has left the tribe!" or whatever the message is" -- the stock game already
does: the to-a-Heathen routine 0x4669E0, the setter 0x467F90's only way to a Heathen, says string 0x48
eSayStoppedBelieving ("A villager has stopped believing in you!"; "A villager has left the tribe!" with the Guardians
of Isola rewrite's sm.xml) through the say bar (0x520F68, 0x44EF60) at 0x4669EC, on every conversion -- and "There
should be a popup too: (NUMBER) villagers have stopped believing in you because of: (REASONS)".

"VVFP Faith Notice.dll" (native/vvfp_faith_notice) counts the believers the Faith drift turns Heathen and the loss
rolls that did it; "VVFP Story Upgrades.dll" shows them with its island-event notice (story_faith_notice.inc).  Run
scripts/build_vvfp_faith_notice.ps1 first; this pins the DLL by SHA-256.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NOTICE_ID = "vv5_heathen_conversion_notice"
NOTICE_NAME = "Popup When Believers Become Heathens"
DLL = "VVFP Faith Notice.dll"
SOURCE = f"assets/faith_notice/{DLL}"
OUT = ROOT / "data" / "vv5_heathen_conversion_notice_feature.json"
STORY_ID = "vv5_story_cheat_upgrades"
INSTALLED_BY = f"{DLL}, VvfpStartup (started by VVFP Startup.dll, second word)"

# The five call sites the companion redirects: (va, stock bytes, what).
SITES = (
    (0x472D17, "E82453FFFF", "the life tick 0x472C90's call of the Faith drift 0x468040: the companion notes the "
                             "record, runs the drift, and counts a believer who is now a Heathen (+0x1CEC)"),
    (0x468051, "E80AB6F9FF", "the drift's food-under-10 roll, call rand 0x403660: the same rand, its answer kept"),
    (0x468071, "E8EAB5F9FF", "the drift's food-250-or-less roll, call rand 0x403660: the same rand, its answer kept"),
    (0x4680AE, "E8ADB5F9FF", "the drift's sickness roll, call rand 0x403660: the same rand, its answer kept"),
    (0x46816C, "E8EFB4F9FF", "the drift's believers roll, call rand 0x403660: the same rand, its answer and the "
                             "believers' count (edi) kept"),
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def feature() -> dict:
    description = (
        "Meant to make VV5 harder and push players to take care of their tribe. "
        "When New Believers' own Faith drift turns believers into Heathens, the game says \"A villager has stopped "
        "believing in you!\" on the bottom bar for each one (that is the game's own line; with Guardians of Isola "
        "it is \"A villager has left the tribe!\"), but after a catch-up, a Time Warp or a time skip nothing told "
        "you how many left or why. With this patch a popup in the game's own island-event window sums them up: "
        "\"The Breaking Point: Several of your villagers have lost faith due to the dire conditions amongst the tribe "
        "and have decided to join the heathens.\" and, below it, \"3 villagers have left due to starvation, 1 due to "
        "sickness and 2 due to too few believers.\" With Guardians of Isola it says the villagers have lost trust in "
        "the village's ability to provide for their needs and have decided to join the Isolans, and lists the "
        "circumstances one a line (\"Starvation: 3 villagers\", \"Food shortages\", \"Sickness\", \"Desire for a "
        "larger community\"). Each believer is counted "
        "once, under the Faith roll that took their Faith: starvation (food under 10), hunger (food 10 to 250), "
        "sickness, or too few believers (fewer than 12). It comes once no believer has left for a few seconds, so "
        "a whole catch-up or time skip is one popup; it waits until no other island event is showing or on its way "
        "and the game is running, and like every island event it needs a living adult to show it to. It is not an "
        "island event: it does not move the next island event, is not counted in Island Events Seen and is not "
        "written to the Island Events log. It counts only believers the Faith drift turns Heathen: a believer an "
        "island event makes a Heathen, and Heathens island events or the Story / Cheat Upgrades make, never bring "
        "it. A popup still waiting when you quit is kept and comes after you load that save again, once; it goes "
        "with the village on Start Over or a deleted tribe and never shows in another save. Nothing in the game is "
        "changed by it. "
        "**On by default.** **Needs Story / Cheat Upgrades (on by default) for the popup: that patch's DLL shows "
        "it.** The companion is \"VVFP Faith Notice.dll\", started by VVFP Startup.dll; saves are never written "
        "by it (the waiting popup is kept in its own file in the patcher's save folder).")
    return {
        "id": NOTICE_ID,
        "enabled": True,
        "catalog_enabled": True,
        "catalog_hidden": False,
        "game_id": "vv5",
        "name": NOTICE_NAME,
        "description": description,
        "output_tag": "Heathen Notice",
        "needs_on": [
            {
                "id": STORY_ID,
                "for": "the popup, which that patch's DLL shows (without it only the game's own bottom-bar line "
                       "is shown)",
            }
        ],
        "behavior_changes": [
            "Every believer the Faith drift 0x468040 turns Heathen (the life tick's call at 0x472D17; live, in the "
            "load-time catch-up, a Time Warp and Choose Time Skip Amount) is counted once, under the first loss roll "
            "that hit, by the executable's own thresholds: starvation -- food under 10 (rand(100) < [0x46805B], or "
            "the next roll < [0x46807B] with food under 10); hunger -- food 10 to 250 (< [0x46807B]); sickness (< "
            "[0x4680B8]); too few believers (fewer than 12: < 12 - n, or 2 x (12 - n) with Faith Loss is "
            "Doubled/Gains Halved, by the bytes at 0x468179); otherwise \"a loss of faith\".",
            "Once no conversion has come for 3 seconds, no time skip is under way, no island event popup is open, no "
            "pick, custom or island event is on its way and the game is running, VVFP Story Upgrades.dll arms one "
            "popup with its island-event notice (as the Time Skip's closing popup; the next island event keeps its "
            "time, the trigger's count is taken back, the Island Events log writes nothing): title FAITH_NOTICE_TITLE "
            "(\"The Breaking Point\"), \"Several of your villagers have lost faith due to the dire conditions amongst "
            "the tribe and have decided to join the heathens.\" (\"One of your villagers has ...\" for one) and, in a "
            "paragraph of its own, \"N villagers have left due to <reason>, M due to <reason> and K due to "
            "<reason>.\"; when the game's own string 0x48 (eSayStoppedBelieving, read at [0x5240A8 + 0x120] as "
            "0x4506D0 reads it) says \"left the tribe\" (the Guardians of Isola rewrite), \"Conditions have been dire "
            "amongst the tribe, and several villagers have been struggling to cope. They have lost trust in the "
            "village's ability to provide for their needs. Citing personal reasons, they have decided to join the "
            "Isolans.\" and \"The following circumstances contributed to their decisions:\" with one line a reason "
            "that came (\"Starvation\", \"Food shortages\", \"Sickness\", \"Desire for a larger community\", "
            "\"Loss of trust\": N villagers). The count starts again when it is armed.",
            "The bottom bar's line for each conversion is the game's own: 0x4669E0 says string 0x48 through the "
            "say bar 0x520F68 / 0x44EF60 (0x4669EC) on every conversion, with or without this patch.",
            "The batch still waiting for its popup (the total and each reason's count) is kept per save slot in "
            "<save folder>\\Virtual Villagers Fun Patcher\\Save <S>\\Data\\Faith Notice\\Waiting Popup - Save <S>.dat "
            "(native/shared/sidecar_io.h: atomic writes; a locked or unreadable file is never replaced and is read "
            "again on the gate's throttle): written when the batch changes (at most every half second, from "
            "VvfpFaithNoticeKeep, which VVFP Story Upgrades.dll calls every frame, never from inside the life tick) "
            "and deleted the moment the popup is armed, when the Story queue's own file takes it over, so a quit "
            "after the arm never shows it twice. It is read when the game's save slot is first seen and added to "
            "what the load-time catch-up has turned since, then shown by the rules above. Start Over or a deleted "
            "tribe (VvfpFaithNoticeVillageReset) forgets it in memory, and native/shared/save_reset.c deletes the "
            "slot's folder with the file; a batch is only written to, and a file only read for, its own slot.",
        ],
        "explicit_non_changes": [
            "No executable byte is patched and no Faith, villager record or save byte is written: the companion "
            "redirects five calls at run time, only after verifying every stock call and the thresholds' "
            "instructions, all or none; the drift runs exactly as before and draws the same random numbers.",
            "Island events that make a believer a Heathen (The Spa, The Cracked Mask, the Custom Island Event) show "
            "their own popup and are not counted. The popup is not an island event: it is not counted in Island "
            "Events Seen and the Island Events log writes nothing for it.",
        ],
        "companion_files": [
            {
                "source": SOURCE,
                "destination": DLL,
                "sha256": sha256(ROOT / SOURCE),
            }
        ],
        "patches": [],
        "runtime_detours": [
            {
                "va": f"0x{va:X}",
                "stock_bytes": stock,
                "written_bytes": "E8XXXXXXXX",
                "routine": what,
                "installed_by": INSTALLED_BY,
            }
            for va, stock, what in SITES
        ],
    }


def check_stock() -> None:
    """Every detour site holds its stock call in the stock executable (research/stock-executables)."""
    import pefile
    exe = ROOT / "research" / "stock-executables" / "Virtual Villagers - New Believers.exe"
    image = pefile.PE(str(exe), fast_load=True).get_memory_mapped_image()
    for va, stock, _ in SITES:
        assert image[va - 0x400000:va - 0x400000 + 5].hex().upper() == stock, hex(va)


def main() -> int:
    check_stock()
    OUT.write_text(json.dumps(feature(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    print("wrote", OUT.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
