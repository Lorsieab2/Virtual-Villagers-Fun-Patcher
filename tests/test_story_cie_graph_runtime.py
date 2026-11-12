"""Branching Custom Island Events, phase 2: the game-side runtime (native/vvfp_story_upgrades/story_graph.inc).

The test build of "VVFP Story Upgrades.dll" is mapped beside each game's rendered executable in the emulator (as
tests/test_story_custom_island_event.py does) and drives a .cieg compiled by src/vv_cie_graph.py:

* The Aspiring Adventurer, in each of the five games, down EVERY history the patcher's own walk finds (each node of
  the history forced, the other button kept to a quiet one): the question's pages, both buttons' labels, every
  page shown afterwards -- the words exactly the patcher's, with the villagers' names and pronouns -- and every
  effect made once (the award paid once, the death and the disappearance told to the Cause of Death companion in
  the event's words, New Believers' Heathen counted as a faith conversion, the health, the dislike and the skill
  rolled), Island Events Seen counted once and every later page a notice the Island Events log skips;
* a plain (question-less) event: its effects as its first page is built, a scaled amount, the author's own cause;
* a quit with the question on screen, or between the pages, resumes where it was; a save older than the run never
  brings it back;
* no villager for a role: the purchase is refused and says why; a village that can no longer fill the roles at
  delivery keeps the event waiting;
* a damaged .cieg (its checksum, its magic, cut short, a loop, an index out of range) is refused.
"""
from __future__ import annotations

import struct
import sys
import unittest
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import vv_cie_graph as cg  # noqa: E402
from story_custom_fixtures import EVENT_COUNTER_GLOBAL  # noqa: E402
from test_story_custom_island_event import (  # noqa: E402
    EVENT_BUF,
    GAMES,
    HAVE_EMULATOR,
    SCRATCH,
    TEXT_BUF,
    Story,
    _food_tech,
    emulated,
    have_stock,
)

if HAVE_EMULATOR:
    from story_emulator import API_STUBS
    from unicorn import UC_HOOK_CODE

GRAPH_JSON = ROOT / "data" / "cie_graphs" / "the_aspiring_adventurer.json"
GRAPH = cg.load(GRAPH_JSON)
CIEG = cg.compile_graph(GRAPH)
NODES = list(GRAPH["nodes"])
IDLE, QUEUED, PRE, ASKED, CHAIN = range(5)

CIEG_BUF = EVENT_BUF + 0x40000
FORCE_BUF = SCRATCH + 0x400
ROLLS_BUF = SCRATCH + 0x600
STATE_BUF = SCRATCH + 0x800
WORDS_BUF = SCRATCH + 0xA00
FILE_BUF = EVENT_BUF + 0x80000
LATE = 0x7FFFFFF0

# The village: four adults; the rolls make Bea the adventurer, Cal the friend and the stranger a woman.
PEOPLE = [(0, "m", 30, "Adam"), (1, "f", 31, "Bea"), (2, "m", 40, "Cal"), (3, "f", 25, "Dee")]
ROLLS = [1, 1, 1, 7, 2, 5] + [0] * 40
SUBJECT, FRIEND = 1, 2
QUIET = {0: ["a_open", "find_dirt", "dirt_safe", "A7"], 1: ["b_open", "b_home"]}
ACTIVE = {"vv1": 0x28, "vv2": 0x30, "vv3": 0xF10, "vv4": 0x1CC4, "vv5": 0x1CD4}
SCALE_STORE = {"food": 0, "tech": 1}


def norm(text: str) -> str:
    return " ".join(text.split())


class Run:
    """One game's process with a village, the companion, and every game routine the effects reach stubbed."""

    def __init__(self, game: str, people=PEOPLE):
        self.game = game
        self.story = Story(game)
        self.n = self.story.n
        self.p = self.story.proc
        self.v = self.story.village
        self.people = people
        p = self.p
        p.api_handlers["SHGetSpecialFolderPathA"] = lambda q: (0, 16)
        p.export("VvfpStoryProbeChoiceCap", 1)
        p.tick = 100000                 # a moment after a save made at 1 (the older-save case)
        p.export("VvfpStoryProbeSetTick", p.tick)
        if game == "vv4":
            self.story.record_call(0x468C60, 0)
        if game == "vv5":
            world = p.alloc(0x18000)
            p.stub(0x425950, lambda q: (world, 0))
            self.story.record_call(0x473440, 0)
            p.stub(0x4669E0, lambda q: (q.write(q.reg("ecx") + 0x1CEC, b"\1"), 0)[1:] and (0, 0))
        # Only the stubs go through Python: every instruction would be far too slow for whole events.
        mu = p.mu
        mu.hook_del(p.code_hook)
        mu.hook_add(UC_HOOK_CODE, p._on_code, begin=API_STUBS, end=API_STUBS + 0xFFFF)
        for va in list(p.stubs):
            mu.hook_add(UC_HOOK_CODE, p._on_code, begin=va, end=va)
        self.reset()

    def reset(self, people=None):
        v = self.v
        L = v.L
        for i, sex, years, name in (people or self.people):
            v.put(i, sex=sex, years=years, name=name)
            self.p.put32(v.record(i) + L["pregnant"], 0)
            for k in range(L["skill_count"]):
                self.p.write(v.record(i) + L["skills"] + 4 * k, struct.pack("<f" if L["floats"] else "<i", 0))
        self.p.export("VvfpStoryProbeQueueSession", 0, 0, LATE, 0)
        self.p.export("VvfpStoryProbeGraphSession", 0, 0)

    # -- the probes ------------------------------------------------------------------------------------------
    def queue(self, data: bytes = CIEG, due: int = 0):
        self.p.write(CIEG_BUF, data)
        at = self.p.export("VvfpStoryProbeGraphQueue", self.n, CIEG_BUF, len(data), due)
        return None if at == 0 else self.p.cstring(at)

    def check(self, data: bytes):
        self.p.write(CIEG_BUF, data)
        at = self.p.export("VvfpStoryProbeGraphCheck", CIEG_BUF, len(data))
        return None if at == 0 else self.p.cstring(at)

    def force(self, nodes, patches=0, scale=0, graph=GRAPH):
        ids = list(graph["nodes"])
        idx = [ids.index(n) for n in nodes]
        self.p.write(FORCE_BUF, struct.pack(f"<{len(idx)}i", *idx) if idx else b"")
        self.p.export("VvfpStoryProbeGraphForce", FORCE_BUF, len(idx), patches, scale)

    def rolls(self, values):
        self.p.write(ROLLS_BUF, struct.pack(f"<{len(values)}i", *values))
        self.p.export("VvfpStoryProbeSetRolls", ROLLS_BUF, min(len(values), 64))

    def state(self) -> dict:
        self.p.export("VvfpStoryProbeGraphState", STATE_BUF)
        v = struct.unpack("<19i", self.p.read(STATE_BUF, 76))
        return {"phase": v[0], "next": v[1], "count": v[2], "armed": v[3], "choice": v[4], "bound": v[5],
                "planned": v[6], "records": v[7:11], "pre": v[11], "told": v[14], "female": v[15:19]}

    def told(self):
        out = []
        for k in range(self.state()["told"]):
            kind = self.p.export("VvfpStoryProbeGraphTold", k, STATE_BUF, WORDS_BUF)
            out.append((kind, self.p.u32(STATE_BUF), self.p.cstring(WORDS_BUF)))
        return out

    def choice_pending(self) -> int:
        self.p.export("VvfpStoryProbeChoiceState", self.n, SCRATCH)
        return struct.unpack("<i", self.p.read(SCRATCH, 4))[0]

    def counter_va(self):
        if self.game == "vv1":
            return self.v.world + 0x9E40
        if self.game == "vv2":
            return self.v.world + 0x2E51C
        return EVENT_COUNTER_GLOBAL[self.game]

    def tick(self):
        self.p.tick += 300
        self.p.export("VvfpStoryProbeSetTick", self.p.tick)
        # The companion's whole tick (the queue's roster checks, a restore) runs past the emulator's default cap.
        self.p.call(self.p.exports["VvfpStoryInstall"], [self.n], limit=20_000_000)

    def graph_file(self) -> bytes:
        size = self.p.export("VvfpStoryProbeGraphFile", 0, 0)
        if size <= 0:
            return b""
        self.p.export("VvfpStoryProbeGraphFile", FILE_BUF, size)
        return self.p.read(FILE_BUF, size)

    def strip(self, text: str, title: str) -> str:
        head = title + "\n\n\n\n"
        return text[len(head):] if text.startswith(head) else text

    # -- one popup after another, as the game's trigger would show them -----------------------------------------
    def play(self, button=None, until=None):
        """Every display until the run ends (or `until` displays): [(kind, text, notice_shown)], kind "page",
        "question" or "result"; the counter is raised before each one as the game's trigger raises it."""
        shown = []
        counter = self.counter_va()
        for _ in range(64):
            st = self.state()
            if st["phase"] == IDLE or (until is not None and len(shown) >= until):
                break
            if not st["armed"] and st["phase"] != ASKED:
                assert self.p.export("VvfpStoryProbeGraphArmNext", self.n) == 1, st
            if self.choice_pending():
                self.p.put32(counter, self.p.u32(counter) + 1)
                self.p.write(TEXT_BUF, b"\0")
                assert self.p.export("VvfpStoryProbeChoiceBegin", self.n, TEXT_BUF, 4096) == 1
                q = self.p.cstring(TEXT_BUF)
                labels = [self.p.cstring(self.p.export("VvfpStoryProbeChoiceLabel", self.n, b)) for b in (0, 1)]
                shown.append(("question", q, self.p.export("VvfpStoryTimeSkipNoticeShown", self.n), labels))
                if button is None:
                    break
                self.p.write(TEXT_BUF, b"\0")
                assert self.p.export("VvfpStoryProbeChoiceResolve", self.n, button, TEXT_BUF, 4096) == 1
                shown.append(("result", self.p.cstring(TEXT_BUF), 0, None))
                continue
            self.p.put32(counter, self.p.u32(counter) + 1)
            self.p.write(TEXT_BUF, b"\0")
            assert self.p.export("VvfpStoryProbeDeliver", self.n, TEXT_BUF, 9000) == 1, st
            shown.append(("page", self.p.cstring(TEXT_BUF), self.p.export("VvfpStoryTimeSkipNoticeShown", self.n),
                          None))
        return shown


def stores(run: Run):
    food, tech, _, _ = _food_tech(run.story)
    return struct.unpack("<i", run.p.read(food, 4))[0], struct.unpack("<i", run.p.read(tech, 4))[0]


def histories(game: int, patches=frozenset()):
    ctx = cg.Context(game, frozenset(patches), frozenset(GRAPH["roles"]))
    return cg.walk(GRAPH, ctx)


@emulated
class AspiringAdventurerEveryHistory(unittest.TestCase):
    """Every history of the owner's event, in each game: the words, the pages and every effect, once."""

    def each_game(self):
        for game in GAMES:
            if have_stock(game):
                yield game

    def check_history(self, run: Run, h, patches: int):
        game = run.game
        g = cg.GAMES[run.n]
        run.reset()
        run.rolls(ROLLS)
        target = [n for n in h.nodes if n != GRAPH["start"]]
        run.force(target + QUIET[1 - h.choice], patches=patches)
        food0, tech0 = stores(run)
        counter = run.counter_va()
        count0 = run.p.u32(counter)
        self.assertIsNone(run.queue())
        shown = run.play(button=h.choice)
        st = run.state()
        self.assertEqual(st["phase"], IDLE, "the run ends with its last page")
        # Who is who: Bea goes, Cal is the friend, the stranger is a woman (the rolls).
        names = {i: name for i, _s, _y, name in PEOPLE}
        sexes = {i: s for i, s, _y, _n in PEOPLE}
        binds = {"subject": cg.Binding(names[SUBJECT], sexes[SUBJECT]),
                 "friend": cg.Binding(names[FRIEND], sexes[FRIEND]), "stranger": cg.Binding("", "f")}
        award = (h.award[0], h.award[1]) if h.award else None
        title = GRAPH["title"]
        # The question: its earlier pages first (notices), then the two-button popup with the last.
        q_at = next(i for i, s in enumerate(shown) if s[0] == "question")
        pre, question, result, after = shown[:q_at], shown[q_at], shown[q_at + 1], shown[q_at + 2:]
        intro = cg.expand(h.popups[0].text, binds)
        self.assertEqual(norm(" ".join(run.strip(t, title) for _k, t, _n, _l in pre + [question])), norm(intro))
        self.assertEqual(question[3], [c["label"] for c in GRAPH["nodes"]["intro"]["choices"]])
        # Every later page, in order: exactly the patcher's words for this history.
        expect = " ".join(cg.expand(pop.text, binds, award) for pop in h.popups[1:])
        got = " ".join(run.strip(t, title) for _k, t, _n, _l in [result] + after)
        self.assertNotIn("could not be made", got)
        self.assertEqual(norm(got), norm(expect))
        # One island event: the question counts once and is logged; every other page is a notice.
        self.assertEqual(question[2], 0)
        for kind, _t, notice, _l in pre + after:
            self.assertEqual(notice, 1, "a later page is a notice: the Island Events log skips it")
        self.assertEqual(run.p.u32(counter), count0 + 1, "Island Events Seen counts the event once")
        # Every effect, once.
        told = run.told()
        expect_told = []
        food1, tech1 = stores(run)
        paid = {"food": 0, "tech": 0}
        r = run.v.record(SUBJECT)
        L = run.v.L
        for _node, e in h.effects:
            do = e["do"]
            if do == "pay_award":
                paid[h.award[0]] += h.award[1]
            elif do == "kill":
                expect_told.append((1, SUBJECT, e["cause"]))
                self.assertEqual(run.v.i32(SUBJECT, L["health"]), 0, "dies: the game's own death")
            elif do == "vanish":
                expect_told.append((2, SUBJECT, "Disappeared in The Aspiring Adventurer"))
                self.assertEqual(run.v.byte(SUBJECT, ACTIVE[game]), 0, "disappears: no body")
            elif do == "status":
                expect_told.append((3, SUBJECT, ""))
                self.assertEqual(run.v.byte(SUBJECT, 0x1CEC), 1, "a Heathen, by the game's own conversion")
            elif do == "health":
                self.assertEqual(run.v.i32(SUBJECT, L["health"]), 10 + ROLLS[3] % 41)
            elif do == "preference":
                running = g.preferences.index("running")
                self.assertIn(running, run.v.prefs(SUBJECT, "dislikes"))
                self.assertNotIn(running, run.v.prefs(SUBJECT, "likes"))
            elif do == "skill":
                pick = e["skills"][ROLLS[3] % len(e["skills"])]
                k = g.skills.index(pick)
                self.assertEqual(run.v.skill(SUBJECT, k), 20 + ROLLS[4] % 11)
                for other in range(L["skill_count"]):
                    if other != k:
                        self.assertEqual(run.v.skill(SUBJECT, other), 0)
        self.assertEqual(told, expect_told, "the companions told exactly once, in the event's words")
        self.assertEqual((food1 - food0, tech1 - tech0), (paid["food"], paid["tech"]), "the award, once, when paid")
        if not any(e["do"] in ("kill", "vanish") for _n, e in h.effects):
            self.assertGreater(run.v.i32(SUBJECT, L["health"]), 0)
            self.assertEqual(run.v.byte(SUBJECT, ACTIVE[game]), 1)
        for i in (0, 2, 3):
            self.assertEqual(run.v.i32(i, L["health"]), 90, "nobody else is touched")
        del r

    def test_every_history_in_every_game(self):
        for game in self.each_game():
            run = Run(game)
            n = int(game[2:])
            cases = [(h, 0) for h in histories(n)]
            if n == 5:
                cases += [(h, 1) for h in histories(n, {"guardians_of_isola"}) if h.end == "L2_heathen"]
            for h, patches in cases:
                with self.subTest(game=game, history=" > ".join(h.nodes), patches=patches):
                    self.check_history(run, h, patches)

    def test_the_question_is_about_the_subject_and_its_pages_fit(self):
        for game in self.each_game():
            run = Run(game)
            run.rolls(ROLLS)
            run.force(QUIET[0] + QUIET[1])
            self.assertIsNone(run.queue())
            st = run.state()
            with self.subTest(game=game):
                self.assertEqual(st["phase"], QUEUED)
                self.assertGreaterEqual(st["pre"], 1, "the owner's long question takes more than one page")
                shown = run.play(button=None)
                self.assertEqual([k for k, *_ in shown], ["page"] * st["pre"] + ["question"])
                self.assertEqual(run.choice_pending(), 0, "asked: no longer armed")
                st = run.state()
                self.assertEqual(st["phase"], ASKED)
                self.assertEqual(st["records"][:2], (SUBJECT, FRIEND))
                self.assertEqual(st["female"][2], 1, "the stranger, rolled a woman")


@emulated
class PlainEventAndCauses(unittest.TestCase):
    """A question-less event: its first page is the island event, every effect made as it is built."""

    GRAPH = cg.load({
        "format": "vvfp-cie-graph", "version": 1, "title": "The Falling Idol", "games": [1, 2, 3, 4, 5],
        "roles": {"subject": {"kind": "villager"}, "helper": {"kind": "villager", "sex": "male"}},
        "start": "s",
        "nodes": {
            "s": {"text": "(Name) finds an old idol in the sand, and (helper.name) helps (him/her) lift it.",
                  "effects": [{"do": "food", "amount": 300, "scaled": True}], "children": [{"next": "k"}]},
            "k": {"popup": "append", "join": "paragraph", "text": "It topples onto (him/her).",
                  "effects": [{"do": "kill", "cause": "Crushed by a falling idol"},
                              {"do": "sick", "role": "helper"}],
                  "children": [{"next": "t"}]},
            "t": {"text": "(helper.Name) carries the idol back to the village.",
                  "effects": [{"do": "tech", "amount": -50}]},
        },
    })

    def test_effects_scaling_and_the_authors_cause(self):
        data = cg.compile_graph(self.GRAPH)
        for game in GAMES:
            if not have_stock(game):
                continue
            run = Run(game)
            run.rolls([1, 0] + [0] * 40)        # Bea, then the only man left for the helper's role: Adam
            run.force([], scale=2)
            food_va, tech_va, _, _ = _food_tech(run.story)
            run.p.put32(food_va, 2000)
            run.p.put32(tech_va, 1000)
            food0, tech0 = stores(run)
            count0 = run.p.u32(run.counter_va())
            self.assertIsNone(run.queue(data))
            shown = run.play()
            with self.subTest(game=game):
                self.assertEqual([k for k, *_ in shown], ["page", "page"])
                self.assertEqual(shown[0][2], 0, "the first page is the island event")
                self.assertEqual(shown[1][2], 1, "the next popup is a notice")
                self.assertEqual(run.p.u32(run.counter_va()), count0 + 1)
                subject, helper = run.state()["records"][:2]
                self.assertEqual((subject, helper), (1, 0))
                self.assertEqual(norm(run.strip(shown[0][1], "The Falling Idol")),
                                 norm("Bea finds an old idol in the sand, and Adam helps her lift it. "
                                      "It topples onto her."))
                self.assertEqual(norm(run.strip(shown[1][1], "The Falling Idol")),
                                 norm("Adam carries the idol back to the village."))
                food1, tech1 = stores(run)
                self.assertEqual(food1 - food0, 300 + 2000 // 10, "scaled with Stored Food and Tech Points")
                self.assertEqual(tech1 - tech0, -50)
                self.assertEqual(run.told(), [(1, subject, "Crushed by a falling idol")])
                self.assertEqual(run.v.i32(subject, run.v.L["health"]), 0)
                self.assertEqual(run.v.sick(0), 1)


@emulated
class ResumeAfterAQuit(unittest.TestCase):
    """A quit with the question on screen, or between the pages, resumes; an older save never brings it back."""

    def target(self):
        h = next(h for h in histories(3) if h.end == "H3")
        return h, [n for n in h.nodes if n != GRAPH["start"]] + QUIET[0]

    def restart(self, game, file, save=LATE):
        run = Run(game)
        run.p.export("VvfpStoryProbeQueueSession", 0, 0, save, 0)
        run.p.write(FILE_BUF, file)
        run.p.export("VvfpStoryProbeGraphSession", FILE_BUF, len(file))
        run.tick()
        return run

    def test_a_question_on_screen_and_the_pages_after_it(self):
        for game in GAMES:
            if not have_stock(game):
                continue
            h, force = self.target()
            # The whole event without a quit, for comparison.
            run = Run(game)
            run.rolls(ROLLS)
            run.force(force)
            self.assertIsNone(run.queue())
            straight = run.play(button=1)
            # Quit with the question on screen.
            run = Run(game)
            run.rolls(ROLLS)
            run.force(force)
            self.assertIsNone(run.queue())
            first = run.play(button=None)
            run.tick()
            file = run.graph_file()
            with self.subTest(game=game, at="question"):
                self.assertTrue(file, "the run is written to its file")
                again = self.restart(game, file)
                st = again.state()
                self.assertEqual((st["phase"], st["armed"]), (ASKED, 1), "the question is armed again")
                rest = again.play(button=1)
                self.assertEqual(rest[0][1], first[-1][1], "the same question")
                self.assertEqual([t for _k, t, *_ in rest], [t for _k, t, *_ in straight[len(first) - 1:]],
                                 "the same answer, the same pages: nothing rolled again")
                self.assertEqual(again.v.i32(SUBJECT, again.v.L["health"]), 10 + ROLLS[3] % 41)
            # Quit between the pages after the answer.
            run = Run(game)
            run.rolls(ROLLS)
            run.force(force)
            self.assertIsNone(run.queue())
            part = run.play(button=1, until=len(first) + 1)
            run.tick()
            file = run.graph_file()
            with self.subTest(game=game, at="pages"):
                again = self.restart(game, file)
                self.assertEqual(again.state()["phase"], CHAIN)
                rest = again.play()
                self.assertEqual([t for _k, t, *_ in part + rest], [t for _k, t, *_ in straight])
                self.assertEqual(again.told(), [], "nothing made twice")
                again.tick()
                self.assertEqual(again.graph_file(), b"", "the file goes with the run's last page")
            with self.subTest(game=game, at="older save"):
                again = self.restart(game, file, save=1)
                self.assertEqual(again.state()["phase"], IDLE, "the save never held it")
                self.assertEqual(again.graph_file(), b"")


@emulated
class RolesAndRefusals(unittest.TestCase):
    def test_no_villager_for_a_role_refuses_the_purchase_and_says_why(self):
        for game in GAMES:
            if not have_stock(game):
                continue
            run = Run(game)
            for i, *_ in PEOPLE:
                run.p.put32(run.v.record(i) + run.v.L["pregnant"], 300)   # every adult carrying a baby
            with self.subTest(game=game):
                why = run.queue()
                self.assertIsNotNone(why)
                self.assertIn("Nobody in the village can be the event's subject", why)
                self.assertIn("not carrying or nursing a baby", why)
                self.assertEqual(run.state()["phase"], IDLE, "nothing queued")

    def test_a_village_that_can_no_longer_fill_the_roles_keeps_it_waiting(self):
        for game in GAMES:
            if not have_stock(game):
                continue
            run = Run(game)
            run.rolls(ROLLS)
            run.force(QUIET[0] + QUIET[1])
            self.assertIsNone(run.queue())
            for i, *_ in PEOPLE:
                run.p.put32(run.v.record(i) + run.v.L["pregnant"], 300)
            with self.subTest(game=game):
                run.p.write(TEXT_BUF, b"\0")
                self.assertEqual(run.p.export("VvfpStoryProbeDeliver", run.n, TEXT_BUF, 9000), 0)
                self.assertEqual(run.p.export("VvfpStoryProbeCustomHeld"), 1, "made due again once it can")
                self.assertEqual(run.state()["phase"], QUEUED)
                for i, *_ in PEOPLE:
                    run.p.put32(run.v.record(i) + run.v.L["pregnant"], 0)
                shown = run.play(button=0)
                self.assertEqual(run.state()["phase"], IDLE)
                self.assertTrue(shown)

    def test_an_event_not_made_for_this_game_is_refused(self):
        data = dict(GRAPH)
        data["games"] = [2]
        cieg = cg.compile_graph(data)
        for game in ("vv1", "vv3"):
            if have_stock(game):
                run = Run(game)
                self.assertIn("is not made for", run.queue(cieg))


def _recrc(data: bytearray) -> bytes:
    struct.pack_into("<I", data, 12, 0)
    struct.pack_into("<I", data, 12, zlib.crc32(bytes(data)))
    return bytes(data)


@emulated
class DamagedFiles(unittest.TestCase):
    def test_a_damaged_cieg_is_refused(self):
        if not have_stock("vv3"):
            self.skipTest("no stock executable")
        run = Run("vv3")
        self.assertIsNone(run.check(CIEG))
        flipped = bytearray(CIEG)
        flipped[len(flipped) // 2] ^= 0x55
        self.assertIn("checksum", run.check(bytes(flipped)))
        self.assertIn("not a version 1", run.check(b"XIEG" + CIEG[4:]))
        self.assertIn("not a version 1", run.check(CIEG[:-10]))
        # A loop, with a good checksum: the first child of "find_safe" back to "a_open".
        h = struct.unpack_from("<4sHHIII HHH HHHHHHHH H IIIIIIII I", CIEG, 0)
        o_node, o_child = h[19], h[20]
        node = NODES.index("find_safe")
        first = struct.unpack_from("<H", CIEG, o_node + 28 * node + 12)[0]
        loop = bytearray(CIEG)
        struct.pack_into("<H", loop, o_child + 12 * first, NODES.index("a_open"))
        self.assertIn("circle", run.check(_recrc(loop)))
        # An index out of range, with a good checksum.
        bad = bytearray(CIEG)
        struct.pack_into("<H", bad, o_child + 12 * first, 999)
        self.assertIsNotNone(run.check(_recrc(bad)))
        # A character the game cannot show, with a good checksum.
        text = bytearray(CIEG)
        at = bytes(text).index(b"nothing but a pile of dirt.")
        text[at] = ord("*")
        self.assertIn("text", run.check(_recrc(text)))
        # ...and refused by the purchase too.
        self.assertIn("checksum", run.queue(bytes(flipped)))
        self.assertEqual(run.state()["phase"], IDLE)


class SourceAndLayout(unittest.TestCase):
    def test_the_picker_and_the_queue_file_layout(self):
        src = (ROOT / "native" / "vvfp_story_upgrades")
        rc = (src / "vvfp_story_upgrades.rc").read_text(encoding="utf-8")
        self.assertIn('"From the library...", 1141', rc)
        self.assertIn("312 DIALOGEX", rc)
        queue = (src / "story_queue.inc").read_text(encoding="utf-8")
        self.assertIn("#define SQ_VERSION 1u", queue, "the queue file's layout is unchanged")
        self.assertIn("!cg_owns_armed(game)", queue, "a graph's page is never written into it")
        h = (src / "story_custom.h").read_text(encoding="utf-8")
        self.assertIn("#define CE_TEXT_BYTES 600", h)


if __name__ == "__main__":
    unittest.main()
