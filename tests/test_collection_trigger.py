"""When the new island events come (native/vvfp_story_upgrades/story_collection.inc; the owner, 2026-11-15).

EMULATED (unicorn, each game's executable as the patcher renders it, the TEST build of "VVFP Story Upgrades.dll";
tests/story_emulator.py, the villagers laid out by tests/story_custom_fixtures.py):

  * THE DECISION: once for each natural island event, 3 seconds (SC_WINDOW) or less before its island timer is due,
    with nothing armed or on its way and no God Power armed: never during the village's two opening events, never
    below 61 villagers, never in trouble; the game's own random routine passes 50 of 100 (SC_REPLACE_PERCENT) and a
    new event is armed in the natural one's place;
  * THE POPULATION the gate counts: the living villagers the game lists and the babies being carried (New Believers'
    believers only);
  * THE TROUBLE GUARD in every game on the game's own records: the stock rescue predicate (both sexes' rules, the
    population with the babies carried below 3), food below 10 a villager or none, half the village sick, fewer than
    6 villagers of 14 or more -- and New Believers' heathens never count;
  * THE CHOICE: every event equally likely across More Island Events and the collection (the Grand collection and
    the Companion Anthology, one manifest; the owner, 2026-11-14): one draw over all of them, each More Island Events
    event weight 1, each collection event its draw weight and a series one event's weight; a candidate that cannot
    be armed is left out and the draw made again; nothing armed when nothing can happen;
  * ONE FRAME AT A TIME through VvfpStoryInstall's own call (The Tree of Life, its clock stood in for): the decision
    arms an event and leaves the keeper's hand-over pending.

The live game is NOT exercised here.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))

import test_aspiring_adventurer as aa  # noqa: E402
import test_story_custom_island_event as sci  # noqa: E402

NEEDS = unittest.skipUnless(sci.HAVE_EMULATOR and sci.TEST_DLL.is_file() and aa.HAVE_STOCK,
                            "needs unicorn, pefile, the stock executables and the Story TEST build")

GAMES = (1, 2, 3, 4, 5)
REPLACE_PERCENT = 50
SC_NONE, SC_ARM = 0, 3
HOUR = 3600


def s32(v: int) -> int:
    return v - (1 << 32) if v >> 31 else v


class Roll:
    """The decision (VvfpStoryProbeCollectionStep) in one game's process."""

    def __init__(self, game: int):
        self.game = game
        self.story = sci.Story(f"vv{game}")
        self.p = self.story.proc
        self.io = self.p.alloc(16 * 4)
        self.p.export("VvfpStoryProbeCollectionReset")

    def rolls(self, *values: int) -> None:
        at = self.p.alloc(4 * max(1, len(values)))
        for k, v in enumerate(values):
            self.p.put32(at + 4 * k, v)
        self.p.export("VvfpStoryProbeSetRolls", at, len(values))

    def step(self, counter: int, now: int, natural: int, busy: int = 0, god: int = 0, trouble: int = 0,
             population: int = 80) -> dict:
        for k, v in enumerate((self.game, counter, busy, now, natural, god, trouble, population)):
            self.p.put32(self.io + 4 * k, v & 0xFFFFFFFF)
        self.p.export("VvfpStoryProbeCollectionStep", self.io)
        out = [s32(self.p.u32(self.io + 4 * k)) for k in range(8, 13)]
        return dict(action=out[0], decided=out[1], natural=out[2] & 0xFFFFFFFF, seen=out[4])


@NEEDS
class TheDecision(unittest.TestCase):
    def test_at_the_natural_event_half_the_time(self) -> None:
        for game in GAMES:
            with self.subTest(game=game):
                r = Roll(game)
                r.rolls(REPLACE_PERCENT - 1)
                self.assertEqual(r.step(5, 1000, 1003)["action"], SC_ARM)
                r = Roll(game)
                r.rolls(REPLACE_PERCENT)
                self.assertEqual(r.step(5, 1000, 1003)["action"], SC_NONE)

    def test_once_for_each_natural_time(self) -> None:
        r = Roll(4)
        r.rolls(0, 0)
        self.assertEqual(r.step(5, 1000, 1003)["action"], SC_ARM)
        self.assertEqual(r.step(5, 1001, 1003)["action"], SC_NONE)       # decided already
        self.assertEqual(r.step(6, 2000, 2002)["action"], SC_ARM)       # the next natural event

    def test_only_in_the_last_seconds(self) -> None:
        r = Roll(3)
        r.rolls(0)
        self.assertEqual(r.step(5, 1000, 1004)["action"], SC_NONE)
        self.assertEqual(r.step(5, 1000, 1000 - 1)["action"], SC_NONE)  # passed already
        self.assertEqual(r.step(5, 1001, 1004)["action"], SC_ARM)

    def test_never_while_anything_is_armed_or_a_god_power(self) -> None:
        r = Roll(5)
        r.rolls(0, 0)
        self.assertEqual(r.step(5, 1000, 1002, busy=1)["action"], SC_NONE)
        self.assertEqual(r.step(5, 1000, 1002, god=1)["action"], SC_NONE)
        self.assertEqual(r.step(5, 1000, 1002)["action"], SC_ARM)

    def test_never_an_opening_event(self) -> None:
        for counter, expected in ((0, SC_NONE), (1, SC_NONE), (2, SC_ARM)):
            with self.subTest(counter=counter):
                r = Roll(1)
                r.rolls(0)
                self.assertEqual(r.step(counter, 1000, 1002)["action"], expected)

    def test_never_below_61_villagers(self) -> None:
        for population, expected in ((60, SC_NONE), (61, SC_ARM)):
            with self.subTest(population=population):
                r = Roll(2)
                r.rolls(0)
                self.assertEqual(r.step(5, 1000, 1002, population=population)["action"], expected)

    def test_never_in_trouble(self) -> None:
        r = Roll(1)
        r.rolls(0)
        self.assertEqual(r.step(5, 1000, 1002, trouble=1)["action"], SC_NONE)

    def test_no_village_forgets(self) -> None:
        r = Roll(3)
        self.assertEqual(r.step(-1, 1001, 0)["seen"], -1)


@NEEDS
class ThePopulation(unittest.TestCase):
    def test_living_villagers_and_the_babies_carried(self) -> None:
        for game in GAMES:
            with self.subTest(game=game):
                st = sci.Story(f"vv{game}")
                for i in range(6):
                    st.village.put(i, sex="m" if i < 3 else "f", years=20 + i, name=f"V{i}")
                st.proc.put32(st.village.record(4) + st.village.L["pregnant"], 1)
                self.assertEqual(st.proc.export("VvfpStoryProbeCollectionPopulation", st.n, -1), 7)

    def test_new_believers_heathens_never_count(self) -> None:
        st = sci.Story("vv5")
        for i in range(6):
            st.village.put(i, sex="m" if i < 3 else "f", years=30, name=f"V{i}", faction=1 if i >= 4 else 0)
        self.assertEqual(st.proc.export("VvfpStoryProbeCollectionPopulation", st.n, -1), 4)


@NEEDS
class TheTroubleGuard(unittest.TestCase):
    """The game's own records, as the rescue rule and the guard read them."""

    def story(self, game: int, men: int = 4, women: int = 4, food: int = 1000):
        st = sci.Story(f"vv{game}")
        for i in range(men + women):
            st.village.put(i, sex="m" if i < men else "f", years=20 + i, name=f"V{i}")
        st.proc.put32(sci._food_tech(st)[0], food)
        return st

    def trouble(self, st) -> int:
        return st.proc.export("VvfpStoryProbeCollectionTrouble", st.n)

    def test_a_healthy_village_is_not_in_trouble(self) -> None:
        for game in GAMES:
            with self.subTest(game=game):
                self.assertEqual(self.trouble(self.story(game)), 0)

    def test_the_rescue_predicate(self) -> None:
        for game in GAMES:
            for men, women, expected in ((5, 2, 1), (5, 3, 0), (2, 5, 1), (3, 5, 0), (4, 4, 0), (6, 1, 1)):
                with self.subTest(game=game, men=men, women=women):
                    self.assertEqual(self.trouble(self.story(game, men, women)), expected)

    def test_low_food(self) -> None:
        for game in GAMES:
            with self.subTest(game=game):
                self.assertEqual(self.trouble(self.story(game, food=80)), 0)     # 8 villagers x 10
                self.assertEqual(self.trouble(self.story(game, food=79)), 1)
                self.assertEqual(self.trouble(self.story(game, food=0)), 1)

    def test_few_grown_villagers(self) -> None:
        for game in GAMES:
            with self.subTest(game=game):
                st = self.story(game, 3, 3)
                self.assertEqual(self.trouble(st), 0)                         # 6 of 14 or more
                st.village.put(5, sex="f", years=13, name="Kid")
                self.assertEqual(self.trouble(st), 1)

    def test_half_the_village_sick(self) -> None:
        sick = {1: (0x354, 4), 2: (0x53C, 4), 3: (0xE89, 1), 4: (0x1C48, 1), 5: (0x1C48, 1)}
        for game in GAMES:
            with self.subTest(game=game):
                st = self.story(game)
                off, size = sick[game]
                for i in range(3):
                    st.proc.write(st.village.record(i) + off, (1).to_bytes(size, "little"))
                self.assertEqual(self.trouble(st), 0)                         # 3 of 8
                st.proc.write(st.village.record(3) + off, (1).to_bytes(size, "little"))
                self.assertEqual(self.trouble(st), 1)                         # 4 of 8

    def test_new_believers_heathens_never_count(self) -> None:
        st = self.story(5, 4, 4)
        for i in range(4, 8):
            st.village.put(i, sex="f", years=30, name=f"H{i}", faction=1)  # the women are Heathens
        self.assertEqual(self.trouble(st), 1)                             # 4 believing men, no women


MANIFEST = "\n".join([
    "# id\ttitle\tgames\tweight\tseries\tcredit",
    "a_solo\tA Solo\t3,4\t1\t\tcredit a",
    "b_heavy\tB Heavy\t4\t3\t\tcredit b",
    "c_s1\tSeries One\t4\t1\tseries_x\tcredit c",
    "d_s2\tSeries Two\t4\t1\tseries_x\tcredit d",
    "e_other\tOther Game\t1\t1\t\tcredit e",
]) + "\n"


@NEEDS
class TheChoice(unittest.TestCase):
    def roll(self, more: list[int] | None = None, more_ok: int = 0, coll_ok: int = 0, manifest: str = MANIFEST):
        r = Roll(4)
        text = r.p.alloc(len(manifest) + 1)
        r.p.write(text, manifest.encode() + b"\0")
        r.p.export("VvfpStoryProbeCollectionManifest", text if manifest else 0, more_ok, coll_ok)
        if more is not None:
            self._fake_more(r, more)
        return r

    def _fake_more(self, r: Roll, possible: list[int]) -> None:
        """More Island Events installed in The Tree of Life with `possible` (1 / 0) for its registry entries."""
        p = r.p
        stubs = {n: p.alloc(16) for n in ("Installed", "Count", "Info")}
        p.stub(stubs["Installed"], lambda pr: (4, 0))
        p.stub(stubs["Count"], lambda pr: (len(possible), 0))

        def info(pr):
            k = pr.arg(0)
            pr.write(pr.arg(1), f"Event {k}\0".encode())
            pr.write(pr.arg(2), b"About it.\0")
            pr.write(pr.arg(3), b"two villagers\0")
            return possible[k], 20
        p.stub(stubs["Info"], info)
        prior_module, prior_proc = p.api_handlers.get("GetModuleHandleA"), p.api_handlers.get("GetProcAddress")
        fake = 0x0EA00000

        def module(pr):
            name = pr.cstring(pr.arg(0)) if pr.arg(0) else ""
            return (fake, 4) if name == "VVFP More Island Events.dll" else (prior_module(pr) if prior_module else (0, 4))

        def proc(pr):
            if pr.arg(0) == fake:
                return {"VvfpMoreIslandEventsInstalled": stubs["Installed"], "VvfpMoreIslandEventsPickCount":
                        stubs["Count"], "VvfpMoreIslandEventsPickInfo": stubs["Info"]}.get(pr.cstring(pr.arg(1)), 0), 8
            return prior_proc(pr) if prior_proc else (0, 8)
        p.api_handlers["GetModuleHandleA"] = module
        p.api_handlers["GetProcAddress"] = proc

    def choose(self, r: Roll) -> tuple[bool, list[int]]:
        trace = r.p.alloc(64 * 4)
        got = r.p.export("VvfpStoryProbeCollectionChoose", 4, trace, 64)
        return bool(got & 0x100), [r.p.u32(trace + 4 * k) for k in range(got & 0xFF)]

    def test_the_collection_alone_by_weight_and_series(self) -> None:
        # The Tree of Life's entries: a_solo 1, b_heavy 3, the series 1 (c_s1, d_s2): total 5.
        for draw, expected in ((0, 0), (1, 1), (3, 1), (4, 2)):
            with self.subTest(draw=draw):
                r = self.roll(coll_ok=0xF)
                r.rolls(draw, 0)
                armed, trace = self.choose(r)
                self.assertTrue(armed)
                self.assertEqual(trace, [0x10000 | expected])
        r = self.roll(coll_ok=0xF)
        r.rolls(4, 1)                                          # the series, then its second member
        self.assertEqual(self.choose(r), (True, [0x10000 | 3]))

    def test_other_games_entries_never_offered(self) -> None:
        r = self.roll(coll_ok=0xFF)
        for draw in range(5):
            r.rolls(draw, 0)
            armed, trace = self.choose(r)
            self.assertTrue(all((t & 0xFFFF) < 4 for t in trace))

    def test_a_candidate_that_cannot_be_armed_is_left_out(self) -> None:
        r = self.roll(coll_ok=0b0010)                          # only b_heavy arms
        r.rolls(0, 0, 0)
        armed, trace = self.choose(r)
        self.assertTrue(armed)
        self.assertEqual(trace, [0x10000 | 0, 0x10000 | 1])

    def test_nothing_armed_when_nothing_can_happen(self) -> None:
        r = self.roll(coll_ok=0)
        r.rolls(*([0] * 16))
        armed, trace = self.choose(r)
        self.assertFalse(armed)
        self.assertEqual(sorted(t & 0xFFFF for t in trace), [0, 1, 2, 3])   # every event tried once

    def test_every_event_equally_likely_across_the_sources(self) -> None:
        # More Island Events' possible entries 0 and 2 (weight 1 each) and the collection's a_solo 1, b_heavy 3, the
        # series 1: one draw over 2 + 5 = 7.  Draws 0-1 are More Island Events' (each refused here, as the emulated
        # registry cannot arm: then 1 + 5, then the collection's 5), 2-6 the collection's.
        for draw, expected in ((0, [0, 2, 0x10000 | 0]), (1, [2, 0, 0x10000 | 0]), (2, [0x10000 | 0]),
                               (3, [0x10000 | 1]), (5, [0x10000 | 1]), (6, [0x10000 | 2])):
            with self.subTest(draw=draw):
                r = self.roll(more=[1, 0, 1], more_ok=0, coll_ok=0xF)
                r.rolls(draw, 0, 0)
                armed, trace = self.choose(r)
                self.assertTrue(armed)
                self.assertEqual(trace, expected)
        # No draw between the sources first: a refused More Island Events event leaves 1 + 5, drawn again.
        r = self.roll(more=[1, 0, 1], more_ok=0, coll_ok=0xF)
        r.rolls(1, 1, 0)                                       # registry entry 2 (refused), then the collection's first
        armed, trace = self.choose(r)
        self.assertTrue(armed)
        self.assertEqual(trace, [2, 0x10000 | 0])
        r = self.roll(more=[1, 0, 1], more_ok=0, coll_ok=0xF)
        r.rolls(6, 1)                                          # the series, then its second member
        self.assertEqual(self.choose(r), (True, [0x10000 | 3]))

    def test_more_island_events_alone(self) -> None:
        r = self.roll(more=[1, 1], more_ok=0, coll_ok=0, manifest="")
        r.p.export("VvfpStoryProbeCollectionManifest", 0, 0, 0)
        r.rolls(1, 0)
        armed, trace = self.choose(r)
        self.assertFalse(armed)
        self.assertEqual(trace, [1, 0])                        # no collection: no source draw, then the other


@NEEDS
class OneFrameAtATime(unittest.TestCase):
    """The Tree of Life: its clock (0x403750) stood in for, its island timer world+0x170E0, the count 0x4D6E04."""

    def test_a_natural_event_replaced_through_the_frame_hook(self) -> None:
        st = sci.Story("vv4")
        p = st.proc
        for i in range(8):
            st.village.put(i, sex="m" if i < 4 else "f", years=25, name=f"V{i}")
        p.put32(sci._food_tech(st)[0], 1000)
        clock = [10_000]
        p.stub(0x403750, lambda pr: (clock[0], 0))
        text = p.alloc(len(MANIFEST) + 1)
        p.write(text, MANIFEST.encode() + b"\0")
        p.export("VvfpStoryProbeCollectionReset")
        p.export("VvfpStoryProbeCollectionManifest", text, 0, 0b0001)
        p.export("VvfpStoryProbeCollectionPopulation", 4, 61)  # 61 villagers for the gate
        world = st.village.world
        counter = sci.EVENT_COUNTER_GLOBAL["vv4"]
        p.put32(counter, 5)
        p.put32(world + 0x170E0, clock[0] + 600)
        p.export("VvfpStoryProbeCollectionTick", 4)            # ten minutes before the natural event: nothing
        state = p.alloc(7 * 4)
        p.export("VvfpStoryProbeCollectionState", state)
        self.assertEqual(p.u32(state), 0)
        at = p.alloc(8)
        p.put32(at, 0)
        p.put32(at + 4, 0)
        p.export("VvfpStoryProbeSetRolls", at, 2)
        clock[0] += 598                                        # two seconds before it
        p.export("VvfpStoryProbeCollectionTick", 4)
        p.export("VvfpStoryProbeCollectionState", state)
        self.assertEqual(p.u32(state), 1)                      # decided
        self.assertEqual(p.u32(state + 8), 10_000 + 600)       # for this natural time
        p.export("VvfpStoryProbeCollectionPopulation", 4, -1)


@NEEDS
class LivingRows(unittest.TestCase):
    """The Living Event Engine's rows in the draw (story_living.inc; tests/test_living_runtime.py has the rest)."""

    def test_living_rows_without_their_pack_are_never_drawn(self) -> None:
        import test_living_runtime as lr
        run = lr.Living("vv4")
        run.manifest()
        run.p.export("VvfpStoryProbeLivingPack", 0, 0)
        run.rolls([0] * 64)
        self.assertEqual(run.choose(), (False, []))          # every living row left out before the draw

    def test_a_living_category_is_one_series(self) -> None:
        """Six living rows in five categories: five series of weight 1 (no history: no mood bias); roll 4 is the
        TRA series, whose two rows are equally likely (the member roll 1: its second row)."""
        import test_living_runtime as lr
        run = lr.Living("vv4")
        run.manifest()
        run.rolls([4, 1] + [0] * 62)
        armed, trace = run.choose()
        self.assertTrue(armed)
        self.assertEqual(trace, [5])                          # living_mc_tra_13
        run.idle()
        # Now a serious row was armed: warm and social weigh 2 (per, cel, art, odd), the TRA series 1 (its row
        # left): 9 in all, and roll 5 is Art.
        run.rolls([5] + [0] * 63)
        armed, trace = run.choose()
        self.assertEqual(trace[0], 2)

    def test_a_series_whose_rows_cannot_be_cast_is_passed_over(self) -> None:
        """Art, Knowledge, and Craft (row 2) has no variant four adults can play: the draw is made again."""
        import test_living_runtime as lr
        run = lr.Living("vv4")
        run.manifest()
        run.rolls([2, 0] + [0] * 62)
        armed, trace = run.choose()
        self.assertTrue(armed)
        self.assertEqual(trace[:2], [2, 0])


if __name__ == "__main__":
    unittest.main()
