import ida_auto
import ida_hexrays
import ida_funcs
import ida_name
import ida_pro
import idautils

ida_auto.auto_wait()
if not ida_hexrays.init_hexrays_plugin():
    print("HEX_RAYS_UNAVAILABLE")
    ida_pro.qexit(1)

for ea in idautils.Functions():
    func = ida_funcs.get_func(ea)
    if func is None or func.end_ea - func.start_ea > 0x5000:
        continue
    try:
        text = str(ida_hexrays.decompile(ea))
    except Exception:
        continue
    if any(token in text for token in ("+ 920", "+ 924", "+ 928", "+ 932", "+ 936", "+ 940", "+ 944", "+ 948")):
        print(f"===== {ea:08X} {ida_name.get_ea_name(ea)} =====")
        print(text)

ida_pro.qexit(0)
