"""Read-only authenticated inventory, export-plan, and export validator."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
QUERY_PATH = ROOT / "data/native_evidence_queries.json"
GAMES = {
    "vv3": ("Virtual Villagers - The Secret City.exe", 831488, "8BC5DB382D02BC5C21AD5F607580D60FF44A6519CC7EB133F03113BAACAE6503"),
    "vv4": ("Virtual Villagers - The Tree of Life.exe", 929792, "6D27A429FFCA5F1F71FDD7ECA761ED1BB67E85F976494BA178B3D7BE01F1B220"),
    "vv5": ("Virtual Villagers - New Believers.exe", 991232, "92946781980220E9D1A2E6C573925519934608F5215F4A0F8CE3B90088C5C65D"),
}

class EvidenceError(ValueError):
    pass

def canonical_json(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode("utf-8")

def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()

def _inside(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False

def _reparse(path: Path) -> bool:
    attrs = getattr(path.lstat(), "st_file_attributes", 0)
    return path.is_symlink() or bool(attrs & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))

def read_no_follow(path: Path) -> bytes:
    before = path.lstat()
    if _reparse(path) or not stat.S_ISREG(before.st_mode):
        raise EvidenceError(f"non-regular or linked artifact rejected: {path}")
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags)
    try:
        opened = os.fstat(fd)
        if (before.st_dev, before.st_ino, before.st_size) != (opened.st_dev, opened.st_ino, opened.st_size):
            raise EvidenceError(f"artifact identity changed while opening: {path}")
        chunks = []
        while True:
            block = os.read(fd, 1024 * 1024)
            if not block:
                break
            chunks.append(block)
        after = os.fstat(fd)
        if (opened.st_dev, opened.st_ino, opened.st_size, opened.st_mtime_ns) != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns):
            raise EvidenceError(f"artifact changed while hashing: {path}")
        return b"".join(chunks)
    finally:
        os.close(fd)

def inventory_folder(workspace_root: Path, game_folder: Path, game: str) -> dict[str, Any]:
    root = workspace_root.resolve(strict=True)
    folder = game_folder.resolve(strict=True)
    if folder == root or not _inside(folder, root):
        raise EvidenceError("game folder must be a child of the declared self-contained workspace root")
    if _reparse(folder):
        raise EvidenceError("game folder cannot be a link or reparse point")
    files = []
    for current, dirs, names in os.walk(folder, followlinks=False):
        current_path = Path(current)
        for name in list(dirs):
            if _reparse(current_path / name):
                raise EvidenceError(f"linked directory rejected: {current_path / name}")
        for name in names:
            path = current_path / name
            payload = read_no_follow(path)
            files.append({"path": path.relative_to(folder).as_posix(), "size": len(payload), "sha256": sha(payload)})
    files.sort(key=lambda item: item["path"].casefold())
    if not files:
        raise EvidenceError("complete game folder cannot be empty")
    exe_name, exe_size, exe_sha = GAMES[game]
    exe = next((item for item in files if item["path"].casefold() == exe_name.casefold()), None)
    if exe != {"path": exe_name, "size": exe_size, "sha256": exe_sha}:
        raise EvidenceError("exact stock executable fingerprint mismatch")
    record = {"schema": "vvfp.full-folder-inventory.v1", "game": game, "root_name": folder.name, "file_count": len(files), "files": files}
    record["inventory_sha256"] = sha(canonical_json(record))
    return record

def dry_run_plan(inventory: dict[str, Any]) -> dict[str, Any]:
    queries = json.loads(QUERY_PATH.read_text(encoding="utf-8"))
    game = inventory["game"]
    return {"schema": "vvfp.native-evidence-plan.v1", "dry_run": True, "game": game, "inventory_sha256": inventory["inventory_sha256"], "queries": queries["queries"], "exporters": ["ida_python", "ghidra"], "writes": []}

def validate_export(export: dict[str, Any], inventory: dict[str, Any], exe_bytes: bytes) -> list[str]:
    errors = []
    queries = json.loads(QUERY_PATH.read_text(encoding="utf-8"))["queries"]
    if export.get("schema") != "vvfp.authenticated-native-export.v1": errors.append("schema mismatch")
    if export.get("generated_by") not in ("ida_python", "ghidra"): errors.append("untrusted generator")
    if export.get("synthetic") is not False or export.get("manual") is not False: errors.append("synthetic/manual export rejected")
    if export.get("game") != inventory.get("game") or export.get("inventory_sha256") != inventory.get("inventory_sha256"): errors.append("source binding mismatch")
    rows = export.get("functions")
    if not isinstance(rows, list) or [row.get("query_id") for row in rows if isinstance(row, dict)] != [q["id"] for q in queries]:
        errors.append("partial, duplicate, or reordered query results")
        rows = []
    required = {"query_id", "status", "function_start_ea", "function_end_ea", "file_offset", "raw_bytes", "instructions", "callers", "xrefs", "registers", "stack_cleanup", "call_convention"}
    for row in rows:
        if set(row) != required or row.get("status") != "resolved":
            errors.append(f"{row.get('query_id')}: incomplete row"); continue
        try:
            start, end, offset = int(row["function_start_ea"], 0), int(row["function_end_ea"], 0), int(row["file_offset"], 0)
            raw = bytes.fromhex(row["raw_bytes"])
        except (TypeError, ValueError):
            errors.append(f"{row.get('query_id')}: malformed address/bytes"); continue
        if end <= start or not raw or offset < 0 or exe_bytes[offset:offset + len(raw)] != raw:
            errors.append(f"{row.get('query_id')}: bounds or source bytes mismatch")
        if not row["instructions"] or not isinstance(row["callers"], list) or not isinstance(row["xrefs"], list) or not isinstance(row["registers"], dict) or not row["registers"]:
            errors.append(f"{row.get('query_id')}: instructions/xrefs/register proof missing")
        if not row["stack_cleanup"] or not row["call_convention"] or "REVIEW_REQUIRED" in row["stack_cleanup"] or "REVIEW_REQUIRED" in row["call_convention"]:
            errors.append(f"{row.get('query_id')}: ABI proof missing")
    if export.get("artifact_sha256") != sha(canonical_json({k: v for k, v in export.items() if k != "artifact_sha256"})):
        errors.append("export artifact hash mismatch")
    return errors

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("inventory", "plan", "validate"))
    parser.add_argument("--workspace-root", required=True, type=Path)
    parser.add_argument("--game-folder", required=True, type=Path)
    parser.add_argument("--game", required=True, choices=tuple(GAMES))
    parser.add_argument("--export", type=Path)
    args = parser.parse_args(argv)
    try:
        inv = inventory_folder(args.workspace_root, args.game_folder, args.game)
        if args.command == "inventory": output = inv
        elif args.command == "plan": output = dry_run_plan(inv)
        else:
            if args.export is None: raise EvidenceError("--export is required for validate")
            export_path = args.export.resolve(strict=True)
            if not _inside(export_path, args.workspace_root.resolve(strict=True)): raise EvidenceError("export must be inside workspace root")
            export = json.loads(read_no_follow(export_path).decode("utf-8"))
            exe_name = GAMES[args.game][0]
            errors = validate_export(export, inv, read_no_follow(args.game_folder / exe_name))
            output = {"valid": not errors, "errors": errors}
        sys.stdout.buffer.write(canonical_json(output))
        return 0 if not output.get("errors") else 2
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, EvidenceError) as exc:
        sys.stderr.write(str(exc) + "\n"); return 2

if __name__ == "__main__":
    raise SystemExit(main())
