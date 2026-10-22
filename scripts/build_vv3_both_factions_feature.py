"""Generate the "Both Factions: Nature and Magic" row (The Secret City).

The owner: buy BOTH the Faction of Nature and the Faction of Magic, both
working at once, without crashing or breaking saves.  The faction bought first
(the primary) stays in the save exactly as the stock game keeps it; the one
bought second (the secondary) is kept in a per-save file and given back at
run time by a companion of its own (docs/vv3-both-factions.md).

The behaviour lives in one companion, "VVFP VV3 Both Factions.dll"
(native/vvfp_vv3_both_factions).  The startup loader (VVFP Startup.dll) calls
its VvfpStartup(game, shipped) once at game start; the DLL verifies the stock
bytes and writes the detours at run time.  The row patches no executable byte.
The DLL is pinned by SHA-256, so re-run this after every rebuild.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DLL = ROOT / "assets" / "both_factions" / "VVFP VV3 Both Factions.dll"
OUT = ROOT / "data" / "vv3_both_factions_feature.json"
INSTALLED_BY = "VVFP VV3 Both Factions.dll, VvfpStartup"
SIDECAR = ("Virtual Villagers Fun Patcher\\Save <S>\\Data\\Factions\\"
           "Virtual Villagers 3 Second Faction - Save <S>.dat")


def main() -> None:
    sha = hashlib.sha256(DLL.read_bytes()).hexdigest().upper()
    manifest = {
        "id": "vv3_both_factions",
        "enabled": True,
        "catalog_enabled": True,
        "catalog_hidden": False,
        "game_id": "vv3",
        "name": "Both Factions: Nature and Magic",
        "description": (
            "After choosing a faction on the Tech screen, the other faction can be bought there too, "
            "at its stock price in tech points, and both work at the same time: every level of Nature "
            "(faster food, the Pitcher Plant herb, longer lives) and every level of Magic (the "
            "scientists' extra point, the Berry Plant herb, the higher population maximum), with both "
            "herbs on the island and both factions lit on the Tech screen. The faction bought first stays "
            "in the save exactly as the stock game keeps it; the second one is kept in its own file in "
            "the save's folder (" + SIDECAR + ") and comes back when that save is loaded. So every save "
            "is one the stock game loads: without this patch it loads with the first faction only, and "
            "the second faction's levels are not lost from the file. Start Over deletes the file. "
            "**Unverified in play: the effect has not been tested live.** This patch needs no other row. "
            "It is on by default for The Secret City; untick it to keep the stock game. The companion is "
            "\"VVFP VV3 Both Factions.dll\", started by VVFP Startup.dll; if the DLL cannot be loaded, "
            "the stock game runs."
        ),
        "output_tag": "Both Factions",
        "dependencies": [],
        "behavior_changes": [
            "The Tech screen purchase (0x465640) no longer answers \"You have already chosen your faction!\" (string 0x419): Magic (technology 6) can be bought while Nature (5) is above 0 (the jg at 0x4656FE becomes two nops) and Nature while Magic is above 0 (the jle at 0x465734 becomes a jmp). The second faction is bought like any technology, at its stock price (0x427020, the table at 0x4A818C) and without the faction confirmation, which the stock game asks only while both are 0.",
            "Which faction was bought second is noted as it is bought (0x4657D5, before the game's own level-up 0x426FD0).",
            "Saving (0x427D1F): after the stock copy of the seven levels into the save buffer (0x426F60), the second faction's level is written as 0 there, so the stock loader's refusal of a save with both factions (0x427060, 0x427067..0x427079) can never be met. The level is kept in \"" + SIDECAR + "\" with the save's fingerprint (FNV-1a 64 over the save buffer's first 0x6CDC bytes and the tech points), the slot, and both factions and levels; the file keeps the last 16 saves' entries and is written atomically (a temporary file moved over it).",
            "Loading (0x428A08): after the stock loader accepts the save, the entry written with exactly this save (same slot, same fingerprint, the same first faction at the same level) gives the second faction its level back through the game's own level-up 0x426FD0, as the stock loader restores every level. Any other save of the slot loads as the stock game loads it.",
            "The world draw 0x420B30 also draws the Magic herb (herb_magic.png, the Berry Plant) when it has drawn the Nature herb (herb_nature.png, the Pitcher Plant): its ret at 0x420BD5 becomes a nop. The two are separate images at separate places, and the herbs' own drop places (map regions 30 and 31, 0x421340 and 0x4213D0) and carried items (0x24 and 0x25) never read a technology.",
            "The Tech screen (0x464AE4): with both factions above 0, both columns get the sunbeam (sunbeam.png, image 0x90, at the columns' x - 0x28, full strength) and neither is darkened; with one faction or none the stock drawing runs.",
            "Every other faction reader takes its own technology and works with both: Nature 1 fruit refill (0x4347C3), Nature 3 longevity (0x4601C4), Magic 1 research point (0x4593DC), Magic 3 population maximum (0x45FE9D), the Ghostly Dream island events (0x4154F0, 0x415630), and the Tech screen's level marks and information (0x4649C0, 0x464C30).",
        ],
        "explicit_non_changes": [
            "This row changes no executable bytes: VVFP VV3 Both Factions.dll verifies the stock bytes at each place and writes its changes at run time; a different build of the game installs nothing. Everything is installed together or not at all, and the purchase last, so no village can hold both factions unless the save and load changes are in place.",
            "No save ever holds both factions: the game's save keeps the first faction only, as the stock game writes it. Without the companion, the stock game loads every save with the first faction.",
            "The first faction's purchase is stock, with its \"Are you sure?\" confirmation; prices, levels (at most 3), tech points and every other technology are unchanged.",
            "A save made with both factions by editing memory or the save file (which the stock loader refuses) is not repaired.",
            "Nothing is written to a villager record.",
        ],
        "companion_files": [
            {
                "source": "assets/both_factions/VVFP VV3 Both Factions.dll",
                "destination": "VVFP VV3 Both Factions.dll",
                "sha256": sha,
            },
        ],
        "patches": [],
        "runtime_detours": [
            {
                "va": "0x427D1F",
                "stock_bytes": "B918265800E837F2FFFF",
                "written_bytes": "E9XXXXXXXX9090909090",
                "routine": "the save (0x427C60): the copy of the seven levels into the save buffer (0x426F60); after it, a second faction is written as 0 in the buffer and kept in the per-save file with the save's fingerprint",
                "installed_by": INSTALLED_BY,
            },
            {
                "va": "0x428A08",
                "stock_bytes": "B918265800E84EE6FFFF",
                "written_bytes": "E9XXXXXXXX9090909090",
                "routine": "the load (0x428880): the stock level loader (0x427060); after it accepts the save, the file's entry with this save's fingerprint gives the second faction its level back (0x426FD0)",
                "installed_by": INSTALLED_BY,
            },
            {
                "va": "0x4657D5",
                "stock_bytes": "56B918265800E8F017FCFF",
                "written_bytes": "E9XXXXXXXX909090909090",
                "routine": "the Tech screen purchase (0x465640): the level-up of the technology bought; a faction bought while the other is above 0 is noted as the second faction",
                "installed_by": INSTALLED_BY,
            },
            {
                "va": "0x464AE4",
                "stock_bytes": "8B87D400000083F8FF",
                "written_bytes": "E9XXXXXXXX90909090",
                "routine": "the Tech screen draw (0x4649C0): the chosen faction's sunbeam and the other column's shade; with both factions both get the sunbeam and neither is shaded (on to 0x464BE1)",
                "installed_by": INSTALLED_BY,
            },
            {
                "va": "0x420BD5",
                "stock_bytes": "C3",
                "written_bytes": "90",
                "routine": "the world draw (0x420B30): the return after the Nature herb; the Magic herb is then drawn too (checked with the push 6 after it, C36A06)",
                "installed_by": INSTALLED_BY,
            },
            {
                "va": "0x4656FE",
                "stock_bytes": "7F36",
                "written_bytes": "9090",
                "routine": "the Tech screen purchase (0x465640): Magic refused while Nature is above 0 (jg 0x465736, \"You have already chosen your faction!\"); written last with 0x465734",
                "installed_by": INSTALLED_BY,
            },
            {
                "va": "0x465734",
                "stock_bytes": "7ECA",
                "written_bytes": "EBCA",
                "routine": "the Tech screen purchase (0x465640): Nature allowed only while Magic is 0 (jle 0x465700); written last",
                "installed_by": INSTALLED_BY,
            },
        ],
    }
    OUT.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n")
    print("wrote", OUT.relative_to(ROOT), sha)


if __name__ == "__main__":
    main()
