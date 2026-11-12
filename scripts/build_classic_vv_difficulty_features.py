"""Generate data/vv4_classic_vv_difficulty_feature.json and data/vv5_classic_vv_difficulty_feature.json: "Classic VV
Difficulty" (The Tree of Life, New Believers).

The owner (2026-11-07): "there should also be two big patches for VV4 and VV5 to give that "Classic VV Difficulty"
feel" -- then "have the classic vv difficulty on default for owner's defaults! (set the sliders to 2x." and "can you
make the text colored red for the classic vv difficulty patch titles?"

The row changes no byte itself: it needs the harder-game patches (its dependencies), so ticking it ticks them all,
the way any patch ticks what it needs; unticking one of them unticks this row too.  The patcher window draws its
title in red (vv_fun_patcher_gui.CLASSIC_DIFFICULTY_FUN_PATCH_IDS); Owner's Defaults ticks it and sets both sliders
(2-10x Tech Cost, Hungrier Villagers) to 2.  Off in the normal defaults, like every piece.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NAME = "Classic VV Difficulty"

PIECES = {
    "vv4": [("vv4_food_pays_like_earlier_games", "Food Gains are Flat, like VV1-3 (Harder Games)"),
            ("vv4_hungrier_villagers", "Hungrier Villagers (2-10x Meals)"),
            ("vv4_tech_cost_multiplier", "2-10x Tech Cost"),
            ("vv4_science_collectibles_complete", "Science Collectibles Only Count When Complete"),
            ("vv4_harder_fishing_unlock", "Harder Fishing Unlock in VV4"),
            ("vv4_collectible_spawn_like_vv3", "Collectible Spawn Timing works like VV1-3"),
            ("vv4_sickness_like_vv3", "Sickness works like VV1-3"),
            ("vv4_yellow_fruit_trees_limited", "Yellow Fruit Trees are No Longer Unlimited"),
            # The owner (2026-11-12): a member of Classic VV Difficulty in The Tree of Life and New Believers.
            ("vv4_island_events_scale_with_population", "Island Events Scale With Population (like The Lost Children)"),
            # The owner (2026-11-12): a member of each game's Classic VV Difficulty.
            ("vv4_aspiring_adventurer_event", "The Aspiring Adventurer (New Island Event)"),
            ("vv4_difficulty_settings", "Difficulty Settings")],
    "vv5": [("vv5_food_pays_like_earlier_games", "Food Gains are Flat, like VV1-3 (Harder Games)"),
            ("vv5_hungrier_villagers", "Hungrier Villagers (2-10x Meals)"),
            ("vv5_tech_cost_multiplier", "2-10x Tech Cost"),
            ("vv5_science_collectibles_complete", "Science Collectibles Only Count When Complete"),
            ("vv5_faith_loss_doubled_gains_halved", "Faith Loss is Doubled/Gains Halved"),
            ("vv5_sickness_like_vv3", "Sickness works like VV1-3"),
            ("vv5_island_events_scale_with_population", "Island Events Scale With Population (like The Lost Children)"),
            ("vv5_aspiring_adventurer_event", "The Aspiring Adventurer (New Island Event)"),
            ("vv5_difficulty_settings", "Difficulty Settings")],
}


def feature(game: str) -> dict:
    names = [name for _, name in PIECES[game]]
    listed = ", ".join(names[:-1]) + " and " + names[-1]
    return {
        "id": f"{game}_classic_vv_difficulty",
        "enabled": True,
        "catalog_enabled": True,
        "catalog_hidden": False,
        "game_id": game,
        "name": NAME,
        "description": (
            "Makes the game play as hard as the classic Virtual Villagers games; off by default. Ticking it ticks "
            f"all of these: {listed}. Set how hard with the two sliders (2-10x Tech Cost and Hungrier Villagers); "
            "Owner's Defaults sets both to 2. Unticking any of them unticks this row too, and then the rest stay "
            "as they are. This row changes nothing by itself. **Needs all of the patches it names.**"),
        "output_tag": "Classic VV Difficulty",
        "dependencies": [patch_id for patch_id, _ in PIECES[game]],
        "behavior_changes": ["None of its own: it ticks " + listed + "."],
        "explicit_non_changes": ["No executable byte, file or save is changed by this row itself."],
        "evidence_status": "a selection of other patches; each one's own evidence applies",
        "companion_files": [],
        "patches": [],
    }


def main() -> None:
    for game in PIECES:
        out = ROOT / "data" / f"{game}_classic_vv_difficulty_feature.json"
        out.write_text(json.dumps(feature(game), indent=2, ensure_ascii=False) + "\n", encoding="utf-8",
                       newline="\n")
        print("wrote", out.relative_to(ROOT))


if __name__ == "__main__":
    main()
