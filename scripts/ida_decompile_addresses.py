"""IDA batch helper: decompile specified virtual addresses to JSON."""

import json
import sys

import ida_auto
import ida_funcs
import ida_hexrays
import ida_pro


def main() -> None:
    if len(sys.argv) < 3:
        raise SystemExit("usage: ida_decompile_addresses.py OUTPUT ADDRESS...")
    output = sys.argv[1]
    addresses = [int(value, 0) for value in sys.argv[2:]]
    ida_auto.auto_wait()
    if not ida_hexrays.init_hexrays_plugin():
        raise RuntimeError("Hex-Rays decompiler is unavailable")
    results = []
    for address in addresses:
        function = ida_funcs.get_func(address)
        if function is None:
            results.append({"address": hex(address), "error": "no containing function"})
            continue
        try:
            pseudocode = str(ida_hexrays.decompile(function.start_ea))
            results.append(
                {
                    "address": hex(address),
                    "function_start": hex(function.start_ea),
                    "name": ida_funcs.get_func_name(function.start_ea),
                    "pseudocode": pseudocode,
                }
            )
        except Exception as exc:
            results.append({"address": hex(address), "error": str(exc)})
    with open(output, "w", encoding="utf-8") as handle:
        json.dump(results, handle, indent=2)
    ida_pro.qexit(0)


main()
