"""Pick Island Event picks More Island Events' events (v1.35.97).

The registry (native/vvfp_more_island_events/mie_pick.inc, one line per event) and the two companions' handshake:
"VVFP More Island Events.dll" lists each game's events for the Pick Island Event list (VvfpMoreIslandEventsPickCount /
PickInfo: title, one sentence, what it needs, possible now), and each game's draw asks the Story / Cheat Upgrades
companion which event is due (VvfpStoryMoreEventDue) and, in A New Home and The Lost Children, says whether it came
(VvfpStoryMoreEventDone).

EMULATED (unicorn, the stock executables, the shipped More Island Events DLL with the Story companion's two exports
stood in for; the Story TEST build with More Island Events' three stood in for):
  * the list: each game's events in the registry's order -- A New Home The Aspiring Adventurer and The Cave Explorers,
    The Lost Children The Aspiring Adventurer and The Climb, The Secret City The Aspiring Adventurer, The Troubling
    Signs and Diving for Treasure, The Tree of Life and New Believers The Aspiring Adventurer -- each possible only
    when its own requirements hold (the owner's protected villagers never count), with plain words for what it needs;
  * the draw takes the picked event, in all five games: A New Home's encounter setup begins it without a draw and
    says it came; The Lost Children's family-A draw is its own number; the later games' selector puts its object in
    slot 0 (Diving for Treasure and The Troubling Signs each their own, whatever the coin would have said);
  * an event that can no longer happen when it is due is refused (A New Home, The Lost Children: told, the stock
    draw runs);
  * the Story side: the list is empty without More Island Events; an armed pick is due only in its game and village,
    once; Done clears it (delivered or refused, the refusal kept for the next chooser); a pick lapses after ten
    minutes; the family slot each game's chooser needs.
"""
from __future__ import annotations

import os
import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))

import test_aspiring_adventurer as aa  # noqa: E402

STORY_DLL = Path(os.environ.get(
    "VVFP_STORY_TEST_DLL", ROOT / "tests" / "test_dlls" / "VVFP Story Upgrades.test.dll"))
FAKE_STORY = 0x0E900000
FAKE_MORE = 0x0EA00000
NEEDS_RUN = aa.HAVE_EMULATOR and aa.HAVE_STOCK and aa.DLL.is_file()

# The registry, in order (mie_pick.inc MIE_PICKS): index -> (title, games).
REGISTRY = [
    ("The Aspiring Adventurer", (1, 2, 3, 4, 5)),
    ("The Cave Explorers", (1,)),
    ("The Climb", (2,)),
    ("The Troubling Signs", (3,)),
    ("Diving for Treasure", (3,)),
    ("The Playful Dolphins", (4,)),
    ("The Mysterious Mask", (4,)),
]


class PickedVillage(aa.Village):
    """A game with More Island Events started, and Pick Island Event's two exports stood in for: `due` is the
    registry index Pick Island Event has due (-1 none); every Done is kept."""

    def __init__(self, game: int):
        self.due = -1
        self.done: list[tuple[int, int]] = []
        super().__init__(game)

    def _cod(self) -> None:
        super()._cod()
        p = self.p
        module, proc = p.api_handlers["GetModuleHandleA"], p.api_handlers["GetProcAddress"]
        due_stub, done_stub = p.alloc(16), p.alloc(16)

        def module2(pr):
            name = pr.cstring(pr.arg(0)) if pr.arg(0) else ""
            return (FAKE_STORY, 4) if name == "VVFP Story Upgrades.dll" else module(pr)

        def proc2(pr):
            if pr.arg(0) == FAKE_STORY:
                name = pr.cstring(pr.arg(1))
                return {"VvfpStoryMoreEventDue": due_stub, "VvfpStoryMoreEventDone": done_stub}.get(name, 0), 8
            return proc(pr)

        p.api_handlers["GetModuleHandleA"] = module2
        p.api_handlers["GetProcAddress"] = proc2
        p.stub(due_stub, lambda pr: ((self.due if pr.arg(0) == self.game else -1) & 0xFFFFFFFF, 4))

        def done(pr):
            self.done.append((pr.arg(0), pr.arg(1)))
            if pr.arg(0) == self.game:
                self.due = -1
            return 0, 8
        p.stub(done_stub, done)

    def entries(self) -> list[tuple[int, str, int, str]]:
        """The game's registry entries: (index, title, possible, needs)."""
        out = []
        bufs = [self.p.alloc(400) for _ in range(3)]
        for k in range(self.p.export("VvfpMoreIslandEventsPickCount")):
            state = self.p.export("VvfpMoreIslandEventsPickInfo", k, *bufs, 400)
            if state == 0xFFFFFFFF:
                continue
            out.append((k, self.p.cstring(bufs[0], 400), state, self.p.cstring(bufs[2], 400)))
        return out


@unittest.skipUnless(NEEDS_RUN, "needs unicorn, pefile and the stock executables")
class TheList(unittest.TestCase):
    def test_each_games_events_in_the_registrys_order(self) -> None:
        for game in aa.GAMES:
            with self.subTest(game=game):
                v = PickedVillage(game)
                titles = [e[1] for e in v.entries()]
                expect = [t for t, games in REGISTRY if game in games]
                self.assertEqual(titles, expect)

    def test_possible_only_by_its_own_requirements(self) -> None:
        for game in aa.GAMES:
            with self.subTest(game=game):
                v = PickedVillage(game)
                v.villager(0, "Ana", True)
                adventurer = v.entries()[0]
                self.assertEqual(adventurer[2], 0)                   # one who may go: never
                self.assertIn("two villagers of 14 or more", adventurer[3])
                v.villager(1, "Ben", carrying=500)                   # protected: nursing
                self.assertEqual(v.entries()[0][2], 0)
                v.villager(1, "Ben")
                self.assertEqual(v.entries()[0][2], 1)

    def test_the_first_island_events_rule_in_a_new_home_and_the_lost_children(self) -> None:
        for game, field in ((1, 0x9E40), (2, 0x2E51C)):
            with self.subTest(game=game):
                v = PickedVillage(game)
                v.villager(0, "Ana", True)
                v.villager(1, "Ben")
                v.p.put32(v.world + field, 1)
                entry = v.entries()[0]
                self.assertEqual(entry[2], 0)
                self.assertIn("first island events", entry[3])

    def test_the_climb_and_the_cave_say_what_they_need(self) -> None:
        v = PickedVillage(1)
        v.villager(0, "Ana", True)
        v.villager(1, "Ben")
        cave = [e for e in v.entries() if e[1] == "The Cave Explorers"][0]
        self.assertEqual(cave[2], 0)                                 # The Cave not solved
        self.assertIn("The Cave puzzle solved", cave[3])
        v2 = PickedVillage(2)
        v2.villager(0, "Ana", True, years=15)                       # Research 50, but under 18
        climb = [e for e in v2.entries() if e[1] == "The Climb"][0]
        self.assertEqual(climb[2], 0)
        self.assertIn("Trainee in Research", climb[3])


@unittest.skipUnless(NEEDS_RUN, "needs unicorn, pefile and the stock executables")
class TheDraw(unittest.TestCase):
    def village(self, game: int) -> PickedVillage:
        v = PickedVillage(game)
        v.villager(0, "Ana", True)
        v.villager(1, "Ben")
        return v

    def test_a_new_home_begins_the_picked_event_without_a_draw(self) -> None:
        v = self.village(1)
        v.due = 0
        self.assertTrue(v.begin([]))
        self.assertEqual(v.p.u32(v.dlg + 0x5094), 0x7F4B1A2E)
        self.assertEqual(v.done, [(1, 1)])
        self.assertIn("The Aspiring Adventurer", v.shown())

    def test_a_new_home_refuses_an_event_that_can_not_happen(self) -> None:
        v = self.village(1)
        v.due = 1                                                    # The Cave Explorers, The Cave not solved
        v.dlg = v.p.alloc(0x6000)
        v.p.put32(v.dlg + 0x50A4, v.world)
        v.p.put32(v.dlg + 0x50A8, v.base)
        v.rolls = [0] * 40
        v.p.call(0x4189E0, [], ecx=v.dlg)
        self.assertEqual(v.done, [(1, 0)])
        self.assertNotEqual(v.p.u32(v.dlg + 0x5094), 0x7F4B1A2E)     # the stock draw ran

    def test_the_lost_children_takes_the_events_own_number(self) -> None:
        v = self.village(2)
        v.due = 0
        dlg = v.p.alloc(0x6000)
        v.p.put32(dlg + 0x50AC, v.world)
        v.p.put32(dlg + 0x50B0, v.base)
        v.rolls = [5] * 10                                           # a stock draw would be 5
        v.p.call(0x41F780, [], ecx=dlg)
        self.assertEqual(v.p.u32(dlg + 0x509C), 21)
        self.assertEqual(v.done, [(2, 1)])

    def test_the_lost_children_refuses_the_climb_without_a_climber(self) -> None:
        v = self.village(2)                                          # Research 50, but the age rule holds: drop it
        for i in (0, 1):
            v.p.put32(v.rec(i) + v.L["age"], 15 * 20)                # 15: never climbs
        v.due = 2
        dlg = v.p.alloc(0x6000)
        v.p.put32(dlg + 0x50AC, v.world)
        v.p.put32(dlg + 0x50B0, v.base)
        v.rolls = [21] * 10
        v.p.call(0x41F780, [], ecx=dlg)
        self.assertEqual(v.done, [(2, 0)])
        self.assertNotEqual(v.p.u32(dlg + 0x509C), 22)

    def test_the_later_games_put_the_picked_object_in_slot_0(self) -> None:
        for game in (3, 4, 5):
            with self.subTest(game=game):
                v = self.village(game)
                self.assertTrue(v.listed())
                natural = v.obj
                v.due = 0
                v.listed()
                self.assertEqual(v.obj, natural)                     # the Adventurer's own object
                self.assertEqual(v.done, [])                         # the Story's own pick delivers slot 0

    def test_the_secret_city_puts_each_picked_event_in_slot_0(self) -> None:
        v = self.village(3)
        objects = {}
        for k in (0, 3, 4):
            v.due = k
            v.listed()
            objects[k] = v.obj
        self.assertEqual(len(set(objects.values())), 3)              # each its own object, whatever the coin said
        v.due = -1
        v.listed()
        self.assertIn(v.obj, (objects[0], objects[4]))               # unpicked: one that can happen (no chief robe)


@unittest.skipUnless(aa.HAVE_EMULATOR and aa.HAVE_STOCK and STORY_DLL.is_file(), "needs the Story TEST build")
class TheStorySide(unittest.TestCase):
    """The Story companion with More Island Events' three exports stood in for."""

    def process(self, game: int, more: bool = True, possible=(1, 0)):
        p = aa.Process(aa.STOCK[game].read_bytes(), STORY_DLL)
        stubs = {name: p.alloc(16) for name in ("Installed", "Count", "Info")}
        p.stub(stubs["Installed"], lambda pr: (game, 0))
        p.stub(stubs["Count"], lambda pr: (len(possible), 0))

        def info(pr):
            k = pr.arg(0)
            if k >= len(possible):
                return 0xFFFFFFFF, 20
            pr.write(pr.arg(1), f"Event {k}\0".encode())
            pr.write(pr.arg(2), b"About it.\0")
            pr.write(pr.arg(3), b"two villagers\0")
            return possible[k], 20
        p.stub(stubs["Info"], info)
        prior_module = p.api_handlers.get("GetModuleHandleA")
        prior_proc = p.api_handlers.get("GetProcAddress")

        def module(pr):
            name = pr.cstring(pr.arg(0)) if pr.arg(0) else ""
            if name == "VVFP More Island Events.dll":
                return (FAKE_MORE if more else 0), 4
            return prior_module(pr) if prior_module else (0, 4)

        def proc(pr):
            if pr.arg(0) == FAKE_MORE:
                name = pr.cstring(pr.arg(1))
                return {"VvfpMoreIslandEventsInstalled": stubs["Installed"], "VvfpMoreIslandEventsPickCount":
                        stubs["Count"], "VvfpMoreIslandEventsPickInfo": stubs["Info"]}.get(name, 0), 8
            return prior_proc(pr) if prior_proc else (0, 8)
        p.api_handlers["GetModuleHandleA"] = module
        p.api_handlers["GetProcAddress"] = proc
        p.export("VvfpStoryProbeSetTick", 0)
        return p

    def listed(self, p, game: int) -> list[tuple[int, int]]:
        k, possible = p.alloc(64), p.alloc(64)
        n = p.export("VvfpStoryProbeMoreList", game, k, possible, 16)
        return [(p.u32(k + 4 * i), p.u32(possible + 4 * i)) for i in range(n)]

    def test_listed_only_with_more_island_events(self) -> None:
        for game in aa.GAMES:
            with self.subTest(game=game):
                self.assertEqual(self.listed(self.process(game), game), [(0, 1), (1, 0)])
                self.assertEqual(self.listed(self.process(game, more=False), game), [])

    def test_due_once_in_its_own_game_then_done(self) -> None:
        slots = {1: (1 << 6) | 0x3E, 2: (1 << 6) | 0x3E, 3: 0, 4: 0, 5: 0}
        for game in aa.GAMES:
            with self.subTest(game=game):
                p = self.process(game)
                self.assertEqual(p.export("VvfpStoryProbeMoreArm", game, 1, 0), slots[game])
                self.assertEqual(p.export("VvfpStoryMoreEventDue", game), 1)
                other = 1 if game != 1 else 2
                self.assertEqual(p.export("VvfpStoryMoreEventDue", other), 0xFFFFFFFF)
                p.export("VvfpStoryMoreEventDone", game, 1)
                self.assertEqual(p.export("VvfpStoryMoreEventDue", game), 0xFFFFFFFF)
                self.assertEqual(p.export("VvfpStoryProbeArmedSlot"), 0xFFFFFFFF)

    def test_a_refusal_is_kept_and_counted(self) -> None:
        p = self.process(2)
        stats = p.exports["VvfpStoryStats"]
        p.export("VvfpStoryProbeMoreArm", 2, 0, 0)
        p.export("VvfpStoryMoreEventDone", 2, 0)
        delivered, refused = struct.unpack("<ii", p.read(stats, 8))
        self.assertEqual((delivered, refused), (0, 1))
        self.assertEqual(p.export("VvfpStoryMoreEventDue", 2), 0xFFFFFFFF)

    def test_a_pick_lapses_after_ten_minutes(self) -> None:
        p = self.process(3)
        p.export("VvfpStoryProbeMoreArm", 3, 0, 0)
        p.export("VvfpStoryProbeSetTick", 10 * 60 * 1000 + 1)
        self.assertEqual(p.export("VvfpStoryMoreEventDue", 3), 0xFFFFFFFF)

    def test_a_stock_pick_is_never_a_more_pick(self) -> None:
        p = self.process(3)
        p.export("VvfpStoryProbeMoreArm", 3, 0, 0)
        p.export("VvfpStoryProbeSetPick", 3, 0, 0)                 # a stock event armed over it
        self.assertEqual(p.export("VvfpStoryMoreEventDue", 3), 0xFFFFFFFF)


if __name__ == "__main__":
    unittest.main()
