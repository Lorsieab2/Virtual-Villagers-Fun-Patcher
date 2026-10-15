"""Generate the "Tribal Chief Supervises the Hospital" row (The Secret City).

The owner: the Tribal Chief should be able to direct work when dropped on the
Hospital hotspot.  In the stock game the Hospital drop gives the chief the
Healing site (+0xEA0 = 9), and the chief's supervision roll 0x45FC60 is asked
for fishing, fruit, honey, huts, research and puzzles, but never for a cure.
This row makes the healer's failed cure roll (0x457395 / 0x45739A in the
stock executable) also ask that roll for the hospital, so a chief standing on
the hospital helps the cure.

The behaviour lives in one companion, "VVFP VV3 Chief Hospital.dll"
(native/vvfp_chief_hospital).  The startup loader (VVFP Startup.dll) calls its
VvfpStartup(game, shipped) once at game start; the DLL verifies the eight stock
bytes and writes the detour at run time.  The row patches no executable byte.
The DLL is pinned by SHA-256, so re-run this after every rebuild.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DLL = ROOT / "assets" / "chief_hospital" / "VVFP VV3 Chief Hospital.dll"
OUT = ROOT / "data" / "vv3_chief_hospital_feature.json"
INSTALLED_BY = "VVFP VV3 Chief Hospital.dll, VvfpStartup"


def main() -> None:
    sha = hashlib.sha256(DLL.read_bytes()).hexdigest().upper()
    manifest = {
        "id": "vv3_chief_hospital_supervision",
        "enabled": True,
        "catalog_enabled": True,
        "catalog_hidden": False,
        "game_id": "vv3",
        "name": "Tribal Chief Supervises the Hospital",
        "description": (
            "Dropping the Tribal Chief on the Hospital hotspot makes the chief supervise the "
            "hospital. A healer whose cure roll fails then gets a second chance: the chief's "
            "supervision roll, which passes about 25% of the time per Leadership level, lets the "
            "cure go ahead as if the healer had passed. Otherwise the cure is exactly the stock one. "
            "The stock game already gives the chief this supervision bonus for fishing, fruit, honey, "
            "huts, research and puzzles, but never for a cure. **Unverified in play: the effect has "
            "not been tested live.** This patch needs no other row and does not add the Origins "
            "Upgrades buttons. It is on by default for The Secret City; untick it to keep the stock "
            "cure. The companion is \"VVFP VV3 Chief Hospital.dll\", started by VVFP Startup.dll; if the "
            "DLL cannot be loaded, the stock cure runs."
        ),
        "output_tag": "Chief Hospital",
        "dependencies": [],
        "behavior_changes": [
            "When a healer's Healing roll in a cure fails (the roll at 0x457395), the game asks the chief's supervision roll 0x45FC60 for the Hospital site (9). That roll passes only when the Tribal Chief is alive, not sick, standing on the hospital hotspot (+0xEA0 = 9), and rand(100) < 25 x Leadership level; then the cure continues as a passed Healing roll does.",
            "A passed Healing roll is unchanged, and so is every cure when no chief is on the hospital: the supervision roll then draws nothing from the game's random generator.",
        ],
        "explicit_non_changes": [
            "This row changes no executable bytes: VVFP VV3 Chief Hospital.dll verifies the eight stock bytes at 0x45739A and writes a jump to its stub at run time; a different build of the game installs nothing.",
            "The chief's supervision is unchanged everywhere else: fishing, fruit, honey, huts, research and puzzles keep their stock bonuses, and the chief still never picks a job.",
            "A healer who dislikes medicine still fails half of their cures, as in the stock game; a chief's success is a pass of the Healing roll, not a guaranteed cure.",
            "Catch-up healing (the cure scan at 0x45B94A) is not changed by this row.",
            "Nothing is written to a villager record, the save or any file.",
        ],
        "companion_files": [
            {
                "source": "assets/chief_hospital/VVFP VV3 Chief Hospital.dll",
                "destination": "VVFP VV3 Chief Hospital.dll",
                "sha256": sha,
            },
        ],
        "patches": [],
        "runtime_detours": [
            {
                "va": "0x45739A",
                "stock_bytes": "84C00F848F000000",
                "written_bytes": "E9XXXXXXXX909090",
                "routine": "the healer's cure (0x457350): the test of the Healing roll's result, after its call at 0x457395; a failed roll asks the chief's supervision roll for the hospital (0x45FC60(9)) before the stock failure at 0x457431",
                "installed_by": INSTALLED_BY,
            },
        ],
    }
    OUT.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n")
    print("wrote", OUT.relative_to(ROOT), sha)


if __name__ == "__main__":
    main()
