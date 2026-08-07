"""Fail-closed validator for the VV3 Expanded-256 save/serializer ABI gate."""
from __future__ import annotations
import argparse, copy, hashlib, json, os, stat, sys
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "data" / "vv3_expanded_256_save_serializer_abi_gate.json"
SOURCE = "8BC5DB382D02BC5C21AD5F607580D60FF44A6519CC7EB133F03113BAACAE6503"
PROTOTYPE = "6EE3361A7AC35F441763647C1E2FC9EC49569DE5EF372BDB41D243D03002D601"
STORED = "FE66D22010BC42302136C2B4EFD8100AF2D5938802CA52156313E235BCC56D0C"
ROW_IDS = ("loader_entry","loader_cave","loader_postcopy","save_count","writer_primary","writer_secondary","writer_final")
ROW_EAS = ("0x428949","0x47B3B1","0x428961","0x428810","0x45C860","0x45C8D0","0x45EF80")
GAPS = ("save_sizes_layouts","loader_abi","writer_abi","record_geometry","padding","encoding","save_lifecycle","identity_boundaries","runtime_receipts")
SHA = __import__('re').compile(r"^[0-9A-F]{64}$")
REPARSE = 0x400

class GateError(ValueError): pass
def req(v: bool, m: str) -> None:
    if not v: raise GateError(m)
def pairs(items):
    out={}
    for k,v in items: req(k not in out, f"duplicate JSON key: {k}"); out[k]=v
    return out
def canonical(v: object) -> bytes:
    return (json.dumps(v,sort_keys=True,separators=(",",":"),ensure_ascii=False)+"\n").encode()
def load(path: Path, canonical_only=False) -> Mapping[str,Any]:
    raw=path.read_bytes(); value=json.loads(raw.decode(),object_pairs_hook=pairs)
    req(isinstance(value,dict),"root must be object")
    if canonical_only: req(raw==canonical(value),"candidate JSON is not canonical")
    return value
def digest(doc: Mapping[str,Any]) -> str:
    body=copy.deepcopy(dict(doc)); body["integrity"]["canonical_sha256"]=None
    return hashlib.sha256(canonical(body)).hexdigest().upper()
def file_hash(path: Path) -> str:
    # Dependencies are text Git blobs; bind their canonical LF content so the
    # same commit validates in CRLF worktrees and clean Git archives.
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest().upper()
def safe_file(root: Path, rel: str, size: int, sha: str) -> None:
    p=PureWindowsPath(rel); req("\\" not in rel and not p.drive and not p.root and all(x not in ("",".","..") and ":" not in x for x in rel.split("/")),"unsafe evidence path")
    target=root.joinpath(*PurePosixPath(rel).parts); before=os.lstat(target)
    req(stat.S_ISREG(before.st_mode) and not stat.S_ISLNK(before.st_mode) and not (getattr(before,"st_file_attributes",0)&REPARSE),"evidence file is symlink/reparse/nonfile")
    raw=target.read_bytes(); after=os.lstat(target)
    req((before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns)==(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns),"evidence file mutated or substituted")
    req(len(raw)==size and hashlib.sha256(raw).hexdigest().upper()==sha,"evidence identity mismatch")

def validate_contract(doc: Mapping[str,Any]) -> dict[str,object]:
    req(doc.get("schema")=="vvfp.vv3_expanded_256_save_serializer_abi_gate" and doc.get("schema_version")==1,"schema mismatch")
    req(doc.get("status")=="STOP" and doc.get("enabled") is False,"gate enabled")
    b=doc["bindings"]; req(b["source_sha256"]==SOURCE and b["prototype_sha256"]==PROTOTYPE and b["stored_index_gate_sha256"]==STORED,"fingerprint/dependency mismatch")
    expected={"folder_inventory_schema_sha256":"118986E7F78F90597BF2B804D7C68DBE41158C599098A4F9A2E2C652AF3675FE","runtime_receipt_schema_sha256":"52F8B12D1FFBB87A5D25381DD6D8172B118467015F17C805C10F5604E6FAAB52","exporter_manifest_schema_sha256":"EE94B02D964DFCE7729BE610DC6AAD1553E88B65ADF31CD9E763CB84A15767BE","runtime_harness_sha256":"AB1C8A37A2B3450501A62404E6E6C6342F545AC8F0828EACC0DC4A8589861D67"}
    paths={"folder_inventory_schema_sha256":"data/vv3_expanded_256_folder_inventory.schema.json","runtime_receipt_schema_sha256":"data/vv3_expanded_256_runtime_receipt.schema.json","exporter_manifest_schema_sha256":"data/vv3_expanded_256_exporter_manifest.schema.json","runtime_harness_sha256":"scripts/prepare_vv3_expanded_runtime_capture.py"}
    for k,v in expected.items(): req(b[k]==v and file_hash(ROOT/paths[k])==v,f"stale binding: {k}")
    rows=doc["native_rows"]; req(tuple(x["id"] for x in rows)==ROW_IDS and tuple(x["ea"] for x in rows)==ROW_EAS,"native row set mismatch")
    req(all(x["expected"] is None and x["evidence_refs"]==[] for x in rows),"checked-in native row populated")
    gaps=doc["gap_matrix"]; req(tuple(x["id"] for x in gaps)==GAPS and all(x["status"]=="evidence_absent" for x in gaps),"gap matrix changed")
    req(doc["runtime_evidence"]=={"candidate":None,"authenticated":False,"structural_valid":False,"gate_ready":False},"runtime evidence populated")
    req(doc["decision"]=={"publication_ready":False,"runtime_go":False,"player_go":False,"native_emission_permitted":False,"status":"STOP"},"decision relaxed")
    req(doc["integrity"]["canonical_sha256"]==digest(doc),"canonical digest mismatch")
    return {"contract_valid":True,"native_rows":7,"gaps":9,"gate_ready":False,"runtime_go":False,"player_go":False,"publication_ready":False,"status":"STOP"}

def validate_candidate(path: Path, root: Path) -> dict[str,object]:
    errors=[]
    try:
        c=load(path,True); req(c.get("source_sha256")==SOURCE and c.get("prototype_sha256")==PROTOTYPE and c.get("stored_index_gate_sha256")==STORED,"candidate identity mismatch")
        refs=set(c.get("artifact_refs",[])); req(bool(refs) and len(refs)==len(c.get("artifact_refs",[])),"artifact refs absent/duplicate")
        for name in ("exporter_manifest","folder_inventory","runtime_receipt"):
            x=c[name]; req(x.get("authenticated") is True and x.get("no_follow") is True and x.get("re_read_verified") is True,"unauthenticated binding"); req(SHA.fullmatch(x["sha256"]) is not None,"invalid hash"); safe_file(root,x["path"],x["size"],x["sha256"])
        rows=c["native_rows"]; req(tuple(x["id"] for x in rows)==ROW_IDS and tuple(x["ea"] for x in rows)==ROW_EAS,"candidate native rows incomplete/reordered")
        for row in rows:
            req(row["full_folder_bound"] is True and row["xrefs_complete"] is True and row["artifact_refs"],"native row not authenticated/full-folder bound")
            tuples=[(x["address"],x["kind"]) for x in row["xrefs"]]; req(len(tuples)==len(set(tuples)),"duplicate xref")
            req(set(row["artifact_refs"])<=refs,"unknown native artifact ref")
        # Real receipts remain pending under the checked-in v1 harness; structural evidence cannot grant GO.
    except (GateError,KeyError,TypeError,ValueError,OSError,json.JSONDecodeError) as exc: errors.append(str(exc))
    return {"structural_valid":not errors,"authenticated_source":not errors,"gate_ready":False,"runtime_go":False,"player_go":False,"publication_ready":False,"status":"STOP","errors":errors}

def main(argv=None) -> int:
    ap=argparse.ArgumentParser(); ap.add_argument("--contract",type=Path,default=CONTRACT); ap.add_argument("--candidate",type=Path); ap.add_argument("--catalog-root",type=Path)
    a=ap.parse_args(argv)
    try: result=validate_contract(load(a.contract));
    except Exception as exc: print(json.dumps({"contract_valid":False,"status":"STOP","error":str(exc)},sort_keys=True)); return 1
    if a.candidate:
        if not a.catalog_root: print(json.dumps({"status":"STOP","error":"--catalog-root required"},sort_keys=True)); return 1
        result=validate_candidate(a.candidate,a.catalog_root)
    print(json.dumps(result,sort_keys=True)); return 1 if a.candidate or not result["contract_valid"] else 0
if __name__=="__main__": sys.exit(main())
