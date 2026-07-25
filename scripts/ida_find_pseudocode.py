"""IDA batch helper: export decompiled functions containing requested text."""

from __future__ import annotations

import json

import ida_auto
import ida_funcs
import ida_hexrays
import ida_pro
import idautils
import idc


def main() -> None:
    if len(idc.ARGV) < 3:
        raise RuntimeError("usage: script.py OUTPUT NEEDLE [NEEDLE ...]")
    destination = idc.ARGV[1]
    needles = [value.lower() for value in idc.ARGV[2:]]
    ida_auto.auto_wait()
    if not ida_hexrays.init_hexrays_plugin():
        raise RuntimeError("Hex-Rays is unavailable")
    matches = []
    failures = 0
    for address in idautils.Functions():
        function = ida_funcs.get_func(address)
        if function is None:
            continue
        try:
            pseudocode = str(ida_hexrays.decompile(function))
        except Exception:
            failures += 1
            continue
        lowered = pseudocode.lower()
        found = [needle for needle in needles if needle in lowered]
        if found:
            matches.append(
                {
                    "address": f"0x{address:X}",
                    "name": idc.get_func_name(address),
                    "needles": found,
                    "pseudocode": pseudocode,
                }
            )
    with open(destination, "w", encoding="utf-8") as handle:
        json.dump({"matches": matches, "decompile_failures": failures}, handle, indent=2)
    ida_pro.qexit(0)


main()
