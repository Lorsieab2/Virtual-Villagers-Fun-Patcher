"""A New Home's Golden Child and the age-unit step, emulated in the stock executable (the Game Mechanics window's
VV1 line "he never eats, never starves, never falls sick, never dies of old age and never regains health").

The world tick 0x42E900 loads the Golden Child's family number 0xC7 into ebp (0x42E957).  In its per-villager
ageing loop, after the age is advanced (0x42EB0C), a record whose family (+0x36C) is 0xC7 has its age (+0x348) and
processed age (+0x34C) set to 100 (0x42EB80..0x42EB8E).  The age-unit body that eats, starves, sickens, heals and
rolls old age runs a villager only while the processed age is below the age (0x42EC74 / 0x42EC80, else 0x42F145).
Both pieces are run here on the stock bytes, for the Golden Child and for an ordinary villager."""
from __future__ import annotations

import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXE = ROOT / "research" / "stock-executables" / "Virtual Villagers - A New Home.exe"
if not EXE.is_file():
    EXE = ROOT / "inputs" / "vv1-stock-copy" / "Virtual Villagers - A New Home.exe"

try:
    import pefile
    from unicorn import UC_ARCH_X86, UC_HOOK_CODE, UC_MODE_32, Uc
    from unicorn.x86_const import (UC_X86_REG_EAX, UC_X86_REG_EBP, UC_X86_REG_EDI, UC_X86_REG_EIP, UC_X86_REG_ESI,
                                   UC_X86_REG_ESP)
except ImportError:  # pragma: no cover -- the dev requirements carry both
    pefile = None

HEAP, ARRAY, STACK = 0x10000000, 0x10100000, 0x20000000
GOLDEN, AGE, PROCESSED, AGE_TIMER, FAMILY = 0xC7, 0x348, 0x34C, 0x33C, 0x36C


@unittest.skipUnless(pefile is not None and EXE.is_file(), "the stock A New Home executable is not here")
class GoldenChild(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        pe = pefile.PE(str(EXE), fast_load=True)
        cls.base = pe.OPTIONAL_HEADER.ImageBase
        cls.image = pe.get_memory_mapped_image()

    def machine(self):
        mu = Uc(UC_ARCH_X86, UC_MODE_32)
        mu.mem_map(self.base, (len(self.image) + 0xFFF) & ~0xFFF)
        mu.mem_write(self.base, self.image)
        for at in (HEAP, ARRAY, STACK - 0x10000):
            mu.mem_map(at, 0x20000)
        mu.reg_write(UC_X86_REG_ESP, STACK - 0x100)
        return mu

    def emulate(self, mu, start: int, stops: tuple[int, ...]) -> int:
        reached = []

        def hook(uc, addr, size, user_data):
            if addr in stops:
                reached.append(addr)
                uc.emu_stop()
        mu.hook_add(UC_HOOK_CODE, hook)
        mu.emu_start(start, 0xFFFFFFFF, count=200)
        return reached[0] if reached else mu.reg_read(UC_X86_REG_EIP)

    def test_the_tick_loads_his_family(self) -> None:
        at = 0x42E957 - self.base
        self.assertEqual(self.image[at:at + 5], b"\xbd" + struct.pack("<I", GOLDEN))   # mov ebp, 0xC7

    def lock(self, family: int, age: int, processed: int) -> tuple[int, int, int]:
        mu = self.machine()
        record = ARRAY
        mu.mem_write(record + FAMILY, struct.pack("<i", family))
        mu.mem_write(record + AGE, struct.pack("<i", age))
        mu.mem_write(record + PROCESSED, struct.pack("<i", processed))
        mu.mem_write(record + AGE_TIMER, struct.pack("<i", 77))
        mu.mem_write(HEAP, struct.pack("<II", HEAP + 0x1000, ARRAY))   # [esi] the world, [esi+4] the records
        mu.reg_write(UC_X86_REG_ESI, HEAP)
        mu.reg_write(UC_X86_REG_EDI, 0)                                 # the record's offset in the array
        mu.reg_write(UC_X86_REG_EBP, GOLDEN)
        self.assertEqual(self.emulate(mu, 0x42EB70, (0x42EBA3,)), 0x42EBA3)
        return tuple(struct.unpack("<i", mu.mem_read(record + off, 4))[0] for off in (AGE, PROCESSED, AGE_TIMER))

    def test_his_age_is_set_back_to_five(self) -> None:
        self.assertEqual(self.lock(GOLDEN, 137, 120), (100, 100, 0))
        self.assertEqual(self.lock(5, 137, 120), (137, 120, 77))       # anyone else keeps their age

    def body(self, age: int, processed: int) -> int:
        mu = self.machine()
        mu.mem_write(ARRAY + AGE, struct.pack("<i", age))
        mu.mem_write(ARRAY + PROCESSED, struct.pack("<i", processed))
        mu.reg_write(UC_X86_REG_EAX, ARRAY)
        return self.emulate(mu, 0x42EC74, (0x42F145, 0x42EC86))

    def test_the_age_unit_body_skips_him(self) -> None:
        self.assertEqual(self.body(100, 100), 0x42F145)                # locked: no eating, starving, sickness, healing
        self.assertEqual(self.body(137, 120), 0x42EC86)                # an ordinary villager with an age unit due


if __name__ == "__main__":
    unittest.main()
