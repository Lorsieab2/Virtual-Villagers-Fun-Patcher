"""The Nursery School lines of the Game Mechanics page (src/vv_game_mechanics_nursery.py, and the Nursery School
lines of vv_game_mechanics_catchup.py, items_vv4.py and items_vv5.py): every number and address is re-read from the
stock exes, and the lesson itself is run in unicorn (tests/nursery_emulation.py) with the game's own code."""
from __future__ import annotations

import random
import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import vv_game_mechanics as gm  # noqa: E402
import vv_game_mechanics_catchup as catchup  # noqa: E402
import vv_game_mechanics_items_vv4 as items4  # noqa: E402
import vv_game_mechanics_items_vv5 as items5  # noqa: E402
import vv_game_mechanics_nursery as nursery  # noqa: E402

STOCK = ROOT / "research" / "stock-executables"
BASE = 0x400000


def _image(name: str) -> bytes:
    import pefile
    return bytes(pefile.PE(str(STOCK / name), fast_load=True).get_memory_mapped_image())


class _Village:
    def __init__(self, features=()):
        self.features = set(features)

    def has(self, feature: str):
        return feature in self.features


def _text(game: int, features=()) -> str:
    return "\n".join(f.text for f in nursery.lines(_Village(features), game))


class ExeBytes(unittest.TestCase):
    """The constants and instructions the lines quote, in the stock exes."""

    def test_new_believers(self) -> None:
        img = _image("Virtual Villagers - New Believers.exe")
        at = lambda a, n: img[a - BASE:a - BASE + n]  # noqa: E731
        d = lambda a: struct.unpack_from("<d", img, a - BASE)[0]  # noqa: E731
        self.assertEqual((d(0x498B38), d(0x498B30), d(0x498810)), (1440.0, 10.0, 5.0))
        self.assertEqual(at(0x425FB3, 6), bytes.fromhex("DC3D388B4900"))           # fdivr 1440.0
        self.assertEqual(at(0x425FB9, 6), bytes.fromhex("DC0D308B4900"))           # fmul 10.0
        self.assertEqual(at(0x425FDF, 6), bytes.fromhex("DC3510884900"))           # fdiv 5.0
        self.assertEqual(at(0x425FB1, 2), bytes.fromhex("6A64"))                   # rand(100) ...
        self.assertEqual(at(0x425FCD, 3), bytes.fromhex("83F832"))                 # ... < 50, once a tick
        self.assertEqual(at(0x425F80, 4), bytes.fromhex("6A006A08"))               # the teacher: job 8
        self.assertEqual(at(0x42600E, 10), bytes.fromhex("81BF8C1B000018010000"))  # age < 280
        self.assertEqual(at(0x42603B, 2), bytes.fromhex("6A06"))                   # rand(6) while all are 0
        self.assertEqual(at(0x43AA06, 10), bytes.fromhex("C786541C000008000000"))  # the drop sets job 8
        self.assertEqual(at(0x43A9BC, 3), bytes.fromhex("83FB03"))                 # 3 skills at 50 or more
        self.assertEqual(at(0x43AB3A, 8), bytes.fromhex("C744240C08020000"))       # "Not enough skills to teach!"
        self.assertEqual(at(0x445F32, 7), bytes.fromhex("80B9EC1C000000"))         # pick-up: Heathens refused
        self.assertEqual(at(0x424D87, 6), bytes.fromhex("D905D4804900"))           # the Heathen Chief's skills ...
        self.assertEqual(struct.unpack_from("<f", img, 0x4980D4 - BASE)[0], 100.0)  # ... are 100
        self.assertEqual(at(0x424D5F, 2), bytes.fromhex("6A0D"))                   # role 13
        self.assertEqual(at(0x41F78F, 2), bytes.fromhex("6A07"))                   # the Earthquake: rand(7) + 2
        self.assertEqual(at(0x466966, 7), bytes.fromhex("83BEFC1C00000D"))         # joining keeps role 13 only
        for text in (b"Not enough skills to teach!", b"Celebrating", b"Devotion",
                     b"You cannot touch heathens because they do not believe in you.",
                     b"This will help them raise smarter \nchildren."):
            self.assertIn(text, img)

    def test_tree_of_life(self) -> None:
        img = _image("Virtual Villagers - The Tree of Life.exe")
        at = lambda a, n: img[a - BASE:a - BASE + n]  # noqa: E731
        d = lambda a: struct.unpack_from("<d", img, a - BASE)[0]  # noqa: E731
        self.assertEqual((d(0x48D688), d(0x48D680), d(0x48D678)), (1440.0, 10.0, 5.0))
        self.assertEqual(at(0x4203F3, 4), bytes.fromhex("6A006A08"))
        self.assertEqual(at(0x420487, 10), bytes.fromhex("81BF8C1B000018010000"))
        self.assertEqual(at(0x4204B4, 2), bytes.fromhex("6A05"))
        self.assertEqual(at(0x4376B4, 10), bytes.fromhex("C786541C000008000000"))
        self.assertEqual(at(0x43764C, 3), bytes.fromhex("83FB03"))
        self.assertEqual(at(0x4377F6, 8), bytes.fromhex("C744240C53020000"))
        self.assertEqual(at(0x437480, 5), bytes.fromhex("68F8020000"))            # the completion tip 0x2F8
        self.assertIn(b"Not enough skills to teach!", img)
        self.assertNotIn(b"Devotion", img)


class Lesson(unittest.TestCase):
    """The game's own lesson, run in unicorn."""

    def setUp(self) -> None:
        import nursery_emulation as ne
        self.ne = ne

    def _school(self, game, speed=6, teacher=100.0):
        e = self.ne.Nursery(game, speed=speed)
        e.villager(0, age=600, skills=[teacher] * game.skills, job=8)
        return e

    def test_amounts_match_the_page(self) -> None:
        for game in (self.ne.VV5, self.ne.VV4):
            n = game.skills
            for speed in nursery.SPEEDS:
                e = self._school(game, speed)
                e.villager(1, age=100, skills=[10.0] * n)
                e.lesson([0, 10])                      # the teacher pick, then a whole lesson
                whole = nursery.lesson(100 * n, speed)
                self.assertAlmostEqual(e.skills(1)[0] - 10.0, whole, places=5)
                e.lesson([0, 70])                      # a spread lesson
                self.assertAlmostEqual(e.skills(1)[1] - 10.0, whole / 5, places=5)
                self.assertAlmostEqual(whole * 60 / speed, nursery.per_hour(100 * n))
        self.assertIn("0.125, 0.25 or 0.4167", _text(5))
        self.assertIn("0.025, 0.05 or 0.0833", _text(5))
        self.assertIn("0.1042, 0.2083 or 0.3472", _text(4))
        self.assertIn("1.5 a real-life hour and every other skill below 50 gains 0.25", _text(5))
        self.assertIn("1.25 a real-life hour and every other skill below 50 gains 0.2083", _text(4))

    def test_whole_numbers_of_the_teacher(self) -> None:
        e = self._school(self.ne.VV5, 10, 99.9)
        e.villager(1, age=0, skills=[20.0] * 6)
        e.lesson([0, 0])
        self.assertAlmostEqual(e.skills(1)[0] - 20.0, 99 * 6 * 10 / 14_400, places=5)   # 594, not 599.4

    def test_heathen_children_learn_and_adults_do_not(self) -> None:
        e = self._school(self.ne.VV5)
        e.villager(1, age=279, skills=[0.0] * 6, heathen=True)
        e.villager(2, age=280, skills=[0.0] * 6, heathen=True)
        e.villager(3, age=280, skills=[0.0] * 6)
        asked = e.lesson([0, 70])
        self.assertEqual(asked, [1, 100])
        self.assertTrue(all(s > 0 for s in e.skills(1)))
        self.assertEqual(e.skills(2), [0.0] * 6)
        self.assertEqual(e.skills(3), [0.0] * 6)
        self.assertIn("Heathen children included", _text(5))

    def test_one_roll_and_a_drawn_skill_for_each_child_at_zero(self) -> None:
        e = self._school(self.ne.VV5)
        for i in (1, 2):
            e.villager(i, age=0, skills=[0.0] * 6)
        asked = e.lesson([0, 49, 2, 5])
        self.assertEqual(asked, [1, 100, 6, 6])
        self.assertGreater(e.skills(1)[2], 0)
        self.assertGreater(e.skills(2)[5], 0)

    def test_the_top_skill_at_50_gets_nothing(self) -> None:
        e = self._school(self.ne.VV5, gm.SLOW)
        e.villager(1, age=0, skills=[50.0, 10.0, 10.0, 10.0, 10.0, 49.95])
        e.lesson([0, 0])
        self.assertEqual(e.skills(1), [50.0, 10.0, 10.0, 10.0, 10.0, struct.unpack("<f", struct.pack("<f", 49.95))[0]])
        e.lesson([0, 99])                              # spread: all but the one at 50; 49.95 + 0.0833 passes 50
        s = e.skills(1)
        self.assertEqual(s[0], 50.0)
        self.assertGreater(s[5], 50.0)
        self.assertTrue(all(x > 10.0 for x in s[1:5]))

    def test_ties_go_to_the_last_skill(self) -> None:
        for game, last in ((self.ne.VV5, 5), (self.ne.VV4, 4)):
            n = game.skills
            e = self._school(game)
            e.villager(1, age=0, skills=[0.6] + [0.1] * (n - 1))   # every skill below a whole 1
            e.villager(2, age=0, skills=[12.0] * n)                # equal whole numbers, no fraction
            e.villager(3, age=0, skills=[12.5] + [0.0] * (n - 2) + [12.1])
            e.lesson([0, 0])
            self.assertGreater(e.skills(1)[last], 0.1 + 1e-6)
            self.assertGreater(e.skills(2)[0], 12.0)
            self.assertGreater(e.skills(3)[last], 12.1 + 1e-6)
        self.assertIn("(Devotion over all the others)", _text(5))
        self.assertIn("(Building over all the others)", _text(4))

    def test_no_teacher_no_lesson_and_several_one_at_random(self) -> None:
        e = self.ne.Nursery(self.ne.VV5)
        e.villager(1, age=0, skills=[1.0] * 6)
        self.assertEqual(e.lesson([]), [])
        self.assertEqual(e.skills(1), [1.0] * 6)
        e.villager(0, age=600, skills=[100.0] * 6, job=8)
        e.villager(2, age=600, skills=[50.0] * 6, job=8)
        self.assertEqual(e.lesson([1, 0]), [2, 100])   # the second of two teachers: 300
        self.assertAlmostEqual(e.skills(1)[0] - 1.0, 300 * 6 / 14_400, places=5)

    def test_a_heathen_with_the_job_still_teaches(self) -> None:
        """The UNCONFIRMED line's code half: the teacher pick has no Heathen test."""
        e = self.ne.Nursery(self.ne.VV5)
        e.villager(0, age=600, skills=[100.0] * 6, job=8, heathen=True)
        e.villager(1, age=0, skills=[1.0] * 6)
        e.lesson([0, 0])
        self.assertGreater(e.skills(1)[0], 1.0)
        line = next(f for f in nursery.lines(_Village(), 5) if "whether it stays was not traced" in f.text)
        self.assertFalse(line.confirmed)

    def test_four_hundred_children_from_zero(self) -> None:
        """The emulated counts the page quotes: which skill a child starting at 0 ends up trained in."""
        expect = {5: ((3, 394), (6, 371), (10, 341)), 4: ((3, 398), (6, 385), (10, 357))}
        for game, number in ((self.ne.VV5, 5), (self.ne.VV4, 4)):
            n = game.skills
            for speed, count in expect[number]:
                rng = random.Random(1)
                e = self.ne.Nursery(game, speed=speed)
                last = 0
                for _ in range(400):
                    e.villager(0, age=600, skills=[100.0] * n, job=8)
                    e.villager(1, age=0, skills=[0.0] * n)
                    for _tick in range(30):
                        roll = rng.randrange(100)
                        draw = [rng.randrange(n)] if roll < 50 and all(s == 0 for s in e.skills(1)) else []
                        e.lesson([0, roll] + draw)
                    s = e.skills(1)
                    last += max(range(n), key=lambda i: (s[i], i)) == n - 1
                self.assertEqual(last, count, (number, speed))
        self.assertIn("394, 371 and 341", _text(5))
        self.assertIn("398, 385 and 357", _text(4))


class PageLines(unittest.TestCase):
    def test_every_line_is_labelled(self) -> None:
        for game in (4, 5):
            for fact in nursery.lines(_Village(), game):
                self.assertEqual(fact.group, "Tech points and effects")
                self.assertIn(fact.verified, (gm.CODE, gm.OWNER, False))
                self.assertNotIn("VV4", fact.text)
                self.assertNotIn("VV5", fact.text)

    def test_the_owners_questions_are_answered(self) -> None:
        text = _text(5)
        for words in ("A Heathen child gains Devotion", "Village children gain in all six skills at once",
                      "The Nursery School's completion is not a skill gain",
                      "A Retired Heathen Chief's joining gives no skill", "The Earthquake gives no skill",
                      "The owner (in play)"):
            self.assertIn(words, text)
        owner = [f for f in nursery.lines(_Village(), 5) if f.text.startswith("The owner")]
        self.assertEqual([f.verified for f in owner], [gm.OWNER])

    def test_the_divisor_patch(self) -> None:
        self.assertNotIn("a sixth instead of a fifth", _text(5))
        self.assertIn("a sixth instead of a fifth", _text(5, {nursery.VV5_NURSERY}))

    def test_the_other_pages_agree(self) -> None:
        src = (ROOT / "src" / "vv_game_mechanics_catchup.py").read_text(encoding="utf-8")
        self.assertIn("Heathen children included, learns from the Nursery School teacher", src)
        self.assertIn("a skill drawn 1 in 6 while", src)
        self.assertIn("a skill drawn 1 in 5 while", src)
        self.assertNotIn("half the time all to the child's highest skill", src)
        names5 = {e.name: e for e in items5.entries()}
        self.assertIn("Heathen children included", names5["The Nursery School"].text)
        names4 = {e.name: e for e in items4.entries()}
        self.assertIn("at least 3 of the five skills", names4["The Nursery School (the building)"].text)
        self.assertTrue(catchup)


if __name__ == "__main__":
    unittest.main()
