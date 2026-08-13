#!/usr/bin/env python3
"""Validate the disabled VV5 post-prototype overlay and its exact bindings."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "vv5_post_prototype_overlay_evidence.json"
SCHEMA = ROOT / "data" / "schemas" / "vv5_post_prototype_overlay_evidence.schema.json"
CANDIDATE_SCHEMA = ROOT / "data" / "schemas" / "vv5_post_prototype_overlay.schema.json"
BUILDER_PATH = ROOT / "scripts" / "build_vv5_post_prototype_overlay.py"

SPEC = importlib.util.spec_from_file_location("vv5_post_prototype_overlay_builder", BUILDER_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("cannot load VV5 overlay builder")
B = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(B)

ROWS_SHA256 = "892F67E5D979D120E82AE400EB8E239688BDAF01C1C58CD32781984529E43D17"


def require(value: object, message: str) -> None:
    if not value:
        raise ValueError(message)


def expected_evidence() -> dict[str, object]:
    return {
        "schema": "vvfp.vv5_post_prototype_overlay_evidence.v1",
        "status": "static_overlay_go_runtime_stop",
        "enabled": False,
        "catalog_visible": False,
        "native_output": False,
        "runtime_go": False,
        "player_go": False,
        "publication_ready": False,
        "candidate": {
            "path": "data/candidates/vv5_post_prototype_overlay.json",
            "canonical_sha256": B.build()["canonical_sha256"],
        },
        "bindings": {
            "prototype_sha256": B.PROTOTYPE_SHA256,
            "expanded_manifest_rows_sha256": B.MANIFEST_ROWS_SHA256,
            "c342_source_text_sha256": B.LEDGER_SOURCE_SHA256,
            "c342_ledger_sha256": B.LEDGER_SHA256,
            "central_index_gate_sha256": B.STORED_INDEX_SOURCE_SHA256,
            "save_geometry_sha256": B.SAVE_GEOMETRY_SOURCE_SHA256,
        },
        "overlay": {
            "row_count": 16,
            "rows_sha256": ROWS_SHA256,
            "dbxxx_overlap_count": 0,
            "c342_ledger_overlap_count": 0,
            "result_size": B.PROTOTYPE_SIZE,
            "result_checksum": B.RESULT_CHECKSUM,
            "result_sha256": B.RESULT_SHA256,
        },
        "runtime_evidence": {"status": "absent_stop", "receipts": []},
        "player_evidence": {"status": "absent_stop", "receipts": []},
    }


def validate(path: Path = DATA, root: Path = ROOT, prototype: Path | None = None) -> dict[str, object]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    require(data == expected_evidence(), "evidence contract drifted")

    evidence_schema = json.loads((Path(root) / SCHEMA.relative_to(ROOT)).read_text(encoding="utf-8"))
    candidate_schema = json.loads((Path(root) / CANDIDATE_SCHEMA.relative_to(ROOT)).read_text(encoding="utf-8"))
    require(evidence_schema["$id"] == data["schema"], "evidence schema id")
    require(evidence_schema["additionalProperties"] is False, "evidence schema is not closed")
    require(candidate_schema["$id"] == B.build()["schema"], "candidate schema id")
    require(candidate_schema["additionalProperties"] is False, "candidate schema is not closed")

    candidate_path = Path(root) / data["candidate"]["path"]
    candidate = json.loads(candidate_path.read_text(encoding="utf-8"))
    B.validate(candidate, Path(root))
    rows_digest = hashlib.sha256(
        json.dumps(candidate["overlay"]["rows"], sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest().upper()
    require(rows_digest == ROWS_SHA256, "overlay rows digest")
    if prototype is not None:
        rendered = B.render_candidate(Path(prototype).read_bytes())
        require(hashlib.sha256(rendered).hexdigest().upper() == B.RESULT_SHA256, "source-bound result")
    return data


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", type=Path, default=DATA)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--prototype", type=Path)
    args = parser.parse_args()
    validate(args.evidence, args.root, args.prototype)
    print("VV5 post-prototype overlay evidence: STOP (static overlay valid; runtime/player/publication absent)")
