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

    def test_replays_the_two_loads_and_returns_after_them(self) -> None:
        # the cave starts with the hooked loads (y, then x) and ends back at 0x4463B5
        self.assertEqual(self.code[:8], tips.HOOK_PREIMAGE)
        jmps = [int(i.op_str, 16) for i in self.ins if i.mnemonic == "jmp"]
        self.assertEqual(jmps, [tips.HOOK_RETURN])
        self.assertEqual(tips.HOOK_RETURN, tips.HOOK_VA + len(tips.HOOK_PREIMAGE))


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


# The game's event queue: [0x4DACCC] is the queue object S, [S] its body Q; Q+0 the
# listener list (nodes: +0 object, +4 flags (bit 0: mouse), +8 stop byte, +0xC next),
# Q+4 the object holding the mouse (none here), Q+8 the button-held byte.  0x4022D0
# (this = S) posts an event to 0x402160, which calls each mouse listener's slot 1
# (type, x, y) front to back until one takes it (returns true).
QUEUE_GLOBAL = 0x4DACCC
QUEUE_POST = 0x4022D0
MAIN_SCENE_VTABLE = 0x49A2F4      # theMainScene (constructor 0x444630); slot 1 = 0x446370
VILLAGE_MOUSE_DOWN = 0x445A60     # the village's own mouse-down, answered here
HEAP = 0x00300000
OTHER_SLOT = HEAP + 0xF00         # slot 1 of a stand-in for another screen or a pop-up


class _Game:
    """The exe mapped at 0x400000; only leaves are answered: SDL_GetMouseState, the
    bar, the sound, the village's mouse-down and a stand-in screen's slot 1."""

    def __init__(self, exe: bytes) -> None:
        import pefile
        from unicorn import UC_ARCH_X86, UC_HOOK_CODE, UC_MODE_32, Uc

        image = pefile.PE(data=exe, fast_load=True).get_memory_mapped_image()
        self.mu = mu = Uc(UC_ARCH_X86, UC_MODE_32)
        mu.mem_map(0x400000, (len(image) + 0xFFF) & ~0xFFF)
        mu.mem_write(0x400000, image)
        mu.mem_map(STACK, 0x10000)
        mu.mem_map(HEAP, 0x10000)
        mu.mem_map(HALT, 0x1000)
        self.pointer = (0, 0)
        self.other_takes = True
        self.seen: dict = {}
        mu.hook_add(UC_HOOK_CODE, self._hook)

    # -- registers and stack ------------------------------------------------
    def _reg(self, name: str, value: int | None = None) -> int:
        from unicorn import x86_const
        reg = getattr(x86_const, f"UC_X86_REG_{name}")
        if value is None:
            return self.mu.reg_read(reg)
        self.mu.reg_write(reg, value & 0xFFFFFFFF)
        return value

    def _args(self, n: int) -> tuple:
        return struct.unpack(f"<{n}i", self.mu.mem_read(self._reg("ESP") + 4, 4 * n))

    def _ret(self, pop: int, eax: int) -> None:
        sp = self._reg("ESP")
        back = struct.unpack("<I", self.mu.mem_read(sp, 4))[0]
        self._reg("EAX", eax)
        self._reg("ESP", sp + 4 + pop)
        self._reg("EIP", back)

    def _hook(self, uc, address, _size, _data) -> None:
        seen = self.seen
        if address == GET_MOUSE_STATE:            # SDL_GetMouseState(int *x, int *y), cdecl
            px, py = self._args(2)
            uc.mem_write(px & 0xFFFFFFFF, struct.pack("<i", self.pointer[0]))
            uc.mem_write(py & 0xFFFFFFFF, struct.pack("<i", self.pointer[1]))
            self._ret(0, 1)
        elif address == tips.BAR_SETTEXT:         # Bar::SetText(id, param); ret 8
            seen["tips"].append((self._reg("ECX"), *self._args(2)))
            self._ret(8, 0)
        elif address == tips.SND_PLAY:            # SoundMgr::PlaySound(id); ret 4
            seen["sounds"].append((self._reg("ECX"), *self._args(1)))
            self._ret(4, 0)
        elif address == VILLAGE_MOUSE_DOWN:       # thiscall (x, y); ret 8
            seen["village"].append(self._args(2))
            self._ret(8, 1)
        elif address == OTHER_SLOT:               # thiscall (type, x, y); ret 0xC
            seen["other"].append(self._args(3))
            self._ret(12, 1 if self.other_takes else 0)
        elif address == QUEUE_CALL:
            # the three values just pushed for the queue: event 2, then the pair
            seen["event"] = struct.unpack("<3i", uc.mem_read(self._reg("ESP"), 12))
            uc.emu_stop()

    def _fresh(self) -> dict:
        self.seen = {"tips": [], "sounds": [], "village": [], "other": []}
        return self.seen

    # -- the two runs ---------------------------------------------------------
    def pump_click(self, x: int, y: int) -> dict:
        """The global event loop's button-down case, 0x404A36 to the queue call 0x404A8B."""
        seen = self._fresh()
        self.pointer = (x, y)
        self.mu.mem_write(EVENT_SP + 0x24, struct.pack("<I", 0x401))   # SDL_MOUSEBUTTONDOWN
        self.mu.mem_write(EVENT_SP + 0x34, b"\x01")                    # SDL_BUTTON_LEFT
        self._reg("ESP", EVENT_SP)
        self._reg("EBX", 0)
        self.mu.emu_start(CASE_DOWN, HALT, count=500)
        return seen

    def post_click(self, listeners: list[str], x: int, y: int) -> dict:
        """Post event 2 (x, y) through the game's own queue (0x4022D0 -> 0x402160) with
        the listener list front to back: "village" is a theMainScene object (its real
        vtable 0x49A2F4), "other" a stand-in screen or pop-up."""
        seen = self._fresh()
        mu = self.mu
        mu.mem_write(HEAP, b"\0" * 0x1000)
        s, q, village, other, vtable = HEAP, HEAP + 0x10, HEAP + 0x100, HEAP + 0x200, HEAP + 0x300
        mu.mem_write(s, struct.pack("<I", q))
        mu.mem_write(QUEUE_GLOBAL, struct.pack("<I", s))
        mu.mem_write(village, struct.pack("<I", MAIN_SCENE_VTABLE))
        mu.mem_write(vtable, struct.pack("<II", 0, OTHER_SLOT))
        mu.mem_write(other, struct.pack("<I", vtable))
        objects = {"village": village, "other": other}
        head = 0
        for i, name in reversed(list(enumerate(listeners))):
            node = HEAP + 0x400 + 0x10 * i
            mu.mem_write(node, struct.pack("<IIII", objects[name], 0xF, 0, head))
            head = node
        mu.mem_write(q, struct.pack("<IIB", head, 0, 0))
        sp = STACK + 0x8000
        for value in (HALT, 2, x, y)[::-1]:
            sp -= 4
            mu.mem_write(sp, struct.pack("<I", value & 0xFFFFFFFF))
        sp_frame = sp
        self._reg("ESP", sp_frame)
        self._reg("ECX", s)
        mu.emu_start(QUEUE_POST, HALT, count=2000)
        return seen


@unittest.skipUnless(STOCK.exists(), "stock New Believers exe not present")
class ClickSpotEmulationTest(unittest.TestCase):
    """The spot is the curled vine under the Puzzles button (stock button 7, image
    btn_puzzle.png, placed at x 105, y 690 by 0x4449EB..0x444A05): across 164-194,
    down 729-757.  The event loop queues (2, x, y) from SDL_GetMouseState(&x, &y)
    (0x404A4F..0x404A61); the village scene's slot hands x and y to its mouse-down
    (0x4463AD..0x4463B7), where the patch looks at them."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.stock = STOCK.read_bytes()
        cls.patched = _patched_image(cls.stock)

    def test_manifest_matches_the_generator(self) -> None:
        built = tips.build(self.stock)
        for off in (0x463AD, 0x94890):
            self.assertEqual(built[off:off + 0x60], self.patched[off:off + 0x60])
        self.assertEqual(self.patched[0x4A5C:0x4A61], self.stock[0x4A5C:0x4A61])  # event loop untouched

    def test_hook_runs_only_for_the_village_scene(self) -> None:
        # the hooked slot 0x446370 is named by theMainScene's vtable (0x49A2F8) and nothing else
        import pefile
        image = pefile.PE(data=self.stock, fast_load=True).get_memory_mapped_image()
        needle = struct.pack("<I", 0x446370)
        found, at = [], image.find(needle)
        while at != -1:
            found.append(0x400000 + at)
            at = image.find(needle, at + 1)
        self.assertEqual(found, [MAIN_SCENE_VTABLE + 4])

    def test_stock_queues_x_then_y(self) -> None:
        seen = _Game(self.stock).pump_click(179, 740)
        self.assertEqual(seen["event"], (2, 179, 740))
        self.assertEqual(seen["tips"], [])

    def test_click_under_puzzles_on_the_village_shows_a_tip(self) -> None:
        self.assertEqual((tips.VINE_X_LO, tips.VINE_X_HI, tips.VINE_Y_LO, tips.VINE_Y_HI), (164, 194, 729, 757))
        game = _Game(self.patched)
        for x, y in ((164, 729), (179, 740), (194, 757)):
            with self.subTest(x=x, y=y):
                seen = game.post_click(["village"], x, y)
                self.assertEqual(len(seen["tips"]), 1)
                bar, tip_id, param = seen["tips"][0]
                self.assertEqual(bar, tips.BAR_THIS)
                self.assertTrue(tips.TIP_ID_BASE <= tip_id < tips.TIP_ID_BASE + tips.TIP_COUNT)
                self.assertEqual(param, -1)
                self.assertEqual(seen["sounds"], [(tips.SND_MGR, tips.SND_ID)])
                self.assertEqual(seen["village"], [(x, y)])   # the village still gets the click

    def test_swapped_reading_and_edges_show_nothing(self) -> None:
        game = _Game(self.patched)
        for x, y in ((740, 179), (757, 164), (729, 194), (163, 740), (195, 740), (179, 728), (179, 758)):
            with self.subTest(x=x, y=y):
                seen = game.post_click(["village"], x, y)
                self.assertEqual((seen["tips"], seen["sounds"]), ([], []))
                self.assertEqual(seen["village"], [(x, y)])

    def test_other_screens_never_show_a_tip(self) -> None:
        game = _Game(self.patched)
        # another screen shown (Menu, Tech, Map, ...: the village scene is hidden, so not listed)
        seen = game.post_click(["other"], 179, 740)
        self.assertEqual((seen["tips"], seen["sounds"], seen["village"]), ([], [], []))
        self.assertEqual(seen["other"], [(2, 179, 740)])
        # a pop-up over the village that takes the click
        game.other_takes = True
        seen = game.post_click(["other", "village"], 179, 740)
        self.assertEqual((seen["tips"], seen["sounds"], seen["village"]), ([], [], []))
        # the event loop itself no longer looks at the click on any screen
        seen = game.pump_click(179, 740)
        self.assertEqual((seen["tips"], seen["sounds"]), ([], []))
        self.assertEqual(seen["event"], (2, 179, 740))

    def test_a_popup_that_lets_the_click_through_acts_like_the_village_buttons(self) -> None:
        game = _Game(self.patched)
        game.other_takes = False
        seen = game.post_click(["other", "village"], 179, 740)
        self.assertEqual(len(seen["tips"]), 1)
        self.assertEqual(seen["village"], [(179, 740)])


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
