"""IDA batch export for exact-build expanded-population certification.

This exporter is intentionally read-only with respect to the input executable.
It inventories decoded operands that touch the villager pool, the data tail
that moves when the pool grows, and the stock ``.shr``/``.rsrc`` sections.  It
also records every decoded 149/150/151/255/256 immediate so the committed
manifest can be reconciled against constants that were deliberately left
native.
"""

from __future__ import annotations

import json
import sys

import ida_auto
import ida_funcs
import ida_lines
import ida_loader
import ida_nalt
import ida_segment
import ida_ua
import idautils
import idc


CONFIG = {
    "vv3": {
        "manager": 0x59E110,
        "first": 0x59E124,
        "end150": 0x6C5D2C,
        "data_end": 0x6C7518,
        "stride": 0x1F8C,
        "stock_shr_start": 0x6C8000,
        "stock_shr_end": 0x6C9000,
        "stock_rsrc_start": 0x6C9000,
        "stock_rsrc_end": 0x6DF000,
    },
    "vv4": {
        "manager": 0x50E568,
        "first": 0x50E5AC,
        "end150": 0x6BFCD4,
        "data_end": 0x727344,
        "stride": 0x2E3C,
        "stock_shr_start": 0x728000,
        "stock_shr_end": 0x729000,
        "stock_rsrc_start": 0x729000,
        "stock_rsrc_end": 0x73F000,
    },
    "vv5": {
        "manager": 0x554148,
        "first": 0x554190,
        "end150": 0x70F368,
        "data_end": 0x7B1DA4,
        "stride": 0x2F44,
        "stock_shr_start": 0x7B2000,
        "stock_shr_end": 0x7B3000,
        "stock_rsrc_start": 0x7B3000,
        "stock_rsrc_end": 0x7C9000,
    },
}


def _segment(name: str):
    for segment_ea in idautils.Segments():
        if idc.get_segm_name(segment_ea) == name:
            return ida_segment.getseg(segment_ea)
    return None


def _range_reason(value: int, config: dict[str, int], ranges: dict[str, tuple[int, int]]):
    reasons: list[str] = []
    if config["first"] <= value < config["end150"]:
        reasons.append("stock_record_pool")
    if config["end150"] <= value < config["data_end"]:
        reasons.append("moving_data_tail")
    for name in (".shr", ".rsrc"):
        low, high = ranges.get(name, (0, 0))
        if low <= value < high:
            reasons.append(f"section_{name[1:]}")
    dynamic_shr = ranges.get(".shr", (0, 0))
    if (
        dynamic_shr[0] != config["stock_shr_start"]
        and config["stock_shr_start"] <= value < config["stock_shr_end"]
    ):
        reasons.append("stale_stock_shr")
    dynamic_rsrc = ranges.get(".rsrc", (0, 0))
    if (
        dynamic_rsrc[0] != config["stock_rsrc_start"]
        and config["stock_rsrc_start"] <= value < config["stock_rsrc_end"]
    ):
        reasons.append("stale_stock_rsrc")
    return reasons


def _instruction_context(ea: int, before: int = 3, after: int = 3):
    heads = []
    cursor = ea
    for _ in range(before):
        cursor = idc.prev_head(cursor)
        if cursor == idc.BADADDR:
            break
        heads.append(cursor)
    heads.reverse()
    heads.append(ea)
    cursor = ea
    for _ in range(after):
        cursor = idc.next_head(cursor)
        if cursor == idc.BADADDR:
            break
        heads.append(cursor)
    return [
        {
            "ea": f"0x{head:X}",
            "disasm": ida_lines.tag_remove(
                idc.generate_disasm_line(head, 0) or ""
            ),
        }
        for head in heads
    ]


def main() -> None:
    ida_auto.auto_wait()
    if len(sys.argv) < 3:
        raise RuntimeError("expected arguments: <game-id> <output-json>")
    game_id = sys.argv[-2]
    output = sys.argv[-1]
    config = CONFIG[game_id]
    imagebase = ida_nalt.get_imagebase()

    ranges: dict[str, tuple[int, int]] = {}
    segments = []
    for segment_ea in idautils.Segments():
        segment = ida_segment.getseg(segment_ea)
        name = idc.get_segm_name(segment_ea)
        ranges[name] = (segment.start_ea, segment.end_ea)
        segments.append(
            {
                "name": name,
                "start": f"0x{segment.start_ea:X}",
                "end": f"0x{segment.end_ea:X}",
                "perm": int(segment.perm),
            }
        )

    references = []
    constants = []
    branch_references = []
    decoded_heads = 0
    executable_bytes = 0
    for segment_ea in idautils.Segments():
        segment = ida_segment.getseg(segment_ea)
        if not segment or not (segment.perm & ida_segment.SEGPERM_EXEC):
            continue
        executable_bytes += segment.end_ea - segment.start_ea
        for instruction_ea in idautils.Heads(segment.start_ea, segment.end_ea):
            if not idc.is_code(idc.get_full_flags(instruction_ea)):
                continue
            instruction = ida_ua.insn_t()
            if not ida_ua.decode_insn(instruction, instruction_ea):
                continue
            decoded_heads += 1
            function = ida_funcs.get_func(instruction_ea)
            function_ea = function.start_ea if function else None
            disasm = ida_lines.tag_remove(
                idc.generate_disasm_line(instruction_ea, 0) or ""
            )
            raw = idc.get_bytes(instruction_ea, instruction.size) or b""
            instruction_file_offset = ida_loader.get_fileregion_offset(
                instruction_ea
            )
            for index, operand in enumerate(instruction.ops):
                if operand.type == ida_ua.o_void:
                    break
                values = {int(operand.value), int(operand.addr)}
                # IDA reports some 32-bit absolute memory operands as an RVA
                # even though the rendered line shows the rebased VA.  Keep
                # both forms so references such as
                # ``cmp ds:dword_728234, 0`` are not silently omitted.
                if (
                    operand.type == ida_ua.o_mem
                    and 0 < int(operand.addr) < imagebase
                ):
                    values.add(imagebase + int(operand.addr))
                values = sorted(values)
                common = {
                    "ea": f"0x{instruction_ea:X}",
                    "source_segment": idc.get_segm_name(instruction_ea),
                    "rva": f"0x{instruction_ea - imagebase:X}",
                    "file_offset": (
                        f"0x{instruction_file_offset:X}"
                        if instruction_file_offset >= 0
                        else None
                    ),
                    "operand_file_offset": (
                        f"0x{instruction_file_offset + operand.offb:X}"
                        if instruction_file_offset >= 0 and operand.offb > 0
                        else None
                    ),
                    "function": (
                        f"0x{function_ea:X}" if function_ea is not None else None
                    ),
                    "function_name": (
                        idc.get_func_name(function_ea)
                        if function_ea is not None
                        else None
                    ),
                    "disasm": disasm,
                    "bytes": raw.hex().upper(),
                    "instruction_size": int(instruction.size),
                    "operand": index,
                    "operand_type": int(operand.type),
                    "operand_offb": int(operand.offb),
                    "operand_size": int(ida_ua.get_dtype_size(operand.dtype)),
                    "values": [f"0x{value:X}" for value in values],
                }
                hits = []
                for value in values:
                    hits.extend(_range_reason(value, config, ranges))
                if hits:
                    references.append(dict(common, reasons=sorted(set(hits))))
                if any(value in {149, 150, 151, 255, 256} for value in values):
                    constants.append(
                        dict(
                            common,
                            context=_instruction_context(instruction_ea),
                            constants=[
                                value
                                for value in values
                                if value in {149, 150, 151, 255, 256}
                            ],
                        )
                    )
                if operand.type in {ida_ua.o_near, ida_ua.o_far}:
                    target = int(operand.addr)
                    target_reasons = _range_reason(target, config, ranges)
                    branch_references.append(
                        dict(
                            common,
                            target=f"0x{target:X}",
                            target_segment=idc.get_segm_name(target),
                            reasons=sorted(set(target_reasons)),
                        )
                    )

    payload = {
        "input": idc.get_input_file_path(),
        "root_filename": idc.get_root_filename(),
        "game_id": game_id,
        "imagebase": f"0x{imagebase:X}",
        "config": {
            key: f"0x{value:X}" for key, value in config.items()
        },
        "segments": segments,
        "decoded_instruction_heads": decoded_heads,
        "executable_segment_bytes": executable_bytes,
        "references": references,
        "branch_references": branch_references,
        "constants": constants,
    }
    with open(output, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")


main()
