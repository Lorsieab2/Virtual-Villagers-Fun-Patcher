"""Export IDA-resolved direct callers for the resource writers."""

from __future__ import annotations

import json
import sys

import ida_auto
import ida_bytes
import ida_funcs
import ida_hexrays
import ida_lines
import ida_pro
import idautils
import idc


def main() -> None:
    if len(sys.argv) < 3:
        raise SystemExit("usage: ida_export_writer_callers.py OUTPUT WRITER_VA...")
    output = sys.argv[1]
    writers = [int(value, 0) for value in sys.argv[2:]]
    ida_auto.auto_wait()
    if not ida_hexrays.init_hexrays_plugin():
        raise RuntimeError("Hex-Rays decompiler is unavailable")
    rows = []
    seen = set()
    for writer in writers:
        for xref in idautils.XrefsTo(writer, 0):
            caller = ida_funcs.get_func(xref.frm)
            instruction_size = ida_bytes.get_item_size(xref.frm)
            key = (writer, xref.frm)
            if key in seen:
                continue
            seen.add(key)
            pseudocode = None
            if caller is not None:
                pseudocode = ida_lines.tag_remove(str(ida_hexrays.decompile(caller.start_ea)))
            rows.append(
                {
                    "writer": f"0x{writer:X}",
                    "xref_from": f"0x{xref.frm:X}",
                    "xref_line": ida_lines.tag_remove(idc.generate_disasm_line(xref.frm, 0) or ""),
                    "xref_size": instruction_size,
                    "return_address": f"0x{xref.frm + instruction_size:X}",
                    "caller_start": f"0x{caller.start_ea:X}" if caller else None,
                    "caller_name": idc.get_func_name(caller.start_ea) if caller else None,
                    "pseudocode": pseudocode,
                }
            )
    rows.sort(key=lambda row: (int(row["writer"], 16), int(row["xref_from"], 16)))
    with open(output, "w", encoding="utf-8") as handle:
        json.dump(rows, handle, indent=2)
        handle.write("\n")
    ida_pro.qexit(0)


main()
