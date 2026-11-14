"""Branching Custom Island Events, format version 6 (the Isola Grand Event Collection): the game-side runtime
(native/vvfp_story_upgrades/story_graph.inc) against the contract docs/event-collection/cie-v6-binary.md.

The test build of "VVFP Story Upgrades.dll" runs beside each game's rendered executable in the emulator, as
tests/test_story_cie_graph_runtime.py does:

* the SHARED WALK VECTORS (tests/data/cie_v6_expand_vectors.json, made by src/vv_cie_graph.py simulate): the same
  random stream gives the same path, effect rolls, pool picks and aliases as the patcher's walk, and the pages say
  exactly the popups' words (pools, game words, inline picks, the new pronouns, the role shorthand, the glyph
  fallback with and without the Unicode Text companion, a choice shown only in The Secret City, the harm guard);
* each new effect -- celebrate (one villager and everyone), action, mood (good and bad), health_change, skill_set
  and damage -- made once, on its own page, in all five games, with ONE Island Events log entry (damage's own line);
* a quit between pages resumes with the same picks; a version 3 run file still loads;
* casting: STRICT refuses a requirement nobody meets (and the event's own requirement), PREFER drops it and queues;
  "highest" keeps the top skill; a harm-capable role never takes a nursing parent; cg_queue_origin;
* the loader refuses a pool that reaches itself, an unknown pool token and eight answers.
"""
from __future__ import annotations

import copy
import hashlib
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
from test_story_custom_island_event import (  # noqa: E402
    DO_ACTION,
    HAVE_EMULATOR,
    SCRATCH,
    TEXT_BUF,
    emulated,
    have_stock,
)

if HAVE_EMULATOR:
    from test_story_cie_graph_runtime import ASKED, CIEG_BUF, DONE, IDLE, Run, stores
    from unicorn import UC_HOOK_CODE

VECTORS = json.loads((ROOT / "tests" / "data" / "cie_v6_expand_vectors.json").read_text(encoding="utf-8"))
PICKS_BUF = SCRATCH + 0x1000
WHY_BUF = SCRATCH + 0x3000
DAMAGE_BUF = SCRATCH + 0x3200
LAYOUT_BUF = SCRATCH + 0x3300
FARMING = {"vv1": 2, "vv2": 2, "vv3": 0, "vv4": 0, "vv5": 0}
GAME_IDS = ("vv1", "vv2", "vv3", "vv4", "vv5")


def norm(text: str) -> str:
    return " ".join(text.split())


def compiled(graph: dict) -> bytes:
    """The graph compiled as the patcher compiles it (its fit checked for a game with Scrolling Popups: the pages
    are the engine's to lay out here)."""
    return cg.compile_graph(cg.load(copy.deepcopy(graph), scrolling=True))


class Names:
    """The names of a .cieg's roles, nodes and pools, by index (read from the binary itself)."""

    def __init__(self, blob: bytes):
        u16 = lambda at: struct.unpack_from("<H", blob, at)[0]  # noqa: E731
        u32 = lambda at: struct.unpack_from("<I", blob, at)[0]  # noqa: E731
        n_role, n_node, n_string = u16(26), u16(28), u16(38)
        o_role, o_node, o_string = u32(44), u32(48), u32(72)
        o_pool, n_pool = u32(76), u16(84)
        blob_at = o_string + 4 * n_string

        def s(i):
            at = blob_at + struct.unpack_from("<I", blob, o_string + 4 * i)[0]
            return blob[at:blob.index(b"\0", at)].decode()
        self.roles = [s(struct.unpack_from("<H", blob, o_role + 16 * i + 4)[0]) for i in range(n_role)]
        self.role_flags = [blob[o_role + 16 * i + 1] for i in range(n_role)]
        self.nodes = [s(struct.unpack_from("<H", blob, o_node + 28 * i + 4)[0]) for i in range(n_node)]
        self.pools = [s(struct.unpack_from("<H", blob, o_pool + 12 * i)[0]) for i in range(n_pool)]


if HAVE_EMULATOR:
    class V6(Run):
        """A run with the version 6 probes."""

        def __init__(self, game: str, people=None):
            """people: (index, sex, years, name, farming, nursing); None: the runtime tests' four adults."""
            from test_story_cie_graph_runtime import PEOPLE
            super().__init__(game, PEOPLE if people is None else [x[:4] for x in people])
            self.recorded: dict[int, list] = {}
            self.p.api_handlers.setdefault("GetSystemTimeAsFileTime",
                                           lambda q: (q.write(q.arg(0), bytes(8)) or 0, 4))
            self.p.api_handlers.setdefault("CharUpperBuffA", self._upper)
            if people is not None:
                self.place(people)

        @staticmethod
        def _upper(q):
            """user32 CharUpperBuffA (stdcall: the text, its length; returns the length), as Windows-1252 does."""
            at, n = q.arg(0), q.arg(1)
            q.write(at, q.read(at, n).decode("cp1252").upper().encode("cp1252", "replace"))
            return n, 8

        def observe(self, who=None):
            return self.watch() if getattr(self, "watch", None) else super().observe()

        def record(self, va: int, pop: int):
            def fn(p):
                self.recorded.setdefault(va, []).append([p.reg("ecx")] + [p.arg(i) for i in range(pop // 4)])
                return 0, pop
            self.p.stub(va, fn)
            self.p.mu.hook_add(UC_HOOK_CODE, self.p._on_code, begin=va, end=va)

        def place(self, people):
            """The village: (index, sex, years, name, farming, nursing)."""
            v, L = self.v, self.v.L
            for i in range(10):
                self.p.write(v.record(i) + L["active"], b"\0")
            for i, sex, years, name, farming, nursing in people:
                v.put(i, sex=sex, years=years, name=name)
                self.p.put32(v.record(i) + L["pregnant"], 1 if nursing else 0)
                for k in range(L["skill_count"]):
                    value = farming if k == FARMING[self.game] else 0
                    self.p.write(v.record(i) + L["skills"] + 4 * k,
                                 struct.pack("<f" if L["floats"] else "<i", value))

        def queue6(self, data: bytes, strict: bool = False, origin: int = 0):
            self.p.write(CIEG_BUF, data)
            due = (0x100 if strict else 0) | (origin << 9)
            at = self.p.export("VvfpStoryProbeGraphQueue", self.n, CIEG_BUF, len(data), due)
            return None if at == 0 else self.p.cstring(at)

        def facts(self, unicode: int = -1, structures: int = -1):
            self.p.export("VvfpStoryProbeGraphFacts", unicode & 0xFFFFFFFF, structures & 0xFFFFFFFF, 0)

        def damaged(self):
            self.p.export("VvfpStoryProbeGraphFacts", 0xFFFFFFFF, 0xFFFFFFFE, DAMAGE_BUF)
            return list(struct.unpack("<8i", self.p.read(DAMAGE_BUF, 32)))

        def v6state(self) -> dict:
            cap = 64
            n = self.p.export("VvfpStoryProbeGraphPicks", PICKS_BUF, cap)
            v = struct.unpack(f"<{n}i", self.p.read(PICKS_BUF, 4 * n))
            picks = [tuple(v[1 + 3 * i:4 + 3 * i]) for i in range(min(v[0], cap))]
            o = 1 + 3 * cap
            aliases = list(v[o:o + 16])
            o += 16
            relaxed, cast, origin = v[o:o + 3]
            o += 3
            shown = v[o]
            mp = [m for m in v[o + 1:o + 8] if m >= 0]
            o += 8
            nfx = v[o]
            fx = [[v[o + 1 + 2 * i], v[o + 2 + 2 * i]] for i in range(min(nfx, 64))]
            return {"picks": picks, "aliases": aliases, "relaxed": relaxed, "cast": cast, "origin": origin,
                    "shown": shown, "map": mp, "fx": fx}

        def path(self) -> list[int]:
            out = SCRATCH + 0x2000
            n = self.p.export("VvfpStoryProbeGraphPath", 0, out, 128)
            return list(struct.unpack(f"<{n}i", self.p.read(out, 4 * n)))

        def displays(self) -> list[str]:
            out = []
            for k in range(self.state()["count"]):
                at = self.p.export("VvfpStoryProbeGraphDisplay", k)
                out.append(self.p.cstring(at, 4000) if at else "")
            return out

        def labels(self, count: int = 7) -> list[str]:
            out = []
            for b in range(count):
                at = self.p.export("VvfpStoryProbeChoiceLabel", self.n, b)
                if at:
                    out.append(self.p.cstring(at))
            return out

        def walk_through(self, answers=()):
            """Every display until the run ends, answering each question with the CHOICE index given (mapped to
            its button: the buttons close up over a choice not shown).  [(kind, text)] and the observations."""
            answers = list(answers)
            shown = []
            self.seen = []
            for _ in range(64):
                st = self.state()
                if st["phase"] in (IDLE, DONE):
                    break
                self.p.tick += 1000
                self.p.export("VvfpStoryProbeSetTick", self.p.tick)
                if not st["armed"] and st["phase"] != ASKED:
                    assert self.p.export("VvfpStoryProbeGraphArmNext", self.n) == 1, st
                if self.choice_pending():
                    self.p.write(TEXT_BUF, b"\0")
                    assert self.p.export("VvfpStoryProbeChoiceBegin", self.n, TEXT_BUF, 4096) == 1
                    shown.append(("question", self.p.cstring(TEXT_BUF), self.labels()))
                    self.seen.append(self.observe())
                    choice = answers.pop(0)
                    button = self.v6state()["map"].index(choice)
                    self.p.write(TEXT_BUF, b"\0")
                    assert self.p.export("VvfpStoryProbeChoiceResolve", self.n, button, TEXT_BUF, 4096) == 1
                    shown.append(("result", self.p.cstring(TEXT_BUF), None))
                    self.seen.append(self.observe())
                    continue
                self.p.write(TEXT_BUF, b"\0")
                assert self.p.export("VvfpStoryProbeDeliver", self.n, TEXT_BUF, 9000) == 1, st
                shown.append(("page", self.p.cstring(TEXT_BUF), None))
                self.seen.append(self.observe())
            return shown


def vector_village(case: dict):
    """One villager for each bound villager role, as the case names them (cook1 / gardener1: Farming 5, the rest 1
    for a Farming role and 0 otherwise -- so "highest" and the requirements single each one out)."""
    people = []
    g = case["graph"]
    for k, (role, b) in enumerate(case["bindings"].items()):
        spec = g["roles"][role]
        if spec.get("kind", "villager") != "villager":
            continue
        years = 8 if spec.get("max_age", 99) <= 13 else 30
        skill = spec.get("skill")
        farming = (5 if k == 0 else 1) if skill else 0
        if role == "cook2":
            farming = 0
        people.append((len(people), b["sex"], years, b["name"], farming, False))
    return people


# Rolls the binding takes that the patcher's walk does not model, and where they come in the stream (a start
# question's own words are drawn at the purchase, before the binding): (after this many rolls, [the rolls]).
BIND_ROLLS = {"gardening_vv3": (2, [0]), "gardening_vv3_plots": (2, [0]),
              "gaps_vv1_tribe": (0, [0]), "gaps_vv3_no_tribe": (0, [0])}


@emulated
class SharedVectors(unittest.TestCase):
    """The engine's walk is the patcher's walk: path, effect rolls, picks, aliases and the words read."""

    def run_case(self, case: dict) -> None:
        game = f"vv{case['game']}"
        data = compiled(case["graph"])
        e = case["expect"]
        self.assertEqual(hashlib.sha256(data).hexdigest(), e["cieg_sha256"], "the same compiled file")
        names = Names(data)
        r = V6(game, vector_village(case))
        at, extra = BIND_ROLLS.get(case["name"], (0, []))
        rolls = list(case["rolls"])
        r.rolls(rolls[:at] + extra + rolls[at:] + [0] * 8)
        r.facts(unicode=1 if case["unicode"] else 0, structures=0xFF)
        facts = case["facts"]
        if facts is not None:
            protected = [role for role in case["bindings"] if f"harmable:{role}" not in facts]
            for role in protected:
                idx = [p[3] for p in vector_village(case)].index(case["bindings"][role]["name"])
                r.p.export("VvfpStoryProbeGraphNurseAtWalk", idx)
        if "tribe" in case:
            put_tribe(r, game, case["tribe"])
        self.assertIsNone(r.queue6(data))
        shown = r.walk_through(case["answers"])
        st = r.v6state()
        self.assertEqual([names.nodes[i] for i in r.path()], e["nodes"])
        self.assertEqual(st["fx"], e["fx"])
        self.assertEqual([[names.pools[p], k, None if item < 0 else item] for p, k, item in st["picks"]],
                         [list(x) for x in e["picks"]])
        aliases = {names.roles[i]: names.roles[m] for i, m in enumerate(st["aliases"][:len(names.roles)])
                   if m >= 0}
        self.assertEqual(aliases, e["aliases"])
        self.assertEqual(norm(" ".join(r.displays())), norm(" ".join(e["popups"])), "the words the player reads")
        self.assertTrue(shown)

    def test_every_vector_in_its_game(self):
        ran = 0
        for case in VECTORS["cases"]:
            if not have_stock(f"vv{case['game']}"):
                continue
            with self.subTest(case=case["name"]):
                self.run_case(case)
                ran += 1
        self.assertGreater(ran, 0)


def effects_graph(game: str) -> dict:
    """One page for each new effect, in order."""
    action = {"vv1": "Dancing", "vv2": "Dancing", "vv3": "Dancing", "vv4": "Dancing (another dance)",
              "vv5": "Dancing"}[game]
    return {
        "format": "vvfp-cie-graph", "version": 6, "title": "Every New Effect", "games": [int(game[2])],
        "roles": {"subject": {"kind": "villager", "min_age": 14}, "friend": {"kind": "villager", "min_age": 14}},
        "start": "p0",
        "nodes": {
            "p0": {"text": "Everyone celebrates.", "effects": [{"do": "celebrate", "who": "all"}],
                   "children": [{"next": "p1"}]},
            "p1": {"text": "(Friend) celebrates alone.", "effects": [{"do": "celebrate", "who": "friend"}],
                   "children": [{"next": "p2"}]},
            "p2": {"text": "(Friend) dances.", "effects": [{"do": "action", "role": "friend", "action": action}],
                   "children": [{"next": "p3"}]},
            "p3": {"text": "(Friend) is glad.", "effects": [{"do": "mood", "role": "friend", "mood": "good"}],
                   "children": [{"next": "p4"}]},
            "p4": {"text": "(Name) is cross.", "effects": [{"do": "mood", "role": "subject", "mood": "bad"}],
                   "children": [{"next": "p5"}]},
            "p5": {"text": "(Name) is hurt.",
                   "effects": [{"do": "health_change", "role": "subject", "min": -30, "max": -30}],
                   "children": [{"next": "p6"}]},
            "p6": {"text": "(Friend) masters farming.",
                   "effects": [{"do": "skill", "role": "friend", "skills": ["Farming"], "set": 100}],
                   "children": [{"next": "p7"}]},
            "p7": {"text": "A hut is damaged.",
                   "effects": [{"do": "damage", "structures": "any", "min": 40, "max": 40}]},
        },
    }


# The behaviour routines a page's effect starts (the stop first, then the game's own routine).
CELEBRATE = {"vv1": (0x443FA0, 8), "vv2": (0x459B60, 12)}
SHAKE = {"vv1": 0x43A040, "vv2": 0x44B1B0}
DANCE = {"vv1": 0x43F200, "vv2": 0x450580}


@emulated
class NewEffects(unittest.TestCase):
    """Each new effect once, on its own page, and the event's ONE log entry."""

    def test_each_new_effect_on_its_page_in_every_game(self):
        for game in GAME_IDS:
            if not have_stock(game):
                continue
            with self.subTest(game=game):
                r = V6(game, [(0, "m", 30, "Adam", 0, False), (1, "f", 31, "Bea", 0, False),
                              (2, "m", 8, "Kid", 0, True)])
                if game in DO_ACTION:
                    r.record(DO_ACTION[game], 8)
                    started = lambda: [c[1] for c in r.recorded.get(DO_ACTION[game], [])]  # noqa: E731
                else:
                    for va, pop in (CELEBRATE[game], (SHAKE[game], 4), (DANCE[game], 4)):
                        r.record(va, pop)
                    started = lambda: sum(([va] * len(r.recorded.get(va, []))  # noqa: E731
                                           for va in (CELEBRATE[game][0], SHAKE[game], DANCE[game])), [])
                r.rolls([0] * 40)
                r.log(1)
                r.facts(structures=0x3)
                data = compiled(effects_graph(game))
                self.assertIsNone(r.queue6(data))
                health0 = r.v.i32(0, r.v.L["health"])
                r.watch = lambda: (len(started()), r.v.i32(0, r.v.L["health"]),  # noqa: E731
                                   r.v.skill(1, FARMING[game]), sum(1 for x in r.damaged() if x))
                shown = r.walk_through()
                self.assertEqual(len(shown), 8, [s[1][:40] for s in shown])
                self.assertIn(r.state()["phase"], (IDLE, DONE))
                self.assertEqual(list(r.state()["records"][:2]), [0, 1], "Adam the subject, Bea the friend")
                starts = [w[0] for w in r.seen]
                # celebrate all: everyone listed (the nursing child too), then one villager a page.
                self.assertEqual(starts, [3, 4, 5, 6, 7, 7, 7, 7], "each start on its own page, once")
                self.assertEqual([w[1] for w in r.seen], [health0] * 5 + [health0 - 30] * 3,
                                 "health_change on its page")
                self.assertEqual([w[2] for w in r.seen], [0] * 6 + [100] * 2, "skill_set on its page")
                self.assertEqual([w[3] for w in r.seen], [0] * 7 + [1], "damage on its page")
                damaged = r.damaged()
                self.assertEqual(sorted(x for x in damaged if x), [40], "one structure, 40% of its work")
                n, _now, filed = r.log()
                self.assertEqual(n, 1, "ONE Island Events log entry")
                self.assertEqual(filed.count("Event: Every New Effect"), 1)
                self.assertIn("Damaged: ", filed)
                self.assertIn("40% of its building work lost", filed)


@emulated
class ResumeAndFile(unittest.TestCase):
    """A quit between pages comes back with the same words; a version 3 run file still loads."""

    def test_a_quit_between_pages_keeps_the_picks(self):
        case = next(c for c in VECTORS["cases"] if c["name"] == "kitchen_vv1_keep")
        if not have_stock("vv1"):
            self.skipTest("no stock A New Home")
        data = compiled(case["graph"])
        r = V6("vv1", vector_village(case))
        r.rolls(list(case["rolls"]) + [0] * 8)
        r.facts(unicode=0, structures=0)
        r.p.export("VvfpStoryProbeQueueSession", 0, 0, 1, 0)
        self.assertIsNone(r.queue6(data))
        if not r.state()["armed"]:
            assert r.p.export("VvfpStoryProbeGraphArmNext", r.n) == 1
        r.p.write(TEXT_BUF, b"\0")
        assert r.p.export("VvfpStoryProbeDeliver", r.n, TEXT_BUF, 9000) == 1
        before = r.v6state()["picks"]
        words = r.displays()
        r.tick()
        file = r.graph_file()
        again = V6("vv1", vector_village(case))
        again.rolls([5] * 40)                        # other rolls: nothing may be drawn again
        again.facts(unicode=0, structures=0)
        again.p.export("VvfpStoryProbeQueueSession", 0, 0, 0x7FFFFFF0, 0)
        buf = again.p.alloc(len(file) + 16)
        again.p.write(buf, file)
        again.p.export("VvfpStoryProbeGraphSession", buf, len(file))
        again.tick()
        self.assertNotEqual(again.state()["phase"], IDLE, "put back")
        self.assertEqual(again.v6state()["picks"], before, "the same picks")
        self.assertEqual(again.displays()[:len(words)], words, "the same words")

    def test_a_version_3_run_file_still_loads(self):
        if not have_stock("vv3"):
            self.skipTest("no stock The Secret City")
        from test_story_cie_graph_runtime import CIEG
        r = V6("vv3")
        r.rolls([0] * 40)
        self.assertIsNone(r.queue6(CIEG))
        for _ in range(8):                          # the question's earlier pages, then the question
            if not r.state()["armed"]:
                assert r.p.export("VvfpStoryProbeGraphArmNext", r.n) == 1
            r.p.write(TEXT_BUF, b"\0")
            if r.choice_pending():
                break
            assert r.p.export("VvfpStoryProbeDeliver", r.n, TEXT_BUF, 9000) == 1
        assert r.p.export("VvfpStoryProbeChoiceBegin", r.n, TEXT_BUF, 4096) == 1
        labels = r.labels(2)
        r.tick()
        file = bytearray(r.graph_file())
        r.p.export("VvfpStoryProbeGraphFileLayout", LAYOUT_BUF)
        v3, head, whole = struct.unpack("<3i", r.p.read(LAYOUT_BUF, 12))
        self.assertEqual(struct.unpack_from("<I", file, 4)[0], 4, "written as version 4")
        old = bytes(file[:head]) + bytes(file[head:head + v3]) + bytes(file[head + whole:])
        old = bytearray(old)
        struct.pack_into("<I", old, 4, 3)
        struct.pack_into("<I", old, 16, v3)
        again = V6("vv3")
        again.rolls([0] * 40)
        again.p.export("VvfpStoryProbeQueueSession", 0, 0, 0x7FFFFFF0, 0)
        buf = again.p.alloc(len(old) + 16)
        again.p.write(buf, bytes(old))
        again.p.export("VvfpStoryProbeGraphSession", buf, len(old))
        again.tick()
        self.assertEqual(again.state()["phase"], ASKED, "a version 3 file is put back")
        again.p.write(TEXT_BUF, b"\0")
        assert again.p.export("VvfpStoryProbeChoiceBegin", again.n, TEXT_BUF, 4096) == 1
        self.assertEqual(again.labels(2), labels)


def cast_graph(**role) -> dict:
    spec = {"kind": "villager", "min_age": 14}
    spec.update(role)
    return {"format": "vvfp-cie-graph", "version": 6, "title": "The Cast", "games": [1, 2, 3, 4, 5],
            "roles": {"subject": spec}, "start": "p",
            "nodes": {"p": {"text": "(Name) is chosen.", "effects": [{"do": "celebrate", "who": "subject"}]}}}


@emulated
class Casting(unittest.TestCase):
    """STRICT and PREFER, "highest", the protected filter, cg_queue_origin."""

    def run_game(self):
        for game in GAME_IDS:
            if have_stock(game):
                return game
        self.skipTest("no stock game")

    def test_strict_refuses_a_requirement_nobody_meets_prefer_drops_it(self):
        game = self.run_game()
        data = compiled(cast_graph(skill={"names": ["Farming"], "min": 50}))
        village = [(0, "m", 30, "Adam", 10, False), (1, "f", 31, "Bea", 20, False)]
        r = V6(game, village)
        r.rolls([0] * 40)
        why = r.queue6(data, strict=True, origin=2)
        self.assertIsNotNone(why, "strict: nobody has Farming 50")
        self.assertIn("Farming 50", why)
        r = V6(game, village)
        self.assertIsNone(r.queue6(data), "prefer: the requirement is dropped, the event queued")
        st = r.v6state()
        self.assertEqual(st["relaxed"], 1)
        self.assertEqual(st["cast"], 1)

    def test_the_events_own_requirement_holds_only_when_strict(self):
        game = self.run_game()
        g = cast_graph()
        g["requirement"] = {"min_eligible": 1, "if": {"min_population": 10}}
        data = compiled(g)
        r = V6(game, [(0, "m", 30, "Adam", 0, False)])
        self.assertIsNotNone(r.queue6(data, strict=True))
        r = V6(game, [(0, "m", 30, "Adam", 0, False)])
        self.assertIsNone(r.queue6(data))

    def test_highest_keeps_the_top_skill(self):
        game = self.run_game()
        data = compiled(cast_graph(skill={"names": ["Farming"], "min": 1, "pick": "highest"}))
        for roll in range(3):
            with self.subTest(roll=roll):
                r = V6(game, [(0, "m", 30, "Adam", 10, False), (1, "f", 31, "Bea", 30, False),
                              (2, "m", 32, "Cal", 30, False)])
                r.rolls([roll] * 40)
                self.assertIsNone(r.queue6(data))
                r.walk_through()
                self.assertIn(r.state()["records"][0], (1, 2), "only the villagers with the top value")

    def test_a_harm_capable_role_never_takes_a_nursing_parent(self):
        game = self.run_game()
        g = cast_graph()
        g["nodes"]["p"]["effects"] = [{"do": "health_change", "role": "subject", "min": -5, "max": -5}]
        data = compiled(g)
        self.assertTrue(Names(data).role_flags[0] & 32, "the compiler marks it protected")
        for roll in range(2):
            with self.subTest(roll=roll):
                r = V6(game, [(0, "f", 30, "Ann", 0, True), (1, "m", 31, "Bob", 0, False)])
                r.rolls([roll] * 40)
                self.assertIsNone(r.queue6(data))
                r.walk_through()
                self.assertEqual(r.state()["records"][0], 1, "never the nursing mother")
                r = V6(game, [(0, "f", 30, "Ann", 0, True)])
                self.assertIsNotNone(r.queue6(data), "only a nursing parent: nobody may be harmed")

    def test_queue_origin(self):
        game = self.run_game()
        data = compiled(cast_graph(skill={"names": ["Farming"], "min": 50}))
        r = V6(game, [(0, "m", 30, "Adam", 0, False)])
        r.p.write(CIEG_BUF, data)
        ok = r.p.export("VvfpStoryProbeGraphQueueOrigin", r.n, CIEG_BUF, len(data), 2, 0, WHY_BUF)
        self.assertEqual(ok, 0, "strict, natural: refused")
        self.assertIn("Farming", r.p.cstring(WHY_BUF))
        ok = r.p.export("VvfpStoryProbeGraphQueueOrigin", r.n, CIEG_BUF, len(data), 1, 1, WHY_BUF)
        self.assertEqual(ok, 1, r.p.cstring(WHY_BUF))
        st = r.v6state()
        self.assertEqual((st["origin"], st["cast"]), (1, 1))
        ok = r.p.export("VvfpStoryProbeGraphQueueOrigin", r.n, CIEG_BUF, len(data), 2, 1, WHY_BUF)
        self.assertEqual(ok, 0, "one branching event at a time")


@emulated
class Loader(unittest.TestCase):
    """A damaged version 6 file is refused whole."""

    def base(self) -> bytes:
        g = cast_graph()
        g["pools"] = {"A": {"items": ["one", "two"]}, "B": {"items": ["x {A}"]}}
        g["nodes"]["p"]["text"] = "(Name) finds {B} and {A.2}."
        return compiled(g)

    def patched(self, data: bytes, old: bytes, new: bytes) -> bytes:
        assert len(old) == len(new) and data.count(old) == 1
        b = bytearray(data.replace(old, new))
        struct.pack_into("<I", b, 12, 0)
        struct.pack_into("<I", b, 12, zlib.crc32(bytes(b)) & 0xFFFFFFFF)
        return bytes(b)

    def test_refusals(self):
        game = next((g for g in GAME_IDS if have_stock(g)), None)
        if game is None:
            self.skipTest("no stock game")
        r = V6(game)
        data = self.base()
        self.assertIsNone(r.check(data))
        self.assertIsNotNone(r.check(self.patched(data, b"x {A}", b"x {B}")), "a pool reaching itself")
        self.assertIsNotNone(r.check(self.patched(data, b"{A.2}", b"{C.2}")), "an unknown pool")
        self.assertIsNotNone(r.check(self.patched(data, b"{A.2}", b"{A.9}")), "instance 9")
        eight = cast_graph()
        eight["nodes"] = {"q": {"type": "question", "text": "Pick.", "choices": [
            {"label": f"Door {k}", "next": "e"} for k in range(7)]}, "e": {"text": "Done."}}
        eight["start"] = "q"
        blob = compiled(eight)
        self.assertIsNone(r.check(blob), "seven answers")
        # The question's child count 7 -> 8 (its node record's +14).
        b = bytearray(blob)
        o_node = struct.unpack_from("<I", b, 48)[0]
        struct.pack_into("<H", b, o_node + 14, 8)
        struct.pack_into("<I", b, 12, 0)
        struct.pack_into("<I", b, 12, zlib.crc32(bytes(b)) & 0xFFFFFFFF)
        self.assertIsNotNone(r.check(bytes(b)), "eight answers")


# ---- The format gaps G1-G7 (docs/event-collection/cie-v6-binary.md, the lead's collection_gaps_spec) -------------

TRIBE_MANAGER = {"vv1": 0x48AEDC, "vv2": 0x4997BC, "vv3": 0x4B309C, "vv4": 0x4CB51C, "vv5": 0x4DACE0}
TRIBE_AT = {"vv1": 0x10, "vv2": 0x10, "vv3": 0x12ED4, "vv4": 0x170C0, "vv5": 0x17D1C}
TWO = [(0, "f", 30, "Ana", 0, False), (1, "m", 31, "Bo", 0, False)]


def gap_graph(game: str, **extra) -> dict:
    g = {"format": "vvfp-cie-graph", "version": 6, "title": "The Gaps", "games": [int(game[2])],
         "roles": {"subject": {"kind": "villager", "min_age": 14}}, "start": "p",
         "nodes": {"p": {"text": "(Name) waits."}}}
    g.update(extra)
    return g


def put_tribe(r, game: str, name: str | None) -> None:
    """The tribe's name where the game's save manager keeps it (None: an unnamed village)."""
    va = TRIBE_MANAGER[game]
    manager = r.p.u32(va)
    if manager == 0:
        manager = r.p.alloc(0x18000)
        r.p.put32(va, manager)
    r.p.write(manager + TRIBE_AT[game], (name or "").encode() + b"\0")


@emulated
class FormatGaps(unittest.TestCase):
    """G1-G7 in every game."""

    def games(self):
        for game in GAME_IDS:
            if have_stock(game):
                yield game

    def words(self, r) -> str:
        return norm(" ".join(r.displays()))

    def test_g1_five_buttons_the_answers_page_is_a_popup_of_its_own(self):
        for game in self.games():
            for n in (4, 5):
                with self.subTest(game=game, buttons=n):
                    choices = [{"label": f"Door {k + 1}", "next": f"d{k}"} for k in range(n)]
                    nodes = {"q": {"type": "question", "text": "(Name) sees doors.", "choices": choices}}
                    for k in range(n):
                        nodes[f"d{k}"] = {"text": f"Behind door {k + 1}.",
                                          "effects": [{"do": "tech", "amount": 10 * (k + 1)}]}
                    r = V6(game, TWO)
                    r.rolls([0] * 40)
                    self.assertIsNone(r.queue6(compiled(gap_graph(game, start="q", nodes=nodes))))
                    if not r.state()["armed"]:
                        r.p.export("VvfpStoryProbeGraphArmNext", r.n)
                    r.p.write(TEXT_BUF, b"\0")
                    assert r.p.export("VvfpStoryProbeChoiceBegin", r.n, TEXT_BUF, 4096) == 1
                    tech0 = stores(r)[1]
                    r.p.write(TEXT_BUF, b"\0")
                    assert r.p.export("VvfpStoryProbeChoiceResolve", r.n, 1, TEXT_BUF, 4096) == 1
                    result = r.p.cstring(TEXT_BUF)
                    if n == 4:
                        self.assertIn("Behind door 2", result, "two to four: in the question's popup")
                        self.assertEqual(stores(r)[1] - tech0, 20)
                        continue
                    self.assertEqual(result, "", "five or more: nothing in the question's popup")
                    self.assertEqual(stores(r)[1], tech0, "its effect waits for its own page")
                    shown = r.walk_through()
                    self.assertEqual(len(shown), 1)
                    self.assertIn("Behind door 2", shown[0][1], "its own popup")
                    self.assertEqual(stores(r)[1] - tech0, 20, "made once, with its page")

    def test_g2_the_other_member(self):
        for game in self.games():
            for roll in (0, 1):
                with self.subTest(game=game, roll=roll):
                    g = gap_graph(game, roles={
                        "a": {"kind": "villager", "min_age": 14}, "b": {"kind": "villager", "min_age": 14},
                        "pick": {"kind": "alias", "of": ["a", "b"]}, "rest": {"kind": "other", "of": "pick"}})
                    g["nodes"]["p"] = {"text": "(Pick) leads. (rest) follows (rest.him/her).",
                                       "effects": [{"do": "skill", "role": "rest", "skills": ["Farming"],
                                                    "set": 100}]}
                    r = V6(game, TWO)
                    # The binding: a among Ana / Bo (roll), then b; then the alias's own roll.
                    r.rolls([0, roll] + [0] * 40)
                    self.assertIsNone(r.queue6(compiled(g)))
                    r.walk_through()
                    picked = "Ana" if roll == 0 else "Bo"
                    rest, pron, idx = ("Bo", "him", 1) if roll == 0 else ("Ana", "her", 0)
                    self.assertEqual(self.words(r), f"{picked} leads. {rest} follows {pron}.")
                    self.assertEqual(r.v.skill(idx, FARMING[game]), 100, "the effect on the other member")
                    self.assertEqual(r.v.skill(1 - idx, FARMING[game]), 0)

    def test_g3_distinct_from(self):
        for game in self.games():
            with self.subTest(game=game):
                g = gap_graph(game, pools={"A": {"items": ["red", "blue"]},
                                           "B": {"items": ["red", "blue"], "distinct_from": ["A"]}})
                g["nodes"]["p"]["text"] = "(Name) likes {A} not {B}."
                r = V6(game, TWO)
                r.rolls([0, 0, 0] + [0] * 40)          # the cast, A (red), B would be red too
                self.assertIsNone(r.queue6(compiled(g)))
                r.walk_through()
                self.assertIn("likes red not blue.", self.words(r))

    def test_g5_the_tribes_name_at_run_time(self):
        for game in self.games():
            for name in ("Kalahuna", None):
                with self.subTest(game=game, name=name):
                    g = gap_graph(game)
                    g["nodes"]["p"]["text"] = "{@Tribe} gathers. (Name) speaks for {@tribe}."
                    r = V6(game, TWO)
                    r.rolls([0] * 40)
                    put_tribe(r, game, name)
                    self.assertIsNone(r.queue6(compiled(g)))
                    r.walk_through()
                    want = (f"{name} gathers. Ana speaks for {name}." if name
                            else "The village gathers. Ana speaks for the village.")
                    self.assertEqual(self.words(r), want)

    def test_g6_quotes_in_the_title(self):
        for game in self.games():
            with self.subTest(game=game):
                r = V6(game, TWO)
                r.rolls([0] * 40)
                self.assertIsNone(r.queue6(compiled(gap_graph(game, title='The "Best" Garden'))))
                shown = r.walk_through()
                self.assertEqual(len(shown), 1)
                self.assertEqual(r.state()["phase"] in (IDLE, DONE), True)

    def test_g7_a_stranger_first(self):
        for game in self.games():
            for question in (False, True):
                with self.subTest(game=game, question=question):
                    g = gap_graph(game, roles={"visitor": {"kind": "stranger", "sex": "female"},
                                               "host": {"kind": "villager", "min_age": 14}})
                    if question:
                        g["start"] = "q"
                        g["nodes"] = {"q": {"type": "question", "text": "A visitor greets (host).",
                                            "choices": [{"label": "Welcome her", "next": "p"},
                                                        {"label": "Wave", "next": "p"}]},
                                      "p": {"text": "(Host) and the visitor talk. (visitor.He/She) smiles."}}
                    else:
                        g["nodes"]["p"]["text"] = "(Host) and the visitor talk. (visitor.He/She) smiles."
                    r = V6(game, TWO)
                    r.rolls([0] * 40)
                    self.assertIsNone(r.queue6(compiled(g)))
                    shown = r.walk_through([0] if question else ())
                    self.assertIn("Ana and the visitor talk. She smiles.", norm(" ".join(t for _k, t, _l in shown)))


PIPELINE_EVENTS = ("v20/all_v20_between_life_and_death.json", "v22/all_v22_4_parents_lesson.json")


@emulated
class PipelinePilots(unittest.TestCase):
    """Between Life and Death and The Parent's Lesson (Track D's pilots, seven buttons) compile and run in every
    game they list without Scrolling Popups: every button, each answer's popup of its own."""

    def test_the_seven_button_pilots_run_without_scrolling(self):
        root = ROOT / "data" / "event_collection"
        ran = 0
        for rel in PIPELINE_EVENTS:
            path = root / rel
            if not path.is_file():
                self.skipTest(f"{rel} is not on this branch")
            sys.path.insert(0, str(ROOT / "scripts"))
            import collection_check as cc
            graph = cc.graph_for_engine(json.loads(path.read_text(encoding="utf-8")))
            g = cg.load(copy.deepcopy(graph), scrolling=False, shared_pools={"pools": cc.shared_pools()})
            data = cg.compile_graph(g)
            start = g["nodes"][g["start"]]
            for game in (f"vv{n}" for n in g["games"]):
                if not have_stock(game):
                    continue
                for choice in range(len(start.get("choices", [])) or 1):
                    with self.subTest(event=rel, game=game, choice=choice):
                        people = [(0, "f", 30, "Ana", 20, False), (1, "m", 31, "Bo", 20, False),
                                  (2, "f", 35, "Cia", 20, False), (3, "m", 40, "Dov", 20, False),
                                  (4, "f", 8, "Eli", 0, False), (5, "m", 9, "Fin", 0, False)]
                        r = V6(game, people)
                        r.rolls([0] * 64)
                        r.p.export("VvfpStoryProbeGraphScroll", 0)
                        why = r.queue6(data)
                        self.assertIsNone(why, why)
                        try:
                            shown = r.walk_through([choice] * 16)
                        except ValueError as e:
                            if "not in list" not in str(e):
                                raise
                            continue               # this choice is not shown in this game (its if)
                        self.assertIn(r.state()["phase"], (IDLE, DONE))
                        self.assertTrue(shown)
                        for _kind, text, _labels in shown:
                            self.assertLessEqual(len(text), 2000)
                        ran += 1
        self.assertGreater(ran, 0)


@emulated
class G1LayoutParity(unittest.TestCase):
    """G1: the answer page after five or more buttons is laid out in the NOTICE layout (the plain popup the engine
    shows it through) by both sides: for each game, the line counts at which it takes one page and two are the same
    in the engine and in src/vv_cie_graph.py (GAMES[g].plain) -- New Believers 14 lines, not the result's 17."""

    def engine_pages(self, game: str, lines: int) -> int:
        text = "\n".join(f"Line {i + 1}." for i in range(lines))
        choices = [{"label": f"Door {k + 1}", "next": "d"} for k in range(5)]
        g = gap_graph(game, start="q", nodes={
            "q": {"type": "question", "text": "(Name) sees doors.", "choices": choices},
            "d": {"text": text}})
        r = V6(game, TWO)
        r.rolls([0] * 40)
        r.p.export("VvfpStoryProbeGraphScroll", 0)
        self.assertIsNone(r.queue6(compiled(g)))
        shown = r.walk_through([0])
        self.assertEqual(shown[1][1], "", "five buttons: nothing in the question's popup")
        return len(shown) - 2                      # the question, its (empty) result, then the answer's pages

    def test_the_g1_page_takes_the_notice_layout_in_both(self):
        for game in GAME_IDS:
            if not have_stock(game):
                continue
            n = int(game[2])
            plain = cg.GAMES[n].plain
            title = "The Gaps"
            # The most one-line paragraphs one notice page holds, as Python counts it.
            fit = max(k for k in range(1, 40)
                      if len(cg.paginate(plain, title, "\n".join(f"Line {i + 1}." for i in range(k)))[0]) == 1)
            with self.subTest(game=game, lines=fit):
                self.assertEqual(self.engine_pages(game, fit), 1, "the engine holds as many on one page")
            with self.subTest(game=game, lines=fit + 1):
                self.assertEqual(self.engine_pages(game, fit + 1), 2, "and no more")
            if n == 5:
                result = cg.GAMES[5].result
                self.assertGreater(result.lines, plain.lines, "New Believers: the result popup is taller")
                self.assertEqual(plain.lines, 14)


if __name__ == "__main__":
    unittest.main()
