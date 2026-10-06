"""Story / Cheat Upgrades: Custom Island Event with two choices (the engine).

The owner: "I want the player to be able to choose the outcomes.  Some
buttons should have a chance of multiple outcomes too."

A two-choice event is the custom event's title and QUESTION, two button
labels, and for each button one to four OUTCOMES, each with a chance (a
weight 1-100), its own result text and its own changes.  This file tests the
game-independent engine (native/vvfp_story_upgrades/story_custom.inc) in the
test build of "VVFP Story Upgrades.dll", mapped beside each game's rendered
executable in the emulator, exactly as tests/test_story_custom_island_event.py
does:

* the layout the tests pack is the companion's own (ce_choice, ce_outcome);
* the weighted roll: every value of every chance split, one outcome always,
  and the real random source's shares;
* every refusal, per button and outcome;
* arming: the same lock, 10-minute lapse and village binding as a plain
  custom event, and the plain delivery never takes a question;
* the hooks' entry points: the question's text and labels, and the answer
  applying exactly the rolled outcome's changes and composing its text;
* the dialogs' controls in the shipped DLL.

The per-game delivery hooks (each game's own two-button popup) are tested
with the hooks themselves.
"""
from __future__ import annotations

import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))

import test_story_custom_island_event as part2  # noqa: E402
from story_custom_fixtures import (  # noqa: E402
    RESULT_SIZE,
    Choice,
    Event,
    Outcome,
    Spawn,
    unpack_result,
)
from test_story_custom_island_event import (  # noqa: E402
    ADD,
    EVENT_BUF,
    GAMES,
    PANEL,
    RESULT_BUF,
    SCRATCH,
    TEN_MINUTES,
    TEXT_BUF,
    Story,
    _dialogs,
    _food_tech,
    emulated,
    have_stock,
)

CHOICE_BUF = EVENT_BUF + 0x20000
COUNTS = SCRATCH + 0x800
CAP_CHOICE = 0x04000000

# Each game's two-choice popup, as its adapter declares it (story_c*.inc):
# question characters a line, question lines, result characters, result
# lines, the result leads with the title, label characters.  The numbers are
# the longest and tallest stock two-choice texts of each game (A New Home
# and The Lost Children: less the two lines the villager's picture adds).
CHOICE_PANEL = {
    "vv1": (49, 13, 49, 13, 1, 34),
    "vv2": (46, 16, 46, 16, 1, 30),
    "vv3": (48, 11, 48, 11, 0, 32),
    "vv4": (48, 11, 48, 11, 0, 34),
    "vv5": (48, 11, 48, 17, 0, 38),
}


def _story(game, **kw):
    story = Story(game, **kw)
    story.proc.export("VvfpStoryProbeChoiceCap", 1)
    story.village.put(1, sex="m", years=30, name="Adam")
    story.village.put(2, sex="f", years=30, name="Bea")
    return story


def _stories(games=GAMES, **kw):
    for game in games:
        if have_stock(game):
            yield game, _story(game, **kw)


def _write(story, event: Event, choice: Choice):
    event.game = story.n
    story.proc.write(EVENT_BUF, event.pack())
    story.proc.write(CHOICE_BUF, choice.pack())


def _refusal(story, event: Event, choice: Choice):
    _write(story, event, choice)
    at = story.proc.export("VvfpStoryProbeChoiceRefusal", story.n, EVENT_BUF, CHOICE_BUF)
    return None if at == 0 else story.proc.cstring(at)


def _set(story, event: Event, choice: Choice, tick=0):
    _write(story, event, choice)
    story.proc.export("VvfpStoryProbeSetChoice", story.n, EVENT_BUF, CHOICE_BUF, tick)


def _begin(story):
    story.proc.write(TEXT_BUF, b"\0")
    ok = story.proc.export("VvfpStoryProbeChoiceBegin", story.n, TEXT_BUF, 4096)
    return ok, story.proc.cstring(TEXT_BUF)


def _label(story, button):
    at = story.proc.export("VvfpStoryProbeChoiceLabel", story.n, button)
    return None if at == 0 else story.proc.cstring(at)


def _resolve(story, button):
    """The answer; the text returned is the result's body: in A New Home and
    The Lost Children the result replaces the whole popup text, so it must
    start with the title and four line breaks, which are checked and cut."""
    at = story.proc.export("VvfpStoryProbeChoiceTitle", story.n)
    title = story.proc.cstring(at) if at else ""
    story.proc.write(TEXT_BUF, b"\0")
    ok = story.proc.export("VvfpStoryProbeChoiceResolve", story.n, button, TEXT_BUF, 4096)
    story.proc.export("VvfpStoryProbeResult", RESULT_BUF)
    text = story.proc.cstring(TEXT_BUF)
    if ok and CHOICE_PANEL[story.game][4]:
        head = title + "\n\n\n\n"
        if not text.startswith(head):
            raise AssertionError(f"{story.game}: the result does not lead with the title: {text!r}")
        text = text[len(head):]
    return ok, unpack_result(story.proc.read(RESULT_BUF, RESULT_SIZE)), text


def _state(story):
    story.proc.export("VvfpStoryProbeChoiceState", story.n, SCRATCH)
    return dict(zip(("pending", "asked", "button", "outcome"),
                    struct.unpack("<4i", story.proc.read(SCRATCH, 16))))


def _stats(story):
    p = story.proc
    return dict(zip(("delivered", "refused", "lapsed", "discarded"),
                    struct.unpack("<4i", p.read(p.exports["VvfpStoryStats"], 16))))


def _result(text, **kw):
    return Outcome(kw.pop("chance", 1), Event(title="", text=text, **kw))


def _question(**kw):
    return Event(title=kw.pop("title", "A Fork"), text=kw.pop("text", "Which way?"), **kw)


def _choice(story, **kw):
    """Left: sick Adam (chance 1) or Adam's head 7 (chance 3); Right: Bea sick."""
    return Choice(
        labels=kw.pop("labels", ("Left", "Right")),
        outcomes=kw.pop("outcomes", (
            [_result("Adam fell ill.", changes=[story.change(1, sick=1)]),
             _result("Adam looks new.", chance=3, changes=[story.change(1, head=7)])],
            [_result("Bea fell ill.", changes=[story.change(2, sick=1)])],
        )),
        **kw)


# ---------------------------------------------------------------------------
# The layout
# ---------------------------------------------------------------------------

@emulated
class ChoiceLayoutTests(unittest.TestCase):
    def test_the_choice_structures_match_story_custom_h(self):
        if not have_stock("vv3"):
            self.skipTest("no stock executable")
        story = Story("vv3")
        story.proc.export("VvfpStoryProbeChoiceSizes", SCRATCH)
        sizes = struct.unpack("<10i", story.proc.read(SCRATCH, 40))
        labels = 2 * Choice.BUTTON_BYTES
        self.assertEqual(sizes, (Choice.SIZE, Outcome.SIZE, 4, 4 + labels, 4 + labels + 8,
                                 Choice.BUTTON_BYTES, Choice.MAX_OUTCOMES, 100, 12, 4))

    def test_the_event_layout_is_unchanged(self):
        """ce_event (packed by every Custom Island Event test) is untouched."""
        if not have_stock("vv3"):
            self.skipTest("no stock executable")
        story = Story("vv3")
        story.proc.export("VvfpStoryProbeSizes", SCRATCH)
        self.assertEqual(struct.unpack("<i", story.proc.read(SCRATCH, 4))[0], Event.SIZE)


# ---------------------------------------------------------------------------
# The weighted roll
# ---------------------------------------------------------------------------

SPLITS = [(1,), (100,), (1, 1), (3, 1), (1, 99), (1, 2, 3, 4), (100, 1, 50, 7), (100, 100, 100, 100)]


@emulated
class RollTests(unittest.TestCase):
    def setUp(self):
        if not have_stock("vv3"):
            self.skipTest("no stock executable")
        self.story = Story("vv3")

    def _index(self, chances, roll):
        p = self.story.proc
        p.write(SCRATCH, struct.pack(f"<{len(chances)}i", *chances))
        return p.export("VvfpStoryProbeRollIndex", SCRATCH, len(chances), roll)

    def test_every_roll_of_every_split_picks_its_outcome(self):
        for chances in SPLITS:
            want = [k for k, c in enumerate(chances) for _ in range(c)]
            got = [self._index(chances, r) for r in range(sum(chances))]
            with self.subTest(chances=chances):
                self.assertEqual(got, want, "each outcome takes exactly its chance of the rolls, in order")
                self.assertEqual([got.count(k) for k in range(len(chances))], list(chances))

    def _many(self, chances, times):
        p = self.story.proc
        choice = Choice(outcomes=([_result("x", chance=c) for c in chances], [_result("y")]))
        p.write(CHOICE_BUF, choice.pack())
        p.export("VvfpStoryProbeRollMany", 3, CHOICE_BUF, 0, times, COUNTS)
        return list(struct.unpack("<4i", p.read(COUNTS, 16)))

    def test_one_outcome_always_happens(self):
        self.assertEqual(self._many((1,), 200), [200, 0, 0, 0])
        self.assertEqual(self._many((100,), 200), [200, 0, 0, 0])

    def test_the_real_source_gives_each_outcome_its_share(self):
        for chances, times in (((3, 1), 4000), ((1, 1, 1, 1), 4000), ((1, 2, 3, 4), 5000)):
            counts = self._many(chances, times)
            total = sum(chances)
            with self.subTest(chances=chances):
                self.assertEqual(sum(counts), times)
                for k, c in enumerate(chances):
                    expected = times * c / total
                    sd = (times * (c / total) * (1 - c / total)) ** 0.5
                    self.assertLess(abs(counts[k] - expected), 6 * sd, (k, counts))
                self.assertEqual(counts[len(chances):], [0] * (4 - len(chances)))


# ---------------------------------------------------------------------------
# Refusals
# ---------------------------------------------------------------------------

@emulated
class ChoiceRefusalTests(unittest.TestCase):
    def test_a_complete_event_is_accepted(self):
        for game, story in _stories():
            with self.subTest(game=game):
                self.assertIsNone(_refusal(story, _question(), _choice(story)))

    def test_without_the_games_hook_a_question_is_refused(self):
        for game, story in _stories():
            story.proc.export("VvfpStoryProbeChoiceCap", 0)
            caps = story.proc.export("VvfpStoryProbeCaps", story.n)
            with self.subTest(game=game, hooked=bool(caps & CAP_CHOICE)):
                why = _refusal(story, _question(), _choice(story))
                if caps & CAP_CHOICE:
                    self.assertIsNone(why)
                else:
                    self.assertEqual(why, "This game can not ask a question with two choices yet.")

    def test_a_choice_not_enabled_is_a_plain_event(self):
        for game, story in _stories():
            with self.subTest(game=game):
                plain = _question(food_op=ADD, food_amount=5, changes=[story.change(1, sick=1)])
                self.assertIsNone(_refusal(story, plain, Choice(enabled=0)))
                self.assertEqual(_refusal(story, Event(title=""), Choice(enabled=0)), "Give the event a title.")

    def test_the_question(self):
        for game, story in _stories():
            lines = CHOICE_PANEL[game][1]
            cases = [
                (_question(title=""), "Give the event a title."),
                (_question(text="a *star*"), "title and question may use letters"),
                (_question(text="\n" * lines), "question must fit"),
                (_question(food_op=ADD, food_amount=5), "every change belongs to an outcome"),
                (_question(refill=1), "every change belongs to an outcome"),
                (_question(village=1), "every change belongs to an outcome"),
                (_question(changes=[story.change(1, sick=1)]), "every change belongs to an outcome"),
                (_question(spawns=[Spawn()]), "every change belongs to an outcome"),
                (_question(values=[(0, 1)]), "every change belongs to an outcome"),
                (_question(puzzles=[(0, 1)]), "every change belongs to an outcome"),
                (_question(revives=[(9, 1, 50, 1)]), "every change belongs to an outcome"),
            ]
            for event, words in cases:
                with self.subTest(game=game, words=words, text=event.text[:8]):
                    self.assertIn(words, _refusal(story, event, _choice(story)) or "")

    def test_the_labels(self):
        for game, story in _stories():
            limit = max(n for n in range(1, Choice.BUTTON_BYTES)
                        if _refusal(story, _question(), _choice(story, labels=("x" * n, "No"))) is None)
            with self.subTest(game=game, limit=limit):
                self.assertEqual(limit, CHOICE_PANEL[game][5], "the game's own label width")
                why = _refusal(story, _question(), _choice(story, labels=("x" * (limit + 1), "No")))
                self.assertIn(f"{limit} characters at most", why or "")
                self.assertIsNone(_refusal(story, _question(), _choice(story, labels=("No", "x" * limit))))
            for labels, words in (
                (("", "No"), "First button: Give both buttons a label."),
                (("Yes", "   "), "Second button: Give both buttons a label."),
                (("Y*s", "No"), "First button: A button label may use letters"),
            ):
                with self.subTest(game=game, labels=labels):
                    self.assertIn(words, _refusal(story, _question(), _choice(story, labels=labels)) or "")

    def test_the_outcomes(self):
        for game, story in _stories():
            lines = CHOICE_PANEL[game][3]
            ok = _result("It went well.")

            def with_left(*outcomes, counts=None):
                return _choice(story, outcomes=(list(outcomes), [ok]), counts=counts)
            cases = [
                (Choice(labels=("Yes", "No"), outcomes=([ok], [])), "Second button: give it one to 4 outcomes."),
                (with_left(ok, counts=(5, 1)), "First button: give it one to 4 outcomes."),
                (with_left(ok, _result("x", chance=0)), "First button, outcome 2: Each outcome's chance is 1 to 100."),
                (with_left(_result("x", chance=101)), "outcome 1: Each outcome's chance is 1 to 100."),
                (with_left(_result("x", chance=-5)), "Each outcome's chance is 1 to 100."),
                (with_left(_result("")), "First button, outcome 1: Give each outcome a result text."),
                (with_left(_result(" \r\n ")), "Give each outcome a result text."),
                (with_left(_result("(odd)")), "The result text may use letters"),
                (with_left(_result("x" + "\n" * lines)), "The result text must fit"),
            ]
            for choice, words in cases:
                with self.subTest(game=game, words=words):
                    self.assertIn(words, _refusal(story, _question(), choice) or "")
            for chances in ((1,), (100,), (1, 100, 50, 7)):
                with self.subTest(game=game, chances=chances):
                    choice = with_left(*[_result("x", chance=c) for c in chances])
                    self.assertIsNone(_refusal(story, _question(), choice))
            story.room[0] = False
            with self.subTest(game=game, case="full village"):
                choice = _choice(story, outcomes=([ok], [ok, _result("Twins!", spawns=[Spawn()])]))
                self.assertEqual(_refusal(story, _question(), choice),
                                 "Second button, outcome 2: The village is full: there is no room for "
                                 "new villagers.")
                baby = _result("A baby.", changes=[story.change(2, litter=1)])
                self.assertIn("no room for babies",
                              _refusal(story, _question(), _choice(story, outcomes=([baby], [ok]))) or "")

    def test_the_games_own_refusal(self):
        for game in GAMES:
            if not have_stock(game):
                continue
            story = Story(game)
            story.proc.export("VvfpStoryProbeChoiceCap", 1)
            story.village.put(1, sex="m", years=5, name="Kid")
            with self.subTest(game=game):
                ok = _result("x")
                self.assertIn("living adult",
                              _refusal(story, _question(), Choice(outcomes=([ok], [ok]))) or "")


# ---------------------------------------------------------------------------
# Arming: the lock, the lapse, the village
# ---------------------------------------------------------------------------

@emulated
class ChoiceArmingTests(unittest.TestCase):
    def _world(self, proc, game):
        import test_story_cheat_upgrades as part1

        return part1.LockTests._world(None, proc, game)

    def _queued(self, game, slot=1):
        story = _story(game, slot=slot)
        self._world(story.proc, game)
        _write(story, _question(), _choice(story))
        self.assertEqual(story.proc.export("VvfpStoryProbeQueueChoice", story.n, EVENT_BUF, CHOICE_BUF, 0), 1)
        return story

    def test_one_island_event_at_a_time(self):
        for game in GAMES:
            if not have_stock(game):
                continue
            story = self._queued(game)
            p, n = story.proc, story.n
            with self.subTest(game=game):
                self.assertEqual(p.export("VvfpStoryPickPending", n), 1)
                self.assertEqual(p.export("VvfpStoryProbePending", n), 1, "the island event is made due")
                self.assertEqual(_state(story)["pending"], 1)
                self.assertEqual(p.export("VvfpStoryPickIslandEvent", n, 0), 0)
                self.assertIn("already queued", p.messages[-1])
                self.assertEqual(p.export("VvfpStoryCustomIslandEvent", n, 0), 0)
                self.assertIn("already queued", p.messages[-1])

    def test_queueing_remembers_the_village(self):
        for game in GAMES:
            if not have_stock(game):
                continue
            for change in ("none", "other slot", "reset"):
                story = self._queued(game, slot=3)
                if change == "other slot":
                    story.host.slot = 4
                elif change == "reset":
                    story.proc.export("VvfpStoryVillageReset", story.n, 3)
                with self.subTest(game=game, change=change):
                    self.assertEqual(story.proc.export("VvfpStoryPickPending", story.n),
                                     1 if change == "none" else 0)
                    self.assertEqual(_begin(story)[0], 1 if change == "none" else 0)

    def test_a_question_waits_however_long_it_takes(self):
        """A two-choice Custom Island Event never lapses with time (the
        owner, 2026-10-06)."""
        for game, story in _stories():
            _set(story, _question(), _choice(story), tick=1000)
            story.proc.export("VvfpStoryProbeSetTick", 1000 + TEN_MINUTES + 1)
            with self.subTest(game=game):
                self.assertEqual(_state(story)["pending"], 1)
                self.assertEqual(_stats(story)["lapsed"], 0)

    def test_the_plain_delivery_never_takes_a_question(self):
        for game, story in _stories():
            _set(story, _question(), _choice(story))
            with self.subTest(game=game):
                self.assertEqual(story.proc.export("VvfpStoryProbeDeliver", story.n, TEXT_BUF, 4096), 0)
                self.assertEqual(_state(story)["pending"], 1, "still armed for the question")
                self.assertEqual((story.village.sick(1), story.village.sick(2)), (0, 0))
            with self.subTest(game=game, case="plain"):
                part2._set_custom(story, Event())
                self.assertEqual(_state(story)["pending"], 0, "a plain event is not a question")
                self.assertEqual(_begin(story)[0], 0, "and is never asked")
                self.assertEqual(story.proc.export("VvfpStoryProbeDeliver", story.n, TEXT_BUF, 4096), 1)


# ---------------------------------------------------------------------------
# The hooks' entry points
# ---------------------------------------------------------------------------

@emulated
class QuestionTests(unittest.TestCase):
    def test_the_question_text_and_labels(self):
        for game, story in _stories():
            width = CHOICE_PANEL[game][0]
            separate = PANEL[game][3]
            words = " ".join(["island"] * 20)
            _set(story, _question(title="The Long Night", text=words), _choice(story, labels=("Run", "Hide")))
            ok, text = _begin(story)
            with self.subTest(game=game):
                self.assertEqual(ok, 1)
                body = text
                if separate:
                    self.assertNotIn("The Long Night", text)
                else:
                    self.assertTrue(text.startswith("The Long Night\n\n\n\n"), text)
                    body = text.split("\n\n\n\n", 1)[1]
                self.assertEqual(body.replace("\n", " "), words)
                self.assertTrue(all(len(line) <= width for line in body.split("\n")))
                self.assertEqual((_label(story, 0), _label(story, 1)), ("Run", "Hide"))
                self.assertIsNone(_label(story, 2))
                title = story.proc.export("VvfpStoryProbeChoiceTitle", story.n)
                self.assertEqual(story.proc.cstring(title), "The Long Night")
                self.assertEqual((story.village.sick(1), story.village.sick(2)), (0, 0),
                                 "nothing changes before a button is clicked")

    def test_asking_takes_the_event_once(self):
        for game, story in _stories():
            _set(story, _question(), _choice(story))
            self.assertEqual(_begin(story)[0], 1)
            with self.subTest(game=game):
                state = _state(story)
                self.assertEqual((state["pending"], state["asked"]), (0, 1))
                self.assertEqual(story.proc.export("VvfpStoryPickPending", story.n), 0, "the lock is released")
                self.assertEqual(_stats(story)["delivered"], 1)
                self.assertEqual(_begin(story)[0], 0)


@emulated
class AnswerTests(unittest.TestCase):
    def _answer(self, game, button, roll, outcomes=None):
        story = _story(game)
        food = _food_tech(story)[0]
        story.proc.put32(food, 1000)
        choice = _choice(story) if outcomes is None else _choice(story, outcomes=outcomes)
        _set(story, _question(), choice)
        _begin(story)
        story.proc.export("VvfpStoryProbeSetRoll", roll)
        return story, food, _resolve(story, button)

    def test_the_rolled_outcome_and_only_it_is_applied(self):
        # Left: chances 1 (sick) and 3 (head 7): roll 0 is the first, 1-3 the second.
        for game in GAMES:
            if not have_stock(game):
                continue
            for roll, want in ((0, 0), (1, 1), (3, 1), (4, 0)):     # 4 wraps to 0 (mod 4)
                story, _, (ok, r, text) = self._answer(game, 0, roll)
                v = story.village
                with self.subTest(game=game, roll=roll):
                    self.assertEqual(ok, 1)
                    self.assertEqual(_state(story)["button"], 0)
                    self.assertEqual(_state(story)["outcome"], want)
                    if want == 0:
                        self.assertEqual((v.sick(1), v.i32(1, v.L["head"])), (1, 3))
                        self.assertTrue(text.startswith("Adam fell ill."), text)
                    else:
                        self.assertEqual((v.sick(1), v.i32(1, v.L["head"])), (0, 7))
                        self.assertTrue(text.startswith("Adam looks new."), text)
                    self.assertEqual(v.sick(2), 0, "the other button's outcome is not applied")
                    self.assertEqual(r["changed"], 1)

    def test_the_other_button(self):
        for game in GAMES:
            if not have_stock(game):
                continue
            story, _, (ok, r, text) = self._answer(game, 1, -1)
            v = story.village
            with self.subTest(game=game):
                self.assertEqual(ok, 1)
                self.assertEqual((_state(story)["button"], _state(story)["outcome"]), (1, 0))
                self.assertEqual((v.sick(1), v.sick(2), v.i32(1, v.L["head"])), (0, 1, 3))
                self.assertEqual(text, "Bea fell ill.")

    def test_the_result_text_has_the_outcome_lines_and_never_the_title(self):
        for game in GAMES:
            if not have_stock(game):
                continue
            outcomes = ([_result("You found berries.", food_op=ADD, food_amount=250)],
                        [_result("Nothing.")])
            story, food, (ok, r, text) = self._answer(game, 0, -1, outcomes)
            with self.subTest(game=game):
                self.assertEqual(story.proc.u32(food), 1250)
                self.assertEqual((r["food_before"], r["food_after"]), (1000, 1250))
                self.assertTrue(text.startswith("You found berries.\n"), text)
                self.assertIn("250 food", text)
                self.assertNotIn("A Fork", text)

    def test_answers_once_and_only_buttons_0_and_1(self):
        for game in GAMES:
            if not have_stock(game):
                continue
            story = _story(game)
            _set(story, _question(), _choice(story))
            _begin(story)
            with self.subTest(game=game):
                self.assertEqual(_resolve(story, 2)[0], 0)
                self.assertEqual(_resolve(story, -1)[0], 0)
                self.assertEqual(_state(story)["asked"], 1, "a wrong button leaves the question waiting")
                self.assertEqual(_resolve(story, 1)[0], 1)
                self.assertEqual(_resolve(story, 1)[0], 0)
                self.assertEqual(_label(story, 0), None)
                self.assertEqual(story.village.sick(2), 1)

    def test_an_answer_in_another_village_changes_nothing(self):
        for game in GAMES:
            if not have_stock(game):
                continue
            for case in ("other slot", "reset"):
                story = _story(game)
                _set(story, _question(), _choice(story))
                _begin(story)
                if case == "other slot":
                    story.host.slot = 2
                else:
                    story.proc.export("VvfpStoryVillageReset", story.n, 1)
                with self.subTest(game=game, case=case):
                    ok, r, text = _resolve(story, 1)
                    self.assertEqual((ok, text), (0, ""))
                    self.assertEqual(story.village.sick(2), 0)
                    self.assertEqual(_stats(story)["discarded"], 1)
                    self.assertEqual(_state(story)["asked"], 0)

    def test_an_event_armed_while_a_question_waits_never_replaces_it(self):
        for game in GAMES:
            if not have_stock(game):
                continue
            story = _story(game)
            first = _choice(story, labels=("A1", "A2"),
                            outcomes=([_result("Adam.", changes=[story.change(1, sick=1)])], [_result("-")]))
            second = _choice(story, labels=("B1", "B2"),
                             outcomes=([_result("Bea.", changes=[story.change(2, sick=1)])], [_result("-")]))
            _set(story, _question(), first)
            _begin(story)
            for _ in range(2):          # armed again and again while the first waits
                _set(story, _question(), second)
            with self.subTest(game=game):
                self.assertEqual((_label(story, 0), _label(story, 1)), ("A1", "A2"))
                self.assertEqual(_resolve(story, 0)[2], "Adam.")
                self.assertEqual((story.village.sick(1), story.village.sick(2)), (1, 0))
                self.assertEqual(_begin(story)[0], 1)
                self.assertEqual(_label(story, 0), "B1")
                self.assertEqual(_resolve(story, 0)[2], "Bea.")
                self.assertEqual(story.village.sick(2), 1)


# ---------------------------------------------------------------------------
# The dialogs
# ---------------------------------------------------------------------------

class ChoiceDialogTests(unittest.TestCase):
    DLL = ROOT / "assets" / "story_upgrades" / "VVFP Story Upgrades.dll"

    def setUp(self):
        if not part2.HAVE_EMULATOR:
            self.skipTest("pefile not installed")
        self.dialogs = _dialogs(self.DLL)

    def test_the_main_dialog_offers_the_question(self):
        caption, controls = self.dialogs[302]
        self.assertEqual(controls[1137][1], "Ask a question with two choices")
        self.assertEqual(controls[1138][1], "Choices...")
        self.assertIn(1139, controls, "the Description label the outcome mode renames")
        self.assertIn(1136, controls, "the note the modes reword")

    def test_the_choices_dialog(self):
        caption, controls = self.dialogs[310]
        self.assertEqual(caption, "Choices")
        for b in range(2):
            with self.subTest(button=b):
                for first in (3701, 3711, 3721, 3731, 3741, 3751, 3761):
                    self.assertIn(first + b, controls)
                self.assertEqual(controls[3721 + b][1], "Add...")
                self.assertEqual(controls[3731 + b][1], "Edit...")
                self.assertEqual(controls[3741 + b][1], "Remove")
                self.assertTrue(controls[3751 + b][2] & 0x2000, "the chance takes digits only")
        self.assertIn(3771, controls)


if __name__ == "__main__":
    unittest.main()
