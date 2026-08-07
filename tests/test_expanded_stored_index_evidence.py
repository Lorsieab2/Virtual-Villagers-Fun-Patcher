from __future__ import annotations

import copy
import hashlib
import json
import unittest
from pathlib import Path

from scripts import validate_expanded_stored_index_evidence as MODULE


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "data" / "expanded_256_stored_index_evidence.json"
SCHEMA = ROOT / "data" / "schemas" / "expanded_256_stored_index_evidence.schema.json"
DOC = ROOT / "docs" / "expanded-256-stored-index-evidence.md"


def _sha(path: Path) -> str:
    return MODULE.source_text_sha256(path)


class ExpandedStoredIndexEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract = json.loads(CONTRACT.read_text(encoding="utf-8"))

    def _recanonicalize(self, document: dict[str, object]) -> None:
        document["integrity"]["canonical_sha256"] = MODULE.canonical_sha256(
            document, remove_key="canonical_sha256"
        )

    def _row(
        self,
        game_id: str,
        category: str,
        *,
        path_id: str | None = None,
        storage_width: int = 32,
        sentinel: int | None = 0xFFFFFFFF,
        synthetic: bool = False,
    ) -> dict[str, object]:
        source_path = ROOT / "data" / "expanded_256.json"
        row: dict[str, object] = {
            "path_id": path_id or f"{game_id}-{category}-fixture",
            "category": category,
            "function_name": "sub_401000",
            "function_ea": "0x401000",
            "instruction_ea": "0x401010",
            "operand_file_offset": "0x1011",
            "operand_width_bits": storage_width,
            "storage_width_bits": storage_width,
            "sentinel": {
                "width_bits": storage_width,
                "encoding": "twos_complement" if sentinel is not None else "none",
                "unsigned_value": sentinel,
                "meaning": "no_record" if sentinel is not None else "none",
            },
            "xrefs": [{"from_function": "sub_402000", "from_ea": "0x402010", "kind": "call"}],
            "record_255": {"accepted": True, "proof": "authenticated runtime receipt"},
            "indices_256_259": {"unreachable": True, "non_saveable": True, "proof": "authenticated runtime receipt"},
            "runtime_receipt_refs": [f"receipt-{game_id}-{category}"],
            "source": {
                "artifact": "data/expanded_256.json",
                "sha256": _sha(source_path),
                "row_sha256": "0" * 64,
                "provenance": "exact_ida_plus_player_runtime_receipt",
            },
            "synthetic": synthetic,
        }
        row["source"]["row_sha256"] = MODULE.evidence_row_sha256(row)
        return row

    def test_canonical_contract_is_stop_with_exact_counts(self) -> None:
        result = MODULE.validate_contract(self.contract, root=ROOT)
        self.assertEqual(result["status"], "STOP")
        self.assertFalse(result["publication_eligible"])
        self.assertEqual(result["games"]["vv4"]["candidate_edits"], 13)
        self.assertEqual(result["games"]["vv5"]["candidate_edits"], 15)
        self.assertEqual(result["games"]["vv4"]["relocations"], 13)
        self.assertEqual(result["games"]["vv5"]["relocations"], 66)
        self.assertEqual(result["games"]["vv4"]["categories_complete"], 0)
        self.assertEqual(result["games"]["vv5"]["categories_total"], 11)

    def test_schema_and_source_hashes_are_exact(self) -> None:
        schema = self.contract["source_provenance"]["schema"]
        self.assertEqual(schema["sha256"], _sha(SCHEMA))
        for record in self.contract["source_provenance"]["source_files"]:
            self.assertEqual(record["sha256"], _sha(ROOT / record["path"]))

    def test_publication_cannot_be_enabled(self) -> None:
        mutated = copy.deepcopy(self.contract)
        mutated["publication"]["enabled"] = True
        self._recanonicalize(mutated)
        with self.assertRaisesRegex(MODULE.StoredIndexEvidenceError, "publication guard"):
            MODULE.validate_contract(mutated, root=ROOT)

    def test_wrong_stock_and_relocation_fingerprints_fail_closed(self) -> None:
        stock = copy.deepcopy(self.contract)
        stock["games"]["vv4"]["stock_fingerprint"]["sha256"] = "0" * 64
        self._recanonicalize(stock)
        with self.assertRaisesRegex(MODULE.StoredIndexEvidenceError, "stock fingerprint"):
            MODULE.validate_contract(stock, root=ROOT)
        relocation = copy.deepcopy(self.contract)
        relocation["games"]["vv5"]["relocation_ledger"]["count"] = 65
        self._recanonicalize(relocation)
        with self.assertRaisesRegex(MODULE.StoredIndexEvidenceError, "relocation count"):
            MODULE.validate_contract(relocation, root=ROOT)

    def test_missing_duplicate_or_reordered_categories_fail_closed(self) -> None:
        missing = copy.deepcopy(self.contract)
        missing["games"]["vv4"]["path_categories"].pop()
        self._recanonicalize(missing)
        with self.assertRaisesRegex(MODULE.StoredIndexEvidenceError, "categories are missing"):
            MODULE.validate_contract(missing, root=ROOT)
        duplicate = copy.deepcopy(self.contract)
        duplicate["games"]["vv5"]["path_categories"][1] = copy.deepcopy(
            duplicate["games"]["vv5"]["path_categories"][0]
        )
        self._recanonicalize(duplicate)
        with self.assertRaisesRegex(MODULE.StoredIndexEvidenceError, "categories are missing"):
            MODULE.validate_contract(duplicate, root=ROOT)

    def test_missing_duplicate_or_stale_candidate_edits_fail_closed(self) -> None:
        missing = copy.deepcopy(self.contract)
        missing["games"]["vv4"]["candidate_static_edits"].pop()
        self._recanonicalize(missing)
        with self.assertRaisesRegex(MODULE.StoredIndexEvidenceError, "candidate edit set"):
            MODULE.validate_contract(missing, root=ROOT)
        duplicate = copy.deepcopy(self.contract)
        duplicate["games"]["vv5"]["candidate_static_edits"][1]["manifest_offset"] = duplicate["games"]["vv5"]["candidate_static_edits"][0]["manifest_offset"]
        self._recanonicalize(duplicate)
        with self.assertRaisesRegex(MODULE.StoredIndexEvidenceError, "duplicate candidate edit offset"):
            MODULE.validate_contract(duplicate, root=ROOT)
        stale = copy.deepcopy(self.contract)
        stale["games"]["vv5"]["candidate_static_edits"][0]["manifest_row_sha256"] = "0" * 64
        self._recanonicalize(stale)
        with self.assertRaisesRegex(MODULE.StoredIndexEvidenceError, "digest is stale"):
            MODULE.validate_contract(stale, root=ROOT)

    def test_byte_ff_sentinel_is_ambiguous_with_record_255(self) -> None:
        mutated = copy.deepcopy(self.contract)
        category = mutated["games"]["vv5"]["path_categories"][0]
        category["evidence_rows"] = [
            self._row("vv5", "selection", storage_width=8, sentinel=0xFF)
        ]
        self._recanonicalize(mutated)
        with self.assertRaisesRegex(MODULE.StoredIndexEvidenceError, "byte 0xFF is ambiguous"):
            MODULE.validate_contract(mutated, root=ROOT)

    def test_missing_xrefs_and_record_or_padding_proof_fail_closed(self) -> None:
        for field, message in (
            ("xrefs", "xrefs are missing"),
            ("record_255", "record 255 is not proved accepted"),
            ("indices_256_259", "indices 256-259 are not proved"),
        ):
            with self.subTest(field=field):
                mutated = copy.deepcopy(self.contract)
                row = self._row("vv4", "selection")
                if field == "xrefs":
                    row[field] = []
                elif field == "record_255":
                    row[field]["accepted"] = False
                else:
                    row[field]["unreachable"] = False
                row["source"]["row_sha256"] = MODULE.evidence_row_sha256(row)
                mutated["games"]["vv4"]["path_categories"][0]["evidence_rows"] = [row]
                self._recanonicalize(mutated)
                with self.assertRaisesRegex(MODULE.StoredIndexEvidenceError, message):
                    MODULE.validate_contract(mutated, root=ROOT)

    def test_synthetic_manual_or_stale_source_evidence_fails_closed(self) -> None:
        synthetic = copy.deepcopy(self.contract)
        synthetic["games"]["vv4"]["path_categories"][0]["evidence_rows"] = [
            self._row("vv4", "selection", synthetic=True)
        ]
        self._recanonicalize(synthetic)
        with self.assertRaisesRegex(MODULE.StoredIndexEvidenceError, "synthetic evidence"):
            MODULE.validate_contract(synthetic, root=ROOT)
        injected = copy.deepcopy(self.contract)
        row = self._row("vv4", "selection")
        row["manual_result"] = True
        injected["games"]["vv4"]["path_categories"][0]["evidence_rows"] = [row]
        self._recanonicalize(injected)
        with self.assertRaisesRegex(MODULE.StoredIndexEvidenceError, "fields are incomplete or injected"):
            MODULE.validate_contract(injected, root=ROOT)
        stale = copy.deepcopy(self.contract)
        row = self._row("vv5", "selection")
        row["source"]["sha256"] = "0" * 64
        row["source"]["row_sha256"] = MODULE.evidence_row_sha256(row)
        stale["games"]["vv5"]["path_categories"][0]["evidence_rows"] = [row]
        self._recanonicalize(stale)
        with self.assertRaisesRegex(MODULE.StoredIndexEvidenceError, "source hash is stale"):
            MODULE.validate_contract(stale, root=ROOT)

    def test_duplicate_path_ids_fail_closed(self) -> None:
        mutated = copy.deepcopy(self.contract)
        for index, category_name in ((0, "selection"), (1, "roster")):
            category = mutated["games"]["vv4"]["path_categories"][index]
            category["status"] = "observed_complete"
            category["missing_evidence"] = []
            category["evidence_rows"] = [
                self._row("vv4", category_name, path_id="vv4-duplicate-path")
            ]
            category["expected_path_count"] = 1
            category["path_ledger_sha256"] = hashlib.sha256(
                MODULE._canonical_bytes(category["evidence_rows"])
            ).hexdigest().upper()
        self._recanonicalize(mutated)
        with self.assertRaisesRegex(MODULE.StoredIndexEvidenceError, "duplicate stored-index path id"):
            MODULE.validate_contract(mutated, root=ROOT)

    def test_observed_category_requires_exact_path_count_and_ledger_digest(self) -> None:
        count = copy.deepcopy(self.contract)
        category = count["games"]["vv5"]["path_categories"][0]
        category["status"] = "observed_complete"
        category["missing_evidence"] = []
        category["evidence_rows"] = [self._row("vv5", "selection")]
        category["expected_path_count"] = 2
        category["path_ledger_sha256"] = hashlib.sha256(
            MODULE._canonical_bytes(category["evidence_rows"])
        ).hexdigest().upper()
        self._recanonicalize(count)
        with self.assertRaisesRegex(MODULE.StoredIndexEvidenceError, "path count is incomplete"):
            MODULE.validate_contract(count, root=ROOT)
        digest = copy.deepcopy(count)
        category = digest["games"]["vv5"]["path_categories"][0]
        category["expected_path_count"] = 1
        category["path_ledger_sha256"] = "0" * 64
        self._recanonicalize(digest)
        with self.assertRaisesRegex(MODULE.StoredIndexEvidenceError, "path ledger digest is stale"):
            MODULE.validate_contract(digest, root=ROOT)

    def test_padding_reachability_cannot_be_claimed_without_runtime_capture(self) -> None:
        mutated = copy.deepcopy(self.contract)
        layout = mutated["games"]["vv5"]["layout_boundary"]
        layout["record_255"]["path_acceptance_proof"] = "observed_complete"
        layout["indices_256_259"]["unreachable_proof"] = "observed_complete"
        layout["indices_256_259"]["non_saveable_proof"] = "observed_complete"
        self._recanonicalize(mutated)
        with self.assertRaisesRegex(MODULE.StoredIndexEvidenceError, "claimed without exact runtime evidence"):
            MODULE.validate_contract(mutated, root=ROOT)

    def test_vv5_dword_minus_one_evidence_cannot_be_generalized(self) -> None:
        vv4 = copy.deepcopy(self.contract)
        vv4["games"]["vv4"]["index_model"]["storage_width_bits"] = 32
        vv4["games"]["vv4"]["index_model"]["sentinel"] = copy.deepcopy(
            vv4["games"]["vv5"]["index_model"]["sentinel"]
        )
        self._recanonicalize(vv4)
        with self.assertRaisesRegex(MODULE.StoredIndexEvidenceError, "generalized to VV4"):
            MODULE.validate_contract(vv4, root=ROOT)
        vv5 = copy.deepcopy(self.contract)
        vv5["games"]["vv5"]["index_model"]["generalizable_to_other_paths"] = True
        self._recanonicalize(vv5)
        with self.assertRaisesRegex(MODULE.StoredIndexEvidenceError, "generalized outside cited paths"):
            MODULE.validate_contract(vv5, root=ROOT)

    def test_docs_preserve_stop_and_no_runtime_overclaim(self) -> None:
        text = DOC.read_text(encoding="utf-8")
        flat = " ".join(text.split())
        self.assertIn("all eleven path categories", flat)
        self.assertIn("byte `0xFF`", flat)
        self.assertIn("VV5 DWORD/`-1` evidence is path-scoped", flat)
        self.assertIn("VV4 is not inferred from VV5", flat)
        self.assertIn("13-row VV4", flat)
        self.assertIn("66-row VV5", flat)
        self.assertIn("No game was launched and no real save was accessed", flat)
        self.assertIn("publication remains `false`", flat)


if __name__ == "__main__":
    unittest.main()
