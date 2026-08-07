#!/usr/bin/env python3
import argparse, hashlib, json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/vv4_full256_serializer_evidence.json"
VV4_DIGEST = "CEE01F4AEC59CB1CEE0F42E3DDDB3A24615261E628ED0629C1BFAABF421A897D"
VV5_C342_DIGEST = "14E460773ADC065E053FA30921ED01D33A5F36AD49DC754CCD69127EA02C01B7"

def fail(ok, msg):
    if not ok: raise ValueError(msg)

def ledger_digest(doc):
    rows = doc["expanded_shr_relocations"]["patches"]
    return hashlib.sha256(json.dumps(rows, sort_keys=True, separators=(",", ":")).encode()).hexdigest().upper()

def validate(path=DATA, root=ROOT):
    d=json.loads(Path(path).read_text(encoding="utf-8"))
    fail(d["schema_version"]=="vvfp.vv4_full256_serializer_evidence.v1","schema")
    fail(d["status"]=="static_reference_stop" and d["enabled"] is False,"must remain disabled")
    fail(not any(d["publication"].values()),"publication/runtime/player must remain false")
    fail(d["bindings"]["stock_sha256"]=="6D27A429FFCA5F1F71FDD7ECA761ED1BB67E85F976494BA178B3D7BE01F1B220","stock fingerprint")
    fail(d["bindings"]["vv4_relocation_ledger"]=={"path":"data/vv4_origins_feature.json","count":13,"digest":VV4_DIGEST},"VV4 ledger binding")
    fail(d["bindings"]["c342_vv5_relocation_ledger"]=={"path":"data/vv5_origins_feature.json","count":66,"digest":VV5_C342_DIGEST,"integration_only":True},"C342 VV5 binding")
    fail(d["geometry"]=={"stock_body":94476,"table_start":51296,"stock_tail_start":90296,"record_stride":260,"added_records":106,"expanded_tail_start":117856,"expanded_body":122036,"expanded_file":122060,"header":24},"geometry")
    s=d["stock_functions"]["serializer"]; r=d["stock_functions"]["deserializer"]
    fail(len(s["rows"])==24 and s["rows"][21]==["0x4660FE","C6841868C8000000","unconditional terminator"],"serializer exact rows")
    fail(len(r["rows"])==16 and r["unresolved_exact_rows"]==["0x466132 acquire compact base call","0x466151 call 45DBE0","0x46616C next-zero instruction"],"deserializer exact/unknown rows")
    fail(s["hook_guard"]=={"raw":417952,"bytes":"5355565733"} and r["hook_guard"]=={"raw":418064,"bytes":"5356578D79"},"hook guards")
    fail(d["required_semantics"]=={"writer_bound":256,"terminator_predicate":"packed_count < 256","full_256_terminator":False,"reader_hard_bound":256,"full_unterminated_256_success":True,"tail_start":"0x1CC60","tail_preserved":True},"required semantics")
    fail(d["current_candidate"]["status"]=="insufficient_stop" and len(d["current_candidate"]["immediate_edits"])==2,"candidate insufficiency")
    fail(d["replacement"]["status"]=="unknown_stop" and all(v is None for k,v in d["replacement"].items() if k!="status"),"unknown replacement fields must be null")
    fail(d["atomic_writer"]["status"]=="unknown_stop" and len(d["atomic_writer"]["gates"])==6 and d["atomic_writer"]["completed"]==[],"atomic writer STOP")
    fail(d["runtime_fault_matrix"]["status"]=="absent_stop" and len(d["runtime_fault_matrix"]["cases"])==21 and d["runtime_fault_matrix"]["receipts"]==[],"runtime matrix STOP")
    fail(d["evidence"]==[],"checked-in evidence must be empty")
    vv4=json.loads((Path(root)/"data/vv4_origins_feature.json").read_text(encoding="utf-8"))
    rows=vv4["expanded_shr_relocations"]["patches"]
    fail(len(rows)==13 and ledger_digest(vv4)==VV4_DIGEST,"local VV4 ledger changed")
    return True

if __name__=="__main__":
    p=argparse.ArgumentParser(); p.add_argument("--contract",type=Path,default=DATA); p.add_argument("--root",type=Path,default=ROOT); a=p.parse_args()
    validate(a.contract,a.root); print("VV4 full-256 serializer evidence: STOP (contract valid; native/runtime/player evidence absent)")
