from __future__ import annotations

import hashlib
import json
import struct
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import vv_fun_patcher as P


CONTRACT_PATH = ROOT / "data" / "expanded_256_static_repair_integration.json"
SCHEMA_PATH = ROOT / "data" / "schemas" / "expanded_256_static_repair_integration.schema.json"


class ExpandedStaticRepairIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
        self.atomic_contract = json.loads(
            P.EXPANDED_ATOMIC_WRITER_INTEGRATION_PATH.read_text(encoding="utf-8")
        )

    def test_contract_is_closed_and_runtime_fail_closed(self) -> None:
        self.assertEqual(
            set(self.contract),
            {
                "schema", "status", "native_output", "runtime_go", "player_go",
                "publication_ready", "games",
            },
        )
        self.assertEqual(
            self.contract["schema"],
            "vvfp.expanded_256_static_repair_integration.v1",
        )
        self.assertTrue(self.contract["native_output"])
        self.assertFalse(self.contract["runtime_go"])
        self.assertFalse(self.contract["player_go"])
        self.assertFalse(self.contract["publication_ready"])
        self.assertEqual(set(self.contract["games"]), {"vv3", "vv4", "vv5"})
        self.assertEqual(
            P.source_text_sha256(CONTRACT_PATH.read_bytes()),
            P.EXPANDED_STATIC_REPAIR_INTEGRATION_SHA256,
        )
        loaded = P._expanded_static_repair_integration()
        self.assertEqual(loaded, self.contract)
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        self.assertFalse(schema["additionalProperties"])
        self.assertFalse(schema["$defs"]["game"]["additionalProperties"])
        self.assertFalse(schema["$defs"]["mode"]["additionalProperties"])

    def test_contract_rejects_identity_drift(self) -> None:
        changed = json.loads(json.dumps(self.contract))
        changed["games"]["vv5"]["manifest_rows_sha256"] = "0" * 64
        with tempfile.TemporaryDirectory() as directory:
            fake_path = Path(directory) / "contract.json"
            fake_path.write_text(json.dumps(changed), encoding="utf-8")
            with mock.patch.object(P, "EXPANDED_STATIC_REPAIR_INTEGRATION_PATH", fake_path), mock.patch.object(
                P,
                "EXPANDED_STATIC_REPAIR_INTEGRATION_SHA256",
                P.source_text_sha256(fake_path.read_bytes()),
            ):
                with self.assertRaisesRegex(P.PatcherError, "manifest binding is stale"):
                    P._expanded_static_repair_integration()

    @staticmethod
    def _source(game_id: str) -> Path:
        names = {
            "vv3": ROOT / "research" / "stock-executables" / "Virtual Villagers - The Secret City.exe",
            "vv4": ROOT / "inputs" / "vv4-stock-copy" / "Virtual Villagers - The Tree of Life.exe",
            "vv5": ROOT / "inputs" / "vv5-stock-copy" / "Virtual Villagers - New Believers.exe",
        }
        source = names[game_id]
        if not source.is_file():
            raise unittest.SkipTest(f"exact {game_id} stock executable is not present")
        return source

    def test_real_vv4_vv5_expanded_renders_apply_reviewed_repairs(self) -> None:
        for game_id in ("vv4", "vv5"):
            source = self._source(game_id)
            build = P.identify(source)
            game = self.contract["games"][game_id]
            for mode_id, identity in game["modes"].items():
                with self.subTest(game=game_id, mode=mode_id):
                    rendered, applied = P.render_patched_bytes(source, build, mode_id)
                    final_sha = hashlib.sha256(rendered).hexdigest().upper()
                    atomic_identity = self.atomic_contract["games"][game_id]["modes"][mode_id]
                    self.assertEqual(final_sha, atomic_identity["result_sha256"])
                    repairs = P._expanded_static_repair_summary(applied, final_sha)
                    self.assertEqual(len(repairs), 1)
                    self.assertEqual(repairs[0]["repair_id"], game["repair_id"])
                    self.assertEqual(repairs[0]["stage_parent_sha256"], identity["parent_sha256"])
                    self.assertEqual(repairs[0]["stage_result_sha256"], identity["result_sha256"])
                    self.assertEqual(repairs[0]["final_sha256"], final_sha)
                    self.assertFalse(repairs[0]["runtime_go"])
                    self.assertFalse(repairs[0]["player_go"])

    def test_real_vv3_composed_expanded_renders_apply_reviewed_save_repair(self) -> None:
        source = self._source("vv3")
        build = next(item for item in P.load_builds() if item.id == "vv3")
        features = [
            P.FunPatch(json.loads((ROOT / "data" / "candidates" / "vv3_origins_running_base_candidate.json").read_text(encoding="utf-8"))),
            P.FunPatch(json.loads((ROOT / "data" / "candidates" / "vv3_all_villagers_like_running_candidate.json").read_text(encoding="utf-8"))),
        ]
        game = self.contract["games"]["vv3"]
        final_with_post_repairs = {
            "experimental_expanded_256": "AAD29CC8A55ABA7F20087A8FDE595BB84405813B9D544A9674B9D6C8E293EF71",
            "experimental_expanded_256_progression": "3483E19B58074B41F73EA5472FDC5385B05E5517D33EF8A6B304C49F0B160A47",
        }
        for mode_id, identity in game["modes"].items():
            with self.subTest(mode=mode_id):
                rendered, applied = P.render_patched_bytes(
                    source,
                    build,
                    mode_id,
                    _fun_patches_override=features,
                )
                final_sha = hashlib.sha256(rendered).hexdigest().upper()
                atomic_identity = self.atomic_contract["games"]["vv3"]["modes"][mode_id]
                self.assertEqual(len(rendered), atomic_identity["result_size"])
                self.assertEqual(final_sha, final_with_post_repairs[mode_id])
                before_healer_repair = bytearray(rendered)
                before_healer_repair[0x5FA46:0x5FA4A] = bytes.fromhex("807B1F00")
                for patch in P.VV3_EXPANDED_CAPACITY_CORRECTIONS:
                    offset = int(patch["offset"], 0)
                    before_healer_repair[
                        offset : offset + len(bytes.fromhex(patch["before"]))
                    ] = bytes.fromhex(patch["before"])
                P._canonicalize_pe_checksum(before_healer_repair)
                self.assertEqual(
                    hashlib.sha256(before_healer_repair).hexdigest().upper(),
                    atomic_identity["result_sha256"],
                )
                repairs = P._expanded_static_repair_summary(applied, final_sha)
                self.assertEqual([item["repair_id"] for item in repairs], [game["repair_id"]])
                self.assertEqual(repairs[0]["stage_result_sha256"], identity["result_sha256"])

    def test_stock_modes_never_apply_expanded_repairs(self) -> None:
        for game_id in ("vv3", "vv4", "vv5"):
            source = self._source(game_id)
            build = P.identify(source)
            for mode_id in ("collection_progression", "immediate_fixed"):
                with self.subTest(game=game_id, mode=mode_id):
                    rendered, applied = P.render_patched_bytes(source, build, mode_id)
                    self.assertEqual(
                        P._expanded_static_repair_summary(
                            applied, hashlib.sha256(rendered).hexdigest().upper()
                        ),
                        [],
                    )

    def test_stage_parent_mutation_is_rejected_transactionally(self) -> None:
        source = self._source("vv5")
        build = P.identify(source)
        mode = "experimental_expanded_256"
        variant = P.get_patch_variant(build, mode)
        stage = bytearray(source.read_bytes())
        for patch in P._expanded_patches(build, variant):
            offset = int(patch["offset"], 0)
            before = P._patch_bytes(patch, "before")
            after = P._patch_bytes(patch, "after")
            self.assertEqual(bytes(stage[offset : offset + len(before)]), before)
            stage[offset : offset + len(after)] = after
        P._canonicalize_pe_checksum(stage)
        stage[0x1000] ^= 1
        snapshot = bytes(stage)
        with self.assertRaisesRegex(P.PatcherError, "parent guard failed"):
            P._apply_reviewed_expanded_static_repair(
                stage, build, mode, "post_manifest", set()
            )
        self.assertEqual(bytes(stage), snapshot)

    def test_static_render_reports_repair_while_public_dry_run_stays_closed(self) -> None:
        source = self._source("vv4")
        mode = "experimental_expanded_256"
        with self.assertRaisesRegex(P.PatcherError, "publication is disabled"):
            P.dry_run(source, mode)
        build = P.identify(source)
        patched, applied = P.render_patched_bytes(source, build, mode)
        result_sha256 = hashlib.sha256(patched).hexdigest().upper()
        self.assertEqual(
            result_sha256,
            self.atomic_contract["games"]["vv4"]["modes"][mode]["result_sha256"],
        )
        self.assertEqual(
            [
                item["repair_id"]
                for item in P._expanded_static_repair_summary(applied, result_sha256)
            ],
            ["vv4_full256_serializer_reader_gate"],
        )
        self.assertEqual(
            [
                item["atomic_writer_id"]
                for item in P._expanded_atomic_writer_summary(applied, result_sha256)
            ],
            ["vv4_expanded_atomic_writer"],
        )

    def test_c342_and_manifest_pins_remain_exact(self) -> None:
        self.assertEqual(
            P.VV4_ORIGINS_RELOCATION_LEDGER_SHA256,
            "CEE01F4AEC59CB1CEE0F42E3DDDB3A24615261E628ED0629C1BFAABF421A897D",
        )
        self.assertEqual(
            P.VV5_ORIGINS_RELOCATION_LEDGER_SHA256,
            "14E460773ADC065E053FA30921ED01D33A5F36AD49DC754CCD69127EA02C01B7",
        )
        self.assertEqual(
            self.contract["games"]["vv4"]["manifest_rows_sha256"],
            P.EXPANDED_MANIFEST_IDENTITIES["vv4"]["patches_sha256"],
        )
        self.assertEqual(
            self.contract["games"]["vv5"]["manifest_rows_sha256"],
            P.EXPANDED_MANIFEST_IDENTITIES["vv5"]["patches_sha256"],
        )

    def test_vv4_stock_and_current_parent_singleton_hashes_are_distinctly_bound(self) -> None:
        game = self.contract["games"]["vv4"]
        helper = game["helper_lineage"]
        candidate = json.loads(
            (ROOT / game["candidate_path"]).read_text(encoding="utf-8")
        )
        self.assertEqual(
            candidate["d353_helpers"]["singleton"]["sha256"],
            helper["stock_sha256"],
        )
        self.assertEqual(helper["manifest_row_raw"], "0x1FE9B")
        self.assertEqual(helper["manifest_before"], "C8710100")
        self.assertEqual(helper["manifest_after"], "70DD0100")
        self.assertEqual(
            helper["current_parent_sha256"],
            "C7F59E4CCE21060EC4A0D8C71B78F995ADF5DFB2B8C8F2EC4C64ED7E35C98E5F",
        )
        self.assertNotEqual(helper["stock_sha256"], helper["current_parent_sha256"])
        self.assertTrue(helper["abi_control_flow_unchanged"])


if __name__ == "__main__":
    unittest.main()
