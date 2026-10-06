"""Every like / dislike list the patcher prints is the game's own.

The owner (2026-10-06): "Always use the in-game actual exe data!!!!!! The
logs must conform with either the save file or the exe."  A villager stores
its likes and dislikes as numbers into its game's own word list, so a list
copied from a neighbouring game prints the wrong word -- A New Home's had been
The Lost Children's cut to 47 words (heights, learning, parrots ... where the
game says rough wood, dancing, birds, and no "sleeping" at all), and The
Secret City's printed frogs and soap where it says alchemy and potions.

Each list below is compared word for word with the one in the stock
executable (research/stock-executables, git-ignored: skipped without it).
"""

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STOCK = ROOT / "research" / "stock-executables"
EXES = {
    1: "Virtual Villagers - A New Home.exe",
    2: "Virtual Villagers - The Lost Children.exe",
    3: "Virtual Villagers - The Secret City.exe",
    4: "Virtual Villagers - The Tree of Life.exe",
    5: "Virtual Villagers - New Believers.exe",
}


def exe_list(game):
    data = (STOCK / EXES[game]).read_bytes()
    match = re.search(rb"ants, ?crowds[^\x00]*", data)
    return [w.strip() for w in match.group(0).decode("latin-1").split(",")]


def c_words(text):
    return [w.strip() for w in "".join(re.findall(r'"([^"]*)"', text)).split(",")]


def named_list(path, name):
    text = (ROOT / path).read_text(encoding="utf-8")
    match = re.search(r"(?:static const char %s\[\] =|#define %s \\)\n((?:\s*\"[^\"]*\"[ \\]*\n?)+)"
                      % (name, name), text)
    assert match, (path, name)
    return c_words(match.group(1))


def adapter_list(path):
    """The Custom Island Event adapter's inline list (story_cN.inc)."""
    text = (ROOT / path).read_text(encoding="utf-8")
    match = re.search(r'\n((?:    "ants,[^"]*"\n)(?:    "[^"]*"\n)*?    "[^"]*"),\n', text)
    assert match, path
    return c_words(match.group(1))


EXPORTERS = ("native/parentage_export/parentage_export.c",
             "native/population_export/population_export.c")


@unittest.skipUnless(STOCK.is_dir(), "stock executables not present")
class PreferenceListsMatchTheExes(unittest.TestCase):
    def test_the_exporters_lists(self):
        for path in EXPORTERS:
            for name, game in (("PREFERENCES_47", 1), ("PREFERENCES_62", 2),
                               ("PREFERENCES_79_VV3", 3), ("PREFERENCES_79", 4),
                               ("PREFERENCES_79", 5)):
                with self.subTest(path=path, name=name, game=game):
                    self.assertEqual(named_list(path, name), exe_list(game))

    def test_the_secret_city_reads_its_own_list(self):
        parentage = (ROOT / EXPORTERS[0]).read_text(encoding="utf-8")
        self.assertIn("0xFB4, 0xFC0, 3, PREFERENCES_79_VV3,", parentage)
        population = (ROOT / EXPORTERS[1]).read_text(encoding="utf-8")
        self.assertIn('PREFERENCES_79_VV3,\n        "Virtual Villagers 3"',
                      population.replace("\r\n", "\n"))
        c3 = (ROOT / "native/vvfp_story_upgrades/story_c3.inc").read_text(encoding="utf-8")
        self.assertIn("STORY_PREFERENCES_79_VV3,", c3)

    def test_the_custom_island_event_lists(self):
        self.assertEqual(adapter_list("native/vvfp_story_upgrades/story_c1.inc"), exe_list(1))
        self.assertEqual(adapter_list("native/vvfp_story_upgrades/story_c2.inc"), exe_list(2))
        common = "native/vvfp_story_upgrades/story_common.inc"
        self.assertEqual(named_list(common, "STORY_PREFERENCES_79_VV3"), exe_list(3))
        self.assertEqual(named_list(common, "STORY_PREFERENCES_79"), exe_list(4))
        self.assertEqual(named_list(common, "STORY_PREFERENCES_79"), exe_list(5))

    def test_a_new_home_offers_sleeping(self):
        """Its list's last word is an ordinary like and dislike."""
        c1 = (ROOT / "native/vvfp_story_upgrades/story_c1.inc").read_text(encoding="utf-8")
        self.assertIn("    4, 47,\n", c1.replace("\r\n", "\n"))
        self.assertEqual(exe_list(1)[46], "sleeping")
        self.assertNotIn("(sleeping) is not offered", c1)


if __name__ == "__main__":
    unittest.main()
