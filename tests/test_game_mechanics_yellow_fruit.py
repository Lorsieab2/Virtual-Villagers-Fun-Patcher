"""Game Mechanics (The Tree of Life): "Yellow Fruit Trees are No Longer Unlimited" on the page and in the estimates.

  * the patch's own lines under Food sources and Refills, with the tree's supply read from the companion's file for
    the save's slot ("Virtual Villagers Fun Patcher\\Save <S>\\Data\\Fruit Trees\\Virtual Villagers 4 Yellow Fruit Tree -
    Save <S>.dat") when it belongs to this village, and the refill rule (full every 40 age units);
  * with the patch the Cooking Pit fruit is a limited source (the fruit left, capped at 1,000, refilled to full every
    40 age units, like A New Home's crop field) and the catch-up bonus is capped by the fruit the tree gives (1,000
    every 40 units at 5 a bonus);
  * without it, the page is as before (the fruit never runs out).
"""
from __future__ import annotations

import struct
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import vv_game_mechanics as gm  # noqa: E402
import vv_game_mechanics_life as life  # noqa: E402
import vv_game_mechanics_vv4 as vv4  # noqa: E402
from test_game_mechanics_cooking_pit_and_bloom import adult, text, vv4_save  # noqa: E402
from test_vv4_yellow_fruit_trees_limited import identity, tree_file  # noqa: E402

NOW = 1.8e9
TRIBE = [adult("A", 100), adult("B", 100), adult("C", 60), adult("D", 20)]


def render(folder: Path, installed: frozenset, *, living=frozenset(), people=TRIBE) -> str:
    village = gm.Village(folder, 4, 1, folder / "Virtual Villagers - The Tree of Life1.ldw", vv4_save(True, False),
                         installed, NOW)
    with mock.patch.object(life, "people", return_value=people), \
            mock.patch.object(vv4, "fruit_living", return_value=set(living)):
        return text(vv4.facts(village))


class YellowFruitPage(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.folder = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def write(self, data: bytes, slot: int = 1) -> None:
        path = self.folder / "Virtual Villagers Fun Patcher" / f"Save {slot}" / "Data" / "Fruit Trees" / \
            f"Virtual Villagers 4 Yellow Fruit Tree - Save {slot}.dat"
        path.parent.mkdir(parents=True)
        path.write_bytes(data)

    def test_the_identity_is_the_companions(self) -> None:
        self.assertEqual(vv4.fruit_identity(1, b"Ana\0junk", b"", b""), identity("Ana"))
        self.assertEqual(vv4.fruit_identity(0, b"Bo", b"Dad", b"Mum"), identity("Bo", 0, "Dad", "Mum"))

    def test_the_patch_lines_and_the_supply_from_the_file(self) -> None:
        self.write(tree_file(412, units=30, roster=[identity("Ana")]))
        page = render(self.folder, frozenset({vv4.YELLOW_FRUIT}), living={identity("Ana")})
        self.assertIn("Yellow Fruit Trees are No Longer Unlimited\" is in the game: the yellow fruit tree holds at "
                      "most 1,000 fruit, refilled to full every 40 age units", page)
        self.assertIn("412 of 1,000 fruit left; refilled to full after 10 more age units", page)
        self.assertIn("the yellow fruit tree is refilled to 1,000 every 40 age units", page)
        self.assertIn("Food Mastery multiplies the food, not the fruit taken", page)
        self.assertIn("Dendrology", page)

    def test_another_villages_file_is_not_this_villages_supply(self) -> None:
        self.write(tree_file(2, roster=[identity("Old")]))
        page = render(self.folder, frozenset({vv4.YELLOW_FRUIT}), living={identity("New")})
        self.assertIn("no file of the patch's for this village, so the tree is full (1,000 fruit)", page)
        self.assertNotIn("2 of 1,000 fruit left", page)

    def test_the_cooking_pit_fruit_is_a_limited_source(self) -> None:
        self.write(tree_file(412, units=30, roster=[identity("Ana")]))
        village = gm.Village(self.folder, 4, 1, self.folder / "x1.ldw", vv4_save(True, False),
                             frozenset({vv4.YELLOW_FRUIT}), NOW)
        seen = []
        real = life.Context

        def capture(*a, **k):
            ctx = real(*a, **k)
            seen.append(ctx)
            return ctx

        with mock.patch.object(life, "people", return_value=TRIBE), \
                mock.patch.object(vv4, "fruit_living", return_value={identity("Ana")}), \
                mock.patch.object(life, "Context", side_effect=capture):
            vv4.facts(village)
        fruit = [s for s in seen[0].sources if s.name == "The Cooking Pit fruit"]
        self.assertEqual(len(fruit), 1)
        s = fruit[0]
        self.assertFalse(s.unlimited)
        self.assertEqual((s.amount, s.cap, s.step, s.per_unit), (412, 1000, 1000, 1000 / 40))
        self.assertEqual(s.first_in, gm.real_seconds(10 * 360, seen[0].speed_value))
        # Without the patch: the stock source, unlimited.
        stock = gm.Village(self.folder, 4, 1, self.folder / "x1.ldw", vv4_save(True, False), frozenset(), NOW)
        seen.clear()
        with mock.patch.object(life, "people", return_value=TRIBE), \
                mock.patch.object(life, "Context", side_effect=capture):
            vv4.facts(stock)
        self.assertTrue([s for s in seen[0].sources if s.name == "The Cooking Pit fruit"][0].unlimited)

    def test_the_catch_up_bonus_is_capped_by_the_fruit(self) -> None:
        big = [adult(f"V{i}", 100) for i in range(20)]               # 20 x 3.75 = 75 food a unit
        page = render(self.folder, frozenset({vv4.YELLOW_FRUIT}), people=big)
        # 1,000 fruit / 5 a bonus / 40 units = 5 bonuses a unit, 25 food at Food Mastery 1.
        self.assertIn("so at most 25.0 food a unit on average, not 75.0", page)
        self.assertIn("so about 25.0 food each counted age unit", page)
        small = render(self.folder, frozenset({vv4.YELLOW_FRUIT}))
        self.assertIn("this village's bonuses fit in the tree's 1,000 fruit every 40 age units", small)
        self.assertIn("so about 9.2 food each counted age unit", small)
        stock = render(self.folder, frozenset(), people=big)
        self.assertIn("so about 75.0 food each counted age unit", stock)
        self.assertNotIn("Yellow Fruit Trees", stock)


if __name__ == "__main__":
    unittest.main()


class YellowBreadfruitEvent(unittest.TestCase):
    """The patch's own island event, A Closer Look (Yellow Breadfruit), under Island events: only with the patch."""

    def events(self, installed: frozenset) -> str:
        import vv_game_mechanics_events as events
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            village = gm.Village(folder, 4, 1, folder / "Virtual Villagers - The Tree of Life1.ldw",
                                 vv4_save(True, False), installed, NOW)
            return " ".join(f.text for f in events.facts(village))

    def test_listed_with_its_conditions_and_effect_only_with_the_patch(self) -> None:
        page = self.events(frozenset({vv4.YELLOW_FRUIT}))
        self.assertIn("A Closer Look (Blackberries) -- needs a living villager of any age", page)
        self.assertIn("A Closer Look (Yellow Breadfruit) -- needs the Cooking Pit restored and a living villager of "
                      "any age; added by \"Yellow Fruit Trees are No Longer Unlimited\"", page)
        self.assertIn("The Cooking Pit's yellow fruit tree gains 350 fruit, up to its 1,000, and the villager walks "
                      "to the tree", page)
        stock = self.events(frozenset())
        self.assertIn("A Closer Look (Blackberries)", stock)
        self.assertNotIn("Yellow Breadfruit", stock)
