"""Create a deterministic, no-follow inventory or a dry-run evidence plan."""
from __future__ import annotations
import argparse, hashlib, json, os, stat
from pathlib import Path

REPO=Path(__file__).resolve().parents[1]

def sha256(path: Path) -> str:
    before=path.lstat()
    if stat.S_ISLNK(before.st_mode) or getattr(before,"st_file_attributes",0) & 0x400: raise ValueError(f"link/reparse point forbidden: {path}")
    flags=os.O_RDONLY|getattr(os,"O_BINARY",0)|getattr(os,"O_NOFOLLOW",0)
    fd=os.open(path,flags); h=hashlib.sha256()
    try:
        opened=os.fstat(fd)
        if (before.st_dev,before.st_ino,before.st_size)!=(opened.st_dev,opened.st_ino,opened.st_size): raise ValueError(f"file identity changed before read: {path}")
        with os.fdopen(fd,"rb",closefd=False) as f:
            for block in iter(lambda:f.read(1024*1024),b""): h.update(block)
    finally: os.close(fd)
    after=path.lstat()
    if (before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns)!=(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns): raise ValueError(f"file changed during read: {path}")
    return h.hexdigest().upper()

def _inside(path: Path) -> Path:
    initial=path.absolute()
    st=initial.lstat()
    if stat.S_ISLNK(st.st_mode) or getattr(st,"st_file_attributes",0) & 0x400:
        raise ValueError("input root link/reparse point forbidden")
    p=path.resolve(strict=True); root=REPO.resolve(strict=True)
    try: p.relative_to(root)
    except ValueError: raise ValueError("input must be a copied self-contained folder inside this workspace")
    if p==root: raise ValueError("repository root is not a game-folder input")
    return p

def inventory(folder: Path) -> dict:
    root=_inside(folder)
    root_before=root.stat()
    records=[]; folded_paths=set()
    for current, dirs, files in os.walk(root,topdown=True,followlinks=False):
        base=Path(current)
        for name in list(dirs)+list(files):
            p=base/name; st=p.lstat()
            attrs=getattr(st,"st_file_attributes",0)
            if stat.S_ISLNK(st.st_mode) or attrs & 0x400: raise ValueError(f"link/reparse point forbidden: {p.relative_to(root).as_posix()}")
        dirs.sort(key=str.casefold); files.sort(key=str.casefold)
        for name in files:
            p=base/name; st=p.stat()
            rel=p.relative_to(root).as_posix(); folded=rel.casefold()
            if folded in folded_paths: raise ValueError(f"case-insensitive path collision: {rel}")
            folded_paths.add(folded)
            if not stat.S_ISREG(st.st_mode): raise ValueError(f"non-regular file forbidden: {rel}")
            records.append({"path":rel,"size":st.st_size,"sha256":sha256(p)})
    records.sort(key=lambda r:r["path"].casefold())
    root_after=root.stat()
    if (root_before.st_dev,root_before.st_ino,root_before.st_mtime_ns)!=(root_after.st_dev,root_after.st_ino,root_after.st_mtime_ns): raise ValueError("folder identity changed during inventory")
    canonical=json.dumps(records,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()
    return {"schema_version":1,"root_name":root.name,"complete":True,"no_follow":True,"file_count":len(records),"dll_count":sum(r["path"].lower().endswith(".dll") for r in records),"inventory_sha256":hashlib.sha256(canonical).hexdigest().upper(),"files":records}

def plan(game: str, folder: Path, manifest: Path) -> dict:
    inv=inventory(folder); m=json.loads(_inside(manifest).read_text(encoding="utf-8"))
    return {"schema_version":1,"dry_run":True,"game_id":game,"input_inventory_sha256":inv["inventory_sha256"],"manifest_sha256":sha256(manifest),"queries":[{"topic":topic,"query_id":qid,"action":"resolve-or-prove-absent"} for topic,qids in m["required_topics"].items() for qid in qids],"launches_performed":0,"exports_written":0}

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("folder",type=Path); ap.add_argument("--game",choices=("vv1","vv2")); ap.add_argument("--manifest",type=Path,default=REPO/"data/native_evidence/vv1_vv2_native_query_manifest.json"); ap.add_argument("--dry-run",action="store_true")
    a=ap.parse_args(); result=plan(a.game,a.folder,a.manifest) if a.dry_run and a.game else inventory(a.folder)
    if a.dry_run and not a.game: ap.error("--dry-run requires --game")
    print(json.dumps(result,indent=2,sort_keys=True))
if __name__=="__main__": main()
