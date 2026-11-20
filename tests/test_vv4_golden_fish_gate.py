"""Complete Fish Scales = Golden Fish in Nets (The Tree of Life): no Golden Fish shows or is caught below 12 scales.

The owner (2026-11-18, live 256 game, Fish Scale 10 of 12): a Golden Fish showed in the fishing nets although the
patch was on.  The rule: with the patch on, the Golden Fish must neither appear nor be catchable until all 12 Fish
Scales are found.

Every Golden Fish path in the stock exe, read from the code:

* The nets' catch pile (the nets object's draw, 0x432CB5..0x432D7D, nets state 4): it reads the scale count
  (collection 0x46 through 0x413B90) and draws GoldFishPile.png (sprite 39, nets object +0x40) on both nets, at
  (0x6EB, 0x4B2) and (0x711, 0x5C0), when the count is 2 or more (0x432CF0 cmp eax, 2); else fishpile1.png
  (sprite 38, +0x3C).  This picture is what the owner saw.  The patch now needs 12 here (0x32CF2: 02 -> 0C).
* The catch (the fisher at the nets, 0x43334E..0x4333AC): rand(100) < 2 x scales + 1 and scales >= 1 (0x433384
  cmp eax, 1) carry a Golden Fish (carried object 0x39, 0x43338B) and go to job event 17 (0x4645E1, which pays
  the Golden Fish's food); else a plain fish (0x38).  The patch already needed 12 here (0x33386: 01 -> 0C).  This is
  the only place a Golden Fish is carried and the only place job event 17 is chosen.
* No island event, item or catch-up step grants one (no other push 0x39 reaches the carry setter 0x4697C0, and the
  only other scale-count reads, 0x43C3F0 / 0x440C00 / 0x46835C, are the collection's count text and the completed
  collection bonus).  The middle-of-the-water shape in the owner's screenshot is the game's own open-hand cursor
  (hand_open.png), not a fish.

Pinned here: the stock and rendered bytes in every population mode and with 256 Villagers, and both the draw and
the catch RUN in an emulator over the stock and rendered executables at 0..12 scales.
"""
from __future__ import annotations

import struct
import sys
import unittest
from pathlib import Path

import pefile
from unicorn import UC_ARCH_X86, UC_HOOK_CODE, UC_MODE_32, Uc
from unicorn.x86_const import UC_X86_REG_EAX, UC_X86_REG_EIP, UC_X86_REG_ESI, UC_X86_REG_ESP

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import vv_fun_patcher as vfp  # noqa: E402

STOCK = ROOT / "research" / "stock-executables"
EXE = STOCK / "Virtual Villagers - The Tree of Life.exe"
ROW = "vv4_complete_scales_golden_fish"

COUNT = 0x413B90        # collection count (thiscall, 4 args)
DRAW = 0x44C790         # sprite draw (thiscall, 7 args)
RAND = 0x4036D0         # rand(n) (cdecl)
CARRY = 0x4697C0        # villager's carried object (thiscall, 1 arg)
PILE = (0x432CB5, 0x432D7D)
CATCH = (0x43334E, 0x4333AC)
PLAIN, GOLD = 0x1111, 0x2222    # the nets object's +0x3C (fishpile1) and +0x40 (GoldFishPile)
SITES = {0x32CF0: ("83F802", "83F80C"), 0x33384: ("83F801", "83F80C")}
MODES = ("stock", "collection_progression", "immediate_fixed")


def _render(mode: str = "immediate_fixed", rows: tuple[str, ...] = (ROW,)) -> bytes:
    build = next(b for b in vfp.load_builds() if b.id == "vv4")
    rendered, applied = vfp.render_patched_bytes(EXE, build, mode, list(rows))
    owners = {r["owner"] for r in applied}
    assert (f"feature:{ROW}" in owners) == (ROW in rows), owners
    return bytes(rendered)


def _machine(image: bytes):
    pe = pefile.PE(data=image, fast_load=True)
    mu = Uc(UC_ARCH_X86, UC_MODE_32)
    top = max(s.VirtualAddress + max(s.Misc_VirtualSize, s.SizeOfRawData) for s in pe.sections)
    mu.mem_map(0x400000, (top + 0xFFFF) & ~0xFFFF)
    for s in pe.sections:
        raw = image[s.PointerToRawData:s.PointerToRawData + s.SizeOfRawData]
        mu.mem_write(0x400000 + s.VirtualAddress, raw[:max(s.Misc_VirtualSize, s.SizeOfRawData)])
    obj, stack = 0x20000000, 0x70000000
    mu.mem_map(obj, 0x10000)
    mu.mem_map(stack - 0x10000, 0x20000)
    mu.mem_write(obj + 0x3C, struct.pack("<II", PLAIN, GOLD))
    mu.reg_write(UC_X86_REG_ESP, stack - 0x100)
    mu.reg_write(UC_X86_REG_ESI, obj)
    return mu


def _ret(mu, value: int | None, pop: int) -> None:
    esp = mu.reg_read(UC_X86_REG_ESP)
    ret = struct.unpack("<I", mu.mem_read(esp, 4))[0]
    if value is not None:
        mu.reg_write(UC_X86_REG_EAX, value)
    mu.reg_write(UC_X86_REG_ESP, esp + 4 + pop)
    mu.reg_write(UC_X86_REG_EIP, ret)


def _pile(image: bytes, scales: int) -> list[tuple[int, int, int]]:
    """Run the nets' catch-pile draw: the (sprite, x, y) of each net's pile."""
    mu, drawn = _machine(image), []

    def hook(mu, address, size, user_data):
        if address == COUNT:
            _ret(mu, scales, 0x10)
        elif address == DRAW:
            esp = mu.reg_read(UC_X86_REG_ESP)
            drawn.append(struct.unpack("<III", mu.mem_read(esp + 4, 12)))
            _ret(mu, 0, 0x1C)
        elif address == PILE[1]:
            mu.emu_stop()

    mu.hook_add(UC_HOOK_CODE, hook)
    mu.emu_start(PILE[0], 0, count=500)
    assert mu.reg_read(UC_X86_REG_EIP) == PILE[1]
    return drawn


def _catch(image: bytes, scales: int, roll: int) -> int:
    """Run the fisher's catch with rand() returning roll: the carried object (0x39 Golden Fish, 0x38 fish)."""
    mu, carried = _machine(image), []

    def hook(mu, address, size, user_data):
        if address == COUNT:
            _ret(mu, scales, 0x10)
        elif address == RAND:
            _ret(mu, roll, 0)
        elif address == CARRY:
            esp = mu.reg_read(UC_X86_REG_ESP)
            carried.append(struct.unpack("<I", mu.mem_read(esp + 4, 4))[0])
            mu.emu_stop()

    mu.hook_add(UC_HOOK_CODE, hook)
    mu.emu_start(CATCH[0], 0, count=200)
    assert len(carried) == 1, carried
    return carried[0]


def _expected_pile(sprite: int) -> list[tuple[int, int, int]]:
    return [(sprite, 0x6EB, 0x4B2), (sprite, 0x711, 0x5C0)]


class GoldenFishGateTests(unittest.TestCase):
    def test_bytes_in_every_mode_and_with_256(self):
        stock = EXE.read_bytes()
        pe = pefile.PE(str(EXE), fast_load=True)
        self.assertEqual(pe.get_offset_from_rva(0x432CF0 - 0x400000), 0x32CF0)
        self.assertEqual(pe.get_offset_from_rva(0x433384 - 0x400000), 0x33384)
        for off, (before, _) in SITES.items():
            self.assertEqual(stock[off:off + 3].hex().upper(), before)
        for mode in MODES:
            for rows in ((ROW,), (ROW, "vv4_population_256")):
                with self.subTest(mode=mode, rows=rows):
                    image = _render(mode, rows)
                    for off, (_, after) in SITES.items():
                        self.assertEqual(image[off:off + 3].hex().upper(), after)

    def test_stock_shows_and_catches_golden_fish_before_twelve(self):
        """The bug: the stock code shows the Golden Fish pile from 2 scales and catches one from 1."""
        stock = EXE.read_bytes()
        self.assertEqual(_pile(stock, 10), _expected_pile(GOLD))
        self.assertEqual(_pile(stock, 1), _expected_pile(PLAIN))
        self.assertEqual(_catch(stock, 10, 0), 0x39)
        self.assertEqual(_catch(stock, 0, 0), 0x38)

    def test_no_golden_fish_below_twelve_scales(self):
        for rows in ((ROW,), (ROW, "vv4_population_256")):
            image = _render("immediate_fixed", rows)
            for scales in range(12):
                with self.subTest(rows=rows, scales=scales):
                    self.assertEqual(_pile(image, scales), _expected_pile(PLAIN))
                    for roll in (0, 1, 24, 99):
                        self.assertEqual(_catch(image, scales, roll), 0x38)

    def test_twelve_scales_is_stock(self):
        stock = EXE.read_bytes()
        for mode in MODES:
            for rows in ((ROW,), (ROW, "vv4_population_256")):
                image = _render(mode, rows)
                with self.subTest(mode=mode, rows=rows):
                    self.assertEqual(_pile(image, 12), _pile(stock, 12))
                    self.assertEqual(_pile(image, 12), _expected_pile(GOLD))
                    for roll in range(0, 100, 3):
                        self.assertEqual(_catch(image, 12, roll), _catch(stock, 12, roll))
                    self.assertEqual(_catch(image, 12, 24), 0x39)
                    self.assertEqual(_catch(image, 12, 25), 0x38)


if __name__ == "__main__":
    unittest.main()
