"""The simple in-game event editor's text, its button labels and Custom Island Event death causes: practically
unlimited with Scrolling Popups (the owner, 2026-11-17), all five games.

The owner: with Scrolling Popups on, the simple Custom Island Event editor's text, its button labels and a branching
event's death cause become practically unlimited, as PR #776 made the library events' texts; without Scrolling
Popups the old caps stay and the editor says why.  Every popup scrolls; only a single word wider than the screen
matters.

  * native/vvfp_story_upgrades/story_custom.h: ce_event.text holds CE_TEXT_STORE (100,000) bytes and a label
    CE_LABEL_STORE (4,096); the old caps (CE_TEXT_BYTES 600, CE_BUTTON_BYTES 40) stay without Scrolling Popups
    (story_custom.inc ce_text_cap / ce_label_cap / ce_text_cap_refusal, the editor's EM_LIMITTEXT and counters).
  * A simple question runs in ONE popup with Scrolling Popups (story_custom.inc ce_choice_begin, ce_op_simple): its
    choices are rows after the text (story_graph.inc cg_op_rows / cg_label), so a long label wraps in its own row;
    the result replaces the text in the same popup, led by the label picked.
  * story_queue.inc: the queue file is version 2; version 1 files (written before) are still read -- the pinned
    files in tests/story_queue_v1_files.json were written by the version 1 test build itself (ground truth).
  * Death causes: story_graph.inc cg_cause_bytes; "VVFP Cause of Death.dll" keeps the words whole (its words file
    version 2, version 1 still read: native/vvfp_cause_of_death/cause_files_harness.c), on the later games' graves
    (tests/test_cie_words_on_later_graves.py) and in the Deaths log; src/vv_cie_graph.py cause_cap.

EMULATED (unicorn, the stock executables, the TEST build of the companion).
"""
from __future__ import annotations

import base64
import json
import struct
import sys
import unittest
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import vv_cie_graph as cg  # noqa: E402
from story_custom_fixtures import Choice, Event, Outcome  # noqa: E402
from test_story_custom_island_event import EVENT_BUF, GAMES, HAVE_EMULATOR, emulated, have_stock  # noqa: E402

if HAVE_EMULATOR:
    import test_story_queued_purchases as q
    from test_story_two_choice import CHOICE_BUF, _story

STEPS = 2_000_000_000
BIG = 0x30000
SQ_CUSTOM, SQ_ASKED = 2, 16
V1_FILES = ROOT / "tests" / "story_queue_v1_files.json"
WORDS = ("The tide rolled in over the black sand while the elders told the story of the first canoe, and the "
         "children listened with wide eyes. ")


def big(p, name: str, *args: int) -> int:
    return p.call(p.exports[name], list(args), limit=STEPS)


def story_text(chars: int, end: str = "THE VERY LAST WORDS.") -> str:
    body = (WORDS * (chars // len(WORDS) + 1))[:chars - len(end) - 2]
    return body.rsplit(" ", 1)[0] + " " + end


def long_label(chars: int, k: int) -> str:
    words = "Walk along the long path past the singing stones and the old fishing nets to the reef "
    return (f"Choice {k + 1}: " + words * (chars // len(words) + 2))[:chars].rsplit(" ", 1)[0] + f" end{k + 1}"


def flat(text: str) -> str:
    return " ".join(text.split())


def write(story, event: Event, choice: Choice | None = None) -> None:
    event.game = story.n
    story.proc.write(EVENT_BUF, event.pack())
    if choice is not None:
        story.proc.write(CHOICE_BUF, choice.pack())


def choice_refusal(story, event: Event, choice: Choice) -> str | None:
    write(story, event, choice)
    at = big(story.proc, "VvfpStoryProbeChoiceRefusal", story.n, EVENT_BUF, CHOICE_BUF)
    return None if at == 0 else story.proc.cstring(at)


def plain_refusal(story, event: Event) -> str | None:
    write(story, event)
    at = big(story.proc, "VvfpStoryProbeRefusal", story.n, EVENT_BUF)
    return None if at == 0 else story.proc.cstring(at)


def long_choice(labels=(long_label(300, 0), long_label(300, 1)), result_chars: int = 6000) -> Choice:
    return Choice(labels=labels,
                  outcomes=((Outcome(1, Event(title="", text="Left: " + story_text(result_chars, "LEFT ENDS."))),),
                            (Outcome(1, Event(title="", text="Right: " + story_text(result_chars, "RIGHT ENDS."))),)))


class TheCapsInTheSource(unittest.TestCase):
    def test_fields_and_caps(self):
        h = (ROOT / "native/vvfp_story_upgrades/story_custom.h").read_text(encoding="utf-8")
        self.assertIn("#define CE_TEXT_BYTES 600", h, "the old cap stays (without Scrolling Popups)")
        self.assertIn("#define CE_TEXT_STORE CE_LONG_TEXT_MAX", h)
        self.assertIn("#define CE_LABEL_STORE CE_LONG_LINE_BYTES", h)
        self.assertIn("char text[CE_TEXT_STORE];", h)
        self.assertIn("char labels[2][CE_LABEL_STORE];", h)
        self.assertEqual((Event.TEXT_BYTES, Choice.BUTTON_BYTES), (cg.LONG_TEXT_MAX, cg.LONG_LINE_BYTES + 1))

    def test_the_editor_explains_without_scrolling_popups(self):
        ui = (ROOT / "native/vvfp_story_upgrades/story_custom_ui.inc").read_text(encoding="utf-8")
        self.assertIn("EM_LIMITTEXT, (WPARAM)(ce_text_cap() - 1)", ui)
        self.assertIn("int width = ce_label_cap(ui.a);", ui)
        self.assertIn("too long without Scrolling Popups", ui)
        self.assertIn("characters in %s without the Scrolling Popups patch (with it, ", ui)

    def test_the_validator_and_the_library_window_count_causes_by_scrolling(self):
        g = {"format": "vvfp-cie-graph", "version": 6, "title": "The Long Fall", "games": [1, 2, 3, 4, 5],
             "roles": {"v": {"kind": "villager"}}, "start": "a",
             "nodes": {"a": {"text": "(v) fell.", "effects": [{"do": "kill", "role": "v",
                                                                "cause": story_text(2000, "at the end.")}]}}}
        _g, problems = cg.validate(g, scrolling=True)
        self.assertFalse([p for p in problems if "cause" in p], problems)
        _g, problems = cg.validate(g, scrolling=False)
        self.assertTrue(any("cause" in p and f"up to {cg.CAUSE_BYTES}" in p and "Scrolling Popups" in p
                            for p in problems), problems)
        g["nodes"]["a"]["effects"][0]["cause"] = "Go " * 1400
        _g, problems = cg.validate(g, scrolling=True)
        self.assertTrue(any(f"up to {cg.LONG_LINE_BYTES}" in p for p in problems), "the sanity cap holds")
        import vv_cie_library_window as lw
        self.assertEqual(lw.cause_count(70, False)[1], cg.CAUSE_BYTES)
        self.assertIn("without the Scrolling Popups patch", lw.cause_count(70, False)[0])
        self.assertEqual(lw.cause_count(2000, True)[1], cg.LONG_LINE_BYTES)


@emulated
class TheEditorsTextAndLabels(unittest.TestCase):
    def stories(self, scroll: int):
        for game in GAMES:
            if have_stock(game):
                story = _story(game)
                story.proc.export("VvfpStoryProbeGraphScroll", scroll)
                yield game, story

    def test_with_scrolling_popups_text_and_labels_are_practically_unlimited(self):
        question = Event(title="The Long Tide", text=story_text(12000))
        for game, story in self.stories(1):
            with self.subTest(game=game):
                self.assertIsNone(choice_refusal(story, question, long_choice()))
                # A plain event's description: refused (or not) for the same reasons as a short one -- never its length.
                self.assertEqual(plain_refusal(story, Event(title="The Long Tide", text=story_text(12000))),
                                 plain_refusal(story, Event(title="The Long Tide", text="Short.")))

    def test_the_question_runs_in_one_popup_with_its_whole_labels_and_texts(self):
        question = Event(title="The Long Tide", text=story_text(12000))
        for game, story in self.stories(1):
            with self.subTest(game=game):
                p = story.proc
                choice = long_choice()
                write(story, question, choice)
                self.assertEqual(p.export("VvfpStoryProbeSetChoice", story.n, EVENT_BUF, CHOICE_BUF, 0), 1)
                buf = p.alloc(BIG)
                self.assertEqual(big(p, "VvfpStoryProbeChoiceBegin", story.n, buf, BIG), 1)
                text = flat(p.cstring(buf))
                self.assertIn("THE VERY LAST WORDS.", text, "the whole question, never cut at 600")
                self.assertEqual(big(p, "VvfpStoryProbeOnePopupBegun", story.n), 1, "the host takes one popup")
                self.assertEqual(big(p, "VvfpStoryProbeOnePopupRows", story.n), 2, "two choice rows")
                for k in range(2):
                    self.assertEqual(p.cstring(big(p, "VvfpStoryProbeChoiceLabel", story.n, k)), choice.labels[k],
                                     "the label whole (its row wraps it)")
                p.write(buf, b"\0")
                self.assertEqual(big(p, "VvfpStoryProbeChoiceResolve", story.n, 1, buf, BIG), 1)
                result = flat(p.cstring(buf))
                self.assertIn("RIGHT ENDS.", result, "the whole result")
                self.assertIn(flat(choice.labels[1]), result, "the choice picked leads the result")
                self.assertLess(result.index(flat(choice.labels[1])), result.index("Right:"))
                self.assertEqual(big(p, "VvfpStoryProbeOnePopupRows", story.n), 0, "then OK")
                p.write(buf, b"\0")
                self.assertEqual(big(p, "VvfpStoryProbeOnePopupOk", story.n, buf, BIG), 0, "OK ends it")

    def test_without_scrolling_popups_the_old_caps_stay_and_say_why(self):
        for game, story in self.stories(0):
            with self.subTest(game=game):
                why = plain_refusal(story, Event(title="Tide", text=story_text(700)))
                self.assertIn("599", why or "")
                self.assertIn("Scrolling Popups", why or "")
                why = choice_refusal(story, Event(title="Tide", text="Which way?"),
                                     long_choice(labels=(long_label(60, 0), "No"), result_chars=40))
                self.assertIn("First button", why or "")
                self.assertIn("Scrolling Popups", why or "")
                why = choice_refusal(story, Event(title="Tide", text=story_text(700)), long_choice(("Yes", "No"), 40))
                self.assertIn("Scrolling Popups", why or "")
                # A short question is asked as before: the game's own two-button popup, not one popup.
                p = story.proc
                choice = long_choice(("Yes", "No"), 40)
                write(story, Event(title="Tide", text="Which way?"), choice)
                self.assertEqual(p.export("VvfpStoryProbeSetChoice", story.n, EVENT_BUF, CHOICE_BUF, 0), 1)
                buf = p.alloc(BIG)
                self.assertEqual(big(p, "VvfpStoryProbeChoiceBegin", story.n, buf, BIG), 1)
                self.assertEqual(big(p, "VvfpStoryProbeOnePopupBegun", story.n), 0)
                self.assertEqual(big(p, "VvfpStoryProbeOnePopupRows", story.n), 0)

    def test_a_single_word_wider_than_the_screen_is_still_refused(self):
        for game, story in self.stories(1):
            with self.subTest(game=game):
                why = choice_refusal(story, Event(title="Tide", text="Which way?"),
                                     long_choice(labels=("W" * 120, "No"), result_chars=40))
                self.assertIn("wider than the screen", why or "")
                self.assertIsNone(choice_refusal(story, Event(title="Tide", text="Which way?"),
                                                 long_choice(labels=("Wade " * 24, "No"), result_chars=40)),
                                  "many short words: only the length is free")


@emulated
class TheQueueFile(unittest.TestCase):
    def test_version_1_files_written_before_still_load(self):
        files = json.loads(V1_FILES.read_text(encoding="utf-8"))
        for game in GAMES:
            if not have_stock(game):
                continue
            for kind in ("plain", "question"):
                with self.subTest(game=game, kind=kind):
                    data = zlib.decompress(base64.b64decode(files[f"{game}_{kind}"]))
                    self.assertEqual(struct.unpack_from("<I", data, 4)[0], 1, "a version 1 file")
                    again = q.fresh(game)
                    again.proc.export("VvfpStoryProbeChoiceCap", 1)
                    q.session(again, data, q.LATE)
                    q.tick(again)
                    s = q.state(again)
                    self.assertEqual((s["custom"], s["question"]), (1, int(kind == "question")),
                                     "the event queued before the upgrade is put back")
                    p = again.proc
                    buf = p.alloc(BIG)
                    if kind == "plain":
                        self.assertEqual(big(p, "VvfpStoryProbeDeliver", again.n, buf, BIG), 1)
                        self.assertIn("every villager watched it", p.cstring(buf))
                    else:
                        self.assertEqual(big(p, "VvfpStoryProbeChoiceBegin", again.n, buf, BIG), 1)
                        self.assertIn("every villager", p.cstring(buf))
                        self.assertEqual(p.cstring(big(p, "VvfpStoryProbeChoiceLabel", again.n, 0)),
                                         "Wade out into the old tide now")
                        self.assertEqual(p.cstring(big(p, "VvfpStoryProbeChoiceLabel", again.n, 1)),
                                         "Stay on the warm dry beach")
                        q.tick(again)
                        now = q.queue_file(again)
                        self.assertEqual(struct.unpack_from("<I", now, 4)[0], 2, "rewritten as version 2")
                        self.assertEqual(q.have(now, again) & (SQ_CUSTOM | SQ_ASKED), SQ_CUSTOM | SQ_ASKED)

    def test_a_long_question_survives_a_quit_whole(self):
        for game in GAMES:
            if not have_stock(game):
                continue
            with self.subTest(game=game):
                story = q.fresh(game)
                p = story.proc
                p.export("VvfpStoryProbeChoiceCap", 1)
                p.export("VvfpStoryProbeGraphScroll", 1)
                choice = long_choice(result_chars=3000)
                packed = choice.pack()
                at = p.alloc(len(packed))
                p.write(at, packed)
                p.write(EVENT_BUF, Event(game=story.n, title="The Long Tide", text=story_text(9000)).pack())
                self.assertEqual(p.export("VvfpStoryProbeSetChoice", story.n, EVENT_BUF, at, p.tick), 1)
                q.tick(story)
                data = q.queue_file(story)
                self.assertEqual(struct.unpack_from("<I", data, 4)[0], 2)
                p.export("VvfpStoryProbeQueueSaved")
                again = q.fresh(game)
                again.proc.export("VvfpStoryProbeChoiceCap", 1)
                again.proc.export("VvfpStoryProbeGraphScroll", 1)
                q.session(again, data, q.LATE)
                q.tick(again)
                self.assertEqual(q.state(again)["question"], 1)
                buf = again.proc.alloc(BIG)
                self.assertEqual(big(again.proc, "VvfpStoryProbeChoiceBegin", again.n, buf, BIG), 1)
                self.assertIn("THE VERY LAST WORDS.", flat(again.proc.cstring(buf)))
                self.assertEqual(again.proc.cstring(big(again.proc, "VvfpStoryProbeChoiceLabel", again.n, 1)),
                                 choice.labels[1])

    def test_a_malformed_file_is_never_misread(self):
        files = json.loads(V1_FILES.read_text(encoding="utf-8"))
        game = next((g for g in GAMES if have_stock(g)), None)
        if game is None:
            self.skipTest("no stock executable")
        data = bytearray(zlib.decompress(base64.b64decode(files[f"{game}_question"])))
        for name, bad in (("cut short", bytes(data[:-10])),
                          ("another layout", bytes(data[:20]) + struct.pack("<I", 1234) + bytes(data[24:])),
                          ("an unknown version", bytes(data[:4]) + struct.pack("<I", 3) + bytes(data[8:]))):
            with self.subTest(name=name):
                again = q.fresh(game)
                again.proc.export("VvfpStoryProbeChoiceCap", 1)
                q.session(again, bad, q.LATE)
                q.tick(again)
                self.assertEqual(q.state(again)["custom"], 0, "nothing put back from it")


@emulated
class TheDeathCause(unittest.TestCase):
    def test_a_long_cause_loads_only_with_scrolling_popups(self):
        g = {"format": "vvfp-cie-graph", "version": 6, "title": "The Long Fall", "games": [1, 2, 3, 4, 5],
             "roles": {"v": {"kind": "villager"}}, "start": "a",
             "nodes": {"a": {"text": "(v) fell.", "effects": [{"do": "kill", "role": "v",
                                                                "cause": story_text(2000, "at the end.")}]}}}
        data = cg.compile_graph(cg.load(g, scrolling=True))
        from test_story_cie_graph_runtime import Run
        for game in GAMES:
            if not have_stock(game):
                continue
            with self.subTest(game=game):
                r = Run(game)
                buf = r.p.alloc(len(data) + 16)
                r.p.write(buf, data)
                r.p.export("VvfpStoryProbeGraphScroll", 1)
                at = big(r.p, "VvfpStoryProbeGraphCheck", buf, len(data))
                self.assertEqual(at, 0, r.p.cstring(at) if at else "")
                r.p.export("VvfpStoryProbeGraphScroll", 0)
                self.assertNotEqual(big(r.p, "VvfpStoryProbeGraphCheck", buf, len(data)), 0,
                                    "without Scrolling Popups the old 63 characters stay")


if __name__ == "__main__":
    unittest.main()
