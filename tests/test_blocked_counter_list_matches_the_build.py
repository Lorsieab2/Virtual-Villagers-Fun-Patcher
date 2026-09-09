"""The research document's blocked-counter list must match what the build emits.

`docs/village-statistics-export-research.md` carries a "Fields still blocked on
exact evidence" list, and `scripts/build_statistics_features.py` decides which
counters are actually built. Nothing kept the two in step, and a prose list
restating configuration is a cache: it goes stale silently, because correcting
the build does not touch it and correcting it does not touch the build.

That gap is not hypothetical. PR #300 carried both directions of the failure at
once, two lines apart, and needed two reviewers to catch by eye:

  * The Tree of Life was listed as SHIPPING `Villagers Died`. It does not: the
    build configures no death hooks for it at all. A counter documented as
    shipped but absent makes unstarted work look finished, which is how a
    requirement gets silently dropped.
  * `Debris Cleared` was listed as BLOCKED for The Tree of Life. It ships. A
    counter documented as blocked but present invites a second session to
    build it again from scratch.

Both errors survived review of the commit that introduced them because reading
a prose list against a Python dict is exactly the comparison a human does
badly. This module does it mechanically, in both directions, so the next
divergence fails here instead of shipping.

The check is deliberately keyed on what the build CONFIGURES rather than on
what the exporter prints. Configuration is the thing a contributor edits when
adding a counter, so it is the thing most likely to move without the prose
following.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RESEARCH = ROOT / "docs" / "village-statistics-export-research.md"
BUILDER = ROOT / "scripts" / "build_statistics_features.py"

# The prose names each game by title; the build keys them by id.
TITLES = {
    "vv1": "A New Home",
    "vv2": "The Lost Children",
    "vv3": "The Secret City",
    "vv4": "The Tree of Life",
    "vv5": "New Believers",
}

# A counter is "configured" for a game when the builder carries the key that
# DRIVES ITS HOOK -- one key per counter, not any key mentioning it.
#
# The storage address is deliberately excluded. `build_game` emits death only
# inside `for death in config.get("death_hooks", ...)` and debris only under
# `debris_hook_va`; the matching `*_stat_va` values are read only inside those
# branches. So a partial edit that removes the hook list and leaves the address
# behind emits nothing while still mentioning the counter, and a membership
# test over both keys would call that shipped. That is the exact scenario this
# module exists to catch, so it must turn on the driving key alone.
COUNTER_KEYS = {
    "death": "death_hooks",
    "debris": "debris_hook_va",
    "twins": "twins_hook_va",
    "burial": "burial_hook_va",
}

# The blocked-list bullet that governs each counter, by the phrase that opens
# it, together with the games the counter is REQUESTED for.
#
# Scope matters: "not built" and "not applicable" are different states, and
# only the first belongs on a list of things blocked pending evidence. Debris
# is a stream mechanic the first three games do not have -- the exporter says
# so directly ("The Tree of Life uses it for Debris Cleared; The Secret City
# has no equivalent") -- so requiring a blocked entry for them would be this
# module inventing a requirement rather than checking one.
#
# A counter with no games left to block has NO bullet, which is the correct
# end state rather than a missing one: `Debris Cleared` reached it when the
# entry was removed on discovering the counter ships.
BLOCKED_BULLETS = {
    "death": ("Villagers Died", {"vv1", "vv2", "vv3", "vv4", "vv5"}),
    # Debris is requested for The Tree of Life ALONE. New Believers requests
    # Heathens Converted instead and has no debris hook or exporter row, so
    # including it here would invent a blocked requirement rather than check
    # one -- and the research document would have to make a false claim to
    # satisfy it.
    "debris": ("Debris Cleared", {"vv4"}),
}


def _game_configs() -> dict[str, str]:
    """The builder's GAMES dict, split into one text block per game id."""
    text = BUILDER.read_text(encoding="utf-8")
    starts = [
        (m.start(), m.group(1))
        for m in re.finditer(r'^    "(vv\d)": \{', text, re.MULTILINE)
    ]
    if not starts:
        raise AssertionError(
            "no game blocks found in the builder; this module's parse of "
            "GAMES has drifted from the file it reads"
        )
    # The LAST game must stop at the end of the GAMES dict, not the end of the
    # file. Using len(text) swept `build_game` into vv5's block -- 23,554
    # characters instead of 1,250 -- and since that function mentions every
    # configuration key, vv5 then read as having every counter. The bug is
    # invisible in the passing direction: it only ever ADDS counters, so it
    # makes absent bullets look correct rather than making present ones fail.
    end = text.index("\n}\n", starts[-1][0])
    bounds = [pos for pos, _ in starts] + [end]
    return {
        game_id: text[pos : bounds[index + 1]]
        for index, (pos, game_id) in enumerate(starts)
    }


def _configured(counter: str, block: str) -> bool:
    return COUNTER_KEYS[counter] in block


def _blocked_list() -> str:
    """The body of the 'Fields still blocked on exact evidence' section."""
    text = RESEARCH.read_text(encoding="utf-8")
    start = text.index("## Fields still blocked on exact evidence")
    end = text.index("\n### ", start)
    return text[start:end]


class BlockedCounterListMatchesTheBuildTests(unittest.TestCase):
    def setUp(self) -> None:
        self.configs = _game_configs()
        self.blocked = _blocked_list()

    def test_the_parse_finds_every_game(self) -> None:
        """A positive control: a parse that finds nothing proves nothing.

        Every assertion below is a search for a game's name inside a block of
        text. If the parse silently returned no blocks, or blocks for only
        some games, each of those searches would pass vacuously and this
        module would report success while checking nothing.
        """
        self.assertEqual(set(self.configs), set(TITLES))
        for game_id, block in self.configs.items():
            with self.subTest(game=game_id):
                self.assertIn(
                    "burial_hook_va",
                    block,
                    "every game ships a burial counter; a block without one "
                    "means the parse split the builder in the wrong places",
                )

    def test_a_blocked_counter_is_not_configured(self) -> None:
        """Listed as blocked, but the build emits it -> built twice.

        This is the `Debris Cleared` half of the PR #300 defect. A reader
        picking work off the blocked list would rebuild something that
        already ships.
        """
        for counter, (phrase, _scope) in BLOCKED_BULLETS.items():
            for game_id in self._named_blocked(phrase):
                with self.subTest(counter=counter, game=game_id):
                    self.assertFalse(
                        _configured(counter, self.configs[game_id]),
                        "%r is listed as blocked for %s, but the build "
                        "configures it. A counter documented as blocked but "
                        "present invites building it a second time."
                        % (phrase, TITLES[game_id]),
                    )

    def test_a_configured_counter_is_not_listed_as_blocked(self) -> None:
        """Configured, and absent from its blocked bullet -> genuinely shipped.

        The other direction, and the `Villagers Died` half of the defect: a
        game that does NOT configure a counter must be named as blocked, or
        the document implies it ships when it does not.
        """
        for counter, (phrase, scope) in BLOCKED_BULLETS.items():
            named = self._named_blocked(phrase)
            for game_id, block in self.configs.items():
                if game_id not in scope or _configured(counter, block):
                    continue
                with self.subTest(counter=counter, game=game_id):
                    self.assertIn(
                        game_id,
                        named,
                        "the build configures no %s counter for %s, so it "
                        "must be named as blocked. A counter documented as "
                        "shipped but absent makes unstarted work look "
                        "finished." % (counter, TITLES[game_id]),
                    )

    def _named_blocked(self, phrase: str) -> set[str]:
        """Game ids the `phrase` bullet names as blocked.

        Read from the bullet's **bolded** span rather than its whole text. The
        prose around it deliberately names the games that DO ship, to say why
        the others do not, so a substring search over the bullet reports every
        game mentioned as blocked -- including the shipped ones it is
        contrasting against. The bold is what carries the claim.

        A counter with no games left to block correctly has no bullet at all;
        that returns the empty set, and the shipped-direction test then has
        nothing to require.
        """
        marker = "- " + phrase
        if marker not in self.blocked:
            return set()
        start = self.blocked.index(marker)
        remainder = self.blocked[start + len(marker) :]
        nxt = remainder.find("\n- ")
        bullet = remainder if nxt == -1 else remainder[:nxt]
        bold = re.findall(r"\*\*(.+?)\*\*", bullet, re.DOTALL)
        self.assertTrue(
            bold,
            "the %r bullet names no games in bold; this module reads the "
            "bolded span to tell a blocked game from one merely mentioned, "
            "so an unbolded list cannot be checked" % phrase,
        )
        span = " ".join(bold)
        return {
            game_id
            for game_id, title in TITLES.items()
            if title in span
        }


if __name__ == "__main__":
    unittest.main()
