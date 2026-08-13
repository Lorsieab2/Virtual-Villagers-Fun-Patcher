from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from vv3_expanded_256_evidence import REQUIRED_INDEX_PATHS, REQUIRED_PADDING_PATHS, canonical_json_bytes
from tests.test_vv3_expanded_256_evidence import _authenticated_fixture


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "validate_vv3_stored_index_evidence_gate",
    ROOT / "scripts" / "validate_vv3_stored_index_evidence_gate.py",
)
GATE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = GATE
SPEC.loader.exec_module(GATE)


def _observation(index: int, artifact_id: str) -> dict[str, object]:
    return {
        "ea": f"0x{0x401000 + index:X}",
        "file_offset": f"0x{0x1000 + index:X}",
        "raw_bytes": "90",
        "artifact_id": artifact_id,
        "xref_set_complete": True,
        "xrefs": [
            {"ea": f"0x{0x402000 + index:X}", "kind": "code"},
            {"ea": f"0x{0x403000 + index:X}", "kind": "data"},
        ],
    }


def _candidate(contract: dict[str, object], anchor: dict[str, object]) -> dict[str, object]:
    artifact_id = anchor["artifact_ids"][0]
    paths = []
    for ordinal, path_id in enumerate(REQUIRED_INDEX_PATHS, start=1):
        paths.append(
            {
                "ordinal": ordinal,
                "id": path_id,
                "status": "observed",
                "derivation": {
                    "game_id": "vv3",
                    "source_kind": "authenticated_native_observation",
                    "cross_game_source": None,
                    "inferred": False,
                },
                "width_bits": 16,
                "sentinel": {
                    "kind": "none",
                    "width_bits": 16,
                    "signed": False,
                    "value": None,
                    "raw_bytes": None,
                    "source": "authenticated_vv3_observation",
                    "observation_refs": [artifact_id],
                },
                "record_255": {
                    "accepted": True,
                    "saveable": True,
                    "observation_refs": [artifact_id],
                },
                "observations": [_observation(ordinal, artifact_id)],
            }
        )
    source_files = contract["source_provenance"]["source_files"]
    receipt_hash = next(
        item["sha256"]
        for item in source_files
        if item["path"] == "data/vv3_expanded_256_runtime_receipt.schema.json"
    )
    return {
        "schema": GATE.CANDIDATE_SCHEMA,
        "schema_version": GATE.CANDIDATE_SCHEMA_VERSION,
        "status": "observed",
        "evidence_class": "authenticated_vv3_native_observation",
        "synthetic": False,
        "ambiguous": False,
        "incomplete": False,
        "provenance": {
            "game_id": "vv3",
            "source_sha256": anchor["source_sha256"],
            "prototype_sha256": anchor["prototype_sha256"],
            "evidence_sha256": anchor["evidence_sha256"],
            "exporter_manifest_sha256": anchor["exporter_manifest_sha256"],
            "exporter_manifest_file_sha256": anchor["exporter_manifest_file_sha256"],
            "exporter_producer": anchor["exporter_producer"],
            "exporter_run_id": anchor["exporter_run_id"],
            "authenticated_by": "validate_evidence_file",
        },
        "paths": paths,
        "serializer_binding": {
            "id": "serializer",
            "status": "observed",
            "record_255_saved": True,
            "padding_saved": False,
            "observations": [_observation(100, artifact_id)],
        },
        "padding_records": [
            {
                "index": index,
                "reachable": False,
                "saveable": False,
                "required_path_refs": list(REQUIRED_PADDING_PATHS),
                "observation_refs": [artifact_id],
            }
            for index in GATE.PADDING_INDICES
        ],
        "receipt_binding": {
            "schema": GATE.RECEIPT_SCHEMA,
            "schema_sha256": receipt_hash,
            "receipt_id": "future-player-receipt-1",
            "stage_ids": list(GATE.RECEIPT_STAGE_IDS),
            "player_confirmed": True,
        },
    }


class VV3StoredIndexEvidenceGateTests(unittest.TestCase):
    def test_source_provenance_hash_uses_vvfp_source_text_v1(self) -> None:
        expected = GATE.hashlib.sha256(b"alpha\nbeta\n").hexdigest().upper()
        variants = (
            b"alpha\nbeta\n",
            b"alpha\r\nbeta\r\n",
            b"alpha\rbeta\r",
            b"\xef\xbb\xbfalpha\r\nbeta\r\n",
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "source.txt"
            for content in variants:
                with self.subTest(content=content):
                    source.write_bytes(content)
                    self.assertEqual(GATE._hash_repo_file("source.txt", root), expected)
            source.write_bytes(b"\xff\xfeinvalid")
            with self.assertRaisesRegex(GATE.StoredIndexGateError, "not valid UTF-8"):
                GATE._hash_repo_file("source.txt", root)

    def setUp(self) -> None:
        self.contract = copy.deepcopy(GATE.load_contract())
        self.anchor = {
            "evidence_sha256": "A" * 64,
            "exporter_manifest_path": "manifests/exporter.json",
            "exporter_manifest_sha256": "B" * 64,
            "exporter_manifest_file_sha256": "C" * 64,
            "exporter_producer": "vv3-ida-exporter",
            "exporter_run_id": "authenticated-run",
            "source_sha256": GATE.VV3_SOURCE_SHA256,
            "prototype_sha256": GATE.VV3_PROTOTYPE_SHA256,
            "artifact_ids": ["capture-1"],
        }

    def _recanonicalize(self, contract: dict[str, object]) -> None:
        contract["integrity"]["canonical_sha256"] = GATE._canonical_digest(contract)

    def test_canonical_contract_is_exact_and_stop(self) -> None:
        summary = GATE.validate_contract(self.contract, root=ROOT)
        self.assertTrue(summary["contract_valid"])
        self.assertEqual(summary["paths"], 10)
        self.assertFalse(summary["gate_ready"])
        self.assertFalse(summary["runtime_go"])
        self.assertFalse(summary["player_go"])
        self.assertFalse(summary["publication_ready"])
        self.assertEqual(summary["status"], "STOP")

    def test_ten_paths_are_exact_and_serializer_is_separate(self) -> None:
        self.assertEqual([item["id"] for item in self.contract["paths"]], list(REQUIRED_INDEX_PATHS))
        self.assertEqual(self.contract["paths"][-1]["id"], "callbacks")
        self.assertEqual(self.contract["serializer_binding"]["id"], "serializer")
        self.assertNotIn("serializer", REQUIRED_INDEX_PATHS)

    def test_reviewed_expectations_are_absent_not_invented(self) -> None:
        expectations = self.contract["reviewed_expectations"]
        self.assertEqual(expectations["status"], "absent")
        for field in ("widths", "sentinels", "exact_eas", "complete_xrefs"):
            self.assertIsNone(expectations[field])
        for item in self.contract["paths"]:
            self.assertIsNone(item["expected_width_bits"])
            self.assertIsNone(item["expected_sentinel"])
            self.assertEqual(item["expected_complete_xrefs"], [])

    def test_contract_forbids_ff_and_vv5_borrowing(self) -> None:
        forbidden = self.contract["evidence_policy"]["forbidden_assumptions"]
        self.assertEqual(
            forbidden,
            [
                "byte_0xFF_sentinel_inference",
                "vv5_dword_minus_one_borrowing",
                "cross_game_width_or_sentinel_borrowing",
            ],
        )

    def test_contract_source_hash_or_commit_mutation_fails_closed(self) -> None:
        for label in ("hash", "8444", "0940"):
            with self.subTest(label=label):
                changed = copy.deepcopy(self.contract)
                if label == "hash":
                    changed["source_provenance"]["source_files"][0]["sha256"] = "0" * 64
                elif label == "8444":
                    changed["source_provenance"]["authenticated_evidence_commit"] = "0" * 40
                else:
                    changed["source_provenance"]["runtime_receipt_commit"] = "0" * 40
                self._recanonicalize(changed)
                with self.assertRaises(GATE.StoredIndexGateError):
                    GATE.validate_contract(changed, root=ROOT)

    def test_contract_rejects_nested_extra_keys_and_reordered_source_files(self) -> None:
        for label in ("policy extra", "padding extra", "reordered sources"):
            with self.subTest(label=label):
                changed = copy.deepcopy(self.contract)
                if label == "policy extra":
                    changed["evidence_policy"]["unexpected"] = True
                elif label == "padding extra":
                    changed["padding_contract"]["unexpected"] = True
                else:
                    changed["source_provenance"]["source_files"].reverse()
                self._recanonicalize(changed)
                with self.assertRaises(GATE.StoredIndexGateError):
                    GATE.validate_contract(changed, root=ROOT)

    def test_contract_cannot_populate_unreviewed_width_or_sentinel(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["reviewed_expectations"].update({"status": "reviewed", "widths": {"selection": 8}})
        changed["paths"][0].update({"status": "observed", "expected_width_bits": 8, "expected_sentinel": 255})
        self._recanonicalize(changed)
        with self.assertRaisesRegex(GATE.StoredIndexGateError, "unreviewed stored-index expectations"):
            GATE.validate_contract(changed, root=ROOT)

    def test_publication_runtime_or_player_go_cannot_be_enabled(self) -> None:
        for key in ("enabled", "runtime_go", "player_go", "eligible"):
            with self.subTest(key=key):
                changed = copy.deepcopy(self.contract)
                changed["publication"][key] = True
                self._recanonicalize(changed)
                with self.assertRaisesRegex(GATE.StoredIndexGateError, "publication boundary"):
                    GATE.validate_contract(changed, root=ROOT)

    def test_structurally_complete_candidate_still_cannot_be_gate_ready(self) -> None:
        candidate = _candidate(self.contract, self.anchor)
        result = GATE.validate_candidate(candidate, self.contract, self.anchor)
        self.assertTrue(result.structural_valid, result.errors)
        self.assertTrue(result.authenticated_source)
        self.assertFalse(result.gate_ready)
        self.assertFalse(result.runtime_go)
        self.assertFalse(result.player_go)
        self.assertFalse(result.publication_ready)

    def test_inferred_ff_and_borrowed_vv5_dword_minus_one_are_rejected(self) -> None:
        cases = {
            "inferred ff": {
                "derivation": {"game_id": "vv3", "source_kind": "authenticated_native_observation", "cross_game_source": None, "inferred": True},
                "width_bits": 8,
                "sentinel": {"kind": "value", "width_bits": 8, "signed": False, "value": 255, "raw_bytes": "FF", "source": "authenticated_vv3_observation", "observation_refs": ["claimed"]},
            },
            "borrowed vv5": {
                "derivation": {"game_id": "vv3", "source_kind": "authenticated_native_observation", "cross_game_source": "vv5", "inferred": False},
                "width_bits": 32,
                "sentinel": {"kind": "value", "width_bits": 32, "signed": True, "value": -1, "raw_bytes": "FFFFFFFF", "source": "authenticated_vv3_observation", "observation_refs": ["claimed"]},
            },
        }
        for label, updates in cases.items():
            with self.subTest(label=label):
                candidate = _candidate(self.contract, self.anchor)
                candidate["paths"][0].update(updates)
                result = GATE.validate_candidate(candidate, self.contract, self.anchor)
                self.assertFalse(result.structural_valid)
                self.assertTrue(any("inferred or cross-game" in error for error in result.errors), result.errors)

    def test_missing_reordered_or_duplicate_path_fails(self) -> None:
        for label in ("missing", "reordered", "duplicate"):
            with self.subTest(label=label):
                candidate = _candidate(self.contract, self.anchor)
                if label == "missing":
                    candidate["paths"].pop()
                elif label == "reordered":
                    candidate["paths"][0], candidate["paths"][1] = candidate["paths"][1], candidate["paths"][0]
                else:
                    candidate["paths"][1] = copy.deepcopy(candidate["paths"][0])
                result = GATE.validate_candidate(candidate, self.contract, self.anchor)
                self.assertFalse(result.structural_valid)

    def test_bool_width_and_mismatched_sentinel_bytes_fail(self) -> None:
        for label in ("bool", "raw width"):
            with self.subTest(label=label):
                candidate = _candidate(self.contract, self.anchor)
                path = candidate["paths"][0]
                if label == "bool":
                    path["width_bits"] = True
                else:
                    path["sentinel"].update({"kind": "value", "value": 255, "raw_bytes": "FF"})
                result = GATE.validate_candidate(candidate, self.contract, self.anchor)
                self.assertFalse(result.structural_valid)

    def test_record_255_requires_acceptance_and_saveability_on_every_path(self) -> None:
        for key in ("accepted", "saveable"):
            with self.subTest(key=key):
                candidate = _candidate(self.contract, self.anchor)
                candidate["paths"][4]["record_255"][key] = False
                result = GATE.validate_candidate(candidate, self.contract, self.anchor)
                self.assertFalse(result.structural_valid)
                self.assertTrue(any("record-255" in error for error in result.errors))

    def test_padding_256_259_must_be_unreachable_and_non_saveable(self) -> None:
        for mutation in ("missing", "reachable", "saveable", "paths"):
            with self.subTest(mutation=mutation):
                candidate = _candidate(self.contract, self.anchor)
                if mutation == "missing":
                    candidate["padding_records"].pop()
                elif mutation == "reachable":
                    candidate["padding_records"][0]["reachable"] = True
                elif mutation == "saveable":
                    candidate["padding_records"][1]["saveable"] = True
                else:
                    candidate["padding_records"][2]["required_path_refs"].pop()
                result = GATE.validate_candidate(candidate, self.contract, self.anchor)
                self.assertFalse(result.structural_valid)

    def test_serializer_must_save_255_and_exclude_padding(self) -> None:
        for key, value in (("record_255_saved", False), ("padding_saved", True)):
            with self.subTest(key=key):
                candidate = _candidate(self.contract, self.anchor)
                candidate["serializer_binding"][key] = value
                result = GATE.validate_candidate(candidate, self.contract, self.anchor)
                self.assertFalse(result.structural_valid)
                self.assertTrue(any("serializer" in error for error in result.errors))

    def test_complete_xrefs_are_nonempty_unique_and_canonical(self) -> None:
        mutations = {
            "incomplete": lambda observation: observation.update({"xref_set_complete": False}),
            "missing": lambda observation: observation.update({"xrefs": []}),
            "duplicate": lambda observation: observation["xrefs"].append(copy.deepcopy(observation["xrefs"][0])),
            "same EA different kind": lambda observation: observation["xrefs"].append({"ea": observation["xrefs"][-1]["ea"], "kind": "other"}),
            "reordered": lambda observation: observation["xrefs"].reverse(),
        }
        for label, mutate in mutations.items():
            with self.subTest(label=label):
                candidate = _candidate(self.contract, self.anchor)
                mutate(candidate["paths"][0]["observations"][0])
                result = GATE.validate_candidate(candidate, self.contract, self.anchor)
                self.assertFalse(result.structural_valid)
                self.assertTrue(any("xref" in error for error in result.errors), result.errors)

    def test_candidate_requires_file_authenticated_source_provenance(self) -> None:
        candidate = _candidate(self.contract, self.anchor)
        result = GATE.validate_candidate(candidate, self.contract, None)
        self.assertFalse(result.structural_valid)
        self.assertFalse(result.authenticated_source)
        self.assertTrue(any("not authenticated from files" in error for error in result.errors))
        changed = copy.deepcopy(candidate)
        changed["provenance"]["exporter_manifest_sha256"] = "0" * 64
        result = GATE.validate_candidate(changed, self.contract, self.anchor)
        self.assertFalse(result.structural_valid)
        self.assertTrue(any("provenance mismatch" in error for error in result.errors))

    def test_every_observation_and_receipt_ref_must_use_authenticated_artifact_ids(self) -> None:
        mutations = {
            "observation": lambda candidate: candidate["paths"][0]["observations"][0].update({"artifact_id": "invented"}),
            "sentinel": lambda candidate: candidate["paths"][0]["sentinel"].update({"observation_refs": ["invented"]}),
            "record255": lambda candidate: candidate["paths"][0]["record_255"].update({"observation_refs": ["invented"]}),
            "padding": lambda candidate: candidate["padding_records"][0].update({"observation_refs": ["invented"]}),
        }
        for label, mutate in mutations.items():
            with self.subTest(label=label):
                candidate = _candidate(self.contract, self.anchor)
                mutate(candidate)
                result = GATE.validate_candidate(candidate, self.contract, self.anchor)
                self.assertFalse(result.structural_valid)
                self.assertTrue(any("not authenticated" in error for error in result.errors), result.errors)

    def test_receipt_schema_stages_and_player_confirmation_are_exact(self) -> None:
        for mutation in ("schema", "stages", "player"):
            with self.subTest(mutation=mutation):
                candidate = _candidate(self.contract, self.anchor)
                if mutation == "schema":
                    candidate["receipt_binding"]["schema_sha256"] = "0" * 64
                elif mutation == "stages":
                    candidate["receipt_binding"]["stage_ids"].pop()
                else:
                    candidate["receipt_binding"]["player_confirmed"] = False
                result = GATE.validate_candidate(candidate, self.contract, self.anchor)
                self.assertFalse(result.structural_valid)

    def test_real_temporary_authenticated_fixture_reaches_structural_only_stop(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            evidence_path, _, _, _ = _authenticated_fixture(root)
            anchor = GATE.authenticate_candidate_anchor(evidence_path, root)
            candidate = _candidate(self.contract, anchor)
            candidate_path = root / "stored-index-candidate.json"
            candidate_path.write_bytes(canonical_json_bytes(candidate))
            completed = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "validate_vv3_stored_index_evidence_gate.py"),
                    "--candidate",
                    str(candidate_path),
                    "--authenticated-evidence-json",
                    str(evidence_path),
                    "--catalog-root",
                    str(root),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
        self.assertEqual(completed.returncode, 1)
        result = json.loads(completed.stdout)
        self.assertTrue(result["structural_valid"], result)
        self.assertTrue(result["authenticated_source"])
        self.assertFalse(result["gate_ready"])
        self.assertEqual(result["status"], "STOP")

    def test_candidate_json_rejects_duplicate_keys_and_noncanonical_order(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            duplicate = root / "duplicate.json"
            duplicate.write_bytes(b'{"schema":"a","schema":"b"}')
            with self.assertRaisesRegex(GATE.StoredIndexGateError, "duplicate JSON key"):
                GATE._load_json(duplicate, canonical=True)
            reordered = root / "reordered.json"
            reordered.write_text(json.dumps({"z": 1, "a": 2}, separators=(",", ":")), encoding="utf-8")
            with self.assertRaisesRegex(GATE.StoredIndexGateError, "not canonical"):
                GATE._load_json(reordered, canonical=True)

    def test_schema_docs_and_source_preserve_disabled_boundary(self) -> None:
        schema = json.loads((ROOT / "data" / "vv3_expanded_256_stored_index_gate.schema.json").read_text(encoding="utf-8"))
        candidate_schema = json.loads((ROOT / "data" / "vv3_expanded_256_stored_index_evidence.schema.json").read_text(encoding="utf-8"))
        self.assertEqual(schema["properties"]["paths"]["minItems"], 10)
        self.assertFalse(schema["properties"]["publication"]["properties"]["enabled"]["const"])
        self.assertEqual(schema["properties"]["reviewed_expectations"]["properties"]["status"]["const"], "absent")
        self.assertEqual(candidate_schema["properties"]["paths"]["minItems"], 10)
        self.assertEqual(candidate_schema["properties"]["padding_records"]["minItems"], 4)
        self.assertFalse(candidate_schema["$defs"]["derivation"]["properties"]["inferred"]["const"])
        self.assertEqual(candidate_schema["$defs"]["derivation"]["properties"]["cross_game_source"]["type"], "null")
        docs = " ".join((ROOT / "docs" / "vv3-expanded-256-stored-index-evidence-gate.md").read_text(encoding="utf-8").split())
        self.assertIn("byte `0xFF` is not treated as a VV3 sentinel", docs)
        self.assertIn("VV5 DWORD/`-1` behavior is not imported into VV3", docs)
        self.assertIn("No stock executable, game folder, DLL, save, native emission, package, or launch", docs)
        source = (ROOT / "scripts" / "validate_vv3_stored_index_evidence_gate.py").read_text(encoding="utf-8")
        for forbidden in ("import subprocess", "os.startfile", "Popen(", "emit_native", "copy_vanilla_saves"):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
