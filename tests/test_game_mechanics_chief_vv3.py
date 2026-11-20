"""Game Mechanics: the owner's answers on #819 (2026-11-19).

  * Expert fishers: a second fishing line where crabs come (A New Home from Farming 90, The Secret City from 88),
    with the crab's chance and food, live and while catching up, in the same places as the Farming 50 line.
  * The Secret City's Tribal Chief: its bonus on fish counted when it directs the sea, and its own group, "Tribal
    Chief: Directing work", with this save's live state, every site's bonus, catch-up and the patches.
  * "Once The Sharks puzzle is solved, the sea never runs out."
  * At a glance and the food estimates give one shortfall (life.shortfall_hour), the refills as refills() counts
    them: a full source adds nothing until it is picked.
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
sys.path.insert(0, str(ROOT / "tests"))

import vv_game_mechanics as gm  # noqa: E402
import vv_game_mechanics_chief_vv3 as chief  # noqa: E402
import vv_game_mechanics_life as life  # noqa: E402
import vv_game_mechanics_vv3 as vv3  # noqa: E402
import vv_game_mechanics_vv4 as vv4  # noqa: E402
from test_game_mechanics_fishing_source import LINE, number, render, save  # noqa: E402

NOW = 1.8e9
EXPERT = re.compile(r"Expert fishers \(Farming 100; ([^)]*)\), to feed the same village on \w+ speed: live, (\d+) farmers? bringing about ([\d,.]+) catches "
                    r"per real-life hour \(([\d.]+) food a catch\); while catching up, (\d+) farmers? bringing about "
                    r"([\d,.]+) catches for each real-life hour of time away counted \(([\d.]+) food a catch\)\.")


def vv3_save(leadership: int = 2, sharks: bool = True) -> bytes:
    data = bytearray(save(3, sharks))
    struct.pack_into("<i", data, vv3.HEADER + vv3.TECHS + 4 * vv3.LEADERSHIP, leadership)
    return bytes(data)


def vv3_page(data: bytes, boss: chief.Chief | None) -> str:
    with mock.patch.object(chief, "chief", return_value=boss):
        return render(3, data)


def group(page_facts: list[gm.Fact]) -> list[str]:
    return [f.text for f in page_facts if f.group == chief.GROUP]


class ExpertFishers(unittest.TestCase):
    def test_a_new_home_crabs_from_farming_90(self) -> None:
        page = render(1, save(1, True))
        found = EXPERT.findall(page)
        self.assertEqual(len(found), 2)                       # At a glance and the food estimates
        words, live_n, live_c, live_food, caught_n, caught_c, caught_food = found[0]
        self.assertIn("from Farming 90, 21 catches in 100 are a crab worth 55 food instead of 9", words)
        self.assertEqual(float(live_food), 18.66)             # 0.21 x 55 + 0.79 x 9
        self.assertEqual(float(caught_food), 18.66)
        eaten = number(LINE.findall(page)[0][1])
        self.assertAlmostEqual(number(live_c), eaten / 18.66, delta=0.06)
        # Fewer farmers than at Farming 50, in the Farmers needed line too.
        plain = LINE.findall(page)[0]
        self.assertLess(int(live_n), int(plain[2]))
        self.assertRegex(page, r"Fishing alone: .*; expert fishers \(Farming 100, crabs included\): live, "
                               + live_n + r" farmers? and about " + re.escape(live_c))

    def test_the_secret_city_crabs_from_farming_88(self) -> None:
        page = vv3_page(vv3_save(), None)
        found = EXPERT.findall(page)
        self.assertEqual(len(found), 2)
        self.assertIn("from Farming 88, 10 catches in 100 are a crab worth 55 food instead of a fish", found[0][0])
        self.assertEqual((float(found[0][3]), float(found[0][6])), (12.7, 12.7))      # 0.1 x 55 + 0.9 x 8

    def test_no_expert_line_where_no_crab_comes(self) -> None:
        for game in (2, 4, 5):
            with self.subTest(game=game):
                self.assertNotIn("Expert fishers", render(game, save(game, True)))


class ChiefOnFish(unittest.TestCase):
    def test_directing_the_sea_counts_a_third_on_the_roll(self) -> None:
        boss = chief.Chief("Chief", chief.SEA, False, 100)
        page = vv3_page(vv3_save(leadership=2), boss)
        # 8 + 50% x (8 // 3) = 9 food a fish at Normal, and 9 while catching up.
        found = LINE.findall(page)
        self.assertEqual((found[1][4], found[1][7]), ("9", "9"))
        self.assertIn("the Tribal Chief directing the sea adds a third to a fish 50% of the time, counted", page)
        # The expert's fish get it too, its crabs do not: 0.1 x 55 + 0.9 x 9.
        self.assertEqual(float(EXPERT.findall(page)[0][3]), 13.6)

    def test_no_bonus_elsewhere_sick_or_at_leadership_0(self) -> None:
        for boss, leadership in ((chief.Chief("Chief", chief.TREE, False, 100), 2),
                                 (chief.Chief("Chief", chief.SEA, True, 100), 2),
                                 (chief.Chief("Chief", chief.SEA, False, 100), 0), (None, 2)):
            with self.subTest(boss=boss, leadership=leadership):
                page = vv3_page(vv3_save(leadership=leadership), boss)
                self.assertEqual(LINE.findall(page)[1][4], "8")
                self.assertIn("no Tribal Chief directs the sea now, so no chief bonus is counted", page)


class DirectingWork(unittest.TestCase):
    def facts(self, boss, leadership: int = 2) -> list[str]:
        village = gm.Village(Path("."), 3, 1, Path("3.ldw"), vv3_save(leadership), frozenset(), NOW)
        with mock.patch.object(chief, "chief", return_value=boss):
            return [f.text for f in chief.facts(village, leadership, 1, lambda pid: pid == 7)]

    def test_its_own_group_on_the_page_in_order(self) -> None:
        self.assertIn(chief.GROUP, gm.GROUPS)
        page_facts = [f for f in gm.general(3, now=NOW)]
        self.assertIsInstance(page_facts, list)
        with mock.patch.object(chief, "chief", return_value=None):
            village = gm.Village(Path("."), 3, 1, Path("3.ldw"), vv3_save(), frozenset(), NOW)
            with mock.patch.object(life, "people", return_value=[]):
                self.assertTrue(group(vv3.facts(village)))

    def test_live_state_first(self) -> None:
        self.assertIn("Chief, the Tribal Chief, is directing work at the sea: each fish caught gets a third more",
                      self.facts(chief.Chief("Chief", chief.SEA, False, 100))[0])
        self.assertIn("(50% of the time at Leadership 2)", self.facts(chief.Chief("Chief", chief.SEA, False, 100))[0])
        self.assertIn("The chief is sick now, so the roll never passes",
                      self.facts(chief.Chief("Chief", chief.HIVE, True, 100))[0])
        self.assertIn("That work is finished, so the chief stops directing it",
                      self.facts(chief.Chief("Chief", 0x16, False, 100))[0])          # The Ancient Bath (7) solved
        self.assertIn("is not directing any work", self.facts(chief.Chief("Chief", 0, False, 100))[0])
        self.assertIn("This village has no Tribal Chief now", self.facts(None)[0])
        self.assertIn("Leadership is 0 in this village, so directing work never adds anything",
                      "\n".join(self.facts(chief.Chief("Chief", chief.SEA, False, 100), leadership=0)))
        self.assertIn("nothing in the stock game (the chief stops at once)",
                      self.facts(chief.Chief("Chief", 9, False, 100))[0])

    def test_every_site_catch_up_and_the_patches(self) -> None:
        text = "\n".join(self.facts(chief.Chief("Chief", chief.SEA, False, 100)))
        for words in ("The sea (once The Sharks is solved): each fish caught gets a third more",
                      "Any fruit tree: each fruit pick, from any tree, adds a third more food",
                      "The bee hive (once The Bee Hive is solved): each honey take adds half as much again",
                      "Research: each research session that pays adds a third more tech points at Science level 0, "
                      "a quarter more",
                      "Any hut: each building step on any hut adds 1 more",
                      "The Ancient Bath: each work step adds 1 more", "The Roster of the Dead: each work step adds 1",
                      "The Ruins: each work step adds 1 more",
                      "The Statue's scaffolding (the chief can be dropped there only at Leadership 3): each load",
                      "25%, 50% or 75% at Leadership 1, 2 or 3, never at 0",
                      "the chief gets no job turns of its own, but the others' work at its site still asks the roll",
                      "fish 8 becomes 10", "an owned Food Point Doubler doubles fruit and honey picks, fish and crabs",
                      "an owned Tech Point Doubler doubles the research points, the chief's research bonus included",
                      "Tribal Chief Supervises the Hospital", "Learning Skills Never Fails",
                      # renamed from "Builders and Healers Work First" (0c05629f4; data/vv3_work_first_feature.json)
                      "Fruit Counts When It Reaches the Food Bin", "Villagers Work Their Own Job First",
                      "No other patch changes the chief's site, the roll or the bonus",
                      "no Food Mastery and no \"Food Gains are Flat\" patch"):
            self.assertIn(words, text)

    def test_the_check_before_directing_is_the_sick(self) -> None:
        text = "\n".join(self.facts(chief.Chief("Chief", chief.SEA, False, 100)))
        self.assertIn("if any villager is \"Not feeling well\" at that moment", text)
        self.assertIn("the chief always goes \"Concerned about the sick\" instead", text)
        self.assertIn("There are no odds on it", text)
        self.assertNotIn("not traced", text)
        stock = ROOT / "research" / "stock-executables" / "Virtual Villagers - The Secret City.exe"
        if not stock.is_file():
            self.skipTest("stock executables not present")
        exe = stock.read_bytes()
        # 0x45BDD8: push 0x2D (the behaviour looked for), then on a hit push 0x8A (the chief's own) at 0x45BDED.
        self.assertEqual(exe[0x5BDD8:0x5BDDA], bytes.fromhex("6A2D"))
        self.assertEqual(exe[0x5BDED:0x5BDF2], bytes.fromhex("688A000000"))
        import island_event_exe as strings
        if strings.available(3):
            self.assertEqual((strings.text(3, 0x11C), strings.text(3, 0x1E4)),
                             ("Not feeling well", "Concerned about the sick"))

    def test_the_roll_matches_the_exe(self) -> None:
        self.assertEqual([chief.chance(n) for n in range(4)], [0.0, 0.25, 0.5, 0.75])
        stock = ROOT / "research" / "stock-executables" / "Virtual Villagers - The Secret City.exe"
        if not stock.is_file():
            self.skipTest("stock executables not present")
        exe = stock.read_bytes()
        # 0x45FC60 at file offset 0x5FC60 (the code section maps 0x401000 to 0x1000): its leadership x 0x19 and
        # rand(0x64), and the fish bonus's site 0x1C push at 0x458EBF.
        self.assertEqual(exe[0x5FC9A:0x5FC9D], bytes.fromhex("6BF619"))
        self.assertEqual(exe[0x5FC98:0x5FC9A], bytes.fromhex("6A64"))
        self.assertEqual(exe[0x58EBF:0x58EC1], bytes.fromhex("6A1C"))


class TheSharksWording(unittest.TestCase):
    def test_food_sources_line(self) -> None:
        page = vv3_page(vv3_save(sharks=False), None)
        self.assertIn("Once The Sharks puzzle is solved, the sea never runs out", page)
        self.assertNotIn("\nThe sea never runs out", "\n" + page)


class OneShortfall(unittest.TestCase):
    def test_at_a_glance_and_the_estimates_agree_with_a_full_source(self) -> None:
        data = bytearray(save(4, False))
        struct.pack_into("<i", data, vv4.BERRIES, vv4.BERRY_CAP)        # the bush full: it refills nothing now
        page = render(4, bytes(data))
        glance = number(re.search(r"Mushrooms to make up the shortfall: your villagers eat about ([\d,]+) more", page)[1])
        estimate = number(re.search(r"To fill the gap of about ([\d,]+) food per real-life hour", page)[1])
        self.assertEqual(glance, estimate)
        # The shared function: eating less the refills, a full source adding nothing.
        village = gm.Village(Path("."), 4, 1, Path("4.ldw"), bytes(data), frozenset(), NOW)
        ctx = life.Context(village, 6, NOW, 1000, low_food=500, extra_from=8000,
                           sources=[life.Source("Full", 10, 10, 5.0), life.Source("Open", 0, 10, 1.0)])
        eaten, refilled, gap = life.shortfall_hour(ctx, 3)
        self.assertEqual(refilled, 1.0 * 3600 / ctx.unit)
        self.assertEqual(gap, eaten - refilled)
        self.assertEqual(eaten, 3 * life.eat_per_unit(ctx) * 3600 / ctx.unit)

    def test_villagers_on_the_refills_alone_agree_with_a_full_source(self) -> None:
        # The owner, 2026-11-19 (yes to Q1): the same rule as the shortfall, one shared function in both places.
        data = bytearray(save(4, False))
        struct.pack_into("<i", data, vv4.BERRIES, vv4.BERRY_CAP)
        page = render(4, bytes(data))
        glance = re.search(r"Villagers the food can keep at 100% health: about ([\d,.]+) on the refills alone", page)
        estimate = re.search(r"Sustainable population on the refills alone: about ([\d,.]+) villagers", page)
        self.assertEqual(glance[1], estimate[1])
        self.assertEqual(glance[1], "0.0")                   # the only refilling source, the bush, is full
        village = gm.Village(Path("."), 4, 1, Path("4.ldw"), bytes(data), frozenset(), NOW)
        ctx = life.Context(village, 6, NOW, 1000, low_food=500, extra_from=8000,
                           sources=[life.Source("Full", 10, 10, 5.0), life.Source("Open", 0, 10, 1.0)])
        self.assertEqual(life.on_refills(ctx), 1.0 / life.eat_per_unit(ctx))


if __name__ == "__main__":
    unittest.main()
