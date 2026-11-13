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
* a damaged .cieg (its checksum, its magic, cut short, a loop, an index out of range) is refused;
* version 2, questions anywhere: a page, a question, a chance split, a page and a second question, every branch in
  every game (each effect with its own page, once; one island event counted; ONE Island Events log entry with each
  answer's "Choice:" line), and a quit with the second question on screen or before the first answer's page resumes
  with nothing made twice and the log entry continued as the save holds it.
"""
from __future__ import annotations

import re
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
IDLE, QUEUED, PRE, ASKED, CHAIN, DONE = range(6)

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

    def sent(self):
        """(times the entry was handed to the log, the entry last handed over, its `disk`, its `final`)."""
        text, info = FILE_BUF + 0x64000, FILE_BUF + 0x66000
        n = self.p.export("VvfpStoryProbeGraphSent", text, 0x2000, info)
        disk, final = struct.unpack("<2i", self.p.read(info, 8))
        return n, self.p.cstring(text, 0x2000), disk, final

    def log(self, on: int = -1):
        """The Island Events log stood in for (on 1: each page's lines "  page <k>"): (entries filed, the entry
        as it is now, the last one filed)."""
        now, filed = FILE_BUF + 0x60000, FILE_BUF + 0x62000
        n = self.p.export("VvfpStoryProbeGraphLog", on & 0xFFFFFFFF, now, filed, 0x2000)
        return n, self.p.cstring(now, 0x2000), self.p.cstring(filed, 0x2000)

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
    def observe(self, who=SUBJECT) -> dict:
        """What a page can change, read after each display (see play)."""
        L = self.v.L
        food, tech = stores(self)
        return {"health": self.v.i32(who, L["health"]), "active": self.v.byte(who, ACTIVE[self.game]),
                "heathen": self.v.byte(who, 0x1CEC) if self.game == "vv5" else 0, "food": food, "tech": tech,
                "dislikes": self.v.prefs(who, "dislikes"),
                "skills": [self.v.skill(who, k) for k in range(L["skill_count"])],
                "told": len(self.told()), "tick": self.p.tick}

    def play(self, button=None, until=None):
        """Every display until the run ends (or `until` displays): [(kind, text, notice_shown)], kind "page",
        "question" or "result"; the counter is raised before each one as the game's trigger raises it, and the
        clock moves on a second.  self.seen[i] is the village after display i, self.before before the first."""
        shown = []
        counter = self.counter_va()
        self.before = self.observe()
        self.seen = []
        for _ in range(64):
            st = self.state()
            if st["phase"] in (IDLE, DONE) or (until is not None and len(shown) >= until):
                break
            self.p.tick += 1000
            self.p.export("VvfpStoryProbeSetTick", self.p.tick)
            if not st["armed"] and st["phase"] != ASKED:
                assert self.p.export("VvfpStoryProbeGraphArmNext", self.n) == 1, st
            if self.choice_pending():
                self.p.put32(counter, self.p.u32(counter) + 1)
                self.p.write(TEXT_BUF, b"\0")
                assert self.p.export("VvfpStoryProbeChoiceBegin", self.n, TEXT_BUF, 4096) == 1
                q = self.p.cstring(TEXT_BUF)
                labels = [self.p.cstring(self.p.export("VvfpStoryProbeChoiceLabel", self.n, b)) for b in (0, 1)]
                shown.append(("question", q, self.p.export("VvfpStoryTimeSkipNoticeShown", self.n), labels))
                self.seen.append(self.observe())
                if button is None:
                    break
                self.p.tick += 1000
                self.p.export("VvfpStoryProbeSetTick", self.p.tick)
                self.p.write(TEXT_BUF, b"\0")
                assert self.p.export("VvfpStoryProbeChoiceResolve", self.n, button, TEXT_BUF, 4096) == 1
                shown.append(("result", self.p.cstring(TEXT_BUF), 0, None))
                self.seen.append(self.observe())
                continue
            self.p.put32(counter, self.p.u32(counter) + 1)
            self.p.write(TEXT_BUF, b"\0")
            assert self.p.export("VvfpStoryProbeDeliver", self.n, TEXT_BUF, 9000) == 1, st
            shown.append(("page", self.p.cstring(TEXT_BUF), self.p.export("VvfpStoryTimeSkipNoticeShown", self.n),
                          None))
            self.seen.append(self.observe())
        return shown


def stores(run: Run):
    food, tech, _, _ = _food_tech(run.story)
    return struct.unpack("<i", run.p.read(food, 4))[0], struct.unpack("<i", run.p.read(tech, 4))[0]


SENTENCES = re.compile(r"(?<=[.!?])\s+")


def _award_seen(e, run, h):
    kind, amount = h.award[0], h.award[1]
    return lambda o: o[kind] - run.before[kind] == amount


def _skill_seen(e, run, h):
    k = cg.GAMES[run.n].skills.index(e["skills"][ROLLS[3] % len(e["skills"])])
    return lambda o: o["skills"][k] == 20 + ROLLS[4] % 11


# For each effect of the owner's event: has the village (an observation, Run.observe) got it yet?
EFFECT_SEEN = {
    "pay_award": _award_seen,
    "food": lambda e, run, h: (lambda o: True),           # deferred: nothing to see until paid
    "tech": lambda e, run, h: (lambda o: True),
    "kill": lambda e, run, h: (lambda o: o["health"] == 0),
    "vanish": lambda e, run, h: (lambda o: o["active"] == 0),
    "status": lambda e, run, h: (lambda o: o["heathen"] == 1),
    "health": lambda e, run, h: (lambda o: o["health"] == 10 + ROLLS[3] % 41),
    "preference": lambda e, run, h: (
        lambda o: cg.GAMES[run.n].preferences.index("running") in o["dislikes"]),
    "skill": _skill_seen,
}


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
        self.assertIn(st["phase"], (IDLE, DONE), "the run ends with its last page")
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
        # EACH EFFECT ON ITS OWN PAGE: the page showing the end of its node's text (its last sentence) is the first
        # display after which the village shows it.
        ctx = cg.Context(run.n, frozenset({"guardians_of_isola"} if patches else ()), frozenset(GRAPH["roles"]))
        texts = [norm(run.strip(t, title)) for _k, t, _n, _l in shown]
        for node, e in h.effects:
            if e["do"] in ("food", "tech") and e.get("defer"):
                continue                       # the award: seen when paid (pay_award)
            raw = cg.node_text(GRAPH["nodes"][node], ctx, h.nodes)
            last = norm(SENTENCES.split(cg.expand(raw, binds, award).split("\n")[-1])[-1])
            page = next(i for i, t in enumerate(texts) if last in t)
            done = EFFECT_SEEN[e["do"]](e, run, h)
            with self.subTest(node=node, effect=e["do"]):
                self.assertTrue(done(run.seen[page]), f"made with the page that ends {node}")
                self.assertFalse(done(run.seen[page - 1] if page > 0 else run.before), "not before it")

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
                # The first page makes its own nodes' effects (the food, the death, the sickness); the tech waits
                # for the page that says so.
                self.assertEqual((run.seen[0]["food"] - food0, run.seen[0]["tech"] - tech0, run.seen[0]["told"]),
                                 (500, 0, 1))
                self.assertEqual(run.seen[1]["tech"] - tech0, -50)


@emulated
class EffectsWaitForTheirPage(unittest.TestCase):
    """The owner (2026-11-12): "The effects wait for their own page."  Three popups, one effect each: each is made
    as its page is built; a quit between pages resumes with each effect exactly once; a villager gone between pages
    has only their own later effects skipped."""

    GRAPH = cg.load({
        "format": "vvfp-cie-graph", "version": 1, "title": "Three Gifts", "games": [1, 2, 3, 4, 5],
        "roles": {"subject": {"kind": "villager"}},
        "start": "s",
        "nodes": {
            "s": {"text": "(Name) finds a basket of fruit.", "effects": [{"do": "food", "amount": 100}],
                  "children": [{"next": "t"}]},
            "t": {"text": "Then (he/she) finds an old book about the stars.",
                  "effects": [{"do": "skill", "skills": ["Research"], "min": 5, "max": 5}],
                  "children": [{"next": "u"}]},
            "u": {"text": "At last (he/she) trips on a root and limps home.",
                  "effects": [{"do": "health", "value": 40}]},
        },
    })
    DATA = cg.compile_graph(GRAPH)

    def start(self, game):
        run = Run(game)
        run.rolls([1] + [0] * 40)          # Bea
        run.force([])
        self.assertIsNone(run.queue(self.DATA))
        return run

    def research(self, run):
        return run.v.skill(SUBJECT, cg.GAMES[run.n].skills.index("Research"))

    def restart(self, game, file, save):
        run = Run(game)
        run.p.export("VvfpStoryProbeQueueSession", 0, 0, save, 0)
        run.p.write(FILE_BUF, file)
        run.p.export("VvfpStoryProbeGraphSession", FILE_BUF, len(file))
        run.tick()
        return run

    def test_each_effect_with_its_own_page(self):
        for game in GAMES:
            if not have_stock(game):
                continue
            run = self.start(game)
            shown = run.play()
            k = cg.GAMES[run.n].skills.index("Research")
            with self.subTest(game=game):
                self.assertEqual(len(shown), 3)
                f0 = run.before["food"]
                got = [(o["food"] - f0, o["skills"][k], o["health"]) for o in run.seen]
                self.assertEqual(got, [(100, 0, 90), (100, 5, 90), (100, 5, 40)])

    def test_a_quit_between_pages_makes_each_effect_once(self):
        for game in GAMES:
            if not have_stock(game):
                continue
            run = self.start(game)
            run.play(until=2)                         # the food and the book made
            t1 = run.seen[0]["tick"]                  # the food's moment; the book's is t1 + 1000
            run.tick()
            file = run.graph_file()
            with self.subTest(game=game, save="after both"):
                again = self.restart(game, file, LATE)
                self.assertEqual(again.state()["phase"], CHAIN)
                rest = again.play()
                self.assertEqual(len(rest), 1, "only the last page is still to come")
                # A new process stands for the reloaded save: what the save held is not made again.
                self.assertEqual((again.seen[-1]["food"] - again.before["food"], self.research(again),
                                  again.v.i32(SUBJECT, again.v.L["health"])), (0, 0, 40))
            with self.subTest(game=game, save="between them"):
                again = self.restart(game, file, t1 + 500)   # the save holds the food, not the book
                rest = again.play()
                self.assertEqual(len(rest), 2, "the book's page again, then the last")
                self.assertEqual((again.seen[-1]["food"] - again.before["food"], self.research(again),
                                  again.v.i32(SUBJECT, again.v.L["health"])), (0, 5, 40))
            # Every page shown, and a crash before the save caught up with the last one.
            run = self.start(game)
            run.play()
            self.assertEqual(run.state()["phase"], DONE, "kept until a save holds its last page")
            last = run.seen[-1]["tick"]
            run.p.export("VvfpStoryProbeQueueSession", 0, 0, last - 500, 0)
            run.tick()
            file = run.graph_file()
            with self.subTest(game=game, save="before the last page"):
                self.assertTrue(file, "the finished run's file waits for the save")
                again = self.restart(game, file, last - 500)
                rest = again.play()
                self.assertEqual(len(rest), 1)
                self.assertEqual((self.research(again), again.v.i32(SUBJECT, again.v.L["health"])), (0, 40))
            with self.subTest(game=game, save="after the last page"):
                run.p.export("VvfpStoryProbeQueueSession", 0, 0, LATE, 0)
                run.tick()
                self.assertEqual(run.graph_file(), b"", "the save holds it all: the file goes")
                again = self.restart(game, file, LATE)
                self.assertIn(again.state()["phase"], (IDLE,), "nothing shown again")

    def test_the_island_events_log_keeps_one_entry_continued_across_a_quit(self):
        """The owner (2026-11-12): ONE Island Events log entry per branching event -- its title, then every
        page's changes in page order as they happen -- filed once when the event is over; a quit between pages
        continues the same entry (a page shown again first takes its own lines back), nothing logged twice; the
        game's own bracket around each of its popups writes no record of its own (VvfpStoryGraphLogged, once)."""
        whole = "  Event: Three Gifts\n  page 0\n  page 1\n  page 2\n"
        for game in GAMES:
            if not have_stock(game):
                continue
            with self.subTest(game=game, at="straight"):
                run = self.start(game)
                run.log(1)
                run.play(until=1)
                title = run.p.alloc(32)
                run.p.write(title, b"Three Gifts\0")
                self.assertEqual(run.p.export("VvfpStoryGraphLogged", run.n, title), 1, "this popup is the event's")
                self.assertEqual(run.p.export("VvfpStoryGraphLogged", run.n, title), 0, "...asked once")
                self.assertEqual(run.log()[:2], (0, "  Event: Three Gifts\n  page 0\n"), "appended as it happens")
                self.assertEqual(run.sent(), (1, "  Event: Three Gifts\n  page 0\n", -1, 0),
                                 "...and handed to the log at once (its held record, for the next save)")
                run.play()
                self.assertEqual(run.log()[0::2], (1, whole), "one entry, filed once, every page in order")
                other = run.p.alloc(32)
                run.p.write(other, b"The Strange Berries\0")
                self.assertEqual(run.p.export("VvfpStoryGraphLogged", run.n, other), 0, "another event's popup")
            run = self.start(game)
            run.log(1)
            run.play(until=2)
            t1 = run.seen[0]["tick"]
            run.tick()
            file = run.graph_file()
            self.assertEqual(run.log()[0], 0, "nothing filed mid-run")
            held = {LATE: "  Event: Three Gifts\n  page 0\n  page 1\n", t1 + 500: "  Event: Three Gifts\n  page 0\n"}
            for save, label in ((LATE, "resumed"), (t1 + 500, "resumed, the save before the second page")):
                with self.subTest(game=game, at=label):
                    again = Run(game)
                    again.log(1)                         # the log is there as the run is put back
                    again.p.export("VvfpStoryProbeQueueSession", 0, 0, save, 0)
                    again.p.write(FILE_BUF, file)
                    again.p.export("VvfpStoryProbeGraphSession", FILE_BUF, len(file))
                    again.tick()
                    self.assertEqual(again.sent(), (1, held[save], len(held[save]), 0),
                                     "the log is told what the save's log holds of the entry: the same entry goes on")
                    again.play()
                    self.assertEqual(again.log()[0::2], (1, whole), "the same entry, continued: nothing twice")

    def test_a_question_s_entry_has_its_choice_and_none_when_nothing_changed(self):
        for game in GAMES:
            if not have_stock(game):
                continue
            run = Run(game)
            n = int(game[2:])
            for end, expect_pages in (("H3", 1), ("A7", 0)):
                h = next(h for h in histories(n) if h.end == end)
                run.reset()
                run.rolls(ROLLS)
                run.force([x for x in h.nodes if x != GRAPH["start"]] + QUIET[1 - h.choice])
                run.log(1)
                self.assertIsNone(run.queue())
                run.play(button=h.choice)
                count, _now, filed = run.log()
                label = GRAPH["nodes"]["intro"]["choices"][h.choice]["label"]
                with self.subTest(game=game, end=end):
                    self.assertEqual(count, 1)
                    self.assertTrue(filed.startswith(f"  Event: The Aspiring Adventurer\n  Choice: {label}\n"), filed)
                    self.assertEqual(filed.count("  page "), expect_pages)
                    if not expect_pages:
                        self.assertTrue(filed.endswith("  Changes: none\n"), filed)

    def test_a_villager_gone_between_pages_has_only_their_own_effects_skipped(self):
        for game in GAMES:
            if not have_stock(game):
                continue
            run = self.start(game)
            run.play(until=1)
            run.p.put32(run.v.record(SUBJECT) + run.v.L["health"], 0)   # died of old age between the pages
            shown = run.play()
            with self.subTest(game=game):
                self.assertEqual(len(shown), 2, "the event goes on")
                self.assertEqual(self.research(run), 0)
                self.assertEqual(run.v.i32(SUBJECT, run.v.L["health"]), 0, "never made alive again")
                self.assertTrue(all("could not be made" not in t for _k, t, *_ in shown))
                self.assertIn("trips on a root", shown[-1][1])


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
                self.assertEqual(again.graph_file(), b"", "the file goes once a save holds the last page")
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


# ---- Version 2: questions anywhere (v1.35.97, the owner: "events as complex as The Cave Explorers") ----------------

MULTI = cg.load({
    "format": "vvfp-cie-graph", "version": 2, "title": "Two Questions", "games": [1, 2, 3, 4, 5],
    "roles": {"subject": {"kind": "villager"}},
    "start": "p",
    "nodes": {
        "p": {"text": "(Name) finds a \"door\" in the hill.", "effects": [{"do": "food", "amount": 100}],
              "children": [{"next": "q1"}]},
        "q1": {"type": "question", "text": "Should (he/she) open it?", "choices": [
            {"label": "Open it", "next": "o"}, {"label": "Leave it", "next": "l"}]},
        "o": {"text": "It opens onto the dark.", "effects": [{"do": "tech", "amount": 10}],
              "children": [{"next": "o1", "weight": 3}, {"next": "o2"}]},
        "o1": {"popup": "append", "text": "A stair goes down.", "children": [{"next": "q2"}]},
        "o2": {"popup": "append", "text": "(He/She) falls and limps home.", "effects": [{"do": "health", "value": 40}]},
        "q2": {"type": "question", "text": "Does (name) go down?", "choices": [
            {"label": "Go down", "next": "d"}, {"label": "Go home", "next": "u"}]},
        "d": {"text": "Old books! (Name) reads all night.",
              "effects": [{"do": "skill", "skills": ["Research"], "min": 5, "max": 5}]},
        "u": {"text": "(Name) goes home."},
        "l": {"text": "(Name) walks away."},
    },
})
MULTI_CIEG = cg.compile_graph(MULTI)


def play_answers(run: Run, answers, until=None):
    """Run.play, answering each question in turn with the next of `answers` (stops at a question when none is
    left): [(kind, text, notice_shown, labels)]."""
    shown = []
    counter = run.counter_va()
    answers = list(answers)
    run.before = run.observe()
    run.seen = []
    for _ in range(64):
        st = run.state()
        if st["phase"] in (IDLE, DONE) or (until is not None and len(shown) >= until):
            break
        run.p.tick += 1000
        run.p.export("VvfpStoryProbeSetTick", run.p.tick)
        if not st["armed"] and st["phase"] != ASKED:
            assert run.p.export("VvfpStoryProbeGraphArmNext", run.n) == 1, st
        if run.choice_pending():
            run.p.put32(counter, run.p.u32(counter) + 1)
            run.p.write(TEXT_BUF, b"\0")
            assert run.p.export("VvfpStoryProbeChoiceBegin", run.n, TEXT_BUF, 4096) == 1
            labels = [run.p.cstring(run.p.export("VvfpStoryProbeChoiceLabel", run.n, b)) for b in (0, 1)]
            shown.append(("question", run.p.cstring(TEXT_BUF), run.p.export("VvfpStoryTimeSkipNoticeShown", run.n),
                          labels))
            run.seen.append(run.observe())
            if not answers or (until is not None and len(shown) >= until):
                break
            run.p.tick += 1000
            run.p.export("VvfpStoryProbeSetTick", run.p.tick)
            run.p.write(TEXT_BUF, b"\0")
            assert run.p.export("VvfpStoryProbeChoiceResolve", run.n, answers.pop(0), TEXT_BUF, 4096) == 1
            shown.append(("result", run.p.cstring(TEXT_BUF), 0, None))
            run.seen.append(run.observe())
            continue
        run.p.put32(counter, run.p.u32(counter) + 1)
        run.p.write(TEXT_BUF, b"\0")
        assert run.p.export("VvfpStoryProbeDeliver", run.n, TEXT_BUF, 9000) == 1, st
        shown.append(("page", run.p.cstring(TEXT_BUF), run.p.export("VvfpStoryTimeSkipNoticeShown", run.n), None))
        run.seen.append(run.observe())
    return shown


@emulated
class QuestionsAnywhere(unittest.TestCase):
    """A version 2 graph -- a page, a question, a chance split, a page, a second question -- in all five games:
    every branch reached, each effect with its own page and made once, ONE island event counted and ONE Island
    Events log entry with both answers, and a quit with the second question on screen, or between pages, resumes
    with the log matching the save."""

    def start(self, game, forced, log=True):
        run = Run(game)
        run.rolls([1] + [0] * 40)              # Bea
        run.force(forced, graph=MULTI)
        if log:
            run.log(1)
        self.assertIsNone(run.queue(MULTI_CIEG))
        return run

    def research(self, run):
        return run.v.skill(SUBJECT, cg.GAMES[run.n].skills.index("Research"))

    def histories(self, n):
        return cg.walk(MULTI, cg.Context(n, frozenset(), frozenset(MULTI["roles"])))

    def expect_kinds(self, h):
        out, last = [], None
        for pop in h.popups:
            out.append("question" if pop.layout == "question" else "result" if last == "question" else "page")
            last = pop.layout
        return out

    def test_every_branch_in_every_game(self):
        binds = {"subject": cg.Binding("Bea", "f")}
        for game in GAMES:
            if not have_stock(game):
                continue
            n = int(game[2:])
            for h in self.histories(n):
                with self.subTest(game=game, history=" > ".join(h.nodes)):
                    run = self.start(game, list(h.nodes))
                    count0 = run.p.u32(run.counter_va())
                    shown = play_answers(run, [b for _q, b in h.answers])
                    self.assertIn(run.state()["phase"], (IDLE, DONE))
                    self.assertEqual([k for k, *_ in shown], self.expect_kinds(h))
                    self.assertEqual([norm(run.strip(t, "Two Questions")) for _k, t, *_ in shown],
                                     [norm(cg.expand(pop.text, binds)) for pop in h.popups])
                    for (q, b), labels in zip(h.answers, [s[3] for s in shown if s[0] == "question"]):
                        self.assertEqual(labels, [c["label"] for c in MULTI["nodes"][q]["choices"]])
                    # ONE island event: the first page; every question and page after it a notice's count.
                    self.assertEqual(run.p.u32(run.counter_va()), count0 + 1, "Island Events Seen counts it once")
                    self.assertEqual(shown[0][2], 0)
                    for kind, _t, notice, _l in shown[1:]:
                        self.assertEqual(notice, 0 if kind in ("question", "result") else 1)
                    # Each effect once, with its own page.
                    seen = run.seen
                    f0, t0 = run.before["food"], run.before["tech"]
                    self.assertEqual(seen[0]["food"] - f0, 100)
                    self.assertEqual(seen[0]["tech"] - t0, 0)
                    if "o" in h.nodes:
                        at = next(i for i, s in enumerate(shown) if "It opens" in s[1])
                        self.assertEqual(seen[at - 1]["tech"] - t0, 0, "not before its page")
                        self.assertEqual(seen[at]["tech"] - t0, 10, "with its page")
                    self.assertEqual(seen[-1]["tech"] - t0, 10 if "o" in h.nodes else 0)
                    self.assertEqual(seen[-1]["food"] - f0, 100)
                    self.assertEqual(run.v.i32(SUBJECT, run.v.L["health"]), 40 if "o2" in h.nodes else 90)
                    self.assertEqual(self.research(run), 5 if "d" in h.nodes else 0)
                    # ONE log entry: the title, each answer's "Choice:" line where it was given, every page's lines.
                    filed_count, _now, filed = run.log()
                    self.assertEqual(filed_count, 1)
                    lines = ["  Event: Two Questions"]
                    for k, (kind, _t, _n, labels) in enumerate(shown):
                        if kind == "result":
                            q, b = h.answers[sum(1 for s in shown[:k] if s[0] == "result")]
                            lines.append(f"  Choice: {MULTI['nodes'][q]['choices'][b]['label']}")
                    self.assertTrue(filed.startswith(lines[0] + "\n"), filed)
                    self.assertEqual([x for x in filed.splitlines() if x.startswith("  Choice: ")], lines[1:])
                    self.assertEqual(filed.count("  page "), 1 + ("o" in h.nodes) + ("d" in h.nodes))

    def restart(self, game, file, save, log=True):
        run = Run(game)
        if log:
            run.log(1)
        run.p.export("VvfpStoryProbeQueueSession", 0, 0, save, 0)
        run.p.write(FILE_BUF, file)
        run.p.export("VvfpStoryProbeGraphSession", FILE_BUF, len(file))
        run.tick()
        return run

    def test_a_quit_mid_event_resumes_and_the_log_matches_the_save(self):
        h = next(h for h in self.histories(3) if h.end == "d")
        for game in GAMES:
            if not have_stock(game):
                continue
            straight_run = self.start(game, list(h.nodes))
            straight = play_answers(straight_run, [0, 0])
            whole = straight_run.log()[2]
            # Quit with the second question on screen (pages 0..3: p, q1, o, q2).
            run = self.start(game, list(h.nodes))
            first = play_answers(run, [0], until=4)
            self.assertEqual(first[-1][0], "question")
            self.assertEqual(run.state()["phase"], ASKED)
            run.tick()
            file = run.graph_file()
            with self.subTest(game=game, at="the second question, saved after it"):
                again = self.restart(game, file, LATE)
                st = again.state()
                self.assertEqual((st["phase"], st["armed"]), (ASKED, 1), "the second question is armed again")
                rest = play_answers(again, [0])
                self.assertEqual(rest[0][1], first[-1][1], "the same question")
                self.assertEqual([t for _k, t, *_ in first + rest[1:]], [t for _k, t, *_ in straight])
                self.assertEqual((again.seen[-1]["food"] - again.before["food"],
                                  again.seen[-1]["tech"] - again.before["tech"]), (0, 0), "nothing made twice")
                self.assertEqual(self.research(again), 5)
                self.assertEqual(again.log()[0::2], (1, whole), "the same entry, continued: nothing twice")
            # Quit after the first answer's page, the save made before that page's effects.
            t_open = run.seen[2]["tick"]
            with self.subTest(game=game, at="the first answer, saved before its page"):
                again = self.restart(game, file, t_open - 500)
                st = again.state()
                self.assertEqual(st["phase"], ASKED, "the save lacks the answer: the first question again")
                held = again.sent()
                self.assertEqual(held[1:3], ("  Event: Two Questions\n  page 0\n", 32),
                                 "the log is told what the save's log holds: the first page, not the answer")
                rest = play_answers(again, [0, 0])
                self.assertEqual([t for _k, t, *_ in first[:1] + rest], [t for _k, t, *_ in straight])
                self.assertEqual((again.seen[-1]["food"] - again.before["food"],
                                  again.seen[-1]["tech"] - again.before["tech"]), (0, 10),
                                 "the first page's food is in the save; the answer's tech is made now, once")
                self.assertEqual(again.log()[0::2], (1, whole))
            # The same quit, the other answer this time: the second question's segments go with the first answer.
            with self.subTest(game=game, at="answered the other way after the reload"):
                again = self.restart(game, file, t_open - 500)
                rest = play_answers(again, [1])
                self.assertEqual(norm(again.strip(rest[-1][1], "Two Questions")), "Bea walks away.")
                self.assertIn("  Choice: Leave it\n", again.log()[2])
                self.assertNotIn("Open it", again.log()[2])


CAVE_GRAPH = cg.load(ROOT / "data" / "cie_graphs" / "the_cave_explorers.json")
CAVE_CIEG = cg.compile_graph(CAVE_GRAPH)


@emulated
class CaveExplorersFromTheLibrary(unittest.TestCase):
    """The library's second example (A New Home), every history: three questions deep, the owner's words with their
    double quotes, both villagers' endings and the awards."""

    def test_every_history(self):
        if not have_stock("vv1"):
            self.skipTest("no stock executable")
        run = Run("vv1")
        binds = {"subject": cg.Binding("Bea", "f"), "friend": cg.Binding("Cal", "m")}
        title = CAVE_GRAPH["title"]
        for h in cg.walk(CAVE_GRAPH, cg.Context(1, frozenset(), frozenset(CAVE_GRAPH["roles"]))):
            with self.subTest(history=" > ".join(h.nodes)):
                run.reset()
                run.rolls(ROLLS)
                run.force(list(h.nodes), graph=CAVE_GRAPH)
                food0, tech0 = stores(run)
                self.assertIsNone(run.queue(CAVE_CIEG))
                shown = play_answers(run, [b for _q, b in h.answers])
                self.assertIn(run.state()["phase"], (IDLE, DONE))
                self.assertEqual(run.state()["records"][:2], (SUBJECT, FRIEND))
                award = (h.award[0], h.award[1]) if h.award else None
                self.assertEqual(norm(" ".join(run.strip(t, title) for _k, t, *_ in shown)),
                                 norm(" ".join(cg.expand(pop.text, binds, award) for pop in h.popups)))
                self.assertNotIn("could not be made", " ".join(t for _k, t, *_ in shown))
                food1, tech1 = stores(run)
                paid = (h.award[1] if h.award and h.award[0] == "food" else 0,
                        h.award[1] if h.award and h.award[0] == "tech" else 0)
                self.assertEqual((food1 - food0, tech1 - tech0), paid)
                L = run.v.L
                for who, role in ((SUBJECT, "subject"), (FRIEND, "friend")):
                    done = {e["do"] for _n, e in h.effects if e.get("role") == role}
                    self.assertEqual(run.v.byte(who, ACTIVE["vv1"]), 0 if "vanish" in done else 1)
                    if "kill" in done:
                        self.assertEqual(run.v.i32(who, L["health"]), 0)


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
