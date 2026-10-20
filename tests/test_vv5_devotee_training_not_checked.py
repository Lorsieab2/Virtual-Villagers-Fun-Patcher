"""Easier Devotee Training (New Believers): a villager NOT checked on Devotion
honours only 14% of the times the row would let them.

The owner (2026-10-20): "Applies to patch behaviors only: ALL villagers NOT
checked on X skill perform actions that train that skill 14% of the time."
Honoring trains Devotion.  The row sends an ordinary villager with Devotion
skill above 0 from the live scheduler's Retired-Chief test (0x46F1DD) to an
added Honoring branch (0x494900: the stock 50% timing chance, then Honoring,
behaviour 0xA0).  A villager whose job checkmark ([record + 0x1C74]) is
Devotion (5) goes there as before; any other villager first passes through
the gate at 0x494D00, which lets them on only when the game's rand(100) is
below 14 and otherwise takes the stock branch (0x46F23A).

RUN from the rendered executable in an emulator from the scheduler's
`mov ecx, [esi+0x1B88]` (0x46F1D7), with only the game's RNG wrapper 0x403660
scripted, to the first of: the behaviour setter 0x465580 (its behaviour
argument), the stock branch 0x46F23A, the Retired-Chief branch 0x46F1E6.
"""
from __future__ import annotations

import random
import struct
import sys
import unittest
from pathlib import Path

import pefile
from unicorn import UC_ARCH_X86, UC_HOOK_CODE, UC_MODE_32, Uc
from unicorn.x86_const import UC_X86_REG_EAX, UC_X86_REG_EIP, UC_X86_REG_ESI, UC_X86_REG_ESP

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

EXE = ROOT / "research" / "stock-executables" / "Virtual Villagers - New Believers.exe"
STOCK_ABSENT = "the stock executables (research/stock-executables) are gitignored and absent"
FEATURE = "vv5_easier_devotee_training"
START, STOCK_BRANCH, CHIEF_BRANCH, SETTER, RNG = 0x46F1D7, 0x46F23A, 0x46F1E6, 0x465580, 0x403660
HONORING = 0xA0
OBJ, RECORD, STACK_TOP = 0x0E000000, 0x0E100000, 0x0F000000
DEVOTION, PREFERENCE, RETIRED = 0x1C70, 0x1C74, 0x1CFC


class _Machine:
    def __init__(self, image: bytes):
        pe = pefile.PE(data=image)
        self.mu = mu = Uc(UC_ARCH_X86, UC_MODE_32)
        mu.mem_map(0x400000, (pe.OPTIONAL_HEADER.SizeOfImage + 0xFFF) & ~0xFFF)
        mu.mem_write(0x400000, image[:pe.OPTIONAL_HEADER.SizeOfHeaders])
        for section in pe.sections:
            mu.mem_write(0x400000 + section.VirtualAddress, section.get_data())
        mu.mem_map(OBJ, 0x200000)
        mu.mem_map(STACK_TOP - 0x10000, 0x10000)
        mu.mem_write(OBJ + 0x1B88, struct.pack("<I", RECORD))
        self.rolls: list[int] = []
        self.seen: list[int] = []
        self.end = None
        mu.hook_add(UC_HOOK_CODE, self._hook)

    def _hook(self, mu, address, size, _):
        if address == RNG:
            esp = mu.reg_read(UC_X86_REG_ESP)
            ret, n = struct.unpack("<Ii", mu.mem_read(esp, 8))
            value = self.rolls.pop(0) % n
            self.seen.append(n)
            mu.reg_write(UC_X86_REG_EAX, value)
            mu.reg_write(UC_X86_REG_ESP, esp + 4)
            mu.reg_write(UC_X86_REG_EIP, ret)
        elif address in (STOCK_BRANCH, CHIEF_BRANCH):
            self.end = address
            mu.emu_stop()
        elif address == SETTER:
            esp = mu.reg_read(UC_X86_REG_ESP)
            self.end = ("behaviour", struct.unpack("<I", mu.mem_read(esp + 4, 4))[0])
            mu.emu_stop()

    def run(self, preference: int, rolls, devotion: float = 2.0, retired: int = 0):
        self.mu.mem_write(RECORD + DEVOTION, struct.pack("<f", devotion))
        self.mu.mem_write(RECORD + PREFERENCE, struct.pack("<i", preference))
        self.mu.mem_write(RECORD + RETIRED, struct.pack("<i", retired))
        self.rolls, self.seen, self.end = list(rolls), [], None
        self.mu.reg_write(UC_X86_REG_ESI, OBJ)
        self.mu.reg_write(UC_X86_REG_ESP, STACK_TOP - 0x400)
        self.mu.emu_start(START, 0, count=5000)
        return self.end


@unittest.skipUnless(EXE.is_file(), STOCK_ABSENT)
class NotCheckedOnDevotion(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import vv_fun_patcher as vfp
        build = next(b for b in vfp.load_builds() if b.id == "vv5")
        rendered, _ = vfp.render_patched_bytes(EXE, build, "stock", [FEATURE])
        cls.m = _Machine(bytes(rendered))

    def test_a_devotee_is_unchanged(self):
        self.assertEqual(self.m.run(5, [0]), ("behaviour", HONORING))
        self.assertEqual(self.m.seen, [100], "the stock 50% timing roll only")
        self.assertEqual(self.m.run(5, [50]), STOCK_BRANCH)

    def test_anyone_else_needs_the_14_percent_roll_first(self):
        for preference in (-1, 0, 1, 2, 3, 4):
            with self.subTest(preference=preference, roll=13):
                self.assertEqual(self.m.run(preference, [13, 0]), ("behaviour", HONORING))
                self.assertEqual(self.m.seen, [100, 100])
            with self.subTest(preference=preference, roll=14):
                # A failed roll is the stock branch, exactly as with no Devotion skill.
                self.assertEqual(self.m.run(preference, [14, 0]), STOCK_BRANCH)
                self.assertEqual(self.m.seen, [100])
                self.assertEqual(self.m.run(preference, [0], devotion=0.0), STOCK_BRANCH)

    def test_retired_chiefs_keep_the_stock_branch(self):
        self.assertEqual(self.m.run(1, [0, 0], retired=13), CHIEF_BRANCH)
        self.assertEqual(self.m.seen, [])

    def test_measured_shares(self):
        rng = random.Random(20261020)
        n = 4000
        for preference, low, high in ((5, 0.46, 0.54), (1, 0.055, 0.085), (-1, 0.055, 0.085)):
            with self.subTest(preference=preference):
                honoured = 0
                for _ in range(n):
                    honoured += self.m.run(preference, [rng.randrange(0x8000), rng.randrange(0x8000)]) == (
                        "behaviour", HONORING)
                share = honoured / n
                print(f"vv5 Easier Devotee Training, checkmark {preference}: Honoring {share:.3f}")
                self.assertTrue(low <= share <= high, share)


if __name__ == "__main__":
    unittest.main()
