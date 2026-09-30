"""The VV3 companion ships no debug-only state.

"VVFP VV3 Safe Upgrades.dll" is deployed by the VV3 Origins manifest as
"VVFP Origins Icons.dll".  It used to keep two debug arrays,
g_vv3_worlddbg and g_vv3_chiefdbg, fill them on every village mask draw,
and publish their addresses into the patch-owned .vv3md page at +0x3C and
+0x40 so a memory reader could inspect them.  Nothing in the patcher read
them, and nothing debug-only may reach a shipped build.

These tests fail if the arrays, their page slots, or any other pointer
publication into .vv3md beyond the two the exe caves consume come back --
checked in the C source and in the prebuilt binaries a player receives.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

try:
    import pefile
    from capstone import CS_ARCH_X86, CS_MODE_32, Cs
    from capstone.x86 import X86_OP_IMM, X86_OP_MEM
except ImportError:  # pragma: no cover - optional binary inspection dependencies
    pefile = None
    Cs = None

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "native" / "vv3_full_mastery_candidate" / "vv3_full_mastery_candidate.c"
SHIPPED_DLL = ROOT / "data" / "candidates" / "VVFP VV3 Safe Upgrades.dll"
CANONICAL_DLL = ROOT / "data" / "candidates" / "VVFP VV3 Full Mastery Candidate.dll"

PAGE_VA = 0x006E0000
PAGE_END = PAGE_VA + 0x1000
DEBUG_SLOTS = {PAGE_VA + 0x3C, PAGE_VA + 0x40}
# The only pointers the DLL may publish into .vv3md: VV3WorldMaskDrawAt for
# the world head-draw cave, and VV3RunningMaskBoundary.
PUBLISHED_SLOTS = {PAGE_VA + 0x04, PAGE_VA + 0x48}


def _page_references(path: Path):
    """Every absolute .vv3md address the DLL's executable code touches, and
    every store of a DLL-image pointer into that page."""
    pe = pefile.PE(data=path.read_bytes())
    image_base = pe.OPTIONAL_HEADER.ImageBase
    image_end = image_base + pe.OPTIONAL_HEADER.SizeOfImage
    md = Cs(CS_ARCH_X86, CS_MODE_32)
    md.detail = True
    md.skipdata = True
    touched: set[int] = set()
    published: set[int] = set()
    for section in pe.sections:
        if not section.Characteristics & 0x20000000:  # IMAGE_SCN_MEM_EXECUTE
            continue
        base = image_base + section.VirtualAddress
        for ins in md.disasm(section.get_data(), base):
            if ins.id == 0:
                continue
            page_disp = None
            imm = None
            for op in ins.operands:
                if op.type == X86_OP_MEM and op.mem.base == 0 and op.mem.index == 0:
                    value = op.mem.disp & 0xFFFFFFFF
                    if PAGE_VA <= value < PAGE_END:
                        page_disp = value
                        touched.add(value)
                elif op.type == X86_OP_IMM:
                    value = op.imm & 0xFFFFFFFF
                    imm = value
                    if PAGE_VA <= value < PAGE_END:
                        touched.add(value)
            if (
                ins.mnemonic == "mov"
                and page_disp is not None
                and imm is not None
                and image_base <= imm < image_end
            ):
                published.add(page_disp)
    return touched, published


class VV3SafeUpgradesSourceHasNoDebugStateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = SOURCE.read_text(encoding="utf-8")

    def _assert_absent(self, needle: str, haystack: str) -> None:
        self.assertFalse(needle in haystack, f"{needle!r} is back in {SOURCE.name}")

    def test_debug_draw_logs_are_gone(self) -> None:
        for name in ("g_vv3_worlddbg", "g_vv3_chiefdbg"):
            self._assert_absent(name, self.source)
        match = re.search(r"\b\w*dbg\w*\b", self.source)
        self.assertIsNone(match, match and f"debug identifier {match.group()!r} in {SOURCE.name}")

    def test_debug_page_slots_are_not_written(self) -> None:
        normalized = self.source.upper().replace("0X006E00", "0X6E00")
        for slot in sorted(DEBUG_SLOTS):
            self._assert_absent(f"0X{slot:X}", normalized)

    def test_layout_comment_names_no_undefined_slots(self) -> None:
        # The layout comment once listed a "+0x34 auto-load latch (exe-side)"
        # that no builder or manifest defines, plus the two debug slots.
        for stale in ("auto-load latch", "worlddbg", "chiefdbg"):
            self._assert_absent(stale, self.source)


@unittest.skipIf(pefile is None or Cs is None, "pefile/capstone not installed")
class VV3SafeUpgradesBinaryHasNoDebugStateTests(unittest.TestCase):
    def test_shipped_and_canonical_builds_are_identical(self) -> None:
        self.assertEqual(SHIPPED_DLL.read_bytes(), CANONICAL_DLL.read_bytes())

    def test_binary_never_touches_the_debug_slots(self) -> None:
        for path in (SHIPPED_DLL, CANONICAL_DLL):
            with self.subTest(dll=path.name):
                touched, _ = _page_references(path)
                self.assertTrue(touched, "found no .vv3md references at all")
                self.assertFalse(touched & DEBUG_SLOTS, sorted(hex(v) for v in touched))

    def test_binary_publishes_only_the_two_consumed_pointers(self) -> None:
        for path in (SHIPPED_DLL, CANONICAL_DLL):
            with self.subTest(dll=path.name):
                _, published = _page_references(path)
                self.assertEqual(published, PUBLISHED_SLOTS, sorted(hex(v) for v in published))


if __name__ == "__main__":
    unittest.main()
