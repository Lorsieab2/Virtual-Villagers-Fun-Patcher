"""The VV5 mask overlay must hand the heathen head draw its own frame.

VV5 crashed on startup for the owner in v1.35.6. The Windows crash dump named
the cause exactly, and it was an argument-order defect in this trampoline.

The overlay replaces the believer head draw at 0x47279C. It performs that stock
call unchanged, then repeats the tuple through the HEATHEN head draw so the mask
lands on top. The two callees differ:

    0x44F5E0  believer head draw  ret 0x1C  -> 7 stack arguments
    0x44F4E0  heathen  head draw  ret 0x20  -> 8 stack arguments

so the overlay pushes one extra dword, the mask selector. The defect was WHERE
it pushed it. On x86 the last push is the lowest address and therefore argument
ONE, so pushing the selector last put it where the first real argument belongs
and shifted all seven others up by a dword.

The dump made the consequence concrete. 0x44F4E0 saves four registers, so its
first stack argument is at [esp+0x14]; it does `mov ebp,[esp+0x14]` then
`mov ecx,ebp` then `call 0x4271C0`, and 0x4271C0 is `mov eax,[ecx+8]; ret`.
With the frame shifted, ecx held 5 -- a small integer, not an object pointer --
so the read went to 0x0000000D and faulted 0xC0000005 at 0x004271C0.

The stock heathen branch at 0x472769 shows the correct order: `push edx`, the
selector, comes FIRST of its six pushes and is therefore the HIGHEST argument,
with the two floats already written below it by an earlier `sub esp,8`.

These guards read the emitted bytes, because that is where the defect lived --
the source read plausibly either way, and its own comment described the correct
rule while the code did the opposite.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "data" / "vv5_task9_native_actions.json"

PAGE_VA = 0x7C9000
OVERLAY_VA = 0x7CFA00

BELIEVER_DRAW = 0x44F5E0   # ret 0x1C, 7 stack arguments
HEATHEN_DRAW = 0x44F4E0    # ret 0x20, 8 stack arguments
SELECTOR = "dword ptr [0x7b1d04]"


class VV5MaskOverlayArgumentOrderTests(unittest.TestCase):
    def setUp(self) -> None:
        try:
            import capstone  # noqa: F401
        except ImportError:  # pragma: no cover - optional dependency
            self.skipTest("capstone is not installed")

    def overlay(self, layout="immediate_fixed"):
        """The decoded instructions of the mask overlay trampoline."""
        import capstone

        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        blob = manifest["pe_append_transaction"]["layouts"][layout]["append_bytes"]
        code = bytes.fromhex(blob)
        offset = OVERLAY_VA - PAGE_VA
        md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
        return list(md.disasm(code[offset:offset + 0x80], OVERLAY_VA))

    def heathen_frame(self, stream):
        """The pushes between the believer call and the heathen call."""
        believer = next(
            i for i, ins in enumerate(stream)
            if ins.mnemonic == "call" and ins.op_str == hex(BELIEVER_DRAW))
        heathen = next(
            i for i, ins in enumerate(stream)
            if ins.mnemonic == "call" and ins.op_str == hex(HEATHEN_DRAW))
        self.assertLess(
            believer, heathen,
            "the stock believer draw must happen before the mask overlay")
        return [ins for ins in stream[believer:heathen]
                if ins.mnemonic == "push"]

    def test_the_selector_is_the_first_push(self) -> None:
        """First push == highest argument == where the stock frame puts it.

        This is the assertion the crash was about. Pushing the selector last
        makes it argument one and shifts every real argument, which is what
        produced the 0xC0000005 at 0x004271C0 on startup.
        """
        for layout in ("immediate_fixed", "collection_progression"):
            with self.subTest(layout=layout):
                pushes = self.heathen_frame(self.overlay(layout))
                self.assertTrue(pushes, "the overlay pushes no arguments")
                self.assertEqual(
                    pushes[0].op_str,
                    SELECTOR,
                    "the mask selector must be pushed FIRST, so it lands as the "
                    "highest argument exactly as the stock heathen branch at "
                    "0x472769 places it; pushing it last makes it argument one "
                    "and shifts the callee's whole frame",
                )

    def test_the_selector_is_never_the_last_push(self) -> None:
        """The specific defect, pinned directly.

        Stated separately from the positive assertion because this is the exact
        shape that shipped and crashed, and a future edit that reorders these
        pushes should fail on the thing that actually broke.
        """
        for layout in ("immediate_fixed", "collection_progression"):
            with self.subTest(layout=layout):
                pushes = self.heathen_frame(self.overlay(layout))
                self.assertNotEqual(
                    pushes[-1].op_str,
                    SELECTOR,
                    "the selector is the last push, so it is argument one -- "
                    "this is the v1.35.6 startup crash",
                )

    def test_the_heathen_draw_receives_eight_arguments(self) -> None:
        """0x44F4E0 is ret 0x20, so it cleans eight dwords.

        Pushing any other number leaves the caller's stack unbalanced, which is
        a different crash from the argument shift but just as fatal.
        """
        for layout in ("immediate_fixed", "collection_progression"):
            with self.subTest(layout=layout):
                pushes = self.heathen_frame(self.overlay(layout))
                self.assertEqual(
                    len(pushes), 8,
                    "the heathen head draw cleans 0x20 bytes, so it must be "
                    "given exactly eight dwords")

    def test_the_seven_forwarded_arguments_keep_their_order(self) -> None:
        """Below the selector, the tuple is the caller's own seven, in order.

        Read from [ebp+8] upward at the call site means pushed from [ebp+0x20]
        downward, so that the lowest source displacement ends up as argument
        one. A reversal here would not crash -- it would draw the mask in the
        wrong place, which is far harder to notice.
        """
        # Capstone prints a single-digit displacement bare (8) and everything
        # else in hex (0xc, 0x10). Written out literally rather than formatted,
        # so the guard fails on a wrong ORDER rather than on a formatting rule
        # this test guessed at -- an earlier version failed for exactly that.
        expected = [
            "dword ptr [ebp + 0x20]",
            "dword ptr [ebp + 0x1c]",
            "dword ptr [ebp + 0x18]",
            "dword ptr [ebp + 0x14]",
            "dword ptr [ebp + 0x10]",
            "dword ptr [ebp + 0xc]",
            "dword ptr [ebp + 8]",
        ]
        for layout in ("immediate_fixed", "collection_progression"):
            with self.subTest(layout=layout):
                pushes = self.heathen_frame(self.overlay(layout))
                self.assertEqual(
                    [p.op_str for p in pushes[1:]],
                    expected,
                    "the seven forwarded arguments must keep the caller's order")


if __name__ == "__main__":
    unittest.main()
