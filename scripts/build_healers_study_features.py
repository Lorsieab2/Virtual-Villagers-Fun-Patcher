"""Generate the two "Healers Study Plants Regardless of Food" rows.

The owner: "Healers study plants (VV1-VV2) or study medicine regardless of
the food supply (for VV4 and VV5, only if the Hospital is accessible/built)."
A New Home and The Lost Children skip the continue-last-activity step of
their idle scheduler when food is plentiful, so a healer studying a plant
stops; The Secret City, The Tree of Life and New Believers read no food total
on the way to medicine study (and VV4/VV5 already require the Hospital), so
they need no row.

The behaviour lives in one companion, "VVFP Healers Study.dll"
(native/vvfp_healers_study); each game's Origins companion, which runs every
frame, loads it by full path and calls VvfpHealersStudyInstall(game), which
verifies the stock bytes and writes the detour at run time.  The rows patch
no executable byte.

The DLL is pinned by SHA-256, so re-run this after every rebuild.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import sys  # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parent))
from origins_base_text import ORIGINS_BASE_SENTENCE  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DLL = ROOT / "assets" / "healers_study" / "VVFP Healers Study.dll"

ROWS = {
    "vv1": {
        "threshold": 400,
        "plant": "the plant it was dropped on (the medical cactus)",
        "site": {"va": "0x44836F", "stock_bytes": "6A00578BCEE86717FFFF",
                 "routine": "the idle scheduler's general selection (0x448220), the target of its 400-food jump"},
        "call": "0x447CD0(index, 60)",
        "catch_up": (
            "During catch-up -- the time that passes while the game is closed, "
            "and Time Warp -- A New Home already keeps a healer's plant study "
            "going by itself whenever it gives the healer healing work and no "
            "one needs healing (with Builders and Healers Work First, at least "
            "three times in four), so this patch changes nothing there."
        ),
    },
    "vv2": {
        "threshold": 300,
        "plant": "a plant (the same four-plant roll the stock game makes)",
        "site": {"va": "0x461A22", "stock_bytes": "6A00578BCEE83482FEFF",
                 "routine": "the idle scheduler's general selection (0x461850), the target of its 300-food jump"},
        "call": "0x460590(index, 40)",
        "catch_up": (
            "During catch-up -- the time that passes while the game is closed, "
            "and Time Warp -- the normal game never continues plant study at "
            "all; with this patch a villager who was studying a plant carries "
            "on there too, at any food level, about three times in four each "
            "time catch-up chooses what they do (otherwise catch-up's own choice "
            "stands)."
        ),
        "catch_up_site": {"va": "0x43B581", "stock_bytes": "5557E868460200",
                          "routine": "the catch-up worker's pick dispatch (0x43B4D0: push ebp; push edi; call 0x45FBF0)"},
    },
}


def main() -> None:
    sha = hashlib.sha256(DLL.read_bytes()).hexdigest().upper()
    for game, row in ROWS.items():
        t = row["threshold"]
        description = (
            f"Healers are more likely to keep studying plants regardless of the food "
            f"supply. A villager who was studying {row['plant']} carries on studying "
            f"when the village has {t} food or more, exactly as the stock game already "
            f"does below {t} -- about three times in four each time the game chooses "
            f"what the healer does; the rest of the time the game chooses exactly as "
            f"it always has. With Builders Fix Huts When Idle also selected, the two "
            f"share that one roll per choice. {row['catch_up']} "
            f"{ORIGINS_BASE_SENTENCE} That base's companion loads "
            f"this patch's DLL; if the DLL cannot be loaded, the stock scheduler runs "
            f"unchanged."
        )
        manifest = {
            "id": f"{game}_healers_study_regardless_of_food",
            "enabled": True,
            "catalog_enabled": True,
            "catalog_hidden": False,
            "game_id": game,
            "name": "Healers Study Plants Regardless of Food",
            "description": description,
            "output_tag": "Healers Study",
            "dependencies": [f"{game}_enable_origins_exclusive_features"],
            "behavior_changes": [
                f"At {t} food or more, a villager in plant-study state 9 gets the stock continue-last-activity call {row['call']} that the stock scheduler makes only below {t}; if it starts a job, the scheduler's own done epilogue runs.",
                "About three times in four, not always: when Builders Fix Huts When Idle is loaded the companion asks its roll for the decision (VvfpFixHutsRoll, one 75% roll per run of the idle scheduler, shared by every patch the run reaches); without it, this site -- reached at most once per run -- draws a 75% roll of its own. Neither touches the game's random numbers. When the roll fails the stock selection runs.",
            ],
            "explicit_non_changes": [
                "This row changes no executable bytes: the Origins companion loads the DLL, which detours the scheduler at run time only after verifying the stock bytes; a different build of the game installs nothing.",
                f"Below {t} food nothing changes: the stock code has already made the call.",
                "Only villagers already studying a plant (state 9, set when the player drops a villager on a plant) are affected; every other villager's selection is the stock one.",
                "What the study does -- which plant, its animation, its Healing practice -- is the game's own.",
                "Nothing is written to a villager record, the save or any file.",
            ],
            "companion_files": [
                {"source": "assets/healers_study/VVFP Healers Study.dll",
                 "destination": "VVFP Healers Study.dll", "sha256": sha},
            ],
            "patches": [],
            "runtime_detours": [{**row["site"], "installed_by": "VVFP Healers Study.dll, VvfpHealersStudyInstall"}],
        }
        if "catch_up_site" in row:
            manifest["behavior_changes"].append(
                "Catch-up (time passed while the game was closed, and Time Warp) never runs the idle scheduler: the catch-up worker (0x43B4D0) runs the task-state continuation 0x461580, whose plant-study case starts nothing, and then dispatches the picked job, whose Healing case does nothing when no one is sick. At the worker's pick dispatch (0x43B581, reached after 0x461580 as in the live scheduler), a villager in state 9 gets 0x460590(index, 40) on the same 75% roll, at any food level; if it starts a job the worker's own finish (0x43B588) runs, otherwise the pick is dispatched exactly as the stock call would, with the stock return address, so Builders and Healers Work First still recognises it. The worker's research pick (job 2) never reaches this point and is unchanged.")
            manifest["runtime_detours"].append(
                {**row["catch_up_site"], "installed_by": "VVFP Healers Study.dll, VvfpHealersStudyInstall"})
        else:
            manifest["explicit_non_changes"].append(
                "Catch-up is unchanged: A New Home's catch-up worker (0x42E790) dispatches the picked job, and the dispatcher's Healing case already continues plant study (activity 9 -> 0x443270, at 0x4478EF).")
        out = ROOT / "data" / f"{game}_healers_study_feature.json"
        out.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n")
        print("wrote", out.relative_to(ROOT), sha)


if __name__ == "__main__":
    main()
