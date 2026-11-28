"""New Believers: "Fix Vanilla Bugs" -- polishing the Tribute Statue gives its Divine Energy.

The owner, 2026-11-18 (approved "if true"): the game's own tip says "Polishing the statue gives energy and building
skill." (string 1164), and the game has the step that pays it: work event 40 (the work-event dispatcher 0x46CE60's
case at 0x46DA16, table slot 0x46DF24) adds 1 Divine Energy through the game's own adder 0x424F80, which keeps it
between 0 and the village's cap (+0x17D60).  But nothing ever asks for event 40: the work-event step (op 20, built
by 0x474EF0, the only maker of that step; the dispatcher's only caller is the step executor at 0x473D13) is queued
at 58 places, none with 40, and "Polishing the statue" (action 0x9D, 0x455020) queues only animations, waits and its
Building practice (0x474780(4)).  So polishing trained Building and never gave energy.

The fix queues the game's own event 40 right after the polishing's Building practice: the three pushes at 0x455109
become a call to a cave (0x451B73: push 0x28; mov ecx,esi; call 0x474EF0; jmp 0x451B93) whose second piece
(0x451B93: pop eax; push edi; push 0x64; push 0x36; jmp eax) puts the three pushes back and returns.  Each polish
then pays the game's +1 when that step is reached, capped by the game's own adder.

Everything below RUNS the stock and the patcher's rendered bytes in unicorn, in all three population modes.
"""
from __future__ import annotations

import functools
import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vv_fun_patcher import load_builds, render_patched_bytes  # noqa: E402

try:
    import capstone
    import pefile
    from unicorn import UC_ARCH_X86, UC_HOOK_CODE, UC_MODE_32, Uc
    from unicorn.x86_const import UC_X86_REG_EAX, UC_X86_REG_ECX, UC_X86_REG_EIP, UC_X86_REG_ESP
except ImportError:  # pragma: no cover
    pefile = None

FEATURE_ID = "vv5_fix_vanilla_bugs"
STOCK = ROOT / "research" / "stock-executables" / "Virtual Villagers - New Believers.exe"
MODES = ("stock", "collection_progression", "immediate_fixed")
BASE, STK, RETURN, HEAP = 0x400000, 0x20000000, 0x0BAD0000, 0x30000000

# (file offset, stock bytes, patched bytes) -- the rows the feature adds, in order.
FIXES = (
    (0x55109, bytes.fromhex("576A646A36"), bytes.fromhex("E865CAFFFF")),
    (0x51B73, bytes.fromhex("CC" * 11), bytes.fromhex("6A2889F1E874330200EB15")),
    (0x51B93, bytes.fromhex("CC" * 8), bytes.fromhex("58576A646A36FFE0")),
)
POLISH = 0x455020                 # action 0x9D "Polishing the statue" (registered at 0x464696)
WORK_EVENT_STEP, PRACTICE_STEP = 0x474EF0, 0x474780
CAVE = 0x451B73                   # the fix's first piece
DISPATCH, ADD_ENERGY, MANAGER = 0x46CE60, 0x424F80, 0x425950
ENERGY, CAP = 0x17D64, 0x17D60


def _have() -> bool:
    return pefile is not None and STOCK.is_file()


@functools.lru_cache(maxsize=None)
def _render(mode: str) -> bytes:
    build = next(b for b in load_builds() if b.id == "vv5")
    data, _ = render_patched_bytes(STOCK, build, mode, [FEATURE_ID])
    return bytes(data)


def _ret_imm(image: bytes, va: int) -> int:
    """The stack bytes a function pops: its first ret's immediate."""
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    for ins in md.disasm(image[va - BASE:va - BASE + 0x400], va):
        if ins.mnemonic == "ret":
            return int(ins.op_str, 16) if ins.op_str else 0
    raise AssertionError(f"no ret in {va:#x}")


class _Machine:
    def __init__(self, data: bytes) -> None:
        pe = pefile.PE(data=data)
        self.image = image = pe.get_memory_mapped_image()
        self.mu = mu = Uc(UC_ARCH_X86, UC_MODE_32)
        mu.mem_map(BASE, (max(len(image), pe.OPTIONAL_HEADER.SizeOfImage) + 0xFFFF) & ~0xFFFF)
        mu.mem_write(BASE, image)
        mu.mem_map(STK, 0x100000)
        mu.mem_map(RETURN, 0x1000)
        mu.mem_map(HEAP, 0x100000)

    def esp(self) -> int:
        return self.mu.reg_read(UC_X86_REG_ESP)

    def u32(self, address: int) -> int:
        return struct.unpack("<I", self.mu.mem_read(address, 4))[0]

    def call(self, address: int, args: list[int], ecx: int = 0) -> None:
        sp = STK + 0x80000
        for value in reversed(args):
            sp -= 4
            self.mu.mem_write(sp, struct.pack("<I", value))
        sp -= 4
        self.mu.mem_write(sp, struct.pack("<I", RETURN))
        self.mu.reg_write(UC_X86_REG_ESP, sp)
        self.mu.reg_write(UC_X86_REG_ECX, ecx)
        self.mu.emu_start(address, RETURN, count=200_000)

    def stub(self, address: int, value: int = 0) -> None:
        """Return at once from `address`, popping what the function pops, with eax = value."""
        pops = _ret_imm(self.image, address)

        def hook(uc, _address, _size, _user):
            sp = uc.reg_read(UC_X86_REG_ESP)
            ret = struct.unpack("<I", uc.mem_read(sp, 4))[0]
            uc.reg_write(UC_X86_REG_ESP, sp + 4 + pops)
            uc.reg_write(UC_X86_REG_EAX, value)
            uc.reg_write(UC_X86_REG_EIP, ret)
        self.mu.hook_add(UC_HOOK_CODE, hook, begin=address, end=address)


def _polish_steps(data: bytes) -> list[tuple[int, int]]:
    """Run "Polishing the statue" with every call it makes stubbed; the steps it queues, in order."""
    m = _Machine(data)
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    seen: list[tuple[int, int]] = []
    targets = set()
    for ins in md.disasm(m.image[POLISH - BASE:0x455225 - BASE], POLISH):
        if ins.mnemonic == "call" and ins.op_str.startswith("0x"):
            targets.add(int(ins.op_str, 16))
    for target in targets:
        if target in (WORK_EVENT_STEP, PRACTICE_STEP, CAVE):
            continue                              # the fix's own piece runs for real
        m.stub(target, HEAP + 0x1000)             # string lookups get a buffer; rand gets a value to add to

    def record(target):
        pops = _ret_imm(m.image, target)

        def hook(uc, _address, _size, _user):
            sp = uc.reg_read(UC_X86_REG_ESP)
            ret, arg = struct.unpack("<II", uc.mem_read(sp, 8))
            seen.append((target, arg))
            uc.reg_write(UC_X86_REG_ESP, sp + 4 + pops)
            uc.reg_write(UC_X86_REG_EAX, 0x5A5A5A5A)    # a step maker's answer the action must not need
            uc.reg_write(UC_X86_REG_EIP, ret)
        m.mu.hook_add(UC_HOOK_CODE, hook, begin=target, end=target)
    record(WORK_EVENT_STEP)
    record(PRACTICE_STEP)
    villager = HEAP + 0x2000
    m.call(POLISH, [villager])
    return seen


@unittest.skipUnless(_have(), "stock executables are not available")
class PolishingPaysTheEnergy(unittest.TestCase):
    def test_the_row_carries_the_fix(self) -> None:
        import json
        feature = next(f for f in json.loads((ROOT / "data" / "builds.json").read_text(encoding="utf-8"))["fun_patches"]
                       if f["id"] == FEATURE_ID)
        rows = [(int(p["offset"], 16), bytes.fromhex(p["before"]), bytes.fromhex(p["after"]))
                for p in feature["patches"]]
        # The Nursery foundation caption's row (tests/test_vv5_nursery_foundation_caption.py), then the Clothing Hut
        # click's (tests/test_vv5_clothing_hut_click.py), then the duplicate-pickup fix's
        # (tests/test_duplicate_pickups.py), come after this fix.
        from test_duplicate_pickups import dupe_pickup_fixes
        from test_vv5_clothing_hut_click import clothing_hut_click_fixes
        from test_vv5_nursery_foundation_caption import foundation_caption_fixes
        dupe = list(dupe_pickup_fixes("vv5"))
        self.assertEqual(rows[-len(dupe):], dupe)
        rows = rows[:-len(dupe)]
        click = list(clothing_hut_click_fixes())
        self.assertEqual(rows[-len(click):], click)
        rows = rows[:-len(click)]
        caption = list(foundation_caption_fixes())
        self.assertEqual(rows[-len(caption):], caption)
        rows = rows[:-len(caption)]
        self.assertEqual(rows[-len(FIXES):], list(FIXES))
        self.assertIn("Polishing the statue", feature["description"])

    def test_the_bytes_are_stock_where_the_row_writes(self) -> None:
        stock = STOCK.read_bytes()
        for offset, before, _after in FIXES:
            self.assertEqual(stock[offset:offset + len(before)], before)
        for offset in (0x51B73, 0x51B93):         # an int3 left on each side of each piece
            n = next(len(b) for o, b, _a in FIXES if o == offset)
            self.assertEqual(stock[offset - 1], 0xCC)
            self.assertEqual(stock[offset + n], 0xCC)

    def test_stock_polishing_queues_no_energy(self) -> None:
        steps = _polish_steps(STOCK.read_bytes())
        self.assertIn((PRACTICE_STEP, 4), steps)                    # Building practice
        self.assertNotIn(WORK_EVENT_STEP, [t for t, _a in steps])

    def test_patched_polishing_queues_event_40_after_the_practice(self) -> None:
        for mode in MODES:
            with self.subTest(mode=mode):
                data = _render(mode)
                for offset, _before, after in FIXES:
                    self.assertEqual(data[offset:offset + len(after)], after)
                steps = _polish_steps(data)
                self.assertEqual([s for s in steps if s[0] == WORK_EVENT_STEP], [(WORK_EVENT_STEP, 40)])
                practice = steps.index((PRACTICE_STEP, 4))
                self.assertEqual(steps[practice + 1], (WORK_EVENT_STEP, 40))
                stock_steps = _polish_steps(STOCK.read_bytes())
                self.assertEqual([s for s in steps if s[0] != WORK_EVENT_STEP], stock_steps)  # nothing else changes

    def test_event_40_adds_one_divine_energy_up_to_the_cap(self) -> None:
        for energy, cap, expect in ((10, 100, 11), (100, 100, 100), (0, 50, 1)):
            with self.subTest(energy=energy, cap=cap):
                m = _Machine(_render("stock"))
                manager = HEAP + 0x40000
                m.mu.mem_write(manager + CAP, struct.pack("<ii", cap, energy))
                m.stub(MANAGER, manager)
                m.stub(0x450530, HEAP + 0x1000)
                m.stub(0x4500D0, 0)
                villager = HEAP + 0x10000
                m.call(DISPATCH, [40], ecx=villager)
                self.assertEqual(struct.unpack("<i", m.mu.mem_read(manager + ENERGY, 4))[0], expect)


if __name__ == "__main__":
    unittest.main()
