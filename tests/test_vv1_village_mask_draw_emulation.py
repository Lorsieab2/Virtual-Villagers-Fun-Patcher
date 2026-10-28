"""Run VV1's village head-draw calls through the Origins mask hooks.

A New Home draws villagers in the compositor 0x437790 (called at 0x4240FE).
The age test at 0x4379A7 (`cmp [rec+0x348],0x118`) splits loop 1:

  * children draw their heads through the seven-argument thunk 0x409410 ->
    0x408AF0 (e.g. the female head at 0x437FB9);
  * adults (`jge 0x438014` at 0x4379B1) draw their heads through the
    five-argument thunk 0x4093C0 -> 0x408740, from the same male_heads /
    female_heads sheets ([gameobj+0x3DFF8] / [+0x3DFF4]; the swim head at
    0x438150, the walking head at 0x438273) and their action sheets the same
    way (male_actions [gameobj+0x3DFF0] at 0x438220);
  * an adult standing in water first gets a ripple drawn under it at 0x43808A,
    through the other five-argument thunk 0x4093E0 -> 0x408840, from
    [gameobj+0x3E008] -- ripple.png, built at 0x43C2D3..0x43C2EB.  That is not
    a head, and the Origins row leaves 0x4093E0 stock.

This test renders the patcher's real output in all three population modes,
with the Origins row alone and with every VV1 public patch, starts the CPU at
each stock call instruction with the arguments pushed, and records every call
into the three stock draw functions.  A masked villager's head must be drawn
and then its mask (same x, lifted y, mask colour row); the ripple and the
action sheet must be drawn alone.  Skipped (not failed) when the optional
`unicorn` package is unavailable.
"""
from __future__ import annotations

import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

try:  # optional dependency
    from unicorn import UC_ARCH_X86, UC_HOOK_CODE, UC_MODE_32, Uc
    from unicorn.x86_const import (
        UC_X86_REG_EAX, UC_X86_REG_EBP, UC_X86_REG_EBX, UC_X86_REG_ECX,
        UC_X86_REG_EDI, UC_X86_REG_EIP, UC_X86_REG_ESI, UC_X86_REG_ESP,
    )

    HAVE_UNICORN = True
except ImportError:  # pragma: no cover - environment dependent
    HAVE_UNICORN = False

STOCK_CANDIDATES = (
    ROOT / "inputs" / "vv1-stock-copy" / "Virtual Villagers - A New Home.exe",
    ROOT / "research" / "stock-executables" / "Virtual Villagers - A New Home.exe",
)
MODES = ("stock", "immediate_fixed", "collection_progression")
ORIGINS = "vv1_enable_origins_exclusive_features"

# Patch-owned .vv1md scratch the hooks read (scripts/build_vv1_origins_feature.py).
MASK_TABLE = 0x491000
MASK_MANAGER = 0x491098
CUR_IDX = 0x4911B4
MASK_SPRITE = 0x4911B8

GAMEOBJ = 0x20000000
RECORD_SIZE = 0x3D8
STACK = 0x30000000
RENDERER = 0x40000000          # ECX at the call: [RENDERER] is the surface
SURFACE = 0x41000000
RIPPLE, MALE_HEADS, FEMALE_HEADS, MALE_ACTIONS, MASK = (
    0x61000000, 0x62000000, 0x63000000, 0x64000000, 0x65000000)
SHEETS = {0x3E008: RIPPLE, 0x3DFF8: MALE_HEADS, 0x3DFF4: FEMALE_HEADS, 0x3DFF0: MALE_ACTIONS}
DRAW_FNS = {0x408AF0: 0x1C, 0x408740: 0x14, 0x408840: 0x14}  # entry -> ret imm
ADULT = 0x200
CHILD = 0x50
X, Y, ROW, COL, SCALE = 100, 200, 4, 3, 100

# The stock 0x4093C0 callers: all fourteen sit in loop 1's adult branch.
ADULT_THUNK_CALLERS = (0x438150, 0x438220, 0x438273, 0x438296, 0x4382E9, 0x438337, 0x43838D,
                       0x4383D5, 0x43854F, 0x4385A3, 0x4385E9, 0x438733, 0x438787, 0x4387CD)


def _stock() -> Path | None:
    return next((path for path in STOCK_CANDIDATES if path.is_file()), None)


def _render(mode: str, every_public_patch: bool) -> bytes:
    import vv_fun_patcher as patcher

    builds = {build.id: build for build in patcher.load_builds()}
    if every_public_patch:
        ids = [item.id for item in patcher.load_fun_patches() if item.game_id == "vv1"]
    else:
        ids = [ORIGINS]
    rendered, _ = patcher.render_patched_bytes(_stock(), builds["vv1"], mode, ids)
    return bytes(rendered)


def _sections(image: bytes):
    pe = struct.unpack_from("<I", image, 0x3C)[0]
    count = struct.unpack_from("<H", image, pe + 6)[0]
    optional = struct.unpack_from("<H", image, pe + 20)[0]
    base = struct.unpack_from("<I", image, pe + 24 + 28)[0]
    table = pe + 24 + optional
    for index in range(count):
        entry = table + 40 * index
        vsize, rva, rsize, raw = struct.unpack_from("<IIII", image, entry + 8)
        yield base + rva, max(vsize, rsize), raw, rsize


def _draw(image: bytes, call_site: int, args: list[int], *, index: int, age: int, mask: int):
    """Execute the stock CALL at call_site; return every draw-function call."""
    mu = Uc(UC_ARCH_X86, UC_MODE_32)
    for va, size, raw, rsize in _sections(image):
        start = va & ~0xFFF
        end = (va + size + 0xFFF) & ~0xFFF
        mu.mem_map(start, end - start)
        mu.mem_write(va, image[raw:raw + rsize])
    mu.mem_map(GAMEOBJ, 0x100000)
    mu.mem_map(STACK, 0x10000)
    mu.mem_map(RENDERER, 0x1000)
    mu.mem_write(RENDERER, struct.pack("<I", SURFACE))
    for offset, sprite in SHEETS.items():
        mu.mem_write(GAMEOBJ + offset, struct.pack("<I", sprite))
    mu.mem_write(GAMEOBJ + index * RECORD_SIZE + 0x348, struct.pack("<I", age))
    mu.mem_write(MASK_MANAGER, struct.pack("<I", GAMEOBJ))
    mu.mem_write(CUR_IDX, struct.pack("<I", index))
    mu.mem_write(MASK_SPRITE, struct.pack("<I", MASK))  # atlas already built
    table = bytearray(128)
    table[index >> 1] |= mask << 4 if index & 1 else mask
    mu.mem_write(MASK_TABLE, bytes(table))
    top = STACK + 0x8000
    esp = top - 4 * len(args)
    mu.mem_write(esp, struct.pack(f"<{len(args)}I", *args))
    saved = dict(EBX=0x0B0B0B0B, ESI=0x05050505, EDI=0x0D0D0D0D, EBP=0x0E0E0E0E)
    for name, value in saved.items():
        mu.reg_write(globals()[f"UC_X86_REG_{name}"], value)
    mu.reg_write(UC_X86_REG_ESP, esp)
    mu.reg_write(UC_X86_REG_ECX, RENDERER)
    mu.reg_write(UC_X86_REG_EAX, 0x77)
    draws = []

    def stub(uc, address, size, _data) -> None:
        sp = uc.reg_read(UC_X86_REG_ESP)
        count = DRAW_FNS[address] // 4
        ret, *called = struct.unpack(f"<{count + 1}I", uc.mem_read(sp, 4 * (count + 1)))
        draws.append((address, uc.reg_read(UC_X86_REG_ECX), tuple(called)))
        uc.reg_write(UC_X86_REG_ESP, sp + 4 + DRAW_FNS[address])
        uc.reg_write(UC_X86_REG_EIP, ret)

    for address in DRAW_FNS:
        mu.hook_add(UC_HOOK_CODE, stub, begin=address, end=address)
    mu.emu_start(call_site, call_site + 5, count=5000)
    if mu.reg_read(UC_X86_REG_EIP) != call_site + 5:
        raise AssertionError(f"stopped at {mu.reg_read(UC_X86_REG_EIP):#x}")
    if mu.reg_read(UC_X86_REG_ESP) != top:
        raise AssertionError("the call did not pop exactly its own arguments")
    for name, value in saved.items():
        if mu.reg_read(globals()[f"UC_X86_REG_{name}"]) != value:
            raise AssertionError(f"{name} not preserved")
    return draws


@unittest.skipUnless(HAVE_UNICORN, "unicorn is not installed")
@unittest.skipUnless(_stock() is not None, "the stock VV1 executable is not available")
class VV1VillageMaskDrawEmulation(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.stock = _stock().read_bytes()
        cls.images = {
            (mode, "every public patch" if every else "Origins alone"): _render(mode, every)
            for mode in MODES
            for every in (False, True)
        }

    def _each(self):
        for (mode, family), image in self.images.items():
            with self.subTest(mode=mode, family=family):
                yield image

    def test_the_ripple_is_never_masked(self) -> None:
        args = [RIPPLE, X, Y, 2, 0x3ECCCCCD]
        for image in self._each():
            for mask in (0, 1, 5):
                self.assertEqual(
                    _draw(image, 0x43808A, args, index=3, age=ADULT, mask=mask),
                    [(0x408840, SURFACE, tuple(args))],
                )

    def test_the_ripple_thunk_is_left_stock(self) -> None:
        for image in self._each():
            self.assertEqual(image[0x93E0:0x93E7], self.stock[0x93E0:0x93E7])

    def test_adult_heads_get_their_mask(self) -> None:
        for site, sheet in ((0x438150, MALE_HEADS), (0x438273, MALE_HEADS), (0x438150, FEMALE_HEADS)):
            args = [sheet, X, Y, ROW, COL]
            for image in self._each():
                for mask in (1, 3, 5):
                    with self.subTest(site=hex(site), sheet=hex(sheet), mask=mask):
                        self.assertEqual(
                            _draw(image, site, args, index=7, age=ADULT, mask=mask),
                            [(0x408740, SURFACE, tuple(args)),
                             (0x408740, SURFACE, (MASK, X, Y - 48, mask - 1, COL))],
                        )

    def test_unmasked_adults_and_action_sheets_draw_alone(self) -> None:
        cases = ((0x438150, MALE_HEADS, 0), (0x438220, MALE_ACTIONS, 2))
        for site, sheet, mask in cases:
            args = [sheet, X, Y, ROW, COL]
            for image in self._each():
                with self.subTest(site=hex(site)):
                    self.assertEqual(
                        _draw(image, site, args, index=4, age=ADULT, mask=mask),
                        [(0x408740, SURFACE, tuple(args))],
                    )

    def test_child_heads_get_their_mask(self) -> None:
        args = [FEMALE_HEADS, X, Y, ROW, COL, SCALE, 1]
        lift = (SCALE * 15) >> 5
        for image in self._each():
            for mask in (1, 4):
                self.assertEqual(
                    _draw(image, 0x437FB9, args, index=6, age=CHILD, mask=mask),
                    [(0x408AF0, SURFACE, tuple(args)),
                     (0x408AF0, SURFACE, (MASK, X, Y - lift, mask - 1, COL, SCALE, 1))],
                )

    def test_only_the_stock_adult_branch_enters_the_adult_hook(self) -> None:
        # The adult hook has no caller-address gate because nothing else calls
        # 0x4093C0: no other rel32 call or jump in any rendered image, and no
        # stored pointer to it.
        for image in self._each():
            sources = []
            for va, size, raw, rsize in _sections(image):
                code = image[raw:raw + rsize]
                for offset in range(len(code) - 4):
                    if code[offset] in (0xE8, 0xE9):
                        rel = struct.unpack_from("<i", code, offset + 1)[0]
                        if (va + offset + 5 + rel) & 0xFFFFFFFF == 0x4093C0:
                            sources.append(va + offset)
            self.assertEqual(sorted(sources), list(ADULT_THUNK_CALLERS))
            self.assertNotIn(struct.pack("<I", 0x4093C0), image)


if __name__ == "__main__":
    unittest.main()
