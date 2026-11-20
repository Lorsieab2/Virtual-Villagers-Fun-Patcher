"""The Lost Children's Fix Vanilla Bugs (the owner, 2026-11-18): the fish left in the waters (+0x2EAD0) and the field's
protection from birds (+0x2EAD4) stop at 0 instead of going below it (data/builds.json vv2_fix_vanilla_bugs, the
patches at 0x632CB and 0x6325E).

The fishing payoff (0x4632CB..0x463311) and the harvest payoff's subtracts (0x46325E..0x46327B) run in the emulator on
the stock image, with and without the patch: the same catch (11 / 8 / 5 by speed, 8 while catching up), the same food
call's argument and object, the crops' own subtract kept, and each count stops at 0 only with the patch.
"""
from __future__ import annotations

import json
import struct
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXE = ROOT / "inputs" / "vv2-stock-copy" / "Virtual Villagers - The Lost Children.exe"
try:
    import pefile
    from unicorn import UC_ARCH_X86, UC_MODE_32, Uc
    from unicorn.x86_const import UC_X86_REG_EAX, UC_X86_REG_ECX, UC_X86_REG_EDI, UC_X86_REG_ESI, UC_X86_REG_ESP
    HAVE = True
except ImportError:                     # pragma: no cover
    HAVE = False

OBJ, WORLD, STACK = 0x10000000, 0x20000000, 0x30000000
FISH, FIELD, CROPS, CATCHING_UP, SPEED = 0x2EAD0, 0x2EAD4, 0x2EAD8, 0x3046C, 0x2EB08


def fvb_patches() -> list[dict]:
    builds = json.loads((ROOT / "data" / "builds.json").read_text(encoding="utf-8"))
    p = next(x for x in builds["fun_patches"] if x["id"] == "vv2_fix_vanilla_bugs")
    return [x for x in p["patches"] if x["offset"] in ("0x632CB", "0x6325E")]


@unittest.skipUnless(HAVE and EXE.exists(), "needs unicorn, pefile and the stock The Lost Children in inputs/")
class StopAtZero(unittest.TestCase):
    def machine(self, patched: bool) -> Uc:
        pe = pefile.PE(str(EXE))
        mu = Uc(UC_ARCH_X86, UC_MODE_32)
        image = bytearray(pe.get_memory_mapped_image())
        if patched:
            for x in fvb_patches():
                at, before, after = int(x["offset"], 16), bytes.fromhex(x["before"]), bytes.fromhex(x["after"])
                self.assertEqual(bytes(image[at:at + len(before)]), before, x["offset"])
                self.assertEqual(len(before), len(after))
                image[at:at + len(after)] = after
        size = (len(image) + 0xFFF) & ~0xFFF
        mu.mem_map(0x400000, size)
        mu.mem_write(0x400000, bytes(image))
        mu.mem_map(OBJ, 0xE58000)
        mu.mem_map(WORLD, 0x31000)
        mu.mem_map(STACK - 0x10000, 0x20000)
        mu.mem_write(OBJ + 0xE574D4, struct.pack("<I", WORLD))
        mu.reg_write(UC_X86_REG_ESI, OBJ)
        mu.reg_write(UC_X86_REG_ESP, STACK)
        return mu

    def i32(self, mu: Uc, off: int) -> int:
        return struct.unpack("<i", mu.mem_read(WORLD + off, 4))[0]

    def fish(self, patched: bool, fish: int, speed: int, catching_up: int = 0):
        mu = self.machine(patched)
        mu.mem_write(WORLD + FISH, struct.pack("<i", fish))
        mu.mem_write(WORLD + SPEED, struct.pack("<i", speed))
        mu.mem_write(WORLD + CATCHING_UP, bytes([catching_up]))
        mu.emu_start(0x4632CB, 0x463312)            # up to the food call (its argument pushed)
        pushed = struct.unpack("<I", mu.mem_read(mu.reg_read(UC_X86_REG_ESP), 4))[0]
        return self.i32(mu, FISH), pushed, mu.reg_read(UC_X86_REG_ECX)

    def test_the_stock_bytes_are_the_patches_before(self):
        self.assertEqual(len(fvb_patches()), 2)
        self.machine(True)

    def test_fish_stop_at_zero(self):
        self.assertEqual(self.fish(True, 4, 3)[0], 0)
        self.assertEqual(self.fish(False, 4, 3)[0], 4 - 11, "the stock game goes below 0")
        self.assertEqual(self.fish(True, -50, 3)[0], 0, "an old save's count below 0 comes back to 0 at the next catch")

    def test_the_catch_is_unchanged(self):
        for speed, catching_up, amount in ((3, 0, 11), (10, 0, 5), (5, 0, 8), (3, 1, 8)):
            with self.subTest(speed=speed, catching_up=catching_up):
                for patched in (False, True):
                    left, pushed, ecx = self.fish(patched, 1000, speed, catching_up)
                    self.assertEqual((left, pushed, ecx), (1000 - amount, amount, WORLD))

    def field(self, patched: bool, field: int, crops: int, yield_: int):
        mu = self.machine(patched)
        mu.mem_write(WORLD + FIELD, struct.pack("<i", field))
        mu.mem_write(WORLD + CROPS, struct.pack("<i", crops))
        mu.reg_write(UC_X86_REG_EDI, yield_)
        mu.emu_start(0x46325E, 0x46327C)
        return self.i32(mu, FIELD), self.i32(mu, CROPS), mu.reg_read(UC_X86_REG_EAX)

    def test_the_field_stops_at_zero_and_the_crops_are_unchanged(self):
        self.assertEqual(self.field(True, 6, 800, 10), (0, 790, WORLD))
        self.assertEqual(self.field(False, 6, 800, 10), (-4, 790, WORLD), "the stock game goes below 0")
        self.assertEqual(self.field(True, 500, 800, 10), (490, 790, WORLD))
        self.assertEqual(self.field(True, 6, 5, 10), (0, -5, WORLD), "the crops' own subtract is not changed")


if __name__ == "__main__":
    unittest.main()
