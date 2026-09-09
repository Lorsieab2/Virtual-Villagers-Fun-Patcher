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

# The single key that GATES each counter's emission in the builder, and so
# decides whether the counter ships.
#
# Deliberately one key, not any of the counter's keys. Emission is guarded by
# `config.get("burial_hook_va")`, `config.get("twins_hook_va")`,
# `config.get("debris_hook_va")` and `config.get("death_hooks", [])`; every
# `*_stat_va` is read only INSIDE the branch its hook key opens. Accepting an
# auxiliary key would mean a hook removed while its storage address was left
# behind still reads as shipped here, while the builder emits nothing -- which
# is precisely the shipped-but-absent regression this module exists to catch.
COUNTER_GATE = {
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
# Scopes come from `docs/village-statistics-requirements.md`, which is the
# document that says what was asked for. Villagers Died is requested for all
# five games; Debris Cleared is listed under The Tree of Life alone, with New
# Believers asking for Heathens Converted instead.
BLOCKED_BULLETS = {
    "death": ("Villagers Died", {"vv1", "vv2", "vv3", "vv4", "vv5"}),
    "debris": ("Debris Cleared", {"vv4"}),
}


def _game_configs() -> dict[str, str]:
    """The builder's GAMES dict, split into one text block per game id.

    The last game's block must stop at the end of GAMES, not at the end of
    the file. Everything after GAMES is the builder's own code, which
    mentions every configuration key it can consume, so a slice running to
    EOF reports the final game as configuring every counter regardless of
    what its dictionary says. That is not hypothetical: it shipped in the
    first draft of this module and made VV5 opaque to every check here while
    the positive control still passed, because the control asked whether a
    block *contained* a key rather than whether it *ended* in the right
    place.
    """
    text = BUILDER.read_text(encoding="utf-8")
    opening = re.search(r"^GAMES = \{", text, re.MULTILINE)
    if opening is None:
        raise AssertionError(
            "no GAMES dict found in the builder; this module's parse has "
            "drifted from the file it reads"
        )
    # The dict is written one game per top-level key at four spaces, so its
    # close is the first "}" in the first column after it opens.
    closing = re.search(r"^\}", text[opening.end() :], re.MULTILINE)
    if closing is None:
        raise AssertionError(
            "GAMES is never closed at column zero; the builder's formatting "
            "changed and this module's parse needs updating"
        )
    body = text[opening.end() : opening.end() + closing.start()]
    starts = [
        (m.start(), m.group(1))
        for m in re.finditer(r'^    "(vv\d)": \{', body, re.MULTILINE)
    ]
    if not starts:
        raise AssertionError(
            "no game blocks found in the builder; this module's parse of "
            "GAMES has drifted from the file it reads"
        )
    bounds = [pos for pos, _ in starts] + [len(body)]
    return {
        game_id: body[pos : bounds[index + 1]]
        for index, (pos, game_id) in enumerate(starts)
    }


def _configured(counter: str, block: str) -> bool:
    return ('"%s"' % COUNTER_GATE[counter]) in block


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

    def test_no_block_runs_past_the_end_of_games(self) -> None:
        """Each block must END in the right place, not merely contain a key.

        The first draft of this module sliced the last game to the end of the
        file, so VV5's block swallowed the builder's own code -- which names
        every configuration key it consumes. Every counter then read as
        configured for VV5 whatever its dictionary held, and the control
        above still passed, because containing `burial_hook_va` says nothing
        about where a block stops.

        Two independent bounds, since a wrong boundary is invisible to a
        containment check: no block may carry builder code, and no block may
        be wildly larger than its siblings.
        """
        for game_id, block in self.configs.items():
            with self.subTest(game=game_id):
                for token in ("def build_game", "def main", "raise RuntimeError"):
                    self.assertNotIn(
                        token,
                        block,
                        "%s's block contains builder code (%r), so it runs "
                        "past the end of GAMES and every key lookup in it is "
                        "meaningless" % (game_id, token),
                    )
        largest = max(len(b) for b in self.configs.values())
        smallest = min(len(b) for b in self.configs.values())
        self.assertLess(
            largest,
            smallest * 20,
            "one game's block dwarfs the others (%d vs %d chars), which is "
            "what an unbounded final slice looks like"
            % (largest, smallest),
        )

    def test_only_the_gating_key_counts_as_configured(self) -> None:
        """A leftover storage address must not read as a shipped counter.

        `death_stat_va` and `debris_stat_va` are consumed only inside the
        branch their hook key opens, so a hook removed while its address was
        left behind emits nothing while still looking configured. Accepting
        any auxiliary key would let exactly the regression this module
        targets pass, so the gate is asserted to be the hook key alone.
        """
        for counter, gate in COUNTER_GATE.items():
            with self.subTest(counter=counter):
                self.assertFalse(
                    _configured(counter, '"%s_stat_va": 0x1234,' % counter),
                    "a bare %s_stat_va reads as configured; the gate must be "
                    "%r, which is what the builder branches on"
                    % (counter, gate),
                )
                self.assertTrue(
                    _configured(counter, '"%s": [],' % gate),
                    "the gating key %r is not recognised, so this module "
                    "cannot see the counter at all" % gate,
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
