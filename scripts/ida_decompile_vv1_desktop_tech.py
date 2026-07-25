"""Decompile the supported desktop VV1 Tech Scene neighborhood."""

import ida_auto
import ida_funcs
import ida_hexrays
import ida_name
import ida_pro
import idautils


RANGES = (
    (0x00433000, 0x00436000),
)


ida_auto.auto_wait()
if not ida_hexrays.init_hexrays_plugin():
    print("VV1_DESKTOP_HEXRAYS_UNAVAILABLE")
    ida_pro.qexit(1)

print("VV1_DESKTOP_TECH_DECOMPILATION_BEGIN")
for ea in idautils.Functions():
    if not any(start <= ea < end for start, end in RANGES):
        continue
    function = ida_funcs.get_func(ea)
    name = ida_name.get_ea_name(ea)
    print(f"\n===== {ea:08X} {function.end_ea - function.start_ea:08X} {name} =====")
    try:
        print(ida_hexrays.decompile(ea))
    except Exception as error:
        print(f"DECOMPILE_ERROR {error}")
print("VV1_DESKTOP_TECH_DECOMPILATION_END")

ida_pro.qexit(0)
