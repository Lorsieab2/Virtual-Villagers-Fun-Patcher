"""Write data/vv<N>_village_solidarity_feature.json: "Village Solidarity", all five games (the owner, 2026-11-17).

The row ships "VVFP Village Solidarity.dll" (native/vvfp_village_solidarity), started by VVFP Startup.dll from its
second word.  The village's 0-100 score (kept outside the save) is moved by the new events' pages tagged "solidarity"
(raise / lower / neutral, src/vv_cie_graph.py) and changes ONLY the odds of the patcher's own events and endings
(native/vvfp_story_upgrades asks the companion's factor).  Its strength is the row's slider (0.1x to 10x, 1 the
normal strength), written beside the DLL as "VVFP Village Solidarity.txt" (src/vv_village_scores.py).  The Tech
screen shows "Village Solidarity: 62 / 100".  Off by default and in Select All; on in Owner's Defaults.

One command after the DLL's source changes: this script builds it (scripts/build_vvfp_village_solidarity.ps1) and
pins it in the five rows (--no-build: pin the DLL as it is).
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import vv_village_scores as scores  # noqa: E402

GAMES = (1, 2, 3, 4, 5)
DLL_NAME = scores.SOLIDARITY_DLL
DLL = ROOT / "assets" / "village_solidarity" / DLL_NAME
NATIVE = ROOT / "native" / "vvfp_village_solidarity"

DESCRIPTION = (
    "Gives each village a **Village Solidarity** score from 0 to 100, starting at 50. The patcher's new island events "
    "(the Isola Grand Event Collection, the Companion Anthology, More Island Events and your own Custom Island "
    "Events) can mark a page as raising, lowering or not changing it: songs and gatherings, fair resolutions, mutual "
    "aid, welcoming newcomers and feelings like happiness, trust, gratitude and hope raise it; unresolved conflicts, "
    "unfairness, broken promises and feelings like tension, distrust, resentment and fear lower it; solemn "
    "remembrance and quiet reflection leave it as it is. Every raise and every lower moves it by the same "
    f"{scores.STEP} points. **The score only changes odds:** the higher it is, the more likely the new cooperative "
    "and celebration events and the cooperative endings of a chance split; the lower it is, the more likely the new "
    "repair, peace and apology events and the tense endings (at the normal strength each point away from 50 adds 2% "
    "to the favoured event's or ending's own chance weight, so 0 or 100 doubles it; nothing is ever forced and "
    "nothing else is made less likely). It never changes work, helping, idling, skills or health, and the game's "
    "own island events and their chances never change. The slider sets the strength, 0.1x to 10x (1x is normal). "
    "The Tech screen shows \"Village Solidarity: 62 / 100\" in the game's own font; the Game Mechanics page shows it "
    "too. The score is kept outside the save, in the save's own Village Scores file, and every change is written to "
    "the save's Village Solidarity log; Start Over clears both. Without this patch the events' marks are only words "
    "in their files. **Needs Story / Cheat Upgrades (on by default), which runs the new events; ticking this ticks "
    "it.** **The score moves only when new events with marked pages happen: tick the Isola Grand Event Collection "
    "or More Island Events, or write your own Custom Island Events.** **Works the same in every population mode.** "
    "**On in Owner's Defaults; off in the normal defaults and in Select All.** The companion is \"" + DLL_NAME
    + "\", started by VVFP Startup.dll; the save is never written."
)


# Each game's Tech screen splice (native/vvfp_village_solidarity/counter_vv<N>.inc; pinned against the stock
# executables by tests/test_village_solidarity_counter_*.py): (va, stock bytes, what).
COUNTER_SITES: dict[int, list[tuple[int, str, str]]] = {
    1: [(0x43401B, "8B8E24010000", "the Tech screen draw 0x433B20, where its text widgets are drawn")],
    2: [(0x441D2B, "8B8E24010000", "the Tech screen draw 0x441830, where its text widgets are drawn")],
    3: [(0x464C1D, "5F5E83C424C3", "the Tech screen draw 0x4649C0, its return")],
    4: [(0x43E87E, "5F5E5D5B83C418C3", "the Tech screen draw 0x43E640, its return")],
    5: [(0x44121C, "5E5D5B83C428C3", "the Tech screen draw 0x440F80, its return")],
}


def counter_sites(game: int) -> list[tuple[int, str, str]]:
    """(va, stock bytes, what) of each Tech screen splice the companion makes in `game`."""
    sites = COUNTER_SITES.get(game, [])
    text = (NATIVE / f"counter_vv{game}.inc").read_text(encoding="utf-8")
    for va, _stock, _what in sites:
        if f"0x{va:08X}u" not in text and f"0x{va:06X}" not in text:
            raise SystemExit(f"counter_vv{game}.inc does not name its site 0x{va:06X}")
    return sites


def row(game: int, dll_sha: str) -> dict:
    sites = counter_sites(game)
    return {
        "id": f"vv{game}{scores.SOLIDARITY_ROW_SUFFIX}",
        "enabled": True,
        "catalog_enabled": True,
        "catalog_hidden": False,
        "game_id": f"vv{game}",
        "name": scores.SOLIDARITY_NAME,
        "description": DESCRIPTION,
        "output_tag": scores.SOLIDARITY_NAME,
        "dependencies": [f"vv{game}_story_cheat_upgrades"],
        "behavior_changes": [
            "The village's Village Solidarity score (0..100, 50 at the start) is kept in \"Virtual Villagers Fun "
            "Patcher\\Save <S>\\Data\\Village Scores\\Village Scores - Save <S>.txt\" (one line per score, written "
            "atomically: native/shared/sidecar_io.h); each change is appended to \"...Save <S>\\Logs\\Village "
            "Solidarity\\Village Solidarity Log.txt\" (append-only, rolling on at 512 KB; the same words in all five "
            "games). Start Over deletes the save's folder with both (native/shared/save_reset.c).",
            "Story / Cheat Upgrades (native/vvfp_story_upgrades/story_graph.inc) asks the companion "
            "(VvfpVillageScoreTag) when a branching event reaches a page tagged \"solidarity\" (the .cieg node "
            "flags' bits 1-2: 1 raise, 2 lower, 3 neutral): raise +" + str(scores.STEP) + ", lower -"
            + str(scores.STEP) + ", neutral 0, clamped to 0..100.",
            "At a weighted chance split, a branch whose next page is tagged \"raise\" (a cooperative ending) has its "
            "weight multiplied by the companion's factor for a high score, one tagged \"lower\" (a tense ending) by "
            "the factor for a low score (VvfpVillageScoreFactor, per mille: 1000 + 2 x the strength in tenths x the "
            "score's distance from 50 on that side, else 1000).",
            "The rare collection draw after a natural island event (story_collection.inc) multiplies a collection "
            "event's draw weight the same way when its manifest marks it \"cooperative\" (a high score) or "
            "\"repair\" (a low score); every other candidate keeps its weight.",
        ] + ([
            "The Tech screen draw is spliced to show \"Village Solidarity: <score> / 100\" in the game's own font "
            "(translated through VVFP Translations.dll): native/vvfp_village_solidarity/counter_vv" + str(game)
            + ".inc."
        ] if sites else []),
        "explicit_non_changes": [
            "The game's own island events and their chances never change: the Story companion's rare roll is the "
            "only draw the factor touches, and it is never in place of a natural event.",
            "Nothing changes work, helping, idling, skills, health, food or tech: real effects of an event stay "
            "exactly as the event gives them.",
            "Nothing is written to the save or to a villager record; " + (
                "the Tech screen splices are made at run time only after every site holds its stock bytes, all or "
                "none." if sites else "no game code is spliced."),
        ],
        "evidence_status": "the score file, the moves, the clamp and the factor emulated in "
                           "tests/test_village_solidarity.py; the story engine's tag and odds hooks emulated in the "
                           "same file; runtime/player confirmation pending",
        "companion_files": [
            {"source": f"assets/village_solidarity/{DLL_NAME}", "destination": DLL_NAME, "sha256": dll_sha},
        ],
        "patches": [],
        "runtime_detours": [
            {"va": f"0x{va:06X}", "stock_bytes": stock, "routine": what,
             "installed_by": f"{DLL_NAME}, VvfpStartup (started by VVFP Startup.dll, second word)"}
            for va, stock, what in sites
        ],
    }


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def main() -> None:
    if "--no-build" not in sys.argv[1:]:
        subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                        str(ROOT / "scripts" / "build_vvfp_village_solidarity.ps1")], check=True)
    digest = sha(DLL)
    for game in GAMES:
        out = ROOT / "data" / f"vv{game}{scores.SOLIDARITY_ROW_SUFFIX}_feature.json"
        out.write_text(json.dumps(row(game, digest), indent=2) + "\n", encoding="utf-8", newline="\n")
        print("wrote", out.relative_to(ROOT), digest)


if __name__ == "__main__":
    main()
