"""IDA batch helper: export functions relevant to 150-record manager expansion."""

from __future__ import annotations

import json
import sys

import ida_auto
import ida_funcs
import ida_hexrays
import ida_idaapi
import ida_lines
import ida_nalt
import ida_segment
import ida_ua
import idautils
import idc


CONFIG = {
    "Virtual Villagers - The Secret City.exe": {
        "id": "vv3",
        "manager": 0x59E110,
        "first": 0x59E124,
        "end150": 0x6C5D2C,
        "data_end": 0x6C7518,
        "stride": 0x1F8C,
        "constructor": 0x45C730,
        "save_tail": 73428,
        "save_max": 77840,
        "forced": [0x427C60, 0x428810, 0x428880, 0x428B60],
    },
    "Virtual Villagers - The Tree of Life.exe": {
        "id": "vv4",
        "manager": 0x50E568,
        "first": 0x50E5AC,
        "end150": 0x6BFCD4,
        "data_end": 0x727344,
        "stride": 0x2E3C,
        "constructor": 0x467CE0,
        "save_tail": 90304,
        "save_max": 94720,
        "forced": [],
    },
    "Virtual Villagers - New Believers.exe": {
        "id": "vv5",
        "manager": 0x554148,
        "first": 0x554190,
        "end150": 0x70F368,
        "data_end": 0x7B1DA4,
        "stride": 0x2F44,
        "constructor": 0x471DF0,
        "save_tail": 93468,
        "save_max": 97920,
        "forced": [],
    },
}


def decompile(ea: int) -> str:
    try:
        text = str(ida_hexrays.decompile(ea))
        return ida_lines.tag_remove(text)
    except Exception as exc:  # IDA batch audit should continue.
        return f"<decompile failed: {exc}>"


def main() -> None:
    ida_auto.auto_wait()
    input_name = idc.get_root_filename()
    config = CONFIG[input_name]
    output = sys.argv[-1]
    findings: dict[int, list[dict[str, object]]] = {}

    for segment_ea in idautils.Segments():
        segment = ida_segment.getseg(segment_ea)
        if not segment or not (segment.perm & ida_segment.SEGPERM_EXEC):
            continue
        for function_ea in idautils.Functions(segment.start_ea, segment.end_ea):
            function = ida_funcs.get_func(function_ea)
            if not function:
                continue
            hits: list[dict[str, object]] = []
            for instruction_ea in idautils.FuncItems(function_ea):
                instruction = ida_ua.insn_t()
                if not ida_ua.decode_insn(instruction, instruction_ea):
                    continue
                for index, operand in enumerate(instruction.ops):
                    if operand.type == ida_ua.o_void:
                        break
                    values = {int(operand.value), int(operand.addr)}
                    reasons = []
                    if 0x96 in values:
                        reasons.append("constant_150")
                    if 0x95 in values:
                        reasons.append("constant_149")
                    if config["stride"] in values:
                        reasons.append("record_stride")
                    if any(
                        config["manager"] <= value <= config["end150"] + 0x10000
                        for value in values
                    ):
                        reasons.append("manager_address")
                    if any(
                        config["end150"] <= value < config["data_end"]
                        for value in values
                    ):
                        reasons.append("relocate_absolute_data_tail")
                    manager_tail = config["end150"] - config["manager"]
                    manager_limit = config["data_end"] - config["manager"]
                    if any(manager_tail <= value < manager_limit for value in values):
                        reasons.append("relocate_manager_tail_offset")
                    if any(
                        config["save_tail"] <= value <= config["save_max"]
                        for value in values
                    ):
                        reasons.append("expand_save_tail_offset")
                    if reasons:
                        hits.append(
                            {
                                "ea": f"0x{instruction_ea:X}",
                                "disasm": ida_lines.tag_remove(
                                    idc.generate_disasm_line(instruction_ea, 0) or ""
                                ),
                                "operand": index,
                                "operand_type": int(operand.type),
                                "operand_offb": int(operand.offb),
                                "operand_size": int(ida_ua.get_dtype_size(operand.dtype)),
                                "instruction_size": int(instruction.size),
                                "reasons": reasons,
                                "values": [f"0x{value:X}" for value in sorted(values)],
                            }
                        )
            if hits:
                findings[function_ea] = hits

    # Ensure known manager routines are present even if their key arithmetic is
    # expressed through register increments rather than an immediate operand.
    findings.setdefault(config["constructor"], [])
    for function_ea in config["forced"]:
        findings.setdefault(function_ea, [])
    functions = []
    for function_ea, hits in sorted(findings.items()):
        function = ida_funcs.get_func(function_ea)
        pseudocode = decompile(function_ea)
        instructions = []
        if function and any(
            marker in pseudocode for marker in ("[150]", "[151]", "[300]", "[450]")
        ):
            for instruction_ea in idautils.FuncItems(function_ea):
                instruction = ida_ua.insn_t()
                if not ida_ua.decode_insn(instruction, instruction_ea):
                    continue
                operands = []
                for index, operand in enumerate(instruction.ops):
                    if operand.type == ida_ua.o_void:
                        break
                    operands.append(
                        {
                            "index": index,
                            "type": int(operand.type),
                            "offb": int(operand.offb),
                            "dtype_size": int(ida_ua.get_dtype_size(operand.dtype)),
                            "value": f"0x{int(operand.value):X}",
                            "addr": f"0x{int(operand.addr):X}",
                            "reg": int(operand.reg),
                            "phrase": int(operand.phrase),
                        }
                    )
                instructions.append(
                    {
                        "ea": f"0x{instruction_ea:X}",
                        "size": int(instruction.size),
                        "bytes": idc.get_bytes(instruction_ea, instruction.size).hex(),
                        "disasm": ida_lines.tag_remove(
                            idc.generate_disasm_line(instruction_ea, 0) or ""
                        ),
                        "operands": operands,
                    }
                )
        functions.append(
            {
                "ea": f"0x{function_ea:X}",
                "end": f"0x{function.end_ea:X}" if function else None,
                "name": idc.get_func_name(function_ea),
                "hits": hits,
                "pseudocode": pseudocode,
                "instructions": instructions,
            }
        )

    code_tail_hits = []
    for segment_ea in idautils.Segments():
        segment = ida_segment.getseg(segment_ea)
        if not segment or not (segment.perm & ida_segment.SEGPERM_EXEC):
            continue
        for instruction_ea in idautils.Heads(segment.start_ea, segment.end_ea):
            if not idc.is_code(idc.get_full_flags(instruction_ea)):
                continue
            instruction = ida_ua.insn_t()
            if not ida_ua.decode_insn(instruction, instruction_ea):
                continue
            for index, operand in enumerate(instruction.ops):
                if operand.type == ida_ua.o_void:
                    break
                values = {int(operand.value), int(operand.addr)}
                matching = [
                    value
                    for value in values
                    if config["end150"] <= value < config["data_end"]
                ]
                if not matching:
                    continue
                code_tail_hits.append(
                    {
                        "ea": f"0x{instruction_ea:X}",
                        "disasm": ida_lines.tag_remove(
                            idc.generate_disasm_line(instruction_ea, 0) or ""
                        ),
                        "operand": index,
                        "operand_type": int(operand.type),
                        "operand_offb": int(operand.offb),
                        "operand_size": int(ida_ua.get_dtype_size(operand.dtype)),
                        "instruction_size": int(instruction.size),
                        "reasons": ["relocate_absolute_data_tail"],
                        "values": [
                            f"0x{value:X}" for value in sorted(values)
                        ],
                    }
                )

    segments = []
    for segment_ea in idautils.Segments():
        segment = ida_segment.getseg(segment_ea)
        segments.append(
            {
                "name": idc.get_segm_name(segment_ea),
                "start": f"0x{segment.start_ea:X}",
                "end": f"0x{segment.end_ea:X}",
                "perm": segment.perm,
            }
        )

    payload = {
        "input": idc.get_input_file_path(),
        "imagebase": f"0x{ida_nalt.get_imagebase():X}",
        "config": {
            key: (
                f"0x{value:X}"
                if isinstance(value, int)
                else [f"0x{item:X}" for item in value]
                if isinstance(value, list)
                else value
            )
            for key, value in config.items()
        },
        "segments": segments,
        "functions": functions,
        "code_tail_hits": code_tail_hits,
    }
    with open(output, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")
