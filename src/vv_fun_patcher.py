from __future__ import annotations

import argparse
import hashlib
import json
import os
import struct
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "data" / "builds.json"

class PatcherError(RuntimeError):
    pass

@dataclass(frozen=True)
class Build:
    raw: dict[str, Any]
    def __getattr__(self, name: str) -> Any:
        try:
            return self.raw[name]
        except KeyError as exc:
            raise AttributeError(name) from exc

def load_builds() -> list[Build]:
    data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8-sig"))
    return [Build(item) for item in data["games"]]

def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()

def identify(path: Path) -> Build:
    path = path.resolve()
    if not path.is_file():
        raise PatcherError(f"Game executable not found: {path}")
    size = path.stat().st_size
    candidates = [build for build in load_builds() if build.size == size]
    if not candidates:
        raise PatcherError(f"Unsupported executable size: {size:,} bytes")
    digest = sha256(path)
    for build in candidates:
        if digest == build.sha256:
            return build
    raise PatcherError("This executable is not one of the five exact supported stock builds. " + f"SHA-256: {digest}")

def validate_all_sources(sources: dict[str, Path]) -> list[tuple[Build, Path]]:
    builds = load_builds()
    missing = [build.title for build in builds if build.id not in sources or not str(sources[build.id]).strip()]
    if missing:
        raise PatcherError("Choose all five original game EXEs. Missing: " + ", ".join(missing))
    resolved: list[tuple[Build, Path]] = []
    used_paths: set[Path] = set()
    for expected in builds:
        source = Path(sources[expected.id]).resolve()
        actual = identify(source)
        if actual.id != expected.id:
            raise PatcherError(f"Wrong game selected for {expected.title}: identified {actual.title}")
        if source in used_paths:
            raise PatcherError(f"The same executable was selected more than once: {source}")
        used_paths.add(source)
        resolved.append((expected, source))
    return resolved

def _pe_checksum_layout(data: bytearray) -> tuple[int, int]:
    if data[:2] != b"MZ":
        raise PatcherError("Input is not a Windows PE executable (missing MZ header).")
    pe_offset = struct.unpack_from("<I", data, 0x3C)[0]
    if data[pe_offset:pe_offset + 4] != b"PE\0\0":
        raise PatcherError("Input is not a Windows PE executable (missing PE header).")
    optional_offset = pe_offset + 24
    magic = struct.unpack_from("<H", data, optional_offset)[0]
    if magic not in (0x10B, 0x20B):
        raise PatcherError(f"Unsupported PE optional-header magic: 0x{magic:04X}")
    return optional_offset + 64, len(data)

def pe_checksum(data: bytearray) -> int:
    checksum_offset, length = _pe_checksum_layout(data)
    struct.pack_into("<I", data, checksum_offset, 0)
    total = 0
    padded = data + (b"\0" if len(data) % 2 else b"")
    for offset in range(0, len(padded), 2):
        total += padded[offset] | (padded[offset + 1] << 8)
        total = (total & 0xFFFF) + (total >> 16)
    total = (total & 0xFFFF) + (total >> 16)
    return ((total & 0xFFFF) + length) & 0xFFFFFFFF

def render_patched_bytes(source: Path, build: Build) -> tuple[bytearray, list[dict[str, str]]]:
    data = bytearray(source.read_bytes())
    applied: list[dict[str, str]] = []
    for patch in build.patches:
        offset = int(patch["offset"], 0)
        before = bytes.fromhex(patch["before"])
        after = bytes.fromhex(patch["after"])
        if len(before) != len(after):
            raise PatcherError(f"Internal manifest error at {patch['offset']}: length changed")
        actual = bytes(data[offset:offset + len(before)])
        if actual != before:
            raise PatcherError(f"Byte guard failed at {patch['offset']}: expected {before.hex().upper()}, found {actual.hex().upper()}")
        data[offset:offset + len(after)] = after
        applied.append({"offset":patch["offset"],"before":before.hex().upper(),"after":after.hex().upper(),"purpose":patch["purpose"]})
    checksum_offset, _ = _pe_checksum_layout(data)
    checksum = pe_checksum(data)
    struct.pack_into("<I", data, checksum_offset, checksum)
    return data, applied

def _result(build: Build, source: Path, patched: bytearray, applied: list[dict[str, str]]) -> dict[str, Any]:
    return {"game":build.title,"source":str(source.resolve()),"output_name":build.output_name,"villager_slots":build.villager_slots,"patches":applied,"result_sha256":hashlib.sha256(patched).hexdigest().upper()}

def dry_run(source: Path) -> dict[str, Any]:
    build = identify(source)
    patched, applied = render_patched_bytes(source, build)
    return _result(build, source, patched, applied)

def dry_run_all(sources: dict[str, Path]) -> list[dict[str, Any]]:
    validated = validate_all_sources(sources)
    results = []
    for build, source in validated:
        patched, applied = render_patched_bytes(source, build)
        results.append(_result(build, source, patched, applied))
    return results

def _log_data(build: Build, source: Path, output: Path, output_hash: str, applied: list[dict[str, str]]) -> dict[str, Any]:
    return {"patcher":"Virtual Villagers Fun Patcher","patch":"Modified Max Pop","created_utc":datetime.now(timezone.utc).isoformat(),"game":build.title,"villager_slots":build.villager_slots,"source_path":str(source.resolve()),"source_sha256":build.sha256,"output_path":str(output),"output_sha256":output_hash,"patches":applied}

def apply_patch(source: Path, output_dir: Path, overwrite: bool = False) -> tuple[Path, Path]:
    build = identify(source)
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    output = output_dir / build.output_name
    if output.exists() and not overwrite:
        raise PatcherError(f"Output already exists: {output}")
    patched, applied = render_patched_bytes(source, build)
    fd, temp_name = tempfile.mkstemp(prefix="vvfp-", suffix=".tmp", dir=output_dir)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(patched)
            handle.flush()
            os.fsync(handle.fileno())
        temp_path = Path(temp_name)
        if temp_path.stat().st_size != source.stat().st_size:
            raise PatcherError("Verification failed: patched file size changed")
        os.replace(temp_path, output)
    except Exception:
        Path(temp_name).unlink(missing_ok=True)
        raise
    output_hash = sha256(output)
    expected_hash = hashlib.sha256(patched).hexdigest().upper()
    if output_hash != expected_hash:
        output.unlink(missing_ok=True)
        raise PatcherError("Verification failed: output hash does not match generated bytes")
    log_path = output.with_suffix(".patch-log.json")
    log_path.write_text(json.dumps(_log_data(build, source, output, output_hash, applied), indent=2) + "\n", encoding="utf-8")
    return output, log_path

def apply_all(sources: dict[str, Path], output_dir: Path, overwrite: bool = False) -> list[tuple[Path, Path]]:
    validated = validate_all_sources(sources)
    plans: list[tuple[Build, Path, bytearray, list[dict[str, str]], Path]] = []
    output_dir = output_dir.resolve()
    for build, source in validated:
        patched, applied = render_patched_bytes(source, build)
        plans.append((build, source, patched, applied, output_dir / build.output_name))
    existing = [output for _, _, _, _, output in plans if output.exists()]
    if existing and not overwrite:
        raise PatcherError("Bulk output already exists; no files were written:\n" + "\n".join(str(path) for path in existing))
    output_dir.mkdir(parents=True, exist_ok=True)
    staged: list[tuple[Path, tuple[Build, Path, bytearray, list[dict[str, str]], Path]]] = []
    try:
        for plan in plans:
            build, source, patched, applied, output = plan
            fd, temp_name = tempfile.mkstemp(prefix=f"vvfp-{build.id}-", suffix=".tmp", dir=output_dir)
            with os.fdopen(fd, "wb") as handle:
                handle.write(patched)
                handle.flush()
                os.fsync(handle.fileno())
            temp_path = Path(temp_name)
            if temp_path.stat().st_size != source.stat().st_size:
                raise PatcherError(f"Verification failed before bulk commit: {build.title} size changed")
            if sha256(temp_path) != hashlib.sha256(patched).hexdigest().upper():
                raise PatcherError(f"Verification failed before bulk commit: {build.title} hash mismatch")
            staged.append((temp_path, plan))
        for temp_path, (_, _, _, _, output) in staged:
            os.replace(temp_path, output)
    except Exception:
        for temp_path, _ in staged:
            temp_path.unlink(missing_ok=True)
        raise
    results: list[tuple[Path, Path]] = []
    for build, source, patched, applied, output in plans:
        output_hash = sha256(output)
        expected_hash = hashlib.sha256(patched).hexdigest().upper()
        if output_hash != expected_hash:
            raise PatcherError(f"Bulk verification failed after commit: {build.title}")
        log_path = output.with_suffix(".patch-log.json")
        log_path.write_text(json.dumps(_log_data(build, source, output, output_hash, applied), indent=2) + "\n", encoding="utf-8")
        results.append((output, log_path))
    return results

def _add_all_source_args(parser: argparse.ArgumentParser) -> None:
    for build in load_builds():
        parser.add_argument(f"--{build.id}", required=True, type=Path, help=build.input_name)

def _all_sources_from_args(args: argparse.Namespace) -> dict[str, Path]:
    return {build.id:getattr(args, build.id) for build in load_builds()}

def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="Virtual Villagers Fun Patcher")
    sub = parser.add_subparsers(dest="command", required=True)
    identify_cmd = sub.add_parser("identify", help="identify an exact supported stock EXE")
    identify_cmd.add_argument("exe", type=Path)
    dry_cmd = sub.add_parser("dry-run", help="verify and preview without writing output")
    dry_cmd.add_argument("exe", type=Path)
    apply_cmd = sub.add_parser("apply", help="create one modified copy")
    apply_cmd.add_argument("exe", type=Path)
    apply_cmd.add_argument("output_dir", type=Path)
    apply_cmd.add_argument("--overwrite", action="store_true")
    dry_all_cmd = sub.add_parser("dry-run-all", help="verify all five games without writing output")
    _add_all_source_args(dry_all_cmd)
    apply_all_cmd = sub.add_parser("apply-all", help="create all five modified copies together")
    apply_all_cmd.add_argument("output_dir", type=Path)
    apply_all_cmd.add_argument("--overwrite", action="store_true")
    _add_all_source_args(apply_all_cmd)
    return parser

def main() -> int:
    args = _parser().parse_args()
    try:
        if args.command == "identify":
            print(json.dumps(identify(args.exe).raw, indent=2))
        elif args.command == "dry-run":
            print(json.dumps(dry_run(args.exe), indent=2))
        elif args.command == "apply":
            output, log = apply_patch(args.exe, args.output_dir, args.overwrite)
            print(f"Created: {output}")
            print(f"Log: {log}")
        elif args.command == "dry-run-all":
            print(json.dumps(dry_run_all(_all_sources_from_args(args)), indent=2))
        else:
            results = apply_all(_all_sources_from_args(args), args.output_dir, args.overwrite)
            for output, log in results:
                print(f"Created: {output}")
                print(f"Log: {log}")
        return 0
    except PatcherError as exc:
        print(f"Error: {exc}")
        return 1

if __name__ == "__main__":
    raise SystemExit(main())
