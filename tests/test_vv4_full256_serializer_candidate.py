import copy
import hashlib
import json
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.build_vv4_full256_serializer_candidate import (
    FINAL_SHA256,
    GATE,
    MODEL,
    PAGE_SHA256,
    READER,
    ROOT,
    WRAPPER,
    rel32,
    render_candidate,
    section_header,
    section_page,
    validate,
)


class CandidateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.data = json.loads(MODEL.read_text(encoding="utf-8"))

    def bad(self, mutate) -> None:
        data = copy.deepcopy(self.data)
        mutate(data)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "model.json"
            path.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaises(ValueError):
                validate(path)

    def test_model_is_static_go_but_all_runtime_and_publication_gates_stop(self) -> None:
        data = validate()
        self.assertEqual(data["status"], "static_serializer_reader_go_writer_stop")
        self.assertFalse(data["enabled"])
        self.assertFalse(data["native_output"])
        self.assertFalse(data["runtime_go"])
        self.assertFalse(data["player_go"])
        self.assertFalse(data["publication_eligible"])
        self.assertEqual(data["writer_model"]["status"], "blocked_pending_d355")

    def test_exact_caller_calls(self) -> None:
        self.assertEqual(rel32(0x41F125, 0x871180), "E856204500")
        self.assertEqual(rel32(0x41FD34, 0x871100), "E8C7134500")

    def test_exact_section_header_and_page_digest(self) -> None:
        self.assertEqual(
            section_header().hex().upper(),
            "2E7676347800000000100000001047000010000000300E0000000000000000000000000020000060",
        )
        page = section_page()
        self.assertEqual(len(page), 0x1000)
        self.assertEqual(hashlib.sha256(page).hexdigest().upper(), PAGE_SHA256)
        self.assertEqual(page[: len(WRAPPER)], WRAPPER)
        self.assertEqual(page[0x100 : 0x100 + len(READER)], READER)
        self.assertEqual(page[0x180 : 0x180 + len(GATE)], GATE)
        occupied = set(range(len(WRAPPER)))
        occupied.update(range(0x100, 0x100 + len(READER)))
        occupied.update(range(0x180, 0x180 + len(GATE)))
        self.assertTrue(all(byte == 0 for index, byte in enumerate(page) if index not in occupied))

    def test_exact_direct_call_targets_and_gate_stack_paths(self) -> None:
        def target(payload: bytes, va: int, offset: int) -> int:
            self.assertEqual(payload[offset], 0xE8)
            displacement = struct.unpack_from("<i", payload, offset + 1)[0]
            return va + offset + 5 + displacement

        self.assertEqual(target(WRAPPER, 0x871000, 0x24), 0x45EAA0)
        self.assertEqual(target(WRAPPER, 0x871000, 0x29), 0x41FE70)
        self.assertEqual(target(WRAPPER, 0x871000, 0x3C), 0x45DB30)
        self.assertEqual(target(WRAPPER, 0x871000, 0x59), 0x41FE70)
        self.assertEqual(target(READER, 0x871100, 0x0F), 0x45D8A0)
        self.assertEqual(target(READER, 0x871100, 0x27), 0x41FE70)
        self.assertEqual(target(READER, 0x871100, 0x4C), 0x45DBE0)
        self.assertEqual(target(GATE, 0x871180, 0x04), 0x871000)
        self.assertEqual(GATE[:4], bytes.fromhex("FF742404"))
        self.assertIn(bytes.fromhex("84C07403C20400"), GATE)
        self.assertTrue(GATE.endswith(bytes.fromhex("83C40831C05F5EC20400")))

    def test_wrong_parent_is_rejected_before_render(self) -> None:
        with self.assertRaisesRegex(ValueError, "wrong parent"):
            render_candidate(bytes(0xE3000))

    def test_enable_rejected(self) -> None:
        self.bad(lambda data: data.update(enabled=True))

    def test_native_output_rejected(self) -> None:
        self.bad(lambda data: data.update(native_output=True))

    def test_composed_parent_rejected(self) -> None:
        self.bad(lambda data: data["parent"].update(sha256="0" * 64))

    def test_section_overlap_rejected(self) -> None:
        self.bad(lambda data: data["section"].update(raw_start=0xE2FFF))

    def test_header_guard_rejected(self) -> None:
        self.bad(lambda data: data["section"].update(header_guard="00" * 39 + "01"))

    def test_section_header_rejected(self) -> None:
        self.bad(lambda data: data["section"].update(final_header_bytes="00" * 40))

    def test_page_digest_rejected(self) -> None:
        self.bad(lambda data: data["section"].update(page_sha256="0" * 64))

    def test_pe_guard_rejected(self) -> None:
        self.bad(lambda data: data["pe_guards"].update(section_count_before=6))

    def test_hook_preimage_rejected(self) -> None:
        self.bad(lambda data: data["hooks"][0].update(before="90" * 5))

    def test_hook_target_rejected(self) -> None:
        self.bad(lambda data: data["hooks"][1].update(target=0x871101))

    def test_routine_bytes_rejected(self) -> None:
        self.bad(lambda data: data["exact_routines"]["serializer"].update(bytes="90"))

    def test_gate_digest_rejected(self) -> None:
        self.bad(lambda data: data["exact_routines"]["serializer_failure_gate"].update(sha256="0" * 64))

    def test_d353_helper_hash_rejected(self) -> None:
        self.bad(lambda data: data["d353_helpers"]["decode"].update(sha256="0" * 64))

    def test_instruction_model_truncation_rejected(self) -> None:
        self.bad(lambda data: data["wrapper_model"]["serializer"].update(instruction_model=[]))

    def test_register_contract_rejected(self) -> None:
        self.bad(lambda data: data["wrapper_model"]["serializer"].update(preserves=["EBX"]))

    def test_tail_semantics_rejected(self) -> None:
        self.bad(lambda data: data["wrapper_model"]["deserializer"].update(full_256_unterminated="read tail"))

    def test_final_bytes_rejected(self) -> None:
        self.bad(lambda data: data["final"].update(serializer_bytes="90"))

    def test_final_candidate_digest_rejected(self) -> None:
        self.bad(lambda data: data["final"].update(candidate_sha256="0" * 64))

    def test_checksum_pin_rejected(self) -> None:
        self.bad(lambda data: data["uninstall"].update(checksum_after="00000000"))

    def test_atomic_writer_blocker_removal_rejected(self) -> None:
        self.bad(lambda data: data["blocked_evidence"].pop())

    def test_writer_guard_rejected(self) -> None:
        self.bad(lambda data: data["writer_model"]["entry"].update(before="90" * 6))

    def test_writer_target_placeholder_rejected(self) -> None:
        self.bad(lambda data: data["writer_model"]["entry"].update(target=0x871200))

    def test_writer_resolver_placeholder_rejected(self) -> None:
        self.bad(lambda data: data["writer_model"].update(resolver_bytes="90"))

    def test_replace_existing_weakening_rejected(self) -> None:
        self.bad(lambda data: data["writer_model"]["atomic_contract"].update(final_absent="MoveFileExA replace existing"))

    def test_nonfatal_writer_failure_rejected(self) -> None:
        self.bad(lambda data: data["writer_model"]["atomic_contract"].update(failure_policy="return false and continue"))

    def test_record_sized_terminator_rejected(self) -> None:
        self.bad(lambda data: data["wrapper_model"]["serializer"].update(terminator="write zero 0x104 record"))

    def test_clear_reset_order_rejected(self) -> None:
        self.bad(lambda data: data["wrapper_model"]["deserializer"].update(clear_before_reset="reset then clear"))

    def test_unchecked_close_rejected(self) -> None:
        self.bad(lambda data: data["writer_model"]["atomic_contract"]["required_sequence"].remove("checked CloseHandle verification handle"))

    def test_identity_check_rejected(self) -> None:
        self.bad(lambda data: data["writer_model"]["atomic_contract"]["required_sequence"].remove("verify volume serial and FileId identity"))

    def test_replace_tuple_rejected(self) -> None:
        self.bad(lambda data: data["writer_model"]["atomic_contract"].update(final_exists="ReplaceFileA flags0"))

    def test_caller_ledger_rejected(self) -> None:
        self.bad(lambda data: data["writer_model"]["caller_ledger"]["sites"].pop())

    def test_cli_requires_dry_run(self) -> None:
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts/build_vv4_full256_serializer_candidate.py")],
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(result.returncode, 0)

    def test_cli_dry_run(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts/build_vv4_full256_serializer_candidate.py"),
                "--dry-run",
            ],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("STOP", result.stdout)
        self.assertIn("atomic writer", result.stdout)

    def test_final_hash_constant_is_exact(self) -> None:
        self.assertEqual(
            FINAL_SHA256,
            "364E35167E4DA8D9407030E42D41306A78FB50B73C7532B2D5166729EA447C43",
        )


if __name__ == "__main__":
    unittest.main()
