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

# W^X: all writable mask state lives in the patch-owned .vv1md section
# (0x491000..0x492000), which is writable but NOT executable. Nothing is
# written into the executable .vv1mc code page at runtime.
DATA_GAP_LO = 0x491000
DATA_GAP_HI = 0x492000
TABLE_VA = 0x491000  # 256 villagers x 4 bits = 128 bytes, in .vv1md
TABLE_SIZE = 128
MANAGER_VA = 0x491098  # villager-array base, stashed by the render hook, in .vv1md
RECORD_STRIDE = 0x3D8
# The mask code is at the very start of the appended .vv1mc section.
HOOK_FILE_OFFSET = 0x8E000
HOOK_VA = 0x490000
SHR_LO = 0x490000
SHR_HI = 0x491000


def _render(mode: str) -> bytes:
    import vv_fun_patcher as p

    builds = {b.id: b for b in p.load_builds()}
    # Birth Control owns the same exact stock append tail as Origins; the
    # catalog deliberately rejects that unsafe composition.  This helper is
    # exercising the Origins mask output, so select the compatible features.
    ids = [
        x.id
        for x in p.load_fun_patches()
        if x.game_id == "vv1" and x.id != "vv1_birth_control"
    ]
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
        """Table and manager must sit in .vv1md, not executable .vv1mc.

        This is the W^X invariant. The whole table and the manager pointer
        must fall inside the patch-owned .vv1md page, which is RW/non-executable
        so no runtime write ever lands on an executable page.
        """
        self.assertTrue(
            DATA_GAP_LO <= TABLE_VA and TABLE_VA + TABLE_SIZE <= DATA_GAP_HI,
            "mask table is not inside .vv1md's writable non-executable section",
        )
        self.assertTrue(
            DATA_GAP_LO <= MANAGER_VA < DATA_GAP_HI,
            "villager-array-base pointer is not inside the .vv1md section",
        )
        data = _render("immediate_fixed")
        pe = pefile.PE(data=data, fast_load=True)
        base = pe.OPTIONAL_HEADER.ImageBase
        for s in pe.sections:
            lo = base + s.VirtualAddress
            hi = lo + s.Misc_VirtualSize
            if lo <= TABLE_VA < hi:
                name = s.Name.rstrip(b"\x00").decode()
                self.assertEqual(name, ".vv1md", "mask table escaped .vv1md")
                self.assertFalse(
                    s.Characteristics & 0x20000000,
                    ".vv1md section is executable -- W^X violated",
                )
                self.assertTrue(
                    s.Characteristics & 0x80000000, ".vv1md is not writable"
                )
                break
        else:
            self.fail("no section owns the mask table VA -- .vv1md not present")

    def test_no_mask_write_targets_the_executable_code_section(self):
        """The mask code must never write into executable .vv1mc.

        A write into .vv1mc from the mask hooks is self-modifying code. Every
        mask write must land in .vv1md instead.
        """
        data = _render("immediate_fixed")
        md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
        offenders = []
        off = HOOK_FILE_OFFSET
        cave = data[off:off + 0x1000]
        for insn in md.disasm(cave, HOOK_VA):
            dest = insn.op_str.split(",")[0]
            for m in re.findall(r"\[0x([0-9a-f]+)\]", dest):
                if (
                    SHR_LO <= int(m, 16) < SHR_HI
                    and insn.mnemonic
                    in ("mov", "inc", "dec", "add", "sub", "and", "or", "xor")
                ):
                    offenders.append(f"{insn.address:#x}: {insn.mnemonic} {insn.op_str}")
        self.assertEqual(
            offenders, [], f"mask code writes into executable .vv1mc: {offenders}"
        )

    def test_dll_and_patch_agree_on_the_table_addresses(self):
        """Two files, one address pair -- a mismatch splits picker from render."""
        dll = DLL_SOURCE.read_text(encoding="utf-8")
        patch = PATCH_SOURCE.read_text(encoding="utf-8")

        self.assertIn("0x00491000", dll, "DLL lost the mask table address")
        self.assertIn(
            "#define VV_MASK_MANAGER (*(unsigned char **)(VV_MASK_SCRATCH_BASE + 0x98))",
            dll,
            "DLL lost the villager-array base slot",
        )
        self.assertIn("#define VV_RECORD_STRIDE 0x3D8", dll)
        self.assertIn("#define VV_MASK_SLOTS 256", dll)

        self.assertIn("MASK_DATA_SECTION_VA = 0x491000", patch)
        self.assertIn(f"MASK_TABLE_SIZE = {TABLE_SIZE}", patch)
        self.assertIn("MASK_MANAGER_VA = DATA_SCRATCH_BASE_VA + 0x98", patch)

    def test_render_hook_reads_the_table_and_bounds_checks_the_index(self):
        """The shared village draw hook keys off the stashed record index."""
        data = _render("immediate_fixed")
        md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
        joined = "\n".join(
            f"{insn.mnemonic} {insn.op_str}"
            for insn in md.disasm(data[HOOK_FILE_OFFSET:HOOK_FILE_OFFSET + 0x344], HOOK_VA)
        )

        self.assertIn(
            "mov eax, dword ptr [esi + edi*4 + 0x3dbdc]",
            joined,
            "hook must form the record index exactly as the engine does",
        )
        self.assertIn(
            f"cmp edx, {TABLE_SIZE * 2:#x}",
            joined,
            "hook must bounds-check the index against the table's slot count",
        )
        self.assertIn(
            f"movzx eax, byte ptr [eax + {TABLE_VA:#x}]",
            joined,
            "hook must read the packed nibble from the patch-owned table",
        )
        self.assertIn(
            f"mov eax, dword ptr [{MANAGER_VA:#x}]",
            joined,
            "hook must read the stashed villager-array base",
        )
        for dead in ("0x3d4", "0x374"):
            self.assertNotIn(
                dead, joined, f"hook must not read record byte {dead}"
            )

    def test_hook_lands_on_the_engine_instruction_boundaries_it_claims(self):
        """The stage-1 stash resumes at the next stock instruction boundary."""
        joined = _hook_disasm(_render("immediate_fixed"))
        self.assertEqual(
            joined[0],
            "mov eax, dword ptr [esi + edi*4 + 0x3dbdc]",
            "stash must begin with the stock index load",
        )
        self.assertEqual(
            joined[-1],
            "jmp 0x43779f",
            "stash must resume at the instruction after the splice",
        )

    def test_hook_preserves_every_register_the_engine_still_needs(self):
        """The identity stash leaves the engine's loop registers untouched."""
        joined = _hook_disasm(_render("immediate_fixed"))
        self.assertEqual(
            joined,
            [
                "mov eax, dword ptr [esi + edi*4 + 0x3dbdc]",
                "mov dword ptr [0x4911b4], eax",
                "jmp 0x43779f",
            ],
        )


if __name__ == "__main__":
    unittest.main()
