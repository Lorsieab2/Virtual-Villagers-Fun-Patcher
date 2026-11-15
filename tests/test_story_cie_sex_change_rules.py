"""The engine's rules around a sex change and carrying (the owner, 2026-11-15), every game, in the emulator with the
test build of "VVFP Story Upgrades.dll" (tests/test_story_cie_graph_runtime_v6.py's V6 run):

  * has_living_child finds a parent by the parent FIELD on the child's record, never by the parent's sex now: a
    villager recorded as a child's mother whose sex is now male still has a living child (A New Home: through its
    parentage sidecar, as the kinship roles read it);
  * the Golden Child is never cast for a role a sex_change effect names, even with protected "allow";
  * a nursing_parent role never casts anyone under 18 (children never carry in events), and the compiler refuses
    such a role with a lower min_age;
  * the gender presentation (code 23, cie-v6-binary.md 29): set (on) or cleared (off) through "VVFP Gender
    Presentation.dll" as the test build stands it in, in every game; a refusal when the companion is not in the
    game; never cast for the Golden Child, The Secret City's Tribal Chief, New Believers' story villagers; the
    compiler's encoding (a = 1 on, 0 off) and its refusal of anything but true / false.
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
import test_story_cie_graph_runtime_v6 as rt  # noqa: E402
from test_story_custom_island_event import emulated, have_stock  # noqa: E402

GAME_IDS = rt.GAME_IDS


def child_graph(game: str) -> dict:
    return {"format": "vvfp-cie-graph", "version": 6, "title": "A Wave Across the Sand", "games": [int(game[2])],
            "roles": {"subject": {"kind": "villager", "min_age": 20}},
            "start": "p",
            "nodes": {"p": {"text": "(Name) looks around.",
                            "children": [{"next": "yes", "if": {"has_living_child": "subject"}, "else": "no"}]},
                      "yes": {"popup": "append", "text": "A child waves."},
                      "no": {"popup": "append", "text": "Nobody waves."}}}


GOLDEN_GRAPH = {
    "format": "vvfp-cie-graph", "version": 6, "title": "A Quiet Talk", "games": [1],
    "roles": {"subject": {"kind": "villager", "min_age": 0, "protected": "allow"}},
    "start": "p",
    "nodes": {"p": {"text": "(Name) shares a private truth.", "effects": [{"do": "sex_change", "role": "subject"}]}},
}


def presentation_graph(game: str, on: bool = True, allow: bool = False) -> dict:
    subject = {"kind": "villager", "min_age": 0}
    if allow:
        subject["protected"] = "allow"
    return {"format": "vvfp-cie-graph", "version": 6, "title": "A New Look", "games": [int(game[2])],
            "roles": {"subject": subject},
            "start": "p",
            "nodes": {"p": {"text": "(Name) tries a new look.",
                            "effects": [{"do": "presentation", "role": "subject", "on": on}]}}}


def nursing_graph(game: str, min_age: int = 18) -> dict:
    return {"format": "vvfp-cie-graph", "version": 6, "title": "A Lullaby", "games": [int(game[2])],
            "roles": {"parent": {"kind": "villager", "min_age": min_age, "special": "nursing_parent"}},
            "start": "p",
            "nodes": {"p": {"text": "(Parent) hums a lullaby."}}}


class CompilerRules(unittest.TestCase):
    def test_a_nursing_parent_is_18_or_more(self):
        for game in GAME_IDS:
            with self.subTest(game=game):
                with self.assertRaises(Exception) as caught:
                    cg.load(copy.deepcopy(nursing_graph(game, 14)), scrolling=True)
                self.assertIn("nursing_parent role has min_age 18", str(caught.exception))
                cg.load(copy.deepcopy(nursing_graph(game, 18)), scrolling=True)

    def test_every_collection_nursing_parent_is_an_adult(self):
        import json
        for path in sorted((ROOT / "data" / "event_collection").rglob("*.json")):
            text = path.read_text(encoding="utf-8")
            if '"nursing_parent"' not in text:
                continue

            def walk(o):
                if isinstance(o, dict):
                    if o.get("special") == "nursing_parent":
                        self.assertGreaterEqual(o.get("min_age", 14), 18, path.name)
                    for v in o.values():
                        walk(v)
                elif isinstance(o, list):
                    for v in o:
                        walk(v)
            walk(json.loads(text))


@emulated
class PresentationCompiler(unittest.TestCase):
    def test_the_effect_encodes_on_and_off(self):
        for on, a in ((True, 1), (False, 0)):
            with self.subTest(on=on):
                data = rt.compiled(presentation_graph("vv4", on))
                self.assertIn(struct.pack("<BBBBiiHH", 23, 0, 0, 0, a, 0, 0xFFFF, 0), data)
        g = presentation_graph("vv4")
        del g["nodes"]["p"]["effects"][0]["on"]
        self.assertIn(struct.pack("<BBBBiiHH", 23, 0, 0, 0, 1, 0, 0xFFFF, 0), rt.compiled(g), "on by default")

    def test_on_is_true_or_false(self):
        g = presentation_graph("vv4")
        g["nodes"]["p"]["effects"][0]["on"] = 1
        with self.assertRaises(Exception) as caught:
            cg.load(g, scrolling=True)
        self.assertIn("presentation on is true", str(caught.exception))

    def test_its_automatic_line(self):
        e = {"do": "presentation", "role": "subject", "on": True}
        self.assertEqual(cg.auto_line_options(e, 4), ["(subject.Name)'s look changes."])


class PresentationEngine(unittest.TestCase):
    @staticmethod
    def chosen(r) -> list[list[int]]:
        buf = r.p.alloc(4 * 32)
        n = r.p.export("VvfpStoryProbeGraphPresentation", 2, buf, 16)
        v = struct.unpack(f"<{2 * n}i", r.p.read(buf, 8 * n)) if n else ()
        return [list(v[2 * i:2 * i + 2]) for i in range(n)]

    def test_set_and_cleared_in_every_game(self):
        for game in GAME_IDS:
            if not have_stock(game):
                continue
            for on in (True, False):
                for mode in (1, 0):
                    with self.subTest(game=game, on=on, installed=mode):
                        r = rt.V6(game, [(0, "f", 30, "Ana", 0, False)])
                        r.p.export("VvfpStoryProbeGraphPresentation", mode, 0, 0)
                        sex = r.v.i32(0, r.v.L["sex"][0])
                        r.rolls([0] * 40)
                        self.assertIsNone(r.queue6(rt.compiled(presentation_graph(game, on)), strict=True, origin=2))
                        text = rt.norm(" ".join(t for _k, t, _l in r.walk_through()))
                        self.assertIn("Ana tries a new look.", text)
                        self.assertEqual(r.v.i32(0, r.v.L["sex"][0]), sex, "the sex field is never written")
                        if mode:
                            self.assertEqual(self.chosen(r), [[0, 1 if on else 0]])
                            self.assertNotIn("could not be made", text)
                        else:
                            self.assertEqual(self.chosen(r), [])
                            self.assertIn("could not be made", text, "no companion: a refusal, nothing changed")

    def _never_cast(self, game: str, make) -> None:
        for roll in range(3):
            with self.subTest(game=game, roll=roll):
                r = rt.V6(game, [(0, "m", 30, "Moku", 0, False), (1, "f", 30, "Ana", 0, False)])
                make(r)
                r.p.export("VvfpStoryProbeGraphPresentation", 1, 0, 0)
                r.rolls([roll] * 40)
                self.assertIsNone(r.queue6(rt.compiled(presentation_graph(game, allow=True))))
                text = rt.norm(" ".join(t for _k, t, _l in r.walk_through()))
                self.assertIn("Ana tries a new look.", text)
                self.assertEqual(self.chosen(r), [[1, 1]], "only Ana")

    def test_the_golden_child_is_never_cast(self):
        if have_stock("vv1"):
            self._never_cast("vv1", lambda r: r.p.put32(r.v.record(0) + 0x36C, 0xC7))

    def test_the_tribal_chief_is_never_cast(self):
        if have_stock("vv3"):
            self._never_cast("vv3", lambda r: r.p.write(r.v.record(0) + 0xE80, b"\x01"))

    def test_story_villagers_are_never_cast(self):
        if have_stock("vv5"):
            self._never_cast("vv5", lambda r: r.p.put32(r.v.record(0) + 0x1CFC, 12))


class EngineRules(unittest.TestCase):
    def test_has_living_child_after_the_parent_s_sex_changed(self):
        for game in GAME_IDS:
            if not have_stock(game):
                continue
            for recorded in (True, False):
                with self.subTest(game=game, recorded=recorded):
                    # Ana is recorded as Kiki's mother; Ana's sex is male now.
                    r = rt.V6(game, [(0, "m", 40, "Ana", 0, False), (1, "m", 6, "Kiki", 0, False)])
                    head, body = rt.LOOKS[game]
                    looks = (r.p.u32(r.v.record(0) + head), r.p.u32(r.v.record(0) + body))
                    if recorded:
                        rt.set_parents(r, game, 1, mother=("Ana",) + looks)
                    r.rolls([0] * 40)
                    self.assertIsNone(r.queue6(rt.compiled(child_graph(game))))
                    text = rt.norm(" ".join(t for _k, t, _l in r.walk_through()))
                    self.assertIn("A child waves." if recorded else "Nobody waves.", text)

    def test_the_golden_child_is_never_cast_for_a_sex_change(self):
        if not have_stock("vv1"):
            self.skipTest("no stock A New Home")
        for roll in range(4):
            with self.subTest(roll=roll):
                r = rt.V6("vv1", [(0, "m", 5, "Goldie", 0, False), (1, "f", 30, "Ana", 0, False)])
                r.p.put32(r.v.record(0) + 0x36C, 0xC7)            # the Golden Child's family
                r.rolls([roll] * 40)
                self.assertIsNone(r.queue6(rt.compiled(GOLDEN_GRAPH)))
                text = rt.norm(" ".join(t for _k, t, _l in r.walk_through()))
                self.assertIn("Ana shares a private truth.", text)
                self.assertEqual(r.v.i32(0, r.v.L["sex"][0]), r.v.L["sex"][1], "the Golden Child is unchanged")
        r = rt.V6("vv1", [(0, "m", 5, "Goldie", 0, False)])
        r.p.put32(r.v.record(0) + 0x36C, 0xC7)
        r.rolls([0] * 40)
        self.assertIsNotNone(r.queue6(rt.compiled(GOLDEN_GRAPH)), "nobody else: the event is not cast at all")

    def test_a_nursing_parent_is_never_a_child(self):
        for game in GAME_IDS:
            if not have_stock(game):
                continue
            for years, cast in ((15, False), (17, False), (18, True), (30, True)):
                with self.subTest(game=game, years=years):
                    r = rt.V6(game, [(0, "f", years, "Ana", 0, True), (1, "m", 40, "Bo", 0, False)])
                    r.rolls([0] * 40)
                    result = r.queue6(rt.compiled(nursing_graph(game)), strict=True)
                    if cast:
                        self.assertIsNone(result)
                        self.assertIn("Ana hums a lullaby.", rt.norm(" ".join(t for _k, t, _l in r.walk_through())))
                    else:
                        self.assertIsNotNone(result, "strict: a carrier under 18 is never the nursing parent")
                        # A bought event prefers its requirements: with nobody to meet them it casts someone else,
                        # never the child who carries.
                        r = rt.V6(game, [(0, "f", years, "Ana", 0, True), (1, "m", 40, "Bo", 0, False)])
                        r.rolls([0] * 40)
                        self.assertIsNone(r.queue6(rt.compiled(nursing_graph(game))))
                        self.assertNotIn("Ana hums", rt.norm(" ".join(t for _k, t, _l in r.walk_through())))


if __name__ == "__main__":
    unittest.main()
