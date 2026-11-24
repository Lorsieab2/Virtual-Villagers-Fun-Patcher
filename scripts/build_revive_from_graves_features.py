"""Generate the five "Revive Buried/Disappeared Villagers" rows (the owner, 2026-11-22).

    python scripts/build_revive_from_graves_features.py

Each row ships one flag file, "VVFP Revive From Graves.txt", beside the companions; "VVFP Story Upgrades.dll" (which
the Story / Cheat Upgrades row ships) offers the upgrade while that file is there
(native/vvfp_story_upgrades/story_revive.inc rv_offered), and each game's Origins companion adds the Tech menu's
button (native/shared/story_bridge.h vvfp_story_add_revive_button).  No executable byte is written.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FLAG = "assets/story_upgrades/VVFP Revive From Graves.txt"

GAMES = {
    "vv1": "A New Home",
    "vv2": "The Lost Children",
    "vv3": "The Secret City",
    "vv4": "The Tree of Life",
    "vv5": "New Believers",
}

# What each game's graveyard is and how its grave goes (story_revive.inc).
GRAVES = {
    "vv1": "the cemetery's 50 graves (world +0xA31C, 0x2C each): the grave's own place is emptied (every reader "
           "treats an age of 0 as an empty place, and the next burial takes the first empty one)",
    "vv2": "the memorial's 50 graves (world +0x2EB0C, 0x7C each): the grave's own place is emptied, epitaph "
           "included (as A New Home)",
    "vv3": "the Roster of the Dead (0x5973F0 +0x974, 500 entries of 0x30) and the first 50 entries' gravestones "
           "(0x5973F0, 0x2C each): every count and the save's loader stop at the first empty entry, so the later "
           "entries and their stones move down one place and the last is emptied; an entry that moves to place 49 "
           "from 50 gets the stone the game's writer (0x454FF0) would give it, its epitaph by the writer's own rule",
    "vv4": "the mausoleum's Roster of the Dead (0x5025C8, 500 entries of 0x5C): the later entries move down one "
           "place and the last is emptied (every count and the save's loader stop at the first empty entry)",
    "vv5": "the mausoleum's Roster of the Dead (0x5481A8, 500 entries of 0x5C): as The Tree of Life",
}

SPECIAL = {
    "vv1": " The Golden Child is listed but can not come back: only his puzzle makes a Golden Child.",
    "vv2": " An Esteemed Elder comes back as an ordinary villager (their totem stays as it is).",
    "vv3": " A Tribal Chief comes back as an ordinary villager, not the chief (the robe makes a chief).",
    "vv4": "",
    "vv5": (" A Heathen whose death or disappearance the logs record (\"Faction: Heathen\") is listed and comes back as a"
            " Heathen in the camp, through the game's own Heathen creator (an ordinary Heathen)."
            " New Believers' puzzle Heathens (the Heathen Chief, the Heathen Mommy and the others) are listed but can"
            " not come back, and a believer who left to become a Heathen is listed as alive among the Heathens."),
}


# Seen working in a running game (the owner's live tests, 2026-11-23): New Believers and A New Home.  The other
# three keep the note.
SEEN_LIVE = ("vv1", "vv5")


def row(game: str, digest: str) -> dict:
    title = GAMES[game]
    description = (
        "**Needs Story / Cheat Upgrades** (it adds to that row's Tech-screen upgrades). A new upgrade in the Tech "
        "screen's upgrades menu, \"Revive Buried/Disappeared Villagers\", which costs 100,000 tech points each time "
        "while Story / Cheat Upgrades cost Tech Points is ticked and nothing while it is unticked, like the other "
        "story upgrades. It lists every buried villager and every "
        "villager who vanished, from the village's own Deaths and Disappearances log, with their name, sex, age at "
        "death, cause of death or what happened, grave line and epitaph, likes and dislikes, head and body, parents, "
        "mask, custom title and special title, and their skills from the last Village History snapshot of them; "
        "anything the logs do not hold is shown as unknown. The one you pick comes back as the same person - name "
        "and last name, sex, parents, likes and dislikes, looks, mask, custom title and skills - aged 5, through the "
        "game's own villager creator, and their grave is removed. It can be bought again and again. **Refused, with "
        "nothing charged, while the village is at its maximum population or has fewer tech points than it costs.** "
        "**The list comes from the logs: villagers are listed only when \"Write Births and Conceptions Log to Text "
        "File\" and \"Show Cause of Death and Epitaphs on Graves, and Log Every Death\" logged their death or "
        "disappearance (without them the list is empty), and their skills are known only with a "
        "Village History snapshot of them.** A villager in the village now is never listed." + SPECIAL[game]
        + " The returned villager gets an \"Arrived\" record (How: Returned from the dead) in the Births and "
        "Conceptions log at the next save; nothing is counted as a birth or a death. Off by default; on in Owner's "
        "Defaults." + ("" if game in SEEN_LIVE else " **Unverified in play: not yet tested in a running game.**")
    )
    return {
        "id": f"{game}_revive_from_graves",
        "enabled": True,
        "game_id": game,
        "name": "Revive Buried/Disappeared Villagers",
        "description": description,
        "output_tag": "Revive From Graves",
        "dependencies": [f"{game}_story_cheat_upgrades"],
        "behavior_changes": [
            "\"VVFP Story Upgrades.dll\" offers the upgrade while \"VVFP Revive From Graves.txt\" is in the patcher's "
            "folder (its contents are never read); the Origins companion adds the Tech menu's button last, above "
            "its other story buttons, as wide as its label needs.",
            "The list: every \"Death <n>\" and \"Disappeared\" record of this save slot's Deaths and Disappearances "
            "logs (both folder layouts), the newest record of each person (name, sex, head, body, likes, dislikes); "
            "the skills from the newest Village History snapshot of the same name, sex, head and body no older than "
            "at death.",
            "The revival: the game's own creator (through the Custom Island Event's spawn: the game's own room "
            "predicate and a free record first) at age 100 (5 years), then the name, head, body, every like and "
            "dislike the record holds room for, the skills, the parents (A New Home: with Show Parents in Details "
            "Screen), the custom title and the mask.",
            f"The grave ({title}): {GRAVES[game]}. Matched by name and age at death"
            + (" and the head and body" if game in ("vv4", "vv5") else "")
            + ", each grave to one record in log order; a grave that changed since the list was made is never "
              "removed (the purchase is refused).",
            "With Story / Cheat Upgrades cost Tech Points ticked, 100,000 tech points are taken only once the villager is "
            "back (free with it unticked); with fewer the purchase is refused, so "
            "the tech points never go below 0.",
        ],
        "explicit_non_changes": [
            "No executable byte is patched: the row's only file is its flag.",
            "Nothing is counted as a birth or a death, and the game's own statistics are not touched; the logs are "
            "append-only, so the old Death or Disappeared record stays and the Arrived record says they returned.",
            "A body awaiting burial is not listed (Custom Island Event's Revive brings bodies back).",
        ],
        "evidence_status": "emulated: the list from log texts, the refusals, the purchase through each game's own "
                           "creator in all three population modes, the grave's removal and the game's own grave "
                           "counts afterwards (tests/test_story_revive_from_graves.py); runtime/player confirmation "
                           "pending",
        "companion_files": [
            {"source": FLAG, "destination": "VVFP Revive From Graves.txt", "sha256": digest},
        ],
        "patches": [],
    }


def main() -> None:
    digest = hashlib.sha256((ROOT / FLAG).read_bytes()).hexdigest().upper()
    for game in GAMES:
        path = ROOT / "data" / f"{game}_revive_from_graves_feature.json"
        path.write_text(json.dumps(row(game, digest), indent=2, ensure_ascii=False) + "\n", encoding="utf-8",
                        newline="\n")
        print(path)


if __name__ == "__main__":
    main()
