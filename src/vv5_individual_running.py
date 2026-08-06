"""Explicit disabled VV5 Grant Running EXE+DLL publication transaction.

The candidate is not public.  These entry points are for independent audit
and guarded internal rendering only; they never broaden catalog enablement.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import struct
import uuid
from pathlib import Path

from vv_fun_patcher import PatcherError, render_vv5_individual_running_parent, remove_vv5_individual_running_parent
from vv3_individual_full_mastery import (
    _transaction as _strict_pair_transaction,
    recover_atomic as _strict_recover_atomic,
    _delete_file_by_handle as _strict_delete_file_by_handle,
    _move_noreplace as _strict_move_noreplace,
    _quarantine_delete as _strict_quarantine_delete,
    _inventory_entry as _strict_inventory_entry,
    _publish_exclusive as _strict_publish_exclusive,
)

ROOT = Path(__file__).resolve().parents[1]
DLL_SHA256 = "29927CECB448B64944E18E2BA11893DC84C91B39241FBB2549FC2A464E0BE2ED"
DLL_SIZE = 298496
DLL_NAME = "VVFP VV5 Full Mastery Candidate.dll"
VV5_FEATURE_OWNER = "vv5_individual_grant_running_candidate"
VV5_MODE = "collection_progression"
VV5_EXE_BASENAME = "Virtual Villagers - New Believers - Modded.exe"
VV5_PARENT_EXE_SHA256 = "857E22D7C361B802508BF789C3CC486E42E76021F5AA579BB1D16CC6E0D017A0"
VV5_CANDIDATE_EXE_SHA256 = "1E3FD6CE44E906BD8DDD7C937D68AB74671D8F197BC1D767A2B0622F1A0F7907"
VV5_PARENT_DLL_SHA256 = DLL_SHA256
VV5_CANDIDATE_DLL_SHA256 = DLL_SHA256
ISSUANCE_SCHEMA_VERSION = 2
ISSUANCE_REGISTRY_NAME = ".vv5run-issuance"
AUTHORITY_NAME = ".authority"
AUTHORITY_SCHEMA_VERSION = 1


def _require_windows_identity_atomic() -> None:
    if os.name != "nt" or struct.calcsize("P") != 8:
        raise PatcherError("VV5 Running publication/recovery identity-atomic operations are certified only on 64-bit Windows.")


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


def _validate_recovery_ancestors(path: Path) -> None:
    """Validate directory ancestors before touching an untrusted report."""
    if os.name != "nt" or struct.calcsize("P") != 8:
        raise PatcherError("VV5 Running recovery identity-atomic paths are certified only on 64-bit Windows.")
    current = Path(os.path.abspath(os.fspath(path))).parent
    chain: list[Path] = []
    while True:
        chain.append(current)
        if current.parent == current:
            break
        current = current.parent
    for item in reversed(chain):
        if not os.path.lexists(item):
            raise PatcherError(f"VV5 Running recovery ancestor is missing: {item}")
        st = os.lstat(item)
        if stat.S_ISLNK(st.st_mode) or _unsafe(st):
            raise PatcherError(f"VV5 Running recovery reparse ancestor: {item}")
        if not stat.S_ISDIR(st.st_mode):
            raise PatcherError(f"VV5 Running recovery non-directory ancestor: {item}")


def _validate_recovery_siblings(parent: Path, *, selected: str | None = None) -> None:
    """Reject unknown VV5/chain residue before a report is used or mutated."""
    canonical_re = re.compile(r"\.vv5run-recovery-[0-9a-f]{32}\.json")
    emergency_re = re.compile(r"\.vv5run-emergency-[0-9a-f]{32}\.json")
    successor_re = re.compile(r"\.vv5run-recovery-[0-9a-f]{32}\.v[0-9a-f]{32}\.json")
    pointer_re = re.compile(r"\.vv5run-(?:recovery|emergency)-[0-9a-f]{32}\.json\.pointer")
    cleanup_re = re.compile(r"\.vv5run-cleanup-[0-9a-f]{32}\.json")
    known_reports: set[str] = set()
    chain_entries: list[tuple[str, Path, os.stat_result]] = []
    captured: dict[str, dict[str, object]] = {}
    def capture_file(path: Path, label: str) -> dict[str, object]:
        record = _inventory(parent, path)
        if record is None:
            raise PatcherError(f"VV5 Running recovery sibling disappeared: {label}")
        return record
    entries = list(os.scandir(parent))
    for entry in entries:
        name = entry.name
        if name.startswith(".vv5run-"):
            path = Path(entry.path)
            st = os.lstat(path)
            if name == ISSUANCE_REGISTRY_NAME or re.fullmatch(r"\.vv5run-recovery-[0-9a-f]{32}", name):
                if stat.S_ISLNK(st.st_mode) or _unsafe(st) or not stat.S_ISDIR(st.st_mode):
                    raise PatcherError(f"VV5 Running recovery sibling is unsafe: {name}")
                captured[name] = {"type": "directory", "size": int(st.st_size), "sha256": None, "st_dev": int(st.st_dev), "st_ino": int(st.st_ino)}
                continue
            if canonical_re.fullmatch(name) or emergency_re.fullmatch(name) or successor_re.fullmatch(name) or pointer_re.fullmatch(name) or cleanup_re.fullmatch(name):
                if stat.S_ISLNK(st.st_mode) or _unsafe(st) or not stat.S_ISREG(st.st_mode):
                    raise PatcherError(f"VV5 Running recovery sibling is unsafe: {name}")
                captured[name] = capture_file(path, name)
                if canonical_re.fullmatch(name) or emergency_re.fullmatch(name):
                    known_reports.add(name)
                continue
            raise PatcherError(f"VV5 Running recovery contains unknown .vv5run residue: {name}")
        if name.startswith(".chain-"):
            path = Path(entry.path)
            st = os.lstat(path)
            if stat.S_ISLNK(st.st_mode) or _unsafe(st) or not stat.S_ISREG(st.st_mode) or not name.endswith(".json"):
                raise PatcherError(f"VV5 Running recovery chain member is unsafe: {name}")
            chain_entries.append((name, path, st))
            captured[name] = capture_file(path, name)
    for name, _path, _st in chain_entries:
        target = name[len(".chain-"):-len(".json")]
        if target not in known_reports:
            raise PatcherError(f"VV5 Running recovery chain manifest is orphaned or foreign: {name}")
    if selected is not None and selected not in known_reports:
        raise PatcherError("VV5 Running selected recovery report is not an accepted chain member.")
    # Recapture the complete hidden recovery namespace, not just the names we
    # happened to select.  This closes the scan-to-use interval for a foreign
    # child that is added, removed, or renamed between the two scans.
    with os.scandir(parent) as final_entries:
        final_names: set[str] = set()
        for entry in final_entries:
            name = entry.name
            if not (name.startswith(".vv5run-") or name.startswith(".chain-")):
                continue
            final_names.add(name)
            if name not in captured:
                raise PatcherError(f"VV5 Running recovery sibling membership changed before use: {name}")
            path = Path(entry.path)
            st = os.lstat(path)
            if stat.S_ISLNK(st.st_mode) or _unsafe(st):
                raise PatcherError(f"VV5 Running recovery sibling became unsafe: {name}")
            if stat.S_ISDIR(st.st_mode):
                final_record = {"type": "directory", "size": int(st.st_size), "sha256": None, "st_dev": int(st.st_dev), "st_ino": int(st.st_ino)}
            elif stat.S_ISREG(st.st_mode):
                final_record = _inventory(parent, path)
            else:
                raise PatcherError(f"VV5 Running recovery sibling has unsafe type: {name}")
            if final_record != captured[name]:
                raise PatcherError(f"VV5 Running recovery sibling changed before use: {name}")
        if final_names != set(captured):
            raise PatcherError("VV5 Running recovery sibling membership changed before use.")


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
    _require_windows_identity_atomic()
    _safe_ancestors(path.parent)
    with open(path, "xb") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    _safe_ancestors(path.parent)


def _cleanup(path: Path, *, expected: dict[str, object] | None = None) -> None:
    _require_windows_identity_atomic()
    if not os.path.lexists(path):
        if expected is not None:
            raise PatcherError(f"VV5 Running owned cleanup path disappeared: {path}")
        return
    actual = _inventory(path.parent, path)
    if actual is None:
        raise PatcherError(f"VV5 Running owned cleanup path disappeared: {path}")
    if expected is not None and any(actual.get(key) != expected.get(key) for key in ("type", "size", "sha256", "st_dev", "st_ino")):
        raise PatcherError(f"VV5 Running owned cleanup identity changed: {path}")
    st = os.lstat(path)
    if stat.S_ISLNK(st.st_mode) or _unsafe(st) or not stat.S_ISREG(st.st_mode):
        raise PatcherError(f"VV5 Running unsafe owned cleanup path: {path}")
    after = os.lstat(path)
    if after.st_size != actual["size"] or stat.S_ISLNK(after.st_mode) or _unsafe(after):
        raise PatcherError(f"VV5 Running owned cleanup identity changed: {path}")
    _strict_delete_file_by_handle(path, actual)
    if os.path.lexists(path):
        raise PatcherError(f"VV5 Running owned cleanup path remained after identity-bound deletion: {path}")


def _restore(path: Path, pre: tuple[bool, bytes | None], published: bytes, backup: Path | None) -> bool:
    _require_windows_identity_atomic()
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
    before = os.lstat(path)
    if stat.S_ISLNK(before.st_mode) or _unsafe(before) or not stat.S_ISREG(before.st_mode):
        raise PatcherError(f"VV5 Running unsafe inventory member: {path}")
    data = _read(path)
    st = os.lstat(path)
    if (int(st.st_dev), int(st.st_ino), int(st.st_size), stat.S_IFMT(st.st_mode)) != (int(before.st_dev), int(before.st_ino), int(before.st_size), stat.S_IFMT(before.st_mode)):
        raise PatcherError(f"VV5 Running inventory member changed during capture: {path}")
    return {"path": _relative(root, path), "type": "regular_file", "size": len(data), "sha256": _sha(data), "st_dev": int(getattr(st, "st_dev", 0)), "st_ino": int(getattr(st, "st_ino", 0))}


def _identity(path: Path) -> dict[str, int]:
    st = os.lstat(path)
    return {"st_dev": int(getattr(st, "st_dev", 0)), "st_ino": int(getattr(st, "st_ino", 0))}


def _registry_members(registry: Path) -> dict[str, dict[str, object]]:
    """Capture the complete direct-child registry inventory without following links."""
    if not os.path.lexists(registry):
        raise PatcherError("VV5 Running issuance registry is missing.")
    st = os.lstat(registry)
    if stat.S_ISLNK(st.st_mode) or _unsafe(st) or not stat.S_ISDIR(st.st_mode):
        raise PatcherError("VV5 Running issuance registry is unsafe.")
    start_identity = (int(st.st_dev), int(st.st_ino), int(st.st_size))
    members: dict[str, dict[str, object]] = {}
    with os.scandir(registry) as entries:
        for entry in entries:
            child = Path(entry.path)
            if child.parent != registry or entry.name in {".", ".."} or "/" in entry.name or "\\" in entry.name:
                raise PatcherError("VV5 Running issuance registry child path is unsafe.")
            child_st = os.lstat(child)
            if stat.S_ISLNK(child_st.st_mode) or _unsafe(child_st) or not stat.S_ISREG(child_st.st_mode):
                raise PatcherError("VV5 Running issuance registry contains an unsafe child.")
            record = _inventory(registry.parent, child)
            if record is None:
                raise PatcherError("VV5 Running issuance registry child disappeared.")
            members[entry.name] = record
    end = os.lstat(registry)
    if stat.S_ISLNK(end.st_mode) or _unsafe(end) or not stat.S_ISDIR(end.st_mode) or (int(end.st_dev), int(end.st_ino), int(end.st_size)) != start_identity:
        raise PatcherError("VV5 Running issuance registry changed during enumeration.")
    with os.scandir(registry) as entries:
        end_names = set()
        for entry in entries:
            end_names.add(entry.name)
            end_st = os.lstat(entry.path)
            if stat.S_ISLNK(end_st.st_mode) or _unsafe(end_st) or not stat.S_ISREG(end_st.st_mode):
                raise PatcherError("VV5 Running issuance registry member became unsafe during enumeration.")
    if end_names != set(members):
        raise PatcherError("VV5 Running issuance registry membership changed during enumeration.")
    final_registry = os.lstat(registry)
    if stat.S_ISLNK(final_registry.st_mode) or _unsafe(final_registry) or not stat.S_ISDIR(final_registry.st_mode) or (int(final_registry.st_dev), int(final_registry.st_ino), int(final_registry.st_size)) != start_identity:
        raise PatcherError("VV5 Running issuance registry changed during final recapture.")
    for name, captured in members.items():
        final = _inventory(registry.parent, registry / name)
        if final != captured:
            raise PatcherError("VV5 Running issuance registry member changed during final recapture.")
    return members


def _assert_registry_members(
    registry: Path,
    registry_identity: dict[str, int],
    expected: dict[str, dict[str, object]],
) -> None:
    """Require the exact owned registry set and identities before a checkpoint."""
    if _identity(registry) != registry_identity:
        raise PatcherError("VV5 Running issuance registry identity changed.")
    actual = _registry_members(registry)
    if set(actual) != set(expected):
        raise PatcherError("VV5 Running issuance registry contains foreign or concurrent material.")
    for name, record in expected.items():
        if actual.get(name) != record:
            raise PatcherError("VV5 Running issuance registry member changed.")


def _rebase_registry_record(registry: Path, path: Path, record: dict[str, object]) -> dict[str, object]:
    """Normalize a registry-relative helper record to its parent-root path."""
    rebased = dict(record)
    rebased["path"] = _relative(registry.parent, path)
    return rebased


def _canonical(path: Path) -> str:
    return os.path.normcase(os.path.abspath(os.fspath(path)))


def _registry(parent: Path) -> tuple[Path, dict[str, int], bool]:
    """Return the fixed destination-parent-owned issuance registry."""
    _require_windows_identity_atomic()
    _safe_ancestors(parent)
    registry = parent / ISSUANCE_REGISTRY_NAME
    created = False
    if os.path.lexists(registry):
        st = os.lstat(registry)
        if stat.S_ISLNK(st.st_mode) or _unsafe(st) or not stat.S_ISDIR(st.st_mode):
            raise PatcherError("VV5 Running issuance registry is unsafe.")
    else:
        registry.mkdir()
        created = True
        _safe_ancestors(parent)
    record = _strict_inventory_entry(parent, registry)
    if record.get("type") != "directory":
        raise PatcherError("VV5 Running issuance registry is unsafe.")
    return registry, _identity(registry), created


def _cleanup_registry(registry: Path, expected: dict[str, int]) -> None:
    _require_windows_identity_atomic()
    if not os.path.lexists(registry):
        raise PatcherError("VV5 Running issuance registry disappeared before cleanup.")
    st = os.lstat(registry)
    if stat.S_ISLNK(st.st_mode) or _unsafe(st) or not stat.S_ISDIR(st.st_mode):
        raise PatcherError("VV5 Running issuance registry identity changed.")
    if _identity(registry) != expected:
        raise PatcherError("VV5 Running issuance registry was substituted.")
    members = _registry_members(registry)
    if members:
        raise PatcherError("VV5 Running issuance registry is nonempty or contains foreign material.")
    record = _strict_inventory_entry(registry.parent, registry)
    before_identity = _identity(registry)
    before_members = _registry_members(registry)
    if before_identity != expected or before_members:
        raise PatcherError("VV5 Running issuance registry changed before directory removal.")
    _strict_quarantine_delete(registry, record, directory=True)
    if os.path.lexists(registry):
        raise PatcherError("VV5 Running issuance registry remained after directory removal.")


def _authority_path(registry: Path) -> Path:
    return registry / AUTHORITY_NAME


def _ensure_authority(registry: Path, registry_identity: dict[str, int], created: bool) -> tuple[Path, str, dict[str, object]]:
    """Create or validate the per-install authority secret before publication."""
    path = _authority_path(registry)
    if os.path.lexists(path):
        before = _inventory(registry.parent, path)
        if before is None:
            raise PatcherError("VV5 Running issuance authority disappeared.")
        raw = json.loads(_read(path).decode("utf-8"))
        if (
            not isinstance(raw, dict)
            or set(raw) != {"schema_version", "kind", "feature_owner", "mode", "token", "registry_identity"}
            or raw.get("schema_version") != AUTHORITY_SCHEMA_VERSION
            or raw.get("kind") != "vv5_running_authority"
            or raw.get("feature_owner") != VV5_FEATURE_OWNER
            or raw.get("mode") != VV5_MODE
            or not isinstance(raw.get("token"), str)
            or not re.fullmatch(r"[0-9a-f]{64}", raw["token"])
            or raw.get("registry_identity") != registry_identity
        ):
            raise PatcherError("VV5 Running issuance authority is malformed or bound to another registry.")
        record = _inventory(registry.parent, path)
        record_final = _inventory(registry.parent, path)
        if record != before or record_final != before or _identity(registry) != registry_identity:
            raise PatcherError("VV5 Running issuance authority changed during discovery.")
        return path, raw["token"], {"record": record_final, "token": raw["token"], "registry_identity": registry_identity, "created": False}
    if not created:
        raise PatcherError("VV5 Running issuance authority is missing from an existing registry.")
    token = (uuid.uuid4().hex + uuid.uuid4().hex)
    payload = {
        "schema_version": AUTHORITY_SCHEMA_VERSION,
        "kind": "vv5_running_authority",
        "feature_owner": VV5_FEATURE_OWNER,
        "mode": VV5_MODE,
        "token": token,
        "registry_identity": registry_identity,
    }
    _write_issuance(path, payload)
    record = _inventory(registry.parent, path)
    if record is None:
        raise PatcherError("VV5 Running issuance authority identity could not be captured.")
    record_final = _inventory(registry.parent, path)
    if record_final != record or _identity(registry) != registry_identity:
        raise PatcherError("VV5 Running issuance authority changed during creation.")
    return path, token, {"record": record_final, "token": token, "registry_identity": registry_identity, "created": True}


def _quarantine_owned(
    path: Path,
    expected: dict[str, object],
    *,
    owner_parent: Path,
    tombstone_name: str | None = None,
    preserved_name: str | None = None,
    progress=None,
) -> tuple[Path, dict[str, object], Path]:
    """Move an owned registry member outside the registry without overwriting."""
    _require_windows_identity_atomic()
    actual = _inventory(path.parent, path)
    if actual is None or any(actual.get(key) != expected.get(key) for key in ("type", "size", "sha256", "st_dev", "st_ino")):
        raise PatcherError(f"VV5 Running issuance cleanup identity changed: {path}")
    if progress is not None:
        progress("intent", {"source_record": actual})
    tombstone_name = tombstone_name or f".{path.parent.name}-{path.name}.vv5run-tombstone-{uuid.uuid4().hex}"
    preserved_name = preserved_name or f".{path.name}.vv5run-preserved-{uuid.uuid4().hex}.backup"
    if Path(tombstone_name).name != tombstone_name or Path(preserved_name).name != preserved_name:
        raise PatcherError("VV5 Running quarantine name is unsafe.")
    tombstone = owner_parent / tombstone_name
    if os.path.lexists(tombstone):
        raise PatcherError("VV5 Running issuance tombstone target raced.")
    try:
        if stat.S_ISDIR(os.lstat(path).st_mode):
            _strict_move_noreplace(path, tombstone)
        else:
            os.link(path, tombstone)
    except OSError as exc:
        raise PatcherError("VV5 Running issuance tombstone publication failed.") from exc
    moved = _inventory(owner_parent, tombstone)
    if moved is None or any(moved.get(key) != actual.get(key) for key in ("type", "size", "sha256", "st_dev", "st_ino")):
        raise PatcherError("VV5 Running issuance tombstone identity changed.")
    if progress is not None:
        progress("tombstone_verified", {"tombstone_name": tombstone.name, "tombstone_record": moved})
    source_before_delete = _inventory(path.parent, path)
    tombstone_before_delete = _inventory(owner_parent, tombstone)
    if source_before_delete != actual or tombstone_before_delete != moved:
        raise PatcherError("VV5 Running issuance tombstone/source changed before deletion.")
    preserved = owner_parent / preserved_name
    if os.path.lexists(preserved):
        raise PatcherError("VV5 Running issuance preserved backup target raced.")
    # Preserve a verified copy before consuming the original.  If the write
    # fails after creating a partial file, remove only that exact owned partial
    # (or retain it as explicit failure evidence); never delete a raced foreign
    # replacement and never strand an unreported artifact.
    source_bytes = _read(path)
    preserved_after_exception: dict[str, object] | None = None
    try:
        _write(preserved, source_bytes)
    except Exception as exc:
        if os.path.lexists(preserved):
            try:
                partial = _inventory(owner_parent, preserved)
                if partial is not None and partial.get("type") == "regular_file" and partial.get("size") == len(source_bytes) and partial.get("sha256") == _sha(source_bytes):
                    # The write raised after a complete, verified copy was
                    # published; accept that copy and continue safely.
                    preserved_after_exception = partial
                else:
                    # A partial or substituted file cannot be deleted merely
                    # because it has our generated name.  Record its exact
                    # identity in a durable, machine-readable marker so the
                    # owner can decide whether/how to replay cleanup.
                    marker = owner_parent / f".vv5-preserved-backup-failure-{uuid.uuid4().hex}.json"
                    marker_payload = {
                        "schema_version": 1,
                        "kind": "vv5_preserved_backup_failure",
                        "path": preserved.name,
                        "record": partial,
                        "expected_sha256": _sha(source_bytes),
                        "expected_size": len(source_bytes),
                    }
                    try:
                        _write(marker, (json.dumps(marker_payload, indent=2, sort_keys=True) + "\n").encode("utf-8"))
                    except Exception as marker_exc:
                        raise PatcherError(f"VV5 Running preserved backup failure left unrecorded residue: {preserved}") from marker_exc
                    raise PatcherError(f"VV5 Running preserved backup residue recorded at {marker}: {preserved}")
            except Exception as cleanup_exc:
                if isinstance(cleanup_exc, PatcherError):
                    raise cleanup_exc from exc
                raise PatcherError(f"VV5 Running preserved backup cleanup failed; residue retained: {preserved}") from cleanup_exc
        if preserved_after_exception is None:
            raise PatcherError("VV5 Running preserved backup creation failed; no unowned residue remains.") from exc
    preserved_record = preserved_after_exception or _inventory(owner_parent, preserved)
    if preserved_record is None or preserved_record.get("sha256") != actual.get("sha256") or preserved_record.get("size") != actual.get("size"):
        raise PatcherError("VV5 Running issuance preserved backup verification failed.")
    if progress is not None:
        progress("preserved_verified", {"preserved_name": preserved.name, "preserved_record": preserved_record})
    source_before_delete = _inventory(path.parent, path)
    tombstone_before_delete = _inventory(owner_parent, tombstone)
    if source_before_delete != actual or tombstone_before_delete != moved:
        raise PatcherError("VV5 Running issuance tombstone/source changed before deletion.")
    if stat.S_ISREG(os.lstat(path).st_mode):
        _strict_delete_file_by_handle(path, actual)
    elif os.path.lexists(path):
        raise PatcherError("VV5 Running issuance directory source remained after quarantine.")
    tombstone_after_delete = _inventory(owner_parent, tombstone)
    if tombstone_after_delete != moved:
        raise PatcherError("VV5 Running issuance tombstone changed after source deletion.")
    if os.path.lexists(path):
        raise PatcherError("VV5 Running issuance source was replaced during deletion.")
    if progress is not None:
        progress("source_removed_verified", {"source_record": actual, "tombstone_record": moved, "preserved_record": preserved_record})
    return tombstone, moved, preserved


def _cleanup_record_path(owner_parent: Path) -> Path:
    return owner_parent / f".vv5run-cleanup-{uuid.uuid4().hex}.json"


def _cleanup_record_payload(
    owner_parent: Path,
    registry: Path,
    registry_identity: dict[str, int],
    owned: list[tuple[Path, dict[str, object]]],
    *,
    remove_registry: bool,
    authority: tuple[Path, dict[str, object]] | None = None,
) -> dict[str, object]:
    authority_binding: dict[str, object] | None = None
    if authority is not None:
        authority_path, authority_record = authority
        authority_bytes = _read(authority_path)
        authority_raw = json.loads(authority_bytes.decode("utf-8"))
        if not isinstance(authority_raw, dict) or authority_raw.get("kind") != "vv5_running_authority":
            raise PatcherError("VV5 Running cleanup authority source is malformed.")
        authority_binding = {
            "name": authority_path.name,
            "role": "authority",
            "record": _rebase_registry_record(registry, authority_path, authority_record),
            "token": authority_raw.get("token"),
            "registry_identity": registry_identity,
            "owner_parent_absolute": _canonical(owner_parent),
            "feature_owner": VV5_FEATURE_OWNER,
            "mode": VV5_MODE,
        }
    issuance_bindings: list[dict[str, object]] = []
    for path, record in owned:
        if authority is not None and path == authority[0]:
            continue
        binding: dict[str, object] = {
            "name": path.name,
            "role": "issuance",
            "record": _rebase_registry_record(registry, path, record),
        }
        try:
            raw = json.loads(_read(path).decode("utf-8"))
            if isinstance(raw, dict):
                for key in ("token", "authority_token", "operation", "destination_parent_absolute", "destination_paths_absolute", "members"):
                    if key in raw:
                        binding[key] = raw[key]
        except Exception:
            # A cleanup record still retains the verified source identity; a
            # malformed source will fail closed during replay.
            pass
        issuance_bindings.append(binding)
    return {
        "schema_version": 2,
        "kind": "vv5_running_cleanup_transaction",
        "feature_owner": VV5_FEATURE_OWNER,
        "mode": VV5_MODE,
        "operation": "issuance_cleanup",
        "owner_parent_absolute": str(owner_parent.absolute()).casefold(),
        "registry_relative": registry.name,
        "registry_identity": registry_identity,
        "remove_registry": bool(remove_registry),
        "state": "started",
        "record_version": 1,
        "previous_record_name": None,
        "previous_record_identity": None,
        "authority_binding": authority_binding,
        "issuance_bindings": issuance_bindings,
        "transaction_binding": {
            "owner_parent_absolute": _canonical(owner_parent),
            "registry_relative": registry.name,
            "registry_identity": registry_identity,
            "operation": "issuance_cleanup",
            "artifact_names": [path.name for path, _record in owned],
            "artifact_roles": {path.name: "authority" if authority is not None and path == authority[0] else "issuance" for path, _record in owned},
            "remove_registry": bool(remove_registry),
        },
        "artifacts": [
            {
                "name": path.name,
                "role": "authority" if path.name == AUTHORITY_NAME else "issuance_member",
                "source_record": _rebase_registry_record(registry, path, record),
                "tombstone_name": None,
                "tombstone_record": None,
                "preserved_name": None,
                "preserved_record": None,
                "guard_name": None,
                "guard_record": None,
            }
            for path, record in owned
        ],
    }


def _write_cleanup_record(owner_parent: Path, payload: dict[str, object]) -> tuple[Path, dict[str, object]]:
    _require_windows_identity_atomic()
    record_path = _cleanup_record_path(owner_parent)
    data = (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")
    try:
        _write(record_path, data)
    except Exception as exc:
        # A late flush exception can occur after a complete exclusive record
        # is durable.  Accept only that exact complete record as replayable.
        if os.path.lexists(record_path):
            actual = _inventory(owner_parent, record_path)
            if actual is not None and actual.get("sha256") == _sha(data) and actual.get("size") == len(data):
                return record_path, actual
        raise PatcherError("VV5 Running cleanup authority creation failed; evidence was not proven complete.") from exc
    record = _inventory(owner_parent, record_path)
    if record is None:
        raise PatcherError("VV5 Running cleanup authority could not be captured.")
    return record_path, record


def _update_cleanup_record(record_path: Path, expected: dict[str, object], payload: dict[str, object]) -> tuple[Path, dict[str, object]]:
    """Version an owned cleanup authority with exclusive no-replace publication."""
    _require_windows_identity_atomic()
    current = _inventory(record_path.parent, record_path)
    if current != expected:
        raise PatcherError("VV5 Running cleanup authority changed before update.")
    if payload.get("record_version") is None:
        payload["record_version"] = 1
    payload["record_version"] = int(payload["record_version"]) + 1
    payload["previous_record_name"] = record_path.name
    payload["previous_record_identity"] = expected
    next_path = _cleanup_record_path(record_path.parent)
    tmp = next_path.with_suffix(".tmp")
    data = (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")
    try:
        _write(tmp, data)
    except Exception as exc:
        if os.path.lexists(tmp):
            partial = _inventory(record_path.parent, tmp)
            if partial is None or partial.get("sha256") != _sha(data) or partial.get("size") != len(data):
                raise PatcherError("VV5 Running cleanup authority update left incomplete evidence.") from exc
        else:
            raise
    if _inventory(record_path.parent, record_path) != expected:
        _cleanup(tmp, expected=_inventory(record_path.parent, tmp))
        raise PatcherError("VV5 Running cleanup authority raced during update.")
    _strict_publish_exclusive(tmp, next_path, record_path.parent)
    updated = _inventory(record_path.parent, next_path)
    if updated is None or updated.get("sha256") != _sha(data):
        raise PatcherError("VV5 Running cleanup authority update postverify failed.")
    # Keep the predecessor as a durable chain member.  A replay can therefore
    # recover from an interruption after any number of successor publications
    # (including a three-version retirement) without guessing which record was
    # the last authoritative state.  Finalization retires the chain in order,
    # oldest first, after the latest record has passed its stable namespace
    # check.
    return next_path, updated


def _cleanup_authority_chain(owner_parent: Path) -> list[tuple[Path, dict[str, object], dict[str, object]]]:
    """Capture and validate the complete transitive cleanup-authority chain."""
    candidates: list[tuple[Path, dict[str, object], dict[str, object]]] = []
    with os.scandir(owner_parent) as entries:
        for entry in entries:
            if not re.fullmatch(r"\.vv5run-cleanup-[0-9a-f]{32}\.json", entry.name):
                continue
            path = owner_parent / entry.name
            raw, identity = _validate_cleanup_record(path)
            candidates.append((path, raw, identity))
    if not candidates:
        raise PatcherError("VV5 Running cleanup authority chain is missing.")
    by_name = {path.name: (path, raw, identity) for path, raw, identity in candidates}
    if len(by_name) != len(candidates):
        raise PatcherError("VV5 Running cleanup authority chain contains duplicate names.")
    latest = max(candidates, key=lambda item: int(item[1]["record_version"]))
    seen: set[str] = set()
    chain: list[tuple[Path, dict[str, object], dict[str, object]]] = []
    current = latest
    expected_version = int(latest[1]["record_version"])
    while True:
        path, raw, identity = current
        if path.name in seen:
            raise PatcherError("VV5 Running cleanup authority chain contains a cycle.")
        seen.add(path.name)
        if int(raw["record_version"]) != expected_version:
            raise PatcherError("VV5 Running cleanup authority chain versions are not contiguous.")
        chain.append(current)
        previous_name = raw.get("previous_record_name")
        previous_identity = raw.get("previous_record_identity")
        if previous_name is None:
            if previous_identity is not None:
                raise PatcherError("VV5 Running cleanup authority predecessor is ambiguous.")
            break
        if not isinstance(previous_name, str) or not isinstance(previous_identity, dict):
            raise PatcherError("VV5 Running cleanup authority predecessor is malformed.")
        previous = by_name.get(previous_name)
        if previous is None or previous[2] != previous_identity:
            raise PatcherError("VV5 Running cleanup authority predecessor identity is not bound.")
        expected_version -= 1
        current = previous
    if seen != set(by_name):
        raise PatcherError("VV5 Running cleanup authority chain has an orphan or competing branch.")
    return chain


def _cleanup_namespace(parent: Path) -> dict[str, dict[str, object]]:
    """Stable no-follow inventory of every VV5 recovery-owned hidden member."""
    result: dict[str, dict[str, object]] = {}
    with os.scandir(parent) as entries:
        for entry in entries:
            if not (entry.name.startswith(".vv5run-") or entry.name.startswith(".vv5-preserved-")):
                continue
            path = parent / entry.name
            st = os.lstat(path)
            if stat.S_ISLNK(st.st_mode) or _unsafe(st):
                raise PatcherError(f"VV5 Running hidden namespace contains unsafe member: {entry.name}")
            if stat.S_ISREG(st.st_mode):
                record = _inventory(parent, path)
            elif stat.S_ISDIR(st.st_mode):
                record = {"type": "directory", "size": int(st.st_size), "sha256": None, "st_dev": int(st.st_dev), "st_ino": int(st.st_ino)}
            else:
                raise PatcherError(f"VV5 Running hidden namespace contains unsupported member: {entry.name}")
            if record is None:
                raise PatcherError(f"VV5 Running hidden namespace member disappeared: {entry.name}")
            result[entry.name] = record
    with os.scandir(parent) as entries:
        recaptured: dict[str, dict[str, object]] = {}
        for entry in entries:
            if entry.name in result:
                path = parent / entry.name
                st = os.lstat(path)
                if stat.S_ISREG(st.st_mode):
                    recaptured[entry.name] = _inventory(parent, path)
                elif stat.S_ISDIR(st.st_mode):
                    recaptured[entry.name] = {"type": "directory", "size": int(st.st_size), "sha256": None, "st_dev": int(st.st_dev), "st_ino": int(st.st_ino)}
                else:
                    raise PatcherError(f"VV5 Running hidden namespace member changed type: {entry.name}")
        if recaptured != result:
            raise PatcherError("VV5 Running hidden namespace changed during final recapture.")
    return result


def _validate_cleanup_record(record_path: Path) -> tuple[dict[str, object], dict[str, object]]:
    _require_windows_identity_atomic()
    _safe_ancestors(record_path.parent)
    if not re.fullmatch(r"\.vv5run-cleanup-[0-9a-f]{32}\.json", record_path.name):
        raise PatcherError("VV5 Running cleanup authority filename is invalid.")
    record = _inventory(record_path.parent, record_path)
    if record is None:
        raise PatcherError("VV5 Running cleanup authority is missing.")
    raw = json.loads(_read(record_path).decode("utf-8"))
    required = {"schema_version", "kind", "feature_owner", "mode", "operation", "owner_parent_absolute", "registry_relative", "registry_identity", "remove_registry", "state", "record_version", "previous_record_name", "previous_record_identity", "authority_binding", "issuance_bindings", "transaction_binding", "artifacts"}
    if not isinstance(raw, dict) or set(raw) != required or raw.get("schema_version") != 2 or raw.get("kind") != "vv5_running_cleanup_transaction" or raw.get("feature_owner") != VV5_FEATURE_OWNER or raw.get("mode") != VV5_MODE or raw.get("operation") != "issuance_cleanup" or raw.get("owner_parent_absolute") != str(record_path.parent.absolute()).casefold() or raw.get("registry_relative") != ISSUANCE_REGISTRY_NAME or raw.get("state") not in {"started", "quarantining", "cleaning"} or not isinstance(raw.get("record_version"), int) or raw.get("record_version") < 1 or not isinstance(raw.get("artifacts"), list) or not isinstance(raw.get("issuance_bindings"), list) or not isinstance(raw.get("transaction_binding"), dict):
        raise PatcherError("VV5 Running cleanup authority schema is unsupported or ambiguous.")
    binding = raw.get("authority_binding")
    if binding is not None and (not isinstance(binding, dict) or set(binding) != {"name", "role", "record", "token", "registry_identity", "owner_parent_absolute", "feature_owner", "mode"} or binding.get("name") != AUTHORITY_NAME or binding.get("role") != "authority" or binding.get("registry_identity") != raw.get("registry_identity") or binding.get("owner_parent_absolute") != raw.get("owner_parent_absolute") or binding.get("feature_owner") != VV5_FEATURE_OWNER or binding.get("mode") != VV5_MODE or not isinstance(binding.get("token"), str) or not re.fullmatch(r"[0-9A-Fa-f]{32,128}", binding.get("token", "")) or not isinstance(binding.get("record"), dict) or binding["record"].get("path") != f"{ISSUANCE_REGISTRY_NAME}/{AUTHORITY_NAME}"):
        raise PatcherError("VV5 Running cleanup authority external binding is malformed.")
    transaction_binding = raw.get("transaction_binding")
    if transaction_binding.get("owner_parent_absolute") != raw.get("owner_parent_absolute") or transaction_binding.get("registry_relative") != raw.get("registry_relative") or transaction_binding.get("registry_identity") != raw.get("registry_identity") or transaction_binding.get("operation") != raw.get("operation") or transaction_binding.get("remove_registry") != raw.get("remove_registry"):
        raise PatcherError("VV5 Running cleanup transaction binding is inconsistent.")
    if raw.get("previous_record_name") is not None and (not isinstance(raw.get("previous_record_name"), str) or Path(str(raw.get("previous_record_name"))).name != raw.get("previous_record_name") or not isinstance(raw.get("previous_record_identity"), dict)):
        raise PatcherError("VV5 Running cleanup predecessor binding is malformed.")
    if len({str(item.get("name", "")).casefold() for item in raw["artifacts"] if isinstance(item, dict)}) != len(raw["artifacts"]):
        raise PatcherError("VV5 Running cleanup authority contains duplicate members.")
    artifact_keys = {"name", "role", "source_record", "tombstone_name", "tombstone_record", "preserved_name", "preserved_record", "guard_name", "guard_record"}
    for item in raw["artifacts"]:
        if not isinstance(item, dict) or set(item) != artifact_keys or not isinstance(item.get("name"), str) or Path(item["name"]).name != item["name"] or item.get("role") not in {"authority", "issuance_member"}:
            raise PatcherError("VV5 Running cleanup authority member schema is invalid.")
        for key in ("source_record", "tombstone_record", "preserved_record", "guard_record"):
            value = item.get(key)
            if value is None:
                continue
            if not isinstance(value, dict) or value.get("type") != "regular_file":
                raise PatcherError("VV5 Running cleanup authority member identity is invalid.")
            sha = value.get("sha256")
            if not isinstance(sha, str) or not re.fullmatch(r"[0-9A-Fa-f]{64}", sha):
                raise PatcherError("VV5 Running cleanup authority SHA-256 is invalid.")
            value["sha256"] = sha.upper()
        source_record = item.get("source_record")
        if not isinstance(source_record, dict) or source_record.get("path") != f"{ISSUANCE_REGISTRY_NAME}/{item['name']}":
            raise PatcherError("VV5 Running cleanup authority source path is not registry-bound.")
    artifact_names = {str(item.get("name")) for item in raw["artifacts"] if isinstance(item, dict)}
    bound_names = transaction_binding.get("artifact_names")
    bound_roles = transaction_binding.get("artifact_roles")
    if not isinstance(bound_names, list) or {str(name) for name in bound_names} != artifact_names or not isinstance(bound_roles, dict) or set(bound_roles) != artifact_names:
        raise PatcherError("VV5 Running cleanup transaction artifact binding is incomplete.")
    actual_roles = {str(item["name"]): ("authority" if item.get("role") == "authority" else "issuance") for item in raw["artifacts"]}
    if bound_roles != actual_roles:
        raise PatcherError("VV5 Running cleanup transaction artifact roles are inconsistent.")
    authority_items = [item for item in raw["artifacts"] if isinstance(item, dict) and item.get("role") == "authority"]
    if isinstance(binding, dict) and AUTHORITY_NAME in artifact_names and (len(authority_items) != 1 or authority_items[0].get("source_record") != binding.get("record")):
        raise PatcherError("VV5 Running cleanup authority source is not externally bound.")
    for binding in raw["issuance_bindings"]:
        if not isinstance(binding, dict) or not isinstance(binding.get("name"), str) or binding.get("role") != "issuance" or binding.get("name") not in artifact_names or not isinstance(binding.get("record"), dict) or binding["record"].get("path") != f"{ISSUANCE_REGISTRY_NAME}/{binding['name']}":
            raise PatcherError("VV5 Running cleanup issuance binding is malformed.")
    expected_issuance_names = {name for name in artifact_names if name != AUTHORITY_NAME}
    if {str(item.get("name")) for item in raw["issuance_bindings"] if isinstance(item, dict)} != expected_issuance_names:
        raise PatcherError("VV5 Running cleanup issuance binding set is incomplete.")
    return raw, record


def recover_cleanup_atomic(record_path: Path, mode: str = VV5_MODE) -> None:
    """Replay an interrupted VV5 issuance cleanup without consuming foreign material."""
    if mode != VV5_MODE:
        raise PatcherError("VV5 Running supports Collection Progression only.")
    record_path = Path(record_path)
    raw, record_identity = _validate_cleanup_record(record_path)
    owner_parent = record_path.parent
    chain = _cleanup_authority_chain(owner_parent)
    latest_path, latest_raw, latest_identity = chain[0]
    if latest_path != record_path:
        # A caller may hand us an older predecessor after an interrupted
        # retirement; the complete chain is authoritative and the newest
        # record is the only replay head.
        record_path, raw, record_identity = latest_path, latest_raw, latest_identity
    superseded_records: list[tuple[Path, dict[str, object]]] = [(path, identity) for path, _item, identity in chain[1:]]
    registry = owner_parent / ISSUANCE_REGISTRY_NAME
    registry_identity = raw.get("registry_identity")
    registry_present = os.path.lexists(registry)
    if not isinstance(registry_identity, dict) or (registry_present and _identity(registry) != registry_identity) or (not registry_present and not bool(raw.get("remove_registry"))):
        raise PatcherError("VV5 Running cleanup registry identity changed.")
    authority_binding = raw.get("authority_binding")
    # A cleanup record without external authority provenance may only be
    # replayed while its original registry is still present.  Once the
    # registry has been removed (including remove_registry=true), no
    # self-described record is accepted as a destructive authority.
    if authority_binding is None and not registry_present:
        raise PatcherError("VV5 Running cleanup lacks externally authenticated authority for absent registry.")
    if not registry_present:
        # Once the registry is gone, replay is valid only when every owned
        # member has already produced preserved recovery evidence.  Accepting
        # a bare authority token or a self-described empty artifact set would
        # turn an absent-registry record into a forgeable deletion authority.
        for item in raw.get("artifacts", []):
            if not isinstance(item, dict) or not item.get("tombstone_record") or not item.get("preserved_record"):
                raise PatcherError("VV5 Running absent-registry replay lacks complete preserved evidence.")
    if authority_binding is not None:
        authority_path = registry / AUTHORITY_NAME
        if not registry_present and raw.get("state") != "cleaning":
            raise PatcherError("VV5 Running cleanup external authority is missing or changed.")
        if not registry_present:
            members_now = {}
        else:
            members_now = _registry_members(registry)
        if os.path.lexists(authority_path):
            if _inventory(owner_parent, authority_path) != authority_binding.get("record"):
                raise PatcherError("VV5 Running cleanup external authority is missing or changed.")
            authority_raw = json.loads(_read(authority_path).decode("utf-8"))
            if not isinstance(authority_raw, dict) or authority_raw.get("token") != authority_binding.get("token") or authority_raw.get("registry_identity") != registry_identity or authority_raw.get("feature_owner") != VV5_FEATURE_OWNER or authority_raw.get("mode") != VV5_MODE:
                raise PatcherError("VV5 Running cleanup external authority token is invalid.")
            if AUTHORITY_NAME not in members_now or members_now[AUTHORITY_NAME] != authority_binding.get("record"):
                raise PatcherError("VV5 Running cleanup authority registry membership changed.")
        elif members_now:
            # During a started/quarantining replay the authority itself may
            # already have been quarantined while issuance members remain.
            # Accept that transitional state only when every remaining member
            # is an explicitly bound cleanup artifact; foreign members still
            # fail closed before any further mutation.
            if raw.get("state") not in {"started", "quarantining", "cleaning"}:
                raise PatcherError("VV5 Running cleanup authority disappeared with registry members still present.")
            bound = {
                str(item.get("name"))
                for item in raw.get("artifacts", [])
                if isinstance(item, dict) and item.get("role") in {"issuance", "issuance_member", "authority"}
            }
            if not set(members_now).issubset(bound):
                raise PatcherError("VV5 Running cleanup authority disappeared with foreign registry members present.")
    elif raw.get("schema_version") == 2 and registry_present and _registry_members(registry):
        raise PatcherError("VV5 Running cleanup lacks an external authority binding.")
    if raw.get("state") == "started":
        if not registry_present:
            # The registry may already have been removed after a late
            # publication failure.  With no source member left to quarantine,
            # advance the durable record to cleaning and finalize the retained
            # tombstone/preserved evidence deterministically.
            raw["state"] = "cleaning"
            next_path, _next_identity = _update_cleanup_record(record_path, record_identity, raw)
            return recover_cleanup_atomic(next_path, mode=mode)
        current_members = _registry_members(registry)
        # Quarantine exactly one member and publish a successor before the
        # next member.  Every partial started replay is therefore durable and
        # retryable at a member boundary.
        for item in raw["artifacts"]:
            if item.get("role") not in {"issuance", "issuance_member", "authority"}:
                continue
            if item.get("tombstone_name") and item.get("preserved_name"):
                continue
            source = registry / str(item["name"])
            pending = raw.get("transaction_binding", {}).get("pending")
            pending_for_item = pending if isinstance(pending, dict) and pending.get("name") == item.get("name") else None
            if pending_for_item is not None and pending_for_item.get("source_record") != item.get("source_record"):
                raise PatcherError("VV5 Running pending quarantine source binding is inconsistent.")
            if pending_for_item is not None:
                # A restart must adopt only targets whose exact records were
                # durably journaled.  A physical target with no checkpoint is
                # ambiguous (including same-content foreign material), so it
                # remains untouched and recovery fails closed.
                tombstone_name = pending_for_item.get("tombstone_name")
                preserved_name = pending_for_item.get("preserved_name")
                if not isinstance(tombstone_name, str) or not isinstance(preserved_name, str) or Path(tombstone_name).name != tombstone_name or Path(preserved_name).name != preserved_name:
                    raise PatcherError("VV5 Running pending quarantine names are malformed.")
                tombstone = owner_parent / tombstone_name
                preserved = owner_parent / preserved_name
                source_binding = pending_for_item.get("source_record")
                if not isinstance(source_binding, dict):
                    raise PatcherError("VV5 Running pending quarantine source identity is missing.")
                substate = pending_for_item.get("substate", "intent")
                if substate not in {"intent", "tombstone_verified", "preserved_verified", "source_removed_verified"}:
                    raise PatcherError("VV5 Running pending quarantine substate is unsupported.")
                tombstone_expected = pending_for_item.get("tombstone_record")
                preserved_expected = pending_for_item.get("preserved_record")
                tombstone_exists = os.path.lexists(tombstone)
                preserved_exists = os.path.lexists(preserved)
                if tombstone_exists and not isinstance(tombstone_expected, dict):
                    raise PatcherError("VV5 Running pending tombstone exists without an immutable checkpoint.")
                if preserved_exists and not isinstance(preserved_expected, dict):
                    raise PatcherError("VV5 Running pending preserved copy exists without an immutable checkpoint.")
                if isinstance(tombstone_expected, dict) and _inventory(owner_parent, tombstone) != tombstone_expected:
                    raise PatcherError("VV5 Running pending tombstone identity changed.")
                if isinstance(preserved_expected, dict) and _inventory(owner_parent, preserved) != preserved_expected:
                    raise PatcherError("VV5 Running pending preserved identity changed.")
                if substate in {"tombstone_verified", "preserved_verified", "source_removed_verified"} and (not tombstone_exists or not preserved_exists):
                    raise PatcherError("VV5 Running pending checkpoint targets are missing.")
                if substate == "source_removed_verified":
                    if os.path.lexists(source):
                        raise PatcherError("VV5 Running source reappeared after removal checkpoint.")
                    item["tombstone_name"] = tombstone.name
                    item["tombstone_record"] = tombstone_expected
                    item["preserved_name"] = preserved.name
                    item["preserved_record"] = preserved_expected
                    raw["transaction_binding"].pop("pending", None)
                    next_path, _next_identity = _update_cleanup_record(record_path, record_identity, raw)
                    return recover_cleanup_atomic(next_path, mode=mode)
                if substate in {"tombstone_verified", "preserved_verified"} and os.path.lexists(source):
                    source_record = _inventory(registry.parent, source)
                    if source_record != source_binding:
                        raise PatcherError("VV5 Running pending source identity changed before adoption.")
                    if substate == "tombstone_verified":
                        # A verified tombstone is not enough to recreate the
                        # preserved target; its absence is a hard stop.
                        if not preserved_exists:
                            raise PatcherError("VV5 Running preserved target is missing after tombstone checkpoint.")
                        pending_for_item["substate"] = "preserved_verified"
                        next_path, _next_identity = _update_cleanup_record(record_path, record_identity, raw)
                        return recover_cleanup_atomic(next_path, mode=mode)
                    _strict_delete_file_by_handle(source, source_binding)
                    if os.path.lexists(source):
                        raise PatcherError("VV5 Running pending source removal did not verify.")
                    pending_for_item["substate"] = "source_removed_verified"
                    pending_for_item["source_record"] = source_binding
                    next_path, _next_identity = _update_cleanup_record(record_path, record_identity, raw)
                    return recover_cleanup_atomic(next_path, mode=mode)
                if substate in {"tombstone_verified", "preserved_verified"}:
                    raise PatcherError("VV5 Running pending source state is inconsistent with checkpoint.")
                if substate == "intent" and (tombstone_exists or preserved_exists):
                    raise PatcherError("VV5 Running uncheckpointed quarantine target cannot be adopted safely.")
            if not os.path.lexists(source):
                raise PatcherError("VV5 Running started cleanup issuance member is missing.")
            source_record = _inventory(registry.parent, source)
            expected_source = item.get("source_record")
            if source_record is None or not isinstance(expected_source, dict) or any(source_record.get(key) != expected_source.get(key) for key in ("type", "size", "sha256", "st_dev", "st_ino")):
                raise PatcherError("VV5 Running started cleanup issuance member changed.")
            if pending_for_item is not None:
                tombstone_name = pending_for_item.get("tombstone_name")
                preserved_name = pending_for_item.get("preserved_name")
                if not isinstance(tombstone_name, str) or not isinstance(preserved_name, str):
                    raise PatcherError("VV5 Running pending quarantine names are malformed.")
            else:
                tombstone_name = f".{registry.name}-{source.name}.vv5run-tombstone-{uuid.uuid4().hex}"
                preserved_name = f".{source.name}.vv5run-preserved-{uuid.uuid4().hex}.backup"

            # Recovery may discover an older record that predates the pending
            # quarantine checkpoint.  Publish that intent before touching the
            # source; the next replay then has deterministic names and an
            # identity-bound starting point.
            if pending_for_item is None:
                raw.setdefault("transaction_binding", {})["pending"] = {
                    "name": item["name"],
                    "source_record": expected_source,
                    "tombstone_name": tombstone_name,
                    "preserved_name": preserved_name,
                    "substate": "intent",
                }
                raw["state"] = "started"
                next_path, _next_identity = _update_cleanup_record(record_path, record_identity, raw)
                return recover_cleanup_atomic(next_path, mode=mode)

            def journal_progress(state, details):
                nonlocal record_path, record_identity
                pending = raw.get("transaction_binding", {}).get("pending")
                if not isinstance(pending, dict) or pending.get("name") != item["name"]:
                    raise PatcherError("VV5 Running recovery quarantine lost its pending source binding.")
                pending["substate"] = state
                pending.update(details)
                raw["state"] = "quarantining"
                record_path, record_identity = _update_cleanup_record(record_path, record_identity, raw)

            tombstone, tombstone_record, preserved = _quarantine_owned(
                source,
                source_record,
                owner_parent=owner_parent,
                tombstone_name=tombstone_name,
                preserved_name=preserved_name,
                progress=journal_progress,
            )
            item["tombstone_name"] = tombstone.name
            item["tombstone_record"] = tombstone_record
            item["preserved_name"] = preserved.name
            item["preserved_record"] = _inventory(owner_parent, preserved)
            if item["preserved_record"] is None:
                raise PatcherError("VV5 Running started cleanup preserved copy is missing.")
            # Keep the state as started until every member has a durable
            # tombstone/preserved record.  This makes the successor replay
            # continue with the next member rather than skipping directly to
            # cleaning after the first checkpoint.
            raw["transaction_binding"].pop("pending", None)
            raw["state"] = "started"
            next_path, _next_identity = _update_cleanup_record(record_path, record_identity, raw)
            return recover_cleanup_atomic(next_path, mode=mode)
        raw["state"] = "quarantining"
        next_path, _next_identity = _update_cleanup_record(record_path, record_identity, raw)
        return recover_cleanup_atomic(next_path, mode=mode)
    artifacts = raw["artifacts"]
    allowed_hidden = {record_path.name} | {path.name for path, _identity in superseded_records}
    for item in artifacts:
        for key in ("name", "tombstone_name", "preserved_name", "guard_name"):
            if isinstance(item, dict) and isinstance(item.get(key), str):
                allowed_hidden.add(item[key])
    with os.scandir(owner_parent) as namespace_entries:
        for entry in namespace_entries:
            if entry.name.startswith(".vv5run-") or entry.name.startswith(".vv5-preserved-"):
                if entry.name not in allowed_hidden and entry.name != ISSUANCE_REGISTRY_NAME:
                    raise PatcherError("VV5 Running cleanup namespace contains unknown residue.")
    for item in artifacts:
        if not isinstance(item, dict):
            raise PatcherError("VV5 Running cleanup authority member is malformed.")
        for key in ("tombstone_name", "preserved_name", "guard_name"):
            name = item.get(key)
            if name is not None and (not isinstance(name, str) or Path(name).name != name):
                raise PatcherError("VV5 Running cleanup authority member path is unsafe.")
        tombstone = owner_parent / item["tombstone_name"] if item.get("tombstone_name") else None
        preserved = owner_parent / item["preserved_name"] if item.get("preserved_name") else None
        guard = owner_parent / item["guard_name"] if item.get("guard_name") else None
        if registry_present:
            expected_members = _registry_members(registry)
            expected_names = set(expected_members)
            if item["name"] in expected_names:
                if _inventory(owner_parent, registry / item["name"]) != item.get("source_record"):
                    raise PatcherError("VV5 Running cleanup registry member changed before deletion.")
        # Verify the preserved copy before touching the tombstone.  This keeps
        # at least one independently hashed owned copy alive across every
        # tombstone/guard boundary.
        if preserved is not None and os.path.lexists(preserved):
            preserved_expected = item.get("preserved_record")
            if _inventory(owner_parent, preserved) != preserved_expected:
                raise PatcherError("VV5 Running preserved copy changed before tombstone cleanup.")
        if tombstone is not None and os.path.lexists(tombstone):
            _cleanup(tombstone, expected=item.get("tombstone_record"))
            if os.path.lexists(tombstone):
                raise PatcherError("VV5 Running cleanup tombstone remained after deletion.")
        if guard is not None and os.path.lexists(guard):
            expected = item.get("guard_record")
            actual = _inventory(owner_parent, guard)
            if actual != expected:
                raise PatcherError("VV5 Running cleanup guard changed during replay.")
            _cleanup(guard, expected=expected)
            if os.path.lexists(guard):
                raise PatcherError("VV5 Running cleanup guard remained after deletion.")
        if preserved is not None and os.path.lexists(preserved):
            expected = item.get("preserved_record")
            actual = _inventory(owner_parent, preserved)
            if actual != expected:
                raise PatcherError("VV5 Running cleanup preserved backup changed during replay.")
            _cleanup(preserved, expected=expected)
            if os.path.lexists(preserved):
                raise PatcherError("VV5 Running cleanup preserved copy remained after deletion.")
    if bool(raw.get("remove_registry")) and registry_present:
        _assert_registry_members(registry, registry_identity, {})
        _cleanup_registry(registry, registry_identity)
        if os.path.lexists(registry):
            raise PatcherError("VV5 Running cleanup registry remained after deletion.")
    # Stable namespace verification is performed before retiring any cleanup
    # authority.  In particular, an inserted/recreated hidden member keeps the
    # current authority durable and makes the operation fail closed.
    namespace_after_members = _cleanup_namespace(owner_parent)
    allowed_after = {record_path.name} | {path.name for path, _identity in superseded_records}
    if not set(namespace_after_members).issubset(allowed_after):
        raise PatcherError("VV5 Running cleanup namespace changed before authority retirement.")
    # Retire predecessors oldest-first.  The current record remains available
    # until every older authority has been removed and the final namespace is
    # recaptured.
    for prior_path, prior_identity in reversed(superseded_records):
        _cleanup(prior_path, expected=prior_identity)
        if os.path.lexists(prior_path):
            raise PatcherError("VV5 Running superseded cleanup authority remained after finalization.")
        if not set(_cleanup_namespace(owner_parent)).issubset(allowed_after):
            raise PatcherError("VV5 Running cleanup namespace changed during authority retirement.")
    _cleanup(record_path, expected=record_identity)
    if os.path.lexists(record_path):
        raise PatcherError("VV5 Running cleanup authority remained after deletion.")
    if _cleanup_namespace(owner_parent):
        raise PatcherError("VV5 Running cleanup namespace retained residue after finalization.")


def _cleanup_issuance_artifacts(
    registry: Path,
    registry_identity: dict[str, int],
    artifacts: list[tuple[Path, dict[str, object]]],
    authority: tuple[Path, dict[str, object]] | None,
    *,
    retain_authority: tuple[Path, dict[str, object]] | None = None,
    remove_registry: bool = True,
) -> None:
    """Retire issuance members only through verified quarantine and cleanup."""
    _require_windows_identity_atomic()
    if not os.path.lexists(registry) or _identity(registry) != registry_identity:
        raise PatcherError("VV5 Running issuance registry changed before cleanup.")
    owned = list(artifacts) + ([authority] if authority is not None else [])
    expected_members = owned + ([retain_authority] if retain_authority is not None else [])
    expected = {path.name: _rebase_registry_record(registry, path, record) for path, record in expected_members}
    _assert_registry_members(registry, registry_identity, expected)
    cleanup_payload = _cleanup_record_payload(
        registry.parent,
        registry,
        registry_identity,
        owned,
        remove_registry=remove_registry,
        authority=authority or retain_authority,
    )
    cleanup_record_path, cleanup_record_identity = _write_cleanup_record(registry.parent, cleanup_payload)
    tombstones: list[tuple[Path, dict[str, object], Path]] = []
    # Keep a second verified hard-link while the tombstone is retired.  If the
    # preserved path is replaced in the tombstone-delete interval, this guard
    # retains the last owned bytes and is left for deterministic retry.
    guards: dict[str, tuple[Path, dict[str, object]]] = {}
    try:
        for path, record in owned:
            _assert_registry_members(registry, registry_identity, expected)
            pending_tombstone = f".{registry.name}-{path.name}.vv5run-tombstone-{uuid.uuid4().hex}"
            pending_preserved = f".{path.name}.vv5run-preserved-{uuid.uuid4().hex}.backup"
            cleanup_payload["transaction_binding"]["pending"] = {
                "name": path.name,
                "source_record": _rebase_registry_record(registry, path, record),
                "tombstone_name": pending_tombstone,
                "preserved_name": pending_preserved,
            }
            cleanup_payload["state"] = "quarantining"
            cleanup_record_path, cleanup_record_identity = _update_cleanup_record(cleanup_record_path, cleanup_record_identity, cleanup_payload)

            def journal_progress(state, details):
                nonlocal cleanup_record_path, cleanup_record_identity
                pending = cleanup_payload["transaction_binding"].get("pending")
                if not isinstance(pending, dict) or pending.get("name") != path.name:
                    raise PatcherError("VV5 Running quarantine progress lost its pending source binding.")
                pending["substate"] = state
                pending.update(details)
                cleanup_payload["state"] = "quarantining"
                cleanup_record_path, cleanup_record_identity = _update_cleanup_record(cleanup_record_path, cleanup_record_identity, cleanup_payload)

            quarantine = _quarantine_owned(
                path,
                record,
                owner_parent=registry.parent,
                tombstone_name=pending_tombstone,
                preserved_name=pending_preserved,
                progress=journal_progress,
            )
            tombstones.append(quarantine)
            item = next(item for item in cleanup_payload["artifacts"] if item["name"] == path.name)
            item["tombstone_name"] = quarantine[0].name
            item["tombstone_record"] = quarantine[1]
            item["preserved_name"] = quarantine[2].name
            item["preserved_record"] = _inventory(registry.parent, quarantine[2])
            cleanup_payload["transaction_binding"].pop("pending", None)
            cleanup_payload["state"] = "quarantining"
            cleanup_record_path, cleanup_record_identity = _update_cleanup_record(cleanup_record_path, cleanup_record_identity, cleanup_payload)
            expected.pop(path.name, None)
            _assert_registry_members(registry, registry_identity, expected)
        for _tombstone, record, preserved in tombstones:
            guard = preserved.parent / f".{preserved.name}.vv5-preserved-guard-{uuid.uuid4().hex}.backup"
            if os.path.lexists(guard):
                raise PatcherError("VV5 Running preserved-backup guard target raced.")
            try:
                os.link(preserved, guard)
            except OSError as exc:
                raise PatcherError("VV5 Running preserved-backup guard publication failed; authority retained.") from exc
            guard_record = _inventory(guard.parent, guard)
            if guard_record is None or guard_record.get("sha256") != record.get("sha256") or guard_record.get("size") != record.get("size"):
                raise PatcherError("VV5 Running preserved-backup guard verification failed.")
            guards[str(preserved)] = (guard, guard_record)
            item = next(item for item in cleanup_payload["artifacts"] if item["preserved_name"] == preserved.name)
            item["guard_name"] = guard.name
            item["guard_record"] = guard_record
        cleanup_payload["state"] = "cleaning"
        cleanup_record_path, cleanup_record_identity = _update_cleanup_record(cleanup_record_path, cleanup_record_identity, cleanup_payload)
        for tombstone, record, preserved in tombstones:
            _assert_registry_members(registry, registry_identity, expected)
            _cleanup(tombstone, expected=record)
            _assert_registry_members(registry, registry_identity, expected)
            guard, guard_record = guards[str(preserved)]
            preserved_record = _inventory(preserved.parent, preserved)
            if preserved_record is None or preserved_record.get("sha256") != record.get("sha256") or preserved_record.get("size") != record.get("size"):
                raise PatcherError("VV5 Running preserved backup changed before cleanup.")
            if _inventory(guard.parent, guard) != guard_record:
                raise PatcherError("VV5 Running preserved-backup guard changed before cleanup.")
            _assert_registry_members(registry, registry_identity, expected)
            _cleanup(preserved, expected=preserved_record)
            if os.path.lexists(preserved):
                raise PatcherError("VV5 Running preserved backup remained after cleanup.")
            # The guard is the last owned copy.  It is deleted only after the
            # primary preserved copy has been proven and retired.
            if _inventory(guard.parent, guard) != guard_record:
                raise PatcherError("VV5 Running preserved-backup guard changed before final cleanup.")
            _assert_registry_members(registry, registry_identity, expected)
            _cleanup(guard, expected=guard_record)
            if os.path.lexists(guard):
                raise PatcherError("VV5 Running preserved-backup guard remained after cleanup.")
            _assert_registry_members(registry, registry_identity, expected)
        # Successor publication retains the complete cleanup-authority chain;
        # all chain members are owned until final retirement.
        allowed_hidden = {ISSUANCE_REGISTRY_NAME}
        with os.scandir(registry.parent) as cleanup_entries:
            for entry in cleanup_entries:
                if re.fullmatch(r"\.vv5run-cleanup-[0-9a-f]{32}\.json", entry.name):
                    allowed_hidden.add(entry.name)
        with os.scandir(registry.parent) as namespace_entries:
            for entry in namespace_entries:
                if entry.name.startswith(".vv5run-") or entry.name.startswith(".vv5-preserved-"):
                    if entry.name not in allowed_hidden:
                        raise PatcherError("VV5 Running cleanup namespace contains unknown residue.")
        # Keep the registry as durable authority until every tombstone and
        # preserved backup has been verified and retired.  A registry cleanup
        # failure therefore remains retryable and cannot discard the last
        # ownership record prematurely.
        if remove_registry:
            _assert_registry_members(registry, registry_identity, {})
            _cleanup_registry(registry, registry_identity)
        # Retire the durable cleanup chain only after the registry and every
        # preserved copy have passed postverification.  Older records are
        # removed first; the latest record remains the final authority until
        # the namespace is stable.
        chain = _cleanup_authority_chain(registry.parent)
        latest_path, _latest_raw, latest_identity = chain[0]
        for prior_path, _prior_raw, prior_identity in reversed(chain[1:]):
            _cleanup(prior_path, expected=prior_identity)
            if os.path.lexists(prior_path):
                raise PatcherError("VV5 Running cleanup predecessor remained during retirement.")
            _cleanup_namespace(registry.parent)
        _cleanup(latest_path, expected=latest_identity)
    except Exception:
        # Any remaining tombstone is deliberate durable authority evidence;
        # never claim zero residue after a raced or foreign cleanup.
        raise


def _write_issuance(path: Path, payload: dict[str, object]) -> None:
    _require_windows_identity_atomic()
    _safe_ancestors(path.parent)
    if os.path.lexists(path):
        raise PatcherError("VV5 Running issuance record collision.")
    tmp = path.with_suffix(".tmp")
    if os.path.lexists(tmp):
        raise PatcherError("VV5 Running issuance temporary collision.")
    tmp_identity: dict[str, object] | None = None
    try:
        data = (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")
        _write(tmp, data)
        tmp_identity = _inventory(tmp.parent, tmp)
        if tmp_identity is None or os.path.lexists(path):
            raise PatcherError("VV5 Running issuance target raced.")
        _strict_publish_exclusive(tmp, path, path.parent)
        published = _inventory(path.parent, path)
        if published is None or any(published.get(key) != tmp_identity.get(key) for key in ("type", "size", "sha256", "st_dev", "st_ino")):
            raise PatcherError("VV5 Running issuance publication verification failed.")
    except Exception as exc:
        if os.path.lexists(tmp):
            if tmp_identity is not None:
                _cleanup(tmp, expected=tmp_identity)
        if isinstance(exc, PatcherError):
            raise
        raise PatcherError("VV5 Running issuance publication failed; no destination was overwritten.") from exc


def _issuance_pointer_path(path: Path) -> Path:
    return path.with_name(f".{path.name}.pointer")


def _publish_exclusive(tmp: Path, final: Path, root: Path) -> dict[str, object]:
    _require_windows_identity_atomic()
    try:
        _strict_publish_exclusive(tmp, final, root)
    except Exception as exc:
        raise PatcherError(f"VV5 Running issuance successor publication failed: {final}") from exc
    record = _inventory(root, final)
    if record is None:
        raise PatcherError("VV5 Running issuance successor publication disappeared.")
    return record


def _load_issuance_pointer(path: Path, before: dict[str, object]) -> tuple[Path, dict[str, object], Path, dict[str, object]] | None:
    pointer = _issuance_pointer_path(path)
    if not os.path.lexists(pointer):
        return None
    pointer_before = _inventory(path.parent, pointer)
    # The canonical record in the report is rooted at the destination parent,
    # whereas pointer/successor records are rooted at the registry.  Compare
    # the canonical using its original parent root so the path field is not
    # spuriously treated as an identity mutation.
    if pointer_before is None or _inventory(path.parent.parent, path) != before:
        raise PatcherError("VV5 Running issuance pointer/canonical record disappeared or changed.")
    raw = json.loads(_read(pointer).decode("utf-8"))
    required = {"schema_version", "kind", "canonical_name", "canonical_record", "successor_name", "successor_record", "registry_identity"}
    if not isinstance(raw, dict) or set(raw) != required or raw.get("schema_version") != 1 or raw.get("kind") != "vv5_issuance_pointer" or raw.get("canonical_name") != path.name or raw.get("canonical_record") != before:
        raise PatcherError("VV5 Running issuance pointer is malformed or stale.")
    successor_name = raw.get("successor_name")
    if not isinstance(successor_name, str) or Path(successor_name).name != successor_name or not re.fullmatch(re.escape(path.stem) + r"\.v[0-9a-f]{32}" + re.escape(path.suffix), successor_name):
        raise PatcherError("VV5 Running issuance successor name is unsafe.")
    successor = path.parent / successor_name
    successor_record = _inventory(path.parent, successor)
    pointer_record = _inventory(path.parent, pointer)
    if successor_record is None or pointer_record is None or successor_record != raw.get("successor_record"):
        raise PatcherError("VV5 Running issuance pointer identity changed.")
    pointer_final = _inventory(path.parent, pointer)
    successor_final = _inventory(path.parent, successor)
    canonical_final = _inventory(path.parent.parent, path)
    if pointer_final != pointer_before or successor_final != successor_record or canonical_final != before:
        raise PatcherError("VV5 Running issuance pointer chain changed during final recapture.")
    if raw.get("registry_identity") != _identity(path.parent):
        raise PatcherError("VV5 Running issuance pointer registry changed.")
    return successor, successor_final, pointer, pointer_final


def _replace_issuance(path: Path, before: dict[str, object], payload: dict[str, object]) -> dict[str, object]:
    _require_windows_identity_atomic()
    current = _inventory(path.parent, path)
    if current is None or any(current.get(key) != before.get(key) for key in ("type", "size", "sha256", "st_dev", "st_ino")):
        raise PatcherError("VV5 Running issuance record was substituted before binding.")
    pointer = _issuance_pointer_path(path)
    if os.path.lexists(pointer):
        raise PatcherError("VV5 Running issuance pointer already exists.")
    successor = path.with_name(f"{path.stem}.v{uuid.uuid4().hex}{path.suffix}")
    successor_tmp = successor.with_suffix(".tmp")
    pointer_tmp = pointer.with_suffix(".tmp")
    successor_record: dict[str, object] | None = None
    pointer_tmp_record: dict[str, object] | None = None
    data = (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")
    try:
        _write(successor_tmp, data)
        current = _inventory(path.parent, path)
        if current is None or any(current.get(key) != before.get(key) for key in ("type", "size", "sha256", "st_dev", "st_ino")):
            raise PatcherError("VV5 Running issuance record raced during binding.")
        successor_record = _publish_exclusive(successor_tmp, successor, path.parent)
        pointer_payload = {
            "schema_version": 1,
            "kind": "vv5_issuance_pointer",
            "canonical_name": path.name,
            "canonical_record": before,
            "successor_name": successor.name,
            "successor_record": successor_record,
            "registry_identity": _identity(path.parent),
        }
        _write(pointer_tmp, (json.dumps(pointer_payload, indent=2, sort_keys=True) + "\n").encode("utf-8"))
        pointer_tmp_record = _inventory(path.parent, pointer_tmp)
        if pointer_tmp_record is None:
            raise PatcherError("VV5 Running issuance pointer temporary disappeared.")
        _publish_exclusive(pointer_tmp, pointer, path.parent)
        _load_issuance_pointer(path, before)
        return successor_record
    except Exception:
        for temp, record in ((successor_tmp, None), (pointer_tmp, pointer_tmp_record)):
            if os.path.lexists(temp):
                try:
                    _cleanup(temp, expected=record or _inventory(path.parent, temp))
                except Exception:
                    pass
        if successor_record is not None and os.path.lexists(successor) and not os.path.lexists(pointer):
            try:
                _cleanup(successor, expected=successor_record)
            except Exception:
                pass
        raise


def _issuance_payload(token: str, authority_token: str, authority_record: dict[str, object], operation: str, parent: Path, destinations: list[Path], pre: dict[Path, tuple[bool, bytes | None]], published: dict[Path, bytes], registry: Path, registry_identity: dict[str, int]) -> dict[str, object]:
    return {
        "schema_version": ISSUANCE_SCHEMA_VERSION,
        "token": token,
        "authority_token": authority_token,
        "authority_record": authority_record,
        "feature_owner": VV5_FEATURE_OWNER,
        "mode": VV5_MODE,
        "operation": operation,
        "parent_identity": _identity(parent),
        "destination_parent_absolute": _canonical(parent),
        "destination_paths_absolute": [_canonical(p) for p in destinations],
        "registry_relative": ISSUANCE_REGISTRY_NAME,
        "registry_identity": registry_identity,
        "members": [
            {
                "destination": p.name,
                "pre_exists": bool(pre[p][0]),
                "pre_sha256": _sha(pre[p][1]) if pre[p][1] is not None else None,
                "pre_size": len(pre[p][1]) if pre[p][1] is not None else 0,
                "published_sha256": _sha(published[p]),
                "published_size": len(published[p]),
            }
            for p in destinations
        ],
    }


def _bind_issuance(path: Path, token: str, report: Path, report_payload: dict[str, object], before: dict[str, object]) -> dict[str, object]:
    raw = json.loads(_read(path).decode("utf-8"))
    if raw.get("schema_version") != ISSUANCE_SCHEMA_VERSION or raw.get("token") != token or not isinstance(raw.get("authority_token"), str) or not isinstance(raw.get("authority_record"), dict):
        raise PatcherError("VV5 Running issuance record is invalid.")
    if (
        raw.get("destination_parent_absolute") != report_payload.get("destination_parent_absolute")
        or raw.get("destination_paths_absolute") != report_payload.get("destination_paths_absolute")
        or raw.get("registry_relative") != ISSUANCE_REGISTRY_NAME
        or raw.get("registry_identity") != report_payload.get("issuance_registry_identity")
        or raw.get("authority_token") != (report_payload.get("issuance_identity") or {}).get("authority_token")
        or raw.get("authority_record") != (report_payload.get("issuance_identity") or {}).get("authority_record")
    ):
        raise PatcherError("VV5 Running issuance destination/registry binding is invalid.")
    bound = dict(raw)
    bound.update({
        "report_name": report.name,
        "report_sha256": _sha(_read(report)),
        "report_parent_identity": _identity(report.parent),
        "recovery_root_name": report_payload.get("recovery_root_name"),
        "recovery_root_identity": report_payload.get("recovery_root_identity"),
        "report_members": report_payload.get("members"),
        "report_kind": json.loads(_read(report).decode("utf-8")).get("kind", "recovery_report"),
    })
    return _replace_issuance(path, before, bound)


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
        raw_rel = str(member["destination_relative"])
        rel = Path(raw_rel); key = rel.as_posix().casefold()
        if raw_rel not in {VV5_EXE_BASENAME, DLL_NAME} or rel.parts != (raw_rel,) or rel.is_absolute() or not rel.parts or ".." in rel.parts or key in seen:
            raise PatcherError("VV5 Running recovery destination path is unsafe")
        seen.add(key)
        for field in ("backup_relative", "stage_relative"):
            if member[field] is not None:
                p = Path(str(member[field]))
                if p.is_absolute() or ".." in p.parts or not p.parts:
                    raise PatcherError("VV5 Running recovery owned path is unsafe")
    expected_names = [VV5_EXE_BASENAME, DLL_NAME]
    if [str(item["destination_relative"]) for item in members] != expected_names:
        raise PatcherError("VV5 Running recovery destination members are not canonical direct children")
    if not isinstance(payload["ownership_inventory"], list):
        raise PatcherError("VV5 Running recovery ownership inventory is invalid")


def _discover_reports(parent: Path, *, issuance_token: str | None = None) -> list[Path]:
    """Discover only regular, no-follow VV5 recovery records under a stable parent."""
    parent_record = _strict_inventory_entry(parent.parent, parent)
    if parent_record.get("type") != "directory":
        raise PatcherError("VV5 Running recovery parent is unsafe")
    found: list[Path] = []
    captured_records: dict[str, dict[str, object]] = {}
    canonical_re = re.compile(r"\.vv5run-(?:recovery|emergency)-[0-9a-f]{32}\.json")
    successor_re = re.compile(r"\.vv5run-recovery-[0-9a-f]{32}\.v[0-9a-f]{32}\.json")
    pointer_re = re.compile(r"\.vv5run-(?:recovery|emergency)-[0-9a-f]{32}\.json\.pointer")
    with os.scandir(parent) as entries:
        for entry in entries:
            name = entry.name
            if not name.startswith(".vv5run-"):
                continue
            candidate = Path(entry.path)
            st = os.lstat(candidate)
            if name == ISSUANCE_REGISTRY_NAME:
                if stat.S_ISLNK(st.st_mode) or _unsafe(st) or not stat.S_ISDIR(st.st_mode):
                    raise PatcherError("VV5 Running recovery discovery encountered an unsafe issuance registry")
                continue
            if re.fullmatch(r"\.vv5run-recovery-[0-9a-f]{32}", name):
                if stat.S_ISLNK(st.st_mode) or _unsafe(st) or not stat.S_ISDIR(st.st_mode):
                    raise PatcherError("VV5 Running recovery discovery encountered an unsafe recovery root")
                continue
            if not (canonical_re.fullmatch(name) or successor_re.fullmatch(name) or pointer_re.fullmatch(name)):
                raise PatcherError(f"VV5 Running recovery discovery encountered unknown residue: {name}")
            if stat.S_ISLNK(st.st_mode) or _unsafe(st) or not stat.S_ISREG(st.st_mode):
                raise PatcherError("VV5 Running recovery discovery encountered an unsafe member")
            if not canonical_re.fullmatch(name):
                continue
            candidate_record = _strict_inventory_entry(parent, candidate)
            raw = json.loads(_read(candidate).decode("utf-8"))
            candidate_final = _strict_inventory_entry(parent, candidate)
            if candidate_final != candidate_record:
                raise PatcherError("VV5 Running recovery report changed during discovery")
            if issuance_token is not None:
                nested = raw.get("recovery_payload") if isinstance(raw, dict) else None
                if not (isinstance(raw, dict) and raw.get("issuance_token") == issuance_token) and not (isinstance(nested, dict) and nested.get("issuance_token") == issuance_token):
                    continue
            found.append(candidate)
            captured_records[candidate.name] = candidate_record
    # A final complete scan prevents a same-content inode replacement or an
    # unknown .vv5run residue appearing after the first enumeration.
    parent_after = _strict_inventory_entry(parent.parent, parent)
    if parent_after != parent_record:
        raise PatcherError("VV5 Running recovery parent changed during report discovery")
    with os.scandir(parent) as entries:
        for entry in entries:
            if entry.name.startswith(".vv5run-") and not (
                entry.name == ISSUANCE_REGISTRY_NAME
                or re.fullmatch(r"\.vv5run-recovery-[0-9a-f]{32}", entry.name)
                or canonical_re.fullmatch(entry.name)
                or successor_re.fullmatch(entry.name)
                or pointer_re.fullmatch(entry.name)
            ):
                raise PatcherError(f"VV5 Running recovery discovery encountered unknown residue: {entry.name}")
    found = sorted(found, key=lambda p: p.name)
    for candidate in found:
        final_record = _strict_inventory_entry(parent, candidate)
        if final_record != captured_records.get(candidate.name):
            raise PatcherError("VV5 Running recovery report changed during final recapture")
    return found


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
    _strict_publish_exclusive(tmp, report, parent)
    _validate_report(json.loads(_read(report).decode("utf-8")), parent)
    return report


def _publish(operation: str, destinations: list[Path], pre: dict[Path, tuple[bool, bytes | None]], published: dict[Path, bytes], parent: Path, *, mode: str = VV5_MODE) -> None:
    _require_windows_identity_atomic()
    if mode != VV5_MODE:
        raise PatcherError("VV5 Running supports Collection Progression only.")
    if [Path(destination).name for destination in destinations] != [VV5_EXE_BASENAME, DLL_NAME]:
        raise PatcherError("VV5 Running destinations do not match the certified game/DLL names.")
    parent_identity = _identity(parent)
    registry, registry_identity, registry_created = _registry(parent)
    authority_path: Path | None = None
    authority_token: str | None = None
    authority: dict[str, object] | None = None
    issuance_path: Path | None = None
    issuance_token = uuid.uuid4().hex
    try:
        # A registry is a single active-transaction lock.  Existing authority
        # is valid only when it is the sole child; any issuance, pointer,
        # successor, temporary, or foreign child rejects before publication.
        existing = _registry_members(registry)
        if registry_created:
            if existing:
                raise PatcherError("VV5 Running newly created issuance registry is not empty.")
        elif set(existing) != {AUTHORITY_NAME}:
            raise PatcherError("VV5 Running issuance registry already has an active or foreign transaction.")
        authority_path, authority_token, authority = _ensure_authority(registry, registry_identity, registry_created)
        authority_record = authority["record"]
        _assert_registry_members(registry, registry_identity, {AUTHORITY_NAME: authority_record})
        if _identity(parent) != parent_identity:
            raise PatcherError("VV5 Running destination parent changed during issuance setup.")
        issuance_path = registry / f"{issuance_token}.json"
        issuance_payload = _issuance_payload(issuance_token, authority_token, authority_record, operation, parent, destinations, pre, published, registry, registry_identity)
    except Exception:
        # Setup is failure-owned: a registry created by this attempt may be
        # removed only through its captured identities and only while empty.
        if registry_created and authority_path is not None and authority is not None and os.path.lexists(authority_path):
            try:
                _cleanup_issuance_artifacts(registry, registry_identity, [], (authority_path, authority["record"]))
            except Exception as cleanup_exc:
                raise PatcherError("VV5 Running issuance setup failed; authority evidence retained.") from cleanup_exc
        elif registry_created and os.path.lexists(registry):
            try:
                _cleanup_registry(registry, registry_identity)
            except Exception as cleanup_exc:
                raise PatcherError("VV5 Running issuance setup failed; registry evidence retained.") from cleanup_exc
        raise
    assert authority_path is not None and authority_token is not None and authority is not None and issuance_path is not None
    try:
        _write_issuance(issuance_path, issuance_payload)
        issuance_identity = _inventory(parent, issuance_path)
        if issuance_identity is None:
            raise PatcherError("VV5 Running issuance identity could not be captured.")
        _assert_registry_members(
            registry,
            registry_identity,
            {AUTHORITY_NAME: authority["record"], issuance_path.name: issuance_identity},
        )
    except Exception:
        if os.path.lexists(issuance_path):
            try:
                current_issuance = _inventory(parent, issuance_path)
                if current_issuance is not None:
                    _cleanup_issuance_artifacts(
                        registry,
                        registry_identity,
                        [(issuance_path, current_issuance)],
                        (authority_path, authority["record"]) if authority["created"] else None,
                        retain_authority=(authority_path, authority["record"]) if not authority["created"] else None,
                        remove_registry=bool(authority["created"]),
                    )
                elif registry_created and authority["created"]:
                    raise PatcherError("VV5 Running issuance identity could not be captured safely.")
            except Exception as cleanup_exc:
                raise PatcherError("VV5 Running issuance setup failed; authority evidence retained.") from cleanup_exc
        raise
    try:
        if _identity(parent) != parent_identity:
            raise PatcherError("VV5 Running destination parent changed before publication.")
        _assert_registry_members(
            registry,
            registry_identity,
            {AUTHORITY_NAME: authority["record"], issuance_path.name: issuance_identity},
        )
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
                "destination_exe_basename": VV5_EXE_BASENAME,
                "companion_dll_basename": DLL_NAME,
                "member_roles": {VV5_EXE_BASENAME: "game_executable", DLL_NAME: "companion_dll"},
                "issuance_token": issuance_token,
                "issuance_name": f"{ISSUANCE_REGISTRY_NAME}/{issuance_path.name}",
                "issuance_registry_relative": ISSUANCE_REGISTRY_NAME,
                "issuance_registry_identity": registry_identity,
                "issuance_identity": {"record": issuance_identity, "authority_token": authority_token, "authority_record": authority["record"]},
                "vv5_schema": "vv5_running_recovery_v2",
                "destination_parent_absolute": _canonical(parent),
                "destination_paths_absolute": [_canonical(p) for p in destinations],
            },
        )
    except Exception as exc:
        if _identity(parent) != parent_identity:
            raise PatcherError("VV5 Running destination parent changed during publication; evidence retained.") from exc
        try:
            _assert_registry_members(
                registry,
                registry_identity,
                {AUTHORITY_NAME: authority["record"], issuance_path.name: issuance_identity},
            )
        except Exception as registry_exc:
            raise PatcherError("VV5 Running issuance registry changed during publication; evidence retained.") from registry_exc
        reports = []
        for candidate in _discover_reports(parent, issuance_token=issuance_token):
            raw = json.loads(_read(candidate).decode("utf-8"))
            if raw.get("kind") == "emergency_recovery_marker":
                bound_payload = dict(raw.get("recovery_payload") or {})
                bound_payload.update({"recovery_root_name": raw.get("recovery_root_name"), "recovery_root_identity": raw.get("recovery_root_identity")})
                reports.append((candidate, bound_payload))
            else:
                reports.append((candidate, raw))
        if len(reports) == 1:
            try:
                bound_identity = _bind_issuance(issuance_path, issuance_token, reports[0][0], reports[0][1], issuance_identity)
                if bound_identity is None:
                    raise PatcherError("VV5 Running issuance binding identity is missing.")
            except Exception as bind_exc:
                raise PatcherError("VV5 Running recovery issuance binding failed; report and issuance retained.") from bind_exc
        elif len(reports) > 1:
            raise PatcherError("VV5 Running recovery issuance is ambiguous; evidence retained.") from exc
        elif os.path.lexists(issuance_path):
            _cleanup_issuance_artifacts(
                registry,
                registry_identity,
                [(issuance_path, issuance_identity)],
                (authority_path, authority["record"]) if authority["created"] else None,
                retain_authority=(authority_path, authority["record"]) if not authority["created"] else None,
                remove_registry=bool(authority["created"]),
            )
        raise
    # The strict transaction is the sole production path.  Once it has
    # returned, bind no legacy replay implementation: verify and remove only
    # the originally captured issuance record, then return immediately.
    pointer_info = _load_issuance_pointer(issuance_path, issuance_identity)
    artifacts = [(issuance_path, issuance_identity)]
    if pointer_info is not None:
        artifacts.extend([(pointer_info[0], pointer_info[1]), (pointer_info[2], pointer_info[3])])
    _assert_registry_members(
        registry,
        registry_identity,
        {authority_path.name: authority["record"], **{path.name: record for path, record in artifacts}},
    )
    _cleanup_issuance_artifacts(
        registry,
        registry_identity,
        artifacts,
        (authority_path, authority["record"]) if authority["created"] else None,
        retain_authority=(authority_path, authority["record"]) if not authority["created"] else None,
        remove_registry=bool(authority["created"]),
    )
    return


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
    # Validate the complete ancestor chain before touching the caller-supplied
    # report itself.  This prevents a reparse/junction parent from redirecting
    # the first lexists/lstat or any subsequent recovery mutation.
    _validate_recovery_ancestors(report)
    supplied_st = os.lstat(report) if os.path.lexists(report) else None
    if supplied_st is None:
        raise PatcherError("VV5 Running recovery report is missing.")
    if stat.S_ISDIR(supplied_st.st_mode):
        _validate_recovery_siblings(report)
    else:
        _validate_recovery_siblings(report.parent, selected=report.name)
    if stat.S_ISDIR(supplied_st.st_mode):
        _safe_ancestors(report)
        directory_record = _strict_inventory_entry(report.parent, report)
        canonical = []
        emergency = []
        successor = []
        with os.scandir(report) as entries:
            for entry in entries:
                name = entry.name
                if not name.startswith(".vv5run-"):
                    continue
                candidate = Path(entry.path)
                entry_st = os.lstat(candidate)
                if name == ISSUANCE_REGISTRY_NAME:
                    if stat.S_ISLNK(entry_st.st_mode) or _unsafe(entry_st) or not stat.S_ISDIR(entry_st.st_mode):
                        raise PatcherError("VV5 Running issuance registry is unsafe during report discovery")
                    continue
                if re.fullmatch(r"\.vv5run-recovery-[0-9a-f]{32}", name):
                    if stat.S_ISLNK(entry_st.st_mode) or _unsafe(entry_st) or not stat.S_ISDIR(entry_st.st_mode):
                        raise PatcherError("VV5 Running recovery root is unsafe during report discovery")
                    continue
                if stat.S_ISLNK(entry_st.st_mode) or _unsafe(entry_st) or not stat.S_ISREG(entry_st.st_mode):
                    raise PatcherError(f"VV5 Running recovery chain contains an unsafe member: {name}")
                if re.fullmatch(r"\.vv5run-(?:recovery|emergency)-[0-9a-f]{32}\.json\.pointer", name):
                    continue
                if re.fullmatch(r"\.vv5run-recovery-[0-9a-f]{32}\.json", name):
                    canonical.append(candidate)
                elif re.fullmatch(r"\.vv5run-recovery-[0-9a-f]{32}\.v[0-9a-f]{32}\.json", name):
                    successor.append(candidate)
                elif re.fullmatch(r"\.vv5run-emergency-[0-9a-f]{32}\.json", name):
                    emergency.append(candidate)
                else:
                    raise PatcherError(f"VV5 Running recovery chain contains an unknown report member: {name}")
        if _strict_inventory_entry(report.parent, report) != directory_record:
            raise PatcherError("VV5 Running recovery report directory changed during discovery.")
        if successor and not canonical:
            raise PatcherError("VV5 Running versioned recovery successor is orphaned.")
        if len(emergency) > 1 or (emergency and (canonical or successor)):
            raise PatcherError("VV5 Running recovery authority chain is ambiguous.")
        if emergency:
            report = emergency[0]
        elif len(canonical) == 1:
            report = canonical[0]
        else:
            raise PatcherError("VV5 Running recovery report is ambiguous.")
    if not (report.name.startswith(".vv5run-recovery-") or report.name.startswith(".vv5run-emergency-")):
        raise PatcherError("VV5 Running recovery report owner is invalid.")
    _safe_ancestors(report.parent)
    report_parent_before = _identity(report.parent)
    report_bytes = _read(report)
    report_record_before = _inventory(report.parent, report)
    if report_record_before is None:
        raise PatcherError("VV5 Running recovery report disappeared during capture.")
    report_sha256 = _sha(report_bytes)
    raw_loaded = json.loads(report_bytes.decode("utf-8"))
    is_emergency = isinstance(raw_loaded, dict) and raw_loaded.get("kind") == "emergency_recovery_marker"
    if is_emergency:
        if not report.name.startswith(".vv5run-emergency-") or not isinstance(raw_loaded.get("recovery_payload"), dict):
            raise PatcherError("VV5 Running emergency marker owner is invalid.")
        raw = dict(raw_loaded["recovery_payload"])
        raw.update({
            "recovery_root_name": raw_loaded.get("recovery_root_name"),
            "recovery_root_identity": raw_loaded.get("recovery_root_identity"),
            "ownership_inventory": raw_loaded.get("ownership_inventory"),
            "report_name": report.name,
            "report_parent_identity": _identity(report.parent),
        })
    else:
        raw = raw_loaded
    if any(raw.get(k) != v for k, v in {
        "feature_owner": VV5_FEATURE_OWNER,
        "mode": VV5_MODE,
        "parent_sha256": VV5_PARENT_EXE_SHA256,
        "candidate_sha256": VV5_CANDIDATE_EXE_SHA256,
        "destination_exe_basename": VV5_EXE_BASENAME,
        "companion_dll_basename": DLL_NAME,
        "member_roles": {VV5_EXE_BASENAME: "game_executable", DLL_NAME: "companion_dll"},
    }.items()):
        raise PatcherError("VV5 Running recovery report identity mismatch.")
    issuance_name = raw.get("issuance_name")
    issuance_token = raw.get("issuance_token")
    expected_issuance_name = f"{ISSUANCE_REGISTRY_NAME}/{issuance_token}.json" if isinstance(issuance_token, str) else None
    if not isinstance(issuance_name, str) or not isinstance(issuance_token, str) or issuance_name != expected_issuance_name:
        raise PatcherError("VV5 Running recovery issuance binding is missing or malformed.")
    registry = report.parent / ISSUANCE_REGISTRY_NAME
    if not os.path.lexists(registry):
        raise PatcherError("VV5 Running issuance registry is missing.")
    registry_st = os.lstat(registry)
    if stat.S_ISLNK(registry_st.st_mode) or _unsafe(registry_st) or not stat.S_ISDIR(registry_st.st_mode):
        raise PatcherError("VV5 Running issuance registry is unsafe.")
    registry_members_before = _registry_members(registry)
    issuance_path = registry / f"{issuance_token}.json"
    if issuance_path.parent != registry or issuance_path.name != f"{issuance_token}.json":
        raise PatcherError("VV5 Running recovery issuance path is unsafe.")
    issuance_meta = raw.get("issuance_identity")
    if not isinstance(issuance_meta, dict) or set(issuance_meta) != {"record", "authority_token", "authority_record"}:
        raise PatcherError("VV5 Running recovery authority binding is missing.")
    issuance_identity = issuance_meta.get("record")
    if not isinstance(issuance_identity, dict) or _inventory(report.parent, issuance_path) != issuance_identity:
        raise PatcherError("VV5 Running recovery issuance record is missing.")
    authority_path = registry / AUTHORITY_NAME
    authority_record = issuance_meta.get("authority_record")
    authority_token = issuance_meta.get("authority_token")
    if not isinstance(authority_record, dict) or not isinstance(authority_token, str):
        raise PatcherError("VV5 Running recovery authority binding is malformed.")
    if _inventory(report.parent, authority_path) != authority_record:
        raise PatcherError("VV5 Running recovery authority identity changed.")
    authority_raw = json.loads(_read(authority_path).decode("utf-8"))
    if (
        not isinstance(authority_raw, dict)
        or set(authority_raw) != {"schema_version", "kind", "feature_owner", "mode", "token", "registry_identity"}
        or authority_raw.get("schema_version") != AUTHORITY_SCHEMA_VERSION
        or authority_raw.get("kind") != "vv5_running_authority"
        or authority_raw.get("feature_owner") != VV5_FEATURE_OWNER
        or authority_raw.get("mode") != VV5_MODE
        or authority_raw.get("token") != authority_token
        or authority_raw.get("registry_identity") != raw.get("issuance_registry_identity")
    ):
        raise PatcherError("VV5 Running recovery authority secret is invalid.")
    issuance_pointer = _load_issuance_pointer(issuance_path, issuance_identity)
    registry_identity = raw.get("issuance_registry_identity")
    if not isinstance(registry_identity, dict):
        raise PatcherError("VV5 Running recovery issuance registry identity is missing.")
    expected_registry = {AUTHORITY_NAME: authority_record, issuance_path.name: issuance_identity}
    if issuance_pointer is not None:
        expected_registry[issuance_pointer[0].name] = _rebase_registry_record(registry, issuance_pointer[0], issuance_pointer[1])
        expected_registry[issuance_pointer[2].name] = _rebase_registry_record(registry, issuance_pointer[2], issuance_pointer[3])
    _assert_registry_members(registry, registry_identity, expected_registry)
    bound_issuance_path = issuance_pointer[0] if issuance_pointer is not None else issuance_path
    bound_issuance_identity = issuance_pointer[1] if issuance_pointer is not None else issuance_identity
    issuance = json.loads(_read(bound_issuance_path).decode("utf-8"))
    root_identity = raw.get("recovery_root_identity")
    report_parent_identity = raw.get("report_parent_identity")
    root_entry = next((item for item in raw.get("ownership_inventory", []) if item.get("type") == "directory" and "/" not in str(item.get("path", ""))), None)
    expected_root_identity = {"st_dev": int(root_entry["st_dev"]), "st_ino": int(root_entry["st_ino"])} if isinstance(root_entry, dict) else None
    root_identity_matches = isinstance(root_identity, dict) and isinstance(expected_root_identity, dict) and root_identity.get("st_dev") == expected_root_identity["st_dev"] and root_identity.get("st_ino") == expected_root_identity["st_ino"]
    if raw.get("report_name") != report.name or raw.get("recovery_root_name") != (Path(str(root_entry["path"])).name if isinstance(root_entry, dict) else None) or not root_identity_matches:
        raise PatcherError("VV5 Running recovery report location identity mismatch.")
    parent_st = os.lstat(report.parent)
    if not isinstance(root_identity, dict) or not isinstance(report_parent_identity, dict) or report_parent_identity != {"st_dev": int(parent_st.st_dev), "st_ino": int(parent_st.st_ino)}:
        raise PatcherError("VV5 Running recovery report root identity mismatch.")
    if raw.get("destination_parent_absolute") != _canonical(report.parent) or raw.get("destination_paths_absolute") != [_canonical(report.parent / VV5_EXE_BASENAME), _canonical(report.parent / DLL_NAME)]:
        raise PatcherError("VV5 Running recovery destination parent/path binding mismatch.")
    if raw.get("issuance_registry_relative") != ISSUANCE_REGISTRY_NAME or registry_identity != _identity(registry):
        raise PatcherError("VV5 Running recovery issuance registry binding mismatch.")
    expected_issuance_operation = "remove" if raw.get("operation") == "removal" else "install"
    if (
        issuance.get("schema_version") != ISSUANCE_SCHEMA_VERSION
        or issuance.get("token") != issuance_token
        or issuance.get("feature_owner") != VV5_FEATURE_OWNER
        or issuance.get("mode") != VV5_MODE
        or issuance.get("operation") != expected_issuance_operation
        or issuance.get("parent_identity") != report_parent_identity
        or issuance.get("report_name") != report.name
        or issuance.get("report_sha256") != report_sha256
        or issuance.get("report_parent_identity") != report_parent_identity
        or issuance.get("recovery_root_name") != raw.get("recovery_root_name")
        or issuance.get("recovery_root_identity") != root_identity
        or issuance.get("report_members") != raw.get("members")
        or issuance.get("destination_parent_absolute") != _canonical(report.parent)
        or issuance.get("destination_paths_absolute") != [_canonical(report.parent / VV5_EXE_BASENAME), _canonical(report.parent / DLL_NAME)]
        or issuance.get("registry_relative") != ISSUANCE_REGISTRY_NAME
        or issuance.get("registry_identity") != _identity(registry)
        or issuance.get("authority_token") != authority_token
        or issuance.get("authority_record") != authority_record
    ):
        raise PatcherError("VV5 Running recovery issuance record does not bind this report.")
    members = raw.get("members")
    if not isinstance(members, list) or [str(item.get("destination_relative")) for item in members] != [VV5_EXE_BASENAME, DLL_NAME]:
        raise PatcherError("VV5 Running recovery member names are not canonical.")
    expected_member_identity = {
        VV5_EXE_BASENAME: {
            "install": (VV5_CANDIDATE_EXE_SHA256, 0xF6000),
            "install_new": (VV5_CANDIDATE_EXE_SHA256, 0xF6000),
            "install_existing": (VV5_CANDIDATE_EXE_SHA256, 0xF6000),
            "removal": (VV5_PARENT_EXE_SHA256, 0xF4000),
        },
        DLL_NAME: {"install": (DLL_SHA256, DLL_SIZE), "install_new": (DLL_SHA256, DLL_SIZE), "install_existing": (DLL_SHA256, DLL_SIZE), "removal": (DLL_SHA256, DLL_SIZE)},
    }
    for member in members:
        name = str(member["destination_relative"])
        if Path(name).parts != (name,) or name not in expected_member_identity:
            raise PatcherError("VV5 Running recovery destination must be a canonical direct child.")
        expected_sha, expected_size = expected_member_identity[name][str(raw.get("operation"))]
        if member.get("published_sha256") != expected_sha or member.get("published_size") != expected_size:
            raise PatcherError("VV5 Running recovery member hash/size identity mismatch.")
        if str(raw.get("operation")) == "install_new":
            if member.get("pre_exists") or member.get("pre_sha256") is not None or member.get("pre_size") != 0:
                raise PatcherError("VV5 Running install_new recovery preimage is not absent.")
        elif str(raw.get("operation")) == "install_existing":
            expected_pre = VV5_PARENT_EXE_SHA256 if name == VV5_EXE_BASENAME else VV5_PARENT_DLL_SHA256
            expected_pre_size = 0xF4000 if name == VV5_EXE_BASENAME else DLL_SIZE
            if not member.get("pre_exists") or member.get("pre_sha256") != expected_pre or member.get("pre_size") != expected_pre_size:
                raise PatcherError("VV5 Running install_existing recovery preimage identity mismatch.")
        elif str(raw.get("operation")) == "removal":
            expected_pre = VV5_CANDIDATE_EXE_SHA256 if name == VV5_EXE_BASENAME else VV5_CANDIDATE_DLL_SHA256
            expected_pre_size = 0xF6000 if name == VV5_EXE_BASENAME else DLL_SIZE
            if not member.get("pre_exists") or member.get("pre_sha256") != expected_pre or member.get("pre_size") != expected_pre_size:
                raise PatcherError("VV5 Running removal recovery preimage identity mismatch.")
    required_metadata = {
        "feature_owner": VV5_FEATURE_OWNER,
        "mode": VV5_MODE,
        "parent_sha256": VV5_PARENT_EXE_SHA256,
        "candidate_sha256": VV5_CANDIDATE_EXE_SHA256,
        "destination_exe_basename": VV5_EXE_BASENAME,
        "companion_dll_basename": DLL_NAME,
        "member_roles": {VV5_EXE_BASENAME: "game_executable", DLL_NAME: "companion_dll"},
        "recovery_root_name": raw.get("recovery_root_name"),
        "recovery_root_identity": root_identity,
        "report_parent_identity": report_parent_identity,
        "issuance_token": issuance_token,
        "issuance_name": issuance_name,
        "issuance_registry_relative": raw.get("issuance_registry_relative"),
        "issuance_registry_identity": raw.get("issuance_registry_identity"),
        "issuance_identity": issuance_meta,
        "vv5_schema": "vv5_running_recovery_v2",
        "destination_parent_absolute": raw.get("destination_parent_absolute"),
        "destination_paths_absolute": raw.get("destination_paths_absolute"),
    }
    if not is_emergency:
        required_metadata["report_name"] = report.name
    if _registry_members(registry) != registry_members_before:
        raise PatcherError("VV5 Running issuance registry changed before replay publication")
    _validate_recovery_siblings(report.parent, selected=report.name)
    if _identity(report.parent) != report_parent_before or _inventory(report.parent, report) != report_record_before:
        raise PatcherError("VV5 Running report/parent changed immediately before replay.")
    if _inventory(report.parent, authority_path) != authority_record or _inventory(report.parent, issuance_path) != issuance_identity:
        raise PatcherError("VV5 Running authority/issuance changed immediately before replay.")
    _strict_recover_atomic(
        report,
        recovery_prefix=".vv5run",
        required_metadata=required_metadata,
        expected_report_sha256=report_sha256,
    )
    # The shared strict replay is the sole recovery implementation.  Its
    # return means the pair, report, and owned recovery tree have passed full
    # verification.  Only then may the originally captured issuance record be
    # removed; any substitution/race is a fail-closed error.
    if _identity(report.parent) != report_parent_before:
        raise PatcherError("VV5 Running destination parent changed during recovery.")
    if _inventory(report.parent, issuance_path) != issuance_identity or (issuance_pointer is not None and _load_issuance_pointer(issuance_path, issuance_identity) is None):
        raise PatcherError("VV5 Running issuance record changed during replay.")
    artifacts = [(issuance_path, issuance_identity)]
    if issuance_pointer is not None:
        current_pointer = _load_issuance_pointer(issuance_path, issuance_identity)
        if current_pointer is None:
            raise PatcherError("VV5 Running issuance pointer disappeared during replay.")
        artifacts.extend([(current_pointer[0], current_pointer[1]), (current_pointer[2], current_pointer[3])])
    _assert_registry_members(
        registry,
        registry_identity,
        {
            authority_path.name: _rebase_registry_record(registry, authority_path, authority_record),
            **{path.name: _rebase_registry_record(registry, path, record) for path, record in artifacts},
        },
    )
    _cleanup_issuance_artifacts(registry, registry_identity, artifacts, (authority_path, authority_record))
    return


def install_atomic(source: Path, destination: Path, mode: str, *, companion_source: Path | None = None, companion_destination: Path | None = None) -> None:
    _require_windows_identity_atomic()
    if mode != VV5_MODE:
        raise PatcherError("VV5 Running supports Collection Progression only.")
    if companion_source is None or companion_destination is None:
        raise PatcherError("VV5 Running companion is mandatory.")
    if Path(destination).name != VV5_EXE_BASENAME or Path(companion_destination).name != DLL_NAME:
        raise PatcherError("VV5 Running destinations do not match the certified game/DLL names.")
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
    _require_windows_identity_atomic()
    if mode != VV5_MODE:
        raise PatcherError("VV5 Running supports Collection Progression only.")
    if companion_destination is None or companion_restore_source is None:
        raise PatcherError("VV5 Running removal companion arguments are mandatory.")
    if Path(destination).name != VV5_EXE_BASENAME or Path(companion_destination).name != DLL_NAME:
        raise PatcherError("VV5 Running destinations do not match the certified game/DLL names.")
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
