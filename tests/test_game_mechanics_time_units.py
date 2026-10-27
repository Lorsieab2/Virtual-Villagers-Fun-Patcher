"""Game Mechanics (src/vv_game_mechanics.py): every time on every tab names its clock.

The owner, 2026-10-27: "Make sure all the game mechanics data is accurate and specify game time vs real time.
Please!!!!!"  Every tab is rendered -- each game's general rules (no save) and the repo's real save fixtures
(tests/fixtures/rename_tribe) -- and a line that states a duration or a rate must say which clock it runs on:

  * the game's clock (it follows the speed) -- "on the game's clock", or a real-life length at a named speed ("6 minutes of real-life play on Normal
    speed", "3, 6 or 10 real-life minutes on Fast, Normal or Slow", the owner's "every 3 hours on Normal speed");
  * real time -- "real time", or "real-life ..." with "at every speed" / "at any speed";
  * or the pointer to the clock key: "see Time and units" (ages and age units, gm.AGES).

A villager age or an age-unit count is game time by definition; a line that gives one without naming a clock gets
gm.AGES.  The pointer covers only ages and age units: a line with seconds, minutes, hours or days must name their
clock in its own words too.
"""
from __future__ import annotations

import gzip
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import vv_game_mechanics as gm  # noqa: E402
import vv_tribe_rename  # noqa: E402

FIXTURES = ROOT / "tests" / "fixtures" / "rename_tribe"
SAVES = ("vv1-huttest-1", "vv2-huttest-1", "vv3-huttest-1", "vv3-256-1", "vv4-huttest-1", "vv4-256-1",
         "vv5-huttest-1", "vv5-256-1")
NOW = 1_790_000_000 + 3_000_000

# A time amount: a number with a unit (also "2-second", "36 real-life hours", "14-year-olds"), a rate ("each age
# unit", "per hour"), any age unit, or an m:ss countdown.  Dates ("3 October 2026, 7:00 AM") are taken out first.
_UNITS = r"(?:seconds?|minutes?|hours?|days?|weeks?|months?)"
_AMOUNT = r"\b\d[\d,.]*(?:\s*(?:to|or|,)\s*\d[\d,.]*)?[\s-]*(?:real-life[\s-]+|real[\s-]+)?"
TIME = re.compile(_AMOUNT + r"(?:" + _UNITS[3:-1] + r"|years?|age units?|-year-olds?)\b"
                  r"|\b(?:an?|one|each|every|per) (?:real-life )?(?:minute|hour|day|age unit|year)\b"
                  r"|\b(?:per|each|every) second\b|\bage units?\b|\b\d+:\d\d\b")
NOT_AGE = re.compile(_AMOUNT + _UNITS + r"\b|\b(?:an?|one|each|every|per) (?:real-life )?(?:minute|hour|day)\b"
                     r"|\b(?:per|each|every) second\b|\b\d+:\d\d\b")
DATE = re.compile(r"\b\d{1,2} (?:January|February|March|April|May|June|July|August|September|October|November|"
                  r"December) \d{4}, \d{1,2}:\d\d (?:AM|PM)")
# The pinned phrasings that name a clock (gm.CLOCK_WORDS is the page's own copy; both are checked here).
CLOCK = re.compile(
    r"\bthe game's (?:own )?clock\b|\breal time\b|see Time and units|\bon (?:Fast|Normal|Slow) speed\b"
    r"|\breal-life\b.*\b(?:on (?:Fast|Normal|Slow)\b|Fast, Normal\b|Fast or Normal\b|at (?:every|any) speed\b"
    r"|whatever the speed\b)"
    r"|\b(?:on (?:Fast|Normal|Slow)\b|Fast, Normal\b|Fast or Normal\b|at (?:every|any) speed\b).*\breal-life\b",
    re.S)


def pages():
    """(name, facts) for every tab: each game's general page, then each committed save fixture."""
    for game in range(1, 6):
        yield f"general {game}", gm.general(game, now=NOW)
    for name in SAVES:
        number, slot = int(name[2]), int(name[-1])
        base = next(item.base for item in vv_tribe_rename.GAMES if item.number == number)
        root = Path(tempfile.mkdtemp(prefix="gmtu"))
        try:
            (root / base).mkdir()
            (root / base / f"{base}{slot}.ldw").write_bytes(gzip.decompress((FIXTURES / f"{name}.ldw.gz").read_bytes()))
            yield name, gm.read(root / base, number, slot, [], now=NOW)
        finally:
            shutil.rmtree(root, True)


def missing_clock(text: str) -> bool:
    """True when `text` states a time amount and names no clock (see the module docstring)."""
    body = DATE.sub("<date>", gm.tidy(text))
    if TIME.search(body) and not CLOCK.search(body):
        return True
    rest = body.replace(gm.AGES, "")             # the ages pointer does not cover seconds, minutes, hours or days
    return bool(NOT_AGE.search(rest) and not CLOCK.search(rest))


class EveryLineNamesItsClock(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.pages = list(pages())

    def test_every_tab_was_rendered(self) -> None:
        self.assertEqual(len(self.pages), 5 + len(SAVES))
        for name, facts in self.pages:
            with self.subTest(tab=name):
                self.assertGreater(len(facts), 50)

    def test_a_line_with_a_time_names_its_clock(self) -> None:
        for name, facts in self.pages:
            with self.subTest(tab=name):
                bad = [f"{f.group}: {f.text}" for f in facts if missing_clock(f.text)]
                self.assertEqual(bad, [], "\n\n".join(bad[:10]))

    def test_the_page_and_the_test_pin_the_same_phrasings(self) -> None:
        for text in ("an age unit is 6 minutes of real-life play on Normal speed", "every 3 hours on Normal speed",
                     "10 real-life minutes, the same at every speed", "36 real-life hours at any speed",
                     "an hour (on the game's clock: 30 minutes on Fast)", "lasts 2 minutes (real time)", gm.AGES):
            with self.subTest(text=text):
                self.assertTrue(CLOCK.search(text))
                self.assertTrue(gm.CLOCK_WORDS.search(text))
        for text in ("lasts 5 minutes", "36 real-life hours after his birth", "every 40 seconds",
                     "a child of 10 years", "1 in 4,800 each age unit", "5:00 at the start"):
            with self.subTest(text=text):
                self.assertTrue(missing_clock(text), text)

    def test_the_banned_words_stay_out(self) -> None:
        """The owner's rule of 2026-10-22 (tests/test_game_mechanics.py): never "game" + a time unit, "game time"
        included -- a timer on the game's clock is said "on the game's clock" or at a named speed."""
        for name, facts in self.pages:
            with self.subTest(tab=name):
                text = gm.render(facts).lower()
                self.assertNotRegex(text, r"game (hours?|minutes?|seconds?|time|clock units?)\b")
                self.assertNotRegex(text, r"\bclock (seconds|units)\b")

    def test_the_ages_pointer_covers_only_ages(self) -> None:
        self.assertFalse(missing_clock(f"a boy of 13 years joins. {gm.AGES}"))
        self.assertTrue(missing_clock(f"a boy of 13 years joins and stays 5 minutes. {gm.AGES}"))

    def test_with_clock_adds_the_pointer_to_an_age_line_only(self) -> None:
        age = gm.with_clock(gm.Fact("Island events", "A man of 600 age units joins"))
        self.assertEqual(age.text, f"A man of 600 age units joins. {gm.AGES}")
        timed = gm.Fact("Other", "An age unit is 3, 6 or 10 real-life minutes on Fast, Normal or Slow.")
        self.assertIs(gm.with_clock(timed), timed)
        plain = gm.Fact("Other", "Fishing: 9 food a catch.")
        self.assertIs(gm.with_clock(plain), plain)

    def test_every_tab_has_the_clock_key(self) -> None:
        """Time and units: what game time and real time mean, and whether each runs while paused or closed."""
        for name, facts in self.pages:
            with self.subTest(tab=name):
                key = [f for f in facts if f.text.startswith("Time and units:")]
                self.assertEqual(len(key), 1)
                self.assertEqual(key[0].group, gm.TIME_UNITS)
                self.assertEqual(gm.GROUPS.index(gm.TIME_UNITS), 2)          # right after the two summaries
                for words in ("A timer on the game's clock follows the speed", "stands still while the game is paused",
                              "while the game is closed it counts only as far as time away counts",
                              "Real time is the computer's clock", gm.SAME_EVERY_SPEED,
                              "whether it runs while the game is paused or closed"):
                    self.assertIn(words, key[0].text)
                units = facts[facts.index(key[0]) + 1]
                self.assertTrue(units.sub)
                self.assertIn("an age unit is 3, 6 or 10 real-life minutes on Fast, Normal or Slow", units.text)
                self.assertIn("Every age, villager year and age unit on this page runs on the game's clock.", units.text)


class SettledClocks(unittest.TestCase):
    """Clocks read from the stock code (or the owner) that the page must keep saying the same way everywhere."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.text = {name: gm.render(facts) for name, facts in pages()}

    def test_island_events_are_real_time_and_wait_while_paused(self) -> None:
        # VV1 0x42E930, VV2/VV3 the pause shift, VV4 0x42034A, VV5 0x425E45: the pause moves the timer on.
        for game in range(1, 6):
            with self.subTest(game=game):
                text = self.text[f"general {game}"]
                self.assertRegex(text, r"Island events: their timer runs on real time \(real-life hours, the same at "
                                       r"every speed\), so the whole time closed counts; while the game is paused it "
                                       r"stands still")

    def test_the_vv3_potion_follows_the_speed(self) -> None:
        """The owner: a brewed potion's time follows the game speed."""
        self.assertIn("the potion's time runs on the game's clock (it follows the speed, the owner's word)", self.text["general 3"])

    def test_the_vv2_fire_is_set_by_the_speed_it_is_lit_at(self) -> None:
        # The fuel 0x4624CF..0x46253F: 0x8CA0, 0x11940 or 0x23280 seconds; rescale 0x43B5A0 on a speed change.
        text = self.text["general 2"]
        self.assertIn("10, 20 or 40 hours on Fast, Normal or Slow: the length is set by the speed it is lit or "
                      "fuelled at", text)
        self.assertIn("from Normal to Slow 20 hours left become 33 hours 20 minutes, not 40", text)

    def test_effects_on_the_computers_clock_are_real_time(self) -> None:
        # VV4 0x460A90 -> 0x403750 (the Purify glow), VV5 0x41441B (+90: an item lies), VV2 0x44E907 (the Gong glow).
        self.assertIn("a glow for 4 real-life minutes (240 seconds; real time, the same at every speed", self.text["vv4-huttest-1"])
        self.assertIn("1 minute 30 seconds (real time, the same at every speed: 90 seconds on the computer's clock",
                      self.text["general 5"])
        self.assertIn("for 30 real-life seconds (real time: 30 seconds on the clock 0x403200)", self.text["general 2"])

    def test_unproven_clocks_say_so(self) -> None:
        # Each in a line of its own, so the label stands beside it (a confirmed line never carries the word).
        for game, words in ((4, "Running: whether a walk's 3.4, 6.7 or 24.9 seconds are real time or on the game's clock "
                                "was not traced."),
                            (4, "The hummingbird's 3 to 5 (23 to 25) real-life minutes: whether they are real time or on "
                                "the game's clock was not traced.")):
            with self.subTest(words=words):
                self.assertIn(f"{gm.UNCONFIRMED}  {words}", self.text[f"general {game}"])

    def test_the_vv3_ash_key_trips_are_on_the_games_clock(self) -> None:
        # Each water trip sets a timer 600 seconds ahead through 0x426790 (wall now + seconds x rate / 6).
        self.assertIn("10 minutes on the game's clock, 5, 10 or 16 minutes 40 seconds of real-life play on Fast, Normal "
                      "or Slow", self.text["general 3"])


if __name__ == "__main__":
    unittest.main()
