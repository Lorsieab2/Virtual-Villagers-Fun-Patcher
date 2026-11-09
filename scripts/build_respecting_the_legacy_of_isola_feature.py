"""Generate data/vv5_respecting_the_legacy_of_isola_feature.json: "Respecting the Legacy of Isola" (New Believers).

Built like Classic VV Difficulty (scripts/build_classic_vv_difficulty_features.py): the row changes no byte itself,
it needs the five patches below (its dependencies), so ticking it ticks them all, the way any patch ticks what it
needs; unticking one of them unticks this row too.  The owner's pieces, exactly these five (not Villagers Have Last
Names, not Heathen Mommy Puzzle Restoration, not Charitable Soul Epitaph).  Off in the normal defaults; on in
Owner's Defaults and Select All.  The patcher window draws its title in green (vv_fun_patcher_gui.TITLE_COLOURS).
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ID = "vv5_respecting_the_legacy_of_isola"
NAME = "Respecting the Legacy of Isola"

# (id, name, the owner's own opening sentences for the piece)
PIECES = [
    ("vv5_guardians_of_isola_rewrite", "Guardians of Isola Rewrite",
     "Changes some aspects of VV5 to make things more culturally respectful (hopefully!) Focused around peace, "
     "post-traumatic healing and growth."),
    ("vv5_respectful_hovel_cover", "Shrine to the Ancestors",
     "Turns the restored hovel into an ancestral shrine. A sacred, peaceful place where villagers can honor the "
     "ancestral spirits that guide them."),
    ("vv5_heathens_keep_masks_when_converted", "Heathens Keep Their Masks When Converted",
     "\"Heathen\" masks are culturally important to them. Their choices must be honored."),
    ("vv5_hovel_memorial_actions", "Memorial Actions Can Also Occur at the Heathen Hovel",
     "Best paired with \"Shrine to the Ancestors\". Villagers will sometimes come here to pay their respects to "
     "those that passed on, and others that guide their fate."),
    ("vv5_heathen_conversion_notice", "Popup When Believers Become Heathens",
     "Meant to make VV5 harder and push players to take care of their tribe."),
]


def feature() -> dict:
    names = [name for _, name, _ in PIECES]
    listed = ", ".join(names[:-1]) + " and " + names[-1]
    # The popup's own title in the game is "The Breaking Point".
    titled = {"vv5_heathen_conversion_notice": " (The Breaking Point)"}
    pieces = " ".join(f"{name}{titled.get(patch_id, '')}: {line}" for patch_id, name, line in PIECES)
    return {
        "id": ID,
        "enabled": True,
        "catalog_enabled": True,
        "catalog_hidden": False,
        "game_id": "vv5",
        "name": NAME,
        "description": (
            f"**Needs all five of the patches it names: {listed}; ticking it ticks them.** "
            "**Heathens Keep Their Masks When Converted runs on the Origins-exclusive base, which the patcher "
            "installs automatically with it, so this also adds the Origins Upgrades buttons to the Tech and "
            "Villager Details screens.** "
            "**The Breaking Point popup also needs Story / Cheat Upgrades (on by default), which this row does not "
            "tick.** "
            f"One tick for the patches that make New Believers more respectful of Isola and its people. {pieces} "
            "Unticking any of them unticks this row too, and then the rest stay as they are. This row changes "
            "nothing by itself. Off by default; Owner's Defaults and Select All tick it."),
        "output_tag": NAME,
        "dependencies": [patch_id for patch_id, _, _ in PIECES],
        "behavior_changes": ["None of its own: it ticks " + listed + "."],
        "explicit_non_changes": ["No executable byte, file or save is changed by this row itself."],
        "evidence_status": "a selection of other patches; each one's own evidence applies",
        "companion_files": [],
        "patches": [],
    }


def main() -> None:
    out = ROOT / "data" / f"{ID}_feature.json"
    out.write_text(json.dumps(feature(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    print("wrote", out.relative_to(ROOT))


if __name__ == "__main__":
    main()
