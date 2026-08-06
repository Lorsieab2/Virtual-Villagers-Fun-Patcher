"""Explicit disabled VV5 Grant Running EXE+DLL publication transaction.

The candidate is not public.  These entry points are for independent audit
and guarded internal rendering only; they never broaden catalog enablement.
"""
from __future__ import annotations

import hashlib
import json
import os
import stat
import uuid
from pathlib import Path

from vv_fun_patcher import PatcherError, render_vv5_individual_running_parent, remove_vv5_individual_running_parent

ROOT = Path(__file__).resolve().parents[1]
DLL_SHA256 = "29927CECB448B64944E18E2BA11893DC84C91B39241FBB2549FC2A464E0BE2ED"
DLL_SIZE = 298496
DLL_NAME = "VVFP VV5 Full Mastery Candidate.dll"


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def _unsafe(st: os.stat_result) -> bool:
    return bool(getattr(st, "st_file_attributes", 0) & 0x400)


def _safe_ancestors(path: Path) -> None:
    p = Path(os.path.abspath(os.fspath(path)))
    chain = []
    while True:
        chain.append(p)
        if p.parent == p:
            break
        p = p.parent
    for item in reversed(chain):
        if not os.path.lexists(item):
            continue
        st = os.lstat(item)
        if stat.S_ISLNK(st.st_mode) or _unsafe(st):
            raise PatcherError(f"VV5 Running reparse ancestor: {item}")
        if item != chain[0] and not stat.S_ISDIR(st.st_mode):
            raise PatcherError(f"VV5 Running non-directory ancestor: {item}")


def _read(path: Path) -> bytes:
    _safe_ancestors(path.parent)
    if not os.path.lexists(path):
        raise PatcherError(f"VV5 Running missing file: {path}")
    before = os.lstat(path)
    if stat.S_ISLNK(before.st_mode) or _unsafe(before) or not stat.S_ISREG(before.st_mode):
        raise PatcherError(f"VV5 Running unsafe file: {path}")
    fd = os.open(os.fspath(path), os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0))
    try:
        opened = os.fstat(fd)
        if opened.st_size != before.st_size or stat.S_IFMT(opened.st_mode) != stat.S_IFMT(before.st_mode):
            raise PatcherError(f"VV5 Running file identity changed: {path}")
        data = bytearray()
        while True:
            chunk = os.read(fd, 1024 * 1024)
            if not chunk:
                break
            data.extend(chunk)
        after = os.fstat(fd)
        if after.st_size != opened.st_size or (opened.st_ino and after.st_ino and opened.st_ino != after.st_ino):
            raise PatcherError(f"VV5 Running file changed while reading: {path}")
        return bytes(data)
    finally:
        os.close(fd)


def _state(path: Path) -> tuple[bool, bytes | None]:
    return (False, None) if not os.path.lexists(path) else (True, _read(path))


def _parent(destinations: list[Path]) -> Path:
    paths = [Path(os.path.abspath(os.fspath(p))) for p in destinations]
    if paths[0] == paths[1] or paths[0].parent != paths[1].parent:
        raise PatcherError("VV5 Running EXE and DLL must share one destination parent.")
    parent = paths[0].parent
    _safe_ancestors(parent)
    if not parent.is_dir():
        raise PatcherError("VV5 Running destination parent is unsafe.")
    return parent


def _write(path: Path, data: bytes) -> None:
    _safe_ancestors(path.parent)
    with open(path, "xb") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())


def _cleanup(path: Path) -> None:
    if not os.path.lexists(path):
        return
    st = os.lstat(path)
    if stat.S_ISLNK(st.st_mode) or _unsafe(st) or not stat.S_ISREG(st.st_mode):
        raise PatcherError(f"VV5 Running unsafe owned cleanup path: {path}")
    path.unlink()


def _restore(path: Path, pre: tuple[bool, bytes | None], published: bytes, backup: Path | None) -> bool:
    try:
        current = _state(path)
        if current == pre:
            return True
        if current[0] and current[1] != published:
            return False
        if not pre[0]:
            _cleanup(path)
            return not os.path.lexists(path)
        if backup is None or _read(backup) != pre[1]:
            return False
        stage = path.parent / f".{path.name}.vv5run-restore-{uuid.uuid4().hex}.stage"
        _write(stage, pre[1] or b"")
        os.replace(stage, path)
        return _state(path) == pre
    except (OSError, PatcherError):
        return False


def _report(parent: Path, operation: str, members: list[dict[str, object]], error: str) -> Path:
    report = parent / f".vv5run-recovery-{uuid.uuid4().hex}.json"
    tmp = report.with_suffix(".tmp")
    payload = {"schema_version": 1, "operation": operation, "destination_parent": str(parent), "members": members, "error": error}
    _write(tmp, (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    os.replace(tmp, report)
    return report


def _publish(operation: str, destinations: list[Path], pre: dict[Path, tuple[bool, bytes | None]], published: dict[Path, bytes], parent: Path) -> None:
    token = uuid.uuid4().hex
    stages = {p: parent / f".{p.name}.vv5run-{token}.stage" for p in destinations}
    backups = {p: parent / f".{p.name}.vv5run-{token}.backup" for p in destinations if pre[p][0]}
    if any(os.path.lexists(p) for p in (*stages.values(), *backups.values())):
        raise PatcherError("VV5 Running staging collision.")
    try:
        for p in destinations:
            _write(stages[p], published[p])
        for p, b in backups.items():
            _write(b, pre[p][1] or b"")
        for p in destinations:
            if _state(p) != pre[p] or _read(stages[p]) != published[p]:
                raise PatcherError("VV5 Running pre-replace race or stage mutation.")
        for p in destinations:
            os.replace(stages[p], p)
        if any(_state(p) != (True, published[p]) for p in destinations):
            raise PatcherError("VV5 Running pair postverify failed.")
    except Exception as exc:
        restored = {}
        for p in destinations:
            restored[p] = _restore(p, pre[p], published[p], backups.get(p))
        if all(restored.values()) and all(_state(p) == pre[p] for p in destinations):
            for p in (*stages.values(), *backups.values()):
                if os.path.lexists(p):
                    _cleanup(p)
            raise PatcherError(f"VV5 Running {operation} failed; pair restored") from exc
        members = [{"path": str(p), "pre_exists": pre[p][0], "pre_sha256": _sha(pre[p][1]) if pre[p][1] is not None else None, "published_sha256": _sha(published[p]), "backup": str(backups[p]) if p in backups else None, "stage": str(stages[p])} for p in destinations]
        report = _report(parent, operation, members, str(exc))
        raise PatcherError(f"VV5 Running {operation} unresolved; recovery retained at {report}") from exc
    for p in (*stages.values(), *backups.values()):
        if os.path.lexists(p):
            _cleanup(p)


def recover_atomic(report_path: Path) -> None:
    """Replay a retained VV5 pair report without consuming its evidence.

    The report is intentionally strict: only schema-1 reports produced by this
    module are accepted, both members must still be the published pair, and
    backups are copied to fresh sibling stages and retained until the complete
    pair verifies.  A failed replay leaves the report and backups intact.
    """
    report_path = Path(report_path)
    parent = report_path.parent
    _safe_ancestors(parent)
    raw = json.loads(_read(report_path).decode("utf-8"))
    if raw.get("schema_version") != 1 or raw.get("operation") not in {"install", "remove"}:
        raise PatcherError("VV5 Running recovery schema is unsupported.")
    members = raw.get("members")
    if not isinstance(members, list) or len(members) != 2:
        raise PatcherError("VV5 Running recovery member inventory is incomplete.")
    token = uuid.uuid4().hex
    stages: list[Path] = []
    try:
        for member in members:
            if not isinstance(member, dict):
                raise PatcherError("VV5 Running recovery member is malformed.")
            destination = Path(member["path"])
            backup_name = member.get("backup")
            if not backup_name:
                raise PatcherError("VV5 Running recovery backup is missing.")
            backup = Path(backup_name)
            if backup.parent != parent or destination.parent != parent:
                raise PatcherError("VV5 Running recovery path escapes its owned parent.")
            expected = member.get("pre_sha256")
            published = member.get("published_sha256")
            if not isinstance(expected, str) or not isinstance(published, str):
                raise PatcherError("VV5 Running recovery hashes are incomplete.")
            if not os.path.lexists(destination) or _sha(_read(destination)) != published:
                raise PatcherError("VV5 Running recovery destination precondition failed.")
            backup_bytes = _read(backup)
            if _sha(backup_bytes) != expected:
                raise PatcherError("VV5 Running recovery backup hash mismatch.")
            stage = parent / f".{destination.name}.vv5run-{token}.replay"
            _write(stage, backup_bytes)
            stages.append(stage)
        # No replacement occurs until both backups and both destinations pass preflight.
        for member, stage in zip(members, stages):
            destination = Path(member["path"])
            os.replace(stage, destination)
        for member in members:
            destination = Path(member["path"])
            if _sha(_read(destination)) != member["pre_sha256"]:
                raise PatcherError("VV5 Running recovery postverify failed.")
    except Exception:
        for stage in stages:
            if os.path.lexists(stage):
                # Keep any failed replay material for a later operator review.
                pass
        raise
    for member in members:
        backup = Path(member["backup"])
        if os.path.lexists(backup):
            _cleanup(backup)
    _cleanup(report_path)


def install_atomic(source: Path, destination: Path, mode: str, *, companion_source: Path | None = None, companion_destination: Path | None = None) -> None:
    if companion_source is None or companion_destination is None:
        raise PatcherError("VV5 Running companion is mandatory.")
    destinations = [Path(destination), Path(companion_destination)]
    parent = _parent(destinations)
    source_bytes = _read(source)
    candidate, _ = render_vv5_individual_running_parent(source, mode)
    dll = _read(companion_source)
    if len(dll) != DLL_SIZE or _sha(dll) != DLL_SHA256:
        raise PatcherError("VV5 Running companion hash mismatch.")
    pre = {p: _state(p) for p in destinations}
    parent_dll = _read(ROOT / "data" / "candidates" / DLL_NAME)
    expected = {destinations[0]: source_bytes, destinations[1]: parent_dll}
    for p in destinations:
        if pre[p][0] and pre[p][1] != expected[p]:
            raise PatcherError("VV5 Running destination preimage mismatch.")
    _publish("install", destinations, pre, {destinations[0]: bytes(candidate), destinations[1]: dll}, parent)


def remove_atomic(destination: Path, mode: str, *, companion_destination: Path | None = None, companion_restore_source: Path | None = None) -> None:
    if companion_destination is None or companion_restore_source is None:
        raise PatcherError("VV5 Running removal companion arguments are mandatory.")
    destinations = [Path(destination), Path(companion_destination)]
    parent = _parent(destinations)
    candidate = _read(destination)
    restored_exe = bytearray(candidate)
    remove_vv5_individual_running_parent(restored_exe, mode)
    parent_dll = _read(companion_restore_source)
    current_dll = _read(companion_destination)
    if _sha(current_dll) != DLL_SHA256 or _sha(parent_dll) != DLL_SHA256:
        raise PatcherError("VV5 Running removal companion identity mismatch.")
    pre = {destinations[0]: (True, candidate), destinations[1]: (True, current_dll)}
    _publish("remove", destinations, pre, {destinations[0]: bytes(restored_exe), destinations[1]: parent_dll}, parent)
