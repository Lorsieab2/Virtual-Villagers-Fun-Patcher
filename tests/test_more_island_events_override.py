"""Pick Island Event's override for More Island Events' own events (the owner, 2026-11-25, all five games).

The owner: "it safely uses the available people in the village/game etc" -- "none of the usual requirements should
apply, unless it's literally technically impossible".  native/vvfp_more_island_events/mie_pick.inc THE OVERRIDE:

  * VvfpMoreIslandEventsPickInfoOverride(k, title, description, needs, cap): the picker's list with the override
    ticked -- the same entries; 1 when the override's tests hold; `needs` what the event still needs with it;
  * a pick is bought with the override when the Story companion's VvfpStoryMoreEventOverride(game) says so (1 while
    the pick VvfpStoryMoreEventDue returns was bought with it); only then do the event's draw and begin use the
    override's tests, held from the draw to the event's begin (the Story companion clears its pick first).

EMULATED (unicorn, the stock executables, the shipped "VVFP More Island Events.dll"; the Story companion's three
exports stood in for, as tests/test_aspiring_adventurer.py Village does -- its Done clears the pick, and the later
games' "taking" of the pick before the event's condition is asked is done here too):
  * every event whose requirement is dropped runs its popup and its effects to the end with that requirement false
    and the override's pick due: The Cave Explorers (no Cave puzzle, 20 years apart), The Climb (Research 0), The
    Troubling Signs (no robe, ten villagers), The Mysterious Mask (seven villagers), The Remembrance Ceremony in New
    Believers (no Last Heathen; the mausoleum only, the hovel patch installed), The Rumblings in all five games (a
    puzzle unsolved);
  * the same village without the override: refused exactly as before (A New Home / The Lost Children told Done 0;
    the later games' condition false);
  * what is kept: the villagers each event casts (and their ages), a grave, a finished structure, the tribe's name,
    the village's first island events -- each refused with plain words;
  * the normal list (VvfpMoreIslandEventsPickInfo) never uses the override's tests, even while an override pick is
    due; a pick bought without the override after one bought with it is the event's own test again.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT / "scripts"))

import test_aspiring_adventurer as aa  # noqa: E402
from test_cave_explorers import CaveVillage, cave_rolls  # noqa: E402
from test_ceremony_and_rumblings import (ACT_HONOR, REMEMBRANCE, RUMBLINGS, Ceremony,  # noqa: E402
                                         pick_index, remembrance_village)
from test_mysterious_mask import Mask, mask_rolls  # noqa: E402
from test_the_climb import ClimbVillage, climb_rolls  # noqa: E402
from test_troubling_signs import Signs  # noqa: E402

NEEDS = unittest.skipUnless(aa.HAVE_EMULATOR and aa.HAVE_STOCK and aa.DLL.is_file(),
                            "needs unicorn, pefile, the stock executables and the built DLL")
NATIVE = ROOT / "native" / "vvfp_more_island_events"

# The registry (mie_pick.inc MIE_PICKS) indexes.
ADVENTURER, CAVE, CLIMB, SIGNS, DIVING, DOLPHINS, MASK, REMEMBRANCE_K, REMEMBRANCE_NB, RUMBLINGS_K = range(10)


def story_override(v: aa.Village, on: bool = True) -> None:
    """The Story companion's VvfpStoryMoreEventOverride stood in for: 1 while the pick due in the village's game was
    bought with the override (`v.override`), else 0.  Every call is kept in `v.override_asked`."""
    p = v.p
    v.override = on
    v.override_asked = []
    stub = p.alloc(16)
    prior = p.api_handlers["GetProcAddress"]

    def proc(pr):
        if pr.arg(0) in v.story_handles and pr.cstring(pr.arg(1)) == "VvfpStoryMoreEventOverride":
            return stub, 8
        return prior(pr)

    def over(pr):
        game = pr.arg(0)
        v.override_asked.append(game)
        return (1 if v.override and game == v.game and v.due >= 0 else 0), 4
    p.api_handlers["GetProcAddress"] = proc
    p.stub(stub, over)


def info(v: aa.Village, k: int, override: bool) -> tuple[int, str, str]:
    """Registry entry `k`: (state, title, needs) by PickInfo or PickInfoOverride (-1: not in this game)."""
    bufs = [v.p.alloc(600) for _ in range(3)]
    name = "VvfpMoreIslandEventsPickInfoOverride" if override else "VvfpMoreIslandEventsPickInfo"
    state = v.p.export(name, k, *bufs, 600)
    state = -1 if state == 0xFFFFFFFF else state
    return state, v.p.cstring(bufs[0], 600), v.p.cstring(bufs[2], 600)


class TakesThePick:
    """The later games: Story / Cheat Upgrades' selector takes the pick (take_pick) before it asks the event's
    condition, so the pick is no longer due when the condition and the begin run."""

    def list_draw(self, pick):  # noqa: D401
        out = super().list_draw(pick)
        self.due = -1
        return out


class TakenSigns(TakesThePick, Signs):
    pass


class TakenMask(TakesThePick, Mask):
    pass


class TakenCeremony(TakesThePick, Ceremony):
    pass


# ---- Static ------------------------------------------------------------------------------------------------------

class TheTable(unittest.TestCase):
    def test_every_event_has_its_override_words_and_a_row(self) -> None:
        import build_more_island_events as builder
        import vv_translations as vt
        keys = [e["key"] for e in builder.pick_entries()]
        override = builder.pick_override_needs()
        self.assertEqual(sorted(override), sorted(keys))
        rows = {r["stem"]: r for r in vt.load_patcher_strings()}
        for key in keys:
            with self.subTest(key=key):
                row = rows[f"{builder.PICK_STEM}.{key}.needs_override"]
                self.assertEqual(row["english"], override[key])
                self.assertEqual(row.get("route"), "key")
                self.assertNotRegex(override[key], r"(?i)heathen|convert|puzzle|robe|population|research|tech")

    def test_the_story_export_and_the_new_export_are_named(self) -> None:
        pick = (NATIVE / "mie_pick.inc").read_text(encoding="utf-8")
        self.assertIn('mp_story("VvfpStoryMoreEventOverride")', pick)
        self.assertIn("int __stdcall VvfpMoreIslandEventsPickInfoOverride(int k, char *title, char *description, "
                      "char *needs, int cap)", pick)
        self.assertIn("VvfpMoreIslandEventsPickInfoOverride=_VvfpMoreIslandEventsPickInfoOverride@20",
                      (NATIVE / "vvfp_more_island_events.def").read_text(encoding="utf-8"))


# ---- The list ----------------------------------------------------------------------------------------------------

@NEEDS
class TheList(unittest.TestCase):
    def test_the_same_entries_and_never_less_possible(self) -> None:
        for game in aa.GAMES:
            with self.subTest(game=game):
                v = aa.Village(game)
                v.villager(0, "Ana", True)
                v.villager(1, "Ben")
                count = v.p.export("VvfpMoreIslandEventsPickCount")
                for k in range(count):
                    plain, over = info(v, k, False), info(v, k, True)
                    self.assertEqual(plain[0] < 0, over[0] < 0, k)
                    self.assertEqual(plain[1], over[1])
                    if plain[0] == 1:
                        self.assertEqual(over[0], 1, k)

    def test_the_cave_explorers(self) -> None:
        v = CaveVillage(cave_open=False)
        v.villager(0, "Ana", True, years=20)
        v.villager(1, "Ben", years=40)                       # 20 years apart, The Cave not solved
        self.assertEqual(info(v, CAVE, False)[0], 0)
        state, title, needs = info(v, CAVE, True)
        self.assertEqual((state, title), (1, "The Cave Explorers"))
        self.assertTrue(needs.startswith("two villagers of 18 or more who may go"))
        v.villager(1, "Ben", years=17)                       # only one adult: technically needed
        self.assertEqual(info(v, CAVE, True)[0], 0)
        v.villager(1, "Ben", years=40, carrying=500)         # nursing: protected, never cast
        self.assertEqual(info(v, CAVE, True)[0], 0)

    def test_the_first_island_events_stay(self) -> None:
        for game, field in ((1, 0x9E40), (2, 0x2E51C)):
            with self.subTest(game=game):
                v = aa.Village(game)
                v.villager(0, "Ana", True)
                v.villager(1, "Ben")
                v.p.put32(v.world + field, 1)
                state, _, needs = info(v, ADVENTURER, True)
                self.assertEqual(state, 0)
                self.assertEqual(needs, "the village's first island events to have happened")

    def test_the_climb(self) -> None:
        v = ClimbVillage()
        v.scientist(0, "Ana", True, research=0)
        self.assertEqual(info(v, CLIMB, False)[0], 0)
        self.assertEqual(info(v, CLIMB, True)[:2], (1, "The Climb"))
        v.scientist(0, "Ana", True, research=90, years=17)
        state, _, needs = info(v, CLIMB, True)
        self.assertEqual(state, 0)
        self.assertTrue(needs.startswith("a villager of 18 or more who may go"))

    def test_the_troubling_signs(self) -> None:
        v = Signs()
        v.chief(robed=False)
        v.village(9)                                          # ten villagers, the chief not robed
        self.assertEqual(info(v, SIGNS, False)[0], 0)
        self.assertEqual(info(v, SIGNS, True)[0], 1)
        v = Signs()
        v.chief(robed=False)
        v.village(8)                                          # eight others: the nine are what it casts
        state, _, needs = info(v, SIGNS, True)
        self.assertEqual(state, 0)
        self.assertIn("nine other villagers of 18 or more", needs)
        v = Signs()
        v.village(20)                                         # no Tribal Chief at all: the speaker
        self.assertEqual(info(v, SIGNS, True)[0], 0)
        v = Signs(tribe="")
        v.chief(robed=False)
        v.village(9)
        self.assertEqual(info(v, SIGNS, True)[0], 0)          # no tribe name: the words name it

    def test_the_mysterious_mask(self) -> None:
        v = Mask()
        v.build(2, 5)                                          # seven villagers
        self.assertEqual(info(v, MASK, False)[0], 0)
        self.assertEqual(info(v, MASK, True)[0], 1)
        v = Mask()
        v.build(1, 5)
        state, _, needs = info(v, MASK, True)
        self.assertEqual(state, 0)
        self.assertEqual(needs, "two to four children under 14 and five villagers of 18 or more who may be picked")
        v = Mask()
        v.build(2, 4)
        self.assertEqual(info(v, MASK, True)[0], 0)

    def test_the_remembrance_ceremony(self) -> None:
        v = remembrance_village(5)
        v.last_heathen(False)
        self.assertEqual(info(v, REMEMBRANCE_NB, False)[0], 0)
        self.assertEqual(info(v, REMEMBRANCE_NB, True), (1, "The Remembrance Ceremony", "at least one grave"))
        for game in aa.GAMES:
            with self.subTest(game=game):
                v = remembrance_village(game)
                v.graves(0)
                self.assertEqual(info(v, pick_index(game, REMEMBRANCE), True)[0], 0)   # a grave to honor

    def test_the_rumblings(self) -> None:
        for game in aa.GAMES:
            with self.subTest(game=game):
                v = Ceremony(game)
                v.villager(0, "Ana", True)
                v.puzzles(missing=3)
                for k in range(v.structures()):
                    v.finish(k, False)
                self.assertEqual(info(v, RUMBLINGS_K, True), (0, "The Rumblings", "a finished hut"))
                v.finish(v.structures() - 1)
                self.assertEqual(info(v, RUMBLINGS_K, False)[0], 0)
                self.assertEqual(info(v, RUMBLINGS_K, True)[0], 1)

    def test_the_normal_list_never_uses_the_override(self) -> None:
        v = TakenSigns()
        story_override(v)
        v.chief(robed=False)
        v.village(9)
        _, obj = v.list_draw(SIGNS)                            # an override pick drawn: held for its condition
        self.assertTrue(v.can_fire(obj))
        self.assertEqual(info(v, SIGNS, False)[0], 0)          # the list: the event's own test, still
        self.assertEqual(info(v, SIGNS, True)[0], 1)
        self.assertTrue(v.can_fire(obj))                       # asking the list changed nothing
        v.run_list(0)                                          # the next draw, nothing due: the hold is over
        self.assertFalse(v.can_fire(obj))


# ---- The delivery ------------------------------------------------------------------------------------------------

@NEEDS
class TheCaveExplorers(unittest.TestCase):
    def village(self, over: bool) -> CaveVillage:
        v = CaveVillage(cave_open=False)
        story_override(v, over)
        v.villager(0, "Ana", True, years=20)
        v.villager(1, "Ben", years=40)
        return v

    def test_runs_to_the_end_with_the_override(self) -> None:
        v = self.village(True)
        before = v.stores()
        v.play_cave(cave_rolls(keep="KEEP_ONE", keep_award=5), [0, 1, 1])
        self.assertTrue(v.closed_at_end)
        self.assertEqual(v.done, [(1, 1)])
        self.assertEqual(v.cave_state()[:2], [0, 1])
        self.assertEqual(v.health(1), 0)                       # name2 dies: the game's own death
        self.assertEqual(v.health(0), 100)
        self.assertEqual(v.stores(), before)
        self.assertEqual(v.p.read(v.world + 0x9FA8, 1), b"\x00")   # The Cave never touched

    def test_refused_without_it(self) -> None:
        v = self.village(False)
        self.assertFalse(v.begin([0] * 20))
        self.assertEqual(v.done, [(1, 0)])


@NEEDS
class TheClimb(unittest.TestCase):
    def village(self, over: bool) -> ClimbVillage:
        v = ClimbVillage()
        story_override(v, over)
        v.scientist(0, "Ana", True, research=0)
        v.villager(1, "Kid", years=10)
        return v

    def test_the_summit_with_the_override(self) -> None:
        v = self.village(True)
        before = v.stores()
        v.play_climb(climb_rolls(falls=False), 1)
        self.assertTrue(v.closed_at_end)
        self.assertEqual(v.done, [(2, 1)])                     # Done before the popup: the pick was held to begin
        self.assertEqual(v.research(0), 100)
        self.assertGreater(v.stores()[1], before[1])
        self.assertEqual(len(v.celebrations), 1)

    def test_the_advice_with_the_override(self) -> None:
        v = self.village(True)
        v.play_climb(climb_rolls(gain=3), 2)
        self.assertTrue(v.closed_at_end)
        self.assertEqual(v.research(0), 13)

    def test_refused_without_it_and_after_it(self) -> None:
        v = self.village(False)
        self.assertFalse(v.begin_climb(climb_rolls(falls=False)))
        self.assertEqual(v.done, [(2, 0)])
        v = self.village(True)
        v.play_climb(climb_rolls(falls=False), 1)
        v.scientist(0, "Ana", True, research=0)
        v.override = False                                     # the next pick bought without the override
        self.assertFalse(v.begin_climb(climb_rolls(falls=False)))
        self.assertEqual(v.done, [(2, 1), (2, 0)])


@NEEDS
class TheTroublingSigns(unittest.TestCase):
    def village(self, over: bool) -> TakenSigns:
        v = TakenSigns()
        story_override(v, over)
        v.chief(robed=False)
        v.village(9)
        v.set_stores(1000, 5000)
        return v

    def test_runs_to_the_end_with_the_override(self) -> None:
        for group in range(4):
            with self.subTest(group=group):
                v = self.village(True)
                self.assertTrue(v.open())
                state = v.ts_state()
                self.assertEqual(state[0], 0)                  # the chief, unrobed, is the speaker
                travellers = state[6:11]
                steps = v.play(group)
                self.assertEqual(steps[-1][0], "close")
                self.assertEqual(v.ts_state()[17], 1)          # the effects made
                for i in travellers:
                    self.assertEqual(v.present(i), 0)          # the five left
                for i in state[2:6] + [0]:
                    self.assertEqual(v.present(i), 1)

    def test_refused_without_it(self) -> None:
        v = self.village(False)
        self.assertFalse(v.open())


@NEEDS
class TheMysteriousMask(unittest.TestCase):
    def village(self, over: bool) -> TakenMask:
        v = TakenMask()
        story_override(v, over)
        v.build(2, 5)
        return v

    def test_runs_to_the_end_with_the_override(self) -> None:
        for answer, kw in ((0, {}), (2, dict(home=False, captured=True))):
            with self.subTest(answer=answer):
                v = self.village(True)
                self.assertTrue(v.open(mask_rolls(children=2, adults=5, **kw)))
                steps = v.play(answer)
                self.assertEqual(steps[-1][0], "close")
                state = v.mk_state()
                self.assertEqual(state[16], 1)
                for i in state[5:10]:
                    self.assertEqual(v.present(i), 0)          # the five volunteers left
                children_gone = [v.present(i) for i in (0, 1)]
                self.assertEqual(children_gone, [0, 0] if kw.get("captured") else [1, 1])

    def test_refused_without_it(self) -> None:
        v = self.village(False)
        self.assertFalse(v.open(mask_rolls(children=2, adults=5)))


@NEEDS
class TheRumblings(unittest.TestCase):
    def village(self, game: int, over: bool) -> Ceremony:
        v = (TakenCeremony if game >= 3 else Ceremony)(game)
        story_override(v, over)
        v.villager(0, "Ana", True)
        v.villager(1, "Ben")
        v.puzzles(missing=3)
        for k in range(v.structures()):
            v.finish(k, k == 0)
        return v

    def test_every_game_with_a_puzzle_unsolved(self) -> None:
        for game in aa.GAMES:
            with self.subTest(game=game):
                v = self.village(game, True)
                before = v.progress(0)
                if game >= 3:
                    self.assertTrue(v.due_can_happen(RUMBLINGS))
                text = v.happen(RUMBLINGS, [0] * 8)
                self.assertIn("The Rumblings", text)
                state = v.cr_state()
                self.assertEqual(state[0], RUMBLINGS)
                self.assertEqual(state[6], 1)                  # the effects made
                self.assertGreater(state[7], 0)                # the finished hut damaged
                self.assertNotEqual(v.progress(0), before)     # its building work changed (each game's own way)
                if game <= 2:
                    self.assertEqual(v.done, [(game, 1)])

    def test_refused_without_it(self) -> None:
        for game in aa.GAMES:
            with self.subTest(game=game):
                v = self.village(game, False)
                if game >= 3:
                    self.assertFalse(v.due_can_happen(RUMBLINGS))
                else:
                    v.happen(RUMBLINGS, [0] * 8)
                    self.assertEqual(v.done, [(game, 0)])
                    self.assertEqual(v.cr_state()[6], 0)       # nothing of ours happened


@NEEDS
class TheRemembranceCeremonyInNewBelievers(unittest.TestCase):
    def village(self, over: bool, hovel: bool = True) -> Ceremony:
        import build_vv5_hovel_memorial_actions as hovel_patch
        v = remembrance_village(5)
        v.__class__ = TakenCeremony
        story_override(v, over)
        v.last_heathen(False)
        v.villager(2, "Cid")
        if hovel:
            for patch in hovel_patch.feature()["patches"]:
                v.p.mu.mem_write(0x400000 + int(patch["offset"], 16), bytes.fromhex(patch["after"]))
            v.p.mu.ctl_flush_tb()
        return v

    def test_before_the_last_heathen_the_mausoleum_only(self) -> None:
        v = self.village(True)
        self.assertEqual(v.p.export("VvfpCeremonyHovelPatch"), 1)
        self.assertTrue(v.due_can_happen(REMEMBRANCE))
        v.set_food(1000)
        v.pop = 3
        v.happen(REMEMBRANCE, [0] * 12)                        # rolls that would send them to the hovel
        state = v.cr_state()
        self.assertEqual((state[0], state[1], state[2], state[6]), (REMEMBRANCE, 3, 0, 1))
        self.assertEqual([v.act(i) for i in range(3)], [ACT_HONOR] * 3)
        self.assertEqual([(s[1], s[2]) for s in v.sent if s[0] == "do"], [(0, 17), (1, 17), (2, 17)])
        self.assertEqual(v.food(), 970)

    def test_refused_without_it(self) -> None:
        v = self.village(False)
        self.assertFalse(v.due_can_happen(REMEMBRANCE))


@NEEDS
class TheOthersAreUnchanged(unittest.TestCase):
    """The Aspiring Adventurer, Diving for Treasure and The Playful Dolphins need only the villagers they cast: the
    override changes nothing for them, and a pick of theirs bought with it is delivered as any."""

    def test_the_adventurer_with_the_override_in_every_game(self) -> None:
        for game in aa.GAMES:
            with self.subTest(game=game):
                v = aa.Village(game)
                story_override(v)
                v.villager(0, "Ana", True)
                v.villager(1, "Ben")
                self.assertEqual(info(v, ADVENTURER, True)[0], 1)
                self.assertTrue(v.begin(aa.rolls(game=game)))
                v.villager(1, "Ben", years=13)
                self.assertEqual(info(v, ADVENTURER, True)[0], 0)


if __name__ == "__main__":
    unittest.main()
