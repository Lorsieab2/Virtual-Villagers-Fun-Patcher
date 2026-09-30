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
                    self.assertEqual(_refill(image, nature, 2699), (100, False))
                    # 2700 s * 84 / 99900 = 2: a 45-minute refill brings what
                    # a stock hour does.
                    self.assertEqual(_refill(image, nature, 2700), (102, True))
                    self.assertEqual(_refill(image, nature, 86400), (100 + 86400 * 84 // 99900, True))

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
