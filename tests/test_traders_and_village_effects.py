"""Traders and the new island-event effects (docs/event-collection/cie-v6-binary.md 33-35; the owner's spec of
2026-11-16/17; docs/event-collection/traders-and-effects-research.md).

- Patcher side: "supply" for every game's goods, "trade", "group", "village" and the condition "has_supply" compile,
  decompile and are refused when wrong; the codes match the native engine.
- Game side: "VVFP Story Upgrades.dll" (its test build) in each stock executable in the emulator: goods never go
  below 0 and stop at the game's ceiling; a trade is all or nothing; a word the game does not keep changes nothing;
  has_supply routes the walk; group sickness never reaches a protected villager and cure clears everyone; a group
  behaviour starts only its age group's action; a tech level stays within 1..3 and is raised by the game's own
  routine in The Secret City, The Tree of Life and New Believers; the weather is started by the game's own starter
  (and never in A New Home or The Lost Children); the next island event moves; a construction stops one short.
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
from test_story_custom_island_event import HAVE_EMULATOR, _food_tech, emulated, have_stock  # noqa: E402

if HAVE_EMULATOR:
    from test_story_cie_graph_runtime import DONE, IDLE
    from test_story_cie_graph_runtime_v6 import V6

GAME_IDS = ("vv1", "vv2", "vv3", "vv4", "vv5")
NATIVE = ROOT / "native" / "vvfp_story_upgrades"
VILLAGE = [(0, "m", 30, "Adam", 0, False), (1, "f", 31, "Bea", 0, False), (2, "m", 8, "Kai", 0, False),
           (3, "f", 70, "Ula", 0, False)]
DO_ACTION = {"vv3": 0x455570, "vv4": 0x45DEC0, "vv5": 0x465580}
WEATHER_STARTER = {"vv3": (0x41FB40, 0x4B86C4), "vv4": (0x46BC30, 0x6C461C), "vv5": (0x477060, 0x718EA0)}
LEVEL_RAISE = {"vv3": 0x426FD0, "vv4": 0x41E1D0, "vv5": 0x423610}
LEVEL_AT = {"vv3": 0x582618, "vv4": 0x4D6F5C, "vv5": 0x51D5CC}       # area 0 (Science)
LEVEL_WORLD = {"vv1": 0xA2C4, "vv2": 0x2EA7C}                          # Science, a world offset
COLLECTIBLE_AT = {"vv3": 0x58F438 + 4 * 0x34, "vv4": 0x4CC918, "vv5": 0x4DBFC8 + 0x630 + 4 * 0x50}


def pages(effects_per_page: list[list[dict]], games: list[int], title: str = "Village Test") -> dict:
    nodes = {}
    for k, fx in enumerate(effects_per_page):
        nodes[f"p{k}"] = {"text": f"Page {k + 1}.", "effects": fx}
        if k + 1 < len(effects_per_page):
            nodes[f"p{k}"]["children"] = [{"next": f"p{k + 1}"}]
    return {"format": "vvfp-cie-graph", "version": 6, "title": title, "games": games,
            "roles": {"subject": {"kind": "villager", "min_age": 14}}, "start": "p0", "nodes": nodes}


def compiled(graph: dict) -> bytes:
    return cg.compile_graph(cg.load(copy.deepcopy(graph), scrolling=True))


class PatcherSide(unittest.TestCase):
    def test_the_codes_match_the_engine(self):
        native = (NATIVE / "story_graph.inc").read_text(encoding="utf-8")
        for name, code in (("TRADE", 26), ("GROUP", 27), ("VILLAGE", 28)):
            self.assertIn(f"CGE_{name} = {code}", native)
            self.assertEqual(cg.EFFECT_CODES[name.lower()], code)
        self.assertIn("CGC_HAS_SUPPLY = 18", native)
        self.assertEqual(cg.COND_CODES["has_supply"], 18)
        village = (NATIVE / "story_graph_village.inc").read_text(encoding="utf-8")
        for word in cg.GOODS:
            self.assertIn(f'"{word}"', village, word)
        for kind in cg.GROUP_KINDS:
            self.assertIn(f'{{ "{kind}"', village, kind)

    def test_round_trip(self):
        fx = [{"do": "trade", "give": "food", "give_amount": 50, "get": "tech", "get_amount": 20},
              {"do": "supply", "item": "collectible", "min": -2, "max": -1},
              {"do": "group", "kind": "song", "who": "all"},
              {"do": "group", "kind": "sick", "who": "all", "percent": 25},
              {"do": "group", "kind": "speech", "who": "subject"},
              {"do": "village", "what": "event_timer", "min": -6, "max": -2},
              {"do": "village", "what": "tech_level", "step": -1, "area": "Medicine"},
              {"do": "village", "what": "construction", "min": 50, "max": 100},
              {"do": "village", "what": "weather", "weather": "storm"}]
        g = pages([fx], [1, 2, 3, 4, 5])
        g["nodes"]["p0"]["children"] = []
        back = cg.decompile_graph(compiled(g))
        self.assertEqual(back["nodes"]["p0"]["effects"], fx)

    def test_has_supply_round_trip_and_where_it_may_stand(self):
        g = pages([[], []], [3])
        g["nodes"]["p0"]["children"] = [{"next": "p1", "if": {"has_supply": {"item": "honey", "min": 40}}}]
        g["nodes"]["p0"]["else"] = "p1"
        g["requirement"] = {"if": {"has_supply": {"item": "food", "min": 100}}}
        back = cg.decompile_graph(compiled(g))
        self.assertEqual(back["nodes"]["p0"]["children"][0]["if"], {"has_supply": {"item": "honey", "min": 40}})
        self.assertEqual(back["requirement"]["if"], {"has_supply": {"item": "food", "min": 100}})

    def test_wrong_effects_are_refused(self):
        for games, bad, why in (
                ([1, 2, 3, 4, 5], {"do": "supply", "item": "mushrooms", "min": 1, "max": 1}, "supply item"),
                ([3], {"do": "supply", "item": "fish", "min": 1, "max": 1}, "no game of the event keeps"),
                ([4], {"do": "supply", "item": "cloth", "min": 1, "max": 100}, "gain"),
                ([4], {"do": "supply", "item": "food", "min": 1, "max": 10000}, "gain"),
                ([4], {"do": "trade", "give": "food", "give_amount": 0, "get": "tech", "get_amount": 1}, "1.."),
                ([4], {"do": "trade", "give": "soap", "give_amount": 1, "get": "soap", "get_amount": 1}, "another"),
                ([4], {"do": "trade", "give": "honey", "give_amount": 1, "get": "food", "get_amount": 1},
                 "no game of the event keeps"),
                ([4], {"do": "group", "kind": "juggle"}, "group kind"),
                ([4], {"do": "group", "kind": "cure", "who": "subject"}, "whole village"),
                ([4], {"do": "group", "kind": "sick"}, "percent"),
                ([4], {"do": "village", "what": "tech_level", "step": 2}, "step"),
                ([4], {"do": "village", "what": "tech_level", "step": 1, "area": "Magic"}, "area"),
                ([1, 2], {"do": "village", "what": "weather", "weather": "rain"}, "no game of the event has"),
                ([3], {"do": "village", "what": "weather", "weather": "sun"}, "no game of the event has"),
                ([4], {"do": "village", "what": "event_timer", "min": -1, "max": 1}, "event_timer"),
                ([4], {"do": "village", "what": "construction", "min": 0, "max": 5}, "construction")):
            g = pages([[bad]], games)
            with self.subTest(bad=bad), self.assertRaises(Exception) as ctx:
                cg.load(g, scrolling=True)
            self.assertIn(why, str(ctx.exception))

    def test_no_automatic_lines(self):
        for e in ({"do": "trade", "give": "food", "give_amount": 1, "get": "tech", "get_amount": 1},
                  {"do": "group", "kind": "dance", "who": "all"},
                  {"do": "village", "what": "weather", "weather": "fog"}):
            self.assertEqual(cg.auto_line_options(e, 4), [])


@emulated
class GameSide(unittest.TestCase):
    """The village in each stock executable's own memory, changed by the companion's walk."""

    def run_graph(self, game: str, graph: dict, setup=None, answers=(), people=VILLAGE):
        r = V6(game, people)
        if game == "vv3":
            world = r.p.alloc(0x13000)
            r.p.stub(0x428B60, lambda q: (world, 0))
            r.world3 = world
        if game == "vv4" and r.p.u32(0x4CB51C) == 0:
            r.p.put32(0x4CB51C, r.p.alloc(0x18000))
        if game == "vv5" and r.p.u32(0x4DACE0) == 0:
            r.p.put32(0x4DACE0, r.p.alloc(0x18000))
        r.p.export("VvfpStoryProbeGraphPuzzles", 0xFFFF)
        r.p.export("VvfpStoryProbeGraphSupplyCap", 0)
        if setup:
            setup(r)
        r.rolls([0] * 60)
        r.log(1)
        self.assertIsNone(r.queue6(compiled(graph)))
        shown = r.walk_through(list(answers))
        self.assertIn(r.state()["phase"], (IDLE, DONE))
        r.p.export("VvfpStoryProbeGraphPuzzles", -1)
        r.p.export("VvfpStoryProbeGraphSupplyCap", -1)
        return r, shown

    def food_tech(self, r) -> tuple[int, int]:
        food, tech, _, _ = _food_tech(r.story)
        return struct.unpack("<i", r.p.read(food, 4))[0], struct.unpack("<i", r.p.read(tech, 4))[0]

    def set_food_tech(self, r, food: int, tech: int) -> None:
        f, t, _, _ = _food_tech(r.story)
        r.p.put32(f, food)
        r.p.put32(t, tech)

    def test_a_trade_is_all_or_nothing_in_every_game(self):
        for game in GAME_IDS:
            if not have_stock(game):
                continue
            with self.subTest(game=game):
                g = pages([[{"do": "trade", "give": "food", "give_amount": 100, "get": "tech", "get_amount": 30}],
                           [{"do": "trade", "give": "food", "give_amount": 1000, "get": "tech",
                             "get_amount": 999}]], [int(game[2])])
                r, _ = self.run_graph(game, g, lambda r: self.set_food_tech(r, 500, 10))
                self.assertEqual(self.food_tech(r), (400, 40), "the first trade; the second is short: nothing")

    def test_has_supply_routes_the_walk(self):
        g = {"format": "vvfp-cie-graph", "version": 6, "title": "Market Day", "games": [4],
             "roles": {"subject": {"kind": "villager", "min_age": 14}}, "start": "s",
             "nodes": {"s": {"type": "branch", "children": [
                 {"next": "rich", "if": {"has_supply": {"item": "food", "min": 300}}}, {"next": "poor"}]},
                 "rich": {"text": "The trader stays."}, "poor": {"text": "The trader moves on."}}}
        if not have_stock("vv4"):
            self.skipTest("no stock The Tree of Life")
        for food, word in ((500, "stays"), (299, "moves on")):
            with self.subTest(food=food):
                _r, shown = self.run_graph("vv4", g, lambda r, food=food: self.set_food_tech(r, food, 0))
                self.assertIn(word, " ".join(s[1] for s in shown))

    def test_goods_never_go_below_zero_and_stop_at_the_ceiling(self):
        cases = {   # game: (item, address of the count (world offset for VV1/VV2), start, change, ceiling)
            "vv1": ("berries", ("world", 0xA2F4), 4990, 100, 5000),
            "vv2": ("fish", ("world", 0x2EAD0), 2150, 100, 2200),
            "vv3": ("honey", ("abs", 0x5945E0), 2990, 50, 3000),
            "vv4": ("blackberries", ("w4", 0x170F8), 990, 50, 1000),
            "vv5": ("noni", ("w5", 0x17D58), 980, 50, 1000),
        }
        for game, (item, (kind, off), start, change, top) in cases.items():
            if not have_stock(game):
                continue
            with self.subTest(game=game, item=item):
                g = pages([[{"do": "supply", "item": item, "min": change, "max": change}],
                           [{"do": "supply", "item": item, "min": -9999, "max": -9999}]], [int(game[2])])
                seen = []

                def at(r, kind=kind, off=off, game=game):
                    if kind == "world":
                        return r.story.village.world + off
                    if kind == "w4":
                        return r.p.u32(0x4CB51C) + off
                    if kind == "w5":
                        return r.p.u32(0x4DACE0) + off
                    return off

                def setup(r, at=at, start=start):
                    r.p.put32(at(r), start)
                    r.watch = lambda: seen.append(struct.unpack("<i", r.p.read(at(r), 4))[0])  # noqa: E731

                self.run_graph(game, g, setup)
                self.assertEqual(seen, [top, 0], "the ceiling, then never below 0")

    def test_a_good_the_game_does_not_keep_changes_nothing(self):
        if not have_stock("vv1"):
            self.skipTest("no stock A New Home")
        g = pages([[{"do": "supply", "item": "collectible", "min": 3, "max": 3},
                    {"do": "trade", "give": "food", "give_amount": 10, "get": "honey", "get_amount": 5}]],
                  [1, 3])
        r, _ = self.run_graph("vv1", g, lambda r: self.set_food_tech(r, 500, 7))
        self.assertEqual(self.food_tech(r), (500, 7), "A New Home keeps no collectibles and no honey")
        _n, _now, filed = r.log()
        self.assertNotIn(" -> ", filed)

    def test_collectibles_take_only_duplicates(self):
        for game in ("vv3", "vv4", "vv5"):
            if not have_stock(game):
                continue
            with self.subTest(game=game):
                base = COLLECTIBLE_AT[game]
                g = pages([[{"do": "supply", "item": "collectible", "min": -5, "max": -5}],
                           [{"do": "supply", "item": "collectible", "min": 2, "max": 2}]], [int(game[2])])
                counts = []

                def setup(r, base=base):
                    for k in range(48):
                        r.p.put32(base + 4 * k, 0)
                    r.p.put32(base, 3)
                    r.p.put32(base + 4, 1)
                    r.watch = lambda: counts.append([struct.unpack("<i", r.p.read(base + 4 * k, 4))[0]  # noqa
                                                     for k in range(48)])

                self.run_graph(game, g, setup)
                self.assertEqual(counts[0][:2], [1, 1], "two duplicates taken, every piece kept")
                self.assertTrue(all(c >= 0 for c in counts[0]))
                self.assertEqual(sum(counts[1]), sum(counts[0]) + 2)
        if have_stock("vv2"):
            g = pages([[{"do": "supply", "item": "collectible", "min": -3, "max": -3}],
                       [{"do": "supply", "item": "collectible", "min": 1, "max": 1}]], [2])
            found = []

            def setup2(r):
                w = r.story.village.world
                r.p.write(w + 0x2E720, b"\1" + b"\0" * 47)
                r.watch = lambda: found.append(sum(r.p.read(w + 0x2E720, 48)))  # noqa: E731

            self.run_graph("vv2", g, setup2)
            self.assertEqual(found, [1, 2], "The Lost Children's found flags: never taken, one more found")

    def test_group_sickness_spares_the_protected_and_cure_clears(self):
        if not have_stock("vv4"):
            self.skipTest("no stock The Tree of Life")
        people = [(0, "m", 30, "Adam", 0, False), (1, "f", 31, "Bea", 0, True), (2, "m", 8, "Kai", 0, False)]
        g = pages([[{"do": "group", "kind": "sick", "percent": 100}], [{"do": "group", "kind": "cure"}]], [4])
        sick = []

        def setup(r):
            r.watch = lambda: sick.append([r.v.sick(i) for i in range(3)])  # noqa: E731

        self.run_graph("vv4", g, setup, people=people)
        self.assertEqual(sick, [[1, 0, 1], [0, 0, 0]], "the nursing mother is never made sick; cure clears all")

    def test_a_group_behaviour_starts_its_age_group(self):
        for game in ("vv3", "vv4", "vv5"):
            if not have_stock(game):
                continue
            with self.subTest(game=game):
                g = pages([[{"do": "group", "kind": "play"}], [{"do": "group", "kind": "stories"}],
                           [{"do": "group", "kind": "dance"}]], [int(game[2])])
                starts = []

                def setup(r, game=game):
                    r.record(DO_ACTION[game], 8)
                    r.watch = lambda: starts.append(len(r.recorded.get(DO_ACTION[game], [])))  # noqa: E731

                self.run_graph(game, g, setup)
                self.assertEqual([b - a for a, b in zip([0] + starts, starts)], [1, 2, 4],
                                 "the child plays; the elder tells and the child listens; all four dance")

    def test_tech_levels_stay_within_one_to_three(self):
        for game in GAME_IDS:
            if not have_stock(game):
                continue
            with self.subTest(game=game):
                g = pages([[{"do": "village", "what": "tech_level", "step": 1, "area": "Science"}],
                           [{"do": "village", "what": "tech_level", "step": 1, "area": "Science"}],
                           [{"do": "village", "what": "tech_level", "step": -1, "area": "Science"}],
                           [{"do": "village", "what": "tech_level", "step": -1, "area": "Science"}],
                           [{"do": "village", "what": "tech_level", "step": -1, "area": "Science"}]],
                          [int(game[2])])
                levels = []

                def setup(r, game=game):
                    at = r.story.village.world + LEVEL_WORLD[game] if game in LEVEL_WORLD else LEVEL_AT[game]
                    r.p.put32(at, 2)
                    if game in LEVEL_RAISE:
                        # the game's own raise, observed (its listeners are the game's): +1, at most 3
                        def raise_(q, at=at):
                            q.write(at, struct.pack("<i", min(3, struct.unpack("<i", q.read(at, 4))[0] + 1)))
                            return 0, 8 if game == "vv5" else 4
                        r.p.stub(LEVEL_RAISE[game], raise_)
                        r.p.mu.hook_add(1 << 2, r.p._on_code, begin=LEVEL_RAISE[game], end=LEVEL_RAISE[game])
                    r.watch = lambda: levels.append(struct.unpack("<i", r.p.read(at, 4))[0])  # noqa: E731

                self.run_graph(game, g, setup)
                self.assertEqual(levels, [3, 3, 2, 1, 1])

    def test_the_weather_is_the_games_own_starter(self):
        for game in GAME_IDS:
            if not have_stock(game):
                continue
            with self.subTest(game=game):
                games = [int(game[2])] + ([4] if game in ("vv1", "vv2") else [])
                g = pages([[{"do": "village", "what": "weather", "weather": "rain"}],
                           [{"do": "village", "what": "weather", "weather": "storm"}]], games)

                def setup(r, game=game):
                    if game in WEATHER_STARTER:
                        r.record(WEATHER_STARTER[game][0], 8)

                r, _ = self.run_graph(game, g, setup)
                _n, _now, filed = r.log()
                if game not in WEATHER_STARTER:
                    self.assertNotIn("Weather:", filed, "no weather in A New Home or The Lost Children")
                    continue
                calls = r.recorded.get(WEATHER_STARTER[game][0], [])
                storm = 5 if game == "vv5" else 3
                self.assertEqual(calls, [[WEATHER_STARTER[game][1], 2, 0], [WEATHER_STARTER[game][1], storm, 0]])
                self.assertIn("Weather: rain", filed)

    def test_the_next_island_event_moves(self):
        timers = {"vv1": ("world", 0xA300), "vv2": ("world", 0x2EAE0), "vv4": ("w4", 0x170E0)}
        for game, (kind, off) in timers.items():
            if not have_stock(game):
                continue
            with self.subTest(game=game):
                g = pages([[{"do": "village", "what": "event_timer", "min": -3, "max": -3}],
                           [{"do": "village", "what": "event_timer", "min": 5, "max": 5}]], [int(game[2])])
                seen = []

                def setup(r, kind=kind, off=off):
                    at = (r.story.village.world if kind == "world" else r.p.u32(0x4CB51C)) + off
                    r.p.put32(at, 0xF0000000)
                    r.watch = lambda: seen.append(r.p.u32(at))  # noqa: E731

                self.run_graph(game, g, setup)
                self.assertEqual(seen, [0xF0000000 - 3 * 3600, 0xF0000000 + 2 * 3600])

    def test_a_construction_stops_one_short(self):
        if have_stock("vv1"):
            g = pages([[{"do": "village", "what": "construction", "min": 50, "max": 50}],
                       [{"do": "village", "what": "construction", "min": 500, "max": 500}]], [1])
            seen = []

            def setup1(r):
                w = r.story.village.world
                r.p.put32(w + 0x9FE4, 100)
                r.p.put32(w + 0x9FE8, 0)
                r.watch = lambda: seen.append(r.p.u32(w + 0x9FE4))  # noqa: E731

            self.run_graph("vv1", g, setup1)
            self.assertEqual(seen, [150, 249], "hut 1's 250 is left to the builder's next trip")
        if have_stock("vv4"):
            g = pages([[{"do": "village", "what": "construction", "min": 50, "max": 50}]], [4])
            seen4 = []

            def setup4(r):
                r.p.put32(0x4D8BF8 + 8 * 19, 1990)
                r.p.put32(0x4D8B20 + 4 * 19, 2000)
                r.watch = lambda: seen4.append(r.p.u32(0x4D8BF8 + 8 * 19))  # noqa: E731

            self.run_graph("vv4", g, setup4)
            self.assertEqual(seen4, [1999])


if __name__ == "__main__":
    unittest.main()
