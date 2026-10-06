"""Custom Island Event Maker, v1.35.46 additions (all five games).

The owner's requests of 2026-10-01: food sources and stores set to an
amount, puzzles marked solved or unsolved, special statuses (A New Home's
Golden Child, The Secret City's Tribal Chief, New Believers' Heathen masks and
new Heathens), pregnancies ended ("0 babies") or given a different number of
babies, the unborn baby's father, many more behaviours, and skeletons brought
back to life -- plus the patcher fixes found on the way (a Golden Child in a
custom pregnancy, The Lost Children's byte flags, its refill's side effect,
custom titles dropped at death).

Everything runs the shipped bytes as tests/test_story_custom_island_event.py
does: each game's executable as the patcher renders it, in all three
population modes where the population matters, with the test build of the
companion mapped beside it; the game routines that need the whole game are
replaced by stubs that record the arguments the companion passes.
"""
from __future__ import annotations

import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))

import test_story_custom_island_event as base  # noqa: E402
from story_custom_fixtures import Change, Event, Spawn  # noqa: E402

GAMES = base.GAMES
MODES = base.MODES
have_stock = base.have_stock
emulated = base.emulated

# Each game's room predicate, stop routine (va, bytes popped) and clock.
ROOM = {"vv1": 0x43A1A0, "vv2": 0x44B310, "vv3": 0x45FE30, "vv4": 0x468350, "vv5": 0x472BD0}
STOP = {"vv1": (0x439470, 4), "vv2": (0x4492A0, 4), "vv3": (0x460F70, 4), "vv4": (0x468C60, 0),
        "vv5": (0x473440, 0)}
PREGNANT = {"vv1": (0x358, 0x35C), "vv2": (0x540, 0x544), "vv3": (0xE8C, 0xE90), "vv4": (0x1C4C, 0x1C50),
            "vv5": (0x1C4C, 0x1C50)}
NOW = 0x0BADCAFE


def story(game, mode="collection_progression"):
    s = base.Story(game, mode)
    s.order = []
    return s


def record(s, va, pop, value=0, also=None):
    """Stub `va` (thiscall, `pop` bytes) to record [ecx, args...] in s.order
    and s.calls, optionally running `also(proc)` first."""
    def fn(p):
        if also is not None:
            also(p)
        row = [p.reg("ecx")] + [p.arg(i) for i in range(pop // 4)]
        s.calls.setdefault(va, []).append(row)
        s.order.append((va, row))
        return value, pop
    s.proc.stub(va, fn)


def getter(s, va, value):
    s.proc.stub(va, lambda p: (value, 0))


def i32(proc, va):
    return struct.unpack("<i", proc.read(va, 4))[0]


# ---------------------------------------------------------------------------
# A, B: food sources and stores set to an amount
# ---------------------------------------------------------------------------

@emulated
class ValueTests(unittest.TestCase):
    def _fields(self, s):
        """(value index, address, what makes it available) per game."""
        w = s.village.world
        g = s.game
        if g == "vv1":
            return [(0, w + 0xA2F4, None), (1, w + 0xA2F8, lambda: s.proc.put32(w + 0xA2E4, 2))]
        if g == "vv2":
            return [(0, w + 0x2EACC, None), (1, w + 0x2EAD0, None), (2, w + 0x2EAD4, None),
                    (3, w + 0x2EAD8, lambda: s.proc.write(w + 0x2E798, b"\1"))]
        if g == "vv3":
            def plant():
                s.proc.put32(0x594844, 3)
            return ([(k, 0x594810 + 0x18 * k, plant) for k in range(3)]
                    + [(3 + k, 0x59480C + 0x18 * k, plant) for k in range(3)] + [(6, 0x5945E0, None)])
        if g == "vv4":
            return [(0, w + 0x170F8, None), (1, 0x4D8618, None), (2, 0x4D8D98, None)]
        farm = [0]
        s.proc.stub(0x43AE80, lambda p: (farm[0], 4))
        return [(0, w + 0x17D58, None), (1, w + 0x17D5C, lambda: farm.__setitem__(0, 1))]

    RANGES = {"vv1": [(0, 5000), (0, 800)], "vv2": [(0, 1500), (0, 2200), (0, 1000), (0, 800)],
              "vv3": [(0, 1000)] * 3 + [(0, 2)] * 3 + [(0, 3000)],
              "vv4": [(0, 1000), (0, 6), (0, 99)], "vv5": [(0, 1000), (0, 800)]}

    def test_each_store_is_set_within_the_games_own_range_and_nothing_else_changes(self):
        for game in GAMES:
            if not have_stock(game):
                continue
            for which, va, enable in self._fields(s := story(game)):
                low, high = self.RANGES[game][which]
                with self.subTest(game=game, value=which):
                    if game == "vv3":
                        s.proc.put32(0x594844, 0)          # no tree planted yet
                    if enable is not None:
                        s.proc.put32(va, 123 if high > 2 else 1)
                        ok, r, _ = s.apply(Event(values=[(which, high)]))
                        self.assertEqual(r["refused"], 1, "not there yet: refused")
                        self.assertEqual(s.proc.u32(va), 123 if high > 2 else 1)
                        enable()
                    before = s.proc.read(va - 64, 128)
                    for amount in (low, high, (low + high) // 2):
                        ok, r, _ = s.apply(Event(values=[(which, amount)]))
                        self.assertEqual(r["refused"], 0)
                        self.assertEqual(i32(s.proc, va), amount)
                    after = s.proc.read(va - 64, 128)
                    self.assertEqual(before[:64] + before[68:], after[:64] + after[68:],
                                     "only the store itself is written")
                    for bad in (low - 1, high + 1):
                        ok, r, _ = s.apply(Event(values=[(which, bad)]))
                        self.assertEqual(r["refused"], 1, f"{bad} is outside {low}-{high}")
                        self.assertEqual(i32(s.proc, va), (low + high) // 2)

    def test_a_tree_kind_is_never_past_papaya(self):
        if not have_stock("vv3"):
            self.skipTest("no stock executable")
        s = story("vv3")
        s.proc.put32(0x594844, 1)
        ok, r, _ = s.apply(Event(values=[(3, 3)]))
        self.assertEqual(r["refused"], 1)
        ok, r, _ = s.apply(Event(values=[(4, 1)]))
        self.assertEqual(r["refused"], 1, "tree 2 is not planted")
        self.assertEqual(s.proc.u32(0x59480C + 0x18), 0)

    def test_the_amount_is_set_after_the_refill(self):
        if not have_stock("vv4"):
            self.skipTest("no stock executable")
        s = story("vv4")
        w = s.village.world
        ok, r, _ = s.apply(Event(refill=1, values=[(0, 40)]))
        self.assertEqual(s.proc.u32(w + 0x170F8), 40)


# ---------------------------------------------------------------------------
# C: puzzles
# ---------------------------------------------------------------------------

def puzzle_index(game, name):
    source = base.ADAPTER_SOURCES[game].read_text(encoding="utf-8")
    body = source[source.index("_PUZZLE_DEFS[] = {"):]
    names = []
    for line in body.splitlines()[1:]:
        if line.startswith("};"):
            break
        if line.strip().startswith('{ "'):
            names.append(line.strip()[3:].split('"', 1)[0])
    return names.index(name)


@emulated
class Vv1PuzzleTests(unittest.TestCase):
    def setUp(self):
        if not have_stock("vv1"):
            self.skipTest("no stock executable")
        self.s = story("vv1")
        self.w = self.s.village.world
        self.p = self.s.proc
        self.p.put32(self.w + 0x9E1C, 1000)
        self.now = [1000 + 5 * 3600 + 7]
        self.p.stub(0x402F70, lambda q: (self.now[0], 0))

    def mark(self, name, solved):
        return self.s.apply(Event(puzzles=[(puzzle_index("vv1", name), solved)]))[1]

    def test_solved_writes_progress_flag_and_hours_and_unsolved_a_new_villages_state(self):
        r = self.mark("The Well", 1)
        self.assertEqual(r["refused"], 0)
        self.assertEqual((self.p.u32(self.w + 0xA054), self.p.read(self.w + 0xA058, 1),
                          self.p.u32(self.w + 0x9EA8)), (2, b"\1", 5))
        self.now[0] += 10 * 3600
        self.mark("The Well", 1)
        self.assertEqual(self.p.u32(self.w + 0x9EA8), 5, "already solved: nothing is written")
        self.mark("The Well", 0)
        self.assertEqual((self.p.u32(self.w + 0xA054), self.p.read(self.w + 0xA058, 1)), (0, b"\0"))
        self.mark("The Hut (the first small hut)", 1)
        self.mark("The Hut (the first small hut)", 0)
        self.assertEqual(self.p.u32(self.w + 0x9FE4), 125, "a new village's hut progress")

    def test_hours_are_at_least_one(self):
        self.now[0] = 1000
        self.mark("The School", 1)
        self.assertEqual(self.p.u32(self.w + 0x9EA4), 1)

    def test_beach_and_treasure_keep_their_first_hours(self):
        self.p.put32(self.w + 0x9E58, 3)
        self.mark("The Beach", 1)
        self.assertEqual((self.p.u32(self.w + 0x9FB4), self.p.u32(self.w + 0x9E58)), (150, 3))

    def test_herb_mastery_takes_its_four_herbs_both_ways(self):
        herbs = [self.w + k for k in (0xA060, 0xA068, 0xA070, 0xA078)]
        self.mark("Herb Mastery", 1)
        self.assertEqual([self.p.read(h, 1) for h in herbs] + [self.p.read(self.w + 0xA080, 1)], [b"\1"] * 5)
        self.mark("Herb Mastery", 0)
        self.assertEqual([self.p.read(h, 1) for h in herbs] + [self.p.read(self.w + 0xA080, 1)], [b"\0"] * 5)

    def test_the_cave_is_not_unsolved_while_the_player_is_inside_it(self):
        self.mark("The Cave", 1)
        self.p.put32(self.w + 0xACB4, 0x14)
        r = self.mark("The Cave", 0)
        self.assertEqual((r["refused"], self.p.read(self.w + 0x9FA8, 1)), (1, b"\1"))
        self.p.put32(self.w + 0xACB4, 2)
        r = self.mark("The Cave", 0)
        self.assertEqual((r["refused"], self.p.read(self.w + 0x9FA8, 1)), (0, b"\0"))

    def test_the_later_huts_go_back_to_started_only_when_the_village_is_big_enough(self):
        v = self.s.village
        name = "The second small hut (not on the Puzzles screen)"
        self.mark(name, 1)
        self.mark(name, 0)
        self.assertEqual(self.p.u32(self.w + 0x9FEC), 0)
        for i in range(15):
            v.put(i, sex="f", years=30, name=f"V{i}")
        self.mark(name, 1)
        self.mark(name, 0)
        self.assertEqual(self.p.u32(self.w + 0x9FEC), 1)

    def test_the_walk_grid_is_rebuilt_for_the_puzzles_it_reads(self):
        nav = self.p.alloc(0x100)
        self.p.put32(self.s.village.array + 0x3E014, nav)
        record(self.s, 0x414590, 0)
        self.mark("The Temple", 1)
        self.mark("The Well", 1)
        self.assertEqual(self.s.calls[0x414590], [[nav]])

    def test_the_golden_child_puzzle_is_never_offered(self):
        with self.assertRaises(ValueError):
            puzzle_index("vv1", "The Golden Child")


@emulated
class Vv2PuzzleTests(unittest.TestCase):
    def setUp(self):
        if not have_stock("vv2"):
            self.skipTest("no stock executable")
        self.s = story("vv2")
        self.w = self.s.village.world
        self.p = self.s.proc
        self.p.put32(self.w + 0x2E4F8, 500)
        self.p.stub(0x403200, lambda q: (500 + 2 * 3600, 0))
        for k in range(0x1FB, 0x214):
            self.p.write(self.w + k, b"\1")

    def mark(self, name, solved):
        return self.s.apply(Event(puzzles=[(puzzle_index("vv2", name), solved)]))[1]

    def test_solved_writes_flag_progress_hours_and_gate_and_redraws(self):
        scene, overlay = self.p.alloc(0x40), self.p.alloc(0x40)
        self.p.put32(self.s.village.array + 0xE574D8, scene)
        self.p.put32(self.s.village.array + 0xE574E8, overlay)
        record(self.s, 0x418660, 0)
        record(self.s, 0x41C1D0, 0)
        self.mark("The Hospital", 1)
        self.assertEqual((self.p.read(self.w + 0x2E780, 1), self.p.u32(self.w + 0x2E77C),
                          self.p.u32(self.w + 0x2E53C), self.p.read(self.w + 0x200, 1)), (b"\1", 1200, 2, b"\0"))
        self.assertEqual((self.s.calls[0x418660], self.s.calls[0x41C1D0]), ([[scene]], [[overlay]]))
        self.mark("The Hospital", 0)
        self.assertEqual((self.p.read(self.w + 0x2E780, 1), self.p.u32(self.w + 0x2E77C),
                          self.p.u32(self.w + 0x2E53C)), (b"\0", 0, 0))

    def test_the_gong_of_wonder_is_whole_exactly_when_its_four_pieces_are(self):
        pieces = ["The Boxed Gong Piece", "The Sunken Gong Piece", "The Inlaid Gong Piece",
                  "The Overgrown Gong Piece"]
        for name in pieces[:3]:
            self.mark(name, 1)
        self.assertEqual((self.p.read(self.w + 0x2E7F0, 1), self.p.u32(self.w + 0x2EAC8)), (b"\0", 0))
        self.assertEqual(self.p.read(self.w + 0x2E7D0, 1), b"\1", "the crate is opened too")
        self.mark(pieces[3], 1)
        self.assertEqual((self.p.read(self.w + 0x2E7F0, 1), self.p.u32(self.w + 0x2EAC8)), (b"\1", 1))
        self.mark(pieces[1], 0)
        self.assertEqual(self.p.read(self.w + 0x2E7F0, 1), b"\0")

    def test_the_mosaic_stays_while_its_inlaid_piece_is_out(self):
        self.mark("The Ancient Mosaic", 1)
        self.mark("The Inlaid Gong Piece", 1)
        r = self.mark("The Ancient Mosaic", 0)
        self.assertEqual((r["refused"], self.p.read(self.w + 0x2E7B8, 1)), (1, b"\1"))

    def test_the_stew_is_never_unsolved_and_herbs_and_gates_go_back(self):
        self.mark("The Stew", 1)
        r = self.mark("The Stew", 0)
        self.assertEqual((r["refused"], self.p.read(self.w + 0x2E7A8, 1)), (1, b"\1"))
        self.mark("Herb Mastery", 1)
        self.assertEqual(self.p.read(self.w + 0x2E860, 41)[::8], b"\1" * 6)
        self.mark("Herb Mastery", 0)
        self.assertEqual(self.p.read(self.w + 0x2E860, 41)[::8], b"\0" * 6)
        self.assertEqual(self.p.read(self.w + 0x201, 1), b"\1", "its message can show again")

    def test_the_dam_starts_the_crops_from_nothing(self):
        self.p.put32(self.w + 0x2EAD8, 600)
        self.mark("The Dam", 1)
        self.assertEqual(self.p.u32(self.w + 0x2EAD8), 0)


@emulated
class Vv3PuzzleTests(unittest.TestCase):
    def setUp(self):
        if not have_stock("vv3"):
            self.skipTest("no stock executable")
        self.s = story("vv3")
        self.p = self.s.proc
        self.p.stub(0x426590, lambda q: (NOW, 0))
        record(self.s, 0x435680, 4)

    def entry(self, i):
        return (i32(self.p, 0x594990 + 8 * i), self.p.u32(0x594994 + 8 * i))

    def mark(self, name, solved):
        return self.s.apply(Event(puzzles=[(puzzle_index("vv3", name), solved)]))[1]

    def test_solved_is_the_threshold_and_the_clock_and_unsolved_zero(self):
        for name, i, threshold in (("The First Chief", 0, 1), ("The Roster of the Dead", 3, 700),
                                   ("The Ruins", 6, 1800)):
            self.mark(name, 1)
            self.assertEqual(self.entry(i), (threshold, NOW))
            self.mark(name, 0)
            self.assertEqual(self.entry(i), (0, 0))
        self.assertNotIn(0x435680, self.s.calls)

    def test_objects_with_their_own_state_go_through_reset_puzzle(self):
        for name, i in (("The Statue", 8), ("The Sharks", 10), ("Aromatherapy", 11)):
            self.p.put32(0x594990 + 8 * i, 99)
            self.p.put32(0x594994 + 8 * i, 5)
            self.mark(name, 0)
            self.assertEqual(self.s.calls[0x435680][-1], [0x594990, i])
            self.assertEqual(self.entry(i), (0, 0))

    def test_the_keys_count_in_the_door_and_never_come_back_out(self):
        self.mark("The Ash Key", 1)
        self.mark("The Clam Key", 1)
        self.assertEqual(i32(self.p, 0x594990 + 8 * 19), 2)
        r = self.mark("The Clam Key", 0)
        self.assertEqual((r["refused"], i32(self.p, 0x594990 + 8 * 14)), (1, 1))

    def test_the_statue_is_never_marked_solved(self):
        r = self.mark("The Statue", 1)
        self.assertEqual((r["refused"], self.entry(8)), (1, (0, 0)))


@emulated
class Vv4AndVv5PuzzleTests(unittest.TestCase):
    """The Tree of Life and New Believers: the game's own Advance and Reset."""

    def _advance(self, s, entries, thresholds):
        def advance(p):
            i = p.arg(0)
            if i32(p, entries + 8 * i) < i32(p, thresholds + 4 * i):
                p.put32(entries + 8 * i, i32(p, entries + 8 * i) + 1)
                if i32(p, entries + 8 * i) >= i32(p, thresholds + 4 * i):
                    p.put32(entries + 8 * i + 4, NOW)
        return advance

    def test_tree_of_life(self):
        if not have_stock("vv4"):
            self.skipTest("no stock executable")
        s = story("vv4")
        p = s.proc
        record(s, 0x438A30, 4, also=self._advance(s, 0x4D8BF8, 0x4D8B20))
        record(s, 0x438710, 4, also=lambda q: q.put32(0x4D8BF8 + 8 * q.arg(0), 0))
        record(s, 0x46D090, 0)
        record(s, 0x46D610, 4)
        record(s, 0x433D80, 0)
        r = s.apply(Event(puzzles=[(1, 1)]))[1]
        self.assertEqual(r["refused"], 1, "the thresholds are not there before the game fills them")
        for i, threshold in enumerate([1, 1, 1, 1, 1, 5, 1, 1, 1, 5, 1, 1, 1, 1, 1, 3]):
            p.put32(0x4D8B20 + 4 * i, threshold)
        r = s.apply(Event(puzzles=[(1, 1), (5, 1), (11, 1)]))[1]
        self.assertEqual(r["refused"], 0)
        self.assertEqual([c[1] for c in s.calls[0x438A30]], [1, 5, 11])
        self.assertEqual((p.u32(0x4D8CF4), p.u32(0x4D8D04)), (1, 0), "the stream flows")
        self.assertEqual((p.u32(0x4D86B0), p.u32(0x4D86B4), p.u32(0x4D86AC)), (0, 6, 4), "the nets are mended")
        self.assertEqual((p.u32(0x4D8BF8 + 8 * 5), p.u32(0x4D8BFC + 8 * 5)), (5, NOW))
        s.apply(Event(puzzles=[(6, 1)]))
        self.assertEqual([c[1] for c in s.calls[0x46D610]], [0x14, 0x15, 0x16, 0x17])
        self.assertEqual((p.u32(0x4D8724), s.calls[0x433D80]), (3, [[0x4D8720]]))
        r = s.apply(Event(puzzles=[(6, 0)]))[1]
        self.assertEqual((r["refused"], p.u32(0x4D8BF8 + 8 * 6)), (1, 1), "The Cooking Pit stays")
        s.apply(Event(puzzles=[(1, 0), (5, 0)]))
        self.assertEqual([c[1] for c in s.calls[0x438710]], [1, 5])
        self.assertEqual((p.u32(0x4D8BF8 + 8), p.u32(0x4D8BFC + 8)), (0, 0))
        self.assertEqual(s.calls[0x46D090], [[0x705148]], "the terrain after the stream")
        calls = len(s.calls[0x438A30])
        s.apply(Event(puzzles=[(11, 1)]))
        self.assertEqual(len(s.calls[0x438A30]), calls, "already solved: no second completion")

    def test_new_believers(self):
        if not have_stock("vv5"):
            self.skipTest("no stock executable")
        s = story("vv5")
        p = s.proc
        record(s, 0x43AF80, 4, also=self._advance(s, 0x51E008, 0x51DF30))
        record(s, 0x43AC10, 4, also=lambda q: q.put32(0x51E008 + 8 * q.arg(0), 0))
        p.stub(0x41ED40, lambda q: (NOW + 1, 0))
        for i in range(26):
            p.put32(0x51DF30 + 4 * i, 2000 if 19 <= i <= 24 else 2 if i == 10 else 1)
        idx = {name: puzzle_index("vv5", name) for name in (
            "The Prison Break", "The Hungry Totem", "Hut 1 (not on the Puzzles screen)",
            "The nursery school building", "The Nursery School (the milestone, not on the Puzzles screen)",
            "The Lake")}
        s.apply(Event(puzzles=[(idx["The Prison Break"], 1), (idx["The Hungry Totem"], 1),
                               (idx["The Lake"], 1)]))
        self.assertEqual((p.u32(0x51E008 + 16), p.u32(0x51E00C + 16)), (1, NOW + 1), "written directly")
        self.assertEqual([c[1] for c in s.calls[0x43AF80]], [3, 10])
        self.assertEqual((p.u32(0x51E008 + 80), p.u32(0x51E00C + 80)), (2, NOW))
        p.write(0x51DCD8 + 0x30, b"\1")                  # a builder is part way through hut 1
        r = s.apply(Event(puzzles=[(idx["Hut 1 (not on the Puzzles screen)"], 1)]))[1]
        self.assertEqual(r["refused"], 1)
        p.write(0x51DCD8 + 0x30, b"\0")
        r = s.apply(Event(puzzles=[(idx["The Nursery School (the milestone, not on the Puzzles screen)"], 1)]))[1]
        self.assertEqual(r["refused"], 1, "the milestone needs its building")
        s.apply(Event(puzzles=[(idx["The nursery school building"], 1)]))
        s.apply(Event(puzzles=[(idx["The Nursery School (the milestone, not on the Puzzles screen)"], 1)]))
        self.assertEqual(p.u32(0x51E008), 1)
        r = s.apply(Event(puzzles=[(idx["The nursery school building"], 0)]))[1]
        self.assertEqual(r["refused"], 1, "the building stays while its milestone is solved")
        s.apply(Event(puzzles=[(idx["The Hungry Totem"], 0), (idx["The Prison Break"], 0)]))
        self.assertEqual([c[1] for c in s.calls[0x43AC10]], [3, 2])
        self.assertEqual((p.u32(0x51E008 + 24), p.u32(0x51E00C + 24)), (0, 0))
        r = s.apply(Event(puzzles=[(idx["The Lake"], 0)]))[1]
        self.assertEqual(r["refused"], 1)

    def test_the_heathen_puzzles_and_the_farm_are_never_offered(self):
        source = base.ADAPTER_SOURCES["vv5"].read_text(encoding="utf-8")
        for name in ("The Sick Heathen", "The Heathen Builder", "The Heathen Scientist", "The Heathen Chief",
                     "The Heathen Parent", "The Hydroponic Farm", "The Last Heathen"):
            with self.subTest(name=name):
                with self.assertRaises(ValueError):
                    puzzle_index("vv5", name)
        table = source[source.index("static const c5_puzzle C5_PUZZLES[] = {"):]
        ids = [int(x) for x in __import__("re").findall(r"\{ (\d+),", table[:table.index("};")])]
        self.assertFalse({1, 5, 9, 13, 16, 17, 18, 25} & set(ids))


# ---------------------------------------------------------------------------
# D: special statuses
# ---------------------------------------------------------------------------

@emulated
class StatusTests(unittest.TestCase):
    def test_a_golden_child_appears_as_the_puzzle_makes_him(self):
        if not have_stock("vv1"):
            self.skipTest("no stock executable")
        for mode in MODES:
            s = story("vv1", mode)
            w = s.village.world
            p = s.proc
            p.put32(w + 0x9E1C, 0)
            p.stub(0x402F70, lambda q: (7 * 3600, 0))
            ok, r, _ = s.apply(Event(village=0b1000))
            with self.subTest(mode=mode):
                self.assertEqual(s.calls[0x43C350][0][1:], [0xC7, 0, 0, 0, 0x28])
                child = s.creations[0][0]
                self.assertEqual(s.village.i32(child, 0x340), 7 * 3600)
                self.assertEqual((p.read(w + 0xA008, 1), p.u32(w + 0x9E80)), (b"\1", 7))
                p.put32(w + 0x9E80, 3)
                s.apply(Event(village=0b1000))
                self.assertEqual(p.u32(w + 0x9E80), 3, "a second one leaves the puzzle's hour")
                s.room[0] = False
                ok, r, _ = s.apply(Event(village=0b1000))
                self.assertEqual((r["refused"], len(s.calls[0x43C350])), (1, 2), "no room, no child")

    def test_a_golden_child_from_the_event_is_a_custom_island_event_arrival(self):
        """The owner's v1.35.58 preview: Okwui, the Golden Child this event made,
        was logged "How: unknown" -- the event never told Cause of Death, which
        names a creator call it does not know "unknown"."""
        if not have_stock("vv1"):
            self.skipTest("no stock executable")
        for mode in MODES:
            s = story("vv1", mode)
            p = s.proc
            told = []
            export = p.alloc(0x10)
            p.api_handlers["GetModuleHandleA"] = lambda q: (
                0x73000000 if q.cstring(q.arg(0)) == "VVFP Cause of Death.dll" else 0, 4)
            p.api_handlers["GetProcAddress"] = lambda q: (
                export if q.cstring(q.arg(1)) == "VvfpCauseArrivedBy" else 0, 8)

            def arrived(q):
                told.append((q.arg(0), q.arg(1), q.cstring(q.arg(2))))
                return 0, 12
            p.stub(export, arrived)
            p.api_handlers["GetSystemTimeAsFileTime"] = lambda q: (q.write(q.arg(0), bytes(8)) or 0, 4)
            ok, r, _ = s.apply(Event(village=0b1000))
            with self.subTest(mode=mode):
                child = s.creations[0][0]
                self.assertEqual(told, [(1, child, "Custom Island Event")])
                s.room[0] = False
                s.apply(Event(village=0b1000))
                self.assertEqual(len(told), 1, "no child, nobody told")

    def test_a_tribal_chief_is_robed_by_the_games_own_routine(self):
        if not have_stock("vv3"):
            self.skipTest("no stock executable")
        s = story("vv3")
        v = s.village
        p = s.proc
        robed = []

        def robe(q):
            r = q.arg(0)
            q.write(r + 0xE80, b"\1")
            robed.append(r)
        record(s, 0x45FBC0, 4, also=robe)
        record(s, 0x435990, 4)
        v.put(1, sex="m", years=40, name="Chief")
        v.put(2, sex="m", years=30, name="Next")
        v.put(3, sex="f", years=10, name="Child")
        ok, r, _ = s.apply(Event(changes=[s.change(1, status=0)]))
        self.assertEqual((robed, s.calls[0x435990]), ([v.record(1)], [[0x594990, 0]]))
        self.assertEqual(s.calls[0x45FBC0][0][0], 0x59E110)
        ok, r, _ = s.apply(Event(changes=[s.change(2, status=0)]))
        self.assertEqual((r["refused"], v.byte(2, 0xE80)), (1, 0), "refused while a chief lives")
        ok, r, _ = s.apply(Event(changes=[s.change(2, status=1)]))
        self.assertEqual((r["refused"], v.byte(1, 0xE80), v.byte(2, 0xE80)), (0, 0, 1), "the old chief steps down")
        ok, r, _ = s.apply(Event(changes=[s.change(3, status=1)]))
        self.assertEqual((r["refused"], v.byte(2, 0xE80), v.byte(3, 0xE80)), (0, 0, 1),
                         "a child is robed too (the owner: children are chiefs in the game itself)")

    def test_heathen_masks_for_anyone(self):
        """The owner (2026-10-06): a believer is made a Heathen first, and a
        puzzle's own Heathen takes a mask too, at the player's own risk."""
        if not have_stock("vv5"):
            self.skipTest("no stock executable")
        s = story("vv5")
        v = s.village
        v.put(1, sex="m", years=30, name="Heathen", faction=1)
        v.put(2, sex="m", years=30, name="Believer")
        v.put(3, sex="f", years=30, name="Mommy", faction=1)
        s.proc.put32(v.record(3) + 0x1CFC, 0x11)
        for status, bytes_ in ((3, (1, 0)), (4, (0, 1)), (2, (0, 0))):
            ok, r, _ = s.apply(Event(changes=[s.change(1, status=status)]))
            self.assertEqual((v.byte(1, 0x1CED), v.byte(1, 0x1CEE), r["refused"]), bytes_ + (0,))
        s.proc.stub(0x4669E0, lambda q: (q.write(q.reg("ecx") + 0x1CEC, b"\1"), 0)[1:] and (0, 0))
        ok, r, _ = s.apply(Event(changes=[s.change(2, status=3), s.change(3, status=4)]))
        self.assertEqual(r["refused"], 0)
        self.assertEqual((v.byte(2, 0x1CEC), v.byte(2, 0x1CED)), (1, 1), "the believer: an orange Heathen")
        self.assertEqual((v.byte(3, 0x1CEE), v.i32(3, 0x1CFC)), (1, 0), "the Mommy: a red Heathen now")

    def test_new_heathens_come_from_the_games_heathen_creator(self):
        if not have_stock("vv5"):
            self.skipTest("no stock executable")
        for mode in MODES:
            s = story("vv5", mode)

            def heathen(q):
                args = [q.arg(i) for i in range(9)]
                s.calls.setdefault(0x46FD20, []).append([q.reg("ecx")] + args)
                index = s._create(1 if args[3] == 1 else 0, args[4])
                q.write(s.village.record(index) + 0x1CEC, b"\1")
                return index, 0x24
            s.proc.stub(0x46FD20, heathen)
            ok, r, _ = s.apply(Event(spawns=[Spawn(count=2, sex=1, age=300, faction=1),
                                             Spawn(count=1, sex=2, age=300, faction=0)]))
            with self.subTest(mode=mode):
                self.assertEqual([c[1:] for c in s.calls[0x46FD20]],
                                 [[1, 0, 0, 0, 300, 0, 0, 0, 0xFFFFFFC9]] * 2)
                self.assertEqual(s.calls[0x46FD20][0][0], 0x554148)
                self.assertEqual(len(s.calls[0x471E20]), 1, "a believer from the believer creator")
                s.room[0] = False
                ok, r, _ = s.apply(Event(spawns=[Spawn(count=1, sex=1, age=300, faction=1)]))
                self.assertEqual((r["born"], r["no_room_spawns"], len(s.calls[0x46FD20])), (0, 1, 2))


# ---------------------------------------------------------------------------
# E: pregnancy -- none, a different number of babies, the father
# ---------------------------------------------------------------------------

@emulated
class PregnancyAdditionTests(unittest.TestCase):
    def _pregnant(self, s, i, litter_field):
        v = s.village
        on, litter = PREGNANT[s.game]
        v.put(i, sex="f", years=30, name="Mother")
        s.proc.put32(v.record(i) + on, 400)
        s.proc.put32(v.record(i) + litter, litter_field)
        return v.record(i)

    def test_zero_babies_ends_the_pregnancy_and_leaves_the_counters(self):
        counters = {"vv1": None, "vv2": None, "vv3": 0x5824A8, "vv4": 0x4D6DE8, "vv5": 0x51D360}
        for game in GAMES:
            if not have_stock(game):
                continue
            s = story(game)
            record(s, *STOP[game])
            r_ = self._pregnant(s, 2, 3)
            on, litter = PREGNANT[game]
            made = counters[game]
            if made is None:
                made = s.village.world + (0x9E24 if game == "vv1" else 0x2E500)
            s.proc.put32(made, 9)
            ok, r, _ = s.apply(Event(changes=[s.change(2, litter=-1)]))
            with self.subTest(game=game):
                self.assertEqual((r["refused"], s.proc.u32(r_ + on), s.proc.u32(r_ + litter)), (0, 0, 0))
                self.assertEqual(s.proc.u32(made), 9, "Babies Made is left as counted")
                if game == "vv1":
                    self.assertEqual(s.proc.u32(r_ + 0x3C), 0x13)
                if game == "vv2":
                    self.assertEqual(s.proc.u32(r_ + 0x44), 0x1A)
                if game != "vv2":
                    self.assertIn(STOP[game][0], s.calls)
                ok, r, _ = s.apply(Event(changes=[s.change(2, litter=-1)]))
                self.assertEqual(r["refused"], 1, "nobody to end")

    def test_an_existing_pregnancy_changes_its_babies_each_only_with_room(self):
        single = {"vv1": 0, "vv2": 0, "vv3": 1, "vv4": 1, "vv5": 1}
        for game in GAMES:
            if not have_stock(game):
                continue
            for mode in MODES:
                s = story(game, mode)
                r_ = self._pregnant(s, 2, single[game])
                on, litter = PREGNANT[game]
                with self.subTest(game=game, mode=mode):
                    ok, r, _ = s.apply(Event(changes=[s.change(2, litter=3)]))
                    self.assertEqual((r["conceived"], s.proc.u32(r_ + litter)), (2, 3))
                    ok, r, _ = s.apply(Event(changes=[s.change(2, litter=1)]))
                    self.assertEqual((r["conceived"], s.proc.u32(r_ + litter)), (0, single[game]))
                    s.room[0] = False
                    ok, r, _ = s.apply(Event(changes=[s.change(2, litter=2)]))
                    self.assertEqual((r["conceived"], r["no_room_babies"], s.proc.u32(r_ + litter)),
                                     (0, 1, single[game]))
                    self.assertNotEqual(s.proc.u32(r_ + on), 0)

    def test_the_unborn_babys_father(self):
        fields = {"vv2": (0x5C0, 0x1C, 0x5E0, 0x5DC), "vv3": (0xE48, 0x18, 0xE68, 0xE64),
                  "vv4": (0x1C10, 0x18, 0x1C30, 0x1C2C), "vv5": (0x1C10, 0x18, 0x1C30, 0x1C2C)}
        for game, (name, cap, head, body) in fields.items():
            if not have_stock(game):
                continue
            s = story(game)
            r_ = self._pregnant(s, 2, 0)
            s.village.put(3, sex="f", years=30, name="NotExpecting")
            before = s.proc.read(r_, 0x2000)
            ok, r, _ = s.apply(Event(changes=[
                s.change(2, unborn_set=1, unborn_name="Makoa", unborn_head=7, unborn_body=9),
                s.change(3, unborn_set=1, unborn_name="Nobody")]))
            with self.subTest(game=game):
                self.assertEqual(r["refused"], 1, "a villager not expecting has no unborn baby")
                self.assertEqual(s.proc.read(r_ + name, cap), b"Makoa" + bytes(cap - 5))
                self.assertEqual((s.village.i32(2, head), s.village.i32(2, body)), (7, 9))
                after = s.proc.read(r_, 0x2000)
                changed = {k for k in range(0x2000) if before[k] != after[k]}
                self.assertTrue(changed <= set(range(name, name + cap)) | set(range(head, head + 4))
                                | set(range(body, body + 4)))
                ok, r, _ = s.apply(Event(changes=[s.change(2, unborn_set=1, unborn_head=30)]))
                self.assertEqual((r["refused"], s.village.i32(2, head)), (1, 7), "head out of range")

    def test_a_golden_child_carries_and_fathers_at_the_players_own_risk(self):
        """Stock never does it; the owner allows it (the dialog warns), the
        delivery making another Golden Child (0x42EF39)."""
        if not have_stock("vv1"):
            self.skipTest("no stock executable")
        s = story("vv1")
        record(s, 0x439470, 4)
        v = s.village
        v.put(2, sex="f", years=30, name="Mother")
        v.put(3, sex="m", years=30, name="Golden")
        s.proc.put32(v.record(3) + 0x36C, 0xC7)
        ok, r, _ = s.apply(Event(changes=[s.change(2, litter=1, father=3,
                                                   father_fingerprint=v.identity(3))]))
        self.assertEqual((r["conceived"], r["refused"]), (1, 0))
        self.assertNotEqual(v.i32(2, 0x358), 0)
        self.assertEqual(v.i32(2, 0x394), 0xC7, "the father's family: the delivery makes a Golden Child")
        v.put(4, sex="f", years=30, name="GoldenToo")
        s.proc.put32(v.record(4) + 0x36C, 0xC7)
        ok, r, _ = s.apply(Event(changes=[s.change(4, litter=1)]))
        self.assertEqual((r["conceived"], r["refused"]), (1, 0))


# ---------------------------------------------------------------------------
# G: revive
# ---------------------------------------------------------------------------

REVIVE = {
    # health, sick (offset, size), last-update time, clock routine(s)
    "vv1": dict(health=0x344, sick=0x354, stamp=0x340),
    "vv2": dict(health=0x52C, sick=0x53C, stamp=0x528),
    "vv3": dict(health=0xE78, sick=0xE89, stamp=0xE70),
    "vv4": dict(health=0x1C40, sick=0x1C48, stamp=0x1C38),
    "vv5": dict(health=0x1C40, sick=0x1C48, stamp=0x1C38),
}


def stub_clock(s):
    g = s.game
    if g == "vv1":
        s.proc.stub(0x402F70, lambda q: (NOW, 0))
    elif g == "vv2":
        s.proc.stub(0x403200, lambda q: (NOW, 0))
    else:
        world = s.proc.alloc(0x100)
        getter(s, {"vv3": 0x428B60, "vv4": 0x41FE70, "vv5": 0x425950}[g], world)
        clock = {"vv3": 0x403330, "vv4": 0x403750, "vv5": 0x4036E0}[g]
        s.proc.stub(clock, lambda q: (NOW if q.reg("ecx") == world else 0, 0))
    if g in ("vv3", "vv4", "vv5"):
        arbiter = {"vv3": 0x462670, "vv4": 0x46AF00, "vv5": 0x4758B0}[g]

        def arbitrate(q):
            block = q.reg("ecx")
            q.put32(block + 0xC, q.arg(0))
            q.put32(block + 0x10, q.arg(1) & 0xFFFFFFFF)
        record(s, arbiter, 8, also=arbitrate)


@emulated
class ReviveTests(unittest.TestCase):
    def _skeleton(self, s, i, name="Bones"):
        v = s.village
        v.put(i, sex="f", years=30, name=name, health=0)
        off = REVIVE[s.game]["sick"]
        s.proc.write(v.record(i) + off, b"\1")
        return (i, v.identity(i), 60, 1)

    def test_a_skeleton_chosen_in_villager_changes_comes_back_then_changes(self):
        """The owner (2026-10-06): "All Skeletons" -- a chosen skeleton is
        revived first (health 100, cured), then gets its changes."""
        for game in GAMES:
            if not have_stock(game):
                continue
            s = story(game)
            stub_clock(s)
            record(s, *STOP[game])
            v = s.village
            i, ident, _, _ = self._skeleton(s, 4)
            change = s.change(4, head=7)            # the identity the dialog takes from the body
            ok, r, _ = s.apply(Event(revives=[(i, ident, 100, 1)], changes=[change]))
            with self.subTest(game=game):
                self.assertEqual((r["revived"], r["skipped"], r["changed"]), (1, 0, 1))
                self.assertEqual(v.i32(4, REVIVE[game]["health"]), 100)
                self.assertEqual(v.i32(4, base.LAYOUTS[game]["head"]), 7, "changed after the revive")

    def test_a_skeleton_comes_back_with_the_clock_and_the_games_own_routines(self):
        for game in GAMES:
            if not have_stock(game):
                continue
            for mode in MODES:
                s = story(game, mode)
                stub_clock(s)
                record(s, *STOP[game])
                f = REVIVE[game]
                rev = self._skeleton(s, 4)
                ok, r, text = s.apply(Event(revives=[rev]))
                v = s.village
                with self.subTest(game=game, mode=mode):
                    self.assertEqual((r["revived"], r["refused"], r["skipped"]), (1, 0, 0))
                    self.assertEqual(v.i32(4, f["health"]), 60)
                    self.assertEqual(v.proc.u32(v.record(4) + f["stamp"]), NOW,
                                     "the last-update time is now: no aging for the time dead")
                    self.assertEqual(v.byte(4, f["sick"]), 0)
                    self.assertIn(STOP[game][0], s.calls)
                    if game in ("vv3", "vv4", "vv5"):
                        self.assertEqual(i32(s.proc, v.record(4) + f["health"] + 4), -1,
                                         "the cause of death back to the living value")
                    # stale: the record now holds somebody else
                    rev2 = self._skeleton(s, 5)
                    v.put(5, sex="m", years=50, name="Other", health=0)
                    ok, r, _ = s.apply(Event(revives=[rev2]))
                    self.assertEqual((r["revived"], r["skipped"]), (0, 1))
                    # a full village: the body keeps its own record, so the
                    # revive needs no room (the owner, 2026-10-06)
                    rev3 = self._skeleton(s, 6)
                    s.room[0] = False
                    ok, r, text = s.apply(Event(revives=[rev3]))
                    self.assertEqual((r["revived"], r["no_room_revives"], v.i32(6, f["health"])), (1, 0, 60))

    def test_without_the_cure_the_sickness_stays_and_alive_or_gone_is_never_revived(self):
        for game in GAMES:
            if not have_stock(game):
                continue
            s = story(game)
            stub_clock(s)
            record(s, *STOP[game])
            i, ident, _, _ = self._skeleton(s, 4)
            ok, r, _ = s.apply(Event(revives=[(i, ident, 100, 0)]))
            v = s.village
            with self.subTest(game=game):
                self.assertEqual((r["revived"], v.byte(4, REVIVE[game]["sick"])), (1, 1))
                ok, r, _ = s.apply(Event(revives=[(i, v.identity(4), 100, 1)]))
                self.assertEqual((r["revived"], r["skipped"]), (0, 1), "alive now")
                j, ident_j, _, _ = self._skeleton(s, 7)
                active = base.LAYOUTS[game]["active"]
                s.proc.write(v.record(7) + active, b"\0")
                ok, r, _ = s.apply(Event(revives=[(j, ident_j, 100, 1)]))
                self.assertEqual((r["revived"], r["skipped"], v.i32(7, REVIVE[game]["health"])), (0, 1, 0),
                                 "a freed record is never written")
                ok, r, _ = s.apply(Event(revives=[(7, ident_j, 0, 1)]))
                self.assertEqual(r["revived"], 0)

    def test_look_alike_dead_records_are_never_revived(self):
        # (New Believers: a Heathen body is a body -- the Custom Island Event
        # can kill a Heathen -- so it is no look-alike.)
        cases = {"vv2": (0x558, 1), "vv4": (0x1CC7, 1)}
        for game, (off, value) in cases.items():
            if not have_stock(game):
                continue
            s = story(game)
            stub_clock(s)
            record(s, *STOP[game])
            i, _, _, _ = self._skeleton(s, 4)
            s.proc.write(s.village.record(4) + off, bytes([value]))
            ok, r, _ = s.apply(Event(revives=[(i, s.village.identity(4), 100, 1)]))
            with self.subTest(game=game):
                self.assertEqual((r["revived"], r["skipped"]), (0, 1))

    def test_new_believers_waits_for_its_own_reanimate(self):
        if not have_stock("vv5"):
            self.skipTest("no stock executable")
        s = story("vv5")
        stub_clock(s)
        record(s, *STOP["vv5"])
        rev = self._skeleton(s, 4)
        s.village.put(9, sex="m", years=30, name="Rising")
        s.proc.write(s.village.record(9) + 0x1CE1, b"\1")
        ok, r, _ = s.apply(Event(revives=[rev]))
        self.assertEqual((r["revived"], r["refused"]), (0, 1))

    def test_the_secret_city_brings_a_dead_chief_back_even_with_a_living_one(self):
        """The owner (2026-10-06): allowed, the revive dialog warning "Do this at
        your own risk"."""
        if not have_stock("vv3"):
            self.skipTest("no stock executable")
        s = story("vv3")
        stub_clock(s)
        record(s, *STOP["vv3"])
        rev = self._skeleton(s, 4)
        s.proc.write(s.village.record(4) + 0xE80, b"\1")
        s.village.put(5, sex="m", years=40, name="NewChief")
        s.proc.write(s.village.record(5) + 0xE80, b"\1")
        ok, r, _ = s.apply(Event(revives=[rev]))
        self.assertEqual((r["revived"], r["refused"]), (1, 0))
        self.assertEqual(s.village.byte(4, 0xE80), 1, "a chief again")


@emulated
class TitleSurvivesDeathTests(unittest.TestCase):
    """story_titles.inc: a title stays while its villager is a skeleton (a
    revive brings them back with it) and goes once the record is freed or
    holds someone else."""

    def test_title_kept_through_death_and_dropped_when_the_record_is_freed(self):
        from story_custom_fixtures import MemoryFiles

        for game in GAMES:
            if not have_stock(game):
                continue
            s = story(game)
            p = s.proc
            MemoryFiles(p)
            path = r"C:\Save\Custom Titles - Save 1.dat"
            p.write(base.SCRATCH, path.encode() + b"\0")
            p.export("VvfpStoryProbeTitlesLoaded", s.n, 1, base.SCRATCH)
            v = s.village
            v.put(2, sex="f", years=30, name="Hina")
            p.write(base.SCRATCH + 0x100, b"Storyteller\0")
            p.export("VvfpStoryProbeTitleSet", s.n, 2, base.SCRATCH + 0x100)
            tick = [10_000]

            def sweep():
                tick[0] += 5000
                p.tick = tick[0]
                p.export("VvfpStoryInstall", s.n)
                return p.export("VvfpStoryProbeTitleCount")
            with self.subTest(game=game):
                self.assertEqual(sweep(), 1)
                p.put32(v.record(2) + base.LAYOUTS[game]["health"], 0)     # dies
                self.assertEqual(sweep(), 1, "a skeleton keeps the title")
                p.write(v.record(2) + base.LAYOUTS[game]["active"], b"\0")  # buried / gone
                self.assertEqual(sweep(), 0)


if __name__ == "__main__":
    unittest.main()
