#!/usr/bin/env python3
"""Validate the disabled VV4 full-256 serializer model; never emit a PE."""
import argparse, hashlib, json, struct
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
MODEL=ROOT/"data/candidates/vv4_full256_serializer_static_candidate.json"
PARENT_SHA="3697317341C23B107F8C06F6D4164BC4602BF5CB90DFB56A6B68EB7EA3C43EE1"

def require(v,m):
    if not v: raise ValueError(m)
def rel32(source,target): return "E9"+struct.pack("<i",target-(source+5)).hex().upper()

def validate(path=MODEL):
    d=json.loads(Path(path).read_text(encoding="utf-8"))
    require(d["status"]=="blocked_static_model","status")
    require(not any(d[k] for k in ("enabled","catalog_visible","native_output","runtime_go","player_go","publication_eligible")),"candidate must remain disabled")
    require(d["parent"]=={"mode":"experimental_expanded_256","size":0xE3000,"sha256":PARENT_SHA,"exclusive":True},"exclusive parent")
    require(d["rejected_composed_parents"]==["full_mastery","full_heal","fullscreen","running"],"composed-parent rejection")
    require(d["ledger_bindings"]["vv4"]=={"count":13,"digest":"CEE01F4AEC59CB1CEE0F42E3DDDB3A24615261E628ED0629C1BFAABF421A897D"},"VV4 ledger")
    s=d["section"]; require(s["name"]==".vv4x" and (s["raw_start"],s["raw_end"],s["rva"],s["va"],s["header_raw"])==(0xE3000,0xE4000,0x471000,0x871000,0x2C0),"section layout")
    require(s["characteristics"]=="RX" and s["header_guard"]=="00"*40 and s["final_header_bytes"] is None,"section header guard")
    expected=[("serializer",0x4660A0,0x660A0,"5355565733",0x871000,"E95BAF4000"),("deserializer",0x466110,0x66110,"5356578D79",0x871100,"E9EBAF4000")]
    for row,e in zip(d["hooks"],expected):
        name,va,raw,before,target,after=e
        require((row["name"],row["va"],row["raw"],row["before"],row["target"],row["after"])==e,"hook pin")
        require(rel32(va,target)==after,"rel32 mismatch")
    helpers={"drain":("0x45EAA0","0x45EAD9","13BBB3D0FB0BE6970B5EB454B706229CF536487C9C5481527FE64F8EE17B5E75"),"singleton":("0x41FE70","0x41FEEA","CFD2040568A260D38E125A6973C4B849FBBA0440553A2A301DDA79C0317BBE08"),"encode":("0x45DB30","0x45DBD1","EB2932E1BAED9F12AD14928677DC1A3248DF9A0615A7C67A400A1604474844E3"),"reset":("0x45D8A0","0x45D9AC","BA84FBE6CC322E112B7CF8956EC433516E5623E36767FD35578CB2691A0FE469"),"decode":("0x45DBE0","0x45DCD0","68A1C70F2CE2F3EA627FF17F55A5D6A22C2182CE248B664440BB36EDD9358A07")}
    for name,pin in helpers.items(): require(tuple(d["d353_helpers"][name][k] for k in ("ea","end","sha256"))==pin,"D353 helper pin")
    for name,regs in (("serializer",["EBX","EBP","ESI","EDI"]),("deserializer",["EBX","ESI","EDI"])):
        w=d["wrapper_model"][name]; require(w["preserves"]==regs and w["bound"]==256 and w["return"]=="AL boolean; ret 4","ABI model")
        require(w["singleton"]=={"function":"0x41FE70","compact_base_offset":"0xC868","null_result":"AL=0"},"singleton model")
        require(len(w["instruction_model"])>=9,"complete instruction model")
    require(d["wrapper_model"]["serializer"]["terminator"]=="write exactly one zero byte only when packed_count < 256","terminator")
    require(d["wrapper_model"]["deserializer"]["full_256_unterminated"]=="success without reading record 257 or tail","reader bound")
    require(d["wrapper_model"]["deserializer"]["clear_before_reset"]=="clear all 256 live records before resetting load index","clear/reset order")
    writer=d["writer_model"]
    require(writer["status"]=="blocked_pending_d355" and writer["entry"]=={"ea":"0x4039B0","raw":0x39B0,"before":"81EC04020000","replacement_kind":"complete_entry_e9_rel32_plus_nop","target":None,"after":None},"writer entry guard")
    atomic=writer["atomic_contract"]
    require(atomic["temp_create"]=="sibling CREATE_NEW | WRITE_THROUGH" and atomic["final_exists"]=="ReplaceFileA(final,temp,backup,0,NULL,NULL)","atomic replacement contract")
    require(atomic["required_sequence"]==["exact write","flush","checked CloseHandle write handle","no-follow reopen","reject reparse point","verify volume serial and FileId identity","GetFileSizeEx equals 24 plus body","compare complete 24-byte header and complete body","checked CloseHandle verification handle"],"verification sequence")
    require("without MOVEFILE_REPLACE_EXISTING" in atomic["final_absent"] and "leave it untouched and fail fatally" in atomic["final_absent"],"raced final policy")
    require(atomic["temp_cleanup"]=="delete only identity-verified owned temp" and atomic["directory_entry_power_loss_durability"]=="unsupported and unproved on Windows API contract","cleanup/durability policy")
    require(atomic["api_resolution"]=="dynamic" and atomic["failure_policy"]=="fatal process abandon until all callers prove checked failure handling","writer safety policy")
    require(writer["resolver_bytes"] is None and writer["page_bytes"] is None and writer["final_sha256"] is None,"D355 placeholders must remain null")
    require(writer["caller_ledger"]=={"status":"complete_addresses_unproved_handling_stop","sites":["0x41F04D","0x41F060","0x41F13A","0x41F14F","0x41F160","0x41E4C0"],"nonreturn_primitive":None},"writer caller ledger")
    require(len(d["blocked_evidence"])==6,"blocker inventory")
    require(all(v is None for v in d["final"].values()),"final bytes/hashes must remain null")
    require(d["uninstall"]["candidate_sha256"] is None and d["uninstall"]["checksum_before"] is None and d["uninstall"]["checksum_after"] is None,"uninstall proof absent")
    return d

def main():
    p=argparse.ArgumentParser(); p.add_argument("--model",type=Path,default=MODEL); p.add_argument("--parent",type=Path); p.add_argument("--dry-run",action="store_true"); a=p.parse_args()
    d=validate(a.model)
    if a.parent:
        b=a.parent.read_bytes(); require(len(b)==0xE3000 and hashlib.sha256(b).hexdigest().upper()==PARENT_SHA,"wrong parent")
    require(a.dry_run,"disabled model accepts only --dry-run")
    print("VV4 full-256 serializer candidate: STOP (static model valid; native output disabled)")

if __name__=="__main__": main()
