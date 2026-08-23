"""The mask selection must live in memory the PATCH owns, never in the record.

Two villager-record bytes were tried and both turned out to be occupied by
the engine, in ways a static displacement scan provably cannot detect:

  +0x374 was inside the villager NAME buffer (name base +0x370) -- a live
         record read back "Nuru" there. Writing a mask renamed the villager,
         and the render's 1..5 range check then rejected the byte (it held
         'u' = 117), so nothing drew and the corruption was silent. Names are
         written by a string copy, so the byte has no displacement reference.

  +0x3D4 had exactly one reference in the whole executable (the record
         initialiser zeroing it) and read all-zero across a 40-villager
         sample, so the previous version of this file certified it as free.
         On a fresh load of a real 210-villager save, with no mask ever set,
         it read 0->196, 1->9, 3->1, 5->1, 8->1, 15->2. The save-LOAD path
         writes it via a bulk read -- again invisible to a displacement scan.

A scan of all 211 records then found 186 always-zero bytes but NO run of >=4
consecutive, and every one is the high byte of a dword holding a small value
(writing 1..5 into one would make the engine read e.g. 0x03000000). VV1's
984-byte record is full. There is no free byte to find.

So these tests no longer try to certify a record byte. They pin the opposite
property: that the feature touches NO record byte at all, and that its table
lives in a window this patch owns and can prove free FROM THE BUILD, rather
than inferring it from a sample of live data. That distinction is the whole
lesson of the two failures above.
"""
from __future__ import annotations

import re
import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

try:
    import capstone
    import pefile  # noqa: F401  (import guard only)

    HAVE_DEPS = True
except ImportError:  # pragma: no cover - environment dependent
    HAVE_DEPS = False

STOCK = ROOT / "inputs" / "vv1-stock-copy" / "Virtual Villagers - A New Home.exe"
DLL_SOURCE = ROOT / "native" / "vv1_origins_icons" / "vv1_origins_icons.c"
PATCH_SOURCE = ROOT / "scripts" / "build_vv1_origins_feature.py"

# The table: 256 villagers, one nibble each, placed at the END of the .shr
# gap that runs 0x8B07E..0x8B180 so that both neighbouring sub-caves keep
# their growth room (the preflight cave below keeps 130 bytes, and the
# village-wide payload at 0x8B180 starts exactly where this table ends).
TABLE_FILE_START = 0x8B100
TABLE_SIZE = 128
TABLE_VA = 0x48D100
MANAGER_VA = 0x48DEE4  # villager-array base, stashed by the render hook
RECORD_STRIDE = 0x3D8
HOOK_FILE_OFFSET = 0x8BEA8 + 0x48
HOOK_VA = 0x48DEA8 + 0x48


def _render(mode: str) -> bytes:
    import vv_fun_patcher as p

    builds = {b.id: b for b in p.load_builds()}
    ids = [x.id for x in p.load_fun_patches() if x.game_id == "vv1"]
    data, _ = p.render_patched_bytes(STOCK, builds["vv1"], mode, ids)
    return bytes(data)


def _hook_disasm(data: bytes) -> list[str]:
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    out = []
    for insn in md.disasm(data[HOOK_FILE_OFFSET:HOOK_FILE_OFFSET + 160], HOOK_VA):
        out.append(f"{insn.mnemonic} {insn.op_str}")
        if insn.mnemonic == "jmp" and insn.op_str.startswith("0x4377"):
            break
    return out


@unittest.skipUnless(HAVE_DEPS and STOCK.exists(), "needs capstone/pefile + stock exe")
class VV1MaskFieldIsFreeTests(unittest.TestCase):
    def test_no_record_byte_is_used_for_the_mask_anywhere(self):
        """Neither file may reference a villager-record mask byte."""
        dll = DLL_SOURCE.read_text(encoding="utf-8")
        self.assertNotIn(
            "VV_MASK_OFFSET",
            dll,
            "the DLL still has a villager-record mask offset -- the whole "
            "point of the table is that no record byte is involved",
        )
        # The abandoned offsets are still NAMED in the comments on purpose --
        # that history is the reason the table exists. What must not survive
        # is any CODE that touches them, so strip comments before checking.
        code = re.sub(r"/\*.*?\*/", "", dll, flags=re.S)
        code = re.sub("//[^" + chr(10) + "]*", "", code)
        for dead in ("0x374", "0x3D4", "0x3d4"):
            self.assertNotIn(
                dead,
                code,
                f"DLL code still touches the abandoned record byte {dead}",
            )

    def test_table_window_is_free_in_every_population_variant(self):
        """Free proven from the build, not inferred from a live sample."""
        for mode in ("immediate_fixed", "stock"):
            with self.subTest(mode=mode):
                data = _render(mode)
                window = data[TABLE_FILE_START:TABLE_FILE_START + TABLE_SIZE]
                self.assertEqual(len(window), TABLE_SIZE)
                self.assertEqual(
                    sum(window),
                    0,
                    f"{mode}: something now writes into the mask table window",
                )

    def test_nothing_else_addresses_the_table_window(self):
        """No other patch and no stock code may point into the table.

        The render hook's own load encodes 0x48D100 as a disp32, so exactly
        one hit is expected; anything more means the window was claimed twice.
        """
        data = _render("immediate_fixed")
        lo, hi = TABLE_VA, TABLE_VA + TABLE_SIZE
        hits = [
            (hex(i), hex(struct.unpack_from("<I", data, i)[0]))
            for i in range(0, len(data) - 4)
            if lo <= struct.unpack_from("<I", data, i)[0] < hi
        ]
        self.assertLessEqual(
            len(hits),
            1,
            f"unexpected references into the mask table window: {hits}",
        )

    def test_dll_and_patch_agree_on_the_table_addresses(self):
        """Two files, one address pair -- a mismatch splits picker from render."""
        dll = DLL_SOURCE.read_text(encoding="utf-8")
        patch = PATCH_SOURCE.read_text(encoding="utf-8")

        self.assertIn("0x0048D100", dll, "DLL lost the mask table address")
        self.assertIn("0x0048DEE4", dll, "DLL lost the villager-array base slot")
        self.assertIn("#define VV_RECORD_STRIDE 0x3D8", dll)
        self.assertIn("#define VV_MASK_SLOTS 256", dll)

        self.assertIn("MASK_TABLE_FILE_OFFSET = 0x8B100", patch)
        self.assertIn(f"MASK_TABLE_SIZE = {TABLE_SIZE}", patch)
        self.assertIn("MASK_MANAGER_VA = MASK_OVERLAY_VA + 0x3C", patch)

    def test_render_hook_reads_the_table_and_bounds_checks_the_index(self):
        """The hook must key off the record INDEX and reject out-of-range."""
        joined = "\n".join(_hook_disasm(_render("immediate_fixed")))

        self.assertIn(
            "mov ecx, dword ptr [esi + edi*4 + 0x3dbdc]",
            joined,
            "hook must form the record index exactly as the engine does",
        )
        self.assertIn(
            f"cmp ecx, {TABLE_SIZE * 2:#x}",
            joined,
            "hook must bounds-check the index against the table's slot count",
        )
        self.assertIn(
            f"movzx edx, byte ptr [edx + {TABLE_VA:#x}]",
            joined,
            "hook must read the packed nibble from the patch-owned table",
        )
        self.assertIn(
            f"mov dword ptr [{MANAGER_VA:#x}], esi",
            joined,
            "hook must stash the villager-array base for the picker",
        )
        for dead in ("0x3d4", "0x374"):
            self.assertNotIn(
                dead, joined, f"hook must not read record byte {dead}"
            )

    def test_hook_lands_on_the_engine_instruction_boundaries_it_claims(self):
        """A skewed assembly base silently redirects every absolute branch.

        This happened: the hook was assembled for a base 8 bytes below where
        it was written, so the resume jmp pointed at 0x4377c6 -- the MIDDLE of
        the instruction at 0x4377c7 -- which would have executed garbage.
        Both targets are real instruction starts in stock, so pin them.
        """
        joined = _hook_disasm(_render("immediate_fixed"))
        self.assertEqual(
            joined[0],
            "jne 0x4388ce",
            "hook must preserve the engine's own not-occupied branch target",
        )
        self.assertEqual(
            joined[-1],
            "jmp 0x4377be",
            "hook must resume at the instruction after the splice",
        )

    def test_hook_preserves_every_register_the_engine_still_needs(self):
        """ECX/EDX are the only registers the engine reloads after the splice.

        Verified against stock: 0x4377c7 writes ECX and 0x4377ca writes EDX
        before either is read, so both are dead scratch. EAX (record), EBX
        (0xC7), EBP (4), ESI (manager) and EDI (slot) are all still live, and
        clobbering any of them would corrupt the engine's own draw loop.
        """
        clobbered = set()
        for line in _hook_disasm(_render("immediate_fixed")):
            mnemonic, _, operands = line.partition(" ")
            if mnemonic in ("mov", "movzx", "shr", "and", "add", "sub"):
                dest = operands.split(",")[0].strip()
                if re.fullmatch(r"e[abcds][xpi]", dest):
                    clobbered.add(dest)
        self.assertLessEqual(
            clobbered,
            {"ecx", "edx"},
            f"hook clobbers registers the engine still needs: "
            f"{sorted(clobbered - {'ecx', 'edx'})}",
        )


if __name__ == "__main__":
    unittest.main()
