"""PRACTICALLY UNLIMITED TEXT in Custom Island Events (the owner, 2026-11-16): "With the scrollbar patch active (+
unicode if it's required), Custom Island Events should have a practically unlimited character and word count for any
text."

  * The patcher (src/vv_cie_graph.py validate(scrolling=True)): a part's text up to LONG_TEXT_MAX bytes, a title or a
    choice up to LONG_LINE_BYTES; no screen-width rule for a choice (its row grows) or a title (it wraps).  Without
    Scrolling Popups the old caps stay, and each problem says the patch would allow it.
  * The engine (story_graph.inc, the companion's test build in the emulator): the .cieg loader takes such texts; with
    Scrolling Popups the run shows them WHOLE (the text, every label, the title), never cut; without it the event is
    refused, saying why.
  * The field (one_popup.h op_long_text_put / VvfpPopupWholeText): a text longer than the dialog's field holds is put
    there as its start, and the whole text is answered for exactly that start.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import vv_cie_graph as cg  # noqa: E402
from test_story_custom_island_event import GAMES, HAVE_EMULATOR, emulated, have_stock  # noqa: E402

if HAVE_EMULATOR:
    from test_story_cie_graph_runtime import CIEG_BUF, IDLE, Run

STEPS = 2_000_000_000                     # a 20,000-character text takes more instructions than a short one's 2 million


def big(p, name: str, *args: int) -> int:
    """An export called with room for the long texts' instructions."""
    return p.call(p.exports[name], list(args), limit=STEPS)

WORDS = ("The tide rolled in over the black sand while the elders told the story of the first canoe and the "
         "children listened with wide eyes, asking again and again what the island looked like before the "
         "village was built. ")


def story(chars: int) -> str:
    """`chars` characters of story, ending in a marker."""
    body = (WORDS * (chars // len(WORDS) + 1))[:chars - 20]
    return body.rsplit(" ", 1)[0] + " THE VERY LAST WORDS."


def label(chars: int, k: int) -> str:
    words = ("Ask the elder of the eastern shore to carry the woven basket of fruit along the long path past the "
             "singing stones and the old fishing nets, then return before the moon rises over the reef ")
    return (f"Choice {k + 1}: " + words * 4)[:chars].rsplit(" ", 1)[0]


TITLE = ("The Remarkably Long And Winding Tale Of The Elder Who Walked Around The Whole Island Twice Before "
         "Breakfast And Still Came Home In Time To Feed The Goats And Tell Everyone All About It Again")


def long_graph(text_chars: int = 20000, labels: int = 4, label_chars: int = 300, title: str = TITLE) -> dict:
    choices = [{"label": label(label_chars, k), "next": f"a{k}"} for k in range(labels)]
    nodes = {"q": {"type": "question", "text": story(text_chars) + " Which way?", "choices": choices}}
    for k in range(labels):
        nodes[f"a{k}"] = {"text": f"Answer {k + 1}: " + story(text_chars // 2)}
    return {"format": "vvfp-cie-graph", "version": 6, "title": title, "games": [1, 2, 3, 4, 5],
            "roles": {}, "start": "q", "nodes": nodes}


class Validator(unittest.TestCase):
    def test_with_scrolling_popups_long_texts_titles_and_labels_pass(self):
        g, problems = cg.validate(long_graph(), scrolling=True)
        self.assertEqual(problems, [])
        blob = cg.compile_graph(g)
        self.assertEqual(cg.decompile_graph(blob), cg.without_names(g), "compiled and read back whole")

    def test_without_scrolling_popups_the_old_caps_stay_and_say_so(self):
        cases = (("text", long_graph(), f"longer than {cg.NODE_TEXT_MAX} characters"),
                 ("title", long_graph(600, 2, 20), "as written"),
                 ("label", long_graph(600, 2, 300, "Short"), f"at most {cg.LABEL_BYTES_V6}"))
        for what, g, words in cases:
            with self.subTest(what=what):
                _g, problems = cg.validate(g, scrolling=False)
                self.assertTrue(any(words in p and "Scrolling Popups" in p for p in problems), problems)
                _g, problems = cg.validate(g, scrolling=True)
                self.assertEqual(problems, [], "with Scrolling Popups it passes")

    def test_the_old_caps_still_hold_exactly_without_scrolling(self):
        for chars, ok in ((cg.NODE_TEXT_MAX - 40, True), (cg.NODE_TEXT_MAX + 40, False)):
            with self.subTest(chars=chars):
                g = long_graph(text_chars=chars, labels=2, label_chars=20, title="Short")
                g["nodes"]["q"]["text"] = story(chars)
                _g, problems = cg.validate(g, scrolling=False)
                self.assertEqual(not any(f"longer than {cg.NODE_TEXT_MAX}" in p for p in problems), ok, problems)

    def test_the_sanity_caps_hold_with_scrolling(self):
        g = long_graph(text_chars=cg.LONG_TEXT_MAX + 50, labels=2, label_chars=20, title="Short")
        _g, problems = cg.validate(g, scrolling=True)
        self.assertTrue(any(f"longer than {cg.LONG_TEXT_MAX}" in p for p in problems), problems)
        g = long_graph(text_chars=500, labels=2, label_chars=20, title="Short")
        g["nodes"]["q"]["choices"][0]["label"] = "Go " * 1400
        _g, problems = cg.validate(g, scrolling=True)
        self.assertTrue(any(f"at most {cg.LONG_LINE_BYTES}" in p for p in problems), problems)
        g = long_graph(text_chars=500, labels=2, label_chars=20, title="Long " * 900)
        _g, problems = cg.validate(g, scrolling=True)
        self.assertTrue(any(f"longer than {cg.LONG_LINE_BYTES}" in p for p in problems), problems)

    def test_a_choice_wider_than_the_screen_needs_no_pronouns_with_scrolling(self):
        g = long_graph(text_chars=500, labels=2, label_chars=90, title="Short")
        _g, problems = cg.validate(g, scrolling=True)
        self.assertEqual(problems, [])
        _g, problems = cg.validate(g, scrolling=False)
        self.assertTrue(any("runs off the screen" in p or "at most" in p for p in problems), problems)


@emulated
class Engine(unittest.TestCase):
    BIG = 0x30000                         # the text buffer handed to the engine: room for the whole text

    def start(self, game, data, scroll=1):
        r = Run(game)
        r.reset()
        r.rolls([0] * 60)
        r.log(1)
        r.p.export("VvfpStoryProbeGraphScroll", scroll)
        r.p.write(CIEG_BUF, data)
        at = big(r.p, "VvfpStoryProbeGraphQueue", r.n, CIEG_BUF, len(data), 0)
        return r, None if at == 0 else r.p.cstring(at)

    def test_the_whole_text_every_label_and_the_title_are_shown_never_cut(self):
        g = cg.load(long_graph(), scrolling=True)
        data = cg.compile_graph(g)
        self.assertGreater(len(data), 0x8000)
        for game in GAMES:
            if not have_stock(game):
                continue
            with self.subTest(game=game):
                r, why = self.start(game, data)
                self.assertIsNone(why)
                p = r.p
                buf = p.alloc(self.BIG)
                if not r.state()["armed"]:
                    assert big(p, "VvfpStoryProbeGraphArmNext", r.n) == 1
                p.write(buf, b"\0")
                assert big(p, "VvfpStoryProbeChoiceBegin", r.n, buf, self.BIG) == 1
                text = p.cstring(buf, self.BIG)
                self.assertGreater(len(text), 20000, "the whole text, not a field's 2,000 bytes")
                self.assertIn("THE VERY LAST WORDS", " ".join(text.upper().split()))
                n = big(p, "VvfpStoryProbeOnePopupRows", r.n)
                self.assertEqual(n, 4)
                for k in range(n):
                    shown = p.cstring(big(p, "VvfpStoryProbeChoiceLabel", r.n, k), 8000)
                    self.assertGreater(len(shown), 250, "a long label whole")
                    self.assertTrue(shown.endswith(label(300, k)[-30:]), shown[-60:])
                title = p.cstring(big(p, "VvfpStoryProbeGraphTitle", 0), 8000)
                if game in ("vv3", "vv4", "vv5"):
                    self.assertEqual(title, TITLE, "the title whole (Scrolling Popups wraps it)")
                else:
                    # A New Home and The Lost Children lead the text with the title: its first line, and the rest
                    # after the picture's gap -- every word of it shown.
                    self.assertTrue(TITLE.startswith(title) and title, title)
                    self.assertIn(" ".join(TITLE.split()[-6:]), " ".join(text.split()))
                p.write(buf, b"\0")
                assert big(p, "VvfpStoryProbeChoiceResolve", r.n, 3, buf, self.BIG) == 1
                outcome = " ".join(p.cstring(buf, self.BIG).split())
                self.assertGreater(len(outcome), 10000)
                self.assertIn(label(300, 3)[-30:], outcome, "the choice picked starts the answer, whole")
                p.write(buf, b"\0")
                self.assertEqual(big(p, "VvfpStoryProbeOnePopupOk", r.n, buf, self.BIG), 0, "OK ends it")
                _n_filed, _now, filed = r.log()
                self.assertIn(label(300, 3)[-30:], " ".join(filed.split()),
                              "the log's Choice line holds the whole label")

    def test_without_scrolling_popups_the_event_is_refused_saying_why(self):
        data = cg.compile_graph(cg.load(long_graph(), scrolling=True))
        for game in GAMES:
            if not have_stock(game):
                continue
            with self.subTest(game=game):
                r, why = self.start(game, data, scroll=0)
                self.assertIsNotNone(why)
                self.assertIn("Scrolling Popups", why)
                self.assertEqual(r.state()["phase"], IDLE)

    def test_a_short_event_is_queued_without_scrolling_popups_as_before(self):
        g = long_graph(text_chars=600, labels=2, label_chars=20, title="Short")
        data = cg.compile_graph(cg.load(g, scrolling=False))
        for game in GAMES:
            if have_stock(game):
                with self.subTest(game=game):
                    _r, why = self.start(game, data, scroll=0)
                    self.assertIsNone(why)
                break

    def test_the_field_holds_the_start_and_the_whole_text_is_answered_for_it(self):
        for game in GAMES:
            if not have_stock(game):
                continue
            r, _why = self.start(game, cg.compile_graph(cg.load(long_graph(600, 2, 20, "Short"), scrolling=True)))
            p = r.p
            whole = story(20000).encode()
            src, field = p.alloc(len(whole) + 16), p.alloc(2100)
            p.write(src, whole + b"\0")
            held = big(p, "VvfpStoryProbeLongPut", src, field, 2000)
            self.assertLess(held, 2000 - 15, "a little short of the field: the game's own copy keeps every byte")
            shown = p.read(field, held + 1)
            self.assertEqual(shown, whole[:held] + b"\0", "the start, as written")
            self.assertIn(whole[held:held + 1], (b" ", b"\n"), "cut at a space")
            at = big(p, "VvfpPopupWholeText", field)
            self.assertNotEqual(at, 0)
            self.assertEqual(p.cstring(at, len(whole) + 8).encode(), whole, "the whole text for that start")
            p.write(field + 10, b"X")                        # the field changed: not that text's start any more
            self.assertEqual(big(p, "VvfpPopupWholeText", field), 0)
            short = b"A short text."
            p.write(src, short + b"\0")
            self.assertEqual(big(p, "VvfpStoryProbeLongPut", src, field, 2000), len(short))
            self.assertEqual(big(p, "VvfpPopupWholeText", field), 0, "a text that fits: the field is whole")
            break


if __name__ == "__main__":
    unittest.main()
