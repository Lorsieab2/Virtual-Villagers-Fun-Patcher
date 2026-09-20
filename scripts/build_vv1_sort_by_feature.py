"""Generate data/vv1_sort_by_feature.json -- Sort by Age/Skill/Health in Details Screen.

A New Home's Details arrows walk the villager records in index order.  The
Lost Children and the later games sort them instead: ascending by age, by the
villager's highest skill, or by health, with the record index as the
tie-break, and they keep a list position that survives a change of order
(measured live in The Secret City -- see native/vv1_sort_by/vv1_sort_by.c).
This row ships the companion "VVFP VV1 Sort By.dll", which the Origins row's
two arrow hooks ask which villager to select, and which draws the "Sort By:"
band from the Origins companion's Details portrait hook.

The art is the owner's, after their mockup: a "Sort By:" plate, one plate per
order with its word, and The Lost Children's radio sheet.  Every image is
drawn 1:1 and sized from the file, so replacing the PNGs is enough.

The DLL and the image are pinned by SHA-256, so the manifest must be
regenerated after every rebuild of the DLL.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DLL = ROOT / "assets" / "sort_by" / "VVFP VV1 Sort By.dll"
RADIO = ROOT / "assets" / "sort_by" / "vvfp_sort_radio.png"
PLATES = {m: ROOT / "assets" / "sort_by" / f"vvfp_sort_{m}.png" for m in ("age", "skill", "health")}
TITLE = ROOT / "assets" / "sort_by" / "vvfp_sort_title.png"
OUT = ROOT / "data" / "vv1_sort_by_feature.json"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def main() -> None:
    manifest = {
        "id": "vv1_sort_by",
        "enabled": True,
        "catalog_enabled": True,
        "catalog_hidden": False,
        "game_id": "vv1",
        "name": "Sort by Age/Skill/Health in Details Screen",
        "description": (
            "Adds The Lost Children's Sort By band to A New Home's Villager Detail "
            "screen, under the Age and Gender boxes: Age, Skill and Health, each with "
            "a radio. The left and right arrows then walk the villagers in that order "
            "the way the later games do -- ascending by age, by the villager's highest "
            "skill, or by health, with earlier villagers first among equals, and the "
            "place in the list is kept when the order is changed. Age is the default. "
            "Requires Enable Origins-Exclusive Features, whose companion loads "
            "this one and whose arrow hooks ask it which villager comes next."
        ),
        "output_tag": "Sort By",
        "dependencies": [
            "vv1_enable_origins_exclusive_features",
        ],
        "behavior_changes": [
            "The Details screen shows a \"Sort By:\" band with Age, Skill and Health plates and radios in the space between the Age/Gender boxes and the villager strip; clicking a plate or its radio chooses the order.",
            "The Details left/right arrows step through the living villagers in the chosen order (ascending key, record index among equals, wrapping at either end); the list position is kept across a change of order, as in the later games.",
        ],
        "explicit_non_changes": [
            "This row changes no executable bytes itself: the two arrow hooks and the portrait hook belong to the Origins row's patch; without this DLL they fall through to the stock arrows.",
            "Nothing is written to a villager record, the save or any file: the chosen order lasts for the session, as in the later games.",
            "The villager strip, the world-view selection and every other way of choosing a villager are untouched; they simply set the position the arrows continue from.",
        ],
        "companion_files": [
            {
                "source": "assets/sort_by/VVFP VV1 Sort By.dll",
                "destination": "VVFP VV1 Sort By.dll",
                "sha256": _sha(DLL),
            },
            {
                "source": "assets/sort_by/vvfp_sort_radio.png",
                "destination": "Images/vvfp_sort_radio.png",
                "sha256": _sha(RADIO),
            },
        ] + [
            {
                "source": f"assets/sort_by/vvfp_sort_{m}.png",
                "destination": f"Images/vvfp_sort_{m}.png",
                "sha256": _sha(PLATES[m]),
            }
            for m in ("age", "skill", "health")
        ] + [
            {
                "source": "assets/sort_by/vvfp_sort_title.png",
                "destination": "Images/vvfp_sort_title.png",
                "sha256": _sha(TITLE),
            },
        ],
        "patches": [],
    }
    OUT.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n")
    print("wrote", OUT.relative_to(ROOT), _sha(DLL))


if __name__ == "__main__":
    main()
