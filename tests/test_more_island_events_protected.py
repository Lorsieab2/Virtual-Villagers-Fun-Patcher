"""More Island Events: the owner's protected villagers are never picked (2026-11-13).

The owner: "no protected villagers can ever be chosen by these new events unless I explicitly say otherwise", and
"protected means no nursing villagers male or female, golden child, vv3 tribal chief, any other villager stock island
events forbid and never pick, vv2 totems. everyone else should be fair game."

Static: ONE check (adv_core.inc adv_is_protected / adv_is_protected_allowing with ADV_ALLOW_TRIBAL_CHIEF), used by
every game's picker (adv_game.eligible, which the Adventurer's adventurer and friend, The Cave Explorers' two and
The Climb's climber all go through).

EMULATED (the stock executables, the shipped DLL): in each game every protected kind is protected and never
eligible -- a nursing mother, a nursing father, A New Home's Golden Child, The Lost Children's totem statue, The
Secret City's Tribal Chief (allowed only with the flag), The Tree of Life's body or ghost, New Believers' Reanimate
and roles 12-17; the fair-game kinds (an Esteemed Elder who is not a statue, The Secret City's Esteemed Elder, The
Tree of Life's Scholar, New Believers' Former Heathen) are eligible; and an event whose only candidates are protected
never spawns (the Adventurer in all five games, The Cave Explorers, The Climb).
"""
from __future__ import annotations

import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))

from test_aspiring_adventurer import DLL, GAMES, HAVE_EMULATOR, HAVE_STOCK, LAYOUT, Village  # noqa: E402

NATIVE = ROOT / "native" / "vvfp_more_island_events"

# (what, field offset, size, value) per game: the protected kinds beyond nursing.
PROTECTED = {
    1: [("the Golden Child", 0x36C, 4, 0xC7)],
    2: [("an Esteemed Elder's totem statue", 0x558, 1, 1)],
    3: [("the Tribal Chief", 0xE80, 1, 1)],
    4: [("a body or a ghost", 0x1CC7, 1, 1)],
    5: [("a Reanimate in progress", 0x1CE1, 1, 1)] + [(f"role {r}", 0x1CFC, 4, r) for r in range(12, 18)],
}
# Fair game (the owner: "everyone else"): special in some way, never protected.
FAIR = {
    2: [("an Esteemed Elder (not a statue)", 0x7FC, 1, 1)],
    5: [("a Former Heathen (orange mask byte)", 0x1CED, 1, 1), ("role 11", 0x1CFC, 4, 11)],
}
CHIEF = 0x1


def protected(v, i: int, allow: int = 0) -> int:
    return v.p.export("VvfpMoreIslandEventsProtected", v.game, v.rec(i), allow)


class TheOneCheck(unittest.TestCase):
    def test_every_picker_uses_it(self) -> None:
        core = (NATIVE / "adv_core.inc").read_text(encoding="utf-8")
        self.assertIn("static int adv_is_protected(int game, const unsigned char *r)", core)
        self.assertIn("#define ADV_ALLOW_TRIBAL_CHIEF", core)
        for name, games in (("adv_vv1.inc", (1,)), ("adv_vv2.inc", (2,)), ("adv_vv345.inc", (3, 4, 5))):
            source = (NATIVE / name).read_text(encoding="utf-8")
            for game in games:
                self.assertIn(f"!adv_is_protected({game}, r)", source, (name, game))
        # The Cave Explorers' and The Climb's pickers go through the game's eligible.
        self.assertIn("g->eligible(r)", (NATIVE / "cave_core.inc").read_text(encoding="utf-8"))
        self.assertIn("g->eligible(r)", (NATIVE / "climb_core.inc").read_text(encoding="utf-8"))


@unittest.skipUnless(HAVE_EMULATOR and HAVE_STOCK and DLL.is_file(), "needs unicorn, pefile and the stock executables")
class Emulated(unittest.TestCase):
    def test_each_protected_kind_in_each_game(self) -> None:
        for game in GAMES:
            kinds = [("a nursing mother", LAYOUT[game]["carrying"], 4, 500, True),
                     ("a nursing father", LAYOUT[game]["carrying"], 4, 500, False)]
            kinds += [(w, o, n, val, True) for w, o, n, val in PROTECTED[game]]
            for what, off, size, value, woman in kinds:
                with self.subTest(game=game, what=what):
                    v = Village(game)
                    v.villager(0, "Ana", woman, years=30)
                    self.assertEqual((protected(v, 0), v.eligible(0)), (0, 1))
                    v.p.write(v.rec(0) + off, value.to_bytes(size, "little"))
                    self.assertEqual(protected(v, 0), 1)
                    self.assertEqual(v.eligible(0), 0)

    def test_the_tribal_chief_only_with_the_flag(self) -> None:
        v = Village(3)
        v.villager(0, "Ana", True, years=30)
        v.p.write(v.rec(0) + 0xE80, b"\x01")
        self.assertEqual((protected(v, 0), protected(v, 0, CHIEF)), (1, 0))
        v.p.put32(v.rec(0) + LAYOUT[3]["carrying"], 500)
        self.assertEqual(protected(v, 0, CHIEF), 1)               # the flag allows the chief, never a nursing one
        v = Village(5)
        v.villager(0, "Ana", True, years=30)
        v.p.put32(v.rec(0) + 0x1CFC, 13)
        self.assertEqual(protected(v, 0, CHIEF), 1)               # The Secret City's chief only

    def test_everyone_else_is_fair_game(self) -> None:
        cases = [(g, w, o, n, val) for g, items in FAIR.items() for w, o, n, val in items]
        for game, what, off, size, value in cases:
            with self.subTest(game=game, what=what):
                v = Village(game)
                v.villager(0, "Ana", True, years=30)
                v.p.write(v.rec(0) + off, value.to_bytes(size, "little"))
                self.assertEqual((protected(v, 0), v.eligible(0)), (0, 1))
        for game, base, count, floats, need in ((3, 0xEAC, 5, False, 3), (4, 0x1C5C, 5, True, 5)):
            with self.subTest(game=game, what="an Esteemed Elder / Scholar by skills"):
                v = Village(game)
                v.villager(0, "Ana", True, years=60)
                for k in range(need):
                    v.p.write(v.rec(0) + base + 4 * k, struct.pack("<f", 95.0) if floats else struct.pack("<i", 95))
                self.assertEqual((protected(v, 0), v.eligible(0)), (0, 1))

    def test_only_protected_candidates_never_spawn_the_adventurer(self) -> None:
        for game in GAMES:
            with self.subTest(game=game):
                v = Village(game)
                v.villager(0, "Ana", True, years=30, carrying=500)
                v.villager(1, "Ben", False, years=30, carrying=500)
                self.assertEqual(v.possible(), 0)
                _what, off, size, value = PROTECTED[game][0]
                v.villager(1, "Ben", False, years=30)
                v.p.write(v.rec(1) + off, value.to_bytes(size, "little"))
                v.villager(0, "Ana", True, years=30)
                self.assertEqual(v.possible(), 0)                 # one free, one protected: never
                if game >= 3:
                    self.assertFalse(v.listed())

    def test_only_protected_candidates_never_spawn_the_cave_or_the_climb(self) -> None:
        from test_cave_explorers import CaveVillage
        v = CaveVillage()
        v.villager(0, "Ana", True, years=20)
        v.villager(1, "Ben", False, years=20, special=(0x36C, 4, 0xC7))   # the Golden Child
        self.assertEqual(v.p.export("VvfpCaveExplorersPossible"), 0)
        v.villager(1, "Ben", False, years=20, carrying=500)              # a nursing father
        self.assertEqual(v.p.export("VvfpCaveExplorersPossible"), 0)
        v.villager(1, "Ben", False, years=20, special=(0x36C, 4, 0))      # neither: the pair may go
        self.assertEqual(v.p.export("VvfpCaveExplorersPossible"), 1)
        from test_the_climb import ClimbVillage
        for what, kw in (("nursing", dict(carrying=500)), ("a totem statue", dict(special=(0x558, 1, 1)))):
            with self.subTest(what=what):
                c = ClimbVillage()
                c.scientist(0, "Ana", True, **kw)
                self.assertEqual(c.climb_possible(), 0)
                self.assertFalse(c.begin_climb([0, 0, 0]))
        c = ClimbVillage()
        c.scientist(0, "Ana", True)
        c.p.write(c.rec(0) + 0x7FC, b"\x01")                     # an Esteemed Elder, not a statue: fair game
        self.assertEqual(c.climb_possible(), 1)


if __name__ == "__main__":
    unittest.main()
