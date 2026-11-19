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
    from unicorn import UC_HOOK_CODE
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
CLOCK = {"vv3": 0x403330, "vv5": 0x4036E0}                           # the island timers' clocks (sc_clock)
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
        for name, code in (("TRADE", 41), ("GROUP", 42), ("VILLAGE", 43)):
            self.assertIn(f"CGE_{name} = {code}", native)
            self.assertEqual(cg.EFFECT_CODES[name.lower()], code)
        self.assertIn("CGC_HAS_SUPPLY = 19", native)
        self.assertEqual(cg.COND_CODES["has_supply"], 19)
        village = (NATIVE / "story_graph_village.inc").read_text(encoding="utf-8")
        for word in cg.GOODS:
            self.assertIn(f'"{word}"', village, word)
        for kind in cg.GROUP_KINDS:
            if kind != "effect":                 # every "effect:" word is words only: refused by the compiler
                self.assertIn(f'"{kind}:"' if kind == "work" else f'{{ "{kind}"', village, kind)
        self.assertEqual(cg.TEMP_EFFECTS, {})

    def test_round_trip(self):
        fx = [{"do": "trade", "give": "food", "give_amount": 50, "get": "tech", "get_amount": 20},
              {"do": "supply", "item": "collectible", "min": -2, "max": -1},
              {"do": "group", "kind": "song", "who": "all"},
              {"do": "group", "kind": "speech", "who": "subject"},
              {"do": "village", "what": "event_timer", "min": -6, "max": -2},
              {"do": "village", "what": "tech_level", "step": -1, "area": "Medicine"},
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
                ([4], {"do": "village", "what": "spawn"}, "village what"),
                ([4], {"do": "village", "what": "tech_level", "step": 2}, "step"),
                ([4], {"do": "village", "what": "tech_level", "step": 1, "area": "Magic"}, "area"),
                ([1, 2], {"do": "village", "what": "weather", "weather": "rain"}, "no game of the event has"),
                ([3], {"do": "village", "what": "weather", "weather": "sun"}, "no game of the event has"),
                ([4], {"do": "village", "what": "event_timer", "min": -1, "max": 1}, "event_timer"),
                ([4], {"do": "village", "what": "construction", "min": 1, "max": 5}, "village what")):
            g = pages([[bad]], games)
            with self.subTest(bad=bad), self.assertRaises(Exception) as ctx:
                cg.load(g, scrolling=True)
            self.assertIn(why, str(ctx.exception))

    def test_their_lines_are_written_as_they_are_made(self):
        # The owner (2026-11-18): a line whenever an effect happens, with the amount.  These are written by the
        # engine as each is made (village.inc cg_after_line), so a simulated walk has none; the fit takes the widest.
        for e, want in (({"do": "trade", "give": "food", "give_amount": 1, "get": "tech", "get_amount": 2},
                         ["The village gives 1 food.", "The village gets 2 tech points."]),
                        ({"do": "group", "kind": "dance", "who": "all"}, ["The village dances."]),
                        ({"do": "village", "what": "weather", "weather": "fog"}, ["Fog rolls in."]),
                        ({"do": "village", "what": "event_timer", "min": 5, "max": 5},
                         ["The next island event will come 72 hours later."])):
            self.assertEqual(cg.auto_line_options(e, 4), want)
            self.assertEqual(cg.auto_line_options(e, 4, None, [0, 0]), [])


@emulated
class GameSide(unittest.TestCase):
    """The village in each stock executable's own memory, changed by the companion's walk."""

    def run_graph(self, game: str, graph: dict, setup=None, answers=(), people=VILLAGE):
        r = V6(game, people)
        if game == "vv3":
            world = r.p.alloc(0x13000)
            r.p.stub(0x428B60, lambda q: (world, 0))
            r.p.mu.hook_add(UC_HOOK_CODE, r.p._on_code, begin=0x428B60, end=0x428B60)
            r.world3 = world
        if game == "vv4" and r.p.u32(0x4CB51C) == 0:
            r.p.put32(0x4CB51C, r.p.alloc(0x18000))
        if game == "vv5" and r.p.u32(0x4DACE0) == 0:
            r.p.put32(0x4DACE0, r.p.alloc(0x18000))
        r.p.export("VvfpStoryProbeGraphPuzzles", 0xFFFF)
        r.p.export("VvfpStoryProbeGraphSupplyCap", 0)
        if setup:
            setup(r)
        r.rolls([0] * 400)
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

    def test_a_gain_never_takes_away_above_the_ceiling(self):
        """Food or tech already above the engine's ceiling: a gain changes nothing (never a negative room)."""
        if not have_stock("vv4"):
            self.skipTest("no stock The Tree of Life")
        g = pages([[{"do": "supply", "item": "food", "min": 10, "max": 10},
                    {"do": "supply", "item": "tech", "min": 10, "max": 10}]], [4])
        r, _ = self.run_graph("vv4", g, lambda r: self.set_food_tech(r, 0x7FFFFFFF, 0x7FFFFFFF))
        self.assertEqual(self.food_tech(r), (0x7FFFFFFF, 0x7FFFFFFF))

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

    def test_a_trade_for_a_collectible_that_cannot_come_charges_nothing(self):
        """The Lost Children with 11 of 12 in every set: no piece may come (none may finish a set), so a trade for one
        takes nothing either (Codex P2)."""
        if not have_stock("vv2"):
            self.skipTest("no stock The Lost Children")
        g = pages([[{"do": "trade", "give": "food", "give_amount": 100, "get": "collectible", "get_amount": 1}]], [2])

        def setup(r):
            self.set_food_tech(r, 500, 0)
            w = r.story.village.world
            r.p.write(w + 0x2E720, (b"\1" * 11 + b"\0") * 4)

        r, _ = self.run_graph("vv2", g, setup)
        self.assertEqual(self.food_tech(r)[0], 500)
        self.assertEqual(sum(r.p.read(r.story.village.world + 0x2E720, 48)), 44)
    def test_a_big_collectible_gain_from_an_empty_collection(self):
        """VV3-VV5 with no piece yet: a gain of 50 (above the old 33 / 44 room) gives all 50 (the first new piece, then duplicates), never
        finishing a set (Codex P2)."""
        for game in ("vv3", "vv4", "vv5"):
            if not have_stock(game):
                continue
            with self.subTest(game=game):
                base = COLLECTIBLE_AT[game]
                g = pages([[{"do": "supply", "item": "collectible", "min": 50, "max": 50}]], [int(game[2])])

                def setup(r, base=base):
                    for k in range(48):
                        r.p.put32(base + 4 * k, 0)

                r, _ = self.run_graph(game, g, setup)
                counts = [struct.unpack("<i", r.p.read(base + 4 * k, 4))[0] for k in range(48)]
                self.assertEqual(sum(counts), 50)
                for s in range(0, 48, 12):
                    self.assertLess(sum(1 for c in counts[s:s + 12] if c > 0), 12, "no set is ever finished")
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
                        r.p.mu.hook_add(UC_HOOK_CODE, r.p._on_code, begin=LEVEL_RAISE[game], end=LEVEL_RAISE[game])
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

    def test_construction_never_reaches_the_weather(self):
        """"construction" is words only (the owner's final list): a .cieg that still holds it (old data: here a
        weather effect's word changed to it, the checksum made again) is refused by the game's loader, and nothing --
        no weather -- is started.  The runtime itself (cg_village_fx) acts only on the words the loader allows."""
        import zlib
        for game in ("vv3", "vv4", "vv5"):
            if not have_stock(game):
                continue
            with self.subTest(game=game):
                blob = bytearray(compiled(pages([[{"do": "village", "what": "weather", "weather": "rain"}]],
                                                [int(game[2])])))
                at = bytes(blob).index(b"weather:rain\0")
                blob[at:at + 12] = b"construction"
                struct.pack_into("<I", blob, 12, 0)
                struct.pack_into("<I", blob, 12, zlib.crc32(bytes(blob)))
                r = V6(game, VILLAGE)
                r.record(WEATHER_STARTER[game][0], 8)
                self.assertIsNotNone(r.queue6(bytes(blob)), "refused")
                self.assertEqual(r.recorded.get(WEATHER_STARTER[game][0], []), [], "no weather")
        source = (NATIVE / "story_graph_village.inc").read_text(encoding="utf-8")
        body = source[source.index("static void cg_village_fx("):]
        body = body[:body.index("\n}\n")]
        self.assertIn('cg_prefix(s, "weather:")', body, "the weather only for a weather word")
        self.assertNotIn("} else {", body, "no catch-all branch")

    def test_the_next_island_event_moves(self):
        """Sooner is the Gong of Wonder's luck (VV2 0x44ECE1: now + 60 s); later adds hours but never past now + the
        game's longest gap (23 / 19 / 15 / 15 / 15 h); neither ever goes before now."""
        timers = {"vv1": ("world", 0xA300, 23), "vv2": ("world", 0x2EAE0, 19), "vv3": ("w3", 0x12EF4, 15),
                  "vv4": ("w4", 0x170E0, 15), "vv5": ("w5", 0x17D3C, 15)}
        for game, (kind, off, longest) in timers.items():
            if not have_stock(game):
                continue
            with self.subTest(game=game):
                g = pages([[{"do": "village", "what": "event_timer", "min": -3, "max": -3}],
                           [{"do": "village", "what": "event_timer", "min": 5, "max": 5}],
                           [{"do": "village", "what": "event_timer", "min": 72, "max": 72}],
                           [{"do": "village", "what": "event_timer", "min": -1, "max": -1}]], [int(game[2])])
                seen = []

                def setup(r, kind=kind, off=off, game=game):
                    if game in CLOCK:
                        r.record(CLOCK[game], 0)               # the game's clock: now = 0
                    base = {"world": lambda: r.story.village.world, "w3": lambda: r.world3,
                            "w4": lambda: r.p.u32(0x4CB51C), "w5": lambda: r.p.u32(0x4DACE0)}[kind]()
                    at = base + off
                    r.p.put32(at, 0xF0000000)
                    r.watch = lambda: seen.append(r.p.u32(at))  # noqa: E731

                r, _ = self.run_graph(game, g, setup)
                now = seen[0] - 60
                self.assertEqual(seen, [now + 60, now + 60 + 5 * 3600, now + longest * 3600, now + 60])
                self.assertEqual(r.p.export("VvfpStoryProbeGraphTimerApplied") & 0xFFFFFFFF, 0xFFFFFFFF,
                                 "the last change, for the outcome line: soon")

    def test_the_popup_says_what_was_made(self):
        """The owner (2026-11-18): each change ends the popup with its line and the amount made (after the cap)."""
        timers = {"vv1": ("world", 0xA300), "vv2": ("world", 0x2EAE0), "vv3": ("w3", 0x12EF4),
                  "vv4": ("w4", 0x170E0), "vv5": ("w5", 0x17D3C)}
        for game, (kind, off) in timers.items():
            if not have_stock(game):
                continue
            with self.subTest(game=game):
                # sooner first (a minute from now, whatever the clock), then 5 hours on from there (under the cap)
                g = pages([[{"do": "village", "what": "event_timer", "min": -3, "max": -3}],
                           [{"do": "village", "what": "event_timer", "min": 5, "max": 5}],
                           [{"do": "group", "kind": "cure"}]], [int(game[2])])
                for n in g["nodes"].values():
                    n["auto_text"] = True

                def setup(r, kind=kind, off=off, game=game):
                    if game in CLOCK:
                        r.record(CLOCK[game], 0)
                    base = {"world": lambda: r.story.village.world, "w3": lambda: r.world3,
                            "w4": lambda: r.p.u32(0x4CB51C), "w5": lambda: r.p.u32(0x4DACE0)}[kind]()
                    r.p.put32(base + off, 0xF0000000)

                _r, shown = self.run_graph(game, g, setup)
                text = " ".join(" ".join(t for _kind, t, _labels in shown).split())
                self.assertIn("Page 1. The next island event will come in about a minute.", text)
                self.assertIn("Page 2. The next island event will come 5 hours later.", text)
                self.assertIn("Page 3. Every villager is cured.", text)

# Section 36: the work rush's starters (VV1/VV2: the action routine, its argument count; VV3-VV5: the action ids)
WORK_RUSH = {"vv1": ((0x441E10, 4), (0x439D80, 8)), "vv2": ((0x456F70, 4), (0x44A1E0, 8)),
             "vv3": (0xB, 0x3A), "vv4": (0x63, 0x4F), "vv5": (0x6C, 0x55)}
TEMP_SETTERS = {"vv3": ((0x4583A0, 20),), "vv4": ((0x437EC0, 8), (0x438CA0, 8), (0x460A90, 20))}
# The job ticked on the Details screen (story_graph_village.inc cg_job_ticked): its field, and (Adam, Bea, Cal)'s
# values: Farming, none, Research.
JOB_TICKED = {"vv1": (0x3D0, (1, 0, 3, 0)), "vv2": (0x7F8, (1, 0, 4, 0)), "vv3": (0xEC0, (0, -1, 3, -1)),
              "vv4": (0x1C70, (0, -1, 3, -1)), "vv5": (0x1C74, (0, -1, 3, -1))}
STORY3 = 0x5F                      # The Secret City's "Telling a story (Parenting practice)"
SPAWNER = {"vv3": (0x42D940, 0x58F428, 12), "vv4": (0x413EE0, 0x4CC838, 12), "vv5": (0x4141E0, 0x4DBFC8, 28)}


@emulated
class WorkRushSpawnTempEffects(unittest.TestCase):
    """The owner's 2026-11-18 additions (cie-v6-binary.md 36), in each stock executable."""

    side = None

    def setUp(self):
        self.side = GameSide()

    def test_patcher_side(self):
        fx = [{"do": "group", "kind": "work", "skill": "Farming", "who": "all"},
              {"do": "supply", "item": "yellow_fruit", "min": -50, "max": -50}]
        g = pages([fx], [3, 4])
        g["nodes"]["p0"]["children"] = []
        self.assertEqual(cg.decompile_graph(compiled(g))["nodes"]["p0"]["effects"], fx)
        for games, bad, why in (([4], {"do": "group", "kind": "work", "skill": "Farming", "who": "subject"}, "whole"),
                                ([4], {"do": "group", "kind": "work", "skill": "Juggling"}, "skill"),
                                ([3], {"do": "group", "kind": "effect", "effect": "hiccups"}, "words only"),
                                ([4], {"do": "group", "kind": "effect", "effect": "clean"}, "words only"),
                                ([4], {"do": "group", "kind": "effect", "effect": "gunk"}, "words only"),
                                ([4], {"do": "group", "kind": "effect", "effect": "stew_wait"}, "words only"),
                                ([3], {"do": "supply", "item": "yellow_fruit", "min": 1, "max": 1}, "no game")):
            with self.subTest(bad=bad), self.assertRaises(Exception) as ctx:
                cg.load(pages([[bad]], games), scrolling=True)
            self.assertIn(why, str(ctx.exception))
        # no event ever sets the glow (the owner, 2026-11-18: meditation is words only), so never clean and glow
        with self.assertRaises(Exception) as ctx:
            cg.load(pages([[{"do": "group", "kind": "effect", "effect": "glow", "who": "subject"}]], [4]), scrolling=True)
        self.assertIn("words only", str(ctx.exception))

    def test_work_rush_only_the_skills_workers_work(self):
        """The owner's rule: the rushed job ticked (Adam) works; no job ticked and the rushed skill the highest (Bea)
        works; another job ticked (Cal: Research), even with Farming the highest, rests; no job ticked and no skill
        at all (Dan) rests; the child (Kai) is left as is."""
        people = [(0, "m", 30, "Adam", 10, False), (1, "f", 31, "Bea", 90, False), (2, "m", 40, "Cal", 50, False),
                  (3, "f", 35, "Dan", 0, False), (4, "m", 8, "Kai", 0, False)]
        for game, (work, rest) in WORK_RUSH.items():
            if not have_stock(game):
                continue
            with self.subTest(game=game):
                g = pages([[{"do": "group", "kind": "work", "skill": "Farming"}]], [int(game[2])])
                off, ticked = JOB_TICKED[game]

                def setup(r, game=game, work=work, rest=rest, off=off, ticked=ticked):
                    for i, value in enumerate(ticked):
                        r.p.put32(r.v.record(i) + off, value & 0xFFFFFFFF)
                    if game in DO_ACTION:
                        r.record(DO_ACTION[game], 8)
                    else:
                        r.record(*work)
                        r.record(*rest)

                r, _ = self.side.run_graph(game, g, setup, people=people)
                # Cal and Dan: the job's own starter first (it picks the site; its steps are never run), then the
                # busy state (here the starters are only recorded, so no walk is found and the busy state stays)
                if game in DO_ACTION:
                    started = [(c[0], c[1]) for c in r.recorded.get(DO_ACTION[game], [])]
                    who = [r.v.record(i) for i in range(4)]
                    self.assertEqual(started, [(who[0], work), (who[1], work), (who[2], work), (who[2], rest),
                                               (who[3], work), (who[3], rest)], "Adam and Bea work; Cal and Dan rest")
                else:
                    self.assertEqual([c[1] for c in r.recorded.get(work[0], [])], [0, 1, 2, 3], "Adam and Bea work")
                    self.assertEqual([c[1] for c in r.recorded.get(rest[0], [])], [2, 3], "Cal and Dan rest")

    def test_a_parenting_rush_is_storytelling_or_nothing(self):
        """Birth Control (the owner): a Parenting rush never sends anyone to embrace -- only the game's storytelling
        (The Lost Children, The Secret City); where a game has none, the rush does nothing at all."""
        people = [(0, "m", 30, "Adam", 10, False), (1, "f", 31, "Bea", 10, False)]
        for game in ("vv1", "vv3", "vv4", "vv5"):
            if not have_stock(game):
                continue
            with self.subTest(game=game):
                g = pages([[{"do": "group", "kind": "work", "skill": "Parenting"}]], [int(game[2])])
                off, ticked = JOB_TICKED[game]
                parenting = {"vv1": 2, "vv3": 1, "vv4": 1, "vv5": 1}[game]

                def setup(r, game=game, off=off, parenting=parenting):
                    for i in range(2):
                        r.p.put32(r.v.record(i) + off, parenting)
                    if game in DO_ACTION:
                        r.record(DO_ACTION[game], 8)
                    else:
                        for va, pop in WORK_RUSH[game]:
                            r.record(va, pop)

                r, _ = self.side.run_graph(game, g, setup, people=people)
                if game == "vv3":
                    self.assertEqual(sorted(c[1] for c in r.recorded.get(DO_ACTION[game], [])), [STORY3, STORY3])
                elif game in DO_ACTION:
                    self.assertEqual(r.recorded.get(DO_ACTION[game], []), [], "no storytelling: nothing at all")
                else:
                    self.assertFalse(any(r.recorded.get(va) for va, _pop in WORK_RUSH[game]))
    def test_yellow_fruit_through_the_fruit_supply_companion(self):
        if not have_stock("vv4"):
            self.skipTest("no stock The Tree of Life")
        g = pages([[{"do": "supply", "item": "yellow_fruit", "min": 950, "max": 950}],
                   [{"do": "trade", "give": "yellow_fruit", "give_amount": 300, "get": "food", "get_amount": 50}],
                   [{"do": "supply", "item": "yellow_fruit", "min": -9999, "max": -9999}]], [4])
        r, _ = self.side.run_graph("vv4", g, lambda r: (r.p.export("VvfpStoryProbeGraphYellowFruit", 100),
                                                        self.side.set_food_tech(r, 0, 0)))
        self.assertEqual(r.p.export("VvfpStoryProbeGraphYellowFruit", -2), 0, "1000, then 700, then never below 0")
        self.assertEqual(self.side.food_tech(r)[0], 50)
        r, _ = self.side.run_graph("vv4", g, lambda r: (r.p.export("VvfpStoryProbeGraphYellowFruit", -1),
                                                        self.side.set_food_tech(r, 0, 0)))
        self.assertEqual(self.side.food_tech(r)[0], 0, "no Yellow Fruit Trees limited: no count, no trade")
        r.p.export("VvfpStoryProbeGraphYellowFruit", -2)


EVENT_DIRS = [ROOT / "data" / "event_collection" / "drafts_c" / d for d in ("dr_trd", "dr_vfx")]


@emulated
class NewEventsRunInEveryGame(unittest.TestCase):
    """Every trader and Village Moments event, every choice, in each of its games, through the engine; a trader's
    Trade gives exactly what it says when the goods are food or tech (cie-v6-binary.md 33)."""

    def test_every_event_every_choice(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        import collection_check as cc
        import json
        paths = sorted(p for d in EVENT_DIRS for p in d.glob("*.json"))
        self.assertEqual(len(paths), 29)
        side = GameSide()
        ran = 0
        for path in paths:
            graph = cc.graph_for_engine(json.loads(path.read_text(encoding="utf-8")))
            setup_id = "setup"
            choices = len(graph["nodes"][setup_id].get("choices", [])) or 1
            for gn in graph["games"]:
                game = f"vv{gn}"
                if not have_stock(game):
                    continue
                g = graph
                for choice in range(choices):
                    with self.subTest(event=path.stem, game=game, choice=choice):
                        def setup(r, gn=gn, game=game):
                            side.set_food_tech(r, 5000, 5000)
                            r.p.export("VvfpStoryProbeGraphGoods", 1)
                            r.p.export("VvfpStoryProbeGraphScroll", 1)   # the collection's rows need Scrolling Popups
                            # the game's own weather starter and level raise, recorded (their own tests above)
                            if game in WEATHER_STARTER:
                                r.record(WEATHER_STARTER[game][0], 8)
                            if game in LEVEL_RAISE:
                                r.record(LEVEL_RAISE[game], 8 if game == "vv5" else 4)
                            if game in CLOCK:
                                r.record(CLOCK[game], 0)           # the game's clock (now = 0)
                            if game in SPAWNER:                   # the game's own spawner and effect setters
                                r.record(SPAWNER[game][0], SPAWNER[game][2])
                            for va, pop in TEMP_SETTERS.get(game, ()):
                                r.record(va, pop)
                            if game == "vv3":
                                r.p.put32(0x594844, 3)                # three fruit trees planted
                            if gn == 4:
                                for at in (0x4D8618, 0x4D8D98, 0x4D8ACC):
                                    r.p.put32(at, 5)
                        r, shown = side.run_graph(game, g, setup, answers=[choice])
                        r.p.export("VvfpStoryProbeGraphGoods", -1)
                        self.assertTrue(shown)
                        o1 = graph["nodes"]["o1"].get("effects", []) if choice == 0 else []
                        for e in o1:
                            if e["do"] == "trade" and e["give"] in ("food", "tech"):
                                food, tech = side.food_tech(r)
                                left = food if e["give"] == "food" else tech
                                self.assertEqual(left, 5000 - e["give_amount"])
                        ran += 1
        self.assertGreater(ran, 100)


if __name__ == "__main__":
    unittest.main()
