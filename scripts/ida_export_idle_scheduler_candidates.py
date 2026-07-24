"""Export likely adult idle-scheduler functions from an IDA database."""

from __future__ import annotations

import json
import sys

import ida_auto
import ida_funcs
import ida_hexrays
import idautils
import idc


def previous_heads(ea: int, count: int = 14) -> list[int]:
    result: list[int] = []
    cursor = ea
    for _ in range(count):
        cursor = idc.prev_head(cursor)
        if cursor == idc.BADADDR:
            break
        result.append(cursor)
    return result


def is_candidate(ea: int) -> bool:
    if idc.print_insn_mnem(ea).lower() != "cmp":
        return False
    if idc.get_operand_type(ea, 1) != idc.o_imm:
        return False
    if idc.get_operand_value(ea, 1) != 0x41:
        return False
    prior = previous_heads(ea)
    has_call = any(idc.print_insn_mnem(item).lower() == "call" for item in prior)
    has_rng_bound = any(
        idc.print_insn_mnem(item).lower() == "push"
        and idc.get_operand_type(item, 0) == idc.o_imm
        and idc.get_operand_value(item, 0) == 100
        for item in prior
    )
    return has_call and has_rng_bound


def main() -> int:
    if len(idc.ARGV) != 2:
        raise RuntimeError("Expected one output JSON path")
    output = idc.ARGV[1]
    ida_auto.auto_wait()
    starts: set[int] = set()
    matches: list[int] = []
    for function_ea in idautils.Functions():
        function = ida_funcs.get_func(function_ea)
        if function is None:
            continue
        for ea in idautils.Heads(function.start_ea, function.end_ea):
            if is_candidate(ea):
                starts.add(function.start_ea)
                matches.append(ea)
    exported = []
    for start in sorted(starts):
        function = ida_funcs.get_func(start)
        try:
            pseudocode = str(ida_hexrays.decompile(start))
        except Exception as error:
            pseudocode = f"<decompile failed: {error}>"
        exported.append(
            {
                "function_start": f"0x{start:X}",
                "function_end": f"0x{function.end_ea:X}" if function else None,
                "name": idc.get_func_name(start),
                "matches": [f"0x{ea:X}" for ea in matches if function and function.start_ea <= ea < function.end_ea],
                "pseudocode": pseudocode,
            }
        )
    with open(output, "w", encoding="utf-8") as handle:
        json.dump(exported, handle, indent=2)
        handle.write("\n")
    idc.qexit(0)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
