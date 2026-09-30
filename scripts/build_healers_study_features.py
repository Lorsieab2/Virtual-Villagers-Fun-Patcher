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
    },
    "vv2": {
        "threshold": 300,
        "plant": "a plant (the same four-plant roll the stock game makes)",
        "site": {"va": "0x461A22", "stock_bytes": "6A00578BCEE83482FEFF",
                 "routine": "the idle scheduler's general selection (0x461850), the target of its 300-food jump"},
        "call": "0x460590(index, 40)",
    },
}


def main() -> None:
    sha = hashlib.sha256(DLL.read_bytes()).hexdigest().upper()
    for game, row in ROWS.items():
        t = row["threshold"]
        description = (
            f"Healers keep studying plants regardless of the food supply. A villager "
            f"who was studying {row['plant']} carries on studying when the village has "
            f"{t} food or more, exactly as the stock game already does below {t}; "
            f"plentiful food no longer makes a healer stop. Applies in live play and "
            f"during catch-up. {ORIGINS_BASE_SENTENCE} That base's companion loads "
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
        out = ROOT / "data" / f"{game}_healers_study_feature.json"
        out.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n")
        print("wrote", out.relative_to(ROOT), sha)


if __name__ == "__main__":
    main()
