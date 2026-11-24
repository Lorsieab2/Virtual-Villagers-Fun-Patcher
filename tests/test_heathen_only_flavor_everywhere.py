"""The owner (2026-11-23): "If only heathens or outsiders are involved in any island event ... Food and tech points
gain loss to the heathen tribe = acceptable but flavor text only. Our tribe doesnt get altered."  Found live on main
f9736b7d: a Custom Island Event with only Heathens ("All Heathens") and Food +100 said "Your village gains 100 food."
and added the food.

Every engine path that changes the tribe's own stores, emulated beside New Believers' stock executable:
* the plain Custom Island Event (story_custom.inc ce_apply / ce_compose_in_once): every villager changed a Heathen --
  its food, tech points, stores and structures (a puzzle) are the Heathens' village's, made nowhere, each told with
  "(no effect)"; one believer among them -- made as always;
* the branching engine (story_graph.inc cg_heathen_cast_now): a Heathen cast however the event cast them (here a
  heathen_ok Isolan role, no row installed) is the Heathens' own cast.
"""
from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import vv_cie_graph as cg  # noqa: E402
from test_story_custom_island_event import HAVE_EMULATOR, emulated, have_stock  # noqa: E402

if HAVE_EMULATOR:
    from story_custom_fixtures import Event  # noqa: E402
    from test_story_custom_island_event import Story, _food_tech  # noqa: E402
    from test_story_cie_graph_runtime import stores  # noqa: E402
    from test_story_cie_graph_runtime_v6 import V6  # noqa: E402

ADD = 1
FACTION = 0x1CEC
PUZZLE_NEEDED, PUZZLE_PROGRESS = 0x51DF30, 0x51E008     # the game's own per-puzzle need and progress


@emulated
class PlainCustomIslandEvent(unittest.TestCase):
    def setUp(self):
        if not have_stock("vv5"):
            self.skipTest("no stock New Believers")

    def story(self, heathens):
        story = Story("vv5")
        v = story.village
        for i, name in ((0, "Romotu"), (1, "Coral"), (2, "Ana")):
            v.put(i, sex="m" if i == 0 else "f", years=30, name=name)
        for i in heathens:
            story.proc.write(v.record(i) + FACTION, b"\x01")
        for p in range(40):
            story.proc.put32(PUZZLE_NEEDED + 4 * p, 1)
        return story

    def event(self, story, who):
        return Event(food_op=ADD, food_amount=100, tech_op=ADD, tech_amount=50, puzzles=[(1, 1)],
                     changes=[story.change(i, health=80) for i in who])

    def puzzles(self, story) -> bytes:
        return story.proc.read(PUZZLE_PROGRESS, 8 * 40)

    def test_only_heathens_change_nothing_of_the_tribe(self):
        story = self.story(heathens=(0, 1))
        food, tech, _lf, _lt = _food_tech(story)
        p = story.proc
        p.put32(food, 1000)
        p.put32(tech, 3000)
        before = self.puzzles(story)
        ok, r, text = story.apply(self.event(story, (0, 1)))
        text = " ".join(text.split())                    # the popup's own line breaks
        self.assertEqual(r["heathens_only"], 1)
        self.assertEqual((p.u32(food), p.u32(tech)), (1000, 3000), "our tribe doesn't get altered")
        self.assertEqual(self.puzzles(story), before, "no structure (puzzle) of the tribe is made")
        self.assertIn("The Heathens' village gains 100 food. (no effect)", text)
        self.assertIn("The Heathens' village gains 50 tech points. (no effect)", text)
        self.assertIn("The Heathens' village's buildings and stores change. (no effect)", text)
        self.assertNotIn("Your village gains", text)
        self.assertEqual(r["changed"], 2, "the Heathens' own changes are made as always")

    def test_a_believer_among_them_changes_the_tribe(self):
        story = self.story(heathens=(0,))
        food, tech, _lf, _lt = _food_tech(story)
        p = story.proc
        p.put32(food, 1000)
        p.put32(tech, 3000)
        before = self.puzzles(story)
        ok, r, text = story.apply(self.event(story, (0, 2)))
        self.assertEqual(r["heathens_only"], 0)
        self.assertEqual((p.u32(food), p.u32(tech)), (1100, 3050))
        self.assertNotEqual(self.puzzles(story), before, "the puzzle is solved for the tribe")
        self.assertIn("Your village gains 100 food.", text)
        self.assertNotIn("(no effect)", text)

    def test_no_villager_at_all_is_the_tribes_own_gift(self):
        story = self.story(heathens=(0, 1))
        food, _t, _lf, _lt = _food_tech(story)
        story.proc.put32(food, 1000)
        ok, r, text = story.apply(Event(food_op=ADD, food_amount=100))
        self.assertEqual(r["heathens_only"], 0)
        self.assertEqual(story.proc.u32(food), 1100)


@emulated
class RevivedAndNewVillagers(unittest.TestCase):
    """Codex on #859: a skeleton the event brings back (before its villagers' changes) is in the event by the faction
    it comes back as -- a believer's revived body is the tribe's own, a Heathen's comes back a Heathen -- and so is a
    new villager it makes (a believer unless made a Heathen)."""

    def setUp(self):
        if not have_stock("vv5"):
            self.skipTest("no stock New Believers")

    def run_event(self, skeleton_heathen=None, spawn_faction=None):
        from test_story_maker_additions import REVIVE, STOP, record, stub_clock, story as maker_story
        from story_custom_fixtures import Spawn
        s = maker_story("vv5")
        stub_clock(s)
        record(s, *STOP["vv5"])
        v = s.village
        v.put(0, sex="m", years=30, name="Romotu")
        s.proc.write(v.record(0) + FACTION, b"\x01")
        revives, changes = [], [s.change(0, health=80)]
        if skeleton_heathen is not None:
            v.put(4, sex="f", years=30, name="Bones", health=0)
            s.proc.write(v.record(4) + REVIVE["vv5"]["sick"], b"\x01")
            if skeleton_heathen:
                s.proc.write(v.record(4) + FACTION, b"\x01")
            revives = [(4, v.identity(4), 100, 1)]
            changes.append(s.change(4, health=90))
        spawns = [] if spawn_faction is None else [Spawn(count=1, faction=spawn_faction)]
        food, _t, _lf, _lt = _food_tech(s)
        s.proc.put32(food, 1000)
        ok, r, text = s.apply(Event(food_op=ADD, food_amount=100, revives=revives, changes=changes, spawns=spawns))
        return r, s.proc.u32(food), " ".join(text.split())

    def test_a_believers_skeleton_revived_makes_it_the_tribes(self):
        r, food, text = self.run_event(skeleton_heathen=False)
        self.assertEqual(r["heathens_only"], 0)
        self.assertEqual(food, 1100)
        self.assertNotIn("(no effect)", text)

    def test_a_heathens_skeleton_revived_keeps_it_the_heathens(self):
        r, food, text = self.run_event(skeleton_heathen=True)
        self.assertEqual(r["heathens_only"], 1)
        self.assertEqual(food, 1000)
        self.assertIn("The Heathens' village gains 100 food. (no effect)", text)

    def test_a_new_villager_is_the_tribes_unless_made_a_heathen(self):
        from story_custom_fixtures import KEEP, Spawn
        for faction, heathens_only, want in ((KEEP, 0, 1100), (1, 1, 1000)):   # the game's own: a believer
            with self.subTest(faction=faction):
                s = Story("vv5")
                v = s.village
                v.put(0, sex="m", years=30, name="Romotu")
                s.proc.write(v.record(0) + FACTION, b"\x01")

                def heathen(q, s=s):            # the game's Heathen creator 0x46FD20, stood in for
                    index = s._create(1 if q.arg(3) == 1 else 0, q.arg(4))
                    q.write(s.village.record(index) + FACTION, b"\x01")
                    return index, 0x24
                s.proc.stub(0x46FD20, heathen)
                food, _t, _lf, _lt = _food_tech(s)
                s.proc.put32(food, 1000)
                ok, r, _text = s.apply(Event(food_op=ADD, food_amount=100, changes=[s.change(0, health=80)],
                                             spawns=[Spawn(count=1, faction=faction)]))
                self.assertEqual((r["heathens_only"], s.proc.u32(food)), (heathens_only, want))


class Translations(unittest.TestCase):
    """Codex on #859: each flavor line is looked up by the stem the translation catalog gives it
    (data/translations/patcher_strings.json, scripts/build_patch_text_inventory.py), with that very English -- else a
    translation never reaches the line."""

    def test_every_line_uses_its_catalog_stem(self):
        import json
        import re
        source = (ROOT / "native" / "vvfp_story_upgrades" / "story_custom.inc").read_text(encoding="utf-8")
        body = source[source.index("static int ce_heathens_lines("):]
        body = body[:body.index("\n}\n")]
        stems = re.findall(r'"(vvfp\.story/story_custom\.ce_heathens_lines\.[^"]+)"', body)
        words = re.findall(r'"(The (?:Heathens|Isolans)\' village[^"]*)"', body)
        self.assertEqual(len(stems), 14)
        self.assertEqual(len(words), 14)
        catalog = json.loads((ROOT / "data" / "translations" / "patcher_strings.json").read_text(encoding="utf-8"))
        rows = {r["stem"]: r["english"] for r in catalog["strings"]}
        for stem, english in zip(stems, words):
            with self.subTest(stem=stem):
                self.assertIn(stem, rows, "a stem the catalog has")
                self.assertEqual(rows[stem], english, "the catalog's English for that stem")

def graph(roles: dict) -> dict:
    return {"format": "vvfp-cie-graph", "version": 6, "title": "Camp Life", "games": [5], "roles": roles,
            "start": "p",
            "nodes": {"p": {"text": "(isolan.Name) shares a meal by the fire.", "auto_text": True,
                            "effects": [{"do": "food", "amount": 50}, {"do": "tech", "amount": 30}]}}}


def compiled(g: dict) -> bytes:
    return cg.compile_graph(cg.load(copy.deepcopy(g), scrolling=True))


@emulated
class BranchingEvent(unittest.TestCase):
    """No "Heathens can be selected in Island Events" row: a vanilla heathen_ok Isolan role casts the Heathen."""

    def setUp(self):
        if not have_stock("vv5"):
            self.skipTest("no stock New Believers")

    def run_with(self, roles, people, heathens):
        r = V6("vv5", people)
        for i in heathens:
            r.p.write(r.v.record(i) + FACTION, b"\x01")
        text = "vv5\n"
        buf = r.p.alloc(len(text) + 1)
        r.p.write(buf, text.encode("ascii") + b"\0")
        r.p.export("VvfpStoryProbeInstalledPatches", 5, buf)
        r.rolls([0] * 40)
        before = stores(r)
        self.assertIsNone(r.queue6(compiled(graph(roles))))
        words = " ".join(" ".join(s[1] for s in r.walk_through()).split())
        return before, stores(r), words

    def test_a_heathen_ok_isolan_alone_is_flavor(self):
        before, after, words = self.run_with({"isolan": {"kind": "villager", "min_age": 14, "heathen_ok": True}},
                                             [(0, "m", 30, "Romotu", 0, False)], heathens=(0,))
        self.assertEqual(after, before)
        self.assertIn("The Heathens' village gains 50 food. (no effect)", words)
        self.assertIn("The Heathens' village gains 30 tech points. (no effect)", words)

    def test_with_a_believer_it_is_the_tribes(self):
        before, after, words = self.run_with({"isolan": {"kind": "villager", "min_age": 14, "heathen_ok": True},
                                              "host": {"kind": "villager", "min_age": 14}},
                                             [(0, "m", 30, "Romotu", 0, False), (1, "f", 30, "Ana", 0, False)],
                                             heathens=(0,))
        self.assertEqual(after, (before[0] + 50, before[1] + 30))
        self.assertNotIn("(no effect)", words)


if __name__ == "__main__":
    unittest.main()
