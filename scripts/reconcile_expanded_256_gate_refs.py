"""Reconcile an IDA reference export with the committed 256-cap manifest.

This is an evidence tool, not a patch generator.  It verifies every manifest
guard against the exact stock executable, every emitted byte against the
prototype, and maps decoded references and population-sized constants to the
guarded operand that owns them.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from collections import Counter
from pathlib import Path


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def _pe_layout(data: bytes) -> dict:
    pe = struct.unpack_from("<I", data, 0x3C)[0]
    if data[pe : pe + 4] != b"PE\0\0":
        raise RuntimeError("input is not a PE image")
    section_count = struct.unpack_from("<H", data, pe + 6)[0]
    optional_size = struct.unpack_from("<H", data, pe + 20)[0]
    characteristics = struct.unpack_from("<H", data, pe + 22)[0]
    optional = pe + 24
    section_table = optional + optional_size
    sections = []
    for index in range(section_count):
        offset = section_table + 40 * index
        sections.append(
            {
                "name": data[offset : offset + 8]
                .rstrip(b"\0")
                .decode("ascii", errors="replace"),
                "virtual_size": f"0x{struct.unpack_from('<I', data, offset + 8)[0]:X}",
                "rva": f"0x{struct.unpack_from('<I', data, offset + 12)[0]:X}",
                "raw_size": f"0x{struct.unpack_from('<I', data, offset + 16)[0]:X}",
                "raw_offset": f"0x{struct.unpack_from('<I', data, offset + 20)[0]:X}",
                "characteristics": f"0x{struct.unpack_from('<I', data, offset + 36)[0]:08X}",
            }
        )
    relocation_directory = optional + 96 + 5 * 8
    return {
        "coff_characteristics": f"0x{characteristics:04X}",
        "relocations_stripped": bool(characteristics & 1),
        "dll_characteristics": f"0x{struct.unpack_from('<H', data, optional + 70)[0]:04X}",
        "section_alignment": f"0x{struct.unpack_from('<I', data, optional + 32)[0]:X}",
        "file_alignment": f"0x{struct.unpack_from('<I', data, optional + 36)[0]:X}",
        "size_of_image": f"0x{struct.unpack_from('<I', data, optional + 56)[0]:X}",
        "checksum": f"0x{struct.unpack_from('<I', data, optional + 64)[0]:08X}",
        "base_relocation_rva": (
            f"0x{struct.unpack_from('<I', data, relocation_directory)[0]:X}"
        ),
        "base_relocation_size": (
            f"0x{struct.unpack_from('<I', data, relocation_directory + 4)[0]:X}"
        ),
        "sections": sections,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("game_id", choices=("vv3", "vv4", "vv5"))
    parser.add_argument("stock_exe")
    parser.add_argument("prototype_exe")
    parser.add_argument("ida_export")
    parser.add_argument("output_json")
    parser.add_argument("--manifest", default="data/expanded_256.json")
    args = parser.parse_args()

    stock_path = Path(args.stock_exe)
    prototype_path = Path(args.prototype_exe)
    stock = stock_path.read_bytes()
    prototype = prototype_path.read_bytes()
    manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
    game = manifest["games"][args.game_id]
    exported = json.loads(Path(args.ida_export).read_text(encoding="utf-8"))

    patches = game["patches"]
    by_offset = {int(patch["offset"], 16): patch for patch in patches}
    guard_errors = []
    ranges = []
    for patch in patches:
        offset = int(patch["offset"], 16)
        before = bytes.fromhex(patch["before"])
        after = bytes.fromhex(patch["after"])
        if len(before) != len(after):
            guard_errors.append(
                {
                    "offset": patch["offset"],
                    "error": "before/after length mismatch",
                }
            )
            continue
        if stock[offset : offset + len(before)] != before:
            guard_errors.append(
                {"offset": patch["offset"], "error": "stock guard mismatch"}
            )
        if prototype[offset : offset + len(after)] != after:
            guard_errors.append(
                {"offset": patch["offset"], "error": "prototype byte mismatch"}
            )
        ranges.append((offset, offset + len(after), patch["offset"]))

    overlaps = []
    ranges.sort()
    for previous, current in zip(ranges, ranges[1:]):
        if current[0] < previous[1]:
            overlaps.append({"left": previous[2], "right": current[2]})

    references = []
    for reference in exported["references"]:
        operand_text = reference.get("operand_file_offset")
        operand_offset = int(operand_text, 16) if operand_text else None
        patch = by_offset.get(operand_offset) if operand_offset is not None else None
        references.append(
            {
                "ea": reference["ea"],
                "operand_file_offset": operand_text,
                "reasons": reference["reasons"],
                "disasm": reference["disasm"],
                "manifest_match": patch is not None,
                "manifest_purpose": patch["purpose"] if patch else None,
            }
        )

    constants = []
    for constant in exported["constants"]:
        operand_text = constant.get("operand_file_offset")
        operand_offset = int(operand_text, 16) if operand_text else None
        patch = by_offset.get(operand_offset) if operand_offset is not None else None
        for value in constant["constants"]:
            constants.append(
                {
                    "value": value,
                    "ea": constant["ea"],
                    "operand_file_offset": operand_text,
                    "function": constant["function_name"],
                    "disasm": constant["disasm"],
                    "context": constant["context"],
                    "manifest_match": patch is not None,
                    "manifest_purpose": patch["purpose"] if patch else None,
                }
            )

    reference_summary = Counter()
    for reference in references:
        for reason in reference["reasons"]:
            reference_summary[
                f"{reason}:{'matched' if reference['manifest_match'] else 'unmatched'}"
            ] += 1
    constant_summary = Counter(
        (
            constant["value"],
            "matched" if constant["manifest_match"] else "unmatched",
        )
        for constant in constants
    )

    payload = {
        "game_id": args.game_id,
        "stock": {
            "path": str(stock_path),
            "size": len(stock),
            "sha256": _sha256(stock),
            "pe": _pe_layout(stock),
        },
        "prototype": {
            "path": str(prototype_path),
            "size": len(prototype),
            "sha256": _sha256(prototype),
            "pe": _pe_layout(prototype),
        },
        "manifest": {
            "path": args.manifest,
            "source_sha256": game["source_sha256"],
            "prototype_sha256": game["prototype_sha256"],
            "declared_patch_count": game["patch_count"],
            "actual_patch_count": len(patches),
            "purpose_counts": dict(
                sorted(Counter(patch["purpose"] for patch in patches).items())
            ),
            "guard_errors": guard_errors,
            "overlaps": overlaps,
        },
        "ida_export": {
            "path": args.ida_export,
            "decoded_instruction_heads": exported["decoded_instruction_heads"],
            "executable_segment_bytes": exported["executable_segment_bytes"],
            "reference_summary": {
                key: value for key, value in sorted(reference_summary.items())
            },
            "constant_summary": [
                {"value": value, "status": status, "count": count}
                for (value, status), count in sorted(constant_summary.items())
            ],
            "unmatched_moving_references": [
                reference
                for reference in references
                if not reference["manifest_match"]
                and any(
                    reason in {"moving_data_tail", "section_shr"}
                    for reason in reference["reasons"]
                )
            ],
            "unpatched_population_sized_constants": [
                constant for constant in constants if not constant["manifest_match"]
            ],
        },
    }
    Path(args.output_json).write_text(
        json.dumps(payload, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
