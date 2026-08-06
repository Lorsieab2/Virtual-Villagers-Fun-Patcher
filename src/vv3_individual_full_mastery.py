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
    except OSError as exc:
        raise PatcherError(f"VV3 individual Full Mastery file fsync failed: {path}") from exc
    finally:
        os.close(fd)


def _fsync_dir(path: Path) -> None:
    """Flush a directory when the platform exposes directory fsync.

    Windows does not expose directory handles through ``os.open``; that is a
    capability limitation rather than a swallowed fsync error.  Any actual
    ``fsync`` failure is fail-closed.
    """
    try:
        fd = os.open(os.fspath(path), os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            try:
                os.fsync(fd)
            except OSError as exc:
                raise PatcherError(f"VV3 individual Full Mastery directory fsync failed: {path}") from exc
        finally:
            os.close(fd)
    except OSError:
        if os.name != "nt":
            raise


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
    _validate_recovery_payload(payload, parent)
    _write_file(tmp, (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    os.replace(tmp, report)
    _fsync_dir(parent)
    _validate_recovery_payload(json.loads(_read_regular(report).decode("utf-8")), parent)
    return report


def _relative_owned(root: Path, path: Path | None) -> str | None:
    if path is None:
        return None
    try:
        rel = Path(os.path.abspath(os.fspath(path))).relative_to(Path(os.path.abspath(os.fspath(root))))
    except ValueError as exc:
        raise PatcherError("VV3 individual Full Mastery recovery path escapes its root.") from exc
    if rel.is_absolute() or not rel.parts or ".." in rel.parts:
        raise PatcherError("VV3 individual Full Mastery recovery path is unsafe.")
    return rel.as_posix()


def _inventory_member(root: Path, path: Path | None) -> dict[str, object] | None:
    if path is None or not os.path.lexists(path):
        return None
    data = _read_regular(path)
    st = os.lstat(path)
    return {
        "path": _relative_owned(root, path),
        "type": "regular_file",
        "size": len(data),
        "sha256": _sha(data),
        "st_dev": int(getattr(st, "st_dev", 0)),
        "st_ino": int(getattr(st, "st_ino", 0)),
    }


def _validate_recovery_payload(payload: dict[str, object], root: Path) -> None:
    required = {"schema_version", "operation", "recovery_root", "destination_parent", "initial_precondition", "replay_guard", "members", "ownership_inventory", "failure_diagnostic"}
    if not isinstance(payload, dict) or set(payload) != required or payload.get("schema_version") != 2:
        raise PatcherError("VV3 individual Full Mastery recovery schema is unsupported or ambiguous.")
    if payload["operation"] not in {"install_new", "install_existing", "removal"} or payload["recovery_root"] != "." or payload["destination_parent"] != ".":
        raise PatcherError("VV3 individual Full Mastery recovery operation/root contract is invalid.")
    initial = payload["initial_precondition"]
    if not isinstance(initial, dict) or set(initial) != {"kind", "members"} or initial["kind"] not in {"absent", "pair"}:
        raise PatcherError("VV3 individual Full Mastery initial precondition is invalid.")
    if payload["operation"] == "install_new" and initial["kind"] != "absent":
        raise PatcherError("install_new requires an immutable absent precondition.")
    if payload["operation"] != "install_new" and initial["kind"] != "pair":
        raise PatcherError("VV3 recovery operation requires an owned pair precondition.")
    members = payload["members"]
    if not isinstance(members, list) or len(members) != 2:
        raise PatcherError("VV3 individual Full Mastery recovery requires exactly two members.")
    member_keys = {"destination_relative", "destination_type", "pre_exists", "pre_sha256", "pre_size", "published_sha256", "published_size", "backup_relative", "stage_relative", "backup_inventory", "stage_inventory"}
    seen: set[str] = set()
    for member in members:
        if not isinstance(member, dict) or set(member) != member_keys or member["destination_type"] != "regular_file":
            raise PatcherError("VV3 individual Full Mastery recovery member schema is invalid.")
        rel = Path(str(member["destination_relative"]))
        key = rel.as_posix().casefold()
        if rel.is_absolute() or not rel.parts or ".." in rel.parts or key in seen:
            raise PatcherError("VV3 individual Full Mastery recovery path is escaped or duplicated.")
        seen.add(key)
        for field in ("backup_relative", "stage_relative"):
            value = member[field]
            if value is not None:
                p = Path(str(value))
                if p.is_absolute() or ".." in p.parts or not p.parts:
                    raise PatcherError("VV3 individual Full Mastery recovery owned path is unsafe.")
        for field in ("pre_sha256", "published_sha256"):
            if member[field] is not None and (not isinstance(member[field], str) or len(member[field]) != 64):
                raise PatcherError("VV3 individual Full Mastery recovery hash is malformed.")
        for field in ("pre_size", "published_size"):
            if not isinstance(member[field], int) or member[field] < 0:
                raise PatcherError("VV3 individual Full Mastery recovery size is malformed.")
        for field in ("backup_inventory", "stage_inventory"):
            inv = member[field]
            if inv is not None:
                if not isinstance(inv, dict) or set(inv) != {"path", "type", "size", "sha256", "st_dev", "st_ino"} or inv["type"] != "regular_file":
                    raise PatcherError("VV3 individual Full Mastery recovery inventory is malformed.")
    inventory = payload["ownership_inventory"]
    if not isinstance(inventory, list):
        raise PatcherError("VV3 individual Full Mastery recovery ownership inventory is malformed.")
    seen_inventory: set[str] = set()
    for item in inventory:
        if not isinstance(item, dict) or set(item) != {"path", "type", "size", "sha256", "st_dev", "st_ino"} or item["type"] != "regular_file":
            raise PatcherError("VV3 individual Full Mastery recovery ownership item is malformed.")
        rel = Path(str(item["path"]))
        key = rel.as_posix().casefold()
        if rel.is_absolute() or not rel.parts or ".." in rel.parts or key in seen_inventory:
            raise PatcherError("VV3 individual Full Mastery recovery ownership path is unsafe or duplicated.")
        seen_inventory.add(key)


def _remove_owned(path: Path) -> None:
    if not os.path.lexists(path):
        return
    st = os.lstat(path)
    if stat.S_ISLNK(st.st_mode) or _unsafe_stat(st) or not stat.S_ISREG(st.st_mode):
        raise PatcherError(f"VV3 individual Full Mastery unsafe cleanup member: {path}")
    # Recheck identity/type/hash immediately before unlinking owned material.
    checked = _read_regular(path)
    st2 = os.lstat(path)
    if stat.S_ISLNK(st2.st_mode) or _unsafe_stat(st2) or not stat.S_ISREG(st2.st_mode) or st2.st_size != len(checked):
        raise PatcherError(f"VV3 individual Full Mastery cleanup identity changed: {path}")
    path.unlink()


def _copy_preserved(source: Path, target: Path, expected: bytes) -> None:
    _write_file(target, expected)
    if _read_regular(target) != expected:
        raise PatcherError(f"VV3 individual Full Mastery copy verification failed: {target}")


def _replace_verified(stage: Path, destination: Path, expected_destination: tuple[bool, bytes | None], expected_stage: bytes) -> None:
    """Perform a replace only after immediate no-follow identity/hash checks."""
    if _state(destination) != expected_destination:
        raise PatcherError(f"VV3 individual Full Mastery destination race: {destination}")
    if _read_regular(stage) != expected_stage:
        raise PatcherError(f"VV3 individual Full Mastery stage race: {stage}")
    os.replace(stage, destination)


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
            _replace_verified(stage, path, current, original or b"")
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
            _replace_verified(stages[p], p, pre[p], published[p])
        if any(_state(p) != (True, published[p]) for p in destinations):
            raise PatcherError("VV3 individual Full Mastery publication postverify failed.")
        # Backups/stages become cleanup-eligible only after complete pair
        # postverification, never merely after the second replace call.
        committed = True
    except Exception as exc:
        restored = {}
        for p in destinations:
            restored[p] = _restore_member(p, *pre[p], published[p], backup=backups.get(p))
        if all(restored.values()) and all(_state(p) == pre[p] for p in destinations):
            for p in (*stages.values(), *backups.values()):
                if os.path.lexists(p):
                    _remove_owned(p)
            _fsync_dir(parent)
            raise PatcherError(f"VV3 individual Full Mastery {operation} publication failed; pair restored") from exc
        else:
            report_operation = "removal" if operation == "remove" else ("install_existing" if any(pre[p][0] for p in destinations) else "install_new")
            member_records = []
            for p in destinations:
                backup = backups.get(p)
                stage = stages[p]
                member_records.append({
                    "destination_relative": _relative_owned(parent, p),
                    "destination_type": "regular_file",
                    "pre_exists": bool(pre[p][0]),
                    "pre_sha256": _sha(pre[p][1]) if pre[p][1] is not None else None,
                    "pre_size": len(pre[p][1]) if pre[p][1] is not None else 0,
                    "published_sha256": _sha(published[p]),
                    "published_size": len(published[p]),
                    "backup_relative": _relative_owned(parent, backup),
                    "stage_relative": _relative_owned(parent, stage),
                    "backup_inventory": _inventory_member(parent, backup),
                    "stage_inventory": _inventory_member(parent, stage),
                })
            report = _write_recovery(parent, {
                "operation": report_operation,
                "recovery_root": ".",
                "destination_parent": ".",
                "initial_precondition": {
                    "kind": "absent" if report_operation == "install_new" else "pair",
                    "members": [{"path": _relative_owned(parent, p), "exists": bool(pre[p][0]), "sha256": _sha(pre[p][1]) if pre[p][1] is not None else None, "size": len(pre[p][1]) if pre[p][1] is not None else 0} for p in destinations],
                },
                "replay_guard": "published_or_initial",
                "members": member_records,
                "ownership_inventory": [m for rec in member_records for m in (rec["backup_inventory"], rec["stage_inventory"]) if m is not None],
                "failure_diagnostic": str(exc),
            })
            raise PatcherError(f"VV3 individual Full Mastery transaction failed; recovery retained at {report}") from exc
    finally:
        if committed:
            for p in (*stages.values(), *backups.values()):
                if os.path.lexists(p):
                    _remove_owned(p)
            _fsync_dir(parent)


def recover_atomic(report_or_root: Path) -> None:
    """Replay schema-v2 evidence with relative no-follow ownership checks."""
    report = Path(report_or_root)
    if report.is_dir():
        reports = [p for p in os.scandir(report) if p.name.startswith(".vv3im-recovery-") and p.name.endswith(".json")]
        if len(reports) != 1:
            raise PatcherError("VV3 individual Full Mastery recovery report is ambiguous.")
        report = Path(reports[0].path)
    _safe_ancestor_chain(report.parent)
    payload = json.loads(_read_regular(report).decode("utf-8"))
    _validate_recovery_payload(payload, report.parent)
    root = report.parent
    for item in payload["ownership_inventory"]:
        owned = root / str(item["path"])
        if not os.path.lexists(owned) or _unsafe_stat(os.lstat(owned)) or _sha(_read_regular(owned)) != item["sha256"] or os.lstat(owned).st_size != item["size"]:
            raise PatcherError("VV3 individual Full Mastery recovery ownership inventory changed.")
    members = payload["members"]
    resolved: list[tuple[dict[str, object], Path, Path | None]] = []
    for member in members:
        destination = root / str(member["destination_relative"])
        backup = root / str(member["backup_relative"]) if member["backup_relative"] else None
        stage = root / str(member["stage_relative"]) if member["stage_relative"] else None
        _safe_ancestor_chain(destination.parent)
        if backup is not None:
            _safe_ancestor_chain(backup.parent)
            if not os.path.lexists(backup) or _sha(_read_regular(backup)) != member["pre_sha256"] or len(_read_regular(backup)) != member["pre_size"]:
                raise PatcherError("VV3 individual Full Mastery recovery backup mismatch.")
        current = _state(destination)
        pre_exists = bool(member["pre_exists"])
        if current[0] and _sha(current[1] or b"") not in {member["published_sha256"], member["pre_sha256"]}:
            raise PatcherError("VV3 individual Full Mastery recovery destination is foreign.")
        if not current[0] and pre_exists:
            raise PatcherError("VV3 individual Full Mastery recovery destination is unexpectedly absent.")
        resolved.append((member, destination, backup))
    # Stage every restore before replacing either member; backups remain intact.
    stages: list[tuple[dict[str, object], Path, Path]] = []
    try:
        for member, destination, backup in resolved:
            if not member["pre_exists"]:
                continue
            data = _read_regular(backup) if backup is not None else b""
            stage = root / f".{destination.name}.vv3im-replay-{uuid.uuid4().hex}.stage"
            _write_file(stage, data)
            if _sha(_read_regular(stage)) != member["pre_sha256"]:
                raise PatcherError("VV3 individual Full Mastery replay stage mismatch.")
            stages.append((member, destination, stage))
        for member, destination, backup in resolved:
            current = _state(destination)
            if current[0] and _sha(current[1] or b"") not in {member["published_sha256"], member["pre_sha256"]}:
                raise PatcherError("VV3 individual Full Mastery replay race detected.")
        for member, destination, stage in stages:
            if _state(destination)[0] and _sha(_read_regular(destination)) == member["pre_sha256"]:
                continue
            if _sha(_read_regular(stage)) != member["pre_sha256"]:
                raise PatcherError("VV3 individual Full Mastery replay stage changed.")
            _replace_verified(stage, destination, _state(destination), _read_regular(stage))
        for member, destination, backup in resolved:
            if member["pre_exists"]:
                if _state(destination) != (True, _read_regular(backup)):
                    raise PatcherError("VV3 individual Full Mastery replay postverify failed.")
            elif os.path.lexists(destination):
                _remove_owned(destination)
        for member, destination, backup in resolved:
            if member["pre_exists"] and _state(destination)[1] != _read_regular(backup):
                raise PatcherError("VV3 individual Full Mastery replay pair verification failed.")
        for member, destination, backup in resolved:
            if backup is not None and os.path.lexists(backup):
                _remove_owned(backup)
        _remove_owned(report)
    except Exception:
        # Never consume backups or delete evidence on a failed replay.
        raise


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
