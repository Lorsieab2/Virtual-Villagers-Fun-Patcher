"""Audit current-feature references across a moved ``.shr`` section.

The stock all-feature render is IDA-analyzed to establish branch intent.  This
script then recomputes each expected relative displacement for the expanded
layout and also scans every byte position for four-byte values in the stock
``.shr`` range.  The latter are candidates, not automatically pointers:
instruction opcodes can coincidentally form the same integer.  Decoded operand
matches are identified separately.  The script never modifies either image.
"""

from __future__ import annotations

import argparse
import json
import struct
from pathlib import Path


def _sections(data: bytes) -> dict[str, dict[str, int]]:
    pe = struct.unpack_from("<I", data, 0x3C)[0]
    optional_size = struct.unpack_from("<H", data, pe + 20)[0]
    optional = pe + 24
    image_base = struct.unpack_from("<I", data, optional + 28)[0]
    count = struct.unpack_from("<H", data, pe + 6)[0]
    table = optional + optional_size
    result = {}
    for index in range(count):
        offset = table + index * 40
        name = data[offset : offset + 8].rstrip(b"\0").decode("ascii")
        result[name] = {
            "image_base": image_base,
            "virtual_size": struct.unpack_from("<I", data, offset + 8)[0],
            "rva": struct.unpack_from("<I", data, offset + 12)[0],
            "raw_size": struct.unpack_from("<I", data, offset + 16)[0],
            "raw_offset": struct.unpack_from("<I", data, offset + 20)[0],
        }
    return result


def _signed(data: bytes) -> int:
    return int.from_bytes(data, "little", signed=True)


def _encoded_signed(value: int, size: int) -> bytes:
    return value.to_bytes(size, "little", signed=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("game_id")
    parser.add_argument("stock_all_current_exe")
    parser.add_argument("expanded_all_current_exe")
    parser.add_argument("stock_ida_export")
    parser.add_argument("output_json")
    args = parser.parse_args()

    stock = Path(args.stock_all_current_exe).read_bytes()
    expanded = Path(args.expanded_all_current_exe).read_bytes()
    stock_sections = _sections(stock)
    expanded_sections = _sections(expanded)
    stock_shr = stock_sections[".shr"]
    expanded_shr = expanded_sections[".shr"]
    image_base = stock_shr["image_base"]
    old_start = image_base + stock_shr["rva"]
    old_size = max(stock_shr["virtual_size"], stock_shr["raw_size"])
    old_end = old_start + old_size
    new_start = image_base + expanded_shr["rva"]
    delta = new_start - old_start

    exported = json.loads(Path(args.stock_ida_export).read_text(encoding="utf-8"))
    decoded_absolute_offsets = {
        int(reference["operand_file_offset"], 16)
        for reference in exported["references"]
        if reference.get("operand_file_offset")
        and any(
            reason in {"section_shr", "stale_stock_shr"}
            for reason in reference.get("reasons", [])
        )
    }
    branches = []
    for branch in exported["branch_references"]:
        if branch["source_segment"] != ".shr" and branch["target_segment"] != ".shr":
            continue
        operand_offset = int(branch["operand_file_offset"], 16)
        operand_size = branch["operand_size"]
        instruction_ea = int(branch["ea"], 16)
        instruction_size = branch["instruction_size"]
        stock_target = int(branch["target"], 16)
        expanded_instruction_ea = (
            instruction_ea + delta
            if branch["source_segment"] == ".shr"
            else instruction_ea
        )
        expected_target = (
            stock_target + delta
            if branch["target_segment"] == ".shr"
            else stock_target
        )
        expected_displacement = (
            expected_target - (expanded_instruction_ea + instruction_size)
        )
        actual_bytes = expanded[operand_offset : operand_offset + operand_size]
        actual_displacement = _signed(actual_bytes)
        actual_target = (
            expanded_instruction_ea + instruction_size + actual_displacement
        )
        try:
            expected_bytes = _encoded_signed(expected_displacement, operand_size)
            encodable = True
        except OverflowError:
            expected_bytes = b""
            encodable = False
        branches.append(
            {
                "operand_file_offset": branch["operand_file_offset"],
                "source_segment": branch["source_segment"],
                "stock_ea": branch["ea"],
                "expanded_ea": f"0x{expanded_instruction_ea:X}",
                "stock_target": branch["target"],
                "expected_target": f"0x{expected_target:X}",
                "actual_target": f"0x{actual_target:X}",
                "operand_size": operand_size,
                "stock_bytes": stock[
                    operand_offset : operand_offset + operand_size
                ].hex().upper(),
                "expected_bytes": expected_bytes.hex().upper(),
                "actual_bytes": actual_bytes.hex().upper(),
                "encodable": encodable,
                "pass": encodable and actual_bytes == expected_bytes,
                "disasm": branch["disasm"],
            }
        )

    absolute_candidates = []
    shr_raw_start = stock_shr["raw_offset"]
    shr_raw_end = shr_raw_start + stock_shr["raw_size"]
    for offset in range(0, len(stock) - 3):
        value = struct.unpack_from("<I", stock, offset)[0]
        if not old_start <= value < old_end:
            continue
        expected = value + delta
        actual = struct.unpack_from("<I", expanded, offset)[0]
        absolute_candidates.append(
            {
                "file_offset": f"0x{offset:X}",
                "classification": (
                    "decoded_absolute_operand"
                    if offset in decoded_absolute_offsets
                    else "raw_pattern_requires_classification"
                ),
                "source_region": (
                    ".shr" if shr_raw_start <= offset < shr_raw_end else "external"
                ),
                "stock_value": f"0x{value:X}",
                "expected_value": f"0x{expected:X}",
                "actual_value": f"0x{actual:X}",
                "stock_bytes": stock[offset : offset + 4].hex().upper(),
                "expected_bytes": struct.pack("<I", expected).hex().upper(),
                "actual_bytes": expanded[offset : offset + 4].hex().upper(),
                "pass": actual == expected,
            }
        )

    payload = {
        "game_id": args.game_id,
        "stock_shr": {
            "va": f"0x{old_start:X}",
            "raw_offset": f"0x{stock_shr['raw_offset']:X}",
            "raw_size": f"0x{stock_shr['raw_size']:X}",
        },
        "expanded_shr": {
            "va": f"0x{new_start:X}",
            "raw_offset": f"0x{expanded_shr['raw_offset']:X}",
            "raw_size": f"0x{expanded_shr['raw_size']:X}",
        },
        "delta": f"0x{delta:X}",
        "relative_branches": branches,
        "relative_summary": {
            "total": len(branches),
            "pass": sum(branch["pass"] for branch in branches),
            "fail": sum(not branch["pass"] for branch in branches),
        },
        "absolute_candidates": absolute_candidates,
        "absolute_summary": {
            "total": len(absolute_candidates),
            "decoded_operands": sum(
                candidate["classification"] == "decoded_absolute_operand"
                for candidate in absolute_candidates
            ),
            "raw_patterns": sum(
                candidate["classification"]
                == "raw_pattern_requires_classification"
                for candidate in absolute_candidates
            ),
            "internal": sum(
                candidate["source_region"] == ".shr"
                for candidate in absolute_candidates
            ),
            "external": sum(
                candidate["source_region"] == "external"
                for candidate in absolute_candidates
            ),
            "pass": sum(candidate["pass"] for candidate in absolute_candidates),
            "fail": sum(
                not candidate["pass"] for candidate in absolute_candidates
            ),
        },
    }
    Path(args.output_json).write_text(
        json.dumps(payload, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
