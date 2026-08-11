#!/usr/bin/env python3
"""Render a source-bound VV4 Expanded-256 serializer/reader candidate.

This builder consumes the newest locally certified VV4 Expanded progression
render and adds only the reviewed 256-record serializer/reader section.  It
does not enable public publication and it does not claim atomic-writer or
runtime/player certification.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path

try:
    from build_vv4_full256_serializer_candidate import (
        GATE,
        MODEL,
        READER,
        WRAPPER,
        _pe_checksum,
        require,
        section_header,
        section_page,
        validate,
    )
except ModuleNotFoundError:
    from scripts.build_vv4_full256_serializer_candidate import (
        GATE,
        MODEL,
        READER,
        WRAPPER,
        _pe_checksum,
        require,
        section_header,
        section_page,
        validate,
    )


BASE_SHA256 = (
    "AC430442DE23406236903CAA6FC9A992D52DCF3269A95ED345A9EF6F18B9C30A"
)
BASE_SIZE = 0xE3000
IMAGE_BASE = 0x400000
SECTION_HEADER_RAW = 0x2C0
SECTION_COUNT_RAW = 0x106
SIZE_OF_IMAGE_RAW = 0x150
CHECKSUM_RAW = 0x158
SERIALIZER_CALL_RAW = 0x1F125
SERIALIZER_CALL_VA = 0x41F125
DESERIALIZER_CALL_RAW = 0x1FD34
DESERIALIZER_CALL_VA = 0x41FD34
SERIALIZER_TARGET_VA = 0x871000
DESERIALIZER_TARGET_VA = 0x871100
STOCK_SERIALIZER_CALL = bytes.fromhex("E8766F0400")
STOCK_DESERIALIZER_CALL = bytes.fromhex("E8D7630400")
FINAL_SIZE = 0xE4000


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def call_rel32(call_site_va: int, target_va: int) -> bytes:
    displacement = target_va - (call_site_va + 5)
    require(-(1 << 31) <= displacement < (1 << 31), "call target displacement")
    return b"\xE8" + struct.pack("<i", displacement)


def render(source: bytes, model_path: Path = MODEL) -> tuple[bytes, dict[str, object]]:
    model = validate(model_path)
    require(len(source) == BASE_SIZE, "latest VV4 Expanded base size")
    require(sha256(source) == BASE_SHA256, "latest VV4 Expanded base identity")
    work = bytearray(source)

    require(work[:2] == b"MZ", "MZ")
    pe_offset = struct.unpack_from("<I", work, 0x3C)[0]
    require(pe_offset == 0x100 and work[pe_offset : pe_offset + 4] == b"PE\0\0", "PE")
    require(struct.unpack_from("<H", work, pe_offset + 4)[0] == 0x14C, "machine")
    require(struct.unpack_from("<H", work, pe_offset + 20)[0] == 0xE0, "optional header size")
    optional = pe_offset + 24
    require(struct.unpack_from("<H", work, optional)[0] == 0x10B, "PE32")
    require(struct.unpack_from("<I", work, optional + 28)[0] == IMAGE_BASE, "image base")
    require(struct.unpack_from("<I", work, optional + 32)[0] == 0x1000, "section alignment")
    require(struct.unpack_from("<I", work, optional + 36)[0] == 0x1000, "file alignment")
    require(struct.unpack_from("<I", work, optional + 60)[0] == 0x1000, "headers size")
    require(struct.unpack_from("<H", work, SECTION_COUNT_RAW)[0] == 5, "section count")
    require(struct.unpack_from("<I", work, SIZE_OF_IMAGE_RAW)[0] == 0x471000, "SizeOfImage")
    require(work[SECTION_HEADER_RAW : SECTION_HEADER_RAW + 40] == b"\0" * 40, "section header slot")
    require(work[SERIALIZER_CALL_RAW : SERIALIZER_CALL_RAW + 5] == STOCK_SERIALIZER_CALL, "serializer call")
    require(
        work[DESERIALIZER_CALL_RAW : DESERIALIZER_CALL_RAW + 5]
        == STOCK_DESERIALIZER_CALL,
        "deserializer call",
    )

    page = section_page()
    require(sha256(page) == model["section"]["page_sha256"], "reviewed .vv4x page")
    serializer_call = call_rel32(SERIALIZER_CALL_VA, SERIALIZER_TARGET_VA)
    deserializer_call = call_rel32(DESERIALIZER_CALL_VA, DESERIALIZER_TARGET_VA)

    struct.pack_into("<H", work, SECTION_COUNT_RAW, 6)
    struct.pack_into("<I", work, SIZE_OF_IMAGE_RAW, 0x472000)
    work[SECTION_HEADER_RAW : SECTION_HEADER_RAW + 40] = section_header()
    work[SERIALIZER_CALL_RAW : SERIALIZER_CALL_RAW + 5] = serializer_call
    work[DESERIALIZER_CALL_RAW : DESERIALIZER_CALL_RAW + 5] = deserializer_call
    work.extend(page)

    checksum = _pe_checksum(work, CHECKSUM_RAW)
    struct.pack_into("<I", work, CHECKSUM_RAW, checksum)
    require(len(work) == FINAL_SIZE, "candidate size")
    require(work[SECTION_HEADER_RAW : SECTION_HEADER_RAW + 40] == section_header(), "section header")
    require(sha256(work[BASE_SIZE:]) == sha256(page), "appended page")

    report = {
        "game_id": "vv4",
        "status": "static_candidate_runtime_stop",
        "publication_enabled": False,
        "runtime_go": False,
        "player_go": False,
        "source_sha256": BASE_SHA256,
        "source_size": BASE_SIZE,
        "candidate_sha256": sha256(work),
        "candidate_size": len(work),
        "candidate_section": {
            "name": ".vv4x",
            "raw_start": "0xE3000",
            "raw_end": "0xE4000",
            "rva": "0x471000",
            "va": "0x871000",
            "page_sha256": sha256(page),
        },
        "hooks": {
            "serializer": {
                "raw": "0x1F125",
                "before": STOCK_SERIALIZER_CALL.hex().upper(),
                "after": serializer_call.hex().upper(),
                "target_va": "0x871000",
            },
            "deserializer": {
                "raw": "0x1FD34",
                "before": STOCK_DESERIALIZER_CALL.hex().upper(),
                "after": deserializer_call.hex().upper(),
                "target_va": "0x871100",
            },
        },
        "reviewed_routines": {
            "serializer_length": len(WRAPPER),
            "deserializer_length": len(READER),
            "failure_gate_length": len(GATE),
            "bound": 256,
            "full_256_terminator": False,
            "reader_hard_bound": True,
            "tail_preserved": True,
        },
        "remaining_stop_gates": [
            "atomic save writer and checked failure handling at all six callers",
            "runtime save/load/reload and full-256 fault receipts",
            "player confirmation and package/publication certification",
        ],
    }
    return bytes(work), report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source_exe", type=Path)
    parser.add_argument("output_exe", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()

    if args.source_exe.resolve() == args.output_exe.resolve():
        raise SystemExit("refusing to overwrite the source executable")
    candidate, report = render(args.source_exe.read_bytes())
    args.output_exe.parent.mkdir(parents=True, exist_ok=True)
    args.output_exe.write_bytes(candidate)
    report_path = args.report or args.output_exe.with_suffix(".candidate.json")
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
