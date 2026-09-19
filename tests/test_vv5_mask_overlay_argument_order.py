"""The VV5 mask overlay must keep the push order that actually renders masks.

This trampoline has shipped in three different shapes. Only one of them draws a
mask, and the difference is visible only to a human looking at the game:

    selector pushed LAST   -> argument 1   masks render correctly  (KNOWN GOOD)
    selector pushed FIRST  -> argument 8   no crash; selector lands in a
                                           reserved float slot
    selector 3rd-from-last -> argument 6   renders a whole villager body as a
                                           ghost overlay instead of a mask

The owner confirmed the first shape working in a real game, then reported the
breakage after it was changed, and photographed the ghost body produced by the
third. That is the evidence this guard exists to protect.

WHY NOT DERIVE THE ORDER FROM THE STOCK CALL SITE

Because it was tried, twice, and produced two visibly broken builds. The stock
heathen site at 0x472769 pushes its selector first of six, which looks like it
settles the question -- but the overlay is not reproducing that site. The two
draw routines end in DIFFERENT renderers:

    believer 0x44F5E0   ret 0x1C, 7 args, final call 0x409CB0
    heathen  0x44F4E0   ret 0x20, 8 args, final call 0x409DF0

so the believer tuple the overlay forwards is not the heathen tuple, and
choosing a slot for the selector inside an already-mismatched tuple cannot be
reasoned to the right answer. The empirical order wins.

If this guard ever fails because someone "corrected" the ABI, the correct
response is to get runtime evidence that masks still render BEFORE changing it.
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

# The runtime-verified frame, argument 1 first.
EXPECTED_ARGUMENTS = [
    SELECTOR,                   # arg 1  <- pushed LAST
    "dword ptr [ebp + 8]",
    "dword ptr [ebp + 0xc]",
    "dword ptr [ebp + 0x10]",
    "dword ptr [ebp + 0x14]",
    "dword ptr [ebp + 0x18]",
    "dword ptr [ebp + 0x1c]",
    "dword ptr [ebp + 0x20]",
]


class VV5MaskOverlayArgumentOrderTests(unittest.TestCase):
    def setUp(self) -> None:
        try:
            import capstone  # noqa: F401
        except ImportError:  # pragma: no cover - optional dependency
            self.skipTest("capstone is not installed")

    def overlay(self, layout="immediate_fixed"):
        import capstone

        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        blob = manifest["pe_append_transaction"]["layouts"][layout]["append_bytes"]
        code = bytes.fromhex(blob)
        offset = OVERLAY_VA - PAGE_VA
        md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
        return list(md.disasm(code[offset:offset + 0x80], OVERLAY_VA))

    def arguments(self, layout):
        """The heathen call arguments, argument 1 first.

        The pushes are in reverse argument order because the last push is the
        lowest address, so the list is reversed to read as the callee sees it.
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
        return list(reversed([ins.op_str for ins in stream[believer:heathen]
                              if ins.mnemonic == "push"]))

    def test_the_selector_is_argument_one(self) -> None:
        """Pushed last. This exact order is what rendered masks in the game."""
        for layout in ("immediate_fixed", "collection_progression"):
            with self.subTest(layout=layout):
                self.assertEqual(
                    self.arguments(layout).index(SELECTOR) + 1, 1,
                    "the mask selector must be argument 1 -- the only ordering "
                    "observed to render masks correctly in a running game")

    def test_the_selector_is_never_argument_six(self) -> None:
        """Argument 6 renders a ghost villager body. Photographed by the owner."""
        for layout in ("immediate_fixed", "collection_progression"):
            with self.subTest(layout=layout):
                self.assertNotEqual(
                    self.arguments(layout)[5], SELECTOR,
                    "selector at argument 6 draws a whole villager body as a "
                    "ghost overlay instead of a mask")

    def test_the_selector_is_never_argument_eight(self) -> None:
        """Argument 8 is a reserved float slot; it shifts both floats."""
        for layout in ("immediate_fixed", "collection_progression"):
            with self.subTest(layout=layout):
                self.assertNotEqual(
                    self.arguments(layout)[-1], SELECTOR,
                    "selector at argument 8 occupies a reserved float slot")

    def test_the_heathen_draw_receives_eight_arguments(self) -> None:
        """0x44F4E0 is ret 0x20, so it cleans eight dwords."""
        for layout in ("immediate_fixed", "collection_progression"):
            with self.subTest(layout=layout):
                self.assertEqual(
                    len(self.arguments(layout)), 8,
                    "the heathen head draw cleans 0x20 bytes, so it must be "
                    "given exactly eight dwords")

    def test_the_whole_frame_matches_the_verified_order(self) -> None:
        """Every slot, not just the selector's."""
        for layout in ("immediate_fixed", "collection_progression"):
            with self.subTest(layout=layout):
                self.assertEqual(
                    self.arguments(layout), EXPECTED_ARGUMENTS,
                    "the overlay frame must match the runtime-verified order")

    def test_the_trampoline_does_not_nest_the_stolen_call(self) -> None:
        """The #371 startup-crash fix must survive this restoration.

        VV5 crashed on startup when this page WRAPPED the call it replaced,
        leaving the callee to read the game's arguments through two return
        addresses. The page must impersonate the routine instead: re-push the
        seven arguments, call, and clean the caller's frame with `ret 0x1C`.
        """
        for layout in ("immediate_fixed", "collection_progression"):
            with self.subTest(layout=layout):
                stream = self.overlay(layout)
                believer = next(
                    i for i, ins in enumerate(stream)
                    if ins.mnemonic == "call" and ins.op_str == hex(BELIEVER_DRAW))
                forwarded = [ins for ins in stream[:believer]
                             if ins.mnemonic == "push"
                             and ins.op_str.startswith("dword ptr [ebp")]
                self.assertEqual(
                    len(forwarded), 7,
                    "the seven arguments must be re-pushed before the stolen call")
                rets = [ins for ins in stream if ins.mnemonic == "ret"]
                self.assertTrue(
                    any(r.op_str and int(r.op_str, 16) == 0x1C for r in rets),
                    "the page must clean the caller's arguments with ret 0x1C")


if __name__ == "__main__":
    unittest.main()
