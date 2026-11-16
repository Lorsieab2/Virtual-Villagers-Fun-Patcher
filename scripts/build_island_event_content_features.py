"""Write the island events' content controls (v1.35.97, the owner 2026-11-15), one set of rows per game:

  * vvN_island_event_content_notes  -- Content Notes for Island Events (on in Owner's Defaults, off elsewhere);
  * vvN_island_event_filter_fNN     -- the 28 content filters F01-F28 (off everywhere, Owner's Defaults too).

No executable byte and no file of their own: each row is a name in "VVFP Installed Patches.txt" (the patcher writes
every installed row there), which Story / Cheat Upgrades reads.  The new events carry what to do with each
(src/vv_event_content.py writes it into every compiled event); the game's own events are never touched.  The patcher
shows them in each game's Island Events section (src/vv_fun_patcher_gui.py).

    python scripts/build_island_event_content_features.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import vv_event_content as content  # noqa: E402

GAMES = (1, 2, 3, 4, 5)
UNVERIFIED = "**Unverified in play: the effect has not been tested live.**"


def needs_on(game: int) -> list[dict]:
    return [{"id": f"vv{game}_isola_grand_event_collection", "for": "the new island events it acts on"}]


def row(game: int, ident: str, name: str, description: str, changes: list[str]) -> dict:
    return {
        "id": f"vv{game}_{ident}",
        "enabled": True,
        "catalog_enabled": True,
        "catalog_hidden": False,
        "game_id": f"vv{game}",
        "name": name,
        "description": description,
        "output_tag": name,
        "dependencies": [],
        "needs_on": needs_on(game),
        "conflicts": [],
        "behavior_changes": changes,
        "explicit_non_changes": [
            "No executable byte, game file or save is changed: the row is only a name in the installed patches' list "
            "(\"VVFP Installed Patches.txt\") that Story / Cheat Upgrades reads.",
            "The game's own island events, their text and their chances are never changed: it acts on the added "
            "events only.",
        ],
        "evidence_status": "the compiled events' conditions and effects pinned in tests/test_event_content.py; "
                           "runtime/player confirmation pending",
        "companion_files": [],
        "patches": [],
        "runtime_detours": [],
    }


def notes_row(game: int) -> dict:
    labels = ", ".join(content.NOTE_LABELS)
    return row(game, content.NOTES_PATCH, "Content Notes for Island Events",
               "Before the main text of a new island event that may touch a sensitive subject, a short note names it, "
               "for example \"Content note: Bereavement\". It never says which outcome will come. The labels are: "
               f"{labels}. A subject the content filters below have removed from that event is left out of its note. "
               "New events only (the Isola Grand Event Collection's); the game's own events are unchanged. "
               f"Off by default; Owner's Defaults ticks it. {UNVERIFIED}",
               ["The first text of each new event that may touch a sensitive subject starts with \"Content note: "
                "<labels>\" (a variant of that text compiled into the event, shown while this row is installed)."])


def filter_row(game: int, fid: str) -> dict:
    name = f"Content Filter: {content.FILTERS[fid]}"
    return row(game, content.filter_patch(fid), name,
               f"Keeps \"{content.FILTERS[fid].lower()}\" out of the new island events. Applied before the random draw at a natural island event "
               "picks an event: an outcome with that content is dropped where the event still makes sense without it "
               "(the other outcomes keep their shares), otherwise the whole event is skipped. Filters never hide a "
               "kind of person. New events only; the game's own events are unchanged. "
               f"Off by default, Owner's Defaults too. {UNVERIFIED}",
               [f"Every new event's outcomes tagged {fid} are left out of its draw while this row is installed, and "
                "an event that cannot do without them is skipped (its requirement)."])


ANY_TIME = "island_events_any_time"


def any_time_row(game: int) -> dict:
    record = row(game, ANY_TIME, "No Safeguards for Island Events (and Additional Events too)",
                 "For masochists. All island events, the game's own included, can happen at any time: new events can replace rescue events and the two opening events, and no population limit or trouble guard applies. Only the villagers an event needs are still required. "
                 "It applies to whichever island events are on in the game. Anyone can be picked and any event can "
                 "happen at any time (nursing mothers and fathers, the Golden Child, the Tribal Chief and New "
                 "Believers' story villagers included), except when a pick would make no sense in the event -- a "
                 "child's role needs a child, an age change needs a fitting age, a pregnancy needs a villager who can "
                 "carry -- or the event names someone the village does not have (no Chief, no Chief event). Objects "
                 "that are not living villagers, such as The Lost Children's totem statues, are never picked, and "
                 "the guards against crashes and damaged saves stay. "
                 f"Off by default, in Owner's Defaults and in Select All too. {UNVERIFIED}",
                 ["For the new events (Story / Cheat Upgrades): no 61-villager gate, rescue events and the two opening "
                  "events may be replaced, no trouble guard and no safeguards; only the villagers each event needs. "
                  "The game's own events' conditions are lifted by another companion (later). It applies to whichever "
                  "island events are on in the game."])
    record["needs_on"] = []           # it applies to whichever island events are on (the owner, 2026-11-15)
    return record


def rows(game: int) -> list[dict]:
    return ([notes_row(game), any_time_row(game)]
            + [filter_row(game, f) for f in content.FILTER_IDS])


def feature_path(record: dict) -> Path:
    return ROOT / "data" / f"{record['id']}_feature.json"


def main() -> None:
    n = 0
    for game in GAMES:
        for record in rows(game):
            feature_path(record).write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            n += 1
    print(f"{n} rows written")


if __name__ == "__main__":
    main()
