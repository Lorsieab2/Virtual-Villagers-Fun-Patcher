#!/usr/bin/env python3
"""Read-only C342 VV4/VV5 folder, source-text, ledger, and export preflight."""
import argparse, hashlib, json, os, stat
from pathlib import Path

try:
    from scripts.source_text_hash import source_text_sha256
except ImportError:
    from source_text_hash import source_text_sha256

ROOT=Path(__file__).resolve().parents[1]
CONTRACT=ROOT/"data/c342_export_preflight.json"

class PreflightError(ValueError): pass
def require(ok,msg):
    if not ok: raise PreflightError(msg)
def raw_sha(path):
    h=hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda:f.read(1024*1024),b""): h.update(chunk)
    return h.hexdigest().upper()
def no_follow_files(root):
    require(root.is_dir() and not root.is_symlink(),f"input folder missing or symlink: {root}")
    files=[]
    for base,dirs,names in os.walk(root,topdown=True,followlinks=False):
        basep=Path(base)
        kept=[]
        for name in dirs:
            p=basep/name; st=p.lstat(); attrs=getattr(st,"st_file_attributes",0)
            require(not p.is_symlink() and not (attrs & 0x400),f"unsafe directory entry: {p}")
            kept.append(name)
        dirs[:]=kept
        for name in names:
            p=basep/name; st=p.lstat(); attrs=getattr(st,"st_file_attributes",0); require(not p.is_symlink() and not (attrs & 0x400),f"unsafe file entry: {p}"); files.append(p)
    return sorted(files,key=lambda p:p.relative_to(root).as_posix().casefold())
def inventory_digest(root, files):
    records=[]
    for p in files:
        relative=p.relative_to(root).as_posix(); size=p.stat().st_size; first=raw_sha(p); second=raw_sha(p)
        require(first==second,f"unstable input file: {relative}"); records.append({"path":relative,"size":size,"sha256":first})
    payload=json.dumps(records,sort_keys=True,separators=(",",":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest().upper()
def check_folder(root, game, spec):
    files=no_follow_files(root); require(len(files)==spec["physical_file_count"],f"{game} physical file count {len(files)} != {spec['physical_file_count']}")
    exe=root/spec["stock_executables"][game]["name"]; require(exe.is_file() and not exe.is_symlink(),f"{game} stock executable missing")
    require(raw_sha(exe)==spec["stock_executables"][game]["sha256"],f"{game} stock executable hash mismatch")
    return {"count":len(files),"stock_exe_sha256":raw_sha(exe),"inventory_sha256":inventory_digest(root,files)}
def check_rebind(root, game, spec):
    binding=spec["c342_rebind"][game]; p=root/binding["ledger_path"]; require(p.is_file(),f"{game} ledger missing")
    d=json.loads(p.read_text(encoding="utf-8")); rows=d["expanded_shr_relocations"]["patches"]
    require(len(rows)==binding["ledger_count"],f"{game} ledger count mismatch")
    require(d["expanded_shr_relocations"]["ledger_sha256"]==binding["ledger_sha256"],f"{game} ledger digest mismatch")
    require(source_text_sha256(p)==binding["source_text_sha256"],f"{game} source-text pin mismatch")
    return {"count":len(rows),"ledger_sha256":binding["ledger_sha256"],"source_text_sha256":binding["source_text_sha256"]}
def check_export(path, game, spec, folder_result):
    require(path.is_file() and not path.is_symlink(),f"{game} machine export missing: {path}")
    d=json.loads(path.read_text(encoding="utf-8")); req=spec["required_machine_export"]
    require(d.get("status")==req["status_required"],f"{game} export status is not authenticated")
    require(d.get("synthetic") is False and d.get("manual_injection") is False,"synthetic/manual export rejected")
    for key in req["required_fields"]: require(key in d and d[key] not in (None,"",[]),f"{game} export field missing: {key}")
    require(d["source_executable_sha256"]==folder_result["stock_exe_sha256"],f"{game} export executable binding mismatch")
    body=dict(d); body.pop("re_read_sha256",None); expected=hashlib.sha256(json.dumps(body,sort_keys=True,separators=(",",":")).encode("utf-8")).hexdigest().upper()
    require(d["re_read_sha256"]==expected,f"{game} export canonical re-read hash mismatch")
    return {"status":d["status"],"rows":len(d["rows"])}
def validate(root=ROOT, vv4_folder=None, vv5_folder=None, vv4_export=None, vv5_export=None):
    c=json.loads(CONTRACT.read_text(encoding="utf-8")); require(c["status"].startswith("preflight_stop"),"preflight must remain STOP")
    require(not any(c["gates"][k] for k in ("enabled","catalog","native_output","runtime_go","player_go","publication")) and c["gates"]["evidence"]==[],"gates changed")
    results={}
    for game,folder,export in (("vv4",vv4_folder,vv4_export),("vv5",vv5_folder,vv5_export)):
        require(folder is not None, f"{game} input folder not supplied")
        fr=check_folder(Path(folder),game,c); binding=check_rebind(Path(root),game,c)
        # Inventory digest is intentionally required from a separately produced no-follow manifest; no synthetic count is accepted.
        require(export is not None,f"{game} machine export not supplied")
        results[game]={"folder":fr,"rebind":binding,"export":check_export(Path(export),game,c,fr)}
    return results
def main():
    p=argparse.ArgumentParser(); p.add_argument("--root",type=Path,default=ROOT); p.add_argument("--vv4-folder",type=Path); p.add_argument("--vv5-folder",type=Path); p.add_argument("--vv4-export",type=Path); p.add_argument("--vv5-export",type=Path); a=p.parse_args()
    try: validate(a.root,a.vv4_folder,a.vv5_folder,a.vv4_export,a.vv5_export)
    except (PreflightError,FileNotFoundError,json.JSONDecodeError) as e: print(f"C342 export preflight: STOP ({e})"); raise SystemExit(2)
    print("C342 export preflight: STOP-safe inputs and exports validated")
if __name__=="__main__": main()
