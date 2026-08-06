"""Production VV3 individual Full Mastery PE append/install helpers.

This module owns only the disabled/catalog-hidden ``.vv3im`` candidate.  It
operates on the already-composed Fullscreen Collection/Immediate parents and
derives the final section/header/checksum bytes from their exact 0xCE000 PE
layout.  Unknown parents and malformed candidate metadata fail closed.
"""
from __future__ import annotations

import hashlib
import importlib.util
import os
import struct
import stat
import json
import uuid
from pathlib import Path

from vv_fun_patcher import PatcherError, _pe_checksum_layout, pe_checksum, _validate_vv3_individual_full_mastery_candidate

ROOT = Path(__file__).resolve().parents[1]
BUILDER = ROOT / "scripts" / "build_vv3_individual_mastery_candidate.py"
HOOK_OFFSET = 0xA38C3
HOOK_BEFORE = bytes.fromhex("E938C02300")
HOOK_AFTER = bytes.fromhex("E938E72300")
APPEND_OFFSET = 0xCE000
APPEND_SIZE = 0x1000
SECTION_HEADER_OFFSET = 0x340
PARENT_HASHES = {
    "collection_progression": "8DD1CE07C885DDA3DD038D0B2F5C4F019D8C5BAC5DCA29F9799CE0C7909D2CEA",
    "immediate_fixed": "78758FD0003842AEFAC092A47874329C9C103F9AD46483E6ECA71291EFD3E382",
}
OUTPUT_HASHES = {
    "collection_progression": "BFFA0B5F54CD084138EABD68D3EA67F834CEFE915F7DB0000F81639F34BF90F1",
    "immediate_fixed": "6550141AFFAEF3F7965E89F1B32A3F4CB929E8E217778C5BBCB512AAC499E59C",
}
COMPANION_DLL_SHA256 = "9F866CB6F92C745CD2AA7009AEC4EB70FA5521EFF0C8F7BABE2058BB4D2F8533"


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def _page() -> bytes:
    spec = importlib.util.spec_from_file_location("vv3_individual_mastery_builder", BUILDER)
    if spec is None or spec.loader is None:
        raise PatcherError("VV3 individual Full Mastery builder is unavailable.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    page, details = module.build_page()
    expected = str(details.get("page_sha256", "")).upper()
    if len(page) != APPEND_SIZE or _sha(page) != expected:
        raise PatcherError("VV3 individual Full Mastery page hash/size mismatch.")
    return bytes(page)


def _header_patches() -> list[tuple[int, bytes, bytes]]:
    return [
        (0x10E, bytes.fromhex("0800"), bytes.fromhex("0900")),
        (0x158, bytes.fromhex("00202E00"), bytes.fromhex("00302E00")),
        (
            SECTION_HEADER_OFFSET,
            bytes(40),
            bytes.fromhex("2E767633696D00000010000000202E000010000000E00C0000000000000000000000000020000060"),
        ),
    ]


def render_parent(source: bytes, mode: str) -> bytes:
    _validate_vv3_individual_full_mastery_candidate()
    if mode not in PARENT_HASHES:
        raise PatcherError("VV3 individual Full Mastery supports stock modes only.")
    if len(source) != APPEND_OFFSET or _sha(source) != PARENT_HASHES[mode]:
        raise PatcherError("VV3 individual Full Mastery parent fingerprint mismatch.")
    if source[HOOK_OFFSET : HOOK_OFFSET + len(HOOK_BEFORE)] != HOOK_BEFORE:
        raise PatcherError("VV3 individual Full Mastery composed hook preimage mismatch.")
    page = _page()
    work = bytearray(source)
    for offset, before, after in _header_patches():
        if bytes(work[offset : offset + len(before)]) != before:
            raise PatcherError(f"VV3 individual Full Mastery header guard failed at 0x{offset:X}.")
        work[offset : offset + len(after)] = after
    work[HOOK_OFFSET : HOOK_OFFSET + len(HOOK_AFTER)] = HOOK_AFTER
    work.extend(page)
    checksum_offset, _ = _pe_checksum_layout(work)
    struct.pack_into("<I", work, checksum_offset, 0)
    struct.pack_into("<I", work, checksum_offset, pe_checksum(work))
    result = bytes(work)
    if _sha(result) != OUTPUT_HASHES[mode]:
        raise PatcherError("VV3 individual Full Mastery emitted output hash mismatch.")
    return result


def remove_candidate(candidate: bytes, mode: str) -> bytes:
    _validate_vv3_individual_full_mastery_candidate()
    if mode not in PARENT_HASHES:
        raise PatcherError("VV3 individual Full Mastery supports stock modes only.")
    if len(candidate) != APPEND_OFFSET + APPEND_SIZE:
        raise PatcherError("VV3 individual Full Mastery candidate size mismatch.")
    page = _page()
    if bytes(candidate[APPEND_OFFSET:]) != page:
        raise PatcherError("VV3 individual Full Mastery owned page guard mismatch.")
    work = bytearray(candidate[:APPEND_OFFSET])
    if bytes(work[HOOK_OFFSET : HOOK_OFFSET + len(HOOK_AFTER)]) != HOOK_AFTER:
        raise PatcherError("VV3 individual Full Mastery removal hook guard mismatch.")
    work[HOOK_OFFSET : HOOK_OFFSET + len(HOOK_BEFORE)] = HOOK_BEFORE
    for offset, before, after in reversed(_header_patches()):
        if bytes(work[offset : offset + len(after)]) != after:
            raise PatcherError(f"VV3 individual Full Mastery removal header guard failed at 0x{offset:X}.")
        work[offset : offset + len(before)] = before
    checksum_offset, _ = _pe_checksum_layout(work)
    struct.pack_into("<I", work, checksum_offset, 0)
    struct.pack_into("<I", work, checksum_offset, pe_checksum(work))
    if _sha(work) != PARENT_HASHES[mode]:
        raise PatcherError("VV3 individual Full Mastery removal did not restore the parent.")
    return bytes(work)


def _read_regular(path: Path) -> bytes:
    """Read only a non-reparse regular file; recovery never follows links."""
    if not os.path.lexists(path) or path.is_symlink():
        raise PatcherError(f"VV3 individual Full Mastery unsafe or missing file: {path}")
    st = os.lstat(path)
    if not stat.S_ISREG(st.st_mode):
        raise PatcherError(f"VV3 individual Full Mastery non-regular file: {path}")
    return path.read_bytes()


def _state(path: Path) -> tuple[bool, bytes | None]:
    if not os.path.lexists(path):
        return False, None
    return True, _read_regular(path)


def _write_recovery(parent: Path, details: dict[str, object]) -> Path:
    report = parent / f".vv3im-recovery-{uuid.uuid4().hex}.json"
    tmp = report.with_suffix(".tmp")
    tmp.write_text(json.dumps(details, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, report)
    return report


def _restore_member(path: Path, existed: bool, original: bytes | None, published: bytes) -> bool:
    """Restore one member without touching a foreign race-created file."""
    try:
        if not os.path.lexists(path):
            return not existed
        current = _read_regular(path)
        if existed:
            if current == original:
                return True
            if current != published:
                return False
            path.write_bytes(original or b"")
            return _read_regular(path) == (original or b"")
        if current != published:
            return False
        path.unlink()
        return not os.path.lexists(path)
    except (OSError, PatcherError):
        return False


def install_atomic(source: Path, destination: Path, mode: str, *, companion_source: Path | None = None, companion_destination: Path | None = None) -> None:
    """Install the EXE and mandatory companion as one guarded transaction."""
    if companion_source is None or companion_destination is None:
        raise PatcherError("VV3 individual Full Mastery companion is mandatory.")
    source_bytes = _read_regular(source)
    candidate = render_parent(source_bytes, mode)
    companion_bytes = _read_regular(companion_source)
    if len(companion_bytes) != 298496 or _sha(companion_bytes) != COMPANION_DLL_SHA256:
        raise PatcherError("VV3 individual Full Mastery companion hash mismatch.")
    destinations = [destination, companion_destination]
    if destination == companion_destination:
        raise PatcherError("VV3 individual Full Mastery destinations must be distinct.")
    for path in destinations:
        if path.parent.is_symlink() or not path.parent.is_dir():
            raise PatcherError("VV3 individual Full Mastery destination parent is unsafe.")
    pre = {path: _state(path) for path in destinations}
    expected_preimage = {destination: source_bytes, companion_destination: companion_bytes}
    for path, (exists, data) in pre.items():
        if exists and data != expected_preimage[path]:
            raise PatcherError("VV3 individual Full Mastery destination preimage mismatch.")
    token = uuid.uuid4().hex
    stages = {destination: destination.parent / f".{destination.name}.vv3im-{token}.stage", companion_destination: companion_destination.parent / f".{companion_destination.name}.vv3im-{token}.stage"}
    if any(os.path.lexists(p) for p in stages.values()):
        raise PatcherError("VV3 individual Full Mastery staging collision.")
    backups = {path: path.parent / f".{path.name}.vv3im-{token}.backup" for path, (exists, _) in pre.items() if exists}
    if any(os.path.lexists(p) for p in backups.values()):
        raise PatcherError("VV3 individual Full Mastery backup collision.")
    published = {destination: candidate, companion_destination: companion_bytes}
    committed: list[Path] = []
    try:
        stages[destination].write_bytes(candidate)
        stages[companion_destination].write_bytes(companion_bytes)
        for path, backup in backups.items():
            backup.write_bytes(pre[path][1] or b"")
            if _read_regular(backup) != pre[path][1]:
                raise PatcherError("VV3 individual Full Mastery backup verification failed.")
        if _read_regular(stages[destination]) != candidate or _read_regular(stages[companion_destination]) != companion_bytes:
            raise PatcherError("VV3 individual Full Mastery staged verification failed.")
        for path in destinations:
            current = _state(path)
            if current != pre[path]:
                raise PatcherError("VV3 individual Full Mastery destination race before publication.")
        os.replace(stages[destination], destination); committed.append(destination)
        if _state(companion_destination) != pre[companion_destination]:
            raise PatcherError("VV3 individual Full Mastery companion race before publication.")
        os.replace(stages[companion_destination], companion_destination); committed.append(companion_destination)
        if _read_regular(destination) != candidate or _read_regular(companion_destination) != companion_bytes:
            raise PatcherError("VV3 individual Full Mastery publication verification failed.")
    except Exception as exc:
        restored = all(_restore_member(path, *pre[path], published[path]) for path in destinations)
        for stage in stages.values():
            if os.path.lexists(stage):
                try: stage.unlink()
                except OSError: pass
        if not restored:
            _write_recovery(destination.parent, {"operation": "install", "destinations": [str(p) for p in destinations], "error": str(exc), "preconditions": {str(p): {"exists": pre[p][0], "sha256": _sha(pre[p][1]) if pre[p][1] is not None else None} for p in destinations}, "backups": {str(p): str(b) for p, b in backups.items()}})
        elif all(not os.path.lexists(p) or _read_regular(p) == pre[path][1] for path, p in backups.items()):
            for backup in backups.values():
                if os.path.lexists(backup): backup.unlink()
        raise
    for stage in stages.values():
        if os.path.lexists(stage): stage.unlink()
    for backup in backups.values():
        if os.path.lexists(backup): backup.unlink()


def remove_atomic(destination: Path, mode: str, *, companion_destination: Path | None = None, companion_restore_source: Path | None = None) -> None:
    """Remove EXE and mandatory companion, restoring both exact parents."""
    if companion_destination is None or companion_restore_source is None:
        raise PatcherError("VV3 individual Full Mastery companion removal arguments are mandatory.")
    candidate = _read_regular(destination)
    parent = remove_candidate(candidate, mode)
    companion_parent = _read_regular(companion_restore_source)
    if len(companion_parent) != 298496 or _sha(companion_parent) != COMPANION_DLL_SHA256 or _sha(_read_regular(companion_destination)) != COMPANION_DLL_SHA256:
        raise PatcherError("VV3 individual Full Mastery companion removal preimage mismatch.")
    destinations = [destination, companion_destination]
    for path in destinations:
        if path.parent.is_symlink() or not path.parent.is_dir():
            raise PatcherError("VV3 individual Full Mastery removal parent is unsafe.")
    pre = {destination: (True, candidate), companion_destination: (True, _read_regular(companion_destination))}
    published = {destination: parent, companion_destination: companion_parent}
    token = uuid.uuid4().hex
    stages = {destination: destination.parent / f".{destination.name}.vv3im-remove-{token}.stage", companion_destination: companion_destination.parent / f".{companion_destination.name}.vv3im-remove-{token}.stage"}
    if any(os.path.lexists(p) for p in stages.values()):
        raise PatcherError("VV3 individual Full Mastery removal staging collision.")
    backups = {path: path.parent / f".{path.name}.vv3im-remove-{token}.backup" for path in destinations}
    if any(os.path.lexists(p) for p in backups.values()):
        raise PatcherError("VV3 individual Full Mastery removal backup collision.")
    try:
        stages[destination].write_bytes(parent)
        stages[companion_destination].write_bytes(companion_parent)
        for path, backup in backups.items():
            backup.write_bytes(pre[path][1] or b"")
            if _read_regular(backup) != pre[path][1]:
                raise PatcherError("VV3 individual Full Mastery removal backup verification failed.")
        if _read_regular(stages[destination]) != parent or _read_regular(stages[companion_destination]) != companion_parent:
            raise PatcherError("VV3 individual Full Mastery removal staging verification failed.")
        if any(_state(path) != pre[path] for path in destinations):
            raise PatcherError("VV3 individual Full Mastery removal destination race.")
        os.replace(stages[destination], destination)
        if _state(companion_destination) != pre[companion_destination]:
            raise PatcherError("VV3 individual Full Mastery companion removal race.")
        os.replace(stages[companion_destination], companion_destination)
        if _read_regular(destination) != parent or _read_regular(companion_destination) != companion_parent:
            raise PatcherError("VV3 individual Full Mastery removal postverify failed.")
    except Exception as exc:
        restored = all(_restore_member(path, True, pre[path][1], published[path]) for path in destinations)
        for stage in stages.values():
            if os.path.lexists(stage):
                try: stage.unlink()
                except OSError: pass
        if not restored:
            _write_recovery(destination.parent, {"operation": "remove", "destinations": [str(p) for p in destinations], "error": str(exc), "preconditions": {str(p): {"exists": True, "sha256": _sha(pre[p][1])} for p in destinations}, "backups": {str(p): str(b) for p, b in backups.items()}})
        elif all(os.path.lexists(path) and _read_regular(path) == pre[path][1] for path in destinations):
            for backup in backups.values():
                if os.path.lexists(backup): backup.unlink()
        raise
    for backup in backups.values():
        if os.path.lexists(backup): backup.unlink()
