"""IDA 9 Python template. Run only after authorization inside IDA.

Populate RESOLVED_EAS from reviewed IDA analysis. The script refuses partial
coverage and extracts bytes/instructions/xrefs from the loaded database; it
does not accept pasted instruction text or byte strings.
"""
import hashlib, json
from pathlib import Path
import ida_bytes, ida_funcs, ida_gdl, ida_idaapi, ida_kernwin, ida_lines, ida_nalt, idautils

QUERY_MANIFEST = Path(__file__).resolve().parents[1] / "data/native_evidence_queries.json"
RESOLVED_EAS = {}  # query_id -> reviewed function EA; incomplete maps fail.

def export(game, inventory_sha256, output):
    queries = json.loads(QUERY_MANIFEST.read_text(encoding="utf-8"))["queries"]
    if set(RESOLVED_EAS) != {q["id"] for q in queries}: raise RuntimeError("all query EAs must be resolved")
    rows=[]
    for query in queries:
        ea=RESOLVED_EAS[query["id"]]; fn=ida_funcs.get_func(ea)
        if fn is None or fn.start_ea != ea: raise RuntimeError(f"{query['id']}: exact function start required")
        raw=ida_bytes.get_bytes(fn.start_ea, fn.end_ea-fn.start_ea)
        rows.append({"query_id":query["id"],"status":"resolved","function_start_ea":hex(fn.start_ea),"function_end_ea":hex(fn.end_ea),"file_offset":hex(ida_nalt.get_fileregion_offset(fn.start_ea)),"raw_bytes":raw.hex().upper(),"instructions":[{"ea":hex(i),"text":ida_lines.generate_disasm_line(i,0)} for i in idautils.FuncItems(fn.start_ea)],"callers":[hex(x.frm) for x in idautils.XrefsTo(fn.start_ea)],"xrefs":[hex(x.frm) for x in idautils.XrefsTo(fn.start_ea)],"registers":{},"stack_cleanup":"REVIEW_REQUIRED_FROM_EXTRACTED_INSTRUCTIONS","call_convention":"REVIEW_REQUIRED_FROM_TYPE_INFO"})
    data={"schema":"vvfp.authenticated-native-export.v1","generated_by":"ida_python","synthetic":False,"manual":False,"game":game,"inventory_sha256":inventory_sha256,"functions":rows}
    canonical=lambda v:(json.dumps(v,sort_keys=True,separators=(",",":"),ensure_ascii=False)+"\n").encode()
    data["artifact_sha256"]=hashlib.sha256(canonical(data)).hexdigest().upper(); output.write_bytes(canonical(data))
