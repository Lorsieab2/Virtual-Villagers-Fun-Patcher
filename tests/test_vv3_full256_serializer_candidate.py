import copy
import hashlib
import importlib.util
import json
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "builder", ROOT / "scripts" / "build_vv3_full256_serializer_candidate.py"
)
B = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(B)


class Full256StaticCandidateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.value = B.build()

    def bad(self, mutate) -> None:
        value = copy.deepcopy(self.value)
        mutate(value)
        with self.assertRaises(ValueError):
            B.validate(value)

    def test_checked_in_model_is_deterministic(self) -> None:
        self.assertEqual(
            self.value,
            json.loads(B.OUTPUT.read_text(encoding="utf-8")),
        )
        self.assertEqual(B.validate(), self.value)

    def test_disabled_everywhere(self) -> None:
        self.assertFalse(self.value["enabled"])
        self.assertFalse(self.value["catalog_visible"])
        self.assertFalse(self.value["native_output"])
        self.assertEqual(self.value["decision"]["status"], "STOP")
        self.assertFalse(self.value["decision"]["atomic_writer_go"])
        self.assertFalse(self.value["decision"]["whole_load_rollback_go"])

    def test_exact_parents_and_results(self) -> None:
        self.assertEqual(
            [(row["mode"], row["sha256"], row["pe_checksum_before"], row["pe_checksum_after"], row["result_sha256"]) for row in self.value["parents"]],
            [(mode, parent, before, after, result) for mode, parent, before, after, result in B.PARENTS],
        )
        self.assertTrue(
            all(
                row["size"] == "0xCC000"
                and row["sections"] == 6
                and row["size_of_image"] == "0x3B9000"
                and row["result_size"] == "0xCD000"
                and row["result_sections"] == 7
                and row["result_size_of_image"] == "0x3BA000"
                for row in self.value["parents"]
            )
        )

    def test_manifest_binding_preserves_1263_rows(self) -> None:
        self.assertEqual(
            self.value["expanded_manifest"],
            {"path": "data/expanded_256.json", "row_count": 1263, "rows_sha256": B.MANIFEST_ROWS_SHA256},
        )

    def test_section_plan_and_header_are_exact(self) -> None:
        section = self.value["section_plan"]
        self.assertEqual(
            (section["name"], section["header_raw"], section["raw_start"], section["raw_end"], section["rva"], section["va"], section["characteristics"]),
            (".vv3sv", "0x2F0", "0xCC000", "0xCD000", "0x3B9000", "0x7B9000", "RX"),
        )
        self.assertEqual(bytes.fromhex(section["header_bytes"]), B.SECTION_HEADER)
        self.assertEqual(section["section_sha256"], B.PAGE_SHA256)

    def test_section_page_layout_and_digest(self) -> None:
        page = B.section_page()
        self.assertEqual(len(page), 0x1000)
        self.assertEqual(hashlib.sha256(page).hexdigest().upper(), B.PAGE_SHA256)
        self.assertEqual(page[: len(B.SERIALIZER)], B.SERIALIZER)
        self.assertEqual(page[0x200 : 0x200 + len(B.READER)], B.READER)
        self.assertEqual(page[0x3C0 : 0x3C0 + len(B.GATE)], B.GATE)

    def test_exact_hook_calls(self) -> None:
        self.assertEqual(B.rel32(0x427D57, 0x7B93C0), "E864163900")
        self.assertEqual(B.rel32(0x428A4C, 0x7B9200), "E8AF073900")
        self.assertEqual(
            [(row["raw"], row["preimage"], row["after"], row["target"]) for row in self.value["hooks"]],
            [
                ("0x27D57", "E824720300", "E864163900", "0x7B93C0"),
                ("0x28A4C", "E80F3E0300", "E8AF073900", "0x7B9200"),
            ],
        )

    def test_exact_routine_lengths_and_hashes(self) -> None:
        routines = self.value["exact_routines"]
        for name, payload in (("serializer", B.SERIALIZER), ("deserializer", B.READER), ("serializer_failure_gate", B.GATE)):
            self.assertEqual(routines[name]["length"], len(payload))
            self.assertEqual(bytes.fromhex(routines[name]["bytes"]), payload)
            self.assertEqual(routines[name]["sha256"], hashlib.sha256(payload).hexdigest().upper())

    def test_exact_direct_call_targets(self) -> None:
        def target(payload: bytes, va: int, offset: int) -> int:
            self.assertEqual(payload[offset], 0xE8)
            return va + offset + 5 + struct.unpack_from("<i", payload, offset + 1)[0]

        self.assertEqual(target(B.SERIALIZER, 0x7B9000, 0x0A), 0x428B60)
        self.assertEqual(target(B.SERIALIZER, 0x7B9000, 0x2B), 0x455DD0)
        self.assertEqual(target(B.SERIALIZER, 0x7B9000, 0x3D), 0x455460)
        self.assertEqual(target(B.READER, 0x7B9200, 0x0A), 0x428B60)
        self.assertEqual(target(B.READER, 0x7B9200, 0x42), 0x456000)
        self.assertEqual(target(B.READER, 0x7B9200, 0x6D), 0x456830)
        self.assertEqual(target(B.GATE, 0x7B93C0, 0x04), 0x7B9000)

    def test_abis_exact(self) -> None:
        self.assertEqual(
            B.ABIS,
            tuple((row["id"], row["start"], row["end"], row["sha256"], row["contract"]) for row in self.value["abis"]),
        )

    def test_wrapper_semantics_are_bounded(self) -> None:
        wrapper = self.value["wrapper_model"]
        self.assertEqual(wrapper["logical_indices"], "0..255")
        self.assertEqual(wrapper["padding"], "256..259 forbidden")
        self.assertIn("count==256 returns AL=1 without tail write", wrapper["serializer"])
        self.assertIn("record 257 and tail are never read or written", wrapper["deserializer"])

    def test_save_failure_gate_is_exact(self) -> None:
        gate = self.value["caller_failure_gate"]
        self.assertTrue(gate["load_caller_tests_al"])
        self.assertTrue(gate["save_caller_tests_al"])
        self.assertTrue(gate["recoverable_failure"])
        self.assertEqual(gate["save_caller_patch_raw"], "0x27D57")
        self.assertEqual(gate["save_caller_after"], "E864163900")

    def test_atomic_writer_remains_null_and_disabled(self) -> None:
        writer = self.value["atomic_writer_plan"]
        self.assertFalse(writer["enabled"])
        self.assertFalse(writer["native_output"])
        self.assertEqual(writer["stock_writer"], "0x403530")
        self.assertIsNone(writer["dynamic_api_resolver_bytes"])
        self.assertIsNone(writer["wrapper_bytes"])
        self.assertIsNone(writer["wrapper_sha256"])
        self.assertIsNone(writer["import_changes"])

    def test_writer_callsites_remain_expectations_not_emission(self) -> None:
        rows = self.value["atomic_writer_plan"]["callsites"]
        self.assertTrue(B.validate_writer_callsites(self.value))
        self.assertTrue(all(row["emitted"] is None for row in rows))
        self.assertEqual(
            [(row["raw"], row["preimage"], row["expected"]) for row in rows],
            [
                ("0x27C7D", "E8AEB8FDFF", "E87E173900"),
                ("0x27C92", "E899B8FDFF", "E869173900"),
                ("0x27D6C", "E8BFB7FDFF", "E88F163900"),
                ("0x27D81", "E8AAB7FDFF", "E87A163900"),
            ],
        )

    def test_whole_load_rollback_remains_null_stop(self) -> None:
        rollback = self.value["whole_load_rollback"]
        self.assertEqual(rollback["status"], "STOP")
        self.assertTrue(all(value is None for key, value in rollback.items() if key != "status"))

    def test_each_writer_preimage_mutation_fails_closed(self) -> None:
        for index in range(4):
            changed = copy.deepcopy(self.value)
            changed["atomic_writer_plan"]["callsites"][index]["preimage"] = "00" * 5
            self.assertFalse(B.validate_writer_callsites(changed), index)
            with self.assertRaises(ValueError):
                B.validate(changed)

    def test_static_page_mutation_fails_closed(self) -> None:
        self.bad(lambda value: value["exact_routines"]["serializer"].update(bytes="90"))

    def test_parent_rebind_fails_closed(self) -> None:
        self.bad(lambda value: value["parents"][0].update(sha256="0" * 64))

    def test_manifest_rebind_fails_closed(self) -> None:
        self.bad(lambda value: value["expanded_manifest"].update(row_count=1262))

    def test_atomic_writer_claim_fails_closed(self) -> None:
        self.bad(lambda value: value["atomic_writer_plan"].update(enabled=True))

    def test_whole_load_rollback_claim_fails_closed(self) -> None:
        self.bad(lambda value: value["whole_load_rollback"].update(status="GO"))

    def test_wrong_parent_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "wrong parent"):
            B.render_candidate(bytes(0xCC000), B.PARENTS[0][0])

    def _render_exact_parents(self) -> list[tuple[str, bytes]]:
        stock = ROOT / "research" / "stock-executables" / "Virtual Villagers - The Secret City.exe"
        if not stock.is_file():
            self.skipTest("exact VV3 stock executable is not present")
        sys.path.insert(0, str(ROOT / "src"))
        from vv_fun_patcher import FunPatch, load_builds, render_patched_bytes

        build = next(item for item in load_builds() if item.id == "vv3")
        features = [
            FunPatch(json.loads((ROOT / "data" / "candidates" / "vv3_origins_running_base_candidate.json").read_text(encoding="utf-8"))),
            FunPatch(json.loads((ROOT / "data" / "candidates" / "vv3_all_villagers_like_running_candidate.json").read_text(encoding="utf-8"))),
        ]
        return [
            (mode, bytes(render_patched_bytes(stock, build, mode, _fun_patches_override=features)[0]))
            for mode, *_ in B.PARENTS
        ]

    def test_source_bound_renderer_matches_both_exact_results(self) -> None:
        expected = {row["mode"]: row for row in self.value["parents"]}
        atomic = json.loads(
            (ROOT / "data" / "expanded_atomic_writer_integration.json").read_text(
                encoding="utf-8"
            )
        )["games"]["vv3"]["modes"]
        for mode, rendered in self._render_exact_parents():
            with self.subTest(mode=mode):
                self.assertEqual(atomic[mode]["parent_sha256"], expected[mode]["result_sha256"])
                self.assertEqual(len(rendered), atomic[mode]["result_size"])
                self.assertEqual(
                    hashlib.sha256(rendered).hexdigest().upper(),
                    atomic[mode]["result_sha256"],
                )
                self.assertEqual(rendered[0xCC000:0xCC400], B.section_page()[:0x400])
                self.assertEqual(rendered[0x27D57:0x27D5C].hex().upper(), "E864163900")
                self.assertEqual(rendered[0x28A4C:0x28A51].hex().upper(), "E8AF073900")

    def test_check_rejects_stale_model(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "candidate.json"
            path.write_text("{}", encoding="utf-8")
            with self.assertRaises(ValueError):
                B.main(["--check", "--output", str(path)])

    def test_cli_check_and_dry_run(self) -> None:
        checked = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "build_vv3_full256_serializer_candidate.py"), "--check"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(checked.returncode, 0, checked.stderr)
        dry = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "build_vv3_full256_serializer_candidate.py"), "--dry-run"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(dry.returncode, 0, dry.stderr)
        self.assertIn("STOP", dry.stdout)
        self.assertIn("whole-load rollback", dry.stdout)

    def test_json_parses(self) -> None:
        json.loads(B.OUTPUT.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
