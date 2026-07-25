"""Print a focused inventory from the symbol-rich VV1 Origins ARM library."""

import ida_auto
import ida_funcs
import ida_kernwin
import ida_name
import ida_nalt
import ida_pro
import idautils


KEYWORDS = (
    "upgrade",
    "doubler",
    "tech",
    "food",
    "master",
    "youth",
    "running",
    "purchase",
    "bonus",
)


def relevant(text: str) -> bool:
    lowered = text.lower()
    return any(keyword in lowered for keyword in KEYWORDS)


ida_auto.auto_wait()
print("VV1_ORIGINS_INPUT", ida_nalt.get_input_file_path())

print("VV1_ORIGINS_FUNCTIONS_BEGIN")
for ea in idautils.Functions():
    function = ida_funcs.get_func(ea)
    if function is None:
        continue
    name = ida_name.get_ea_name(ea)
    demangled = ida_name.demangle_name(name, ida_name.MNG_LONG_FORM) or name
    if relevant(demangled):
        print(f"{ea:08X}\t{function.end_ea - function.start_ea:08X}\t{demangled}")
print("VV1_ORIGINS_FUNCTIONS_END")

print("VV1_ORIGINS_NAMES_BEGIN")
for ea, name in idautils.Names():
    demangled = ida_name.demangle_name(name, ida_name.MNG_LONG_FORM) or name
    if relevant(demangled):
        print(f"{ea:08X}\t{demangled}")
print("VV1_ORIGINS_NAMES_END")

print("VV1_ORIGINS_STRINGS_BEGIN")
for item in idautils.Strings():
    text = str(item)
    if relevant(text):
        print(f"{item.ea:08X}\t{text}")
        for xref in idautils.XrefsTo(item.ea):
            function = ida_funcs.get_func(xref.frm)
            if function is None:
                continue
            name = ida_name.get_ea_name(function.start_ea)
            demangled = ida_name.demangle_name(name, ida_name.MNG_LONG_FORM) or name
            print(f"  XREF {xref.frm:08X}\t{function.start_ea:08X}\t{demangled}")
print("VV1_ORIGINS_STRINGS_END")

ida_pro.qexit(0)
