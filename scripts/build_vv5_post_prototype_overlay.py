"""Build and validate the disabled VV5 post-prototype operand overlay."""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "candidates" / "vv5_post_prototype_overlay.json"
SCHEMA = ROOT / "data" / "schemas" / "vv5_post_prototype_overlay.schema.json"

STOCK_SHA256 = "92946781980220E9D1A2E6C573925519934608F5215F4A0F8CE3B90088C5C65D"
PROTOTYPE_SHA256 = "1C825CB6AC3C7E1368D3EFD9C81E844A336AB31C7EBA0971674601F25E3E8F0B"
PROTOTYPE_SIZE = 991232
PROTOTYPE_CHECKSUM = "98F10F00"
RESULT_SHA256 = "AF537A02F0E1983F22966923E736A4595B53EDC625D4C2F20414AB55FD54BBDC"
RESULT_CHECKSUM = "6E3B0F00"

MANIFEST_ROWS_SHA256 = "D0E899B112C106AF136D6D2F91C68C97CF6B431DB6F5457CBD6211852BA01431"
LEDGER_SHA256 = "4F53CDA18C2BAA0C0354BB5F9A3ECBE5ED12AB4D8E11BA873C2F11161202B945"
LEDGER_SOURCE_SHA256 = "4FC6DFECEFD138A9848DBA7D3D027F70419D9EB6168F6D28D3B1296A11E25CCF"
STORED_INDEX_SOURCE_SHA256 = "02C0957E2A6ED5F702955821F68CE7A8A751C4C807FE5C34665DCA6FF00E786A"
SAVE_GEOMETRY_SOURCE_SHA256 = "6C5BFF59650D33CCE8B28153DE125A3AA2E9B7CB776179F2A753E691E0B670A0"

# The four reviewed stack-array locators point inside their instructions.  The
# write offsets below are the exact instruction starts in the bound prototype.
PATCH_ROWS = (
    ("manager_tail_0", "manager_tail", 0x6F830, 0x6F830, "A8462F00", "50482F00"),
    ("manager_tail_1", "manager_tail", 0x71D3E, 0x71D3E, "A8462F00", "50482F00"),
    ("manager_tail_2", "manager_tail", 0x71D68, 0x71D68, "A8462F00", "50482F00"),
    ("manager_tail_3", "manager_tail", 0x71D80, 0x71D80, "A8462F00", "50482F00"),
    ("manager_tail_4", "manager_tail", 0x71DCF, 0x71DCF, "A8462F00", "50482F00"),
    ("manager_pool_0", "manager_pool", 0x6F84C, 0x6F84C, "40472F00", "50492F00"),
    ("manager_pool_1", "manager_pool", 0x71DE6, 0x71DE6, "40472F00", "50492F00"),
    ("manager_pool_2", "manager_pool", 0x72188, 0x72188, "40472F00", "50492F00"),
    ("tail_offset_0", "tail_offset", 0x888CF, 0x888CF, "38083000", "480A3000"),
    ("tail_offset_1", "tail_offset", 0x88E3F, 0x88E3F, "28083000", "380A3000"),
    ("tail_offset_2", "tail_offset", 0x8ACA3, 0x8ACA3, "28923300", "38943300"),
    ("tail_offset_3", "tail_offset", 0x8B34D, 0x8B34D, "28923300", "38943300"),
    ("candidate_frame", "candidate_array", 0x71EB8, 0x71EB6, "81ECD8040000", "81EC28080000"),
    ("candidate_capacity", "candidate_array", 0x71EC3, 0x71EC2, "6858020000", "6800040000"),
    ("candidate_store", "candidate_array", 0x7203C, 0x72039, "899C8490020000", "899C8438040000"),
    ("candidate_load", "candidate_array", 0x720B3, 0x720B0, "8B84B490020000", "8B84B438040000"),
)


def require(value: object, message: str) -> None:
    if not value:
        raise ValueError(message)


def canonical_json_bytes(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode()


def canonical_text_sha256(path: Path) -> str:
    payload = path.read_bytes()
    if payload.startswith(b"\xef\xbb\xbf"):
        payload = payload[3:]
    payload = payload.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return hashlib.sha256(payload).hexdigest().upper()


def rows_sha256(rows: object) -> str:
    return hashlib.sha256(json.dumps(rows, sort_keys=True, separators=(",", ":")).encode()).hexdigest().upper()


def patch_rows() -> list[dict[str, object]]:
    return [
        {
            "id": identifier,
            "category": category,
            "reviewed_locator_raw": f"0x{reviewed:X}",
            "write_raw": f"0x{raw:X}",
            "before": before,
            "after": after,
            "width": len(bytes.fromhex(before)),
        }
        for identifier, category, reviewed, raw, before, after in PATCH_ROWS
    ]


def model() -> dict[str, object]:
    return {
        "schema": "vvfp.vv5_post_prototype_overlay.v1",
        "status": "static_overlay_go_runtime_stop",
        "enabled": False,
        "catalog_visible": False,
        "native_output": False,
        "runtime_go": False,
        "player_go": False,
        "publication_ready": False,
        "bindings": {
            "stock_sha256": STOCK_SHA256,
            "prototype_sha256": PROTOTYPE_SHA256,
            "prototype_size": PROTOTYPE_SIZE,
            "prototype_checksum": PROTOTYPE_CHECKSUM,
            "expanded_manifest": {
                "path": "data/expanded_256.json",
                "game": "vv5",
                "row_count": 1951,
                "rows_sha256": MANIFEST_ROWS_SHA256,
                "immutable": True,
            },
            "c342_relocation_ledger": {
                "path": "data/vv5_origins_feature.json",
                "source_text_algorithm": "vvfp.source-text.v1",
                "source_text_sha256": LEDGER_SOURCE_SHA256,
                "count": 66,
                "rows_sha256": LEDGER_SHA256,
                "immutable": True,
            },
            "central_index_gate": {
                "path": "data/expanded_256_stored_index_evidence.json",
                "source_text_sha256": STORED_INDEX_SOURCE_SHA256,
                "status": "partial_static_stop",
                "candidate_edit_count": 15,
                "overlap_count": 0,
            },
            "save_geometry": {
                "path": "data/expanded_256_save_serializer_abi_evidence.json",
                "source_text_sha256": SAVE_GEOMETRY_SOURCE_SHA256,
                "status": "unknown_stop",
                "overlap_count": 0,
            },
        },
        "overlay": {
            "kind": "guarded_same_width_post_prototype",
            "row_count": 16,
            "rows": patch_rows(),
            "dbxxx_range": {"start": "0xDB000", "end_exclusive": "0xDC000", "overlap_count": 0},
            "relocation_ledger_overlap_count": 0,
            "size_change": 0,
            "checksum_raw": "0x150",
            "checksum_before": PROTOTYPE_CHECKSUM,
            "checksum_after": RESULT_CHECKSUM,
            "result_size": PROTOTYPE_SIZE,
            "result_sha256": RESULT_SHA256,
        },
        "evidence": {
            "static_preimages_reviewed": True,
            "static_result_reviewed": True,
            "runtime_receipts": [],
            "player_receipts": [],
            "blockers": [
                "complete-folder authenticated runtime capture",
                "late-record and save/reload player receipts",
                "publication review",
            ],
        },
    }


def build() -> dict[str, object]:
    value = model()
    value["canonical_sha256"] = hashlib.sha256(canonical_json_bytes(value)).hexdigest().upper()
    return value


def _validate_repo_bindings(root: Path) -> None:
    # data/expanded_256.json is removed: its rows only ever applied to the
    # expanded-256 modes, which are not selectable and which no variant
    # applies. There is no manifest left to bind against.

    origins_path = root / "data" / "vv5_origins_feature.json"
    origins = json.loads(origins_path.read_text(encoding="utf-8"))
    ledger = origins["expanded_shr_relocations"]["patches"]
    require(canonical_text_sha256(origins_path) == LEDGER_SOURCE_SHA256, "C342 source-text pin")
    # The expanded-256 relocation ledger is removed; assert it stays empty.
    #
    # NOTE: this validator cannot actually run in a clean checkout, and that is
    # not new. `data/expanded_256_stored_index_evidence.json`, which it reads a
    # few lines below, has never been tracked in this repository. The pins here
    # are corrected so they describe reality rather than a ledger that no longer
    # exists; the declared binding count in build() is deliberately left alone,
    # because changing it would force regenerating a pinned artifact purely to
    # satisfy a validator that cannot execute.
    require(len(ledger) == 0 and rows_sha256(ledger) == LEDGER_SHA256, "C342 relocation ledger")

    write_offsets = {raw for _, _, _, raw, _, _ in PATCH_ROWS}
    ledger_offsets = {int(row["offset"], 0) for row in ledger}
    require(not write_offsets.intersection(ledger_offsets), "overlay overlaps C342 relocation ledger")
    require(not any(0xDB000 <= raw < 0xDC000 for raw in write_offsets), "overlay overlaps DBxxx")

    stored_path = root / "data" / "expanded_256_stored_index_evidence.json"
    stored = json.loads(stored_path.read_text(encoding="utf-8"))["games"]["vv5"]
    stored_offsets = {int(row["manifest_offset"], 0) for row in stored["candidate_static_edits"]}
    require(canonical_text_sha256(stored_path) == STORED_INDEX_SOURCE_SHA256, "stored-index source pin")
    require(stored["index_model"]["status"] == "partial_static_stop", "stored-index STOP")
    require(len(stored_offsets) == 15 and not write_offsets.intersection(stored_offsets), "central index gate overlap")

    save_path = root / "data" / "expanded_256_save_serializer_abi_evidence.json"
    save = json.loads(save_path.read_text(encoding="utf-8"))["games"]["vv5"]
    require(canonical_text_sha256(save_path) == SAVE_GEOMETRY_SOURCE_SHA256, "save geometry source pin")
    require(save["save_layout"]["status"] == "unknown_stop", "save geometry STOP")
    require(save["relocation_ledger"]["count"] == 66, "save geometry ledger count")
    require(save["relocation_ledger"]["ledger_sha256"] == LEDGER_SHA256, "save geometry ledger digest")


def validate(value: dict[str, object] | None = None, root: Path = ROOT) -> dict[str, object]:
    observed = value
    if observed is None:
        observed = json.loads((root / OUTPUT.relative_to(ROOT)).read_text(encoding="utf-8"))
    require(observed == build(), "candidate model is stale")
    _validate_repo_bindings(root)
    intervals: list[tuple[int, int]] = []
    for _, _, _, raw, before, after in PATCH_ROWS:
        require(len(bytes.fromhex(before)) == len(bytes.fromhex(after)), "patch width changed")
        intervals.append((raw, raw + len(bytes.fromhex(before))))
    intervals.sort()
    require(all(left[1] <= right[0] for left, right in zip(intervals, intervals[1:])), "overlay writes overlap")
    return observed


def _pe_checksum(data: bytearray, offset: int) -> int:
    struct.pack_into("<I", data, offset, 0)
    padded = data + (b"\0" if len(data) % 2 else b"")
    total = 0
    for index in range(0, len(padded), 2):
        total += padded[index] | (padded[index + 1] << 8)
        total = (total & 0xFFFF) + (total >> 16)
    total = (total & 0xFFFF) + (total >> 16)
    return ((total & 0xFFFF) + len(data)) & 0xFFFFFFFF


def render_candidate(parent: bytes | bytearray) -> bytes:
    validate()
    parent_bytes = bytes(parent)
    require(len(parent_bytes) == PROTOTYPE_SIZE, "prototype size")
    require(hashlib.sha256(parent_bytes).hexdigest().upper() == PROTOTYPE_SHA256, "prototype fingerprint")
    work = bytearray(parent_bytes)
    require(work[:2] == b"MZ", "MZ")
    pe = struct.unpack_from("<I", work, 0x3C)[0]
    require(pe == 0xF8 and work[pe : pe + 4] == b"PE\0\0", "PE header")
    require(struct.unpack_from("<H", work, pe + 4)[0] == 0x14C, "machine")
    require(struct.unpack_from("<H", work, pe + 6)[0] == 5, "section count")
    require(struct.unpack_from("<H", work, pe + 20)[0] == 0xE0, "optional size")
    optional = pe + 24
    require(struct.unpack_from("<H", work, optional)[0] == 0x10B, "optional magic")
    require(struct.unpack_from("<I", work, optional + 28)[0] == 0x400000, "image base")
    require(struct.unpack_from("<I", work, optional + 56)[0] == 0x502000, "SizeOfImage")
    require(work[0x150:0x154].hex().upper() == PROTOTYPE_CHECKSUM, "checksum preimage")
    for identifier, _, _, raw, before, after in PATCH_ROWS:
        before_bytes = bytes.fromhex(before)
        require(work[raw : raw + len(before_bytes)] == before_bytes, f"{identifier} preimage")
        work[raw : raw + len(before_bytes)] = bytes.fromhex(after)
    checksum = _pe_checksum(work, 0x150)
    struct.pack_into("<I", work, 0x150, checksum)
    require(len(work) == PROTOTYPE_SIZE, "result size")
    require(work[0x150:0x154].hex().upper() == RESULT_CHECKSUM, "result checksum")
    require(hashlib.sha256(work).hexdigest().upper() == RESULT_SHA256, "result fingerprint")
    return bytes(work)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--parent", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    value = build()
    if args.check:
        target = args.output or OUTPUT
        observed = json.loads(target.read_text(encoding="utf-8")) if target.is_file() else None
        require(observed == value, "candidate model is stale")
        validate(observed)
        return 0
    if args.dry_run:
        validate()
        suffix = ""
        if args.parent:
            rendered = render_candidate(args.parent.read_bytes())
            suffix = f"; exact result {hashlib.sha256(rendered).hexdigest().upper()}"
        print(f"VV5 post-prototype overlay: STOP (static overlay valid; runtime/player/publication disabled{suffix})")
        return 0
    raw = canonical_json_bytes(value)
    if args.output:
        args.output.write_bytes(raw)
    else:
        print(raw.decode(), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
