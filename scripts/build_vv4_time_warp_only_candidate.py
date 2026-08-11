#!/usr/bin/env python3
"""Render the VV4 Expanded-256 candidate with only Time Warp in Upgrades.

The source is the authenticated clean Expanded-256 progression base.  This
builder intentionally does not consume the all-current Origins render: that
render already contains additional Origins rows and therefore cannot satisfy
the Time-Warp-only request.  The existing serializer/reader section is then
added so the candidate retains the prior 256-record save extension.

This remains a static candidate.  It does not claim runtime/player approval or
publication readiness.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import build_expanded_time_warp as time_warp  # noqa: E402
import build_vv4_full256_serializer_candidate as serializer  # noqa: E402


BASE = (
    ROOT
    / "outputs/expanded-256-audit/vv4-renders/"
    / "vv4-experimental_expanded_256_progression-base.exe"
)
BASE_SHA256 = "737F475764EBB9F35BC6C68337698D46F6D03BA0560B9BE4E352F80AF48FE791"
BASE_SIZE = 0xE3000
FINAL_SIZE = 0xE4000
FINAL_SHA256 = "3AD22192212E3D82455EF771AB7B37E841082EE08F3FF10AEB826F2EE5D0AE0F"
MODE = "experimental_expanded_256_progression"
FEATURE_ID = "vv4_expanded_256_time_warp"

TIME_WARP_PAYLOAD_RAW = 0x89373
TIME_WARP_PAYLOAD_SHA256 = "AE2CF0EFF570C6492C00B4C9C1E4399D40B4BBD670265681035990436999C062"
TIME_WARP_CONSTRUCTOR_RAW = 0x3E165
TIME_WARP_CONSTRUCTOR_BEFORE = bytes.fromhex("8BC68B4C244C")
TIME_WARP_CONSTRUCTOR_AFTER = bytes.fromhex("E949B2040090")
TIME_WARP_HANDLER_RAW = 0x3E9F0
TIME_WARP_HANDLER_BEFORE = bytes.fromhex("578BF9E828F00000")
TIME_WARP_HANDLER_AFTER = bytes.fromhex("E97EA90400909090")

SERIALIZER_CALL_RAW = 0x1F125
SERIALIZER_CALL_BEFORE = bytes.fromhex("E8766F0400")
DESERIALIZER_CALL_RAW = 0x1FD34
DESERIALIZER_CALL_BEFORE = bytes.fromhex("E8D7630400")
SECTION_COUNT_RAW = 0x106
SIZE_OF_IMAGE_RAW = 0x150
CHECKSUM_RAW = 0x158
SECTION_HEADER_RAW = 0x2C0

COMPANION = ROOT / "data/candidates/VVFP VV5 Task9 Origins Icons.dll"
COMPANION_SHA256 = "B402ED8316CD6EB2C43B056848E622DC0924188C81C683F5E2813466AF8045D0"
COMPANION_SIZE = 297472


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def require(value: object, message: str) -> None:
    if not value:
        raise ValueError(message)


def render(source: bytes) -> tuple[bytes, dict[str, object]]:
    require(len(source) == BASE_SIZE, "clean Expanded-256 base size")
    require(sha256(source) == BASE_SHA256, "clean Expanded-256 base identity")
    require(COMPANION.is_file(), "Time Warp companion DLL is missing")
    require(COMPANION.stat().st_size == COMPANION_SIZE, "Time Warp companion DLL size")
    require(sha256(COMPANION.read_bytes()) == COMPANION_SHA256, "Time Warp companion DLL identity")

    payload, layout = time_warp.build_vv4_payload(MODE)
    require(len(payload) == 3213, "Time Warp payload size")
    require(sha256(payload) == TIME_WARP_PAYLOAD_SHA256, "Time Warp payload identity")

    work = bytearray(source)
    require(
        work[TIME_WARP_PAYLOAD_RAW : TIME_WARP_PAYLOAD_RAW + len(payload)]
        == b"\0" * len(payload),
        "Time Warp cave preimage",
    )
    require(
        work[TIME_WARP_CONSTRUCTOR_RAW : TIME_WARP_CONSTRUCTOR_RAW + len(TIME_WARP_CONSTRUCTOR_BEFORE)]
        == TIME_WARP_CONSTRUCTOR_BEFORE,
        "Time Warp constructor hook preimage",
    )
    require(
        work[TIME_WARP_HANDLER_RAW : TIME_WARP_HANDLER_RAW + len(TIME_WARP_HANDLER_BEFORE)]
        == TIME_WARP_HANDLER_BEFORE,
        "Time Warp handler hook preimage",
    )
    work[TIME_WARP_PAYLOAD_RAW : TIME_WARP_PAYLOAD_RAW + len(payload)] = payload
    work[TIME_WARP_CONSTRUCTOR_RAW : TIME_WARP_CONSTRUCTOR_RAW + len(TIME_WARP_CONSTRUCTOR_AFTER)] = (
        TIME_WARP_CONSTRUCTOR_AFTER
    )
    work[TIME_WARP_HANDLER_RAW : TIME_WARP_HANDLER_RAW + len(TIME_WARP_HANDLER_AFTER)] = (
        TIME_WARP_HANDLER_AFTER
    )

    require(work[SECTION_HEADER_RAW : SECTION_HEADER_RAW + 40] == b"\0" * 40, "serializer section slot")
    require(
        work[SERIALIZER_CALL_RAW : SERIALIZER_CALL_RAW + len(SERIALIZER_CALL_BEFORE)]
        == SERIALIZER_CALL_BEFORE,
        "serializer call preimage",
    )
    require(
        work[DESERIALIZER_CALL_RAW : DESERIALIZER_CALL_RAW + len(DESERIALIZER_CALL_BEFORE)]
        == DESERIALIZER_CALL_BEFORE,
        "deserializer call preimage",
    )

    page = serializer.section_page()
    struct.pack_into("<H", work, SECTION_COUNT_RAW, 6)
    struct.pack_into("<I", work, SIZE_OF_IMAGE_RAW, 0x472000)
    work[SECTION_HEADER_RAW : SECTION_HEADER_RAW + 40] = serializer.section_header()
    work[SERIALIZER_CALL_RAW : SERIALIZER_CALL_RAW + 5] = bytes.fromhex("E8D61E4500")
    work[DESERIALIZER_CALL_RAW : DESERIALIZER_CALL_RAW + 5] = bytes.fromhex("E8C7134500")
    work.extend(page)

    checksum = serializer._pe_checksum(work, CHECKSUM_RAW)
    struct.pack_into("<I", work, CHECKSUM_RAW, checksum)
    require(len(work) == FINAL_SIZE, "candidate size")
    require(sha256(work) == FINAL_SHA256, "candidate identity")

    report: dict[str, object] = {
        "game_id": "vv4",
        "mode": MODE,
        "feature_id": FEATURE_ID,
        "status": "static_candidate_runtime_stop",
        "publication_enabled": False,
        "runtime_go": False,
        "player_go": False,
        "base": {
            "path": "outputs/expanded-256-audit/vv4-renders/vv4-experimental_expanded_256_progression-base.exe",
            "sha256": BASE_SHA256,
            "size": BASE_SIZE,
        },
        "candidate": {"sha256": FINAL_SHA256, "size": FINAL_SIZE},
        "tech_screen": {
            "button": "Upgrades",
            "enabled_rows": ["Time Warp"],
            "other_origins_rows_enabled": False,
            "command": 13,
        },
        "time_warp": {
            "payload_raw": f"0x{TIME_WARP_PAYLOAD_RAW:X}",
            "payload_size": len(payload),
            "payload_sha256": sha256(payload),
            "handler_length": layout["handler_length"],
            "constructor_length": layout["constructor_length"],
            "show_menu_length": layout["show_menu_length"],
            "show_message_length": layout["show_message_length"],
            "transaction_length": layout["transaction_length"],
            "constructor_hook": {
                "raw": f"0x{TIME_WARP_CONSTRUCTOR_RAW:X}",
                "before": TIME_WARP_CONSTRUCTOR_BEFORE.hex().upper(),
                "after": TIME_WARP_CONSTRUCTOR_AFTER.hex().upper(),
            },
            "handler_hook": {
                "raw": f"0x{TIME_WARP_HANDLER_RAW:X}",
                "before": TIME_WARP_HANDLER_BEFORE.hex().upper(),
                "after": TIME_WARP_HANDLER_AFTER.hex().upper(),
            },
        },
        "serializer_section": {
            "name": ".vv4x",
            "raw_start": "0xE3000",
            "raw_end": "0xE4000",
            "rva": "0x471000",
            "va": "0x871000",
            "page_sha256": sha256(page),
            "bound": 256,
        },
        "companion": {
            "source": "data/candidates/VVFP VV5 Task9 Origins Icons.dll",
            "destination": "VVFP Origins Icons.dll",
            "sha256": COMPANION_SHA256,
            "size": COMPANION_SIZE,
        },
        "remaining_stop_gates": [
            "atomic save writer and checked failure handling at all six callers",
            "runtime save/load/reload and full-256 fault receipts",
            "live player confirmation and package/publication certification",
        ],
    }
    return bytes(work), report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source_exe", nargs="?", type=Path, default=BASE)
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
