"""Game Mechanics: The Tree of Life's Cooking Pit and New Believers' Hand of Bloom in the food estimates, and fish
listed only once each game's fishing is open (the owner, 2026-11-08).

  * The Cooking Pit restored: the fruit is a source that never runs out, with the live worker estimate per speed
    (its 4 fruit spots each free themselves after 45 game-clock seconds, 0x46D563), and the catch-up bonus from the
    save's own working villagers' Farming (FRUITWELLS, 0x468A7A) in the estimates, the farmers needed and time away.
  * Hand of Bloom: the tribe's Divine Energy income from its believers' Devotion, the casts it allows, and each use.
  * The Tree of Life's fishing net only with Fishing Nets solved; New Believers' lake only with The Lake restored.
"""
from __future__ import annotations

import struct
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import vv_game_mechanics as gm  # noqa: E402
import vv_game_mechanics_farmers_vv4 as farmers4  # noqa: E402
import vv_game_mechanics_life as life  # noqa: E402
import vv_game_mechanics_vv4 as vv4  # noqa: E402
import vv_game_mechanics_vv5 as vv5  # noqa: E402

NOW = 1.8e9


def adult(name: str, farming: float, devotion: float = 0.0, game: int = 4) -> life.Person:
    skills = (farming, 10.0, 10.0, 10.0, 10.0) + ((devotion,) if game == 5 else ())
    return life.Person(name, "Male", 30 * life.YEAR, 30 * life.YEAR, 100, False, 0, 1, skills=skills)


def text(facts) -> str:
    return "\n".join(f.text for f in facts)


def render(game: int, data: bytes, people) -> str:
    village = gm.Village(Path("."), game, 1, Path(f"{game}.ldw"), data, frozenset(), NOW)
    module = vv4 if game == 4 else vv5
    with mock.patch.object(life, "people", return_value=people):
        return text(module.facts(village))


def vv4_save(pit: bool, nets: bool) -> bytes:
    data = bytearray(gm.blank_save(4, NOW))
    if pit:
        struct.pack_into("<i", data, vv4.PUZZLE_ENTRIES + 8 * 6, vv4.PUZZLE_THRESHOLDS[6])
    if nets:
        struct.pack_into("<i", data, vv4.PUZZLE_ENTRIES + 8 * 11, vv4.PUZZLE_THRESHOLDS[11])
    struct.pack_into("<i", data, vv4.FOOD, 1000)
    return bytes(data)


class CookingPit(unittest.TestCase):
    TRIBE = [adult("A", 100), adult("B", 100), adult("C", 60), adult("D", 20)]

    def test_the_bonus_comes_from_the_tribes_own_farming(self) -> None:
        page = render(4, vv4_save(True, False), self.TRIBE)
        # 3.75 + 3.75 + 1.75 + 0 at Food Mastery 1
        self.assertIn("This village: 4 working villagers, 3 of them with Farming above 25, so about 9.2 food each "
                      "counted age unit", page)
        self.assertIn("the Cooking Pit adds about", page)
        self.assertIn("the Cooking Pit's 9.2 food each counted age unit taken off first", page)

    def test_live_fruit_trips_have_a_worker_estimate_and_never_run_out(self) -> None:
        page = render(4, vv4_save(True, False), self.TRIBE)
        self.assertIn("The Cooking Pit fruit alone: while catching up no farmer is sent to it", page)
        self.assertRegex(page, r"only about \d+ villagers can work it at once on \w+ speed \(an estimate")
        self.assertIn("the Cooking Pit fruit never runs out, but live only about 14, 7 or 5", page)
        self.assertNotIn("fishing adds without limit", page)
        self.assertEqual(farmers4.TRIPS[2].key, "fruit stomps")
        self.assertEqual(farmers4.TRIPS[2].max_workers, {3: 14, 6: 7, 10: 5})

    def test_nothing_of_the_pit_before_it_is_restored(self) -> None:
        page = render(4, vv4_save(False, False), self.TRIBE)
        self.assertNotIn("The Cooking Pit while catching up (it is restored)", page)
        self.assertNotIn("The Cooking Pit fruit alone", page)

    def test_the_net_is_a_source_only_with_fishing_nets_solved(self) -> None:
        self.assertNotIn("The fishing net alone", render(4, vv4_save(False, False), self.TRIBE))
        page = render(4, vv4_save(False, True), self.TRIBE)
        self.assertIn("fishing adds without limit", page)


def vv5_save(lake: bool, energy: int, cap: int) -> bytes:
    data = bytearray(gm.blank_save(5, NOW))
    if lake:
        struct.pack_into("<i", data, vv5.PROJECTS + 8 * 10, vv5.PUZZLE_THRESHOLDS[10])
    struct.pack_into("<i", data, vv5.ENERGY, energy)
    struct.pack_into("<i", data, vv5.ENERGY_CAP, cap)
    struct.pack_into("<i", data, vv5.FOOD, 1000)
    return bytes(data)


class HandOfBloom(unittest.TestCase):
    TRIBE = [adult("A", 50, 90, 5), adult("B", 50, 60, 5), adult("C", 50, 10, 5)]

    def test_income_casts_and_uses(self) -> None:
        page = render(5, vv5_save(False, 400, 500), self.TRIBE)
        # 9 + 4 + 1 = 14 Divine Energy an age unit; 150 / 14 = 10.7 age units a cast
        self.assertIn("this tribe's 3 believers make about 14 Divine Energy each age unit", page)
        self.assertIn("One cast's worth comes every 10.7 age units", page)
        self.assertIn("2 castable now", page)
        self.assertIn("On the noni bushes: +100 to +199 noni", page)
        self.assertIn("On open ground: 17 to 22 plants", page)

    def test_hard_adds_one_each(self) -> None:
        data = bytearray(vv5_save(False, 400, 500))
        struct.pack_into("<i", data, life.DIFFICULTY_AT[5], 2)
        page = render(5, bytes(data), self.TRIBE)
        self.assertIn("make about 17 Divine Energy each age unit", page)      # 14 + 1 each (the reviewer's figure)
        self.assertIn("One cast's worth comes every 8.8 age units", page)

    def test_noni_near_full_keeps_part_of_the_cast(self) -> None:
        data = bytearray(vv5_save(False, 400, 500))
        struct.pack_into("<i", data, vv5.NONI, 900)
        self.assertIn("now 900, so about 100 noni", render(5, bytes(data), self.TRIBE))

    def test_below_150_cap_it_cannot_be_cast(self) -> None:
        self.assertIn("The cap is below 150, so Hand of Bloom cannot be cast yet.",
                      render(5, vv5_save(False, 50, 100), self.TRIBE))

    def test_the_lake_is_a_source_only_once_restored(self) -> None:
        self.assertNotIn("Fishing at the lake alone", render(5, vv5_save(False, 0, 100), self.TRIBE))
        self.assertIn("fishing adds without limit", render(5, vv5_save(True, 0, 100), self.TRIBE))


if __name__ == "__main__":
    unittest.main()
