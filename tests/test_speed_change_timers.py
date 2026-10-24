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
