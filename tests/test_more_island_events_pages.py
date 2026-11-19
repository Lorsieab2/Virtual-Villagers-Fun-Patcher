"""More Island Events: the effects wait for their own page, in all five games (the owner's standing rule).

EMULATED (unicorn, the stock executables, the shipped DLL; tests/story_emulator.py), for The Aspiring Adventurer in
all five games and The Cave Explorers in A New Home (The Climb has its own, tests/test_the_climb.py):
  * the ending's effects (a death, an award) are made on the click that shows the ending's LAST page, never before;
  * the Island Events log's one entry ("VVFP Island Events.dll" stood in for): nothing handed over before that page
    -- so a save before it holds neither the effects nor the entry -- then the log's own comparison around the
    effects (Begin / End) and the entry, complete and final: "Event:", a "Choice:" line for each answer clicked,
    the changes;
  * VvfpMoreIslandEventsLogged: 1 while the event is the companion's (the game's own brackets write nothing of their
    own), 0 once the game draws its next event;
  * nothing twice: OK pressed again after the close, and an event left before its last page (a quit) whose popup is
    then replaced by a new one, never make the effects again or at all.

The live game is NOT exercised here.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

from test_aspiring_adventurer import DLL, GAMES, HAVE_EMULATOR, HAVE_STOCK, Village, rolls  # noqa: E402
from test_cave_explorers import CaveVillage, cave_rolls  # noqa: E402

FAKE_ISLAND_EVENTS = 0x0EA00000


def fake_log(v) -> list[tuple]:
    """"VVFP Island Events.dll"'s one-entry exports stood in for on `v`: each call recorded, with the village then."""
    p = v.p
    calls: list[tuple] = []
    code = p.alloc(32)
    p.write(code, b"\xC3" * 32)
    exports = {"VvfpIslandEventsGraphBegin": code, "VvfpIslandEventsGraphEnd": code + 8,
               "VvfpIslandEventsGraphWrite": code + 16}

    def begin(pr):
        calls.append(("begin", snapshot(v)))
        return 1, 4

    def end(pr):
        calls.append(("end", snapshot(v)))
        pr.write(pr.arg(1), b"  Ana: Health 100 -> 0\n\0")
        return len("  Ana: Health 100 -> 0\n"), 12

    def write(pr):
        calls.append(("write", pr.arg(0), pr.cstring(pr.arg(2), 4000), pr.arg(4)))
        return 1, 20
    p.stub(code, begin)
    p.stub(code + 8, end)
    p.stub(code + 16, write)
    module, proc = p.api_handlers["GetModuleHandleA"], p.api_handlers["GetProcAddress"]
    p.api_handlers["GetModuleHandleA"] = lambda pr, m=module: (
        (FAKE_ISLAND_EVENTS, 4) if pr.arg(0) and pr.cstring(pr.arg(0)) == "VVFP Island Events.dll" else m(pr))
    p.api_handlers["GetProcAddress"] = lambda pr, c=proc: (
        (exports.get(pr.cstring(pr.arg(1)), 0), 8) if pr.arg(0) == FAKE_ISLAND_EVENTS else c(pr))
    return calls


def snapshot(v) -> tuple:
    return (v.stores(), v.health(0), v.health(1), v.present(0), v.present(1))


def logged(v, title: str) -> int:
    at = v.p.alloc(len(title) + 1)
    v.p.write(at, title.encode() + b"\0")
    return v.p.export("VvfpMoreIslandEventsLogged", v.game, at)


def adventurer(game: int, log: bool = True):
    v = Village(game)
    v.villager(0, "Ana", True)
    v.villager(1, "Ben")
    calls = fake_log(v) if log else []
    return v, calls


def play_steps(v, rolls_: list[int], answer: int) -> list[tuple]:
    """The Adventurer's popup, click by click: (what was clicked, the village after it, the log's calls so far)."""
    if not v.begin(rolls_):
        raise AssertionError("the event was not drawn")
    steps = []
    for _ in range(v.state()[15] - 1):
        v.click(0)
    v.click(answer)
    steps.append(("answer", snapshot(v)))
    for _ in range(v.state()[16 if answer == 1 else 17] - 1):
        v.click(0)
        steps.append(("ok", snapshot(v)))
    v.ui.clear()
    v.click(0)
    steps.append(("close", snapshot(v)))
    return steps


A2 = dict(find=0, survive=False, end=0)          # "Go investigate!": the beast, dies (a grave)


@unittest.skipUnless(HAVE_EMULATOR and HAVE_STOCK and DLL.is_file(), "needs unicorn, pefile and the stock executables")
class TheAdventurer(unittest.TestCase):
    def test_the_effects_on_the_last_page_only_and_one_entry(self) -> None:
        for game in GAMES:
            with self.subTest(game=game):
                v, calls = adventurer(game)
                before = snapshot(v)
                steps = play_steps(v, rolls(game=game, **A2), 1)
                pages = v.state()[16]
                self.assertGreater(pages, 1)                     # the opening's page, then the ending's
                shown_last = steps[pages - 1]                     # the click that showed the last page
                for kind, state in steps[:pages - 1]:
                    self.assertEqual(state, before, kind)         # nothing on the earlier pages
                self.assertEqual(shown_last[1][1], 0)             # the death, as the last page shows
                self.assertEqual(steps[-1][1], shown_last[1])     # nothing more at the close
                kinds = [c[0] for c in calls]
                self.assertEqual(kinds, ["begin", "end", "write"])
                self.assertEqual(calls[0][1], before)
                self.assertEqual(calls[1][1][1], 0)
                self.assertEqual(calls[2][1], game)
                self.assertEqual(calls[2][2], "  Event: The Aspiring Adventurer\n  Choice: Go investigate!\n"
                                              "  Ana: Health 100 -> 0\n")
                self.assertEqual(calls[2][3], 1)                  # final: handed over once, complete

    def test_an_award_on_the_last_page(self) -> None:
        for game in GAMES:
            with self.subTest(game=game):
                v, calls = adventurer(game)
                before = snapshot(v)
                steps = play_steps(v, rolls(game=game, find=1, end=0), 1)   # A1: the meat, food
                pages = v.state()[16]
                for kind, state in steps[:pages - 1]:
                    self.assertEqual(state, before, kind)
                self.assertNotEqual(steps[pages - 1][1][0], before[0])

    def test_logged_while_ours_then_not(self) -> None:
        for game in GAMES:
            with self.subTest(game=game):
                v, _ = adventurer(game)
                self.assertEqual(logged(v, "The Aspiring Adventurer"), 0)
                play_steps(v, rolls(game=game, **A2), 1)
                self.assertEqual(logged(v, "The Aspiring Adventurer"), 1)   # through the close's own bracket
                if game <= 2:
                    self.assertEqual(logged(v, "Some Other Event"), 0)
                v.villager(1, "Ben", years=10)                    # the next draw: not ours
                v.begin([0] * 20)
                self.assertEqual(logged(v, "The Aspiring Adventurer"), 0)

    def test_nothing_twice(self) -> None:
        for game in GAMES:
            with self.subTest(game=game):
                # OK again after the close.
                v, calls = adventurer(game)
                play_steps(v, rolls(game=game, find=1, end=0), 1)
                after = snapshot(v)
                v.click(0)
                v.click(1)
                self.assertEqual(snapshot(v), after)
                self.assertEqual([c[0] for c in calls].count("write"), 1)
                # Left before the last page (a quit): its popup gone, a new event's popup instead.
                v, calls = adventurer(game)
                before = snapshot(v)
                self.assertTrue(v.begin(rolls(game=game, **A2)))
                for _ in range(v.state()[15] - 1):
                    v.click(0)
                v.click(1)                                        # the answer: its first page only
                self.assertEqual(snapshot(v), before)
                self.assertEqual(calls, [])                       # a save now: no effects, no entry -- they match
                v.begin(rolls(game=game, find=1, end=0))          # the game reloaded: another popup
                self.assertEqual(snapshot(v), before)             # the first event's effects never come
                for _ in range(v.state()[15] - 1):
                    v.click(0)
                v.click(1)
                for _ in range(v.state()[16] + 2):
                    v.click(0)
                self.assertEqual(v.health(0), 100)                # no death from the left event
                self.assertEqual([c[0] for c in calls].count("write"), 1)
                self.assertEqual(calls[-1][2].count("  Choice: "), 1)   # only the new event's own answer

    def test_without_the_log_companion(self) -> None:
        for game in GAMES:
            with self.subTest(game=game):
                v, _ = adventurer(game, log=False)
                play_steps(v, rolls(game=game, **A2), 1)
                self.assertEqual(v.health(0), 0)


@unittest.skipUnless(HAVE_EMULATOR and HAVE_STOCK and DLL.is_file(), "needs unicorn, pefile and the stock executables")
class TheCaveExplorers(unittest.TestCase):
    def village(self):
        v = CaveVillage()
        v.villager(0, "Ana", True, years=20)
        v.villager(1, "Ben", False, years=24)
        return v, fake_log(v)

    def play(self, v, rolls_, answers):
        """Every click, with the village after it and whether the answers were up before it."""
        self.assertTrue(v.begin(rolls_))
        steps = []
        answers = list(answers)
        for _ in range(60):
            if v.answers_up():
                v.click(answers.pop(0) + 1)
                steps.append(("answer", snapshot(v)))
            else:
                v.ui.clear()
                v.click(0)
                if v.closed():
                    steps.append(("close", snapshot(v)))
                    break
                steps.append(("ok", snapshot(v)))
        return steps

    def test_both_die_on_the_last_page_with_every_choice_logged(self) -> None:
        v, calls = self.village()
        before = snapshot(v)
        steps = self.play(v, cave_rolls(keep="KEEP_BOTH"), [0, 1, 1])
        last = len(steps) - 2                                     # the click before the close showed the last page
        self.assertEqual(steps[-1][0], "close")
        for kind, state in steps[:last]:
            self.assertEqual(state, before, kind)                 # nothing on any earlier page or answer
        self.assertEqual((steps[last][1][1], steps[last][1][2]), (0, 0))   # both die as the last page shows
        self.assertEqual([c[0] for c in calls], ["begin", "end", "write"])
        self.assertEqual(calls[-1][2], "  Event: The Cave Explorers\n  Choice: Explore the Cave\n"
                                       "  Choice: Stay Here\n  Choice: Curses schmurses. I'm keeping them.\n"
                                       "  Ana: Health 100 -> 0\n")
        self.assertEqual(calls[-1][3], 1)

    def test_an_award_waits_for_its_page(self) -> None:
        v, calls = self.village()
        before = snapshot(v)
        steps = self.play(v, cave_rolls(scream=False, find="FIND_COINS"), [0, 0])
        changed = [i for i, (_, s) in enumerate(steps) if s != before]
        self.assertTrue(changed)
        self.assertEqual(changed[0], len(steps) - 2)              # the click that shows the last page
        self.assertIn("  Choice: Proceed Further\n", calls[-1][2])

    def test_dont_explore_logs_changes_none(self) -> None:
        v, calls = self.village()
        steps = self.play(v, cave_rolls(), [1])
        self.assertEqual(steps[-1][0], "close")
        self.assertTrue(calls[-1][2].startswith("  Event: The Cave Explorers\n  Choice: Don't explore\n"))
        self.assertEqual(calls[-1][3], 1)


if __name__ == "__main__":
    unittest.main()
