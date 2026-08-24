"""Read-only IDA export for the exact VV2 Origins audit."""

from __future__ import annotations

import hashlib
import json

import ida_auto
import ida_bytes
import ida_funcs
import ida_hexrays
import ida_lines
import ida_nalt
import ida_pro
import idautils
import idc


INPUT_SHA256 = "46C1503C209255C9CDEFA941DB2F449C8CF8E2CDD5C7D13CD975326E377ED677"
OUTPUT = r"C:\Users\Owner\Documents\Codex\Misc LDW Game Projects\Virtual-Villagers-Fun-Patcher\handoff-staging\ida-doubler-audit\vv2-native-required.json"

TARGETS = {
    "tech_writer": 0x426290,
    "food_writer": 0x4262B0,
    "full_mastery_evaluator": 0x44D4C0,
    "native_skill_writer": 0x445430,
    "native_mastery_manager": 0x44F4E0,
    "mastery_adjacent_path": 0x44D190,
    "life_age_updater": 0x43B690,
    "pregnancy_writer": 0x44B980,
    "gong_handler": 0x44E8A0,
    "island_event_two_choice": 0x4204B0,
    "island_event_dispatcher": 0x433600,
    "duplicate_collectible_dispatcher": 0x461B10,
    "native_preference_add": 0x420D00,
    "native_preference_remove": 0x420D80,
    "native_preference_lookup": 0x420C80,
}


def clean(value):
    return ida_lines.tag_remove(str(value)) if value is not None else None


def decompile(ea: int):
    function = ida_funcs.get_func(ea)
    if function is None:
        return None
    try:
        item = ida_hexrays.decompile(function.start_ea)
    except Exception as exc:  # pragma: no cover - IDA runtime behavior
        return f"<decompile error: {exc}>"
    return clean(item)


def xrefs_to(ea: int):
    rows = []
    for xref in idautils.XrefsTo(ea, 0):
        caller = ida_funcs.get_func(xref.frm)
        size = ida_bytes.get_item_size(xref.frm)
        rows.append(
            {
                "from": f"0x{xref.frm:X}",
                "return_address": f"0x{xref.frm + size:X}",
                "size": size,
                "line": clean(idc.generate_disasm_line(xref.frm, 0) or ""),
                "caller_start": f"0x{caller.start_ea:X}" if caller else None,
                "caller_name": idc.get_func_name(caller.start_ea) if caller else None,
            }
        )
    return rows


def function_instructions(ea: int):
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
                "line": clean(idc.generate_disasm_line(item, 0) or ""),
                "operand": idc.print_operand(item, 0),
            }
        )
    return rows


def raw_sha256(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def main() -> None:
    ida_auto.auto_wait()
    if not ida_hexrays.init_hexrays_plugin():
        raise RuntimeError("Hex-Rays decompiler is unavailable")
    input_path = idc.get_input_file_path()
    actual_sha256 = raw_sha256(input_path)
    if actual_sha256 != INPUT_SHA256:
        raise RuntimeError(f"input SHA-256 mismatch: {actual_sha256}")
    functions = {}
    for name, ea in TARGETS.items():
        functions[name] = {
            "va": f"0x{ea:X}",
            "name": idc.get_func_name(ea),
            "pseudocode": decompile(ea),
            "xrefs_to": xrefs_to(ea),
            "call_jump_instructions": function_instructions(ea),
        }
    payload = {
        "input": input_path,
        "input_sha256": actual_sha256,
        "imagebase": f"0x{ida_nalt.get_imagebase():X}",
        "targets": functions,
        "writer_xrefs": {
            "tech": xrefs_to(TARGETS["tech_writer"]),
            "food": xrefs_to(TARGETS["food_writer"]),
        },
    }
    with open(OUTPUT, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")
    ida_pro.qexit(0)


main()
