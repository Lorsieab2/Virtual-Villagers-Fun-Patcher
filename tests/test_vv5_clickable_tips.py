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

    def test_counter_lives_in_writable_shr_not_text(self) -> None:
        # the click counter must be written outside read-only .text
        self.assertGreaterEqual(tips.COUNTER_VA, 0x7B2000)
        self.assertLess(tips.COUNTER_VA, 0x7B3000)
        self.assertTrue(any(i.mnemonic == "mov" and hex(tips.COUNTER_VA) in i.op_str for i in self.ins))

    def test_tail_returns_to_hook_plus_five(self) -> None:
        jmps = [int(i.op_str, 16) for i in self.ins if i.mnemonic == "jmp"]
        self.assertIn(tips.HOOK_VA + 5, jmps)


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
