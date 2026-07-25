"""List every VV1 desktop instruction that accesses food or tech points."""

from pathlib import Path

import ida_auto
import ida_bytes
import ida_funcs
import ida_ida
import ida_lines
import ida_pro
import idautils


OUTPUT = Path(
    r"C:\Users\Owner\Documents\Codex\Misc LDW Game Projects"
    r"\Virtual-Villagers-Fun-Patcher\research\vv1-origins-apk"
    r"\desktop-resource-accesses.txt"
)
DISPLACEMENTS = (0xA2EC, 0xA2FC)


def main() -> None:
    ida_auto.auto_wait()
    rows: list[str] = []
    for ea in idautils.Heads(ida_ida.inf_get_min_ea(), ida_ida.inf_get_max_ea()):
        text = ida_lines.generate_disasm_line(ea, 0) or ""
        plain = ida_lines.tag_remove(text)
        if not any(f"{value:X}h" in plain for value in DISPLACEMENTS):
            continue
        function = ida_funcs.get_func(ea)
        function_name = ida_funcs.get_func_name(function.start_ea) if function else "<none>"
        raw = ida_bytes.get_bytes(ea, ida_bytes.get_item_size(ea)) or b""
        rows.append(f"{ea:08X} {function_name:<16} {raw.hex().upper():<30} {plain}")
    OUTPUT.write_text("\n".join(rows) + "\n", encoding="utf-8")
    ida_pro.qexit(0)


main()
