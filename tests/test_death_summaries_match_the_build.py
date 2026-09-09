"""Every statement of which games ship Villagers Died must agree with the build.

`tests/test_blocked_counter_list_matches_the_build.py` ties the *blocked list*
to the builder in both directions. That is one statement of the fact, and the
research document contains four:

  1. the blocked bullet, naming the games that do NOT ship it
  2. its follow-on sentence, naming the games that DO
  3. the "Villagers Died" section heading, naming them again
  4. the arbiter table, one row per shipping game

When The Tree of Life gained the counter, only the first was updated, because
that is the one a guard was watching. The other three kept describing the old
state, and the section ended up contradicting itself within four lines: a
heading saying two games ship it, immediately above prose saying a third does.

That is the same defect the blocked-list guard exists to prevent, one level up
-- a fact restated in several places, with only one of them checked. A reader
consulting any of the other three would conclude the feature does not exist.

So this module checks the restatements rather than the list, and derives the
truth from `scripts/build_statistics_features.py` rather than from any prose,
because the builder is what decides whether a counter is emitted at all.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RESEARCH = ROOT / "docs" / "village-statistics-export-research.md"
BUILDER = ROOT / "scripts" / "build_statistics_features.py"

TITLES = {
    "vv1": "A New Home",
    "vv2": "The Lost Children",
    "vv3": "The Secret City",
    "vv4": "The Tree of Life",
    "vv5": "New Believers",
}


def _ships_death() -> set[str]:
    """Game ids whose configuration makes the builder emit a death counter.

    Keyed on `death_hooks`, which is what `build_game` iterates; a game with
    no hooks emits nothing however many other death keys it carries.
    """
    text = BUILDER.read_text(encoding="utf-8")
    opening = re.search(r"^GAMES = \{", text, re.MULTILINE)
    closing = re.search(r"^\}", text[opening.end() :], re.MULTILINE)
    body = text[opening.end() : opening.end() + closing.start()]
    starts = [
        (m.start(), m.group(1))
        for m in re.finditer(r'^    "(vv\d)": \{', body, re.MULTILINE)
    ]
    bounds = [pos for pos, _ in starts] + [len(body)]
    shipping = set()
    for index, (pos, game_id) in enumerate(starts):
        block = body[pos : bounds[index + 1]]
        if '"death_hooks"' in block:
            shipping.add(game_id)
    return shipping


def _death_section() -> str:
    text = RESEARCH.read_text(encoding="utf-8")
    start = text.index("### Villagers Died")
    end = text.index("\n### ", start + 1)
    return text[start:end]


class DeathSummariesMatchTheBuildTests(unittest.TestCase):
    def setUp(self) -> None:
        self.shipping = _ships_death()
        self.section = _death_section()
        self.document = RESEARCH.read_text(encoding="utf-8")

    def test_the_build_ships_the_counter_somewhere(self) -> None:
        """Positive control.

        Every assertion below compares a prose claim against this set. If it
        came back empty -- a parse that found no games, or a key that had been
        renamed -- the comparisons would still pass for any document that
        named no games at all, and this module would report success while
        checking nothing.
        """
        self.assertTrue(
            self.shipping,
            "no game configures death_hooks; either the counter was removed "
            "or this module's parse of GAMES has drifted",
        )
        self.assertLessEqual(self.shipping, set(TITLES))

    def test_the_section_heading_names_every_shipping_game(self) -> None:
        """The bolded "Shipped for ..." heading is the first thing read."""
        heading = self.section.split("\n\n")[1]
        self.assertTrue(
            heading.startswith("**Shipped for"),
            "the Villagers Died section no longer opens with a Shipped-for "
            "heading; this module's parse needs updating",
        )
        for game_id in sorted(self.shipping):
            with self.subTest(game=game_id):
                self.assertIn(
                    TITLES[game_id],
                    heading,
                    "%s ships the counter but the section heading does not "
                    "name it, so a reader stopping at the heading concludes "
                    "it does not exist" % TITLES[game_id],
                )
        for game_id in sorted(set(TITLES) - self.shipping):
            with self.subTest(game=game_id, shipping=False):
                self.assertNotIn(
                    TITLES[game_id],
                    heading,
                    "%s does not ship the counter but the heading claims it "
                    "does" % TITLES[game_id],
                )

    def test_the_arbiter_table_has_a_row_per_shipping_game(self) -> None:
        """The table is the reference a builder actually works from.

        A missing row does not read as an omission; it reads as evidence the
        game was never done.
        """
        rows = re.findall(r"^\| ([A-Z][^|]+?) \| `0x", self.section, re.MULTILINE)
        named = {title.strip() for title in rows}
        for game_id in sorted(self.shipping):
            with self.subTest(game=game_id):
                self.assertIn(
                    TITLES[game_id],
                    named,
                    "%s ships the counter but has no row in the arbiter "
                    "table" % TITLES[game_id],
                )

    def test_the_blocked_bullet_follow_on_agrees(self) -> None:
        """The sentence after the blocked bullet restates the shipping set.

        It sits two lines from the bullet a separate guard already checks, and
        was the last of the three to be noticed precisely because that guard
        made the neighbouring line look supervised.
        """
        marker = "- Villagers Died"
        start = self.document.index(marker)
        bullet = self.document[start : self.document.index("\n- ", start + 1)]
        for game_id in sorted(self.shipping):
            with self.subTest(game=game_id):
                self.assertIn(
                    TITLES[game_id],
                    bullet,
                    "%s ships the counter but the blocked bullet's follow-on "
                    "sentence does not say so" % TITLES[game_id],
                )


if __name__ == "__main__":
    unittest.main()
