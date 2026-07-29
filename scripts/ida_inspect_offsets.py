"""Inspect exact file offsets in an already analyzed PE through IDALIB.

The script is read-only.  It reports whether each byte belongs to an IDA item,
the containing instruction or data item, nearby decoded heads, function
ownership, raw bytes, names, and xrefs.  It is intended to distinguish real
relocation operands/data pointers from coincidental four-byte patterns.
"""

from __future__ import annotations

import json
import sys

import ida_auto
import ida_bytes
import ida_funcs
import ida_lines
import ida_loader
import ida_nalt
import idautils
import idc


def _head(ea: int) -> dict[str, object]:
    flags = idc.get_full_flags(ea)
    size = max(1, idc.get_item_size(ea))
    function = ida_funcs.get_func(ea)
    return {
        "ea": f"0x{ea:X}",
        "file_offset": (
            f"0x{ida_loader.get_fileregion_offset(ea):X}"
            if ida_loader.get_fileregion_offset(ea) >= 0
            else None
        ),
        "size": size,
        "is_code": bool(idc.is_code(flags)),
        "is_data": bool(idc.is_data(flags)),
        "name": idc.get_name(ea) or None,
        "function": (
            f"0x{function.start_ea:X}" if function is not None else None
        ),
        "function_name": (
            idc.get_func_name(function.start_ea)
            if function is not None
            else None
        ),
        "line": ida_lines.tag_remove(idc.generate_disasm_line(ea, 0) or ""),
        "bytes": (idc.get_bytes(ea, size) or b"").hex().upper(),
    }


def _context(item_head: int, before: int = 4, after: int = 4):
    heads = []
    cursor = item_head
    for _ in range(before):
        cursor = idc.prev_head(cursor)
        if cursor == idc.BADADDR:
            break
        heads.append(cursor)
    heads.reverse()
    heads.append(item_head)
    cursor = item_head
    for _ in range(after):
        cursor = idc.next_head(cursor)
        if cursor == idc.BADADDR:
            break
        heads.append(cursor)
    return [_head(head) for head in heads]


def main() -> None:
    ida_auto.auto_wait()
    if len(sys.argv) < 3:
        raise RuntimeError("expected arguments: <output-json> <file-offset>...")
    output = sys.argv[1]
    imagebase = ida_nalt.get_imagebase()
    rows = []
    for text in sys.argv[2:]:
        file_offset = int(text, 0)
        ea = ida_loader.get_fileregion_ea(file_offset)
        item_head = idc.get_item_head(ea)
        item_end = idc.get_item_end(ea)
        rows.append(
            {
                "requested_file_offset": f"0x{file_offset:X}",
                "ea": f"0x{ea:X}",
                "rva": f"0x{ea - imagebase:X}",
                "segment": idc.get_segm_name(ea),
                "item_head": f"0x{item_head:X}",
                "item_end": f"0x{item_end:X}",
                "offset_in_item": ea - item_head,
                "item": _head(item_head),
                "context": _context(item_head),
                "xrefs_to": [
                    {
                        "from": f"0x{xref.frm:X}",
                        "type": int(xref.type),
                        "iscode": bool(xref.iscode),
                    }
                    for xref in idautils.XrefsTo(ea, 0)
                ],
                "xrefs_from": [
                    {
                        "to": f"0x{xref.to:X}",
                        "type": int(xref.type),
                        "iscode": bool(xref.iscode),
                    }
                    for xref in idautils.XrefsFrom(item_head, 0)
                ],
                "raw_window": (
                    idc.get_bytes(max(0, ea - 16), 36) or b""
                ).hex().upper(),
            }
        )
    with open(output, "w", encoding="utf-8") as handle:
        json.dump(
            {
                "input": idc.get_input_file_path(),
                "imagebase": f"0x{imagebase:X}",
                "rows": rows,
            },
            handle,
            indent=2,
        )
        handle.write("\n")


main()
