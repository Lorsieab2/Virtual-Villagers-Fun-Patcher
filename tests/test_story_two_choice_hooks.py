"""Story / Cheat Upgrades: a Custom Island Event question in each game's OWN
two-choice popup (the delivery hooks of native/vvfp_story_upgrades).

Each game's executable as the patcher renders it (all three population
modes), with the test build of "VVFP Story Upgrades.dll" installed beside it
in the emulator; the game's own two-choice code runs for real wherever it
can run alone:

* A New Home (villager encounters) and The Lost Children (family A): the
  family rolls send a question to the two-choice family; the encounter
  setup call (0x41A51F / 0x42244A) writes the question, padded to the
  tallest result (the popup is sized once, from the question), the labels,
  no villager, the stock width and a variant past the stock jump table; the
  game's own click handler (0x41A3D0 / 0x4222F0) reaches the resolve call,
  whose outcomes scope stub hands it to the answer, which rolls, applies and
  writes the result in place of the question.  A natural encounter's setup
  and resolve are the game's own, also at the address a question used.
* The Secret City, The Tree of Life, New Believers: the pick site hands the
  presenter a two-choice event object (a stock two-choice vtable copy) whose
  methods the dialog asks; the game's own click handler (0x419A00 /
  0x417EA0 / 0x418720) calls its choice method (the answer), its result id
  and, on OK, its apply (nothing more happens).  The villager shown is a
  living one, never a Heathen in New Believers.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))

from story_custom_fixtures import Choice, Event, Outcome  # noqa: E402
from test_story_custom_island_event import (  # noqa: E402
    ADD,
    EVENT_BUF,
    MODES,
    SELECT,
    Story,
    _food_tech,
    emulated,
    have_stock,
)
from test_story_two_choice import CHOICE_BUF, CHOICE_PANEL  # noqa: E402

try:
    from story_emulator import HEAP
except ImportError:  # pragma: no cover - environment dependent
    HEAP = 0

STACK = HEAP + 0x3000000 if HEAP else 0
FOOD0 = 1000


def _outcome(text, chance=1, **kw):
    return Outcome(chance, Event(title="", text=text, **kw))


def _choice(story):
    """Left: 50/50 a small haul (+100 food) or a big one (+500); Right: Bea sick."""
    return Choice(labels=("Go fishing", "Stay home"), outcomes=(
        [_outcome("A small haul.", 50, food_op=ADD, food_amount=100),
         _outcome("A big haul.", 50, food_op=ADD, food_amount=500)],
        [_outcome("Bea fell ill.", changes=[story.change(2, sick=1)])],
    ))


RAND = {"vv1": 0x402F10, "vv2": 0x4031A0, "vv3": 0x4032D0, "vv4": 0x4036D0, "vv5": 0x403660}


def _story(game, mode="collection_progression"):
    story = Story(game, mode)
    # The game's own rand(bound) (its CRT needs the thread's TLS): the
    # bound's last value, recorded, so a roll through it is seen.
    story.rand_bounds = []

    def rand(p):
        story.rand_bounds.append(p.arg(0))
        return p.arg(0) - 1, 0
    story.proc.stub(RAND[game], rand)
    story.village.put(1, sex="m", years=30, name="Adam")
    story.village.put(2, sex="f", years=30, name="Bea")
    story.proc.put32(_food_tech(story)[0], FOOD0)
    return story


def _arm(story, title="The Strange Lights", text="Lights over the sea. What now?"):
    event = Event(title=title, text=text)
    event.game = story.n
    story.proc.write(EVENT_BUF, event.pack())
    story.proc.write(CHOICE_BUF, _choice(story).pack())
    story.proc.export("VvfpStoryProbeSetChoice", story.n, EVENT_BUF, CHOICE_BUF, 0)
    story.proc.export("VvfpStoryProbeSetTick", 0)


def _lines(text):
    return text.count("\n") + 1 if text else 0


# ---------------------------------------------------------------------------
# A New Home and The Lost Children: the two-choice family's dialog
# ---------------------------------------------------------------------------

DIALOG = {
    # setup call, stock setup, click handler, resolve call, stock resolve,
    # question, result, labels, variant, villager, choice, stock variant bound,
    # handler's sound / remove / add, first-event counter
    "vv1": dict(site=0x41A51F, setup=0x4189E0, handler=0x41A3D0, resolve_site=0x41A444,
                resolve=0x419380, q=0x74, res=0x2783, l1=0x4E92, l2=0x4F92, variant=0x5094,
                subject=0x5098, choice=0x509C, bound=15, stubs=(0x431470, 0x40ABC0, 0x40AB80),
                counter=0x9E40, rolls=((0x423818, 100), 0x402F10)),
    "vv2": dict(site=0x42244A, setup=0x41F780, handler=0x4222F0, resolve_site=0x422364,
                resolve=0x4204B0, q=0x7C, res=0x278B, l1=0x4E9A, l2=0x4F9A, variant=0x509C,
                subject=0x50A0, choice=0x50A4, bound=20, stubs=(0x43F010, 0x40B5A0, 0x40B560),
                counter=0x2E51C, rolls=((0x42EF28, 100), 0x4031A0)),
}


@emulated
class EncounterDialogTests(unittest.TestCase):
    def _dialog(self, story):
        d = DIALOG[story.game]
        p = story.proc
        dlg = p.alloc(0x5200)
        p.put32(dlg + 0x54, 2)                  # the ctor's button ids (0x41A495 / 0x4223B5)
        p.put32(dlg + 0x58, 3)
        p.put32(dlg + 0x5C, 4)
        p.put32(dlg + d["subject"], 0xFFFFFFFF)
        p.put32(dlg + d["choice"], 0xFFFFFFFF)
        for va in d["stubs"]:
            story.record_call(va, 4)
        story.record_call(d["setup"], 0, value=1)
        story.record_call(d["resolve"], 0)
        return dlg

    def _setup(self, story, dlg):
        d = DIALOG[story.game]
        p = story.proc
        p.set_reg("esp", STACK)
        p.set_reg("ecx", dlg)
        p.set_reg("ebx", 0x1111)
        p.set_reg("esi", dlg)
        p.set_reg("edi", 0x2222)
        p.set_reg("ebp", 0x3333)
        p.run(d["site"], d["site"] + 5)
        self.assertEqual(p.reg("esp"), STACK, "no stack arguments, as the stock setup")
        self.assertEqual((p.reg("ebx"), p.reg("esi"), p.reg("edi"), p.reg("ebp")),
                         (0x1111, dlg, 0x2222, 0x3333))
        return p.reg("eax") & 0xFF

    def _click(self, story, dlg, button_id, roll=-1):
        story.proc.export("VvfpStoryProbeSetRoll", roll)
        return story.proc.call(DIALOG[story.game]["handler"], [8, button_id], ecx=dlg) & 0xFF

    def _each(self, modes=("collection_progression",)):
        for game in DIALOG:
            if not have_stock(game):
                continue
            for mode in modes:
                yield game, mode, _story(game, mode)

    def test_the_question_is_the_dialogs_text_and_buttons(self):
        for game, mode, story in self._each(MODES):
            d = DIALOG[game]
            p = story.proc
            dlg = self._dialog(story)
            _arm(story)
            with self.subTest(game=game, mode=mode):
                self.assertEqual(self._setup(story, dlg), 1)
                self.assertNotIn(d["setup"], story.calls, "the game's own setup is not run")
                question = p.cstring(dlg + d["q"], 0x2710)
                self.assertTrue(question.startswith(
                    "The Strange Lights\n\n\n\nLights over the sea. What now?"), question)
                self.assertTrue(all(len(line) <= CHOICE_PANEL[game][0] for line in question.split("\n")))
                self.assertEqual((p.cstring(dlg + d["l1"]), p.cstring(dlg + d["l2"])),
                                 ("Go fishing", "Stay home"))
                self.assertGreater(p.u32(dlg + d["variant"]), d["bound"],
                                   "past the stock resolve's jump table")
                self.assertEqual(p.u32(dlg + d["subject"]), 0xFFFFFFFF, "no villager shown")
                self.assertEqual(p.u32(dlg + 0x60), 0x1C2, "the stock encounter width")
                self.assertEqual(story.proc.export("VvfpStoryProbeCustomPending", story.n), 0)
                self.assertEqual(p.u32(_food_tech(story)[0]), FOOD0, "nothing changes before a click")

    def test_each_button_rolls_applies_and_shows_its_result(self):
        for game, mode, story in self._each(MODES):
            d = DIALOG[game]
            p = story.proc
            food = _food_tech(story)[0]
            cases = ((2, 0, "A small haul.", FOOD0 + 100, 0),
                     (2, 70, "A big haul.", FOOD0 + 500, 0),
                     (3, -1, "Bea fell ill.", FOOD0, 1))
            for button_id, roll, words, food_after, bea_sick in cases:
                story = _story(game, mode)
                p = story.proc
                dlg = self._dialog(story)
                _arm(story)
                self._setup(story, dlg)
                question = p.cstring(dlg + d["q"], 0x2710)
                with self.subTest(game=game, mode=mode, button=button_id, roll=roll):
                    self.assertEqual(self._click(story, dlg, button_id, roll), 1)
                    self.assertNotIn(d["resolve"], story.calls, "the game's own resolve is not run")
                    result = p.cstring(dlg + d["res"], 0x2710)
                    self.assertTrue(result.startswith("The Strange Lights\n\n\n\n" + words), result)
                    self.assertEqual(p.u32(food), food_after)
                    self.assertEqual(story.village.sick(2), bea_sick)
                    self.assertEqual(p.read(dlg + 0x50, 1), b"\1", "the dialog draws the result")
                    self.assertLessEqual(_lines(result), _lines(question),
                                         "the popup sized from the question holds the result")
                    if button_id == 2:
                        self.assertIn("food", result)

    def test_the_question_is_padded_to_the_tallest_result(self):
        for game, mode, story in self._each():
            d = DIALOG[game]
            p = story.proc
            dlg = self._dialog(story)
            _arm(story, text="Short?")
            self._setup(story, dlg)
            question = p.cstring(dlg + d["q"], 0x2710)
            # The tallest result (Bea's): the title, three empty lines, the
            # text, an empty line, "999 of the chosen villagers were no longer
            # here." (two lines at The Lost Children's 46 characters) and
            # "999 changes could not be made.".
            skipped = 2 if CHOICE_PANEL[game][2] < 48 else 1
            with self.subTest(game=game):
                self.assertEqual(_lines(question), 1 + 3 + 1 + 1 + skipped + 1)
                self.assertEqual(question.rstrip("\n"), "The Strange Lights\n\n\n\nShort?",
                                 "only line breaks are added")

    def test_a_natural_encounter_is_the_games_own(self):
        for game, mode, story in self._each(MODES):
            d = DIALOG[game]
            dlg = self._dialog(story)
            with self.subTest(game=game, mode=mode):
                self.assertEqual(self._setup(story, dlg), 1)
                self.assertEqual(story.calls[d["setup"]], [[dlg]])
                self._click(story, dlg, 2)
                self.assertEqual(story.calls[d["resolve"]], [[dlg]])
                self.assertEqual(story.proc.u32(dlg + d["choice"]), 1)

    def test_the_dialogs_address_is_forgotten(self):
        """The dialog lives on the trigger's stack: the next encounter there
        is the game's own, whether the question was answered or not."""
        for game, mode, story in self._each():
            d = DIALOG[game]
            p = story.proc
            dlg = self._dialog(story)
            _arm(story)
            self._setup(story, dlg)
            self._setup(story, dlg)              # a natural encounter at the same address
            with self.subTest(game=game, case="setup again"):
                self.assertEqual(story.calls[d["setup"]], [[dlg]])
                self._click(story, dlg, 2)
                self.assertEqual(story.calls[d["resolve"]], [[dlg]])
                self.assertEqual(p.u32(_food_tech(story)[0]), FOOD0)
            story = _story(game)
            p = story.proc
            dlg = self._dialog(story)
            _arm(story)
            self._setup(story, dlg)
            self._click(story, dlg, 3)
            self._click(story, dlg, 2)          # the handler's resolve call again
            with self.subTest(game=game, case="answered"):
                self.assertEqual(story.calls[d["resolve"]], [[dlg]])
                self.assertEqual(p.u32(_food_tech(story)[0]), FOOD0, "answered once")

    def test_only_the_questions_dialog_is_answered(self):
        """Another dialog's resolve (another address) is the game's own even
        while a question waits."""
        for game, mode, story in self._each():
            d = DIALOG[game]
            p = story.proc
            asked = self._dialog(story)
            other = p.alloc(0x5200)
            for off, value in ((0x54, 2), (0x58, 3), (0x5C, 4)):
                p.put32(other + off, value)
            _arm(story)
            self._setup(story, asked)
            self._click(story, other, 2)
            with self.subTest(game=game):
                self.assertEqual(story.calls[d["resolve"]], [[other]])
                self.assertEqual(p.u32(_food_tech(story)[0]), FOOD0)
                self._click(story, asked, 2, 0)
                self.assertEqual(p.u32(_food_tech(story)[0]), FOOD0 + 100, "the question still answers")

    def test_a_missed_dispatch_changes_nothing(self):
        """The variant written is past the stock resolve's jump table: run the
        game's own resolve on the question's dialog and nothing is written."""
        for game, mode, story in self._each():
            d = DIALOG[game]
            p = story.proc
            dlg = self._dialog(story)
            _arm(story)
            self._setup(story, dlg)
            del story.proc.stubs[d["resolve"]]
            p.put32(dlg + d["choice"], 1)
            p.write(dlg + d["res"], b"untouched\0")
            p.call(d["resolve"], [], ecx=dlg)
            with self.subTest(game=game):
                self.assertEqual(p.cstring(dlg + d["res"]), "untouched")
                self.assertEqual(p.u32(_food_tech(story)[0]), FOOD0)

    def test_the_family_roll_sends_a_question_to_the_two_choice_family(self):
        for game, mode, story in self._each():
            (site, bound), rand = DIALOG[game]["rolls"]
            p = story.proc
            p.stub(rand, lambda q: (42, 0))
            _arm(story)
            p.put32(STACK, bound)
            p.set_reg("esp", STACK)
            p.run(site, site + 5)
            with self.subTest(game=game):
                self.assertEqual(p.reg("eax"), 0, "below 20: the two-choice family")

    def test_a_question_may_be_the_first_island_event(self):
        for game, mode, story in self._each():
            p = story.proc
            p.put32(story.village.world + DIALOG[game]["counter"], 0)
            event = Event(title="First", text="Which?")
            event.game = story.n
            p.write(EVENT_BUF, event.pack())
            p.write(CHOICE_BUF, _choice(story).pack())
            with self.subTest(game=game):
                self.assertEqual(p.export("VvfpStoryProbeChoiceRefusal", story.n, EVENT_BUF, CHOICE_BUF), 0)
                self.assertIn("first island event", story.refusal(Event(title="Plain", text="x")) or "")


# ---------------------------------------------------------------------------
# The Secret City, The Tree of Life, New Believers: the event object
# ---------------------------------------------------------------------------

HANDLER = {
    # click handler, hide button, show button, close, the dialog's text routine
    "vv3": (0x419A00, 0x40C230, 0x40C1F0, 0x40E020, 0x4185A0),
    "vv4": (0x417EA0, 0x40C210, 0x40C190, 0x40E090, 0x416F60),
    "vv5": (0x418720, 0x40C700, 0x40C680, 0x40E580, 0x417700),
}


@emulated
class ObjectQuestionTests(unittest.TestCase):
    def _object(self, story, roll=-1):
        table, site, resume, register, *_ = SELECT[story.game]
        p = story.proc
        for slot in range(1, 58):
            p.put32(table + 4 * slot, p.alloc(0x20))
        _arm(story)
        story.proc.export("VvfpStoryProbeSetRoll", roll)      # the villager shown
        p.set_reg("esi", 5)
        p.set_reg("esp", STACK)
        p.run(site, resume)
        return p.reg(register)

    def _method(self, story, obj, offset, *args):
        p = story.proc
        return p.call(p.u32(p.u32(obj) + offset), list(args), ecx=obj)

    def _text(self, story, string_id):
        lookup = SELECT[story.game][4]
        return story.proc.cstring(story.proc.call(lookup, [string_id]), 4000)

    def _each(self, modes=("collection_progression",)):
        for game in HANDLER:
            if not have_stock(game):
                continue
            for mode in modes:
                yield game, mode, _story(game, mode)

    def test_the_dialog_asks_the_question(self):
        for game, mode, story in self._each(MODES):
            p = story.proc
            obj = self._object(story)
            title_id, body_id = SELECT[game][6], SELECT[game][7]
            with self.subTest(game=game, mode=mode):
                self.assertEqual(obj, p.export("VvfpStoryProbeObject"))
                self.assertEqual(self._method(story, obj, 0x10) & 0xFF, 1, "a two-choice event")
                self.assertEqual(self._method(story, obj, 0x08), title_id)
                self.assertEqual(self._text(story, title_id), "The Strange Lights")
                self.assertEqual(self._method(story, obj, 0x0C), body_id)
                self.assertEqual(self._text(story, body_id), "Lights over the sea. What now?")
                self.assertEqual(self._text(story, self._method(story, obj, 0x14)), "Go fishing")
                self.assertEqual(self._text(story, self._method(story, obj, 0x18)), "Stay home")
                shown = self._method(story, obj, 0x1C)
                self.assertIn(shown, (story.village.record(1), story.village.record(2)),
                              "a living villager is shown")
                self.assertEqual(self._method(story, obj, 0x20), 0, "no second villager")
                self.assertEqual(self._method(story, obj, 0x24), 5, "the stock pose")
                self.assertEqual(self._method(story, obj, 0x3C), 0xFFFFFFFF, "no amount")
                tallest = self._text(story, self._method(story, obj, 0x28, 0))
                self.assertTrue(tallest.startswith("A small haul.") or tallest.startswith("A big haul."))
                self.assertIn("food", tallest)
                self.assertEqual(self._text(story, self._method(story, obj, 0x28, 1)).split("\n")[0],
                                 "Bea fell ill.")
                self.assertEqual(p.u32(_food_tech(story)[0]), FOOD0, "nothing changes before a click")

    def test_the_games_click_handler_answers(self):
        for game, mode, story in self._each(MODES):
            handler, hide, show, close, text = HANDLER[game]
            for button_id, roll, words, food_after, bea_sick in (
                    (2, 0, "A small haul.", FOOD0 + 100, 0),
                    (2, 99, "A big haul.", FOOD0 + 500, 0),
                    (3, -1, "Bea fell ill.", FOOD0, 1)):
                story = _story(game, mode)
                p = story.proc
                obj = self._object(story)
                for va in (hide, show, text):
                    story.record_call(va, 4)
                story.record_call(close, 0)
                dlg = p.alloc(0x900)
                p.put32(dlg + 0x50, obj)
                p.put32(dlg + 0x85C, 0xB1)
                p.put32(dlg + 0x860, 0xB2)
                p.put32(dlg + 0x864, 0xB0)
                food = _food_tech(story)[0]
                p.export("VvfpStoryProbeSetRoll", roll)
                p.call(handler, [8, button_id], ecx=dlg)
                with self.subTest(game=game, mode=mode, button=button_id, roll=roll):
                    self.assertEqual(p.u32(dlg + 0x830), button_id - 2)
                    shown = story.calls[text][-1][1]
                    result = self._text(story, shown)
                    self.assertTrue(result.startswith(words), result)
                    self.assertNotIn("The Strange Lights", result, "the title stays above it")
                    self.assertEqual(p.u32(food), food_after)
                    self.assertEqual(story.village.sick(2), bea_sick)
                    self.assertEqual(story.calls[show], [[dlg, 0xB0]], "OK is shown")
                    p.call(handler, [8, 1], ecx=dlg)     # OK: the apply
                    self.assertEqual(p.u32(food), food_after, "applied once")
                    self.assertEqual(story.calls[close], [[dlg]])
                    self.assertLessEqual(_lines(result), CHOICE_PANEL[game][3])

    def test_the_popup_is_sized_for_any_result(self):
        """Before the click +0x28 gives each button's tallest result."""
        for game, mode, story in self._each():
            p = story.proc
            obj = self._object(story)
            tallest = _lines(self._text(story, self._method(story, obj, 0x28, 0)))
            p.export("VvfpStoryProbeSetRoll", 0)
            self._method(story, obj, 0x34, 0)
            shown = _lines(self._text(story, self._method(story, obj, 0x28, 0)))
            with self.subTest(game=game):
                self.assertGreaterEqual(tallest, shown)

    def test_new_believers_never_shows_a_heathen(self):
        if not have_stock("vv5"):
            self.skipTest("no stock executable")
        for roll in range(4):
            story = _story("vv5")
            story.village.put(1, sex="m", years=30, name="Heath", faction=1)
            story.village.put(3, sex="m", years=30, name="Cal")
            obj = self._object(story, roll)
            with self.subTest(roll=roll):
                self.assertIn(self._method(story, obj, 0x1C),
                              (story.village.record(2), story.village.record(3)))

    def test_with_nobody_to_show_the_question_waits(self):
        for game, mode, story in self._each():
            story = Story(game)
            obj = self._object(story)
            table = SELECT[game][0]
            with self.subTest(game=game):
                self.assertEqual(obj, story.proc.u32(table + 4 * 5), "the game's own event")
                self.assertEqual(story.proc.export("VvfpStoryProbeCustomPending", story.n), 1)


if __name__ == "__main__":
    unittest.main()
