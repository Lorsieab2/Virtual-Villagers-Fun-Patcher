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


def two_kinds_graph(game: int, extra: list[dict] | None = None) -> dict:
    """The owner (2026-11-22): a page that tells two kinds -- its own food loss in "(award2)", the tech award in
    "(award)" -- then a page with a food and a tech change of its own that it does not state (both lines stay).  `extra`: more effects on the first page."""
    first = [{"do": "food", "amount": -40}, {"do": "tech", "amount": 7, "defer": True}, {"do": "pay_award"}]
    return {"format": "vvfp-cie-graph", "version": 6, "title": "Exact Amounts", "games": [game],
            "roles": {"subject": {"kind": "villager", "min_age": 14}}, "start": "p0",
            "nodes": {"p0": {"text": "(Subject) dries the yams. Your village loses (award2) food. Your villagers gain "
                                     "(award) tech points.",
                             "effects": first + (extra or []), "auto_text": True, "children": [{"next": "p1"}]},
                      "p1": {"text": "A second page.", "effects": [{"do": "food", "amount": 25},
                                                                   {"do": "tech", "amount": 3}],
                             "auto_text": True}}}


def two_awards_graph(game: int) -> dict:
    """One run that defers two different awards: each page's (award) / (award_unit) is the award as it stands there
    (the engine's per-node fill), never the run's last."""
    return {"format": "vvfp-cie-graph", "version": 6, "title": "Exact Amounts", "games": [game],
            "roles": {"subject": {"kind": "villager", "min_age": 14}}, "start": "p0",
            "nodes": {"p0": {"text": "First prize: (award) (award_unit).",
                             "effects": [{"do": "food", "amount": 150, "defer": True}, {"do": "pay_award"}],
                             "children": [{"next": "p1"}]},
                      "p1": {"text": "Second prize: (award) (AWARD_UNIT).",
                             "effects": [{"do": "tech", "amount": 9, "defer": True}, {"do": "pay_award"}]}}}


def count_awards_graph(game: int) -> dict:
    """Codex (#842): (award2) and (award) inside a count token's options are filled with the rest of the node's
    words, never shown as "(award2)"."""
    return {"format": "vvfp-cie-graph", "version": 6, "title": "Exact Amounts", "games": [game],
            "roles": {"subject": {"kind": "villager", "min_age": 14}}, "start": "p0",
            "nodes": {"p0": {"text": "The cooks share {#made:(award2) food|(award2) food each}. Prize: "
                                     "{#made:(award) (award_unit)|(award) (award_unit) each}.",
                             "effects": [{"do": "food", "amount": 25}, {"do": "tech", "amount": 7, "defer": True},
                                         {"do": "pay_award"}], "auto_text": True}}}


def moving_graph(game: int, award: bool) -> dict:
    """Page 1, then a page whose words state its amounts: (award2) a food loss and (award) a tech award, or (`award`)
    the award alone."""
    if award:
        text, fx = "Your villagers gain (award) tech points.", [{"do": "tech", "amount": 7, "defer": True},
                                                                {"do": "pay_award"}]
    else:
        text = "Your village loses (award2) food. Your villagers gain (award) tech points."
        fx = [{"do": "food", "amount": -40}, {"do": "tech", "amount": 7, "defer": True}, {"do": "pay_award"}]
    return {"format": "vvfp-cie-graph", "version": 6, "title": "Exact Amounts", "games": [game],
            "roles": {"subject": {"kind": "villager", "min_age": 14}}, "start": "p0",
            "nodes": {"p0": {"text": "Page 1.", "effects": [{"do": "tech", "amount": 3}], "auto_text": True,
                             "children": [{"next": "p1"}]},
                      "p1": {"text": text, "effects": fx, "auto_text": True}}}


# The three nodes that tell two kinds (the owner's decision, 2026-11-22): event file, node, the award's kind.
TWO_KIND_EVENTS = (("s061_soft_yams", "c2o1", "tech"), ("s064_stranger_recipe", "c2o1", "tech"),
                   ("s095_lucky_harvest", "c2o2", "food"))


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

    def test_award2_states_the_nodes_own_change(self):
        """The owner (2026-11-22): "Your village loses (award) food. Your villagers gain (award) tech points." filled
        both with the tech award's amount and added "The village loses M food.".  (award2) is the node's own food /
        tech change: each kind shows its own amount, once; every other effect's line stays."""
        self.assertTrue(cg.says_award2("Your village loses (award2) food."))
        self.assertTrue(cg.says_award2("(AWARD2) food."))
        self.assertFalse(cg.says_award2("Your village gains (award) food."))
        self.assertFalse(cg.says_award("Your village loses (award2) food."), "(award2) is not (award)")
        self.assertEqual(cg.award2_effect([{"do": "tech", "defer": True}, {"do": "mood"}, {"do": "food"},
                                           {"do": "tech"}]), 2)
        self.assertIsNone(cg.award2_effect([{"do": "tech", "defer": True}, {"do": "pay_award"}]))
        sick = [{"do": "sick", "role": "subject"}]
        for game in (1, 2, 3, 4, 5):
            with self.subTest(game=game):
                out = cg.simulate(cg.load(copy.deepcopy(two_kinds_graph(game, sick))), game, [0] * 8,
                                  {"subject": cg.Binding("Adam", "m")})
                text = "\n".join(out["popups"])
                self.assertIn("Your village loses 40 food. Your villagers gain 7 tech points.", text)
                self.assertEqual(text.count("40 food"), 1, text)
                self.assertEqual(text.count("7 tech points"), 1, text)
                self.assertIn("Adam becomes sick.", text, "every other effect's line stays")
                self.assertIn("A second page.\nThe village gains 25 food.\nThe village gains 3 tech points.", text,
                              "no (award) / (award2): both lines stay")
                self.assertEqual(out["fx"][0][0], -40, "the food loss is still made")

    def test_two_awards_in_one_run_each_as_it_stands(self):
        """A fix along the way (2026-11-22): simulate filled every (award) of a run with the LAST award deferred, so
        a first page paying 150 food read "9 tech points"; the engine fills each node's text as its own effects
        leave the award (cg_group).  Now the mirror does too."""
        for game in (1, 2, 3, 4, 5):
            with self.subTest(game=game):
                out = cg.simulate(cg.load(copy.deepcopy(two_awards_graph(game))), game, [0] * 8,
                                  {"subject": cg.Binding("Adam", "m")})
                text = "\n".join(out["popups"])
                self.assertIn("First prize: 150 food.", text)
                self.assertIn("Second prize: 9 TECH POINTS.", text)
        self.assertEqual(cg.fill_award("(award) (Award_unit) \\(award\\)", None), "  \\(award\\)")

    def test_award_placeholders_in_count_options(self):
        for game in (1, 2, 3, 4, 5):
            with self.subTest(game=game):
                out = cg.simulate(cg.load(copy.deepcopy(count_awards_graph(game))), game, [0] * 8,
                                  {"subject": cg.Binding("Adam", "m")})
                text = "\n".join(out["popups"])
                self.assertIn("The cooks share 25 food. Prize: 7 tech points.", text)
                self.assertNotIn("(award", text.lower())
                self.assertNotIn("The village gains 25 food", text, "(award2) states it")

    def test_award2_is_checked_and_measured(self):
        g = two_kinds_graph(3)
        g["nodes"]["p0"]["effects"] = [{"do": "tech", "amount": 7, "defer": True}, {"do": "pay_award"}]
        with self.assertRaises(cg.GraphError) as caught:
            cg.load(g)
        self.assertIn("no food or tech change of its own", str(caught.exception))
        g = two_kinds_graph(3)
        g["nodes"]["q"] = {"type": "question", "text": "Which?", "choices": [
            {"label": "Take (award2)", "next": "p0"}, {"label": "Leave", "next": "p1"}]}
        g["start"] = "q"
        with self.assertRaises(cg.GraphError) as caught:
            cg.load(g)
        self.assertIn("is not a placeholder a label can show", str(caught.exception))
        lg = cg.lower(cg.load(two_kinds_graph(3)))
        self.assertEqual(cg.worst_v6("Loses (award2) food.", lg, cg.GAMES[3], None, award2=4), "Loses 9999 food.")
        self.assertEqual(cg.award2_width({"do": "food", "amount": -40}, cg.GAMES[3]), 2)

    def test_the_three_two_kind_events(self):
        """s061 The Soft Yams, s064 The Stranger's Recipe, s095 The Lucky Harvest: the node's second "(award)" (the
        other kind's) is "(award2)"; in every game each kind shows its own amount and no automatic line repeats it."""
        import json
        sys.path.insert(0, str(ROOT / "scripts"))
        from collection_check import graph_for_engine
        import build_event_collection_features as build
        pools = build.shared_pools(build.DATA)
        for ident, nid, kind in TWO_KIND_EVENTS:
            path = build.DATA / "rewrites" / "rw_s" / f"{ident}.json"
            g, problems = cg.validate(graph_for_engine(json.loads(path.read_text(encoding="utf-8"))),
                                      scrolling=True, shared_pools=pools)
            self.assertEqual(problems, [], ident)
            text = g["nodes"][nid]["text"]
            self.assertEqual((text.count("(award)"), text.count("(award2)")), (1, 1), ident)
            other = "food" if kind == "tech" else "tech"
            self.assertEqual(g["nodes"][nid]["effects"][cg.award2_effect(g["nodes"][nid]["effects"])]["do"], other)
            for game in (1, 2, 3, 4, 5):
                with self.subTest(event=ident, game=game):
                    out = self._reach(g, game, nid)
                    shown = "\n".join(out["popups"])
                    k = out["nodes"].index(nid)
                    before = sum(len(g["nodes"][n]["effects"]) for n in out["nodes"][:k]
                                 if g["nodes"][n]["type"] != "question")
                    effects = g["nodes"][nid]["effects"]
                    rolls = out["fx"][before:before + len(effects)]
                    award = next(r[0] for e, r in zip(effects, rolls) if e.get("defer"))
                    own = abs(next(r[0] for e, r in zip(effects, rolls) if e["do"] == other and not e.get("defer")))
                    unit = {"food": "food", "tech": "tech points"}
                    said = f"{award} {unit[kind]}", f"{own} {unit[other]}"
                    self.assertTrue(all(s in shown for s in said), shown)
                    for s in said:
                        self.assertNotIn(f"The village gains {s}", shown)
                        self.assertNotIn(f"The village loses {s}", shown)
                    if award != own:
                        self.assertNotIn(f"{award} {unit[other]}", shown, "never the award's amount for the other")

    @staticmethod
    def _reach(g: dict, game: int, nid: str) -> dict:
        """A simulated run through node `nid` (the first of a fixed list of streams and answers that reaches it)."""
        binds = {r: cg.Binding("Adam", "m") for r, v in g["roles"].items() if v["kind"] == "villager"}
        for seed in range(400):
            rolls = [(seed * 7919 + k * 104729) % 100000 for k in range(64)]
            for answers in ([0], [1], [2], [0, 0], [1, 0], [0, 1], [1, 1]):
                try:
                    out = cg.simulate(g, game, rolls, binds, answers)
                except (IndexError, ValueError):
                    continue
                if nid in out["nodes"]:
                    return out
        raise AssertionError(f"no run reaches {nid}")

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

    def test_award2_states_the_nodes_own_change(self):
        """The engine (the owner, 2026-11-22): a page that tells two kinds shows each its own amount -- the food loss
        in (award2) as it is really made, the tech award in (award) -- once each, with no automatic line repeating
        either; a page that states neither keeps both lines.  Everything is made: the loss, both awards, the gain."""
        for game in self.games():
            for food, said, after in ((500, 40, 485), (20, 20, 25)):
                with self.subTest(game=game, food=food):
                    r, shown = self.run_graph(game, two_kinds_graph(int(game[2])),
                                              lambda r, f=food: self.side.set_food_tech(r, f, 10))
                    text = "\n".join(t for _kind, t, _labels in shown)
                    flat = one_line(shown)
                    self.assertIn(f"Your village loses {said} food. Your villagers gain 7 tech points.", flat)
                    self.assertEqual(flat.count(f"{said} food"), 1, text)
                    self.assertEqual(flat.count("7 tech points"), 1, text)
                    self.assertNotIn("loses 7", flat)
                    self.assertIn("A second page. The village gains 25 food. The village gains 3 tech points.", flat,
                                  "no (award) / (award2): both lines stay")
                    self.assertEqual(self.side.food_tech(r), (after, 20), "all four changes made")

    def test_two_awards_in_one_run_each_as_it_stands(self):
        """The engine (what the Python mirror now copies): each page's (award) is the award as it stands there."""
        for game in self.games():
            with self.subTest(game=game):
                r, shown = self.run_graph(game, two_awards_graph(int(game[2])),
                                          lambda r: self.side.set_food_tech(r, 500, 10))
                flat = one_line(shown)
                self.assertIn("First prize: 150 food.", flat)
                self.assertIn("Second prize: 9 TECH POINTS.", flat)
                self.assertEqual(self.side.food_tech(r), (650, 19), "both awards paid")

    def test_award_placeholders_in_count_options(self):
        """Codex (#842): a count option's (award2) / (award) was shown as written; now filled like the rest."""
        for game in self.games():
            with self.subTest(game=game):
                r, shown = self.run_graph(game, count_awards_graph(int(game[2])),
                                          lambda r: self.side.set_food_tech(r, 500, 10))
                flat = one_line(shown)
                self.assertIn("The cooks share 25 food", flat)          # either option (the count kept from earlier)
                self.assertIn("Prize: 7 tech points", flat)
                self.assertNotIn("(award", flat.lower())
                self.assertNotIn("The village gains 25 food", flat)
                self.assertEqual(self.side.food_tech(r), (525, 20))

    def _moving(self, game, graph, food, tech, then):
        def setup(r):
            self.side.set_food_tech(r, food, tech)
            state = {"n": 0}

            def watch():
                state["n"] += 1
                if state["n"] == 1:
                    then(r)
            r.watch = watch
        return self.run_graph(game, graph, setup)

    def test_award2_put_right_when_the_village_moves(self):
        """Codex (#842): laid out with 100 food (the page to lose 40), 15 left once page 1 is shown: the page's own
        words say 15 -- never the 40 it was laid out with -- and no extra line contradicts them."""
        for game in self.games():
            with self.subTest(game=game):
                r, shown = self._moving(game, moving_graph(int(game[2]), False), 100, 0,
                                        lambda r: self.side.set_food_tech(r, 15, self.side.food_tech(r)[1]))
                flat = one_line(shown)
                self.assertIn("Your village loses 15 food. Your villagers gain 7 tech points.", flat)
                self.assertNotIn("40 food", flat)
                self.assertNotIn("The village loses", flat)
                self.assertNotIn("\x03", "".join(t for _k, t, _l in shown))
                self.assertEqual(self.side.food_tech(r), (0, 10))

    def test_award_put_right_when_the_village_moves(self):
        """The same for (award): a tech store that fills to the game's limit after page 1 takes only 2 of the 7."""
        top = 0x7FFFFFFF - 1000000                      # story_custom.h CE_MAX_AMOUNT
        for game in self.games():
            with self.subTest(game=game):
                r, shown = self._moving(game, moving_graph(int(game[2]), True), 100, 0,
                                        lambda r: self.side.set_food_tech(r, self.side.food_tech(r)[0], top - 2))
                flat = one_line(shown)
                self.assertIn("Your villagers gain 2 tech points.", flat)
                self.assertNotIn("7 tech points", flat)
                self.assertNotIn("The village gains 2", flat)
                self.assertEqual(self.side.food_tech(r), (100, top))

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
