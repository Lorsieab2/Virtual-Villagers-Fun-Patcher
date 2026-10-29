from __future__ import annotations

import hashlib
import importlib.util
import struct
import sys
import unittest
from pathlib import Path

from capstone import CS_ARCH_X86, CS_MODE_32, Cs

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

SPEC = importlib.util.spec_from_file_location(
    "vv5_clickable_tips", ROOT / "scripts/build_vv5_clickable_tips.py"
)
assert SPEC and SPEC.loader
tips = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(tips)


class HandlerWiringTest(unittest.TestCase):
    def setUp(self) -> None:
        self.code = tips._handler_bytes()
        self.md = Cs(CS_ARCH_X86, CS_MODE_32)
        self.ins = list(self.md.disasm(self.code, tips.CODE_VA))

    def test_calls_native_bar_setter_and_play_sound(self) -> None:
        calls = [int(i.op_str, 16) for i in self.ins if i.mnemonic == "call"]
        self.assertIn(tips.BAR_SETTEXT, calls)  # Bar::SetText -> tip + timer
        self.assertIn(tips.SND_PLAY, calls)     # SoundMgr::PlaySound

    def test_plays_hou_ogg_id(self) -> None:
        # hou.ogg is play id 0x61 (naive manifest id minus one)
        self.assertEqual(tips.SND_ID, 0x61)
        pushes = [i.op_str for i in self.ins if i.mnemonic == "push"]
        self.assertIn(hex(tips.SND_ID), pushes)

    def test_random_tip_id_range(self) -> None:
        # 50 eRandomTip strings at contiguous ids 0x461..0x492
        self.assertEqual(tips.TIP_COUNT, 50)
        self.assertEqual(tips.TIP_ID_BASE, 0x461)
        self.assertEqual(tips.TIP_ID_BASE + tips.TIP_COUNT - 1, 0x492)

    def test_selects_tip_at_random_via_rdtsc(self) -> None:
        # the tip index comes from rdtsc (CPU timestamp) folded by the tip count,
        # so each click is random rather than a predictable running counter
        self.assertTrue(any(i.mnemonic == "rdtsc" for i in self.ins))
        self.assertTrue(any(i.mnemonic == "div" for i in self.ins))
        # no writable-scratch counter is used anymore
        self.assertFalse(hasattr(tips, "COUNTER_VA"))

    def test_tail_returns_to_hook_plus_five(self) -> None:
        jmps = [int(i.op_str, 16) for i in self.ins if i.mnemonic == "jmp"]
        self.assertIn(tips.HOOK_VA + 5, jmps)


STOCK = ROOT / "research/stock-executables/Virtual Villagers - New Believers.exe"
BUILDS = ROOT / "data/builds.json"

# The stock event pump's left-button-down case (SDL_MOUSEBUTTONDOWN, 0x401): it asks
# SDL_GetMouseState (thunk 0x47B996) for the pointer, then queues event 2 with the
# two values for the screen's own handler (0x402200 / 0x4022D0).
CASE_DOWN = 0x404A36
QUEUE_CALL = 0x404A8B
GET_MOUSE_STATE = 0x47B996
STACK = 0x00200000
EVENT_SP = STACK + 0x8000     # esp inside the pump; the SDL_Event sits at esp+0x24
HALT = 0x0F000000


def _patched_image(stock: bytes) -> bytes:
    """The stock exe with the manifest's guarded edits applied, as the patcher does."""
    import json
    raw = bytearray(stock)
    build = next(b for b in json.loads(BUILDS.read_text(encoding="utf-8"))["fun_patches"]
                 if b["id"] == "vv5_clickable_tips")
    for edit in build["patches"]:
        off = int(edit["offset"], 16)
        before, after = bytes.fromhex(edit["before"]), bytes.fromhex(edit["after"])
        assert raw[off:off + len(before)] == before, edit["purpose"]
        raw[off:off + len(after)] = after
    return bytes(raw)


def _click(exe: bytes, x: int, y: int) -> dict:
    """Run the pump's button-down case from 0x404A36 to the queue call at 0x404A8B
    with the pointer at (x, y); only SDL and the bar / sound leaves are answered."""
    import pefile
    from unicorn import UC_ARCH_X86, UC_HOOK_CODE, UC_MODE_32, Uc
    from unicorn.x86_const import (UC_X86_REG_EAX, UC_X86_REG_EBX, UC_X86_REG_ECX,
                                   UC_X86_REG_EIP, UC_X86_REG_ESP)

    pe = pefile.PE(data=exe, fast_load=True)
    image = pe.get_memory_mapped_image()
    mu = Uc(UC_ARCH_X86, UC_MODE_32)
    size = (len(image) + 0xFFF) & ~0xFFF
    mu.mem_map(0x400000, size)
    mu.mem_write(0x400000, image)
    mu.mem_map(STACK, 0x10000)
    mu.mem_map(HALT, 0x1000)
    mu.mem_write(EVENT_SP + 0x24, struct.pack("<I", 0x401))   # SDL_MOUSEBUTTONDOWN
    mu.mem_write(EVENT_SP + 0x34, b"\x01")                    # button: SDL_BUTTON_LEFT
    seen: dict = {"tips": [], "sounds": []}

    def ret(n_args: int, eax: int = 0) -> None:
        sp = mu.reg_read(UC_X86_REG_ESP)
        back = struct.unpack("<I", mu.mem_read(sp, 4))[0]
        mu.reg_write(UC_X86_REG_EAX, eax)
        mu.reg_write(UC_X86_REG_ESP, sp + 4 + 4 * n_args)
        mu.reg_write(UC_X86_REG_EIP, back)

    def args(n: int) -> tuple:
        sp = mu.reg_read(UC_X86_REG_ESP)
        return struct.unpack(f"<{n}i", mu.mem_read(sp + 4, 4 * n))

    def hook(uc, address, _size, _data) -> None:
        if address == GET_MOUSE_STATE:            # SDL_GetMouseState(int *x, int *y), cdecl
            px, py = args(2)
            uc.mem_write(px & 0xFFFFFFFF, struct.pack("<i", x))
            uc.mem_write(py & 0xFFFFFFFF, struct.pack("<i", y))
            sp = uc.reg_read(UC_X86_REG_ESP)
            back = struct.unpack("<I", uc.mem_read(sp, 4))[0]
            uc.reg_write(UC_X86_REG_EAX, 1)
            uc.reg_write(UC_X86_REG_ESP, sp + 4)
            uc.reg_write(UC_X86_REG_EIP, back)
        elif address == tips.BAR_SETTEXT:         # Bar::SetText(id, param); ret 8
            seen["tips"].append((uc.reg_read(UC_X86_REG_ECX), *args(2)))
            ret(2)
        elif address == tips.SND_PLAY:            # SoundMgr::PlaySound(id); ret 4
            seen["sounds"].append((uc.reg_read(UC_X86_REG_ECX), *args(1)))
            ret(1)
        elif address == QUEUE_CALL:
            # the three values just pushed for the queue: event 2, then the pair
            seen["event"] = struct.unpack("<3i", uc.mem_read(uc.reg_read(UC_X86_REG_ESP), 12))
            uc.emu_stop()

    mu.hook_add(UC_HOOK_CODE, hook)
    mu.reg_write(UC_X86_REG_ESP, EVENT_SP)
    mu.reg_write(UC_X86_REG_EBX, 0)
    mu.emu_start(CASE_DOWN, HALT, count=500)
    return seen


@unittest.skipUnless(STOCK.exists(), "stock New Believers exe not present")
class ClickSpotEmulationTest(unittest.TestCase):
    """The spot is the curled vine under the Puzzles button (stock button 7, image
    btn_puzzle.png, placed at x 105, y 690 by 0x4449EB..0x444A05): across 164-194,
    down 729-757.  At the hook ecx holds y and edx holds x (0x404A54 / 0x404A58
    read SDL_GetMouseState's y and x), so the handler's tests are on that spot."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.stock = STOCK.read_bytes()
        cls.patched = _patched_image(cls.stock)

    def test_manifest_matches_the_generator(self) -> None:
        built = tips.build(self.stock)
        for off in (0x4A5C, 0x94890):
            self.assertEqual(built[off:off + 0x70], self.patched[off:off + 0x70])

    def test_stock_queues_x_then_y(self) -> None:
        seen = _click(self.stock, 179, 740)
        self.assertEqual(seen["event"], (2, 179, 740))
        self.assertEqual(seen["tips"], [])

    def test_click_under_puzzles_shows_a_tip(self) -> None:
        for x, y in ((tips.VINE_X_LO, tips.VINE_Y_LO), (179, 740), (tips.VINE_X_HI, tips.VINE_Y_HI)):
            with self.subTest(x=x, y=y):
                self.assertEqual((tips.VINE_X_LO, tips.VINE_X_HI, tips.VINE_Y_LO, tips.VINE_Y_HI),
                                 (164, 194, 729, 757))
                seen = _click(self.patched, x, y)
                self.assertEqual(len(seen["tips"]), 1)
                bar, tip_id, param = seen["tips"][0]
                self.assertEqual(bar, tips.BAR_THIS)
                self.assertTrue(tips.TIP_ID_BASE <= tip_id < tips.TIP_ID_BASE + tips.TIP_COUNT)
                self.assertEqual(param, -1)
                self.assertEqual(seen["sounds"], [(tips.SND_MGR, tips.SND_ID)])
                self.assertEqual(seen["event"], (2, x, y))   # the game still gets the click

    def test_swapped_reading_and_edges_show_nothing(self) -> None:
        for x, y in ((740, 179), (757, 164), (729, 194),
                     (tips.VINE_X_LO - 1, 740), (tips.VINE_X_HI + 1, 740),
                     (179, tips.VINE_Y_LO - 1), (179, tips.VINE_Y_HI + 1)):
            with self.subTest(x=x, y=y):
                seen = _click(self.patched, x, y)
                self.assertEqual(seen["tips"], [])
                self.assertEqual(seen["sounds"], [])
                self.assertEqual(seen["event"], (2, x, y))


class ReproducibilityTest(unittest.TestCase):
    def test_known_parent_yields_known_result(self) -> None:
        if not tips.DEFAULT_INPUT.exists():
            self.skipTest("certified parent exe not present in this checkout")
        parent = tips.DEFAULT_INPUT.read_bytes()
        if hashlib.sha256(parent).hexdigest().upper() != tips.KNOWN_PARENT_SHA256:
            self.skipTest("input is not the certified known-good parent")
        result = tips.build(parent)
        self.assertEqual(
            hashlib.sha256(result).hexdigest().upper(), tips.KNOWN_RESULT_SHA256
        )
        self.assertEqual(result[:2], b"MZ")


if __name__ == "__main__":
    unittest.main()
