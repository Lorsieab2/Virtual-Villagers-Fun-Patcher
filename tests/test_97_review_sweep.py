"""v1.35.97 review sweep: the open review findings on the .97 PRs that integ/97-all did not yet fix, each pinned here.

  * #774 (Codex): a mixer piece with more roles than the engine's PC_MAX_SLOTS (64) is reported and left out, so it
    can never make the game refuse the whole pieces file.
  * #831 (Codex): "No food or tech losses" also catches a food / tech effect whose per_game amounts take away.
  * #801 (Codex): a solidarity tag that is not a string is a validation problem, never a TypeError.
  * #791 (Codex): a dated next-refill line has one live countdown, not a second static "(in ...)".
  * #796 (Codex): Minimal Detail keeps an island event's name over its numbers ("name -- condition" headers) and
    keeps the food-shortage warning beside the farmer counts.
  * #815 (Codex): an owned Tech Point Doubler is counted in the research times (Minimal Detail hides the words that
    used to halve them); an older A New Home save with no migration marker cannot say whether it owns one; liking or
    disliking learning changes the Research test.
  * #809 / #826: the Jobs and training line about Work First follows the id the patch ships with.
"""
from __future__ import annotations

import struct
import sys
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import vv_cie_graph as cg  # noqa: E402
import vv_game_mechanics as gm  # noqa: E402
import vv_game_mechanics_life as life  # noqa: E402
import vv_game_mechanics_tech_time as tech_time  # noqa: E402
import vv_player_events as pe  # noqa: E402

NOW = 1_800_000_000.0


class MixerPieceRoles(unittest.TestCase):
    def piece(self, roles: int) -> str:
        return ("Piece: crowd\nKind: Flavour\n" + "".join(f"Role r{k}: villager\n" for k in range(roles))
                + "Text: The whole village gathers.\n")

    def test_more_than_64_roles_is_left_out_with_a_problem(self) -> None:
        ok = pe.parse_text(self.piece(pe.PIECE_MAX_SLOTS), "p.txt")
        self.assertFalse([str(p) for i in ok for p in i.problems])
        big = pe.parse_text(self.piece(pe.PIECE_MAX_SLOTS + 1) + "\n" + self.piece(2).replace("crowd", "pair"),
                            "p.txt")
        self.assertTrue(any("at most 64 roles" in p.text for p in big[0].problems))
        self.assertFalse(big[1].problems)
        data, _probs = pe.compile_pieces(big, 1)
        count = struct.unpack_from("<I", data, 20)[0]
        self.assertEqual(count, 1, "only the piece the engine can load is written")
        self.assertEqual(pe.PIECE_MAX_SLOTS, int(next(
            line.split()[2] for line in (ROOT / "native" / "vvfp_story_upgrades" / "story_procedural.inc")
            .read_text(encoding="utf-8").splitlines() if line.startswith("#define PC_MAX_SLOTS"))))


class NoLossesRule(unittest.TestCase):
    def event(self, effect: dict) -> types.SimpleNamespace:
        return types.SimpleNamespace(kind="event", graph={"nodes": {"a": {"effects": [effect]}}}, piece=None)

    def test_per_game_losses_break_the_rule(self) -> None:
        rules = {"no_losses": True}
        self.assertIsNone(pe.rule_problem(self.event({"do": "food", "amount": 50}), rules))
        self.assertIsNone(pe.rule_problem(self.event({"do": "food", "amount": 50, "per_game": {"1": [25, 50]}}),
                                          rules))
        for bad in ({"do": "food", "amount": 50, "per_game": {"1": [-50, -25]}},
                    {"do": "tech", "amount": 5, "per_game": {"3": [-5, 5]}},
                    {"do": "food", "amount": -10},
                    {"do": "food", "amount": -10, "max": -5},
                    {"do": "food", "size": "small", "loss": True}):
            with self.subTest(effect=bad):
                self.assertIn("No food or tech losses", pe.rule_problem(self.event(bad), rules) or "")
        self.assertIsNone(pe.rule_problem(self.event({"do": "food", "amount": -10}), {"no_losses": False}))


class SolidarityTagType(unittest.TestCase):
    def test_a_list_is_a_problem_not_a_crash(self) -> None:
        for value in (["raise", "lower"], {"raise": 1}, 3):
            with self.subTest(value=value):
                g = {"format": "vvfp-cie-graph", "version": 1, "title": "Test", "games": [1, 2, 3, 4, 5],
                     "roles": {"subject": {"kind": "villager"}}, "start": "a",
                     "nodes": {"a": {"text": "(Name) smiles.", "solidarity": value}}}
                _g, problems = cg.normalize(g)
                self.assertTrue(any("solidarity is raise, lower or neutral" in p for p in problems), problems)


class NextRefillCountdown(unittest.TestCase):
    def test_one_live_countdown(self) -> None:
        s = life.Source("Blackberries", 200, 1000, 1.0, step=100, interval=600.0, next_at=NOW + 120, rule=True)
        ctx = types.SimpleNamespace(paused=False, village=types.SimpleNamespace(now=NOW), sources=[s], speed=1)
        facts = [f for f in life.fill_lines(ctx) if "next refill" in f.text]
        self.assertEqual(len(facts), 1)
        self.assertEqual(facts[0].text, f"Blackberries, next refill: at {gm.DUE}.")
        full = next(f for f in life.fill_lines(ctx) if "time to full" in f.text)
        self.assertIn("(8 refills), with nobody picking", full.text)
        for now in (NOW, NOW + 60):
            line = gm.render([f for f in facts], now)
            self.assertEqual(line.count("(in "), 1, line)
        # Paused, or undated: words only, no countdown.
        paused = types.SimpleNamespace(paused=True, village=ctx.village, sources=[s], speed=1)
        text = next(f for f in life.fill_lines(paused) if "next refill" in f.text)
        self.assertIsNone(text.due)
        self.assertIn("once you unpause", text.text)


class MinimalDetail(unittest.TestCase):
    def test_an_event_header_heads_its_numbers(self) -> None:
        facts = [gm.Fact("Island events", "The Aspiring Doctor (mushrooms) -- needs a living villager", gm.CODE),
                 gm.Fact("Island events", "\"Eat a bit\": -15 to -34 health.", gm.CODE, True),
                 gm.Fact("Island events", "The Aspiring Doctor (bark) -- needs a living villager", gm.CODE),
                 gm.Fact("Island events", "\"Eat a bit\": +25 health.", gm.CODE, True)]
        self.assertEqual([(f.text, f.sub) for f in gm.minimum(facts)],
                         [("The Aspiring Doctor (mushrooms):", False), ("\"Eat a bit\": -15 to -34 health.", True),
                          ("The Aspiring Doctor (bark):", False), ("\"Eat a bit\": +25 health.", True)])

    def test_general_vv4_keeps_the_event_names(self) -> None:
        text = gm.render(gm.minimum(gm.general(4, now=NOW)), NOW)
        lines = text.splitlines()
        at = next(k for k, line in enumerate(lines) if "Eat a bit\": cured, -15 to -34 health" in line)
        self.assertIn("The Aspiring Doctor (mushrooms):", lines[at - 1])

    def test_the_shortage_stays_beside_the_farmers(self) -> None:
        from test_game_mechanics_time_units import pages
        page = dict((name, facts) for name, facts in pages() if name == "vv4-huttest-1")["vv4-huttest-1"]
        full, short = gm.render(page), gm.render(gm.minimum(page))
        self.assertIn("Blackberries alone: while catching up, 1 farmer; live, 1 farmer, but it cannot feed the village "
                      "alone", full)
        self.assertIn("Blackberries alone: while catching up, 1 farmer; live, 1 farmer, but it cannot feed the village "
                      "alone", short)
        if "even with every source the village is short" in full:
            self.assertIn("even with every source the village is short", short)


class TechDoubler(unittest.TestCase):
    def test_a_new_home_without_the_marker_cannot_say(self) -> None:
        data = bytearray(0xABDC + 12)
        self.assertIsNone(tech_time.doubler_owned(1, bytes(data)))          # 0 and no marker: maybe in the old file
        struct.pack_into("<I", data, tech_time.VV1_DOUBLER_MIGRATED_AT, 1)
        self.assertIs(tech_time.doubler_owned(1, bytes(data)), False)
        struct.pack_into("<I", data, 0x9E94, 1)
        self.assertIs(tech_time.doubler_owned(1, bytes(data)), True)
        struct.pack_into("<I", data, tech_time.VV1_DOUBLER_MIGRATED_AT, 0)
        self.assertIs(tech_time.doubler_owned(1, bytes(data)), True)        # a 1 is always the village's own

    def test_the_factor_needs_the_patch_and_the_doubler(self) -> None:
        data = bytearray(0x900)
        struct.pack_into("<I", data, 0x890, 1)                               # VV4: the Tech Doubler's bit

        def village(has):
            return types.SimpleNamespace(game=4, data=bytes(data), has=lambda f: has.get(f))
        self.assertEqual(tech_time.doubler_factor(village({"vv4_enable_origins_exclusive_features": True})), 2)
        self.assertEqual(tech_time.doubler_factor(village({})), 1)
        struct.pack_into("<I", data, 0x890, 2)                               # the Food Doubler only
        self.assertEqual(tech_time.doubler_factor(village({"vv4_enable_origins_exclusive_features": True})), 1)

    def test_the_rate_doubles_and_minimal_detail_keeps_it(self) -> None:
        source = (ROOT / "src" / "vv_game_mechanics_tech_time.py").read_text(encoding="utf-8")
        self.assertEqual(source.count("* doubled  # noqa: E731"), 2)        # glance() and lines()
        self.assertIn("already count it", source)
        self.assertNotIn("takes half as long as it says", source)


class LearningAndResearch(unittest.TestCase):
    def test_learning_changes_the_research_test(self) -> None:
        source = (ROOT / "src" / "vv_game_mechanics_tech_time.py").read_text(encoding="utf-8")
        self.assertNotIn("never the Research test or its pay", source)
        self.assertIn("liking learning makes the Research test pass 33 more times in 100", source)
        # The chances pages say the same of the one skill test (+66 instead of +33 liked, +16 disliked).
        for game in (2, 3, 4, 5):
            text = (ROOT / "src" / f"vv_game_mechanics_chances_vv{game}.py").read_text(encoding="utf-8")
            self.assertIn("likes learning", text)


if __name__ == "__main__":
    unittest.main()
