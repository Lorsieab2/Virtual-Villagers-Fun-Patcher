"""Build the VV3 Expanded-256 capacity candidate without optional gameplay pages.

This builder is deliberately separate from the public renderer.  It emits a
static/package candidate only; runtime, player, and publication gates remain
false until the player supplies live execution evidence.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import build_vv3_expanded_time_warp as reviewed  # noqa: E402
import vv_fun_patcher as patcher  # noqa: E402
from expanded_atomic_writer import apply_atomic_writer_bytes  # noqa: E402


STOCK_SHA256 = "8BC5DB382D02BC5C21AD5F607580D60FF44A6519CC7EB133F03113BAACAE6503"
EXPANDED_MANIFEST_ROWS_SHA256 = "04B93127BC4D5C6787AB013DE9205813D44947DBC16A370DBC234C06588AC3FB"
GAME_ID = "vv3"
CAPACITY_SECTION_NAME = ".vv3rs"
CAPACITY_SECTION_RAW = 0xCB000
CAPACITY_SECTION_RVA = 0x3B8000
CAPACITY_SECTION_SIZE = 0x1000
CAPACITY_SECTION_HEADER_RAW = 0x2C8
CAPACITY_SECTION_COUNT_BEFORE = bytes.fromhex("0500")
CAPACITY_SECTION_COUNT_AFTER = bytes.fromhex("0600")
CAPACITY_SIZE_OF_IMAGE_BEFORE = bytes.fromhex("00803B00")
CAPACITY_SIZE_OF_IMAGE_AFTER = bytes.fromhex("00903B00")
CAPACITY_SECTION_CHARACTERISTICS = 0x40000040  # initialized read/write data, not executable

CRITICAL_OFFSETS = {
    "fault_site_0xD1A0": 0xD1A0,
    "healer_endpoint": 0x5FA46,
    "population_loop_26_a": 0x5E8F8,
    "population_loop_26_b": 0x5EA9C,
    "reset_loop_26": 0x5D7D6,
    "three_child_free_slot_guard": 0x7B266,
    "two_child_free_slot_guard": 0x7B286,
    "chief_candidate_assignment": 0x5FB9C,
    "time_warp_constructor_hook_unchanged": 0x6547D,
    "time_warp_event_hook_unchanged": 0x65640,
}
CRITICAL_WIDTHS = {
    "fault_site_0xD1A0": 8,
    "healer_endpoint": 4,
    "population_loop_26_a": 5,
    "population_loop_26_b": 5,
    "reset_loop_26": 5,
    "three_child_free_slot_guard": 4,
    "two_child_free_slot_guard": 4,
    "chief_candidate_assignment": 4,
    "time_warp_constructor_hook_unchanged": 5,
    "time_warp_event_hook_unchanged": 8,
}


def sha256_bytes(data: bytes | bytearray) -> str:
    return hashlib.sha256(bytes(data)).hexdigest().upper()


def source_text_sha256(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def section_header() -> bytes:
    header = bytearray(40)
    header[:8] = CAPACITY_SECTION_NAME.encode("ascii").ljust(8, b"\0")
    struct.pack_into(
        "<IIII",
        header,
        8,
        CAPACITY_SECTION_SIZE,
        CAPACITY_SECTION_RVA,
        CAPACITY_SECTION_SIZE,
        CAPACITY_SECTION_RAW,
    )
    struct.pack_into("<I", header, 36, CAPACITY_SECTION_CHARACTERISTICS)
    return bytes(header)


def install_capacity_reservation(parent: bytearray) -> tuple[bytearray, list[dict[str, str]]]:
    """Reserve the first appended page without adding executable gameplay code."""

    data = bytearray(parent)
    if len(data) != CAPACITY_SECTION_RAW:
        raise RuntimeError(f"VV3 Expanded parent size mismatch: {len(data):#x}")
    rows = [
        {
            "offset": "0x10E",
            "before": CAPACITY_SECTION_COUNT_BEFORE.hex(),
            "after": CAPACITY_SECTION_COUNT_AFTER.hex(),
            "purpose": "add the neutral VV3 reserved capacity section",
        },
        {
            "offset": "0x158",
            "before": CAPACITY_SIZE_OF_IMAGE_BEFORE.hex(),
            "after": CAPACITY_SIZE_OF_IMAGE_AFTER.hex(),
            "purpose": "extend SizeOfImage through the neutral capacity section",
        },
        {
            "offset": f"0x{CAPACITY_SECTION_HEADER_RAW:X}",
            "before": bytes(40).hex(),
            "after": section_header().hex(),
            "purpose": "install the non-executable .vv3rs reserved section header",
        },
    ]
    reviewed.apply_rows(data, rows)
    data.extend(bytes(CAPACITY_SECTION_SIZE))
    reviewed.canonicalize(data)
    return data, rows


def build_candidate(mode: str) -> tuple[bytearray, dict[str, Any]]:
    build = next(item for item in patcher.load_builds() if item.id == GAME_ID)
    source = ROOT / "research" / "stock-executables" / build.input_name
    original = source.read_bytes()
    if sha256_bytes(original) != STOCK_SHA256:
        raise RuntimeError("VV3 stock identity mismatch")

    parent = reviewed.expanded_parent(mode)
    reserved, reservation_rows = install_capacity_reservation(parent)
    static = reviewed.install_static(reserved)
    atomic, atomic_records, atomic_metadata = apply_atomic_writer_bytes(static, GAME_ID)
    reviewed.canonicalize(atomic)

    if len(atomic) != 0xCE000:
        raise RuntimeError(f"VV3 final size drifted: {len(atomic):#x}")
    if atomic[CAPACITY_SECTION_RAW : CAPACITY_SECTION_RAW + CAPACITY_SECTION_SIZE] != bytes(
        CAPACITY_SECTION_SIZE
    ):
        raise RuntimeError("VV3 neutral capacity section is not zero-filled")
    if bytes(atomic[0x6547D : 0x6547D + 5]) != bytes.fromhex("8B4C243C5F"):
        raise RuntimeError("VV3 Time Warp constructor hook changed")
    if bytes(atomic[0x65640 : 0x65640 + 8]) != bytes.fromhex("6AFF64A100000000"):
        raise RuntimeError("VV3 Time Warp event hook changed")

    variant = patcher.get_patch_variant(build, mode)
    expanded_rows = patcher._expanded_patches(build, variant)
    safety_rows = patcher._safety_patches(build, mode)
    population_rows = variant["patches"]
    static_candidate = json.loads(
        (ROOT / "data" / "candidates" / "vv3_full256_serializer_candidate.json").read_text(
            encoding="utf-8"
        )
    )
    report: dict[str, Any] = {
        "schema": "vvfp.vv3_expanded_256_capacity_build.v1",
        "status": "STATIC_BUILD_STOP_RUNTIME_PLAYER",
        "game_id": GAME_ID,
        "mode": mode,
        "source": {
            "path": str(source),
            "size": len(original),
            "sha256": sha256_bytes(original),
        },
        "output": {
            "size": len(atomic),
            "sha256": sha256_bytes(atomic),
            "pe_checksum": bytes(atomic[0x160 : 0x164]).hex().upper(),
        },
        "gates": {
            "native_output": False,
            "runtime_go": False,
            "player_go": False,
            "publication_ready": False,
        },
        "composition": {
            "expanded_parent": {
                "size": len(parent),
                "sha256": sha256_bytes(parent),
                "expanded_row_count": len(expanded_rows),
                "safety_row_count": len(safety_rows),
                "population_row_count": len(population_rows),
                "manifest_rows_sha256": EXPANDED_MANIFEST_ROWS_SHA256,
            },
            "neutral_capacity_section": {
                "name": CAPACITY_SECTION_NAME,
                "raw": f"0x{CAPACITY_SECTION_RAW:X}",
                "rva": f"0x{CAPACITY_SECTION_RVA:X}",
                "size": CAPACITY_SECTION_SIZE,
                "characteristics": f"0x{CAPACITY_SECTION_CHARACTERISTICS:08X}",
                "executable": False,
                "zero_filled": True,
                "rows": reservation_rows,
            },
            "static_serializer_reader": {
                "candidate_id": static_candidate["candidate_id"],
                "page_raw": static_candidate["section_plan"]["raw_start"],
                "page_sha256": static_candidate["section_plan"]["section_sha256"],
                "hook_count": len(static_candidate["hooks"]),
                "runtime_go": False,
                "player_go": False,
            },
            "atomic_writer": {
                "records": atomic_records,
                "metadata": atomic_metadata,
            },
        },
        "critical_bytes": {
            name: bytes(atomic[offset : offset + CRITICAL_WIDTHS[name]]).hex().upper()
            for name, offset in CRITICAL_OFFSETS.items()
        },
        "explicit_non_changes": [
            "No Time Warp executable page or Time Warp hooks are installed.",
            "The original stock executable is not overwritten.",
            "No companion DLL is required or emitted by this capacity build.",
        ],
        "required_player_evidence": [
            "live crash trace with exception code, fault RVA, registers, caller return address, and stack",
            "startup/new-village/load-stock-save/reload/offline-catch-up results",
            "population checkpoints 125, 150, 151, 160, 200, 254, 255, and 256",
            "save, exit, reload, and continued play at 256",
        ],
        "builder_source_sha256": source_text_sha256(Path(__file__)),
        "atomic_generator_source_sha256": source_text_sha256(ROOT / "src" / "expanded_atomic_writer.py"),
    }
    return atomic, report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--mode",
        choices=reviewed.MODES,
        action="append",
        dest="modes",
        help="Build one or more exact Expanded-256 modes; defaults to both.",
    )
    args = parser.parse_args()
    modes = tuple(args.modes or reviewed.MODES)
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    index: dict[str, Any] = {
        "schema": "vvfp.vv3_expanded_256_capacity_build_index.v1",
        "status": "STATIC_BUILD_STOP_RUNTIME_PLAYER",
        "outputs": [],
    }
    for mode in modes:
        data, report = build_candidate(mode)
        suffix = "immediate" if mode == "experimental_expanded_256" else "progression"
        name = f"Virtual Villagers - The Secret City - Expanded 256 Cap - {suffix}.exe"
        exe = output_dir / name
        exe.write_bytes(data)
        report_path = output_dir / f"{exe.stem}.build-report.json"
        report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        index["outputs"].append(
            {
                "mode": mode,
                "executable": name,
                "report": report_path.name,
                "size": report["output"]["size"],
                "sha256": report["output"]["sha256"],
            }
        )
    (output_dir / "BUILD-STATUS.txt").write_text(
        "VV3 Expanded-256 capacity candidate\n"
        "Static/package build only. Runtime, player, and publication gates are STOP.\n"
        "Do not overwrite the stock executable.\n",
        encoding="utf-8",
    )
    (output_dir / "build-index.json").write_text(
        json.dumps(index, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
