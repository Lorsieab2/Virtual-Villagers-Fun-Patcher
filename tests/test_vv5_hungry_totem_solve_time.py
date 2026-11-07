"""New Believers: "Fix Vanilla Bugs" -- the Puzzles screen's time for The Hungry Totem.

The owner, 2026-11-06: "can you make a fix for the VV5 Hungry Totem not counting the number of hours it takes to
complete the puzzle? (for some reason it's permanently set to 0 regardless of when you solved it)".

The game keeps the time right: Advance 0x43AF80 stamps every puzzle's solve time from the game clock (0x41ED40 on
0x51D490) into the puzzle table 0x51E008 (each puzzle a (progress, time) pair), The Hungry Totem's dismantling
(0x439650) included, and the owner's own save holds 3,474 seconds for it.  The fault is on the Puzzles screen: its
text for a solved puzzle (0x448FE0: the puzzle's tip, then "Completed in N hours") zeroes ebx at the start
(0x449002); each puzzle's branch pushes its id and jumps to 0x449069, which calls the time getter 0x43AF20 and keeps
the answer with "mov ebx,eax" (0x449073) before the hours (ebx / 3600) are formatted.  The Hungry Totem's branch
calls the getter itself and then jumps to 0x449075 (0x44917C), one instruction too far, so the "mov ebx,eax" is
skipped and the hours are always 0 / 3600 = 0.  The fix moves that jump's target back two bytes onto 0x449073.

Everything below RUNS the stock and the patcher's rendered bytes in unicorn: each puzzle's branch of the real
routine, with the puzzle solved at a known time, up to its sprintf (0x4490C8, "%s\\n\\n%s%i %s.").
"""
from __future__ import annotations

import functools
import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vv_fun_patcher import load_builds, load_fun_patches, render_patched_bytes  # noqa: E402

try:
    import pefile
    from unicorn import UC_ARCH_X86, UC_HOOK_CODE, UC_MODE_32, Uc
    from unicorn.x86_const import UC_X86_REG_EAX, UC_X86_REG_EBX, UC_X86_REG_EIP, UC_X86_REG_ESP
except ImportError:  # pragma: no cover
    pefile = None

FEATURE_ID = "vv5_fix_vanilla_bugs"
STOCK = ROOT / "research" / "stock-executables" / "Virtual Villagers - New Believers.exe"
NO_STOCK = "stock executables are not available"
MODES = ("stock", "collection_progression", "immediate_fixed")
BASE, STK, RETURN = 0x400000, 0x20000000, 0x0BAD0000

FIX = (0x4917C, bytes.fromhex("E9F4FEFFFF"), bytes.fromhex("E9F2FEFFFF"))   # jmp 0x449075 -> jmp 0x449073
TABLE, THRESHOLDS = 0x51E008, 0x51DF30
TEXTS, TEXT = 0x450D40, 0x4506D0              # the string table's instance, its lookup (ret 4)
SPRINTF, NOT_SOLVED = 0x4490C8, 0x449421
# Each puzzle's branch from its own "is it solved" test: (id, entry, its tip's text id).
BRANCHES = ((1, 0x44904E, 0x2F0), (2, 0x449129, 0x2E8), (3, 0x449157, 0x2E9), (4, 0x44918F, 0x2ED))
STRING = 0x40000000                            # a lookup's answer: STRING + its text id


def _have() -> bool:
    return pefile is not None and STOCK.is_file()


@functools.lru_cache(maxsize=None)
def _render(mode: str) -> bytes:
    build = next(b for b in load_builds() if b.id == "vv5")
    data, _ = render_patched_bytes(STOCK, build, mode, [FEATURE_ID])
    return bytes(data)


class _Machine:
    """The mapped executable, a stack, and the string table's two calls answered by stubs."""

    def __init__(self, data: bytes) -> None:
        pe = pefile.PE(data=data)
        image = pe.get_memory_mapped_image()
        self.mu = mu = Uc(UC_ARCH_X86, UC_MODE_32)
        mu.mem_map(BASE, (max(len(image), pe.OPTIONAL_HEADER.SizeOfImage) + 0xFFFF) & ~0xFFFF)
        mu.mem_write(BASE, image)
        mu.mem_map(STK, 0x100000)
        mu.mem_map(RETURN, 0x1000)
        self.seen: dict = {}
        mu.hook_add(UC_HOOK_CODE, self._code)

    def _code(self, uc, address, _size, _user) -> None:
        if address not in (TEXTS, TEXT, SPRINTF, NOT_SOLVED):
            return
        sp = uc.reg_read(UC_X86_REG_ESP)
        back = struct.unpack("<I", uc.mem_read(sp, 4))[0]
        if address == TEXTS:
            uc.reg_write(UC_X86_REG_EAX, 0x1234)
            uc.reg_write(UC_X86_REG_ESP, sp + 4)
            uc.reg_write(UC_X86_REG_EIP, back)
        elif address == TEXT:
            text_id = struct.unpack("<I", uc.mem_read(sp + 4, 4))[0]
            uc.reg_write(UC_X86_REG_EAX, STRING + text_id)
            uc.reg_write(UC_X86_REG_ESP, sp + 8)
            uc.reg_write(UC_X86_REG_EIP, back)
        elif address == SPRINTF:
            # sprintf(buffer, "%s\n\n%s%i %s.", tip, "Completed in ", hours, "hours")
            args = struct.unpack("<6I", uc.mem_read(sp, 24))
            self.seen["text"] = (args[2] - STRING, args[3] - STRING,
                                 struct.unpack("<i", struct.pack("<I", args[4]))[0], args[5] - STRING)
            uc.emu_stop()
        else:
            self.seen["text"] = None
            uc.emu_stop()


@functools.lru_cache(maxsize=None)
def _machine(data: bytes) -> _Machine:
    return _Machine(data)


def completed_in(data: bytes, puzzle: int, seconds: int, solved: bool = True, ebx: int = 0):
    """Run the Puzzles screen's branch for `puzzle`, solved `seconds` after the clock's start: (the tip's text id,
    the hours it formats), or None when the routine leaves without text (not solved)."""
    machine = _machine(data)
    mu = machine.mu
    for pid in range(0, 26):
        mu.mem_write(THRESHOLDS + 4 * pid, struct.pack("<i", 1))
        mu.mem_write(TABLE + 8 * pid, struct.pack("<ii", 0, 0))
    mu.mem_write(TABLE + 8 * puzzle, struct.pack("<ii", 1 if solved else 0, seconds if solved else 0))
    mu.reg_write(UC_X86_REG_ESP, STK + 0x80000)
    mu.reg_write(UC_X86_REG_EBX, ebx)            # the routine's own xor ebx,ebx (0x449002) by default
    machine.seen.clear()
    entry = next(e for pid, e, _tip in BRANCHES if pid == puzzle)
    mu.emu_start(entry, RETURN, count=5000)
    if "text" not in machine.seen:
        raise AssertionError(f"puzzle {puzzle}: the branch reached neither its text nor its exit")
    if machine.seen["text"] is None:
        return None
    tip, completed, hours, word = machine.seen["text"]
    assert (completed, word) == (0x4A3, 0x4A4), (hex(completed), hex(word))   # eCompletedIn, eHours
    return tip, hours


@unittest.skipUnless(_have(), NO_STOCK)
class StockTests(unittest.TestCase):
    def test_the_site_holds_the_stock_jump(self):
        raw = STOCK.read_bytes()
        offset, before, _after = FIX
        self.assertEqual(raw[offset:offset + len(before)], before)
        self.assertEqual(pefile.PE(str(STOCK), fast_load=True).get_offset_from_rva(offset), offset)
        # the jump's old and new targets: past "mov ebx,eax" (8B D8), and onto it
        self.assertEqual(BASE + offset + 5 + struct.unpack("<i", before[1:])[0], 0x449075)
        self.assertEqual(BASE + offset + 5 + struct.unpack("<i", FIX[2][1:])[0], 0x449073)
        self.assertEqual(raw[0x49073:0x49075], b"\x8b\xd8")

    def test_stock_shows_0_hours_for_the_hungry_totem_only(self):
        raw = STOCK.read_bytes()
        for pid, _entry, tip in BRANCHES:
            for seconds in (3_474, 10 * 3600 + 5, 400 * 3600):
                with self.subTest(puzzle=pid, seconds=seconds):
                    want = 0 if pid == 3 else seconds // 3600
                    self.assertEqual(completed_in(raw, pid, seconds), (tip, want))
        # the 0 is whatever ebx held: the routine's own 0
        self.assertEqual(completed_in(raw, 3, 50 * 3600, ebx=7 * 3600), (0x2E9, 7))

    def test_not_solved_shows_no_text(self):
        raw = STOCK.read_bytes()
        for pid, _entry, _tip in BRANCHES:
            self.assertIsNone(completed_in(raw, pid, 0, solved=False))
            self.assertIsNone(completed_in(_render("stock"), pid, 0, solved=False))


@unittest.skipUnless(_have(), NO_STOCK)
class RenderTests(unittest.TestCase):
    def test_the_row_carries_the_fix(self):
        row = next(p for p in load_fun_patches() if p.id == FEATURE_ID).raw
        pinned = [(int(p["offset"], 16), bytes.fromhex(p["before"]), bytes.fromhex(p["after"])) for p in row["patches"]]
        self.assertIn(FIX, pinned)
        self.assertIn("The Hungry Totem", row["description"])
        self.assertTrue(row["description"].endswith("**Needs no other patch.**"))

    def test_patched_shows_the_kept_hours_in_every_mode(self):
        for mode in MODES:
            data = _render(mode)
            offset, _before, after = FIX
            self.assertEqual(data[offset:offset + len(after)], after, mode)
            for pid, _entry, tip in BRANCHES:
                for seconds in (3_474, 3_600, 10 * 3600 + 5, 400 * 3600):
                    with self.subTest(mode=mode, puzzle=pid, seconds=seconds):
                        self.assertEqual(completed_in(data, pid, seconds), (tip, seconds // 3600))
            # a stamp of 0 (a puzzle the game kept no time for) still reads as 0 hours
            self.assertEqual(completed_in(data, 3, 0), (0x2E9, 0))

    def test_only_the_jump_changes(self):
        stock = STOCK.read_bytes()
        without = render_patched_bytes(STOCK, next(b for b in load_builds() if b.id == "vv5"), "stock", [])[0]
        self.assertEqual(bytes(without)[FIX[0]:FIX[0] + 5], FIX[1])
        self.assertEqual(stock[FIX[0]:FIX[0] + 5], FIX[1])


if __name__ == "__main__":
    unittest.main()
