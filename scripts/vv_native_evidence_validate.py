"""Validate canonical authenticated IDA/Ghidra evidence exports."""
from __future__ import annotations
import argparse, hashlib, json, re
from pathlib import Path
HEX64=re.compile(r"^[0-9A-F]{64}$"); EA=re.compile(r"^0x[0-9A-F]+$")
FORBIDDEN=("synthetic","manual","placeholder","todo","tbd","unknown","guessed")

class EvidenceError(ValueError): pass
def fail(path,msg): raise EvidenceError(f"{path}: {msg}")
def canonical_hash(value): return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()).hexdigest().upper()
def load(path): return json.loads(Path(path).read_text(encoding="utf-8"))
def _hex(v,p):
    if not isinstance(v,str) or not HEX64.fullmatch(v): fail(p,"must be uppercase SHA-256")
def _ea(v,p):
    if not isinstance(v,str) or not EA.fullmatch(v): fail(p,"must be canonical uppercase 0x address")
def _clean(v,p="export"):
    if isinstance(v,str) and any(x in v.casefold() for x in FORBIDDEN): fail(p,"manual/synthetic/placeholder content forbidden")
    if isinstance(v,dict):
        for k,x in v.items(): _clean(x,f"{p}.{k}")
    if isinstance(v,list):
        for i,x in enumerate(v): _clean(x,f"{p}[{i}]")

def validate(export,manifest,inventory):
    if export.get("schema_version")!=1 or export.get("producer") not in ("ida-python","ghidra-python"): fail("export","unsupported producer/schema")
    if export.get("automated_export") is not True or export.get("manual_edits") is not False or export.get("complete") is not True: fail("export","must be complete automated unedited export")
    _clean(export)
    if export.get("game_id") not in manifest["games"]: fail("export.game_id","unsupported")
    binding=export.get("source_binding",{})
    if set(binding)!={"executable_sha256","folder_inventory_sha256","manifest_sha256","exporter_sha256","analyzer_name","analyzer_version"}: fail("source_binding","field set mismatch")
    for name in ("executable_sha256","folder_inventory_sha256","manifest_sha256","exporter_sha256"): _hex(binding.get(name),f"source_binding.{name}")
    if not binding["analyzer_name"] or not binding["analyzer_version"]: fail("source_binding","analyzer identity/version required")
    if binding["folder_inventory_sha256"]!=inventory.get("inventory_sha256"): fail("source_binding","folder inventory mismatch")
    if binding["manifest_sha256"]!=canonical_hash(manifest): fail("source_binding.manifest_sha256","manifest mismatch")
    files=inventory.get("files",[])
    if not any(x.get("sha256")==binding["executable_sha256"] and x.get("path","").lower().endswith(".exe") for x in files): fail("source_binding.executable_sha256","executable is not bound to inventory")
    expected={(topic,qid) for topic,qids in manifest["required_topics"].items() for qid in qids}
    funcs=export.get("functions")
    if not isinstance(funcs,list): fail("functions","must be array")
    actual=set(); required=set(manifest["required_function_fields"]); ikeys=set(manifest["required_instruction_fields"])
    for i,f in enumerate(funcs):
        if set(f)!=required: fail(f"functions[{i}]","field set mismatch")
        key=(f["topic"],f["query_id"])
        if key in actual or key not in expected: fail(f"functions[{i}]","duplicate or unexpected query")
        actual.add(key)
        if f["status"] not in manifest["allowed_status"]: fail(f"functions[{i}].status","invalid")
        for n in ("start_ea","end_ea"): _ea(f[n],f"functions[{i}].{n}")
        for n in ("start_file_offset","end_file_offset"):
            if type(f[n]) is not int or f[n]<0: fail(f"functions[{i}].{n}","must be nonnegative integer")
        _hex(f["raw_bytes_sha256"],f"functions[{i}].raw_bytes_sha256")
        if f["status"]=="resolved":
            try: raw=bytes.fromhex(f["raw_bytes_hex"])
            except Exception: fail(f"functions[{i}].raw_bytes_hex","invalid hex")
            if hashlib.sha256(raw).hexdigest().upper()!=f["raw_bytes_sha256"]: fail(f"functions[{i}]","raw byte hash mismatch")
            if not f["instructions"]: fail(f"functions[{i}].instructions","empty")
            for j,ins in enumerate(f["instructions"]):
                if set(ins)!=ikeys: fail(f"functions[{i}].instructions[{j}]","field set mismatch")
                _ea(ins["ea"],f"functions[{i}].instructions[{j}].ea")
        if f["source_binding"]!=binding: fail(f"functions[{i}].source_binding","must equal export binding")
    if actual!=expected: fail("functions",f"partial export; missing {len(expected-actual)} queries")
    unsigned=dict(export); claimed=unsigned.pop("artifact_sha256",None); _hex(claimed,"artifact_sha256")
    if canonical_hash(unsigned)!=claimed: fail("artifact_sha256","canonical artifact hash mismatch")
    return True

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("export",type=Path); ap.add_argument("--manifest",type=Path,required=True); ap.add_argument("--inventory",type=Path,required=True); a=ap.parse_args(); validate(load(a.export),load(a.manifest),load(a.inventory)); print("VALID")
if __name__=="__main__": main()
