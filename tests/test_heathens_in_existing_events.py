"""New Believers: Heathens in the existing island events (the owner, 2026-11-23; docs/event-collection/cie-v6-binary.md
45 and 45a).

THE TABLE.  The owner's approved audit ("Heathens in Existing Events", part 4) is kept verbatim in
data/event_collection/heathen_roles_audit.tsv; scripts/build_heathen_roles.py turns it into
data/event_collection/heathen_roles_existing.json by the owner's rulings (YES, YES+WORDING, ONLY-IF-ALL-HEATHENS and NO
-> "allowed"; SAME-FACTION -> "kin"; ALREADY and no villager -> nothing).  Every row is checked, and twenty by hand
through the compiled collection.

THE ENGINE (the test build of "VVFP Story Upgrades.dll" in the emulator):
* "kin": a family role is a Heathen only beside Heathen family, a believer only beside believers (a kinship relation
  and a pregnancy's two parents);
* a cast Heathen's "believer" words are swapped automatically ("a person of faith"), Guardians of Isola's too, never
  "Guardians";
* a puzzle's Heathen (roles 12-17) may be cast, and their record is byte for byte the same after every kind of
  effect: told ("(no effect)"), never made.

THE STOCK EVENTS (New Believers' rendered executable, the companion installed): with the row the believer part of an
event may draw an ordinary Heathen -- in proportion, never roles 12-17, never a sick one; a Heathen part never takes
the same Heathen; the Faith part of The Vision, The Mask, Doubt, The Spa and The Cracked Mask never reaches a drawn
Heathen; the group events reach ordinary Heathens.  Each check is also made without the row (mutation: stock).
"""
from __future__ import annotations

import collections
import copy
import struct
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests"))

import vv_cie_graph as cg  # noqa: E402
import build_heathen_roles as hr  # noqa: E402
from test_story_custom_island_event import HAVE_EMULATOR, emulated, have_stock  # noqa: E402

if HAVE_EMULATOR:
    from test_story_cie_graph_runtime_v6 import V6
    from story_emulator import Process
    from story_custom_fixtures import Village
    from test_story_outcomes import TEST_DLL, render

FACTION, ROLE, SICK, FAITH = 0x1CEC, 0x1CFC, 0x1C48, 0x1CF0
MOTHER_NAME = 0x1BD9
ROW = "vv5_heathens_in_island_events"
STRIDE = 0x2F44

# The draft's own totals (part 4): events by verdict, roles by verdict.
DRAFT_EVENTS = {"YES": 4268, "NO": 29, "ALREADY": 10, "NO-VILLAGER": 53}
DRAFT_ROLES = {"YES": 6657, "YES+WORDING": 437, "SAME-FACTION": 295, "ONLY-IF-ALL-HEATHENS": 30, "NO": 61,
               "ALREADY": 10}


def compiled(g: dict) -> bytes:
    return cg.compile_graph(cg.load(copy.deepcopy(g), scrolling=True))


class Table(unittest.TestCase):
    rows = hr.audit_rows()

    def test_the_audit_is_the_owners_draft(self):
        roles = collections.Counter(v for _e, r, v, _l in self.rows if r)
        self.assertEqual(dict(roles), DRAFT_ROLES)
        self.assertEqual(sum(roles.values()), 7490)
        events = {}
        for e, r, v, _l in self.rows:
            events.setdefault(e, set()).add(v)
        self.assertEqual(len(events), 4360)
        self.assertEqual(sum(1 for vs in events.values() if vs == {"NO-VILLAGER"}), DRAFT_EVENTS["NO-VILLAGER"])

    def test_every_row_maps_by_the_owners_rulings(self):
        made = hr.modes(self.rows)
        want = {"YES": "allowed", "YES+WORDING": "allowed", "ONLY-IF-ALL-HEATHENS": "allowed", "NO": "allowed",
                "SAME-FACTION": "kin"}
        for e, r, v, link in self.rows:
            if v in want:
                self.assertEqual(made[e][r], want[v], (e, r, v))
                if v == "SAME-FACTION":
                    self.assertTrue(link, f"{e} {r}: a family role names its family link")
            elif r:
                self.assertNotIn(r, made.get(e, {}), (e, r, v))
        # the 8 Living Engine "person of faith" events (the owner's Q7: YES) and every NO: allowed
        for e in ("lvauth22_chief_false", "lvauth27_spiritual", "lvuns15_mask_forest", "lvuns21_gods_need",
                  "lvuns23_silence_after", "lvuns31_price_legend", "lvuns34_god_may_have", "lvuns37_unproven"):
            self.assertTrue(made[e] and set(made[e].values()) == {"allowed"}, e)

    def test_the_generated_file_is_current(self):
        done = subprocess.run([sys.executable, str(ROOT / "scripts" / "build_heathen_roles.py"), "--check"],
                              capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stderr)

    def test_every_new_believers_event_role_is_judged(self):
        import json
        judged = {(e, r) for e, r, _v, _l in self.rows}
        events = {e for e, _r, _v, _l in self.rows}
        for path in (ROOT / "data" / "event_collection").rglob("*.json"):
            try:
                d = json.loads(path.read_text(encoding="utf-8"))
            except ValueError:
                continue
            if not (isinstance(d, dict) and d.get("format") == "vvfp-cie-graph"
                    and isinstance(d.get("collection"), dict) and 5 in d.get("games", [])):
                continue
            ident = d["collection"]["id"]
            if ident.startswith("he"):      # the Heathen-only events (heathen_roles.json, their own audit)
                continue
            self.assertIn(ident, events, path)
            for rid, r in (d.get("roles") or {}).items():
                if isinstance(r, dict) and r.get("kind", "villager") == "villager":
                    self.assertIn((ident, rid), judged)

    # Twenty by hand: (event, role, the draft's verdict, the compiled mode).
    BY_HAND = (
        ("il001_mister_pebbles", "subject", "YES", "allowed"),
        ("il001_mister_pebbles", "friend", "YES", "allowed"),
        ("il052_morning_song", "child", "SAME-FACTION", "kin"),
        ("il196_same_argument", "friend", "SAME-FACTION", "kin"),
        ("b222_singing_boat", "subject", "SAME-FACTION", "kin"),
        ("s090_baby_ferns", "subject", "SAME-FACTION", "kin"),
        ("il149_experiment", "subject", "YES+WORDING", "allowed"),
        ("anhs11_chief_nobody", "worker", "YES+WORDING", "allowed"),
        ("hum43_tug_war_nobody", "judge", "ONLY-IF-ALL-HEATHENS", "allowed"),
        ("b250_contest_best", "chief", "ONLY-IF-ALL-HEATHENS", "allowed"),
        ("lbl086_unpopular_chief", "leader", "ONLY-IF-ALL-HEATHENS", "allowed"),
        ("blf07_blessing_canoe", "friend", "NO", "allowed"),
        ("lvuns23_silence_after", "believer", "NO", "allowed"),
        ("lvuns23_silence_after", "scientist", "NO", "allowed"),
        ("hc6_sabotage", "prankster", "NO", "allowed"),
        ("vv5_great_laundry_mishap", "finder", "NO", "allowed"),
        ("vv5_great_laundry_mishap", "isolan", "ALREADY", "never"),
        ("blf26_isolan_feast", "friend", "ALREADY", "never"),
        ("vv5_field_day", "player", "YES+WORDING", "allowed"),
        ("tim138_shells_breeze", "subject", "YES", "allowed"),
    )

    def test_twenty_by_hand_through_the_compiled_collection(self):
        import build_event_collection_features as ec
        self.assertEqual(len(self.BY_HAND), 20)
        verdicts = {(e, r): v for e, r, v, _l in self.rows}
        events = ec.compile_events(only={e for e, *_ in self.BY_HAND})
        by_id = {x["id"]: x for x in events}
        for e, r, verdict, mode in self.BY_HAND:
            with self.subTest(event=e, role=r):
                self.assertEqual(verdicts[(e, r)], verdict)
                roles = cg.decompile_graph(by_id[e]["cieg"])["roles"]
                self.assertEqual(roles[r].get("heathens", "never"), mode)

    def test_kin_is_bits_5_and_3_and_back(self):
        g = {"format": "vvfp-cie-graph", "version": 6, "title": "Kin", "games": [5],
             "roles": {"a": {"kind": "villager", "min_age": 14, "heathens": "allowed"},
                       "b": {"kind": "villager", "min_age": 14, "heathens": "kin", "relation": {"sibling_of": "a"}}},
             "start": "p", "nodes": {"p": {"text": "(a) and (b) talk."}}}
        data = compiled(g)
        o_role = struct.unpack_from("<I", data, 44)[0]
        self.assertEqual(data[o_role + 16 + 13] & 0x38, 0x28)
        self.assertEqual(cg.decompile_graph(data)["roles"]["b"]["heathens"], "kin")

    def test_the_rows_stock_sites_are_the_engines_and_the_executables(self):
        import re
        import build_island_event_content_features as rows
        inc = (ROOT / "native" / "vvfp_story_upgrades" / "story_heathen_stock.inc").read_text(encoding="utf-8")
        groups = {int(x, 16) for x in re.findall(r"0x([0-9A-F]{6})u",
                                                  inc[inc.index("HV_GROUPS[]"):inc.index("HV_GROUP_COUNT")])}
        listed = {va for va, target, _ in rows.STOCK_SITES if target == 0x470C60}
        self.assertEqual(listed, groups)
        self.assertNotIn(0x414A81, groups, "The Allergy Season already reaches the Heathens (0x470D60)")
        self.assertNotIn(0x4153C4, groups, "The Salty Air likewise")
        exe = ROOT / "inputs" / "vv5-stock-copy" / "Virtual Villagers - New Believers.exe"
        if not exe.is_file():
            self.skipTest("no New Believers")
        data = exe.read_bytes()
        for va, target, _ in rows.STOCK_SITES:
            self.assertEqual(data[va - 0x400000:va - 0x400000 + 5].hex().upper(), rows.call_bytes(va, target))

    def test_the_puzzle_line_is_flavor(self):
        self.assertEqual(cg.AUTO_LINES["pz_flavor"], "Nothing really happens to <W>. (no effect)")
        engine = (ROOT / "native" / "vvfp_story_upgrades" / "story_graph.inc").read_text(encoding="utf-8")
        self.assertIn('{ "pz_flavor", "Nothing really happens to <W>. (no effect)" }', engine)


def run_with(people, heathens=(), puzzle=(), patches=(ROW,), rolls=0, aging=1):
    r = V6("vv5", people)
    r.p.export("VvfpStoryProbeHeathenAging", aging, 0, 0)
    for i in heathens:
        r.p.write(r.v.record(i) + FACTION, b"\1")
        r.p.write(r.v.record(i) + SICK, b"\0")
        r.p.put32(r.v.record(i) + ROLE, 0)
    for i in puzzle:
        r.p.write(r.v.record(i) + FACTION, b"\1")
        r.p.put32(r.v.record(i) + ROLE, 14)          # a Master
    text = "vv5\n" + "".join(p + "\n" for p in patches)
    buf = r.p.alloc(len(text) + 1)
    r.p.write(buf, text.encode("ascii") + b"\0")
    r.p.export("VvfpStoryProbeInstalledPatches", 5, buf)
    r.rolls([rolls] * 60)
    return r


def words(r) -> str:
    return " ".join(" ".join(s[1] for s in r.walk_through()).split())


@emulated
class Engine(unittest.TestCase):
    def setUp(self):
        if not have_stock("vv5"):
            self.skipTest("no New Believers")

    TWO = [(0, "m", 30, "Tama", 0, False), (1, "f", 28, "Lani", 0, False)]

    def siblings(self, r, *who):
        for i in who:
            r.p.write(r.v.record(i) + MOTHER_NAME, b"Mara\0")

    def kin_graph(self, mode: str) -> bytes:
        return compiled({"format": "vvfp-cie-graph", "version": 6, "title": "Kin", "games": [5],
                         "roles": {"a": {"kind": "villager", "min_age": 14, "heathens": "allowed"},
                                   "b": {"kind": "villager", "min_age": 14, "heathens": mode,
                                         "relation": {"sibling_of": "a"}}},
                         "start": "p", "nodes": {"p": {"text": "(a) and (b) talk."}}})

    def test_kin_keeps_a_family_one_faction(self):
        # a Heathen and a believer, siblings: "allowed" casts them together; "kin" never
        r = run_with(self.TWO, heathens=(1,))
        self.siblings(r, 0, 1)
        self.assertIsNone(r.queue6(self.kin_graph("allowed"), strict=True), "mutation: without kin they are cast")
        r = run_with(self.TWO, heathens=(1,))
        self.siblings(r, 0, 1)
        self.assertIsNotNone(r.queue6(self.kin_graph("kin"), strict=True), "kin: never a Heathen beside a believer")
        for heathens in ((0, 1), ()):
            with self.subTest(heathens=heathens):
                r = run_with(self.TWO, heathens=heathens)
                self.siblings(r, 0, 1)
                self.assertIsNone(r.queue6(self.kin_graph("kin"), strict=True), "one faction: cast")
        r = run_with(self.TWO, heathens=(1,), patches=())
        self.siblings(r, 0, 1)
        self.assertIsNotNone(r.queue6(self.kin_graph("kin"), strict=True), "no row: never a Heathen")

    def test_a_pregnancy_is_between_two_heathens_only(self):
        g = {"format": "vvfp-cie-graph", "version": 6, "title": "Baby", "games": [5],
             "roles": {"mum": {"kind": "villager", "min_age": 18, "sex": "female", "heathens": "kin"},
                       "dad": {"kind": "villager", "min_age": 18, "sex": "male", "heathens": "allowed"}},
             "start": "p", "nodes": {"p": {"text": "(mum) and (dad) smile.",
                                           "effects": [{"do": "pregnant", "role": "mum", "partner": "dad"}]}}}
        people = [(0, "f", 28, "Lani", 0, False), (1, "m", 30, "Tama", 0, False)]
        r = run_with(people, heathens=(0,))
        self.assertIsNotNone(r.queue6(compiled(g), strict=True), "a Heathen mother, a believer father: never")
        r = run_with(people, heathens=(0, 1))
        self.assertIsNone(r.queue6(compiled(g), strict=True), "two Heathens")
        r = run_with(people)
        self.assertIsNone(r.queue6(compiled(g), strict=True), "two believers")

    def believer_graph(self, role: str, text: str, guardians: str | None = None) -> bytes:
        node = {"text": text}
        g = {"format": "vvfp-cie-graph", "version": 6, "title": "Faith", "games": [5],
             "roles": {role: {"kind": "villager", "min_age": 14, "heathens": "allowed"}},
             "start": "p", "nodes": {"p": node}}
        if guardians:
            node["variants"] = [{"if": {"patch": "guardians_of_isola"}, "text": guardians}]
            g["patches"] = ["guardians_of_isola"]
        return compiled(g)

    def test_a_cast_heathens_believer_words_are_swapped(self):
        one = [(0, "m", 30, "Tama", 0, False)]
        cases = (
            ("friend", "(friend), a believer, asks to bless the canoe.", None,
             "a person of faith, asks to bless the canoe."),
            ("subject", "Nobody would guess that (name1) is a believer.", None,
             "Nobody would guess that Tama is a person of faith."),
            ("believer", "A believer asks why the storm came. The believer finds comfort.", None,
             "A person of faith asks why the storm came. The person of faith finds comfort."),
        )
        for role, text, guardians, want in cases:
            with self.subTest(role=role):
                r = run_with(one, heathens=(0,))
                self.assertIsNone(r.queue6(self.believer_graph(role, text, guardians)))
                said = words(r)
                self.assertIn(want, said)
                self.assertNotIn("believer", said)
                r = run_with(one)                      # a believer cast: as written
                self.assertIsNone(r.queue6(self.believer_graph(role, text, guardians)))
                self.assertIn("believer", words(r))
        # Guardians of Isola: "a villager of faith" -> "a person of faith", never "Guardians"
        r = run_with(one, heathens=(0,), patches=(ROW, "vv5_guardians_of_isola_rewrite"))
        self.assertIsNone(r.queue6(self.believer_graph("believer", "A believer asks.", "A villager of faith asks.")))
        said = words(r)
        self.assertIn("A person of faith asks.", said)
        self.assertNotIn("villager of faith", said)
        self.assertNotIn("Guardian", said)
        # another's "believers" are left as written
        r = run_with(one, heathens=(0,))
        self.assertIsNone(r.queue6(self.believer_graph("friend", "(friend) watches the believers sing.")))
        self.assertIn("watches the believers sing.", words(r))

    EFFECTS = (
        {"do": "health_change", "role": "x", "min": -40, "max": -40},
        {"do": "skill", "role": "x", "skills": ["Farming"], "set": 100},
        {"do": "mood", "role": "x", "mood": "bad"},
        {"do": "preference", "role": "x", "dislike": "running"},
        {"do": "appearance", "role": "x", "head": "random", "body": 5},
        {"do": "change_age", "role": "x", "years": [3, 5]},
        {"do": "change_name", "role": "x"},
        {"do": "action", "role": "x", "action": "Dancing"},
        {"do": "celebrate", "who": "x"},
        {"do": "sex_change", "role": "x"},
        {"do": "pregnant", "role": "x", "any_birth_sex": True},
        {"do": "kill", "role": "x", "cause": "unknown"},
        {"do": "vanish", "role": "x"},
        {"do": "die_unrecovered", "role": "x"},
    )

    def test_a_puzzles_heathen_is_never_touched_by_any_effect(self):
        one = [(0, "f", 30, "Mira", 0, False)]
        for fx in self.EFFECTS:
            with self.subTest(fx=fx["do"]):
                g = {"format": "vvfp-cie-graph", "version": 6, "title": "Omen", "games": [5],
                     "roles": {"x": {"kind": "villager", "min_age": 14, "heathens": "allowed",
                                     "protected": "allow"}},
                     "start": "p", "nodes": {"p": {"text": "Something happens to (x).", "auto_text": True,
                                                   "effects": [fx]}}}
                r = run_with(one, puzzle=(0,))
                before = r.p.read(r.v.record(0), STRIDE)
                self.assertIsNone(r.queue6(compiled(g)), fx)
                said = words(r)
                self.assertEqual(r.p.read(r.v.record(0), STRIDE), before, "byte for byte the same record")
                self.assertIn("Nothing really happens to Mira. (no effect)", said)
                # cie-v6-binary.md 46 (#853): that line is the outcome's one "(no effect)", never a second
                self.assertEqual(said.count("(no effect)"), 1, said)
                # mutation: an ordinary Heathen in the same event is changed
                if fx["do"] in ("health_change", "skill", "kill"):
                    r = run_with(one, heathens=(0,))
                    before = r.p.read(r.v.record(0), STRIDE)
                    self.assertIsNone(r.queue6(compiled(g)))
                    words(r)
                    self.assertNotEqual(r.p.read(r.v.record(0), STRIDE), before)

    # Every effect that names a second villager role (Codex on #856: a body swap's "with" wrote the other record).
    PAIR_EFFECTS = (
        {"do": "pregnant", "role": "x", "partner": "y", "any_birth_sex": True},
        {"do": "nursing", "role": "x", "partner": "y"},
        {"do": "body_swap", "role": "x", "with": "y"},
    )

    def pair_graph(self, fx: dict) -> bytes:
        return compiled({"format": "vvfp-cie-graph", "version": 6, "title": "Omen", "games": [5],
                         "roles": {"x": {"kind": "villager", "min_age": 18, "sex": "female", "heathens": "allowed",
                                         "protected": "allow"},
                                   "y": {"kind": "villager", "min_age": 18, "sex": "male", "heathens": "allowed",
                                         "protected": "allow"}},
                         "start": "p", "nodes": {"p": {"text": "(x) and (y) meet.", "auto_text": True,
                                                       "effects": [fx]}}})

    def test_a_puzzles_heathen_is_never_written_in_any_role_position(self):
        """The puzzle's Heathen as the first role and as the second; the other an ordinary Heathen.  Every effect of
        EFFECTS (one role, given to the second role here) and PAIR_EFFECTS (two): the puzzle's Heathen's record is
        byte for byte the same."""
        two = [(0, "f", 30, "Mira", 0, False), (1, "m", 32, "Kai", 0, False)]
        cases = [(fx, 0) for fx in self.PAIR_EFFECTS] + [(fx, 1) for fx in self.PAIR_EFFECTS]
        cases += [(dict(fx, role="y") if "role" in fx else dict(fx, who="y"), 1) for fx in self.EFFECTS
                  if fx["do"] != "pregnant"]
        for fx, puzzle in cases:
            with self.subTest(fx=fx["do"], puzzle_is="x" if puzzle == 0 else "y"):
                ordinary = 1 - puzzle
                r = run_with(two, heathens=(ordinary,), puzzle=(puzzle,))
                before = r.p.read(r.v.record(puzzle), STRIDE)
                self.assertIsNone(r.queue6(self.pair_graph(fx)), fx)
                said = words(r)
                self.assertEqual(r.p.read(r.v.record(puzzle), STRIDE), before, "never written, in any position")
                self.assertIn("(no effect)", said)

    def test_mutation_a_body_swap_between_two_ordinary_heathens_is_made(self):
        two = [(0, "f", 30, "Mira", 0, False), (1, "m", 32, "Kai", 0, False)]
        r = run_with(two, heathens=(0, 1))
        before = r.p.read(r.v.record(1), STRIDE)
        self.assertIsNone(r.queue6(self.pair_graph({"do": "body_swap", "role": "x", "with": "y"})))
        words(r)
        self.assertNotEqual(r.p.read(r.v.record(1), STRIDE), before, "without a puzzle's Heathen it is made")

    def test_a_puzzles_heathen_is_never_sick_or_dead_when_cast(self):
        g = {"format": "vvfp-cie-graph", "version": 6, "title": "Omen", "games": [5],
             "roles": {"x": {"kind": "villager", "min_age": 14, "heathens": "allowed"}},
             "start": "p", "nodes": {"p": {"text": "(x) waits."}}}
        one = [(0, "f", 30, "Mira", 0, False)]
        r = run_with(one, puzzle=(0,))
        r.p.write(r.v.record(0) + SICK, b"\1")
        self.assertIsNotNone(r.queue6(compiled(g), strict=True), "never sick")


# ---- the stock events (the rendered executable, the companion installed) ------------------------------------------

PICKER, RAND = 0x471870, 0x403660
COND_SHARED, COND_TOY, COND_MUSHROOM, COND_BATS, COND_NECTAR = 0x414B90, 0x415820, 0x4150B0, 0x4166F0, 0x416AB0
VT = {"vision": 0x497674, "mask": 0x497D7C, "spa": 0x497E9C, "doubt": 0x497EE4, "cracked": 0x49824C}
SIMPLE_AT, SIMPLE_BACK = 0x418765, 0x41876E          # the popup's OK: an event with no choice
CHOICE_AT, CHOICE_BACK = 0x418749, 0x418759          # ... with a choice ([esi+0x830])


@emulated
class Stock(unittest.TestCase):
    def setUp(self):
        if not have_stock("vv5"):
            self.skipTest("no New Believers")

    def game(self, row: bool = True):
        p = Process(render("vv5", "collection_progression"), TEST_DLL)
        assert p.export("VvfpStoryInstall", 5) == 1
        v = Village(p, "vv5")
        text = "vv5\n" + (ROW + "\n" if row else "")
        buf = p.alloc(len(text) + 1)
        p.write(buf, text.encode("ascii") + b"\0")
        p.export("VvfpStoryProbeInstalledPatches", 5, buf)
        self.assertEqual(p.export("VvfpStoryProbeHeathenStock"), 1, "every site, or none")
        self.bounds: list[int] = []
        self.answers: list[int] = []

        def rand(q):
            bound = q.arg(0)
            self.bounds.append(bound)
            return (self.answers.pop(0) if self.answers else 0) % max(bound, 1), 0
        p.stub(RAND, rand)
        return p, v

    def person(self, v, i, years=30, sex="m", heathen=False, role=0, sick=False, faith=50):
        r = v.put(i, sex=sex, years=years, name=f"P{i}", faction=1 if heathen else 0)
        v.proc.put32(r + ROLE, role)
        v.proc.write(r + SICK, b"\1" if sick else b"\0")
        v.proc.put32(r + FAITH, faith if not heathen else -40)
        return r

    def cond(self, p, fn: int, vt: int = 0) -> tuple[int, int, int]:
        obj = p.alloc(0x20)
        p.put32(obj, vt)
        ok = p.call(fn, [], ecx=obj) & 0xFF
        return ok, p.u32(obj + 4), p.u32(obj + 0xC)

    def test_the_believer_part_draws_ordinary_heathens_in_proportion(self):
        p, v = self.game()
        b = self.person(v, 0)
        h = self.person(v, 1, heathen=True)
        self.person(v, 2, heathen=True, role=14)               # a Master: never
        self.person(v, 3, heathen=True, sick=True)             # sick: never
        self.answers = [0, 0, 1]                               # believer list, Heathen list, then the share
        ok, got, _ = self.cond(p, COND_SHARED)
        self.assertEqual((ok, got), (1, h))
        self.assertEqual(self.bounds[-1], 2, "one believer and one ordinary Heathen, each as likely")
        self.answers = [0, 0, 0]
        self.assertEqual(self.cond(p, COND_SHARED)[1], b)
        # mutation: without the row the stock draw, believers only
        p, v = self.game(row=False)
        b = self.person(v, 0)
        self.person(v, 1, heathen=True)
        for _ in range(3):
            self.answers = [1, 1, 1]
            self.assertEqual(self.cond(p, COND_SHARED)[1], b)

    def test_never_a_puzzles_or_a_sick_heathen_in_any_believer_part(self):
        p, v = self.game()
        for i, (role, sick) in enumerate(((12, False), (13, False), (14, False), (15, False), (16, False),
                                          (17, False), (0, True))):
            self.person(v, i, years=8 if i % 2 else 30, heathen=True, role=role, sick=sick)
        for fn in (COND_SHARED, 0x415640, COND_TOY, 0x415960, 0x415C40, 0x415E20, 0x415F60, 0x416280,
                   COND_MUSHROOM, 0x4165D0, COND_BATS, COND_NECTAR):
            with self.subTest(cond=hex(fn)):
                self.answers = [5] * 8
                ok, a, c = self.cond(p, fn)
                self.assertEqual((a, c), (0, 0), "nobody: only puzzle's and sick Heathens live")

    def test_the_four_your_tribe_gains_events_may_draw_a_heathen(self):
        """The owner's later word, "All stock" (2026-11-23): Mushroom Day!, The Migrating Fruit Bats, The Aphids in
        the Noni Bush and The Strange Nectar draw a Heathen too; their tribe-wide part is the stock event's own."""
        p, v = self.game()
        h = self.person(v, 1, years=20, heathen=True)
        child = self.person(v, 2, years=8, heathen=True)
        for fn, want in ((COND_MUSHROOM, child), (COND_BATS, child), (COND_SHARED, None), (COND_NECTAR, h)):
            with self.subTest(cond=hex(fn)):
                self.answers = [0, 0, 0]
                ok, got, _ = self.cond(p, fn)
                self.assertIn(got, (h, child) if want is None else (want,))

    def test_a_heathen_part_never_takes_the_heathen_already_drawn(self):
        p, v = self.game()
        only = self.person(v, 1, years=8, heathen=True)
        self.answers = [0] * 8
        ok, a, c = self.cond(p, COND_TOY)
        self.assertEqual((a, ok), (only, 0), "one Heathen child for both parts: the event is not offered")
        other = self.person(v, 2, years=9, heathen=True)
        self.answers = [0] * 8
        ok, a, c = self.cond(p, COND_TOY)
        self.assertEqual(ok, 1)
        self.assertNotEqual(a, c)
        self.assertEqual({a, c}, {only, other})

    def apply(self, p, vt: int, who: int, choice: int | None) -> int:
        obj = p.alloc(0x20)
        p.put32(obj, vt)
        p.put32(obj + 4, who)
        dlg = p.alloc(0x900)
        p.put32(dlg + 0x830, 0 if choice is None else choice)
        # the world the applies also touch, as no-ops: Divine Energy 0x424F80 (thiscall, 1), the walk's stop 0x473440
        # and target 0x4662C0 / 0x4662D0 (thiscall, 1) -- the Faith and faction calls run for real
        p.stub(0x424F80, lambda q: (0, 4))
        p.stub(0x473440, lambda q: (0, 0))
        p.stub(0x4662C0, lambda q: (0, 4))
        p.stub(0x4662D0, lambda q: (0, 4))
        stack = p.alloc(0x2000) + 0x1F00
        p.set_reg("esp", stack)
        p.set_reg("esi", dlg)
        p.set_reg("ecx", obj)
        if choice is None:
            p.run(SIMPLE_AT, SIMPLE_BACK)
        else:
            p.run(CHOICE_AT, CHOICE_BACK)
        return obj

    FAITH_CASES = (("vision", None), ("mask", 0), ("mask", 1), ("doubt", 0), ("doubt", 1), ("spa", 1),
                   ("cracked", 1))

    def test_the_faith_part_never_reaches_a_drawn_heathen(self):
        for name, choice in self.FAITH_CASES:
            with self.subTest(event=name, choice=choice):
                p, v = self.game()
                h = self.person(v, 1, heathen=True)
                p.put32(h + 0x2F14, 7)
                p.put32(h + 0x2F40, 9)
                self.apply(p, VT[name], h, choice)
                self.assertEqual(struct.unpack("<i", p.read(h + FAITH, 4))[0], -40, "Faith as it was")
                self.assertEqual(p.read(h + FACTION, 1), b"\1", "still a Heathen")
                self.assertEqual((p.u32(h + 0x2F14), p.u32(h + 0x2F40)), (7, 9))

    def test_mutation_without_the_row_the_faith_part_reaches_them(self):
        p, v = self.game(row=False)
        h = self.person(v, 1, heathen=True)
        self.answers = [5]
        self.apply(p, VT["vision"], h, None)
        self.assertNotEqual(struct.unpack("<i", p.read(h + FAITH, 4))[0], -40, "stock: The Vision's Faith rise")
        p, v = self.game()
        b = self.person(v, 0)
        self.answers = [5]
        self.apply(p, VT["vision"], b, None)
        self.assertGreater(struct.unpack("<i", p.read(b + FAITH, 4))[0], 50, "a believer's Faith rise is stock")

    def test_the_group_events_reach_ordinary_heathens_only(self):
        started = []
        for row in (True, False):
            with self.subTest(row=row):
                p, v = self.game(row=row)
                b = self.person(v, 0)
                h = self.person(v, 1, heathen=True)
                m = self.person(v, 2, heathen=True, role=16)
                s = self.person(v, 3, heathen=True, sick=True)
                started.clear()
                p.stub(0x465580, lambda q: (started.append((q.reg("ecx"), q.arg(0))), (0, 8))[1])
                p.stub(0x473440, lambda q: (0, 0))
                p.call(0x414AC0, [], ecx=p.alloc(0x20))          # Isola Day Celebration
                who = {r for r, _beh in started}
                self.assertIn(b, who)
                self.assertNotIn(m, who)
                self.assertNotIn(s, who)
                self.assertEqual(h in who, row)
                self.assertTrue(all(beh == 0x2F for _r, beh in started))


if __name__ == "__main__":
    unittest.main()
