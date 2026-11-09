"""Bought island events and barrels: never sold twice for one delivery, never locked for good,
kept across a quit, and gone with a village that is started over (the owner, 2026-11-09:
"Yes fix the issues!!!", after the #736 audit).

1. A bought island event is ON ITS WAY UNTIL THE GAME'S TRIGGER DELIVERS IT.  A New Home, The
   Lost Children and The Tree of Life without its token read their lock as "the island timer due
   within the five seconds the purchase gave it"; The Secret City released its flag (0x6E0050) at
   its due second.  The Tech screen pauses the game, so an event bought there stays due,
   undelivered, while the screen is open: five seconds later the lock read as delivered and a
   second Origins Island Event, Pick or Custom Island Event could be sold -- two charges, one
   event.  The keeper every Origins companion already runs (native/shared/island_timer_keep.h)
   knows a bought event from its purchase (its write of the timer) until the trigger's own write
   for it; the Tech menu's Island Event row (each companion's row_block_reason) and the Story /
   Cheat Upgrades' lock (through the host table: story_bought_on_its_way) now ask it.
2. AN EMPTY VILLAGE IS NEVER LOCKED FOR GOOD.  The trigger does nothing while nobody lives in the
   village, so an island event bought there never comes.  There, and only for a plain Custom
   Island Event (the one event that reaches an empty village), the custom event takes the waiting
   event's place, and it is not charged when that one was bought (story_custom_ui.inc
   ce_purchase_locked).  A barrel waiting in The Tree of Life or New Believers is never replaced.
3. THE TREE OF LIFE: AN ISLAND EVENT BOUGHT BEFORE A BARREL SURVIVES A QUIT WITH IT.  The Barrel's
   cue puts the Island Event back on the shared timer only while its process-only token
   (0x728B08) is set; the token is now kept in the Barrel's own file and set again with it.
4. START OVER (OR THE TRIBE DELETED) TAKES ITS PURCHASES WITH IT.  A barrel or bought island event
   held in the executable's memory came to the new village started in the same slot; "VVFP Save
   Reset.dll" now tells the Origins companion (VvfpOriginsVillageReset), which clears them for the
   village in memory -- no refund: the village that paid is gone, the new one never paid.

Everything here runs the shipped bytes: each game's executable as the patcher renders it, with the
test builds of the keeper and the Story / Cheat Upgrades companion, or the shipped Origins
companions, mapped beside it in the emulator.
"""
from __future__ import annotations

import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))

from test_story_cheat_upgrades import (  # noqa: E402
    CLOCK,
    HAVE_EMULATOR,
    TEST_DLL,
    LockTests,
    have_stock,
    process,
    render,
)

if HAVE_EMULATOR:
    from story_emulator import HEAP, Process  # noqa: E402
    from test_bought_events_keep_natural_timer import (  # noqa: E402
        DLL as KEEPER_DLL,
        HOUR,
        OTHER_ROSTER,
        ROSTER,
        Village as KeeperVillage,
    )
else:  # pragma: no cover - environment dependent
    KEEPER_DLL = ROOT / "tests" / "test_dlls" / "VVFP Island Event Timer.test.dll"

LOCKED = ("vv1", "vv2", "vv3", "vv4")       # the games whose lock went by the clock
GAMES = ("vv1", "vv2", "vv3", "vv4", "vv5")
TIMER = {"vv1": 0xA300, "vv2": 0x2EAE0, "vv3": 0x12EF4, "vv4": 0x170E0, "vv5": 0x17D3C}
CLOCKS = {"vv1": 0x402F70, "vv2": 0x403200, "vv3": 0x403330, "vv4": 0x403750}
ORIGINS_COMPANION = {
    "vv1": ROOT / "assets/origins/VVFP VV1 Origins Icons.dll",
    "vv2": ROOT / "assets/origins/VVFP VV2 Origins Icons.dll",
    "vv3": ROOT / "data/candidates/VVFP VV3 Full Mastery Candidate.dll",
    "vv4": ROOT / "assets/origins/VVFP VV4 Origins Icons.dll",
    "vv5": ROOT / "data/candidates/VVFP VV5 Task9 Origins Icons.dll",
}


def _skip_without(path: Path):
    def wrap(cls):
        return unittest.skipUnless(HAVE_EMULATOR, "capstone/unicorn/pefile not installed")(
            unittest.skipUnless(path.is_file(), "test builds are not in the release source archive")(cls))
    return wrap


def _source(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# 1. The keeper: on its way from the purchase until the trigger delivers it
# ---------------------------------------------------------------------------

@_skip_without(KEEPER_DLL)
class TheKeeperKnowsUntilTheTriggerDelivers(unittest.TestCase):
    """native/shared/island_timer_keep.h itk_on_its_way, the answer every island-event lock asks."""

    @staticmethod
    def on(v) -> int:
        return v.proc.export("ItkProbeOnItsWay")

    def test_the_origins_purchase_is_on_its_way_while_the_tech_screen_stays_open(self):
        for game in LOCKED:
            if not have_stock(game):
                continue
            with self.subTest(game=game):
                v = KeeperVillage(game)
                v.set_timer(CLOCK + 3 * HOUR)
                self.assertEqual(self.on(v), 0, "nothing bought")
                v.buy()                                  # the Origins Island Event's own code
                self.assertEqual(self.on(v), 1)
                v.now += 60                              # the paused Tech screen stays open a minute
                self.assertEqual(self.on(v), 1, "still undelivered")
                # What the old locks read then: due more than five seconds ago is not "within the window".
                self.assertGreater((v.timer() - v.now) & 0xFFFFFFFF, 5)
                self.assertTrue(v.tick(), "the screen closed: the game's trigger runs it")
                self.assertEqual(self.on(v), 0, "delivered: the lock lifts")
                self.assertEqual(v.timer(), CLOCK + 3 * HOUR, "and the natural event keeps its time")

    def test_a_story_arm_is_on_its_way_the_same(self):
        for game in LOCKED:
            if not have_stock(game):
                continue
            with self.subTest(game=game):
                v = KeeperVillage(game)
                v.set_timer(CLOCK + 3 * HOUR)
                v.story_arm(v.now + 5)                   # Pick / Custom Island Event / the notice
                v.now += 600
                self.assertEqual(self.on(v), 1)
                self.assertTrue(v.tick())
                self.assertEqual(self.on(v), 0)

    def test_an_empty_village_keeps_it_on_its_way_until_someone_lives(self):
        """The trigger does nothing while the game's own count is 0 -- not even reschedule -- so the
        event stays on its way (a second one is never sold for it); the Story / Cheat Upgrades let a
        Custom Island Event take its place there (EmptyVillageCustomTakesThePlace)."""
        for game in LOCKED:
            if not have_stock(game):
                continue
            with self.subTest(game=game):
                v = KeeperVillage(game)
                v.set_timer(CLOCK + 3 * HOUR)
                v.buy()
                v.now += 60
                p = v.proc
                owner = v._helpers()
                count = {"vv1": 0x41CF90, "vv2": 0x425860, "vv3": 0x45E8F0, "vv4": 0x467610}[game]
                p.stub(count, lambda q: (0, 0))           # everyone has died
                bought = v.timer()
                for _ in range(3):
                    p.set_reg("esp", HEAP + 0x3000000)
                    p.set_reg("esi", owner)
                    p.set_reg("ebx", 0)
                    p.set_reg("eax", v.now)
                    p.set_reg(v.spec["obj_reg"], v.obj)
                    p.run(v.spec["trigger"], v.spec["skip"])
                    self.assertEqual(v.timer(), bought, "the trigger waited, as stock")
                    self.assertEqual(self.on(v), 1)
                self.assertTrue(v.tick(), "someone lives again: the trigger runs it")
                self.assertEqual(self.on(v), 0)

    def test_never_another_villages_and_start_over_forgets_it(self):
        for game in LOCKED:
            if not have_stock(game):
                continue
            with self.subTest(game=game):
                v = KeeperVillage(game)
                v.set_timer(CLOCK + 3 * HOUR)
                v.buy()
                v.village(1, OTHER_ROSTER)
                self.assertEqual(self.on(v), 0, "another village in the slot")
                v.village(2, ROSTER)
                self.assertEqual(self.on(v), 0, "another slot")
                v.village(1, ROSTER)
                self.assertEqual(self.on(v), 1)
                v.proc.export("ItkProbeVillageReset", 3)
                self.assertEqual(self.on(v), 1, "another slot's tribe deleted: kept")
                v.proc.export("ItkProbeVillageReset", 1)
                self.assertEqual(self.on(v), 0, "Start Over in its slot: gone with the village")


# ---------------------------------------------------------------------------
# 1, 2. The Story / Cheat Upgrades' lock, through the host table
# ---------------------------------------------------------------------------

class _Host:
    """An Origins companion's host table (native/shared/story_bridge.h) of this release: the slot,
    the mask store, the island timer's arming and its "on its way" (`on[0]`)."""

    def __init__(self, proc, n: int, *, size: int = 40):
        self.on = [0]
        code = proc.alloc(0x100)
        proc.write(code, b"\xC3" * 0x60)
        proc.stub(code, lambda p: (1, 0))
        proc.stub(code + 0x10, lambda p: (0, 4))
        proc.stub(code + 0x20, lambda p: (1, 8))
        proc.stub(code + 0x30, lambda p: (0, 8))
        proc.stub(code + 0x40, lambda p: (self.on[0], 0))
        table = proc.alloc(0x40)
        proc.write(table, struct.pack("<10I", size, code, code + 0x10, code + 0x20, 0, 0, 0, 0,
                                      code + 0x30, code + 0x40))
        assert proc.export("VvfpStoryAttachHost", n, table) == 1


@_skip_without(TEST_DLL)
class TheStoryLockAsksTheKeeper(unittest.TestCase):
    def _bought_and_left_open(self, game):
        """A pick armed exactly as the Island Event purchase arms it, then the Tech screen left open a
        minute -- with what each game's old lock then read."""
        n = int(game[2:])
        proc = process(game)
        world = LockTests._world(LockTests(), proc, game)
        proc.export("VvfpStoryInstall", n)
        host = _Host(proc, n)
        proc.export("VvfpStoryProbeArm", n, 0, 0)
        host.on[0] = 1                                            # the keeper saw the arm's write
        proc.stub(CLOCKS[game], lambda p: (CLOCK + 60, 0))         # a minute later, still paused
        if game == "vv3":
            proc.write(0x6E0050, b"\0")      # released by its due second (the menu draw, the frame hook)
        if game == "vv4":
            proc.write(0x728B08, b"\0")      # no token (a relaunch, or the Tech menu's retire)
        return proc, world, host, n

    def test_bought_and_still_undelivered_is_still_on_its_way(self):
        for game in LOCKED:
            if not have_stock(game):
                continue
            with self.subTest(game=game):
                proc, world, host, n = self._bought_and_left_open(game)
                self.assertEqual(proc.export("VvfpStoryProbePending", n), 1,
                                 "a second Island Event, Pick or Custom Island Event would be sold")
                host.on[0] = 0                                    # the trigger delivered it
                self.assertEqual(proc.export("VvfpStoryProbePending", n), 0, "delivered: the lock lifts")

    def test_a_host_without_the_answer_goes_by_the_timer_as_before(self):
        for game in LOCKED:
            if not have_stock(game):
                continue
            with self.subTest(game=game):
                n = int(game[2:])
                proc = process(game)
                LockTests._world(LockTests(), proc, game)
                proc.export("VvfpStoryInstall", n)
                host = _Host(proc, n, size=36)                    # a host built before the entry
                host.on[0] = 1
                proc.export("VvfpStoryProbeArm", n, 0, 0)
                self.assertEqual(proc.export("VvfpStoryProbePending", n), 1, "due within five seconds")
                proc.stub(CLOCKS[game], lambda p: (CLOCK + 3600 * 24, 0))
                if game == "vv3":
                    proc.write(0x6E0050, b"\0")
                if game == "vv4":
                    proc.write(0x728B08, b"\0")
                self.assertEqual(proc.export("VvfpStoryProbePending", n), 0, "its entry is never read")

    def test_new_believers_bits_stay_its_lock(self):
        """New Believers' bits (0x51D388) already last until the delivery (vv5_retire_delivered_island);
        its lock does not ask the keeper, which also holds its Barrel's write."""
        if not have_stock("vv5"):
            self.skipTest("stock executable not present")
        proc = process("vv5")
        world = LockTests._world(LockTests(), proc, "vv5")
        proc.export("VvfpStoryInstall", 5)
        host = _Host(proc, 5)
        host.on[0] = 1
        proc.put32(world + 0x17D3C, CLOCK + 36000)
        proc.put32(world + 0x17D50, CLOCK)
        self.assertEqual(proc.export("VvfpStoryProbePending", 5), 0)


@_skip_without(TEST_DLL)
class EmptyVillageCustomTakesThePlace(unittest.TestCase):
    """story_custom_ui.inc ce_purchase_locked: out = (refused, takes the waiting event's place, free)."""

    def gate(self, e) -> tuple:
        out = e.story.proc.alloc(12)
        e.story.proc.export("VvfpStoryProbeCustomGate", e.n, out)
        return struct.unpack("<3i", e.story.proc.read(out, 12))

    def _empty(self, game):
        from test_story_empty_village import _Empty
        e = _Empty(self, game)
        e.host2 = _Host(e.story.proc, e.n)
        return e

    def test_a_bought_event_waiting_in_an_empty_village(self):
        for game in GAMES:
            if not have_stock(game):
                continue
            with self.subTest(game=game):
                e = self._empty(game)
                p = e.story.proc
                timer = e.trigger.world + TIMER[game]
                # Bought (each game's own record of it), due, and never delivered: nobody lives.
                p.put32(timer, CLOCK - 600 if game != "vv5" else 0)
                e.host2.on[0] = 1
                if game == "vv3":
                    p.write(0x6E0050, b"\1")
                if game == "vv4":
                    p.write(0x728B08, b"\1")
                    p.put32(0x728B0C, CLOCK - 600)
                if game == "vv5":
                    p.put32(0x51D388, 0x10)
                    p.put32(e.trigger.world + 0x17D50, CLOCK)
                self.assertEqual(self.gate(e), (0, 1, 1),
                                 "a Custom Island Event takes its place, and is not charged again")
                e.population[0] = 3                       # someone lives: it will come
                self.assertEqual(self.gate(e), (1, 0, 0), "one island event at a time")

    def test_a_barrel_waiting_is_never_replaced(self):
        for game, setup in (("vv4", lambda p, w: (p.write(0x728B04, b"\1"), p.put32(w + 0x170E0, 0))),
                            ("vv5", lambda p, w: (p.put32(0x51D388, 0x08), p.put32(w + 0x17D3C, 0)))):
            if not have_stock(game):
                continue
            with self.subTest(game=game):
                e = self._empty(game)
                setup(e.story.proc, e.trigger.world)
                e.host2.on[0] = 1
                self.assertEqual(self.gate(e), (1, 0, 0))

    def test_an_armed_pick_keeps_its_place(self):
        for game in GAMES:
            if not have_stock(game):
                continue
            with self.subTest(game=game):
                e = self._empty(game)
                e.story.proc.export("VvfpStoryProbeSetPick", e.n, 0, 0)
                self.assertEqual(self.gate(e)[0], 1)

    def test_nothing_waiting_nothing_waived(self):
        for game in GAMES:
            if not have_stock(game):
                continue
            with self.subTest(game=game):
                e = self._empty(game)
                p = e.story.proc
                p.put32(e.trigger.world + TIMER[game], CLOCK + 36000)
                if game == "vv5":
                    p.put32(0x51D388, 0)
                self.assertEqual(self.gate(e), (0, 0, 0))

    def test_the_charge_is_waived_only_for_the_replacement(self):
        body = _source("native/vvfp_story_upgrades/vvfp_story_upgrades.c")
        charged = body[body.index("static int story_charged("):]
        charged = charged[:charged.index("\n}\n")]
        self.assertIn("if (command == story_custom_island_event) {", charged)
        self.assertIn("if (!waived && a->tech() < price) {", charged)
        self.assertIn("if (done && !story_charge_waived) {", charged)
        custom = _source("native/vvfp_story_upgrades/story_custom_ui.inc")
        custom = custom[custom.index("static int story_custom_island_event(int game, HWND owner) {"):]
        self.assertIn("story_charge_waived = waived;", custom)
        self.assertIn('waived ? "0" : story_price_text(game)', custom)
        self.assertLess(custom.index("ce_purchase_locked(game, &replaces, &waived)) {\n        refusal"),
                        custom.index("story_charge_waived = waived;"))


# ---------------------------------------------------------------------------
# 1, 2. The Origins companions' own rows ask the keeper too
# ---------------------------------------------------------------------------

class TheTechMenuRowsAskTheKeeper(unittest.TestCase):
    def test_each_island_event_row(self):
        vv1 = _source("native/vv1_origins_icons/vv1_origins_icons.c")   # The Lost Children's too
        self.assertIn("if (row == PENDING_ROW_ISLAND && ((state & STATE_ISLAND_PENDING) != 0 || itk_on_its_way())) {",
                      vv1)
        vv3 = _source("native/vv3_full_mastery_candidate/vv3_full_mastery_candidate.c")
        reason = vv3[vv3.index("static int vv3_row_block_reason("):]
        self.assertLess(reason.index("if (itk_on_its_way()) {\n        return VV3_BLOCK_ALREADY_PENDING;"),
                        reason.index("*(volatile unsigned char *)(UINT_PTR)VV3_ISLAND_PENDING_FLAG = 0;"),
                        "the keeper is asked before the flag is released by its due second")
        vv4 = _source("native/vv4_origins_icons/vv4_origins_icons.c")
        self.assertIn("((state & STATE_ISLAND_PENDING) != 0 || vv4_island_on_its_way())", vv4)
        helper = vv4[vv4.index("static int vv4_island_on_its_way(void) {"):]
        helper = helper[:helper.index("\n}\n")]
        self.assertIn("0x00728B04u != 0", helper)
        self.assertIn("0x00728B08u == 0", helper)

    def test_every_host_hands_the_answer_over(self):
        for rel in ("native/vv1_origins_icons/vv1_origins_icons.c", "native/vv2_origins_icons/vv2_origins_icons.c",
                    "native/vv3_full_mastery_candidate/vv3_full_mastery_candidate.c",
                    "native/vv4_origins_icons/vv4_origins_icons.c", "native/vv5_task9_origins/vv5_task9_origins.c"):
            with self.subTest(source=rel):
                self.assertIn("itk_story_arming, itk_story_on_its_way\n    };", _source(rel))

    def test_the_custom_button_is_the_story_companions_to_judge(self):
        bridge = _source("native/shared/story_bridge.h")
        clicked = bridge[bridge.index("static int vvfp_story_pick_clicked("):]
        self.assertLess(clicked.index("if (command == VVFP_STORY_CUSTOM_ID) {"),
                        clicked.index("if (blocked_reason != NULL) {"))


# ---------------------------------------------------------------------------
# 3. The Tree of Life: the Island Event behind a Barrel survives a quit
# ---------------------------------------------------------------------------

@_skip_without(TEST_DLL)
class TheTreeOfLifeIslandEventBehindABarrel(unittest.TestCase):
    def _relaunched(self, token: int):
        """After a relaunch: the Barrel re-armed from its file (vv4_paid_rearm: armed, three
        children, the saved zero timer) and -- with the fix -- the Island Event token from the same
        file (vv4_paid_restore_held: the token, its stamp the timer the re-arm left)."""
        proc = process("vv4")
        world = LockTests._world(LockTests(), proc, "vv4")
        proc.write(0x728B00, b"\1")
        proc.write(0x728B04, b"\1")
        proc.put32(world + 0x170E0, 0)
        proc.write(0x728B08, bytes((token,)))
        proc.put32(0x728B0C, 0)
        proc.export("VvfpStoryInstall", 4)
        return proc, world

    def test_the_barrel_comes_first_then_the_island_event_again(self):
        if not have_stock("vv4"):
            self.skipTest("stock executable not present")
        for token, island_back in ((1, True), (0, False)):
            with self.subTest(token_restored=bool(token)):
                proc, world = self._relaunched(token)
                self.assertEqual(proc.export("VvfpStoryProbePending", 4), 1)
                LockTests()._vv4_trigger(proc, world, (5, 3), seen=1)
                self.assertEqual(proc.read(0x728B04, 1), b"\0", "the Barrel was presented")
                if island_back:
                    self.assertEqual(proc.u32(world + 0x170E0), CLOCK + 5, "the bought event put back")
                    self.assertEqual(proc.u32(0x728B0C), CLOCK + 5)
                    self.assertEqual(proc.export("VvfpStoryProbePending", 4), 1, "and on its way")
                else:
                    self.assertGreater(proc.u32(world + 0x170E0), CLOCK + 5,
                                       "without the token: left for the next natural event (the bug)")

    def test_the_companion_keeps_the_token_with_the_barrel(self):
        vv4 = _source("native/vv4_origins_icons/vv4_origins_icons.c")
        self.assertIn('"Virtual Villagers - The Tree of Life", vv4_paid_rearm,\n    vv4_paid_held, vv4_paid_restore_held\n};',
                      vv4)
        held = vv4[vv4.index("static unsigned int vv4_paid_held(void) {"):]
        held = held[:held.index("static const vv_paid_game VV4_PAID")]
        self.assertIn("0x00728B08u != 0 ? 1u : 0u;", held)
        self.assertIn("*(volatile unsigned char *)(UINT_PTR)0x00728B08u = 1;", held)
        self.assertIn("*(volatile unsigned int *)(UINT_PTR)0x00728B0Cu = 0u;", held)
        paid = _source("native/shared/paid_purchases.h")
        self.assertEqual(paid.count("vv_paid_write(game, slot, vv_paid_word(g), roster)"), 4,
                         "every write keeps what waits behind the token")
        self.assertIn("g->restore_held(f.token >> 8);", paid)


# ---------------------------------------------------------------------------
# 4. Start Over: the Origins companions drop what the erased village bought
# ---------------------------------------------------------------------------

# Each game's save manager (native/shared/game_save_slot.h) and its current-slot field.
SAVE_MANAGER = {"vv1": (0x48AEDC, 0xABE4, 0xB000), "vv2": (0x4997BC, 0x30378, 0x31000),
                "vv3": (0x4B309C, 0x12F24, 0x13000), "vv4": (0x4CB51C, 0x17114, 0x18000),
                "vv5": (0x4DACE0, 0x17D80, 0x18000)}
# What each game holds for a purchase not yet delivered: (address, bytes while bought, bytes after).
HELD = {
    "vv1": ((0x48D700, b"\2", b"\0"), (0x48D704, struct.pack("<I", 17), bytes(4))),
    "vv2": ((0x49C700, b"\3", b"\0"), (0x49C708, struct.pack("<I", 9), bytes(4))),
    "vv3": ((0x6E0058, b"\1", b"\0"), (0x6E004C, struct.pack("<I", CLOCK), bytes(4)),
            (0x6E0050, b"\1", b"\0"), (0x6E0054, struct.pack("<I", CLOCK + 5), bytes(4))),
    "vv4": ((0x728B00, b"\1", b"\0"), (0x728B04, b"\1", b"\0"), (0x728B08, b"\1", b"\0"),
            (0x728B0C, struct.pack("<I", CLOCK + 5), bytes(4))),
    # New Believers: the Barrel's and the Island Event's bits go; the doublers' (1, 2) are the save's.
    "vv5": ((0x51D388, struct.pack("<I", 0x3F), struct.pack("<I", 0x03)),),
}


class StartOverTakesThePurchasesWithTheVillage(unittest.TestCase):
    def test_each_origins_companion_clears_them_for_the_village_in_memory_only(self):
        if not HAVE_EMULATOR:
            self.skipTest("capstone/unicorn/pefile not installed")
        for game in GAMES:
            if not have_stock(game) or not ORIGINS_COMPANION[game].is_file():
                continue
            with self.subTest(game=game):
                n = int(game[2:])
                proc = Process(render(game, "collection_progression"), ORIGINS_COMPANION[game])
                self.assertIn("VvfpOriginsVillageReset", proc.exports)
                pointer, field, size = SAVE_MANAGER[game]
                manager = proc.alloc(size)
                proc.put32(pointer, manager)
                proc.put32(manager + field, 2)           # the village in memory is Save 2's
                for va, bought, _ in HELD[game]:
                    proc.write(va, bought)

                def held():
                    return [proc.read(va, len(bought)) for va, bought, _ in HELD[game]]
                before = held()
                proc.export("VvfpOriginsVillageReset", n, 3)
                self.assertEqual(held(), before, "another slot's tribe deleted: the village in memory keeps them")
                proc.export("VvfpOriginsVillageReset", n % 5 + 1, 2)
                self.assertEqual(held(), before, "another game's call changes nothing")
                proc.export("VvfpOriginsVillageReset", n, 2)
                self.assertEqual(held(), [after for _, _, after in HELD[game]],
                                 "Start Over in its own slot: gone with the village")

    def test_the_reset_companion_tells_each_origins_companion(self):
        reset = _source("native/save_reset_export/save_reset_export.c")
        body = reset[reset.index("__declspec(dllexport) int __stdcall ResetDeletedTribe("):]
        self.assertLess(body.index("notify_origins(game, slot);"), body.index("vv_reset_slot_state("))
        for name in ("VVFP VV1 Origins Icons.dll", "VVFP VV2 Origins Icons.dll", "VVFP Origins Icons.dll",
                     "VVFP VV4 Origins Icons.dll"):
            self.assertIn(f'"{name}",', reset)
        self.assertIn('GetProcAddress(origins, "VvfpOriginsVillageReset")', reset)
        self.assertNotIn("LoadLibrary", reset)
        for rel in ("native/vv1_origins_icons/vv1_origins_icons.def", "native/vv2_origins_icons/vv2_origins_icons.def",
                    "native/vv3_full_mastery_candidate/vv3_full_mastery_candidate.def",
                    "native/vv4_origins_icons/vv4_origins_icons.def", "native/vv5_task9_origins/vv5_task9_origins.def"):
            with self.subTest(def_file=rel):
                self.assertIn("VvfpOriginsVillageReset=_VvfpOriginsVillageReset@8", _source(rel))


if __name__ == "__main__":
    unittest.main()
