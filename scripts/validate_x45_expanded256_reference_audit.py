#!/usr/bin/env python3
import argparse, hashlib, json, struct
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
AUDIT=ROOT/"data/x45_expanded256_reference_audit.json"
LEDGER_DIGESTS={"vv4":"CEE01F4AEC59CB1CEE0F42E3DDDB3A24615261E628ED0629C1BFAABF421A897D","vv5":"A5DF4E109D32E2BC9FDE36E2BA3139230B6E6CD89DE4C3FF784846F4CE803740"}

def sha(b): return hashlib.sha256(b).hexdigest().upper()
def canon_json(p): return sha(json.dumps(json.loads(p.read_text(encoding="utf-8-sig")),sort_keys=True,separators=(",",":")).encode("utf-8"))
def rows(d): return d["expanded_shr_relocations"]["patches"]
def require(v,m):
    if not v: raise ValueError(m)
def check_rel32(game, d, spec):
    require(spec["external_targets_must_not_move"] is True,f"{game} external target policy")
    start=int(spec["shr_stock_start"],16); end=int(spec["shr_stock_end"],16); expanded_start=int(spec["shr_expanded_start"],16); delta=int(spec["delta"],16)
    for r in rows(d):
        if r.get("kind")!="rel32": continue
        source=int(r["source_virtual_address"],16); source_stock=source-delta if source>=expanded_start else source; disp=struct.unpack("<i",bytes.fromhex(r["before"]))[0]; target=source_stock+5+disp
        require(target==int(r["target_stock_virtual_address"],16),f"{game} {r['offset']} stock rel32 target")
        if start <= target < end:
            expected=target+delta
            actual=r.get("target_expanded_virtual_address")
            require(actual is None or int(actual,16)==expected,f"{game} {r['offset']} moved target")
        else:
            require(r.get("target_expanded_virtual_address") is not None and int(r["target_expanded_virtual_address"],16)==target,f"{game} {r['offset']} external target moved")
    return True
def validate(path=AUDIT, root=ROOT):
    a=json.loads(Path(path).read_text(encoding="utf-8")); require(a["status"]=="audit_stop" and a["ledger_changes_allowed"] is False,"audit state")
    require(not any(a["publication"].values()) and a["evidence"]==[],"publication/evidence")
    for game in ("vv4","vv5"):
        spec=a["games"][game]; p=Path(root)/spec["ledger"]["path"]; d=json.loads(p.read_text(encoding="utf-8")); rs=rows(d)
        require(len(rs)==spec["ledger"]["count"] and len(rs)==(13 if game=="vv4" else 66),f"{game} count")
        expected_digest=spec["ledger"].get("digest",spec["ledger"].get("current_digest")); require(d["expanded_shr_relocations"]["ledger_sha256"]==expected_digest,f"{game} embedded digest")
        require(sha(p.read_bytes())==spec["ledger"]["raw_sha256"],f"{game} raw pin")
        require(canon_json(p)==spec["ledger"]["canonical_json_sha256"],f"{game} canonical text pin")
        check_rel32(game,d,spec["rel32_policy"])
    require(a["legacy_stale_references"][0]["classification"]=="stale_raw_file_pin_stop" and a["legacy_stale_references"][1]["classification"]=="stale_raw_file_pin_stop","stale classifications")
    require(all(v.endswith("_stop") for v in a["gates"].values()),"all gates STOP")
    return a
if __name__=="__main__":
    p=argparse.ArgumentParser(); p.add_argument("--audit",type=Path,default=AUDIT); p.add_argument("--root",type=Path,default=ROOT); args=p.parse_args(); validate(args.audit,args.root); print("X45 Expanded-256 reference audit: STOP (ledger/rel32 pins valid; stale refs and runtime evidence gaps remain)")
