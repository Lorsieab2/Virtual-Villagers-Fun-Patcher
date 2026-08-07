"""Build a disabled metadata-only VV3 full-256 serializer candidate model."""
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUTPUT=ROOT/"data"/"candidates"/"vv3_full256_serializer_candidate.json"
SOURCE="8BC5DB382D02BC5C21AD5F607580D60FF44A6519CC7EB133F03113BAACAE6503"
PARENTS=(
 ("experimental_expanded_256","657D321B2F1E9E6D6C223DB1FF0BBA38C2D761A97A6E7F21B98CE1826531A848"),
 ("experimental_expanded_256_progression","3A35745C00102A0964DF6E81B77707539C5BDC03501011F43FF1D2809015B211"),
)
ABIS=(
 ("drain_record","0x455DD0","0x455E0A","26C8489FBAB307D110D1A8045368ECF16DD12F937F6EDE322097445BF2CEAAB1","thiscall ECX=live; no args; ret; no status"),
 ("manager_getter","0x428B60","0x428BCD","C5B6EE39E6DE419C32D141C5E42037261E26DE253ED38F874EC3FD9E3312E4A0","no args; EAX=singleton or null"),
 ("compact_writer","0x455460","0x4554F5","C71380CCF4F747B79B36C4BB2BE3EC9716AEF0EE3A6BC972AA2CFDB6563209FD","thiscall ECX=live; push compact; ret 4; AL=1"),
 ("reset_record","0x456000","0x45611C","8ADD4452CE6228B03A1ED53249C5DA3E6B3FBEF9864527F0EB423EC66E658024","thiscall ECX=live; no args; ret; no status"),
 ("compact_reader","0x456830","0x4568D2","FF9DFFE894F90B9C47BDDD92A29253CCF78A8277DC7C97E1198528093257C959","thiscall ECX=live; push compact; ret 4; AL=1"),
)

def model()->dict[str,object]:
    return {
      "schema":"vvfp.vv3_full256_serializer_static_candidate","schema_version":1,
      "candidate_id":"vv3-full256-serializer-reader-disabled",
      "status":"blocked_static_model","enabled":False,"catalog_visible":False,"native_output":False,
      "source_sha256":SOURCE,
      "parents":[{"mode":m,"sha256":h,"size":"0xCC000","sections":6,"size_of_image":"0x3B9000","result_sha256":None,"pe_checksum":None} for m,h in PARENTS],
      "section_plan":{"name":".vv3sv","header_raw":"0x2F0","raw_start":"0xCC000","raw_end":"0xCD000","rva":"0x3B9000","va":"0x7B9000","size":"0x1000","characteristics":"RX","header_bytes":None,"section_bytes":None,"final_bytes":None},
      "hooks":[
        {"id":"deserializer","raw":"0x27D57","va":"0x427D57","preimage":"E824720300","target":"0x7B9000","expected":"E8A4123900","emitted":None,"sole_callsite":True},
        {"id":"serializer","raw":"0x28A4C","va":"0x428A4C","preimage":"E80F3E0300","target":"0x7B9200","expected":"E8AF073900","emitted":None,"sole_callsite":True}
      ],
      "abis":[{"id":i,"start":s,"end":e,"sha256":h,"contract":c} for i,s,e,h,c in ABIS],
      "wrapper_model":{
        "compact_base":"call 0x428B60 then EAX+0x786C; formal serializer/deserializer pointer is ignored",
        "record_size":"0x11C","logical_indices":"0..255","padding":"256..259 forbidden",
        "serializer":["ECX=live; call 0x455DD0","call 0x428B60; null => AL=0","compact=EAX+0x786C+packed*0x11C","push compact; ECX=live; call 0x455460","terminator only when count<256","count==256 returns AL=1 without tail write"],
        "deserializer":["reset logical records 0..255 through 0x456000","call 0x428B60; null => AL=0","read no more than 256 compact records","compact=EAX+0x786C+index*0x11C","push compact; ECX=live; call 0x456830","terminator before 256 succeeds; exactly 256 succeeds without tail read","257th record is rejected"],
        "register_stack_gate":"wrappers must preserve nonvolatile EBX/ESI/EDI/EBP and restore ESP exactly; compact helpers pop their one argument with ret 4",
        "wrapper_bytes":None,"wrapper_sha256":None
      },
      "caller_failure_gate":{"load_caller_tests_al":True,"save_caller_tests_al":False,"save_caller_patch_raw":None,"save_caller_preimage":None,"save_caller_after":None,"recoverable_failure":False,"reason":"D353 proves save orchestration ignores serializer AL; no exact guarded caller branch dominates the writer."},
      "atomic_writer_plan":{
        "classification":"D354_disabled_plan_pending_D355","stock_writer":"0x403530","wrapper_va":"0x7B9400","wrapper_raw":"0xCC400",
        "callsites":[
          {"raw":"0x27C7D","preimage":None,"expected":"E87E173900","emitted":None},
          {"raw":"0x27C92","preimage":None,"expected":"E869173900","emitted":None},
          {"raw":"0x27D6C","preimage":None,"expected":"E88F163900","emitted":None},
          {"raw":"0x27D81","preimage":None,"expected":"E87A163900","emitted":None}
        ],
        "transaction":["sibling temporary path without numeric save slot","CREATE_NEW plus WRITE_THROUGH","write exact expanded file","flush close and reopen no-follow","verify exact size and authenticated integrity","existing final uses ReplaceFileA flags 0","absent final uses MoveFileExA WRITE_THROUGH without replace-existing","fatal non-returning failure until every caller checks result"],
        "dynamic_api_resolver_bytes":None,"wrapper_bytes":None,"wrapper_sha256":None,"import_changes":None,"enabled":False,"native_output":False,
        "blocker":"D355 must close exact callsite preimages, dynamic API resolver, wrapper bytes, failure path, and caller propagation."
      },
      "uninstall_ledger":{"restore_hooks":[{"raw":"0x27D57","bytes":"E824720300"},{"raw":"0x28A4C","bytes":"E80F3E0300"}],"restore_section_header":None,"truncate_to":"0xCC000","checksum_restore":None,"order":["restore and verify both hook preimages","restore and verify original section header bytes","truncate only candidate-owned 0xCC000..0xCD000","restore and verify parent checksum"]},
      "decision":{"static_layout_go":True,"native_output":False,"enabled":False,"runtime_go":False,"player_go":False,"publication_ready":False,"status":"STOP"},
    }

def canonical_bytes(value:object)->bytes:return (json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=False)+"\n").encode()
def build()->dict[str,object]:
    value=model();value["canonical_sha256"]=hashlib.sha256(canonical_bytes(value)).hexdigest().upper();return value
def main(argv=None)->int:
    ap=argparse.ArgumentParser();ap.add_argument("--output",type=Path);ap.add_argument("--check",action="store_true");a=ap.parse_args(argv);value=build();raw=canonical_bytes(value)
    if a.check:
        target=a.output or OUTPUT
        observed=target.read_bytes().replace(b"\r\n",b"\n") if target.is_file() else b""
        if observed!=raw:raise SystemExit("candidate model is stale")
    elif a.output: a.output.write_bytes(raw)
    else: print(raw.decode(),end="")
    return 0
if __name__=="__main__":raise SystemExit(main())
