"""Validate the disabled VV3 Expanded-256 stabilization contract."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "data" / "vv3_expanded_256_stabilization_gate.json"
SCHEMA = "vvfp.vv3_expanded_256_stabilization_gate"
SOURCE = "8BC5DB382D02BC5C21AD5F607580D60FF44A6519CC7EB133F03113BAACAE6503"
PROTOTYPE = "6EE3361A7AC35F441763647C1E2FC9EC49569DE5EF372BDB41D243D03002D601"
SHA = __import__("re").compile(r"^[0-9A-F]{64}$")


class StabilizationGateError(ValueError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise StabilizationGateError(message)


def _canonical(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode()


def _load(path: Path) -> Mapping[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=dict)


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest().upper()


def _digest(document: Mapping[str, Any]) -> str:
    body = copy.deepcopy(dict(document))
    body["integrity"]["canonical_sha256"] = None
    return hashlib.sha256(_canonical(body)).hexdigest().upper()


def validate(document: Mapping[str, Any], root: Path = ROOT) -> dict[str, object]:
    _require(document.get("schema") == SCHEMA and document.get("schema_version") == 1, "stabilization schema mismatch")
    _require(document.get("status") == "static_stabilization_contract_only", "stabilization contract status changed")
    bindings = document.get("bindings")
    _require(isinstance(bindings, Mapping), "bindings missing")
    _require(bindings.get("source_sha256") == SOURCE and bindings.get("prototype_sha256") == PROTOTYPE, "VV3 source identity mismatch")
    manifest = bindings.get("manifest")
    _require(isinstance(manifest, Mapping), "manifest binding missing")
    manifest_path = root / str(manifest["path"])
    _require(_hash(manifest_path) == manifest["sha256"], "expanded manifest hash mismatch")
    raw = _load(manifest_path)
    game = raw["games"]["vv3"]
    _require(game["source_sha256"] == SOURCE and game["patch_count"] == 1263 and len(game["patches"]) == 1263, "VV3 manifest count or source mismatch")
    _require(manifest["declared_patch_count"] == manifest["actual_patch_count"] == 1263, "VV3 manifest ledger is not exact")
    for group in ("contracts", "validator_inputs"):
        rows = bindings.get(group)
        _require(isinstance(rows, list) and rows, f"{group} missing")
        for row in rows:
            path = root / str(row["path"])
            _require(SHA.fullmatch(str(row["sha256"])) is not None and _hash(path) == row["sha256"], f"stale bound input: {row['path']}")
    geometry = document.get("geometry")
    _require(geometry == {
        "record_size": "0x11C", "records_offset": "0x7864", "logical_first": 0,
        "logical_last": 255, "padding_indices": [256, 257, 258, 259],
        "tail_offset": "0x19464", "expanded_body_size": "0x1A4B4",
        "expanded_file_size": "0x1A4C0", "status": "reference_bound_stop",
    }, "corrected VV3 full-capacity geometry contract changed")
    gates = document.get("evidence_gates")
    _require(isinstance(gates, list) and [row["id"] for row in gates] == [
        "stored_index_width_sentinel_paths", "serializer_reader_abi",
        "full_capacity_save_semantics", "runtime_capture", "relocation_proof",
    ], "evidence gate inventory changed")
    _require(all(row["status"] in {"evidence_absent", "receipt_absent", "decoded_reference_and_runtime_proof_absent"} for row in gates), "an evidence gate was relaxed")
    relocation = document.get("relocation_invariants")
    foreign = relocation["foreign_preservation"]
    _require(foreign["status"] == "pending_containment_integration", "foreign preservation state was relaxed")
    _require(
        foreign["vv4"] == {
            "path": "data/vv4_origins_feature.json",
            "count": 13,
            "ledger_sha256": "CEE01F4AEC59CB1CEE0F42E3DDDB3A24615261E628ED0629C1BFAABF421A897D",
        }
        and foreign["vv5"] == {
            "path": "data/vv5_origins_feature.json",
            "count": 66,
            "ledger_sha256": "14E460773ADC065E053FA30921ED01D33A5F36AD49DC754CCD69127EA02C01B7",
        },
        "foreign relocation ledger identity changed",
    )
    db1a4 = foreign["vv5_db1a4"]
    _require(db1a4 == {
        "offset": "0xDB1A4",
        "before": "7267C6FF",
        "kind": "rel32",
        "source_virtual_address": "0x8EB1A3",
        "source_expanded_virtual_address": "0x8EB1A3",
        "target_stock_virtual_address": "0x41891A",
        "target_expanded_virtual_address": "0x41891A",
        "purpose": "relocate IDA-decoded VV5 current-feature cross-section rel32 operand for expanded 256 mode",
    }, "VV5 DB1A4 semantics changed")
    decision = document.get("decision")
    _require(isinstance(decision, Mapping) and decision.get("native_output") is False and decision.get("enabled") is False and decision.get("runtime_go") is False and decision.get("player_go") is False and decision.get("publication_ready") is False and decision.get("status") == "STOP", "publication/runtime decision relaxed")
    _require(document["integrity"]["canonical_sha256"] == _digest(document), "stabilization canonical digest mismatch")
    return {
        "contract_valid": True,
        "manifest_patches": 1263,
        "evidence_gates": 5,
        "foreign_ledgers": {"vv4": 13, "vv5": 66},
        "gate_ready": False,
        "runtime_go": False,
        "player_go": False,
        "publication_ready": False,
        "status": "STOP",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=Path, default=CONTRACT)
    args = parser.parse_args(argv)
    try:
        result = validate(_load(args.contract))
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"contract_valid": False, "gate_ready": False, "runtime_go": False, "player_go": False, "publication_ready": False, "status": "STOP", "error": str(exc)}, sort_keys=True))
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
