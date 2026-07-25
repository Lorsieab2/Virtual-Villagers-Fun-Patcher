"""Dump the Origins upgrade item tables in a reproducible text form."""

import ida_auto
import ida_bytes
import ida_name
import ida_pro
import idaapi


def text_at(ea: int) -> str:
    raw = ida_bytes.get_strlit_contents(ea, -1, idaapi.STRTYPE_C)
    if raw is None:
        return ""
    return raw.decode("utf-8", errors="replace")


def dump_table(name: str, rows: int, columns: int) -> None:
    ea = ida_name.get_name_ea(idaapi.BADADDR, name)
    print(f"TABLE {name} {ea:08X} rows={rows} columns={columns}")
    for row in range(rows):
        values = []
        for column in range(columns):
            value = ida_bytes.get_dword(ea + 4 * (row * columns + column))
            string = text_at(value)
            values.append(f"{value:08X}" + (f"={string!r}" if string else ""))
        print(f"ROW {row}: " + " | ".join(values))


ida_auto.auto_wait()
dump_table("gPeepUpgradeItems", 3, 6)
dump_table("gIapItems", 12, 5)
dump_table("gProductID", 12, 1)
ida_pro.qexit(0)
