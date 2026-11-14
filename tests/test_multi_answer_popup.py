"""Island-event questions with 2 to 7 answers (the owner, 2026-11-13: "Make the 2-4 option thing general"; the Isola
Grand Event Collection, 2026-11-14: up to seven, all on ONE page).

Custom Island Events (format version 4), in the test build of "VVFP Story Upgrades.dll" mapped beside each game's
rendered executable in the emulator (tests/test_story_cie_graph_runtime.py's Run):

* in all five games: a four-answer question and, after one answer's page, a three-answer one -- every answer
  reachable, its labels, its own page first with its effects made on it (once), ONE Island Events log entry with a
  "Choice:" line per answer, and a quit with the question on screen or after an answer the save lacks resumes
  correctly;
* A New Home and The Lost Children: the question in the game's own encounter dialog (the setup call the companion
  holds, the dialog's draw, its click handler -- the game's own for its two answers): the extra buttons made at the
  first draw with the game's routines, picture and label colours, ids 5 and 6, stacked and centred, the question
  padded for them; each answer by mouse and by keys 1-4; Enter for OK; ours deleted at the next draw;
* The Secret City, The Tree of Life and New Believers: the question shown in the game's own two-choice popup through
  the presenter (each game's pick site, the companion's own path for 3 or 4 answers, a stand-in for the dialog's
  constructor as tests/test_troubling_signs.py has it, the game's own click handler): the extra buttons made with the
  game's own routines, stacked and centred 1.5 button heights apart, long labels on screen; the room told to Scrolling
  Popups; each answer by mouse and by keys 1-4; Enter for OK; our buttons deleted at the OK;
* with two answers the presenter's path, the dialog and its virtual table are exactly the game's (nothing ours).
"""
from __future__ import annotations

import copy
import functools
import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import vv_cie_graph as cg  # noqa: E402
from test_story_custom_island_event import GAMES, HAVE_EMULATOR, TEXT_BUF, emulated, have_stock  # noqa: E402

if HAVE_EMULATOR:
    from story_emulator import STACK_TOP
    from test_story_cie_graph_runtime import ASKED, CHAIN, DONE, IDLE, Run, stores
    from unicorn import UC_HOOK_CODE


def four_doors() -> dict:
    """Four answers, then (after the second answer's own page) three; every answer its own page and effect."""
    return {
        "format": "vvfp-cie-graph", "version": 4, "title": "Four Doors", "games": [1, 2, 3, 4, 5],
        "roles": {"subject": {"kind": "villager"}},
        "start": "q",
        "nodes": {
            "q": {"type": "question", "text": "(Name) finds four doors in the cliff.", "choices": [
                {"label": "Open the red door at the very top", "next": "a"},
                {"label": "Open the blue door", "next": "b"},
                {"label": "Open the green door", "next": "c"},
                {"label": "Open the gold door, the last one", "next": "d"}]},
            "a": {"text": "Behind the red door: food.", "effects": [{"do": "food", "amount": 100}]},
            "b": {"text": "Behind the blue door: a second room.", "children": [{"next": "q2"}]},
            "q2": {"type": "question", "text": "Three more doors.", "choices": [
                {"label": "Left", "next": "e"}, {"label": "Middle", "next": "f"}, {"label": "Right", "next": "h"}]},
            "e": {"text": "Left: tech.", "effects": [{"do": "tech", "amount": 10}]},
            "f": {"text": "Middle: tech.", "effects": [{"do": "tech", "amount": 20}]},
            "h": {"text": "Right: tech.", "effects": [{"do": "tech", "amount": 30}]},
            "c": {"text": "Behind the green door: tech.", "effects": [{"do": "tech", "amount": 100}]},
            "d": {"text": "Behind the gold door: food.", "effects": [{"do": "food", "amount": 200}]},
        },
    }


FOUR = cg.load(four_doors())
FOUR_CIEG = cg.compile_graph(FOUR)
LABELS = [c["label"] for c in FOUR["nodes"]["q"]["choices"]]
LABELS2 = [c["label"] for c in FOUR["nodes"]["q2"]["choices"]]
# Each answer of the first question: (its page's words, food, tech) -- the second answer goes on to q2.
FIRST = {0: ("red door: food", 100, 0), 1: ("a second room", 0, 0), 2: ("green door: tech", 0, 100),
         3: ("gold door: food", 200, 0)}
SECOND = {0: ("Left: tech", 10), 1: ("Middle: tech", 20), 2: ("Right: tech", 30)}

TWO = four_doors()
TWO["version"] = 3
TWO["games"] = [1, 2, 3, 4, 5]
TWO["nodes"] = {"q": {"type": "question", "text": "(Name) finds two doors.", "choices": [
    {"label": "Open the red door at the very top", "next": "a"}, {"label": "Open the green door", "next": "c"}]},
    "a": TWO["nodes"]["a"], "c": TWO["nodes"]["c"]}
TWO_CIEG = cg.compile_graph(cg.load(TWO))

# The three games' two-choice popup and the presenter (the pick site the companion's stub holds, then the
# constructor's call), with the routines the shared popup calls (native/shared/vvfp_multi_answer.h).
TABLE = {
    "vv3": dict(pick=0x419BDB, after=0x419BEF, table=0x4B3C78, ctor=0x4192F0, dvt=0x47F28C, click=0x419A00,
                settext=0x4185A0, hide=0x40C230, show=0x40C1F0, close=0x40E020, alloc=0x46EC93, images=0x42E9D0,
                image=(0x42E8A0, 4), button=0x4019F0, label=0x401620, holder=0x408940, justify=0x40A0C0,
                dialog=0xF0, strings=0x592730),
    "vv4": dict(pick=0x4180F7, after=0x41810B, table=0x4CCA28, ctor=0x417790, dvt=0x48D2C8, click=0x417EA0,
                settext=0x416F60, hide=0x40C210, show=0x40C190, close=0x40E090, alloc=0x470C5C, images=0x44CCF0,
                image=(0x44CB60, 0x83), button=0x401C20, label=0x401600, holder=0x408130, justify=0x409C30,
                dialog=0xD8, strings=0x4DEA20),
    "vv5": dict(pick=0x41895B, after=0x41896F, table=0x4DC850, ctor=0x418020, dvt=0x4984D8, click=0x418720,
                settext=0x417700, hide=0x40C700, show=0x40C680, close=0x40E580, alloc=0x47BBDC, images=0x44FBB0,
                image=(0x44FA20, 0x65), button=0x401BD0, label=0x4015D0, holder=0x4080C0, justify=0x409F00,
                dialog=0xF0, strings=0x5240A8),
}
BUTTON_W, BUTTON_H = 401, 42
LINE = 20
PANEL = (144, 20, 656, 580)
SCREEN_W = 800
# The stand-in constructor (tests/test_troubling_signs.py): the event at +0x50, the tallest page measured (+0x28(0)),
# shown (+0x4C).
CTOR = bytes.fromhex("56" "8BF1" "8B442408" "894650" "8BC8" "8B10" "6A00" "FF5228" "C6464C01" "8BC6" "5E" "C20400")


class Popup:
    """One of the three games with the companion and the question shown in the game's own popup."""

    def __init__(self, game: str):
        self.r = Run(game)
        self.t = TABLE[game]
        self.p = self.r.p
        p, t = self.p, self.t
        self.buttons: dict[int, int] = {}
        self.labels: dict[int, str] = {}
        self.placed: dict[int, tuple[int, int]] = {}
        self.deleted: list[int] = []
        self.ui: list[tuple] = []
        code = p.alloc(64)
        p.write(code, b"\xC3" * 64)
        self.vt = p.alloc(32)
        for k in range(5):
            p.put32(self.vt + 4 * k, code + 8 * k)
        self.stub(code, lambda pr: (self.deleted.append(pr.reg("ecx")) or 0, 4))
        self.stub(code + 8, self._place)
        self.stub(code + 16, lambda pr: (0, 0))
        self.stub(code + 24, lambda pr: (BUTTON_W, 0))
        self.stub(code + 32, lambda pr: (BUTTON_H, 0))
        self.stub(t["images"], lambda pr: (0x7777, 0))
        self.stub(t["alloc"], lambda pr: (p.alloc(0x40), 0))
        self.stub(t["image"][0], self._image)
        self.stub(t["button"], self._button)
        self.stub(t["label"], self._label)
        self.stub(t["holder"], lambda pr: (0x6666, 0))
        self.stub(t["justify"], self._measure)
        self.stub(t["settext"], self._settext)
        self.stub(t["show"], lambda pr: (self.ui.append(("show", pr.arg(0))) or 0, 4))
        self.stub(t["hide"], lambda pr: (self.ui.append(("hide", pr.arg(0))) or 0, 4))
        self.stub(t["close"], lambda pr: (self.ui.append(("close",)) or 0, 0))
        p.write(t["ctor"], CTOR)
        # The Secret City's selector leaves a Barrel of Babies (every slot the same object) alone: slots 1 and 2 differ.
        p.put32(t["table"] + 4, 0x1111)
        p.put32(t["table"] + 8, 0x2222)
        p.mu.ctl_flush_tb()

    def stub(self, va, fn):
        self.p.stub(va, fn)
        self.p.mu.hook_add(UC_HOOK_CODE, self.p._on_code, begin=va, end=va)

    # -- stand-ins ----------------------------------------------------------------------------------------------
    def _image(self, pr):
        assert pr.arg(0) == self.t["image"][1], "the answer picture the constructor uses"
        return 0x5555, 4

    def _place(self, pr):
        ident = next((i for i, b in self.buttons.items() if b == pr.reg("ecx")), 0)
        self.placed[ident] = (pr.arg(0), pr.arg(1))
        return 0, 8

    def _button(self, pr):
        b = pr.reg("ecx")
        pr.put32(b, self.vt)
        self.buttons[pr.arg(0)] = b
        assert pr.arg(1) == 0x5555 and pr.arg(4) == self.dlg, "the picture and the dialog as its listener"
        return b, 0x18

    def _label(self, pr):
        ident = next((i for i, b in self.buttons.items() if b == pr.reg("ecx")), 0)
        self.labels[ident] = pr.cstring(pr.arg(0), 4000)
        return 0, 0x14

    def _measure(self, pr):
        return LINE * (pr.cstring(pr.arg(0), 4000).count("\n") + 1), 0x1C

    def _settext(self, pr):
        entry = pr.u32(self.t["strings"] + 4 * pr.arg(0))
        text = pr.u32(entry + 12) or pr.u32(entry + 8)
        self.ui.append(("text", pr.cstring(text, 4000)))
        if pr.reg("ecx") == self.dlg:
            pr.write(self.dlg + 0x58, pr.cstring(text, 1999).encode("latin-1") + b"\0")
        return 0, 4

    # -- the popup ----------------------------------------------------------------------------------------------
    def present(self) -> int:
        """The armed question presented by the game's presenter: the dialog its constructor builds (on the stack)."""
        p, t, r = self.p, self.t, self.r
        st = r.state()
        if not st["armed"] and st["phase"] != ASKED:
            assert p.export("VvfpStoryProbeGraphArmNext", r.n) == 1, st
        assert r.choice_pending(), "a question is armed"
        esp = STACK_TOP - 0x10000
        self.dlg = d = esp + t["dialog"]
        p.write(d, b"\0" * 0x900)
        p.put32(d, t["dvt"])
        p.write(d + 0x14, struct.pack("<4i", *PANEL))
        p.put32(d + 0x858, 0x1B0)
        self.buttons, self.labels, self.placed = {}, {}, {}
        for ident, field in ((2, 0x85C), (3, 0x860), (1, 0x864)):
            b = p.alloc(0x40)
            p.put32(b, self.vt)
            self.buttons[ident] = b
            p.put32(d + field, b)
        self.ui.clear()
        p.set_reg("esp", esp)
        p.set_reg("esi", 1)
        p.run(t["pick"], t["after"])
        return d

    def click(self, ident: int) -> None:
        self.p.call(self.p.u32(self.p.u32(self.dlg) + 0x0C), [8, ident], ecx=self.dlg)

    def key(self, kind: int, code: int) -> int:
        return self.p.call(self.p.u32(self.p.u32(self.dlg) + 0x08), [kind, code, 0], ecx=self.dlg) & 0xFF

    def room(self) -> int:
        return self.p.export("VvfpStoryButtonRoom", self.dlg)

    def text(self) -> str:
        texts = [u[1] for u in self.ui if u[0] == "text"]
        return texts[-1] if texts else ""

    def answer(self, k: int, by_key: bool) -> None:
        if by_key:
            self.assertKey = self.key(5, ord("1") + k)
        else:
            self.click(2 + k)

    def pages(self) -> list[str]:
        """The notice pages until the next question or the run's end (as the game's trigger shows them)."""
        r, p = self.r, self.p
        shown = []
        for _ in range(32):
            st = r.state()
            if st["phase"] in (IDLE, DONE) or (st["armed"] and r.choice_pending()):
                break
            if not st["armed"]:
                assert p.export("VvfpStoryProbeGraphArmNext", r.n) == 1, st
            if r.choice_pending():
                break
            p.write(TEXT_BUF, b"\0")
            assert p.export("VvfpStoryProbeDeliver", r.n, TEXT_BUF, 9000) == 1
            shown.append(p.cstring(TEXT_BUF))
        return shown


def norm(text: str) -> str:
    return " ".join(text.split())


@emulated
class ThePopup(unittest.TestCase):
    """The Secret City, The Tree of Life, New Believers: the game's own popup with three or four answers."""

    def games(self):
        for game in ("vv3", "vv4", "vv5"):
            if have_stock(game):
                yield game

    def opened(self, game: str, data: bytes = FOUR_CIEG) -> Popup:
        v = Popup(game)
        v.r.reset()
        v.r.rolls([0] * 40)
        self.assertIsNone(v.r.queue(data))
        v.present()
        return v

    def test_four_buttons_made_as_the_game_makes_them_stacked_centred_and_on_screen(self):
        for game in self.games():
            with self.subTest(game=game):
                v = self.opened(game)
                p = v.p
                self.assertEqual(sorted(v.buttons), [1, 2, 3, 4, 5])
                self.assertEqual([v.labels[i] for i in (4, 5)], LABELS[2:])
                self.assertNotEqual(p.u32(v.dlg), TABLE[game]["dvt"], "our copy of the dialog's virtual table")
                self.assertEqual(p.u32(p.u32(v.dlg) + 0x0C) != TABLE[game]["click"], True)
                width, height = PANEL[2] - PANEL[0], PANEL[3] - PANEL[1]
                ys = [v.placed[i][1] for i in (2, 3, 4, 5)]
                for i in (2, 3, 4, 5):
                    self.assertEqual(v.placed[i][0], (width - BUTTON_W) // 2, "centred")
                self.assertEqual(ys[-1], height - 2 * BUTTON_H, "the last where the game puts its second")
                self.assertEqual([b - a for a, b in zip(ys, ys[1:])], [BUTTON_H + BUTTON_H // 2] * 3,
                                 "1.5 button heights apart: labels never meet")
                self.assertGreaterEqual(ys[0], 0)
                for label in LABELS:
                    self.assertLessEqual(cg.label_px(int(game[2:]), label), cg.label_max_px(int(game[2:])))
                self.assertEqual(v.room(), 3 * BUTTON_H, "Scrolling Popups keeps the text above the four")
                self.assertEqual(v.p.export("VvfpStoryButtonRoom", v.dlg + 4), 0, "any other popup: none")
                # The question's text is back after the labels went through it.
                self.assertIn("finds four doors", v.text())

    def test_every_answer_by_mouse_and_by_key(self):
        for game in self.games():
            for k in range(4):
                for by_key in (False, True):
                    with self.subTest(game=game, answer=k, by_key=by_key):
                        v = self.opened(game)
                        food0, tech0 = stores(v.r)
                        v.ui.clear()
                        if by_key:
                            self.assertEqual(v.key(6, 0x3EB), 0, "Enter takes no answer")
                            self.assertEqual(v.key(5, ord("1") + k), 1)
                        else:
                            v.click(2 + k)
                        self.assertEqual(v.r.state()["choice"], k)
                        words, food, tech = FIRST[k]
                        self.assertIn(words, v.text(), "the answer's own page first")
                        food1, tech1 = stores(v.r)
                        self.assertEqual((food1 - food0, tech1 - tech0), (food, tech), "its effects with its page")
                        shown = {a for w, a in v.ui if w == "show"}
                        self.assertIn(v.p.u32(v.dlg + 0x864), shown, "OK shown")
                        hidden = {a for w, a in v.ui if w == "hide"}
                        for ident in (2, 3, 4, 5):
                            self.assertIn(v.buttons[ident], hidden, "every answer hidden")
                        extra = [v.buttons[4], v.buttons[5]]
                        v.ui.clear()
                        if by_key:
                            self.assertEqual(v.key(6, 0x3EB), 1, "Enter is OK")
                        else:
                            v.click(1)
                        self.assertTrue(set(extra) <= set(v.deleted), "our buttons deleted at the OK")
                        self.assertIn(("close",), v.ui)
                        self.assertEqual(v.room(), 0, "closed: no room claimed")
                        self.assertEqual(stores(v.r), (food1, tech1), "nothing made twice")

    def test_three_answers_after_a_page_then_each_answer(self):
        for game in self.games():
            for k in range(3):
                with self.subTest(game=game, answer=k):
                    v = self.opened(game)
                    v.click(3)                                    # the blue door: its own page, then q2
                    self.assertIn("a second room", v.text())
                    v.click(1)
                    self.assertEqual(v.pages(), [])
                    v.present()
                    self.assertEqual(sorted(v.buttons), [1, 2, 3, 4])
                    self.assertEqual(v.labels[4], LABELS2[2])
                    ys = [v.placed[i][1] for i in (2, 3, 4)]
                    self.assertEqual(ys[-1], PANEL[3] - PANEL[1] - 2 * BUTTON_H)
                    self.assertEqual(v.room(), 3 * BUTTON_H // 2)
                    self.assertEqual(v.key(5, ord("4")), 0, "no fourth answer")
                    tech0 = stores(v.r)[1]
                    v.key(5, ord("1") + k)
                    self.assertIn(SECOND[k][0], v.text())
                    self.assertEqual(stores(v.r)[1] - tech0, SECOND[k][1])
                    v.click(1)
                    self.assertIn(v.r.state()["phase"], (IDLE, DONE))

    def test_two_answers_are_the_games_own_popup(self):
        for game in self.games():
            with self.subTest(game=game):
                v = self.opened(game, TWO_CIEG)
                self.assertEqual(sorted(v.buttons), [1, 2, 3], "no button of ours")
                self.assertEqual(v.p.u32(v.dlg), TABLE[game]["dvt"], "the game's own virtual table")
                self.assertEqual(v.placed, {}, "the game's own placing")
                self.assertEqual(v.room(), 0)
                v.click(3)
                self.assertIn("green door: tech", v.text())


@emulated
class EveryGame(unittest.TestCase):
    """All five games, through the companion's question entry points: every answer, its page, its effects, one log
    entry, and a quit with the question on screen."""

    def games(self):
        for game in GAMES:
            if have_stock(game):
                yield game

    def ask(self, r: Run) -> tuple[str, list[str]]:
        st = r.state()
        if not st["armed"] and st["phase"] != ASKED:
            assert r.p.export("VvfpStoryProbeGraphArmNext", r.n) == 1, st
        r.p.write(TEXT_BUF, b"\0")
        assert r.p.export("VvfpStoryProbeChoiceBegin", r.n, TEXT_BUF, 4096) == 1
        labels = []
        for b in range(5):
            at = r.p.export("VvfpStoryProbeChoiceLabel", r.n, b)
            if at:
                labels.append(r.p.cstring(at))
        return r.p.cstring(TEXT_BUF), labels

    def resolve(self, r: Run, b: int) -> str:
        r.p.write(TEXT_BUF, b"\0")
        assert r.p.export("VvfpStoryProbeChoiceResolve", r.n, b, TEXT_BUF, 4096) == 1
        return r.p.cstring(TEXT_BUF)

    def test_every_answer_its_page_its_effects_one_entry(self):
        for game in self.games():
            for k in range(4):
                for k2 in (range(3) if k == 1 else (None,)):
                    with self.subTest(game=game, answer=k, second=k2):
                        r = Run(game)
                        r.reset()
                        r.rolls([0] * 40)
                        r.log(1)
                        self.assertIsNone(r.queue(FOUR_CIEG))
                        q, labels = self.ask(r)
                        self.assertIn("finds four doors", q)
                        self.assertEqual(labels, LABELS)
                        food0, tech0 = stores(r)
                        result = self.resolve(r, k)
                        self.assertIn(FIRST[k][0], result)
                        food1, tech1 = stores(r)
                        self.assertEqual((food1 - food0, tech1 - tech0), FIRST[k][1:])
                        if k2 is not None:
                            q2, labels2 = self.ask(r)
                            self.assertEqual(labels2, LABELS2)
                            self.assertEqual(r.p.export("VvfpStoryProbeChoiceResolve", r.n, 3, TEXT_BUF, 4096), 0,
                                             "a three-answer question has no fourth")
                            result2 = self.resolve(r, k2)
                            self.assertIn(SECOND[k2][0], result2)
                            self.assertEqual(stores(r)[1] - tech1, SECOND[k2][1])
                        self.assertIn(r.state()["phase"], (IDLE, DONE))
                        n, _now, filed = r.log()
                        self.assertEqual(n, 1, "one Island Events log entry")
                        self.assertEqual(filed.count("Choice:"), 1 if k2 is None else 2)
                        self.assertIn(LABELS[k], filed)
                        if k2 is not None:
                            self.assertIn("Choice: " + LABELS2[k2], filed)

    def restart(self, game: str, file: bytes, save: int) -> Run:
        """A new process standing for the reloaded save (made at `save`), with the run's file as it was."""
        r = Run(game)
        r.rolls([0] * 40)
        r.p.export("VvfpStoryProbeQueueSession", 0, 0, save, 0)
        buf = r.p.alloc(len(file) + 16)
        r.p.write(buf, file)
        r.p.export("VvfpStoryProbeGraphSession", buf, len(file))
        r.tick()
        return r

    def test_a_quit_with_the_question_on_screen_asks_it_again_with_the_same_answers(self):
        for game in self.games():
            with self.subTest(game=game):
                r = Run(game)
                r.reset()
                r.rolls([0] * 40)
                self.assertIsNone(r.queue(FOUR_CIEG))
                self.ask(r)
                r.tick()
                again = self.restart(game, r.graph_file(), 0x7FFFFFF0)
                self.assertEqual(again.state()["phase"], ASKED)
                _q, labels = self.ask(again)
                self.assertEqual(labels, LABELS)
                food0 = stores(again)[0]
                self.assertIn(FIRST[3][0], self.resolve(again, 3))
                self.assertEqual(stores(again)[0] - food0, 200)

    def test_a_quit_after_an_answer_the_save_lacks_asks_it_again(self):
        for game in self.games():
            with self.subTest(game=game):
                r = Run(game)
                r.reset()
                r.rolls([0] * 40)
                r.log(1)
                r.p.export("VvfpStoryProbeQueueSession", 0, 0, 1, 0)   # the last save: before the purchase
                self.assertIsNone(r.queue(FOUR_CIEG))
                self.ask(r)
                asked_at = r.p.tick
                r.p.tick += 5000
                r.p.export("VvfpStoryProbeSetTick", r.p.tick)
                self.resolve(r, 2)                       # the green door, its tech made ...
                r.tick()
                again = self.restart(game, r.graph_file(), asked_at + 1)   # ... but the save is from before it
                again.log(1)
                self.assertEqual(again.state()["phase"], ASKED, "asked again")
                _q, labels = self.ask(again)
                self.assertEqual(labels, LABELS, "the same four answers")
                food0, tech0 = stores(again)
                self.assertIn(FIRST[3][0], self.resolve(again, 3))
                self.assertEqual((stores(again)[0] - food0, stores(again)[1] - tech0), (200, 0))
                n, _now, filed = again.log()
                self.assertEqual(filed.count("Choice:"), 1, "one Choice line: the answer given after the reload")
                self.assertIn(LABELS[3], filed)
                self.assertNotIn(LABELS[2], filed)


# A New Home's and The Lost Children's encounter dialog (native/shared/vvfp_multi_answer_12.h).
ENCOUNTER = {
    "vv1": dict(site=0x41A51F, dvt=0x459578, alloc=0x44AF03, button=0x4019B0, image=0x4595C4, label=0x4015B0,
                attach=0x40AB80, remove=0x40ABC0, sound=0x431470, draw=0x4187E0, lines=0x402100, select=0x43A160,
                close=0x40C9B0, resolve=0x419380, buttons=(0x50BC, 0x50C0, 0x50C4), choice=0x509C, res=0x2783,
                q=0x74, font=0x50AC, villagers=0x50A8, sound_field=0x50A0),
    "vv2": dict(site=0x42244A, dvt=0x476714, alloc=0x467F83, button=0x4019D0, image=0x47677C, label=0x4015D0,
                attach=0x40B560, remove=0x40B5A0, sound=0x43F010, draw=0x41F430, lines=0x402190, select=0x44B2D0,
                close=0x40D390, resolve=0x4204B0, buttons=(0x50C8, 0x50CC, 0x50D0), choice=0x50A4, res=0x278B,
                q=0x7C, font=0x50B4, villagers=0x50B0, sound_field=0x50A8),
}
ENC_W, ENC_H = 300, 40
ENC_PANEL = (100, 30, 700, 590)


class Encounter:
    """A New Home or The Lost Children with the companion and the question in the game's own encounter dialog."""

    def __init__(self, game: str):
        self.r = Run(game)
        self.e = ENCOUNTER[game]
        self.p = self.r.p
        p, e = self.p, self.e
        self.made: dict[int, int] = {}            # id -> button (ours, made by the game's own routines)
        self.labels: dict[int, tuple] = {}
        self.placed: dict[int, tuple[int, int]] = {}
        self.deleted: list[int] = []
        self.ui: list[tuple] = []
        code = p.alloc(64)
        p.write(code, b"\xC3" * 64)
        self.vt = p.alloc(32)
        for k in range(5):
            p.put32(self.vt + 4 * k, code + 8 * k)
        self.stub(code, lambda pr: (self.deleted.append(pr.reg("ecx")) or 0, 4))
        self.stub(code + 8, self._place)
        self.stub(code + 16, lambda pr: (0, 0))
        self.stub(code + 24, lambda pr: (ENC_W, 0))
        self.stub(code + 32, lambda pr: (ENC_H, 0))
        self.stub(e["alloc"], lambda pr: (p.alloc(0x40), 0))
        self.stub(e["button"], self._button)
        self.stub(e["label"], self._label)
        self.stub(e["attach"], lambda pr: (self.ui.append(("on", pr.arg(0))) or 0, 4))
        self.stub(e["remove"], lambda pr: (self.ui.append(("off", pr.arg(0))) or 0, 4))
        self.stub(e["sound"], lambda pr: (0, 4))
        self.stub(e["draw"], lambda pr: (self.ui.append(("draw",)) or 0, 0))
        self.stub(e["lines"], lambda pr: (LINE, 4))
        self.stub(e["select"], lambda pr: (0, 4))
        self.stub(e["close"], lambda pr: (self.ui.append(("close",)) or 0, 0))
        p.mu.ctl_flush_tb()

    def stub(self, va, fn):
        self.p.stub(va, fn)
        self.p.mu.hook_add(UC_HOOK_CODE, self.p._on_code, begin=va, end=va)

    def _place(self, pr):
        ident = next((i for i, b in {**self.made, **self.own}.items() if b == pr.reg("ecx")), 0)
        self.placed[ident] = (pr.arg(0), pr.arg(1))
        return 0, 8

    def _button(self, pr):
        b = pr.reg("ecx")
        pr.put32(b, self.vt)
        assert pr.arg(1) == self.e["image"] and pr.arg(4) == self.dlg, "the answers' picture, the dialog listens"
        self.made[pr.arg(0)] = b
        return b, 0x18

    def _label(self, pr):
        ident = next((i for i, b in self.made.items() if b == pr.reg("ecx")), 0)
        self.labels[ident] = (pr.cstring(pr.arg(0)), pr.arg(1), pr.arg(2), pr.arg(3))
        return 0, 0x14

    def open(self, data: bytes = None) -> int:
        """The question armed and the dialog's setup run (the companion's, at the constructor's setup call)."""
        p, e, r = self.p, self.e, self.r
        r.reset()
        r.rolls([0] * 40)
        assert r.queue(data if data is not None else FOUR_CIEG) is None
        if not r.state()["armed"]:
            assert p.export("VvfpStoryProbeGraphArmNext", r.n) == 1
        self.dlg = d = p.alloc(0x5400)
        p.put32(d, e["dvt"])
        p.write(d + 0x14, struct.pack("<4i", *ENC_PANEL))
        for off, v in ((0x54, 2), (0x58, 3), (0x5C, 4)):
            p.put32(d + off, v)
        p.put32(d + e["sound_field"], p.alloc(16))
        p.put32(d + e["villagers"], r.story.village.array)
        font = p.alloc(16)
        p.put32(font, p.alloc(16))
        p.put32(d + e["font"], font)
        self.own = {}
        for ident, off in zip((2, 3, 4), e["buttons"]):
            b = p.alloc(0x40)
            p.put32(b, self.vt)
            p.put32(d + off, b)
            self.own[ident] = b
        p.set_reg("esp", STACK_TOP - 0x10000)
        p.set_reg("ecx", d)
        p.run(e["site"], e["site"] + 5)
        return d

    def draw(self):
        self.p.call(self.p.u32(self.p.u32(self.dlg) + 0x30), [], ecx=self.dlg)

    def click(self, ident: int) -> int:
        return self.p.call(self.p.u32(self.p.u32(self.dlg) + 0x0C), [8, ident], ecx=self.dlg) & 0xFF

    def key(self, kind: int, code: int) -> int:
        return self.p.call(self.p.u32(self.p.u32(self.dlg) + 0x08), [kind, code, 0], ecx=self.dlg) & 0xFF

    def result(self) -> str:
        return self.p.cstring(self.dlg + self.e["res"], 0x2710)


@emulated
class TheEncounterDialog(unittest.TestCase):
    """A New Home and The Lost Children: the game's own encounter dialog with three or four answers."""

    def games(self):
        for game in ("vv1", "vv2"):
            if have_stock(game):
                yield game

    def test_four_buttons_at_the_first_draw_stacked_centred_and_padded(self):
        for game in self.games():
            with self.subTest(game=game):
                v = Encounter(game)
                v.open()
                p, e = v.p, v.e
                self.assertNotEqual(p.u32(v.dlg), e["dvt"], "our copy of the dialog's virtual table")
                question = p.cstring(v.dlg + e["q"], 0x2710)
                self.assertIn("finds four doors", question)
                two = Encounter(game)
                two.open(TWO_CIEG)
                q2 = two.p.cstring(two.dlg + e["q"], 0x2710)
                self.assertEqual(two.p.u32(two.dlg), e["dvt"], "two answers: the game's own dialog, untouched")
                # Room: 2 x 1.5 button heights in the font's lines, beyond what two answers need.
                room = -(-(3 * ENC_H) // LINE)
                self.assertGreaterEqual(question.count("\n") - q2.count("\n"), room)
                # Scrolling Popups knows the dialog by the game's own table, and keeps the padded room for our buttons.
                out = p.alloc(4)
                self.assertEqual(p.export("VvfpMultiAnswerGameVtable", v.dlg, out), e["dvt"])
                self.assertEqual(p.u32(out), room * LINE)
                self.assertEqual(p.export("VvfpMultiAnswerGameVtable", v.dlg + 4, out), 0)
                self.assertTrue(set(v.made.values()) <= set(v.deleted),
                                "before the first draw only the measuring button, made and deleted at once")
                self.assertEqual([u for u in v.ui if u[0] == "on"], [], "nothing attached before the first draw")
                v.draw()
                self.assertEqual(sorted(v.made), [5, 6])
                self.assertEqual(v.labels[5], (LABELS[2], 0xFF000000, 0xFF555555, 0xFF555555))
                self.assertEqual(v.labels[6][0], LABELS[3])
                self.assertIn(("on", v.made[5]), v.ui)
                self.assertIn(("on", v.made[6]), v.ui)
                self.assertEqual(v.ui[-1], ("draw",), "then the game draws")
                width, height = ENC_PANEL[2] - ENC_PANEL[0], ENC_PANEL[3] - ENC_PANEL[1]
                ids = (2, 3, 5, 6)
                ys = [v.placed[i][1] for i in ids]
                for i in ids:
                    self.assertEqual(v.placed[i][0], width // 2 - ENC_W // 2, "centred")
                self.assertEqual(ys[-1], height - 2 * ENC_H)
                self.assertEqual([b - a for a, b in zip(ys, ys[1:])], [ENC_H + ENC_H // 2] * 3)
                self.assertGreaterEqual(ys[0], 0)
                n = len(v.made)
                v.draw()
                self.assertEqual(len(v.made), n, "made once")

    def test_every_answer_by_mouse_and_by_key(self):
        for game in self.games():
            for k in range(4):
                for by_key in (False, True):
                    with self.subTest(game=game, answer=k, by_key=by_key):
                        v = Encounter(game)
                        v.open()
                        v.draw()
                        food0, tech0 = stores(v.r)
                        v.ui.clear()
                        if by_key:
                            self.assertEqual(v.key(6, 0x3EB), 0, "Enter takes no answer")
                            self.assertEqual(v.key(5, ord("1") + k), 1)
                        else:
                            self.assertEqual(v.click((2, 3, 5, 6)[k]), 1)
                        self.assertEqual(v.r.state()["choice"], k)
                        self.assertIn(FIRST[k][0], v.result(), "the answer's own page")
                        food1, tech1 = stores(v.r)
                        self.assertEqual((food1 - food0, tech1 - tech0), FIRST[k][1:])
                        self.assertEqual(v.p.read(v.dlg + 0x50, 1), b"\1", "the result is drawn")
                        off = {a for w, a in v.ui if w == "off"}
                        for b in (v.own[2], v.own[3], v.made[5], v.made[6]):
                            self.assertIn(b, off, "every answer off")
                        self.assertIn(("on", v.own[4]), v.ui, "OK on")
                        v.draw()
                        self.assertTrue({v.made[5], v.made[6]} <= set(v.deleted), "ours deleted at the next draw")
                        v.ui.clear()
                        if by_key:
                            self.assertEqual(v.key(6, 0x3EB), 1, "Enter is OK")
                        else:
                            v.click(4)
                        self.assertEqual(stores(v.r), (food1, tech1), "nothing made twice")

    def test_three_answers_after_a_page(self):
        for game in self.games():
            with self.subTest(game=game):
                v = Encounter(game)
                v.open()
                v.draw()
                v.click(3)                               # the blue door: its page, then q2
                self.assertIn("a second room", v.result())
                v.click(4)
                st = v.r.state()
                if not st["armed"]:
                    self.assertEqual(v.p.export("VvfpStoryProbeGraphArmNext", v.r.n), 1)
                v.made.clear()
                d = v.dlg
                p, e = v.p, v.e
                p.put32(d, e["dvt"])
                p.write(d + 0x50, b"\0")
                p.set_reg("esp", STACK_TOP - 0x10000)
                p.set_reg("ecx", d)
                p.run(e["site"], e["site"] + 5)
                v.draw()
                self.assertEqual(sorted(i for i, b in v.made.items() if b not in v.deleted), [5])
                self.assertEqual(v.labels[5][0], LABELS2[2])
                self.assertEqual(v.key(5, ord("4")), 0, "no fourth answer")
                tech0 = stores(v.r)[1]
                self.assertEqual(v.key(5, ord("3")), 1)
                self.assertIn(SECOND[2][0], v.result())
                self.assertEqual(stores(v.r)[1] - tech0, SECOND[2][1])


# ---- Five to seven answers (format version 6, the Isola Grand Event Collection) ------------------------------------

LONG = "Open the carved door of the old seed storehouse"   # a long label, still on the screen


def many_doors(n: int, hide_in_12: bool = False) -> dict:
    """n answers (each its own page and tech); with hide_in_12 the third is shown only in the later three games."""
    choices = []
    nodes = {}
    for k in range(n):
        label = LONG if k == n - 1 else f"Open door number {k + 1}"
        c = {"label": label, "next": f"d{k}"}
        if hide_in_12 and k == 2:
            c["if"] = {"game": [3, 4, 5]}
        choices.append(c)
        nodes[f"d{k}"] = {"text": f"Behind door {k + 1}: tech.", "effects": [{"do": "tech", "amount": 10 * (k + 1)}]}
    nodes["q"] = {"type": "question", "text": "(Name) finds many doors in the cliff.", "choices": choices}
    return {"format": "vvfp-cie-graph", "version": 6, "title": "Many Doors", "games": [1, 2, 3, 4, 5],
            "roles": {"subject": {"kind": "villager"}}, "start": "q", "nodes": nodes}


@functools.lru_cache(maxsize=None)
def many_cieg(n: int, hide_in_12: bool = False) -> bytes:
    return cg.compile_graph(cg.load(many_doors(n, hide_in_12), scrolling=True))


def many_labels(n: int, hide: bool, game: int) -> list[str]:
    return [c["label"] for k, c in enumerate(many_doors(n, hide)["nodes"]["q"]["choices"])
            if not (hide and k == 2 and game < 3)]


@emulated
class FiveToSevenInThePopup(unittest.TestCase):
    """The Secret City, The Tree of Life, New Believers: 5, 6 and 7 answers in ONE column."""

    def games(self):
        for game in ("vv3", "vv4", "vv5"):
            if have_stock(game):
                yield game

    def test_buttons_ids_layout_keys_and_clicks(self):
        for game in self.games():
            for n in (5, 6, 7):
                for k in range(n):
                    for by_key in (False, True):
                        if by_key and k not in (0, n - 1):
                            continue
                        with self.subTest(game=game, answers=n, answer=k, by_key=by_key):
                            v = Popup(game)
                            v.r.reset()
                            v.r.rolls([0] * 40)
                            self.assertIsNone(v.r.queue(many_cieg(n)))
                            v.present()
                            self.assertEqual(sorted(v.buttons), list(range(1, n + 2)), "ids 4 to n + 1")
                            labels = many_labels(n, False, 3)
                            self.assertEqual([v.labels[i] for i in range(4, n + 2)], labels[2:])
                            width, height = PANEL[2] - PANEL[0], PANEL[3] - PANEL[1]
                            ys = [v.placed[i][1] for i in range(2, n + 2)]
                            step = BUTTON_H + BUTTON_H // 4
                            self.assertEqual(ys[-1], height - 2 * BUTTON_H, "the last where the game puts its second")
                            self.assertEqual([b - a for a, b in zip(ys, ys[1:])], [step] * (n - 1),
                                             "1.25 button heights apart, one column")
                            for i in range(2, n + 2):
                                self.assertEqual(v.placed[i][0], (width - BUTTON_W) // 2, "centred")
                            self.assertGreaterEqual(ys[0], 0)
                            self.assertEqual(v.room(), (n - 1) * step - (BUTTON_H + BUTTON_H // 2))
                            tech0 = stores(v.r)[1]
                            if by_key:
                                self.assertEqual(v.key(5, ord("1") + n), 0, "no answer past the last")
                                self.assertEqual(v.key(5, ord("1") + k), 1)
                            else:
                                v.click(2 + k)
                            self.assertEqual(v.r.state()["choice"], k)
                            self.assertIn(f"Behind door {k + 1}", v.text())
                            self.assertEqual(stores(v.r)[1] - tech0, 10 * (k + 1), "its effect with its page")
                            extra = [v.buttons[i] for i in range(4, n + 2)]
                            v.click(1)
                            self.assertTrue(set(extra) <= set(v.deleted), "ours deleted at the OK")


@emulated
class FiveToSevenEveryGame(unittest.TestCase):
    """All five games through the companion's question entry points: the buttons a choice's `if` leaves (the
    buttons close up), each button's choice, its page and effect."""

    def test_every_button_maps_to_its_choice(self):
        for game in GAMES:
            if not have_stock(game):
                continue
            g = int(game[2])
            for n, hide in ((5, False), (6, False), (7, False), (7, True)):
                labels = many_labels(n, hide, g)
                choices = [k for k in range(n) if not (hide and k == 2 and g < 3)]
                for b in range(len(labels)):
                    with self.subTest(game=game, answers=n, hide=hide, button=b):
                        r = Run(game)
                        r.reset()
                        r.rolls([0] * 40)
                        r.log(1)
                        self.assertIsNone(r.queue(many_cieg(n, hide)))
                        q, shown = EveryGame.ask(self, r)
                        self.assertEqual(shown[:5], labels[:5])
                        got = []
                        for k in range(len(labels)):
                            at = r.p.export("VvfpStoryProbeChoiceLabel", r.n, k)
                            got.append(r.p.cstring(at) if at else None)
                        self.assertEqual(got, labels, "every shown label, the long one whole")
                        self.assertEqual(r.p.export("VvfpStoryProbeChoiceLabel", r.n, len(labels)), 0)
                        tech0 = stores(r)[1]
                        result = EveryGame.resolve(self, r, b)
                        choice = choices[b]
                        self.assertIn(f"Behind door {choice + 1}", result)
                        self.assertEqual(stores(r)[1] - tech0, 10 * (choice + 1))
                        n_filed, _now, filed = r.log()
                        self.assertEqual(n_filed, 1)
                        self.assertIn("Choice: " + labels[b], filed)


@emulated
class FiveToSevenEncounter(unittest.TestCase):
    """A New Home and The Lost Children: 5, 6 and 7 answers in the encounter dialog, ids 5 to n + 2, keys 1-7."""

    def test_buttons_layout_and_every_answer(self):
        for game in ("vv1", "vv2"):
            if not have_stock(game):
                continue
            for n in (5, 6, 7):
                for k in range(n):
                    with self.subTest(game=game, answers=n, answer=k):
                        v = Encounter(game)
                        v.open(many_cieg(n))
                        v.draw()
                        self.assertEqual(sorted(v.made), list(range(5, n + 3)))
                        labels = many_labels(n, False, 1)
                        self.assertEqual([v.labels[i][0] for i in range(5, n + 3)], labels[2:])
                        ids = [2, 3] + list(range(5, n + 3))
                        ys = [v.placed[i][1] for i in ids]
                        step = ENC_H + ENC_H // 4
                        height = ENC_PANEL[3] - ENC_PANEL[1]
                        self.assertEqual(ys[-1], height - 2 * ENC_H)
                        self.assertEqual([b - a for a, b in zip(ys, ys[1:])], [step] * (n - 1))
                        self.assertGreaterEqual(ys[0], 0)
                        tech0 = stores(v.r)[1]
                        if k in (0, n - 1):
                            self.assertEqual(v.key(5, ord("1") + n), 0)
                            self.assertEqual(v.key(5, ord("1") + k), 1)
                        else:
                            self.assertEqual(v.click(ids[k]), 1)
                        self.assertEqual(v.r.state()["choice"], k)
                        self.assertIn(f"Behind door {k + 1}", v.result())
                        self.assertEqual(stores(v.r)[1] - tech0, 10 * (k + 1))


# The 800 x 600 render check (risk R2).  The popup is built from the top: its margin (0x3C, the constructor's own,
# native/shared/scroll_popup.h), the text, then the answers stacked from the bottom (the last two button heights
# above the panel's bottom, OK below them).  Button heights: the emulator's stand-ins (42 the later three, 40 the
# first two), at least the game art's tallest answer picture (popup_button1 / main_wide_button2: 32 px).
TOP_MARGIN = 0x3C


def stacked_height(h: int, n: int) -> int:
    """Panel height from the first answer's top to the bottom: 2 h below the last's top, then (n - 1) steps."""
    step = h + h // 4 if n > 4 else h + h // 2
    return 2 * h + (n - 1) * step


@emulated
class SevenFitOnScreen(unittest.TestCase):
    """Seven answers and at least three text lines fit an 800 x 600 screen in every game, with and without
    Scrolling Popups -- measured on the layout the companion makes (ONE column; two columns are not needed)."""

    def test_seven_answers_and_three_lines_fit_800_by_600(self):
        for game in GAMES:
            if not have_stock(game):
                continue
            g = int(game[2])
            h = BUTTON_H if g >= 3 else ENC_H
            layout = cg.GAMES[g].question
            for scrolling in (False, True):
                with self.subTest(game=game, scrolling=scrolling):
                    # The text lines a question page keeps beside seven answers (the companion's pagination).
                    title = 5 if layout.with_title else 0       # the title, then four line breaks
                    room = min(12, layout.lines - title - 3)     # story_graph.inc cg_answer_room for seven
                    text_lines = layout.lines - title - room
                    self.assertGreaterEqual(text_lines, 3, "at least three lines of text")
                    # The popup: margin, the text (with scrolling it scrolls: three lines are the least shown),
                    # then seven answers and OK.
                    shown = 3 if scrolling else text_lines
                    panel = TOP_MARGIN + LINE * (title + shown) + stacked_height(h, 7)
                    self.assertLessEqual(panel, 600, "the whole popup on an 800 x 600 screen")
                    self.assertLessEqual(panel, 768)
                    # And the companion's own layout of the seven, on that panel: inside it, no two meeting, the
                    # first below the text.
                    if g >= 3:
                        v = Popup(game)
                        v.r.reset()
                        v.r.rolls([0] * 40)
                        v.r.p.export("VvfpStoryProbeGraphScroll", 1 if scrolling else 0)
                        self.assertIsNone(v.r.queue(many_cieg(7)))
                        global PANEL
                        keep = PANEL
                        PANEL = (144, 0, 656, panel)
                        try:
                            v.present()
                        finally:
                            PANEL = keep
                        ys = [v.placed[i][1] for i in range(2, 9)]
                    else:
                        v = Encounter(game)
                        global ENC_PANEL
                        keep = ENC_PANEL
                        ENC_PANEL = (100, 0, 700, panel)
                        try:
                            v.open(many_cieg(7))
                            v.draw()
                        finally:
                            ENC_PANEL = keep
                        ys = [v.placed[i][1] for i in [2, 3] + list(range(5, 10))]
                    self.assertGreaterEqual(ys[0], TOP_MARGIN + LINE * (title + shown),
                                            "the first answer below the text")
                    self.assertTrue(all(b - a >= h for a, b in zip(ys, ys[1:])), "no two answers meet")
                    self.assertLessEqual(ys[-1] + h, panel, "inside the panel")


if __name__ == "__main__":
    unittest.main()
