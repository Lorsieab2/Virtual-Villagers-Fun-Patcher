"""The last line of a one-popup event's result is never under the OK button (live test, v1.35.97: The Secret City's
Aspiring Adventurer result "... Your villagers gain 24144 tech p" and The Troubling Signs' result, New Believers'
Adventurer death outcome -- the last line sat under OK).

THE CAUSE.  A one-popup island event (native/shared/one_popup.h) is the game's two-choice dialog: the constructor
places OK where the two-choice layout puts it, 2 1/2 x the CHOICE button's height above the panel's bottom (The
Secret City 0x41993D..0x419976, The Tree of Life 0x417DE2.., New Believers 0x418666..), but the companion's OK room
(VvfpOnePopupRows' reserve) is 5/2 x OK's own height, the single-OK layout's room (OK 0x14 above the bottom).  The
answer-button picture is taller than OK's, so the text box (and the panel asked for it) ended below OK's top.

The rule, in The Secret City, The Tree of Life and New Believers, for these exact texts and for a sweep of lengths
(fitting without a scrollbar, and scrolled to the end): every glyph of the result is drawn above OK's top, inside the
text box, and the last line is drawn whole.  A New Home and The Lost Children place OK 0x14 above the bottom in their
encounter dialog (0x41A7E4, 0x42270F), inside the 5/2 x OK room, as before.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import test_one_popup_scrolling as base  # noqa: E402

ADVENTURER_VV3 = (
    b"Go Investigate!\n\n"
    b"Against his better judgement, Nasau Bandele leaves the beaten path to check out the strange sight. As he pushes "
    b"through the foliage, the area gets noticeably darker and colder. The hairs on Nasau Bandele's neck stand on end "
    b"as he gets closer to the spot. When Nasau Bandele approaches, he finds... a large golden chest full of "
    b"artifacts! Nasau Bandele's eyes widen at the sight, and he stuffs as much treasure as he can fit in his "
    b"knapsack.\n"
    b"As Nasau Bandele turns to leave, he unexpectedly steps into a trap! Now panicking, he struggles with all his "
    b"might to break free, causing a big ruckus. He hears something coming, and braces for the worst...\n"
    b"Miraculously, Nasau Bandele manages to escape the trap, and quickly runs back to the safety of the village. "
    b"Heart pounding, he frantically warns others about his misadventure, to the relief of all the villagers. Nasau "
    b"Bandele vows to never do something like that EVER again! Your villagers gain 24144 tech points.")
TROUBLING_SIGNS = (
    b"The spiritual leaders\n\n"
    b"\"I have consulted with the spiritual leaders, and have heard your cries for help. There is much we know, and "
    b"much we don't know about the strange misfortunes befalling our village. But I believe we have a plan to fix "
    b"them!\n"
    b"Look amongst yourselves, all who are eligible to work, and from you pick five to represent our tribe. You "
    b"alone will travel to find the cause of our suffering, and heal it, for the sake of us all. Now go forth, and "
    b"discuss your plans with my advisors. They will guide you on your sacred mission. May Isola help us all.\"\n"
    b"On the day of departure, Kei Bandele meets personally with the chosen representatives and wishes them well on "
    b"their journey. As they leave, the tribe prays for a whole week, offering gifts of food to the spirits in hopes "
    b"of granting them salvation. Your village loses 2724 food.")
ADVENTURER_DEATH_VV5 = (
    b"Go Investigate!\n\n"
    b"Against his better judgement, Tolu leaves the beaten path to check out the strange sight. As he pushes through "
    b"the foliage, the area gets noticeably darker and colder. The hairs on Tolu's neck stand on end as he gets "
    b"closer to the spot. When Tolu approaches, he finds... nothing but a pile of dirt.\n"
    b"As Tolu turns to leave, he unexpectedly steps into a trap! Now panicking, he struggles with all his might to "
    b"break free, causing a big ruckus. He hears something coming, and braces for the worst...\n"
    b"The last thing Tolu sees is the wide toothy grin of a large beast, and the terror of his face reflected in its "
    b"eyes.\n"
    b"Later on, some hunters come to check on the trap, and see the unfortunate aftermath. They try to recover Tolu's "
    b"remains, but are unsuccessful. They bring the sad news to the village along with their condolences. The "
    b"villagers mourn for Tolu greatly and lament that things had to turn out this way.")
LIVE = {3: [ADVENTURER_VV3, TROUBLING_SIGNS], 4: [ADVENTURER_VV3, TROUBLING_SIGNS],
        5: [ADVENTURER_DEATH_VV5, TROUBLING_SIGNS, ADVENTURER_VV3]}
QUESTION = base.INTRO + b"\n\n" + base.QUESTION
SENTENCE = b"The villagers talk about it for days, and the story grows a little with every telling. "
GAMES = (3, 4, 5)


@unittest.skipUnless(base.HAVE_ALL, "needs unicorn, the stock executables, the game images and the test build")
class ResultClearOfOk(unittest.TestCase):
    dialogs: dict = {}

    @classmethod
    def setUpClass(cls) -> None:
        import scrolling_popups_emulation as spe
        for game in GAMES:
            cls.dialogs[game] = spe.Dialog(f"vv{game}")

    @classmethod
    def tearDownClass(cls) -> None:
        cls.dialogs.clear()

    def show_result(self, game: int, result: bytes, labels: int = 2):
        """A one-popup event's question with its rows, then its result in the same popup with OK (no rows)."""
        d = self.dialogs[game]
        d.picks = []
        op = {"labels": list(base.LABELS[:labels]), "reserve": 5 * d.picture_of(d.g["ok_id"])[2] // 2}
        d.make(QUESTION, choices=True, title=b"The Aspiring Adventurer", one_popup=op)
        d.draw()
        op["labels"] = []
        d.set_text(result, long_text=len(result) >= 1999)
        return d

    def ok_top(self, d) -> int:
        return d.panel()[1] + d.button_position("ok")[1]

    def check(self, d, blits, label: str) -> None:
        v = d.view()
        ok_top = self.ok_top(d)
        box_bottom = v["box_y"] + v["box_h"]
        self.assertLessEqual(box_bottom, ok_top, f"{label}: the text box ends above OK: {v} OK top {ok_top}")
        glyphs = [b for b in d.text_blits(blits) if b[3][1] + b[1][3] > v["box_y"]]
        self.assertTrue(glyphs, label)
        for b in glyphs:
            self.assertLessEqual(b[3][1] + b[1][3], ok_top, f"{label}: a glyph under OK {b[3]} (OK top {ok_top})")
            self.assertLessEqual(b[3][1] + b[1][3], box_bottom, f"{label}: a glyph past the box {b[3]}")
        if v["vbar"] and v["sy"] != v["content_h"] - v["box_h"]:
            return                                  # not at the end yet: the last line is further down
        # The last line is drawn whole: its top is the content's end less one line, inside the box.
        last_top = v["box_y"] - v["sy"] + v["content_h"] - v["line"]
        self.assertGreaterEqual(last_top, v["box_y"], f"{label}: the last line inside the box {v}")
        self.assertLessEqual(last_top + v["line"], box_bottom, f"{label}: the last line whole {v}")
        self.assertTrue(any(b[3][1] >= last_top - 2 for b in glyphs), f"{label}: the last line drawn {v}")

    def to_end(self, d) -> list:
        left, top, right, bottom = d.panel()
        d.mouse(1, (left + right) // 2, (top + bottom) // 2)
        d.wheel(-200)
        return d.draw()

    def run_text(self, game: int, text: bytes, label: str) -> None:
        d = self.show_result(game, text)
        blits = d.draw()
        v = d.view()
        self.assertEqual(v["sy"], 0, label)
        self.check(d, blits, label + " (top)")
        if v["vbar"]:
            blits = self.to_end(d)
            v = d.view()
            self.assertEqual(v["sy"], v["content_h"] - v["box_h"], label + ": scrolled to the end")
            self.check(d, blits, label + " (end)")

    def test_the_live_texts(self) -> None:
        for game in GAMES:
            for k, text in enumerate(LIVE[game]):
                with self.subTest(game=game, text=k):
                    self.run_text(game, text, f"vv{game} text {k}")

    def test_every_length(self) -> None:
        for game in GAMES:
            for n in (0, 1, 2, 3, 4, 6, 9, 14, 30):
                with self.subTest(game=game, sentences=n):
                    self.run_text(game, b"Go Investigate!\n\n" + SENTENCE * n + b"Your villagers gain 24144 tech "
                                  b"points.", f"vv{game} {n} sentences")

    def test_the_question_rows_stay_above_ok_too(self) -> None:
        for game in GAMES:
            with self.subTest(game=game):
                d = self.dialogs[game]
                op = {"labels": list(base.LABELS[:4]), "reserve": 5 * d.picture_of(d.g["ok_id"])[2] // 2}
                d.make(QUESTION, choices=True, title=b"The Troubling Signs", one_popup=op)
                d.draw()
                v = d.view()
                self.assertLessEqual(v["box_y"] + v["box_h"], self.ok_top(d))


if __name__ == "__main__":
    unittest.main()
