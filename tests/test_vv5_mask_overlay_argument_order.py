"""The VV5 mask overlay must hand the heathen head draw its own frame.

VV5 crashed on startup for the owner in v1.35.6. The Windows crash dump named
the cause, and it was an argument-position defect in this trampoline. A first
repair moved the value to the opposite extreme and was still wrong; Codex caught
that one in review. Both mistakes are pinned here.

The overlay replaces the believer head draw at 0x47279C. It performs that stock
call unchanged, then repeats the tuple through the HEATHEN head draw so the mask
lands on top. Both stock call sites build the same shape -- `sub esp, 8` reserves
two float slots, two `fstp` writes fill them, then the register arguments are
pushed -- so the reserved floats are the HIGHEST arguments:

    heathen  0x44F4E0  ret 0x20, 8 args, site 0x472726
        args 1-5  ecx, edi, ebp, ebx, eax
        arg  6    edx  <- the mask selector
        args 7-8  the two reserved floats

    believer 0x44F5E0  ret 0x1C, 7 args, site 0x472780
        args 1-5  eax, edi, ebp, ebx, edx
        args 6-7  the two reserved floats

So the believer tuple maps onto the heathen call as args 1-5 unchanged, the
selector inserted at 6, and the believer's floats moved up to 7 and 8.

WHAT WENT WRONG, TWICE.

Pushing the selector LAST makes it argument ONE. 0x44F4E0 saves four registers,
so its first stack argument is at [esp+0x14]; it does `mov ebp,[esp+0x14]`,
`mov ecx,ebp`, `call 0x4271C0`, and 0x4271C0 is `mov eax,[ecx+8]; ret`. With the
frame shifted, ecx held 5 -- a save slot number, not an object -- so the read
went to 0x0000000D and faulted 0xC0000005 at 0x004271C0. That is the startup
crash the owner reported.

Pushing it FIRST makes it argument EIGHT. That stops the crash, because args 1-5
are then correct and the dereferenced pointer is real, but the selector sits in a
float slot and both floats shift down -- a masked villager draws with a garbage
coordinate and the selector is read as a float. It fails quietly rather than
loudly, which is worse.

These guards read the emitted bytes, because that is where both defects lived:
the source read plausibly every time, and its own comment twice described a rule
the code did not follow.
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

# The heathen frame, argument 1 first. Arguments 1-5 are the believer's own
# 1-5; argument 6 is the selector; arguments 7-8 are the believer's floats.
EXPECTED_ARGUMENTS = [
    "dword ptr [ebp + 8]",      # arg 1
    "dword ptr [ebp + 0xc]",    # arg 2
    "dword ptr [ebp + 0x10]",   # arg 3
    "dword ptr [ebp + 0x14]",   # arg 4
    "dword ptr [ebp + 0x18]",   # arg 5
    SELECTOR,                   # arg 6
    "dword ptr [ebp + 0x1c]",   # arg 7  (believer float)
    "dword ptr [ebp + 0x20]",   # arg 8  (believer float)
]

SELECTOR_ARGUMENT = 6


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

    def arguments(self, layout):
        """The heathen call's arguments, argument 1 first.

        The pushes between the two calls are in reverse argument order, because
        the last push is the lowest address, so the list is reversed to read as
        the callee sees it.
        """
        stream = self.overlay(layout)
        believer = next(
            i for i, ins in enumerate(stream)
            if ins.mnemonic == "call" and ins.op_str == hex(BELIEVER_DRAW))
        heathen = next(
            i for i, ins in enumerate(stream)
            if ins.mnemonic == "call" and ins.op_str == hex(HEATHEN_DRAW))
        self.assertLess(
            believer, heathen,
            "the stock believer draw must happen before the mask overlay")
        pushes = [ins.op_str for ins in stream[believer:heathen]
                  if ins.mnemonic == "push"]
        return list(reversed(pushes))

    def test_the_selector_is_argument_six(self) -> None:
        """Not one, and not eight. Both of those shipped and both were wrong.

        Argument one is the startup crash. Argument eight stops the crash while
        putting the selector in a float slot, which draws a masked villager at a
        garbage coordinate instead of faulting.
        """
        for layout in ("immediate_fixed", "collection_progression"):
            with self.subTest(layout=layout):
                args = self.arguments(layout)
                self.assertEqual(
                    args.index(SELECTOR) + 1,
                    SELECTOR_ARGUMENT,
                    "the mask selector must land where the stock heathen site "
                    "puts edx -- argument 6 of 8, below the two reserved "
                    "floats",
                )

    def test_the_selector_is_never_argument_one(self) -> None:
        """The v1.35.6 startup crash, pinned by itself."""
        for layout in ("immediate_fixed", "collection_progression"):
            with self.subTest(layout=layout):
                self.assertNotEqual(
                    self.arguments(layout)[0],
                    SELECTOR,
                    "the selector is argument one -- this is the startup crash",
                )

    def test_the_selector_is_never_argument_eight(self) -> None:
        """The first repair, pinned by itself.

        Kept separate from the positive assertion because this shape passes a
        launch test: it only shows up as a mask drawn in the wrong place.
        """
        for layout in ("immediate_fixed", "collection_progression"):
            with self.subTest(layout=layout):
                self.assertNotEqual(
                    self.arguments(layout)[-1],
                    SELECTOR,
                    "the selector is argument eight -- it occupies a float slot "
                    "and shifts both floats down",
                )

    def test_the_heathen_draw_receives_eight_arguments(self) -> None:
        """0x44F4E0 is ret 0x20, so it cleans eight dwords."""
        for layout in ("immediate_fixed", "collection_progression"):
            with self.subTest(layout=layout):
                self.assertEqual(
                    len(self.arguments(layout)), 8,
                    "the heathen head draw cleans 0x20 bytes, so it must be "
                    "given exactly eight dwords")

    def test_the_whole_frame_matches_the_stock_layout(self) -> None:
        """Every slot, not just the selector's.

        The two believer floats have to move UP to 7 and 8 when the selector is
        inserted at 6. Checking only the selector's position would accept a
        frame that put the floats back where they started.
        """
        for layout in ("immediate_fixed", "collection_progression"):
            with self.subTest(layout=layout):
                self.assertEqual(
                    self.arguments(layout),
                    EXPECTED_ARGUMENTS,
                    "the heathen frame must match the stock site slot for slot")


if __name__ == "__main__":
    unittest.main()
