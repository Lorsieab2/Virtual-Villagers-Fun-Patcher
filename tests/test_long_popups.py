"""Long island-event popups in The Secret City, The Tree of Life and New Believers (the owner's standing rule: popups
scroll, so "too long" is never a reason to cut or shorten event text, effects or result lines).

With Scrolling Popups installed one popup holds up to 8,000 counted bytes in every game (story_graph.inc
CG_TEXT_MAX_ONE, src/vv_cie_graph.py ONE_POPUP_TEXT_MAX), as A New Home and The Lost Children already did.  The later
three games' dialog copies its text into a field of 2,000 bytes (+0x58) with the C runtime's strncat(field, text,
2000), which writes one byte PAST the field for a text of 2,000 bytes or more; so Story Upgrades gives the game's
string table only the text's first 1,999 bytes (story_objects.inc ce_popup_text) and Scrolling Popups draws and
measures the whole text, which Story Upgrades hands it for that field (VvfpStoryPopupFullText).

Proofs, in each of the three games:
  * STORY UPGRADES (its test build in the emulator, the game's own executable): a 2,500-byte one-popup event, plain
    and as a question, through the game's own pick site: the string table's text is the whole text's first 1,999
    bytes; the game's OWN text routine (0x4185A0 / 0x416F60 / 0x417700, with its formatter) fills the dialog's field
    with exactly those bytes and never touches the byte after the field; VvfpStoryPopupFullText(field) is the whole
    text; an answer's text (choice_result) the same; the text never holds '{' (the game's placeholders), so the
    field is the text's own start; a short text is the string table's text itself and the export answers NULL;
  * WITHOUT Scrolling Popups the same event is paged as before, every page under the game's 2,000;
  * SCROLLING POPUPS (its test build on each published build, tests/scrolling_popups_emulation.py: the dialog's own
    constructor tail, measure site, panel and body draws): the constructor's measure and the draw receive the whole
    text (never the field), the field stays 1,999 bytes, the panel is capped and the scrollbars are drawn, and the
    scroll reaches the whole text's end; the villager's picture (one popup) is drawn whole at the top of the scrolled
    box above the long text and moves with it; with no export (an older or no Story Upgrades) and for a stock text
    (the game's own events) everything is drawn exactly as before;
  * THE PATCHER'S CHECK: 8,000 bytes with scrolling in every game; without scrolling 1,990 a page as before.
"""
from __future__ import annotations

import functools
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import vv_cie_graph as cg  # noqa: E402
from test_story_custom_island_event import HAVE_EMULATOR, SELECT, TEXT_BUF, emulated, have_stock  # noqa: E402

if HAVE_EMULATOR:
    from story_emulator import HEAP
    from test_story_cie_graph_runtime import IDLE, DONE, Run
    from unicorn import UC_HOOK_CODE

GAMES = ("vv3", "vv4", "vv5")
FIELD = 0x58                      # the dialog's text field: 2,000 bytes, +0x58 .. +0x827
FIELD_BYTES = 2000
# The dialog's text routine and the string manager's getter it calls (its `this` is never read by the formatter).
SETTER = {"vv3": (0x4185A0, 0x42F740), "vv4": (0x416F60, 0x44DA20), "vv5": (0x417700, 0x450D40)}
RAND = {"vv3": 0x4032D0, "vv4": 0x4036D0, "vv5": 0x403660}
PEOPLE = [(0, "f", 30, "Kalani"), (1, "m", 34, "Makoa"), (2, "f", 8, "Ana"), (3, "m", 40, "Cal")]


def _waves(first: int, count: int) -> str:
    return " ".join(f"Wave {k}: the {{Sea.1}} water rolls along the shore and over the old stones." for k in
                    range(first, first + count))


def long_graph(question: bool = False) -> dict:
    """An event whose one popup is well over 2,000 bytes: two long parts (and, as a question, a long answer)."""
    nodes = {
        "a": {"text": "(Name) walks down to the shore at dawn. " + _waves(1, 18), "children": [{"next": "b"}]},
        "b": {"text": _waves(19, 18) + " (Name) counts every one of them.", "children": []},
    }
    if question:
        nodes["b"] = {"type": "question", "text": _waves(19, 18) + " What should (Name) do?",
                      "choices": [{"label": "Keep counting", "next": "c"}, {"label": "Go home", "next": "d"}]}
        nodes["c"] = {"text": _waves(40, 18), "children": [{"next": "c2"}]}
        nodes["c2"] = {"text": _waves(58, 18), "effects": [{"do": "food", "amount": 5}]}
        nodes["d"] = {"text": "(Name) goes home.", "effects": [{"do": "food", "amount": 1}]}
    else:
        nodes["b"]["effects"] = [{"do": "food", "amount": 5}]
        del nodes["b"]["children"]
    return {"format": "vvfp-cie-graph", "version": 6, "title": "The Long Tide", "games": [3, 4, 5],
            "roles": {"subject": {"kind": "villager", "min_age": 14}},
            "pools": {"Sea": {"items": ["calm", "grey", "quiet"]}}, "start": "a", "nodes": nodes}


@functools.lru_cache(maxsize=None)
def long_cieg(question: bool = False, scrolling: bool = True) -> bytes:
    return cg.compile_graph(cg.load(long_graph(question), scrolling=scrolling))


def games():
    for game in GAMES:
        if have_stock(game):
            yield game


class ThePatchersCheck(unittest.TestCase):
    """src/vv_cie_graph.py: one popup holds 8,000 bytes with scrolling in every game; 1,990 a page without."""

    def test_eight_thousand_with_scrolling_in_every_game(self):
        self.assertEqual(cg.ONE_POPUP_TEXT_MAX, 8000)
        for question in (False, True):
            g, problems = cg.validate(long_graph(question), True)
            self.assertEqual([p for p in problems if "bytes" in p], [], problems)
            longest = max(len(pop.worst) for ctx in cg.contexts(g) for h in cg.walk(g, ctx)
                          for pop in cg.one_popup(h.popups))
            self.assertGreater(longest, 2500, "a popup well over the later games' 2,000")

    def test_over_eight_thousand_is_refused(self):
        data = long_graph()
        nodes = {}
        for k in range(6):
            nodes[f"n{k}"] = {"text": _waves(100 * k, 22), "children": [{"next": f"n{k + 1}"}]}
        nodes["n5"].pop("children")
        data["nodes"] = nodes
        data["start"] = "n0"
        _g, problems = cg.validate(data, True)
        for game in ("The Secret City", "The Tree of Life", "New Believers"):
            self.assertTrue(any(p.startswith(game) and "longer than 8000 bytes" in p for p in problems), problems)

    def test_braces_are_never_text(self):
        """The game's formatter expands '{...}' in the text it copies; an event's text can never hold one (only as
        a placeholder, filled in before the popup is shown)."""
        self.assertFalse(cg.text_char_ok("{"))
        self.assertFalse(cg.text_char_ok("}"))


@emulated
class StoryHandsTheWholeText(unittest.TestCase):
    """Story Upgrades' test build, the game's own pick site and text routine."""

    def start(self, game, data, scroll=1):
        r = Run(game, people=PEOPLE)
        r.reset()
        r.rolls([0] * 60)
        r.p.export("VvfpStoryProbeGraphScroll", scroll)
        r.p.put32(r.counter_va(), 5)
        self.assertIsNone(r.queue(data))
        return r

    def at_site(self, r):
        """The game's pick site hands the presenter the armed event's object (ObjectDeliveryTests' way)."""
        table, site, resume, register, *_ = SELECT[r.game]
        p = r.p
        rand = RAND[r.game]
        if rand not in p.stubs:      # the game's own rand(bound) needs its CRT's thread data: 0
            p.stub(rand, lambda q: (0, 0))
            p.mu.hook_add(UC_HOOK_CODE, p._on_code, begin=rand, end=rand)
        if not r.state()["armed"]:
            self.assertEqual(p.export("VvfpStoryProbeGraphArmNext", r.n), 1)
        for slot in range(1, 58):
            p.put32(table + 4 * slot, p.alloc(0x20))
        p.set_reg("esi", 5)
        p.set_reg("esp", HEAP + 0x3000000)
        p.run(site, resume, limit=20_000_000)
        obj = p.reg(register)
        self.assertEqual(obj, p.export("VvfpStoryProbeObject"), "the event's own object")
        return obj

    def method(self, r, obj, offset, *args):
        return r.p.call(r.p.u32(r.p.u32(obj) + offset), list(args), ecx=obj)

    def lookup(self, r, string_id) -> str:
        return r.p.cstring(r.p.call(SELECT[r.game][4], [string_id]), 20000)

    def dialog(self, r, obj):
        """A dialog as the presenter's constructor has it when it calls its text routine: no villager pictures, the
        event; its field and the bytes after it filled with 0xCC."""
        p = r.p
        dlg = p.alloc(0x900)
        p.write(dlg, b"\xCC" * 0x900)
        for field in (0x834, 0x838):
            p.put32(dlg + field, 0)
        p.put32(dlg + 0x50, obj)
        setter, getter = SETTER[r.game]
        if getter not in p.stubs:
            manager = p.alloc(0x40)
            p.stub(getter, lambda q: (manager, 0))
            p.mu.hook_add(UC_HOOK_CODE, p._on_code, begin=getter, end=getter)
        return dlg

    def set_text(self, r, dlg, string_id) -> bytes:
        """The game's own text routine on the dialog; the field's bytes (and the 8 after it)."""
        r.p.call(SETTER[r.game][0], [string_id], ecx=dlg, limit=20_000_000)
        return r.p.read(dlg + FIELD, FIELD_BYTES + 8)

    def full_of(self, r, va) -> str | None:
        at = r.p.export("VvfpStoryPopupFullText", va)
        return r.p.cstring(at, 20000) if at else None

    def assert_cut_and_whole(self, r, dlg, string_id, expect_in=()):
        shown = self.lookup(r, string_id)
        self.assertEqual(len(shown), FIELD_BYTES - 1, "the string table's text: the first 1,999 bytes")
        raw = self.set_text(r, dlg, string_id)
        self.assertEqual(raw.index(b"\0"), FIELD_BYTES - 1, "the field holds 1,999 bytes and its NUL")
        self.assertEqual(raw[FIELD_BYTES:], b"\xCC" * 8, "nothing written past the field")
        self.assertEqual(raw[:FIELD_BYTES - 1].decode("latin-1"), shown, "the game's copy is the text's own start")
        whole = self.full_of(r, dlg + FIELD)
        self.assertIsNotNone(whole, "Scrolling Popups is given the whole text")
        self.assertGreater(len(whole), 2500)
        self.assertTrue(whole.startswith(shown))
        self.assertNotIn("{", whole, "the engine's final text holds no '{': names and pools are filled in")
        self.assertNotIn("}", whole)
        for words in expect_in:
            self.assertIn(words, whole)
        return whole

    def test_a_plain_event_of_2500_bytes(self):
        for game in games():
            with self.subTest(game=game):
                r = self.start(game, long_cieg())
                obj = self.at_site(r)
                body = self.method(r, obj, 0x0C)
                self.assertEqual(body, SELECT[game][7])
                dlg = self.dialog(r, obj)
                whole = self.assert_cut_and_whole(r, dlg, body, ("Wave 1:", "Wave 36:", "counts every one of them"))
                self.assertTrue(whole.rstrip().endswith("."), whole[-200:])
                self.assertTrue(any(name in whole for name in ("Kalani", "Makoa", "Cal")), "(Name) filled in")
                self.assertNotIn("(Name)", whole)

    def test_a_question_of_2500_bytes_and_its_long_answer(self):
        """The question (one popup: the intro and the question, one text) and its answer are written whole by the
        engine (the presenter's object hands them through ce_popup_text exactly as the plain event's above)."""
        for game in games():
            with self.subTest(game=game):
                r = self.start(game, long_cieg(True))
                if not r.state()["armed"]:
                    self.assertEqual(r.p.export("VvfpStoryProbeGraphArmNext", r.n), 1)
                p = r.p
                p.write(TEXT_BUF, b"\0")
                self.assertEqual(p.call(p.exports["VvfpStoryProbeChoiceBegin"], [r.n, TEXT_BUF, 20000],
                                        limit=50_000_000), 1)
                question = p.cstring(TEXT_BUF, 20000)
                self.assertGreater(len(question), 2500)
                for words in ("Wave 1:", "Wave 36:", "What should"):
                    self.assertIn(words, question)
                self.assertNotIn("{", question)
                p.write(TEXT_BUF, b"\0")
                self.assertEqual(p.call(p.exports["VvfpStoryProbeChoiceResolve"], [r.n, 0, TEXT_BUF, 20000],
                                        limit=50_000_000), 1)
                answer = p.cstring(TEXT_BUF, 20000)
                self.assertGreater(len(answer), 2500, "the answer's text, whole")
                self.assertTrue(answer.startswith("Keep counting\n\n"), answer[:80])
                self.assertIn("Wave 75:", answer)
                self.assertNotIn("{", answer)

    def test_a_short_text_is_the_table_s_own_text(self):
        """A short event (the custom events and stock-length ones): the string table carries the text itself, the
        export answers NULL for the field, and nothing changes."""
        short = cg.compile_graph(cg.load({
            "format": "vvfp-cie-graph", "version": 6, "title": "A Calm Sea", "games": [3, 4, 5],
            "roles": {"subject": {"kind": "villager", "min_age": 14}}, "start": "a",
            "nodes": {"a": {"text": "(Name) watches a calm sea.", "effects": [{"do": "food", "amount": 3}]}}},
            scrolling=True))
        for game in games():
            with self.subTest(game=game):
                r = self.start(game, short)
                obj = self.at_site(r)
                body = self.method(r, obj, 0x0C)
                dlg = self.dialog(r, obj)
                shown = self.lookup(r, body)
                self.assertIn("watches a calm sea.", shown)
                raw = self.set_text(r, dlg, body)
                self.assertEqual(raw[:raw.index(b"\0")].decode("latin-1"), shown)
                self.assertIsNone(self.full_of(r, dlg + FIELD), "the field is the whole text")

    def test_the_export_answers_only_a_cut_prefix(self):
        for game in games():
            with self.subTest(game=game):
                r = self.start(game, long_cieg())
                obj = self.at_site(r)
                whole = self.full_of(r, self._field_of(r, obj))
                probe = r.p.alloc(FIELD_BYTES + 16)
                for text, why in ((whole[:1998], "shorter than the cut"), (whole[:1000], "a short start"),
                                  ("X" + whole[1:1999], "not its start"), ("", "empty")):
                    r.p.write(probe, text.encode("latin-1") + b"\0")
                    self.assertIsNone(self.full_of(r, probe), why)
                self.assertEqual(r.p.export("VvfpStoryPopupFullText", 0), 0, "NULL")

    def _field_of(self, r, obj):
        dlg = self.dialog(r, obj)
        self.set_text(r, dlg, self.method(r, obj, 0x0C))
        return dlg + FIELD

    def test_without_scrolling_popups_it_is_paged_as_before(self):
        for game in games():
            with self.subTest(game=game):
                r = self.start(game, long_cieg(scrolling=False), scroll=0)
                p, shown = r.p, []
                for _ in range(12):
                    if r.state()["phase"] in (IDLE, DONE):
                        break
                    if not r.state()["armed"]:
                        self.assertEqual(p.export("VvfpStoryProbeGraphArmNext", r.n), 1)
                    p.put32(r.counter_va(), p.u32(r.counter_va()) + 1)
                    p.write(TEXT_BUF, b"\0")
                    self.assertEqual(p.call(p.exports["VvfpStoryProbeDeliver"], [r.n, TEXT_BUF, 9000],
                                            limit=50_000_000), 1)
                    shown.append(p.cstring(TEXT_BUF, 20000))
                self.assertGreater(len(shown), 1, "paged")
                for text in shown:
                    self.assertLess(len(text.encode("latin-1")), FIELD_BYTES, len(text))
                    self.assertNotIn("{", text)
                words = " ".join(" ".join(t.split()) for t in shown)
                self.assertIn("Wave 1:", words)
                self.assertIn("counts every one of them", words, "nothing cut: the last words on the last page")
                self.assertIn(r.state()["phase"], (IDLE, DONE))


try:
    import test_scrolling_popups as tsp
    HAVE_SP = tsp.HAVE_EMULATOR and tsp.HAVE_STOCK and tsp.HAVE_IMAGES and tsp.TEST_DLL.is_file()
except Exception:  # pragma: no cover - environment dependent
    HAVE_SP = False

LONG = ("(The first words.) " + " ".join(
    f"Wave {k}: the grey water rolls along the shore and over the old stones." for k in range(1, 40))
    + " The very last words of the event.").encode("latin-1")
SHORT = b"Your tribe finds a basket of fruit by the shore."


@unittest.skipUnless(HAVE_SP, "needs unicorn, the stock executables, the game images and the test build")
class ScrollingPopupsDrawTheWholeText(unittest.TestCase):
    dialogs: dict = {}

    @classmethod
    def setUpClass(cls) -> None:
        import scrolling_popups_emulation as spe
        cls.spe = spe
        for game in (3, 4, 5):
            cls.dialogs[game] = spe.Dialog(f"vv{game}")

    @classmethod
    def tearDownClass(cls) -> None:
        cls.dialogs.clear()

    def make(self, d, text, whole=True, rows=True, portrait=False):
        d.set_full_text(text if whole else None)
        op = None
        if rows:
            op = {"labels": [b"Keep counting", b"Go home"], "reserve": 5 * d.picture_of(d.g["ok_id"])[2] // 2}
        d.make(text, one_popup=op, portrait=portrait)
        return d

    def test_the_draw_and_the_measure_receive_the_whole_text(self):
        self.assertGreater(len(LONG), 2500)
        for game, d in self.dialogs.items():
            with self.subTest(game=game):
                # The constructor's own height without the export (the field: 1,999 bytes) and with it (the whole).
                self.make(d, LONG, whole=False)
                cut_height = d.stock_height
                calls = d.record_justify()
                self.make(d, LONG)
                field = d.dialog + 0x58
                self.assertEqual(bytes(d.mu.mem_read(field, FIELD_BYTES)).index(b"\0"), FIELD_BYTES - 1,
                                 "the dialog's field stays 1,999 bytes")
                self.assertIn(field, d.full_asks, "the companion asked for the field's whole text")
                self.assertIn((d.full_va, 1), calls, "the constructor's measure got the whole text")
                self.assertNotIn((field, 1), calls)
                _bx, _by, bw = d.box()
                grown = d.justify_height_widened(d.full_va, bw) - d.justify_height_widened(field, bw)
                self.assertGreater(grown, 0)
                self.assertEqual(d.stock_height - cut_height, grown, "the panel asked for the whole text's height")
                calls.clear()
                blits = d.draw()
                drawn = [t for t, m in calls if m == 0]
                self.assertIn(d.full_va, drawn, "the draw got the whole text")
                self.assertNotIn(field, drawn, "never the field")
                v = d.view()
                self.assertEqual(v["vbar"], 1)
                art = d.art_blits(blits)
                for name in ("up", "down", "track", "knob"):
                    self.assertIn(name, art, "the scrollbars are drawn")
                self.assertGreaterEqual(v["content_h"], d.justify_height_widened(d.full_va, v["box_w"]))
                # Scrolled to the end: the whole text's last line comes into the box.
                left, top, right, bottom = d.panel()
                d.mouse(1, (left + right) // 2, (top + bottom) // 2)
                last = -1
                for _ in range(200):
                    d.wheel(-3)
                    d.draw()
                    sy = d.view()["sy"]
                    if sy == last:
                        break
                    last = sy
                v = d.view()
                self.assertEqual(v["sy"], v["content_h"] - v["box_h"], "the scroll reaches the whole text's end")
                self.assertGreater(v["sy"] + v["box_h"], d.justify_height_widened(field, v["box_w"]),
                                   "past the field's 1,999 bytes")

    def test_the_villager_s_picture_above_the_long_text(self):
        for game, d in self.dialogs.items():
            with self.subTest(game=game):
                self.make(d, LONG, portrait=True)
                d.portrait_calls.clear()
                blits = d.draw()
                v = d.view()
                self.assertEqual(v["vbar"], 1)
                pics = d.portrait_blits(blits)
                self.assertEqual(len(pics), 1, "the picture drawn once")
                x, y, w, h = pics[0][3]
                self.assertEqual((w, h), (self.spe.PORTRAIT_W, self.spe.PORTRAIT_H), "whole at the top")
                self.assertTrue(v["box_x"] <= x and x + w <= v["box_x"] + v["box_w"] and v["box_y"] <= y
                                and y + h <= v["box_y"] + v["box_h"], (pics[0][3], v))
                seen = d.opaque_box(pics[0])
                self.assertTrue(any(g[3][1] >= seen[3] for g in d.text_blits(blits)), "the text after it")
                rows = d.view_rows()
                self.assertGreaterEqual(rows["y"], seen[3])
                y0 = d.portrait_calls[-1][1]
                left, top, right, bottom = d.panel()
                d.mouse(1, (left + right) // 2, (top + bottom) // 2)
                d.wheel(-1)
                d.portrait_calls.clear()
                d.draw()
                self.assertEqual(d.portrait_calls[-1][1], y0 - d.view()["sy"], "it moves with the long text")

    def test_without_the_export_the_field_is_drawn_as_before(self):
        for game, d in self.dialogs.items():
            with self.subTest(game=game):
                self.make(d, LONG, whole=False)
                calls = d.record_justify()
                d.draw()
                self.assertIn(d.dialog + 0x58, [t for t, m in calls if m == 0], "the field, as before")

    def test_a_stock_text_is_drawn_exactly_as_before(self):
        for game, d in self.dialogs.items():
            for rows in (False, True):
                with self.subTest(game=game, rows=rows):
                    self.make(d, SHORT, whole=False, rows=rows)
                    before = [(b[1], b[3]) for b in d.draw()]
                    height = d.stock_height
                    self.make(d, SHORT, whole=True, rows=rows)    # the export present: it answers NULL
                    self.assertEqual(d.stock_height, height)
                    calls = d.record_justify()
                    self.assertEqual([(b[1], b[3]) for b in d.draw()], before)
                    self.assertIn(d.dialog + 0x58, [t for t, m in calls if m == 0])


if __name__ == "__main__":
    unittest.main()
