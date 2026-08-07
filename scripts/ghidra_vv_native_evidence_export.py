"""Ghidra Python template. Run only in a separately authorized Ghidra session."""
import hashlib

def export_query(program, function):
    listing=program.getListing(); memory=program.getMemory(); body=function.getBody(); start=function.getEntryPoint(); end=body.getMaxAddress()
    raw=bytearray(body.getNumAddresses()); memory.getBytes(start,raw)
    instructions=[]; it=listing.getInstructions(body,True)
    while it.hasNext():
        ins=it.next(); b=ins.getBytes()
        instructions.append({"ea":"0x%X"%ins.getAddress().getOffset(),"file_offset":program.getMemory().getAddressSourceInfo(ins.getAddress()).getFileOffset(),"raw_bytes":"".join("%02X"%(x&255) for x in b),"mnemonic":ins.getMnemonicString(),"operands":str(ins)})
    return {"function_name":function.getName(),"start_ea":"0x%X"%start.getOffset(),"end_ea":"0x%X"%(end.getOffset()+1),"start_file_offset":program.getMemory().getAddressSourceInfo(start).getFileOffset(),"end_file_offset":program.getMemory().getAddressSourceInfo(end).getFileOffset()+1,"raw_bytes_sha256":hashlib.sha256(bytes(raw)).hexdigest().upper(),"raw_bytes_hex":"".join("%02X"%(x&255) for x in raw),"instructions":instructions,"callers":[],"callees":[],"xrefs":[]}

def canonical_record(query_id, topic, primitive, binding, observations):
    """Combine analyzer output with reviewed ABI observations; no field is optional."""
    required=("register_contract","stack_cleanup","return_contract","side_effects")
    if set(observations)!=set(required): raise RuntimeError("all ABI/side-effect observations are required")
    result={"query_id":query_id,"topic":topic,"status":"resolved"}; result.update(primitive); result.update(observations); result["source_binding"]=binding; return result

raise RuntimeError("Template only: remove this guard only in a separately authorized Ghidra session after binding reviewed queries and source hashes")
