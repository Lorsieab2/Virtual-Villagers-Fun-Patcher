# Ghidra Jython template; execute only after authorization in a loaded program.
#@category VVFP
import hashlib, json
from java.io import File

RESOLVED_EAS = {}  # query_id -> reviewed address string; incomplete maps fail.

def canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")

def export(query_manifest, game, inventory_sha256, output_path):
    queries=json.load(open(query_manifest,"r"))["queries"]
    if set(RESOLVED_EAS) != set(q["id"] for q in queries): raise RuntimeError("all query EAs must be resolved")
    rows=[]
    fm=currentProgram.getFunctionManager(); listing=currentProgram.getListing(); refs=currentProgram.getReferenceManager()
    for q in queries:
        address=toAddr(RESOLVED_EAS[q["id"]]); fn=fm.getFunctionAt(address)
        if fn is None: raise RuntimeError(q["id"]+": exact function start required")
        body=fn.getBody(); start=fn.getEntryPoint(); end=body.getMaxAddress().add(1); length=int(end.subtract(start)); raw=bytearray(length); currentProgram.getMemory().getBytes(start,raw)
        instructions=[]; it=listing.getInstructions(body,True)
        while it.hasNext():
            ins=it.next(); instructions.append({"ea":str(ins.getAddress()),"text":str(ins)})
        xrefs=[]; rit=refs.getReferencesTo(start)
        while rit.hasNext(): xrefs.append(str(rit.next().getFromAddress()))
        rows.append({"query_id":q["id"],"status":"resolved","function_start_ea":str(start),"function_end_ea":str(end),"file_offset":hex(currentProgram.getMemory().getAddressSourceInfo(start).getFileOffset()),"raw_bytes":"".join("%02X"%(b&255) for b in raw),"instructions":instructions,"callers":xrefs,"xrefs":xrefs,"registers":{},"stack_cleanup":"REVIEW_REQUIRED_FROM_EXTRACTED_INSTRUCTIONS","call_convention":str(fn.getCallingConventionName())})
    data={"schema":"vvfp.authenticated-native-export.v1","generated_by":"ghidra","synthetic":False,"manual":False,"game":game,"inventory_sha256":inventory_sha256,"functions":rows}; data["artifact_sha256"]=hashlib.sha256(canonical(data)).hexdigest().upper(); open(output_path,"wb").write(canonical(data))
