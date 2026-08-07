"""IDA Python template. Run only in a separately authorized IDA session."""
import hashlib, json

def export_query(ea, ida_bytes, ida_funcs, idautils, idc):
    fn=ida_funcs.get_func(ea)
    if not fn: raise RuntimeError("query EA is not inside a function")
    raw=ida_bytes.get_bytes(fn.start_ea,fn.end_ea-fn.start_ea)
    instructions=[]
    for x in idautils.Heads(fn.start_ea,fn.end_ea):
        b=ida_bytes.get_bytes(x,ida_bytes.get_item_size(x))
        instructions.append({"ea":f"0x{x:X}","file_offset":ida_bytes.get_fileregion_offset(x),"raw_bytes":b.hex().upper(),"mnemonic":idc.print_insn_mnem(x),"operands":" ".join(filter(None,(idc.print_operand(x,i) for i in range(8))))})
    return {"function_name":idc.get_func_name(fn.start_ea),"start_ea":f"0x{fn.start_ea:X}","end_ea":f"0x{fn.end_ea:X}","start_file_offset":ida_bytes.get_fileregion_offset(fn.start_ea),"end_file_offset":ida_bytes.get_fileregion_offset(fn.end_ea-1)+1,"raw_bytes_sha256":hashlib.sha256(raw).hexdigest().upper(),"raw_bytes_hex":raw.hex().upper(),"instructions":instructions,"callers":[f"0x{x.frm:X}" for x in idautils.XrefsTo(fn.start_ea)],"callees":[],"xrefs":[]}

def canonical_record(query_id, topic, primitive, binding, observations):
    """Combine analyzer output with reviewed ABI observations; no field is optional."""
    required=("register_contract","stack_cleanup","return_contract","side_effects")
    if set(observations)!=set(required): raise RuntimeError("all ABI/side-effect observations are required")
    return dict({"query_id":query_id,"topic":topic,"status":"resolved"},**primitive,**observations,source_binding=binding)

def main():
    raise RuntimeError("Template only: bind reviewed query EAs and source hashes in an explicitly authorized IDA session")
if __name__=="__main__": main()
