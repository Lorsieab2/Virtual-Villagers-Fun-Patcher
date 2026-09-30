"""VV3 Birth Control, RUN from the rendered executable.

The row makes two behavioural changes in The Secret City, and both are executed
here in an emulator on a render WITH the row and one WITHOUT it:

1. The action-13 mate selector at 0x45CE00 scans the village five records per
   loop turn; each of its five blocks rejects a pair when the CANDIDATE's age
   (ESI, record-4) is 1000 or more and again when the INITIATOR's age (EDX,
   initiator+0xDC4) is.  The row NOPs only the initiator's check in all five
   blocks, so an initiator of any age may pair with a candidate under 1000,
   and a candidate of 1000 or more is still refused.
2. The chooser at 0x459730, having picked the Parenting category (1) for a
   villager whose Parenting preference is not checked, rolls RNG(100) >= 75
   in stock and lets one in four through.  The row replaces that roll with a
   jump to the chooser's reject epilogue (0x4598B8), so the villager is
   refused without a roll; a checked preference, and every other category,
   leave the chooser exactly as in stock.

Only the game's RNG wrapper (0x4032D0) is replaced, by a value chosen per call
site; everything else is the rendered code.
"""
from __future__ import annotations

import struct
import sys
import unittest
from pathlib import Path

import pefile
from unicorn import UC_ARCH_X86, UC_HOOK_CODE, UC_MODE_32, Uc
from unicorn.x86_const import UC_X86_REG_EAX, UC_X86_REG_ECX, UC_X86_REG_ESP

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import vv_fun_patcher as vfp  # noqa: E402

EXE = ROOT / "research" / "stock-executables" / "Virtual Villagers - The Secret City.exe"
FEATURE = "vv3_birth_control"
RNG = 0x4032D0
SELECTOR = 0x45CE00
CHOOSER = 0x459730
FALLBACK_ROLL_RETURN = 0x459897      # the stock RNG(100) the row removes
STRIDE = 0x1F8C
SCRATCH = 0x0F000000
RNG_VALUE = SCRATCH
VILLAGE = 0x20000000
INITIATOR = 0x21000000
RECORD = 0x22000000
RETURN = SCRATCH + 0x800
STACK_TOP = 0x10800000


def _render(with_row: bool) -> bytes:
    build = next(b for b in vfp.load_builds() if b.id == "vv3")
    rendered, applied = vfp.render_patched_bytes(EXE, build, "immediate_fixed", [FEATURE] if with_row else [])
    assert (f"feature:{FEATURE}" in {r["owner"] for r in applied}) == with_row
    return bytes(rendered)


def _machine(image: bytes, rolls: dict[int, int], default_roll: int):
    """Load the image; the RNG wrapper returns rolls[return address] or the default."""
    pe = pefile.PE(data=image)
    mu = Uc(UC_ARCH_X86, UC_MODE_32)
    mu.mem_map(0x400000, (pe.OPTIONAL_HEADER.SizeOfImage + 0xFFF) & ~0xFFF)
    mu.mem_write(0x400000, image[:pe.OPTIONAL_HEADER.SizeOfHeaders])
    for section in pe.sections:
        mu.mem_write(0x400000 + section.VirtualAddress, section.get_data())
    mu.mem_map(SCRATCH, 0x1000)
    mu.mem_map(VILLAGE, 0x200000)
    mu.mem_map(INITIATOR, 0x2000)
    mu.mem_map(RECORD, 0x2000)
    mu.mem_map(STACK_TOP - 0x10000, 0x10000)
    mu.mem_write(RETURN, b"\xF4")
    # mov eax, [RNG_VALUE] ; ret   (cdecl, one argument the caller pops)
    mu.mem_write(RNG, b"\xA1" + struct.pack("<I", RNG_VALUE) + b"\xC3")
    calls = []

    def hook(uc, address, size, _):
        if address == RNG:
            esp = uc.reg_read(UC_X86_REG_ESP)
            ret, n = struct.unpack("<Ii", uc.mem_read(esp, 8))
            calls.append((ret, n))
            uc.mem_write(RNG_VALUE, struct.pack("<I", rolls.get(ret, default_roll)))

    mu.hook_add(UC_HOOK_CODE, hook)
    return mu, calls


def _call(mu, entry: int, arg: int, this: int = 0) -> int:
    esp = STACK_TOP - 0x400
    mu.mem_write(esp, struct.pack("<II", RETURN, arg))
    mu.reg_write(UC_X86_REG_ESP, esp)
    mu.reg_write(UC_X86_REG_ECX, this)
    mu.emu_start(entry, RETURN, count=200000)
    assert mu.reg_read(UC_X86_REG_ESP) == esp + 8, "stdcall with one argument: ret 4"
    return struct.unpack("<i", struct.pack("<I", mu.reg_read(UC_X86_REG_EAX)))[0]


def _select(image: bytes, block: int, initiator_age: int, candidate_age: int) -> int:
    """Run the mate selector over a village whose only eligible candidate is
    record `block` (so it is examined by that one of the five blocks)."""
    mu, _ = _machine(image, {}, 0)
    p = VILLAGE + 0xDDC + block * STRIDE        # the selector's per-record base
    mu.mem_write(p + 0xB0, struct.pack("<i", 1))          # alive / present
    mu.mem_write(p - 4, struct.pack("<i", candidate_age))
    mu.mem_write(p + 0x148, b"\x01")                     # eligible flag
    init = bytearray(0x2000)
    struct.pack_into("<i", init, 0xE78, 1)
    struct.pack_into("<i", init, 0xDC4, initiator_age)
    struct.pack_into("<i", init, 0xDC8, 1)               # differs from the candidate's 0
    struct.pack_into("<i", init, 0xDD0, 7)
    struct.pack_into("<i", init, 0xEE0, 5)
    mu.mem_write(INITIATOR, bytes(init))
    return _call(mu, SELECTOR, INITIATOR, this=VILLAGE)


def _choose(image: bytes, preference: int, category_skill: int, fallback_roll: int) -> tuple[int, list]:
    """Run the chooser for a villager whose one non-zero skill is in category
    `category_skill` (so that category is picked) with the given preference."""
    mu, calls = _machine(image, {FALLBACK_ROLL_RETURN: fallback_roll}, 50)
    record = bytearray(0x2000)
    struct.pack_into("<i", record, 0xEAC + 4 * category_skill, 100)
    struct.pack_into("<i", record, 0xEC0, preference)
    mu.mem_write(RECORD, bytes(record))
    return _call(mu, CHOOSER, RECORD), calls


class VV3BirthControlExecutes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.stock = _render(False)
        cls.patched = _render(True)

    def test_each_selector_block_ignores_the_initiators_age_and_keeps_the_candidates(self):
        for block in range(5):
            for initiator, candidate, stock_ok, patched_ok in (
                (500, 500, True, True),
                (1200, 500, False, True),      # the row's change
                (5000, 999, False, True),
                (500, 1000, False, False),     # the candidate's own ceiling is kept
                (1200, 1200, False, False),
                (300, 500, False, False),      # the stock lower bound (360) is kept
                (500, 300, False, False),
            ):
                with self.subTest(block=block, initiator=initiator, candidate=candidate):
                    self.assertEqual(_select(self.stock, block, initiator, candidate), block if stock_ok else -1)
                    self.assertEqual(_select(self.patched, block, initiator, candidate), block if patched_ok else -1)

    def test_an_unchecked_parenting_preference_is_refused_without_the_25_percent_roll(self):
        for roll in (0, 74, 75, 99):
            with self.subTest(roll=roll):
                stock, stock_calls = _choose(self.stock, -1, 1, roll)
                self.assertEqual(stock, 1 if roll >= 75 else -1, "stock lets one in four through")
                self.assertIn((FALLBACK_ROLL_RETURN, 100), stock_calls)
                patched, patched_calls = _choose(self.patched, -1, 1, roll)
                self.assertEqual(patched, -1)
                self.assertNotIn(FALLBACK_ROLL_RETURN, [ret for ret, _ in patched_calls],
                                 "the fallback roll must not be made at all")
                # everything before the removed roll is untouched
                self.assertEqual(patched_calls, [c for c in stock_calls if c[0] != FALLBACK_ROLL_RETURN])

    def test_a_checked_preference_and_every_other_category_leave_the_chooser_as_stock(self):
        for preference, category, expected in ((1, 1, 1), (-1, 0, 0), (-1, 2, 2), (-1, 3, 3), (-1, 4, 4), (3, 3, 3)):
            for roll in (0, 99):
                with self.subTest(preference=preference, category=category, roll=roll):
                    stock, stock_calls = _choose(self.stock, preference, category, roll)
                    patched, patched_calls = _choose(self.patched, preference, category, roll)
                    self.assertEqual(stock, expected)
                    self.assertEqual(patched, expected)
                    self.assertEqual(patched_calls, stock_calls)


if __name__ == "__main__":
    unittest.main()
