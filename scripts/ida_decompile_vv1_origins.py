"""Decompile the focused VV1 Origins upgrade and purchase implementation."""

import ida_auto
import ida_funcs
import ida_hexrays
import ida_name
import ida_pro
import idautils


CLASS_FRAGMENTS = (
    "CScrollingStoreScene::",
    "CPurchaseManager::ApplyBonus",
    "CPurchaseManagerImpl::Gift",
    "CPurchaseManagerImpl::SetProductAsPurchased",
    "theVillagerClass::Grant",
    "theGameState::IncrementTechPoints",
    "theGameState::IncrementFood",
    "theTechScene::",
)


ida_auto.auto_wait()
if not ida_hexrays.init_hexrays_plugin():
    print("VV1_ORIGINS_HEXRAYS_UNAVAILABLE")
    ida_pro.qexit(1)

targets = set()
for ea in idautils.Functions():
    name = ida_name.get_ea_name(ea)
    demangled = ida_name.demangle_name(name, ida_name.MNG_LONG_FORM) or name
    if any(fragment in demangled for fragment in CLASS_FRAGMENTS):
        targets.add(ea)

print("VV1_ORIGINS_DECOMPILATION_BEGIN")
for ea in sorted(targets):
    function = ida_funcs.get_func(ea)
    name = ida_name.get_ea_name(ea)
    demangled = ida_name.demangle_name(name, ida_name.MNG_LONG_FORM) or name
    print(f"\n===== {ea:08X} {function.end_ea - function.start_ea:08X} {demangled} =====")
    try:
        print(ida_hexrays.decompile(ea))
    except Exception as error:
        print(f"DECOMPILE_ERROR {error}")
print("VV1_ORIGINS_DECOMPILATION_END")

ida_pro.qexit(0)
