"""Generate data/vv1_watering_trains_building_feature.json.

A New Home's "Watering the field" job (0x43FC20, string 588) fetches lagoon
water and waters the field, then advances the garden puzzle; unlike every
other Building job it queues no practice action, so it trains no skill.  The
companion "VVFP VV1 Watering Builds.dll" (native/vv1_watering_builds) detours
the garden progress step (0x43B1E6) and, only while the garden is not yet
done, appends one ordinary practice-Building action to the villager's job.

No executable byte is patched by the row: the Origins companion loads the DLL
from its per-frame tick and it installs its detour only after verifying the
stock bytes.  The DLL is pinned by SHA-256, so re-run this after every
rebuild.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DLL = ROOT / "assets" / "watering" / "VVFP VV1 Watering Builds.dll"
OUT = ROOT / "data" / "vv1_watering_trains_building_feature.json"


def main() -> None:
    sha = hashlib.sha256(DLL.read_bytes()).hexdigest().upper()
    manifest = {
        "id": "vv1_watering_trains_building",
        "enabled": True,
        "catalog_enabled": True,
        "catalog_hidden": False,
        "game_id": "vv1",
        "name": "Watering the Field Trains Building",
        "description": (
            "\"Watering the field\" now gives Building skill, but only when it makes "
            "progress towards the garden puzzle (after the lagoon puzzle is complete). "
            "Each watering that advances the garden ends with one ordinary Building "
            "practice roll, exactly like every other Building job; once the garden is "
            "restored, watering gives nothing extra. \"Watering crops\" and \"Trying to "
            "water strange patch\" are unchanged. "
            "**Requires Enable Origins-Exclusive Features**, whose companion loads this "
            "one; without it the stock game runs unchanged."
        ),
        "output_tag": "Watering Builds",
        "dependencies": ["vv1_enable_origins_exclusive_features"],
        "behavior_changes": [
            "When a villager's \"Watering the field\" job reaches its garden progress step (0x43B1E6) while the garden is not yet restored, one practice-Building action (type 6, skill 4) is appended to the end of that villager's job -- the same action every stock Building job queues last, with the stock chance, amount and failure handling. The last watering that completes the garden counts.",
        ],
        "explicit_non_changes": [
            "This row changes no executable bytes: the Origins companion loads the DLL, which detours 0x43B1E6 at run time only after verifying its twelve stock bytes; a different build of the game installs nothing.",
            "The garden progress itself, its 200-step goal, the lagoon and well requirements, \"Watering crops\" (Farming) and \"Trying to water strange patch\" are unchanged.",
            "Once the garden is restored, watering the field queues no extra practice action.",
        ],
        "runtime_detours": [
            {
                "va": "0x43B1E6",
                "stock_bytes": "8B8610E00300FF80BC9F0000",
                "routine": "the garden progress step (0x43A230 case 4)",
                "installed_by": "VVFP VV1 Watering Builds.dll, VvfpVv1WateringBuildsInstall",
            },
        ],
        "companion_files": [
            {
                "source": "assets/watering/VVFP VV1 Watering Builds.dll",
                "destination": "VVFP VV1 Watering Builds.dll",
                "sha256": sha,
            },
        ],
        "patches": [],
    }
    OUT.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n")
    print("wrote", OUT.relative_to(ROOT), sha)


if __name__ == "__main__":
    main()
