"""VV3 Nature honey refill: the hive actually gains honey.

The shipped stub computed the amount to add, already shifted right by 11,
then jumped back into stock code that shifts it right by 11 again -- so both
paths added 0 while still resetting the refill timer, and the hive never
refilled at any Nature level. The byte pin in test_patcher.py pinned those
defective bytes, so this test executes the routine instead.

Emulates 0x4319E2..0x431A30 (the eligibility check, the amount, the add and
the timer reset) in the stock exe and in a real render, with the clock getter
0x426590 returning a chosen time and the Nature level (technology 5) written
into the tech table the stock getter 0x426FC0 reads.

At Nature 1 or higher a 45-minute refill is worth 2700 * 84 / 99900 = 2.27
units.  The game adds whole units only, so the patch keeps the part it could
not pay for (it sets the timer to now less that time) and the next refill pays
it: honey gathered while the game is open matches the same time away.
"""
from __future__ import annotations

import struct
import sys
import unittest
from pathlib import Path

import pefile
from unicorn import UC_ARCH_X86, UC_HOOK_CODE, UC_MODE_32, Uc
from unicorn.x86_const import (
    UC_X86_REG_EAX,
    UC_X86_REG_EIP,
    UC_X86_REG_ESI,
    UC_X86_REG_ESP,
)

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import vv_fun_patcher as vfp  # noqa: E402

STOCK_VV3 = ROOT / "research" / "stock-executables" / "Virtual Villagers - The Secret City.exe"
FEATURE = "vv3_nature_honey_refill"

CLOCK = 0x426590
TECH_TABLE = 0x582618
NATURE = 5
START, END = 0x4319E2, 0x431A30
HIVE = 0x10000000
T0 = 1000


class Hive:
    """The honey routine of one executable, run again and again on one hive."""

    def __init__(self, image: bytes, nature: int, honey: int = 100, timer: int = T0):
        pe = pefile.PE(data=image, fast_load=True)
        base = pe.OPTIONAL_HEADER.ImageBase
        size = (pe.OPTIONAL_HEADER.SizeOfImage + 0xFFF) & ~0xFFF
        uc = Uc(UC_ARCH_X86, UC_MODE_32)
        uc.mem_map(base, size)
        uc.mem_write(base, pe.header)
        for section in pe.sections:
            data = section.get_data()
            room = size - section.VirtualAddress
            uc.mem_write(base + section.VirtualAddress, data[: max(0, min(len(data), room))])
        uc.mem_write(TECH_TABLE + NATURE * 4, struct.pack("<I", nature))
        uc.mem_map(HIVE, 0x10000)
        uc.mem_write(HIVE + 0xC, struct.pack("<I", timer))
        uc.mem_write(HIVE + 0x10, struct.pack("<I", honey))
        uc.mem_map(0x20000000, 0x10000)
        self.uc = uc
        self.now = timer
        uc.hook_add(UC_HOOK_CODE, self._clock, begin=CLOCK, end=CLOCK)

    def _clock(self, uc, _address, _size, _data):
        sp = uc.reg_read(UC_X86_REG_ESP)
        (ret,) = struct.unpack("<I", uc.mem_read(sp, 4))
        uc.reg_write(UC_X86_REG_EAX, self.now)
        uc.reg_write(UC_X86_REG_ESP, sp + 4)
        uc.reg_write(UC_X86_REG_EIP, ret)

    def check(self, now: int) -> None:
        """The game's update reaching the refill check at clock `now`."""
        self.now = now
        self.uc.reg_write(UC_X86_REG_ESP, 0x20008000)
        self.uc.reg_write(UC_X86_REG_ESI, HIVE)
        self.uc.reg_write(UC_X86_REG_EAX, now)
        self.uc.emu_start(START, END, count=4000)
        if self.uc.reg_read(UC_X86_REG_EIP) != END:
            raise AssertionError("emulation did not reach the routine's end")

    @property
    def honey(self) -> int:
        return struct.unpack("<I", self.uc.mem_read(HIVE + 0x10, 4))[0]

    @property
    def timer(self) -> int:
        return struct.unpack("<I", self.uc.mem_read(HIVE + 0xC, 4))[0]


def _refill(image: bytes, nature: int, elapsed: int, honey: int = 100) -> tuple[int, bool]:
    """Run one refill check; return (honey afterwards, whether the timer reset)."""
    pe = pefile.PE(data=image, fast_load=True)
    base = pe.OPTIONAL_HEADER.ImageBase
    size = (pe.OPTIONAL_HEADER.SizeOfImage + 0xFFF) & ~0xFFF
    uc = Uc(UC_ARCH_X86, UC_MODE_32)
    uc.mem_map(base, size)
    uc.mem_write(base, pe.header)
    for section in pe.sections:
        data = section.get_data()
        room = size - section.VirtualAddress
        uc.mem_write(base + section.VirtualAddress, data[: max(0, min(len(data), room))])
    uc.mem_write(TECH_TABLE + NATURE * 4, struct.pack("<I", nature))
    uc.mem_map(HIVE, 0x10000)
    uc.mem_write(HIVE + 0xC, struct.pack("<I", T0))
    uc.mem_write(HIVE + 0x10, struct.pack("<I", honey))
    stack = 0x20000000
    uc.mem_map(stack, 0x10000)
    uc.reg_write(UC_X86_REG_ESP, stack + 0x8000)
    uc.reg_write(UC_X86_REG_ESI, HIVE)
    now = T0 + elapsed
    uc.reg_write(UC_X86_REG_EAX, now)

    def hook(uc, address, _size, _data):
        if address == CLOCK:
            sp = uc.reg_read(UC_X86_REG_ESP)
            (ret,) = struct.unpack("<I", uc.mem_read(sp, 4))
            uc.reg_write(UC_X86_REG_EAX, now)
            uc.reg_write(UC_X86_REG_ESP, sp + 4)
            uc.reg_write(UC_X86_REG_EIP, ret)

    uc.hook_add(UC_HOOK_CODE, hook)
    uc.emu_start(START, END, count=4000)
    self_eip = uc.reg_read(UC_X86_REG_EIP)
    if self_eip != END:
        raise AssertionError(f"emulation stopped at {self_eip:#x}, not {END:#x}")
    (after,) = struct.unpack("<I", uc.mem_read(HIVE + 0x10, 4))
    (timer,) = struct.unpack("<I", uc.mem_read(HIVE + 0xC, 4))
    return after, timer == now


@unittest.skipUnless(STOCK_VV3.is_file(), "stock VV3 executable not present")
class HoneyRefillAmountTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.stock = STOCK_VV3.read_bytes()
        build = next(b for b in vfp.load_builds() if b.id == "vv3")
        cls.rendered = {}
        for mode in ("stock", "collection_progression", "immediate_fixed"):
            image, _ = vfp.render_patched_bytes(STOCK_VV3, build, mode, [FEATURE])
            cls.rendered[mode] = bytes(image)

    def test_nature_zero_matches_the_stock_game_exactly(self):
        for mode, image in self.rendered.items():
            for elapsed in (3599, 3600, 7200, 36000, 86400):
                with self.subTest(mode=mode, elapsed=elapsed):
                    self.assertEqual(
                        _refill(image, 0, elapsed), _refill(self.stock, 0, elapsed)
                    )

    def test_the_stock_game_really_refills(self):
        # Guards the harness: a stub-free run must show honey growing.
        self.assertEqual(_refill(self.stock, 0, 3600), (102, True))
        self.assertEqual(_refill(self.stock, 0, 86400), (148, True))

    def test_nature_one_or_higher_refills_every_45_minutes(self):
        for mode, image in self.rendered.items():
            for nature in (1, 3):
                with self.subTest(mode=mode, nature=nature):
                    hive = Hive(image, nature)
                    hive.check(T0 + 2699)
                    self.assertEqual((hive.honey, hive.timer), (100, T0))
                    # 2700 s * 84 / 99900 = 2.27: two units now, and the timer
                    # keeps the 0.27 unit's time, floor((2700*84 % 99900) / 84).
                    hive.check(T0 + 2700)
                    self.assertEqual(hive.honey, 102)
                    self.assertEqual(hive.timer, T0 + 2700 - (2700 * 84 % 99900) // 84)
                    away = Hive(image, nature)
                    away.check(T0 + 86400)
                    self.assertEqual(away.honey, 100 + 86400 * 84 // 99900)
                    self.assertEqual(away.timer, T0 + 86400 - (86400 * 84 % 99900) // 84)

    def test_playing_gathers_what_the_same_time_away_does(self):
        # The game checks the hive every frame while it is open, so each
        # refill pays the moment 45 minutes have passed.  Over many refills
        # the total must be the exact rate, within one unit, and equal to one
        # refill for the whole time away.
        for mode, image in self.rendered.items():
            for hours in (12, 100):
                with self.subTest(mode=mode, hours=hours):
                    span = hours * 3600
                    playing = Hive(image, 1, honey=0)
                    second = T0
                    while second < T0 + span:
                        second = max(second + 1, playing.timer + 2700)
                        if second > T0 + span:
                            break
                        playing.check(second)
                    playing.check(T0 + span)
                    away = Hive(image, 1, honey=0)
                    away.check(T0 + span)
                    exact = span * 84 / 99900
                    self.assertLess(abs(playing.honey - exact), 1)
                    self.assertLess(abs(away.honey - exact), 1)
                    self.assertLessEqual(abs(playing.honey - away.honey), 1)

    def test_the_cap_and_nature_zero_are_unchanged(self):
        for mode, image in self.rendered.items():
            with self.subTest(mode=mode):
                full = Hive(image, 1, honey=2999)
                full.check(T0 + 86400)
                self.assertEqual(full.honey, 3000)
                stock = Hive(self.stock, 0)
                patched = Hive(image, 0)
                for now in (T0 + 3599, T0 + 3600, T0 + 3600 + 3599, T0 + 7300):
                    stock.check(now)
                    patched.check(now)
                    self.assertEqual((patched.honey, patched.timer), (stock.honey, stock.timer))

    def test_honey_is_never_reset_without_being_added(self):
        for mode, image in self.rendered.items():
            for nature in (0, 1):
                for elapsed in (2700, 3600, 7200):
                    with self.subTest(mode=mode, nature=nature, elapsed=elapsed):
                        honey, reset = _refill(image, nature, elapsed)
                        if reset:
                            self.assertGreater(honey, 100)


if __name__ == "__main__":
    unittest.main()
