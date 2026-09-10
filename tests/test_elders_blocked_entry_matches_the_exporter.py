"""The Village Elders blocked entry must name the games that lack the row.

The entry used to read "Village Elders where the inherited statistics block
does not already expose it", which names no game at all. That phrasing cannot
go stale, because it never said anything checkable -- and it hid the fact that
the answer is a single game. A blocked item nobody can act on is
indistinguishable from one nobody has looked at.

Which games ship the row is decided by `statistics_export.c`: a writer that
emits a "Village Elders" line ships it. So the entry is checked against the
exporter rather than against prose, in both directions, for the same reason
the death-counter guard checks both -- requiring the blocked games to be named
says nothing about a game named as blocked that actually ships.

The mapping from writer function to games is explicit here rather than
inferred. `write_later_game` serves The Secret City and The Tree of Life, which
is not visible from its name, and a guard that guessed it covered one game
would pass while checking half of what it claims.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RESEARCH = ROOT / "docs" / "village-statistics-export-research.md"
EXPORTER = ROOT / "native" / "statistics_export" / "statistics_export.c"

TITLES = {
    "vv1": "A New Home",
    "vv2": "The Lost Children",
    "vv3": "The Secret City",
    "vv4": "The Tree of Life",
    "vv5": "New Believers",
}

# Which games each writer emits rows for. write_later_game serves two.
WRITER_GAMES = {
    "write_vv1": {"vv1"},
    "write_vv2": {"vv2"},
    "write_later_game": {"vv3", "vv4"},
    "write_vv5": {"vv5"},
}

# The complete emitted row, not the label. A bare substring test on
# "Village Elders" also matches a comment mentioning the row, or a different
# label containing it -- `"Former Village Elders: %d\n"` would keep a game in
# the shipping set with the real row gone. That is correct today only by luck,
# and it is the third substring-where-exact-was-meant defect this repository
# has produced, so the row is matched as the exact format string it is.
ROW = '"Village Elders: %d\\n"'


def _writer_bodies() -> dict[str, str]:
    """Each write_* function's body, split at the next function definition."""
    text = EXPORTER.read_text(encoding="utf-8", errors="replace")
    starts = [
        (m.start(), m.group(1))
        for m in re.finditer(r"^(?:static\s+)?\w[\w \*]*?\b(write_\w+)\s*\(", text, re.M)
    ]
    if not starts:
        raise AssertionError(
            "no write_* functions found in the exporter; this module's parse "
            "has drifted from the file it reads"
        )
    bounds = [pos for pos, _ in starts] + [len(text)]
    return {
        name: text[pos : bounds[index + 1]]
        for index, (pos, name) in enumerate(starts)
    }


def _games_shipping_the_row() -> set[str]:
    bodies = _writer_bodies()
    shipping: set[str] = set()
    for writer, games in WRITER_GAMES.items():
        if ROW in bodies.get(writer, ""):
            shipping |= games
    return shipping


def _elders_blocked_span() -> str:
    """The bolded games in the Village Elders bullet.

    Read from the bold rather than the whole bullet. The prose deliberately
    names the games that DO ship the row, to say why the blocked one is
    blocked, so searching the bullet reports every game it mentions as
    blocked -- including the ones it is contrasting against. That is the same
    trap the blocked-counter guard hit, and it is solved the same way: the
    bold carries the claim, the prose carries the explanation.
    """
    text = RESEARCH.read_text(encoding="utf-8")
    marker = "- Village Elders"
    start = text.index(marker)
    bullet = text[start : text.index("\n- ", start + 1)]
    bold = re.findall(r"\*\*(.+?)\*\*", bullet, re.DOTALL)
    if not bold:
        raise AssertionError(
            "the Village Elders bullet names no games in bold; this module "
            "reads the bolded span to tell a blocked game from one merely "
            "mentioned, so an unbolded entry cannot be checked"
        )
    return " ".join(bold)


class EldersBlockedEntryMatchesTheExporterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.shipping = _games_shipping_the_row()
        self.blocked = _elders_blocked_span()

    def test_every_named_writer_exists(self) -> None:
        """Positive control.

        Every check below asks whether a writer's body contains the row. A
        writer name that no longer matches the exporter would contribute an
        empty body, silently removing its games from the shipping set and
        making the blocked entry look larger than it is -- while this module
        reported success.
        """
        bodies = _writer_bodies()
        for writer in WRITER_GAMES:
            with self.subTest(writer=writer):
                self.assertIn(
                    writer,
                    bodies,
                    "%s is not in the exporter; the writer/game mapping here "
                    "has drifted" % writer,
                )
        self.assertTrue(
            self.shipping,
            "no writer emits a Village Elders row at all; either the row was "
            "removed or the parse is wrong",
        )

    def test_a_game_that_ships_the_row_is_not_listed_as_blocked(self) -> None:
        """Listed as blocked but shipping -> someone rebuilds what exists."""
        for game_id in sorted(self.shipping):
            with self.subTest(game=game_id):
                self.assertNotIn(
                    TITLES[game_id],
                    self.blocked,
                    "%s emits a Village Elders row, so naming it in the "
                    "blocked entry would send a reader to build a row that "
                    "already ships" % TITLES[game_id],
                )

    def test_a_game_without_the_row_is_named(self) -> None:
        """Absent but unlisted -> the requirement is silently dropped."""
        for game_id in sorted(set(TITLES) - self.shipping):
            with self.subTest(game=game_id):
                self.assertIn(
                    TITLES[game_id],
                    self.blocked,
                    "%s emits no Village Elders row, so the blocked entry "
                    "must name it; an unnamed missing row reads as done"
                    % TITLES[game_id],
                )


if __name__ == "__main__":
    unittest.main()
