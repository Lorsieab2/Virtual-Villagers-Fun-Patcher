"""New Believers' Heathen-Exclusive Events HE-01..HE-45 and their engine pieces (the owner approved them 2026-11-23;
docs/event-collection/cie-v6-binary.md 46).

The compiler side (src/vv_cie_graph.py): the grave requirement "min_graves", the encampment actions, the Heathens
group targets, the "oldest" preference and change_age "16.5" compile and read back the same; each is New Believers'
own.

The engine side (native/vvfp_story_upgrades/story_graph.inc, story_c5.inc), the test build beside New Believers'
rendered executable in the emulator:
* E8: an event asking for N graves is refused below N, offered at N (the game's count stood in for);
* E9: the encampment honoring / reflecting starts through "Memorial Actions Can Also Occur at the Heathen Hovel"'s own
  entries (0x494B83 / 0x494DF1) when its bytes are in, and sits the villager ("Sitting") without them;
* E10: a Heathens group takes every ordinary Heathen (or N at random) -- never a believer, never a puzzle's Heathen
  (roles 12-17), never a sick one -- and nobody without the row;
* "oldest": the oldest villager the role may take; "16.5": exactly 330 age units.

The events themselves (data/event_collection/drafts_d/dr_he): the owner's text word for word, each role an ordinary
Heathen ("only") but HE-13's and HE-25's believer, the ages and counts, the effects, the Guardians of Isola forms,
"(no effect)" never written twice, HE-05 and HE-13 asking for a grave, and each run on emulated New Believers.
"""
from __future__ import annotations

import copy
import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT / "scripts"))

import vv_cie_graph as cg  # noqa: E402
from test_story_custom_island_event import HAVE_EMULATOR, emulated, have_stock  # noqa: E402

if HAVE_EMULATOR:
    from test_story_cie_graph_runtime_v6 import V6

FACTION, ROLE, SICK, ACTION = 0x1CEC, 0x1CFC, 0x1C48, 0x1D10
ROW = "vv5_heathens_in_island_events"
SITTING = 0x28
DO_ACTION5 = 0x465580
HOVEL_HONOR, HOVEL_REFLECT = 0x494B83, 0x494DF1


def graph(effects=None, roles=None, requirement=None, games=(5,)) -> dict:
    g = {"format": "vvfp-cie-graph", "version": 6, "title": "Camp Life", "games": list(games),
         "roles": roles or {"subject": {"kind": "villager", "min_age": 14, "heathens": "only"}},
         "start": "p",
         "nodes": {"p": {"text": "(subject) sits by the old mud hut.", "auto_text": True,
                         "effects": effects if effects is not None else []}}}
    if requirement:
        g["requirement"] = requirement
    return g


def compiled(g: dict) -> bytes:
    return cg.compile_graph(cg.load(copy.deepcopy(g), scrolling=True))


class Compiler(unittest.TestCase):
    def test_the_new_pieces_read_back(self):
        fx = [{"do": "action", "role": "subject", "action": "Honoring the dead (at the encampment)"},
              {"do": "action", "role": "subject", "action": "Reflecting (at the encampment)"},
              {"do": "action", "target": {"heathens": "all"},
               "action": "Honoring the dead or reflecting (at the encampment)"},
              {"do": "skill", "target": {"heathens": 2}, "skills": ["Building"], "min": 5, "max": 10},
              {"do": "change_age", "role": "subject", "to": "16.5"}]
        roles = {"subject": {"kind": "villager", "min_age": 18, "heathens": "only", "prefer": "oldest"}}
        back = cg.decompile_graph(compiled(graph(fx, roles, {"min_eligible": 1, "if": {"min_graves": 2}})))
        self.assertEqual(back["requirement"]["if"], {"min_graves": 2})
        self.assertEqual(back["roles"]["subject"]["prefer"], "oldest")
        got = [{k: v for k, v in e.items() if k != "src"} for e in back["nodes"]["p"]["effects"]]
        self.assertEqual(got[0]["action"], "Honoring the dead (at the encampment)")
        self.assertEqual(got[2]["target"], {"heathens": "all"})
        self.assertEqual(got[3]["target"], {"heathens": 2})
        self.assertEqual(got[4]["to"], "16.5")

    def test_the_binary_codes(self):
        data = compiled(graph([{"do": "action", "target": {"heathens": 3}, "action": "Relaxing"}],
                              requirement={"min_eligible": 1, "if": {"min_graves": 1}}))
        o_effect = struct.unpack_from("<I", data, 56)[0]
        code, role, flags, sel = data[o_effect:o_effect + 4]
        self.assertEqual((code, role, sel), (cg.EFFECT_CODES["action"], 254, 9))
        self.assertEqual(struct.unpack_from("<H", data, o_effect + 14)[0], 3)
        self.assertEqual(cg.COND_CODES["min_graves"], 20)
        self.assertEqual(cg.PREFER_CODES["oldest"], 6)
        self.assertEqual(cg.CHANGE_AGE_TO["16.5"], 7)

    def test_each_is_new_believers_own(self):
        for fx, req in (([], {"min_eligible": 1, "if": {"min_graves": 1}}),
                        ([{"do": "action", "role": "subject", "action": "Reflecting (at the encampment)"}], None),
                        ([{"do": "action", "target": {"heathens": "all"}, "action": "Relaxing"}], None)):
            with self.subTest(fx=fx, req=req):
                g = graph(fx, requirement=req, games=(4, 5))
                for r in g["roles"].values():
                    r.pop("heathens")
                _, problems = cg.validate(g, scrolling=True)
                self.assertTrue(any("New Believers' own" in p for p in problems), problems)

    def test_bad_values(self):
        for fx in ({"do": "action", "target": {"heathens": 0}, "action": "Relaxing"},
                   {"do": "action", "target": {"heathens": "some"}, "action": "Relaxing"}):
            _, problems = cg.validate(graph([fx]), scrolling=True)
            self.assertTrue(any("heathens" in p for p in problems), problems)
        _, problems = cg.validate(graph(requirement={"min_eligible": 1, "if": {"min_graves": 0}}), scrolling=True)
        self.assertTrue(any("min_graves is 1..255" in p for p in problems), problems)

    def test_the_engine_knows_the_same_words(self):
        engine = (ROOT / "native" / "vvfp_story_upgrades" / "story_graph.inc").read_text(encoding="utf-8")
        for words in cg.ENCAMPMENT_ACTIONS:
            self.assertIn(f'"{words}"', engine)
        c5 = (ROOT / "native" / "vvfp_story_upgrades" / "story_c5.inc").read_text(encoding="utf-8")
        mie = (ROOT / "native" / "vvfp_more_island_events" / "ceremony_games.inc").read_text(encoding="utf-8")
        for name in ("REGISTRATION", "CHOOSER", "CAVE_A", "CAVE_B"):
            ours = c5.split(f"C5_HOVEL_{name}[")[1].split("};")[0]
            theirs = mie.split(f"CR_HOVEL_{name}[")[1].split("};")[0]
            self.assertEqual(ours, theirs, f"the hovel patch's {name} bytes: the ceremony's own check")


@emulated
class Engine(unittest.TestCase):
    def setUp(self):
        if not have_stock("vv5"):
            self.skipTest("no New Believers")

    def run_with(self, people, heathens=(), puzzle=None, sick=None, patches=(ROW,), rolls=0, graves=-1,
                 hovel=False):
        r = V6("vv5", people)
        r.p.export("VvfpStoryProbeHeathenAging", 1, 0, 0)
        r.p.export("VvfpStoryProbeHeathenEvents", graves, 0)
        for i in heathens:
            r.p.write(r.v.record(i) + FACTION, b"\1")
            r.p.write(r.v.record(i) + SICK, b"\0")
            r.p.put32(r.v.record(i) + ROLE, 0)
        if puzzle is not None:
            r.p.put32(r.v.record(puzzle) + ROLE, 13)        # the Heathen Chief: a puzzle's Heathen
        if sick is not None:
            r.p.write(r.v.record(sick) + SICK, b"\1")
        if hovel:
            import build_vv5_hovel_memorial_actions as hv
            for patch in hv.feature()["patches"]:
                r.p.mu.mem_write(0x400000 + int(patch["offset"], 16), bytes.fromhex(patch["after"]))
            r.p.mu.ctl_flush_tb()
        r.calls = {"do": [], "honor": [], "reflect": []}
        self.stub(r, DO_ACTION5, 8, "do")
        self.stub(r, HOVEL_HONOR, 8, "honor")
        self.stub(r, HOVEL_REFLECT, 0, "reflect")
        text = "vv5\n" + "".join(p + "\n" for p in patches)
        buf = r.p.alloc(len(text) + 1)
        r.p.write(buf, text.encode("ascii") + b"\0")
        r.p.export("VvfpStoryProbeInstalledPatches", 5, buf)
        r.rolls(rolls if isinstance(rolls, list) else [rolls] * 40)
        return r

    @staticmethod
    def stub(r, va, pop, kind):
        from unicorn import UC_HOOK_CODE

        def fn(p):
            ecx = p.reg("ecx")
            r.calls[kind].append((ecx, [p.arg(i) for i in range(2)]))
            return 0, pop
        r.p.stub(va, fn)
        r.p.mu.hook_add(UC_HOOK_CODE, r.p._on_code, begin=va, end=va)

    def index_of(self, r, record_va):
        for i in range(10):
            if r.v.record(i) == record_va:
                return i
        return -1

    def camp(self, r):
        buf = r.p.alloc(8)
        r.p.export("VvfpStoryProbeHeathenEvents", -2, buf)
        return struct.unpack("<2i", r.p.read(buf, 8))

    ONE = [(0, "m", 30, "Tama", 0, False)]
    THREE = [(0, "m", 30, "Tama", 0, False), (1, "f", 28, "Lani", 0, False), (2, "m", 60, "Koa", 0, False)]

    # ---- E8 ----------------------------------------------------------------------------------------------------
    def test_the_grave_requirement(self):
        data = compiled(graph(requirement={"min_eligible": 1, "if": {"min_graves": 2}}))
        for graves, ok in ((0, False), (1, False), (2, True), (5, True)):
            with self.subTest(graves=graves):
                r = self.run_with(self.ONE, heathens=(0,), graves=graves)
                why = r.queue6(data, strict=True)
                if ok:
                    self.assertIsNone(why)
                else:
                    self.assertIsNotNone(why)
                    self.assertIn("at least 2 graves", why)

    # ---- E9 ----------------------------------------------------------------------------------------------------
    def test_encampment_actions_with_the_hovel_patch(self):
        for words, kind, want in (("Honoring the dead (at the encampment)", "honor", 1),
                                  ("Reflecting (at the encampment)", "reflect", 2)):
            with self.subTest(words=words):
                r = self.run_with(self.ONE, heathens=(0,), hovel=True)
                self.assertEqual(self.camp(r)[1], 1, "the hovel patch's bytes are in")
                self.assertIsNone(r.queue6(compiled(graph([{"do": "action", "role": "subject", "action": words}]))))
                r.walk_through()
                self.assertEqual(len(r.calls[kind]), 1, r.calls)
                self.assertEqual(self.camp(r)[0], want)
                self.assertFalse([c for c in r.calls["do"] if c[1][0] == SITTING], "never sat")
                if kind == "honor":
                    self.assertEqual(r.calls[kind][0][0], r.v.record(0))
                    self.assertEqual(r.calls[kind][0][1][0], 17)
                else:
                    self.assertEqual(r.p.u32(r.v.record(0) + ACTION), 29)

    def test_encampment_actions_without_the_hovel_patch_sit(self):
        for words in ("Honoring the dead (at the encampment)", "Reflecting (at the encampment)",
                      "Honoring the dead or reflecting (at the encampment)"):
            with self.subTest(words=words):
                r = self.run_with(self.ONE, heathens=(0,))
                self.assertEqual(self.camp(r)[1], 0)
                self.assertIsNone(r.queue6(compiled(graph([{"do": "action", "role": "subject", "action": words}]))))
                r.walk_through()
                self.assertEqual(r.calls["honor"] + r.calls["reflect"], [])
                self.assertEqual([c[1][0] for c in r.calls["do"] if c[0] == r.v.record(0)], [SITTING])
                self.assertIn(self.camp(r)[0], (11, 12))

    def test_either_is_the_ceremonys_split(self):
        for roll, kind in ((0, "honor"), (49, "honor"), (50, "reflect"), (99, "reflect")):
            with self.subTest(roll=roll):
                r = self.run_with(self.ONE, heathens=(0,), hovel=True, rolls=roll)
                fx = [{"do": "action", "role": "subject",
                       "action": "Honoring the dead or reflecting (at the encampment)"}]
                self.assertIsNone(r.queue6(compiled(graph(fx))))
                r.walk_through()
                self.assertEqual(len(r.calls[kind]), 1, (roll, r.calls))

    # ---- E10 ---------------------------------------------------------------------------------------------------
    def group_run(self, target, heathens, puzzle=None, sick=None, patches=(ROW,), action="Relaxing"):
        people = [(i, "m" if i % 2 else "f", 30 + i, f"P{i}", 0, False) for i in range(6)]
        roles = {"subject": {"kind": "villager", "min_age": 14, "heathens": "only"}}
        fx = [{"do": "action", "target": target, "action": action}]
        r = self.run_with(people, heathens=heathens, puzzle=puzzle, sick=sick, patches=patches)
        return r, r.queue6(compiled(graph(fx, roles)))

    def acted(self, r):
        return sorted({self.index_of(r, c[0]) for c in r.calls["do"]})

    def test_every_heathen_never_a_believer_a_puzzles_or_a_sick_heathen(self):
        r, why = self.group_run({"heathens": "all"}, heathens=(1, 2, 3, 4), puzzle=3, sick=4)
        self.assertIsNone(why)
        r.walk_through()
        self.assertEqual(self.acted(r), [1, 2], "the ordinary, well Heathens only: never 0, 5 (believers), 3, 4")

    def test_n_heathens_at_random(self):
        r, why = self.group_run({"heathens": 1}, heathens=(1, 2, 3))
        self.assertIsNone(why)
        r.walk_through()
        self.assertEqual(len(self.acted(r)), 1)
        self.assertTrue(set(self.acted(r)) <= {1, 2, 3})
        r, why = self.group_run({"heathens": 9}, heathens=(1, 2))
        r.walk_through()
        self.assertEqual(self.acted(r), [1, 2], "fewer than asked: all there are")

    def test_a_group_of_heathens_without_the_row_is_nobody(self):
        people = [(i, "m", 30 + i, f"P{i}", 0, False) for i in range(4)]
        fx = [{"do": "action", "target": {"heathens": "all"}, "action": "Relaxing"}]
        roles = {"subject": {"kind": "villager", "min_age": 14}}
        r = self.run_with(people, heathens=(1, 2), patches=())
        self.assertIsNone(r.queue6(compiled(graph(fx, roles))))
        r.walk_through()
        self.assertEqual(self.acted(r), [])

    def test_the_heathens_group_is_theirs_in_their_own_cast(self):
        """The flavor rule makes the tribe's groups nothing in the Heathens' own cast; a group of the Heathens
        themselves is made as always."""
        r, why = self.group_run({"heathens": "all"}, heathens=(0, 1, 2, 3, 4, 5))
        self.assertIsNone(why)
        r.walk_through()
        self.assertEqual(self.acted(r), [0, 1, 2, 3, 4, 5])

    # ---- oldest, 16.5 ------------------------------------------------------------------------------------------
    def test_oldest(self):
        roles = {"subject": {"kind": "villager", "min_age": 18, "heathens": "only", "prefer": "oldest"}}
        for rolls in (0, 99):
            r = self.run_with(self.THREE, heathens=(0, 1, 2), rolls=rolls)
            self.assertIsNone(r.queue6(compiled(graph([], roles))))
            r.walk_through()
            self.assertEqual(r.state()["records"][0], 2, "the oldest (60), whatever the roll")

    def test_age_sixteen_and_a_half(self):
        r = self.run_with(self.ONE, heathens=(0,))
        self.assertIsNone(r.queue6(compiled(graph([{"do": "change_age", "role": "subject", "to": "16.5"}]))))
        r.walk_through()
        self.assertEqual(r.v.i32(0, r.v.L["age"]), 330)


# ---- The events themselves ------------------------------------------------------------------------------------------

import json  # noqa: E402

import collection_check as cc  # noqa: E402
import collection_lib as lib  # noqa: E402

HE_DIR = lib.DRAFTS_D_DIR / "dr_he"
SPECIAL_ROLES = range(12, 18)


def he_docs() -> dict[str, dict]:
    return {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in sorted(HE_DIR.glob("*.json"))}


def he_compiled(doc: dict) -> bytes:
    g, problems = cg.validate(cc.graph_for_engine(doc), scrolling=True, shared_pools={"pools": cc.shared_pools()})
    assert not problems, problems
    return cg.compile_graph(g)


def doc_texts(doc: dict) -> list[str]:
    out = [doc["title"], doc["collection"]["description"]]
    for nd in doc["nodes"].values():
        out.append(nd.get("text", ""))
        out += [c["label"] for c in nd.get("choices", [])]
    return out


class TheEvents(unittest.TestCase):
    """The 45 files: the owner's text, the casting, the effects, Guardians of Isola, "(no effect)"."""

    @classmethod
    def setUpClass(cls):
        cls.docs = he_docs()

    def test_forty_five_new_believers_only_events_in_one_series(self):
        self.assertEqual(len(self.docs), 45)
        for name, doc in self.docs.items():
            self.assertEqual(doc["games"], [5], name)
            self.assertEqual(doc["collection"]["series"], "dr_he", name)
            self.assertEqual(doc["collection"]["draw_weight"], 1, name)
            self.assertEqual(doc["collection"]["source"], "heathen_ex", name)

    def test_the_source_is_frozen_and_covered(self):
        self.assertEqual(lib.recorded_sha256("heathen_ex"), lib.source_sha256("heathen_ex"))
        data = json.loads(lib.MANIFEST.read_text(encoding="utf-8"))
        self.assertEqual(data["heathen_ex"]["uncovered_lines"], [])
        self.assertEqual(data["heathen_ex"]["overlaps"], [])

    def test_every_file_passes_the_collection_check(self):
        rows = {r["id"]: r for r in json.loads(lib.MANIFEST.read_text(encoding="utf-8"))["rows"]}
        for p in sorted(HE_DIR.glob("*.json")):
            with self.subTest(p.stem):
                rep = cc.check_file(p, rows)
                self.assertEqual(rep.problems, [], p.stem)

    def test_casting(self):
        believers = {"he13_two_peoples_one_grief": {"friend"}, "he25_heathen_toy_lost_found": {"friend"}}
        roles_file = json.loads((lib.COLLECTION_DIR / "heathen_roles.json").read_text(encoding="utf-8"))["events"]
        for name, doc in self.docs.items():
            with self.subTest(name):
                villagers = {r: s for r, s in doc["roles"].items() if s["kind"] == "villager"}
                want_b = believers.get(name, set())
                self.assertEqual({r for r, s in villagers.items() if not s.get("heathens")}, want_b)
                for r, s in villagers.items():
                    if r not in want_b:
                        self.assertEqual(s["heathens"], "only")
                self.assertEqual(doc["requirement"]["min_eligible"], len(villagers))
                entry = roles_file[name]
                self.assertEqual(entry.get("exclusive", False), not want_b)
                self.assertEqual(set(entry["roles"]), set(villagers) - want_b)

    def test_the_age_bands_and_counts(self):
        want = {1: [(18, None)], 4: [(8, None), (8, None)], 7: [(3, 13), (18, None)], 9: [(14, None)] * 3,
                10: [(18, None), (0, None)], 12: [(18, None), (8, None)], 13: [(18, None), (18, None)],
                14: [(14, None)], 24: [(18, None), (0, None), (0, None)], 25: [(3, 13), (3, 13)],
                27: [(3, 13), (3, 13), (18, None)], 28: [(14, 17)], 34: [(18, None), (3, 13)],
                40: [(8, None)] * 3, 41: [(8, 17), (8, 17)], 44: [(18, 19)]}
        for name, doc in self.docs.items():
            num = int(name[2:4])
            if num in want:
                got = [(s["min_age"], s.get("max_age")) for s in doc["roles"].values() if s["kind"] == "villager"]
                self.assertEqual(got, want[num], name)
        for num in (24, 34, 43):
            doc = next(d for n, d in self.docs.items() if n.startswith(f"he{num}_"))
            self.assertEqual(doc["roles"]["subject"].get("prefer"), "oldest", num)

    def test_the_grave_requirement(self):
        for name, doc in self.docs.items():
            want = {"min_graves": 1} if name[:4] in ("he05", "he13") else None
            self.assertEqual(doc["requirement"].get("if"), want, name)

    def test_no_faith_no_death_no_conversion(self):
        for name, doc in self.docs.items():
            for nd in doc["nodes"].values():
                for e in nd.get("effects", []):
                    self.assertNotIn(e["do"], ("faith", "join", "status", "apostasy", "kill", "vanish",
                                               "die_unrecovered", "food", "tech", "pay_award", "damage", "repair",
                                               "supply", "trade", "village", "new_villager"), name)

    def test_the_encampment_and_the_group(self):
        def fx(num):
            doc = next(d for n, d in self.docs.items() if n.startswith(f"he{num:02d}_"))
            return [e for nd in doc["nodes"].values() for e in nd.get("effects", [])]
        for num in (10, 24):
            self.assertIn({"do": "action", "target": {"heathens": "all"},
                           "action": "Honoring the dead or reflecting (at the encampment)"},
                          [{k: v for k, v in e.items() if k != "src"} for e in fx(num)])
        self.assertIn("Scratching for roots (Unsafe)", [e.get("action") for e in fx(29)])
        self.assertIn({"do": "change_age", "role": "subject", "to": "16.5"},
                      [{k: v for k, v in e.items() if k != "src"} for e in fx(17)])

    def test_the_owners_words_and_no_effect_once(self):
        source = lib.SOURCES["heathen_ex"][0].read_text(encoding="utf-8")
        for name, doc in self.docs.items():
            for t in doc_texts(doc):
                plain = t.replace("\\(", "(").replace("\\)", ")")
                self.assertLessEqual(plain.count("(no effect)"), 1, (name, t))
                self.assertNotIn("Guardian", t)
        # the draft's own "(no effect)" lines are shown as written (HE-03, 08, 11, 12, 16, 17, 18, 23, 24, 30, 35)
        shown = sum(t.count("\\(no effect\\)") for d in self.docs.values() for t in doc_texts(d))
        lines = source.split("\n")
        in_events = sum(lines[n - 1].count("(no effect)") for d in self.docs.values()
                        for n in range(d["collection"]["lines"][0], d["collection"]["lines"][1] + 1))
        self.assertEqual(shown, in_events)
        self.assertGreaterEqual(shown, 11)

    def test_guardians_forms(self):
        for name, doc in self.docs.items():
            with self.subTest(name):
                if "Heathen" in doc["title"]:
                    self.assertEqual(doc["title_variants"][0]["if"], cc.GUARDIANS_IF)
                    self.assertNotIn("Heathen", doc["title_variants"][0]["title"])
                for nd in doc["nodes"].values():
                    if "Heathen" in nd.get("text", ""):
                        form = nd["variants"][0]
                        self.assertEqual(form["if"], cc.GUARDIANS_IF)
                        self.assertNotIn("Heathen", form["text"])
                        self.assertNotIn("Guardian", form["text"])
        titles = {d["title"]: d.get("title_variants", [{}])[0].get("title") for d in self.docs.values()}
        for before, after in (("The Heathen Day of Honor", "The Isolan Day of Honor"),
                              ("The Heathen Daredevil", "The Isolan Daredevil"),
                              ("The Heathen Vision", "The Isolan Vision"),
                              ("The Clumsy Heathen's Good Turn", "The Clumsy Isolan's Good Turn"),
                              ("The Heathens' Remembrance", "The Isolans' Remembrance"),
                              ("The Heathen Toy, Lost and Found", "The Isolan Toy, Lost and Found"),
                              ("The Missing Heathen Kids", "The Missing Isolan Kids"),
                              ("The Heathen Weaver", "The Isolan Weaver"),
                              ("The Heathen Cook's Pride", "The Isolan Cook's Pride")):
            self.assertEqual(titles[before], after)


@emulated
class TheEventsRun(unittest.TestCase):
    """Each event cast and run on emulated New Believers, every answer: only ordinary Heathens (and HE-13's / HE-25's
    believer) are cast, never a puzzle's Heathen; the village's stores never move; the pages never say "(no effect)"
    twice; with Guardians of Isola Rewrite they never say Heathen."""

    # 0-5 Heathens of every age band, 6 a believer adult, 7 a believer child, 8 the Heathen Chief (role 13, the
    # oldest of all), 9 a sick Heathen
    PEOPLE = [(0, "f", 6, "Ana", 0, False), (1, "m", 10, "Bo", 0, False), (2, "f", 15, "Cai", 0, False),
              (3, "m", 18, "Dov", 0, False), (4, "f", 32, "Eli", 0, False), (5, "m", 61, "Fen", 0, False),
              (6, "f", 30, "Gia", 0, False), (7, "m", 9, "Hal", 0, False), (8, "m", 70, "Ivo", 0, False),
              (9, "f", 40, "Jun", 0, False)]
    HEATHENS = {0, 1, 2, 3, 4, 5}

    def setUp(self):
        if not have_stock("vv5"):
            self.skipTest("no New Believers")

    def village(self, patches=(ROW,), graves=1):
        from test_story_cie_graph_runtime import stores  # noqa: F401
        r = V6("vv5", self.PEOPLE)
        r.p.export("VvfpStoryProbeHeathenAging", 1, 0, 0)
        r.p.export("VvfpStoryProbeHeathenEvents", graves, 0)
        for i in (0, 1, 2, 3, 4, 5, 8, 9):
            r.p.write(r.v.record(i) + FACTION, b"\1")
            r.p.write(r.v.record(i) + SICK, b"\0")
            r.p.put32(r.v.record(i) + ROLE, 0)
        r.p.put32(r.v.record(8) + ROLE, 13)
        r.p.write(r.v.record(9) + SICK, b"\1")
        text = "vv5\n" + "".join(p + "\n" for p in patches)
        buf = r.p.alloc(len(text) + 1)
        r.p.write(buf, text.encode("ascii") + b"\0")
        r.p.export("VvfpStoryProbeInstalledPatches", 5, buf)
        r.rolls([0] * 200)
        return r

    def run_all(self, guardians: bool):
        from test_story_cie_graph_runtime import stores
        patches = (ROW, "vv5_guardians_of_isola_rewrite") if guardians else (ROW,)
        for name, doc in he_docs().items():
            data = he_compiled(doc)
            answers = len(doc["nodes"]["setup"].get("choices", [])) or 1
            believers = [k for k, (rid, s) in enumerate(doc["roles"].items())
                         if s["kind"] == "villager" and not s.get("heathens")]
            for answer in range(answers if not guardians else 1):
                with self.subTest(name=name, answer=answer, guardians=guardians):
                    r = self.village(patches)
                    before = stores(r)
                    self.assertIsNone(r.queue6(data, strict=True), name)
                    shown = r.walk_through([answer] if doc["nodes"]["setup"].get("choices") else [])
                    cast = [i for i in r.state()["records"] if i >= 0]
                    villagers = [k for k, s in enumerate(doc["roles"].values()) if s["kind"] == "villager"]
                    for k in villagers:
                        i = r.state()["records"][k]
                        if k in believers:
                            self.assertIn(i, (6, 7), "the believer's role takes a believer")
                        else:
                            self.assertIn(i, self.HEATHENS, "an ordinary, well Heathen")
                    self.assertNotIn(8, cast)
                    self.assertNotIn(9, cast)
                    self.assertEqual(stores(r), before, "the village's stores never move")
                    words = " ".join(" ".join(s[1] for s in shown).split())
                    for page in shown:
                        self.assertLessEqual(page[1].count("(no effect)"), 1, page[1])
                    if guardians:
                        self.assertNotIn("Heathen", words)
                        self.assertNotIn("Guardian", words)

    def test_each_event_every_answer(self):
        self.run_all(False)

    def test_each_event_with_guardians_of_isola(self):
        self.run_all(True)

    def test_without_the_row_none_is_offered(self):
        for name, doc in he_docs().items():
            r = self.village(patches=())
            self.assertIsNotNone(r.queue6(he_compiled(doc), strict=True), name)

    def test_after_every_heathen_joined_none_is_offered(self):
        for name, doc in he_docs().items():
            r = self.village()
            for i in (0, 1, 2, 3, 4, 5, 9):
                r.p.write(r.v.record(i) + FACTION, b"\0")
            self.assertIsNotNone(r.queue6(he_compiled(doc), strict=True), name)

    def test_no_grave_no_mausoleum(self):
        for name, doc in he_docs().items():
            if name[:4] in ("he05", "he13"):
                r = self.village(graves=0)
                self.assertIsNotNone(r.queue6(he_compiled(doc), strict=True), name)

    def test_the_effects_reach_the_heathen(self):
        docs = he_docs()
        # HE-17 "Drink It": exactly 16 and a half
        r = self.village()
        self.assertIsNone(r.queue6(he_compiled(docs["he17_strange_nectar_camp"]), strict=True))
        r.walk_through([0])
        who = r.state()["records"][0]
        self.assertEqual(r.v.i32(who, r.v.L["age"]), 330)
        # HE-14 "Let It Go": -15 health
        r = self.village()
        self.assertIsNone(r.queue6(he_compiled(docs["he14_bed_bugs_camp"]), strict=True))
        h = {i: r.v.i32(i, r.v.L["health"]) for i in range(10)}
        r.walk_through([1])
        who = r.state()["records"][0]
        self.assertIn(who, self.HEATHENS)
        self.assertEqual(r.v.i32(who, r.v.L["health"]), h[who] - 15, h)
        # HE-10: every ordinary Heathen honors or reflects (no hovel patch here: each sits), nobody else
        r = self.village()
        sat = []
        r.calls = {"do": [], "honor": [], "reflect": []}
        Engine.stub(r, DO_ACTION5, 8, "do")
        self.assertIsNone(r.queue6(he_compiled(docs["he10_heathen_day_honor"]), strict=True))
        r.walk_through()
        for va, args in r.calls["do"]:
            if args[0] == SITTING:
                sat.append(va)
        self.assertEqual(sorted(sat), sorted(r.v.record(i) for i in self.HEATHENS))


if __name__ == "__main__":
    unittest.main()
