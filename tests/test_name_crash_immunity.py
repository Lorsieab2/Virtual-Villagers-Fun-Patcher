from __future__ import annotations

import struct
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import vv_fun_patcher as patcher  # noqa: E402

try:
    from capstone import CS_ARCH_X86, CS_MODE_32, Cs

    HAVE_CAPSTONE = True
except ImportError:  # pragma: no cover - environment dependent
    HAVE_CAPSTONE = False


IMAGE_BASE = 0x400000
EXPECTED_BASENAME = "Virtual Villagers - The Secret City.exe"


def _synthetic_pe(*, include_immediate_match: bool = False) -> bytearray:
    """Build a compact PE containing the supported VV1 call-site map."""
    data = bytearray(0x90000)
    data[:2] = b"MZ"
    struct.pack_into("<I", data, 0x3C, 0x80)
    data[0x80:0x84] = b"PE\0\0"
    coff = 0x84
    struct.pack_into("<H", data, coff + 2, 1)  # one section
    struct.pack_into("<H", data, coff + 16, 0xE0)  # optional-header size
    optional = coff + 20
    struct.pack_into("<H", data, optional, 0x10B)
    struct.pack_into("<I", data, optional + 28, IMAGE_BASE)
    struct.pack_into("<I", data, optional + 92, 16)
    struct.pack_into("<II", data, optional + 96 + 8, 0x1800, 0x100)

    section = optional + 0xE0
    data[section : section + 8] = b".text\0\0\0"
    struct.pack_into("<I", data, section + 8, 0x80000)  # virtual size
    struct.pack_into("<I", data, section + 12, 0x1000)  # RVA
    struct.pack_into("<I", data, section + 16, 0x80000)  # raw size
    struct.pack_into("<I", data, section + 20, 0x400)  # raw offset
    struct.pack_into("<I", data, section + 36, 0x60000020)  # executable/readable

    def raw(rva: int) -> int:
        return 0x400 + (rva - 0x1000)

    # IMAGE_IMPORT_DESCRIPTOR -> INT, module name, IAT.
    struct.pack_into("<IIIII", data, raw(0x1800), 0x1900, 0, 0, 0x1C00, 0x5711C)
    struct.pack_into("<II", data, raw(0x1900), 0x1C00, 0)
    data[raw(0x1C00) + 2 : raw(0x1C00) + 2 + len(b"GetModuleFileNameA\0")] = b"GetModuleFileNameA\0"

    iat_va = IMAGE_BASE + 0x5711C
    for rva in (0x27DD, 0x2944, 0x50967, 0x50ED5, 0x52C57):
        data[raw(rva) : raw(rva) + 2] = b"\xFF\x15"
        struct.pack_into("<I", data, raw(rva) + 2, iat_va)

    if include_immediate_match:
        # This is deliberately not a call-site: the FF 15 <IAT> bytes begin at
        # byte 1 of MOV EAX, imm32.  A raw byte search would incorrectly redirect
        # this interior match.
        data[raw(0x2A20) : raw(0x2A27)] = b"\xB8\xFF\x15\x1C\x71\x45\x00"
    return data


@unittest.skipUnless(HAVE_CAPSTONE, "requires Capstone")
class NameCrashWrapperTests(unittest.TestCase):
    def _instructions(self, name_len: int = 10):
        blob = patcher._nci_wrapper(0x401A00, 0x500000, name_len)
        return blob, list(Cs(CS_ARCH_X86, CS_MODE_32).disasm(blob, 0x600000))

    def test_success_failure_and_truncation_paths_are_bounded(self) -> None:
        blob, ins = self._instructions()
        self.assertTrue(blob)
        text = [(item.mnemonic, item.op_str) for item in ins]
        fail = next(
            item.address
            for item in ins
            if item.mnemonic == "mov"
            and item.op_str == "eax, dword ptr [esp + 0xc]"
        )
        self.assertNotIn("eax, dword ptr [esp + 0x10]", text)
        self.assertIn(("mov", "edi, dword ptr [esp + 0x18]"), text)
        self.assertIn(("mov", "ecx, dword ptr [esp + 0x1c]"), text)

        # API failure, API-reported truncation, nSize == 0, a scan reaching the
        # nSize boundary, and replacement truncation all branch to the same
        # original-return restore.
        expected_branches = (
            ("test", "eax, eax", "je"),
            ("test", "ecx, ecx", "je"),
            ("cmp", "eax, ecx", "jae"),
            ("cmp", "edi, ebp", "jae"),
            ("cmp", "eax, ebp", "ja"),
        )
        for compare, operand, branch in expected_branches:
            with self.subTest(compare=compare, operand=operand):
                index = next(
                    i
                    for i, item in enumerate(ins)
                    if item.mnemonic == compare and item.op_str == operand
                )
                self.assertEqual(ins[index + 1].mnemonic, branch)
                self.assertEqual(int(ins[index + 1].op_str, 16), fail)

        write_index = next(
            i
            for i, item in enumerate(ins)
            if item.mnemonic == "mov" and item.op_str == "byte ptr [edx], al"
        )
        capacity_index = next(
            i
            for i, item in enumerate(ins)
            if item.mnemonic == "cmp" and item.op_str == "eax, ebp"
        )
        self.assertGreater(write_index, capacity_index)
        self.assertIn(("ret", "0xc"), text)

    def test_every_name_guard_write_is_in_the_applied_ledger(self) -> None:
        data = _synthetic_pe()
        applied: list[dict[str, str]] = []
        result = patcher._apply_name_crash_immunity(
            data, EXPECTED_BASENAME, applied
        )
        self.assertEqual(result["status"], "applied")
        self.assertEqual(len(applied), len(result["writes"]))
        self.assertEqual(
            len({row["offset"] for row in applied}),
            len(applied),
        )
        for row in applied:
            self.assertEqual(row["purpose"], "wrong-exe-name crash immunity")
            self.assertEqual(row["owner"], "automatic:name_crash_immunity")
        # Four, not five: VV1 has five GetModuleFileNameA call sites and the
        # save-folder one (RVA 0x2944) is deliberately left unwrapped so the
        # published exe uses a folder named after itself (#347).
        self.assertEqual(len(result["call_sites"]), 4)
        self.assertNotIn(
            IMAGE_BASE + 0x2944,
            result["call_sites"],
            "the save-folder call site must not be rewritten",
        )
        name_to_code = result["wrapper_va"] - result["name_va"]
        wrapper_length = len(
            patcher._nci_wrapper(
                result["iat_va"], result["name_va"], len(EXPECTED_BASENAME) + 1
            )
        )
        self.assertEqual(
            len(result["writes"][1]["after"]) // 2,
            wrapper_length,
        )
        self.assertGreaterEqual(name_to_code, len(EXPECTED_BASENAME) + 1)

    def test_import_pattern_inside_immediate_is_not_a_call_site(self) -> None:
        data = bytes(_synthetic_pe(include_immediate_match=True))
        info = patcher._nci_pe_info(data)
        self.assertEqual(
            patcher._nci_find_call_sites(data, info, IMAGE_BASE + 0x5711C),
            [],
        )

    def test_finalizer_rejects_unapplied_immunity(self) -> None:
        for reason in ("not a PE32 image", "no GetModuleFileNameA import", "no code cave"):
            with self.subTest(reason=reason), patch.object(
                patcher,
                "_apply_name_crash_immunity",
                return_value={"status": "skipped", "reason": reason},
            ):
                with self.assertRaises(patcher.PatcherError):
                    patcher._require_name_crash_immunity(
                        bytearray(), EXPECTED_BASENAME, []
                    )

        for result in (
            {"status": "applied"},
            {"status": "skipped", "reason": "already immune"},
        ):
            with self.subTest(result=result), patch.object(
                patcher,
                "_apply_name_crash_immunity",
                return_value=result,
            ):
                self.assertEqual(
                    patcher._require_name_crash_immunity(
                        bytearray(), EXPECTED_BASENAME, []
                    ),
                    result,
                )

    def test_partial_call_site_failure_is_fail_closed(self) -> None:
        """One unmappable site must abort the whole rewrite.

        The probe deliberately uses 0x27DD rather than 0x2944. 0x2944 is the
        save-folder call site, which is now REMOVED from the rewrite set
        before any writability check runs, so using it here would test
        nothing -- the earlier version of this test did exactly that and
        started passing for the wrong reason.
        """
        data = _synthetic_pe()
        original = bytes(data)
        with patch.object(
            patcher,
            "_nci_find_call_sites",
            # 0x2944 must be present or the drift guard fires first; the
            # rewrite set after exclusion is {0x27DD, 0x50967}.
            return_value=[
                IMAGE_BASE + 0x27DD,
                IMAGE_BASE + 0x2944,
                IMAGE_BASE + 0x50967,
            ],
        ):
            original_mapper = patcher._nci_rva_to_off
            with patch.object(
                patcher,
                "_nci_rva_to_off",
                side_effect=lambda info, rva: None
                if rva == 0x27DD
                else original_mapper(info, rva),
            ):
                result = patcher._apply_name_crash_immunity(
                    data, EXPECTED_BASENAME, []
                )
        self.assertEqual(result, {"status": "skipped", "reason": "call site not writable"})
        self.assertEqual(bytes(data), original)

    def test_the_save_folder_site_is_left_unwrapped(self) -> None:
        """#347: the published exe must use a folder named after ITSELF.

        Every other site stays wrapped, so the name-gated init path still sees
        the stock basename -- which is what makes the rename survivable for
        VV1/VV2/VV3, where exempting the whole wrapper is not an option.
        """
        for iat_rva, save_rva in patcher._NCI_SAVE_FOLDER_CALL_SITE_RVAS.items():
            with self.subTest(iat=hex(iat_rva)):
                sites = patcher._NCI_CALL_SITE_RVAS[iat_rva]
                self.assertIn(
                    save_rva,
                    sites,
                    "the save-folder site must be one of the discovered sites, "
                    "or the exclusion silently does nothing",
                )
                self.assertGreater(
                    len(sites),
                    1,
                    "excluding the only site would leave nothing wrapped",
                )

    def test_the_named_site_is_the_one_that_builds_the_save_folder(self) -> None:
        """Checked against the executables, not against the map itself.

        A map that is merely self-consistent would still pass while naming a
        CRT internal or the directory-only site -- mutation testing showed
        exactly that. The decisive evidence is the string "\\LDW": it appears
        ONCE in each image and is referenced ONCE, and that reference lies in
        the same function as the save-folder call. So the named site must be
        the `call [IAT]` nearest before that reference.
        """
        import struct

        stock = {
            0x5711C: "Virtual Villagers - A New Home.exe",
            0x7411C: "Virtual Villagers - The Lost Children.exe",
            0x7C130: "Virtual Villagers - The Secret City.exe",
        }
        root = Path(__file__).resolve().parents[1] / "research" / "stock-executables"
        for iat_rva, exe_name in stock.items():
            exe = root / exe_name
            if not exe.is_file():
                self.skipTest("%s is not available" % exe_name)
            blob = exe.read_bytes()
            with self.subTest(game=exe_name):
                pe = struct.unpack_from("<I", blob, 0x3C)[0]
                nsec = struct.unpack_from("<H", blob, pe + 6)[0]
                optsz = struct.unpack_from("<H", blob, pe + 20)[0]
                base = struct.unpack_from("<I", blob, pe + 24 + 28)[0]
                secs = []
                for i in range(nsec):
                    off = pe + 24 + optsz + i * 40
                    secs.append(struct.unpack_from("<IIII", blob, off + 8))

                def to_va(file_off):
                    for vsize, vaddr, rsize, rawoff in secs:
                        if rawoff <= file_off < rawoff + rsize:
                            return base + vaddr + (file_off - rawoff)
                    return None

                # "\LDW" must be unique, or "the reference" is not well defined.
                needle = b"\\LDW"
                self.assertEqual(
                    blob.count(needle), 1, "expected exactly one \\LDW string"
                )
                ldw_va = to_va(blob.index(needle))
                self.assertIsNotNone(ldw_va)
                refs = [
                    i
                    for i in range(len(blob) - 4)
                    if blob[i:i + 4] == struct.pack("<I", ldw_va)
                ]
                self.assertEqual(len(refs), 1, "expected exactly one reference")
                ref_off = refs[0]

                # The nearest `call [IAT]` before that reference.
                call = b"\xff\x15" + struct.pack("<I", base + iat_rva)
                before = [
                    i
                    for i in range(ref_off)
                    if blob[i:i + 6] == call
                ]
                self.assertTrue(before, "no import call before the \\LDW reference")
                nearest_va = to_va(before[-1])
                self.assertEqual(
                    nearest_va - base,
                    patcher._NCI_SAVE_FOLDER_CALL_SITE_RVAS[iat_rva],
                    "the map names a site that is not the one whose function "
                    "builds the save folder",
                )

    def test_every_wrapped_game_has_a_save_folder_exemption(self) -> None:
        """A game left out of the map keeps the reported bug.

        VV4 and VV5 are absent legitimately -- they are exempt from the
        wrapper entirely, so their save-folder sites already see the real
        name. Every game that IS wrapped needs an entry.
        """
        wrapped = {
            iat: rvas
            for iat, rvas in patcher._NCI_CALL_SITE_RVAS.items()
            if iat in (0x5711C, 0x7411C, 0x7C130)
        }
        self.assertEqual(
            set(wrapped),
            set(patcher._NCI_SAVE_FOLDER_CALL_SITE_RVAS),
            "a wrapped game is missing its save-folder exemption",
        )

    def test_a_drifted_save_folder_site_fails_closed(self) -> None:
        """If the map names a site the discovery does not return, stop.

        Silently wrapping everything would restore the reported bug; silently
        wrapping nothing would leave the rename unsurvivable. Neither is safe,
        so the wrapper declines and publication fails closed.
        """
        data = _synthetic_pe()
        original = bytes(data)
        with patch.object(
            patcher,
            "_nci_find_call_sites",
            return_value=[IMAGE_BASE + 0x27DD, IMAGE_BASE + 0x50967],
        ):
            result = patcher._apply_name_crash_immunity(data, EXPECTED_BASENAME, [])
        self.assertEqual(
            result,
            {
                "status": "skipped",
                "reason": "save-folder call site not among the discovered sites",
            },
        )
        self.assertEqual(bytes(data), original)


if __name__ == "__main__":
    unittest.main()
