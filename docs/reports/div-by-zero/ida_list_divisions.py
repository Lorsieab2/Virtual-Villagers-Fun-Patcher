import json
import os

import ida_auto
import ida_funcs
import ida_hexrays
import ida_lines
import ida_nalt
import ida_name
import ida_pro
import ida_ua
import idautils
import idc

ida_auto.auto_wait()
out_path = os.environ.get("DIVS_OUT") or (os.path.splitext(os.path.splitext(idc.get_idb_path())[0])[0] + "_divs.json")
ida_hexrays.init_hexrays_plugin()

HELPER_NAMES = ("_alldiv", "_aulldiv", "_allrem", "_aullrem", "_alldvrm", "_aulldvrm")
sites = []
funcs = {}
for fea in idautils.Functions():
    f = ida_funcs.get_func(fea)
    name = ida_name.get_name(fea)
    lib = bool(f.flags & ida_funcs.FUNC_LIB)
    hits = []
    for ea in idautils.FuncItems(fea):
        m = idc.print_insn_mnem(ea)
        if m in ("div", "idiv"):
            hits.append((ea, m, idc.print_operand(ea, 0)))
        elif m == "call":
            t = idc.get_operand_value(ea, 0)
            tn = ida_name.get_name(t) or ""
            if any(h in tn for h in HELPER_NAMES):
                hits.append((ea, tn, ""))
    if not hits:
        continue
    exprs = []
    text = ""
    if not lib and not any(h in name for h in HELPER_NAMES):
        try:
            cf = ida_hexrays.decompile(fea)
        except Exception as e:  # noqa
            cf = None
            text = "DECOMPILE FAILED %s" % e
        if cf:
            text = "\n".join(ida_lines.tag_remove(l.line) for l in cf.get_pseudocode())

            class V(ida_hexrays.ctree_visitor_t):
                def __init__(self):
                    super().__init__(ida_hexrays.CV_FAST)

                def visit_expr(self, e):
                    if e.op in (ida_hexrays.cot_sdiv, ida_hexrays.cot_udiv, ida_hexrays.cot_smod,
                                ida_hexrays.cot_umod, ida_hexrays.cot_asgsdiv, ida_hexrays.cot_asgudiv,
                                ida_hexrays.cot_asgsmod, ida_hexrays.cot_asgumod):
                        if e.y.op == ida_hexrays.cot_num:
                            pass
                        if not (e.type.is_float() if e.type else False):
                            exprs.append(dict(ea=e.ea, op=e.opname,
                                              y=ida_lines.tag_remove(e.y.print1(None)),
                                              full=ida_lines.tag_remove(e.print1(None)),
                                              const=e.y.op == ida_hexrays.cot_num))
                    return 0
            V().apply_to(cf.body, None)
    funcs[fea] = dict(name=name, lib=lib, hits=hits, exprs=exprs, text=text)

json.dump({hex(k): v for k, v in funcs.items()}, open(out_path, "w"), indent=1)
ida_pro.qexit(0)
