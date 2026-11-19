"""More Island Events never changes the stock island events' chances (the owner's top rule).

The nine events of More Island Events come only when they are due -- picked with Pick Island Event, or drawn by
Story / Cheat Upgrades' separate rare roll (native/vvfp_story_upgrades/story_collection.inc) -- and never take a share
of a game's own draw.  Proved here with the shipped DLL in each game's own selection code (unicorn, the stock
executables; Story's two exports stood in for by tests/test_aspiring_adventurer.py's Village):

  * The Secret City, The Tree of Life, New Believers: the selector's list holds exactly the stock events whose own
    condition holds (the companion adds no entry, due or not), and 10,000 runs of the selector's own draw give each
    listed stock event its 1/c share (a chi-square test) and never slot 0;
  * A New Home: the encounter setup's call of the roller runs the stock roller, rand for rand: 10,000 draws through
    the companion equal 10,000 draws of the stock roller itself with the same random stream, each possible
    encounter 1/m;
  * The Lost Children: family A's chooser through the companion equals the stock chooser draw for draw over 10,000
    runs, the draw's call 0x41F59D never written while nothing is due, each kept event 1/c, never 21 or 22;
  * A New Home's and The Lost Children's single-result choosers (The Remembrance Ceremony, The Rumblings): with both
    possible and nothing due, 1,000 trigger runs reach the game's own constructor untouched, the chooser's draw call
    never written and no draw taken by the companion.

The live game is NOT exercised here.
"""
from __future__ import annotations

import random
import struct
import sys
import unittest
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))

import test_aspiring_adventurer as aa  # noqa: E402

NEEDS = unittest.skipUnless(aa.HAVE_EMULATOR and aa.HAVE_STOCK and aa.DLL.is_file(),
                            "needs unicorn, pefile and the stock executables")
RUNS = 10_000


def chi2_999(df: int) -> float:
    """The chi-square value a fair draw stays under 999 times in 1000 (Wilson-Hilferty; z = 3.090)."""
    k = 2.0 / (9.0 * df)
    return df * (1.0 - k + 3.090 * k ** 0.5) ** 3

if aa.HAVE_EMULATOR:
    from story_emulator import STACK_TOP


def chi_square(counts: Counter, outcomes: list[int], runs: int) -> float:
    expected = runs / len(outcomes)
    return sum((counts.get(o, 0) - expected) ** 2 / expected for o in outcomes)


# The selector of each later game: the stock listing loop's start, the address right after its draw
# (`mov esi, [esp + eax*4 + off]`), and the list's offset from esp while the loop runs.
SELECTORS = {3: (0x419B4D, 0x419B85), 4: (0x418041, 0x4180AF), 5: (0x4188B1, 0x418913)}
STUBBED = {4: {0x448E10: 4}, 5: {}}            # other calls between the loop and the draw (their objects not built)


def seeded_rand(v, rng: random.Random, seen: list[int] | None = None):
    def rand(pr):
        n = pr.arg(0)
        if seen is not None:
            seen.append(n)
        return (rng.randrange(n) if n > 0 else 0), 0
    v.p.stub(v.rand, rand)


@NEEDS
class TheLaterGames(unittest.TestCase):
    def village(self, game: int, slots: list[int]):
        v = aa.Village(game)
        v.villager(0, "Ana", True)
        v.villager(1, "Ben")                       # the Adventurer can happen: it still takes no share
        p = v.p
        code = p.alloc(16)
        p.write(code, b"\xB0\x01\xC3")             # mov al, 1; ret: the event's own condition holds
        vtable = p.alloc(0x40)
        for k in range(16):
            p.put32(vtable + 4 * k, code)
        for slot in slots:
            obj = p.alloc(16)
            p.put32(obj, vtable)
            p.put32(v.t["table"] + 4 * slot, obj)
        for va, pop in STUBBED.get(game, {}).items():
            p.stub(va, lambda pr, pop=pop: (0, pop))
        return v

    def select(self, v) -> tuple[int, int]:
        """The selector's listing loop and its own draw: (entries listed, the slot drawn)."""
        start, after = SELECTORS[v.game]
        p = v.p
        p.set_reg("esp", STACK_TOP - 0x2000)
        p.run(start, after)
        return p.reg("edi"), p.reg("esi")

    def test_the_list_holds_the_stock_events_only(self) -> None:
        for game in (3, 4, 5):
            for due in (-1, 0):
                with self.subTest(game=game, due=due):
                    slots = list(range(1, 50, 2))
                    v = self.village(game, slots)
                    v.due = due
                    v.rolls = [0]
                    listed, drawn = self.select(v)
                    self.assertEqual(listed, len(slots))           # the stock count, nothing added
                    self.assertEqual(drawn, slots[0])
                    self.assertTrue(v.can_fire(v.p.u32(v.t["table"])) or due < 0)

    def test_each_stock_event_its_one_in_c_share(self) -> None:
        for game in (3, 4, 5):
            with self.subTest(game=game):
                slots = list(range(1, 50, 2))                    # 25 events whose condition holds
                v = self.village(game, slots)
                v.due = 0                                        # one of ours due: it still takes no share
                rng = random.Random(1000 + game)
                bounds: list[int] = []
                seeded_rand(v, rng, bounds)
                counts = Counter()
                for _ in range(RUNS):
                    listed, drawn = self.select(v)
                    self.assertEqual(listed, len(slots))
                    counts[drawn] += 1
                self.assertEqual(set(bounds), {len(slots)})     # always rand(c), the stock bound
                self.assertEqual(set(counts), set(slots))       # never slot 0, never anything else
                self.assertLess(chi_square(counts, slots, RUNS), chi2_999(24))


@NEEDS
class ANewHome(unittest.TestCase):
    def village(self):
        v = aa.Village(1)
        v.villager(0, "Ana", True)
        v.villager(1, "Ben")                                     # The Aspiring Adventurer can happen
        return v

    def draws(self, v, through_companion: bool, seed: int) -> list[int]:
        """RUNS encounter draws: through the setup's call (the companion's v1_choose), or the stock roller itself."""
        rng = random.Random(seed)
        seeded_rand(v, rng)
        out = []
        dlg = v.p.alloc(0x6000)
        v.p.put32(dlg + 0x50A4, v.world)
        v.p.put32(dlg + 0x50A8, v.base)
        for _ in range(RUNS):
            if through_companion:
                v.p.set_reg("esp", STACK_TOP - 0x3000)
                v.p.set_reg("ecx", dlg)
                v.p.run(0x4189F2, 0x4189F7)
                out.append(v.p.reg("eax"))
            else:
                out.append(v.p.call(0x418920, [], ecx=dlg))
        return out

    def test_the_stock_roller_draw_for_draw(self) -> None:
        self.assertEqual(aa.Village(1).p.read(0x4189F2, 1), b"\xE8")
        v = self.village()
        ours = self.draws(v, True, 7)
        stock = self.draws(self.village(), False, 7)
        self.assertEqual(ours, stock)
        counts = Counter(ours)
        outcomes = sorted(counts)
        self.assertNotIn(0x7F4B1A2E, outcomes)
        self.assertLess(chi_square(counts, outcomes, RUNS), chi2_999(len(outcomes) - 1))
        self.assertEqual(v.done, [])


@NEEDS
class TheLostChildren(unittest.TestCase):
    def village(self):
        v = aa.Village(2)
        v.villager(0, "Ana", True)
        v.villager(1, "Ben")
        v.p.stub(0x44B310, lambda pr: (0, 0))       # event 4: its own test (the pool it reads not built here) says no
        return v

    def draws(self, v, through_companion: bool, seed: int, writes: list[int] | None = None) -> list[int]:
        rng = random.Random(seed)
        seeded_rand(v, rng)
        out = []
        dlg = v.p.alloc(0x6000)
        v.p.put32(dlg + 0x50AC, v.world)
        v.p.put32(dlg + 0x50B0, v.base)
        for _ in range(RUNS):
            if through_companion:
                v.p.set_reg("esp", STACK_TOP - 0x3000)
                v.p.set_reg("ecx", dlg)
                v.p.run(0x41F792, 0x41F797)
                out.append(v.p.reg("eax"))
            else:
                out.append(v.p.call(0x41F570, [], ecx=dlg))
        return out

    def test_the_stock_chooser_draw_for_draw(self) -> None:
        from unicorn import UC_HOOK_MEM_WRITE
        v = self.village()
        stock_site = v.p.read(0x41F59D, 5)
        writes: list[int] = []
        v.p.mu.hook_add(UC_HOOK_MEM_WRITE, lambda mu, a, address, size, value, d: writes.append(address),
                        begin=0x41F59D, end=0x41F5A1)
        ours = self.draws(v, True, 11)
        stock = self.draws(self.village(), False, 11)
        self.assertEqual(ours, stock)
        self.assertEqual(writes, [])                             # the draw's call: the stock bytes throughout
        self.assertEqual(v.p.read(0x41F59D, 5), stock_site)
        counts = Counter(e & 0xFF for e in ours)
        outcomes = sorted(counts)
        self.assertFalse({21, 22} & set(outcomes))
        self.assertLess(chi_square(counts, outcomes, RUNS), chi2_999(len(outcomes) - 1))

    def test_the_site_is_written_only_while_due(self) -> None:
        from unicorn import UC_HOOK_MEM_WRITE
        v = self.village()
        writes: list[int] = []
        v.p.mu.hook_add(UC_HOOK_MEM_WRITE, lambda mu, a, address, size, value, d: writes.append(address),
                        begin=0x41F59D, end=0x41F5A1)
        stock_site = v.p.read(0x41F59D, 5)
        v.due = 0
        dlg = v.p.alloc(0x6000)
        v.p.put32(dlg + 0x50AC, v.world)
        v.p.put32(dlg + 0x50B0, v.base)
        v.p.set_reg("esp", STACK_TOP - 0x3000)
        v.p.set_reg("ecx", dlg)
        v.p.run(0x41F792, 0x41F797)
        self.assertEqual(v.p.reg("eax") & 0xFF, 21)
        self.assertTrue(writes)
        self.assertEqual(v.p.read(0x41F59D, 5), stock_site)     # put back


@NEEDS
class TheSingleResultChoosers(unittest.TestCase):
    """A New Home's and The Lost Children's single-result island events: with The Remembrance Ceremony and The
    Rumblings both possible and nothing due, the trigger's constructor call reaches the game's own constructor with
    the trigger's own arguments, the chooser's draw call is never written and the companion draws nothing -- the
    chooser's every draw is the stock one."""

    def test_nothing_due_the_stock_constructor_untouched(self) -> None:
        from unicorn import UC_HOOK_MEM_WRITE
        from test_ceremony_and_rumblings import RUMBLINGS, REMEMBRANCE, remembrance_village
        for game, ctor, site, draw_site in ((1, 0x4286B0, 0x423A06, 0x4284DB), (2, 0x4348E0, 0x42F0F7, 0x434607)):
            with self.subTest(game=game):
                v = remembrance_village(game)
                v.puzzles()
                for k in range(v.structures()):
                    v.finish(k, False)
                v.finish(0)
                self.assertTrue(v.possible(REMEMBRANCE) and v.possible(RUMBLINGS))
                p = v.p
                stock = p.read(draw_site, 5)
                calls: list[tuple] = []
                p.stub(ctor, lambda pr: (calls.append((pr.reg("ecx"), pr.arg(0), pr.arg(1))) or pr.reg("ecx"), 8))
                bounds: list[int] = []
                seeded_rand(v, random.Random(5), bounds)
                writes: list[int] = []
                p.mu.hook_add(UC_HOOK_MEM_WRITE, lambda mu, a, address, size, value, d: writes.append(address),
                              begin=draw_site, end=draw_site + 4)
                event = p.alloc(0x6000)
                for k in range(RUNS // 10):
                    esp = STACK_TOP - 0x3000
                    p.put32(esp, 2)
                    p.put32(esp + 4, k)
                    p.set_reg("esp", esp)
                    p.set_reg("ecx", event)
                    p.run(site, site + 5)
                self.assertEqual(calls, [(event, 2, k) for k in range(RUNS // 10)])
                self.assertEqual(bounds, [])                    # the companion drew nothing
                self.assertEqual(writes, [])                    # the chooser's draw call never written
                self.assertEqual(p.read(draw_site, 5), stock)
                self.assertEqual(v.cr_state()[6], 0)


class TheMechanicsPages(unittest.TestCase):
    """The Game Mechanics pages say what the companion does: More Island Events' events never take a share of the
    game's own draw (no "1 in 23", no place of their own in it), and the rare roll's chance is the C table's.
    Needs no emulator: it reads the pages' own catalogs."""

    STALE = ("1 in 23", "1 in m + ", "its own slot", "own place in the draw", "own case in that draw",
             "drawn like them", "1 in 28 plus")

    def test_no_event_claims_a_share_of_the_stock_draw(self) -> None:
        sys.path.insert(0, str(ROOT / "src"))
        for game in range(1, 6):
            catalog = __import__(f"vv_game_mechanics_events_vv{game}")
            ours = [e for e in catalog.EVENTS if e.only_with == f"vv{game}_more_island_events"]
            self.assertTrue(ours, game)
            for event in ours:
                text = event.text + " " + " ".join(s if isinstance(s, str) else s.text for s in event.subs)
                with self.subTest(game=game, event=event.title):
                    self.assertIn("never takes a share of the game's own draw", text)
                    for stale in self.STALE:
                        self.assertNotIn(stale, text)
            rules = " ".join(line.text for line in getattr(catalog, "RULES", ()))
            for stale in self.STALE:
                with self.subTest(game=game, rules=stale):
                    self.assertNotIn(stale, rules)

    def test_the_rare_roll_chance_is_the_companions(self) -> None:
        import re
        sys.path.insert(0, str(ROOT / "src"))
        import vv_game_mechanics_adventurer as gm
        source = (ROOT / "native" / "vvfp_story_upgrades" / "story_collection.inc").read_text(encoding="utf-8")
        table = re.search(r"SC_P_PERCENT\[6\] = \{ 0, (\d+), (\d+), (\d+), (\d+), (\d+) \}", source)
        self.assertIsNotNone(table)
        self.assertEqual(gm.RARE_ROLL_PERCENT, {g: int(table.group(g)) for g in range(1, 6)})


if __name__ == "__main__":
    unittest.main()
