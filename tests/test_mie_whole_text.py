"""More Island Events' own long texts in The Secret City, The Tree of Life and New Believers: ONE scrolling popup,
never pages clicked through with OK (the owner, v1.35.97).

With Scrolling Popups installed, an event's text (its question, or the answer picked and its outcome) is every page
of it, a line apart, however long (mie_one_popup.inc MOP_TEXT_BYTES).  The later three games' dialog field holds
2,000 bytes, so it gets only the text's start, cut at a space (adv_vv345.inc t_op_put, native/shared/one_popup.h
op_long_text_put), and VvfpPopupWholeText gives Scrolling Popups the whole text for it.

A text longer than 2,000 bytes is made here the way a translation makes one: "VVFP Translations.dll" is stood in for
and gives each of the event's sentences-long pieces six times over.  Run in the emulator (tests/story_emulator.py) on
the stock executables with the shipped DLL; the live game is NOT exercised.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import test_aspiring_adventurer as aa  # noqa: E402
import test_one_popup_more_island_events as top  # noqa: E402

NEEDS = top.NEEDS
FIELD = 2000
FAKE_TR = 0x72000000
LATER = (3, 4, 5)
TRANSLATED: list = []                        # each long piece the stand-in made longer


def with_long_translation(v, most: int = 6) -> None:
    """"VVFP Translations.dll" stood in for: every piece of more than 80 bytes comes back most times over (as much
    as its buffer holds whole), every shorter one (a label, a name) as it is."""
    p = v.p
    module_w, proc = p.api_handlers.get("GetModuleHandleW"), p.api_handlers["GetProcAddress"]
    key_fn, text_fn = p.alloc(16), p.alloc(16)

    def key(pr):
        return pr.arg(1), 12                        # vvfp_tr: the English as it is

    def text(pr):
        filled, out, cap = pr.cstring(pr.arg(2)).encode("latin-1"), pr.arg(3), pr.arg(4)
        if len(filled) <= 80:
            return 0, 20
        times = min(most, (cap - 1) // (len(filled) + 1))
        if times < 2:
            return 0, 20
        pr.write(out, b" ".join([filled] * times) + b"\0")
        TRANSLATED.append(len(filled))
        return 1, 20

    def module2(pr):
        if pr.arg(0) and pr.wstring(pr.arg(0)) == "VVFP Translations.dll":
            return FAKE_TR, 4
        return module_w(pr) if module_w is not None else ((0x400000 if pr.arg(0) == 0 else 0), 4)

    def proc2(pr):
        if pr.arg(0) == FAKE_TR:
            return {"VvfpTranslateKey": key_fn, "VvfpTranslateKeyText": text_fn}.get(pr.cstring(pr.arg(1)), 0), 8
        return proc(pr)
    p.stub(key_fn, key)
    p.stub(text_fn, text)
    p.api_handlers["GetModuleHandleW"] = module2
    p.api_handlers["GetProcAddress"] = proc2


def whole_of(v) -> str | None:
    """VvfpPopupWholeText for the dialog's field as it is now."""
    at = v.p.export("VvfpPopupWholeText", v.dlg + 0x58)
    return v.p.cstring(at) if at else None


@NEEDS
class OneScrollingPopup(unittest.TestCase):

    def check_shown(self, v, op, whole: str) -> None:
        """The field holds the text's start (under 2,000 bytes, cut at a space); the whole is VvfpPopupWholeText's."""
        field = op.text()
        self.assertGreater(len(whole), FIELD, "a text longer than the field")
        self.assertLess(len(field), FIELD, "the field never takes 2,000 bytes or more")
        self.assertTrue(whole.startswith(field), "the field is the text's start")
        self.assertIn(whole[len(field)], " \n", "cut at a space or a line break")
        self.assertEqual(whole_of(v), whole, "Scrolling Popups is given the whole text: nothing cut, nothing paged")

    def check_text(self, v, op, whole: str) -> None:
        """Whole in the field when it fits, else its start with the whole for Scrolling Popups."""
        if len(whole) > FIELD - 1:
            self.check_shown(v, op, whole)
        else:
            self.assertEqual(op.text(), whole)
            self.assertIsNone(whole_of(v), "a text that fits: the field is the whole")

    def test_the_aspiring_adventurer(self) -> None:
        for game in LATER:
            for choice in (0, 1):
                with self.subTest(game=game, choice=choice):
                    v, calls = top.adventurer(game)
                    with_long_translation(v)
                    self.assertTrue(top.open_adventurer(v, game, aa.rolls(game=game, find=1, end=0)))
                    op = top.OnePopup(v, game)
                    question = v.pages(0)
                    self.assertGreaterEqual(len(question), 2, "the question is more than one page long")
                    self.check_shown(v, op, "\n".join(question))
                    ours, labels, _ = op.rows()
                    self.assertEqual((ours, labels), (1, top.ADV_LABELS),
                                     "the answers at once: no OK page before them")
                    self.assertEqual(op.pick(choice), 1)
                    outcome = top.ADV_LABELS[choice] + "\n\n" + "\n".join(v.pages(1 + choice))
                    if choice == 0:
                        self.assertGreater(len(outcome), FIELD, "the meat's outcome is longer than the field")
                    self.check_text(v, op, outcome)
                    self.assertEqual(op.rows()[:2], (1, []), "OK now: no answer")
                    self.assertEqual(len(top.writes(calls)), 1, "the effects and the log's one entry, at once")
                    v.ui.clear()
                    op.ok()
                    self.assertTrue(v.closed(), "the first OK ends the event: no more pages")
                    self.assertEqual(len(top.writes(calls)), 1)
                    self.assertIsNone(whole_of(v), "over: the field is no longer ours")

    def test_the_troubling_signs(self) -> None:
        labels = [top.tts.LABELS[g] for g in top.tts.GROUPS]
        for answer in (0, 3):
            with self.subTest(answer=answer):
                v, calls = top.ts_open()
                with_long_translation(v, 4)
                call = v.p.call             # the pages of a long opening take more than a call's usual budget
                v.p.call = lambda address, args=(), **kw: call(address, args, **{**kw, "limit": 50_000_000})
                self.assertTrue(v.open())
                top.constructor_text(v, 3, v.obj)
                op = top.OnePopup(v, 3)
                opening = v.ts_pages(0)
                self.assertGreaterEqual(len(opening), 2, "the opening is more than one page long")
                self.check_shown(v, op, "\n".join(opening))
                self.assertEqual(op.rows()[1], labels, "the four answers at once")
                self.assertEqual(op.pick(answer), 1)
                outcome = v.ts_pages(1 + answer)
                self.check_text(v, op, labels[answer] + "\n\n" + "\n".join(outcome))
                self.assertEqual(op.rows()[1], [])
                self.assertEqual(len(top.writes(calls)), 1)
                v.ui.clear()
                op.ok()
                self.assertTrue(v.closed(), "the first OK ends the event")

    def test_a_short_text_is_the_field(self) -> None:
        for game in LATER:
            with self.subTest(game=game):
                v, _ = top.adventurer(game)
                self.assertTrue(top.open_adventurer(v, game, aa.rolls(game=game, find=1, end=0)))
                op = top.OnePopup(v, game)
                self.assertEqual(op.text(), "\n".join(v.pages(0)))
                self.assertIsNone(whole_of(v), "a text that fits: NULL, the field drawn as it is")

    def test_never_for_another_text(self) -> None:
        v, _ = top.adventurer(4)
        with_long_translation(v)
        self.assertTrue(top.open_adventurer(v, 4, aa.rolls(game=4, find=1, end=0)))
        p = v.p
        field = p.cstring(v.dlg + 0x58)
        other = p.alloc(FIELD + 16)
        for text in (field[:-1], field + "x", "x" + field[1:], ""):
            p.write(other, text.encode("latin-1") + b"\0")
            self.assertEqual(p.export("VvfpPopupWholeText", other), 0, repr(text[:20]))
        self.assertEqual(p.export("VvfpPopupWholeText", 0), 0)


if __name__ == "__main__":
    unittest.main()
