#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "vv3_full256_serializer_evidence.json"
SCHEMA = ROOT / "data" / "schemas" / "vv3_full256_serializer_evidence.schema.json"
MODEL = ROOT / "data" / "candidates" / "vv3_full256_serializer_candidate.json"
ROWS_SHA256 = "04B93127BC4D5C6787AB013DE9205813D44947DBC16A370DBC234C06588AC3FB"


def require(value: object, message: str) -> None:
    if not value:
        raise ValueError(message)


def validate(path: Path = DATA, root: Path = ROOT) -> dict[str, object]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    require(
        set(data)
        == {
            "schema_version",
            "status",
            "enabled",
            "catalog_visible",
            "native_output",
            "runtime_go",
            "player_go",
            "publication_ready",
            "bindings",
            "replacement",
            "atomic_writer",
            "whole_load_rollback",
            "runtime_evidence",
            "player_evidence",
        },
        "top-level evidence fields",
    )
    schema = json.loads((Path(root) / SCHEMA.relative_to(ROOT)).read_text(encoding="utf-8"))
    require(schema["$id"] == "vvfp.vv3_full256_serializer_evidence.v1", "schema id")
    require(schema["additionalProperties"] is False, "schema must be closed")
    require(data["schema_version"] == "vvfp.vv3_full256_serializer_evidence.v1", "schema")
    require(data["status"] == "static_serializer_reader_go_writer_rollback_stop", "status")
    require(
        not any(
            data[key]
            for key in (
                "enabled",
                "catalog_visible",
                "native_output",
                "runtime_go",
                "player_go",
                "publication_ready",
            )
        ),
        "all gates must remain disabled",
    )
    bindings = data["bindings"]
    require(bindings["stock_sha256"] == "8BC5DB382D02BC5C21AD5F607580D60FF44A6519CC7EB133F03113BAACAE6503", "stock binding")
    require(
        bindings["expanded_manifest"]
        == {"path": "data/expanded_256.json", "row_count": 1263, "rows_sha256": ROWS_SHA256},
        "expanded manifest binding",
    )
    require(
        bindings["parents"]
        == [
            {"mode": "experimental_expanded_256", "sha256": "657D321B2F1E9E6D6C223DB1FF0BBA38C2D761A97A6E7F21B98CE1826531A848", "size": 0xCC000},
            {"mode": "experimental_expanded_256_progression", "sha256": "3A35745C00102A0964DF6E81B77707539C5BDC03501011F43FF1D2809015B211", "size": 0xCC000},
        ],
        "parent bindings",
    )
    require(
        data["replacement"]
        == {
            "section": ".vv3sv",
            "section_raw": "0xCC000",
            "section_rva": "0x3B9000",
            "section_va": "0x7B9000",
            "section_sha256": "9F82D59D1436B17ACA69CD637AB40D44DF35323DA46600AAA5FD07315C249B64",
            "serializer_raw": "0xCC000",
            "serializer_sha256": "451EF9D65A9613247FAB9C8C586387F05329F9B6E6048CEE07D0B88E6BE4374E",
            "deserializer_raw": "0xCC200",
            "deserializer_sha256": "C61D124EFBDADF63D3C128E4B23BB0F80AE2D07B031A53396E4BFFF032268775",
            "failure_gate_raw": "0xCC3C0",
            "failure_gate_sha256": "A61E6CAE007E78F4A2ADC3173D3E3C7261E69DA1F9C031EAED441288C105A99B",
            "serializer_hook": {"raw": "0x27D57", "before": "E824720300", "after": "E864163900", "target": "0x7B93C0"},
            "deserializer_hook": {"raw": "0x28A4C", "before": "E80F3E0300", "after": "E8AF073900", "target": "0x7B9200"},
            "results": [
                {"mode": "experimental_expanded_256", "sha256": "585EC60285F20A55658B5CB77E8A81D5B6A632B3A399058F01EB732B4777976B", "checksum": "27F40C00"},
                {"mode": "experimental_expanded_256_progression", "sha256": "3B93CFDD98112D54F4457AA4E84838F98E577DF0AF1B9C20903E1C4CC8F276A8", "checksum": "316F0D00"},
            ],
        },
        "replacement pins",
    )
    stop = {"status": "STOP", "hook_raw": None, "hook_before": None, "hook_after": None}
    atomic = data["atomic_writer"]
    require(
        set(atomic) == {*stop, "wrapper_bytes", "resolver_bytes", "final_sha256"}
        and {key: atomic[key] for key in stop} == stop
        and atomic["wrapper_bytes"] is None
        and atomic["resolver_bytes"] is None
        and atomic["final_sha256"] is None,
        "atomic writer must remain STOP/null",
    )
    rollback = data["whole_load_rollback"]
    require(
        set(rollback) == {*stop, "snapshot_bytes", "rollback_bytes", "final_sha256"}
        and {key: rollback[key] for key in stop} == stop
        and rollback["snapshot_bytes"] is None
        and rollback["rollback_bytes"] is None
        and rollback["final_sha256"] is None,
        "whole-load rollback must remain STOP/null",
    )
    require(data["runtime_evidence"] == {"status": "absent", "receipts": []}, "runtime evidence")
    require(data["player_evidence"] == {"status": "absent", "receipts": []}, "player evidence")

    expanded = json.loads((Path(root) / "data" / "expanded_256.json").read_text(encoding="utf-8"))["games"]["vv3"]
    rows = expanded["patches"]
    digest = hashlib.sha256(json.dumps(rows, sort_keys=True, separators=(",", ":")).encode()).hexdigest().upper()
    require(expanded["patch_count"] == 1263 and len(rows) == 1263 and digest == ROWS_SHA256, "local expanded manifest")
    model = json.loads((Path(root) / MODEL.relative_to(ROOT)).read_text(encoding="utf-8"))
    require(model["expanded_manifest"] == bindings["expanded_manifest"], "candidate/evidence manifest binding")
    require(model["whole_load_rollback"] == {"status": "STOP", "hook_raw": None, "hook_preimage": None, "hook_after": None, "snapshot_bytes": None, "rollback_bytes": None, "final_sha256": None}, "candidate rollback STOP")
    return data


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", type=Path, default=DATA)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    validate(args.evidence, args.root)
    print("VV3 full-256 serializer evidence: STOP (static repair valid; atomic writer/rollback/runtime/player absent)")
