"""Generate data/vv1_show_parents_feature.json -- Show Parents in Details Screen.

A New Home keeps no record of a villager's parents.  This row ships the
companion "VVFP VV1 Parentage.dll" (native/vv1_parentage), which the Origins
companion loads and calls: once per frame to watch the villager records for a
birth, and once per Details portrait draw to paint the parents.  The parentage
companion (the VV1 parentage log row) hands it the father at conception, and
it writes each birth back to that log the moment it sees it.

No executable bytes are changed by this row.  Every hook it relies on -- the
Origins row's exact birth hook inside sub_43C840 (0x43CA48 -> Vv1Born), the
Origins companion's per-frame tick and its Details portrait hook, and the
parentage log's conception trampolines -- lives in those rows' patches,
which is why the row depends on the Origins row: without it nothing calls
the companion.  The
parentage log row is not a declared dependency (the patcher closes a selection
over its prerequisites in both directions, and unticking the log must not
silently untick this); without it the father is simply not captured.

The DLL is pinned by SHA-256 here, so the manifest must be regenerated after
every rebuild of the DLL (the build is not reproducible).
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DLL = ROOT / "assets" / "parentage" / "VVFP VV1 Parentage.dll"
OUT = ROOT / "data" / "vv1_show_parents_feature.json"


def main() -> None:
    digest = hashlib.sha256(DLL.read_bytes()).hexdigest().upper()
    manifest = {
        "id": "vv1_show_parents",
        "enabled": True,
        "catalog_enabled": True,
        "catalog_hidden": False,
        "game_id": "vv1",
        "name": "Show Parents in Details Screen",
        "description": (
            "Gives A New Home the true parentage the later games keep: every villager "
            "born in the village remembers their mother and father for life. While a "
            "villager is under 18 (and again if they are ever made younger), two small, "
            "faded figures of the parents stand in the upper corners of the Details "
            "portrait -- the father on the left facing right, the mother on the right "
            "facing left -- and hovering one reads \"Son of <name>\" or \"Daughter of "
            "<name>\". The record is kept in vv1_parents_<slot>.dat beside the save, "
            "never inside a villager record or the save itself, and an entry is never "
            "erased: only a new villager in the same slot starts it over. Each birth is "
            "also written to the parentage log the moment it is seen, and the Village "
            "Population roster lists each villager's own parents. Founders and villagers "
            "born before this patch have no recorded parents. Requires Enable "
            "Origins-Exclusive Features, whose companion loads this one. The father is "
            "supplied by Write Parentage Log's conception hook, so with that row off only "
            "the mother is recorded."
        ),
        "output_tag": "Show Parents",
        "dependencies": [
            "vv1_enable_origins_exclusive_features",
        ],
        # Works without it, but does less: the father comes from the
        # parentage log's conception hook, and the "Birth" line is written
        # through its companion.
        "needs_on": [
            {
                "id": "vv1_write_parentage_log",
                "for": "the father (with it off only the mother is recorded) and for the \"Birth\" records in the parentage log",
            },
        ],
        "behavior_changes": [
            "The Details portrait of a villager under 18 with recorded parents shows two half-faded parent figures in the frame's upper corners, built from each parent's own head and body rows; hovering one shows \"Son of <name>\" / \"Daughter of <name>\" under the portrait.",
            "Conceptions stash the father's name, head and body against the mother; at each birth the game's own child-creation routine hands the named child and its mother to the companion (the Origins row's hook at 0x43CA48), so both parents are recorded for the child -- during load-time catch-up too -- immediately appended to the parentage log as a \"Birth\" record, then written to vv1_parents_<slot>.dat.",
            "The Village Population roster gains a \"Parents:\" block on A New Home villagers whose parents are recorded.",
        ],
        "explicit_non_changes": [
            "This row changes no executable bytes itself: it is the companion DLL alone, reached through hooks the Origins row (the birth hook, the per-frame tick, the portrait hook) and the parentage log row (the conception hook) install.",
            "No villager record field and no byte of the save is written; the record lives only in the sidecar beside the save.",
            "A recorded entry is never erased by death, ageing or de-ageing; only a new occupant of the same record slot resets it.",
            "Founders, villagers born before the patch, and a birth whose parents cannot be told apart (two look-alike mothers delivering in one frame) are left unknown rather than guessed.",
        ],
        "companion_files": [
            {
                "source": "assets/parentage/VVFP VV1 Parentage.dll",
                "destination": "VVFP VV1 Parentage.dll",
                "sha256": digest,
            }
        ],
        "patches": [],
    }
    OUT.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n")
    print("wrote", OUT.relative_to(ROOT), digest)


if __name__ == "__main__":
    main()
