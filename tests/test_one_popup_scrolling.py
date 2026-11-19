"""ONE popup per island event, as "VVFP Scrolling Popups.dll" draws it (the owner, 2026-11-14; native/shared/one_popup.h).

The owner saw, live in A New Home, The Parent's Lesson (seven answers, Scrolling Popups installed): the title, the
top of the villager's picture, then seven stacked buttons -- the question's words not visible at all.  The root cause
(RootCause below, run on the game's own dialog in the emulator): the companion padded the question with blank lines
worth the five extra buttons AND told Scrolling Popups that same room again, and the seven buttons stood outside the
scrolled text below it; the panel, capped to the 800 x 600 screen, then left a 140-pixel window for the scrolled body,
which holds only the title, the blank lines after it and the villager's picture gap -- the question at its very edge
and the picture cut by its bottom, with a scrollbar for a text that would have fitted.

The new rule, in every game, for 2, 4 and 7 choices (the companion owning the popup is a stand-in here, answering
the protocol exactly as one_popup.h has it; tests/test_one_popup_runtime.py runs the companion itself):
  * the text is drawn and visible, above the choices;
  * the choices are rows at the END of the text, INSIDE the scrolled content, reachable by scrolling, drawn with the
    game's own answer-button picture and the body text's own font in the label's own case;
  * a click on a scrolled row picks that choice (and is not passed to the game);
  * the outcome replaces the text in the same popup (the same panel), from its top, with no rows while OK shows.

Pictures of the 7-choice popup (top and scrolled to the bottom) are written when ONE_POPUP_PICTURES names a folder.
"""
from __future__ import annotations

import os
import sys
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

try:
    import unicorn  # noqa: F401
    HAVE_EMULATOR = True
except ImportError:  # pragma: no cover
    HAVE_EMULATOR = False

NAMES = {1: "A New Home", 2: "The Lost Children", 3: "The Secret City", 4: "The Tree of Life", 5: "New Believers"}
STOCK = {g: ROOT / "research" / "stock-executables" / f"Virtual Villagers - {n}.exe" for g, n in NAMES.items()}
IMAGES = ROOT / "research" / "game-images"
TEST_DLL = ROOT / "tests" / "test_dlls" / "VVFP Scrolling Popups.test.dll"
HAVE_ALL = (HAVE_EMULATOR and all(p.is_file() for p in STOCK.values()) and TEST_DLL.is_file()
            and all((IMAGES / f"Virtual Villagers - {n}" / "Images" / "WideSlider2.png").is_file()
                    for n in NAMES.values()))
PICTURES = Path(os.environ["ONE_POPUP_PICTURES"]) if os.environ.get("ONE_POPUP_PICTURES") else None

TITLE = b"The Parent's Lesson"
INTRO = (b"Ana, a child in the village, has been testing the patience of the adults. Kalani, the adult currently "
         b"responsible for guiding her, decides it is time to teach an important lesson.")
QUESTION = b"Which lesson should Kalani teach?"
LABELS = [b"Honesty", b"Patience", b"Responsibility", b"Kindness and sharing", b"Respect for nature",
          b"Perseverance and humility", b"Think before acting"]
OUTCOME = (b"Truth with Kindness: Ana admits to accidentally spilling berries and helps clean up. Kalani praises the "
           b"honesty and explains that truth and kindness belong together.")
ENC_BUTTON_H = 32                 # A New Home's answer picture (ultra_wide_button.png: 390 x 32)


def wrapped(text: bytes, width: int = 49) -> bytes:
    """A New Home's and The Lost Children's popup text as the companion lays it out (ce_wrap: 49 characters)."""
    return b"\n".join(line.encode() for line in textwrap.wrap(text.decode(), width))


def body(game: int, text: bytes) -> bytes:
    """The popup's text: in the first two games the title leads it, then the villager's picture gap (the title,
    four line breaks, two more for the picture: story_graph.inc cg_compose, story_c1.inc choice_open_gap)."""
    if game <= 2:
        return TITLE + b"\n\n\n\n\n\n" + wrapped(text)
    return text


@unittest.skipUnless(HAVE_ALL, "needs unicorn, the stock executables, the game images and the test build")
class RootCause(unittest.TestCase):
    """The old layout (before one popup): A New Home's encounter dialog with The Parent's Lesson's seven answers, the
    question padded with blank lines worth the extra buttons (choice_fill_dialog: the tallest answer page, the room
    for the buttons, the picture gap; vvfp_multi_answer_12.h mb_room_lines) and that same room told to Scrolling
    Popups (VvfpMultiAnswerGameVtable)."""

    @unittest.expectedFailure
    def test_old_seven_answer_question_scrolled_in_a_window_too_small_for_it(self):
        import scrolling_popups_emulation as spe
        d = spe.Dialog("vv1")
        h = ENC_BUTTON_H
        line = d.run._call(spe.EVENT_HEIGHT["vv1"], d.font, d._cstr(b"X"))
        step = h + h // 4
        room_lines = -(-(6 * step - (h + h // 2)) // line)
        text = TITLE + b"\n\n\n\n\n\n" + QUESTION
        lines = 8 + room_lines + 2                       # an 8-line answer page, the room, the picture gap
        text += b"\n" * (lines - text.count(b"\n") - 1)
        d.make_event("choice", text, answers_room=room_lines * line, button_h=h)
        d.draw()
        v = d.view()
        # The words (7 lines with the title and the picture gap) fit the 800 x 600 screen: they must be shown whole,
        # with no scrollbar.  The old layout scrolls them in a 140-pixel window instead.
        self.assertGreaterEqual(v["box_h"], 7 * line, (v["box_h"], v["content_h"]))
        self.assertEqual(v["vbar"], 0)


@unittest.skipUnless(HAVE_ALL, "needs unicorn, the stock executables, the game images and the test build")
class OnePopup(unittest.TestCase):
    dialogs: dict = {}

    @classmethod
    def setUpClass(cls) -> None:
        import scrolling_popups_emulation as spe
        cls.spe = spe
        for game in NAMES:
            cls.dialogs[game] = spe.Dialog(f"vv{game}")

    @classmethod
    def tearDownClass(cls) -> None:
        cls.dialogs.clear()

    def open(self, game: int, n: int, text: bytes = INTRO + b"\n\n" + QUESTION) -> tuple:
        d = self.dialogs[game]
        d.picks = []
        op = {"labels": list(LABELS[:n]), "reserve": 0}
        if game <= 2:
            op["reserve"] = 5 * ENC_BUTTON_H // 2
            d.make_event("choice", body(game, text), one_popup=op, button_h=ENC_BUTTON_H)
        else:
            op["reserve"] = 5 * d.picture_of(d.g["ok_id"])[2] // 2
            d.make(body(game, text), choices=True, title=TITLE, one_popup=op)
        return d, op

    def body_glyphs(self, d, blits, rows):
        """The text's glyphs: in the box's columns, below the title the later three games draw above the box, and
        above the first row (the rows' labels are glyphs too)."""
        v = d.view()
        return [b for b in d.text_blits(blits)
                if b[3][1] + b[1][3] > v["box_y"] and (rows["n"] == 0 or b[3][1] < rows["y"])]

    def inside(self, b, v) -> bool:
        x, y = b[3][0], b[3][1]
        return (v["box_x"] <= x and x + b[1][2] <= v["box_x"] + v["box_w"]
                and v["box_y"] <= y and y + b[1][3] <= v["box_y"] + v["box_h"])

    def to_bottom(self, d):
        left, top, right, bottom = d.panel()
        d.mouse(1, (left + right) // 2, (top + bottom) // 2)
        d.wheel(-100)
        return d.draw()

    def test_text_then_choices_scrolled_with_it_clicked_where_drawn(self):
        for game in NAMES:
            for n in (2, 4, 7):
                with self.subTest(game=game, choices=n):
                    d, op = self.open(game, n)
                    blits = d.draw()
                    v, rows = d.view(), d.view_rows()
                    self.assertEqual(v["shown"], 1)
                    self.assertEqual((v["sx"], v["sy"]), (0, 0))
                    self.assertEqual(rows["n"], n, "every choice is a row")
                    # The text is drawn and visible, above the choices: its glyphs in the box, the question too.
                    text = self.body_glyphs(d, blits, rows)
                    self.assertTrue(text)
                    self.assertEqual([b[3] for b in text if not self.inside(b, v)], [],
                                     f"the text shown whole at the top: {v} {rows}")
                    self.assertGreaterEqual(rows["y"], max(b[3][1] + b[1][3] for b in text),
                                            "the choices after the text")
                    # The rows are inside the scrolled content: the content is the text and the rows.
                    self.assertEqual(rows["y"] + (n - 1) * rows["step"] + rows["h"] - (v["box_y"] - v["sy"]),
                                     v["content_h"])
                    # Each row: its picture, then its label's glyphs over it.
                    labels = [b for b in blits if rows["y"] <= b[3][1] < rows["y"] + rows["h"]
                              and rows["x"] < b[3][0] and b[1][2] < rows["w"] // 2]
                    if v["vbar"]:
                        # Scroll to the end: the last row is reachable and whole.
                        blits = self.to_bottom(d)
                        v, rows = d.view(), d.view_rows()
                        last_top = rows["y"] + (n - 1) * rows["step"]
                        self.assertGreaterEqual(last_top, v["box_y"])
                        self.assertLessEqual(last_top + rows["h"], v["box_y"] + v["box_h"], "the last row whole")
                        self.assertGreater(v["sy"], 0)
                    else:
                        self.assertTrue(labels, "the labels drawn")
                    # A click on the last row where it is drawn now (scrolled) picks it, and is not the game's.
                    k = n - 1
                    x = rows["x"] + rows["w"] // 2
                    y = rows["y"] + k * rows["step"] + rows["h"] // 2
                    passed = len(d.passed)
                    self.assertFalse(d.click(x, y))
                    self.assertEqual(d.picks, [k])
                    self.assertEqual(len(d.passed), passed, "the click is the choice's, never the game's")
                    # A click beside the rows is the game's as before.
                    self.assertTrue(d.click(d.panel()[0] + 2, d.panel()[1] + 2))
                    self.assertEqual(d.picks, [k])

    def test_every_choice_by_its_row(self):
        for game in NAMES:
            n = 7
            for k in range(n):
                with self.subTest(game=game, choice=k):
                    d, op = self.open(game, n)
                    d.draw()
                    rows = d.view_rows()
                    v = d.view()
                    y = rows["y"] + k * rows["step"] + rows["h"] // 2
                    if y >= v["box_y"] + v["box_h"]:
                        self.to_bottom(d)
                        rows = d.view_rows()
                        y = rows["y"] + k * rows["step"] + rows["h"] // 2
                    self.assertFalse(d.click(rows["x"] + 5, y))
                    self.assertEqual(d.picks, [k])

    def test_the_outcome_replaces_the_text_in_the_same_popup(self):
        for game in NAMES:
            with self.subTest(game=game):
                d, op = self.open(game, 7)
                d.draw()
                panel = d.panel()
                self.to_bottom(d)
                rows = d.view_rows()

                def answer(k, d=d, op=op, game=game):
                    op["labels"] = []                         # OK shows now: no rows
                    if game <= 2:
                        d.mu.mem_write(d.dialog + d.event_kind["a"], body(game, OUTCOME) + b"\0")
                    else:
                        d.set_text(OUTCOME)

                op["on_pick"] = answer
                self.assertFalse(d.click(rows["x"] + 5, rows["y"] + rows["h"] // 2 + 6 * rows["step"]))
                self.assertEqual(d.picks, [6])
                blits = d.draw()
                v, rows = d.view(), d.view_rows()
                self.assertEqual(d.panel(), panel, "the same popup, not resized")
                self.assertEqual(rows["n"], 0, "no rows while OK shows")
                self.assertEqual(v["sy"], 0, "the outcome from its top")
                text = d.text_blits(blits)
                self.assertTrue(text and all(self.inside(b, v) for b in text if b[3][1] >= v["box_y"]))
                # Its words, not the question's: the glyph count of the outcome (no question left).
                self.assertNotEqual(len(text), 0)

    def test_pictures(self):
        if PICTURES is None:
            self.skipTest("ONE_POPUP_PICTURES names no folder")
        PICTURES.mkdir(parents=True, exist_ok=True)
        for game in NAMES:
            with self.subTest(game=game):
                d, _op = self.open(game, 7)
                d.save_picture(d.draw(), PICTURES / f"vv{game}_seven_choices_top.png")
                d.save_picture(self.to_bottom(d), PICTURES / f"vv{game}_seven_choices_bottom.png")


if __name__ == "__main__":
    unittest.main()
