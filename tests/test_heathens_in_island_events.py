"""New Believers: "Heathens can be selected in Island Events/Heathen-Exclusive Events" (the owner, 2026-11-23;
docs/event-collection/cie-v6-binary.md 45).

The compiler side (src/vv_cie_graph.py): a villager role's "heathens": "allowed" / "only" is role byte 13 bit 5 / 4,
read back the same; a Heathens-only role never takes what can not yet happen to a Heathen; the automatic lines of the
Heathens' own cast are pinned (with "(no effect)" and the Isolans' wording).

The engine side (native/vvfp_story_upgrades/story_graph.inc), the test build of "VVFP Story Upgrades.dll" beside New
Believers' rendered executable in the emulator:
* with the row an ordinary Heathen is cast in an "allowed" or "only" role; without it never, and an "only" role is
  then never filled (the event is not offered);
* a puzzle's Heathen (roles 12-17) is cast only with the row (nothing made to them: test_heathens_in_existing_events.py);
* a Heathen is never cast in a role a death, a disappearance or a pregnancy names;
* the Heathens' own cast: the village's food is untouched (statistics and stores never count it) and the page says
  "The Heathens' village gains N food. (no effect)" ("the Isolans' village" with Guardians of Isola);
* a mixed cast gives the food to the village as always, with the village's own line;
* a Heathen pregnancy, or a Heathen and a believer, never conceives.
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

import vv_cie_graph as cg  # noqa: E402
from test_story_custom_island_event import HAVE_EMULATOR, emulated, have_stock  # noqa: E402

if HAVE_EMULATOR:
    from test_story_cie_graph_runtime import stores
    from test_story_cie_graph_runtime_v6 import V6

FACTION, ROLE, SICK = 0x1CEC, 0x1CFC, 0x1C48
ROW = "vv5_heathens_in_island_events"


def graph(heathens: str, effects=None, auto: bool = True, roles: dict | None = None) -> dict:
    r = roles or {"isolan": {"kind": "villager", "min_age": 14, "heathens": heathens}}
    return {"format": "vvfp-cie-graph", "version": 6, "title": "Camp Life", "games": [5],
            "roles": r, "start": "p",
            "nodes": {"p": {"text": "(isolan.Name) shares a meal by the fire.", "auto_text": auto,
                            "effects": effects if effects is not None else [{"do": "food", "amount": 50}]}}}


def compiled(g: dict) -> bytes:
    return cg.compile_graph(cg.load(copy.deepcopy(g), scrolling=True))


class Compiler(unittest.TestCase):
    def test_the_bits_and_back(self):
        for mode, bit in (("allowed", 0x20), ("only", 0x10)):
            with self.subTest(mode=mode):
                data = compiled(graph(mode))
                o_role = struct.unpack_from("<I", data, 44)[0]
                self.assertEqual(data[o_role + 13] & 0x30, bit)
                self.assertTrue(data[o_role + 1] & 8, "believers_only stays set: an older engine casts believers")
                self.assertEqual(cg.decompile_graph(data)["roles"]["isolan"]["heathens"], mode)
        data = compiled(graph("never"))
        o_role = struct.unpack_from("<I", data, 44)[0]
        self.assertEqual(data[o_role + 13] & 0x30, 0, "never: a believer's role, as before")

    def test_bad_values_and_the_barred_effects(self):
        _, problems = cg.validate(graph("sometimes"), scrolling=True)
        self.assertTrue(any("heathens is never, allowed, kin or only" in p for p in problems), problems)
        g = graph("only")
        g["roles"]["isolan"]["heathen_ok"] = True
        _, problems = cg.validate(g, scrolling=True)
        self.assertTrue(any("not both" in p for p in problems), problems)
        for do in ({"do": "clone", "role": "isolan"}, {"do": "status", "role": "isolan", "status": "heathen"}):
            with self.subTest(do=do["do"]):
                _, problems = cg.validate(graph("only", [do]), scrolling=True)
                self.assertTrue(any("never happens to a Heathen" in p for p in problems), problems)
        # the owner (2026-11-23): Heathens can die, disappear and have babies ("VVFP Heathen Aging.dll" carries them)
        for do in ({"do": "kill", "role": "isolan", "cause": "unknown"}, {"do": "vanish", "role": "isolan"},
                   {"do": "pregnant", "role": "isolan", "any_birth_sex": True}):
            with self.subTest(do=do["do"]):
                _, problems = cg.validate(graph("only", [do]), scrolling=True)
                self.assertFalse([p for p in problems if "Heathen" in p], problems)

    def test_the_lines(self):
        hv = {k: v for k, v in cg.AUTO_LINES.items() if k.startswith("hv_")}
        self.assertEqual(len(hv), 14)
        for k, v in hv.items():
            with self.subTest(k=k):
                self.assertIn("the Heathens' village", v.replace("The Heathens'", "the Heathens'"))
                self.assertTrue(v.endswith(" (no effect)"))
                self.assertNotIn("camp", v.lower())
                self.assertEqual(cg.GUARDIANS_AUTO_LINES[k], v.replace("Heathens'", "Isolans'"))
                self.assertNotIn("Guardian", cg.GUARDIANS_AUTO_LINES[k])
        engine = (ROOT / "native" / "vvfp_story_upgrades" / "story_graph.inc").read_text(encoding="utf-8")
        for k, v in hv.items():
            self.assertIn(f'{{ "{k}", "{v}" }}', engine, "pinned equal to CG_AUTO_LINES")
            self.assertIn(f'{{ "{k}", "{cg.GUARDIANS_AUTO_LINES[k]}" }}', engine, "and to CG_HV_ISOLAN")


@emulated
class Engine(unittest.TestCase):
    def setUp(self):
        if not have_stock("vv5"):
            self.skipTest("no New Believers")

    def run_with(self, people, heathens=(), puzzle=None, patches=(ROW,), rolls=0, aging=1, body=0):
        r = V6("vv5", people)
        r.p.export("VvfpStoryProbeHeathenAging", aging, body, 0)    # "VVFP Heathen Aging.dll" stood in for (1)
        for i in heathens:
            r.p.write(r.v.record(i) + FACTION, b"\1")
            r.p.write(r.v.record(i) + SICK, b"\0")
            r.p.put32(r.v.record(i) + ROLE, 0)
        if puzzle is not None:
            r.p.put32(r.v.record(puzzle) + ROLE, 14)        # a Master: a puzzle's Heathen
        text = "vv5\n" + "".join(p + "\n" for p in patches)
        buf = r.p.alloc(len(text) + 1)
        r.p.write(buf, text.encode("ascii") + b"\0")
        r.p.export("VvfpStoryProbeInstalledPatches", 5, buf)
        r.rolls([rolls] * 40)
        return r

    ONE = [(0, "m", 30, "Tama", 0, False)]
    TWO = [(0, "m", 30, "Tama", 0, False), (1, "f", 28, "Lani", 0, False)]

    def test_an_ordinary_heathen_is_cast_only_with_the_row(self):
        for mode in ("allowed", "only"):
            with self.subTest(mode=mode):
                data = compiled(graph(mode))
                r = self.run_with(self.ONE, heathens=(0,))
                self.assertIsNone(r.queue6(data, strict=True), "the row: the Heathen is cast")
                r = self.run_with(self.ONE, heathens=(0,), patches=())
                self.assertIsNotNone(r.queue6(data, strict=True), "no row: never a Heathen")

    def test_an_only_role_takes_no_believer(self):
        data = compiled(graph("only"))
        r = self.run_with(self.ONE)
        self.assertIsNotNone(r.queue6(data, strict=True), "a believer is never cast in a Heathens-only role")
        r = self.run_with(self.TWO, heathens=(1,))
        self.assertIsNone(r.queue6(data, strict=True))
        r.walk_through()
        self.assertEqual(r.state()["records"][0], 1, "the Heathen, never the believer")

    def test_a_puzzles_heathen_is_cast_only_with_the_row(self):
        """The owner (2026-11-23): "Any mention of death/bad outcomes to puzzle heathens = acceptable but flavor only
        (Puzzle heathens are EXEMPT from any actual effects AT ALL TIMES.)" -- with the row a Master may be cast (every
        effect on them told, never made: tests/test_heathens_in_existing_events.py); without it never."""
        data = compiled(graph("allowed"))
        for patches in ((ROW,), (ROW, "vv5_island_events_any_time")):
            with self.subTest(patches=patches):
                r = self.run_with(self.ONE, heathens=(0,), puzzle=0, patches=patches)
                self.assertIsNone(r.queue6(data, strict=True, origin=2), "the row: a Master may be cast")
        r = self.run_with(self.ONE, heathens=(0,), puzzle=0, patches=())
        self.assertIsNotNone(r.queue6(data, strict=True, origin=2), "no row: never")

    def calls(self, r) -> list[int]:
        buf = r.p.alloc(128)
        r.p.export("VvfpStoryProbeHeathenAging", -2, 0, buf)
        return list(struct.unpack("<32i", r.p.read(buf, 128)))

    def test_without_the_aging_companion_never_where_a_death_or_a_pregnancy_names_the_role(self):
        for fx in ({"do": "kill", "role": "isolan", "cause": "unknown"}, {"do": "vanish", "role": "isolan"},
                   {"do": "pregnant", "role": "isolan", "any_birth_sex": True}):
            with self.subTest(fx=fx["do"]):
                data = compiled(graph("allowed", [fx]))
                r = self.run_with(self.ONE, heathens=(0,), aging=0)
                self.assertIsNotNone(r.queue6(data, strict=True), "only a Heathen there: nobody may be cast")
                r = self.run_with(self.ONE, heathens=(0,))
                self.assertIsNone(r.queue6(data, strict=True), "with the companion: the Heathen is cast")

    def test_a_heathens_death_and_disappearance_go_by_the_heathens_rules(self):
        for fx, how, cause in (({"do": "kill", "role": "isolan", "cause": "unknown"}, 0, -1),
                               ({"do": "kill", "role": "isolan", "cause": "custom"}, 0, 5),
                               ({"do": "vanish", "role": "isolan"}, 1, 5),
                               ({"do": "die_unrecovered", "role": "isolan"}, 1, None)):
            with self.subTest(fx=fx["do"], cause=fx.get("cause")):
                r = self.run_with(self.ONE, heathens=(0,))
                deaths = r.p.u32(0x51D3A0)
                self.assertIsNone(r.queue6(compiled(graph("only", [fx]))))
                r.walk_through()
                c = self.calls(r)
                self.assertEqual(c[0:3], [1, 0, how])
                if cause is not None:            # (a disappearance's record is the event's own)
                    self.assertEqual(c[3], cause)
                self.assertEqual(r.p.read(r.v.record(0) + r.v.L["active"], 1), b"\0", "taken: nothing left")
                self.assertEqual(r.p.u32(0x51D3A0), deaths, "never counted")

    def test_the_authors_cause_words_are_kept_for_a_heathens_death_record(self):
        """#852 (logs must be correct): a death with the author's own words hands them to Cause of Death
        (VvfpCauseWordsFor) before the Heathen Aging companion takes the Heathen, so the Death record says them;
        "unknown" and "custom" keep the companion's own words."""
        for cause, told in (("Crushed by a falling coconut", True), ("unknown", False), ("custom", False)):
            with self.subTest(cause=cause):
                r = self.run_with(self.ONE, heathens=(0,))
                fx = [{"do": "kill", "role": "isolan", "cause": cause}]
                self.assertIsNone(r.queue6(compiled(graph("only", fx))))
                r.walk_through()
                words = [w for kind, _i, w in r.told() if kind == 6]
                self.assertEqual(words, [cause] if told else [])
                self.assertEqual(self.calls(r)[3], -1 if cause == "unknown" else 5)

    def test_a_heathen_couples_baby_and_never_with_a_believer(self):
        roles = {"isolan": {"kind": "villager", "min_age": 18, "sex": "female", "heathens": "only"},
                 "mate": {"kind": "villager", "min_age": 18, "sex": "male", "heathens": "only"}}
        fx = [{"do": "pregnant", "role": "isolan", "partner": "mate"}]
        people = [(0, "f", 28, "Lani", 0, False), (1, "m", 30, "Tama", 0, False)]
        r = self.run_with(people, heathens=(0, 1))
        self.assertIsNone(r.queue6(compiled(graph("only", fx, roles=roles))))
        r.walk_through()
        self.assertEqual(self.calls(r)[16:21], [1, 0, 1, 1, 0], "the mother, the father, one baby, not yet born")
        # a believer father: never (the role that pairs with a believer's keeps Heathens out)
        roles["mate"].pop("heathens")
        r = self.run_with(people, heathens=(0,))
        self.assertIsNotNone(r.queue6(compiled(graph("only", fx, roles=roles)), strict=True))
        self.assertEqual(self.calls(r)[16], 0)

    def test_a_partner_alias_of_a_heathen_role_still_lets_a_heathen_carry(self):
        """Codex on #852: the pairing check reads what an alias's members may be, not the alias's own byte 13 (it has
        no Heathen bit) -- a Heathens-only carrier paired with a (single-member) alias of a Heathens-only role is cast."""
        roles = {"isolan": {"kind": "villager", "min_age": 18, "sex": "female", "heathens": "only"},
                 "mate": {"kind": "villager", "min_age": 18, "sex": "male", "heathens": "only"},
                 "someone": {"kind": "alias", "of": ["mate"]}}
        fx = [{"do": "pregnant", "role": "isolan", "partner": "someone"}]
        people = [(0, "f", 28, "Lani", 0, False), (1, "m", 30, "Tama", 0, False)]
        r = self.run_with(people, heathens=(0, 1))
        self.assertIsNone(r.queue6(compiled(graph("only", fx, roles=roles)), strict=True))
        r.walk_through()
        self.assertEqual(self.calls(r)[16:19], [1, 0, 1], "the Heathen mother, the Heathen father drawn by the alias")

    def test_the_heathens_own_cast_moves_no_solidarity(self):
        from test_village_solidarity import fake_solidarity
        g = graph("only")
        g["nodes"]["p"]["solidarity"] = "raise"
        tags: list = []
        r = self.run_with(self.ONE, heathens=(0,))
        fake_solidarity(r.p, 1000, 1000, tags)
        self.assertIsNone(r.queue6(compiled(g)))
        words = " ".join(s[1] for s in r.walk_through())
        self.assertEqual(tags, [], "Codex on #852: the Heathens' own cast never moves the village's score")
        self.assertNotIn("Village Solidarity", words)
        # a mixed cast still does
        roles = {"isolan": {"kind": "villager", "min_age": 14, "heathens": "only"},
                 "host": {"kind": "villager", "min_age": 14}}
        g = graph("only", roles=roles)
        g["nodes"]["p"]["solidarity"] = "raise"
        tags = []
        r = self.run_with(self.TWO, heathens=(1,))
        fake_solidarity(r.p, 1000, 1000, tags)
        self.assertIsNone(r.queue6(compiled(g)))
        r.walk_through()
        self.assertEqual(len(tags), 1)

    def test_your_village_becomes_the_heathens_village(self):
        g = graph("only", [])
        g["nodes"]["p"]["text"] = "(isolan.Name) brings your villagers a gift for your village."
        r = self.run_with(self.ONE, heathens=(0,))
        self.assertIsNone(r.queue6(compiled(g)))
        words = " ".join(" ".join(s[1] for s in r.walk_through()).split())
        self.assertIn("brings the Heathens a gift for the Heathens' village.", words)

    def flavor(self, guardians: bool):
        patches = (ROW, "vv5_guardians_of_isola_rewrite") if guardians else (ROW,)
        r = self.run_with(self.ONE, heathens=(0,), patches=patches)
        before = stores(r)
        self.assertIsNone(r.queue6(compiled(graph("only"))))
        shown = r.walk_through()
        return r, before, " ".join(s[1] for s in shown)

    def test_the_heathens_own_cast_is_flavor_only(self):
        r, before, words = self.flavor(False)
        self.assertEqual(stores(r), before, "the village's food is untouched")
        self.assertIn("The Heathens' village gains 50 food. (no effect)", words)
        self.assertEqual(words.count("(no effect)"), 1, "#853's mark never doubles the flavor line's own")
        self.assertNotIn("The village gains", words)
        r, before, words = self.flavor(True)
        self.assertEqual(stores(r), before)
        self.assertIn("The Isolans' village gains 50 food. (no effect)", words)

    def test_a_mixed_cast_reaches_the_tribe(self):
        roles = {"isolan": {"kind": "villager", "min_age": 14, "heathens": "only"},
                 "host": {"kind": "villager", "min_age": 14}}
        r = self.run_with(self.TWO, heathens=(1,))
        before = stores(r)
        self.assertIsNone(r.queue6(compiled(graph("only", roles=roles))))
        words = " ".join(s[1] for s in r.walk_through())
        self.assertEqual(stores(r)[0], before[0] + 50, "a believer is in it: the food is the tribe's")
        self.assertIn("The village gains 50 food.", words)
        self.assertNotIn("(no effect)", words)

    def test_personal_effects_reach_the_heathen(self):
        fx = [{"do": "health_change", "role": "isolan", "min": -40, "max": -40}]
        r = self.run_with(self.ONE, heathens=(0,))
        h = r.v.i32(0, r.v.L["health"])
        self.assertIsNone(r.queue6(compiled(graph("allowed", fx))))
        r.walk_through()
        self.assertEqual(r.v.i32(0, r.v.L["health"]), h - 40, "beyond vanilla's -30: the row's Heathen as a villager")

    def two_pages(self) -> bytes:
        g = graph("only")
        g["nodes"] = {"p1": {"text": "(isolan.Name) wakes before the camp.", "children": [{"next": "p2"}]},
                      "p2": {"text": "(isolan.Name) shares a meal by the fire.", "auto_text": True,
                             "new_page": True, "effects": [{"do": "food", "amount": 50}]}}
        g["start"] = "p1"
        return compiled(g)

    def resumed(self, file: bytes):
        again = self.run_with(self.ONE, heathens=(0,))
        again.facts(unicode=0, structures=0)
        again.p.export("VvfpStoryProbeQueueSession", 0, 0, 0x7FFFFFF0, 0)
        buf = again.p.alloc(len(file) + 16)
        again.p.write(buf, file)
        again.p.export("VvfpStoryProbeGraphSession", buf, len(file))
        again.tick()
        return again

    def test_the_run_file_keeps_the_heathens_cast_and_a_version_6_file_loads(self):
        from test_story_cie_graph_runtime import IDLE
        from test_story_cie_graph_runtime_v6 import LAYOUT_BUF
        from test_story_custom_island_event import TEXT_BUF
        r = self.run_with(self.ONE, heathens=(0,))
        r.facts(unicode=0, structures=0)
        r.p.export("VvfpStoryProbeQueueSession", 0, 0, 1, 0)
        self.assertIsNone(r.queue6(self.two_pages()))
        if not r.state()["armed"]:
            assert r.p.export("VvfpStoryProbeGraphArmNext", r.n) == 1
        r.p.write(TEXT_BUF, b"\0")
        assert r.p.export("VvfpStoryProbeDeliver", r.n, TEXT_BUF, 9000) == 1
        r.tick()
        file = bytearray(r.graph_file())
        self.assertEqual(struct.unpack_from("<I", file, 4)[0], 7)
        # version 7: put back with the Heathens' own cast, so the food stays the Heathens' village's
        again = self.resumed(bytes(file))
        self.assertNotEqual(again.state()["phase"], IDLE, "put back")
        before = stores(again)
        words = " ".join(s[1] for s in again.walk_through())
        self.assertEqual(stores(again), before)
        self.assertIn("The Heathens' village gains 50 food. (no effect)", words)
        # a version 6 file (before the row): read with the village's own cast, whatever its padding held
        r.p.export("VvfpStoryProbeGraphFileLayout", LAYOUT_BUF)
        lay = struct.unpack("<13i", r.p.read(LAYOUT_BUF, 52))
        head, whole, v6, at = lay[1], lay[2], lay[11], lay[12]
        self.assertIn(v6, (at, at + 4))
        state = bytearray(file[head:head + whole])
        state[at:at + 4] = b"\xff\xff\xff\xff"          # the old padding, as anything
        old = bytearray(bytes(file[:head]) + bytes(state[:v6]) + bytes(file[head + whole:]))
        struct.pack_into("<I", old, 4, 6)
        struct.pack_into("<I", old, 16, v6)
        again = self.resumed(bytes(old))
        self.assertNotEqual(again.state()["phase"], IDLE, "a version 6 file is put back")

    def test_never_a_heathen_partner_for_a_believer(self):
        roles = {"isolan": {"kind": "villager", "min_age": 18, "heathens": "allowed"},
                 "mate": {"kind": "villager", "min_age": 18}}
        fx = [{"do": "pregnant", "role": "mate", "partner": "isolan", "any_birth_sex": True}]
        r = self.run_with(self.TWO, heathens=(0,))
        # the believer's role pairs with the Heathen's: Heathens stay out of it, so with one believer the cast fails
        self.assertIsNotNone(r.queue6(compiled(graph("allowed", fx, roles=roles)), strict=True))
        self.assertEqual(r.v.i32(1, r.v.L["pregnant"]), 0)
        self.assertEqual(self.calls(r)[16], 0)


if __name__ == "__main__":
    unittest.main()
