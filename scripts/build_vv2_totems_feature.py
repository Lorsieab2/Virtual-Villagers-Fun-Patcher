"""Generate the "Esteemed Elders' Totems Use No Villager Records" row (The Lost Children).

The owner (2026-10-19): an Esteemed Elder's totem is a movable decoration, not one of the 256
villager records.  Companion only ("VVFP VV2 Totems.dll", native/vvfp_vv2_totems): "VVFP
Startup.dll" loads it as the game opens and its VvfpStartup verifies and detours the sites below.
No executable byte is patched.  The DLL is pinned by SHA-256, so re-run this after every rebuild
(scripts/build_vvfp_vv2_totems.ps1).
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pefile

ROOT = Path(__file__).resolve().parents[1]
DLL = ROOT / "assets" / "vv2_totems" / "VVFP VV2 Totems.dll"
STOCK = ROOT / "research" / "stock-executables" / "Virtual Villagers - The Lost Children.exe"
OUT = ROOT / "data" / "vv2_totems_out_of_entries_feature.json"

# (va, bytes replaced, what it is) -- native/vvfp_vv2_totems/vvfp_vv2_totems.c SITES.
SITES = (
    (0x4249A0, 5, "the slot load (thiscall manager, slot): after a village loads, ElderTotems.dat is read and "
                  "every totem statue record (Is Totem +0x558 set, health 0 or less) is moved into the store "
                  "and its record freed as the burial frees one (0x46503B)"),
    (0x424BA0, 6, "the slot save (thiscall manager, slot): before a village slot is written, the store is "
                  "written to ElderTotems.dat (a temporary file, then a move); a save that could not write "
                  "it is refused"),
    (0x424C80, 7, "the world reset (new tribe, Start Over, the startup's seeding): the store is emptied"),
    (0x44D190, 5, "the Esteemed Elder's totem maker: the statue goes into the store, never into a record"),
    (0x44D4D1, 9, "the elder pass's first 'fewer than 50 totems' check: no limit while the store works"),
    (0x44D54C, 5, "the elder pass's second 'fewer than 50 totems' check (after the full-village guard's "
                  "count): no limit while the store works"),
    (0x445C1C, 9, "the village draw loop's start: store totems drawn in the game's y order among the records"),
    (0x4478CD, 13, "the village draw loop's end: the rest, and a totem being dragged last"),
    (0x4490BB, 5, "the Map's end: store totems drawn as the Map draws a totem"),
    (0x431071, 5, "the click's hit test (0x44D580): a store totem in front of the record found is picked"),
    (0x431076, 9, "after the hit test: a picked store totem ends the click (no camera drag, no other action)"),
    (0x4308D0, 7, "the village mouse handler: a picked store totem is dragged and placed as a totem record is"),
    (0x429A83, 5, "the name panel with no record selected: \"<name>`s totem\" for a picked store totem"),
    (0x44D4C0, 9, "the Esteemed Elder pass's entry: after it runs, with the village's give-automatically setting "
                  "on, every Esteemed Elder record still without a totem is given one in the store"),
)


def row(sha: str) -> dict:
    image = pefile.PE(str(STOCK)).get_memory_mapped_image()
    detours = []
    for va, n, what in SITES:
        detours.append({
            "va": f"{va:#X}".replace("0X", "0x"),
            "stock_bytes": image[va - 0x400000: va - 0x400000 + n].hex().upper(),
            "routine": what,
            "installed_by": "VVFP VV2 Totems.dll, VvfpStartup",
        })
    return {
        "id": "vv2_totems_out_of_entries",
        "enabled": True,
        "catalog_enabled": True,
        "catalog_hidden": False,
        "game_id": "vv2",
        "name": "Esteemed Elders' Totems Use No Villager Records",
        "description": (
            "In the stock game every Esteemed Elder's totem statue takes one of the village's 256 villager "
            "records for good, so in a big village the statues crowd out babies waiting to be born. With this "
            "patch the totems are kept apart, in a file beside each save "
            "('Virtual Villagers Fun Patcher\\Save <n>\\Data\\Elder Totems\\ElderTotems.dat'), and take no "
            "villager record: when a village loads, every totem in it moves into that file and its record is "
            "free for a villager. The totems look, sort, show their \"<name>`s totem\" label and can be "
            "dragged and placed exactly as before, on the village and on the Map. There is no longer a limit "
            "of 50 Esteemed Elders. **The stock game never reads ElderTotems.dat: before removing this patch, "
            "use Repair Saves & Logs > \"Put Totems Back Into the Save\" (with the game closed), or the "
            "village shows no totems (nothing else changes).** Repair Saves & Logs can also move totems out "
            "with the game closed (\"Move Totems Out of the Save\") and change an elder's totem colour. With "
            "the village's \"Give Esteemed Elders their totems automatically\" setting on (Repair Saves & Logs), "
            "an Esteemed Elder without a totem is given one automatically, during play -- when the village loads "
            "and after every elder check the game makes -- and so is an elder who has passed away without one "
            "(listed by Check or Repair Saves & Logs, given at the next load); an elder who may already have a "
            "totem (the same looks, or the same first name) is left for Repair Saves & Logs to ask about. **Unverified in play: this has not been tested in the "
            "running game yet.** **Needs no other patch.**"
        ),
        "output_tag": "Totems Out of Records",
        "dependencies": [],
        "behavior_changes": [
            "A totem statue record in a loaded village (Is Totem +0x558 set and health 0 or less) is moved into "
            "ElderTotems.dat and its record freed; a villager with the mark but health above 0 is never moved.",
            "A new Esteemed Elder's totem (0x44D190) is kept in ElderTotems.dat with everything the game copies "
            "onto it; the elder is marked and counted by the game's own pass, as before.",
            "No limit of 50 totems: the elder pass's two checks (0x44D4D1, 0x44D54C) never wait while the "
            "store works; the full-village guard's wait no longer applies to totems, which need no record.",
            "Store totems are drawn with the game's own calls in the game's own y order, on the village and on "
            "the Map; a click picks one in front of the villager the game found; the name panel shows "
            "\"<name>`s totem\"; dragging, the dust, the totem puzzle spot (terrain 0x42), the nudge off "
            "unfit ground and the stored home x/y are as the game does them for a totem record.",
            "ElderTotems.dat is written before each save of the slot and read after each load; one bound to "
            "another village is moved aside, never used or overwritten.",
            "With the village's give-automatically setting on (Elder Totem Settings.dat), after each load and "
            "each elder pass (0x44D4C0, detoured at its entry) every Esteemed Elder record (+0x7FC) with no "
            "totem of the same name and looks, or of a recorded rename, is given one as 0x44D190 makes it; the "
            "passed-away elders the patcher lists in PendingElderTotems.dat are given one at the next load and "
            "taken off the list. A near match (the same looks, or the same first name) makes nothing.",
        ],
        "explicit_non_changes": [
            "No executable byte is patched: the companion verifies every site's stock bytes and installs all "
            "of them or none; a different build of the game installs nothing.",
            "The .ldw save stays the stock game's own format: it simply holds no totem records.",
            "If ElderTotems.dat exists but cannot be opened, that session runs as the stock game (nothing is "
            "moved, and the game's own 50-totem limit stands).",
            "Village Statistics, the logs and the family tree never counted totems as villagers and still "
            "do not.",
        ],
        "evidence_status": ("static exact-build verification of every site and emulator tests of each hook "
                            "against the stock executable; runtime/player confirmation pending"),
        "companion_files": [
            {"source": "assets/vv2_totems/VVFP VV2 Totems.dll", "destination": "VVFP VV2 Totems.dll",
             "sha256": sha},
        ],
        "runtime_detours": detours,
        "patches": [],
    }


def main() -> None:
    sha = hashlib.sha256(DLL.read_bytes()).hexdigest().upper()
    OUT.write_text(json.dumps(row(sha), indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    print(OUT.name, sha)


if __name__ == "__main__":
    main()
