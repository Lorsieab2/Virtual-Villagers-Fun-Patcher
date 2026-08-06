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
from vv3_individual_full_mastery import (
    _transaction as _strict_pair_transaction,
    recover_atomic as _strict_recover_atomic,
)

ROOT = Path(__file__).resolve().parents[1]
DLL_SHA256 = "29927CECB448B64944E18E2BA11893DC84C91B39241FBB2549FC2A464E0BE2ED"
DLL_SIZE = 298496
DLL_NAME = "VVFP VV5 Full Mastery Candidate.dll"
VV5_FEATURE_OWNER = "vv5_individual_grant_running_candidate"
VV5_MODE = "collection_progression"
VV5_PARENT_EXE_SHA256 = "857E22D7C361B802508BF789C3CC486E42E76021F5AA579BB1D16CC6E0D017A0"
VV5_CANDIDATE_EXE_SHA256 = "1E3FD6CE44E906BD8DDD7C937D68AB74671D8F197BC1D767A2B0622F1A0F7907"
VV5_PARENT_DLL_SHA256 = DLL_SHA256
VV5_CANDIDATE_DLL_SHA256 = DLL_SHA256


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
        if (opened.st_size != before.st_size or
                stat.S_IFMT(opened.st_mode) != stat.S_IFMT(before.st_mode) or
                (before.st_ino and opened.st_ino and before.st_ino != opened.st_ino) or
                (before.st_dev and opened.st_dev and before.st_dev != opened.st_dev)):
            raise PatcherError(f"VV5 Running file identity changed: {path}")
        data = bytearray()
        while True:
            chunk = os.read(fd, 1024 * 1024)
            if not chunk:
                break
            data.extend(chunk)
        after = os.fstat(fd)
        if (after.st_size != opened.st_size or
                (opened.st_ino and after.st_ino and opened.st_ino != after.st_ino) or
                (opened.st_dev and after.st_dev and opened.st_dev != after.st_dev)):
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
    _safe_ancestors(path.parent)


def _cleanup(path: Path) -> None:
    if not os.path.lexists(path):
        return
    st = os.lstat(path)
    if stat.S_ISLNK(st.st_mode) or _unsafe(st) or not stat.S_ISREG(st.st_mode):
        raise PatcherError(f"VV5 Running unsafe owned cleanup path: {path}")
    before = _read(path)
    after = os.lstat(path)
    if after.st_size != len(before) or stat.S_ISLNK(after.st_mode) or _unsafe(after):
        raise PatcherError(f"VV5 Running owned cleanup identity changed: {path}")
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


def _relative(root: Path, path: Path | None) -> str | None:
    if path is None:
        return None
    try:
        rel = Path(os.path.abspath(os.fspath(path))).relative_to(Path(os.path.abspath(os.fspath(root))))
    except ValueError as exc:
        raise PatcherError("VV5 Running recovery path escapes root") from exc
    if rel.is_absolute() or not rel.parts or ".." in rel.parts:
        raise PatcherError("VV5 Running recovery path is unsafe")
    return rel.as_posix()


def _inventory(root: Path, path: Path | None) -> dict[str, object] | None:
    if path is None or not os.path.lexists(path):
        return None
    data = _read(path); st = os.lstat(path)
    return {"path": _relative(root, path), "type": "regular_file", "size": len(data), "sha256": _sha(data), "st_dev": int(getattr(st, "st_dev", 0)), "st_ino": int(getattr(st, "st_ino", 0))}


def _validate_report(payload: dict[str, object], root: Path) -> None:
    required = {"schema_version", "operation", "recovery_root", "destination_parent", "initial_precondition", "replay_guard", "members", "ownership_inventory", "failure_diagnostic"}
    if not isinstance(payload, dict) or set(payload) != required or payload.get("schema_version") != 2 or payload.get("operation") not in {"install_new", "install_existing", "removal"}:
        raise PatcherError("VV5 Running recovery schema is unsupported or ambiguous")
    if payload["recovery_root"] != "." or payload["destination_parent"] != ".":
        raise PatcherError("VV5 Running recovery root contract is invalid")
    initial = payload["initial_precondition"]
    if not isinstance(initial, dict) or set(initial) != {"kind", "members"} or initial["kind"] not in {"absent", "pair"}:
        raise PatcherError("VV5 Running recovery initial precondition is invalid")
    if payload["operation"] == "install_new" and initial["kind"] != "absent":
        raise PatcherError("VV5 install_new requires absent precondition")
    if payload["operation"] != "install_new" and initial["kind"] != "pair":
        raise PatcherError("VV5 recovery operation requires pair precondition")
    keys = {"destination_relative", "destination_type", "pre_exists", "pre_sha256", "pre_size", "published_sha256", "published_size", "backup_relative", "stage_relative", "backup_inventory", "stage_inventory"}
    seen: set[str] = set()
    members = payload["members"]
    if not isinstance(members, list) or len(members) != 2:
        raise PatcherError("VV5 Running recovery requires two members")
    for member in members:
        if not isinstance(member, dict) or set(member) != keys or member["destination_type"] != "regular_file":
            raise PatcherError("VV5 Running recovery member schema is invalid")
        rel = Path(str(member["destination_relative"])); key = rel.as_posix().casefold()
        if rel.is_absolute() or not rel.parts or ".." in rel.parts or key in seen:
            raise PatcherError("VV5 Running recovery destination path is unsafe")
        seen.add(key)
        for field in ("backup_relative", "stage_relative"):
            if member[field] is not None:
                p = Path(str(member[field]))
                if p.is_absolute() or ".." in p.parts or not p.parts:
                    raise PatcherError("VV5 Running recovery owned path is unsafe")
    if not isinstance(payload["ownership_inventory"], list):
        raise PatcherError("VV5 Running recovery ownership inventory is invalid")


def _report(parent: Path, operation: str, members: list[dict[str, object]], error: str) -> Path:
    report = parent / f".vv5run-recovery-{uuid.uuid4().hex}.json"
    tmp = report.with_suffix(".tmp")
    op = "removal" if operation == "remove" else ("install_existing" if any(m["pre_exists"] for m in members) else "install_new")
    records = []
    for m in members:
        records.append({**m, "destination_relative": _relative(parent, Path(m["path"])), "destination_type": "regular_file", "backup_relative": _relative(parent, Path(m["backup"]) if m.get("backup") else None), "stage_relative": _relative(parent, Path(m["stage"]) if m.get("stage") else None), "backup_inventory": _inventory(parent, Path(m["backup"]) if m.get("backup") else None), "stage_inventory": _inventory(parent, Path(m["stage"]) if m.get("stage") else None)})
        for k in ("path", "backup", "stage"):
            records[-1].pop(k, None)
    payload = {"schema_version": 2, "operation": op, "recovery_root": ".", "destination_parent": ".", "initial_precondition": {"kind": "absent" if op == "install_new" else "pair", "members": [{"path": r["destination_relative"], "exists": r["pre_exists"], "sha256": r["pre_sha256"], "size": r["pre_size"]} for r in records]}, "replay_guard": "published_or_initial", "members": records, "ownership_inventory": [v for r in records for v in (r["backup_inventory"], r["stage_inventory"]) if v is not None], "failure_diagnostic": error}
    _validate_report(payload, parent)
    _write(tmp, (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    os.replace(tmp, report)
    _validate_report(json.loads(_read(report).decode("utf-8")), parent)
    return report


def _publish(operation: str, destinations: list[Path], pre: dict[Path, tuple[bool, bytes | None]], published: dict[Path, bytes], parent: Path, *, mode: str = VV5_MODE) -> None:
    if mode != VV5_MODE:
        raise PatcherError("VV5 Running supports Collection Progression only.")
    # Reuse the independently hardened schema-v2 pair transaction.  This
    # keeps VV5 recovery fail-closed on complete ownership inventories,
    # no-follow/reparse checks, immutable preconditions, durable retry
    # evidence, and exact pair verification rather than maintaining a weaker
    # second implementation.
    expected_preimage = {p: (pre[p][1] or b"") for p in destinations if pre[p][0]}
    _strict_pair_transaction(
        "remove" if operation == "remove" else "install",
        destinations,
        pre,
        published,
        expected_preimage=expected_preimage,
        parent=parent,
        recovery_prefix=".vv5run",
        recovery_metadata={
            "feature_owner": VV5_FEATURE_OWNER,
            "mode": VV5_MODE,
            "parent_sha256": VV5_PARENT_EXE_SHA256,
            "candidate_sha256": VV5_CANDIDATE_EXE_SHA256,
        },
    )
    return

    # Legacy implementation retained below only as unreachable source
    # context; production publication is the strict transaction above.
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
        members = [{"path": str(p), "pre_exists": pre[p][0], "pre_sha256": _sha(pre[p][1]) if pre[p][1] is not None else None, "pre_size": len(pre[p][1]) if pre[p][1] is not None else 0, "published_sha256": _sha(published[p]), "published_size": len(published[p]), "backup": str(backups[p]) if p in backups else None, "stage": str(stages[p])} for p in destinations]
        report = _report(parent, operation, members, str(exc))
        raise PatcherError(f"VV5 Running {operation} unresolved; recovery retained at {report}") from exc
    for p in (*stages.values(), *backups.values()):
        if os.path.lexists(p):
            _cleanup(p)


def recover_atomic(report_path: Path, mode: str = VV5_MODE) -> None:
    """Replay a retained VV5 pair report without consuming its evidence.

    The report is intentionally strict: only schema-2 reports produced by this
    module are accepted, both members must still be the published pair, and
    backups are copied to fresh sibling stages and retained until the complete
    pair verifies.  A failed replay leaves the report and backups intact.
    """
    if mode != VV5_MODE:
        raise PatcherError("VV5 Running supports Collection Progression only.")
    report = Path(report_path)
    if not report.name.startswith(".vv5run-recovery-"):
        raise PatcherError("VV5 Running recovery report owner is invalid.")
    _safe_ancestors(report.parent)
    report_bytes = _read(report)
    report_sha256 = _sha(report_bytes)
    raw = json.loads(report_bytes.decode("utf-8"))
    if any(raw.get(k) != v for k, v in {
        "feature_owner": VV5_FEATURE_OWNER,
        "mode": VV5_MODE,
        "parent_sha256": VV5_PARENT_EXE_SHA256,
        "candidate_sha256": VV5_CANDIDATE_EXE_SHA256,
    }.items()):
        raise PatcherError("VV5 Running recovery report identity mismatch.")
    return _strict_recover_atomic(
        report,
        recovery_prefix=".vv5run",
        required_metadata={
            "feature_owner": VV5_FEATURE_OWNER,
            "mode": VV5_MODE,
            "parent_sha256": VV5_PARENT_EXE_SHA256,
            "candidate_sha256": VV5_CANDIDATE_EXE_SHA256,
        },
        expected_report_sha256=report_sha256,
    )

    report_path = Path(report_path)
    parent = report_path.parent
    _safe_ancestors(parent)
    raw = json.loads(_read(report_path).decode("utf-8"))
    _validate_report(raw, parent)
    members = raw["members"]
    token = uuid.uuid4().hex
    stages: list[tuple[dict[str, object], Path, Path]] = []
    try:
        for member in members:
            if not isinstance(member, dict):
                raise PatcherError("VV5 Running recovery member is malformed.")
            destination = parent / str(member["destination_relative"])
            backup_name = member.get("backup_relative")
            if not backup_name:
                if member["pre_exists"]:
                    raise PatcherError("VV5 Running recovery backup is missing.")
                backup = None
            else:
                backup = parent / str(backup_name)
            if destination.parent != parent or (backup is not None and backup.parent != parent):
                raise PatcherError("VV5 Running recovery path escapes its owned parent.")
            expected = member.get("pre_sha256")
            published = member.get("published_sha256")
            if not isinstance(expected, str) or not isinstance(published, str):
                raise PatcherError("VV5 Running recovery hashes are incomplete.")
            if not os.path.lexists(destination) and member["pre_exists"]:
                raise PatcherError("VV5 Running recovery destination unexpectedly absent.")
            if os.path.lexists(destination) and _sha(_read(destination)) not in {published, expected}:
                raise PatcherError("VV5 Running recovery destination precondition failed.")
            backup_bytes = _read(backup) if backup is not None else b""
            if backup is not None and (_sha(backup_bytes) != expected or len(backup_bytes) != member["pre_size"]):
                raise PatcherError("VV5 Running recovery backup hash/size mismatch.")
            if backup is None and member["pre_exists"]:
                raise PatcherError("VV5 Running recovery backup is required.")
            stage = parent / f".{destination.name}.vv5run-{token}.replay"
            if backup is not None:
                _write(stage, backup_bytes)
                stages.append((member, destination, stage))
        # No replacement occurs until both backups and both destinations pass preflight.
        for member, destination, stage in stages:
            if _sha(_read(stage)) != member["pre_sha256"]:
                raise PatcherError("VV5 Running replay stage changed.")
            os.replace(stage, destination)
        for member in members:
            destination = parent / str(member["destination_relative"])
            if member["pre_exists"] and _sha(_read(destination)) != member["pre_sha256"]:
                raise PatcherError("VV5 Running recovery postverify failed.")
            if not member["pre_exists"] and os.path.lexists(destination):
                _cleanup(destination)
    except Exception:
        for _member, _destination, stage in stages:
            if os.path.lexists(stage):
                # Keep any failed replay material for a later operator review.
                pass
        raise
    for member in members:
        backup = parent / str(member["backup_relative"]) if member["backup_relative"] else None
        if backup is not None and os.path.lexists(backup):
            _cleanup(backup)
    _cleanup(report_path)


def install_atomic(source: Path, destination: Path, mode: str, *, companion_source: Path | None = None, companion_destination: Path | None = None) -> None:
    if mode != VV5_MODE:
        raise PatcherError("VV5 Running supports Collection Progression only.")
    if companion_source is None or companion_destination is None:
        raise PatcherError("VV5 Running companion is mandatory.")
    destinations = [Path(destination), Path(companion_destination)]
    parent = _parent(destinations)
    # Read each authenticated input once, then carry those bytes through
    # rendering/publication so a source race cannot be hidden by a reread.
    source_bytes = _read(source)
    if _sha(source_bytes) != VV5_PARENT_EXE_SHA256:
        raise PatcherError("VV5 Running source EXE identity mismatch.")
    dll = _read(companion_source)
    if len(dll) != DLL_SIZE or _sha(dll) != DLL_SHA256:
        raise PatcherError("VV5 Running companion hash mismatch.")
    parent_dll = _read(ROOT / "data" / "candidates" / DLL_NAME)
    if len(parent_dll) != DLL_SIZE or _sha(parent_dll) != DLL_SHA256:
        raise PatcherError("VV5 Running parent DLL identity mismatch.")
    candidate, _ = render_vv5_individual_running_parent(source_bytes, mode)
    if len(candidate) != 0xF6000 or _sha(bytes(candidate)) != VV5_CANDIDATE_EXE_SHA256:
        raise PatcherError("VV5 Running candidate EXE identity mismatch.")
    pre = {p: _state(p) for p in destinations}
    expected = {destinations[0]: source_bytes, destinations[1]: parent_dll}
    for p in destinations:
        if pre[p][0] and pre[p][1] != expected[p]:
            raise PatcherError("VV5 Running destination preimage mismatch.")
    _publish("install", destinations, pre, {destinations[0]: bytes(candidate), destinations[1]: dll}, parent, mode=mode)


def remove_atomic(destination: Path, mode: str, *, companion_destination: Path | None = None, companion_restore_source: Path | None = None) -> None:
    if mode != VV5_MODE:
        raise PatcherError("VV5 Running supports Collection Progression only.")
    if companion_destination is None or companion_restore_source is None:
        raise PatcherError("VV5 Running removal companion arguments are mandatory.")
    destinations = [Path(destination), Path(companion_destination)]
    parent = _parent(destinations)
    candidate = _read(destination)
    if len(candidate) != 0xF6000 or _sha(candidate) != VV5_CANDIDATE_EXE_SHA256:
        raise PatcherError("VV5 Running removal EXE identity mismatch.")
    restored_exe = bytearray(candidate)
    remove_vv5_individual_running_parent(restored_exe, mode)
    parent_dll = _read(companion_restore_source)
    current_dll = _read(companion_destination)
    if len(current_dll) != DLL_SIZE or len(parent_dll) != DLL_SIZE or _sha(current_dll) != DLL_SHA256 or _sha(parent_dll) != DLL_SHA256:
        raise PatcherError("VV5 Running removal companion identity mismatch.")
    pre = {destinations[0]: (True, candidate), destinations[1]: (True, current_dll)}
    if _sha(bytes(restored_exe)) != VV5_PARENT_EXE_SHA256:
        raise PatcherError("VV5 Running removal did not restore the exact parent EXE.")
    _publish("remove", destinations, pre, {destinations[0]: bytes(restored_exe), destinations[1]: parent_dll}, parent, mode=mode)
