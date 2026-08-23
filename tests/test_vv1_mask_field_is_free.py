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

# W^X: all writable mask state lives in .data's BSS tail (0x48CD18..0x48D000),
# a section that is writable but NOT executable. Nothing is written into the
# executable .shr cave at runtime -- that is what made Malwarebytes quarantine
# the process (a per-frame write into an executable page reads as self-
# modifying code). The mask table and the villager-array-base pointer both
# live here; the mask CODE stays in .shr and only reads them.
DATA_GAP_LO = 0x48CD18  # first byte past stock .data's declared VirtualSize
DATA_GAP_HI = 0x48D000  # .shr begins here
TABLE_VA = 0x48CD20  # 256 villagers x 4 bits = 128 bytes, in .data
TABLE_SIZE = 128
MANAGER_VA = 0x48CDD0  # villager-array base, stashed by the render hook, in .data
RECORD_STRIDE = 0x3D8
# The mask cave now holds only code (the path strings moved to the .rdata
# string cave), so the hook is at the very start of the cave.
HOOK_FILE_OFFSET = 0x8BEA8
HOOK_VA = 0x48DEA8
SHR_LO = 0x48D000
SHR_HI = 0x48E000


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

    def test_all_mask_state_lives_in_writable_nonexecutable_data(self):
        """Table and manager must sit in .data's BSS gap, not executable .shr.

        This is the W^X invariant. The whole table and the manager pointer
        must fall inside 0x48CD18..0x48D000, which the build extends .data's
        VirtualSize to own and which is RW/non-executable -- so no runtime
        write ever lands on an executable page (the Malwarebytes trigger).
        """
        self.assertTrue(
            DATA_GAP_LO <= TABLE_VA and TABLE_VA + TABLE_SIZE <= DATA_GAP_HI,
            "mask table is not inside .data's writable non-executable gap",
        )
        self.assertTrue(
            DATA_GAP_LO <= MANAGER_VA < DATA_GAP_HI,
            "villager-array-base pointer is not inside the .data gap",
        )
        data = _render("immediate_fixed")
        pe = pefile.PE(data=data, fast_load=True)
        base = pe.OPTIONAL_HEADER.ImageBase
        for s in pe.sections:
            lo = base + s.VirtualAddress
            hi = lo + s.Misc_VirtualSize
            if lo <= TABLE_VA < hi:
                name = s.Name.rstrip(b"\x00").decode()
                self.assertEqual(name, ".data", "mask table escaped .data")
                self.assertFalse(
                    s.Characteristics & 0x20000000,
                    ".data section is executable -- W^X violated",
                )
                self.assertTrue(
                    s.Characteristics & 0x80000000, ".data is not writable"
                )
                break
        else:
            self.fail("no section owns the mask table VA -- .data not extended")

    def test_no_mask_write_targets_the_executable_shr_section(self):
        """The mask cave code must never write into executable .shr.

        A write into .shr from the mask hooks is exactly the self-modifying-
        code pattern that got the build quarantined. Every mask write must
        land in .data instead.
        """
        data = _render("immediate_fixed")
        md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
        offenders = []
        off = 0x8BEA8
        cave = data[off:0x8C000]
        for insn in md.disasm(cave, 0x48DEA8):
            dest = insn.op_str.split(",")[0]
            for m in re.findall(r"\[0x([0-9a-f]+)\]", dest):
                if (
                    SHR_LO <= int(m, 16) < SHR_HI
                    and insn.mnemonic
                    in ("mov", "inc", "dec", "add", "sub", "and", "or", "xor")
                ):
                    offenders.append(f"{insn.address:#x}: {insn.mnemonic} {insn.op_str}")
        self.assertEqual(
            offenders, [], f"mask code writes into executable .shr: {offenders}"
        )

    def test_dll_and_patch_agree_on_the_table_addresses(self):
        """Two files, one address pair -- a mismatch splits picker from render."""
        dll = DLL_SOURCE.read_text(encoding="utf-8")
        patch = PATCH_SOURCE.read_text(encoding="utf-8")

        self.assertIn("0x0048CD20", dll, "DLL lost the mask table address")
        self.assertIn("0x0048CDD0", dll, "DLL lost the villager-array base slot")
        self.assertIn("#define VV_RECORD_STRIDE 0x3D8", dll)
        self.assertIn("#define VV_MASK_SLOTS 256", dll)

        self.assertIn("DATA_SCRATCH_BASE_VA = 0x48CD20", patch)
        self.assertIn(f"MASK_TABLE_SIZE = {TABLE_SIZE}", patch)
        self.assertIn("MASK_MANAGER_VA = DATA_SCRATCH_BASE_VA + 0xB0", patch)

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
