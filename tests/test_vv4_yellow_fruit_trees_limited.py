"""Yellow Fruit Trees are No Longer Unlimited (The Tree of Life): "VVFP VV4 Fruit Supply.dll".

Everything here runs the shipped DLL beside The Tree of Life's own code in unicorn (tests/farmers_emulation_vv4.py,
with the companion mapped through tests/story_emulator.py's Process and a small in-memory file system for its
per-save file, tests/test_vv3_both_factions.py's Files).  The fruit trips, the drop on the tree, the farming
dispatcher, the task gate, the stew's item listener and the life tick's catch-up are the game's own routines; only
rand, the clock and the two singleton getters are stand-ins (farmers_emulation_vv4.py says why each is safe).
"Stock" is the same village without the companion.  How much fruit the tree holds is read the way a player reads
it: the tree clicked (its area handler 0x435970, message 2), the status line 0x4DB8E8.

The live effect in a running game is NOT verified here.
"""
from __future__ import annotations

import functools
import json
import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import vv_fun_patcher as patcher  # noqa: E402

try:
    import pefile  # noqa: F401
    from unicorn import UC_HOOK_CODE
    from unicorn.x86_const import UC_X86_REG_EDI, UC_X86_REG_ESP

    import farmers_emulation_vv4 as fe
    import test_vv3_both_factions as both_factions   # its in-memory file system

    HAVE_EMULATOR = fe.STOCK.is_file() and fe.CMAP.is_file()
except ImportError:  # pragma: no cover - environment dependent
    HAVE_EMULATOR = False

ID = "vv4_yellow_fruit_trees_limited"
FEATURE = ROOT / "data" / f"{ID}_feature.json"
DLL = ROOT / "assets" / "fruit_supply" / "VVFP VV4 Fruit Supply.dll"
MODES = ("stock", "collection_progression", "immediate_fixed")
SIDE = ("C:\\Docs\\LDW\\Game\\Virtual Villagers Fun Patcher\\Save {s}\\Data\\Fruit Trees\\"
        "Virtual Villagers 4 Yellow Fruit Tree - Save {s}.dat")

TREE = 0x435970                 # the tree's area handler: (message, villager, ...)
BUSH = 0x46F810                 # the blackberry bush's
DO_ACTION = 0x45DEC0
STATUS = 0x4DB8E8               # the status line's text
SLOT_FIELD = 0x17114            # the game object's current save slot
VTABLE = 0x48E890               # CFruitwells
TASK_GATE = 0x4634D0
DISPATCHER = 0x4639B0
CLEAR_QUEUE = 0x468C60
ITEM_LISTEN = 0x413170          # the item manager 0x4CC0A0: (item, listener)
STEW, STEW_LISTENER, STEW_VTABLE = 0x4D76D8, 0x4D76DC, 0x48E258
CAULDRON_SPOT = 0x704E38 + 0x18 * 20
REC_NAME, REC_TASK, REC_ACTION = 0x1B9C, 0x1C54, 0x1CE0
SKILL_ROLL = 0x462B1A           # rand(100) of the skill check (return address)
BONUS_ROLL = 0x468AA1           # rand(100) of the Cooking Pit bonus
GATE_ROLLS = (0x4634F4, 0x463503)
SITES = {0x46456C: 12, 0x463A38: 11, 0x46364E: 7, 0x4359B8: 7, 0x43597A: 5, 0x468AAB: 12, 0x468AD6: 8,
         0x42EAE7: 7}


def identity(name: str, sex: int = 1, father: str = "", mother: str = "") -> int:
    """The companion's identity of a villager (gender, name and the parents' names, FNV-1a)."""
    h = 2166136261

    def mix(data: bytes, end: int) -> None:
        nonlocal h
        for b in data:
            h = ((h ^ b) * 16777619) & 0xFFFFFFFF
        h = ((h ^ end) * 16777619) & 0xFFFFFFFF

    for b in struct.pack("<I", sex):
        h = ((h ^ b) * 16777619) & 0xFFFFFFFF
    mix(name.encode()[:25], 0xFF)
    mix(father.encode()[:25], 0xFE)
    mix(mother.encode()[:25], 0xFD)
    return h or 1


def tree_file(fruit: int, units: int = 0, roster=(), slot: int = 1, magic: int = 0x46345656) -> bytes:
    ids = list(roster) + [0] * (256 - len(roster))
    return struct.pack("<8I", magic, 1, 4, slot, fruit, units, len(roster), 0) + struct.pack("<256I", *ids)


def side(slot: int = 1) -> str:
    return SIDE.format(s=slot).lower()


@functools.lru_cache(maxsize=None)
def builds():
    return {b.id: b for b in patcher.load_builds()}


@functools.lru_cache(maxsize=None)
def render(mode: str, expanded: bool = False) -> bytes:
    """The Tree of Life's public catalog (this row in it) as the patcher renders it."""
    rows = [p for p in patcher.load_public_fun_patches()
            if p.game_id == "vv4" and p.id not in patcher.ALTERNATIVE_FUN_PATCH_IDS
            and (expanded or p.id not in patcher.EXPERIMENTAL_FUN_PATCH_IDS)]
    ids = patcher.resolve_fun_patch_ids([p.id for p in rows], game_id="vv4")
    assert ID in ids
    data, _ = patcher.render_patched_bytes(fe.STOCK, builds()["vv4"], mode, ids)
    return bytes(data)


class Tree:
    """A Tree of Life village, the Cooking Pit restored, no bush and no nets: the fruit is the only farming."""

    def __init__(self, patched: bool = True, *, exe: bytes | None = None, files: dict | None = None,
                 seed: int = 3, slot: int = 1):
        self.v = fe.Village(seed=seed, berries=0, solved=(6,), exe=exe, dll=DLL if patched else None)
        self.patched = patched
        self.files = None
        if patched:
            self.files = both_factions.Files(self.v.process)
            if files is not None:
                self.files.files = files
            self.v.process.export("VvfpStartup", 4, 0)
            assert self.v.process.export("VvfpYellowFruitInstalled") == 1
        self.v.w32(fe.GAME + SLOT_FIELD, slot)

    def villager(self, name: str = "Ana", index: int = 0, **kw) -> int:
        r = self.v.villager(index=index, skills=kw.pop("skills", {"farming": 100}), **kw)
        self.v.uc.mem_write(r + REC_NAME, name.encode() + b"\0")
        return r

    def readout(self) -> str:
        """The tree clicked: what the status line says ("" when nothing was written)."""
        self.v.uc.mem_write(STATUS, bytes(0x100))
        self.v.call(TREE, 0, 2, self.v.rec(0), 0)
        return bytes(self.v.uc.mem_read(STATUS, 0x100)).split(b"\0")[0].decode("latin-1")

    def left(self) -> int:
        text = self.readout()
        assert text.startswith("Fruit remaining: "), text
        return int(text.rsplit(" ", 1)[1])

    def drop(self, index: int = 0) -> tuple[int, int, int]:
        """A villager dropped on the tree: the action the drop started (the do-action 0x45DEC0's first call) and
        the first two dwords of its argument block."""
        r = self.v.rec(index)
        seen: list[tuple[int, int, int]] = []

        def started(*_):
            sp = self.v.uc.reg_read(UC_X86_REG_ESP)
            action, block = self.v.r32(sp + 4), self.v.r32(sp + 8) & 0xFFFFFFFF
            seen.append((action, self.v.r32(block), self.v.r32(block + 4)))

        hook = self.v.uc.hook_add(UC_HOOK_CODE, started, begin=DO_ACTION, end=DO_ACTION)
        self.v.call(TREE, 0, 0, r, 0)
        self.v.uc.hook_del(hook)
        return seen[0]

    def save(self) -> None:
        """The game saves the puzzles: CFruitwells' save slot, as the puzzles' save 0x438810 calls it."""
        fn = self.v.r32(VTABLE + 4 * 4) & 0xFFFFFFFF
        obj, buf = fe.HEAP + 0x8000, fe.HEAP + 0x9000
        self.v.call(fn, obj, buf, 8)

    def load(self) -> None:
        fn = self.v.r32(VTABLE + 4 * 3) & 0xFFFFFFFF
        obj, buf = fe.HEAP + 0x8000, fe.HEAP + 0x9000
        self.v.call(fn, obj, buf)

    def credits(self, amount: int) -> int:
        return sum(1 for _, a in self.v.food_log if a == amount)


@unittest.skipUnless(HAVE_EMULATOR, "needs pefile, unicorn, the stock executable and research/game-data/vv4")
class FruitTrips(unittest.TestCase):
    def test_a_new_village_starts_full_and_stock_shows_nothing(self) -> None:
        t = Tree()
        t.villager()
        self.assertEqual(t.readout(), "Fruit remaining: 1000")
        s = Tree(patched=False)
        s.villager()
        self.assertEqual(s.readout(), "")                 # the stock tree ignores a click

    def test_each_food_bin_credit_takes_three_and_the_trips_are_stock(self) -> None:
        trips = {}
        for patched in (False, True):
            t = Tree(patched)
            t.villager()
            trips[patched] = [t.v.run_trip(fe.FRUIT) for _ in range(3)]
            self.assertEqual(t.v.food(), 1009)
            if patched:
                self.assertEqual(t.left(), 991)
        self.assertEqual(trips[False], trips[True])       # frame for frame, event for event
        self.assertTrue(all(got == [15] for _, _, got in trips[True]))

    def test_the_status_line_shows_it_for_five_seconds(self) -> None:
        t = Tree()
        t.villager()
        t.readout()
        self.assertEqual(t.v.r32(STATUS + 0x100), int(t.v.t) + 5)

    def test_a_failed_farming_check_takes_nothing(self) -> None:
        t = Tree()
        t.villager(skills={"farming": 0})
        t.v.by_caller[SKILL_ROLL] = 99                    # rand(100) = 99 > Farming + 33: the check fails
        paid, _, got = t.v.run_trip(fe.FRUIT)
        self.assertEqual((paid, got), (-1, []))
        self.assertEqual(t.v.food(), 1000)
        self.assertEqual(t.left(), 1000)

    def test_an_interrupted_trip_takes_nothing(self) -> None:
        t = Tree()
        r = t.villager()
        t.v.start(fe.FRUIT)
        for _ in range(1500):                             # shaking the tree / carrying: well before the bin
            t.v.step_frame()
        self.assertFalse(any(e == 15 for _, e in t.v.events))
        t.v.call(CLEAR_QUEUE, r)                          # the game's own queue clear
        for _ in range(200):
            t.v.step_frame()
        self.assertFalse(any(e == 15 for _, e in t.v.events))
        self.assertEqual(t.left(), 1000)

    def test_a_stomped_fruit_put_in_the_stew_takes_three(self) -> None:
        for patched in (False, True):
            t = Tree(patched)
            t.villager()
            # A stew waiting for its fruit (0x42DDA0: state 4, no fruit in yet), its item listener registered for
            # the stomped fruit (0x413486) and the cauldron's spot open (0x46D880(0x18)).
            t.v.w32(STEW + 0xB10, 4)
            t.v.w32(STEW_LISTENER, STEW_VTABLE)
            t.v.w8(CAULDRON_SPOT, 1)
            t.v.call(ITEM_LISTEN, 0x4CC0A0, 0x37, STEW_LISTENER)
            paid, _, got = t.v.run_trip(fe.FRUIT)
            self.assertEqual((paid, got), (-1, []))       # no food: the fruit went to the stew
            self.assertEqual(t.v.food(), 1000)
            self.assertEqual(t.v.uc.mem_read(STEW + 0xB23, 1)[0], 1)   # the stew has its fruit
            if patched:
                self.assertEqual(t.left(), 997)

    def test_the_stew_takes_nothing_until_the_fruit_is_in_the_pot(self) -> None:
        t = Tree()
        t.villager()
        t.v.w32(STEW + 0xB10, 4)
        t.v.w32(STEW_LISTENER, STEW_VTABLE)
        t.v.w8(CAULDRON_SPOT, 1)
        t.v.call(ITEM_LISTEN, 0x4CC0A0, 0x37, STEW_LISTENER)
        t.v.start(fe.FRUIT)
        while t.v.uc.mem_read(STEW + 0xB23, 1)[0] == 0:
            self.assertEqual(t.left(), 1000)              # decided, carried: nothing taken yet
            for _ in range(100):
                t.v.step_frame()
        self.assertEqual(t.left(), 997)


@unittest.skipUnless(HAVE_EMULATOR, "needs pefile, unicorn, the stock executable and research/game-data/vv4")
class EmptyTree(unittest.TestCase):
    def test_fewer_than_three_refuses_a_drop_like_the_empty_bush(self) -> None:
        # The empty blackberry bush's refusal (0x46F881): action 0x3F ("Refusing") with the text 0xA7, "There is
        # not enough to harvest.", and -1.
        for fruit in (2, 0):
            t = Tree(files={side(): tree_file(fruit, roster=[identity("Ana")])})
            t.villager()
            self.assertEqual(t.drop(), (0x3F, 0xA7, -1), fruit)
            self.assertEqual(t.v.r32(t.v.rec(0) + REC_ACTION), 0x3F)
            self.assertEqual(t.left(), fruit)             # a refusal takes nothing
        t = Tree(files={side(): tree_file(3, roster=[identity("Ana")])})
        t.villager()
        self.assertEqual(t.drop()[0], fe.FRUIT)
        s = Tree(patched=False)
        s.villager()
        self.assertEqual(s.drop()[0], fe.FRUIT)

    def test_the_refusal_is_the_bushs_own(self) -> None:
        """The bush's drop with 3 berries or fewer starts the same action with the same block."""
        t = Tree()
        r = t.villager()
        seen: list[tuple[int, int, int]] = []

        def started(*_):
            sp = t.v.uc.reg_read(UC_X86_REG_ESP)
            block = t.v.r32(sp + 8) & 0xFFFFFFFF
            seen.append((t.v.r32(sp + 4), t.v.r32(block), t.v.r32(block + 4)))

        hook = t.v.uc.hook_add(UC_HOOK_CODE, started, begin=DO_ACTION, end=DO_ACTION)
        t.v.call(BUSH, 0, 0, r, 0)                        # the bush holds 0 berries here
        t.v.uc.hook_del(hook)
        self.assertEqual(seen[0], (0x3F, 0xA7, -1))

    def test_a_trip_at_the_bin_with_fewer_than_three_pays_nothing(self) -> None:
        t = Tree(files={side(): tree_file(4, roster=[identity("Ana"), identity("Bo")])})
        t.villager("Ana", index=0)
        t.villager("Bo", index=1)
        t.v.start(fe.FRUIT, 0)
        t.v.start(fe.FRUIT, 1)
        for _ in range(9000):
            t.v.step_frame(0)
            t.v.step_frame(1)
        self.assertEqual(sum(1 for _, e in t.v.events if e == 15), 2)   # both reached the bin
        self.assertEqual(t.credits(3), 1)                 # one paid: 4 -> 1, the other found 1
        self.assertEqual(t.left(), 1)

    def dispatch_options(self, t: Tree) -> list[int]:
        seen: list[int] = []
        hook = t.v.uc.hook_add(UC_HOOK_CODE, lambda u, *_: seen.append(u.reg_read(UC_X86_REG_EDI)),
                               begin=0x463A62, end=0x463A62)
        t.v.call(DISPATCHER, t.v.rec(0), 0)
        t.v.uc.hook_del(hook)
        return seen

    def test_the_dispatcher_does_not_offer_an_empty_tree(self) -> None:
        full = Tree()
        full.villager()
        self.assertEqual(self.dispatch_options(full), [1])            # the fruit, the only option
        empty = Tree(files={side(): tree_file(2, roster=[identity("Ana")])})
        empty.villager()
        self.assertEqual(self.dispatch_options(empty), [])            # nothing to offer: no rand(n) at all
        self.assertEqual(empty.v.r32(empty.v.rec(0) + REC_ACTION), 0)
        stock = Tree(patched=False)
        stock.villager()
        self.assertEqual(self.dispatch_options(stock), [1])

    def test_the_task_gate_clears_a_fruit_task_on_an_empty_tree(self) -> None:
        for fruit in (1000, 2):
            t = Tree(files={side(): tree_file(fruit, roster=[identity("Ana")])})
            r = t.villager(task=2)
            for caller in GATE_ROLLS:
                t.v.by_caller[caller] = 99                # the villager does not refuse its task
            t.v.call(TASK_GATE, r)
            action = t.v.r32(r + REC_ACTION)
            if fruit == 1000:
                self.assertIn(action, range(100, 105))   # action 100 goes on to its fruit spot, 101..104
                self.assertEqual(t.v.r32(r + REC_TASK), 2)
            else:
                self.assertNotIn(action, range(100, 105))
                self.assertEqual(t.v.r32(r + REC_TASK), 0)


@unittest.skipUnless(HAVE_EMULATOR, "needs pefile, unicorn, the stock executable and research/game-data/vv4")
class CatchUp(unittest.TestCase):
    def catch_up(self, t: Tree, behind: int) -> None:
        r = t.v.rec(0)
        t.v.w32(r + fe.AGE, 500)
        t.v.w32(r + fe.PROC_AGE, 500 - behind)
        t.v.by_caller[BONUS_ROLL] = 0                     # every bonus roll passes (rand(100) < Farming - 25)
        t.v.life_tick(count_turns=True)
        self.assertEqual(t.v.r32(r + fe.PROC_AGE), 500)

    def test_the_bonus_takes_five_and_stops_when_fewer_are_left(self) -> None:
        stock = Tree(patched=False)
        stock.villager()
        self.catch_up(stock, 10)
        self.assertEqual(stock.credits(5), 8)             # every unit but the last 2
        t = Tree(files={side(): tree_file(12, roster=[identity("Ana")])})
        t.villager()
        self.catch_up(t, 10)
        self.assertEqual(t.credits(5), 2)                 # 12 -> 7 -> 2, then nothing
        self.assertEqual(t.left(), 2)

    def test_the_tree_refills_every_40_units_across_catch_up(self) -> None:
        t = Tree(files={side(): tree_file(0, roster=[identity("Ana")])})
        t.villager()
        self.catch_up(t, 45)
        # Units 1..40 find the tree empty; the 40th unit refills it; units 41..43 pay (44 and 45 are the last 2).
        self.assertEqual(t.credits(5), 3)
        self.assertEqual(t.left(), 1000 - 15)

    def test_the_tree_refills_in_live_play(self) -> None:
        t = Tree(files={side(): tree_file(0, units=38, roster=[identity("Ana")])})
        r = t.villager()
        for age in (501, 502):
            t.v.w32(r + fe.AGE, age)
            t.v.w32(r + fe.PROC_AGE, age - 1)
            t.v.life_tick(count_turns=True)
            self.assertEqual(t.left(), 0 if age == 501 else 1000)

    def test_only_the_reference_villager_counts(self) -> None:
        t = Tree(files={side(): tree_file(0, units=38, roster=[identity("Ana"), identity("Bo")])})
        for i, name in enumerate(("Ana", "Bo")):
            r = t.villager(name, index=i)
            t.v.w32(r + fe.AGE, 501)
            t.v.w32(r + fe.PROC_AGE, 500)
        t.v.life_tick(count_turns=True)                   # one unit for two villagers: one unit for the tree
        self.assertEqual(t.left(), 0)


@unittest.skipUnless(HAVE_EMULATOR, "needs pefile, unicorn, the stock executable and research/game-data/vv4")
class TheFile(unittest.TestCase):
    def test_a_save_writes_the_file_and_a_new_session_reads_it(self) -> None:
        t = Tree()
        t.villager()
        t.v.run_trip(fe.FRUIT)
        t.v.run_trip(fe.FRUIT)
        t.save()
        raw = t.files.files[side()]
        magic, version, game, slot, fruit, units, count, _ = struct.unpack_from("<8I", raw)
        self.assertEqual((magic, version, game, slot, fruit, units, count), (0x46345656, 1, 4, 1, 994, 0, 1))
        self.assertEqual(len(raw), 32 + 1024)
        self.assertEqual(struct.unpack_from("<I", raw, 32)[0], identity("Ana"))
        again = Tree(files=dict(t.files.files))
        again.villager()
        self.assertEqual(again.left(), 994)

    def test_a_load_reads_the_file_again(self) -> None:
        t = Tree()
        t.villager()
        self.assertEqual(t.left(), 1000)
        t.files.files[side()] = tree_file(500, roster=[identity("Ana")])
        self.assertEqual(t.left(), 1000)                  # in play: the companion's own count
        t.load()
        self.assertEqual(t.left(), 500)

    def test_start_over_and_another_village_start_full(self) -> None:
        old = {side(): tree_file(2, roster=[identity("Old")])}
        t = Tree(files=dict(old))
        t.villager("New")                                 # Start Over's founders share no one with the file
        self.assertEqual(t.left(), 1000)
        self.assertEqual(t.drop()[0], fe.FRUIT)
        t.save()
        self.assertEqual(struct.unpack_from("<I", t.files.files[side()], 32)[0], identity("New"))
        wiped = Tree()                                    # Start Over emptied the save's folder
        wiped.villager("Old")
        self.assertEqual(wiped.left(), 1000)

    def test_the_same_village_in_play_after_start_over_in_the_slot(self) -> None:
        t = Tree(files={side(): tree_file(2, roster=[identity("Old")])})
        r = t.villager("Old")
        self.assertEqual(t.left(), 2)
        t.v.uc.mem_write(r + REC_NAME, b"New\0")          # the slot now holds a new tribe
        t.v.process.tick += 1000                          # the companion looks at the roster again
        self.assertEqual(t.left(), 1000)

    def test_another_slots_file_and_a_bad_file_are_not_used(self) -> None:
        t = Tree(files={side(2): tree_file(2, roster=[identity("Ana")], slot=2)})
        t.villager()
        self.assertEqual(t.left(), 1000)
        bad = Tree(files={side(): tree_file(2, roster=[identity("Ana")], magic=0x12345678)})
        bad.villager()
        self.assertEqual(bad.left(), 1000)
        self.assertNotIn(side(), bad.files.files)         # set aside, never read again
        self.assertTrue(any(".unreadable-" in k for k in bad.files.files))


@unittest.skipUnless(HAVE_EMULATOR, "needs pefile, unicorn, the stock executable and research/game-data/vv4")
class EveryBuild(unittest.TestCase):
    def test_every_mode_installs_and_a_trip_takes_three(self) -> None:
        for mode in MODES:
            with self.subTest(mode=mode):
                t = Tree(exe=render(mode))
                t.villager()
                t.v.run_trip(fe.FRUIT)
                self.assertEqual(t.left(), 997)

    def test_256_villagers_reads_its_own_table(self) -> None:
        image = render("immediate_fixed", expanded=True)
        t = Tree(exe=image, files={side(): tree_file(2, roster=[identity("Ana")])})
        self.assertEqual(t.readout(), "Fruit remaining: 1000")      # no one alive in the 256 table yet
        rec = 0x800000 + 0x44
        t.v.w8(rec + 0x1CC4, 1)
        t.v.w32(rec + 0x1B90, 1)
        t.v.uc.mem_write(rec + REC_NAME, b"Ana\0")
        t.v.process.tick += 1000
        t.load()
        self.assertEqual(t.readout(), "Fruit remaining: 2")

    def test_the_sites_are_stock_in_every_rendered_build(self) -> None:
        stock = fe.STOCK.read_bytes()
        pe = pefile.PE(data=stock, fast_load=True)
        for mode, expanded in [(m, False) for m in MODES] + [("immediate_fixed", True)]:
            data = render(mode, expanded)
            out = pefile.PE(data=data, fast_load=True)
            for va, n in SITES.items():
                a, b = pe.get_offset_from_rva(va - 0x400000), out.get_offset_from_rva(va - 0x400000)
                self.assertEqual(data[b:b + n], stock[a:a + n], (mode, expanded, hex(va)))


class Manifest(unittest.TestCase):
    def test_the_row(self) -> None:
        row = json.loads(FEATURE.read_text(encoding="utf-8"))
        self.assertEqual(row["name"], "Yellow Fruit Trees are No Longer Unlimited")
        self.assertEqual(row["patches"], [])              # no executable byte: removing it is the stock game
        self.assertEqual(row["companion_files"][0]["destination"], "VVFP VV4 Fruit Supply.dll")
        import hashlib
        self.assertEqual(row["companion_files"][0]["sha256"], hashlib.sha256(DLL.read_bytes()).hexdigest().upper())
        self.assertEqual({int(d["va"], 16) for d in row["runtime_detours"]},
                         set(SITES) | {VTABLE + 16, VTABLE + 12})
        self.assertIn("VVFP VV4 Fruit Supply.dll", patcher.STARTUP_LOADER_COMPANIONS_2)

    def test_off_by_default_owners_defaults_and_classic(self) -> None:
        import vv_fun_patcher_gui as gui
        self.assertIn(ID, gui.DEFAULT_OFF_FUN_PATCH_IDS)
        classic = json.loads((ROOT / "data" / "vv4_classic_vv_difficulty_feature.json").read_text(encoding="utf-8"))
        self.assertIn(ID, classic["dependencies"])


if __name__ == "__main__":
    unittest.main()
