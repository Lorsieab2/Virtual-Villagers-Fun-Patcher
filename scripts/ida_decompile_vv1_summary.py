"""Decompile the supported VV1 main-screen villager-summary neighborhood."""

from pathlib import Path

import ida_auto
import ida_funcs
import ida_hexrays
import ida_name
import ida_pro
import idautils


RANGES = (
    (0x0041A800, 0x0041B100),
    (0x00421000, 0x00423600),
    (0x00435000, 0x00435D00),
    (0x00437200, 0x00438000),
    (0x00439000, 0x0043A200),
    (0x0043B900, 0x0043BC00),
    (0x0043CB00, 0x0043CF00),
    (0x00449000, 0x00449A00),
    (0x0044A400, 0x0044A800),
)
OUTPUT = Path(
    r"C:\Users\Owner\Documents\Codex\Misc LDW Game Projects"
    r"\Virtual-Villagers-Fun-Patcher\research\vv1-summary-pseudocode.txt"
)


ida_auto.auto_wait()
if not ida_hexrays.init_hexrays_plugin():
    OUTPUT.write_text("VV1_SUMMARY_HEXRAYS_UNAVAILABLE\n", encoding="utf-8")
    ida_pro.qexit(1)

rows = ["VV1_SUMMARY_DECOMPILATION_BEGIN"]
for ea in idautils.Functions():
    if not any(start <= ea < end for start, end in RANGES):
        continue
    function = ida_funcs.get_func(ea)
    name = ida_name.get_ea_name(ea)
    rows.append(f"\n===== {ea:08X} {function.end_ea - function.start_ea:08X} {name} =====")
    try:
        rows.append(str(ida_hexrays.decompile(ea)))
    except Exception as error:
        rows.append(f"DECOMPILE_ERROR {error}")
rows.append("VV1_SUMMARY_DECOMPILATION_END")
OUTPUT.write_text("\n".join(rows) + "\n", encoding="utf-8")

ida_pro.qexit(0)
