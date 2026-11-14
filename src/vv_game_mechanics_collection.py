"""The Isola Grand Event Collection on the Game Mechanics pages' Island events group (all five games; v1.35.97).

Shown only when the game's exe has the patch (vvN_isola_grand_event_collection).  Every list is read from what the
patcher ships, so it cannot drift: the game's events and their order from assets/event_collection/vvN/manifest.txt
(the file "VVFP Story Upgrades.dll" reads); each event's section and the effects that can kill or remove a villager
from data/event_collection_index.json, which `build_index` makes from the source graphs
data/event_collection/<section>/<id>.json (the graphs the .cieg files are compiled from; they are not shipped) --
python src/vv_game_mechanics_collection.py writes it, tests/test_game_mechanics_collection.py keeps it equal to
the sources and to every game's manifest.  The roll's rules are native/vvfp_story_upgrades/story_collection.inc's (tests/test_collection_trigger.py);
its chance per game is vv_game_mechanics_adventurer.RARE_ROLL_PERCENT, kept equal to the C table by
tests/test_more_island_events_stock_odds.py.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

import vv_game_mechanics as gm
from vv_game_mechanics_adventurer import PROTECTED, RARE_ROLL_PERCENT

ROOT = Path(__file__).resolve().parents[1]
PATCH = "vv{}_isola_grand_event_collection"
GROUP = "Island events"

# The collection's sections in the order the source file has them, in plain words.
SECTIONS = (
    ("universal", "Universal events"),
    ("original", "The owner's original events and their add-ons"),
    ("exclusive", "Events of one game only"),
    ("v6", "Part V6"), ("v8", "Part V8"), ("v9", "Part V9"), ("v10", "Part V10"), ("v11", "Part V11"),
    ("v13", "Part V13"), ("v14", "Part V14"), ("v17", "Part V17"), ("v18", "Part V18"), ("v20", "Part V20"),
    ("v21", "Part V21"), ("v22", "Part V22"), ("v23", "Part V23"), ("v24", "Part V24"),
    ("vv5_isolan", "Isolan events"),
)
SECTION_WORDS = dict(SECTIONS)


def manifest_path(game: int) -> Path:
    return ROOT / "assets" / "event_collection" / f"vv{game}" / "manifest.txt"


@lru_cache(maxsize=None)
def manifest(game: int) -> tuple[tuple[str, str, str], ...]:
    """(id, title, series) of each event the patcher ships for this game, in the manifest's order."""
    rows = []
    for line in manifest_path(game).read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#"):
            continue
        cells = line.split("\t")
        rows.append((cells[0], cells[1], cells[4] if len(cells) > 4 else ""))
    return tuple(rows)


INDEX_PATH = ROOT / "data" / "event_collection_index.json"
HARMFUL = ("kill", "vanish")                 # the effects listed on the page


def _effects(node) -> set[str]:
    out: set[str] = set()
    if isinstance(node, dict):
        for effect in node.get("effects") if isinstance(node.get("effects"), list) else ():
            if isinstance(effect, dict) and effect.get("do") in HARMFUL:
                out.add(effect["do"])
        for value in node.values():
            out |= _effects(value)
    elif isinstance(node, list):
        for value in node:
            out |= _effects(value)
    return out


def build_index() -> dict:
    """{event id: {"section": ..., "harm": [...]}} from the source graphs (repository only: not shipped)."""
    out = {}
    for source in sorted((ROOT / "data" / "event_collection").glob("*/*.json")):
        graph = json.loads(source.read_text(encoding="utf-8"))
        if not isinstance(graph, dict) or "collection" not in graph:
            continue                                       # manifest.json, shared_pools.json
        out[source.stem] = {"section": graph["collection"]["section"], "harm": sorted(_effects(graph))}
    return {"format": "vvfp-event-collection-index", "version": 1, "events": out}


@lru_cache(maxsize=None)
def index() -> dict:
    return json.loads(INDEX_PATH.read_text(encoding="utf-8"))["events"]


def event_info(event_id: str) -> tuple[str, frozenset]:
    """The event's section and the harmful effects its graph can make ("kill", "vanish")."""
    entry = index()[event_id]
    return entry["section"], frozenset(entry["harm"])


def sections(game: int) -> list[tuple[str, list[str]]]:
    """[(section words, [titles])] for this game, sections in the source's order, titles in the manifest's."""
    grouped: dict[str, list[str]] = {}
    for event_id, title, _series in manifest(game):
        grouped.setdefault(event_info(event_id)[0], []).append(title)
    order = [key for key, _ in SECTIONS] + sorted(set(grouped) - set(SECTION_WORDS))
    return [(SECTION_WORDS.get(key, key), grouped[key]) for key in order if key in grouped]


def deadly(game: int) -> tuple[list[str], list[str]]:
    """The titles of this game's events that can kill a villager, and of those that can make one disappear."""
    kill = [title for event_id, title, _ in manifest(game) if "kill" in event_info(event_id)[1]]
    vanish = [title for event_id, title, _ in manifest(game) if "vanish" in event_info(event_id)[1]]
    return kill, vanish


def series_count(game: int) -> int:
    return len({series for _id, _title, series in manifest(game) if series})


def lines(game: int) -> list[tuple[str, bool]]:
    """(text, sub) of each line, without the patch check."""
    events = manifest(game)
    pct = RARE_ROLL_PERCENT[game]
    kill, vanish = deadly(game)
    out = [
        (f"Isola Grand Event Collection: {len(events)} events in this game. They are rare and never take a share of "
         "the game's own draw, so the game's own island events keep exactly their chances.", False),
        (f"How one comes: after each natural island event, once the village has seen two, a separate roll comes up "
         f"{pct}% of the time (made by Story / Cheat Upgrades with the game's own random routine). Then a rare event "
         "comes later, 30% to 70% of the way to the next natural event (on the same clock as the game's own island "
         "events). It waits while another event is on its way, and gives way when the natural event comes first.",
         True),
        ("It never comes while the village is in trouble: the game's own rescue rule (too few men or women, or fewer "
         "than 3 people counting the babies being carried), food below 10 a villager, half the village sick, or "
         "fewer than 6 villagers of 14 villager years or more. So it never takes a rescue event's place.", True),
        ("Which one: when More Island Events is installed too and both have an event that can happen, each side is "
         "chosen half the time. Within the collection each event is equally likely; a series counts as one event, "
         f"its parts equally likely ({series_count(game)} series in this game). An event whose villagers cannot be "
         "found is left out and another is drawn.", True),
        ("Pick Island Event lists every event with what it needs, and the Custom Island Event library has them in "
         "its own \"Isola Grand Event Collection\" group.", True),
        ("Needs Story / Cheat Upgrades (it runs the roll and the events) and Scrolling Popups (it keeps every page "
         "on the screen).", True),
        (f"Who can be harmed: never a nursing mother or father, {PROTECTED[game]}, or anyone the game's own island "
         "events never pick. They may still take part in harmless roles (speaking, celebrating).", True),
    ]
    out.append((("Can kill a villager (a grave, cause \"Unknown causes\"): "
                 + ", ".join(kill) + ".") if kill else "No event in this game kills a villager.", True))
    out.append((("Can make a villager disappear (no grave): " + ", ".join(vanish) + ".") if vanish
                else "No event in this game makes a villager disappear.", True))
    for words, titles in sections(game):
        out.append((f"{words} ({len(titles)}): " + ", ".join(titles) + ".", True))
    return out


def facts(village: gm.Village) -> list[gm.Fact]:
    """The collection's lines, shown only when the game's exe has the patch."""
    game = village.game
    if game not in RARE_ROLL_PERCENT or village.has(PATCH.format(game)) is not True:
        return []
    return [gm.Fact(GROUP, text, gm.RUNNING, sub=sub) for text, sub in lines(game)]


if __name__ == "__main__":
    INDEX_PATH.write_text(json.dumps(build_index(), indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(f"wrote {INDEX_PATH.relative_to(ROOT)}")
