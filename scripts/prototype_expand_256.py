"""Prototype the structural PE expansion used by the experimental 256 mode.

This consumes IDA audit JSON from research/. It is intentionally a research
tool; the release patcher will use a reviewed, committed manifest instead.
"""

from __future__ import annotations

import argparse
import json
import struct
from pathlib import Path


CONFIG = {
    "vv3": {
        "imagebase": 0x400000,
        "manager": 0x59E110,
        "end150": 0x6C5D2C,
        "data_end": 0x6C7518,
        "extra": 106 * 0x1F8C,
        "save_extra": 106 * 284,
        "manager_range": (0x45C730, 0x460600),
        "record_tokens": (
            "sub_45C840",
            "unk_59E110",
            "byte_59E110",
            "8076",
            "2019",
        ),
        "save_count_functions": {0x428810, 0x45C860, 0x45C8D0, 0x45EF80},
    },
    "vv4": {
        "imagebase": 0x400000,
        "manager": 0x50E568,
        "end150": 0x6BFCD4,
        "data_end": 0x727344,
        "extra": 106 * 0x2E3C,
        "save_extra": 106 * 260,
        "manager_range": (0x465F20, 0x468E00),
        "record_tokens": (
            "sub_466040",
            "unk_50E568",
            "dword_50E568",
            "11836",
            "2959",
        ),
        "save_count_functions": {0x41FAF0, 0x4660A0, 0x466110},
    },
    "vv5": {
        "imagebase": 0x400000,
        "manager": 0x554148,
        "end150": 0x70F368,
        "data_end": 0x7B1DA4,
        "extra": 106 * 0x2F44,
        "save_extra": 106 * 280,
        "manager_range": (0x46F9B0, 0x473000),
        "record_tokens": (
            "sub_46F950",
            "unk_554148",
            "dword_554148",
            "12100",
            "3025",
        ),
        "save_count_functions": {0x4255E0, 0x46F9B0, 0x46FA20},
    },
}


def align(value: int, alignment: int) -> int:
    return (value + alignment - 1) & ~(alignment - 1)


def update_pe_checksum(data: bytearray, log: list) -> None:
    pe = struct.unpack_from("<I", data, 0x3C)[0]
    checksum_offset = pe + 24 + 64
    old = struct.unpack_from("<I", data, checksum_offset)[0]
    struct.pack_into("<I", data, checksum_offset, 0)
    padded = data + (b"\0" if len(data) % 2 else b"")
    total = 0
    for offset in range(0, len(padded), 2):
        total += padded[offset] | (padded[offset + 1] << 8)
        total = (total & 0xFFFF) + (total >> 16)
    total = (total & 0xFFFF) + (total >> 16)
    checksum = ((total & 0xFFFF) + len(data)) & 0xFFFFFFFF
    struct.pack_into("<I", data, checksum_offset, checksum)
    log.append(
        {
            "offset": checksum_offset,
            "old": old,
            "new": checksum,
            "label": "recompute PE checksum",
        }
    )


def patch_dword(data: bytearray, offset: int, old: int, new: int, label: str, log: list) -> None:
    actual = struct.unpack_from("<I", data, offset)[0]
    if actual != old:
        raise RuntimeError(
            f"{label}: expected 0x{old:08X} at 0x{offset:X}, found 0x{actual:08X}"
        )
    struct.pack_into("<I", data, offset, new)
    log.append({"offset": offset, "old": old, "new": new, "label": label})


def operand_offset(data: bytearray, hit: dict, imagebase: int, old: int) -> int:
    instruction_offset = int(hit["ea"], 16) - imagebase
    encoded = struct.pack("<I", old)
    hinted = instruction_offset + hit["operand_offb"]
    if data[hinted : hinted + 4] == encoded:
        return hinted
    size = hit.get("instruction_size", 15)
    instruction = data[instruction_offset : instruction_offset + size]
    matches = [
        instruction_offset + index
        for index in range(max(0, len(instruction) - 3))
        if instruction[index : index + 4] == encoded
    ]
    if len(matches) != 1:
        raise RuntimeError(
            f"{hit['ea']} {hit['disasm']}: could not uniquely locate "
            f"0x{old:08X} in {instruction.hex()}"
        )
    return matches[0]


def matching_value(hit: dict, low: int, high: int) -> int | None:
    for text in hit["values"]:
        value = int(text, 16)
        if low <= value < high:
            return value
    return None


def parse_pe(data: bytearray) -> dict:
    pe = struct.unpack_from("<I", data, 0x3C)[0]
    if data[pe : pe + 4] != b"PE\0\0":
        raise RuntimeError("Not a PE file")
    section_count = struct.unpack_from("<H", data, pe + 6)[0]
    optional_size = struct.unpack_from("<H", data, pe + 20)[0]
    optional = pe + 24
    section_table = optional + optional_size
    sections = []
    for index in range(section_count):
        offset = section_table + 40 * index
        sections.append(
            {
                "header": offset,
                "name": bytes(data[offset : offset + 8]).rstrip(b"\0").decode(),
                "virtual_size": struct.unpack_from("<I", data, offset + 8)[0],
                "rva": struct.unpack_from("<I", data, offset + 12)[0],
                "raw_size": struct.unpack_from("<I", data, offset + 16)[0],
                "raw": struct.unpack_from("<I", data, offset + 20)[0],
            }
        )
    return {
        "pe": pe,
        "optional": optional,
        "section_alignment": struct.unpack_from("<I", data, optional + 32)[0],
        "size_of_image_offset": optional + 56,
        "resource_directory_offset": optional + 96 + 8 * 2,
        "sections": sections,
    }


def expand_stack_candidate_arrays(
    data: bytearray, audit: dict, imagebase: int, log: list, patched_offsets: set[int]
) -> set[int]:
    """Grow bottom-of-frame villager index arrays from 150 to 256 entries."""
    expanded_functions: set[int] = set()
    markers = ("[150]", "[151]", "[300]", "[450]")
    for function in audit["functions"]:
        pseudocode = function["pseudocode"]
        marker = next((item for item in markers if item in pseudocode), None)
        if marker is None or not function.get("instructions"):
            continue
        function_ea = int(function["ea"], 16)
        total_entries = int(marker[1:-1])
        partitions = total_entries // 150 if total_entries % 150 == 0 else 1
        frame_extra = (256 - 150) * 4 * partitions
        instructions = function["instructions"]
        prologue = next(
            (
                instruction
                for instruction in instructions[:4]
                if instruction["disasm"].startswith("sub     esp,")
            ),
            None,
        )
        if prologue is None:
            raise RuntimeError(
                f"{function['ea']}: candidate array function has an unsupported prologue"
            )
        frame_operand = prologue["operands"][1]
        old_frame = int(frame_operand["value"], 16)
        new_frame = old_frame + frame_extra
        frame_offset = (
            int(prologue["ea"], 16) - imagebase + frame_operand["offb"]
        )
        patch_dword(
            data,
            frame_offset,
            old_frame,
            new_frame,
            "expand candidate-array stack frame",
            log,
        )
        patched_offsets.add(frame_offset)

        indexed_local_displacements = []
        for instruction in instructions:
            for operand in instruction["operands"]:
                if operand["type"] != 4 or operand["phrase"] != 4:
                    continue
                displacement = int(operand["addr"], 16)
                if (
                    0 < displacement <= old_frame
                    and "*4" in instruction["disasm"]
                ):
                    indexed_local_displacements.append(displacement)
        first_array_base = min(
            displacement
            for displacement in indexed_local_displacements
            if displacement > 0
        )

        for instruction in instructions:
            instruction_ea = int(instruction["ea"], 16)
            disasm = instruction["disasm"]
            for operand in instruction["operands"]:
                if operand["type"] != 4 or operand["phrase"] != 4:
                    continue
                old_displacement = int(operand["addr"], 16)
                new_displacement = old_displacement
                if old_displacement > old_frame:
                    new_displacement += frame_extra
                elif partitions > 1 and old_displacement >= first_array_base + 600:
                    partition = (old_displacement - first_array_base) // 600
                    partition = min(partition, partitions - 1)
                    new_displacement += partition * (256 - 150) * 4
                if new_displacement == old_displacement:
                    continue
                offset = instruction_ea - imagebase + operand["offb"]
                patch_dword(
                    data,
                    offset,
                    old_displacement,
                    new_displacement,
                    "move expanded candidate-array stack reference",
                    log,
                )
                patched_offsets.add(offset)

            if disasm.startswith("add     esp,"):
                operand = instruction["operands"][1]
                if int(operand["value"], 16) == old_frame:
                    offset = instruction_ea - imagebase + operand["offb"]
                    patch_dword(
                        data,
                        offset,
                        old_frame,
                        new_frame,
                        "restore expanded candidate-array stack frame",
                        log,
                    )
                    patched_offsets.add(offset)
        expanded_functions.add(function_ea)
    return expanded_functions


def expand(game: str, source: Path, audit_path: Path) -> tuple[bytearray, list]:
    config = CONFIG[game]
    data = bytearray(source.read_bytes())
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    log: list[dict] = []
    patched_offsets: set[int] = set()
    pe = parse_pe(data)
    expanded_stack_functions = expand_stack_candidate_arrays(
        data, audit, config["imagebase"], log, patched_offsets
    )

    for function in audit["functions"]:
        for hit in function["hits"]:
            reasons = hit["reasons"]
            old = new = None
            label = ""
            if "relocate_absolute_data_tail" in reasons:
                old = matching_value(hit, config["end150"], config["data_end"])
                if old is not None:
                    new = old + config["extra"]
                    label = "relocate absolute .data tail reference"
            if old is None and "relocate_manager_tail_offset" in reasons:
                low = config["end150"] - config["manager"]
                high = config["data_end"] - config["manager"]
                old = matching_value(hit, low, high)
                if old is not None:
                    new = old + config["extra"]
                    label = "relocate manager-relative tail reference"
            if old is None and "expand_save_tail_offset" in reasons:
                save_tail = int(audit["config"]["save_tail"], 16)
                save_max = int(audit["config"]["save_max"], 16)
                old = matching_value(hit, save_tail, save_max + 1)
                if old is not None:
                    new = old + config["save_extra"]
                    label = "expand saved-state tail offset"
            if old is not None:
                offset = operand_offset(data, hit, config["imagebase"], old)
                if offset in patched_offsets:
                    continue
                patch_dword(data, offset, old, new, label, log)
                patched_offsets.add(offset)

    # IDA can identify compiler-runtime instructions as code even when they are
    # intentionally not assigned to a function. Patch only their decoded
    # operands; a raw sliding-byte sweep can corrupt unrelated instructions.
    for hit in audit.get("code_tail_hits", []):
        old = matching_value(hit, config["end150"], config["data_end"])
        if old is None:
            continue
        hinted_offset = (
            int(hit["ea"], 16) - config["imagebase"] + hit["operand_offb"]
        )
        if hinted_offset in patched_offsets:
            continue
        offset = operand_offset(data, hit, config["imagebase"], old)
        if offset in patched_offsets:
            continue
        patch_dword(
            data,
            offset,
            old,
            old + config["extra"],
            "relocate decoded absolute .data tail reference",
            log,
        )
        patched_offsets.add(offset)

    loop_phrases = (
        "< 150",
        ">= 150",
        "i = 150",
        "j = 150",
        "v1 = 149",
        "v2 = 149",
        "v4 = 149",
        "v11 = 149",
        "for ( i = 149",
        "for ( j = 149",
    )
    for function in audit["functions"]:
        function_ea = int(function["ea"], 16)
        pseudocode = function["pseudocode"]
        in_manager_range = (
            config["manager_range"][0] <= function_ea < config["manager_range"][1]
        )
        has_record_token = any(token in pseudocode for token in config["record_tokens"])
        is_save_count = function_ea in config["save_count_functions"]
        has_loop = any(phrase in pseudocode for phrase in loop_phrases)
        if not (has_loop and (in_manager_range or has_record_token or is_save_count)):
            continue
        has_fixed_candidate_array = any(
            marker in pseudocode for marker in ("[150]", "[151]", "[300]", "[450]")
        )
        if has_fixed_candidate_array and function_ea not in expanded_stack_functions:
            continue
        for hit in function["hits"]:
            reasons = hit["reasons"]
            if "constant_150" not in reasons and "constant_149" not in reasons:
                continue
            disasm = hit["disasm"].lstrip()
            if not disasm.startswith(("cmp", "mov")):
                continue
            old = 0x96 if "constant_150" in reasons else 0x95
            new = 0x100 if old == 0x96 else 0xFF
            offset = operand_offset(data, hit, config["imagebase"], old)
            if offset in patched_offsets:
                continue
            patch_dword(data, offset, old, new, "expand record loop bound", log)
            patched_offsets.add(offset)

    sections = {section["name"]: section for section in pe["sections"]}
    data_section = sections[".data"]
    shr = sections[".shr"]
    rsrc = sections[".rsrc"]
    old_shr_rva = shr["rva"]
    old_rsrc_rva = rsrc["rva"]
    new_data_virtual_size = data_section["virtual_size"] + config["extra"]
    new_shr_rva = align(
        data_section["rva"] + new_data_virtual_size, pe["section_alignment"]
    )
    section_shift = new_shr_rva - old_shr_rva
    new_rsrc_rva = old_rsrc_rva + section_shift

    # These tiny legacy sections have a handful of absolute pointers in code.
    # The images have relocations stripped, so every embedded VA must move too.
    for old_rva, new_rva, section_name in (
        (old_shr_rva, new_shr_rva, ".shr"),
        (old_rsrc_rva, new_rsrc_rva, ".rsrc"),
    ):
        old_va = config["imagebase"] + old_rva
        new_va = config["imagebase"] + new_rva
        encoded = struct.pack("<I", old_va)
        offsets = [
            offset
            for offset in range(len(data) - 3)
            if data[offset : offset + 4] == encoded
        ]
        for offset in offsets:
            patch_dword(
                data,
                offset,
                old_va,
                new_va,
                f"move absolute {section_name} reference",
                log,
            )

    patch_dword(
        data,
        data_section["header"] + 8,
        data_section["virtual_size"],
        new_data_virtual_size,
        "expand .data virtual size",
        log,
    )
    patch_dword(data, shr["header"] + 12, old_shr_rva, new_shr_rva, "move .shr RVA", log)
    patch_dword(
        data, rsrc["header"] + 12, old_rsrc_rva, new_rsrc_rva, "move .rsrc RVA", log
    )
    old_image_size = struct.unpack_from("<I", data, pe["size_of_image_offset"])[0]
    patch_dword(
        data,
        pe["size_of_image_offset"],
        old_image_size,
        old_image_size + section_shift,
        "expand SizeOfImage",
        log,
    )
    old_resource_dir = struct.unpack_from(
        "<I", data, pe["resource_directory_offset"]
    )[0]
    patch_dword(
        data,
        pe["resource_directory_offset"],
        old_resource_dir,
        old_resource_dir + section_shift,
        "move resource directory RVA",
        log,
    )

    for offset in range(rsrc["raw"], rsrc["raw"] + rsrc["raw_size"] - 3, 4):
        value = struct.unpack_from("<I", data, offset)[0]
        if old_rsrc_rva <= value < old_rsrc_rva + rsrc["virtual_size"]:
            patch_dword(
                data,
                offset,
                value,
                value + section_shift,
                "move resource data RVA",
                log,
            )

    update_pe_checksum(data, log)
    return data, log


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("game", choices=CONFIG)
    parser.add_argument("source", type=Path)
    parser.add_argument("audit", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("log", type=Path)
    args = parser.parse_args()
    data, log = expand(args.game, args.source, args.audit)
    args.output.write_bytes(data)
    args.log.write_text(json.dumps(log, indent=2) + "\n", encoding="utf-8")
    print(f"{args.game}: {len(log)} structural edits, {len(data):,} file bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
