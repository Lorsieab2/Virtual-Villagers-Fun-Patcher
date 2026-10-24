"""The patcher's game-speed changes are the game's own (src/vv_save_clock.py).

The owner (2026-10-24): The Secret City's campfire burned about 9 hours on Normal after a Repair
Saves & Logs "Game speed" change, which had written the save's speed dword and nothing else, so the
game's clock kept running at Fast underneath and the fire lit then got Fast's length.

Every test here runs the STOCK executable's own speed routine in an emulator (tests/story_emulator.py)
on the same save fixture the patcher edits, and asserts the patcher's bytes are the routine's bytes:

  * A New Home 0x42E830, The Lost Children 0x43B5A0, New Believers 0x426260 -- rescale(old, new),
    called the way the pause key, the unpause key and the Options speed buttons call it;
  * The Secret City 0x426630, The Tree of Life 0x41DBE0 -- set_speed(new) on the game clock object,
    with the save's clock and every saved timer registered to it as the game registers them.

Only the wall clock each routine reads is a stand-in (it returns the save's last tick, the "now" the
patcher replays the change at), popping exactly what the real routine pops.  Every start (Slow,
Normal, Fast, each paused) to every target, and back.  Then the owner's 10-23 sequence: a save whose
speed dword was set to Paused by an older patcher while its clock ran on Fast, set to Paused Normal
by Repair -- the fire now keeps its correct Normal length.

The live effect in a running game is NOT verified here.
"""
from __future__ import annotations

import functools
import gzip
import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import vv_save_backup as backup  # noqa: E402
import vv_save_clock as clock  # noqa: E402

try:
    import capstone
    import pefile  # noqa: F401
    from story_emulator import Process
    from unicorn.x86_const import UC_X86_REG_FPCW

    HAVE_EMULATOR = True
except ImportError:  # pragma: no cover - environment dependent
    HAVE_EMULATOR = False

FIXTURES = ROOT / "tests" / "fixtures" / "rename_tribe"
MASK = 0xFFFFFFFF
INPUTS = {1: "vv1-stock-copy", 2: "vv2-stock-copy", 3: "vv3-stock-copy", 4: "vv4-stock-copy", 5: "vv5-stock-copy"}
EXE = {1: "Virtual Villagers - A New Home.exe", 2: "Virtual Villagers - The Lost Children.exe",
       3: "Virtual Villagers - The Secret City.exe", 4: "Virtual Villagers - The Tree of Life.exe",
       5: "Virtual Villagers - New Believers.exe"}
# The stock routines and the wall clock each reads.
RESCALE = {1: (0x42E830, 0x402F70), 2: (0x43B5A0, 0x403200), 5: (0x426260, 0x4036E0)}
SET_SPEED = {3: (0x426630, 0x403330, 0x5825D4, 0x5825D0), 4: (0x41DBE0, 0x403750, 0x4D6F18, 0x4D6F10)}
# The manager singleton's getter the routines call for the wall clock's `this` (it would allocate
# the manager on first use): a stand-in returning a dummy manager.
MANAGER_GETTER = {3: 0x428B60, 4: 0x41FE70}
SPEEDS = (3, 6, 10)


def stock_exe(game: int) -> Path:
    return ROOT / "inputs" / INPUTS[game] / EXE[game]


def have(game: int) -> bool:
    return HAVE_EMULATOR and stock_exe(game).is_file()


@functools.lru_cache(maxsize=None)
def image(game: int) -> bytes:
    return stock_exe(game).read_bytes()


def real_pop(game: int, va: int) -> int:
    """What the stock routine at `va` pops on return (its first ret, following jumps at its start)."""
    pe = pefile.PE(data=image(game))
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    at = va
    for _ in range(4):
        data = pe.get_data(at - pe.OPTIONAL_HEADER.ImageBase, 0x400)
        for ins in md.disasm(data, at):
            if ins.mnemonic == "ret":
                return int(ins.op_str, 16) if ins.op_str else 0
            if ins.mnemonic == "jmp" and ins.op_str.startswith("0x"):
                at = int(ins.op_str, 16)
                break
        else:
            break
    raise AssertionError(f"no ret found for 0x{va:X}")


def fixture(name: str) -> bytes:
    return gzip.decompress((FIXTURES / f"{name}.ldw.gz").read_bytes())


class Save:
    """A save's state fields by state offset (buffer offset = state - 8)."""

    def __init__(self, game: int, data: bytes):
        self.game = game
        self.data = bytearray(data)
        self.header = backup._save_header(game, data)
        assert self.header is not None

    def get(self, state: int) -> int:
        return struct.unpack_from("<I", self.data, self.header + state - 8)[0]

    def put(self, state: int, value: int) -> None:
        struct.pack_into("<I", self.data, self.header + state - 8, value & MASK)

    def bytes(self) -> bytes:
        return bytes(self.data)


# ---- the stock routines, run in the emulator --------------------------------------------------

class Emulated:
    """The stock game's speed routine on a save's fields.  The FPU control word is the one a Windows
    process starts with and the games keep (0x27F: 53-bit precision, round to nearest, all masked);
    the emulator's own reset value would be single precision."""

    FPCW = 0x27F

    def __init__(self, game: int, dll: Path | None = None, fpcw: int | None = None):
        self.game = game
        self.p = Process(image(game), dll)
        self.fpcw = self.FPCW if fpcw is None else fpcw
        self.now = 0
        self.state = None
        self.cells = None
        if game in RESCALE:
            routine, wall = RESCALE[game]
        else:
            routine, wall, self.clock, self.count = SET_SPEED[game]
        self.routine = routine
        pop = real_pop(game, wall)
        self.p.stub(wall, lambda q: (self.now & MASK, pop))
        if game in MANAGER_GETTER:
            manager = self.p.alloc(0x20000)
            getter = MANAGER_GETTER[game]
            getter_pop = real_pop(game, getter)
            self.p.stub(getter, lambda q: (manager, getter_pop))

    # A New Home, The Lost Children, New Believers: the routine's object holds the state pointer.
    def load_state(self, save: Save) -> None:
        size = len(save.data) - save.header + 8
        if self.state is None or self.state_size < size:
            self.state = self.p.alloc(size + 0x10)
            self.state_size = size
            self.this = self.p.alloc(0x10)
            self.p.put32(self.this, self.state)
        self.p.write(self.state + 8, bytes(save.data[save.header:]))

    def _call(self, args: list[int], ecx: int) -> None:
        self.p.mu.reg_write(UC_X86_REG_FPCW, self.fpcw)
        self.p.call(self.routine, args, ecx=ecx)

    def rescale(self, old: int, new: int) -> None:
        self._call([old, new], self.this)

    def store_state(self, save: Save) -> None:
        save.data[save.header:] = self.p.read(self.state + 8, len(save.data) - save.header)

    # The Secret City, The Tree of Life: the clock object and its registered timers.
    def load_clock(self, save: Save) -> None:
        rules = clock.GAMES[self.game]
        for k in range(4):
            self.p.put32(self.clock + 0x20 + 4 * k, save.get(rules.clock + 4 * k))
        if self.cells is None:
            self.cells = [self.p.alloc(4) for _ in rules.timers]
        for i, (field, cell) in enumerate(zip(rules.timers, self.cells)):
            self.p.put32(cell, save.get(field))
            self.p.put32(self.clock + 4 * i, cell)          # as 0x426560 / 0x41DAE0 register them
        self.p.put32(self.count, len(rules.timers))

    def set_speed(self, new: int) -> None:
        self._call([new], self.clock)

    def store_clock(self, save: Save) -> None:
        rules = clock.GAMES[self.game]
        for k in range(4):
            save.put(rules.clock + 4 * k, self.p.u32(self.clock + 0x20 + 4 * k))
        for field, cell in zip(rules.timers, self.cells):
            save.put(field, self.p.u32(cell))

    def clock_fields(self) -> list[int]:
        return [self.p.u32(self.clock + 0x20 + 4 * k) for k in range(4)]

    def timers(self) -> list[int]:
        return [self.p.u32(cell) for cell in self.cells]


@functools.lru_cache(maxsize=None)
def emulator(game: int, fpcw: int | None) -> Emulated:
    """One stock process per game (and FPU setting), reloaded with each save's fields."""
    return Emulated(game, fpcw=fpcw)


def stock_edit(game: int, data: bytes, speed: int, paused: bool, fpcw: int | None = None) -> bytes:
    """The save after the player's own keys and buttons, run by the stock routine at the save's last
    tick: the unpause key back to the speed it was paused at, an Options speed button, the pause key."""
    save = Save(game, data)
    rules = clock.GAMES[game]
    emu = emulator(game, fpcw)
    emu.now = save.get(rules.now)
    value = save.get(rules.speed)
    if game in RESCALE:
        emu.load_state(save)
        was_paused = value >= 999
        base = value - 999 if was_paused else value
        if not (was_paused and paused and speed == base):
            if was_paused:
                emu.rescale(value, base)
            if speed != base:
                emu.rescale(base, speed)
            if paused:
                emu.rescale(speed, 999)
            emu.store_state(save)
            save.put(rules.speed, speed + 999 if paused else speed)
        return save.bytes()
    emu.load_clock(save)
    rate, before = emu.clock_fields()[:2]
    if rate == 0 and not (paused and speed == before):
        emu.set_speed(before)
        rate = before
    if rate != 0:
        if speed != rate:
            emu.set_speed(speed)
        if paused:
            emu.set_speed(999)
    emu.store_clock(save)
    save.put(rules.speed, speed + 999 if paused else speed)
    return save.bytes()


# ---- fixtures ------------------------------------------------------------------------------------

def running(game: int, name: str, speed: int) -> bytes:
    """A real save of the game, running at `speed` (its clock consistent with it), with every saved
    clock-tied timer set some hours ahead and one already due, so the routine has work to do."""
    save = Save(game, fixture(name))
    rules = clock.GAMES[game]
    now = save.get(rules.now)
    save.put(rules.speed, speed)
    if isinstance(rules, clock.ClockGame):
        _r, before, _wall, base = (save.get(rules.clock + 4 * k) for k in range(4))
        save.put(rules.clock, speed)
        save.put(rules.clock + 4, before if before in SPEEDS else 6)
        save.put(rules.clock + 8, now - 4321)
        save.put(rules.clock + 12, base)
    for i, field in enumerate(rules.timers):
        save.put(field, now + 7_777 + 13_579 * i if i != 1 else now - 50)
    if isinstance(rules, clock.ClockGame) and len(rules.timers) == 1:
        save.put(rules.timers[0], now + 36_000)
    return save.bytes()


def paused_at(game: int, name: str, speed: int) -> bytes:
    """The same save paused in the game at `speed` (the stock pause, run in the emulator), then
    ticked on for a while paused: its last tick later than the pause."""
    data = stock_edit(game, running(game, name, speed), speed, True)
    save = Save(game, data)
    rules = clock.GAMES[game]
    save.put(rules.now, save.get(rules.now) + 900)
    return save.bytes()


FIXTURE = {1: "vv1-huttest-1", 2: "vv2-huttest-1", 3: "vv3-huttest-1", 4: "vv4-huttest-1", 5: "vv5-huttest-1"}
FIXTURE_256 = {3: "vv3-256-1", 4: "vv4-256-1", 5: "vv5-256-1"}


class EveryChangeIsTheGamesOwn(unittest.TestCase):
    def check(self, game: int, name: str) -> None:
        starts = [(f"running {s}", running(game, name, s)) for s in SPEEDS]
        starts += [(f"paused {s}", paused_at(game, name, s)) for s in SPEEDS]
        for label, data in starts:
            for speed in SPEEDS:
                for paused in (False, True):
                    with self.subTest(game=game, fixture=name, start=label, speed=speed, paused=paused):
                        header = backup._save_header(game, data)
                        mine = clock.edit_speed(game, data, header, speed, paused)
                        theirs = stock_edit(game, data, speed, paused)
                        self.assertEqual(mine if mine is not None else data, theirs)
                        if isinstance(clock.GAMES[game], clock.ClockGame):
                            # ... and at extended precision too: the result never depends on it.
                            self.assertEqual(stock_edit(game, data, speed, paused, fpcw=0x37F), theirs)
                        self.assertEqual(mine is None, theirs == data)
                        # ... and back to where it started: again the game's own bytes.
                        after = mine if mine is not None else data
                        value = Save(game, data).get(clock.GAMES[game].speed)
                        back_paused = value >= 999
                        back = value - 999 if back_paused else value
                        again = clock.edit_speed(game, after, header, back, back_paused)
                        self.assertEqual(again if again is not None else after,
                                         stock_edit(game, after, back, back_paused))

    def test_a_new_home(self) -> None:
        if not have(1):
            self.skipTest("the stock A New Home is not in inputs\\")
        self.check(1, FIXTURE[1])

    def test_the_lost_children(self) -> None:
        if not have(2):
            self.skipTest("the stock Lost Children is not in inputs\\")
        self.check(2, FIXTURE[2])

    def test_the_secret_city(self) -> None:
        if not have(3):
            self.skipTest("the stock Secret City is not in inputs\\")
        self.check(3, FIXTURE[3])
        self.check(3, FIXTURE_256[3])

    def test_the_tree_of_life(self) -> None:
        if not have(4):
            self.skipTest("the stock Tree of Life is not in inputs\\")
        self.check(4, FIXTURE[4])
        self.check(4, FIXTURE_256[4])

    def test_new_believers(self) -> None:
        if not have(5):
            self.skipTest("the stock New Believers is not in inputs\\")
        self.check(5, FIXTURE[5])
        self.check(5, FIXTURE_256[5])


class OnlyTheGamesFieldsChange(unittest.TestCase):
    def test_nothing_but_the_speed_the_clock_and_its_timers(self) -> None:
        for game, name in FIXTURE.items():
            rules = clock.GAMES[game]
            fields = {rules.speed, *rules.timers}
            if isinstance(rules, clock.ClockGame):
                fields |= {rules.clock + 4 * k for k in range(4)}
            data = running(game, name, 3)
            save = Save(game, data)
            allowed = set()
            for state in fields:
                at = save.header + state - 8
                allowed |= set(range(at, at + 4))
            for speed in SPEEDS:
                for paused in (False, True):
                    out = clock.edit_speed(game, data, save.header, speed, paused) or data
                    changed = {i for i in range(len(data)) if data[i] != out[i]}
                    self.assertLessEqual(changed, allowed, (game, speed, paused))


class TheOwnersFire(unittest.TestCase):
    """10-23: a backup's copy paused by an older patcher (only the speed dword: 1002 = Paused Fast)
    while its clock ran on Fast; restored; then Repair set it to Paused Normal."""

    def setUp(self) -> None:
        if not have(3):
            self.skipTest("the stock Secret City is not in inputs\\")

    def save(self) -> bytes:
        save = Save(3, running(3, FIXTURE[3], 3))
        rules = clock.GAMES[3]
        now = save.get(rules.now)
        self.fire = 0x12125
        save.put(self.fire, now + 30_856)          # 8.57 hours left on Fast, as slot 2 had
        save.put(rules.speed, 1002)               # the older patcher's pause: the dword only
        return save.bytes()

    def test_repair_keeps_the_fire_at_its_normal_length(self) -> None:
        data = self.save()
        before = Save(3, data)
        now = before.get(clock.GAMES[3].now)
        fixed = clock.edit_speed(3, data, 12, 6, True)
        after = Save(3, fixed)
        self.assertEqual(after.get(clock.GAMES[3].speed), 1005)
        self.assertEqual([after.get(clock.GAMES[3].clock + 4 * k) for k in range(2)], [0, 6])
        # The fire's 8.57 hours on Fast are 17.14 hours on Normal: twice the wall time.
        self.assertEqual(after.get(self.fire) - now, 2 * 30_856)
        self.assertEqual(fixed, stock_edit(3, data, 6, True))
        # Played: the unpause key (set_speed(6) from the paused clock) moves the fire by the time
        # paused only -- it keeps its Normal length.
        emu = Emulated(3)
        emu.load_clock(after)
        emu.now = now + 600
        emu.set_speed(6)
        self.assertEqual(emu.timers()[2] - emu.now, 2 * 30_856)

    def test_the_old_dword_only_edit_left_the_fast_length(self) -> None:
        data = bytearray(self.save())
        struct.pack_into("<I", data, 12 + 0x12F20 - 8, 1005)     # what Repair used to write
        old = Save(3, bytes(data))
        now = old.get(clock.GAMES[3].now)
        emu = Emulated(3)
        emu.load_clock(old)
        emu.now = now
        emu.set_speed(6)               # unpaused: the clock was never paused, so Fast -> Normal ...
        # ... doubles it here, but the fire lit meanwhile, with the clock still on Fast, gets
        # Fast's 10 hours: the owner's "around 9 hours".
        emu2 = Emulated(3)
        emu2.load_clock(old)
        emu2.now = now
        emu2.p.mu.reg_write(UC_X86_REG_FPCW, Emulated.FPCW)
        emu2.p.call(0x426790, [72_000], ecx=emu2.cells[2])        # the wood: 72,000 game seconds
        self.assertEqual(emu2.timers()[2] - now, 36_000)

    def test_backups_are_paused_as_the_game_pauses(self) -> None:
        data = Save(3, running(3, FIXTURE[3], 3)).bytes()
        paused = backup.pause_save_bytes(3, data)
        self.assertEqual(paused, stock_edit(3, data, 3, True))
        self.assertEqual(Save(3, paused).get(clock.GAMES[3].clock), 0)


class Refusals(unittest.TestCase):
    def test_a_save_the_game_did_not_lay_out_is_refused(self) -> None:
        data = bytearray(running(3, FIXTURE[3], 6))
        struct.pack_into("<I", data, 12 + 0x11ED4 - 8, 0x200)     # the stock 150-villager damage
        with self.assertRaises(clock.SpeedEditRefused):
            clock.edit_speed(3, bytes(data), 12, 3, False)
        with self.assertRaises(backup.SpeedRefused):
            backup.pause_save_bytes(3, bytes(data))

    def test_an_unknown_clock_state_is_refused(self) -> None:
        data = bytearray(running(4, FIXTURE[4], 6))
        struct.pack_into("<I", data, 24 + 0x8E8 - 8, 7)
        with self.assertRaises(clock.SpeedEditRefused):
            clock.edit_speed(4, bytes(data), 24, 3, False)

    def test_a_value_whose_rounding_could_differ_is_refused(self) -> None:
        """A timer so far ahead that timer x 10/6 (single precision) is not held exactly at 53 bits
        and lies within the FPU's rounding of an integer: refused, never guessed."""
        base = Save(3, running(3, FIXTURE[3], 6))
        for timer in range(0xF0000000, 0xF0000000 + 200_000):
            base.put(0x12125, timer)
            try:
                clock.edit_speed(3, base.bytes(), 12, 10, False)
            except clock.SpeedEditRefused:
                break
        else:
            self.fail("no refused value found")
        with self.assertRaises(backup.SpeedRefused):
            backup._speed_edit(3, base.bytes(), 10, False)


if __name__ == "__main__":
    unittest.main()
