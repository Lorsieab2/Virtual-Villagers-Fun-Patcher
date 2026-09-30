"""VV3 Pointing Out a Rare Collectible: retries never write outside the tracker.

The shipped retry jumped from the end of the stock placement routine 0x42DB30
straight back to its loop head, after the routine had already repurposed the
registers that loop head relies on (EDI advanced to the slot, ESI holding the
collectible id, EBP holding the category's y-origin). Every reroll then wrote
the collectible's fields at this + id*0x1C -- past the two-slot record, into
the neighbouring globals -- and nothing bounded the loop.

The fix leaves the stock routine untouched and wraps its only call site
(0x46217F) in a bounded retry: call the stock routine, stop once it has placed
a collectible (tracker slot flag set), otherwise call it again, at most 20
times.

This test executes the wrapper and the real stock routine in a real render,
stubbing only the helpers the routine calls (the CRT rand wrapper, the terrain
placement check, the "a villager is already after it" check and the timer),
and records every memory write.
"""
from __future__ import annotations

import struct
import sys
import unittest
from pathlib import Path

import pefile
from unicorn import UC_ARCH_X86, UC_HOOK_CODE, UC_HOOK_MEM_WRITE, UC_MODE_32, Uc
from unicorn.x86_const import (
    UC_X86_REG_EAX,
    UC_X86_REG_EBP,
    UC_X86_REG_EBX,
    UC_X86_REG_ECX,
    UC_X86_REG_EIP,
    UC_X86_REG_ESI,
    UC_X86_REG_ESP,
)

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import vv_fun_patcher as vfp  # noqa: E402

STOCK_VV3 = ROOT / "research" / "stock-executables" / "Virtual Villagers - The Secret City.exe"
FEATURE = "vv3_rare_collectible_retry"

TRACKER = 0x58F428          # the collections tracker the caller passes in ECX
RECORD = (TRACKER + 4, TRACKER + 0x3C)  # both 0x1C-byte slots
CALL_SITE = 0x46217F
RESUME = 0x462184            # the caller's epilogue after the call
ROUTINE = 0x42DB30

RAND = 0x4032D0              # cdecl rand(n)
PLACEABLE = 0x4206F0         # thiscall (x, y), ret 8
TARGETED = 0x42D820          # thiscall (id), ret 4: a villager is already after it
GATE_A, GATE_B = 0x4358D0, 0x4358F0  # thiscall (6), ret 4
CLOCK_OWNER, CLOCK = 0x428B60, 0x403330

CATEGORY_BASE = 0x20         # ordinary category: ids 0x28..0x2B
SPECIAL_BASE = 0x44          # ids 0x4C..0x4F fall in the special 0x4C..0x57 range


def _load(image: bytes) -> Uc:
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
    return uc


def _run(image: bytes, *, category_base: int, rejections: int, collected: bool = False):
    """Run the call at 0x46217F once. The first `rejections` picks are refused."""
    uc = _load(image)
    # One category, a 100x100 rectangle at (500, 600), the given id base.
    uc.mem_write(TRACKER + 0xDC, struct.pack("<I", 1))
    uc.mem_write(TRACKER + 0x3C, struct.pack("<4I", 500, 600, 600, 700))
    uc.mem_write(TRACKER + 0x4C, struct.pack("<I", category_base))
    if collected:
        for cid in range(0x4C, 0x58):
            uc.mem_write(TRACKER + cid * 4 + 0x10, struct.pack("<I", 1))
    stack = 0x30000000
    uc.mem_map(stack, 0x20000)
    esp = stack + 0x10000
    sentinels = {"ebx": 0x11111111, "esi": 0x22222222, "ebp": 0x33333333}
    uc.reg_write(UC_X86_REG_EBX, sentinels["ebx"])
    uc.reg_write(UC_X86_REG_ESI, sentinels["esi"])
    uc.reg_write(UC_X86_REG_EBP, sentinels["ebp"])
    uc.reg_write(UC_X86_REG_ECX, TRACKER)
    uc.reg_write(UC_X86_REG_ESP, esp)

    state = {"routine_calls": 0, "picks": 0, "bad_writes": []}

    def ret(value: int, pop: int) -> None:
        sp = uc.reg_read(UC_X86_REG_ESP)
        (back,) = struct.unpack("<I", uc.mem_read(sp, 4))
        uc.reg_write(UC_X86_REG_EAX, value)
        uc.reg_write(UC_X86_REG_ESP, sp + 4 + pop)
        uc.reg_write(UC_X86_REG_EIP, back)

    def on_code(uc, address, _size, _data):
        if address == ROUTINE:
            state["routine_calls"] += 1
            if state["routine_calls"] > 100:
                uc.emu_stop()
        elif address == RAND:
            ret(0, 0)
        elif address == PLACEABLE:
            ret(1, 8)
        elif address == TARGETED:
            state["picks"] += 1
            ret(1 if state["picks"] <= rejections else 0, 4)
        elif address in (GATE_A, GATE_B):
            ret(1, 4)
        elif address == CLOCK_OWNER:
            ret(0x12345678, 0)
        elif address == CLOCK:
            ret(1000, 0)

    def on_write(uc, _access, address, size, _value, _data):
        end = address + size
        on_stack = stack <= address < stack + 0x20000
        in_record = RECORD[0] <= address and end <= RECORD[1]
        if not (on_stack or in_record):
            state["bad_writes"].append(address)

    uc.hook_add(UC_HOOK_CODE, on_code)
    uc.hook_add(UC_HOOK_MEM_WRITE, on_write)
    # Enter at the patched call instruction with the caller's return pushed by it.
    uc.emu_start(CALL_SITE, RESUME, count=200000)
    eip = uc.reg_read(UC_X86_REG_EIP)
    flag = uc.mem_read(TRACKER + 4, 1)[0]
    (placed_id,) = struct.unpack("<I", uc.mem_read(TRACKER + 8, 4))
    return {
        "reached_caller": eip == RESUME,
        "esp_balanced": uc.reg_read(UC_X86_REG_ESP) == esp,
        "callee_saved": {
            "ebx": uc.reg_read(UC_X86_REG_EBX) == sentinels["ebx"],
            "esi": uc.reg_read(UC_X86_REG_ESI) == sentinels["esi"],
            "ebp": uc.reg_read(UC_X86_REG_EBP) == sentinels["ebp"],
        },
        "placed": flag == 1,
        "placed_id": placed_id,
        **state,
    }


@unittest.skipUnless(STOCK_VV3.is_file(), "stock VV3 executable not present")
class RareCollectibleRetryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.stock = STOCK_VV3.read_bytes()
        build = next(b for b in vfp.load_builds() if b.id == "vv3")
        cls.rendered = {}
        for mode in ("stock", "collection_progression", "immediate_fixed"):
            image, _ = vfp.render_patched_bytes(STOCK_VV3, build, mode, [FEATURE])
            cls.rendered[mode] = bytes(image)

    def _each_mode(self):
        for mode, image in self.rendered.items():
            with self.subTest(mode=mode):
                yield image

    def assertClean(self, result):
        self.assertTrue(result["reached_caller"], "returns to the caller's epilogue")
        self.assertTrue(result["esp_balanced"])
        self.assertEqual(result["bad_writes"], [], "no write outside the tracker slots")

    def test_the_stock_routine_is_untouched(self):
        for image in self._each_mode():
            self.assertEqual(image[0x2DB30:0x2DC90], self.stock[0x2DB30:0x2DC90])

    def test_the_stock_game_gives_up_after_one_rejection(self):
        # Guards the harness: stock places nothing when its pick is refused.
        result = _run(self.stock, category_base=CATEGORY_BASE, rejections=1)
        self.assertClean(result)
        self.assertEqual(result["routine_calls"], 1)
        self.assertFalse(result["placed"])

    def test_an_eligible_first_pick_is_placed_once(self):
        for image in self._each_mode():
            result = _run(image, category_base=CATEGORY_BASE, rejections=0)
            self.assertClean(result)
            self.assertEqual(result["routine_calls"], 1)
            self.assertTrue(result["placed"])
            self.assertEqual(result["placed_id"], CATEGORY_BASE + 8)

    def test_a_targeted_pick_is_rerolled_without_corruption(self):
        for image in self._each_mode():
            result = _run(image, category_base=CATEGORY_BASE, rejections=3)
            self.assertClean(result)
            self.assertEqual(result["routine_calls"], 4)
            self.assertTrue(result["placed"])
            self.assertEqual(result["placed_id"], CATEGORY_BASE + 8)

    def test_an_already_collected_special_pick_is_bounded(self):
        # Every special id is collected, so every pick is refused: the retry
        # must stop after 20 attempts, place nothing and corrupt nothing.
        for image in self._each_mode():
            result = _run(image, category_base=SPECIAL_BASE, rejections=0, collected=True)
            self.assertClean(result)
            self.assertEqual(result["routine_calls"], 20)
            self.assertFalse(result["placed"])

    def test_the_callers_registers_survive(self):
        # EDI is used as the counter; the caller's epilogue restores it. The
        # other callee-saved registers must come back untouched.
        for image in self._each_mode():
            result = _run(image, category_base=CATEGORY_BASE, rejections=5)
            self.assertEqual(result["callee_saved"], {"ebx": True, "esi": True, "ebp": True})


if __name__ == "__main__":
    unittest.main()
