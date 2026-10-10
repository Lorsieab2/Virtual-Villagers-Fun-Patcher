"""Generate the five "Write Island Events Log to Text File" rows.

The owner, 2026-10-08: an island event changed one of their A New Home children's head and nothing
recorded it -- "all island event changes should be logged. Some events make villagers die,
disappear, change skills, head etc" -- "perhaps also log the title of the event too".

Companion only ("VVFP Island Events.dll", native/vvfp_island_events): "VVFP Startup.dll" loads it as
the game opens and its VvfpStartup detours, at their first instructions, the routines that apply
island events (native/vvfp_island_events/island_event_games.inc has the sites and how each was
found).  No executable byte is patched.  The records are filed by Write Births and Conceptions Log
to Text File's DLL ("VVFP Parentage Export.dll"), so that patch is needed on.  The DLL is pinned by
SHA-256, so re-run this after every rebuild (scripts/build_vvfp_island_events.ps1).
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pefile

ROOT = Path(__file__).resolve().parents[1]
DLL = ROOT / "assets" / "island_events" / "VVFP Island Events.dll"
STOCK = ROOT / "research" / "stock-executables"
EXE = {
    "vv1": "Virtual Villagers - A New Home.exe",
    "vv2": "Virtual Villagers - The Lost Children.exe",
    "vv3": "Virtual Villagers - The Secret City.exe",
    "vv4": "Virtual Villagers - The Tree of Life.exe",
    "vv5": "Virtual Villagers - New Believers.exe",
}
# The routines that apply island events, as the companion detours them (island_event_games.inc):
# their address, the stock first instruction(s) it checks and re-runs, and what each is.
SITES = {
    "vv1": [
        (0x4286B0, "6AFF689E564500", "the island event's constructor, whose chooser runs the event (and a Custom Island Event)"),
        (0x41A3D0, "837C240408", "the villager encounters' button handler (an answer applies the encounter)"),
        (0x42D050, "837C240408", "the Mysterious Crate and sea vials' button handler"),
    ],
    "vv2": [
        (0x4348E0, "6AFF682E2B4700", "the single-result island event's constructor (and a Custom Island Event)"),
        (0x422380, "6AFF68B4204700", "the two-choice event's constructor (its setup can bring a villager)"),
        (0x4222F0, "837C240408", "the two-choice event's button handler (an answer applies it)"),
        (0x438160, "B830760000", "the sacks and vials' resolve"),
        (0x44E8A0, "535556576A64", "the Gong of Wonder's outcome"),
    ],
    "vv3": [
        (0x419B30, "64A100000000", "the island event presenter: picks, shows and applies the event (a Custom Island Event too)"),
        (0x419A00, "837C240408", "the event dialog's button handler (OK applies the event)"),
    ],
    "vv4": [
        (0x418000, "6AFF681B664800", "the event presenter: picks, shows and applies the event (a Custom Island Event too)"),
        (0x418190, "6AFF685B664800", "the single-event presenter (the Origins Barrel)"),
        (0x417790, "6AFF68B9654800", "the event dialog's constructor (it names the event)"),
        (0x417EA0, "837C240408", "the event dialog's button handler (the two-choice answer clicked)"),
    ],
    "vv5": [
        (0x418870, "6AFF68DB154900", "the island event presenter: picks, shows and applies the event (a Custom Island Event too)"),
        (0x418720, "837C240408", "the event dialog's button handler (OK, or a custom event's answer, applies it)"),
    ],
}
NUMBER = {"vv1": 1, "vv2": 2, "vv3": 3, "vv4": 4, "vv5": 5}


def row(game: str, sha: str) -> dict:
    pe = pefile.PE(str(STOCK / EXE[game]))
    image = pe.get_memory_mapped_image()
    detours = []
    for va, stock, what in SITES[game]:
        have = image[va - 0x400000: va - 0x400000 + len(stock) // 2].hex().upper()
        assert have == stock, (game, hex(va), have, stock)
        detours.append({"va": f"{va:#x}", "stock_bytes": stock, "routine": what,
                        "installed_by": "VVFP Island Events.dll, VvfpStartup"})
    n = NUMBER[game]
    description = (
        "Every change an island event makes to a villager is written to a new log, the Island Events log "
        f"(\"Virtual Villagers Fun Patcher Logs\\Island Events\\Virtual Villagers {n} Island Events Log 1.txt\"): "
        "one numbered record per villager it changed, with the event's title as the game shows it, the answer "
        "you picked when it asked, and each change as old -> new -- health, age, sickness, pregnancy, head, "
        "body, name, likes, dislikes, every skill, parents, custom title, mask and Special villager title"
        + {"vv2": ", Esteemed Elder and totem", "vv3": ", and Tribal Chief", "vv5": ", faith and Heathen"}.get(game, "")
        + " -- \"Gone\" for a villager the event took away, and the sex and age of a villager it brought. "
        "What an event changes in the village as a whole -- food, tech points, "
        + {"vv1": "the berries and crops", "vv2": "the coconut trees, fish, the field's protection from birds and the crops", "vv3": "the fruit trees and honey", "vv4": "the blackberries, cutting tools and bars of soap",
           "vv5": "the noni and crops"}[game]
        + ", puzzles solved or unsolved"
        + {"vv3": " and the weather", "vv4": " and the weather", "vv5": " and the weather"}.get(game, "")
        + " -- is one record of its own, a \"Village:\" list of old -> new, and an event that "
        "changes nothing still gets its record, \"Changes: none\". A villager whose head or body an event changed "
        "also gets an \"Appearance changed\" record naming the event, so the Family Tree Maker knows the old "
        "and the new look are the same villager. The records are written when the game saves, like the other "
        "logs. **Needs Write Births and Conceptions Log to Text File: that patch's DLL writes the records.**"
        + (" **A New Home keeps a villager's parents only with Show Parents in Details Screen on: without it, "
           "parents are not logged.**" if game == "vv1" else "")
    )
    return {
        "id": f"{game}_island_events",
        "enabled": True,
        "catalog_enabled": True,
        "catalog_hidden": False,
        "game_id": game,
        "name": "Write Island Events Log to Text File",
        "description": description,
        "output_tag": "Island Events",
        "needs_on": [{"id": f"{game}_write_parentage_log",
                      "for": "the Island Events log, which that patch's DLL writes (without it nothing is written)"}],
        "behavior_changes": [
            "When an island event runs, every villager is copied just before the game applies it and compared just "
            "after; each difference is one line of the villager's \"Island event <n>\" record.",
            "The village's food, tech points, food stores, puzzles and (where the game has one) weather are read just "
            "before and just after too; what changed is one \"Island event <n>\" record with a \"Village:\" list, and an "
            "event that changes nothing is one record ending \"Changes: none\".",
            "A villager the event brings is named with its sex and its age, in game units and years "
            "(\"Age: 340 (17 years old)\").",
            "A head or body change is also an \"Appearance changed\" record in the Births and Conceptions log, "
            "ending \"Changed by: <event> (island event)\".",
            "A new village gets its Island Events log when it is made, like the other logs.",
        ],
        "explicit_non_changes": [
            "No executable byte is patched: the companion detours the routines' first instructions at run time, "
            "after verifying them, and installs nothing if any differs.",
            "The game's own routine runs unchanged, with the same registers and stack; the events, their odds and "
            "their effects are the game's own.",
            "Nothing is written without Write Births and Conceptions Log to Text File.",
        ],
        "evidence_status": ("static exact-build verification of the event routines and the villager records in each "
                            "executable; live-tested per game before release"),
        "companion_files": [
            {"source": "assets/island_events/VVFP Island Events.dll", "destination": "VVFP Island Events.dll",
             "sha256": sha},
        ],
        "runtime_detours": detours,
        "patches": [],
    }


def main() -> None:
    sha = hashlib.sha256(DLL.read_bytes()).hexdigest().upper()
    for game in SITES:
        path = ROOT / "data" / f"{game}_island_events_feature.json"
        path.write_text(json.dumps(row(game, sha), indent=2, ensure_ascii=False) + "\n", encoding="utf-8",
                        newline="\n")
        print(path.name)


if __name__ == "__main__":
    main()
