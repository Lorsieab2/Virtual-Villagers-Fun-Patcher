"""PRACTICALLY UNLIMITED POPUP TEXT and MULTI-LINE CHOICES, as "VVFP Scrolling Popups.dll" draws them (the owner,
2026-11-16; native/shared/one_popup.h):

  * "With the scrollbar patch active, Custom Island Events should have a practically unlimited character and word
    count for any text."  A dialog's text field holds 2,000 bytes in the later three games and 9,999 in A New Home and
    The Lost Children; a longer text is kept whole by its companion, the field holding its start, and Scrolling
    Popups measures and draws the WHOLE text (VvfpPopupWholeText), scrolled.
  * "Long titles wrap; nothing is truncated."  The later three games draw the title on one line: a title wider than
    the text box is drawn in as many lines as it needs at the top of the scrolled box (A New Home and The Lost
    Children lead the text with the title, so it is the long text there).
  * "Multi-line choice popups: with super long sentences, the choice box can accommodate as many lines as it needs."
    Each choice row grows to its label's lines; the rows below move down; each is clicked on its whole height.

The companion owning the popup is a stand-in here answering the protocol exactly as one_popup.h has it (the field
cut as op_long_text_put cuts it); the game's own dialog code runs in the emulator with the companion's test build.
"""
from __future__ import annotations

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

TITLE = b"The Long Tale"
ENC_BUTTON_H = 32                 # A New Home's answer picture (ultra_wide_button.png: 390 x 32)
WORDS = (b"The tide rolled in over the black sand while the elders told the story of the first canoe and the "
         b"children listened with wide eyes, asking again and again what the island looked like before the "
         b"village was built. ")


def long_text(chars: int, tail: bytes = b"THE VERY END.") -> bytes:
    """`chars` characters of story, ending in `tail`."""
    body = (WORDS * (chars // len(WORDS) + 1))[:chars - len(tail) - 1]
    return body.rsplit(b" ", 1)[0] + b" " + tail


def wrapped(text: bytes, width: int = 49) -> bytes:
    """A New Home's and The Lost Children's popup text as the companion lays it out (ce_wrap: 49 characters)."""
    return b"\n".join(line.encode() for line in textwrap.wrap(text.decode(), width))


def body(game: int, text: bytes, title: bytes = TITLE) -> bytes:
    """The popup's text: in the first two games the (wrapped) title leads it, then the villager's picture gap."""
    if game <= 2:
        return wrapped(title) + b"\n\n\n\n\n\n" + wrapped(text)
    return text


def label(chars: int, k: int = 0) -> bytes:
    """A choice of about `chars` characters."""
    words = (b"Ask the elder of the eastern shore to carry the woven basket of fruit along the long path past the "
             b"singing stones and the old fishing nets, then return before the moon rises over the reef ")
    return (b"Choice %d: " % (k + 1) + (words * 4))[:chars].rsplit(b" ", 1)[0]


@unittest.skipUnless(HAVE_ALL, "needs unicorn, the stock executables, the game images and the test build")
class Unlimited(unittest.TestCase):
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

    # -- helpers -----------------------------------------------------------------------------------------------------
    def open(self, game: int, labels: list[bytes], text: bytes, title: bytes = TITLE, long: bool = True,
             one_popup: bool = True):
        d = self.dialogs[game]
        d.picks = []
        op = {"labels": list(labels), "reserve": 0} if one_popup else None
        if game <= 2:
            if op is not None:
                op["reserve"] = 5 * ENC_BUTTON_H // 2
            d.make_event("choice" if one_popup else "plain", body(game, text, title), one_popup=op,
                         button_h=ENC_BUTTON_H, long_text=long)
        else:
            if op is not None:
                op["reserve"] = 5 * d.picture_of(d.g["ok_id"])[2] // 2
            d.make(body(game, text, title), choices=one_popup, title=title, one_popup=op, long_text=long)
        return d, op

    def to_bottom(self, d):
        left, top, right, bottom = d.panel()
        d.mouse(1, (left + right) // 2, (top + bottom) // 2)
        d.wheel(-100000)
        return d.draw()

    def line(self, d) -> int:
        return d.view()["line"]

    def whole_height(self, d, game: int, text: bytes, width: int) -> int:
        """The game's own height of `text` (the later three: the justified paragraph at `width`; the first two: the
        '\\n'-broken text's)."""
        va = d._cstr(text)
        if game <= 2:
            return d.run._call(self.spe.EVENT_HEIGHT[f"vv{game}"], d.font, va)
        return d.justify_height(va, width)

    # -- A: practically unlimited text ---------------------------------------------------------------------------------
    def test_a_20000_character_popup_is_measured_and_drawn_whole(self):
        text = long_text(20000)
        for game in NAMES:
            with self.subTest(game=game):
                d, _op = self.open(game, [b"Listen", b"Leave"], text)
                field = d.whole[0] if d.whole else b""
                self.assertTrue(d.whole, "the text is longer than the field: kept whole by its companion")
                self.assertLess(len(field), self.spe.FIELD_BYTES[f"vv{game}"])
                d.draw()
                v = d.view()
                self.assertEqual(v["shown"], 1)
                self.assertEqual(v["vbar"], 1, "a 20,000-character text scrolls")
                whole = body(game, text)
                rows = d.view_rows()
                # The content is the WHOLE text (not the field's start) and the rows after it.
                text_h = rows["y"] - (v["box_y"] - v["sy"]) - (rows["h"] // 2 * 0)
                expected = self.whole_height(d, game, whole, v["content_w"])
                field_h = self.whole_height(d, game, field, v["content_w"])
                self.assertGreater(expected, field_h + 1000, "the whole text is far taller than its start")
                self.assertGreaterEqual(text_h, expected, (text_h, expected, field_h))
                # Scrolled to the end: the last row is reachable and clicks pick it.
                self.to_bottom(d)
                v, rows = d.view(), d.view_rows()
                self.assertEqual(v["sy"], v["content_h"] - v["box_h"], "scrolled to the very end")
                last = d.row_list()[-1]
                self.assertLessEqual(last[0] + last[1], v["box_y"] + v["box_h"])
                self.assertFalse(d.click(rows["x"] + 5, last[0] + last[1] // 2))
                self.assertEqual(d.picks, [1])

    def test_a_field_that_holds_the_whole_text_is_drawn_from_the_field(self):
        """A text that fits the field: no whole text is asked for (the stand-in answers none) and the popup is as
        before."""
        text = long_text(1500)
        for game in NAMES:
            with self.subTest(game=game):
                d, _op = self.open(game, [b"Listen", b"Leave"], text)
                self.assertIsNone(d.whole)
                d.draw()
                v, rows = d.view(), d.view_rows()
                expected = self.whole_height(d, game, body(game, text), v["content_w"])
                self.assertGreaterEqual(rows["y"] - (v["box_y"] - v["sy"]), expected)

    def test_a_plain_popup_with_a_long_text_scrolls_the_whole_text(self):
        """The later three games' plain island-event popup (OK alone, no rows): the whole text too."""
        text = long_text(20000)
        for game in (3, 4, 5):
            with self.subTest(game=game):
                d, _op = self.open(game, [], text, one_popup=False)
                self.assertTrue(d.whole)
                d.draw()
                v = d.view()
                self.assertEqual((v["shown"], v["vbar"]), (1, 1))
                expected = self.whole_height(d, game, text, v["content_w"])
                self.assertGreaterEqual(v["content_h"], expected)

    def test_a_long_outcome_replaces_the_question_whole(self):
        for game in (3, 4, 5):
            with self.subTest(game=game):
                d, op = self.open(game, [b"Listen", b"Leave"], b"A short question?", long=False)
                outcome = long_text(12000)

                def answer(k, d=d, op=op):
                    op["labels"] = []
                    d.set_text(outcome, long_text=True)

                op["on_pick"] = answer
                d.draw()
                rows = d.view_rows()
                self.assertFalse(d.click(rows["x"] + 5, rows["y"] + rows["h"] // 2))
                d.draw()
                v = d.view()
                self.assertEqual(v["sy"], 0)
                self.assertGreaterEqual(v["content_h"], self.whole_height(d, game, outcome, v["content_w"]))

    # -- A: long titles wrap -------------------------------------------------------------------------------------------
    def test_a_long_title_wraps_at_the_top_of_the_box(self):
        title = (b"The Remarkably Long And Winding Tale Of The Elder Who Walked Around The Whole Island Twice "
                 b"Before Breakfast And Still Came Home In Time To Feed The Goats And Tell Everyone About It")
        for game in (3, 4, 5):
            with self.subTest(game=game):
                d, _op = self.open(game, [b"Listen", b"Leave"], b"A short question?", title=title, long=False)
                blits = d.draw()
                v = d.view()
                title_y = d.i32(d.dialog + 0x84C)
                self.assertEqual(v["box_y"], title_y, "the scrolled box starts at the title")
                # The title's glyphs: the lines at the box's top (the text starts below them).
                glyphs = [b for b in d.text_blits(blits) if b[3][1] < v["box_y"] + 3 * v["line"]]
                self.assertGreaterEqual(len({b[3][1] // v["line"] for b in glyphs}), 3, "three lines or more")
                # every line inside the box: nothing runs past its sides, nothing cut
                self.assertTrue(all(v["box_x"] <= b[3][0] and b[3][0] + b[1][2] <= v["box_x"] + v["box_w"]
                                    for b in glyphs))
                letters = sum(1 for c in title if c != 0x20)
                self.assertGreaterEqual(len([b for b in d.text_blits(blits)
                                             if b[3][1] < v["box_y"] + 4 * v["line"]]), letters,
                                        "every letter of the title drawn")

    def test_a_short_title_is_drawn_by_the_game(self):
        for game in (3, 4, 5):
            with self.subTest(game=game):
                d, _op = self.open(game, [b"Listen", b"Leave"], b"A short question?", long=False)
                d.draw()
                self.assertGreater(d.view()["box_y"], d.i32(d.dialog + 0x84C), "the box starts below the title")

    # -- B: multi-line choices -----------------------------------------------------------------------------------------
    def one_line_row(self, game: int) -> int:
        """A one-line row's height (the game's answer-button picture)."""
        d, _op = self.open(game, [b"Yes", b"No"], b"Well?", long=False)
        d.draw()
        return d.view_rows()["h"]

    def label_glyphs(self, d, blits, top: int, height: int) -> list:
        """The glyphs drawn on the row at `top`: every blit in its band but its picture's (the blits of the
        surface drawn at the row's own corner)."""
        rows = d.view_rows()
        picture = {b[0] for b in blits if (b[3][0], b[3][1]) == (rows["x"], top)}
        picture |= d.panel_surfaces() | d.art_surfaces()          # the panel's tiles, the scrollbars
        return [b for b in blits if top <= b[3][1] < top + height and b[0] not in picture
                and b[1][2] < rows["w"] // 4]

    def check_rows(self, d, labels: list[bytes], one: int) -> None:
        d.draw()
        v, rows = d.view(), d.view_rows()
        drawn = d.row_list()
        self.assertEqual(len(drawn), len(labels))
        for k, (top, height, lines) in enumerate(drawn):
            if k:
                self.assertGreater(top, drawn[k - 1][0] + drawn[k - 1][1], "rows never overlap")
            if len(labels[k]) > 120:
                self.assertGreater(lines, 1, "a long label takes several lines")
                self.assertGreater(height, one, "its row grows to hold them")
            if len(labels[k]) < 20:
                self.assertEqual((lines, height), (1, one), "a short label keeps the one-line row")
        # The content ends with the last row.
        last = drawn[-1]
        self.assertEqual(last[0] + last[1] - (v["box_y"] - v["sy"]), v["content_h"])
        # Every row is clicked on its whole height (its top line, its bottom line), each its own choice.
        for k in range(len(labels)):
            for part in (0.15, 0.85):
                d.picks = []
                d.draw()
                for _ in range(20):             # scrolled until that part of the row shows
                    v = d.view()
                    top, height, _lines = d.row_list()[k]
                    y = int(top + part * height)
                    if v["box_y"] <= y < v["box_y"] + v["box_h"]:
                        break
                    notches = (y - (v["box_y"] + v["box_h"] // 2)) // (3 * v["line"])
                    d.mouse(1, v["box_x"] + 5, v["box_y"] + 5)
                    d.wheel(-notches if notches else (-1 if y >= v["box_y"] else 1))
                    d.draw()
                self.assertFalse(d.click(rows["x"] + 5, y), (k, part))
                self.assertEqual(d.picks, [k], (k, part))

    def test_b_a_long_choice_label_takes_as_many_lines_as_it_needs(self):
        for game in NAMES:
            with self.subTest(game=game):
                one = self.one_line_row(game)
                labels = [label(300), b"Leave"]
                d, _op = self.open(game, labels, b"What should the village do?", long=False)
                d.draw()
                drawn = d.row_list()
                self.assertGreaterEqual(drawn[0][2], 3)
                # Its lines stay on its row: no glyph of the long label runs past the row's sides, and every
                # letter of it is drawn (nothing cut).
                blits = d.draw()
                rows = d.view_rows()
                top, height, lines = d.row_list()[0]
                glyphs = self.label_glyphs(d, blits, top, height)
                self.assertGreaterEqual(len(glyphs), sum(1 for c in labels[0] if c != 0x20), "the whole label drawn")
                self.assertTrue(all(rows["x"] <= b[3][0] and b[3][0] + b[1][2] <= rows["x"] + rows["w"]
                                    for b in glyphs), "every line inside its row")
                self.assertGreaterEqual(max(b[3][1] for b in glyphs) - min(b[3][1] for b in glyphs),
                                        (lines - 1) * (d.view()["line"] - 4), "its lines one below the other")
                self.check_rows(d, labels, one)

    def test_b_four_choices_of_about_300_characters(self):
        for game in NAMES:
            with self.subTest(game=game):
                one = self.one_line_row(game)
                labels = [label(300, k) for k in range(4)]
                d, _op = self.open(game, labels, b"Which path should the elder take?", long=False)
                self.check_rows(d, labels, one)

    def test_b_mixed_short_and_long_choices(self):
        for game in NAMES:
            with self.subTest(game=game):
                one = self.one_line_row(game)
                labels = [b"Yes", label(300, 1), b"No", label(160, 3), b"Maybe later"]
                d, _op = self.open(game, labels, b"Well?", long=False)
                self.check_rows(d, labels, one)

    def test_b_long_labels_with_a_long_text_and_a_long_title(self):
        title = b"A Title Long Enough To Need Two Lines Or More In Every One Of The Three Later Games' Dialogs Here"
        for game in NAMES:
            with self.subTest(game=game):
                labels = [label(300, k) for k in range(4)]
                d, _op = self.open(game, labels, long_text(20000), title=title)
                self.to_bottom(d)
                v = d.view()
                last = d.row_list()[-1]
                self.assertLessEqual(last[0] + last[1], v["box_y"] + v["box_h"], "the last row reachable whole")
                self.assertFalse(d.click(d.view_rows()["x"] + 5, last[0] + last[1] // 2))
                self.assertEqual(d.picks, [3])


if __name__ == "__main__":
    unittest.main()
