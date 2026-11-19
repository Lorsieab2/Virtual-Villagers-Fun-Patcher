"""Game Mechanics: unlimited fishing counted as a food source in all five games (the owner, 2026-11-19: "once
unlimited fishing is unlocked in all 5 games, the game mechanics screen should also show how many farmers/fishing
catches it takes to sustain the village too, and fishing should be counted as a food source too").

  * Before the unlock, fishing is not counted, and the page says what unlocks it: A New Home Farming level 3 with
    the beach cleaned, The Lost Children Sustainable Fishing (from Farming level 2; before it the lake is a limited
    source), The Secret City The Sharks, The Tree of Life Fishing Nets, New Believers The Lake.
  * After it, At a glance, the food estimates and the farmers needed give the farmers and the catches per real-life
    hour (live, and for each hour of time away counted) that feed the village on fishing alone, with the game's own
    food a catch, and fishing's share with all the sources together.
"""
from __future__ import annotations

import re
import struct
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import vv_game_mechanics as gm  # noqa: E402
import vv_game_mechanics_life as life  # noqa: E402
import vv_game_mechanics_vv1 as vv1  # noqa: E402
import vv_game_mechanics_vv2 as vv2  # noqa: E402
import vv_game_mechanics_vv3 as vv3  # noqa: E402
import vv_game_mechanics_vv4 as vv4  # noqa: E402
import vv_game_mechanics_vv5 as vv5  # noqa: E402

NOW = 1.8e9
MODULES = {1: vv1, 2: vv2, 3: vv3, 4: vv4, 5: vv5}
NOT_YET = "Fishing is not counted as a food source yet: "


def adult(game: int, farming: float = 50.0) -> life.Person:
    skills = (farming, 10.0, 10.0, 10.0, 10.0) + ((50.0,) if game == 5 else ())
    return life.Person(f"V{game}", "Male", 30 * life.YEAR, 30 * life.YEAR, 100, False, 0, 1, skills=skills)


def render(game: int, data: bytes) -> str:
    village = gm.Village(Path("."), game, 1, Path(f"{game}.ldw"), data, frozenset(), NOW)
    tribe = [adult(game) for _ in range(20)]
    with mock.patch.object(life, "people", return_value=tribe):
        return "\n".join(f.text for f in MODULES[game].facts(village))


def save(game: int, unlocked: bool, **extra) -> bytes:
    data = bytearray(gm.blank_save(game, NOW))
    if game == 1:
        struct.pack_into("<i", data, vv1.LEVELS + 8 * vv1.FARMING, extra.get("farming", 3))
        data[vv1.BEACH_FLAG] = 1 if unlocked else 0
        struct.pack_into("<i", data, vv1.FOOD, 1000)
    elif game == 2:
        struct.pack_into("<i", data, vv2.LEVELS + 8 * vv2.FARMING_LEVEL + vv2.S, 3)
        data[vv2.SUSTAINABLE_FISHING + vv2.S] = 1 if unlocked else 0
        struct.pack_into("<i", data, vv2.FISH + vv2.S, extra.get("fish", 0))
    elif game == 3:
        struct.pack_into("<i", data, vv3.HEADER + vv3.PUZZLES + 4 + 8 * vv3.SHARKS,
                         vv3.PUZZLE_THRESHOLDS[vv3.SHARKS] if unlocked else 0)
    elif game == 4:
        struct.pack_into("<i", data, vv4.PUZZLE_ENTRIES + 8 * 11, vv4.PUZZLE_THRESHOLDS[11] if unlocked else 0)
        struct.pack_into("<i", data, vv4.FOOD, 1000)
    else:
        struct.pack_into("<i", data, vv5.PROJECTS + 8 * 10, vv5.PUZZLE_THRESHOLDS[10] if unlocked else 0)
        struct.pack_into("<i", data, vv5.FOOD, 1000)
    return bytes(data)


# The game's food a catch at Normal speed (Food Mastery 1, Farming 50: no crab), live and while catching up.
FOOD_A_CATCH = {1: (9, 9), 2: (8, 8), 3: (8, 8), 4: (4, 4), 5: (4, 4)}
UNLOCK = {1: "fishing opens at Farming level 3 with the beach cleaned (The Beach)",
          2: "unlimited fishing opens once Sustainable Fishing is solved, from Farming level 2",
          3: "fishing opens once The Sharks is solved",
          4: "fishing opens once Fishing Nets is solved",
          5: "fishing opens once The Lake is restored"}
LINE = re.compile(r"Fishing never runs out: to feed all (\d+) who eat on fishing alone \(([\d,]+) food per real-life "
                  r"hour on Normal speed\) takes live, (\d+) farmers? bringing about ([\d,.]+) catches per real-life "
                  r"hour \((\S+) food a catch\); while catching up, (\d+) farmers? bringing about ([\d,.]+) catches "
                  r"for each real-life hour of time away counted \((\S+) food a catch\)\.")


def number(text: str) -> float:
    return float(text.replace(",", ""))


class BeforeTheUnlock(unittest.TestCase):
    def test_fishing_is_not_counted_and_the_page_says_what_unlocks_it(self) -> None:
        for game in MODULES:
            with self.subTest(game=game):
                page = render(game, save(game, False))
                self.assertIn(NOT_YET + UNLOCK[game], page)
                self.assertNotIn("Fishing never runs out:", page)
                self.assertNotIn("fishing adds without limit", page)
                self.assertNotRegex(page, r"(Fishing|Fish|The fishing net|Fishing at the lake) alone: while catching up")

    def test_a_new_home_needs_the_beach_cleaned_as_well_as_farming_level_3(self) -> None:
        page = render(1, save(1, False, farming=3))
        self.assertIn("this village is at Farming level 3 and its beach is not cleaned.", page)
        self.assertNotIn("Fishing alone", page)
        self.assertIn(NOT_YET, render(1, save(1, True, farming=2)))

    def test_the_lost_children_keeps_the_limited_lake_before_sustainable_fishing(self) -> None:
        page = render(2, save(2, False, fish=700))
        self.assertIn(NOT_YET + UNLOCK[2] + "; until then the lake's fish are a limited source that never grows back "
                      "(700 left", page)
        self.assertIn("Fish: 700 (they never grow back)", page)
        self.assertRegex(page, r"Fish alone: while catching up, .*It cannot feed the village alone")


class AfterTheUnlock(unittest.TestCase):
    def test_farmers_and_catches_with_the_games_food_a_catch(self) -> None:
        for game in MODULES:
            with self.subTest(game=game):
                page = render(game, save(game, True))
                self.assertNotIn(NOT_YET, page)
                found = LINE.findall(page)
                # At a glance and the food estimates.
                self.assertEqual(len(found), 2, page)
                eaters, eaten, live_n, live_c, live_food, caught_n, caught_c, caught_food = found[1]
                self.assertEqual(int(eaters), 20)
                self.assertEqual((number(live_food), number(caught_food)), FOOD_A_CATCH[game])
                self.assertAlmostEqual(number(live_c), number(eaten) / FOOD_A_CATCH[game][0], delta=0.6)
                self.assertAlmostEqual(number(caught_c), number(eaten) / FOOD_A_CATCH[game][1], delta=0.6)
                # The same farmers as the Farmers needed line for fishing alone, which gives the catches too.
                alone = re.search(r"(?:Fishing|Fish|The fishing net|Fishing at the lake) alone: while catching up, "
                                  r"(\d+) farmers?; live, (\d+) farmers?\. It never runs out: about ([\d,.]+) catches "
                                  r"per real-life hour live and about ([\d,.]+) for each real-life hour of time away "
                                  r"counted while catching up feed the village", page)
                self.assertIsNotNone(alone, page)
                self.assertEqual((alone[1], alone[2], alone[3], alone[4]), (caught_n, live_n, live_c, caught_c))
                # Fishing's share with all the sources together.
                self.assertRegex(page, r"All food sources together: .*Fishing brings about \d+% while catching up "
                                       r"and \d+% live of the food the village eats")

    def test_food_mastery_raises_the_food_a_catch(self) -> None:
        data = bytearray(save(5, True))
        struct.pack_into("<i", data, vv5.LEVELS + 4 * vv5.FOOD_MASTERY, 3)
        found = LINE.findall(render(5, bytes(data)))
        self.assertEqual((found[1][4], found[1][7]), ("8", "8"))

    def test_the_shortfall_can_be_fished(self) -> None:
        page = render(3, save(3, True))
        self.assertRegex(page, r"Mushrooms to make up the shortfall: .*; or fishing: about [\d,.]+ catches a "
                               r"real-life hour \(\d+ farmers? live\)\.")
        self.assertRegex(page, r"To fill the gap .*; or fishing: live about [\d,.]+ catches per real-life hour "
                               r"\(\d+ farmers?\); while catching up about [\d,.]+ catches for each real-life hour of "
                               r"time away counted \(\d+ farmers?\)\.")


if __name__ == "__main__":
    unittest.main()
