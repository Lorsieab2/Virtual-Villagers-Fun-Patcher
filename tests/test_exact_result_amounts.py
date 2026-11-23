"""Every island event result line states the EXACT amount the game really makes (the owner, 2026-11-19), in all five
games, through "VVFP Story Upgrades.dll" (its test build) in each stock executable in the emulator.

- A gain and a loss of food, tech points, a skill and health each say the amount made, after the game's limits: a
  village with 20 food that is to lose 40 is told it loses 20 (and loses 20); a skill at 95 that is to gain 10 is told
  it gains 5 (and reaches 100); a change that changes nothing has no line at all.
- One tech point is "1 tech point".
- Applied = shown: the page states the amount counted when it was laid out, and exactly that is made.  When the village
  moves between the layout and the showing (here: food eaten after the first page), the page's line is put right
  before it is shown, so the words and the store never disagree.
- A group's skill change says how many it changed and by how much (a range when they differ).
- A damage with nothing finished to damage says nothing.
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
    from test_story_cie_graph_runtime_v6 import FARMING
    import test_traders_and_village_effects as _traders   # its runner (imported as a module: never collected twice)

GAME_IDS = ("vv1", "vv2", "vv3", "vv4", "vv5")
NATIVE = ROOT / "native" / "vvfp_story_upgrades"


def pages(effects_per_page: list[list[dict]], game: str) -> dict:
    """One page per list of effects, each with its automatic lines."""
    nodes = {}
    for k, fx in enumerate(effects_per_page):
        nodes[f"p{k}"] = {"text": f"Page {k + 1}.", "effects": fx, "auto_text": True}
        if k + 1 < len(effects_per_page):
            nodes[f"p{k}"]["children"] = [{"next": f"p{k + 1}"}]
    return {"format": "vvfp-cie-graph", "version": 6, "title": "Exact Amounts", "games": [int(game[2])],
            "roles": {"subject": {"kind": "villager", "min_age": 14}}, "start": "p0", "nodes": nodes}


def award_graph(game: int) -> dict:
    """A page paying an award its own words state ("(award)"), then one paying an award they do not."""
    fx = [{"do": "food", "amount": 150, "defer": True}, {"do": "pay_award"}]
    return {"format": "vvfp-cie-graph", "version": 6, "title": "Exact Amounts", "games": [game],
            "roles": {"subject": {"kind": "villager", "min_age": 14}}, "start": "p0",
            "nodes": {"p0": {"text": "(Subject) wins the contest. Your village gains (award) food.",
                             "effects": copy.deepcopy(fx), "auto_text": True, "children": [{"next": "p1"}]},
                      "p1": {"text": "A second prize.", "effects": copy.deepcopy(fx), "auto_text": True}}}


def one_line(shown) -> str:
    return " ".join(" ".join(t for _kind, t, _labels in shown).split())


class PatcherSide(unittest.TestCase):
    def test_the_lines_are_the_engines(self):
        """The new lines are pinned equal to the engine's table, in its order (their translation keys)."""
        native = (NATIVE / "story_graph.inc").read_text(encoding="utf-8")
        table = native[native.index("CG_AUTO_LINES[][2] = {"):]
        table = table[:table.index("\n};")]
        import re
        pairs = re.findall(r'\{ "([^"]+)", "((?:[^"\\]|\\.)*)" \}', table)
        self.assertEqual(pairs, list(cg.AUTO_LINES.items()))
        self.assertEqual(cg.AUTO_LINES["faith"], "<R>'s Faith rises by <N>.")

    def test_one_tech_point(self):
        self.assertEqual(cg.auto_line_options({"do": "tech", "amount": 1}, 3, None, [1, 0]),
                         ["The village gains 1 tech point."])
        self.assertEqual(cg.auto_line_options({"do": "tech", "amount": -1}, 3, None, [-1, 0]),
                         ["The village loses 1 tech point."])
        self.assertEqual(cg.auto_line_options({"do": "tech", "amount": 2}, 3, None, [2, 0]),
                         ["The village gains 2 tech points."])
        self.assertEqual(cg.good_words("cutting_tools", 1), "cutting tool")
        self.assertEqual(cg.good_words("collectible", 3), "collectibles")

    def test_an_award_the_text_states_is_said_once(self):
        """The Cooking Contest (v1.35.97, live): "...Your village gains 590 food.\\nThe village gains 590 food." --
        the author's "(award)" and the pay_award's automatic line said the same gain twice.  The text keeps its words;
        the automatic line goes, and only on a node whose own words say "(award)"."""
        self.assertTrue(cg.says_award("Your village gains (award) food."))
        self.assertTrue(cg.says_award("(Award) food is theirs."))
        self.assertFalse(cg.says_award("The (award_unit) are counted."))
        self.assertFalse(cg.says_award(""))
        for game in (1, 2, 3, 4, 5):
            with self.subTest(game=game):
                out = cg.simulate(cg.load(copy.deepcopy(award_graph(game))), game, [0] * 8,
                                  {"subject": cg.Binding("Adam", "m")})
                text = " ".join(out["popups"])
                self.assertEqual(text.count("150 food"), 2, text)
                self.assertIn("Your village gains 150 food.", text)
                self.assertNotIn("Your village gains 150 food.\nThe village gains 150 food.", text)
                self.assertIn("A second prize.\nThe village gains 150 food.", text, "no (award): the line stays")

    def test_a_restore_gives_back_a_share_of_the_loss(self):
        """cie-v6-binary.md 25a (the owner, 2026-11-22): "Lose health, then restore some" -- the gain is a percent of
        what the loss took, so it is always smaller.  It validates, round-trips the compiled file (flags bit 0) and its
        line states the share given back."""
        fx = [{"do": "health_change", "min": -20, "max": -20},
              {"do": "health_change", "restore": True, "min": 25, "max": 75}]
        g = cg.load(copy.deepcopy(pages([fx], "vv2")))
        self.assertEqual(g["nodes"]["p0"]["effects"][1]["restore"], True)
        back = cg.decompile_graph(cg.compile_graph(g))
        self.assertEqual(back["nodes"]["p0"]["effects"][1].get("restore"), True)
        self.assertEqual((back["nodes"]["p0"]["effects"][1]["min"], back["nodes"]["p0"]["effects"][1]["max"]), (25, 75))
        self.assertEqual(cg.restored(20, 25), 5)
        self.assertEqual(cg.restored(20, 75), 15)
        self.assertEqual(cg.restored(0, 75), 0)
        # the fixed loss takes no roll; the percent's roll 0 is 25, 50 is 75
        for roll, back_n in ((0, 5), (50, 15)):
            out = cg.simulate(g, 2, [roll] + [0] * 7, {"subject": cg.Binding("Adam", "m")})
            text = " ".join(out["popups"])
            self.assertIn("Adam loses 20 health.", text)
            self.assertIn(f"Adam gains {back_n} health.", text)
        for bad in ({"do": "health_change", "restore": True, "min": 0, "max": 50},
                    {"do": "health_change", "restore": True, "min": 25, "max": 101},
                    {"do": "health_change", "restore": True, "min": 25, "max": 75, "target": {"all": True}}):
            with self.subTest(bad=bad):
                _g, problems = cg.validate(copy.deepcopy(pages([[bad]], "vv2")))
                self.assertTrue(any("restore" in p for p in problems), problems)

    def test_the_hospitals_patient_always_ends_worse_off(self):
        """vv2_hospitals_most_difficult B2: the loss (10-20), then 25-75% of it back -- never the whole of it."""
        import json
        doc = json.loads((ROOT / "data" / "event_collection" / "exclusive" / "vv2_hospitals_most_difficult.json")
                         .read_text(encoding="utf-8"))
        loss, back = doc["nodes"]["b2"]["effects"]
        self.assertEqual((loss["do"], loss["min"], loss["max"]), ("health_change", -20, -10))
        self.assertEqual((back["do"], back.get("restore"), back["min"], back["max"]), ("health_change", True, 25, 75))
        for lost in range(10, 21):
            for pct in range(25, 76):
                self.assertLess(cg.restored(lost, pct), lost)
                self.assertGreater(cg.restored(lost, pct), 0)

    def test_a_groups_line_is_counted_for_the_fit(self):
        e = {"do": "skill", "skills": ["Farming"], "min": 5, "max": 5, "target": {"all": True}}
        self.assertEqual(cg.auto_line_options(e, 3), ["256 villagers gain 100 to 5 Farming skill."])
        self.assertEqual(cg.auto_line_options(e, 3, None, [0, 5]), [], "written as it is made")


@emulated
class GameSideAmounts(unittest.TestCase):
    side = None

    def setUp(self):
        self.side = _traders.GameSide()

    def run_graph(self, game, graph, setup=None, people=None):
        people = people or [(0, "m", 30, "Adam", 0, False), (1, "f", 8, "Kia", 0, False)]
        return self.side.run_graph(game, graph, setup, people=people)

    def games(self):
        for game in GAME_IDS:
            if have_stock(game):
                yield game

    def test_food_and_tech_gain_loss_clamp_and_no_change(self):
        for game in self.games():
            cases = (  # food, tech at the start; the effects; lines wanted; lines refused; food, tech after
                (500, 10, [{"do": "food", "amount": 150}, {"do": "tech", "amount": -4}],
                 ["The village gains 150 food.", "The village loses 4 tech points."], [], (650, 6)),
                (20, 0, [{"do": "food", "amount": -40}, {"do": "tech", "amount": 1}],
                 ["The village loses 20 food.", "The village gains 1 tech point."],
                 ["loses 40 food", "1 tech points"], (0, 1)),
                (0, 1, [{"do": "food", "amount": -40}, {"do": "tech", "amount": -1}],
                 ["The village loses 1 tech point."], ["loses 0", "food."], (0, 0)),
            )
            for food, tech, fx, want, never, after in cases:
                with self.subTest(game=game, food=food, tech=tech):
                    r, shown = self.run_graph(game, pages([fx], game),
                                              lambda r, f=food, t=tech: self.side.set_food_tech(r, f, t))
                    text = one_line(shown)
                    for line in want:
                        self.assertIn(line, text)
                    for bit in never:
                        self.assertNotIn(bit, text)
                    self.assertEqual(self.side.food_tech(r), after, "applied = shown")

    def test_the_village_moving_between_layout_and_showing(self):
        """The pages are laid out when the event starts (food 100: page 2 is to lose 40); food is eaten after page 1
        is shown (15 left); page 2 then loses the 15 and says so -- never the 40 it was laid out with."""
        for game in self.games():
            with self.subTest(game=game):
                g = pages([[{"do": "tech", "amount": 3}], [{"do": "food", "amount": -40}]], game)

                def setup(r):
                    self.side.set_food_tech(r, 100, 0)
                    state = {"n": 0}

                    def watch():
                        state["n"] += 1
                        if state["n"] == 1:
                            self.side.set_food_tech(r, 15, self.side.food_tech(r)[1])
                    r.watch = watch

                r, shown = self.run_graph(game, g, setup)
                self.assertIn("Page 2. The village loses 15 food.", one_line(shown))
                self.assertNotIn("loses 40 food", one_line(shown))
                self.assertEqual(self.side.food_tech(r), (0, 3))

    def test_an_award_the_text_states_is_said_once(self):
        """The engine: the page whose words say "(award)" states the gain once (its own words, the amount paid); a
        page whose words do not still has the automatic line.  Both awards are paid."""
        for game in self.games():
            with self.subTest(game=game):
                r, shown = self.run_graph(game, award_graph(int(game[2])),
                                          lambda r: self.side.set_food_tech(r, 500, 0))
                text = "\n".join(t for _kind, t, _labels in shown)
                flat = one_line(shown)
                self.assertIn("Your village gains 150 food.", flat)
                self.assertEqual(flat.count("150 food"), 2, text)
                self.assertIn("A second prize. The village gains 150 food.", flat, "no (award): the line stays")
                self.assertEqual(self.side.food_tech(r), (800, 0), "both awards paid")

    def test_skill_gain_loss_and_cap(self):
        for game in self.games():
            for start, change, line, end in ((50, 10, "Adam gains 10 Farming skill.", 60),
                                             (95, 10, "Adam gains 5 Farming skill.", 100),
                                             (3, -10, "Adam loses 3 Farming skill.", 0),
                                             (40, -10, "Adam loses 10 Farming skill.", 30),
                                             (100, 10, None, 100)):
                with self.subTest(game=game, start=start, change=change):
                    people = [(0, "m", 30, "Adam", start, False), (1, "f", 8, "Kia", 0, False)]
                    g = pages([[{"do": "skill", "skills": ["Farming"], "min": change, "max": change}]], game)
                    r, shown = self.run_graph(game, g, people=people)
                    text = one_line(shown)
                    if line is None:
                        self.assertNotIn("Farming skill", text, "nothing changed: no line")
                    else:
                        self.assertIn(line, text)
                    self.assertEqual(int(r.v.skill(0, FARMING[game])), end, "applied = shown")

    def test_health_gain_loss_and_cap(self):
        for game in self.games():
            for start, change, line, end in ((50, 20, "Adam gains 20 health.", 70),
                                             (95, 20, "Adam gains 5 health.", 100),
                                             (50, -20, "Adam loses 20 health.", 30),
                                             (5, -20, "Adam loses 4 health.", 1),
                                             (100, 20, None, 100)):
                with self.subTest(game=game, start=start, change=change):
                    g = pages([[{"do": "health_change", "min": change, "max": change}]], game)

                    def setup(r, start=start):
                        r.p.put32(r.v.record(0) + r.v.L["health"], start)

                    r, shown = self.run_graph(game, g, setup)
                    text = one_line(shown)
                    if line is None:
                        self.assertNotIn("health.", text, "nothing changed: no line")
                    else:
                        self.assertIn(line, text)
                    self.assertEqual(r.v.i32(0, r.v.L["health"]), end, "applied = shown")

    def test_a_restore_gives_back_a_share_of_what_was_really_lost(self):
        """25a in the engine: 50% of the loss as it was really made (after the clamp at 1) -- the line says it, and the
        villager ends below the start."""
        fx = [{"do": "health_change", "min": -20, "max": -20},
              {"do": "health_change", "restore": True, "min": 50, "max": 50}]
        for game in self.games():
            for start, lost_line, back_line, end in ((60, "Adam loses 20 health.", "Adam gains 10 health.", 50),
                                                     (9, "Adam loses 8 health.", "Adam gains 4 health.", 5)):
                with self.subTest(game=game, start=start):
                    def setup(r, start=start):
                        r.p.put32(r.v.record(0) + r.v.L["health"], start)

                    r, shown = self.run_graph(game, pages([copy.deepcopy(fx)], game), setup)
                    text = one_line(shown)
                    self.assertIn(lost_line, text)
                    self.assertIn(back_line, text)
                    self.assertEqual(r.v.i32(0, r.v.L["health"]), end, "applied = shown, below the start")

    def test_a_restore_follows_the_loss_when_health_moves_after_layout(self):
        """25a (Codex, #840): laid out at 60 (lose 20, restore 50%: back 10); the villager is down to 9 when the page
        is shown, so the loss really takes 8 -- the restore gives back 4 of THAT, never the 10 it was laid out with,
        the line says so, and the villager ends below where the page began."""
        fx = [{"do": "health_change", "min": -20, "max": -20},
              {"do": "health_change", "restore": True, "min": 50, "max": 50}]
        for game in self.games():
            with self.subTest(game=game):
                g = pages([[{"do": "tech", "amount": 3}], copy.deepcopy(fx)], game)

                def setup(r):
                    r.p.put32(r.v.record(0) + r.v.L["health"], 60)
                    state = {"n": 0}

                    def watch():
                        state["n"] += 1
                        if state["n"] == 1:
                            r.p.put32(r.v.record(0) + r.v.L["health"], 9)
                    r.watch = watch

                r, shown = self.run_graph(game, g, setup)
                text = one_line(shown)
                self.assertIn("Adam loses 8 health.", text)
                self.assertIn("Adam gains 4 health.", text)
                self.assertNotIn("gains 10 health", text)
                self.assertEqual(r.v.i32(0, r.v.L["health"]), 5, "a share of the real loss: below the 9")

    def test_a_restore_follows_its_own_villagers_loss(self):
        """25a (Codex, #840): the subject loses 20, the friend loses 10, then the subject gets 50% back -- 10, a share
        of the subject's own loss, not of the friend's loss that came between."""
        fx = [{"do": "health_change", "role": "subject", "min": -20, "max": -20},
              {"do": "health_change", "role": "friend", "min": -10, "max": -10},
              {"do": "health_change", "role": "subject", "restore": True, "min": 50, "max": 50}]
        people = [(0, "m", 30, "Adam", 0, False), (1, "f", 31, "Bea", 0, False)]
        for game in self.games():
            with self.subTest(game=game):
                g = pages([copy.deepcopy(fx)], game)
                g["roles"]["friend"] = {"kind": "villager", "min_age": 14}

                def setup(r):
                    for i in (0, 1):
                        r.p.put32(r.v.record(i) + r.v.L["health"], 60)

                r, shown = self.run_graph(game, g, setup, people=people)
                text = one_line(shown)
                self.assertIn(" loses 20 health.", text)
                self.assertIn(" loses 10 health.", text)
                self.assertIn(" gains 10 health.", text)
                self.assertEqual(sorted(r.v.i32(i, r.v.L["health"]) for i in (0, 1)), [50, 50],
                                 "the subject 60 - 20 + 10, the friend 60 - 10")

    def test_a_groups_skill_line(self):
        for game in self.games():
            with self.subTest(game=game):
                people = [(0, "m", 30, "Adam", 10, False), (1, "f", 31, "Bea", 98, False),
                          (2, "m", 40, "Cal", 100, False)]
                g = pages([[{"do": "skill", "skills": ["Farming"], "min": 5, "max": 5, "target": {"all": True}}],
                           [{"do": "skill", "skills": ["Farming"], "min": 5, "max": 5, "target": {"all": True}}]],
                          game)
                r, shown = self.run_graph(game, g, people=people)
                text = one_line(shown)
                self.assertIn("Page 1. 2 villagers gain 2 to 5 Farming skill.", text, "Cal at 100: unchanged")
                self.assertIn("Page 2. Adam gains 5 Farming skill.", text, "only Adam had room")
                self.assertEqual([int(r.v.skill(i, FARMING[game])) for i in range(3)], [20, 100, 100])

    def test_a_damage_with_nothing_to_damage_says_nothing(self):
        for game in self.games():
            for structures, told in ((0, False), (0x3, True)):
                with self.subTest(game=game, structures=structures):
                    g = pages([[{"do": "damage", "structures": "any", "min": 40, "max": 40}]], game)
                    r, shown = self.run_graph(game, g, lambda r, s=structures: r.facts(structures=s))
                    # (A New Home and The Lost Children's font has no "%": "40 percent")
                    self.assertEqual("A building loses 40" in one_line(shown), told)
                    self.assertEqual(any(r.damaged()), told)


if __name__ == "__main__":
    unittest.main()
