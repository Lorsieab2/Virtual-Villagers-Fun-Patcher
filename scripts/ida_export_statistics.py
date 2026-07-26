"""Export statistics-screen string references and their decompiled functions."""

from __future__ import annotations

import json
import sys

import ida_auto
import ida_funcs
import ida_hexrays
import ida_lines
import ida_pro
import idautils


TERMS = (
    "real hours played",
    "points earned",
    "babies made",
    "food gathered",
    "people cured",
    "mushrooms found",
    "highest population",
    "maximum population",
    "village elders",
    "villagers buried",
    "oldest villager",
    "island events seen",
    "special stews found",
    "twins birthed",
    "triplets birthed",
    "puzzles solved",
)


def main() -> None:
    if len(sys.argv) != 2:
        raise RuntimeError("usage: ida_export_statistics.py OUTPUT")
    destination = sys.argv[1]
    ida_auto.auto_wait()
    if not ida_hexrays.init_hexrays_plugin():
        raise RuntimeError("Hex-Rays is unavailable")

    strings = []
    function_addresses = set()
    for item in idautils.Strings():
        text = str(item)
        if not any(term in text.casefold() for term in TERMS):
            continue
        references = []
        for xref in idautils.XrefsTo(item.ea):
            function = ida_funcs.get_func(xref.frm)
            function_start = function.start_ea if function is not None else None
            if function_start is not None:
                function_addresses.add(function_start)
            references.append(
                {
                    "from": f"0x{xref.frm:X}",
                    "function": (
                        f"0x{function_start:X}" if function_start is not None else None
                    ),
                }
            )
        strings.append(
            {
                "address": f"0x{item.ea:X}",
                "text": text,
                "references": references,
            }
        )

    functions = []
    for address in sorted(function_addresses):
        try:
            pseudocode = ida_lines.tag_remove(str(ida_hexrays.decompile(address)))
        except Exception as exc:
            pseudocode = f"<decompile failed: {exc}>"
        functions.append(
            {
                "address": f"0x{address:X}",
                "name": ida_funcs.get_func_name(address),
                "pseudocode": pseudocode,
            }
        )

    with open(destination, "w", encoding="utf-8") as handle:
        json.dump({"strings": strings, "functions": functions}, handle, indent=2)
    ida_pro.qexit(0)


main()
