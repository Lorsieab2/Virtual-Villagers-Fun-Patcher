"""Export read-only VV1 writer and producer provenance from an IDA database."""

from __future__ import annotations

import json
import sys

import ida_auto
import ida_bytes
import ida_funcs
import ida_hexrays
import ida_lines
import ida_nalt
import ida_pro
import idautils
import idc


TARGETS = {
    "tech_writer": 0x41D120,
    "food_writer": 0x41D140,
    "event_dispatch_candidate": 0x419380,
    "event_result_candidate": 0x427CA0,
    "reward_dispatch_candidate": 0x42B740,
    "resource_event_candidate": 0x43A230,
    "string_lookup_candidate": 0x433970,
    "event_dispatch_parent": 0x41A3D0,
    "event_result_parent": 0x428470,
    "reward_dispatch_parent": 0x42D050,
    "resource_event_parent_a": 0x446C70,
    "resource_event_parent_b": 0x448600,
    "reward_message_dispatch": 0x43A130,
}

STRING_IDS = [
    339, 340, 344, 345, 346, 350, 351, 355, 356, 360, 361, 362, 366, 367,
    369, 370, 374, 375, 377, 378, 382, 383, 387, 388, 389, 393, 394, 398,
    399, 403, 404, 408, 409, 413, 414, 482, 483, 484, 485, 486, 487, 489,
    490, 491, 492, 493, 494, 495, 496, 497, 498, 499,
]

SPECIAL_STRINGS = {
    "golden_child_food": 0x47E2D0,
    "golden_child_crops": 0x47E37C,
    "golden_child_berries": 0x47E430,
}


def resource_string(string_id: int) -> dict[str, object]:
    table = 0x487208
    for index in range(0x275):
        entry = table + index * 20
        if ida_bytes.get_dword(entry) != string_id:
            continue
        strings = []
        for slot in range(1, 5):
            pointer = ida_bytes.get_dword(entry + slot * 4)
            value = ida_bytes.get_strlit_contents(pointer, -1, ida_nalt.STRTYPE_C)
            strings.append(value.decode("latin-1", "replace") if value else None)
        return {"id": string_id, "va": f"0x{entry:X}", "strings": strings}
    return {"id": string_id, "va": None, "strings": []}


def decompile(ea: int) -> str | None:
    function = ida_funcs.get_func(ea)
    if function is None:
        return None
    item = ida_hexrays.decompile(function.start_ea)
    return ida_lines.tag_remove(str(item)) if item else None


def xrefs_to(ea: int) -> list[dict[str, object]]:
    rows = []
    for xref in idautils.XrefsTo(ea, 0):
        caller = ida_funcs.get_func(xref.frm)
        size = ida_bytes.get_item_size(xref.frm)
        rows.append(
            {
                "from": f"0x{xref.frm:X}",
                "return_address": f"0x{xref.frm + size:X}",
                "size": size,
                "line": ida_lines.tag_remove(idc.generate_disasm_line(xref.frm, 0) or ""),
                "caller_start": f"0x{caller.start_ea:X}" if caller else None,
                "caller_name": idc.get_func_name(caller.start_ea) if caller else None,
            }
        )
    return rows


def function_instructions(ea: int) -> list[dict[str, object]]:
    function = ida_funcs.get_func(ea)
    if function is None:
        return []
    rows = []
    for item in idautils.FuncItems(function.start_ea):
        mnemonic = idc.print_insn_mnem(item)
        if mnemonic not in {"call", "jmp"}:
            continue
        rows.append(
            {
                "va": f"0x{item:X}",
                "mnemonic": mnemonic,
                "line": ida_lines.tag_remove(idc.generate_disasm_line(item, 0) or ""),
                "operand": idc.print_operand(item, 0),
            }
        )
    return rows


def instructions_between(start: int, end: int) -> list[dict[str, object]]:
    rows = []
    ea = start
    while ea < end:
        size = ida_bytes.get_item_size(ea)
        if size <= 0:
            size = 1
        rows.append({"va": f"0x{ea:X}", "line": ida_lines.tag_remove(idc.generate_disasm_line(ea, 0) or "")})
        ea += size
    return rows


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: ida_export_vv1_audit.py OUTPUT_JSON")
    output = sys.argv[1]
    ida_auto.auto_wait()
    if not ida_hexrays.init_hexrays_plugin():
        raise RuntimeError("Hex-Rays decompiler is unavailable")
    functions = {}
    for name, ea in TARGETS.items():
        functions[name] = {
            "va": f"0x{ea:X}",
            "name": idc.get_func_name(ea),
            "pseudocode": decompile(ea),
            "xrefs_to": xrefs_to(ea),
            "call_jump_instructions": function_instructions(ea),
        }
    writer_xrefs = {
        name: xrefs_to(ea)
        for name, ea in (
            ("tech_writer", TARGETS["tech_writer"]),
            ("food_writer", TARGETS["food_writer"]),
        )
    }
    special_xrefs = {
        name: xrefs_to(ea) for name, ea in SPECIAL_STRINGS.items()
    }
    payload = {
        "input": idc.get_input_file_path(),
        "functions": functions,
        "writer_xrefs": writer_xrefs,
        "special_string_xrefs": special_xrefs,
        "resource_strings": [resource_string(string_id) for string_id in STRING_IDS],
        "ranges": {
            "sub_419380_tail": instructions_between(0x41A300, 0x41A390),
            "sub_427CA0_writers": instructions_between(0x428160, 0x4281E5),
            "sub_42B740_writers": instructions_between(0x42B840, 0x42C130),
            "sub_43A230_writers": instructions_between(0x43AD60, 0x43B370),
        },
    }
    with open(output, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")
    ida_pro.qexit(0)


main()
