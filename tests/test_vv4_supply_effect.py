"""The "supply" effect (docs/event-collection/cie-v6-binary.md 38, the owner 2026-11-17): an island event's words about
The Tree of Life's cutting tools, bars of soap and cloth bolts (a "sack" is a cloth bolt) change the real counts.

* the patcher side (src/vv_cie_graph.py): the effect loads, compiles and decompiles; a bad item, a range of 0 or
  across 0, and an event without The Tree of Life are refused; it has no automatic outcome line;
* the game side (native/vvfp_story_upgrades/story_graph.inc cg_supply, story_c4.inc C4_SUPPLY_*), the test build of
  "VVFP Story Upgrades.dll" beside the stock The Tree of Life executable in the emulator:
  - tools and cloth stay within 0..6, or 0..99 with Up to 99 Cutting Tools/Soap/Cloth ("VVFP VV4 Supply Cap.dll");
    soap within 0..99; never below 0; a count above the cap (a save made with the cap raised) is never lowered
    by a gain;
  - before the supply's puzzle (The Cutting Tool, Soap Invented, Cloth Invented) is solved nothing changes: the
    words are story only;
  - each change has its line in the event's ONE Island Events log entry;
* every new Tree of Life supply event (data/event_collection/drafts_c/dr_sup) runs through the VV4 engine, every
  choice, and its supply effects make the counts it says.
"""
from __future__ import annotations

import copy
import json
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
    from test_story_cie_graph_runtime import DONE, IDLE
    from test_story_cie_graph_runtime_v6 import V6

TOOLS, SOAP, CLOTH = 0x4D8618, 0x4D8D98, 0x4D8ACC          # the counts (story_c4.inc C4_SUPPLY_AT)
AT = {"cutting_tools": TOOLS, "soap": SOAP, "cloth": CLOTH}
PUZZLE_BIT = {"cutting_tools": 1 << 0, "soap": 1 << 3, "cloth": 1 << 7}   # story_c4.inc C4_PUZZLE_DEFS
ALL_SOLVED = PUZZLE_BIT["cutting_tools"] | PUZZLE_BIT["soap"] | PUZZLE_BIT["cloth"]
SUP_DIR = ROOT / "data" / "event_collection" / "drafts_c" / "dr_sup"
VILLAGE = [(0, "m", 30, "Adam", 0, False), (1, "f", 31, "Bea", 0, False), (2, "m", 40, "Cal", 0, False),
           (3, "f", 25, "Dee", 0, False), (4, "m", 8, "Kai", 0, False), (5, "f", 70, "Ula", 0, False)]


def supply_graph(changes: list[tuple[str, int]]) -> dict:
    """One page for each (item, change), in order."""
    nodes = {}
    for k, (item, delta) in enumerate(changes):
        nodes[f"p{k}"] = {"text": f"Page {k + 1}.", "effects": [{"do": "supply", "item": item, "min": delta,
                                                                  "max": delta}]}
        if k + 1 < len(changes):
            nodes[f"p{k}"]["children"] = [{"next": f"p{k + 1}"}]
    return {"format": "vvfp-cie-graph", "version": 6, "title": "Supply Test", "games": [4],
            "roles": {"subject": {"kind": "villager", "min_age": 14}}, "start": "p0", "nodes": nodes}


def compiled(graph: dict) -> bytes:
    return cg.compile_graph(cg.load(copy.deepcopy(graph), scrolling=True))


class PatcherSide(unittest.TestCase):
    def test_the_effect_compiles_and_decompiles(self):
        g = supply_graph([("cutting_tools", 2), ("soap", -1), ("cloth", 3)])
        g["nodes"]["p0"]["effects"][0].update(min=1, max=3)
        back = cg.decompile_graph(compiled(g))
        self.assertEqual([e for n in ("p0", "p1", "p2") for e in back["nodes"][n]["effects"]],
                         [{"do": "supply", "item": "cutting_tools", "min": 1, "max": 3},
                          {"do": "supply", "item": "soap", "min": -1, "max": -1},
                          {"do": "supply", "item": "cloth", "min": 3, "max": 3}])
        self.assertEqual(cg.EFFECT_CODES["supply"], 25)
        native = (ROOT / "native" / "vvfp_story_upgrades" / "story_graph.inc").read_text(encoding="utf-8")
        self.assertIn("CGE_SUPPLY = 25", native)

    def test_bad_supplies_are_refused(self):
        for bad, why in (({"item": "rope", "min": 1, "max": 1}, "supply item"),
                         ({"item": "soap", "min": 0, "max": 2}, "gain"),
                         ({"item": "soap", "min": -1, "max": 1}, "gain"),
                         ({"item": "cloth", "min": 1, "max": 100}, "gain")):
            g = supply_graph([("soap", 1)])
            g["nodes"]["p0"]["effects"] = [dict({"do": "supply"}, **bad)]
            with self.subTest(bad=bad), self.assertRaises(Exception) as ctx:
                cg.load(g, scrolling=True)
            self.assertIn(why, str(ctx.exception))
        g = supply_graph([("soap", 1)])
        g["games"] = [3]
        with self.assertRaises(Exception) as ctx:
            cg.load(g, scrolling=True)
        self.assertIn("game 4", str(ctx.exception))

    def test_no_automatic_line(self):
        e = {"do": "supply", "item": "cloth", "min": 1, "max": 1}
        self.assertEqual(cg.auto_line_options(e, 4), [])


@emulated
class GameSide(unittest.TestCase):
    """The counts in the stock The Tree of Life's own memory, changed by the companion's walk."""

    def setUp(self):
        if not have_stock("vv4"):
            self.skipTest("needs the stock The Tree of Life executable in inputs/")

    def run_graph(self, graph: dict, counts: dict, solved: int = ALL_SOLVED, cap: int = 0):
        r = V6("vv4", VILLAGE)
        for item, n in counts.items():
            r.p.put32(AT[item], n & 0xFFFFFFFF)
        r.p.export("VvfpStoryProbeGraphPuzzles", solved)
        r.p.export("VvfpStoryProbeGraphSupplyCap", cap)
        r.rolls([0] * 40)
        r.log(1)
        self.assertIsNone(r.queue6(compiled(graph)))
        r.watch = lambda: tuple(r.p.u32(AT[i]) for i in ("cutting_tools", "soap", "cloth"))  # noqa: E731
        shown = r.walk_through()
        self.assertIn(r.state()["phase"], (IDLE, DONE))
        r.p.export("VvfpStoryProbeGraphSupplyCap", -1)
        r.p.export("VvfpStoryProbeGraphPuzzles", -1)
        return r, shown

    def test_the_stock_cap_of_six_and_never_below_zero(self):
        g = supply_graph([("cutting_tools", 5), ("cloth", -5), ("soap", 20), ("cutting_tools", -2)])
        r, shown = self.run_graph(g, {"cutting_tools": 4, "soap": 90, "cloth": 2})
        self.assertEqual(len(shown), 4)
        # each change on its own page: (tools, soap, cloth) after each
        self.assertEqual(r.seen, [(6, 90, 2), (6, 90, 0), (6, 99, 0), (4, 99, 0)])
        _n, _now, filed = r.log()
        for line in ("Cutting tools: 4 -> 6", "Cloth bolts: 2 -> 0", "Bars of soap: 90 -> 99",
                     "Cutting tools: 6 -> 4"):
            self.assertIn(line, filed)

    def test_ninety_nine_with_the_supply_cap(self):
        g = supply_graph([("cutting_tools", 5), ("cloth", 5), ("cloth", 3)])
        r, _shown = self.run_graph(g, {"cutting_tools": 4, "soap": 0, "cloth": 93}, cap=1)
        self.assertEqual(r.seen, [(9, 0, 93), (9, 0, 98), (9, 0, 99)])

    def test_a_count_above_the_cap_is_never_lowered_by_a_gain(self):
        g = supply_graph([("cutting_tools", 2), ("cutting_tools", -1)])
        r, _shown = self.run_graph(g, {"cutting_tools": 9, "soap": 0, "cloth": 0}, cap=0)
        self.assertEqual(r.seen, [(9, 0, 0), (8, 0, 0)])

    def test_flavor_only_before_the_puzzle_is_solved(self):
        g = supply_graph([("cutting_tools", 2), ("soap", 3), ("cloth", 1)])
        for item in ("cutting_tools", "soap", "cloth"):
            with self.subTest(unsolved=item):
                r, _shown = self.run_graph(g, {"cutting_tools": 1, "soap": 1, "cloth": 1},
                                           solved=ALL_SOLVED & ~PUZZLE_BIT[item])
                after = dict(zip(("cutting_tools", "soap", "cloth"), r.seen[-1]))
                expect = {"cutting_tools": 3, "soap": 4, "cloth": 2}
                expect[item] = 1
                self.assertEqual(after, expect)
        r, _shown = self.run_graph(g, {"cutting_tools": 1, "soap": 1, "cloth": 1}, solved=0)
        self.assertEqual(r.seen[-1], (1, 1, 1))
        _n, _now, filed = r.log()
        self.assertNotIn(" -> ", filed)


def sup_events() -> list[Path]:
    return sorted(SUP_DIR.glob("*.json"))


@emulated
class NewEventsRunInTheTreeOfLife(unittest.TestCase):
    """Every new supply event, every choice, through the VV4 engine: each supply effect it has changes its count."""

    def test_every_event_every_choice(self):
        if not have_stock("vv4"):
            self.skipTest("needs the stock The Tree of Life executable in inputs/")
        sys.path.insert(0, str(ROOT / "scripts"))
        import collection_check as cc
        events = sup_events()
        self.assertGreaterEqual(len(events), 10)
        ran = 0
        for path in events:
            doc = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(doc["games"], [4], path.name)
            graph = cc.graph_for_engine(doc)
            choices = len(graph["nodes"][graph["start"]].get("choices", [])) or 1
            for choice in range(choices):
                with self.subTest(event=path.stem, choice=choice):
                    r = V6("vv4", VILLAGE)
                    for at in AT.values():
                        r.p.put32(at, 3)
                    r.p.export("VvfpStoryProbeGraphPuzzles", ALL_SOLVED)
                    r.p.export("VvfpStoryProbeGraphSupplyCap", 0)
                    r.rolls([0] * 60)
                    self.assertIsNone(r.queue6(compiled(graph)))
                    r.watch = lambda r=r: tuple(r.p.u32(AT[i]) for i in AT)  # noqa: E731
                    answers = [choice] if "choices" in graph["nodes"][graph["start"]] else []
                    shown = r.walk_through(answers)
                    self.assertTrue(shown)
                    self.assertIn(r.state()["phase"], (IDLE, DONE))
                    # the effects of the outcome page taken (a fixed change; the roll 0 takes a range's least)
                    page = graph["nodes"][graph["nodes"][graph["start"]]["choices"][choice]["next"]] \
                        if answers else graph["nodes"][graph["start"]]
                    want = {i: 3 for i in AT}
                    for e in page.get("effects", []):
                        if e["do"] == "supply":
                            want[e["item"]] = max(0, min(6, want[e["item"]] + e["min"]))
                    self.assertEqual(r.seen[-1], tuple(want[i] for i in AT))
                    r.p.export("VvfpStoryProbeGraphSupplyCap", -1)
                    r.p.export("VvfpStoryProbeGraphPuzzles", -1)
                    ran += 1
        self.assertGreater(ran, 0)


if __name__ == "__main__":
    unittest.main()
