"""Village History and Village Population list EVERY like and dislike (v1.35.68), all five games.

Found live on the v1.35.68 candidate: the logs printed only the first filled slot ("Dislikes:
green") although the game's own Details panel lists every filled one ("green, crowds") -- The Tree
of Life's Mahi Chuchip, New Believers' Dado ("herbs, crowds" printed as "herbs").  The Island
Events log already printed the full list (VillagePreferenceListText).

The exporter now prints every filled slot, in slot order, ", " between them, in the same words;
the running exporter is checked per game by native/population_export/population_export_harness.c
(several likes with an empty slot between, one, none, index 0, the last slot).  Every reader of a
"Likes:" / "Dislikes:" line takes the full list AND the one-word lines older logs (and the Births,
Arrived and Deaths records) hold: these tests pin that.
"""
import re
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import vv_cut_names  # noqa: E402
import vv_log_additions as additions  # noqa: E402
import vv_log_tools as tools  # noqa: E402

POPULATION = ROOT / "native" / "population_export" / "population_export.c"
HARNESS = ROOT / "native" / "population_export" / "population_export_harness.c"
GRAVES = ROOT / "native" / "parentage_export" / "grave_backfill.inc"
ARRIVALS = ROOT / "native" / "parentage_export" / "arrival_backfill.inc"


class TheValue(unittest.TestCase):
    def test_words_of_a_full_list_an_old_line_and_none(self):
        self.assertEqual(tools.preference_words("green, crowds"), ("green", "crowds"))
        self.assertEqual(tools.preference_words("the ocean"), ("the ocean",))
        self.assertEqual(tools.preference_words("(none)"), ())
        self.assertEqual(tools.preference_words(None), ())
        self.assertEqual(tools.preference_words(""), ())

    def test_an_old_one_word_line_agrees_with_the_list_it_starts(self):
        self.assertTrue(tools.preferences_agree("herbs", "herbs, crowds"))
        self.assertTrue(tools.preferences_agree("herbs, crowds", "herbs"))
        self.assertTrue(tools.preferences_agree("herbs, crowds", "herbs, crowds"))
        self.assertTrue(tools.preferences_agree("(none)", None))

    def test_different_words_never_agree(self):
        self.assertFalse(tools.preferences_agree("crowds", "herbs, crowds"))   # not the FIRST word
        self.assertFalse(tools.preferences_agree("herbs, crowds", "herbs, green"))
        self.assertFalse(tools.preferences_agree("herbs", "(none)"))


def person(name, likes, dislikes):
    return SimpleNamespace(person=(name, likes, dislikes))


class RepairFindsTheVillager(unittest.TestCase):
    """Repair Saves & Logs (titles, masks, factions) finds an older snapshot's villager by name,
    likes and dislikes when the head or body changed since."""

    def test_an_old_snapshot_finds_the_villager_whose_page_lists_more(self):
        current = {("Dado", 4, 5): person("Dado", "herbs, crowds", "green, crowds")}
        older = SimpleNamespace(identity=("Dado", 9, 9), person=("Dado", "herbs", "green"))
        self.assertEqual(additions._now_of(older, current, additions._persons(current)), ("Dado", 4, 5))

    def test_a_full_list_finds_the_same_full_list(self):
        current = {("Dado", 4, 5): person("Dado", "herbs, crowds", "green, crowds")}
        newer = SimpleNamespace(identity=("Dado", 9, 9), person=("Dado", "herbs, crowds", "green, crowds"))
        self.assertEqual(additions._now_of(newer, current, additions._persons(current)), ("Dado", 4, 5))

    def test_two_who_agree_decide_nothing(self):
        current = {("Dado", 4, 5): person("Dado", "herbs, crowds", "green"),
                   ("Dado", 6, 7): person("Dado", "herbs, ants", "green")}
        older = SimpleNamespace(identity=("Dado", 9, 9), person=("Dado", "herbs", "green"))
        self.assertIsNone(additions._now_of(older, current, additions._persons(current)))

    def test_other_words_are_another_villager(self):
        current = {("Dado", 4, 5): person("Dado", "herbs, crowds", "green")}
        older = SimpleNamespace(identity=("Dado", 9, 9), person=("Dado", "crowds", "green"))
        self.assertIsNone(additions._now_of(older, current, additions._persons(current)))


class Block:
    def __init__(self, identity, likes, dislikes):
        self.identity = identity
        self._values = {"Likes": likes, "Dislikes": dislikes}

    def value(self, label):
        return self._values.get(label)


class CutNamesCompareTheWords(unittest.TestCase):
    def test_a_one_word_record_and_a_full_snapshot_agree(self):
        cut, full = ("Hoani Gued", 1, 2), ("Hoani Guedado", 1, 2)
        blocks = [Block(cut, "herbs, crowds", "green, crowds"), Block(full, "herbs", "green")]
        self.assertTrue(vv_cut_names._likes_agree(blocks, cut, full))

    def test_different_words_disagree(self):
        cut, full = ("Hoani Gued", 1, 2), ("Hoani Guedado", 1, 2)
        blocks = [Block(cut, "herbs, crowds", "green"), Block(full, "crowds", "green")]
        self.assertFalse(vv_cut_names._likes_agree(blocks, cut, full))


class TheExporterAndTheReadersMakeRoom(unittest.TestCase):
    def test_the_exporter_prints_the_whole_list(self):
        source = POPULATION.read_text(encoding="latin-1")
        self.assertIn("char preference[1024];", source)
        self.assertEqual(len(re.findall(r"preference_list_text\(record, g->(?:likes|dislikes),", source)), 2)
        self.assertIn('"  Likes: %s\\n"', source)
        self.assertIn('"  Dislikes: %s\\n"', source)

    def test_the_harness_checks_every_game_and_both_logs(self):
        harness = HARNESS.read_text(encoding="latin-1")
        for game, offsets in {1: "0x398u", 2: "0x5F0u", 3: "0xFB4u", 4: "0x1E60u", 5: "0x1F5Cu"}.items():
            self.assertRegex(harness, rf"case {game}: p\.likes = {offsets};")
        self.assertIn('"  Likes: herbs, crowds\\r\\n"', harness)
        self.assertIn('"  Dislikes: green, crowds\\r\\n"', harness)
        self.assertEqual(harness.count("check_prefs(log, 1, "), 3)   # VV2-VV5's loop, VV1's two logs

    def test_the_deaths_backfill_keeps_the_whole_list(self):
        """The Deaths log's grave backfill copies a villager's likes out of the Village History."""
        graves = GRAVES.read_text(encoding="latin-1")
        self.assertIn("#define HISTORY_PREFS_MAX 1024", graves)
        self.assertNotIn("char likes[64];", graves)
        self.assertNotIn("char dislikes[64];", graves)
        self.assertNotIn("char line[512];", graves)
        self.assertNotIn("char line[512];", ARRIVALS.read_text(encoding="latin-1"))


if __name__ == "__main__":
    unittest.main()
