"""Validate the disabled VV3 Expanded-256 full-capacity save contract."""
from __future__ import annotations
import argparse, copy, hashlib, json, os, stat, sys
from pathlib import Path
from typing import Any, Mapping

ROOT=Path(__file__).resolve().parents[1]
CONTRACT=ROOT/"data"/"vv3_expanded_256_full_capacity_save_contract.json"
SOURCE="8BC5DB382D02BC5C21AD5F607580D60FF44A6519CC7EB133F03113BAACAE6503"
PROTOTYPE="6EE3361A7AC35F441763647C1E2FC9EC49569DE5EF372BDB41D243D03002D601"
C342="28c5fa8ef87212fe79ce3d3e5daee51b0e3ad488"
FUNCTIONS=(("serializer","0x45EF80"),("deserializer","0x45C860"),("save_count","0x428810"),("writer_helper","0x45C8D0"))
FAULTS=("counts_0_149_150_254_255","count_256_no_terminator_tail_untouched","reader_exact_256_no_tail_read","reader_257th_record_rejected","padding_256_259_unreachable_non_saveable","premature_missing_or_malformed_terminator","tail_sentinel_preservation","temporary_write_failure","flush_close_failure","verification_failure","atomic_replace_failure","failed_load_nonmutation")
DEPENDENCIES={
 "stored_index_gate_sha256":("data/vv3_expanded_256_stored_index_gate.json","FE66D22010BC42302136C2B4EFD8100AF2D5938802CA52156313E235BCC56D0C"),
 "save_abi_gate_sha256":("data/vv3_expanded_256_save_serializer_abi_gate.json","C61D5B3DFCCC0B849509F28BFB3B406A46AE56E6B7AE3EB9F7B797201908F277"),
 "runtime_receipt_schema_sha256":("data/vv3_expanded_256_runtime_receipt.schema.json","52F8B12D1FFBB87A5D25381DD6D8172B118467015F17C805C10F5604E6FAAB52")}

class ContractError(ValueError): pass
def req(v:bool,m:str)->None:
    if not v: raise ContractError(m)
def pairs(items):
    out={}
    for k,v in items:req(k not in out,f"duplicate JSON key: {k}");out[k]=v
    return out
def canonical(v:object)->bytes:return (json.dumps(v,sort_keys=True,separators=(",",":"),ensure_ascii=False)+"\n").encode()
def load(path:Path=CONTRACT)->Mapping[str,Any]:
    value=json.loads(path.read_text(encoding="utf-8"),object_pairs_hook=pairs);req(isinstance(value,dict),"root must be object");return value
def digest(doc:Mapping[str,Any])->str:
    body=copy.deepcopy(dict(doc));body["integrity"]["canonical_sha256"]=None;return hashlib.sha256(canonical(body)).hexdigest().upper()
def source_hash(path:Path)->str:
    result=os.lstat(path);req(stat.S_ISREG(result.st_mode) and not stat.S_ISLNK(result.st_mode),"dependency is not a no-follow regular file")
    text=path.read_bytes().decode("utf-8-sig");return hashlib.sha256(text.replace("\r\n","\n").replace("\r","\n").encode()).hexdigest().upper()

def validate(doc:Mapping[str,Any],root:Path=ROOT)->dict[str,object]:
    req(doc.get("schema")=="vvfp.vv3_expanded_256_full_capacity_save_contract" and doc.get("schema_version")==1,"schema mismatch")
    req(doc.get("status")=="evidence_reference_stop" and doc.get("enabled") is False,"contract enabled")
    b=doc["bindings"];req(b["source_sha256"]==SOURCE and b["prototype_sha256"]==PROTOTYPE and b["c342_dependency"]==C342,"identity/C342 binding mismatch")
    for key,(rel,expected) in DEPENDENCIES.items():req(b[key]==expected and source_hash(root/rel)==expected,f"dependency mismatch: {key}")
    f=doc["reference_findings"];req(f["classification"]=="D350_D351_unverified_reference_only","reference promoted beyond evidence")
    req((f["record_size"],f["records_offset"],f["tail_offset"],f["expanded_body_size"],f["expanded_file_size"])==("0x11C","0x7864","0x19464","0x1A4B4","0x1A4C0"),"geometry mismatch")
    req(f["logical_first"]==0 and f["logical_last"]==255 and f["padding_indices"]==[256,257,258,259],"logical/padding boundary mismatch")
    rows=doc["native_evidence"]["stock_functions"];req(tuple((x["id"],x["ea"]) for x in rows)==FUNCTIONS,"function set mismatch")
    req(all(x["function_bounds"] is None and x["raw_bytes"] is None and x["complete_xrefs"] is None and x["artifact_refs"]==[] for x in rows),"unauthenticated native evidence populated")
    native=doc["native_evidence"];req(native["save_callers"]==[] and native["candidate_section_bytes"] is None and native["candidate_hook_bytes"] is None and native["candidate_final_bytes"] is None and native["authenticated_full_folder"] is False and native["status"]=="evidence_absent","native emission/evidence boundary relaxed")
    sem=doc["required_semantics"];req("write terminator only when count is less than 256" in sem["writer"] and "stop successfully after exactly 256 records without reading tail" in sem["reader"],"full-capacity semantics missing")
    req("never serialize padding 256 through 259" in sem["writer"] and "never construct or expose padding 256 through 259" in sem["reader"],"padding exclusion missing")
    atomic=sem["atomic_writer"]
    req("atomically replace destination only after verification" in atomic and "preserve prior destination on every failure" in atomic,"atomic writer semantics missing")
    req(atomic.index("verify exact size and authenticated integrity transform") < atomic.index("atomically replace destination only after verification"),"atomic replacement precedes verification")
    matrix=doc["runtime_fault_matrix"];req(tuple(x["id"] for x in matrix)==FAULTS and all(x["status"]=="pending" for x in matrix),"fault matrix changed")
    req(doc["decision"]=={"native_bytes_emitted":False,"enabled":False,"runtime_go":False,"player_go":False,"publication_ready":False,"status":"STOP"},"decision relaxed")
    req(doc["integrity"]["canonical_sha256"]==digest(doc),"canonical digest mismatch")
    return {"contract_valid":True,"functions":4,"faults":12,"native_evidence":False,"enabled":False,"runtime_go":False,"player_go":False,"publication_ready":False,"status":"STOP"}

def main(argv=None)->int:
    ap=argparse.ArgumentParser();ap.add_argument("--contract",type=Path,default=CONTRACT);a=ap.parse_args(argv)
    try:r=validate(load(a.contract))
    except Exception as exc:print(json.dumps({"contract_valid":False,"status":"STOP","error":str(exc)},sort_keys=True));return 1
    print(json.dumps(r,sort_keys=True));return 0
if __name__=="__main__":sys.exit(main())
