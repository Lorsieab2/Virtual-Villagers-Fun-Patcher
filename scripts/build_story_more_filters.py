"""Write which island-event content filters keep each of More Island Events' events out, from the events' content tag
table (data/event_collection/content_tags/mie.json, written by scripts/build_event_content_tags.py) -- never by hand,
so the two can never disagree -- and the most villagers one ending of each can take (SC_MORE_GONE, the casualty
limit below 61 villagers: GONE below, checked against the same tags).  "VVFP Story Upgrades.dll"
(story_collection.inc sc_more_filtered) keeps a More Island Events entry out of the draw and Pick Island Event's list when any filter its tag table names is ticked.  It writes

    native/vvfp_story_upgrades/story_more_filters.h

in the order of More Island Events' registry (native/vvfp_more_island_events/mie_pick.inc MIE_PICKS), the index the
companion's entries carry.  scripts/build_vvfp_story_upgrades.ps1 runs it before every compile.

    python scripts/build_story_more_filters.py
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TAGS = ROOT / "data" / "event_collection" / "content_tags" / "mie.json"
PICKS = ROOT / "native" / "vvfp_more_island_events" / "mie_pick.inc"
OUT_H = ROOT / "native" / "vvfp_story_upgrades" / "story_more_filters.h"

# Each registry entry's event in the tag table (the two Remembrance Ceremony entries are one event).
PICK_TAGS = {
    "aspiring_adventurer": "mie_adventurer",
    "cave_explorers": "mie_cave_explorers",
    "the_climb": "mie_climb",
    "troubling_signs": "mie_troubling_signs",
    "diving_for_treasure": "mie_diving",
    "playful_dolphins": "mie_dolphins",
    "mysterious_mask": "mie_mysterious_mask",
    "remembrance_ceremony": "mie_remembrance",
    "remembrance_ceremony_nb": "mie_remembrance",
    "the_rumblings": "mie_rumblings",
}

_ENTRY = re.compile(r'\{\s*((?:MIE_ALL_GAMES|MIE_IN\(\d\))(?:\s*\|\s*MIE_IN\(\d\))*)\s*,\s*"([a-z0-9_]+)"')


def picks() -> list[tuple[str, tuple[int, ...]]]:
    """MIE_PICKS in order: (entry id, the games it is in)."""
    text = PICKS.read_text(encoding="utf-8")
    m = re.search(r"static const mie_pick MIE_PICKS\[\] = \{(.*?)\n\};", text, re.S)
    if m is None:
        raise SystemExit(f"{PICKS}: MIE_PICKS not found")
    out = []
    for games, ident in _ENTRY.findall(m.group(1)):
        if games == "MIE_ALL_GAMES":
            in_games = (1, 2, 3, 4, 5)
        else:
            in_games = tuple(sorted(int(g) for g in re.findall(r"MIE_IN\((\d)\)", games)))
        out.append((ident, in_games))
    if not out:
        raise SystemExit(f"{PICKS}: MIE_PICKS has no entries")
    return out


def tag_table() -> dict[str, list[str]]:
    """{tag table event id: the filters (F01..F28) it names}."""
    data = json.loads(TAGS.read_text(encoding="utf-8"))
    return {ident: list(entry.get("filters") or []) for ident, entry in data["events"].items()}


def mask(filters: list[str]) -> int:
    bits = 0
    for code in filters:
        m = re.fullmatch(r"F(\d\d)", code)
        if m is None or not 1 <= int(m.group(1)) <= 28:
            raise SystemExit(f"{TAGS}: {code!r} is not a content filter F01..F28")
        bits |= 1 << (int(m.group(1)) - 1)
    return bits


# The filters that mean a villager is gone for good: F01 Child and baby deaths, F02 Pregnancy loss, stillbirth and
# death in childbirth, F03 All deaths in events, F04 Disappearances.  An event whose tags name any of them is deadly;
# its GONE count below must then be above 0 (and every other event's 0), so the two can never disagree.
DEADLY_FILTERS = ("F01", "F02", "F03", "F04")


def deadly(filters: list[str]) -> int:
    return 1 if any(code in DEADLY_FILTERS for code in filters) else 0


# The casualty limit below 61 villagers (the owner, 2026-11-27: "below 61 population a max of 1-2 villagers can die
# or disappear"): the most villagers ONE ending of each event can kill or make disappear (SC_MORE_GONE;
# story_collection.inc leaves an event out of the natural draw below 61 villagers when it is above SC_MAX_GONE, 2).
# Read from each event's own effects in native/vvfp_more_island_events (adv_game.kill / adv_game.vanish), its
# largest group:
#   The Aspiring Adventurer  1  the adventurer dies, disappears or joins another tribe (adv_core.inc)
#   The Cave Explorers       2  the two explorers: the map (both leave), the chasm (both fall), both die (cave_effects)
#   The Climb                1  the climber falls (climb_core.inc)
#   The Troubling Signs      5  the five travellers leave on the mission, every answer (troubling_core.inc ts_effects)
#   Diving for Treasure      1  the diver drowns or is lost (dive_core.inc)
#   The Mysterious Mask      9  the five volunteers in every ending, and in a capture the group of children, up to 4
#                               (mask_core.inc mk_effects)
#   The Playful Dolphins, The Remembrance Ceremony, The Rumblings  0  (the tail slap leaves at least 1 health)
GONE = {
    "aspiring_adventurer": 1, "cave_explorers": 2, "the_climb": 1, "troubling_signs": 5,
    "diving_for_treasure": 1, "playful_dolphins": 0, "mysterious_mask": 9, "remembrance_ceremony": 0,
    "remembrance_ceremony_nb": 0, "the_rumblings": 0,
}


def table() -> list[tuple[str, str, tuple[int, ...], list[str], int]]:
    """Each registry entry in order: (entry id, tag table event, games, filters, mask)."""
    tags = tag_table()
    rows = []
    for ident, games in picks():
        event = PICK_TAGS.get(ident)
        if event is None:
            raise SystemExit(f"{ident}: no tag table event (add it to PICK_TAGS)")
        if event not in tags:
            raise SystemExit(f"{ident}: {event} is not in {TAGS.name}")
        filters = sorted(set(tags[event]))
        if ident not in GONE:
            raise SystemExit(f"{ident}: no casualty count (add it to GONE)")
        if (GONE[ident] > 0) != bool(deadly(filters)):
            raise SystemExit(f"{ident}: GONE {GONE[ident]} but its tags {filters} say "
                             f"{'deadly' if deadly(filters) else 'not deadly'}")
        rows.append((ident, event, games, filters, mask(filters)))
    unused = set(tags) - {r[1] for r in rows}
    if unused:
        raise SystemExit(f"{TAGS.name}: {sorted(unused)} is no More Island Events entry")
    return rows


def render() -> str:
    lines = ["/* GENERATED by scripts/build_story_more_filters.py from data/event_collection/content_tags/mie.json --",
             "   do not edit.  The island-event content filters (bit n-1 for Fnn) that keep each of More Island",
             "   Events' entries out, in its registry's order (native/vvfp_more_island_events/mie_pick.inc MIE_PICKS). */",
             "#ifndef VVFP_STORY_MORE_FILTERS_H",
             "#define VVFP_STORY_MORE_FILTERS_H",
             "",
             "static const unsigned int SC_MORE_FILTERS[] = {"]
    rows = table()
    for k, (ident, event, games, filters, bits) in enumerate(rows):
        names = " ".join(filters) if filters else "none"
        comma = "," if k < len(rows) - 1 else ""
        lines.append(f"    0x{bits:08X}u{comma}   /* {k}: {ident} ({event}): {names} */")
    lines += ["};", f"#define SC_MORE_FILTER_COUNT {len(rows)}", "",
              "/* The most villagers one ending of each entry can kill or make disappear (the casualty limit: below 61",
              "   villagers an entry above SC_MAX_GONE stays out of the natural draw unless No Safeguards is on), the",
              "   same order (scripts/build_story_more_filters.py GONE). */",
              "static const unsigned char SC_MORE_GONE[] = {"]
    for k, (ident, event, games, filters, bits) in enumerate(rows):
        comma = "," if k < len(rows) - 1 else ""
        lines.append(f"    {GONE[ident]}{comma}   /* {k}: {ident} */")
    lines += ["};", "", "#endif", ""]
    return "\n".join(lines)


def main() -> None:
    OUT_H.write_bytes(render().encode("ascii"))
    print(OUT_H)


if __name__ == "__main__":
    main()
