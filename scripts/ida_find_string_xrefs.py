"""IDA batch helper: report code references to strings containing search terms."""

import json
import sys

import ida_auto
import ida_funcs
import ida_pro
import idautils


def main() -> None:
    if len(sys.argv) < 3:
        raise SystemExit("usage: ida_find_string_xrefs.py OUTPUT TERM...")
    output = sys.argv[1]
    terms = [term.casefold() for term in sys.argv[2:]]
    ida_auto.auto_wait()
    matches = []
    for item in idautils.Strings():
        text = str(item)
        if not any(term in text.casefold() for term in terms):
            continue
        xrefs = []
        for xref in idautils.XrefsTo(item.ea):
            function = ida_funcs.get_func(xref.frm)
            xrefs.append(
                {
                    "from": hex(xref.frm),
                    "function": (
                        hex(function.start_ea) if function is not None else None
                    ),
                    "name": (
                        ida_funcs.get_func_name(function.start_ea)
                        if function is not None
                        else None
                    ),
                }
            )
        matches.append({"address": hex(item.ea), "text": text, "xrefs": xrefs})
    with open(output, "w", encoding="utf-8") as handle:
        json.dump(matches, handle, indent=2)
    ida_pro.qexit(0)


main()
