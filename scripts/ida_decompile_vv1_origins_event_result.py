"""Decompile the VV1 Origins native event result composer."""

import ida_auto
import ida_funcs
import ida_hexrays
import ida_idaapi
import ida_name
import ida_pro
import idautils


ida_auto.auto_wait()
if not ida_hexrays.init_hexrays_plugin():
    print("HEXRAYS_UNAVAILABLE")
    ida_pro.qexit(1)

for ea in idautils.Functions():
    name = ida_name.get_ea_name(ea)
    demangled = ida_name.demangle_name(name, ida_name.MNG_LONG_FORM) or name
    if "theNCEventDialog::ComposeResult" in demangled:
        print(f"{ea:08X}")
        print(demangled)
        print(ida_hexrays.decompile(ida_funcs.get_func(ea)))
        ida_pro.qexit(0)

print("COMPOSE_RESULT_NOT_FOUND")
ida_pro.qexit(2)
