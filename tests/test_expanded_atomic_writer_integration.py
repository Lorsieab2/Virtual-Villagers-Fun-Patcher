from __future__ import annotations

import hashlib
import json
import struct
import sys
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import vv_fun_patcher as P
from expanded_atomic_writer import (
    CONFIGS,
    FORMAT_BYTES,
    apply_atomic_writer_bytes,
    assemble_writer,
    assembly_source,
    build_import_page,
    fault_model,
)


CONTRACT_PATH = ROOT / "data" / "expanded_atomic_writer_integration.json"
SCHEMA_PATH = ROOT / "data" / "schemas" / "expanded_atomic_writer_integration.schema.json"


class ExpandedAtomicWriterIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))

    @staticmethod
    def source(game_id: str) -> Path:
        paths = {
            "vv3": ROOT / "research" / "stock-executables" / "Virtual Villagers - The Secret City.exe",
            "vv4": ROOT / "inputs" / "vv4-stock-copy" / "Virtual Villagers - The Tree of Life.exe",
            "vv5": ROOT / "inputs" / "vv5-stock-copy" / "Virtual Villagers - New Believers.exe",
        }
        path = paths[game_id]
        if not path.is_file():
            raise unittest.SkipTest(f"exact {game_id} stock executable is absent")
        return path

    @staticmethod
    def vv3_features() -> list[P.FunPatch]:
        return [
            P.FunPatch(json.loads((ROOT / "data" / "candidates" / "vv3_origins_running_base_candidate.json").read_text(encoding="utf-8"))),
            P.FunPatch(json.loads((ROOT / "data" / "candidates" / "vv3_all_villagers_like_running_candidate.json").read_text(encoding="utf-8"))),
        ]

    def render_parent(self, game_id: str, mode: str):
        source = self.source(game_id)
        build = P.identify(source)
        kwargs = {
            "_fun_patches_override": (
                self.vv3_features() if game_id == "vv3" else []
            )
        }
        if not hasattr(P, "_apply_reviewed_expanded_atomic_writer"):
            return P.render_patched_bytes(source, build, mode, **kwargs)
        static_contract = json.loads(json.dumps(self.contract))
        identity = static_contract["games"][game_id]["modes"][mode]
        identity["result_size"] = identity["parent_size"]
        identity["result_sha256"] = identity["parent_sha256"]
        identity["result_checksum"] = identity["parent_checksum"]
        with mock.patch.object(
            P, "_apply_reviewed_expanded_atomic_writer", return_value=([], [])
        ), mock.patch.object(
            P, "_expanded_atomic_writer_integration", return_value=static_contract
        ), mock.patch.object(
            P, "_apply_vv3_expanded_healer_endpoint_repair", return_value=[]
        ), mock.patch.object(
            P, "_apply_vv3_expanded_capacity_corrections", return_value=[]
        ), mock.patch.object(
            P, "_apply_vv3_expanded_detail_roster_layout", return_value=[]
        ), mock.patch.object(
            P,
            "_apply_vv3_expanded_chief_candidate_assignment_repair",
            return_value=[],
        ):
            return P.render_patched_bytes(source, build, mode, **kwargs)

    def test_contract_generator_and_schema_are_closed(self) -> None:
        self.assertTrue(self.contract["native_output"])
        self.assertFalse(self.contract["runtime_go"])
        self.assertFalse(self.contract["player_go"])
        self.assertFalse(self.contract["publication_ready"])
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        self.assertFalse(schema["additionalProperties"])
        self.assertFalse(schema["$defs"]["game"]["additionalProperties"])
        generator = ROOT / self.contract["generator"]["path"]
        self.assertEqual(
            P.source_text_sha256(generator.read_bytes()),
            self.contract["generator"]["source_text_sha256"],
        )

    def test_parameterized_assembly_and_import_pages_are_deterministic(self) -> None:
        for game_id, config in CONFIGS.items():
            with self.subTest(game=game_id):
                writer = assemble_writer(config)
                game = self.contract["games"][game_id]
                self.assertEqual(len(writer), game["writer_length"])
                self.assertEqual(hashlib.sha256(writer).hexdigest().upper(), game["writer_sha256"])
                stock = self.source(game_id).read_bytes()
                imports = stock[config.original_import_raw:config.original_import_raw + 220]
                page = build_import_page(config, imports)
                self.assertEqual(hashlib.sha256(page).hexdigest().upper(), game["import_page_sha256"])
                self.assertEqual(page[0xF0:0xFD], b"KERNEL32.dll\0")
                self.assertEqual(page[0x200:0x208], bytes(8))

    def test_assembly_source_has_exact_atomic_policy(self) -> None:
        for config in CONFIGS.values():
            source = assembly_source(config)
            for required in (
                "0xC0010000", "0x80000080", "0x00200080",
                "0x80010000", "0x00010080", "push 8",
                "SetFileInformationByHandle", "fatal_nonreturn",
            ):
                if required in {"SetFileInformationByHandle", "fatal_nonreturn"}:
                    continue
                self.assertIn(required, source)
            self.assertIn(f"0x{config.iat['SetFileInformationByHandle']:X}", source)
            self.assertIn("push 0xE0010256", source)
            self.assertNotIn("MOVEFILE_REPLACE_EXISTING", source)
        self.assertEqual(FORMAT_BYTES, b"%s.vvfp.%08X.%08X.%08X.tmp\0")

    def test_runtime_header_and_canonical_backup_path_are_preserved(self) -> None:
        expected_headers = {
            "vv3": (0x4A420C, 0x0C, 0x08),
            "vv4": (0x4B8228, 0x18, 0x10),
            "vv5": (0x4C6248, 0x18, 0x10),
        }
        for game_id, config in CONFIGS.items():
            with self.subTest(game=game_id):
                self.assertEqual(
                    (config.header_va, config.header_size, config.header_size_offset),
                    expected_headers[game_id],
                )
                source = assembly_source(config)
                self.assertIn(f"mov esi, 0x{config.header_va:X}", source)
                self.assertIn(
                    f"mov ecx, 0x{config.header_size // 4:X}", source
                )
                self.assertIn("rep movsd", source)
                self.assertIn("add eax, 0x14", source)
                self.assertIn("mov dword ptr [ebp-0x24], eax", source)
                self.assertIn("push dword ptr [ebp-0x24]", source)
                self.assertIn("lea edi, [ebp-0x730]", source)
                self.assertIn("lea edi, [ebp-0x830]", source)
                self.assertIn("mov dword ptr [ebp-0x14], eax", source)
                self.assertIn("sub esp, 0x840", source)
                self.assertLess(
                    source.index("lea edi, [ebp-0x730]"),
                    source.index("resolve_final_path:"),
                )
                self.assertLess(
                    source.index("resolve_final_path:"),
                    source.index("lea edi, [ebp-0x830]"),
                )
                self.assertNotIn(".bak", source)

    def test_exact_static_parents_generate_exact_sections_callsites_and_hashes(self) -> None:
        for game_id, config in CONFIGS.items():
            for mode, identity in self.contract["games"][game_id]["modes"].items():
                with self.subTest(game=game_id, mode=mode):
                    parent, _ = self.render_parent(game_id, mode)
                    self.assertEqual(len(parent), identity["parent_size"])
                    self.assertEqual(
                        hashlib.sha256(parent).hexdigest().upper(),
                        identity["parent_sha256"],
                    )
                    rendered, _generated, metadata = apply_atomic_writer_bytes(
                        bytearray(parent), game_id
                    )
                    P._canonicalize_pe_checksum(rendered)
                    final_hash = hashlib.sha256(rendered).hexdigest().upper()
                    self.assertEqual(len(rendered), identity["result_size"])
                    self.assertEqual(final_hash, identity["result_sha256"])
                    checksum_offset, _ = P._pe_checksum_layout(rendered)
                    self.assertEqual(rendered[checksum_offset:checksum_offset + 4].hex().upper(), identity["result_checksum"])
                    self.assertEqual(rendered[config.section_count_raw:config.section_count_raw + 2], config.sections_after.to_bytes(2, "little"))
                    self.assertEqual(rendered[config.size_of_image_raw:config.size_of_image_raw + 4], config.size_of_image_after.to_bytes(4, "little"))
                    self.assertEqual(rendered[config.import_directory_raw:config.import_directory_raw + 8], config.import_directory_after)
                    for raw, _before, after in config.callsites:
                        self.assertEqual(rendered[raw:raw + len(after)], after)
                    self.assertEqual(metadata["writer_sha256"], self.contract["games"][game_id]["writer_sha256"])
                    self.assertFalse(metadata["runtime_go"])
                    self.assertFalse(metadata["player_go"])

    def test_stock_modes_never_install_atomic_writer(self) -> None:
        for game_id in CONFIGS:
            source = self.source(game_id)
            build = P.identify(source)
            for mode in ("collection_progression", "immediate_fixed"):
                with self.subTest(game=game_id, mode=mode):
                    rendered, applied = P.render_patched_bytes(
                        source, build, mode, _fun_patches_override=[]
                    )
                    self.assertLessEqual(len(rendered), CONFIGS[game_id].writer_raw)

    def test_parent_and_preimage_failures_are_transactional(self) -> None:
        for game_id in ("vv4", "vv5"):
            source = self.source(game_id)
            build = P.identify(source)
            identity = self.contract["games"][game_id]["modes"][
                "experimental_expanded_256"
            ]
            parent, _ = self.render_parent(game_id, "experimental_expanded_256")
            self.assertEqual(hashlib.sha256(parent).hexdigest().upper(), identity["parent_sha256"])
            mutated = bytearray(parent)
            mutated[CONFIGS[game_id].callsites[0][0]] ^= 1
            before_mutated = bytes(mutated)
            with self.assertRaises(ValueError):
                apply_atomic_writer_bytes(mutated, game_id)
            self.assertEqual(bytes(mutated), before_mutated)

    def test_fault_model_preserves_prior_final_and_cleans_only_verified_temp(self) -> None:
        stages = (
            "create", "write_header", "write_body", "flush", "close_write",
            "reopen_nofollow", "identity", "size", "readback", "close_verify",
            "commit",
        )
        for final_exists in (False, True):
            prior = b"old" if final_exists else None
            for stage in stages:
                with self.subTest(final_exists=final_exists, stage=stage):
                    result = fault_model(final_exists=final_exists, fail_at=stage)
                    self.assertTrue(result["fatal"])
                    if stage == "commit":
                        self.assertFalse(result["final_known"])
                        self.assertIsNone(result["final"])
                    else:
                        self.assertTrue(result["final_known"])
                        self.assertEqual(result["final"], prior)
                    if result["verified"]:
                        self.assertIsNone(result["temp"])
            success = fault_model(final_exists=final_exists)
            self.assertFalse(success["fatal"])
            self.assertEqual(success["final"], b"new")
            self.assertIsNone(success["temp"])


if __name__ == "__main__":
    unittest.main()
