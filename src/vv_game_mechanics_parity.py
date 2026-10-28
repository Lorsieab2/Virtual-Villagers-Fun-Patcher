"""Game Mechanics: the same topics on all five tabs (the owner, 2026-10-27, emphatic: "Same between the virtual villagers
games").

TOPICS lists every kind of entry that any game's tab has (a technology's levels, the puzzles, the huts, the fire, the
stews, the potions, the God powers, ...) and, for each of the five games, either
  * where its entry is: a pattern that the start of one of that tab's lines matches (ENTRY), or
  * that the game does not have it: one line, "<topic>: Not in <game>." and what was checked, with its label (NOT_IN).
parity_facts() gives a game's "Not in" lines, all in the Technologies, items and buildings group (no new group: the
window's group links have no room for one, src/vv_game_mechanics_window.py).  tests/test_game_mechanics_parity.py
checks that every topic is on every tab, as an entry or as one "Not in" line, never both.

HOW "NOT IN" WAS CHECKED (2026-10-27, research/stock-executables): every printable text in the game's stock exe was
searched for the topic's own words.  Where none is there (no stew, potion, totem, statue, faction, Divine Energy or
Heathen text at all) the game has no screen, message, job or puzzle for it, and the line is gm.CODE.  Where the exe
still holds text for it that the game's code was not traced to reach (the later games carry text copied from the
earlier ones, as their unused island events show), the line says so and is UNCONFIRMED.
Read only: nothing here writes anything.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

import vv_game_mechanics as gm

GAME_NAMES = {1: "A New Home", 2: "The Lost Children", 3: "The Secret City", 4: "The Tree of Life",
              5: "New Believers"}
C, U = gm.CODE, False


@dataclass(frozen=True)
class Topic:
    """One kind of entry.  `entry`: game -> a regex the start of a line on that game's tab matches (its entry).
    `not_in`: game -> (what was checked, its label) for a game without it.  Every game is in exactly one."""
    name: str
    entry: dict[int, str] = field(default_factory=dict)
    not_in: dict[int, tuple[str, bool | str]] = field(default_factory=dict)


def _none(words: str) -> str:
    return f"its stock exe holds no text with {words} in it"


def _inherited(words: str) -> str:
    return (f"none is among its puzzles, buildings and items on this tab; its stock exe still holds {words}, text "
            "the game's code was not traced to reach")


TOPICS: tuple[Topic, ...] = (
    Topic("Technology levels 1 to 3", entry={
        1: r"Farming level 1: ", 2: r"Farming level 1: ", 3: r"Science level 1: ", 4: r"Science level 1: ",
        5: r"Science level 1 \("}),
    Topic("Puzzles", entry={
        1: r"The Well: Solved ", 2: r"Fire: Solved ", 3: r"The First Chief: solved ", 4: r"The Cutting Tool: solved ",
        5: r"The Sick Heathen \("}),
    Topic("Population huts", entry={
        1: r"Population huts: ", 2: r"Population huts: ", 3: r"The first hut: ", 4: r"Hut 1: ", 5: r"Hut 1 \("}),
    Topic("Fixing huts", entry={
        1: r"Hut repair ", 2: r"Hut repair ", 3: r"Fixing huts: ", 4: r"Fixing huts: ", 5: r"Fixing a hut "}),
    Topic("The fire", entry={2: r"The fire pit: ", 3: r"The campfire: ", 4: r"The Fire Pit: ", 5: r"The fire pit \("},
          not_in={1: (_none("\"firewood\", \"fire pit\" or \"campfire\"") + " (its only \"fire\" is in a story "
                      "line), and no fire is among its puzzles or buildings", C)}),
    Topic("Mushrooms", entry={1: r"Mushrooms: ", 2: r"Mushrooms: ", 3: r"Mushrooms: ", 4: r"Mushrooms: ",
                              5: r"Brown mushroom \("}),
    # A New Home's own line already says it has none ("Collectibles: A New Home has none."), checked in its code.
    Topic("Collections", entry={
        1: r"Collectibles: A New Home has none", 2: r"Butterfly Collection: ", 3: r"Turtle Shell Collection: ",
        4: r"The Fish Scale collection: ", 5: r"Relics \("}),
    Topic("A snack at the food store", entry={
        1: r"The food store: ", 2: r"A snack \(the food store\): ", 3: r"A snack at the food bin: ",
        4: r"A snack at the food bin: ", 5: r"A snack at the food bin \("}),
    Topic("Fishing", entry={
        1: r"With The Beach cleaned, farmers fish", 2: r"Sustainable Fishing: ", 3: r"Fish and the crab: ",
        4: r"Fish and the Golden Fish: ", 5: r"A noni pick gives .*fishing at the lake gives"}),
    Topic("New clothes", entry={
        1: r"Clothing \(F6\): ", 2: r"The Sewing Hut: ", 3: r"New clothes: ", 4: r"New clothes: ",
        5: r"A change of clothes \("}),
    Topic("Herbs", entry={1: r"Herb Mastery: ", 2: r"Herb Mastery: ", 3: r"The herbs: ", 4: r"The herbs: "},
          not_in={5: (_inherited("\"Showing baby the herbs\" and \"The herbs are ready to make a stew.\""), U)}),
    Topic("Stews", entry={2: r"Stews: ", 4: r"Spicy stew: "},
          not_in={1: (_none("\"stew\""), C),
                  3: (_inherited("\"A hot stew is ready!\" and an island event's \"stews\""), U),
                  5: (_inherited("\"Eating some stew\" and \"This stew needs something nutritious!\""), U)}),
    Topic("Potions", entry={3: r"Potion 0 "},
          not_in={1: (_none("\"potion\""), C), 2: (_none("\"potion\""), C),
                  4: (_inherited("\"Potion Made\" (eTipPuzzlePotionsMade) and \"eSayUsePotion\""), U),
                  5: (_inherited("\"eSayUsePotion\" and island events' potions"), U)}),
    Topic("Totems", entry={2: r"The Elder Totem: ", 5: r"The Hungry Totem \("},
          not_in={1: (_none("\"totem\""), C),
                  3: (_inherited("\"Honoring totem\", the villager's \"'s totem\" and the Elder title"), U),
                  4: (_inherited("\"eTotemsMade\" and the Elder sayings"), U)}),
    Topic("Statues", entry={3: r"The Statue: ", 5: r"The Tribute Statue \("},
          not_in={1: (_none("\"statue\"") + " (its idol is The Idol, a puzzle)", C),
                  2: (_inherited("\"statue\" only in story and island-event lines"), U),
                  4: (_inherited("\"the majestic fish statue\" only as a villager's saying"), U)}),
    Topic("God powers", entry={5: r"The 11 God Powers "},
          not_in={g: (_none("\"Divine Energy\", \"energy\" as a power's currency, \"Lightning Strike\", "
                            "\"Earthquake\" or \"Fog of Doom\"") + "; its \"divine\" is only in a story line"
                      if g in (1, 4) else
                      _none("\"Divine Energy\", \"Lightning Strike\", \"Earthquake\" or \"Fog of Doom\""), C)
                  for g in (1, 2, 3, 4)}),
    Topic("Faith and Heathens", entry={5: r"Faith|Heathen"},
          not_in={g: (_none("\"heathen\" or \"faith\""), C) for g in (1, 2, 3, 4)}),
    Topic("Golden Child", entry={1: r"The Golden Child: "},
          not_in={2: ("no Golden Child is among its 16 puzzles (Puzzles) and no birth makes one; the name is only in a "
                      "story line", U),
                  3: (_none("\"Golden Child\""), C), 4: (_none("\"Golden Child\""), C),
                  5: ("no Golden Child is among its puzzles; the name is only in an island event's story", U)}),
    Topic("The Tribal Chief's powers", entry={3: r"Grant Food \(the chief's power\): "},
          not_in={1: (_none("\"tribal chief\""), C), 2: (_none("\"tribal chief\""), C),
                  4: (_inherited("a \"Tribal Chief\" label and a story line"), U),
                  5: (_inherited("a \"Tribal Chief\" label"), U)}),
    Topic("Factions", entry={3: r"Choosing a faction: "},
          not_in={1: (_none("\"faction\""), C), 2: (_none("\"faction\""), C),
                  4: (_inherited("The Secret City's \"You have already chosen your faction!\""), U),
                  5: (_inherited("The Secret City's \"You have already chosen your faction!\""), U)}),
    Topic("The Gong of Wonder", entry={2: r"The Gong of Wonder: "},
          not_in={1: (_none("\"Gong of Wonder\"") + " (only a gong sound file)", C),
                  3: (_none("\"Gong of Wonder\"") + " (only gong sound files)", C),
                  4: (_none("\"Gong of Wonder\"") + " (only gong sound files)", C),
                  5: (_none("\"Gong of Wonder\"") + " (only gong sound files)", C)}),
    Topic("Origins upgrades", entry={1: r"Origins: Time Warp: ", 2: r"Origins: Time Warp: ", 3: r"Time Warp: ",
                                     4: r"Time Warp: ", 5: r"Time Warp \(50,000"}),
)


def not_in_text(topic: Topic, game: int) -> str:
    checked, _label = topic.not_in[game]
    return f"{topic.name}: Not in {GAME_NAMES[game]}. Checked: {checked}."


def parity_facts(village: gm.Village) -> list[gm.Fact]:
    """The game's "Not in" lines, one for each topic it does not have, in the ITEMS group."""
    return [gm.Fact(gm.ITEMS, not_in_text(topic, village.game), topic.not_in[village.game][1])
            for topic in TOPICS if village.game in topic.not_in]


def table(facts_by_game: dict[int, list[gm.Fact]]) -> dict[str, dict[int, str]]:
    """topic -> game -> "entry", "Not in" or "UNCONFIRMED" (a Not in line that is not verified), read from each tab's
    lines; "missing" when the tab has neither (what the test forbids)."""
    out: dict[str, dict[int, str]] = {}
    for topic in TOPICS:
        row = {}
        for game, facts in facts_by_game.items():
            if game in topic.not_in:
                text = not_in_text(topic, game)
                found = [f for f in facts if f.text == text]
                row[game] = ("Not in" if found and found[0].confirmed else "UNCONFIRMED") if found else "missing"
            else:
                pattern = re.compile(topic.entry[game])
                row[game] = "entry" if any(pattern.match(f.text) for f in facts) else "missing"
        out[topic.name] = row
    return out
