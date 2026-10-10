"""The Tree of Life's Debris Cleared and New Believers' Heathens Converted,
run on the patched bytes in an emulator (audit, 2026-10-09).

* Debris: the clearing action 0x439650 (arg 0: a worker cleared one unit of
  the stream's obstruction level, debris-manager 0x4D8CF0 +0x14) is the one
  place the level goes down; the patch counts each unit at 0x43965A into the
  pending Debris Cleared field 0x4D6E38 (live block +0x58).
* Heathens: the game's SetFaith 0x467F90, when a Heathen's faith rises above 0
  (The Defector's +20, worship), calls the conversion 0x4668B0; the patch
  counts each conversion at its entry into 0x51D3A4 (live block +0x4C), the
  Heathen Mommy (role +0x1CFC == 17) as two."""
from __future__ import annotations

import struct
import unittest

from unicorn import UC_HOOK_CODE
from unicorn.x86_const import UC_X86_REG_EAX, UC_X86_REG_ECX, UC_X86_REG_EIP, UC_X86_REG_ESP

from test_statistics_counts_what_it_says import HEAP, STACK, machine, rd

DEBRIS, DEBRIS_PENDING = 0x4D8CF0, 0x4D6E38
CONVERTED = 0x51D3A4


def call_frame(mu, *args):
    esp = STACK - 0x100
    mu.mem_write(esp, struct.pack("<I", 0xDEAD0000) + b"".join(struct.pack("<i", a) for a in args))
    mu.reg_write(UC_X86_REG_ESP, esp)


class DebrisClearedTests(unittest.TestCase):
    def clear_one(self, patched, level=5):
        mu = machine(4, patched)
        mu.mem_write(DEBRIS + 0x14, struct.pack("<i", level))
        mu.reg_write(UC_X86_REG_ECX, DEBRIS)
        call_frame(mu, 0)                                   # arg 0: a unit cleared
        mu.emu_start(0x439650, 0x439667, count=100)         # up to the trophy credit call
        return rd(mu, DEBRIS + 0x14), rd(mu, DEBRIS_PENDING)

    def test_each_cleared_unit_counts_once(self):
        self.assertEqual(self.clear_one(True), (4, 1))

    def test_stock_counts_nothing(self):
        self.assertEqual(self.clear_one(False), (4, 0))


class HeathensConvertedTests(unittest.TestCase):
    def convert(self, role):
        mu = machine(5, True)
        record = HEAP + 0x1000
        mu.mem_write(record + 0x1CFC, struct.pack("<i", role))
        mu.reg_write(UC_X86_REG_ECX, record)
        call_frame(mu, 0)
        mu.emu_start(0x4668B0, 0x4668B6, count=50)          # the counting wrapper, back in the routine
        return rd(mu, CONVERTED)

    def test_a_heathen_counts_one_and_the_heathen_mommy_two(self):
        self.assertEqual(self.convert(0), 1)
        self.assertEqual(self.convert(0xD), 1)              # the Heathen Chief
        self.assertEqual(self.convert(17), 2)               # the Heathen Mommy

    def test_faith_rising_above_zero_reaches_the_conversion(self):
        self.assertEqual(self.set_faith(-10), [HEAP + 0x1000])

    def test_a_believer_whose_faith_rises_is_not_converted(self):
        self.assertEqual(self.set_faith(10), [])

    def set_faith(self, before):
        mu = machine(5, True)
        record, game = HEAP + 0x1000, HEAP + 0x100000
        mu.mem_write(game + 0x17E39, b"\x01")
        mu.mem_write(record + 0x1CF0, struct.pack("<i", before))
        reached = []

        def hook(uc, address, size, _):
            if address == 0x425950:                         # the game object: conversions enabled
                esp = uc.reg_read(UC_X86_REG_ESP)
                uc.reg_write(UC_X86_REG_EAX, game)
                uc.reg_write(UC_X86_REG_ESP, esp + 4)
                uc.reg_write(UC_X86_REG_EIP, struct.unpack("<I", uc.mem_read(esp, 4))[0])
            elif address == 0x4668B0:
                reached.append(uc.reg_read(UC_X86_REG_ECX))
                uc.emu_stop()

        mu.hook_add(UC_HOOK_CODE, hook)
        mu.reg_write(UC_X86_REG_ECX, record)
        call_frame(mu, 20, 1)                               # SetFaith(20, may convert): The Defector
        mu.emu_start(0x467F90, 0xDEAD0000, count=200)
        return reached


if __name__ == "__main__":
    unittest.main()
