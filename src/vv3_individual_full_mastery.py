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
COMPANION_PARENT_DLL_SHA256 = "35FB96199E745C7D8054FF6A12851B9E09225E3E41D0CE04012604E74968C0D5"


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


def _unsafe_stat(st: os.stat_result) -> bool:
    return bool(getattr(st, "st_file_attributes", 0) & 0x400)


def _safe_ancestor_chain(path: Path) -> None:
    """Reject links/reparse points in every existing ancestor without resolve()."""
    absolute = Path(os.path.abspath(os.fspath(path)))
    chain: list[Path] = []
    current = absolute
    while True:
        chain.append(current)
        if current.parent == current:
            break
        current = current.parent
    for item in reversed(chain):
        if not os.path.lexists(item):
            continue
        st = os.lstat(item)
        if stat.S_ISLNK(st.st_mode) or _unsafe_stat(st):
            raise PatcherError(f"VV3 individual Full Mastery reparse ancestor: {item}")
        if item != absolute and not stat.S_ISDIR(st.st_mode):
            raise PatcherError(f"VV3 individual Full Mastery non-directory ancestor: {item}")
        if getattr(item, "is_junction", lambda: False)():
            raise PatcherError(f"VV3 individual Full Mastery junction ancestor: {item}")


def _read_regular(path: Path) -> bytes:
    """No-follow read with identity checks before and after hashing."""
    _safe_ancestor_chain(path.parent)
    if not os.path.lexists(path):
        raise PatcherError(f"VV3 individual Full Mastery unsafe or missing file: {path}")
    before = os.lstat(path)
    if stat.S_ISLNK(before.st_mode) or _unsafe_stat(before) or not stat.S_ISREG(before.st_mode):
        raise PatcherError(f"VV3 individual Full Mastery non-regular/reparse file: {path}")
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(os.fspath(path), flags)
    except OSError as exc:
        raise PatcherError(f"VV3 individual Full Mastery no-follow open failed: {path}") from exc
    try:
        opened = os.fstat(fd)
        same_identity = opened.st_size == before.st_size and stat.S_IFMT(opened.st_mode) == stat.S_IFMT(before.st_mode)
        if before.st_ino and opened.st_ino and before.st_ino != opened.st_ino:
            same_identity = False
        if before.st_dev and opened.st_dev and before.st_dev != opened.st_dev:
            same_identity = False
        if not same_identity:
            raise PatcherError(f"VV3 individual Full Mastery file identity changed: {path}")
        chunks: list[bytes] = []
        while True:
            chunk = os.read(fd, 1024 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
        after = os.fstat(fd)
        if after.st_size != opened.st_size or stat.S_IFMT(after.st_mode) != stat.S_IFMT(opened.st_mode) or (opened.st_ino and after.st_ino and after.st_ino != opened.st_ino):
            raise PatcherError(f"VV3 individual Full Mastery file changed while reading: {path}")
        return b"".join(chunks)
    finally:
        os.close(fd)


def _state(path: Path) -> tuple[bool, bytes | None]:
    if not os.path.lexists(path):
        return False, None
    return True, _read_regular(path)


def _fsync_file(path: Path) -> None:
    fd = os.open(os.fspath(path), os.O_RDONLY | getattr(os, "O_BINARY", 0))
    try:
        os.fsync(fd)
    except OSError:
        pass
    finally:
        os.close(fd)


def _fsync_dir(path: Path) -> None:
    try:
        fd = os.open(os.fspath(path), os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    except OSError:
        pass


def _write_file(path: Path, data: bytes) -> None:
    _safe_ancestor_chain(path.parent)
    with open(path, "xb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    _fsync_dir(path.parent)


def _write_recovery(parent: Path, details: dict[str, object]) -> Path:
    report = parent / f".vv3im-recovery-{uuid.uuid4().hex}.json"
    tmp = report.with_suffix(".tmp")
    payload = {"schema_version": 2, **details}
    _write_file(tmp, (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    os.replace(tmp, report)
    _fsync_dir(parent)
    return report


def _remove_owned(path: Path) -> None:
    if not os.path.lexists(path):
        return
    st = os.lstat(path)
    if stat.S_ISLNK(st.st_mode) or _unsafe_stat(st) or not stat.S_ISREG(st.st_mode):
        raise PatcherError(f"VV3 individual Full Mastery unsafe cleanup member: {path}")
    path.unlink()


def _copy_preserved(source: Path, target: Path, expected: bytes) -> None:
    _write_file(target, expected)
    if _read_regular(target) != expected:
        raise PatcherError(f"VV3 individual Full Mastery copy verification failed: {target}")


def _restore_member(path: Path, existed: bool, original: bytes | None, published: bytes, *, backup: Path | None = None) -> bool:
    """Restore one member independently through an owned sibling stage."""
    try:
        current = _state(path)
        if existed and current == (True, original):
            return True
        if not existed and current == (False, None):
            return True
        if current[0] and current[1] != published:
            return False
        if existed:
            source = backup if backup is not None else None
            if source is not None and _read_regular(source) != original:
                return False
            stage = path.parent / f".{path.name}.vv3im-restore-{uuid.uuid4().hex}.stage"
            _copy_preserved(source, stage, original or b"") if source is not None else _write_file(stage, original or b"")
            os.replace(stage, path)
            return _state(path) == (True, original)
        if current[0] and current[1] == published:
            _remove_owned(path)
        return not os.path.lexists(path)
    except (OSError, PatcherError):
        return False


def _validate_pair_parent(destinations: list[Path]) -> Path:
    absolute = [Path(os.path.abspath(os.fspath(p))) for p in destinations]
    if len({p.parent for p in absolute}) != 1 or absolute[0] == absolute[1]:
        raise PatcherError("VV3 individual Full Mastery destinations must share one parent and be distinct.")
    parent = absolute[0].parent
    _safe_ancestor_chain(parent)
    if not parent.is_dir():
        raise PatcherError("VV3 individual Full Mastery destination parent is unsafe.")
    return parent


def _transaction(operation: str, destinations: list[Path], pre: dict[Path, tuple[bool, bytes | None]], published: dict[Path, bytes], *, expected_preimage: dict[Path, bytes], parent: Path) -> None:
    token = uuid.uuid4().hex
    stages = {p: parent / f".{p.name}.vv3im-{token}.stage" for p in destinations}
    backups = {p: parent / f".{p.name}.vv3im-{token}.backup" for p in destinations if pre[p][0]}
    if any(os.path.lexists(p) for p in (*stages.values(), *backups.values())):
        raise PatcherError("VV3 individual Full Mastery staging collision.")
    committed = False
    try:
        for p in destinations:
            _write_file(stages[p], published[p])
            if _read_regular(stages[p]) != published[p]:
                raise PatcherError("VV3 individual Full Mastery staged verification failed.")
        for p, b in backups.items():
            _copy_preserved(p, b, pre[p][1] or b"")
        for p in destinations:
            if _state(p) != pre[p] or _read_regular(stages[p]) != published[p]:
                raise PatcherError("VV3 individual Full Mastery pre-replace race.")
        for p in destinations:
            if _state(p) != pre[p]:
                raise PatcherError("VV3 individual Full Mastery destination race before publication.")
            os.replace(stages[p], p)
        committed = True
        if any(_state(p) != (True, published[p]) for p in destinations):
            raise PatcherError("VV3 individual Full Mastery publication postverify failed.")
    except Exception as exc:
        restored = {}
        for p in destinations:
            restored[p] = _restore_member(p, *pre[p], published[p], backup=backups.get(p))
        if all(restored.values()) and all(_state(p) == pre[p] for p in destinations):
            for p in (*stages.values(), *backups.values()):
                if os.path.lexists(p):
                    try: _remove_owned(p)
                    except PatcherError: pass
            _fsync_dir(parent)
            raise PatcherError(f"VV3 individual Full Mastery {operation} publication failed; pair restored") from exc
        else:
            report = _write_recovery(parent, {
                "operation": operation,
                "destination_parent": str(parent),
                "members": [{"path": str(p), "pre_exists": pre[p][0], "pre_sha256": _sha(pre[p][1]) if pre[p][1] is not None else None, "pre_size": len(pre[p][1]) if pre[p][1] is not None else 0, "published_sha256": _sha(published[p]), "published_size": len(published[p]), "backup": str(backups[p]) if p in backups else None, "stage": str(stages[p])} for p in destinations],
                "ownership_inventory": [str(x) for x in (*stages.values(), *backups.values()) if os.path.lexists(x)],
                "error": str(exc),
            })
            raise PatcherError(f"VV3 individual Full Mastery transaction failed; recovery retained at {report}") from exc
    finally:
        if committed:
            for p in (*stages.values(), *backups.values()):
                if os.path.lexists(p):
                    try: _remove_owned(p)
                    except PatcherError: pass
            _fsync_dir(parent)


def recover_atomic(report_or_root: Path) -> None:
    """Replay a strict schema-v2 report; originals are copy-preserved until pair verify."""
    root = Path(report_or_root)
    report = root if root.name.endswith(".json") else root
    if report.is_dir():
        reports = list(report.glob(".vv3im-recovery-*.json"))
        if len(reports) != 1:
            raise PatcherError("VV3 individual Full Mastery recovery report is ambiguous.")
        report = reports[0]
    _safe_ancestor_chain(report.parent)
    payload = json.loads(_read_regular(report).decode("utf-8"))
    if payload.get("schema_version") != 2 or payload.get("operation") not in {"install", "remove"}:
        raise PatcherError("VV3 individual Full Mastery recovery schema is unsupported.")
    members = payload.get("members")
    if not isinstance(members, list) or len(members) != 2:
        raise PatcherError("VV3 individual Full Mastery recovery members are invalid.")
    paths = [Path(m["path"]) for m in members]
    parent = _validate_pair_parent(paths)
    if Path(os.path.abspath(payload.get("destination_parent", ""))) != parent:
        raise PatcherError("VV3 individual Full Mastery recovery destination parent mismatch.")
    for m in members:
        p = Path(m["path"]); backup = Path(m["backup"]) if m.get("backup") else None
        pre_exists = bool(m["pre_exists"])
        current = _state(p)
        if pre_exists:
            if backup is None or _sha(_read_regular(backup)) != m["pre_sha256"]:
                raise PatcherError("VV3 individual Full Mastery recovery backup mismatch.")
            if current[0] and _sha(current[1] or b"") not in {m["published_sha256"], m["pre_sha256"]}:
                raise PatcherError("VV3 individual Full Mastery recovery destination is foreign.")
        elif current[0] and _sha(current[1] or b"") != m["published_sha256"]:
            raise PatcherError("VV3 individual Full Mastery expected-absent recovery destination is foreign.")
    for m in members:
        p = Path(m["path"]); backup = Path(m["backup"]) if m.get("backup") else None
        if bool(m["pre_exists"]):
            original = _read_regular(backup)
            current = _state(p)
            if current != (True, original):
                stage = p.parent / f".{p.name}.vv3im-replay-{uuid.uuid4().hex}.stage"
                _copy_preserved(backup, stage, original)
                os.replace(stage, p)
        elif os.path.lexists(p):
            _remove_owned(p)
    for m in members:
        p = Path(m["path"])
        if bool(m["pre_exists"]):
            if _sha(_read_regular(p)) != m["pre_sha256"]:
                raise PatcherError("VV3 individual Full Mastery recovery postverify failed.")
        elif os.path.lexists(p):
            raise PatcherError("VV3 individual Full Mastery recovery absence postverify failed.")
    for m in members:
        for key in ("backup", "stage"):
            q = m.get(key)
            if q and os.path.lexists(q):
                _remove_owned(Path(q))
    _remove_owned(report)


# Explicit production-facing name used by audit/recovery callers.
recover_vv3_transaction = recover_atomic


def install_atomic(source: Path, destination: Path, mode: str, *, companion_source: Path | None = None, companion_destination: Path | None = None) -> None:
    if companion_source is None or companion_destination is None:
        raise PatcherError("VV3 individual Full Mastery companion is mandatory.")
    destinations = [Path(destination), Path(companion_destination)]
    parent = _validate_pair_parent(destinations)
    source_bytes = _read_regular(source)
    candidate = render_parent(source_bytes, mode)
    companion_bytes = _read_regular(companion_source)
    if len(companion_bytes) != 298496 or _sha(companion_bytes) != COMPANION_DLL_SHA256:
        raise PatcherError("VV3 individual Full Mastery companion hash mismatch.")
    companion_parent_path = ROOT / "data" / "candidates" / "VVFP VV3 Full Mastery Candidate.dll"
    companion_parent = _read_regular(companion_parent_path)
    if len(companion_parent) != 298496 or _sha(companion_parent) != COMPANION_PARENT_DLL_SHA256:
        raise PatcherError("VV3 individual Full Mastery companion parent source mismatch.")
    pre = {p: _state(p) for p in destinations}
    expected_preimage = {destinations[0]: source_bytes, destinations[1]: companion_parent}
    for p in destinations:
        if pre[p][0] and pre[p][1] != expected_preimage[p]:
            raise PatcherError("VV3 individual Full Mastery destination preimage mismatch.")
    _transaction("install", destinations, pre, {destinations[0]: candidate, destinations[1]: companion_bytes}, expected_preimage=expected_preimage, parent=parent)


def remove_atomic(destination: Path, mode: str, *, companion_destination: Path | None = None, companion_restore_source: Path | None = None) -> None:
    if companion_destination is None or companion_restore_source is None:
        raise PatcherError("VV3 individual Full Mastery companion removal arguments are mandatory.")
    candidate = _read_regular(destination)
    parent_bytes = remove_candidate(candidate, mode)
    companion_parent = _read_regular(companion_restore_source)
    if len(companion_parent) != 298496 or _sha(companion_parent) != COMPANION_PARENT_DLL_SHA256:
        raise PatcherError("VV3 individual Full Mastery companion parent hash mismatch.")
    destinations = [Path(destination), Path(companion_destination)]
    parent = _validate_pair_parent(destinations)
    pre = {destinations[0]: (True, candidate), destinations[1]: (True, _read_regular(companion_destination))}
    if _sha(pre[destinations[1]][1] or b"") != COMPANION_DLL_SHA256:
        raise PatcherError("VV3 individual Full Mastery candidate companion preimage mismatch.")
    _transaction("remove", destinations, pre, {destinations[0]: parent_bytes, destinations[1]: companion_parent}, expected_preimage={}, parent=parent)
