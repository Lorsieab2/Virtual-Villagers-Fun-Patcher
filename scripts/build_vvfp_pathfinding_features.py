"""Generate the two Improved Pathfinding rows -- A New Home and The Lost Children.

The Secret City and the games after it plan a route the moment a villager's
next step is blocked: they flood the walkability grid from the goal and walk
the villager down it, round the obstacle (0x4232A0 / 0x423590 in The Secret
City).  A New Home has no such search -- its blocked handler (0x43DFC0) nudges
the villager sideways fifteen times and then clears the whole action queue, so
the villager forgets the task and drops what it carried -- and The Lost
Children's own router gives up on a villager pushed onto an unreached cell.
The owner: exactly VV3, where a hut or the side of anything is never
"unreachable" and only a walled-off task ends the action.  The shared companion
"VVFP Improved Pathfinding.dll" (native/vvfp_pathfinding) brings The Secret
City's model to both.

Neither row patches an executable byte: each game's Origins companion loads
the DLL by full path from its per-frame tick and asks it to install its
detours, which it does only after verifying the stock bytes at every site.
The DLL is pinned by SHA-256, so this must be re-run after every rebuild.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DLL = ROOT / "assets" / "pathfinding" / "VVFP Improved Pathfinding.dll"

GAMES = {
    "vv1": {
        "out": ROOT / "data" / "vv1_improved_pathfinding_feature.json",
        "title": "A New Home",
        "origins": "vv1_enable_origins_exclusive_features",
        "sites": [
            {"va": "0x43DFC0", "stock": "5153558B6C2410", "routine": "the blocked-walk handler"},
        ],
        "changes": [
            "When a villager walking to a task finds the next step blocked, the companion floods the game's own 168x168 walkability grid from the task and queues the end of the first straight run of the way round as a walk-to in front of the current action (the same call the stock nudge makes); on reaching it the villager resumes the task, and a further blockage is handled the same way from there.",
            "While a route exists the villager is never handed back to the stock handler's sideways nudges: bumping into a hut or the side of anything is routed round. Only a task that is truly unreachable -- its own cell on an obstacle, or walled off -- ends the action, at once through the game's own queue clear (0x439470), as The Secret City does; the fifteen nudges never run.",
        ],
        "non_changes": [
            "This row changes no executable bytes: the Origins companion loads the DLL, which detours the handler at 0x43DFC0 at run time only after verifying its seven stock bytes; a different build of the game installs nothing.",
            "Wandering, running from danger and every other movement are untouched; only the walk toward a queued task consults the route.",
            "Nothing is written to a villager record beyond the same walk-to queue entry the stock nudge writes, and nothing to the save or any file.",
        ],
    },
    "vv2": {
        "out": ROOT / "data" / "vv2_improved_pathfinding_feature.json",
        "title": "The Lost Children",
        "origins": "vv2_enable_origins_exclusive_features",
        "sites": [
            {"va": "0x41A700", "stock": "B810B90100", "routine": "the route flood"},
            {"va": "0x41A9B0", "stock": "B867666666", "routine": "the route descent"},
        ],
        "changes": [
            "The route flood keeps the game's (and The Secret City's) rule that a task on a blocked cell is unreachable, but writes the field with the shared flood so the descent below has it.",
            "The route descent takes the neighbour nearest the task rather than the first smaller one in a fixed order, never cuts the corner between two blocked cells, and from an unreached or blocked cell heads for the nearest reached one; the field it writes and reads is laid out exactly as the game's own follower expects.",
        ],
        "non_changes": [
            "This row changes no executable bytes: the Origins companion loads the DLL, which detours the flood at 0x41A700 and the descent at 0x41A9B0 at run time only after verifying their stock bytes; a different build of the game installs nothing.",
            "The follower, the arrival test, the goal-on-24 rule and the child rule for 24 cells are the game's own and are unchanged.",
            "Nothing is written to the save or any file.",
        ],
    },
}


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def main() -> None:
    dll_sha = _sha(DLL)
    for game_id, spec in GAMES.items():
        manifest = {
            "id": f"{game_id}_improved_pathfinding",
            "enabled": True,
            "catalog_enabled": True,
            "catalog_hidden": False,
            "game_id": game_id,
            "name": "Improved Pathfinding",
            "description": (
                "Updates the pathfinding to resemble VV3-VV5. Hopefully villagers don't "
                "get stuck behind things anymore! When a villager's next step toward a "
                "task is blocked, a route round the obstacle is planned on the game's "
                "own walkability grid and followed, the way The Secret City does it, "
                "instead of the villager giving up and dropping the task. "
                "**Requires Enable Origins-Exclusive Features**, whose companion loads "
                "this one; without it the stock walk runs unchanged."
            ),
            "output_tag": "Pathfinding",
            "dependencies": [spec["origins"]],
            "behavior_changes": spec["changes"],
            "explicit_non_changes": spec["non_changes"],
            "runtime_detours": [
                {
                    "va": site["va"],
                    "stock_bytes": site["stock"],
                    "routine": site["routine"],
                    "installed_by": "VVFP Improved Pathfinding.dll, VvfpPathfindingInstall",
                }
                for site in spec["sites"]
            ],
            "companion_files": [
                {
                    "source": "assets/pathfinding/VVFP Improved Pathfinding.dll",
                    "destination": "VVFP Improved Pathfinding.dll",
                    "sha256": dll_sha,
                },
            ],
            "patches": [],
        }
        spec["out"].write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n")
        print("wrote", spec["out"].relative_to(ROOT), dll_sha)


if __name__ == "__main__":
    main()
