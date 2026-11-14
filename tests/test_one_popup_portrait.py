"""The villager's picture scrolls with the text and the choices (the owner, 2026-11-14: "the villager's picture
should scroll too!"; native/shared/scroll_popup.h portrait_site).

In a one-popup island event (native/shared/one_popup.h) the featured villager's picture, drawn by the game under the
popup's title, is part of the scrolled content: in every game, for 2 and 7 choices,
  * at scroll 0 it is drawn WHOLE inside the scroll window, above the text;
  * it moves up with the scroll, exactly as far as the content does;
  * it is clipped at the window's edges like the text: never drawn outside the window;
  * its visible pixels never overlap the text (title, words, row labels) or the choice rows.
A New Home and The Lost Children scroll the dialog's whole body (title, picture gap, text), and the picture now moves
with it; The Secret City, The Tree of Life and New Believers scroll a box that now starts under the title and holds
the picture first, then the text, then the rows.  A popup that is not a one-popup event draws the picture where the
game puts it.

The harness's picture is a stand-in (scrolling_popups_emulation.PORTRAITS: one frame of the game's own head sheet,
drawn by the game's own picture draw at the call's place); the companion moves and clips the game's own call.
Pictures (top and scrolled partway) are written when ONE_POPUP_PORTRAIT_PICTURES names a folder.
"""
from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import test_one_popup_scrolling as base  # noqa: E402

PICTURES = (Path(os.environ["ONE_POPUP_PORTRAIT_PICTURES"]) if os.environ.get("ONE_POPUP_PORTRAIT_PICTURES")
            else None)
TEXT = (base.INTRO + b"\n\n") * 8 + base.QUESTION     # long enough to scroll the picture out, 2 choices too


def overlaps(a, b) -> bool:
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


@unittest.skipUnless(base.HAVE_ALL, "needs unicorn, the stock executables, the game images and the test build")
class PortraitScrolls(unittest.TestCase):
    dialogs: dict = {}

    @classmethod
    def setUpClass(cls) -> None:
        import scrolling_popups_emulation as spe
        cls.spe = spe
        for game in base.NAMES:
            cls.dialogs[game] = spe.Dialog(f"vv{game}")

    @classmethod
    def tearDownClass(cls) -> None:
        cls.dialogs.clear()

    def open(self, game: int, n: int, one_popup: bool = True, text: bytes = TEXT):
        d = self.dialogs[game]
        d.picks = []
        op = {"labels": list(base.LABELS[:n]), "reserve": 0} if one_popup else None
        if game <= 2:
            if op is not None:
                op["reserve"] = 5 * base.ENC_BUTTON_H // 2
            d.make_event("choice", base.body(game, text), one_popup=op, button_h=base.ENC_BUTTON_H, portrait=True)
        else:
            if op is not None:
                op["reserve"] = 5 * d.picture_of(d.g["ok_id"])[2] // 2
            d.make(base.body(game, text), choices=True, title=base.TITLE, one_popup=op, portrait=True)
        return d

    def check(self, d, blits, n) -> tuple:
        """The picture's blit at this scroll: inside the window, its visible pixels clear of every glyph and row.
        Returns (its blit or None, the y the game's call was given)."""
        v, rows = d.view(), d.view_rows()
        window = (v["box_x"], v["box_y"], v["box_x"] + v["box_w"], v["box_y"] + v["box_h"])
        pics = d.portrait_blits(blits)
        self.assertLessEqual(len(pics), 1, "the picture drawn once")
        self.assertTrue(d.portrait_calls, "the game's picture call made")
        call_y = d.portrait_calls[-1][1]
        if not pics:
            return None, call_y
        b = pics[0]
        x, y, w, h = b[3]
        self.assertTrue(window[0] <= x and x + w <= window[2] and window[1] <= y and y + h <= window[3],
                        f"never drawn outside the window: {b[3]} {window}")
        seen = d.opaque_box(b)
        if seen is not None:
            for g in d.text_blits(blits):
                gx, gy = g[3][0], g[3][1]
                self.assertFalse(overlaps(seen, (gx, gy, gx + g[1][2], gy + g[1][3])),
                                 f"a glyph at {g[3]} over the picture {seen}")
            if rows["n"]:
                last = rows["y"] + (rows["n"] - 1) * rows["step"] + rows["h"]
                self.assertFalse(overlaps(seen, (rows["x"], rows["y"], rows["x"] + rows["w"], last)),
                                 f"the rows over the picture {seen} {rows}")
        return b, call_y

    def test_picture_whole_at_the_top_then_scrolled_and_clipped(self):
        for game in base.NAMES:
            for n in (2, 7):
                with self.subTest(game=game, choices=n):
                    d = self.open(game, n)
                    d.portrait_calls.clear()
                    blits = d.draw()
                    v = d.view()
                    self.assertEqual((v["sx"], v["sy"]), (0, 0))
                    self.assertEqual(v["vbar"], 1, "the text scrolls")
                    b, y0 = self.check(d, blits, n)
                    self.assertIsNotNone(b, "the picture shown at the top")
                    self.assertEqual(tuple(b[1][2:]), (self.spe.PORTRAIT_W, self.spe.PORTRAIT_H), "drawn whole")
                    self.assertEqual(b[3][1], y0)
                    self.assertGreaterEqual(y0, v["box_y"])
                    # Above the text: every word of the body below the picture (the title too in the first two).
                    seen = d.opaque_box(b)
                    rows = d.view_rows()
                    self.assertTrue(any(g[3][1] >= seen[3] for g in d.text_blits(blits)), "the text after it")
                    self.assertGreaterEqual(rows["y"], seen[3], "the rows after it")
                    # Scrolled a notch at a time to the end: the picture moves with the content, clipped, never over
                    # the text or the rows.
                    left, top, right, bottom = d.panel()
                    d.mouse(1, (left + right) // 2, (top + bottom) // 2)
                    last_sy, moved, clipped = 0, False, False
                    for _ in range(60):
                        d.wheel(-1)
                        d.portrait_calls.clear()
                        blits = d.draw()
                        sy = d.view()["sy"]
                        b, y = self.check(d, blits, n)
                        self.assertEqual(y, y0 - sy, "the picture moves as far as the content")
                        if sy != last_sy:
                            moved = True
                        if b is not None and b[1][3] < self.spe.PORTRAIT_H:
                            clipped = True
                            self.assertEqual(b[3][1], d.view()["box_y"], "cut at the window's top edge")
                            self.assertEqual(b[1][1] % self.spe.PORTRAIT_H + b[1][3], self.spe.PORTRAIT_H)
                        if sy == last_sy and sy > 0:
                            break
                        last_sy = sy
                    self.assertTrue(moved, "it scrolled")
                    self.assertTrue(clipped, "the picture was cut at the window's edge on its way out")

    def test_not_a_one_popup_event_draws_the_picture_where_the_game_puts_it(self):
        for game in base.NAMES:
            with self.subTest(game=game):
                d = self.open(game, 2, one_popup=False, text=base.QUESTION)
                d.portrait_calls.clear()
                blits = d.draw()
                pics = d.portrait_blits(blits)
                self.assertEqual(len(pics), 1)
                self.assertEqual(tuple(pics[0][1][2:]), (self.spe.PORTRAIT_W, self.spe.PORTRAIT_H))
                if game <= 2:
                    expected = (0x16D, d.i32(d.dialog + 0x68))
                else:
                    expected = (d.i32(d.dialog + 0x840) + (0x19 if game == 4 else 0), d.i32(d.dialog + 0x844))
                self.assertEqual(d.portrait_calls, [expected], "the game's own place, drawn once")

    def test_pictures(self):
        if PICTURES is None:
            self.skipTest("ONE_POPUP_PORTRAIT_PICTURES names no folder")
        PICTURES.mkdir(parents=True, exist_ok=True)
        for game in base.NAMES:
            for n in (2, 7):
                with self.subTest(game=game, choices=n):
                    d = self.open(game, n, text=base.INTRO + b"\n\n" + base.QUESTION)
                    d.save_picture(d.draw(), PICTURES / f"vv{game}_{n}_choices_top.png")
                    left, top, right, bottom = d.panel()
                    d.mouse(1, (left + right) // 2, (top + bottom) // 2)
                    d.wheel(-1)
                    d.save_picture(d.draw(), PICTURES / f"vv{game}_{n}_choices_scrolled.png")


if __name__ == "__main__":
    unittest.main()
