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


# ---- The Secret City, New Believers: the villagers' effects; The Lost Children: the stew pot (the owner, 2026-11-16)
# Per game: the first villager record (stock table), record size, effect list, count, entry size, end offset, the most
# entries, the autosave site, the save routine, the writer's per-villager call, the vtable slots the remove routine
# calls (2 arguments, 1 argument).
FX = {
    3: dict(records=0x59E124, size=0x1F8C, effects=0xF50, count=0xFB0, entry=0x18, end=0x10, max=4,
            autosave=0x427DF3, autosave_stock="E998FFFFFF", save=0x427D90, save_args=0,
            strip=0x45EF9C, strip_stock="E82F6EFFFF", slots=(8, 0xC)),
    5: dict(records=0x554190, size=0x2F44, effects=0x1D3C, count=0x1E8C, entry=0x1C, end=0x14, max=12,
            autosave=0x424684, autosave_stock="E897FFFFFF", save=0x424620, save_args=1,
            strip=0x46F9CF, strip_stock="E8EC66FFFF", slots=(0, 4)),
}
VV5_PAUSE_SITE, VV5_PAUSE_STOCK, VV5_RESUME = 0x41EE6E, "D9E82B4E28D95C2410EB48", 0x41EEC1
VV2_SITE, VV2_STOCK, VV2_POT = 0x43B6B8, "8B97E4EA0200", 0x30450


def stock_process(game: int, dll: bool = True, install: bool = True):
    from story_emulator import Process
    p = Process(edit.stock_exe(game).read_bytes(), DLL if dll else None)
    if dll and install:
        p.export("VvfpStartup", game, 0)
    return p


def target(p, site: int) -> int:
    return (site + 5 + struct.unpack("<i", p.read(site + 1, 4))[0]) & MASK


def have_game(game: int) -> bool:
    return edit.have(game) and DLL.is_file()


class LaterGamesEffects:
    """A villager (record 0) carrying `n` effects, each owned by a stand-in object whose vtable answers the remove
    routine's two calls; the save routine replaced by a stand-in that runs the writer's per-villager call site."""

    def village(self, game: int, dll: bool = True, install: bool = True, n: int = 3):
        f = FX[game]
        p = stock_process(game, dll, install)
        code = p.alloc(16)
        p.write(code, b"\xC2\x08\x00\x90\xC2\x04\x00")
        vtable = p.alloc(16)
        p.put32(vtable + f["slots"][0], code)
        p.put32(vtable + f["slots"][1], code + 4)
        owner = p.alloc(16)
        p.put32(owner, vtable)
        rec = f["records"]
        for k in range(n):
            p.write(rec + f["effects"] + k * f["entry"], struct.pack("<II", owner, 10 + k) + b"\0" * (f["entry"] - 8))
            p.put32(rec + f["effects"] + k * f["entry"] + f["end"], 1_000_000 + 60 * k)
        p.put32(rec + f["count"], n)
        strip = target(p, f["strip"])
        ret = b"\xC3" if f["save_args"] == 0 else b"\xC2\x04\x00"
        p.write(f["save"], b"\xB9" + struct.pack("<I", rec) + b"\xB8" + struct.pack("<I", strip) + b"\xFF\xD0" + ret)
        return p, rec

    def autosave(self, p, game: int) -> None:
        f = FX[game]
        p.call(target(p, f["autosave"]), [0] * f["save_args"], ecx=0x4E0000)

    def other_save(self, p, game: int) -> None:
        f = FX[game]
        p.call(f["save"], [0] * f["save_args"], ecx=0x4E0000)

    def left(self, p, game: int) -> int:
        return p.u32(FX[game]["records"] + FX[game]["count"])


class OnlyTheAutosaveKeepsEffects(LaterGamesEffects, unittest.TestCase):
    """The Secret City and New Believers: the save writer ends every villager's effects; with the DLL the autosave
    runs with a flag that makes the writer's call skip that, and every other save is the base game's."""

    def test_the_autosave_keeps_every_effect(self) -> None:
        for game in (3, 5):
            if not have_game(game):
                continue
            with self.subTest(game=game):
                f = FX[game]
                p, rec = self.village(game)
                before = p.read(rec + f["effects"], f["count"] + 4 - f["effects"])
                self.autosave(p, game)
                self.assertEqual(p.read(rec + f["effects"], f["count"] + 4 - f["effects"]), before)
                self.other_save(p, game)                       # the flag is down again
                self.assertEqual(self.left(p, game), 0)

    def test_every_other_save_and_the_stock_autosave_end_them(self) -> None:
        for game in (3, 5):
            if not have_game(game):
                continue
            for dll in (True, False):
                with self.subTest(game=game, dll=dll):
                    p, _ = self.village(game, dll)
                    self.other_save(p, game)
                    self.assertEqual(self.left(p, game), 0)
                    if not dll:
                        p, _ = self.village(game, dll)
                        self.assertEqual(target(p, FX[game]["autosave"]), FX[game]["save"])
                        self.autosave(p, game)
                        self.assertEqual(self.left(p, game), 0)

    def test_the_sites_are_written_together(self) -> None:
        for game in (3, 5):
            if not have_game(game):
                continue
            f = FX[game]
            pause = {3: (SITES[3][0], SITES[3][1].hex().upper()), 5: (VV5_PAUSE_SITE, VV5_PAUSE_STOCK)}[game]
            sites = [(f["autosave"], f["autosave_stock"]), (f["strip"], f["strip_stock"]), pause]
            p = stock_process(game)
            for va, stock in sites:
                self.assertNotEqual(p.read(va, len(stock) // 2).hex().upper(), stock, hex(va))
            for va, _stock in sites:
                with self.subTest(game=game, changed=hex(va)):
                    p = stock_process(game, install=False)
                    p.write(va + 1, bytes([p.read(va + 1, 1)[0] ^ 0xFF]))
                    p.export("VvfpStartup", game, 0)
                    for other, other_stock in sites:
                        if other != va:
                            self.assertEqual(p.read(other, len(other_stock) // 2).hex().upper(), other_stock)


class TheSecretCityEffectsPause(unittest.TestCase):
    """A potion's effect ends when the computer's clock reaches its end (+0x10); with the DLL coming out of a pause
    (the real set_speed) moves every set end on by the time paused."""

    ENDS = (1_000_600, 1_000_300, 0, 1_000_001)

    def _base(self, record: int) -> int:
        return FX[3]["records"] + record * FX[3]["size"]

    def _village(self, c: Clock) -> None:
        p, f = c.emu.p, FX[3]
        for record in (0, 77, 149):
            for n, end in enumerate(self.ENDS):
                p.put32(self._base(record) + f["effects"] + n * f["entry"] + f["end"], end)
            p.put32(self._base(record) + f["count"], len(self.ENDS))
        p.put32(self._base(5) + f["count"], 9)                       # not a real count: left alone
        p.put32(self._base(5) + f["effects"] + f["end"], 1_000_100)

    def _ends(self, c: Clock, record: int) -> list[int]:
        f = FX[3]
        return [c.emu.p.u32(self._base(record) + f["effects"] + n * f["entry"] + f["end"])
                for n in range(len(self.ENDS))]

    def test_a_pause_stops_every_effect(self) -> None:
        if not have(3):
            self.skipTest("the stock Secret City or the DLL is missing")
        now = 1_000_000
        for dll in (False, True):
            for before, after in ((6, 6), (3, 6), (10, 3)):
                with self.subTest(dll=dll, before=before, after=after):
                    c = Clock(3, dll=dll)
                    c.start(before, now, now + 50_000)
                    self._village(c)
                    c.at(now + 30, 999)
                    c.at(now + 30 + 600, after)
                    shift = 600 if dll else 0
                    for record in (0, 77, 149):
                        self.assertEqual(self._ends(c, record), [e + shift if e else 0 for e in self.ENDS])
                    self.assertEqual(c.emu.p.u32(self._base(5) + FX[3]["effects"] + FX[3]["end"]), 1_000_100)

    def test_a_speed_change_while_running_moves_nothing(self) -> None:
        if not have(3):
            self.skipTest("the stock Secret City or the DLL is missing")
        now = 1_000_000
        c = Clock(3, dll=True)
        c.start(6, now, now + 50_000)
        self._village(c)
        c.at(now + 30, 3)
        c.at(now + 60, 10)
        self.assertEqual(self._ends(c, 0), list(self.ENDS))


class NewBelieversEffectsPause(unittest.TestCase):
    """The game clock's speed routine 0x41EE00 from a pause (rate 0): from 0x41EE61 (eax = now) to the rescale
    0x41EEC1, run for real; with the DLL every set effect end moves on by now - the pause's wall clock."""

    ENDS = (1_000_015, 1_000_035, 0)

    def run_branch(self, dll: bool, now: int, paused_at: int):
        p, f = stock_process(5, dll), FX[5]
        for record in (0, 149):
            base = f["records"] + record * f["size"]
            for n, end in enumerate(self.ENDS):
                p.put32(base + f["effects"] + n * f["entry"] + f["end"], end)
            p.put32(base + f["count"], len(self.ENDS))
        clock = p.alloc(0x40)
        p.put32(clock + 0x20, 0)
        p.put32(clock + 0x24, 6)
        p.put32(clock + 0x28, paused_at)
        p.call(0x41EE61, [0] * 8, regs={"eax": now, "esi": clock}, until=VV5_RESUME)
        return p

    def test_a_pause_stops_every_effect(self) -> None:
        if not have_game(5):
            self.skipTest("the stock New Believers or the DLL is missing")
        for dll in (False, True):
            with self.subTest(dll=dll):
                p, f = self.run_branch(dll, 1_000_620, 1_000_020), FX[5]
                shift = 600 if dll else 0
                for record in (0, 149):
                    base = f["records"] + record * f["size"]
                    got = [p.u32(base + f["effects"] + n * f["entry"] + f["end"]) for n in range(len(self.ENDS))]
                    self.assertEqual(got, [e + shift if e else 0 for e in self.ENDS])
                self.assertEqual(p.reg("ecx"), 600)            # the stock branch's own result is unchanged


class TheLostChildrenStewPotPauses(unittest.TestCase):
    """The village step 0x43B690 while paused (from 0x43B6B8: eax = now, edi = the game) moves its real-clock timers
    on by the time since its last step; with the DLL the stew pot's end (+0x30450) moves with them."""

    def step(self, dll: bool, pot: int):
        p = stock_process(2, dll)
        game = p.alloc(0x31000)
        p.put32(game + 0x2EAE4, 1_000)                 # the last step
        p.put32(game + 0x2EAE0, 5_000)
        p.put32(game + VV2_POT, pot)
        p.call(VV2_SITE, [], regs={"eax": 1_600, "edi": game}, until=0x43B6CE)
        return p.u32(game + VV2_POT), p.u32(game + 0x2EAE0)

    def test_the_pot_pauses(self) -> None:
        if not have_game(2):
            self.skipTest("the stock Lost Children or the DLL is missing")
        self.assertEqual(self.step(True, 2_000), (2_600, 5_600))
        self.assertEqual(self.step(False, 2_000), (2_000, 5_600))
        self.assertEqual(self.step(True, 0), (0, 5_600))     # no stew: nothing to move

    def test_a_changed_byte_installs_nothing(self) -> None:
        if not have_game(2):
            self.skipTest("the stock Lost Children or the DLL is missing")
        for va in (0x43B6AF, VV2_SITE + 2, 0x43B6CD):
            with self.subTest(changed=hex(va)):
                p = stock_process(2, install=False)
                p.write(va, bytes([p.read(va, 1)[0] ^ 0xFF]))
                p.export("VvfpStartup", 2, 0)
                if not VV2_SITE <= va < VV2_SITE + 6:
                    self.assertEqual(p.read(VV2_SITE, 6).hex().upper(), VV2_STOCK)
                else:
                    self.assertEqual(p.read(VV2_SITE, 1), b"\x8B")


class ActionsEndOnlyTheirEffect(unittest.TestCase):
    """The owner (2026-11-17): a game action that ended every effect ends only the one it is about.  The Secret City:
    the hiccups' drink (18), the nonsense talk (38), the breath's meal (36, 37); New Believers: the "stop and wait"
    reset ends the bees in "Hiding in the water" (170) and nothing in any other action."""

    VV3_SITES = {0x42131F: (18,), 0x4218B6: (38,), 0x421AE1: (36, 37)}
    VV3_OWNER = 0x582610
    VV5_RESET, VV5_BEES, VV5_OTHER, VV5_ACTION = 0x467524, 0x4DE000, 0x51C430, 0x1D10

    def villager(self, game: int, entries, dll: bool = True):
        """Record 0 with `entries` [(owner, id)]; every owner's vtable answers the remove routine's two calls."""
        f = FX[game]
        p = stock_process(game, dll)
        code = p.alloc(16)
        p.write(code, b"\xC2\x08\x00\x90\xC2\x04\x00")
        vtable = p.alloc(16)
        p.put32(vtable + f["slots"][0], code)
        p.put32(vtable + f["slots"][1], code + 4)
        for owner in {o for o, _ in entries}:
            p.put32(owner, vtable)
        rec = f["records"]
        for k, (owner, number) in enumerate(entries):
            p.write(rec + f["effects"] + k * f["entry"], struct.pack("<Ii", owner, number) + b"\0" * (f["entry"] - 8))
            p.put32(rec + f["effects"] + k * f["entry"] + f["end"], 1_000_000 + k)
        p.put32(rec + f["count"], len(entries))
        return p, rec

    def left(self, p, game: int, rec: int) -> list[tuple[int, int]]:
        f = FX[game]
        return [struct.unpack("<Ii", p.read(rec + f["effects"] + k * f["entry"], 8))
                for k in range(p.u32(rec + f["count"]))]

    def test_the_secret_city(self) -> None:
        if not have_game(3):
            self.skipTest("the stock Secret City or the DLL is missing")
        everything = [(self.VV3_OWNER, n) for n in (18, 36, 37, 38)]       # 4 entries: the most a villager has
        for site, ends in self.VV3_SITES.items():
            for dll in (True, False):
                with self.subTest(site=hex(site), dll=dll):
                    p, rec = self.villager(3, everything, dll)
                    self.assertEqual(target(p, site) == 0x455DD0, not dll)
                    p.call(target(p, site), [], ecx=rec)
                    want = [e for e in everything if e[1] not in ends] if dll else []
                    self.assertEqual(self.left(p, 3, rec), want)

    def test_new_believers(self) -> None:
        if not have_game(5):
            self.skipTest("the stock New Believers or the DLL is missing")
        entries = [(self.VV5_BEES, 4), (self.VV5_OTHER, 9), (self.VV5_BEES, 6)]
        for action, dll, want in ((170, True, [(self.VV5_OTHER, 9)]), (158, True, entries), (7, True, entries),
                                  (170, False, []), (158, False, [])):
            with self.subTest(action=action, dll=dll):
                p, rec = self.villager(5, entries, dll)
                p.put32(rec + self.VV5_ACTION, action)
                p.call(target(p, self.VV5_RESET), [], ecx=rec)
                self.assertEqual(self.left(p, 5, rec), want)

    def test_a_changed_byte_writes_no_effect_site(self) -> None:
        for game, sites in ((3, list(self.VV3_SITES)), (5, [self.VV5_RESET])):
            if not have_game(game):
                continue
            for site in sites:
                with self.subTest(game=game, site=hex(site)):
                    p = stock_process(game, install=False)
                    stock = p.read(site, 5)
                    p.write(site - 1, bytes([p.read(site - 1, 1)[0] ^ 0xFF]))
                    p.export("VvfpStartup", game, 0)
                    self.assertEqual(p.read(site, 5), stock)
                    self.assertEqual(p.read(FX[game]["autosave"], 5).hex().upper(), FX[game]["autosave_stock"])


class ANewHomeIsUnchanged(unittest.TestCase):
    def test_nothing_is_written(self) -> None:
        if not have_game(1):
            self.skipTest("the stock A New Home or the DLL is missing")
        p0, p = stock_process(1, dll=False), stock_process(1)
        for va, n in ((0x41BFE3, 5), (0x42E830, 0x60)):            # the autosave's jump; the rescale
            self.assertEqual(p.read(va, n), p0.read(va, n))


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
