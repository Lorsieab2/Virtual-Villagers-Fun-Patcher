"""ONE popup per island event in "VVFP More Island Events.dll" (the owner, 2026-11-14; native/shared/one_popup.h).

With Scrolling Popups installed ("VVFP Scrolling Popups.dll" stood in for: VvfpScrollingPopupsInstalled), every More
Island Events question event runs whole in the popup the game builds for it (mie_one_popup.inc):
  * the question's text is ONE text in the dialog's own text field (A New Home / The Lost Children: the question
    field +0x74 / +0x7C, after the title line and the villager's picture lines; the later three: +0x58), with no
    padding for buttons;
  * its answers are VvfpOnePopupRows' rows, the labels as written (never upper-cased), OK's room below them;
  * an answer by row (VvfpOnePopupPick) or by key (1 to N, the dialog's own keyboard handler) writes its outcome into
    the same dialog's text field, with its effects made then, once; a second question (The Cave Explorers) asks
    in the same popup, its rows after its text;
  * that text starts with the answer picked, its row's words on a line of their own and a blank line
    (docs/event-collection/cie-v6-binary.md 19: "Go investigate!\n\n..."), never in the log (its "Choice:" line);
  * the game's own OK (a click, or Enter) then ends it: the game's close, nothing made again, ONE Island Events log
    entry ("VVFP Island Events.dll" stood in for);
  * the game's own two answer buttons are never shown (VV1 / VV2: taken off the dialog at its first draw; the later
    three: hidden);
  * without Scrolling Popups the popup is the paged one of before (VvfpOnePopupRows 0, the game's own buttons).

Run in the emulator (tests/story_emulator.py) on the stock executables with the shipped DLL, in all five games for
The Aspiring Adventurer (two answers), The Troubling Signs (The Secret City) and The Mysterious Mask (The Tree of
Life) for four answers, and The Cave Explorers (A New Home) for a second question in the same popup.  More Island
Events has no four-answer event in A New Home, The Lost Children or New Believers.  The live game is NOT exercised.
"""
from __future__ import annotations

import re
import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import test_aspiring_adventurer as aa  # noqa: E402
from test_more_island_events_pages import fake_log  # noqa: E402

NEEDS = unittest.skipUnless(aa.HAVE_EMULATOR and aa.HAVE_STOCK and aa.DLL.is_file(),
                            "needs unicorn, pefile, the stock executables and the built DLL")
if aa.HAVE_EMULATOR:
    from story_emulator import STACK_TOP
    import test_cave_explorers as tc
    import test_mysterious_mask as tm
    import test_troubling_signs as tts

FAKE_SP = 0x0EB00000
OP_SIZE = 12 + 7 * 128                     # sizeof(op_rows)
DIALOG_VTABLE = {1: 0x459578, 2: 0x476714, 3: 0x47F28C, 4: 0x48D2C8, 5: 0x4984D8}
DRAW = {1: 0x4187E0, 2: 0x41F430}
BODY_ID = {3: 0x3A9, 4: 0x361, 5: 0x3B5}
QUESTION_FIELD = {1: 0x74, 2: 0x7C}
OK_ID = {1: 4, 2: 4, 3: 1, 4: 1, 5: 1}
ADV_LABELS = ["Go investigate!", "Stay on the safe path"]
BUTTON_H = 32


def norm(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def with_scrolling(v) -> None:
    """"VVFP Scrolling Popups.dll" stood in for as installed on village `v` (asked when the event is composed)."""
    p = v.p
    module, proc = p.api_handlers["GetModuleHandleA"], p.api_handlers["GetProcAddress"]
    installed = p.alloc(16)

    def module2(pr):
        name = pr.cstring(pr.arg(0)) if pr.arg(0) else ""
        return (FAKE_SP, 4) if name == "VVFP Scrolling Popups.dll" else module(pr)

    def proc2(pr):
        if pr.arg(0) == FAKE_SP:
            return (installed if pr.cstring(pr.arg(1)) == "VvfpScrollingPopupsInstalled" else 0), 8
        return proc(pr)
    p.api_handlers["GetModuleHandleA"] = module2
    p.api_handlers["GetProcAddress"] = proc2
    p.stub(installed, lambda pr: (1, 0))


def fake_buttons(v, count: int) -> list[int]:
    """`count` button objects of a stand-in class: +0x0C its width, +0x10 its height (BUTTON_H)."""
    p = v.p
    code = p.alloc(48)
    p.write(code, b"\xC3" * 48)
    vt = p.alloc(32)
    for k in range(6):
        p.put32(vt + 4 * k, code + 8 * k)
    p.stub(code, lambda pr: (0, 4))
    p.stub(code + 8, lambda pr: (0, 8))
    p.stub(code + 24, lambda pr: (390, 0))
    p.stub(code + 32, lambda pr: (BUTTON_H, 0))
    out = []
    for _ in range(count):
        b = p.alloc(0x40)
        p.put32(b, vt)
        out.append(b)
    return out


class OnePopup:
    """The popup of village `v` (its dialog v.dlg) as Scrolling Popups and the player drive it."""

    def __init__(self, v, game: int):
        self.v, self.p, self.game = v, v.p, game

    def rows(self) -> tuple[int, list[str], int]:
        p = self.p
        out = p.alloc(OP_SIZE)
        p.write(out, b"\0" * OP_SIZE)
        p.put32(out, OP_SIZE)
        ours = p.export("VvfpOnePopupRows", self.v.dlg, out)
        n = p.u32(out + 4)
        labels = [p.cstring(out + 12 + 128 * k, 128) for k in range(n if ours and n <= 7 else 0)]
        return ours, labels, p.u32(out + 8)

    def text(self) -> str:
        if self.game <= 2:
            return self.p.cstring(self.v.dlg + QUESTION_FIELD[self.game], 9000)
        return self.p.cstring(self.v.dlg + 0x58, 2000)

    def body(self) -> str:
        """The text without A New Home's / The Lost Children's title line and picture lines, as one line."""
        text = self.text()
        if self.game <= 2:
            assert text.startswith(self.title + "\n\n\n\n\n\n"), text[:80]
            text = text[len(self.title):]
        return norm(text)

    def words(self) -> str:
        """The text's own words, line breaks kept: after A New Home's / The Lost Children's title and picture lines."""
        text = self.text()
        if self.game <= 2:
            assert text.startswith(self.title + "\n\n\n\n\n\n"), text[:80]
            text = text[len(self.title):].lstrip("\n")
        return text

    def draw(self) -> None:
        if self.game <= 2:
            self.p.call(self.p.u32(self.p.u32(self.v.dlg) + 0x30), [], ecx=self.v.dlg)

    def pick(self, k: int, by_key: bool = False) -> int:
        p = self.p
        if by_key:
            return p.call(p.u32(p.u32(self.v.dlg) + 0x08), [5, ord("1") + k, 0], ecx=self.v.dlg) & 0xFF
        return p.export("VvfpOnePopupPick", self.v.dlg, k)

    def ok(self, by_key: bool = False) -> None:
        p = self.p
        if by_key:
            p.call(p.u32(p.u32(self.v.dlg) + 0x08), [6, 0x3EB, 0], ecx=self.v.dlg)
        else:
            p.call(p.u32(p.u32(self.v.dlg) + 0x0C), [8, OK_ID[self.game]], ecx=self.v.dlg)

    def answer_click(self, k: int) -> None:
        """A click from the game's own answer k (as if it were on screen): never taken in one popup."""
        ident = (2, 3)[k] if self.game <= 2 else (2, 3)[k]
        self.p.call(self.p.u32(self.p.u32(self.v.dlg) + 0x0C), [8, ident], ecx=self.v.dlg)

    title = "The Aspiring Adventurer"


def open_adventurer(v, game: int, rolls: list[int]) -> bool:
    """The Aspiring Adventurer due, drawn and its popup built through the game's own sites, the dialog carrying the
    game's own virtual table as its constructor leaves it (Village.begin otherwise)."""
    p = v.p
    v.ui.clear()
    v.due = v.PICK
    if game in DRAW:
        p.stub(DRAW[game], lambda pr: (0, 0))
    if game == 1:
        v.dlg = d = p.alloc(0x6000)
        a, b, ok = fake_buttons(v, 3)
        p.put32(d, DIALOG_VTABLE[1])
        p.put32(d + 0x50A4, v.world)
        p.put32(d + 0x50A8, v.base)
        for o, x in ((0x54, 2), (0x58, 3), (0x5C, 4), (0x50BC, a), (0x50C0, b), (0x50C4, ok)):
            p.put32(d + o, x)
        v.rolls = list(rolls)
        p.call(0x4189E0, [], ecx=d)
        if p.u32(d + 0x5094) != 0x7F4B1A2E:
            return False
        esp = STACK_TOP - 0x3000 - 4
        p.put32(esp, b)
        p.set_reg("esp", esp)
        p.set_reg("ecx", d)
        p.run(0x41A87C, 0x41A881)
        v.answer_buttons = (a, b)
        return True
    if game == 2:
        v.dlg = d = p.alloc(0x6000)
        a, b, ok = fake_buttons(v, 3)
        p.put32(d, DIALOG_VTABLE[2])
        p.put32(d + 0x50AC, v.world)
        p.put32(d + 0x50B0, v.base)
        for o, x in ((0x54, 2), (0x58, 3), (0x5C, 4), (0x50C8, a), (0x50CC, b), (0x50D0, ok)):
            p.put32(d + o, x)
        v.rolls = list(rolls)
        if p.call(0x41F780, [], ecx=d) & 0xFF == 0 or p.u32(d + 0x509C) != 21:
            return False
        p.stub(0x422380, lambda pr: (pr.reg("ecx"), 0))
        p.set_reg("esp", STACK_TOP - 0x3000)
        p.set_reg("ecx", d)
        p.run(0x42F1A3, 0x42F1A8)
        v.answer_buttons = (a, b)
        return True
    t = v.t
    if not v.listed():
        return False
    v.dlg = d = p.alloc(0x1000)
    a, b, ok = fake_buttons(v, 3)
    p.put32(d, DIALOG_VTABLE[game])
    for o, x in ((0x85C, a), (0x860, b), (0x864, ok)):
        p.put32(d + o, x)
    v.answer_buttons = (a, b)
    v.rolls = list(rolls)
    obj = v.obj
    p.call(p.u32(p.u32(obj) + 8), ecx=obj)          # the title, as the constructor asks it first

    def ctor(pr):
        pr.put32(pr.reg("ecx") + 0x50, pr.arg(0))
        return pr.reg("ecx"), 4
    p.stub(t["ctor"], ctor)
    esp = STACK_TOP - 0x3000 - 4
    p.put32(esp, obj)
    p.set_reg("esp", esp)
    p.set_reg("ecx", d)
    p.run(*t["site"])
    constructor_text(v, game, obj)
    return True


def constructor_text(v, game: int, obj: int) -> None:
    """The later three games: the question's text the constructor copies into the dialog's +0x58 (the object's
    +0x0C, its string looked up by its id), as the game's own constructor (stood in for) does."""
    p = v.p
    ident = p.call(p.u32(p.u32(obj) + 0x0C), ecx=obj)
    entry = p.u32(aa.TABLES[game]["strings"] + 4 * ident)
    p.write(v.dlg + 0x58, p.read(p.u32(entry + 8), 2000).split(b"\0")[0][:1999] + b"\0")


def adventurer(game: int, scrolling: bool = True):
    v = aa.Village(game)
    v.villager(0, "Ana", True)
    v.villager(1, "Ben")
    calls = fake_log(v)
    if scrolling:
        with_scrolling(v)
    return v, calls


def writes(calls) -> list[tuple]:
    return [c for c in calls if c[0] == "write"]


@NEEDS
class TwoAnswers(unittest.TestCase):
    """The Aspiring Adventurer in all five games."""

    def test_text_rows_pick_outcome_ok(self) -> None:
        for game in aa.GAMES:
            for choice in (0, 1):
                for by_key in (False, True):
                    with self.subTest(game=game, choice=choice, by_key=by_key):
                        v, calls = adventurer(game)
                        roll = aa.rolls(game=game, find=1, end=0)          # A1: the meat, a food award
                        self.assertTrue(open_adventurer(v, game, roll))
                        op = OnePopup(v, game)
                        op.draw()
                        ours, labels, reserve = op.rows()
                        self.assertEqual(ours, 1, "its own dialog: More Island Events answers")
                        self.assertEqual(labels, ADV_LABELS, "the labels as written, never upper-cased")
                        self.assertGreater(reserve, 0, "room for OK below the content")
                        st = v.state()
                        self.assertEqual(st[15], 1, "with Scrolling Popups the question is one page")
                        self.assertEqual(op.body(), norm(" ".join(v.pages(0))), "the whole question, one text")
                        self.assertNotIn("\n \n", op.text(), "no padding for buttons")
                        before = v.stores()
                        self.assertEqual(writes(calls), [])
                        self.assertEqual(op.pick(choice, by_key), 1)
                        result = v.pages(1 + choice)
                        self.assertTrue(op.words().startswith(ADV_LABELS[choice] + "\n\n"), op.text()[:200])
                        self.assertEqual(op.body(), norm(" ".join([ADV_LABELS[choice]] + result)),
                                         "the answer picked, then the outcome, in the same field")
                        self.assertEqual(op.rows()[:2], (1, []), "OK now: no answer")
                        gained = tuple(a - b for a, b in zip(v.stores(), before))
                        if choice == 0:
                            self.assertGreater(gained[0], 0, "A1's award with its text")
                        else:
                            self.assertEqual(gained, (0, 0), "home safe: nothing")
                        self.assertEqual(len(writes(calls)), 1, "the log's one entry, with the outcome")
                        self.assertEqual(op.pick(0), 0, "answered once")
                        after = v.stores()
                        v.ui.clear()
                        op.ok(by_key)
                        self.assertTrue(v.closed(), "the game's OK ends it")
                        self.assertEqual(v.stores(), after, "nothing made again")
                        self.assertEqual(len(writes(calls)), 1, "ONE Island Events log entry")
                        entry = writes(calls)[0][2]
                        self.assertTrue(entry.startswith("  Event: The Aspiring Adventurer\n  Choice: "
                                                         + ADV_LABELS[choice] + "\n"), entry)
                        self.assertEqual(entry.count("  Choice: "), 1)
                        self.assertNotIn(ADV_LABELS[choice] + "\n\n", entry, "the label line is never logged")
                        self.assertEqual(op.rows()[0], 0, "over: the popup is no longer ours")

    def test_the_games_own_answers_are_never_taken(self) -> None:
        for game in aa.GAMES:
            with self.subTest(game=game):
                v, calls = adventurer(game)
                self.assertTrue(open_adventurer(v, game, aa.rolls(game=game, hero=0, find=1, end=0)))
                op = OnePopup(v, game)
                op.draw()
                question = op.text()
                before = v.stores()
                op.answer_click(0)
                self.assertEqual(op.text(), question)
                self.assertEqual(v.stores(), before)
                self.assertEqual(writes(calls), [])
                self.assertEqual(len(op.rows()[1]), 2, "still asking")
                a, b = v.answer_buttons
                if game <= 2:
                    removed = [x for what, x in v.ui if what == "remove"]
                    self.assertIn(a, removed)
                    self.assertIn(b, removed)
                else:
                    hidden = [x for what, x in v.ui if what == "hide"]
                    self.assertIn(a, hidden)
                    self.assertIn(b, hidden)
                op.ok()                                       # asking: OK is not on screen, nothing happens
                self.assertFalse(v.closed())
                self.assertEqual(len(op.rows()[1]), 2)

    def test_both_companions_answer_only_for_their_own(self) -> None:
        for game in aa.GAMES:
            with self.subTest(game=game):
                v, _ = adventurer(game)
                self.assertTrue(open_adventurer(v, game, aa.rolls(game=game, find=1, end=0)))
                p = v.p
                other = p.alloc(0x6000)
                out = p.alloc(OP_SIZE)
                p.put32(out, OP_SIZE)
                self.assertEqual(p.export("VvfpOnePopupRows", other, out), 0)
                self.assertEqual(p.export("VvfpOnePopupPick", other, 0), 0)

    def test_without_scrolling_popups_as_before(self) -> None:
        for game in aa.GAMES:
            with self.subTest(game=game):
                v, calls = adventurer(game, scrolling=False)
                paged = v.play(aa.rolls(game=game, find=1, end=0), 1)
                self.assertTrue(v.closed_at_end)
                self.assertGreaterEqual(len(paged), 2)
                out = v.p.alloc(OP_SIZE)
                v.p.put32(out, OP_SIZE)
                self.assertEqual(v.p.export("VvfpOnePopupRows", v.dlg, out), 0, "no rows: the game's buttons")
                self.assertEqual(len(writes(calls)), 1)


def ts_open(scrolling: bool = True):
    v = tts.standard()
    calls = fake_log(v)
    if scrolling:
        with_scrolling(v)
    return v, calls


@NEEDS
class FourAnswers(unittest.TestCase):
    """The Troubling Signs (The Secret City) and The Mysterious Mask (The Tree of Life)."""

    def check_four(self, v, calls, game, labels, question_pages, outcome_pages, answer, by_key, obj, title):
        constructor_text(v, game, obj)
        op = OnePopup(v, game)
        ours, shown, reserve = op.rows()
        self.assertEqual(ours, 1)
        self.assertEqual(shown, labels, "the four labels as written")
        self.assertGreater(reserve, 0)
        self.assertEqual(op.body(), norm(" ".join(question_pages)), "the whole question, one text")
        before = v.snapshot()[0]
        self.assertEqual(op.pick(answer, by_key), 1)
        self.assertTrue(op.words().startswith(labels[answer] + "\n\n"), op.text()[:200])
        self.assertEqual(op.body(), norm(" ".join([labels[answer]] + outcome_pages())),
                         "the answer picked, then the outcome, in the same field")
        self.assertEqual(op.rows()[1], [])
        self.assertEqual(len(writes(calls)), 1, "its effects and the log's one entry with the outcome")
        after = v.snapshot()
        v.ui.clear()
        op.ok(by_key)
        self.assertTrue(v.closed())
        self.assertEqual(v.snapshot(), after, "nothing made again")
        self.assertEqual(len(writes(calls)), 1)
        entry = writes(calls)[0][2]
        self.assertTrue(entry.startswith(f"  Event: {title}\n  Choice: {labels[answer]}\n"), entry)
        self.assertNotIn(labels[answer] + "\n\n", entry, "the label line is never logged")
        return before

    def test_the_troubling_signs(self) -> None:
        labels = [tts.LABELS[g] for g in tts.GROUPS]
        for answer in range(4):
            for by_key in (False, True):
                with self.subTest(answer=answer, by_key=by_key):
                    v, calls = ts_open()
                    self.assertTrue(v.open())
                    self.assertEqual(v.ts_state()[18], 1, "with Scrolling Popups the opening is one page")
                    self.check_four(v, calls, 3, labels, v.ts_pages(0), lambda: v.ts_pages(1 + answer), answer,
                                    by_key, v.obj, "The Troubling Signs")

    def test_the_mysterious_mask(self) -> None:
        for answer in range(4):
            for by_key in (False, True):
                with self.subTest(answer=answer, by_key=by_key):
                    v = tm.standard()
                    calls = fake_log(v)
                    with_scrolling(v)
                    self.assertTrue(v.open(tm.mask_rolls()))
                    self.check_four(v, calls, 4, tm.LABELS, v.mk_pages(0),
                                    lambda: v.mk_pages(1 + v.mk_state()[15]), answer, by_key, v.obj,
                                    "The Mysterious Mask")

    def test_without_scrolling_popups_the_four_buttons(self) -> None:
        v, calls = ts_open(scrolling=False)
        self.assertTrue(v.open())
        out = v.p.alloc(OP_SIZE)
        v.p.put32(out, OP_SIZE)
        self.assertEqual(v.p.export("VvfpOnePopupRows", v.dlg, out), 0)
        v.play(2)
        self.assertEqual(len(writes(calls)), 1)


def cave_pages(v, which: int) -> list[str]:
    out, k = [], 0
    while True:
        at = v.p.export("VvfpCaveExplorersPage", which, k)
        if not at:
            return out
        out.append(v.p.cstring(at, 4000))
        k += 1


@NEEDS
class ASecondQuestion(unittest.TestCase):
    """The Cave Explorers (A New Home): an answer that leads to another question asks it in the same popup."""

    def test_the_cave_explorers(self) -> None:
        v = tc.CaveVillage()
        v.villager(0, "Ana", True, years=20)
        v.villager(1, "Ben", False, years=24)
        calls = fake_log(v)
        with_scrolling(v)
        v.PICK = tc.CaveVillage.PICK
        self.assertTrue(open_adventurer(v, 1, tc.cave_rolls(scream=False, find="FIND_COINS")))
        op = OnePopup(v, 1)
        op.title = "The Cave Explorers"
        op.draw()
        self.assertEqual(op.body(), norm(" ".join(cave_pages(v, 0))))
        _, labels, _ = op.rows()
        self.assertEqual(len(labels), 2)
        self.assertEqual(labels[0], "Explore the Cave")
        food0 = v.stores()
        self.assertEqual(op.pick(0), 1)
        self.assertTrue(op.words().startswith("Explore the Cave\n\n"), op.text()[:200])
        _, labels2, _ = op.rows()
        self.assertEqual(len(labels2), 2, "the next question's answers after its text")
        self.assertNotEqual(labels2, labels)
        self.assertEqual(v.stores(), food0, "no effect before the ending")
        self.assertEqual(writes(calls), [])
        self.assertEqual(op.pick(0, by_key=True), 1)
        self.assertTrue(op.words().startswith(labels2[0] + "\n\n"), op.text()[:200])
        self.assertEqual(op.rows()[1], [], "the ending: OK")
        self.assertEqual(len(writes(calls)), 1)
        entry = writes(calls)[0][2]
        self.assertEqual(entry.count("  Choice: "), 2, entry)
        self.assertIn("  Choice: Explore the Cave\n", entry)
        self.assertNotIn("Explore the Cave\n\n", entry, "the label line is never logged")
        changed = v.stores()
        v.ui.clear()
        op.ok()
        self.assertTrue(v.closed())
        self.assertEqual(v.stores(), changed)
        self.assertEqual(len(writes(calls)), 1)


if __name__ == "__main__":
    unittest.main()
