from __future__ import annotations

import json
import sys

import ida_auto
import ida_hexrays
import ida_lines
import ida_funcs
import ida_pro
import idautils
import idc


TARGETS = {
    "tech_writer": 0x426290,
    "food_writer": 0x4262B0,
    "skill_writer": 0x445430,
    "elder_evaluator": 0x44D4C0,
    "manager_getter": 0x44F4E0,
    "health_related_a": 0x44C600,
    "life_updater": 0x43B690,
    "preference_like_helper_a": 0x420D22,
    "preference_like_helper_b": 0x420D2B,
    "preference_like_helper_c": 0x420D37,
}


def decompile(ea: int) -> str | None:
    function = ida_funcs.get_func(ea)
    if function is None:
        return None
    item = ida_hexrays.decompile(function.start_ea)
    return ida_lines.tag_remove(str(item)) if item else None


def xrefs_to(ea: int):
    rows = []
    for xref in idautils.XrefsTo(ea, 0):
        rows.append({
            "from": f"0x{xref.frm:X}",
            "line": ida_lines.tag_remove(idc.generate_disasm_line(xref.frm, 0) or ""),
            "caller": idc.get_func_name(xref.frm),
        })
    return rows


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: ida_export_vv2_origins_audit.py OUTPUT_JSON")
    ida_auto.auto_wait()
    if not ida_hexrays.init_hexrays_plugin():
        raise RuntimeError("Hex-Rays decompiler unavailable")
    payload = {
        "input": idc.get_input_file_path(),
        "functions": {
            name: {
                "va": f"0x{ea:X}",
                "name": idc.get_func_name(ea),
                "pseudocode": decompile(ea),
                "xrefs_to": xrefs_to(ea),
            }
            for name, ea in TARGETS.items()
        },
    }
    with open(sys.argv[1], "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")
    ida_pro.qexit(0)


main()
