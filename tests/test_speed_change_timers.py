"""Fix Vanilla Bugs: unpausing at another speed rescales the clock's timers (The Secret City, The
Tree of Life; "VVFP Speed Change Timers.dll", native/vvfp_speed_timers).  Owner-approved 2026-10-24.

THE STOCK BUG, shown by running the stock routine set_speed (VV3 0x426630, VV4 0x41DBE0) in an
emulator: a timer set while running on Fast keeps its Fast wall length when the game is paused and
then unpaused on Normal (the pause key, then an Options speed button -- both are set_speed), because
from a paused clock the routine takes the factor 1 (VV3 0x42669F, VV4 0x41DC4E).  Running on Fast
and switching to Normal directly doubles it, as it should.

THE FIX: the same sequence with the shipped DLL installed (its VvfpStartup run on the stock
executable, and on The Secret City and The Tree of Life as the patcher renders them) rescales by
new / before, exactly as the running branch does; unpausing at the speed the game was paused at is
the stock result byte for byte; and the DLL installs nothing at all when any byte it checks is not
the stock one.

A New Home, The Lost Children and New Believers do not have the bug (their routine counts a paused
speed as Normal on both sides): shown here too, with their stock routines.

The live effect in a running game is NOT verified here.
"""
from __future__ import annotations

import functools
import struct
import sys
import unittest
from fractions import Fraction
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import test_save_speed_edit as edit  # noqa: E402  (the stock-routine emulation and its stand-ins)

DLL = ROOT / "assets" / "speed_timers" / "VVFP Speed Change Timers.dll"
SITES = {3: (0x42669F, bytes.fromhex("8B4628C744240C0000803FEB27")),
         4: (0x41DC4E, bytes.fromhex("D9E82B4E28D95C2410EB48"))}
WINDOW = {3: (0x426630, 0x113), 4: (0x41DBE0, 0x130)}
MASK = 0xFFFFFFFF


def f32(x: float) -> Fraction:
    return Fraction(struct.unpack("<f", struct.pack("<f", x))[0])


class Clock:
    """A game's clock object in the emulator, with one registered timer."""

    def __init__(self, game: int, *, dll: bool, install: bool = True):
        self.game = game
        self.emu = edit.Emulated(game, DLL if dll else None)
        if dll and install:
            self.emu.p.export("VvfpStartup", game, 0)
        _routine, _wall, self.obj, count = edit.SET_SPEED[game]
        self.cell = self.emu.p.alloc(4)
        self.emu.p.put32(self.obj, self.cell)
        self.emu.p.put32(count, 1)
        self.emu.cells = [self.cell]

    def start(self, rate: int, now: int, timer: int) -> None:
        p = self.emu.p
        for k, value in enumerate((rate, 6, now - 100, 50_000)):
            p.put32(self.obj + 0x20 + 4 * k, value)
        p.put32(self.cell, timer)

    def at(self, now: int, new: int) -> None:
        self.emu.now = now
        self.emu.set_speed(new)

    def timer(self) -> int:
        return self.emu.p.u32(self.cell)


def have(game: int) -> bool:
    return edit.have(game) and DLL.is_file()


class TheStockBug(unittest.TestCase):
    def check(self, game: int) -> None:
        now = 200_000_000
        for dll in (False, True):
            with self.subTest(game=game, dll=dll):
                c = Clock(game, dll=dll)
                c.start(3, now, now + 36_000)               # 10 hours left on Fast
                c.at(now + 1_000, 999)                      # the pause key, 1,000 s later
                c.at(now + 5_000, 6)                        # unpaused on Normal 4,000 s later
                left = c.timer() - (now + 5_000)
                if not dll:
                    self.assertEqual(left, 35_000)          # the stock bug: still Fast's length
                else:
                    self.assertEqual(left, 70_000)          # twice: Normal's length
                # Switching speed while running was always right.
                c.start(3, now, now + 36_000)
                c.at(now + 1_000, 6)
                self.assertEqual(c.timer() - (now + 1_000), 70_000)

    def test_the_secret_city(self) -> None:
        if not have(3):
            self.skipTest("the stock Secret City or the DLL is missing")
        self.check(3)

    def test_the_tree_of_life(self) -> None:
        if not have(4):
            self.skipTest("the stock Tree of Life or the DLL is missing")
        self.check(4)


class TheFix(unittest.TestCase):
    def every_pair(self, game: int) -> None:
        now = 150_000_000
        for before in (3, 6, 10):
            for new in (3, 6, 10):
                for left in (1, 777, 36_000, 120_001):
                    with self.subTest(game=game, before=before, new=new, left=left):
                        stock, fixed = Clock(game, dll=False), Clock(game, dll=True)
                        for c in (stock, fixed):
                            c.start(before, now, now + 123 + left)
                            c.at(now + 123, 999)              # paused at now + 123
                            c.at(now + 9_999, new)            # unpaused 9,876 s later
                        if new == before:
                            self.assertEqual(fixed.timer(), stock.timer())
                            self.assertEqual(fixed.emu.clock_fields(), stock.emu.clock_fields())
                            continue
                        pause = now + 123
                        factor = f32(new / before)
                        want = (int((pause + left) * factor) + (now + 9_999) - int(pause * factor)) & MASK
                        self.assertEqual(fixed.timer(), want)
                        self.assertEqual(fixed.emu.clock_fields(), stock.emu.clock_fields())

    def test_the_secret_city(self) -> None:
        if not have(3):
            self.skipTest("the stock Secret City or the DLL is missing")
        self.every_pair(3)

    def test_the_tree_of_life(self) -> None:
        if not have(4):
            self.skipTest("the stock Tree of Life or the DLL is missing")
        self.every_pair(4)

    def test_installs_on_the_rendered_builds(self) -> None:
        import vv_fun_patcher as patcher
        for game in (3, 4):
            if not have(game):
                continue
            build = {b.id: b for b in patcher.load_builds()}[f"vv{game}"]
            ids = [p.id for p in patcher.load_public_fun_patches()
                   if p.game_id == f"vv{game}" and p.id not in patcher.ALTERNATIVE_FUN_PATCH_IDS
                   and p.id not in patcher.EXPERIMENTAL_FUN_PATCH_IDS]
            for mode in ("stock", "collection_progression", "immediate_fixed"):
                with self.subTest(game=game, mode=mode):
                    data, _ = patcher.render_patched_bytes(edit.stock_exe(game), build, mode, ids)
                    from story_emulator import Process
                    p = Process(bytes(data), DLL)
                    site, stock = SITES[game]
                    self.assertEqual(p.read(site, len(stock)), stock)
                    p.export("VvfpStartup", game, 0)
                    self.assertEqual(p.read(site, 1), b"\xE9")


class AllOrNothing(unittest.TestCase):
    def test_one_changed_byte_installs_nothing(self) -> None:
        for game in (3, 4):
            if not have(game):
                continue
            base, size = WINDOW[game]
            site, stock = SITES[game]
            for offset in (0, 0x30, size - 1, site - base + 4):
                with self.subTest(game=game, offset=offset):
                    c = Clock(game, dll=True, install=False)
                    p = c.emu.p
                    original = p.read(base + offset, 1)
                    p.write(base + offset, bytes([original[0] ^ 0xFF]))
                    before = p.read(base, size)
                    p.export("VvfpStartup", game, 0)
                    self.assertEqual(p.read(base, size), before)       # not one byte written
            with self.subTest(game=game, constant="2^32"):
                c = Clock(game, dll=True, install=False)
                p = c.emu.p
                two32 = 0x47F510 if game == 3 else 0x48C4C0
                p.write(two32, b"\x00\x00\x80\x3F")
                p.export("VvfpStartup", game, 0)
                self.assertEqual(p.read(site, len(stock)), stock)

    def test_another_game_installs_nothing(self) -> None:
        if not have(3):
            self.skipTest("the stock Secret City or the DLL is missing")
        c = Clock(3, dll=True, install=False)
        c.emu.p.export("VvfpStartup", 5, 0)
        site, stock = SITES[3]
        self.assertEqual(c.emu.p.read(site, len(stock)), stock)


VV4_RECORDS, VV4_RECORD_SIZE = 0x50E5AC, 0x2E3C       # the population manager 0x50E568 + 0x44, 150 records
VV4_EFFECTS, VV4_COUNT, VV4_EFFECT = 0x1D0C, 0x1E5C, 0x1C


class TheVillagersEffectsPause(unittest.TestCase):
    """The Tree of Life (the owner, 2026-11-16: "All of those effect timers should pause when the game is paused"):
    each villager effect ends when the computer's clock reaches the end it keeps (+0x14 of its entry); with the DLL,
    coming out of a pause moves every set end on by the time paused, through the real set_speed."""

    ENDS = (1_000_240, 1_000_180, 1_000_600, 0, 1_000_001)     # clean body, gunk, stew wait, no end, about to end

    def _village(self, c: Clock) -> None:
        p = c.emu.p
        for record in (0, 77, 149):
            base = VV4_RECORDS + record * VV4_RECORD_SIZE
            for n, end in enumerate(self.ENDS):
                p.put32(base + VV4_EFFECTS + n * VV4_EFFECT + 0x14, end)
            p.put32(base + VV4_COUNT, len(self.ENDS))
        junk = VV4_RECORDS + 5 * VV4_RECORD_SIZE              # a record whose count is not a real one
        p.put32(junk + VV4_COUNT, 0x40)
        p.put32(junk + VV4_EFFECTS + 0x14, 1_000_100)

    def _ends(self, c: Clock, record: int) -> list[int]:
        base = VV4_RECORDS + record * VV4_RECORD_SIZE
        return [c.emu.p.u32(base + VV4_EFFECTS + n * VV4_EFFECT + 0x14) for n in range(len(self.ENDS))]

    def test_a_pause_stops_every_effect(self) -> None:
        if not have(4):
            self.skipTest("the stock Tree of Life or the DLL is missing")
        now = 1_000_000
        for dll in (False, True):
            for before, after in ((6, 6), (3, 6), (10, 3)):
                with self.subTest(dll=dll, before=before, after=after):
                    c = Clock(4, dll=dll)
                    c.start(before, now, now + 50_000)
                    self._village(c)
                    c.at(now + 30, 999)                     # paused 30 s into the effects
                    c.at(now + 30 + 600, after)             # ten minutes later, unpaused (any speed)
                    shift = 600 if dll else 0
                    for record in (0, 77, 149):
                        self.assertEqual(self._ends(c, record),
                                         [e + shift if e else 0 for e in self.ENDS])
                    junk = VV4_RECORDS + 5 * VV4_RECORD_SIZE
                    self.assertEqual(c.emu.p.u32(junk + VV4_EFFECTS + 0x14), 1_000_100)

    def test_a_speed_change_while_running_moves_nothing(self) -> None:
        if not have(4):
            self.skipTest("the stock Tree of Life or the DLL is missing")
        now = 1_000_000
        c = Clock(4, dll=True)
        c.start(6, now, now + 50_000)
        self._village(c)
        c.at(now + 30, 3)                                   # Fast, while running: effects stay real time
        c.at(now + 60, 10)
        self.assertEqual(self._ends(c, 0), list(self.ENDS))


class EffectsProcess:
    """The Tree of Life in the emulator with one villager carrying the clean body, the glow, the gunk and a stew's wait."""

    AUTOSAVE_SITE, STRIP_SITE, SLOT_SAVER = 0x41F1C4, 0x4660C4, 0x41F160
    SPARKLES, SPARKLES_VT, STEWS, STEWS_VT = 0x4CE1C0, 0x48D54C, 0x4D6F50, 0x48D5C4
    # (manager, id, kind): the clean body, the glow, the sticky gunk, a stew's wait
    ENTRIES = ((0x4CE1C0, 7, 2), (0x4CE1C0, 12, 1), (0x4CE1C0, 20, 5), (0x4D6F50, 8, -1))

    def _process(self, install: bool = True):
        from story_emulator import Process
        p = Process(edit.stock_exe(4).read_bytes(), DLL)
        if install:
            p.export("VvfpStartup", 4, 0)
        p.put32(self.SPARKLES, self.SPARKLES_VT)
        p.put32(self.STEWS, self.STEWS_VT)
        for sid in range(512):
            p.put32(self.SPARKLES + 4 + sid * 0x44, 0xFFFFFFFF)
        rec = VV4_RECORDS
        for n, (manager, sid, kind) in enumerate(self.ENTRIES):
            if manager == self.SPARKLES:
                p.put32(self.SPARKLES + 4 + sid * 0x44, kind & MASK)
            p.write(rec + VV4_EFFECTS + n * VV4_EFFECT,
                    struct.pack("<Iiiiiii", manager, sid, kind, 0, 0, 1_000_240, 0))
        p.put32(rec + VV4_COUNT, len(self.ENTRIES))
        return p, rec

    def _target(self, p, site: int) -> int:
        return (site + 5 + struct.unpack("<i", p.read(site + 1, 4))[0]) & MASK

    def _save_through(self, p, rec: int, autosave: bool) -> None:
        # The slot saver stand-in: one villager through the writer's call site's target (ecx = the record).
        strip = self._target(p, self.STRIP_SITE)
        p.write(self.SLOT_SAVER, b"\xB9" + struct.pack("<I", rec) + b"\xB8" + struct.pack("<I", strip)
                + b"\xFF\xD0\xC2\x04\x00")
        caller = self._target(p, self.AUTOSAVE_SITE) if autosave else self.SLOT_SAVER
        p.call(caller, [0], ecx=0x4E0000)

    def _left(self, p, rec: int) -> int:
        return p.u32(rec + VV4_COUNT)


class TheAutosaveKeepsTheEffects(EffectsProcess, unittest.TestCase):
    """The Tree of Life (the owner, 2026-11-16: "just the autosave should have all effects kept"): the save writer's
    per-villager call of 0x45EAA0 (0x4660C4) ends every effect; with the DLL the autosave's call of the slot saver
    (0x41F1C4) runs with a flag that makes that call skip it, and every other save is the base game's."""

    def test_the_sites_are_written_together(self) -> None:
        if not have(4):
            self.skipTest("the stock Tree of Life or the DLL is missing")
        p, _ = self._process()
        for site in (self.AUTOSAVE_SITE, self.STRIP_SITE):
            self.assertEqual(p.read(site, 1), b"\xE8")
            self.assertNotIn(self._target(p, site), (self.SLOT_SAVER, 0x45EAA0))
        p, _ = self._process(install=False)
        p.write(self.STRIP_SITE + 1, b"\x00")                       # one changed byte: neither is written
        p.export("VvfpStartup", 4, 0)
        self.assertEqual(p.read(self.AUTOSAVE_SITE, 5), bytes.fromhex("E897FFFFFF"))

    def test_the_autosave_keeps_every_effect(self) -> None:
        if not have(4):
            self.skipTest("the stock Tree of Life or the DLL is missing")
        p, rec = self._process()
        before = p.read(rec + VV4_EFFECTS, VV4_COUNT + 4 - VV4_EFFECTS)
        self._save_through(p, rec, autosave=True)
        self.assertEqual(p.read(rec + VV4_EFFECTS, VV4_COUNT + 4 - VV4_EFFECTS), before)
        self.assertEqual(self._left(p, rec), 4)
        # the flag is down again: the next other save ends them
        self._save_through(p, rec, autosave=False)
        self.assertEqual(self._left(p, rec), 0)

    def test_every_other_save_ends_every_effect(self) -> None:
        if not have(4):
            self.skipTest("the stock Tree of Life or the DLL is missing")
        for install in (True, False):
            with self.subTest(dll=install):
                p, rec = self._process(install)
                self._save_through(p, rec, autosave=False)
                self.assertEqual(self._left(p, rec), 0)
                self.assertEqual(p.u32(self.SPARKLES + 4 + 7 * 0x44), MASK)     # its sparkle freed

    def test_without_the_dll_the_autosave_ends_them(self) -> None:
        if not have(4):
            self.skipTest("the stock Tree of Life or the DLL is missing")
        p, rec = self._process(install=False)
        self._save_through(p, rec, autosave=True)                    # the stock call: the slot saver itself
        self.assertEqual(self._left(p, rec), 0)


class WipingGunkEndsOnlyTheGunk(EffectsProcess, unittest.TestCase):
    """The Tree of Life (the owner, 2026-11-16): the last step of "Wiping sticky gunk off on tree" called 0x45EAA0
    (0x46431C), which ends every effect of the villager; with the DLL that call ends only the gunk (kind 5)."""

    GUNK_SITE = 0x46431C

    def _wipe(self, p, rec: int) -> None:
        p.call(self._target(p, self.GUNK_SITE), [], ecx=rec)

    def _kinds(self, p, rec: int) -> list[tuple[int, int]]:
        return [struct.unpack("<Ii", p.read(rec + VV4_EFFECTS + n * VV4_EFFECT, 8)) for n in range(self._left(p, rec))]

    def test_only_the_gunk_ends(self) -> None:
        if not have(4):
            self.skipTest("the stock Tree of Life or the DLL is missing")
        p, rec = self._process()
        self.assertNotEqual(self._target(p, self.GUNK_SITE), 0x45EAA0)
        self._wipe(p, rec)
        self.assertEqual(self._kinds(p, rec), [(0x4CE1C0, 7), (0x4CE1C0, 12), (0x4D6F50, 8)])
        self.assertEqual(p.u32(self.SPARKLES + 4 + 20 * 0x44), MASK)        # the gunk's sparkle freed
        self.assertEqual(p.u32(self.SPARKLES + 4 + 7 * 0x44), 2)            # the clean body's kept
        self.assertEqual(p.u32(self.SPARKLES + 4 + 12 * 0x44), 1)           # the glow's kept

    def test_two_gunk_entries_and_none(self) -> None:
        if not have(4):
            self.skipTest("the stock Tree of Life or the DLL is missing")
        p, rec = self._process()
        # a second gunk sparkle first in the list: both go, the rest stay in order
        entries = [(0x4CE1C0, 30, 5)] + list(self.ENTRIES)
        p.put32(self.SPARKLES + 4 + 30 * 0x44, 5)
        for n, (manager, sid, kind) in enumerate(entries):
            p.write(rec + VV4_EFFECTS + n * VV4_EFFECT, struct.pack("<Iiiiiii", manager, sid, kind, 0, 0, 1_000_240, 0))
        p.put32(rec + VV4_COUNT, len(entries))
        self._wipe(p, rec)
        self.assertEqual(self._kinds(p, rec), [(0x4CE1C0, 7), (0x4CE1C0, 12), (0x4D6F50, 8)])
        self._wipe(p, rec)                                                   # no gunk: nothing changes
        self.assertEqual(self._kinds(p, rec), [(0x4CE1C0, 7), (0x4CE1C0, 12), (0x4D6F50, 8)])

    def test_without_the_dll_every_effect_ends(self) -> None:
        if not have(4):
            self.skipTest("the stock Tree of Life or the DLL is missing")
        p, rec = self._process(install=False)
        self.assertEqual(self._target(p, self.GUNK_SITE), 0x45EAA0)
        self._wipe(p, rec)
        self.assertEqual(self._left(p, rec), 0)

    def test_the_gunk_site_is_written_with_the_others(self) -> None:
        if not have(4):
            self.skipTest("the stock Tree of Life or the DLL is missing")
        p, _ = self._process(install=False)
        p.write(self.GUNK_SITE + 1, b"\x00")                         # one changed byte: no effect site is written
        p.export("VvfpStartup", 4, 0)
        self.assertEqual(p.read(self.AUTOSAVE_SITE, 5), bytes.fromhex("E897FFFFFF"))
        self.assertEqual(p.read(self.STRIP_SITE, 5), bytes.fromhex("E8D789FFFF"))


class TheOtherGamesAlreadyRescale(unittest.TestCase):
    """A New Home, The Lost Children, New Believers: pause on Fast, unpause on Normal (an Options
    button: rescale(paused, 6)) -- the stock routine gives Normal's length."""

    def test_stock_rescale_after_a_pause(self) -> None:
        for game in (1, 2, 5):
            if not edit.have(game):
                continue
            with self.subTest(game=game):
                rules = edit.clock.GAMES[game]
                save = edit.Save(game, edit.fixture(edit.FIXTURE[game]))
                now = save.get(rules.now)
                save.put(rules.timers[0], now + 36_000)
                emu = edit.Emulated(game)
                emu.load_state(save)
                emu.now = now
                emu.rescale(3, 999)                 # the pause key on Fast
                emu.rescale(1002, 6)                # Options: Normal
                emu.store_state(save)
                self.assertEqual(save.get(rules.timers[0]) - now, 72_000)


if __name__ == "__main__":
    unittest.main()
