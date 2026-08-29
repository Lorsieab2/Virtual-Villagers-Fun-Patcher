"""Static VV5-contract gates for VV1's Details portrait mask wrapper.

These checks prove the generated call/stack shape and the checked-in source
contract. They do not prove that the game renders correctly at runtime.
"""
from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path

try:
    from capstone import CS_ARCH_X86, CS_MODE_32, Cs

    HAVE_CAPSTONE = True
except ImportError:  # pragma: no cover - environment dependent
    HAVE_CAPSTONE = False


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "data" / "vv1_origins_feature.json"
GENERATOR = ROOT / "scripts" / "build_vv1_origins_feature.py"
SOURCE = ROOT / "native" / "vv1_origins_icons" / "vv1_origins_icons.c"
EXPORTS = ROOT / "native" / "vv1_origins_icons" / "vv1_origins_icons.def"
DLL = ROOT / "assets" / "origins" / "VVFP VV1 Origins Icons.dll"

IMAGE_BASE = 0x400000
STOCK_SCALED_DRAW = 0x409410
PORTRAIT_WRAPPER = 0x490720
PORTRAIT_WRAPPER_FILE_OFFSET = 0x8E720
PORTRAIT_DLL_FN = 0x4911AC
PORTRAIT_SITES = (0x43741B, 0x4374A4, 0x437503, 0x437556)


def _call_target(site: int, encoded: bytes) -> int:
    if len(encoded) != 5 or encoded[0] != 0xE8:
        raise AssertionError(f"{site:#x} is not one five-byte CALL")
    displacement = int.from_bytes(encoded[1:5], "little", signed=True)
    return site + 5 + displacement


class VV1DetailsMaskRenderContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        cls.patches = {
            int(item["offset"], 0): item for item in cls.manifest["patches"]
        }
        cls.source = SOURCE.read_text(encoding="utf-8")
        cls.generator = GENERATOR.read_text(encoding="utf-8")
        cls.exports = EXPORTS.read_text(encoding="utf-8")

    def test_all_four_native_head_calls_keep_call_abi_and_share_one_wrapper(self) -> None:
        for site in PORTRAIT_SITES:
            with self.subTest(site=hex(site)):
                patch = self.patches[site - IMAGE_BASE]
                self.assertEqual(
                    _call_target(site, bytes.fromhex(patch["before"])),
                    STOCK_SCALED_DRAW,
                )
                self.assertEqual(
                    _call_target(site, bytes.fromhex(patch["after"])),
                    PORTRAIT_WRAPPER,
                )

    @unittest.skipUnless(HAVE_CAPSTONE, "requires Capstone")
    def test_wrapper_duplicates_all_seven_args_then_returns_with_stock_cleanup(self) -> None:
        wrapper = bytes.fromhex(self.patches[PORTRAIT_WRAPPER_FILE_OFFSET]["after"])
        ins = list(Cs(CS_ARCH_X86, CS_MODE_32).disasm(wrapper, PORTRAIT_WRAPPER))
        self.assertEqual((ins[0].mnemonic, ins[0].op_str), ("push", "ecx"))
        self.assertEqual(
            [(item.mnemonic, item.op_str) for item in ins[1:8]],
            [("push", "dword ptr [esp + 0x20]")] * 7,
        )
        self.assertEqual(
            (ins[8].mnemonic, ins[8].op_str),
            ("mov", "ecx, dword ptr [esp + 0x1c]"),
        )
        self.assertEqual(
            (ins[9].mnemonic, int(ins[9].op_str, 16)),
            ("call", STOCK_SCALED_DRAW),
        )

        text = " ; ".join(f"{item.mnemonic} {item.op_str}" for item in ins)
        for token in (
            "lea edx, [esp + 8]",
            "push edx",
            "push dword ptr [esp + 4]",
            "push edi",
            "push esi",
            "call eax",
        ):
            with self.subTest(token=token):
                self.assertIn(token, text)
        self.assertEqual((ins[-2].mnemonic, ins[-2].op_str), ("add", "esp, 4"))
        self.assertEqual((ins[-1].mnemonic, ins[-1].op_str.lower()), ("ret", "0x1c"))

    def test_native_overlay_uses_exact_tuple_not_fixed_portrait_reconstruction(self) -> None:
        for token in (
            "#define VV_DETAILS_MASK_Y_NUDGE_PX 10",
            "x = args[1];",
            "scale = args[5];",
            "y = args[2] - (scale >> 3) - VV_DETAILS_MASK_Y_NUDGE_PX;",
            "col = args[4];",
            "enable = args[6];",
            "mov  ecx, draw_wrapper",
        ):
            with self.subTest(token=token):
                self.assertIn(token, self.source)
        for obsolete in (
            "VV_PORTRAIT_X",
            "VV_PORTRAIT_Y_CHILD",
            "VV_ANIMPARAM_OFFSET",
            "PORTRAIT_SCALE_SAVE",
            "0x3E030",
        ):
            with self.subTest(obsolete=obsolete):
                self.assertNotIn(obsolete, self.source + self.generator)

        # The registration remains tied to the live portrait scale, with the
        # requested fixed 10px VV1 Details nudge applied after it. It is not a
        # fixed child/adult coordinate reconstruction.
        self.assertEqual([(scale >> 3) + 10 for scale in (160, 198, 200)], [30, 34, 35])
        self.assertNotIn("VV_PORTRAIT_LIFT_MUL", self.source)

    def test_vv1_details_nudge_is_ten_pixels_and_vv2_override_is_zero(self) -> None:
        vv2 = (ROOT / "native" / "vv2_origins_icons" / "vv2_origins_icons.c").read_text(
            encoding="utf-8"
        )
        self.assertIn("#define VV_DETAILS_MASK_Y_NUDGE_PX 10", self.source)
        self.assertIn(
            "#define VV_DETAILS_MASK_Y_NUDGE_PX 0\n#include \"../vv1_origins_icons/vv1_origins_icons.c\"",
            vv2,
        )
        self.assertEqual(self.source.count("VV_DETAILS_MASK_Y_NUDGE_PX"), 4)
        self.assertEqual(vv2.count("#define VV_DETAILS_MASK_Y_NUDGE_PX 0"), 1)

    @unittest.skipUnless(HAVE_CAPSTONE, "requires Capstone")
    def test_missing_portrait_export_is_cached_as_fail_open(self) -> None:
        wrapper = bytes.fromhex(self.patches[PORTRAIT_WRAPPER_FILE_OFFSET]["after"])
        ins = list(Cs(CS_ARCH_X86, CS_MODE_32).disasm(wrapper, PORTRAIT_WRAPPER))
        shape = [(item.mnemonic, item.op_str) for item in ins]
        self.assertIn(("cmp", "eax, 1"), shape)
        sentinel_check = shape.index(("cmp", "eax, 1"))
        self.assertEqual(shape[sentinel_check + 1][0], "je")
        self.assertIn(
            ("mov", f"dword ptr [{PORTRAIT_DLL_FN:#x}], 1"),
            shape,
        )
        self.assertLess(
            sentinel_check,
            shape.index(("call", "dword ptr [0x457010]")),
        )
        self.assertIn("permanent fail-open sentinel", self.generator)

    def test_native_export_uses_the_four_argument_stdcall_contract(self) -> None:
        self.assertIn("Vv1DrawPortraitMask=_Vv1DrawPortraitMask@16", self.exports)
        self.assertNotIn("Vv1DrawPortraitMask=_Vv1DrawPortraitMask@8", self.exports)
        self.assertIn("void *draw_wrapper,", self.source)
        self.assertIn("const int *args)", self.source)

    def test_manifest_binds_the_rebuilt_companion_dll(self) -> None:
        entry = next(
            item
            for item in self.manifest["companion_files"]
            if item["destination"] == "VVFP VV1 Origins Icons.dll"
        )
        self.assertEqual(
            hashlib.sha256(DLL.read_bytes()).hexdigest().upper(), entry["sha256"]
        )


if __name__ == "__main__":
    unittest.main()
