"""Generate the two fruit-tree timing rows of The Secret City.

The owner asked for two alternative patches that the patcher never builds together:

  * "All Fruit Trees Refill at the Same Time" (vv3_fruit_trees_refill_together), and
  * "Fruit Trees Take Turns Refilling" (vv3_fruit_trees_take_turns): the refills spread
    evenly over the refill interval, so a village living on fruit waits the shortest time with
    no tree to pick.

Each is its own companion (one feature per DLL) built from native/shared/vv3_fruit_timers.h
by scripts/build_vvfp_vv3_fruit_trees.ps1, started by VVFP Startup.dll, which verifies the
stock bytes and writes its detours at run time; the rows patch no executable byte.  The save
keeps the stock per-tree timers; the schedule lives in a per-save file
(docs/vv3-fruit-tree-timing.md).  The DLLs are pinned by SHA-256, so re-run this after every
rebuild.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SIDECAR = ("Virtual Villagers Fun Patcher\\Save <S>\\Data\\Fruit Trees\\"
           "Virtual Villagers 3 Fruit Tree Timers - Save <S>.dat")
TOGETHER = "vv3_fruit_trees_refill_together"
TURNS = "vv3_fruit_trees_take_turns"
TOGETHER_NAME = "All Fruit Trees Refill at the Same Time"
TURNS_NAME = "Fruit Trees Take Turns Refilling"

COMMON_TAIL = (
    "Each tree gets the stock amount of fruit for the time since its own last refill -- the "
    "game's own formula, with Nature level 1's bonus and \"Nature Level 1 Actually Replenishes "
    "Food Sources Faster\" when it is ticked -- so over time every tree gives exactly as much "
    "fruit as in the stock game; only when the fruit comes changes. A newly planted tree still "
    "starts full and is still ready to pick after 8 hours. The island event that refills the "
    "trees is unchanged, and catch-up (the time that passes while the game is closed) and Time "
    "Warp pay the same fruit as the stock game. The save keeps every tree's own stock refill "
    "time, so without this patch the trees simply go back to their own times, with nothing lost; "
    "the patch's schedule is kept in its own file in the save's folder (" + SIDECAR + ") and "
    "Start Over deletes it."
)


def description(name: str, other: str, lead: str, companion: str, default: str) -> str:
    return (
        lead + " " + COMMON_TAIL
        + " **Cannot be ticked together with \"" + other + "\": the two give the trees different "
        "schedules, so tick only one; with both ticked the patcher builds nothing.** "
        "**Unverified in play: the effect has not been tested live.** This patch needs no other row. "
        + default + " The companion is \"" + companion + "\", started by VVFP Startup.dll; if the DLL "
        "cannot be loaded, the stock game runs."
    )


TOGETHER_LEAD = (
    "All the fruit trees refill at the same moment. In the stock game each tree has its own "
    "refill clock, started when it was planted, so the trees refill at different times. With "
    "this patch they share one: when the first tree is due to refill, every tree refills with "
    "it (a tree that was not due yet gets less fruit that once, for the shorter time), and from "
    "then on they refill together. A newly planted tree joins the others' schedule at their "
    "next refill."
)
TURNS_LEAD = (
    "The fruit trees take turns to refill, evenly spread over the refill time: with three trees "
    "one tree refills every hour (every 45 minutes at Nature level 1 with \"Nature Level 1 "
    "Actually Replenishes Food Sources Faster\"), with two trees every hour and a half. In the "
    "stock game each tree's refill clock follows when it was planted, so trees planted close "
    "together refill close together and then leave a long wait. A village that lives on fruit "
    "therefore waits the shortest time with no tree to pick: in a simulation of a hungry village "
    "(12 villagers picking, three trees, Nature 0) the longest wait was 2 hours 46 minutes with "
    "trees planted at the same time and 55 minutes with this patch, for the same fruit per day. "
    "Planting or losing a tree rearranges the turns."
)

BEHAVIOUR_COMMON = [
    "The fruit trees' update 0x434760 (vtable 0x49D1D0 slot 8, run by the world objects' update 0x435880, live and after catch-up and Time Warp): its refill loop (0x43478A..0x43481A) is replaced by the companion's pass, which goes on to the stock tail at 0x43481B (the planting-puzzle check and the removal of dead trees, 0x43487F, unchanged).",
    "The pass keeps every tree's own stock timer (record +0x28) exactly as the stock loop moves it -- set to now whenever it is at least the interval old -- so the save holds the timers the game without this patch would hold.",
    "The fruit follows the patch's schedule: each tree has the time its fruit is paid up to and the moment of its next refill. At that moment it gains floor((now - paid up to) x factor / 3600), the stock formula with the stock factor (37, or the immediate at 0x4347CE at Nature 1 or more: 42, or 56 with the Nature patch), and both move on (paid up to = now, next = now + the interval: 10,800 s, or 8,100 s at Nature 1 or more with the Nature patch, whose test at 0x4347AA the companion recognises). Every tree's fruit is held to 1,000 on every pass, as the stock loop does.",
    "A tree the companion has not seen (newly planted, or every tree of a save without a matching entry) starts from its own stock timer and joins the schedule; a removed tree leaves it (trees are matched by position, planted time and kind, so the list closing up does not mix them).",
    "Saving (0x433EC0, before the stock saver): the schedule is written to \"" + SIDECAR + "\" with an FNV-1a 64 fingerprint of the trees' saved bytes (header, records, count), the last 16 saves kept, written atomically (a temporary file moved over it). Loading (0x433E40, after the stock loader): only the entry written with exactly these trees by this same patch is used; otherwise every tree starts from its stock timer.",
]

NON_CHANGES_COMMON = [
    "This row changes no executable bytes: the companion verifies the stock bytes at its three sites (0x43478A, 0x433E40, 0x433EC0) and that the interval test and factors are the stock ones or the Nature patch's exactly, and writes its detours at run time, all together or none; a different build of the game installs nothing.",
    "The save is stock: the trees' records, their stock timers included, are written by the stock saver; without the companion the stock loop continues from those timers.",
    "No tree earns fruit faster than the stock rate: the amount is the stock formula for the time since its own last refill, and the 1,000 cap is unchanged.",
    "Planting (0x4349FD), the 8-hour growth (0x434030), the pickable checks, the island event refill (0x415AD0) and the fruit job are unchanged.",
    "Nothing is written to a villager record.",
]

DETOURS = [
    ("0x43478A", "8B466433DB", "E9XXXXXXXX",
     "the fruit trees' update (0x434760): the refill loop; the companion's pass runs instead and goes on at 0x43481B"),
    ("0x433E40", "538B5C24085556", "E9XXXXXXXX9090",
     "the trees' loader (vtable slot 3): the stock loader runs first, then the file's entry for exactly these trees restores the schedule"),
    ("0x433EC0", "8BC1837C240860", "E9XXXXXXXX9090",
     "the trees' saver (vtable slot 4): the schedule is written to the per-save file, then the stock saver runs from its start"),
]


def row(feature_id: str, name: str, other_id: str, other_name: str, lead: str, extra: list[str],
        dll: str, tag: str, default: str) -> dict:
    installed_by = dll + ", VvfpStartup"
    return {
        "id": feature_id,
        "enabled": True,
        "catalog_enabled": True,
        "catalog_hidden": False,
        "game_id": "vv3",
        "name": name,
        "description": description(name, other_name, lead, dll, default),
        "output_tag": tag,
        "dependencies": [],
        "conflicts": [other_id],
        "behavior_changes": BEHAVIOUR_COMMON + extra,
        "explicit_non_changes": NON_CHANGES_COMMON,
        "companion_files": [
            {
                "source": "assets/fruit_trees/" + dll,
                "destination": dll,
                "sha256": hashlib.sha256((ROOT / "assets" / "fruit_trees" / dll).read_bytes()).hexdigest().upper(),
            },
        ],
        "patches": [],
        "runtime_detours": [
            {"va": va, "stock_bytes": stock, "written_bytes": written, "routine": routine,
             "installed_by": installed_by}
            for va, stock, written, routine in DETOURS
        ],
    }


def main() -> None:
    rows = {
        TOGETHER: row(
            TOGETHER, TOGETHER_NAME, TURNS, TURNS_NAME, TOGETHER_LEAD,
            ["After every change the trees' next refills are laid out together: the earliest keeps its moment and every other tree's next refill is moved to it, so all refill in the same pass."],
            "VVFP VV3 Trees Refill Together.dll", "Trees Refill Together",
            "It is on by default for The Secret City (Owner's Defaults ticks \"" + TURNS_NAME + "\" instead); untick it to keep the stock game."),
        TURNS: row(
            TURNS, TURNS_NAME, TOGETHER, TOGETHER_NAME, TURNS_LEAD,
            ["After every change the trees' next refills are laid out in turns: the earliest keeps its moment and the others follow it, in the order they were due, by the interval divided by the number of trees (one hour apart with three trees and the stock interval)."],
            "VVFP VV3 Trees Take Turns.dll", "Trees Take Turns",
            "It is off by default (and Select All Patches leaves it off), because \"" + TOGETHER_NAME + "\" is on by default; untick that one first to tick this. Owner's Defaults ticks this one instead."),
    }
    for feature_id, manifest in rows.items():
        out = ROOT / "data" / (feature_id + "_feature.json")
        out.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n")
        print("wrote", out.relative_to(ROOT), manifest["companion_files"][0]["sha256"])


if __name__ == "__main__":
    main()
