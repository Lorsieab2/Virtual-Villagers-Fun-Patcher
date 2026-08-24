import ida_auto
import ida_hexrays
import ida_name
import ida_pro


TARGETS = (0x437230, 0x4410C0, 0x444990, 0x4457D0, 0x43B520, 0x43A1A0)

ida_auto.auto_wait()
if not ida_hexrays.init_hexrays_plugin():
    print("HEX_RAYS_UNAVAILABLE")
    ida_pro.qexit(1)

for ea in TARGETS:
    name = ida_name.get_ea_name(ea)
    print(f"\n===== {ea:08X} {name} =====")
    try:
        print(ida_hexrays.decompile(ea))
    except Exception as exc:
        print(f"DECOMPILE_ERROR {exc}")

ida_pro.qexit(0)
