from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "expanded-256-runtime-evidence.md"
SPEC = importlib.util.spec_from_file_location(
    "validate_expanded_runtime_evidence",
    ROOT / "scripts" / "validate_expanded_runtime_evidence.py",
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


class ExpandedRuntimeEvidenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = MODULE.load_contract()

    def _recanonicalize(self, document: dict[str, object]) -> None:
        integrity = document["integrity"]
        assert isinstance(integrity, dict)
        integrity["canonical_sha256"] = MODULE.canonical_sha256(
            document, remove_key="canonical_sha256"
        )

    def test_canonical_contract_is_static_and_exact(self) -> None:
        summary = MODULE.validate_contract(self.contract, root=ROOT)
        self.assertFalse(summary["publication_eligible"])
        self.assertEqual(summary["games"]["vv4"]["relocations"], 13)
        self.assertEqual(summary["games"]["vv5"]["relocations"], 66)
        self.assertFalse(summary["games"]["vv4"]["runtime_observed"])
        self.assertFalse(summary["games"]["vv5"]["runtime_observed"])
        self.assertFalse(self.contract["publication"]["enabled"])

    def test_contract_pins_exact_stock_and_static_expanded_fingerprints(self) -> None:
        for game_id, expected in {
            "vv4": (929792, "6D27A429FFCA5F1F71FDD7ECA761ED1BB67E85F976494BA178B3D7BE01F1B220"),
            "vv5": (991232, "92946781980220E9D1A2E6C573925519934608F5215F4A0F8CE3B90088C5C65D"),
        }.items():
            game = self.contract["games"][game_id]
            self.assertEqual(game["stock_fingerprint"]["size"], expected[0])
            self.assertEqual(game["stock_fingerprint"]["sha256"], expected[1])
            for mode, fingerprint in game["expanded_fingerprints"].items():
                self.assertEqual(fingerprint["evidence_class"], "static_render_candidate")
                self.assertTrue(fingerprint["runtime_receipt_required"])

    def test_source_hash_mutation_fails_closed(self) -> None:
        mutated = copy.deepcopy(self.contract)
        mutated["source_provenance"]["source_files"][0]["sha256"] = "0" * 64
        self._recanonicalize(mutated)
        with self.assertRaisesRegex(MODULE.RuntimeEvidenceError, "source provenance hash mismatch"):
            MODULE.validate_contract(mutated, root=ROOT)

    def test_relocation_count_mutation_fails_closed_even_with_fresh_contract_digest(self) -> None:
        mutated = copy.deepcopy(self.contract)
        mutated["games"]["vv5"]["relocation_ledger"]["count"] = 65
        self._recanonicalize(mutated)
        with self.assertRaisesRegex(MODULE.RuntimeEvidenceError, "relocation row count mismatch"):
            MODULE.validate_contract(mutated, root=ROOT)

    def test_publication_true_is_rejected_even_if_everything_else_is_static(self) -> None:
        mutated = copy.deepcopy(self.contract)
        mutated["publication"]["enabled"] = True
        self._recanonicalize(mutated)
        with self.assertRaisesRegex(MODULE.RuntimeEvidenceError, "publication must remain false"):
            MODULE.validate_contract(mutated, root=ROOT)

    def test_canonical_runtime_evidence_has_no_producer_or_receipts(self) -> None:
        for game_id in ("vv4", "vv5"):
            evidence = self.contract["games"][game_id]["runtime_evidence"]
            self.assertEqual(evidence["status"], "absent")
            self.assertIsNone(evidence["producer"])
            self.assertEqual(evidence["player_receipts"], [])
            self.assertTrue(all(
                gate["status"] in {"absent", "not_applicable"}
                for gate in evidence["gates"].values()
            ))

    def test_documentation_preserves_static_only_boundary_and_exact_ledger_counts(self) -> None:
        text = DOC.read_text(encoding="utf-8")
        flat = " ".join(text.split())
        self.assertIn("publication, runtime-GO, player-GO, and eligibility flags are all `false`", flat)
        self.assertIn("exactly 13 rows", flat)
        self.assertIn("exactly 66 rows", flat)
        self.assertIn("stock-save import and conversion", flat)
        self.assertIn("late records 149, 150, 254, and 255", flat)
        self.assertIn("Synthetic fixtures", flat)
        self.assertIn("No saves are present in this repository contract", flat)

    def test_synthetic_receipt_cannot_be_observed(self) -> None:
        mutated = copy.deepcopy(self.contract)
        evidence = mutated["games"]["vv4"]["runtime_evidence"]
        evidence.update({
            "status": "observed",
            "evidence_class": "synthetic_fixture",
            "producer": {
                "receipt_id": "fixture-vv4-0001",
                "producer_type": "player_runtime_receipt",
                "operator": "fixture",
                "captured_at": "2026-08-07T00:00:00Z",
                "source_commit": "dda163ad6f68b0a4bc4071b94fe218505974ab49",
                "capture_tool": "unit-test",
                "provenance": "player_observed_exact_build",
                "synthetic": True,
            },
        })
        self._recanonicalize(mutated)
        with self.assertRaisesRegex(MODULE.RuntimeEvidenceError, "class is not authorized"):
            MODULE.validate_contract(mutated, root=ROOT)

    def test_observed_receipt_requires_exact_producer_and_provenance(self) -> None:
        mutated = copy.deepcopy(self.contract)
        evidence = mutated["games"]["vv5"]["runtime_evidence"]
        evidence.update({
            "status": "observed",
            "evidence_class": "player_runtime_receipt",
            "producer": {
                "receipt_id": "receipt-vv5-0001",
                "producer_type": "player_runtime_receipt",
                "operator": "player",
                "captured_at": "2026-08-07T00:00:00Z",
                "source_commit": "dda163ad6f68b0a4bc4071b94fe218505974ab49",
                "capture_tool": "unit-test",
                "provenance": "player_observed_exact_build",
                "synthetic": True,
            },
        })
        evidence["receipt_sha256"] = MODULE.canonical_sha256(
            evidence, remove_key="receipt_sha256"
        )
        self._recanonicalize(mutated)
        with self.assertRaisesRegex(MODULE.RuntimeEvidenceError, "synthetic evidence"):
            MODULE.validate_contract(mutated, root=ROOT)

    def test_incomplete_inventory_fails_closed(self) -> None:
        game = self.contract["games"]["vv4"]
        inventory = {
            "schema_version": "vvfp.runtime_artifact_inventory.v1",
            "status": "observed",
            "complete": True,
            "follow_symlinks": False,
            "no_follow": True,
            "re_read_required": True,
            "records": [],
        }
        with self.assertRaisesRegex(MODULE.RuntimeEvidenceError, "records are missing"):
            MODULE.validate_artifact_inventory(inventory, game)

    def test_complete_inventory_hashes_and_re_reads_without_symlink_following(self) -> None:
        game = copy.deepcopy(self.contract["games"]["vv4"])
        roles = game["required_folder_inventory"]["required_roles"]
        records = []
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for role in roles:
                name = "VVFP Origins Icons.dll" if role == "companion_dll" else f"{role}.bin"
                path = root / name
                data = role.encode("ascii")
                path.write_bytes(data)
                digest = hashlib.sha256(data).hexdigest().upper()
                records.append({
                    "path": name,
                    "role": role,
                    "size": len(data),
                    "sha256": digest,
                    "re_read_sha256": digest,
                    "is_symlink": False,
                    "provenance": "authenticated_runtime_artifact",
                })
                if role == "stock_executable":
                    game["stock_fingerprint"].update({"size": len(data), "sha256": digest})
                elif role == "expanded_executable_immediate":
                    game["expanded_fingerprints"]["experimental_expanded_256"].update({"size": len(data), "sha256": digest})
                elif role == "expanded_executable_progression":
                    game["expanded_fingerprints"]["experimental_expanded_256_progression"].update({"size": len(data), "sha256": digest})
                elif role == "companion_dll":
                    game["required_folder_inventory"]["required_dlls"][0]["sha256"] = digest
            inventory = {
                "schema_version": "vvfp.runtime_artifact_inventory.v1",
                "status": "observed",
                "complete": True,
                "follow_symlinks": False,
                "no_follow": True,
                "re_read_required": True,
                "records": records,
            }
            result = MODULE.validate_artifact_inventory(inventory, game, root=root)
        self.assertEqual(result["records"], len(roles))
        self.assertTrue(result["complete"])

    def test_unsafe_inventory_flags_fail_closed(self) -> None:
        game = self.contract["games"]["vv4"]
        inventory = {
            "schema_version": "vvfp.runtime_artifact_inventory.v1",
            "status": "observed",
            "complete": True,
            "follow_symlinks": True,
            "no_follow": False,
            "re_read_required": True,
            "records": [{"path": "x.exe", "role": "stock_executable"}],
        }
        with self.assertRaisesRegex(MODULE.RuntimeEvidenceError, "disable symlink following"):
            MODULE.validate_artifact_inventory(inventory, game)

    def test_late_record_and_relocation_receipts_require_exact_assertions(self) -> None:
        game = self.contract["games"]["vv5"]
        with self.assertRaisesRegex(MODULE.RuntimeEvidenceError, "late-record receipt indices"):
            MODULE._validate_observed_gate(
                "late_record_boundaries",
                {"status": "observed", "receipt_refs": ["r"], "assertions": {"indices": [149, 150]}},
                game,
            )
        with self.assertRaisesRegex(MODULE.RuntimeEvidenceError, "relocation ledger digest"):
            MODULE._validate_observed_gate(
                "relocation_receipt",
                {"status": "observed", "receipt_refs": ["r"], "assertions": {"count": 66, "ledger_sha256": "0" * 64}},
                game,
            )


if __name__ == "__main__":
    unittest.main()
