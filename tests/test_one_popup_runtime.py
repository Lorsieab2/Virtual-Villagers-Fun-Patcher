"""ONE popup per island event in "VVFP Story Upgrades.dll" (the owner, 2026-11-14; native/shared/one_popup.h): with
Scrolling Popups installed, a branching event (the Isola Grand Event Collection, Custom Island Events) runs whole in
the popup its question path opens -- the text from the start up to and including the first question in ONE text,
its choices drawn by Scrolling Popups after it; a choice shows its outcome (up to the next question, or the ending)
in the same popup; OK ends it.  Run in the emulator on each game's rendered executable (tests/test_story_cie_graph_
runtime.py's Run), in all five games:

  * The Parent's Lesson (the collection's own graph): its intro and its seven-answer question are one text; the run
    is armed once, as a question, and never again; every choice's outcome comes in the same popup with its effects
    made once; ONE Island Events log entry; Island Events Seen counted once.
  * Bug A (the owner's live A New Home, 2026-11-14): in a brand-new village (Island Events Seen 0) the picked event's
    question waited for another island-event trigger after its intro page, and the game's opening event (A Mysterious
    Crate) took it.  In one popup nothing waits for a trigger after the first: the whole event runs start to finish
    with no other island event between its texts.
  * 2, 4 and 7 choices: each choice its own outcome and effect, once; a second question after an answer is asked in
    the same popup, its choices after its text.
  * Without Scrolling Popups: paged as before (the start's intro a page of its own).
"""
from __future__ import annotations

import functools
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT / "scripts"))

import vv_cie_graph as cg  # noqa: E402
from collection_check import graph_for_engine  # noqa: E402
from test_story_custom_island_event import GAMES, HAVE_EMULATOR, TEXT_BUF, emulated, have_stock  # noqa: E402

if HAVE_EMULATOR:
    from test_story_cie_graph_runtime import ASKED, DONE, IDLE, Run, stores

COLLECTION = ROOT / "data" / "event_collection"
# A parent and a child for The Parent's Lesson (its roles: a villager of 14 or more, a child of 3 to 13).
FAMILY = [(0, "f", 30, "Kalani"), (1, "f", 8, "Ana"), (2, "m", 40, "Cal"), (3, "m", 6, "Dee")]


@functools.lru_cache(maxsize=None)
def parents_lesson() -> tuple[dict, bytes]:
    data = json.loads((COLLECTION / "v22" / "all_v22_4_parents.json").read_text(encoding="utf-8"))
    pools = json.loads((COLLECTION / "shared_pools.json").read_text(encoding="utf-8"))
    g = cg.load(graph_for_engine(data), scrolling=True, shared_pools=pools)
    return g, cg.compile_graph(g)


def doors(n: int, then_question: bool = False) -> dict:
    """An intro page, then a question of n choices, each its own page and tech; with then_question the first
    choice's page goes on to a second question of three."""
    choices, nodes = [], {}
    for k in range(n):
        choices.append({"label": f"Open door number {k + 1}", "next": f"d{k}"})
        nodes[f"d{k}"] = {"text": f"Behind door {k + 1}: tech.", "effects": [{"do": "tech", "amount": 10 * (k + 1)}]}
    if then_question:
        nodes["d0"]["children"] = [{"next": "q2"}]
        nodes["d0"]["effects"] = [{"do": "food", "amount": 7}]
        nodes["q2"] = {"type": "question", "text": "Three more doors.", "choices": [
            {"label": "Left", "next": "e0"}, {"label": "Middle", "next": "e1"}, {"label": "Right", "next": "e2"}]}
        for k in range(3):
            nodes[f"e{k}"] = {"text": f"Door {k + 1} of three: tech.",
                              "effects": [{"do": "tech", "amount": 100 * (k + 1)}]}
    nodes["intro"] = {"text": "(Name) walks to the old cliff.", "children": [{"next": "q"}]}
    nodes["q"] = {"type": "question", "text": "(Name) finds many doors in the cliff.", "choices": choices}
    return {"format": "vvfp-cie-graph", "version": 6, "title": "Many Doors", "games": [1, 2, 3, 4, 5],
            "roles": {"subject": {"kind": "villager"}}, "start": "intro", "nodes": nodes}


@functools.lru_cache(maxsize=None)
def doors_cieg(n: int, then_question: bool = False) -> bytes:
    return cg.compile_graph(cg.load(doors(n, then_question), scrolling=True))


def games():
    for game in GAMES:
        if have_stock(game):
            yield game


class OnePopupRun:
    """The event's one popup as its host drives it: opened through the question path (the game's trigger, once),
    every later text through a pick or OK -- never through another trigger."""

    def __init__(self, r: Run):
        self.r = r
        self.p = r.p
        self.arms = 0

    def open(self) -> tuple[str, list[str]]:
        r, p = self.r, self.p
        if not r.state()["armed"]:
            assert p.export("VvfpStoryProbeGraphArmNext", r.n) == 1
        self.arms += 1
        assert r.choice_pending(), "armed as a question: its popup shows choices"
        counter = r.counter_va()
        p.put32(counter, p.u32(counter) + 1)          # the game's trigger counts the island event it makes
        p.write(TEXT_BUF, b"\0")
        assert p.export("VvfpStoryProbeChoiceBegin", r.n, TEXT_BUF, 9000) == 1
        assert p.export("VvfpStoryProbeOnePopupBegun", r.n) == 1, "the host shows the whole event"
        return " ".join(p.cstring(TEXT_BUF, 9000).split()), self.labels()

    def labels(self) -> list[str]:
        n = self.p.export("VvfpStoryProbeOnePopupRows", self.r.n)
        return [self.p.cstring(self.p.export("VvfpStoryProbeChoiceLabel", self.r.n, k)) for k in range(n)]

    def pick(self, k: int) -> tuple[str, list[str]]:
        p = self.p
        p.write(TEXT_BUF, b"\0")
        assert p.export("VvfpStoryProbeChoiceResolve", self.r.n, k, TEXT_BUF, 9000) == 1
        return " ".join(p.cstring(TEXT_BUF, 9000).split()), self.labels()

    def ok(self) -> int:
        self.p.write(TEXT_BUF, b"\0")
        return self.p.export("VvfpStoryProbeOnePopupOk", self.r.n, TEXT_BUF, 9000)

    def quiet(self, test):
        """Nothing armed and nothing waiting for a trigger: the popup holds the run."""
        st = self.r.state()
        test.assertEqual(st["armed"], 0, st)


@emulated
class TheParentsLesson(unittest.TestCase):

    def start(self, game, counter=5):
        r = Run(game, people=FAMILY)
        r.reset()
        r.rolls([0] * 60)
        r.log(1)
        r.p.export("VvfpStoryProbeGraphScroll", 1)
        r.p.put32(r.counter_va(), counter)
        _g, cieg = parents_lesson()
        self.assertIsNone(r.queue(cieg))
        return r

    def test_intro_and_question_one_text_every_choice_in_the_same_popup(self):
        g, _ = parents_lesson()
        labels = [c["label"] for c in g["nodes"]["lesson"]["choices"]]
        for game in games():
            for k in range(7):
                with self.subTest(game=game, choice=k):
                    r = self.start(game)
                    host = OnePopupRun(r)
                    seen0 = r.p.u32(r.counter_va())
                    text, shown = host.open()
                    self.assertIn("testing the patience", text, "the intro")
                    self.assertIn("LESSON SHOULD", text.upper(), "and the question, in ONE text")
                    self.assertLess(text.upper().index("PATIENCE OF THE ADULTS"), text.upper().index("LESSON SHOULD"))
                    self.assertEqual(len(shown), 7)
                    self.assertEqual(shown, [cg.sentence_case(x) for x in labels], "in sentence case, as written")
                    self.assertEqual(shown[0], "Honesty")
                    self.assertIn("Which lesson should Kalani teach?", text, "the question in sentence case")
                    host.quiet(self)
                    outcome, after = host.pick(k)
                    self.assertTrue(outcome.strip(), "the outcome in the same popup")
                    self.assertNotIn("LESSON SHOULD", outcome.upper())
                    self.assertEqual(after, [], "OK now: no choice")
                    host.quiet(self)
                    self.assertEqual(host.ok(), 0, "OK ends the event")
                    self.assertIn(r.state()["phase"], (IDLE, DONE))
                    self.assertEqual(host.arms, 1, "armed once, never again")
                    self.assertEqual(r.p.u32(r.counter_va()), seen0 + 1, "Island Events Seen counted once")
                    n_filed, _now, filed = r.log()
                    self.assertEqual(n_filed, 1, "ONE Island Events log entry")
                    self.assertIn("Choice: ", filed)

    def test_bug_a_a_new_village_runs_the_picked_event_start_to_finish(self):
        """Island Events Seen 0 (the opening events not yet seen): the picked event's intro, question and outcome
        all come in its one popup; no island event of the game's is ever needed between them."""
        for game in games():
            with self.subTest(game=game):
                r = self.start(game, counter=0)
                host = OnePopupRun(r)
                text, shown = host.open()
                self.assertIn("testing the patience", text)
                self.assertEqual(len(shown), 7)
                # Between the texts the run never asks for a trigger: nothing armed, no question pending in the
                # slot another island event could take.
                host.quiet(self)
                self.assertFalse(r.choice_pending())
                outcome, after = host.pick(3)
                host.quiet(self)
                self.assertFalse(r.choice_pending())
                self.assertTrue(outcome.strip())
                self.assertEqual(host.ok(), 0)
                self.assertEqual(host.arms, 1)
                self.assertIn(r.state()["phase"], (IDLE, DONE))


@emulated
class ChoicesAndQuestions(unittest.TestCase):

    def start(self, game, data):
        r = Run(game)
        r.reset()
        r.rolls([0] * 40)
        r.log(1)
        r.p.export("VvfpStoryProbeGraphScroll", 1)
        self.assertIsNone(r.queue(data))
        return r

    def test_two_four_seven_choices_each_its_outcome_once(self):
        for game in games():
            for n in (2, 4, 7):
                for k in sorted({0, n - 1}):
                    with self.subTest(game=game, choices=n, choice=k):
                        r = self.start(game, doors_cieg(n))
                        host = OnePopupRun(r)
                        text, shown = host.open()
                        self.assertIn("walks to the old cliff", text)
                        self.assertIn("finds many doors", text)
                        self.assertEqual(shown, [f"Open door number {i + 1}" for i in range(n)])
                        tech0 = stores(r)[1]
                        outcome, after = host.pick(k)
                        self.assertIn(f"Behind door {k + 1}", outcome)
                        self.assertEqual(after, [])
                        self.assertEqual(stores(r)[1] - tech0, 10 * (k + 1), "its effect, with its text")
                        self.assertEqual(host.ok(), 0)
                        self.assertEqual(stores(r)[1] - tech0, 10 * (k + 1), "once")
                        n_filed, _now, filed = r.log()
                        self.assertEqual(n_filed, 1)
                        self.assertIn(f"Choice: Open door number {k + 1}", filed)

    def test_a_second_question_in_the_same_popup(self):
        for game in games():
            with self.subTest(game=game):
                r = self.start(game, doors_cieg(4, True))
                host = OnePopupRun(r)
                host.open()
                food0, tech0 = stores(r)
                text, shown = host.pick(0)
                self.assertIn("Behind door 1", text, "the answer's text ...")
                self.assertIn("Three more doors", text, "... and the next question, one text")
                self.assertEqual(shown, ["Left", "Middle", "Right"], "its choices after it")
                self.assertEqual(stores(r)[0] - food0, 7, "the answer's effect with its text")
                host.quiet(self)
                text, shown = host.pick(2)
                self.assertIn("Door 3 of three", text)
                self.assertEqual(shown, [])
                self.assertEqual(stores(r)[1] - tech0, 300)
                self.assertEqual(host.ok(), 0)
                self.assertEqual(host.arms, 1)
                n_filed, _now, filed = r.log()
                self.assertEqual(n_filed, 1)
                self.assertIn("Choice: Open door number 1", filed)
                self.assertIn("Choice: Right", filed)

    def test_without_scrolling_popups_the_intro_is_a_page_of_its_own(self):
        for game in games():
            with self.subTest(game=game):
                r = Run(game)
                r.reset()
                r.rolls([0] * 40)
                r.p.export("VvfpStoryProbeGraphScroll", 0)
                self.assertIsNone(r.queue(doors_cieg(4)))
                shown = r.play(button=0)
                self.assertEqual(shown[0][0], "page")
                self.assertIn("walks to the old cliff", shown[0][1])
                self.assertNotIn("finds many doors", shown[0][1])
                self.assertEqual(shown[1][0], "question")


if __name__ == "__main__":
    unittest.main()
