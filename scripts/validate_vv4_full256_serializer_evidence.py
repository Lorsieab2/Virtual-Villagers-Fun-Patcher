#!/usr/bin/env python3
import argparse, hashlib, json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/vv4_full256_serializer_evidence.json"
VV4_DIGEST = "CEE01F4AEC59CB1CEE0F42E3DDDB3A24615261E628ED0629C1BFAABF421A897D"
VV5_C342_DIGEST = "14E460773ADC065E053FA30921ED01D33A5F36AD49DC754CCD69127EA02C01B7"
SERIALIZER_ROWS_SHA256 = "76C0C67381AD1DBDB630929E8CC4B599D410DCB4E6A66FABD9D79D9A4BF84F8A"
DESERIALIZER_ROWS_SHA256 = "02A4012A602D27538B1C7DA56FA5917EBCD6BA12C32D641CD35AE9486563814A"

def fail(ok, msg):
    if not ok: raise ValueError(msg)

def ledger_digest(doc):
    rows = doc["expanded_shr_relocations"]["patches"]
    return hashlib.sha256(json.dumps(rows, sort_keys=True, separators=(",", ":")).encode()).hexdigest().upper()

def row_digest(rows):
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
    fail(len(s["rows"])==24 and row_digest(s["rows"]) == SERIALIZER_ROWS_SHA256 and s["rows"][21]==["0x4660FE","C6841868C8000000","unconditional terminator"],"serializer exact rows")
    fail(len(r["rows"])==16 and row_digest(r["rows"]) == DESERIALIZER_ROWS_SHA256 and r["unresolved_exact_rows"]==["0x466132 acquire compact base call","0x466151 call 45DBE0","0x46616C next-zero instruction"],"deserializer exact/unknown rows")
    fail(s["hook_guard"]=={"raw":417952,"bytes":"5355565733"} and r["hook_guard"]=={"raw":418064,"bytes":"5356578D79"},"hook guards")
    fail(d["required_semantics"]=={"writer_bound":256,"terminator_predicate":"packed_count < 256","full_256_terminator":False,"reader_hard_bound":256,"full_unterminated_256_success":True,"tail_start":"0x1CC60","tail_preserved":True},"required semantics")
    fail(d["current_candidate"]["status"]=="insufficient_stop" and len(d["current_candidate"]["immediate_edits"])==2,"candidate insufficiency")
    fail(d["replacement"]=={
        "status":"static_serializer_reader_go_writer_stop",
        "parent_sha256":"3697317341C23B107F8C06F6D4164BC4602BF5CB90DFB56A6B68EB7EA3C43EE1",
        "new_section":".vv4x",
        "section_raw":"0xE3000",
        "section_rva":"0x471000",
        "section_va":"0x871000",
        "section_sha256":"F33DEFF4EF943EB4371AFD3AC80F3F35BC1DB21865ADCC5F115BDF2E20A37D45",
        "serializer_hook_raw":"0x1F125",
        "serializer_hook_target":"0x871180",
        "deserializer_hook_raw":"0x1FD34",
        "deserializer_hook_target":"0x871100",
        "serializer_final_sha256":"66EDFABF000302C9AD13D1794D3A6C5738DB0A78162A6FDC23406339D6187FE4",
        "deserializer_final_sha256":"DDCEE8650898E484FE569C28C0473D4377FF93739C9CA45E3A3238D95975C596",
        "gate_final_sha256":"7C73BF244E95BD0C0AD7FDB2D8F6CD47854F2C64A5FA2E1A3FE660E6BADFA4A1",
        "candidate_sha256":"364E35167E4DA8D9407030E42D41306A78FB50B73C7532B2D5166729EA447C43",
        "atomic_writer_status":"STOP",
    },"exact static replacement pins")
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
