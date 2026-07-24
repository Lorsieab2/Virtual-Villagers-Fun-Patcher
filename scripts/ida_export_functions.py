"""Export requested functions from an existing IDA database."""

from __future__ import annotations

import json

import ida_auto
import ida_funcs
import ida_hexrays
import idc


def main() -> int:
    if len(idc.ARGV) < 3:
        raise RuntimeError("Expected output JSON path and one or more addresses")
    output = idc.ARGV[1]
    addresses = [int(value, 0) for value in idc.ARGV[2:]]
    ida_auto.auto_wait()
    exported = []
    for address in addresses:
        function = ida_funcs.get_func(address)
        if function is None:
            exported.append({"requested": f"0x{address:X}", "error": "not a function"})
            continue
        try:
            pseudocode = str(ida_hexrays.decompile(function.start_ea))
        except Exception as error:
            pseudocode = f"<decompile failed: {error}>"
        exported.append(
            {
                "requested": f"0x{address:X}",
                "function_start": f"0x{function.start_ea:X}",
                "function_end": f"0x{function.end_ea:X}",
                "name": idc.get_func_name(function.start_ea),
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
