"""The Isola Grand Event Collection's separate rare roll (native/vvfp_story_upgrades/story_collection.inc).

EMULATED (unicorn, each game's executable as the patcher renders it, the TEST build of "VVFP Story Upgrades.dll";
tests/story_emulator.py, the villagers laid out by tests/story_custom_fixtures.py):

  * THE EDGE: a roll is made only when the Island Events Seen count went up while, in the frame before, nothing was
    armed or on its way (the game's own natural event) -- never after a bought, picked or custom one, never during a
    village's two opening events, never on the first frame of a village (nothing seen yet);
  * THE ROLL: probability SC_P_PERCENT per game (A New Home 30, The Lost Children 25, the later three 20), at the
    boundary of the game's own roll; the due time between now and the natural next event, 30% to 70% of the way;
  * AT DUE: it waits while anything is armed, while the natural event is 60 seconds away or less, while New
    Believers' God Power is armed; a natural event that comes first takes its place (cancelled); its natural time
    passed cancels it; the trouble guard cancels it, never delays it;
  * THE TROUBLE GUARD in every game on the game's own records: the stock rescue predicate (both sexes' rules, the
    population with the babies carried below 3), food below 10 a villager or none, half the village sick, fewer than
    6 villagers of 14 or more -- and New Believers' heathens never count;
  * THE CHOICE: More Island Events and the collection 1:1 when both have candidates; within the collection each event
    its draw weight and a series one event's weight; a candidate that cannot be armed is left out and the draw made
    again; nothing armed when nothing can happen;
  * THE SAVE'S FILE: the due roll is kept (in memory in the TEST build) and deleted once delivered or cancelled;
  * ONE FRAME AT A TIME through VvfpStoryInstall's own call (The Tree of Life, its clock stood in for).

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

P_PERCENT = {1: 30, 2: 25, 3: 20, 4: 20, 5: 20}
SC_NONE, SC_SAVE, SC_CANCEL, SC_ARM = 0, 1, 2, 3
HOUR = 3600


def s32(v: int) -> int:
    return v - (1 << 32) if v >> 31 else v


class Roll:
    """The roll's state machine (VvfpStoryProbeCollectionStep) in one game's process."""

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

    def step(self, counter: int, now: int, natural: int, busy: int = 0, god: int = 0, trouble: int = 0) -> dict:
        for k, v in enumerate((self.game, counter, busy, now, natural, god, trouble)):
            self.p.put32(self.io + 4 * k, v & 0xFFFFFFFF)
        self.p.export("VvfpStoryProbeCollectionStep", self.io)
        out = [s32(self.p.u32(self.io + 4 * k)) for k in range(8, 13)]
        return dict(action=out[0], due_set=out[1], due=out[2] & 0xFFFFFFFF, natural=out[3] & 0xFFFFFFFF, seen=out[4])

    def natural_event(self, counter: int, now: int, natural: int, **kw) -> dict:
        """A frame before (count `counter - 1`, nothing armed), then the frame the count went up."""
        self.step(counter - 1, now - 1, now, **{k: v for k, v in kw.items() if k in ("trouble",)})
        return self.step(counter, now, natural, **kw)


@NEEDS
class TheEdge(unittest.TestCase):
    def test_a_natural_event_rolls_once(self) -> None:
        r = Roll(4)
        r.rolls(0, 0)                                          # under p; the due point's draw 0: 30% of the gap
        out = r.natural_event(5, 1000, 1000 + 10 * HOUR)
        self.assertEqual(out["action"], SC_SAVE)
        self.assertEqual(out["due"], 1000 + 10 * HOUR * 300 // 1000)
        self.assertEqual(out["natural"], 1000 + 10 * HOUR)
        self.assertEqual(r.step(5, 1001, 1000 + 10 * HOUR)["action"], SC_NONE)   # the same count: no second roll

    def test_never_after_an_armed_event(self) -> None:
        r = Roll(3)
        r.rolls(0, 0)
        r.step(4, 999, 1000, busy=1)                           # a pick (or bought / custom event) on its way
        out = r.step(5, 1000, 1000 + 10 * HOUR)
        self.assertEqual(out["action"], SC_NONE)
        self.assertEqual(out["due_set"], 0)

    def test_never_on_a_villages_first_frame(self) -> None:
        r = Roll(3)
        r.rolls(0, 0)
        self.assertEqual(r.step(9, 1000, 1000 + 10 * HOUR)["action"], SC_NONE)   # nothing seen before
        self.assertEqual(r.step(-1, 1001, 0)["seen"], -1)                         # no village: forgotten

    def test_never_during_the_opening_events(self) -> None:
        for counter in (1, 2):
            with self.subTest(counter=counter):
                r = Roll(5)
                r.rolls(0, 0)
                out = r.natural_event(counter, 1000, 1000 + 8 * HOUR)
                self.assertEqual(out["action"], SC_SAVE if counter >= 2 else SC_NONE)

    def test_the_trouble_guard_means_no_roll(self) -> None:
        r = Roll(1)
        r.rolls(0, 0)
        self.assertEqual(r.natural_event(5, 1000, 1000 + 12 * HOUR, trouble=1)["action"], SC_NONE)


@NEEDS
class TheRoll(unittest.TestCase):
    def test_each_games_probability(self) -> None:
        for game, p in P_PERCENT.items():
            with self.subTest(game=game):
                r = Roll(game)
                r.rolls(p - 1, 0)
                self.assertEqual(r.natural_event(5, 1000, 1000 + 10 * HOUR)["action"], SC_SAVE)
                r = Roll(game)
                r.rolls(p, 0)
                self.assertEqual(r.natural_event(5, 1000, 1000 + 10 * HOUR)["action"], SC_NONE)

    def test_due_between_now_and_the_natural_event(self) -> None:
        for frac_draw, expected in ((0, 300), (200, 500), (400, 700)):
            with self.subTest(frac_draw=frac_draw):
                r = Roll(2)
                r.rolls(0, frac_draw)
                out = r.natural_event(7, 50_000, 50_000 + 14 * HOUR)
                self.assertEqual(out["due"], 50_000 + 14 * HOUR * expected // 1000)
                self.assertLess(out["due"], out["natural"])


@NEEDS
class AtDue(unittest.TestCase):
    def armed(self, game: int = 4) -> tuple[Roll, dict]:
        r = Roll(game)
        r.rolls(0, 200)                                        # due half way
        out = r.natural_event(5, 0, 10 * HOUR)
        self.assertEqual(out["action"], SC_SAVE)
        return r, out

    def test_not_before_due(self) -> None:
        r, out = self.armed()
        self.assertEqual(r.step(5, out["due"] - 1, out["natural"])["action"], SC_NONE)

    def test_arms_when_clear(self) -> None:
        r, out = self.armed()
        self.assertEqual(r.step(5, out["due"], out["natural"])["action"], SC_ARM)

    def test_waits_while_anything_is_armed(self) -> None:
        r, out = self.armed()
        self.assertEqual(r.step(5, out["due"], out["natural"], busy=1)["action"], SC_NONE)
        self.assertEqual(r.step(5, out["due"] + 5, out["natural"])["action"], SC_ARM)

    def test_never_within_60_seconds_of_a_natural_event(self) -> None:
        r, out = self.armed()
        now = out["due"]
        self.assertEqual(r.step(5, now, now + 60)["action"], SC_NONE)      # the natural timer moved this close
        self.assertEqual(r.step(5, now, now + 61)["action"], SC_ARM)

    def test_waits_while_a_god_power_is_armed(self) -> None:
        r, out = self.armed(5)
        self.assertEqual(r.step(5, out["due"], out["natural"], god=1)["action"], SC_NONE)
        self.assertEqual(r.step(5, out["due"], out["natural"])["action"], SC_ARM)

    def test_trouble_cancels_never_delays(self) -> None:
        r, out = self.armed()
        got = r.step(5, out["due"], out["natural"], trouble=1)
        self.assertEqual((got["action"], got["due_set"]), (SC_CANCEL, 0))
        self.assertEqual(r.step(5, out["due"] + 100, out["natural"])["action"], SC_NONE)

    def test_a_natural_event_first_takes_its_place(self) -> None:
        r, out = self.armed()
        r.rolls(99, 0)                                         # the new natural event's own roll: no new one
        got = r.step(6, out["due"] - 10, out["due"] + 12 * HOUR)
        self.assertEqual((got["action"], got["due_set"]), (SC_CANCEL, 0))

    def test_its_natural_time_passed_cancels_it(self) -> None:
        r, out = self.armed()
        got = r.step(5, out["natural"], out["natural"] + 12 * HOUR)       # e.g. a Time Warp past both
        self.assertEqual((got["action"], got["due_set"]), (SC_CANCEL, 0))


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
        for game in P_PERCENT:
            with self.subTest(game=game):
                self.assertEqual(self.trouble(self.story(game)), 0)

    def test_the_rescue_predicate(self) -> None:
        for game in P_PERCENT:
            for men, women, expected in ((5, 2, 1), (5, 3, 0), (2, 5, 1), (3, 5, 0), (4, 4, 0), (6, 1, 1)):
                with self.subTest(game=game, men=men, women=women):
                    self.assertEqual(self.trouble(self.story(game, men, women)), expected)

    def test_low_food(self) -> None:
        for game in P_PERCENT:
            with self.subTest(game=game):
                self.assertEqual(self.trouble(self.story(game, food=80)), 0)     # 8 villagers x 10
                self.assertEqual(self.trouble(self.story(game, food=79)), 1)
                self.assertEqual(self.trouble(self.story(game, food=0)), 1)

    def test_few_grown_villagers(self) -> None:
        for game in P_PERCENT:
            with self.subTest(game=game):
                st = self.story(game, 3, 3)
                self.assertEqual(self.trouble(st), 0)                         # 6 of 14 or more
                st.village.put(5, sex="f", years=13, name="Kid")
                self.assertEqual(self.trouble(st), 1)

    def test_half_the_village_sick(self) -> None:
        sick = {1: (0x354, 4), 2: (0x53C, 4), 3: (0xE89, 1), 4: (0x1C48, 1), 5: (0x1C48, 1)}
        for game in P_PERCENT:
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

    def test_the_two_sources_one_to_one(self) -> None:
        r = self.roll(more=[1, 0, 1], more_ok=0, coll_ok=0xF)
        r.rolls(0, 1, 1, 0, 0)                                 # source 0: More Island Events, its 2nd possible
        armed, trace = self.choose(r)                          # (refused here), then the collection's first
        self.assertTrue(armed)
        self.assertEqual(trace, [2, 0x10000 | 0])              # registry entry 2 (entry 1 is not possible now)
        r = self.roll(more=[1, 0, 1], more_ok=0, coll_ok=0xF)
        r.rolls(1, 0, 0)                                       # source 1: the collection
        armed, trace = self.choose(r)
        self.assertTrue(armed)
        self.assertEqual(trace, [0x10000 | 0])

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

    def test_roll_due_and_arm_through_the_frame_hook(self) -> None:
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
        world = st.village.world
        counter = sci.EVENT_COUNTER_GLOBAL["vv4"]
        p.put32(world + 0x170E0, clock[0] + 600)
        p.export("VvfpStoryProbeCollectionTick", 4)            # the first frame: the count seen
        p.put32(counter, p.u32(counter) + 1)                   # the game's own event came ...
        p.put32(world + 0x170E0, clock[0] + 10 * HOUR)         # ... and its trigger wrote the next one
        at = p.alloc(8)
        p.put32(at, 0)
        p.put32(at + 4, 0)
        p.export("VvfpStoryProbeSetRolls", at, 2)
        p.export("VvfpStoryProbeCollectionTick", 4)
        state = p.alloc(6 * 4)
        p.export("VvfpStoryProbeCollectionState", state)
        self.assertEqual(p.u32(state), 1)
        due = p.u32(state + 4)
        self.assertEqual(due, clock[0] + 10 * HOUR * 300 // 1000)
        f = p.alloc(16)
        self.assertEqual(p.export("VvfpStoryProbeCollectionFile", f), 1)
        self.assertEqual(p.u32(f + 4), due)
        clock[0] = due
        p.export("VvfpStoryProbeSetRolls", at, 2)
        p.export("VvfpStoryProbeCollectionTick", 4)
        p.export("VvfpStoryProbeCollectionState", state)
        self.assertEqual(p.u32(state), 0)                      # spent
        self.assertEqual(p.export("VvfpStoryProbeCollectionFile", f), 0)   # its file deleted


if __name__ == "__main__":
    unittest.main()
