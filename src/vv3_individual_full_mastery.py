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
import re
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

# Recovery metadata is intentionally caller-specific.  The shared writer may
# transport both callers, but it must never accept a permissive union of their
# security bindings.  VV3 has an owned-root issuance; VV5 has an external
# parent-registry issuance and its own schema marker.
VV3_RECOVERY_METADATA_REQUIRED = {
    "feature_owner", "mode", "parent_sha256", "candidate_sha256",
    "destination_exe_basename", "companion_dll_basename", "member_roles",
    "recovery_root_name", "recovery_root_identity", "report_name",
    "report_parent_identity", "issuance_token", "issuance_name",
    "issuance_identity", "destination_parent_absolute",
    "destination_paths_absolute",
}
VV3_RECOVERY_METADATA_FORBIDDEN = {
    "issuance_registry_relative", "issuance_registry_identity", "vv5_schema",
}
VV5_RECOVERY_METADATA_REQUIRED = {
    "feature_owner", "mode", "parent_sha256", "candidate_sha256",
    "destination_exe_basename", "companion_dll_basename", "member_roles",
    "recovery_root_name", "recovery_root_identity", "report_name",
    "report_parent_identity", "issuance_token", "issuance_name",
    "issuance_registry_relative", "issuance_registry_identity",
    "issuance_identity", "destination_parent_absolute",
    "destination_paths_absolute", "vv5_schema",
}


def _validate_emergency_binding_payload(payload: dict[str, object], *, owner: str) -> None:
    """Require durable embedded bindings; never infer them from marker path."""
    if owner == "vv3_individual_full_mastery":
        required = VV3_RECOVERY_METADATA_REQUIRED
        forbidden = VV3_RECOVERY_METADATA_FORBIDDEN
    elif owner == "vv5_individual_grant_running_candidate":
        required = VV5_RECOVERY_METADATA_REQUIRED
        forbidden = set()
    else:
        raise PatcherError("Current emergency marker feature owner is unsupported.")
    base = {
        "schema_version", "operation", "recovery_root", "destination_parent",
        "report_relative", "initial_precondition", "replay_guard", "members",
        "ownership_inventory", "failure_diagnostic",
    }
    missing = required - set(payload)
    if missing or forbidden.intersection(payload) or set(payload) != base | required:
        raise PatcherError("Current emergency marker lacks the exact caller binding schema.")
    root_name = payload.get("recovery_root_name")
    root_identity = payload.get("recovery_root_identity")
    parent_identity = payload.get("report_parent_identity")
    destination_parent = payload.get("destination_parent_absolute")
    issuance_token = payload.get("issuance_token")
    issuance_name = payload.get("issuance_name")
    issuance_identity = payload.get("issuance_identity")
    if (
        not isinstance(root_name, str) or not isinstance(root_identity, dict)
        or not isinstance(parent_identity, dict) or not isinstance(destination_parent, str)
        or not isinstance(issuance_token, str) or not re.fullmatch(r"[0-9a-f]{32}", issuance_token)
        or not isinstance(issuance_name, str) or not isinstance(issuance_identity, dict)
        or not isinstance(payload.get("member_roles"), dict)
        or not isinstance(payload.get("destination_paths_absolute"), list)
    ):
        raise PatcherError("Current emergency marker contains incomplete durable bindings.")


def _require_windows_identity_atomic() -> None:
    if os.name != "nt" or struct.calcsize("P") != 8:
        raise PatcherError("VV3 individual Full Mastery identity-atomic mutation is certified only on 64-bit Windows.")


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


def _reject_entry(path: Path, st: os.stat_result, *, directory: bool | None = None) -> None:
    """Reject every link/reparse/mount and enforce the expected entry type."""
    if stat.S_ISLNK(st.st_mode) or _unsafe_stat(st):
        raise PatcherError(f"VV3 individual Full Mastery reparse/symlink entry: {path}")
    if getattr(path, "is_junction", lambda: False)():
        raise PatcherError(f"VV3 individual Full Mastery junction entry: {path}")
    if path != Path(os.path.abspath(os.fspath(path))) and not path.is_absolute():
        raise PatcherError(f"VV3 individual Full Mastery non-canonical entry: {path}")
    # Do not reject the volume root itself; reject mount-point descendants.
    if path.parent != path and str(path) != path.anchor and os.path.ismount(path):
        raise PatcherError(f"VV3 individual Full Mastery mount entry: {path}")
    if directory is True and not stat.S_ISDIR(st.st_mode):
        raise PatcherError(f"VV3 individual Full Mastery directory type changed: {path}")
    if directory is False and not stat.S_ISREG(st.st_mode):
        raise PatcherError(f"VV3 individual Full Mastery regular-file type changed: {path}")


def _validate_recovery_root(path: Path) -> Path:
    """Validate a supplied recovery root before any is_dir/scandir operation."""
    absolute = Path(os.path.abspath(os.fspath(path)))
    _safe_ancestor_chain(absolute.parent)
    if not os.path.lexists(absolute):
        raise PatcherError(f"VV3 individual Full Mastery recovery root is missing: {absolute}")
    st = os.lstat(absolute)
    _reject_entry(absolute, st, directory=True)
    return absolute


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
        if item.parent != item and str(item) != item.anchor and os.path.ismount(item):
            raise PatcherError(f"VV3 individual Full Mastery mount ancestor: {item}")
        if item != absolute and not stat.S_ISDIR(st.st_mode):
            raise PatcherError(f"VV3 individual Full Mastery non-directory ancestor: {item}")
        if getattr(item, "is_junction", lambda: False)():
            raise PatcherError(f"VV3 individual Full Mastery junction ancestor: {item}")


def _read_regular(path: Path) -> bytes:
    """No-follow read with identity checks before and after hashing."""
    _safe_ancestor_chain(path.parent)
    if os.name != "nt" and not hasattr(os, "O_NOFOLLOW"):
        raise PatcherError("VV3 individual Full Mastery no-follow capability is unavailable.")
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
    _require_windows_identity_atomic()
    _safe_ancestor_chain(path.parent)
    with open(path, "xb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    _fsync_dir(path.parent)


def _validate_emergency_root(parent: Path, details: dict[str, object], *, inventory: list[dict[str, object]] | None = None) -> tuple[Path, dict[str, object], list[dict[str, object]]]:
    prefix = str(details.get("_report_prefix", ".vv3im"))
    root_name = details.get("_recovery_root_name")
    if not isinstance(root_name, str) or Path(root_name).name != root_name or root_name in {".", ".."} or not re.fullmatch(re.escape(prefix) + r"-recovery-[0-9a-f]{32}", root_name):
        raise PatcherError("VV3 individual Full Mastery emergency recovery root name is unsafe.")
    root = parent / root_name
    if not os.path.lexists(root):
        raise PatcherError("VV3 individual Full Mastery emergency recovery root is missing.")
    root_record = _inventory_entry(parent, root)
    expected_root = details.get("_recovery_root_identity")
    if not isinstance(expected_root, dict) or root_record.get("st_dev") != int(expected_root.get("st_dev", -1)) or root_record.get("st_ino") != int(expected_root.get("st_ino", -1)):
        raise PatcherError("VV3 individual Full Mastery emergency recovery root identity changed.")
    actual = inventory if inventory is not None else _inventory_tree(root)
    owned = [{**item, "path": _relative_owned(parent, root / str(item["path"]))} for item in actual]
    owned.insert(0, root_record)
    expected_owned = details.get("_expected_ownership_inventory")
    if isinstance(expected_owned, list):
        _require_inventory_subset(owned, expected_owned)
    return root, root_record, owned


def _write_emergency_marker(parent: Path, details: dict[str, object], error: BaseException) -> Path:
    """Retain identity-bound evidence when canonical report publication fails."""
    _require_windows_identity_atomic()
    prefix = str(details.get("_report_prefix", ".vv3im"))
    marker = parent / f"{prefix}-emergency-{uuid.uuid4().hex}.json"
    root, root_record, inventory = _validate_emergency_root(parent, details)
    recovery_payload = {key: value for key, value in details.items() if not key.startswith("_")}
    owner = recovery_payload.get("feature_owner")
    if not isinstance(owner, str):
        raise PatcherError("Current emergency marker feature owner is missing.")
    # Marker creation is allowed to persist bindings captured by the failed
    # transaction, but it may not invent role/path/security fields from the
    # marker's current location.  Reconstruction later accepts only this
    # embedded durable envelope.
    recovery_payload["recovery_root_name"] = root.name
    recovery_payload["recovery_root_identity"] = root_record
    # When canonical publication failed before it could allocate a report,
    # this marker is the issued report object.  Persist that exact name in the
    # embedded envelope; recovery never derives it later from marker location.
    recovery_payload.setdefault("report_name", marker.name)
    # Structural report fields are persisted in the marker as a complete
    # schema-v2 envelope even when canonical writer failed before assembling
    # them.  These are not inferred security bindings.
    recovery_payload.setdefault("schema_version", 2)
    recovery_payload.setdefault("recovery_root", ".")
    recovery_payload.setdefault("destination_parent", ".")
    recovery_payload.setdefault("report_relative", marker.name)
    recovery_payload.setdefault("failure_diagnostic", str(error))
    _validate_emergency_binding_payload(recovery_payload, owner=owner)
    payload = {
        "schema_version": 1,
        "kind": "emergency_recovery_marker",
        "feature_owner": owner,
        "operation": details.get("operation"),
        "recovery_root_name": root.name,
        "recovery_root_identity": root_record,
        "ownership_inventory": inventory,
        "expected_ownership_inventory": details.get("_expected_ownership_inventory"),
        "recovery_payload": recovery_payload,
        "failure": str(error),
        "canonical_report_target": f"{prefix}-recovery-*.json",
    }
    tmp = marker.with_suffix(".tmp")
    try:
        _write_file(tmp, (json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n").encode("utf-8"))
        tmp_identity = _inventory_entry(parent, tmp)
        _publish_exclusive(tmp, marker, parent)
        manifest_payload = dict(payload)
        recovery_payload = payload.get("recovery_payload") if isinstance(payload.get("recovery_payload"), dict) else {}
        manifest_payload["ownership_inventory"] = recovery_payload.get("ownership_inventory", payload.get("ownership_inventory"))
        manifest_payload["members"] = recovery_payload.get("members", [])
        manifest_payload["member_roles"] = recovery_payload.get("member_roles") or {}
        manifest_payload["destination_paths_absolute"] = recovery_payload.get("destination_paths_absolute")
        _write_chain_manifest(marker, manifest_payload, marker_name=marker.name, commit_state="emergency_marker")
        _fsync_dir(parent)
        return marker
    except Exception:
        if os.path.lexists(tmp):
            try:
                _remove_owned(tmp, expected=locals().get("tmp_identity"))
            except Exception:
                pass
        raise


def _write_recovery_impl(parent: Path, details: dict[str, object]) -> Path:
    _require_windows_identity_atomic()
    report_prefix = str(details.get("_report_prefix", ".vv3im"))
    payload_details = {key: value for key, value in details.items() if not key.startswith("_")}
    report = parent / f"{report_prefix}-recovery-{uuid.uuid4().hex}.json"
    tmp = report.with_suffix(".tmp")
    payload = {"schema_version": 2, **payload_details, "report_relative": report.name}
    # Metadata is caller-owned.  Do not expose one permissive union to every
    # writer: each feature owner gets an explicit schema, and an unknown owner
    # cannot smuggle arbitrary fields through the shared report writer.
    metadata_schemas = {
        "vv3_individual_full_mastery": set(VV3_RECOVERY_METADATA_REQUIRED),
        "vv5_individual_grant_running_candidate": set(VV5_RECOVERY_METADATA_REQUIRED),
    }
    feature_owner = payload_details.get("feature_owner")
    metadata_keys = metadata_schemas.get(str(feature_owner), set())
    # Current production reports must carry an explicit caller identity.  The
    # old owner-less envelope is not a migration path: accepting it here would
    # let a report reach the authority writer without independently bound
    # issuance evidence.
    if str(feature_owner) not in metadata_schemas:
        raise PatcherError("Current recovery metadata owner is missing or unsupported.")
    if "feature_owner" in payload_details:
        root_name = details.get("_recovery_root_name")
        root_identity = details.get("_recovery_root_identity")
        if not isinstance(root_name, str) or not isinstance(root_identity, dict):
            raise PatcherError("VV3 individual Full Mastery recovery root identity is missing.")
        parent_st = os.lstat(parent)
        payload["recovery_root_name"] = root_name
        payload["recovery_root_identity"] = root_identity
        payload["report_name"] = report.name
        payload["report_parent_identity"] = {"st_dev": int(parent_st.st_dev), "st_ino": int(parent_st.st_ino)}
        # Preserve the exact captured bindings for a possible emergency
        # marker.  Reconstruction must consume these fields verbatim and may
        # never synthesize them from the marker's current parent.
        details["recovery_root_name"] = root_name
        details["recovery_root_identity"] = root_identity
        details["report_name"] = report.name
        details["report_parent_identity"] = payload["report_parent_identity"]
    # The writer adds report/root identity fields below even for the base VV3
    # transaction.  Admit only this fixed metadata schema; unknown fields are
    # still rejected by _validate_recovery_payload.
    allowed_metadata = metadata_keys
    expected_owned = details.get("_expected_ownership_inventory")
    if isinstance(expected_owned, list) and isinstance(details.get("_recovery_root_name"), str):
        recovery_root = parent / str(details["_recovery_root_name"])
        if os.path.lexists(recovery_root):
            current_owned = _inventory_tree(recovery_root)
            for item in current_owned:
                item["path"] = _relative_owned(parent, recovery_root / str(item["path"]))
            root_st = os.lstat(recovery_root)
            current_owned.insert(0, {"path": _relative_owned(parent, recovery_root), "type": "directory", "size": 0, "sha256": None, "st_dev": int(root_st.st_dev), "st_ino": int(root_st.st_ino)})
            _require_inventory_subset(current_owned, expected_owned)
    _validate_recovery_payload(payload, parent, allowed_metadata=allowed_metadata)
    _write_file(tmp, (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    tmp_identity = _inventory_entry(parent, tmp)
    if not os.path.lexists(tmp):
        raise PatcherError("VV3 individual Full Mastery recovery temporary report disappeared.")
    if os.path.lexists(report):
        _remove_owned(tmp, expected=tmp_identity)
        raise PatcherError("VV3 individual Full Mastery recovery report target already exists.")
    try:
        _publish_exclusive(tmp, report, parent)
    except Exception:
        if os.path.lexists(tmp):
            try:
                _remove_owned(tmp, expected=tmp_identity)
            except Exception:
                pass
        raise
    _fsync_dir(parent)
    report_st = os.lstat(report)
    _reject_entry(report, report_st, directory=False)
    _validate_recovery_payload(json.loads(_read_regular(report).decode("utf-8")), parent, allowed_metadata=allowed_metadata)
    try:
        _write_chain_manifest(report, payload)
    except Exception:
        # The canonical report has no usable authority until its manifest is
        # published.  Retire only this exact report identity so the outer
        # emergency-marker path can reconstruct the transaction instead of
        # leaving an ambiguous canonical+marker pair.
        try:
            _remove_owned(report, expected=_inventory_entry(parent, report))
        except Exception:
            pass
        raise
    _fsync_dir(parent)
    return report


def _write_recovery(parent: Path, details: dict[str, object]) -> Path:
    try:
        return _write_recovery_impl(parent, details)
    except Exception as exc:
        try:
            marker = _write_emergency_marker(parent, details, exc)
        except Exception as marker_exc:
            raise PatcherError("VV3 individual Full Mastery canonical recovery report failed and emergency marker creation also failed.") from marker_exc
        raise PatcherError(f"VV3 individual Full Mastery canonical recovery report failed; emergency marker retained at {marker}") from exc


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


def _inventory_entry(root: Path, path: Path) -> dict[str, object]:
    """Capture the exact deletion identity for a file or directory."""
    st = os.lstat(path)
    _reject_entry(path, st)
    if stat.S_ISDIR(st.st_mode):
        return {
            "path": _relative_owned(root, path),
            "type": "directory",
            "size": 0,
            "sha256": None,
            "st_dev": int(st.st_dev),
            "st_ino": int(st.st_ino),
        }
    record = _inventory_member(root, path)
    if record is None:
        raise PatcherError(f"VV3 individual Full Mastery deletion target disappeared: {path}")
    return record


def _publish_exclusive(tmp: Path, final: Path, root: Path) -> None:
    """Publish a new report without replacing a raced final target."""
    _require_windows_identity_atomic()
    tmp_before = _inventory_entry(root, tmp)
    if os.path.lexists(final):
        raise PatcherError(f"VV3 individual Full Mastery exclusive report target raced: {final}")
    try:
        os.link(tmp, final)
    except OSError as exc:
        raise PatcherError(f"VV3 individual Full Mastery exclusive report publication failed: {final}") from exc
    try:
        final_record = _inventory_entry(root, final)
        for key in ("type", "size", "sha256", "st_dev", "st_ino"):
            if final_record.get(key) != tmp_before.get(key):
                raise PatcherError(f"VV3 individual Full Mastery exclusive report postverify failed: {final}")
        tmp_after = _inventory_entry(root, tmp)
        if any(tmp_after.get(key) != tmp_before.get(key) for key in ("type", "size", "sha256", "st_dev", "st_ino")):
            raise PatcherError(f"VV3 individual Full Mastery exclusive report temporary changed: {tmp}")
        # Temporary publication members are not transaction targets; deleting
        # them through _remove_owned would recursively create another cleanup
        # authority.  Use the already identity-bound primitive directly.
        _delete_file_by_handle(tmp, tmp_before)
        final_after = _inventory_entry(root, final)
        if any(final_after.get(key) != tmp_before.get(key) for key in ("type", "size", "sha256", "st_dev", "st_ino")):
            raise PatcherError(f"VV3 individual Full Mastery exclusive report final identity changed: {final}")
    except Exception:
        # The final hard link is retained as durable evidence if its identity
        # cannot be proven after publication.
        raise
    _fsync_dir(root)


def _chain_manifest_path(report: Path) -> Path:
    return report.with_name(f".chain-{report.name}.json")


def _transaction_authority_path(manifest: Path) -> Path:
    """Return the independent authority journal for one chain manifest."""
    token = hashlib.sha256(manifest.name.encode("utf-8")).hexdigest()[:32]
    return manifest.with_name(f".vv3im-journal-{token}.json")


def _read_issuance_binding(manifest: Path) -> dict[str, object] | None:
    """Read the transaction-start issuance evidence bound into a report."""
    report_name = None
    try:
        journal_payload = json.loads(_read_regular(manifest).decode("utf-8"))
        report_name = journal_payload.get("report_name") if isinstance(journal_payload, dict) else None
    except Exception:
        return None
    if not isinstance(report_name, str) or Path(report_name).name != report_name:
        return None
    report = manifest.parent / report_name
    if not os.path.lexists(report):
        return None
    try:
        report_raw = json.loads(_read_regular(report).decode("utf-8"))
    except Exception:
        return None
    if not isinstance(report_raw, dict):
        return None
    if report_raw.get("kind") == "emergency_recovery_marker":
        embedded = report_raw.get("recovery_payload")
        if not isinstance(embedded, dict):
            raise PatcherError("Current emergency recovery marker has no strict recovery payload.")
        owner = embedded.get("feature_owner")
        if not isinstance(owner, str):
            raise PatcherError("Current emergency recovery marker feature owner is missing.")
        _validate_emergency_binding_payload(embedded, owner=owner)
        # Every security binding must come from the durable embedded payload.
        # The marker's location is used only to locate the already-bound
        # objects, never to fill a missing parent/root/issuance field.
        if (
            report_raw.get("recovery_root_name") != embedded.get("recovery_root_name")
            or report_raw.get("recovery_root_identity") != embedded.get("recovery_root_identity")
        ):
            raise PatcherError("Current emergency recovery marker root binding differs from its embedded authority.")
        report_raw = dict(embedded)
    token = report_raw.get("issuance_token")
    name = report_raw.get("issuance_name")
    identity = report_raw.get("issuance_identity")
    if not isinstance(token, str) or not re.fullmatch(r"[0-9a-f]{32}", token) or not isinstance(name, str) or Path(name).is_absolute() or ".." in Path(name).parts or not isinstance(identity, dict):
        return None
    issuance = manifest.parent / name
    # The issuance must be a member of the exact recovery root captured by
    # the report, never an arbitrary sibling that happens to have the right
    # basename.  Revalidate parent/root identities before reading it.
    feature_owner = report_raw.get("feature_owner")
    if feature_owner not in {"vv3_individual_full_mastery", "vv5_individual_grant_running_candidate"}:
        raise PatcherError("Current recovery report has no strict feature owner.")
    strict_vv3 = feature_owner == "vv3_individual_full_mastery"
    root_name = report_raw.get("recovery_root_name")
    root_identity = report_raw.get("recovery_root_identity")
    if feature_owner == "vv5_individual_grant_running_candidate":
        root_pattern = r"\.vv5run-recovery-[0-9a-f]{32}"
    else:
        root_pattern = r"\.vv3im-(?:recovery|emergency)-[0-9a-f]{32}"
    if not isinstance(root_name, str) or Path(root_name).name != root_name or Path(root_name).is_absolute() or ".." in Path(root_name).parts or not re.fullmatch(root_pattern, root_name) or not isinstance(root_identity, dict):
        return None
    root = manifest.parent / root_name
    actual_root = _inventory_entry(manifest.parent, root)
    if actual_root.get("type") != "directory" or any(actual_root.get(key) != root_identity.get(key) for key in ("st_dev", "st_ino")):
        raise PatcherError("VV3 individual Full Mastery issuance recovery root changed before binding.")
    if strict_vv3:
        issuance_parts = Path(name).parts
        if issuance_parts != (root_name, issuance_parts[-1] if issuance_parts else "") or not re.fullmatch(r"\.vv3im-issuance-[0-9a-f]{32}\.json", issuance_parts[-1] if issuance_parts else ""):
            return None
    elif not (isinstance(name, str) and Path(name).parts and Path(name).parts[0] == ".vv5run-issuance" and len(Path(name).parts) == 2 and re.fullmatch(r"[0-9a-f]{32}\.json", Path(name).parts[1])):
        return None
    report_parent_identity = report_raw.get("report_parent_identity")
    actual_parent = _inventory_entry(manifest.parent.parent, manifest.parent)
    if not isinstance(report_parent_identity, dict) or any(actual_parent.get(key) != report_parent_identity.get(key) for key in ("st_dev", "st_ino")):
        raise PatcherError("VV3 individual Full Mastery issuance report parent changed before binding.")
    if report_raw.get("destination_parent_absolute") != str(manifest.parent.absolute()).casefold():
        raise PatcherError("Current recovery report destination parent is missing or relocated.")
    try:
        issuance_record = _inventory_entry(manifest.parent, issuance)
    except (FileNotFoundError, PatcherError) as exc:
        raise PatcherError("VV3 individual Full Mastery issuance evidence is missing or unsafe.") from exc
    if issuance_record != identity.get("record"):
        raise PatcherError("VV3 individual Full Mastery issuance evidence changed before journal binding.")
    if strict_vv3 and not issuance_record.get("path", "").replace("\\", "/").startswith(str(root_name) + "/"):
        return None
    issuance_payload = json.loads(_read_regular(issuance).decode("utf-8"))
    # VV5 owns a separate parent-registry issuance schema.  The shared
    # authority journal must preserve and compare that external record, but
    # VV3's stricter transaction-start schema applies only to VV3 issuance.
    if report_raw.get("feature_owner") == "vv5_individual_grant_running_candidate":
        return {"token": token, "name": name, "record": identity.get("record"), "owner": report_raw.get("feature_owner"), "operation": report_raw.get("operation"), "destination_paths_absolute": report_raw.get("destination_paths_absolute"), "member_roles": report_raw.get("member_roles")}
    required = {"schema_version", "kind", "feature_owner", "operation", "transaction_id", "token", "owner_parent_absolute", "parent_identity", "recovery_root_name", "recovery_root_identity", "destination_paths_absolute", "member_roles", "member_digest", "members", "precondition"}
    if not isinstance(issuance_payload, dict) or set(issuance_payload) != required or issuance_payload.get("schema_version") != 1 or issuance_payload.get("kind") != "vv3_recovery_issuance":
        raise PatcherError("VV3 individual Full Mastery issuance evidence schema is unsupported or forged.")
    if issuance_payload.get("transaction_id") != token or issuance_payload.get("token") != token:
        raise PatcherError("VV3 individual Full Mastery issuance transaction identity is inconsistent.")
    if issuance_payload.get("feature_owner") != report_raw.get("feature_owner") or issuance_payload.get("operation") != report_raw.get("operation"):
        raise PatcherError("VV3 individual Full Mastery issuance owner/operation binding is inconsistent.")
    issuance_root_identity = issuance_payload.get("recovery_root_identity")
    root_identity_matches = isinstance(issuance_root_identity, dict) and isinstance(root_identity, dict) and all(issuance_root_identity.get(key) == root_identity.get(key) for key in ("st_dev", "st_ino"))
    if issuance_payload.get("owner_parent_absolute") != str(manifest.parent.absolute()).casefold() or issuance_payload.get("recovery_root_name") != root_name or not root_identity_matches:
        raise PatcherError("VV3 individual Full Mastery issuance parent/root binding is inconsistent.")
    report_roles = report_raw.get("member_roles") or {}
    issuance_roles = issuance_payload.get("member_roles") or {}
    normalized_issuance_roles = {Path(str(name)).name.casefold(): role for name, role in issuance_roles.items()}
    normalized_report_roles = {str(name).casefold(): role for name, role in report_roles.items()}
    if issuance_payload.get("destination_paths_absolute") != report_raw.get("destination_paths_absolute") or normalized_issuance_roles != normalized_report_roles:
        raise PatcherError("VV3 individual Full Mastery issuance destination/role binding is inconsistent.")
    report_members = report_raw.get("members")
    issuance_members = issuance_payload.get("members")
    if not isinstance(report_members, list) or not isinstance(issuance_members, list) or len(report_members) != len(issuance_members):
        raise PatcherError("VV3 individual Full Mastery issuance member binding is incomplete.")
    expected_members = [
        {"path": str((manifest.parent / str(item.get("destination_relative"))).absolute()).casefold(), "exists": bool(item.get("pre_exists")), "size": int(item.get("pre_size", 0)), "sha256": item.get("pre_sha256")}
        for item in report_members
        if isinstance(item, dict) and isinstance(item.get("destination_relative"), str)
    ]
    if len(expected_members) != len(report_members) or issuance_members != expected_members or issuance_payload.get("precondition") != {item["path"]: {"exists": item["exists"], "size": item["size"], "sha256": item["sha256"]} for item in expected_members}:
        raise PatcherError("VV3 individual Full Mastery issuance precondition/member binding is inconsistent.")
    members_blob = json.dumps(issuance_payload.get("members"), sort_keys=True, separators=(",", ":")).encode("utf-8")
    if issuance_payload.get("member_digest") != _sha(members_blob):
        raise PatcherError("VV3 individual Full Mastery issuance member digest is inconsistent.")
    return {"token": token, "name": name, "record": identity.get("record"), "owner": report_raw.get("feature_owner"), "operation": report_raw.get("operation"), "destination_paths_absolute": report_raw.get("destination_paths_absolute"), "member_roles": report_raw.get("member_roles"), "member_digest": issuance_payload.get("member_digest"), "payload": issuance_payload}


def _discover_transaction_authority(manifest: Path) -> Path:
    """Find the last member of one complete, parent-bound authority chain.

    A publication can be interrupted after any successor is durable.  Follow
    the recorded predecessor identities transitively instead of assuming one
    successor, and reject branches/orphans rather than selecting a convenient
    same-name journal.
    """
    canonical = _transaction_authority_path(manifest)
    token = canonical.stem
    successor_re = re.compile(re.escape(token) + r"\.v[0-9a-f]{32}\.json")
    with os.scandir(manifest.parent) as entries:
        successors = sorted(
            [Path(entry.path) for entry in entries if successor_re.fullmatch(entry.name)],
            key=lambda p: p.name,
        )
    paths: list[Path] = ([canonical] if os.path.lexists(canonical) else []) + successors
    if not paths:
        raise PatcherError("VV3 individual Full Mastery independent transaction authority is missing.")
    records: dict[Path, dict[str, object]] = {}
    for path in paths:
        try:
            raw = json.loads(_read_regular(path).decode("utf-8"))
        except Exception as exc:
            raise PatcherError("VV3 individual Full Mastery transaction authority successor is unreadable.") from exc
        if not isinstance(raw, dict):
            raise PatcherError("VV3 individual Full Mastery transaction authority successor is malformed.")
        record = _inventory_entry(manifest.parent, path)
        if record is None:
            raise PatcherError("VV3 individual Full Mastery transaction authority identity disappeared.")
        records[path] = {"raw": raw, "record": record}

    # A canonical journal is the only valid chain root when present.  Every
    # successor must bind to the immediately preceding captured identity.
    if os.path.lexists(canonical):
        heads = [canonical]
    else:
        heads = [
            path for path, entry in records.items()
            if path != canonical and json.dumps(entry["raw"].get("previous_authority_record"), sort_keys=True) not in {
                json.dumps(other["record"], sort_keys=True) for other_path, other in records.items() if other_path != path
            }
        ]
        if len(heads) != 1:
            raise PatcherError("VV3 individual Full Mastery transaction authority successor chain is missing or ambiguous.")

    current = heads[0]
    consumed = {current}
    while True:
        current_record = records[current]["record"]
        next_paths = [
            path for path, entry in records.items()
            if path not in consumed and entry["raw"].get("previous_authority_record") == current_record
        ]
        if len(next_paths) > 1:
            raise PatcherError("VV3 individual Full Mastery transaction authority successor chain branches.")
        if not next_paths:
            break
        current = next_paths[0]
        consumed.add(current)
    if consumed != set(paths):
        raise PatcherError("VV3 individual Full Mastery transaction authority successor chain contains an orphan.")
    return current


def _write_transaction_authority(manifest: Path, payload: dict[str, object], manifest_record: dict[str, object]) -> tuple[Path, dict[str, object]]:
    """Publish an independent, identity-bound journal for every chain state."""
    _require_windows_identity_atomic()
    journal = _transaction_authority_path(manifest)
    previous: dict[str, object] | None = None
    previous_path: Path | None = None
    if os.path.lexists(journal) or any(
        re.fullmatch(re.escape(journal.stem) + r"\.v[0-9a-f]{32}\.json", entry.name)
        for entry in os.scandir(manifest.parent)
    ):
        # Continue from the discovered chain head, including successor-only
        # states left after an interrupted canonical retirement.  Never select
        # a same-name record by convenience.
        previous_path = _discover_transaction_authority(manifest)
        previous = _inventory_entry(manifest.parent, previous_path)
        if previous is None:
            raise PatcherError("VV3 individual Full Mastery transaction authority head disappeared.")
        try:
            previous_raw = json.loads(_read_regular(previous_path).decode("utf-8"))
        except Exception as exc:
            raise PatcherError("VV3 individual Full Mastery transaction authority target is foreign.") from exc
        required_previous = {"schema_version", "kind", "state", "manifest_name", "manifest_record", "report_name", "report_record", "canonical_name", "canonical_record", "pointer_name", "pointer_record", "successor_name", "successor_record", "marker_name", "marker_record", "recovery_root_name", "recovery_root_record", "ownership_inventory", "members", "member_roles", "destination_paths_absolute", "transaction_journal", "previous_authority_record"}
        previous_keys = set(previous_raw) if isinstance(previous_raw, dict) else set()
        if not isinstance(previous_raw, dict) or previous_keys not in (required_previous, required_previous | {"external_issuance"}) or previous_raw.get("schema_version") != 1 or previous_raw.get("kind") != "vv3_recovery_transaction_authority" or previous_raw.get("manifest_name") != manifest.name:
            raise PatcherError("VV3 individual Full Mastery transaction authority target is foreign.")
        if not isinstance(previous_raw.get("transaction_journal"), dict) or previous_raw["transaction_journal"].get("state") != previous_raw.get("state") or not isinstance(previous_raw.get("members"), list) or not isinstance(previous_raw.get("member_roles"), dict) or not isinstance(previous_raw.get("ownership_inventory"), list) or not isinstance(previous_raw.get("destination_paths_absolute"), list):
            raise PatcherError("VV3 individual Full Mastery transaction authority bindings are malformed.")
        if any(not isinstance(item, dict) or not isinstance(item.get("path"), str) for item in previous_raw.get("ownership_inventory", [])):
            raise PatcherError("VV3 individual Full Mastery transaction authority inventory is malformed.")
        if len({str(path).casefold() for path in previous_raw.get("destination_paths_absolute", [])}) != len(previous_raw.get("destination_paths_absolute", [])):
            raise PatcherError("VV3 individual Full Mastery transaction authority destinations are duplicated.")
        if previous.get("type") != "regular_file" or previous.get("sha256") != _sha(_read_regular(previous_path)):
            raise PatcherError("VV3 individual Full Mastery transaction authority identity/content changed.")
    journal_payload = {
        "schema_version": 1,
        "kind": "vv3_recovery_transaction_authority",
        "state": payload.get("transaction_journal", {}).get("state"),
        "manifest_name": manifest.name,
        "manifest_record": manifest_record,
        "report_name": payload.get("report_name"),
        "report_record": payload.get("report_record"),
        "canonical_name": payload.get("canonical_name"),
        "canonical_record": payload.get("canonical_record"),
        "pointer_name": payload.get("pointer_name"),
        "pointer_record": payload.get("pointer_record"),
        "successor_name": payload.get("successor_name"),
        "successor_record": payload.get("successor_record"),
        "marker_name": payload.get("marker_name"),
        "marker_record": payload.get("marker_record"),
        "recovery_root_name": payload.get("recovery_root_name"),
        "recovery_root_record": payload.get("recovery_root_record"),
        "ownership_inventory": payload.get("ownership_inventory"),
        "members": payload.get("members"),
        "member_roles": payload.get("member_roles"),
        "destination_paths_absolute": payload.get("destination_paths_absolute"),
        "transaction_journal": payload.get("transaction_journal"),
        "previous_authority_record": previous,
    }
    try:
        issuance_binding = _read_issuance_binding(manifest)
    except PatcherError:
        if payload.get("feature_owner") in {"vv3_individual_full_mastery", "vv5_individual_grant_running_candidate"}:
            raise
        issuance_binding = None
    if issuance_binding is not None:
        journal_payload["external_issuance"] = issuance_binding
    # When advancing an existing authority, publish a durable successor first.
    # The prior valid journal is never consumed before that successor has been
    # fully written and identity-verified.  A failure after successor
    # publication leaves the successor discoverable for deterministic replay.
    target = journal if previous is None else journal.with_name(f"{journal.stem}.v{uuid.uuid4().hex}.json")
    tmp = target.with_suffix(".tmp")
    data = (json.dumps(journal_payload, indent=2, sort_keys=True) + "\n").encode("utf-8")
    try:
        _write_file(tmp, data)
    except Exception as exc:
        if os.path.lexists(tmp):
            tmp_record = _inventory_entry(manifest.parent, tmp)
            if tmp_record.get("type") != "regular_file" or tmp_record.get("size") != len(data) or tmp_record.get("sha256") != _sha(data):
                raise PatcherError("VV3 individual Full Mastery transaction authority temporary is incomplete.") from exc
        else:
            raise
    _publish_exclusive(tmp, target, manifest.parent)
    successor_record = _inventory_entry(manifest.parent, target)
    if successor_record is None or successor_record.get("size") != len(data) or successor_record.get("sha256") != _sha(data):
        raise PatcherError("VV3 individual Full Mastery transaction authority successor postverify failed.")
    record = successor_record
    if record is None or record.get("size") != len(data) or record.get("sha256") != _sha(data) or _inventory_entry(manifest.parent, target) != record:
        raise PatcherError("VV3 individual Full Mastery transaction authority postverify failed.")
    return target, record


def _validate_transaction_authority(manifest: Path, payload: dict[str, object], manifest_record: dict[str, object] | None = None) -> tuple[Path, dict[str, object]]:
    journal = _discover_transaction_authority(manifest)
    record = _inventory_entry(manifest.parent, journal)
    if record is None:
        raise PatcherError("VV3 individual Full Mastery independent transaction authority is missing.")
    raw = json.loads(_read_regular(journal).decode("utf-8"))
    required = {"schema_version", "kind", "state", "manifest_name", "manifest_record", "report_name", "report_record", "canonical_name", "canonical_record", "pointer_name", "pointer_record", "successor_name", "successor_record", "marker_name", "marker_record", "recovery_root_name", "recovery_root_record", "ownership_inventory", "members", "member_roles", "destination_paths_absolute", "transaction_journal", "previous_authority_record"}
    raw_keys = set(raw) if isinstance(raw, dict) else set()
    if not isinstance(raw, dict) or raw_keys not in (required, required | {"external_issuance"}) or raw.get("schema_version") != 1 or raw.get("kind") != "vv3_recovery_transaction_authority" or raw.get("manifest_name") != manifest.name:
        raise PatcherError("VV3 individual Full Mastery independent transaction authority is malformed.")
    expected_manifest = manifest_record or _inventory_entry(manifest.parent, manifest)
    if raw.get("manifest_record") != expected_manifest:
        raise PatcherError("VV3 individual Full Mastery independent transaction authority manifest identity changed.")
    for key in ("report_name", "report_record", "canonical_name", "canonical_record", "pointer_name", "pointer_record", "successor_name", "successor_record", "marker_name", "marker_record", "recovery_root_name", "recovery_root_record", "ownership_inventory", "members", "member_roles", "destination_paths_absolute", "transaction_journal"):
        if raw.get(key) != payload.get(key):
            raise PatcherError("VV3 individual Full Mastery independent transaction authority is stale or swapped.")
    if raw.get("state") != payload.get("transaction_journal", {}).get("state"):
        raise PatcherError("VV3 individual Full Mastery independent transaction authority state is inconsistent.")
    if raw.get("previous_authority_record") is not None and not isinstance(raw.get("previous_authority_record"), dict):
        raise PatcherError("VV3 individual Full Mastery transaction authority predecessor binding is malformed.")
    expected_issuance = _read_issuance_binding(manifest)
    if expected_issuance is None or raw.get("external_issuance") != expected_issuance:
        raise PatcherError("Current recovery transaction authority issuance binding is missing or stale.")
    if _inventory_entry(manifest.parent, journal) != record:
        raise PatcherError("VV3 individual Full Mastery independent transaction authority changed before use.")
    return journal, record


def _transaction_journal(
    *,
    state: str,
    report_name: str,
    report_record: dict[str, object],
    canonical_name: str | None,
    canonical_record: dict[str, object] | None,
    pointer_name: str | None,
    pointer_record: dict[str, object] | None,
    successor_name: str | None,
    successor_record: dict[str, object] | None,
    marker_name: str | None,
    marker_record: dict[str, object] | None,
) -> dict[str, object]:
    """Build the single durable authority for every chain transition.

    ``commit_state`` was only descriptive and could not distinguish an
    interrupted successor/pointer/manifest sequence.  The journal binds the
    state, every chain member, and its captured identity in one record.  A
    replay may roll forward only when this authority is internally coherent.
    """
    if state not in {"canonical_published", "successor_pointer_manifest", "emergency_marker"}:
        raise PatcherError("VV3 individual Full Mastery transaction journal state is unsupported.")
    authority = {
        "report": {"name": report_name, "record": report_record},
        "canonical": {"name": canonical_name, "record": canonical_record},
        "pointer": {"name": pointer_name, "record": pointer_record},
        "successor": {"name": successor_name, "record": successor_record},
        "marker": {"name": marker_name, "record": marker_record},
    }
    transitions = {
        "canonical_published": ["report", "manifest"],
        "successor_pointer_manifest": ["canonical", "successor", "pointer", "manifest"],
        "emergency_marker": ["marker", "manifest"],
    }[state]
    return {
        "schema_version": 1,
        "kind": "vv3_recovery_transaction_journal",
        "state": state,
        "transitions": transitions,
        "authority": authority,
    }


def _journal_state(raw: dict[str, object]) -> str:
    journal = raw.get("transaction_journal")
    if not isinstance(journal, dict) or set(journal) != {"schema_version", "kind", "state", "transitions", "authority"} or journal.get("schema_version") != 1 or journal.get("kind") != "vv3_recovery_transaction_journal":
        raise PatcherError("VV3 individual Full Mastery transaction journal is malformed.")
    state = journal.get("state")
    if state not in {"canonical_published", "successor_pointer_manifest", "emergency_marker"}:
        raise PatcherError("VV3 individual Full Mastery transaction journal state is invalid.")
    expected_transitions = {
        "canonical_published": ["report", "manifest"],
        "successor_pointer_manifest": ["canonical", "successor", "pointer", "manifest"],
        "emergency_marker": ["marker", "manifest"],
    }[state]
    if journal.get("transitions") != expected_transitions or not isinstance(journal.get("authority"), dict):
        raise PatcherError("VV3 individual Full Mastery transaction journal transitions are invalid.")
    expected_authority = {
        "report": {"name": raw.get("report_name"), "record": raw.get("report_record")},
        "canonical": {"name": raw.get("canonical_name"), "record": raw.get("canonical_record")},
        "pointer": {"name": raw.get("pointer_name"), "record": raw.get("pointer_record")},
        "successor": {"name": raw.get("successor_name"), "record": raw.get("successor_record")},
        "marker": {"name": raw.get("marker_name"), "record": raw.get("marker_record")},
    }
    if journal.get("authority") != expected_authority:
        raise PatcherError("VV3 individual Full Mastery transaction journal authority is stale or swapped.")
    report_name = raw.get("report_name")
    canonical_name = raw.get("canonical_name")
    pointer_name = raw.get("pointer_name")
    successor_name = raw.get("successor_name")
    marker_name = raw.get("marker_name")
    if state == "canonical_published" and (canonical_name != report_name or pointer_name is not None or successor_name is not None or marker_name is not None):
        raise PatcherError("VV3 individual Full Mastery canonical journal state is inconsistent.")
    if state == "successor_pointer_manifest" and (not isinstance(canonical_name, str) or canonical_name == report_name or not isinstance(pointer_name, str) or successor_name != report_name or marker_name is not None):
        raise PatcherError("VV3 individual Full Mastery successor journal state is inconsistent.")
    if state == "emergency_marker" and (marker_name != report_name or pointer_name is not None or successor_name is not None):
        raise PatcherError("VV3 individual Full Mastery emergency journal state is inconsistent.")
    return str(state)


def _write_chain_manifest(
    report: Path,
    payload: dict[str, object],
    *,
    canonical_name: str | None = None,
    pointer_name: str | None = None,
    successor_name: str | None = None,
    marker_name: str | None = None,
    commit_state: str = "canonical_published",
) -> tuple[Path, dict[str, object]]:
    """Publish one durable ownership record for the complete report chain."""
    _require_windows_identity_atomic()
    manifest = _chain_manifest_path(report)
    if os.path.lexists(manifest):
        raise PatcherError(f"VV3 individual Full Mastery chain manifest target raced: {manifest}")
    report_record = _inventory_entry(report.parent, report)
    canonical_record = _inventory_entry(report.parent, report.parent / canonical_name) if canonical_name else report_record
    pointer_record = _inventory_entry(report.parent, report.parent / pointer_name) if pointer_name else None
    successor_record = _inventory_entry(report.parent, report.parent / successor_name) if successor_name else None
    marker_record = _inventory_entry(report.parent, report.parent / marker_name) if marker_name else None
    root_record = next((item for item in payload.get("ownership_inventory", []) if isinstance(item, dict) and item.get("type") == "directory" and "/" not in str(item.get("path", ""))), None)
    if not isinstance(root_record, dict):
        raise PatcherError("VV3 individual Full Mastery chain manifest root identity is missing.")
    manifest_members = payload.get("members") or []
    manifest_roles = payload.get("member_roles") or {
        str(member.get("destination_relative")): "recovery_member"
        for member in manifest_members
        if isinstance(member, dict) and isinstance(member.get("destination_relative"), str)
    }
    manifest_destinations = payload.get("destination_paths_absolute") or [
        str(member.get("destination_relative"))
        for member in manifest_members
        if isinstance(member, dict) and isinstance(member.get("destination_relative"), str)
    ]
    manifest_payload = {
        "schema_version": 3,
        "kind": "vv3_recovery_chain_manifest",
        "recovery_prefix": str(payload.get("recovery_prefix") or report.name.split("-recovery-", 1)[0].split("-emergency-", 1)[0]),
        "report_name": report.name,
        "report_record": report_record,
        "canonical_name": canonical_name or report.name,
        "canonical_record": canonical_record,
        "pointer_name": pointer_name,
        "pointer_record": pointer_record,
        "successor_name": successor_name,
        "successor_record": successor_record,
        "marker_name": marker_name,
        "marker_record": marker_record,
        "recovery_root_name": payload.get("recovery_root_name") or str(root_record.get("path")),
        "recovery_root_record": root_record,
        "ownership_inventory": payload.get("ownership_inventory"),
        "members": manifest_members,
        "member_roles": manifest_roles,
        "destination_paths_absolute": manifest_destinations,
    }
    manifest_payload["transaction_journal"] = _transaction_journal(
        state=commit_state,
        report_name=report.name,
        report_record=report_record,
        canonical_name=canonical_name or report.name,
        canonical_record=canonical_record,
        pointer_name=pointer_name,
        pointer_record=pointer_record,
        successor_name=successor_name,
        successor_record=successor_record,
        marker_name=marker_name,
        marker_record=marker_record,
    )
    tmp = manifest.with_suffix(".tmp")
    _write_file(tmp, (json.dumps(manifest_payload, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    _publish_exclusive(tmp, manifest, report.parent)
    record = _inventory_entry(report.parent, manifest)
    # The manifest is descriptive; the independent authority journal is the
    # durable ownership source for interrupted transitions and replay.
    if payload.get("feature_owner") not in {"vv3_individual_full_mastery", "vv5_individual_grant_running_candidate"}:
        raise PatcherError("Current recovery chain has no strict feature owner or issuance authority.")
    authority_payload = {**manifest_payload, "feature_owner": payload.get("feature_owner"), "mode": payload.get("mode")}
    _write_transaction_authority(manifest, authority_payload, record)
    return manifest, record


def _read_chain_manifest(report: Path) -> tuple[Path, dict[str, object], dict[str, object]]:
    manifest = _chain_manifest_path(report)
    record = _inventory_entry(report.parent, manifest)
    raw = json.loads(_read_regular(manifest).decode("utf-8"))
    required = {"schema_version", "kind", "transaction_journal", "recovery_prefix", "report_name", "report_record", "canonical_name", "canonical_record", "pointer_name", "pointer_record", "successor_name", "successor_record", "marker_name", "marker_record", "recovery_root_name", "recovery_root_record", "ownership_inventory", "members", "member_roles", "destination_paths_absolute"}
    if not isinstance(raw, dict) or set(raw) != required or raw.get("schema_version") != 3 or raw.get("kind") != "vv3_recovery_chain_manifest" or raw.get("report_name") != report.name:
        raise PatcherError("VV3 individual Full Mastery recovery chain manifest is malformed.")
    journal_state = _journal_state(raw)
    expected_prefix = report.name.split("-recovery-", 1)[0].split("-emergency-", 1)[0]
    if raw.get("recovery_prefix") != expected_prefix:
        raise PatcherError("VV3 individual Full Mastery recovery chain prefix is invalid.")
    if raw.get("report_record") != _inventory_entry(report.parent, report):
        raise PatcherError("VV3 individual Full Mastery recovery chain report identity changed.")
    for name_key, record_key in (("canonical_name", "canonical_record"), ("pointer_name", "pointer_record"), ("successor_name", "successor_record"), ("marker_name", "marker_record")):
        name = raw.get(name_key)
        member_record = raw.get(record_key)
        if name is None:
            if member_record is not None:
                raise PatcherError("VV3 individual Full Mastery recovery chain member presence is inconsistent.")
            continue
        if not isinstance(name, str) or Path(name).name != name or not name:
            raise PatcherError("VV3 individual Full Mastery recovery chain member name is unsafe.")
        path = report.parent / name
        if not isinstance(member_record, dict) or _inventory_entry(report.parent, path) != member_record:
            raise PatcherError("VV3 individual Full Mastery recovery chain member identity changed.")
    root_record = raw.get("recovery_root_record")
    if not isinstance(root_record, dict) or raw.get("recovery_root_name") != Path(str(root_record.get("path"))).name:
        raise PatcherError("VV3 individual Full Mastery recovery chain root binding is malformed.")
    root_rel = Path(str(root_record.get("path")))
    if root_rel.is_absolute() or not root_rel.parts or ".." in root_rel.parts:
        raise PatcherError("VV3 individual Full Mastery recovery chain root path is unsafe.")
    root = report.parent / root_rel
    if _inventory_entry(report.parent, root) != root_record:
        raise PatcherError("VV3 individual Full Mastery recovery chain root identity changed.")
    if not isinstance(raw.get("ownership_inventory"), list) or not isinstance(raw.get("members"), list) or not isinstance(raw.get("member_roles"), dict) or not isinstance(raw.get("destination_paths_absolute"), list):
        raise PatcherError("VV3 individual Full Mastery recovery chain ownership is incomplete.")
    paths = [str(item.get("path")) for item in raw["ownership_inventory"] if isinstance(item, dict)]
    if len(paths) != len(raw["ownership_inventory"]) or len({path.casefold() for path in paths}) != len(paths) or any(Path(path).is_absolute() or not Path(path).parts or ".." in Path(path).parts for path in paths):
        raise PatcherError("VV3 individual Full Mastery recovery chain inventory is unsafe.")
    if len({str(path).casefold() for path in raw["destination_paths_absolute"]}) != len(raw["destination_paths_absolute"]):
        raise PatcherError("VV3 individual Full Mastery recovery chain destination paths are duplicated.")
    effective = json.loads(_read_regular(report).decode("utf-8"))
    emergency_manifest = isinstance(effective, dict) and effective.get("kind") == "emergency_recovery_marker"
    if emergency_manifest:
        marker_payload = effective
        if not re.fullmatch(re.escape(raw["recovery_prefix"]) + r"-emergency-[0-9a-f]{32}\.json", report.name) or marker_payload.get("report_name", report.name) != report.name or marker_payload.get("canonical_report_target") != f"{raw['recovery_prefix']}-recovery-*.json":
            raise PatcherError("VV3 individual Full Mastery emergency marker filename role is invalid.")
        effective = marker_payload.get("recovery_payload") if isinstance(marker_payload.get("recovery_payload"), dict) else {}
    if not isinstance(effective, dict):
        raise PatcherError("VV3 individual Full Mastery recovery chain report payload is malformed.")
    effective_members = effective.get("members") if isinstance(effective, dict) else None
    effective_roles = effective.get("member_roles") if isinstance(effective, dict) else None
    effective_destinations = effective.get("destination_paths_absolute") if isinstance(effective, dict) else None
    if isinstance(effective_members, list):
        effective_roles = effective_roles or {str(member.get("destination_relative")): "recovery_member" for member in effective_members if isinstance(member, dict) and isinstance(member.get("destination_relative"), str)}
        effective_destinations = effective_destinations or [str(member.get("destination_relative")) for member in effective_members if isinstance(member, dict) and isinstance(member.get("destination_relative"), str)]
    if raw.get("members") != effective_members or raw.get("ownership_inventory") != effective.get("ownership_inventory") or raw.get("destination_paths_absolute") != (effective_destinations or []) or raw.get("member_roles") != (effective_roles or {}):
        raise PatcherError("VV3 individual Full Mastery recovery chain does not bind the active report.")
    if not isinstance(effective_roles, dict) or any(not isinstance(value, str) or value not in {"recovery_member", "game_executable", "companion_dll"} for value in effective_roles.values()):
        raise PatcherError("VV3 individual Full Mastery recovery member roles are invalid.")
    if emergency_manifest and (not isinstance(effective.get("member_roles"), dict) or not isinstance(effective.get("destination_paths_absolute"), list) or len({str(item).casefold() for item in effective.get("destination_paths_absolute", [])}) != len(effective.get("destination_paths_absolute", []))):
        raise PatcherError("VV3 individual Full Mastery recovery chain member roles/destinations are ambiguous.")
    canonical_name = raw.get("canonical_name")
    pointer_name = raw.get("pointer_name")
    successor_name = raw.get("successor_name")
    if canonical_name != report.name:
        if not isinstance(canonical_name, str) or not isinstance(pointer_name, str) or successor_name != report.name or _report_pointer_path(report.parent / canonical_name).name != pointer_name:
            raise PatcherError("VV3 individual Full Mastery recovery chain canonical/pointer relationship is invalid.")
    elif pointer_name is not None or successor_name is not None:
        raise PatcherError("VV3 individual Full Mastery recovery chain has an unbound pointer or successor.")
    marker_name = raw.get("marker_name")
    if marker_name is not None and (marker_name != report.name or not report.name.startswith(raw["recovery_prefix"] + "-emergency-")):
        raise PatcherError("VV3 individual Full Mastery recovery chain marker relationship is invalid.")
    if successor_name == report.name and (pointer_name is None or journal_state != "successor_pointer_manifest"):
        raise PatcherError("VV3 individual Full Mastery successor chain commit state is incomplete.")
    if marker_name == report.name and journal_state != "emergency_marker":
        raise PatcherError("VV3 individual Full Mastery emergency chain commit state is invalid.")
    # Re-read the manifest, every bound sibling, and the root immediately
    # before returning them to replay.  This closes the use-after-discovery
    # interval for same-content replacements and foreign chain members.
    if _inventory_entry(report.parent, manifest) != record:
        raise PatcherError("VV3 individual Full Mastery recovery chain manifest changed before use.")
    for name_key, record_key in (("canonical_name", "canonical_record"), ("pointer_name", "pointer_record"), ("successor_name", "successor_record"), ("marker_name", "marker_record")):
        name = raw.get(name_key)
        expected_record = raw.get(record_key)
        if name is not None and _inventory_entry(report.parent, report.parent / str(name)) != expected_record:
            raise PatcherError("VV3 individual Full Mastery recovery chain member changed before use.")
    if _inventory_entry(report.parent, root) != root_record or _inventory_entry(report.parent, report) != raw.get("report_record"):
        raise PatcherError("VV3 individual Full Mastery recovery chain root/report changed before use.")
    _validate_transaction_authority(manifest, raw, record)
    return manifest, record, raw


def _move_noreplace(source: Path, destination: Path) -> None:
    """Move a directory to a fresh tombstone without replacing a raced target."""
    _require_windows_identity_atomic()
    if os.name != "nt":
        raise PatcherError("VV3 individual Full Mastery directory quarantine is certified only on 64-bit Windows.")
    if not os.path.lexists(source):
        raise PatcherError(f"VV3 individual Full Mastery directory quarantine source disappeared: {source}")
    if os.path.lexists(destination):
        raise PatcherError(f"VV3 individual Full Mastery tombstone target raced: {destination}")
    source_record = _inventory_entry(source.parent, source)
    source_parent_record = _inventory_entry(source.parent.parent, source.parent)
    destination_parent_record = _inventory_entry(destination.parent.parent, destination.parent)
    if source_record is None or source_parent_record is None or destination_parent_record is None or source_record.get("type") != "directory" or source_parent_record != destination_parent_record:
        raise PatcherError("VV3 individual Full Mastery directory quarantine parent is unsafe.")
    # Revalidate source, both parents, and the empty tombstone target directly
    # adjacent to the destructive MoveFileExW call.
    if os.path.lexists(destination) or _inventory_entry(source.parent, source) != source_record or _inventory_entry(source.parent.parent, source.parent) != source_parent_record or _inventory_entry(destination.parent.parent, destination.parent) != destination_parent_record:
        raise PatcherError("VV3 individual Full Mastery directory quarantine source/parent raced.")
    if os.name == "nt":
        import ctypes
        kernel32 = ctypes.windll.kernel32
        kernel32.MoveFileExW.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint32]
        kernel32.MoveFileExW.restype = ctypes.c_int
        MOVEFILE_WRITE_THROUGH = 0x00000008
        if not kernel32.MoveFileExW(str(source), str(destination), MOVEFILE_WRITE_THROUGH):
            raise PatcherError(f"VV3 individual Full Mastery no-replace directory quarantine failed: {source}")
        moved_record = _inventory_entry(destination.parent, destination)
        if os.path.lexists(source) or any(moved_record.get(key) != source_record.get(key) for key in ("type", "size", "sha256", "st_dev", "st_ino")) or _inventory_entry(source.parent.parent, source.parent) != source_parent_record or _inventory_entry(destination.parent.parent, destination.parent) != destination_parent_record:
            raise PatcherError("VV3 individual Full Mastery directory quarantine changed source/parent after move.")
        return
    # Portable POSIX rename has replacement semantics; without renameat2
    # support, fail closed instead of risking a foreign tombstone overwrite.
    raise PatcherError("VV3 individual Full Mastery directory quarantine lacks a no-replace primitive")


def _delete_file_by_handle(path: Path, expected: dict[str, object]) -> None:
    """Delete the opened file identity, preserving a raced replacement."""
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes
        kernel32 = ctypes.windll.kernel32
        _configure_windows_delete_api(kernel32, ctypes, wintypes)
        GENERIC_READ = 0x80000000
        DELETE = 0x00010000
        FILE_SHARE_READ = 0x00000001
        FILE_SHARE_WRITE = 0x00000002
        FILE_SHARE_DELETE = 0x00000004
        OPEN_EXISTING = 3
        FILE_FLAG_OPEN_REPARSE_POINT = 0x00200000
        handle = kernel32.CreateFileW(
            str(path), GENERIC_READ | DELETE,
            FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
            None, OPEN_EXISTING, FILE_FLAG_OPEN_REPARSE_POINT, None,
        )
        if handle == ctypes.c_void_p(-1).value:
            raise PatcherError(f"VV3 individual Full Mastery file delete could not open target: {path}")
        try:
            handle_identity = _get_windows_handle_identity(kernel32, ctypes, wintypes, handle)
            opened = os.lstat(path)
            if (int(opened.st_dev), int(opened.st_ino), int(opened.st_size)) != (int(expected["st_dev"]), int(expected["st_ino"]), int(expected["size"])):
                raise PatcherError(f"VV3 individual Full Mastery file delete identity changed: {path}")
            if handle_identity != _get_windows_handle_identity(kernel32, ctypes, wintypes, handle):
                raise PatcherError(f"VV3 individual Full Mastery opened handle identity changed: {path}")
            class FILE_DISPOSITION_INFO_EX(ctypes.Structure):
                _fields_ = [("Flags", wintypes.DWORD)]
            FileDispositionInfoEx = 21
            FILE_DISPOSITION_FLAG_DELETE = 0x00000001
            info = FILE_DISPOSITION_INFO_EX(FILE_DISPOSITION_FLAG_DELETE)
            if not kernel32.SetFileInformationByHandle(handle, FileDispositionInfoEx, ctypes.byref(info), ctypes.sizeof(info)):
                raise PatcherError(f"VV3 individual Full Mastery handle delete failed: {path}")
        finally:
            kernel32.CloseHandle(handle)
        if os.path.lexists(path):
            raise PatcherError(f"VV3 individual Full Mastery file delete postverify failed: {path}")
        return
    raise PatcherError("VV3 individual Full Mastery identity-atomic file deletion is certified only on 64-bit Windows.")


def _delete_directory_by_handle(path: Path, expected: dict[str, object]) -> None:
    """Delete an empty directory through an identity-bound Win64 handle."""
    _require_windows_identity_atomic()
    if os.name != "nt":
        raise PatcherError("VV3 individual Full Mastery identity-atomic directory deletion is certified only on 64-bit Windows.")
    import ctypes
    from ctypes import wintypes
    kernel32 = ctypes.windll.kernel32
    _configure_windows_delete_api(kernel32, ctypes, wintypes)
    GENERIC_READ = 0x80000000
    DELETE = 0x00010000
    FILE_SHARE_READ = 0x00000001
    FILE_SHARE_WRITE = 0x00000002
    FILE_SHARE_DELETE = 0x00000004
    OPEN_EXISTING = 3
    FILE_FLAG_OPEN_REPARSE_POINT = 0x00200000
    FILE_FLAG_BACKUP_SEMANTICS = 0x02000000
    handle = kernel32.CreateFileW(
        str(path), GENERIC_READ | DELETE,
        FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
        None, OPEN_EXISTING,
        FILE_FLAG_OPEN_REPARSE_POINT | FILE_FLAG_BACKUP_SEMANTICS,
        None,
    )
    if handle == ctypes.c_void_p(-1).value:
        raise PatcherError(f"VV3 individual Full Mastery directory delete could not open target: {path}")
    try:
        handle_identity = _get_windows_handle_identity(kernel32, ctypes, wintypes, handle)
        opened = os.lstat(path)
        _reject_entry(path, opened, directory=True)
        if (int(opened.st_dev), int(opened.st_ino)) != (int(expected["st_dev"]), int(expected["st_ino"])):
            raise PatcherError(f"VV3 individual Full Mastery directory delete identity changed: {path}")
        if handle_identity != _get_windows_handle_identity(kernel32, ctypes, wintypes, handle):
            raise PatcherError(f"VV3 individual Full Mastery opened directory handle identity changed: {path}")
        class FILE_DISPOSITION_INFO_EX(ctypes.Structure):
            _fields_ = [("Flags", wintypes.DWORD)]
        info = FILE_DISPOSITION_INFO_EX(0x00000001)
        if not kernel32.SetFileInformationByHandle(handle, 21, ctypes.byref(info), ctypes.sizeof(info)):
            raise PatcherError(f"VV3 individual Full Mastery directory handle delete failed: {path}")
    finally:
        kernel32.CloseHandle(handle)
    if os.path.lexists(path):
        raise PatcherError(f"VV3 individual Full Mastery directory delete postverify failed: {path}")


def _configure_windows_delete_api(kernel32: object, ctypes_module: object, wintypes: object) -> None:
    """Declare the exact 64-bit Win32 signatures used by handle deletion."""
    kernel32.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    kernel32.CreateFileW.restype = wintypes.HANDLE
    kernel32.SetFileInformationByHandle.argtypes = [wintypes.HANDLE, wintypes.INT, wintypes.LPVOID, wintypes.DWORD]
    kernel32.SetFileInformationByHandle.restype = wintypes.BOOL
    kernel32.GetFileInformationByHandleEx.argtypes = [wintypes.HANDLE, wintypes.INT, wintypes.LPVOID, wintypes.DWORD]
    kernel32.GetFileInformationByHandleEx.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL


def _get_windows_handle_identity(kernel32: object, ctypes_module: object, wintypes: object, handle: object) -> tuple[int, bytes]:
    """Return the stable volume/file identity from an open Win64 handle."""
    class FILE_ID_128(ctypes_module.Structure):
        _fields_ = [("Identifier", ctypes_module.c_ubyte * 16)]

    class FILE_ID_INFO(ctypes_module.Structure):
        _fields_ = [("VolumeSerialNumber", ctypes_module.c_ulonglong), ("FileId", FILE_ID_128)]

    info = FILE_ID_INFO()
    FileIdInfo = 18
    if not kernel32.GetFileInformationByHandleEx(handle, FileIdInfo, ctypes_module.byref(info), ctypes_module.sizeof(info)):
        raise PatcherError("VV3 individual Full Mastery could not obtain Win64 handle identity.")
    return int(info.VolumeSerialNumber), bytes(info.FileId.Identifier)


def _inventory_tree(root: Path, *, exclude: set[str] | None = None) -> list[dict[str, object]]:
    """Enumerate every owned recovery descendant without following links."""
    root = _validate_recovery_root(root)
    excluded = {str(item).replace("\\", "/").casefold() for item in (exclude or set())}
    records: list[dict[str, object]] = []
    seen: set[str] = set()

    def walk(directory: Path, prefix: str = "") -> None:
        before = os.lstat(directory)
        _reject_entry(directory, before, directory=True)
        with os.scandir(directory) as scan:
            entries = sorted(list(scan), key=lambda item: (item.name.casefold(), item.name))
        for entry in entries:
            rel = f"{prefix}/{entry.name}" if prefix else entry.name
            rel = rel.replace("\\", "/")
            key = rel.casefold()
            if not key or key in seen or Path(rel).is_absolute() or ".." in Path(rel).parts:
                raise PatcherError(f"VV3 individual Full Mastery recovery inventory collision: {rel}")
            seen.add(key)
            if key in excluded:
                continue
            path = Path(entry.path)
            st = os.lstat(path)
            if stat.S_ISDIR(st.st_mode):
                _reject_entry(path, st, directory=True)
                records.append({"path": rel, "type": "directory", "size": 0, "sha256": None,
                                "st_dev": int(getattr(st, "st_dev", 0)), "st_ino": int(getattr(st, "st_ino", 0))})
                walk(path, rel)
            elif stat.S_ISREG(st.st_mode):
                _reject_entry(path, st, directory=False)
                data = _read_regular(path)
                after = os.lstat(path)
                if (st.st_dev, st.st_ino, st.st_size) != (after.st_dev, after.st_ino, after.st_size):
                    raise PatcherError(f"VV3 individual Full Mastery recovery file identity changed: {path}")
                records.append({"path": rel, "type": "regular_file", "size": len(data), "sha256": _sha(data),
                                "st_dev": int(getattr(st, "st_dev", 0)), "st_ino": int(getattr(st, "st_ino", 0))})
            else:
                raise PatcherError(f"VV3 individual Full Mastery recovery unsupported entry: {path}")
        after = os.lstat(directory)
        if (before.st_dev, before.st_ino, before.st_mode) != (after.st_dev, after.st_ino, after.st_mode):
            raise PatcherError(f"VV3 individual Full Mastery recovery directory identity changed: {directory}")

    walk(root)
    return records


def _verify_inventory(root: Path, expected: list[dict[str, object]], *, exclude: set[str] | None = None) -> None:
    actual = _inventory_tree(root, exclude=exclude)
    normalize = lambda rows: sorted(rows, key=lambda item: str(item["path"]).casefold())
    if normalize(actual) != normalize(expected):
        raise PatcherError("VV3 individual Full Mastery recovery ownership inventory changed.")


def _write_recovery_at(report: Path, payload: dict[str, object], root: Path) -> None:
    _require_windows_identity_atomic()
    refreshed = dict(payload)
    refreshed["report_relative"] = report.name
    if "report_name" in refreshed:
        refreshed["report_name"] = report.name
    allowed = {key for key in ("feature_owner", "mode", "parent_sha256", "candidate_sha256", "destination_exe_basename", "companion_dll_basename", "member_roles", "recovery_root_name", "recovery_root_identity", "report_name", "report_parent_identity", "issuance_token", "issuance_name", "issuance_registry_relative", "issuance_registry_identity", "issuance_identity", "destination_parent_absolute", "destination_paths_absolute") if key in refreshed}
    _validate_recovery_payload(refreshed, root, allowed_metadata=allowed)
    tmp = report.with_suffix(".tmp")
    if os.path.lexists(tmp) or os.path.lexists(report):
        raise PatcherError("VV3 individual Full Mastery recovery report target collision.")
    tmp_identity: dict[str, object] | None = None
    try:
        _write_file(tmp, (json.dumps(refreshed, indent=2, sort_keys=True) + "\n").encode("utf-8"))
        tmp_identity = _inventory_entry(root, tmp)
        if os.path.lexists(report):
            raise PatcherError("VV3 individual Full Mastery recovery report target raced.")
        _publish_exclusive(tmp, report, root)
        _write_chain_manifest(report, refreshed)
    except Exception:
        if os.path.lexists(tmp):
            try:
                if tmp_identity is not None:
                    _remove_owned(tmp, expected=tmp_identity)
            except Exception:
                pass
        raise
    _fsync_dir(root)


def _require_inventory_subset(actual: list[dict[str, object]], expected: object) -> None:
    """Reject foreign/changed descendants while allowing owned members already removed."""
    if not isinstance(expected, list):
        raise PatcherError("VV3 individual Full Mastery recovery inventory baseline is missing.")
    by_path = {str(item.get("path", "")).casefold(): item for item in expected if isinstance(item, dict)}
    for item in actual:
        key = str(item.get("path", "")).casefold()
        if key not in by_path or by_path[key] != item:
            raise PatcherError("VV3 individual Full Mastery recovery ownership inventory adopted a foreign descendant.")


def _extend_owned_cleanup_inventory(root: Path, actual: list[dict[str, object]], expected: object) -> list[dict[str, object]]:
    """Extend a retry baseline only with members named by a verified cleanup journal."""
    if not isinstance(expected, list):
        raise PatcherError("VV3 individual Full Mastery recovery inventory baseline is missing.")
    allowed = list(expected)
    by_path = {str(item.get("path", "")).casefold(): item for item in allowed if isinstance(item, dict)}
    for item in actual:
        path = root / str(item.get("path", ""))
        key = str(item.get("path", "")).casefold()
        if key in by_path:
            continue
        if ".vv3im-cleanup-" not in path.name:
            continue
        try:
            raw = json.loads(_read_regular(path).decode("utf-8"))
        except Exception as exc:
            raise PatcherError("VV3 individual Full Mastery cleanup authority is unreadable during retry.") from exc
        if not isinstance(raw, dict) or raw.get("kind") != "vv3_individual_full_mastery_cleanup_authority" or not isinstance(raw.get("members"), list):
            raise PatcherError("VV3 individual Full Mastery cleanup authority is malformed during retry.")
        allowed.append(item)
        by_path[key] = item
        for member in raw["members"]:
            if not isinstance(member, dict) or not isinstance(member.get("name"), str) or not isinstance(member.get("record"), dict):
                raise PatcherError("VV3 individual Full Mastery cleanup authority member is malformed during retry.")
            owned = path.parent / member["name"]
            rel = _relative_owned(root, owned)
            record = dict(member["record"])
            record["path"] = rel
            allowed.append(record)
            by_path[rel.casefold()] = record
    return allowed


def _report_pointer_path(report: Path) -> Path:
    return report.with_name(f".{report.name}.pointer")


def _load_report_pointer(report: Path, root: Path) -> tuple[Path, dict[str, object], dict[str, object], Path] | None:
    pointer = _report_pointer_path(report)
    if not os.path.lexists(pointer):
        return None
    pointer_record = _inventory_entry(root, pointer)
    raw = json.loads(_read_regular(pointer).decode("utf-8"))
    if not isinstance(raw, dict) or set(raw) != {"schema_version", "kind", "canonical_report", "canonical_record", "successor_name", "successor_record", "report_parent_identity"} or raw.get("schema_version") != 1 or raw.get("kind") != "vv3_recovery_report_pointer" or raw.get("canonical_report") != report.name:
        raise PatcherError("VV3 individual Full Mastery recovery report pointer is malformed.")
    successor_name = raw.get("successor_name")
    if not isinstance(successor_name, str) or Path(successor_name).name != successor_name or not re.fullmatch(re.escape(report.stem) + r"\.v[0-9a-f]{32}" + re.escape(report.suffix), successor_name):
        raise PatcherError("VV3 individual Full Mastery recovery report pointer successor is unsafe.")
    successor = root / successor_name
    successor_record = _inventory_entry(root, successor)
    if successor_record != raw.get("successor_record") or _inventory_entry(root, report) != raw.get("canonical_record"):
        raise PatcherError("VV3 individual Full Mastery recovery report pointer identity changed.")
    parent_st = os.lstat(root)
    if raw.get("report_parent_identity") != {"st_dev": int(parent_st.st_dev), "st_ino": int(parent_st.st_ino)}:
        raise PatcherError("VV3 individual Full Mastery recovery report pointer parent changed.")
    return successor, raw["canonical_record"], pointer_record, pointer


def _report_chain_siblings(parent: Path, report: Path, *, recovery_prefix: str) -> tuple[list[Path], list[Path], list[Path]]:
    """Return canonical reports, exact successors, and emergency markers."""
    canonical_re = re.compile(re.escape(recovery_prefix) + r"-recovery-[0-9a-f]{32}\.json")
    successor_re = re.compile(re.escape(recovery_prefix) + r"-recovery-[0-9a-f]{32}\.v[0-9a-f]{32}\.json")
    emergency_re = re.compile(re.escape(recovery_prefix) + r"-emergency-[0-9a-f]{32}\.json")
    journal_re = re.compile(r"\.vv3im-journal-[0-9a-f]{32}(?:\.v[0-9a-f]{32})?\.json")
    canonical: list[Path] = []
    successors: list[Path] = []
    markers: list[Path] = []
    parent_record = _inventory_entry(parent.parent, parent)
    chain_names: list[str] = []
    pointer_names: list[str] = []
    captured_members: dict[str, dict[str, object]] = {}
    with os.scandir(parent) as scan:
        for entry in scan:
            candidate = Path(entry.path)
            name = entry.name
            if name.startswith(".chain-"):
                st = os.lstat(candidate)
                if not stat.S_ISREG(st.st_mode) or _reject_entry(candidate, st, directory=False):
                    raise PatcherError("VV3 individual Full Mastery recovery chain manifest is unsafe.")
                chain_names.append(name)
                captured_members[name] = _inventory_entry(parent, candidate)
            elif canonical_re.fullmatch(name):
                st = os.lstat(candidate)
                if not stat.S_ISREG(st.st_mode) or _reject_entry(candidate, st, directory=False):
                    raise PatcherError("VV3 individual Full Mastery recovery report is unsafe.")
                canonical.append(candidate)
                captured_members[name] = _inventory_entry(parent, candidate)
            elif successor_re.fullmatch(name):
                st = os.lstat(candidate)
                if not stat.S_ISREG(st.st_mode) or _reject_entry(candidate, st, directory=False):
                    raise PatcherError("VV3 individual Full Mastery recovery successor is unsafe.")
                successors.append(candidate)
                captured_members[name] = _inventory_entry(parent, candidate)
            elif emergency_re.fullmatch(name):
                st = os.lstat(candidate)
                if not stat.S_ISREG(st.st_mode) or _reject_entry(candidate, st, directory=False):
                    raise PatcherError("VV3 individual Full Mastery emergency marker is unsafe.")
                markers.append(candidate)
                captured_members[name] = _inventory_entry(parent, candidate)
            elif name.startswith(".vv3im-journal-"):
                st = os.lstat(candidate)
                if not journal_re.fullmatch(name) or not stat.S_ISREG(st.st_mode) or _reject_entry(candidate, st, directory=False):
                    raise PatcherError("VV3 individual Full Mastery transaction authority journal is unsafe.")
                captured_members[name] = _inventory_entry(parent, candidate)
            elif name.startswith(f".{recovery_prefix}-") and name.endswith(".pointer"):
                st = os.lstat(candidate)
                if not stat.S_ISREG(st.st_mode) or _reject_entry(candidate, st, directory=False):
                    raise PatcherError("VV3 individual Full Mastery recovery pointer is unsafe.")
                pointer_names.append(name)
                captured_members[name] = _inventory_entry(parent, candidate)
    known_names = {path.name for path in (*canonical, *successors, *markers)}
    orphan_chain_names = [name for name in chain_names if name[len(".chain-"):-len(".json")] not in known_names]
    if orphan_chain_names and not markers:
        raise PatcherError("VV3 individual Full Mastery recovery chain manifest is orphaned or foreign.")
    for pointer_name in pointer_names:
        target = pointer_name[1:-len(".pointer")]
        if target not in known_names:
            raise PatcherError("VV3 individual Full Mastery recovery pointer is orphaned or foreign.")
    for chain_name in chain_names:
        _validate_chain_manifest_binding(parent / chain_name, parent, recovery_prefix=recovery_prefix, known_names=known_names)
    # Every chain member is recaptured after complete discovery.  Names and
    # types alone cannot detect a same-content inode replacement or a bytes
    # substitution that occurred during the scan.
    for name, captured in captured_members.items():
        current = _inventory_entry(parent, parent / name)
        if current != captured:
            raise PatcherError("VV3 individual Full Mastery recovery chain member changed after discovery.")
    if _inventory_entry(parent.parent, parent) != parent_record:
        raise PatcherError("VV3 individual Full Mastery recovery report parent changed during discovery.")
    return canonical, successors, markers


def _orphan_chain_manifests(parent: Path, known_names: set[str], *, recovery_prefix: str = ".vv3im") -> list[Path]:
    """Return orphan chain manifests for emergency compatibility checking."""
    found: list[Path] = []
    with os.scandir(parent) as scan:
        for entry in scan:
            if not entry.name.startswith(".chain-"):
                continue
            target = entry.name[len(".chain-"):-len(".json")] if entry.name.endswith(".json") else ""
            if target not in known_names:
                candidate = Path(entry.path)
                st = os.lstat(candidate)
                if not stat.S_ISREG(st.st_mode) or _reject_entry(candidate, st, directory=False):
                    raise PatcherError("VV3 individual Full Mastery orphan chain manifest is unsafe.")
                _validate_chain_manifest_binding(candidate, parent, recovery_prefix=recovery_prefix, known_names=known_names)
                found.append(candidate)
    return found


def _validate_chain_manifest_binding(manifest: Path, parent: Path, *, recovery_prefix: str, known_names: set[str]) -> None:
    """Validate one chain manifest as a closed, report-bound state record."""
    name = manifest.name
    if not re.fullmatch(r"\.chain-.+\.json", name):
        raise PatcherError("VV3 individual Full Mastery chain manifest filename role is invalid.")
    target = name[len(".chain-"):-len(".json")]
    canonical_re = re.escape(recovery_prefix) + r"-recovery-[0-9a-f]{32}\.json"
    successor_re = re.escape(recovery_prefix) + r"-recovery-[0-9a-f]{32}\.v[0-9a-f]{32}\.json"
    emergency_re = re.escape(recovery_prefix) + r"-emergency-[0-9a-f]{32}\.json"
    if not (re.fullmatch(canonical_re, target) or re.fullmatch(successor_re, target) or re.fullmatch(emergency_re, target)):
        raise PatcherError("VV3 individual Full Mastery chain manifest prefix or report role is invalid.")
    raw = json.loads(_read_regular(manifest).decode("utf-8"))
    required = {"schema_version", "kind", "transaction_journal", "recovery_prefix", "report_name", "report_record", "canonical_name", "canonical_record", "pointer_name", "pointer_record", "successor_name", "successor_record", "marker_name", "marker_record", "recovery_root_name", "recovery_root_record", "ownership_inventory", "members", "member_roles", "destination_paths_absolute"}
    if not isinstance(raw, dict) or set(raw) != required or raw.get("schema_version") != 3 or raw.get("kind") != "vv3_recovery_chain_manifest":
        raise PatcherError("VV3 individual Full Mastery chain manifest schema is unsupported.")
    journal_state = _journal_state(raw)
    if raw.get("recovery_prefix") != recovery_prefix or raw.get("report_name") != target:
        raise PatcherError("VV3 individual Full Mastery chain manifest report binding is invalid.")
    target_known = target in known_names
    if target_known:
        target_path = parent / target
        target_record = _inventory_entry(parent, target_path)
        if raw.get("report_record") != target_record:
            raise PatcherError("VV3 individual Full Mastery chain manifest report identity changed.")
        effective = json.loads(_read_regular(target_path).decode("utf-8"))
        if isinstance(effective, dict) and effective.get("kind") == "emergency_recovery_marker":
            effective = effective.get("recovery_payload")
        effective_members = effective.get("members") if isinstance(effective, dict) else None
        effective_roles = effective.get("member_roles") if isinstance(effective, dict) else None
        effective_destinations = effective.get("destination_paths_absolute") if isinstance(effective, dict) else None
        if isinstance(effective_members, list):
            effective_roles = effective_roles or {
                str(member.get("destination_relative")): "recovery_member"
                for member in effective_members
                if isinstance(member, dict) and isinstance(member.get("destination_relative"), str)
            }
            effective_destinations = effective_destinations or [
                str(member.get("destination_relative"))
                for member in effective_members
                if isinstance(member, dict) and isinstance(member.get("destination_relative"), str)
            ]
        if not isinstance(effective, dict) or raw.get("members") != effective_members or raw.get("ownership_inventory") != effective.get("ownership_inventory") or raw.get("member_roles") != (effective_roles or {}) or raw.get("destination_paths_absolute") != (effective_destinations or []):
            raise PatcherError("VV3 individual Full Mastery chain manifest does not bind its report payload.")
    members = raw.get("members")
    roles = raw.get("member_roles")
    destinations = raw.get("destination_paths_absolute")
    if not isinstance(members, list) or not isinstance(roles, dict) or not isinstance(destinations, list):
        raise PatcherError("VV3 individual Full Mastery chain manifest ownership is incomplete.")
    member_paths = [str(item.get("destination_relative")) for item in members if isinstance(item, dict) and isinstance(item.get("destination_relative"), str)]
    if len(member_paths) != len(members) or len({p.casefold() for p in member_paths}) != len(member_paths) or set(roles) != set(member_paths) or any(not isinstance(value, str) or value not in {"recovery_member", "game_executable", "companion_dll"} for value in roles.values()) or len({str(p).casefold() for p in destinations}) != len(destinations):
        raise PatcherError("VV3 individual Full Mastery chain manifest members/roles/destinations are ambiguous.")
    if re.fullmatch(successor_re, target) and journal_state != "successor_pointer_manifest":
        raise PatcherError("VV3 individual Full Mastery successor chain commit state is incomplete.")
    if re.fullmatch(emergency_re, target) and journal_state != "emergency_marker":
        raise PatcherError("VV3 individual Full Mastery emergency chain commit state is invalid.")
    ownership = raw.get("ownership_inventory")
    if not isinstance(ownership, list):
        raise PatcherError("VV3 individual Full Mastery chain manifest inventory is missing.")
    inventory_paths = [str(item.get("path")) for item in ownership if isinstance(item, dict)]
    if len(inventory_paths) != len(ownership) or len({p.casefold() for p in inventory_paths}) != len(inventory_paths) or any(Path(p).is_absolute() or not Path(p).parts or ".." in Path(p).parts for p in inventory_paths):
        raise PatcherError("VV3 individual Full Mastery chain manifest inventory is unsafe or duplicated.")
    for key, expected_name, expected_record in (("canonical_name", "canonical_record", raw.get("canonical_record")), ("pointer_name", "pointer_record", raw.get("pointer_record")), ("successor_name", "successor_record", raw.get("successor_record")), ("marker_name", "marker_record", raw.get("marker_record"))):
        member_name = raw.get(key)
        member_record = raw.get(expected_name)
        if member_name is None:
            if member_record is not None:
                raise PatcherError("VV3 individual Full Mastery chain member presence is inconsistent.")
            continue
        if not isinstance(member_name, str) or Path(member_name).name != member_name or member_name == name or not isinstance(member_record, dict):
            raise PatcherError("VV3 individual Full Mastery chain member identity is invalid.")
        if target_known and _inventory_entry(parent, parent / member_name) != member_record:
            raise PatcherError("VV3 individual Full Mastery chain member identity changed.")


def _refresh_recovery_report(report: Path, payload: dict[str, object], root: Path, replay_root: Path) -> None:
    """Persist the actual retained recovery inventory after a failed replay."""
    _require_windows_identity_atomic()
    active_report = report
    canonical_report = report
    # A replay through a version pointer operates on the active successor,
    # but the durable pointer belongs to the original canonical report.  Walk
    # that relationship before publishing the next successor so retries do
    # not create nested, orphaned pointer chains.
    if re.search(r"-recovery-[0-9a-f]{32}\.v[0-9a-f]{32}$", report.stem):
        sibling_reports, _sibling_successors, _sibling_markers = _report_chain_siblings(root, report, recovery_prefix=".vv3im")
        for candidate in sibling_reports:
            try:
                pointer_info = _load_report_pointer(candidate, root)
            except Exception:
                continue
            if pointer_info is not None and pointer_info[0] == report:
                canonical_report = candidate
                break
    report = canonical_report
    if not os.path.lexists(report):
        root_st = os.lstat(replay_root)
        inventory = _inventory_tree(replay_root)
        for item in inventory:
            item["path"] = _relative_owned(root, replay_root / str(item["path"]))
        inventory.insert(0, {"path": _relative_owned(root, replay_root), "type": "directory", "size": 0, "sha256": None, "st_dev": int(root_st.st_dev), "st_ino": int(root_st.st_ino)})
        _require_inventory_subset(inventory, _extend_owned_cleanup_inventory(root, inventory, payload.get("ownership_inventory")))
        refreshed = dict(payload)
        refreshed["ownership_inventory"] = inventory
        refreshed["report_relative"] = report.name
        if "report_name" in refreshed:
            refreshed["report_name"] = report.name
        stale_manifest = _chain_manifest_path(report)
        if os.path.lexists(stale_manifest):
            _remove_owned(stale_manifest, expected=_inventory_entry(root, stale_manifest))
        return _write_recovery_at(report, refreshed, root)
    report_before = os.lstat(report)
    _reject_entry(report, report_before, directory=False)
    old_manifest, old_manifest_record, _old_manifest_payload = _read_chain_manifest(report)
    old_active_manifest: Path | None = None
    old_active_manifest_record: dict[str, object] | None = None
    if active_report != report and os.path.lexists(_chain_manifest_path(active_report)):
        old_active_manifest = _chain_manifest_path(active_report)
        old_active_manifest_record = _inventory_entry(root, old_active_manifest)
    inventory = _inventory_tree(replay_root)
    for item in inventory:
        item["path"] = _relative_owned(root, replay_root / str(item["path"]))
    root_st = os.lstat(replay_root)
    inventory.insert(0, {"path": _relative_owned(root, replay_root), "type": "directory", "size": 0, "sha256": None, "st_dev": int(root_st.st_dev), "st_ino": int(root_st.st_ino)})
    _require_inventory_subset(inventory, _extend_owned_cleanup_inventory(root, inventory, payload.get("ownership_inventory")))
    refreshed = dict(payload)
    refreshed["ownership_inventory"] = inventory
    refreshed_members = []
    for member in payload["members"]:
        updated = dict(member)
        for field in ("backup_relative", "stage_relative"):
            rel = updated.get(field)
            owned = root / str(rel) if rel else None
            inventory_key = field.replace("_relative", "_inventory")
            updated[inventory_key] = _inventory_member(root, owned)
            if field == "stage_relative" and updated[inventory_key] is None:
                updated[field] = None
        refreshed_members.append(updated)
    refreshed["members"] = refreshed_members
    _validate_recovery_payload(
        refreshed,
        root,
        allowed_metadata={
            key
            for key in (
                "feature_owner",
                "mode",
                "parent_sha256",
                "candidate_sha256",
                "destination_exe_basename",
                "companion_dll_basename",
                "member_roles",
                "recovery_root_name",
                "recovery_root_identity",
                "report_name",
                "report_parent_identity",
                "issuance_token",
                "issuance_name",
                "issuance_registry_relative",
                "issuance_registry_identity",
                "issuance_identity",
                "destination_parent_absolute",
                "destination_paths_absolute",
            )
            if key in refreshed
        },
    )
    now = os.lstat(report)
    _reject_entry(report, now, directory=False)
    if (report_before.st_dev, report_before.st_ino, report_before.st_size) != (now.st_dev, now.st_ino, now.st_size):
        raise PatcherError("VV3 individual Full Mastery recovery report race during refresh.")
    pointer = _report_pointer_path(report)
    if os.path.lexists(pointer):
        raise PatcherError("VV3 individual Full Mastery recovery report already has a version pointer.")
    successor = report.with_name(f"{report.stem}.v{uuid.uuid4().hex}{report.suffix}")
    successor_tmp = successor.with_suffix(".tmp")
    pointer_tmp = pointer.with_suffix(".tmp")
    successor_record: dict[str, object] | None = None
    pointer_tmp_record: dict[str, object] | None = None
    pointer_published = False
    try:
        refreshed["report_relative"] = successor.name
        if "report_name" in refreshed:
            refreshed["report_name"] = successor.name
        _validate_recovery_payload(
            refreshed,
            root,
            allowed_metadata={
                key
                for key in (
                    "feature_owner", "mode", "parent_sha256", "candidate_sha256", "destination_exe_basename", "companion_dll_basename", "member_roles", "recovery_root_name", "recovery_root_identity", "report_name", "report_parent_identity", "issuance_token", "issuance_name", "issuance_registry_relative", "issuance_registry_identity", "issuance_identity", "destination_parent_absolute", "destination_paths_absolute"
                )
                if key in refreshed
            },
        )
        _write_file(successor_tmp, (json.dumps(refreshed, indent=2, sort_keys=True) + "\n").encode("utf-8"))
        _publish_exclusive(successor_tmp, successor, root)
        successor_record = _inventory_entry(root, successor)
        pointer_payload = {
            "schema_version": 1,
            "kind": "vv3_recovery_report_pointer",
            "canonical_report": report.name,
            "canonical_record": _inventory_entry(root, report),
            "successor_name": successor.name,
            "successor_record": successor_record,
            "report_parent_identity": {"st_dev": int(os.lstat(root).st_dev), "st_ino": int(os.lstat(root).st_ino)},
        }
        if os.path.lexists(pointer):
            raise PatcherError("VV3 individual Full Mastery recovery report pointer target raced.")
        _write_file(pointer_tmp, (json.dumps(pointer_payload, indent=2, sort_keys=True) + "\n").encode("utf-8"))
        pointer_tmp_record = _inventory_entry(root, pointer_tmp)
        _publish_exclusive(pointer_tmp, pointer, root)
        pointer_published = True
        _load_report_pointer(report, root)
        _write_chain_manifest(
            successor,
            refreshed,
            canonical_name=report.name,
            pointer_name=pointer.name,
            successor_name=successor.name,
            commit_state="successor_pointer_manifest",
        )
        _remove_owned(old_manifest, expected=old_manifest_record)
        old_journal = _transaction_authority_path(old_manifest)
        if os.path.lexists(old_journal):
            _delete_file_by_handle(old_journal, _inventory_entry(root, old_journal))
        if old_active_manifest is not None and os.path.lexists(old_active_manifest):
            _remove_owned(old_active_manifest, expected=old_active_manifest_record)
            old_active_journal = _transaction_authority_path(old_active_manifest)
            if os.path.lexists(old_active_journal):
                _delete_file_by_handle(old_active_journal, _inventory_entry(root, old_active_journal))
    except Exception:
        for temp, record in ((successor_tmp, None), (pointer_tmp, pointer_tmp_record)):
            if os.path.lexists(temp):
                try:
                    if record is None:
                        record = _inventory_entry(root, temp)
                    _remove_owned(temp, expected=record)
                except Exception:
                    pass
        # A successor is owned only once its pointer is published.  If the
        # pointer target raced, remove that unreferenced successor by its
        # captured identity so it cannot become unreported recovery residue.
        if successor_record is not None and os.path.lexists(successor) and not pointer_published:
            try:
                _remove_owned(successor, expected=successor_record)
            except Exception:
                # Preserve the successor when its identity changed; the
                # caller will retain durable emergency evidence and fail
                # closed rather than deleting foreign material.
                pass
        raise
    _fsync_dir(root)


def _validate_recovery_payload(payload: dict[str, object], root: Path, *, allowed_metadata: set[str] | None = None) -> None:
    required = {"schema_version", "operation", "recovery_root", "destination_parent", "report_relative", "initial_precondition", "replay_guard", "members", "ownership_inventory", "failure_diagnostic"}
    optional = set(allowed_metadata or ())
    if not isinstance(payload, dict) or not required.issubset(payload) or set(payload) - required - optional or payload.get("schema_version") != 2:
        raise PatcherError("VV3 individual Full Mastery recovery schema is unsupported or ambiguous.")
    if payload.get("feature_owner") == "vv5_individual_grant_running_candidate" and payload.get("vv5_schema") != "vv5_running_recovery_v2":
        raise PatcherError("VV5 Running recovery caller schema is unsupported or ambiguous.")
    if payload.get("feature_owner") != "vv5_individual_grant_running_candidate" and "vv5_schema" in payload:
        raise PatcherError("VV5 Running metadata is not valid for this recovery caller.")
    if payload.get("feature_owner") not in {"vv3_individual_full_mastery", "vv5_individual_grant_running_candidate"}:
        raise PatcherError("Current recovery report has no strict feature owner.")
    owner = payload["feature_owner"]
    caller_required = VV3_RECOVERY_METADATA_REQUIRED if owner == "vv3_individual_full_mastery" else VV5_RECOVERY_METADATA_REQUIRED
    caller_forbidden = VV3_RECOVERY_METADATA_FORBIDDEN if owner == "vv3_individual_full_mastery" else set()
    if not caller_required.issubset(payload) or caller_forbidden.intersection(payload):
        raise PatcherError("Current recovery report does not satisfy its exact caller schema.")
    if allowed_metadata is not None and set(allowed_metadata) != (set(payload) - required):
        raise PatcherError("Current recovery report metadata envelope is not exact for its caller.")
    if owner == "vv5_individual_grant_running_candidate" and payload.get("vv5_schema") != "vv5_running_recovery_v2":
        raise PatcherError("VV5 Running recovery caller schema is unsupported or ambiguous.")
    expected_parent = str(root.absolute()).casefold()
    if payload.get("destination_parent_absolute") != expected_parent:
        raise PatcherError("Current recovery report destination parent is missing or relocated.")
    parent_identity = payload.get("report_parent_identity")
    actual_parent = _inventory_entry(root.parent, root)
    if not isinstance(parent_identity, dict) or any(actual_parent.get(key) != parent_identity.get(key) for key in ("st_dev", "st_ino")):
        raise PatcherError("Current recovery report parent identity is missing or changed.")
    if payload["operation"] not in {"install_new", "install_existing", "removal"} or payload["recovery_root"] != "." or payload["destination_parent"] != "." or not isinstance(payload["report_relative"], str) or Path(payload["report_relative"]).name != payload["report_relative"]:
        raise PatcherError("VV3 individual Full Mastery recovery operation/root contract is invalid.")
    initial = payload["initial_precondition"]
    if not isinstance(initial, dict) or set(initial) != {"kind", "members"} or initial["kind"] not in {"absent", "pair"}:
        raise PatcherError("VV3 individual Full Mastery initial precondition is invalid.")
    if payload["operation"] == "install_new" and initial["kind"] != "absent":
        raise PatcherError("install_new requires an immutable absent precondition.")
    if payload["operation"] != "install_new" and initial["kind"] != "pair":
        raise PatcherError("VV3 recovery operation requires an owned pair precondition.")
    guard = payload["replay_guard"]
    if not isinstance(guard, dict) or set(guard) != {"kind", "members"}:
        raise PatcherError("VV3 individual Full Mastery replay guard schema is invalid.")
    expected_guard_kind = "absent" if payload["operation"] == "install_new" else "pair"
    if guard["kind"] != expected_guard_kind or not isinstance(guard["members"], list):
        raise PatcherError("VV3 individual Full Mastery replay guard operation is invalid.")
    members = payload["members"]
    if not isinstance(members, list) or len(members) != 2:
        raise PatcherError("VV3 individual Full Mastery recovery requires exactly two members.")
    member_keys = {"destination_relative", "destination_type", "pre_exists", "pre_sha256", "pre_size", "published_sha256", "published_size", "backup_relative", "stage_relative", "backup_inventory", "stage_inventory", "published_inventory"}
    seen: set[str] = set()
    for member in members:
        if not isinstance(member, dict) or set(member) != member_keys or member["destination_type"] != "regular_file":
            raise PatcherError("VV3 individual Full Mastery recovery member schema is invalid.")
        if not isinstance(member["pre_exists"], bool):
            raise PatcherError("VV3 individual Full Mastery recovery pre_exists type is invalid.")
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
            if member[field] is not None and (not isinstance(member[field], str) or len(member[field]) != 64 or any(ch not in "0123456789abcdefABCDEF" for ch in member[field])):
                raise PatcherError("VV3 individual Full Mastery recovery hash is malformed.")
        for field in ("pre_size", "published_size"):
            if not isinstance(member[field], int) or member[field] < 0:
                raise PatcherError("VV3 individual Full Mastery recovery size is malformed.")
        for field in ("backup_inventory", "stage_inventory", "published_inventory"):
            inv = member[field]
            if inv is not None:
                if not isinstance(inv, dict) or set(inv) != {"path", "type", "size", "sha256", "st_dev", "st_ino"} or inv["type"] != "regular_file" or not isinstance(inv["size"], int) or not isinstance(inv["sha256"], str) or len(inv["sha256"]) != 64:
                    raise PatcherError("VV3 individual Full Mastery recovery inventory is malformed.")
    guard_paths = [Path(str(item)) for item in guard["members"]]
    member_paths = [Path(str(item["destination_relative"])) for item in members]
    if guard_paths != member_paths or any(p.is_absolute() or not p.parts or ".." in p.parts for p in guard_paths):
        raise PatcherError("VV3 individual Full Mastery replay guard members do not match destinations.")
    initial_members = initial["members"]
    if not isinstance(initial_members, list) or len(initial_members) != len(members):
        raise PatcherError("VV3 individual Full Mastery initial precondition members are incomplete.")
    for initial_member, member in zip(initial_members, members):
        if not isinstance(initial_member, dict) or set(initial_member) != {"path", "exists", "sha256", "size"}:
            raise PatcherError("VV3 individual Full Mastery initial precondition member schema is invalid.")
        if str(initial_member["path"]).replace("\\", "/") != str(member["destination_relative"]).replace("\\", "/"):
            raise PatcherError("VV3 individual Full Mastery initial precondition path mismatch.")
        if initial_member["exists"] is not member["pre_exists"] or initial_member["sha256"] != member["pre_sha256"] or initial_member["size"] != member["pre_size"]:
            raise PatcherError("VV3 individual Full Mastery initial precondition does not bind member prestate.")
    if payload["operation"] == "install_new" and any(bool(member["pre_exists"]) for member in members):
        raise PatcherError("VV3 individual Full Mastery install_new precondition is not immutable-absent.")
    inventory = payload["ownership_inventory"]
    if not isinstance(inventory, list):
        raise PatcherError("VV3 individual Full Mastery recovery ownership inventory is malformed.")
    seen_inventory: set[str] = set()
    for item in inventory:
        if not isinstance(item, dict) or set(item) != {"path", "type", "size", "sha256", "st_dev", "st_ino"} or item["type"] not in {"regular_file", "directory"}:
            raise PatcherError("VV3 individual Full Mastery recovery ownership item is malformed.")
        rel = Path(str(item["path"]))
        key = rel.as_posix().casefold()
        if rel.is_absolute() or not rel.parts or ".." in rel.parts or key in seen_inventory:
            raise PatcherError("VV3 individual Full Mastery recovery ownership path is unsafe or duplicated.")
        if item["type"] == "regular_file" and (not isinstance(item["sha256"], str) or len(item["sha256"]) != 64):
            raise PatcherError("VV3 individual Full Mastery recovery ownership hash is malformed.")
        if item["type"] == "directory" and item["sha256"] is not None:
            raise PatcherError("VV3 individual Full Mastery recovery directory hash is invalid.")
        if not isinstance(item["size"], int) or item["size"] < 0:
            raise PatcherError("VV3 individual Full Mastery recovery ownership size is invalid.")
        seen_inventory.add(key)


def _remove_owned(path: Path, *, expected: dict[str, object] | None = None, expected_tree: list[dict[str, object]] | None = None) -> None:
    _require_windows_identity_atomic()
    if not os.path.lexists(path):
        if expected is not None or expected_tree is not None:
            raise PatcherError(f"VV3 individual Full Mastery cleanup target disappeared: {path}")
        return
    if expected is None and expected_tree is None:
        raise PatcherError(f"VV3 individual Full Mastery deletion identity is missing: {path}")
    st = os.lstat(path)
    _reject_entry(path, st)
    if expected is not None:
        expected_type = expected.get("type")
        actual_type = "directory" if stat.S_ISDIR(st.st_mode) else "regular_file" if stat.S_ISREG(st.st_mode) else "other"
        if expected_type != actual_type:
            raise PatcherError(f"VV3 individual Full Mastery owned cleanup type changed: {path}")
        if int(expected.get("st_dev", st.st_dev)) != st.st_dev or int(expected.get("st_ino", st.st_ino)) != st.st_ino:
            raise PatcherError(f"VV3 individual Full Mastery owned cleanup identity changed: {path}")
    if stat.S_ISDIR(st.st_mode):
        expected_by_path: dict[str, dict[str, object]] = {}
        if expected_tree is not None:
            actual_tree = _inventory_tree(path)
            normalize = lambda rows: sorted(rows, key=lambda item: str(item["path"]).casefold())
            if normalize(actual_tree) != normalize(expected_tree):
                raise PatcherError(f"VV3 individual Full Mastery owned cleanup inventory changed: {path}")
            expected_by_path = {str(item["path"]): item for item in expected_tree}
        else:
            _inventory_tree(path)
        with os.scandir(path) as scan:
            children = sorted([Path(item.path) for item in scan], key=lambda item: (item.name.casefold(), item.name))
        for child in children:
            child_key = child.name.replace("\\", "/")
            if expected_tree is not None and child_key not in expected_by_path:
                raise PatcherError(f"VV3 individual Full Mastery owned cleanup child is unrecorded: {child}")
            child_record = expected_by_path.get(child_key)
            if child_record is not None and child_record.get("type") == "directory":
                child_prefix = child_key + "/"
                child_tree = [{**item, "path": str(item["path"])[len(child_prefix):]} for item in expected_tree or [] if str(item["path"]).startswith(child_prefix)]
                _remove_owned(child, expected=child_record, expected_tree=child_tree)
            else:
                _remove_owned(child, expected=child_record)
        before = os.lstat(path)
        _reject_entry(path, before, directory=True)
        if (before.st_dev, before.st_ino) != (st.st_dev, st.st_ino):
            raise PatcherError(f"VV3 individual Full Mastery cleanup directory identity changed: {path}")
        _quarantine_delete(path, expected, directory=True)
        return
    if not stat.S_ISREG(st.st_mode):
        raise PatcherError(f"VV3 individual Full Mastery unsafe cleanup member: {path}")
    checked = _read_regular(path)
    if expected is not None:
        if expected.get("type") != "regular_file" or _sha(checked) != str(expected.get("sha256", "")).upper() or len(checked) != int(expected.get("size", -1)):
            raise PatcherError(f"VV3 individual Full Mastery cleanup content changed: {path}")
        if int(expected.get("st_dev", st.st_dev)) != st.st_dev or int(expected.get("st_ino", st.st_ino)) != st.st_ino:
            raise PatcherError(f"VV3 individual Full Mastery cleanup identity changed: {path}")
    st2 = os.lstat(path)
    _reject_entry(path, st2, directory=False)
    if (st.st_dev, st.st_ino, st.st_size) != (st2.st_dev, st2.st_ino, st2.st_size):
        raise PatcherError(f"VV3 individual Full Mastery cleanup identity changed: {path}")
    _quarantine_delete(path, expected or _inventory_entry(path.parent, path), directory=False)


def _cleanup_authority_path(parent: Path) -> Path:
    return parent / f".vv3im-cleanup-{uuid.uuid4().hex}.json"


def _validate_vv3_hidden_namespace(parent: Path, *, expected: set[str] | None = None) -> None:
    """Reject arbitrary VV3 hidden residue before claiming cleanup success.

    Pattern-shaped names are not ownership proof.  Callers that are in a
    cleanup transaction pass the exact captured hidden-member set; the
    directory is then compared as a complete namespace before success.
    """
    if expected is not None:
        actual = {entry.name for entry in os.scandir(parent) if "vv3im-" in entry.name}
        if actual != set(expected):
            raise PatcherError(f"VV3 individual Full Mastery hidden namespace inventory changed or contains foreign residue: expected={sorted(expected)!r} actual={sorted(actual)!r}.")
        for name in actual:
            _inventory_entry(parent, parent / name)
        return
    def owned_name(name: str) -> bool:
        if name in {".vv3im-recovery-root", ".vv3im-recovery-test"}:
            return True
        for marker in ("vv3im-recovery-", "vv3im-emergency-", "vv3im-journal-", "vv3im-issuance-", "vv3im-tombstone-", "vv3im-preserved-guard-", "vv3im-preserved-", "vv3im-cleanup-", "vv3im-replay-", "vv3im-restore-"):
            start = name.find(marker)
            if start < 0:
                continue
            suffix = name[start + len(marker):]
            if len(suffix) < 32 or not re.fullmatch(r"[0-9a-f]{32}", suffix[:32]):
                continue
            tail = suffix[32:]
            if marker in ("vv3im-recovery-", "vv3im-emergency-") and tail and not tail.startswith((".json", ".v")):
                continue
            if marker in ("vv3im-journal-", "vv3im-issuance-") and tail != ".json":
                continue
            if marker in ("vv3im-tombstone-",) and tail:
                continue
            if marker == "vv3im-preserved-guard-" and tail != ".backup":
                continue
            if marker == "vv3im-preserved-" and tail != ".backup" and not (tail.startswith("-") and tail.endswith(".backup")):
                continue
            if marker in ("vv3im-cleanup-",) and tail != ".json":
                continue
            if marker in ("vv3im-replay-", "vv3im-restore-") and tail != ".stage":
                continue
            return True
        start = name.find("vv3im-")
        if start >= 0:
            suffix = name[start + len("vv3im-"):]
            if len(suffix) >= 32 and re.fullmatch(r"[0-9a-f]{32}", suffix[:32]) and suffix[32:] in (".backup", ".stage"):
                return True
        return False
    with os.scandir(parent) as entries:
        for entry in entries:
            if "vv3im-" in entry.name and not owned_name(entry.name):
                raise PatcherError("VV3 individual Full Mastery hidden namespace contains foreign residue.")


def _write_cleanup_authority(parent: Path, members: list[dict[str, object]]) -> tuple[Path, dict[str, object]]:
    """Record final guard cleanup before the first destructive deletion."""
    _require_windows_identity_atomic()
    path = _cleanup_authority_path(parent)
    parent_identity = _inventory_entry(parent.parent, parent)
    if parent_identity is None:
        raise PatcherError("VV3 individual Full Mastery cleanup authority parent is unavailable.")
    if not isinstance(members, list) or any(not isinstance(item, dict) for item in members):
        raise PatcherError("VV3 individual Full Mastery cleanup authority members are malformed.")
    member_blob = json.dumps(members, sort_keys=True, separators=(",", ":")).encode("utf-8")
    authority_token = uuid.uuid4().hex
    # The cleanup journal must bind to evidence that existed before the
    # journal itself.  Issue a separate transaction record first; a digest or
    # token computed only inside the cleanup authority is not sufficient.
    issuance = None
    issuance_payload = None
    retire_issuance = True
    member_digest = _sha(member_blob)
    member_names = [item.get("name") for item in members]
    member_roles = {str(item.get("name")): item.get("role") for item in members}
    with os.scandir(parent) as entries:
        for entry in entries:
            if entry.name.startswith(".vv3im-issuance-") and entry.name.endswith(".json"):
                candidate = Path(entry.path)
                try:
                    candidate_payload = json.loads(_read_regular(candidate).decode("utf-8"))
                except Exception:
                    continue
                if (
                    isinstance(candidate_payload, dict)
                    and candidate_payload.get("feature_owner") == "vv3_individual_full_mastery"
                    and candidate_payload.get("kind") == "vv3_cleanup_transaction_issuance"
                    and candidate_payload.get("owner_parent_identity") == parent_identity
                    and candidate_payload.get("member_digest") == member_digest
                    and candidate_payload.get("member_names") == member_names
                    and candidate_payload.get("member_roles") == member_roles
                ):
                    issuance = candidate
                    issuance_payload = candidate_payload
                    retire_issuance = True
                    break
    if issuance is None:
        issuance = parent / f".vv3im-issuance-{uuid.uuid4().hex}.json"
        issuance_payload = {
            "schema_version": 1,
            "kind": "vv3_cleanup_transaction_issuance",
            "feature_owner": "vv3_individual_full_mastery",
            "operation": "owned_deletion",
            "owner_parent_identity": parent_identity,
            "member_digest": member_digest,
            "member_names": member_names,
            "member_roles": member_roles,
        }
        _write_file(issuance, (json.dumps(issuance_payload, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    issuance_record = _inventory_entry(parent, issuance)
    if issuance_record is None:
        raise PatcherError("VV3 individual Full Mastery cleanup issuance was not captured.")
    namespace_inventory = [
        _inventory_entry(parent, Path(entry.path))
        for entry in os.scandir(parent)
        if "vv3im-" in entry.name
    ]
    payload = {
        "schema_version": 2,
        "kind": "vv3_individual_full_mastery_cleanup_authority",
        "feature_owner": "vv3_individual_full_mastery",
        "operation": "owned_deletion",
        "state": "started",
        "record_version": 1,
        "previous_record_name": None,
        "previous_record_identity": None,
        "parent_identity": parent_identity,
        "authority_binding": {
            "token": authority_token,
            "owner": "vv3_individual_full_mastery",
            "operation": "owned_deletion",
            "parent_identity": parent_identity,
            "member_digest": _sha(member_blob),
        },
        "transaction_binding": {
            "owner": "vv3_individual_full_mastery",
            "operation": "owned_deletion",
            "parent_identity": parent_identity,
            "member_names": [item.get("name") for item in members],
            "member_roles": {str(item.get("name")): item.get("role") for item in members},
        },
        "external_issuance": {
            "name": issuance.name,
            "record": issuance_record,
            "payload": issuance_payload,
            "retire_on_cleanup": retire_issuance,
        },
        "namespace_inventory": namespace_inventory,
        "members": members,
    }
    tmp = path.with_suffix(".tmp")
    data = (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")
    tmp_record: dict[str, object] | None = None
    try:
        _write_file(tmp, data)
        tmp_record = _inventory_entry(parent, tmp)
    except Exception as exc:
        if os.path.lexists(tmp):
            tmp_record = _inventory_entry(parent, tmp)
            if tmp_record.get("type") != "regular_file" or tmp_record.get("size") != len(data) or tmp_record.get("sha256") != _sha(data):
                raise PatcherError("VV3 individual Full Mastery cleanup authority temporary is incomplete.") from exc
        else:
            raise
    try:
        _publish_exclusive(tmp, path, parent)
        record = _inventory_entry(parent, path)
        if record.get("path") != path.name or record.get("size") != len(data) or record.get("sha256") != _sha(data):
            raise PatcherError("VV3 individual Full Mastery cleanup authority postverify failed.")
    except Exception:
        # Never consume a prior valid authority or leave an untracked temp.
        if os.path.lexists(tmp) and tmp_record is not None:
            try:
                _delete_file_by_handle(tmp, tmp_record)
            except Exception:
                pass
        raise
    return path, record


def recover_cleanup_authority(record_path: Path) -> None:
    """Replay retained VV3 guard cleanup without consuming foreign material."""
    _require_windows_identity_atomic()
    record_path = Path(record_path)
    authority_record = _inventory_entry(record_path.parent, record_path)
    if authority_record is None:
        raise PatcherError("VV3 individual Full Mastery cleanup authority is missing.")
    raw = json.loads(_read_regular(record_path).decode("utf-8"))
    required = {"schema_version", "kind", "feature_owner", "operation", "state", "record_version", "previous_record_name", "previous_record_identity", "parent_identity", "authority_binding", "transaction_binding", "external_issuance", "namespace_inventory", "members"}
    if not isinstance(raw, dict) or set(raw) != required or raw.get("schema_version") != 2 or raw.get("kind") != "vv3_individual_full_mastery_cleanup_authority" or raw.get("feature_owner") != "vv3_individual_full_mastery" or raw.get("operation") != "owned_deletion" or raw.get("state") not in {"started", "cleaning"} or raw.get("record_version") != 1 or not isinstance(raw.get("members"), list):
        raise PatcherError("VV3 individual Full Mastery cleanup authority is malformed.")
    parent = record_path.parent
    if _inventory_entry(parent.parent, parent) != raw.get("parent_identity"):
        raise PatcherError("VV3 individual Full Mastery cleanup authority parent changed.")
    binding = raw.get("authority_binding")
    tx = raw.get("transaction_binding")
    if not isinstance(binding, dict) or set(binding) != {"token", "owner", "operation", "parent_identity", "member_digest"} or binding.get("owner") != raw.get("feature_owner") or binding.get("operation") != raw.get("operation") or binding.get("parent_identity") != raw.get("parent_identity") or not isinstance(binding.get("token"), str) or not re.fullmatch(r"[0-9a-f]{32}", binding["token"]):
        raise PatcherError("VV3 individual Full Mastery cleanup authority binding is malformed.")
    if not isinstance(tx, dict) or set(tx) != {"owner", "operation", "parent_identity", "member_names", "member_roles"} or tx.get("owner") != raw.get("feature_owner") or tx.get("operation") != raw.get("operation") or tx.get("parent_identity") != raw.get("parent_identity"):
        raise PatcherError("VV3 individual Full Mastery cleanup transaction binding is malformed.")
    external = raw.get("external_issuance")
    if not isinstance(external, dict) or set(external) != {"name", "record", "payload", "retire_on_cleanup"} or not isinstance(external.get("name"), str) or Path(external["name"]).name != external["name"] or not isinstance(external.get("record"), dict) or not isinstance(external.get("payload"), dict) or not isinstance(external.get("retire_on_cleanup"), bool):
        raise PatcherError("VV3 individual Full Mastery cleanup issuance binding is malformed.")
    issuance_path = parent / external["name"]
    if _inventory_entry(parent, issuance_path) != external["record"]:
        raise PatcherError("VV3 individual Full Mastery cleanup issuance identity changed.")
    issuance_payload = external["payload"]
    if issuance_payload.get("schema_version") != 1 or issuance_payload.get("feature_owner") != raw.get("feature_owner"):
        raise PatcherError("VV3 individual Full Mastery cleanup issuance payload is stale or forged.")
    if issuance_payload.get("kind") == "vv3_cleanup_transaction_issuance":
        if set(issuance_payload) != {"schema_version", "kind", "feature_owner", "operation", "owner_parent_identity", "member_digest", "member_names", "member_roles"} or issuance_payload.get("operation") != raw.get("operation") or issuance_payload.get("owner_parent_identity") != raw.get("parent_identity") or issuance_payload.get("member_digest") != binding.get("member_digest"):
            raise PatcherError("VV3 individual Full Mastery cleanup issuance payload is stale or forged.")
    elif issuance_payload.get("kind") == "vv3_recovery_issuance":
        if set(issuance_payload) != {"schema_version", "kind", "feature_owner", "operation", "token", "owner_parent_absolute", "destination_paths_absolute", "precondition"} or issuance_payload.get("owner_parent_absolute") != str(parent.absolute()).casefold():
            raise PatcherError("VV3 individual Full Mastery recovery issuance payload is stale or forged.")
    else:
        raise PatcherError("VV3 individual Full Mastery cleanup issuance kind is unsupported.")
    if not isinstance(raw.get("namespace_inventory"), list) or any(not isinstance(item, dict) or not isinstance(item.get("path"), str) for item in raw["namespace_inventory"]):
        raise PatcherError("VV3 individual Full Mastery cleanup namespace inventory is malformed.")
    member_blob = json.dumps(raw["members"], sort_keys=True, separators=(",", ":")).encode("utf-8")
    if binding.get("member_digest") != _sha(member_blob) or tx.get("member_names") != [item.get("name") for item in raw["members"]] or tx.get("member_roles") != {str(item.get("name")): item.get("role") for item in raw["members"]}:
        raise PatcherError("VV3 individual Full Mastery cleanup authority members are not externally bound.")
    member_names = {str(item.get("name")) for item in raw["members"]}
    for item in raw["namespace_inventory"]:
        name = str(item.get("path"))
        if "vv3im-" in name and name not in member_names and _inventory_entry(parent, parent / name) != item:
            raise PatcherError("VV3 individual Full Mastery cleanup namespace identity changed.")
    for member in raw["members"]:
        if not isinstance(member, dict) or set(member) != {"name", "role", "record"} or not isinstance(member.get("name"), str) or Path(member["name"]).name != member["name"] or not isinstance(member.get("record"), dict) or not isinstance(member.get("role"), str):
            raise PatcherError("VV3 individual Full Mastery cleanup authority member is invalid.")
        target = parent / member["name"]
        if os.path.lexists(target):
            if _inventory_entry(record_path.parent, record_path) != authority_record:
                raise PatcherError("VV3 individual Full Mastery cleanup authority changed before member deletion.")
            if _inventory_entry(parent, target) != member["record"]:
                raise PatcherError("VV3 individual Full Mastery cleanup authority member changed before deletion.")
            _delete_file_by_handle(target, member["record"])
            if os.path.lexists(target):
                raise PatcherError("VV3 individual Full Mastery cleanup authority member deletion did not verify.")
            if _inventory_entry(record_path.parent, record_path) != authority_record:
                raise PatcherError("VV3 individual Full Mastery cleanup authority changed after member deletion.")
    # The independently issued transaction record is retained until all
    # cleanup members have verified absence; it is then retired by identity.
    if _inventory_entry(record_path.parent, record_path) != authority_record:
        raise PatcherError("VV3 individual Full Mastery cleanup authority changed before issuance cleanup.")
    if _inventory_entry(parent, issuance_path) != external["record"]:
        raise PatcherError("VV3 individual Full Mastery cleanup issuance changed before deletion.")
    if external["retire_on_cleanup"]:
        _delete_file_by_handle(issuance_path, external["record"])
        if os.path.lexists(issuance_path):
            raise PatcherError("VV3 individual Full Mastery cleanup issuance deletion did not verify.")
    if _inventory_entry(record_path.parent, record_path) != authority_record:
        raise PatcherError("VV3 individual Full Mastery cleanup authority changed after issuance cleanup.")
    expected_hidden = {record_path.name}
    expected_hidden.update(
        str(item["path"])
        for item in raw["namespace_inventory"]
        if "vv3im-" in str(item["path"])
        and str(item["path"]) not in member_names
        and (str(item["path"]) != external["name"] or not external["retire_on_cleanup"])
    )
    _validate_vv3_hidden_namespace(parent, expected=expected_hidden)
    # Require a second complete, identity-checked namespace capture immediately
    # before retiring the last authority.  Any insertion, removal, rename, or
    # same-content substitution observed between the two captures keeps the
    # authority and fails closed for deterministic retry.
    _validate_vv3_hidden_namespace(parent, expected=expected_hidden)
    expected_record = _inventory_entry(parent, record_path)
    if expected_record != authority_record:
        raise PatcherError("VV3 individual Full Mastery cleanup authority changed before final deletion.")
    # The authority file itself is the recovery journal; deleting it through
    # _remove_owned would recursively create another cleanup authority.
    _delete_file_by_handle(record_path, expected_record)
    if os.path.lexists(record_path):
        raise PatcherError("VV3 individual Full Mastery cleanup authority deletion did not verify.")


def _quarantine_delete(path: Path, expected: dict[str, object], *, directory: bool) -> None:
    """Quarantine an owned member before final deletion to bound races."""
    _require_windows_identity_atomic()
    baseline_hidden = {entry.name for entry in os.scandir(path.parent) if "vv3im-" in entry.name}
    tombstone = path.with_name(f".{path.name}.vv3im-tombstone-{uuid.uuid4().hex}")
    if os.path.lexists(tombstone):
        raise PatcherError(f"VV3 individual Full Mastery tombstone collision: {tombstone}")
    before = _inventory_entry(path.parent, path)
    if any(before.get(key) != expected.get(key) for key in ("type", "size", "sha256", "st_dev", "st_ino")):
        raise PatcherError(f"VV3 individual Full Mastery deletion target changed: {path}")
    try:
        if directory:
            _move_noreplace(path, tombstone)
        else:
            os.link(path, tombstone)
    except OSError as exc:
        raise PatcherError(f"VV3 individual Full Mastery owned deletion could not quarantine: {path}") from exc
    moved = _inventory_entry(path.parent, tombstone)
    if any(moved.get(key) != before.get(key) for key in ("type", "size", "sha256", "st_dev", "st_ino")):
        raise PatcherError(f"VV3 individual Full Mastery deletion race quarantined foreign material: {tombstone}")
    if directory:
        if _inventory_tree(tombstone):
            raise PatcherError(f"VV3 individual Full Mastery tombstone directory is not empty: {tombstone}")
        tombstone_before_remove = _inventory_entry(tombstone.parent, tombstone)
        if tombstone_before_remove != moved or _inventory_entry(path.parent.parent, path.parent) != _inventory_entry(tombstone.parent.parent, tombstone.parent):
            raise PatcherError(f"VV3 individual Full Mastery tombstone directory identity changed: {tombstone}")
        _delete_directory_by_handle(tombstone, tombstone_before_remove)
        if os.path.lexists(tombstone):
            raise PatcherError(f"VV3 individual Full Mastery tombstone directory cleanup did not verify: {tombstone}")
    else:
        check = _inventory_entry(path.parent, tombstone)
        source_boundary = _inventory_entry(path.parent, path)
        tombstone_boundary = _inventory_entry(path.parent, tombstone)
        if any(check.get(key) != before.get(key) for key in ("type", "size", "sha256", "st_dev", "st_ino")) or any(source_boundary.get(key) != before.get(key) for key in ("type", "size", "sha256", "st_dev", "st_ino")) or any(tombstone_boundary.get(key) != before.get(key) for key in ("type", "size", "sha256", "st_dev", "st_ino")):
            raise PatcherError(f"VV3 individual Full Mastery tombstone identity changed: {tombstone}")
        preserved = path.with_name(f".{path.name}.vv3im-preserved-{uuid.uuid4().hex}.backup")
        _copy_preserved(path, preserved, _read_regular(path))
        preserved_record = _inventory_entry(path.parent, preserved)
        if preserved_record.get("sha256") != before.get("sha256") or preserved_record.get("size") != before.get("size"):
            raise PatcherError(f"VV3 individual Full Mastery preserved deletion backup mismatch: {preserved}")
        # Keep a second verified owned link until both the tombstone and the
        # primary preserved path have been retired.  If the primary backup is
        # replaced in that interval, this guard retains the original bytes for
        # deterministic recovery and the foreign replacement is never deleted.
        guard = path.with_name(f".{path.name}.vv3im-preserved-guard-{uuid.uuid4().hex}.backup")
        if os.path.lexists(guard):
            raise PatcherError(f"VV3 individual Full Mastery preserved backup guard collision: {guard}")
        os.link(preserved, guard)
        guard_record = _inventory_entry(path.parent, guard)
        if guard_record.get("sha256") != before.get("sha256") or guard_record.get("size") != before.get("size"):
            raise PatcherError(f"VV3 individual Full Mastery preserved backup guard mismatch: {guard}")
        # A second independent owned link remains until the final guard is
        # retired.  This closes the interval after the first guard deletion:
        # one verified copy always survives a preserved/guard substitution.
        guard2 = path.with_name(f".{path.name}.vv3im-preserved-guard-{uuid.uuid4().hex}.backup")
        if os.path.lexists(guard2):
            raise PatcherError(f"VV3 individual Full Mastery preserved backup guard collision: {guard2}")
        os.link(preserved, guard2)
        guard2_record = _inventory_entry(path.parent, guard2)
        if guard2_record.get("sha256") != before.get("sha256") or guard2_record.get("size") != before.get("size"):
            raise PatcherError(f"VV3 individual Full Mastery preserved backup second guard mismatch: {guard2}")
        cleanup_authority, cleanup_authority_record = _write_cleanup_authority(
            path.parent,
            [
                {"name": path.name, "role": "source", "record": before},
                {"name": tombstone.name, "role": "tombstone", "record": moved},
                {"name": preserved.name, "role": "preserved", "record": preserved_record},
                {"name": guard.name, "role": "guard", "record": guard_record},
                {"name": guard2.name, "role": "guard-final", "record": guard2_record},
            ],
        )
        if _inventory_entry(path.parent, path) != before or _inventory_entry(path.parent, tombstone) != moved:
            raise PatcherError(f"VV3 individual Full Mastery tombstone/source changed before deletion: {path}")
        # The hard-link publication above is exclusive/no-replace.  Remove
        # the original only through the identity-bound handle operation.
        _delete_file_by_handle(path, before)
        tombstone_before = _inventory_entry(tombstone.parent, tombstone)
        if any(tombstone_before.get(key) != before.get(key) for key in ("type", "size", "sha256", "st_dev", "st_ino")):
            raise PatcherError(f"VV3 individual Full Mastery tombstone identity changed: {tombstone}")
        _delete_file_by_handle(tombstone, tombstone_before)
        preserved_before_guard_cleanup = _inventory_entry(preserved.parent, preserved)
        if any(preserved_before_guard_cleanup.get(key) != preserved_record.get(key) for key in ("type", "size", "sha256", "st_dev", "st_ino")):
            # Keep the still-verified guard as the recoverable owned copy.
            raise PatcherError(f"VV3 individual Full Mastery preserved backup changed before guard cleanup: {preserved}")
        issuance_names = {entry.name for entry in os.scandir(path.parent) if entry.name.startswith(".vv3im-issuance-")}
        _validate_vv3_hidden_namespace(path.parent, expected=(baseline_hidden - {path.name}) | {preserved.name, guard.name, guard2.name, cleanup_authority.name} | issuance_names)
        if os.path.lexists(guard):
            _delete_file_by_handle(guard, guard_record)
        # Guard-final is retained while the primary preserved copy is
        # retired; a race on the primary cannot destroy the last owned bytes.
        preserved_now = _inventory_entry(preserved.parent, preserved)
        if preserved_now != preserved_record:
            raise PatcherError(f"VV3 individual Full Mastery preserved backup changed after guard cleanup: {preserved}")
        if os.path.lexists(preserved):
            _delete_file_by_handle(preserved, preserved_record)
        guard2_now = _inventory_entry(guard2.parent, guard2)
        if guard2_now != guard2_record:
            raise PatcherError(f"VV3 individual Full Mastery final preserved guard changed: {guard2}")
        if os.path.lexists(guard2):
            _delete_file_by_handle(guard2, guard2_record)
        # Retire the independently issued cleanup evidence only after every
        # owned copy and guard has been verified gone.
        for entry in list(os.scandir(path.parent)):
            if entry.name.startswith(".vv3im-issuance-"):
                issuance_path = Path(entry.path)
                try:
                    issuance_kind = json.loads(_read_regular(issuance_path).decode("utf-8")).get("kind")
                except Exception as exc:
                    raise PatcherError(f"VV3 individual Full Mastery cleanup issuance is unreadable: {issuance_path}") from exc
                if issuance_kind == "vv3_recovery_issuance":
                    continue
                issuance_record = _inventory_entry(path.parent, issuance_path)
                if issuance_record is None:
                    raise PatcherError(f"VV3 individual Full Mastery cleanup issuance disappeared: {issuance_path}")
                _delete_file_by_handle(issuance_path, issuance_record)
                if os.path.lexists(issuance_path):
                    raise PatcherError(f"VV3 individual Full Mastery cleanup issuance deletion did not verify: {issuance_path}")
        if os.path.lexists(cleanup_authority):
            _delete_file_by_handle(cleanup_authority, cleanup_authority_record)
        _validate_vv3_hidden_namespace(path.parent, expected=baseline_hidden - {path.name})
    if os.path.lexists(tombstone):
        raise PatcherError(f"VV3 individual Full Mastery tombstone cleanup did not verify: {tombstone}")


def _copy_preserved(source: Path, target: Path, expected: bytes) -> None:
    _write_file(target, expected)
    if _read_regular(target) != expected:
        raise PatcherError(f"VV3 individual Full Mastery copy verification failed: {target}")


def _replace_verified(stage: Path, destination: Path, expected_destination: tuple[bool, bytes | None], expected_stage: bytes) -> None:
    """Perform a replace only after immediate no-follow identity/hash checks."""
    _require_windows_identity_atomic()
    if _state(destination) != expected_destination:
        raise PatcherError(f"VV3 individual Full Mastery destination race: {destination}")
    stage_before = os.lstat(stage)
    _reject_entry(stage, stage_before, directory=False)
    if _read_regular(stage) != expected_stage:
        raise PatcherError(f"VV3 individual Full Mastery stage race: {stage}")
    stage_check = os.lstat(stage)
    _reject_entry(stage, stage_check, directory=False)
    if (stage_before.st_dev, stage_before.st_ino, stage_before.st_size) != (stage_check.st_dev, stage_check.st_ino, stage_check.st_size):
        raise PatcherError(f"VV3 individual Full Mastery stage identity changed: {stage}")
    destination_before = os.lstat(destination) if os.path.lexists(destination) else None
    if destination_before is not None:
        _reject_entry(destination, destination_before, directory=False)
    os.replace(stage, destination)
    after = os.lstat(destination)
    _reject_entry(destination, after, directory=False)
    if _read_regular(destination) != expected_stage:
        raise PatcherError(f"VV3 individual Full Mastery replacement postverify failed: {destination}")


def _restore_member(path: Path, existed: bool, original: bytes | None, published: bytes, *, backup: Path | None = None, staging_root: Path | None = None) -> bool:
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
            stage_parent = staging_root if staging_root is not None else path.parent
            stage = stage_parent / f".{path.name}.vv3im-restore-{uuid.uuid4().hex}.stage"
            _copy_preserved(source, stage, original or b"") if source is not None else _write_file(stage, original or b"")
            _replace_verified(stage, path, current, original or b"")
            return _state(path) == (True, original)
        if current[0] and current[1] == published:
            _remove_owned(path, expected=_inventory_entry(path.parent, path))
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


def _transaction(operation: str, destinations: list[Path], pre: dict[Path, tuple[bool, bytes | None]], published: dict[Path, bytes], *, expected_preimage: dict[Path, bytes], parent: Path, recovery_prefix: str = ".vv3im", recovery_metadata: dict[str, object] | None = None) -> None:
    _require_windows_identity_atomic()
    token = uuid.uuid4().hex
    recovery_root = parent / f"{recovery_prefix}-recovery-{token}"
    recovery_metadata = dict(recovery_metadata or {})
    recovery_metadata.setdefault("feature_owner", "vv3_individual_full_mastery")
    # Internal audit callers may invoke the transaction primitive directly.
    # Give those reports a complete, explicitly bound VV3 envelope rather
    # than reopening the old owner-only schema; production callers override
    # these values with the certified mode/hash identities.
    recovery_metadata.setdefault("mode", "internal")
    recovery_metadata.setdefault("parent_sha256", _sha(pre[destinations[0]][1] or b""))
    recovery_metadata.setdefault("candidate_sha256", _sha(published[destinations[0]]))
    recovery_metadata.setdefault("destination_exe_basename", destinations[0].name)
    recovery_metadata.setdefault("companion_dll_basename", destinations[1].name)
    recovery_metadata.setdefault("member_roles", {destinations[0].name: "game_executable", destinations[1].name: "companion_dll"})
    recovery_metadata.setdefault("destination_paths_absolute", [str(path.absolute()).casefold() for path in destinations])
    parent_record = _inventory_entry(parent.parent, parent)
    recovery_metadata.setdefault("report_parent_identity", {"st_dev": int(parent_record["st_dev"]), "st_ino": int(parent_record["st_ino"])})
    _safe_ancestor_chain(parent)
    if os.path.lexists(recovery_root):
        raise PatcherError("VV3 individual Full Mastery recovery-root collision.")
    recovery_root_identity: dict[str, object] | None = None
    try:
        recovery_root.mkdir()
        recovery_root_identity = _inventory_entry(parent, recovery_root)
        _fsync_dir(parent)
    except Exception:
        if os.path.lexists(recovery_root):
            try:
                if recovery_root_identity is not None:
                    _remove_owned(recovery_root, expected=recovery_root_identity, expected_tree=[])
            except Exception:
                pass
        raise
    stages = {p: recovery_root / f".{p.name}.{recovery_prefix.lstrip('.')}-{token}.stage" for p in destinations}
    backups = {p: recovery_root / f".{p.name}.{recovery_prefix.lstrip('.')}-{token}.backup" for p in destinations if pre[p][0]}
    # Issue an independently captured transaction record before any pair
    # mutation.  Recovery journals must bind to this pre-existing evidence;
    # a token/digest computed only inside a cleanup report is not authority.
    issuance_token = uuid.uuid4().hex
    issuance_path = recovery_root / f".{recovery_prefix.lstrip('.')}-issuance-{issuance_token}.json"
    issuance_operation = "removal" if operation == "remove" else ("install_existing" if any(pre[p][0] for p in destinations) else "install_new")
    issuance_payload = {
        "schema_version": 1,
        "kind": "vv3_recovery_issuance",
        "feature_owner": recovery_metadata.get("feature_owner", "vv3_individual_full_mastery"),
        "operation": issuance_operation,
        "token": issuance_token,
        "transaction_id": issuance_token,
        "owner_parent_absolute": str(parent.absolute()).casefold(),
        "parent_identity": _inventory_entry(parent.parent, parent),
        "recovery_root_name": recovery_root.name,
        "recovery_root_identity": recovery_root_identity,
        "destination_paths_absolute": [str(p.absolute()).casefold() for p in destinations],
        "member_roles": {str(p.absolute()).casefold(): ("game_executable" if index == 0 else "companion_dll") for index, p in enumerate(destinations)},
        "members": [
            {"path": str(p.absolute()).casefold(), "exists": bool(pre[p][0]), "size": len(pre[p][1]) if pre[p][1] is not None else 0, "sha256": _sha(pre[p][1]) if pre[p][1] is not None else None}
            for p in destinations
        ],
        "precondition": {str(p.absolute()).casefold(): {"exists": bool(pre[p][0]), "sha256": _sha(pre[p][1]) if pre[p][1] is not None else None, "size": len(pre[p][1]) if pre[p][1] is not None else 0} for p in destinations},
    }
    issuance_payload["member_digest"] = _sha(json.dumps(issuance_payload["members"], sort_keys=True, separators=(",", ":")).encode("utf-8"))
    _write_file(issuance_path, (json.dumps(issuance_payload, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    issuance_record = _inventory_member(parent, issuance_path)
    if issuance_record is None:
        raise PatcherError("VV3 individual Full Mastery transaction issuance record was not captured.")
    # VV5 supplies an independently issued parent-registry binding.  Preserve
    # that external authority in the report while still retaining the local
    # transaction issuance record in the owned recovery root.  VV3 callers
    # without an external binding continue to use the local record.
    recovery_metadata.setdefault("issuance_token", issuance_token)
    recovery_metadata.setdefault("issuance_name", _relative_owned(parent, issuance_path))
    recovery_metadata.setdefault("issuance_identity", {"record": issuance_record, "kind": "vv3_recovery_issuance", "transaction_id": issuance_token, "owner_parent_absolute": str(parent.absolute()).casefold(), "parent_identity": issuance_payload["parent_identity"], "recovery_root_name": recovery_root.name, "recovery_root_identity": recovery_root_identity, "operation": operation, "destination_paths_absolute": issuance_payload["destination_paths_absolute"], "member_roles": issuance_payload["member_roles"], "member_digest": issuance_payload["member_digest"]})
    recovery_metadata.setdefault("destination_paths_absolute", issuance_payload["destination_paths_absolute"])
    recovery_metadata.setdefault("destination_parent_absolute", str(parent.absolute()).casefold())
    recovery_metadata.setdefault("member_roles", {p.name: ("game_executable" if index == 0 else "companion_dll") for index, p in enumerate(destinations)})
    if any(os.path.lexists(p) for p in (*stages.values(), *backups.values())):
        raise PatcherError("VV3 individual Full Mastery staging collision.")
    committed = False
    committed_cleanup_inventory: list[dict[str, object]] | None = None
    transaction_inventory_baseline: list[dict[str, object]] | None = None
    try:
        for p in destinations:
            _write_file(stages[p], published[p])
            if _read_regular(stages[p]) != published[p]:
                raise PatcherError("VV3 individual Full Mastery staged verification failed.")
        for p, b in backups.items():
            _copy_preserved(p, b, pre[p][1] or b"")
        transaction_inventory_baseline = _inventory_tree(recovery_root)
        for p in destinations:
            if _state(p) != pre[p] or _read_regular(stages[p]) != published[p]:
                raise PatcherError("VV3 individual Full Mastery pre-replace race.")
        for p in destinations:
            if _state(p) != pre[p]:
                raise PatcherError("VV3 individual Full Mastery destination race before publication.")
            _replace_verified(stages[p], p, pre[p], published[p])
        if any(_state(p) != (True, published[p]) for p in destinations):
            raise PatcherError("VV3 individual Full Mastery publication postverify failed.")
        committed_cleanup_inventory = _inventory_tree(recovery_root)
        # Backups/stages become cleanup-eligible only after complete pair
        # postverification, never merely after the second replace call.
        committed = True
    except Exception as exc:
        restored = {}
        for p in destinations:
            restored[p] = _restore_member(p, *pre[p], published[p], backup=backups.get(p), staging_root=recovery_root)
        cleanup_failed: BaseException | None = None
        if all(restored.values()) and all(_state(p) == pre[p] for p in destinations):
            try:
                if os.path.lexists(recovery_root):
                    rollback_inventory = _inventory_tree(recovery_root)
                    _remove_owned(recovery_root, expected=recovery_root_identity, expected_tree=rollback_inventory)
                _fsync_dir(parent)
            except BaseException as cleanup_exc:
                # Do not delete or adopt an injected descendant.  Fall
                # through to durable report creation below.
                cleanup_failed = cleanup_exc
            if cleanup_failed is None:
                raise PatcherError(f"VV3 individual Full Mastery {operation} publication failed; pair restored") from exc
        if cleanup_failed is not None:
            exc = cleanup_failed
        if cleanup_failed is not None or not (all(restored.values()) and all(_state(p) == pre[p] for p in destinations)):
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
                    "published_inventory": _inventory_member(parent, p) if _state(p) == (True, published[p]) else None,
                })
            inventory = _inventory_tree(recovery_root)
            for item in inventory:
                item["path"] = _relative_owned(parent, recovery_root / str(item["path"]))
            root_st = os.lstat(recovery_root)
            inventory.insert(0, {"path": _relative_owned(parent, recovery_root), "type": "directory", "size": 0, "sha256": None, "st_dev": int(root_st.st_dev), "st_ino": int(root_st.st_ino)})
            report = _write_recovery(parent, {
                "operation": report_operation,
                "recovery_root": ".",
                "destination_parent": ".",
                "initial_precondition": {
                    "kind": "absent" if report_operation == "install_new" else "pair",
                    "members": [{"path": _relative_owned(parent, p), "exists": bool(pre[p][0]), "sha256": _sha(pre[p][1]) if pre[p][1] is not None else None, "size": len(pre[p][1]) if pre[p][1] is not None else 0} for p in destinations],
                },
                "replay_guard": {
                    "kind": "absent" if report_operation == "install_new" else "pair",
                    "members": [_relative_owned(parent, p) for p in destinations],
                },
                "members": member_records,
                "ownership_inventory": inventory,
                "failure_diagnostic": str(exc),
                **recovery_metadata,
                "_report_prefix": recovery_prefix,
                "_recovery_root_name": recovery_root.name,
                "_recovery_root_identity": {"st_dev": int(os.lstat(recovery_root).st_dev), "st_ino": int(os.lstat(recovery_root).st_ino)},
                "_expected_ownership_inventory": [
                    {**item, "path": _relative_owned(parent, recovery_root / str(item["path"]))}
                    for item in (transaction_inventory_baseline or [])
                ] + ([{"path": _relative_owned(parent, recovery_root), "type": "directory", "size": 0, "sha256": None, "st_dev": int(recovery_root_identity["st_dev"]), "st_ino": int(recovery_root_identity["st_ino"])}] if recovery_root_identity is not None else []),
            })
            raise PatcherError(f"VV3 individual Full Mastery transaction failed; recovery retained at {report}") from exc
    finally:
        if committed:
            try:
                if os.path.lexists(recovery_root):
                    _remove_owned(recovery_root, expected=recovery_root_identity, expected_tree=committed_cleanup_inventory or [])
                _fsync_dir(parent)
            except Exception as cleanup_exc:
                # Cleanup is part of the publication contract.  Retain a
                # complete report whenever ownership cleanup or directory
                # durability fails instead of silently leaving residue.
                try:
                    if os.path.lexists(recovery_root):
                        inventory = _inventory_tree(recovery_root)
                        for item in inventory:
                            item["path"] = _relative_owned(parent, recovery_root / str(item["path"]))
                        root_st = os.lstat(recovery_root)
                        inventory.insert(0, {"path": _relative_owned(parent, recovery_root), "type": "directory", "size": 0, "sha256": None, "st_dev": int(root_st.st_dev), "st_ino": int(root_st.st_ino)})
                        _write_recovery(parent, {
                            "operation": "removal" if operation == "remove" else ("install_existing" if any(pre[p][0] for p in destinations) else "install_new"),
                            "recovery_root": ".",
                            "destination_parent": ".",
                            "initial_precondition": {"kind": "pair" if any(pre[p][0] for p in destinations) or operation == "remove" else "absent", "members": [{"path": _relative_owned(parent, p), "exists": bool(pre[p][0]), "sha256": _sha(pre[p][1]) if pre[p][1] is not None else None, "size": len(pre[p][1]) if pre[p][1] is not None else 0} for p in destinations]},
                            "replay_guard": {"kind": "pair" if any(pre[p][0] for p in destinations) or operation == "remove" else "absent", "members": [_relative_owned(parent, p) for p in destinations]},
                            "members": [{"destination_relative": _relative_owned(parent, p), "destination_type": "regular_file", "pre_exists": bool(pre[p][0]), "pre_sha256": _sha(pre[p][1]) if pre[p][1] is not None else None, "pre_size": len(pre[p][1]) if pre[p][1] is not None else 0, "published_sha256": _sha(published[p]), "published_size": len(published[p]), "backup_relative": _relative_owned(parent, backups.get(p)), "stage_relative": _relative_owned(parent, stages[p]), "backup_inventory": _inventory_member(parent, backups.get(p)), "stage_inventory": _inventory_member(parent, stages[p]), "published_inventory": _inventory_member(parent, p) if _state(p) == (True, published[p]) else None} for p in destinations],
                            "ownership_inventory": inventory,
                            "failure_diagnostic": f"cleanup failure: {cleanup_exc}",
                            **recovery_metadata,
                            "_report_prefix": recovery_prefix,
                            "_recovery_root_name": recovery_root.name,
                            "_recovery_root_identity": {"st_dev": int(os.lstat(recovery_root).st_dev), "st_ino": int(os.lstat(recovery_root).st_ino)},
                            "_expected_ownership_inventory": [
                                {**item, "path": _relative_owned(parent, recovery_root / str(item["path"]))}
                                for item in (committed_cleanup_inventory or [])
                            ] + ([{"path": _relative_owned(parent, recovery_root), "type": "directory", "size": 0, "sha256": None, "st_dev": int(recovery_root_identity["st_dev"]), "st_ino": int(recovery_root_identity["st_ino"])}] if recovery_root_identity is not None else []),
                        })
                finally:
                    raise PatcherError("VV3 individual Full Mastery cleanup failed; recovery evidence retained.") from cleanup_exc


def _recover_from_emergency_marker(marker: Path, *, recovery_prefix: str, required_metadata: dict[str, object] | None, expected_report_sha256: str | None) -> None:
    canonical, successors, markers = _report_chain_siblings(marker.parent, marker, recovery_prefix=recovery_prefix)
    if canonical or successors or len(markers) != 1 or markers[0] != marker:
        raise PatcherError("VV3 individual Full Mastery emergency marker conflicts with an existing recovery chain.")
    orphan_manifests = _orphan_chain_manifests(marker.parent, {marker.name}, recovery_prefix=recovery_prefix)
    marker_manifest, marker_manifest_record, _marker_manifest_payload = _read_chain_manifest(marker)
    marker_record = _inventory_entry(marker.parent, marker)
    marker_payload = json.loads(_read_regular(marker).decode("utf-8"))
    if not isinstance(marker_payload, dict) or set(marker_payload) != {"schema_version", "kind", "feature_owner", "operation", "recovery_root_name", "recovery_root_identity", "ownership_inventory", "expected_ownership_inventory", "recovery_payload", "failure", "canonical_report_target"} or marker_payload.get("schema_version") != 1 or marker_payload.get("kind") != "emergency_recovery_marker":
        raise PatcherError("VV3 individual Full Mastery emergency marker schema is unsupported.")
    details = dict(marker_payload.get("recovery_payload") or {})
    marker_owner = marker_payload.get("feature_owner")
    if marker_owner != details.get("feature_owner") or not isinstance(marker_owner, str):
        raise PatcherError("VV3 individual Full Mastery emergency marker caller binding is inconsistent.")
    _validate_emergency_binding_payload(details, owner=marker_owner)
    if (
        marker_payload.get("recovery_root_name") != details.get("recovery_root_name")
        or marker_payload.get("recovery_root_identity") != details.get("recovery_root_identity")
    ):
        raise PatcherError("VV3 individual Full Mastery emergency marker root binding is inconsistent.")
    orphan_records: list[tuple[Path, dict[str, object]]] = []
    for orphan in orphan_manifests:
        orphan_raw = json.loads(_read_regular(orphan).decode("utf-8"))
        orphan_root = orphan_raw.get("recovery_root_record") if isinstance(orphan_raw, dict) else None
        root_matches = isinstance(orphan_root, dict) and orphan_root.get("st_dev") == (marker_payload.get("recovery_root_identity") or {}).get("st_dev") and orphan_root.get("st_ino") == (marker_payload.get("recovery_root_identity") or {}).get("st_ino")
        orphan_destinations = (orphan_raw.get("destination_paths_absolute") or []) if isinstance(orphan_raw, dict) else []
        if not orphan_destinations and isinstance(orphan_raw, dict):
            orphan_destinations = [str(member.get("destination_relative")) for member in (orphan_raw.get("members") or []) if isinstance(member, dict) and isinstance(member.get("destination_relative"), str)]
        marker_destinations = details.get("destination_paths_absolute") or [str(member.get("destination_relative")) for member in (details.get("members") or []) if isinstance(member, dict) and isinstance(member.get("destination_relative"), str)]
        if not isinstance(orphan_raw, dict) or orphan_raw.get("schema_version") != 3 or orphan_raw.get("kind") != "vv3_recovery_chain_manifest" or orphan_raw.get("recovery_root_name") != marker_payload.get("recovery_root_name") or not root_matches or orphan_raw.get("ownership_inventory") != details.get("ownership_inventory") or orphan_raw.get("members") != details.get("members") or orphan_destinations != marker_destinations:
            raise PatcherError("VV3 individual Full Mastery emergency marker is incompatible with an orphan chain manifest.")
        orphan_records.append((orphan, _inventory_entry(marker.parent, orphan)))
    details.update({
        "_report_prefix": recovery_prefix,
        "_recovery_root_name": marker_payload.get("recovery_root_name"),
        "_recovery_root_identity": marker_payload.get("recovery_root_identity"),
        "_expected_ownership_inventory": marker_payload.get("expected_ownership_inventory") or marker_payload.get("ownership_inventory"),
    })
    _validate_emergency_root(marker.parent, details)
    report = _write_recovery(marker.parent, details)
    # The reconstructed canonical report receives a fresh UUID name.  Bind
    # the strict metadata check to that actual name rather than the marker's
    # diagnostic filename, while preserving every other authority field.
    inner_metadata = dict(required_metadata or {})
    if isinstance(details.get("member_roles"), dict):
        inner_metadata["member_roles"] = details["member_roles"]
    if isinstance(details.get("destination_paths_absolute"), list):
        inner_metadata["destination_paths_absolute"] = details["destination_paths_absolute"]
    if required_metadata is not None:
        inner_metadata["report_name"] = report.name
    recover_atomic(report, recovery_prefix=recovery_prefix, required_metadata=inner_metadata, expected_report_sha256=None, _from_emergency=True)
    _remove_owned(marker, expected=marker_record)
    _remove_owned(marker_manifest, expected=marker_manifest_record)
    for orphan, orphan_record in orphan_records:
        _remove_owned(orphan, expected=orphan_record)
    _validate_vv3_hidden_namespace(marker.parent, expected=set())
    _validate_vv3_hidden_namespace(marker.parent, expected=set())


def _compatible_emergency_markers(markers: list[Path], payload: dict[str, object]) -> list[tuple[Path, dict[str, object]]]:
    """Return only markers that describe the same still-owned transaction."""
    compatible: list[tuple[Path, dict[str, object]]] = []
    for marker in markers:
        try:
            marker_payload = json.loads(_read_regular(marker).decode("utf-8"))
            if not isinstance(marker_payload, dict) or marker_payload.get("kind") != "emergency_recovery_marker":
                continue
            details = marker_payload.get("recovery_payload")
            if not isinstance(details, dict):
                continue
            for key in ("feature_owner", "operation", "mode", "parent_sha256", "candidate_sha256", "recovery_root_name"):
                if key in payload and details.get(key) != payload.get(key):
                    raise ValueError("marker transaction identity differs")
            for key in ("destination_paths_absolute", "member_roles"):
                if payload.get(key) is not None and details.get(key) is not None and details.get(key) != payload.get(key):
                    raise ValueError("marker destination/role binding differs")
            if payload.get("members") is not None and details.get("members") is not None and details.get("members") != payload.get("members"):
                marker_destinations = {str(item.get("destination_relative")) for item in (details.get("members") or []) if isinstance(item, dict) and isinstance(item.get("destination_relative"), str)}
                payload_destinations = {str(item.get("destination_relative")) for item in (payload.get("members") or []) if isinstance(item, dict) and isinstance(item.get("destination_relative"), str)}
                if marker_destinations != payload_destinations:
                    raise ValueError("marker member destinations differ")
            compatible.append((marker, marker_payload))
        except Exception:
            continue
    return compatible


def recover_atomic(report_or_root: Path, *, recovery_prefix: str = ".vv3im", required_metadata: dict[str, object] | None = None, expected_report_sha256: str | None = None, _from_emergency: bool = False) -> None:
    _require_windows_identity_atomic()
    """Replay schema-v2 evidence with relative no-follow ownership checks."""
    report = Path(report_or_root)
    # Validate the supplied path before calling is_dir/scandir.  A symlink,
    # junction, mount or reparse root is never opened or traversed.
    supplied = Path(os.path.abspath(os.fspath(report)))
    if not os.path.lexists(supplied):
        raise PatcherError("VV3 individual Full Mastery recovery root/report is missing.")
    supplied_st = os.lstat(supplied)
    _reject_entry(supplied, supplied_st)
    if stat.S_ISDIR(supplied_st.st_mode):
        _validate_recovery_root(supplied)
        reports, successors, markers = _report_chain_siblings(supplied, supplied, recovery_prefix=recovery_prefix)
        if successors and not reports:
            raise PatcherError("VV3 individual Full Mastery versioned recovery successor is orphaned.")
        if (markers and (reports or successors)) or len(markers) > 1:
            raise PatcherError("VV3 individual Full Mastery recovery authority chain is ambiguous.")
        if markers:
            report = markers[0]
        elif len(reports) == 1:
            report = reports[0]
        else:
            raise PatcherError("VV3 individual Full Mastery recovery report is ambiguous.")
    else:
        _reject_entry(supplied, supplied_st, directory=False)
        report = supplied
    pointer_info = None
    pointer_canonical: Path | None = None
    pointer_canonical_record: dict[str, object] | None = None
    pointer_record: dict[str, object] | None = None
    marker_bytes = _read_regular(report)
    try:
        marker_candidate = json.loads(marker_bytes.decode("utf-8"))
    except Exception:
        marker_candidate = None
    if isinstance(marker_candidate, dict) and marker_candidate.get("kind") == "emergency_recovery_marker":
        if not report.name.startswith(f"{recovery_prefix}-emergency-"):
            raise PatcherError("VV3 individual Full Mastery emergency marker owner is invalid.")
        return _recover_from_emergency_marker(report, recovery_prefix=recovery_prefix, required_metadata=required_metadata, expected_report_sha256=expected_report_sha256)
    sibling_reports, sibling_successors, sibling_markers = _report_chain_siblings(report.parent, report, recovery_prefix=recovery_prefix)
    compatible_marker_records: list[tuple[Path, dict[str, object]]] = []
    pointer_info = _load_report_pointer(report, report.parent)
    if pointer_info is None and sibling_successors:
        raise PatcherError("VV3 individual Full Mastery versioned recovery successor is orphaned.")
    if pointer_info is not None and set(p.name for p in sibling_successors) != {pointer_info[0].name}:
        raise PatcherError("VV3 individual Full Mastery recovery successor chain is incomplete or ambiguous.")
    if pointer_info is not None:
        if expected_report_sha256 is not None:
            raise PatcherError("VV3 individual Full Mastery versioned report requires a fresh report hash.")
        canonical_report = report
        report, pointer_canonical_record, pointer_record, _pointer_path = pointer_info
        pointer_canonical = canonical_report
    chain_manifest, chain_manifest_record, _chain_manifest_payload = _read_chain_manifest(report)
    # Keep the current transaction authority as a finalization successor.  It
    # must cover the interval after report/predecessor deletion through the
    # complete post-deletion namespace proof; it is the last authority allowed
    # to be retired.
    final_authority_path = _discover_transaction_authority(chain_manifest)
    final_authority_record = _inventory_entry(report.parent, final_authority_path)
    if final_authority_record is None:
        raise PatcherError("VV3 individual Full Mastery finalization authority is missing.")
    _safe_ancestor_chain(report.parent)
    report_st_before = os.lstat(report)
    _reject_entry(report, report_st_before, directory=False)
    report_bytes = _read_regular(report)
    report_snapshot = _inventory_entry(report.parent, report)
    if expected_report_sha256 is not None and _sha(report_bytes) != expected_report_sha256:
        raise PatcherError("VV3 individual Full Mastery recovery report changed before replay.")
    payload = json.loads(report_bytes.decode("utf-8"))
    recovery_metadata_keys = {
        "feature_owner", "mode", "parent_sha256", "candidate_sha256",
        "destination_exe_basename", "companion_dll_basename", "member_roles",
        "recovery_root_name", "recovery_root_identity", "report_name",
        "report_parent_identity", "issuance_token", "issuance_name",
        "issuance_registry_relative", "issuance_registry_identity",
        "issuance_identity", "destination_parent_absolute",
        "destination_paths_absolute", "vv5_schema",
    }
    _validate_recovery_payload(payload, report.parent, allowed_metadata=recovery_metadata_keys.intersection(payload))
    if sibling_markers and not _from_emergency:
        compatible_marker_records = [(marker, _inventory_entry(report.parent, marker)) for marker, _marker_payload in _compatible_emergency_markers(sibling_markers, payload)]
        if len(compatible_marker_records) != len(sibling_markers):
            raise PatcherError("VV3 individual Full Mastery recovery marker conflicts with canonical report.")
    if required_metadata is not None:
        if any(payload.get(key) != value for key, value in required_metadata.items()):
            raise PatcherError("VV3 individual Full Mastery recovery metadata identity mismatch.")
    if payload["report_relative"] != report.name:
        raise PatcherError("VV3 individual Full Mastery recovery report identity/path mismatch.")
    root = report.parent
    owned_dirs = [item for item in payload["ownership_inventory"] if item.get("type") == "directory" and "/" not in str(item.get("path", ""))]
    if len(owned_dirs) != 1:
        raise PatcherError("VV3 individual Full Mastery recovery root inventory is ambiguous.")
    replay_root = root / str(owned_dirs[0]["path"])
    _validate_recovery_root(replay_root)
    # Compare only the owned hidden recovery root before touching either
    # destination.  The report lives beside the destination pair, which may
    # be a complete game directory containing arbitrary stock/runtime files;
    # those siblings are not recovery-owned and must never be inventoried.
    expected_owned = payload["ownership_inventory"]
    actual_owned = _inventory_tree(replay_root)
    for item in actual_owned:
        item["path"] = _relative_owned(root, replay_root / str(item["path"]))
    replay_root_st = os.lstat(replay_root)
    actual_owned.insert(0, {
        "path": _relative_owned(root, replay_root),
        "type": "directory",
        "size": 0,
        "sha256": None,
        "st_dev": int(replay_root_st.st_dev),
        "st_ino": int(replay_root_st.st_ino),
    })
    if sorted(actual_owned, key=lambda item: str(item["path"]).casefold()) != sorted(expected_owned, key=lambda item: str(item["path"]).casefold()):
        raise PatcherError("VV3 individual Full Mastery recovery ownership inventory changed.")
    for item in payload["ownership_inventory"]:
        owned = root / str(item["path"])
        if not os.path.lexists(owned):
            raise PatcherError("VV3 individual Full Mastery recovery ownership inventory changed.")
        st = os.lstat(owned)
        if item["type"] == "directory":
            _reject_entry(owned, st, directory=True)
            if (st.st_dev, st.st_ino) != (int(item["st_dev"]), int(item["st_ino"])):
                raise PatcherError("VV3 individual Full Mastery recovery ownership directory identity changed.")
        else:
            _reject_entry(owned, st, directory=False)
            if _sha(_read_regular(owned)) != item["sha256"] or st.st_size != item["size"] or (st.st_dev, st.st_ino) != (int(item["st_dev"]), int(item["st_ino"])):
                raise PatcherError("VV3 individual Full Mastery recovery ownership file changed.")
    members = payload["members"]
    resolved: list[tuple[dict[str, object], Path, Path | None]] = []
    destination_snapshots: dict[Path, dict[str, object] | None] = {}
    for member in members:
        destination = root / str(member["destination_relative"])
        backup = root / str(member["backup_relative"]) if member["backup_relative"] else None
        stage = root / str(member["stage_relative"]) if member["stage_relative"] else None
        _safe_ancestor_chain(destination.parent)
        if member["pre_exists"] and backup is None:
            raise PatcherError("VV3 individual Full Mastery recovery required backup is missing.")
        if backup is not None:
            _safe_ancestor_chain(backup.parent)
            if not os.path.lexists(backup) or member.get("backup_inventory") is None or _inventory_entry(root, backup) != member.get("backup_inventory") or _sha(_read_regular(backup)) != member["pre_sha256"] or len(_read_regular(backup)) != member["pre_size"]:
                raise PatcherError("VV3 individual Full Mastery recovery backup mismatch.")
        if stage is not None and os.path.lexists(stage) and member.get("stage_inventory") is not None and _inventory_entry(root, stage) != member.get("stage_inventory"):
            raise PatcherError("VV3 individual Full Mastery recovery stage mismatch.")
        current = _state(destination)
        destination_snapshots[destination] = _inventory_entry(root, destination) if current[0] else None
        pre_exists = bool(member["pre_exists"])
        # install_new has an immutable absent precondition.  A foreign tree
        # with byte-identical published content is still a race and is never
        # adopted by replay.
        if payload["operation"] == "install_new" and current[0]:
            published_identity = member.get("published_inventory")
            if published_identity is None or current[1] is None or _sha(current[1]) != member["published_sha256"] or int(published_identity.get("st_dev", -1)) != int(os.lstat(destination).st_dev) or int(published_identity.get("st_ino", -1)) != int(os.lstat(destination).st_ino):
                raise PatcherError("VV3 individual Full Mastery install_new recovery requires an absent or owned-published destination.")
        if current[0] and _sha(current[1] or b"") not in {member["published_sha256"], member["pre_sha256"]}:
            raise PatcherError("VV3 individual Full Mastery recovery destination is foreign.")
        if not current[0] and pre_exists:
            raise PatcherError("VV3 individual Full Mastery recovery destination is unexpectedly absent.")
        resolved.append((member, destination, backup))
    # Revalidate the complete report chain, root, backups, and destination
    # identities together immediately before creating or replacing any stage.
    if pointer_canonical is not None:
        _load_report_pointer(pointer_canonical, root)
    if not os.path.lexists(report) or _inventory_entry(root, report) != report_snapshot:
        raise PatcherError("VV3 individual Full Mastery recovery report changed before mutation.")
    for member, destination, backup in resolved:
        now = _inventory_entry(root, destination) if os.path.lexists(destination) else None
        if now != destination_snapshots[destination]:
            raise PatcherError("VV3 individual Full Mastery recovery destination changed before mutation.")
        if member["pre_exists"] and (backup is None or _inventory_entry(root, backup) != member.get("backup_inventory")):
            raise PatcherError("VV3 individual Full Mastery recovery backup changed before mutation.")
    # Stage every restore before replacing either member; backups remain intact.
    replay_payload = payload
    preserved_backup_paths: list[Path] = []
    preserved_backup_records: dict[Path, dict[str, object]] = {}
    stages: list[tuple[dict[str, object], Path, Path]] = []
    replay_stage_paths: list[Path] = []
    replay_stage_records: dict[Path, dict[str, object]] = {}
    try:
        for member, destination, backup in resolved:
            if not member["pre_exists"]:
                continue
            data = _read_regular(backup) if backup is not None else b""
            stage = replay_root / f".{destination.name}.vv3im-replay-{uuid.uuid4().hex}.stage"
            _write_file(stage, data)
            replay_stage_paths.append(stage)
            if _sha(_read_regular(stage)) != member["pre_sha256"]:
                raise PatcherError("VV3 individual Full Mastery replay stage mismatch.")
            replay_stage_records[stage] = _inventory_entry(replay_root, stage)
            stages.append((member, destination, stage))
        for member, destination, backup in resolved:
            current = _state(destination)
            if current[0] and _sha(current[1] or b"") not in {member["published_sha256"], member["pre_sha256"]}:
                raise PatcherError("VV3 individual Full Mastery replay race detected.")
        for member, destination, stage in stages:
            current_identity = _inventory_entry(root, destination) if os.path.lexists(destination) else None
            if current_identity != destination_snapshots[destination]:
                raise PatcherError("VV3 individual Full Mastery recovery destination changed before replacement.")
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
                _remove_owned(destination, expected=_inventory_entry(root, destination))
        for member, destination, backup in resolved:
            if member["pre_exists"] and _state(destination)[1] != _read_regular(backup):
                raise PatcherError("VV3 individual Full Mastery replay pair verification failed.")
        # Keep copy-preserved backups until every cleanup member is verified;
        # if cleanup is interrupted, the refreshed report points at these
        # copies rather than at any backup that may already have been removed.
        replay_members = [dict(member) for member in members]
        for replay_member, (_member, destination, backup) in zip(replay_members, resolved):
            if backup is None:
                continue
            preserved = replay_root / f".vv3im-preserved-{uuid.uuid4().hex}-{destination.name}.backup"
            _copy_preserved(backup, preserved, _read_regular(backup))
            preserved_backup_paths.append(preserved)
            preserved_backup_records[preserved] = _inventory_entry(root, preserved)
            replay_member["backup_relative"] = _relative_owned(root, preserved)
            replay_member["backup_inventory"] = _inventory_member(root, preserved)
        replay_payload = dict(payload)
        replay_payload["members"] = replay_members
        # Bind the full pre-cleanup recovery inventory, including any
        # copy-preserved backups created for this replay.  Refreshes may only
        # retain a subset of these verified members; foreign descendants are
        # rejected rather than adopted.
        replay_inventory = _inventory_tree(replay_root)
        for item in replay_inventory:
            item["path"] = _relative_owned(root, replay_root / str(item["path"]))
        replay_root_current = os.lstat(replay_root)
        replay_inventory.insert(0, {"path": _relative_owned(root, replay_root), "type": "directory", "size": 0, "sha256": None, "st_dev": int(replay_root_current.st_dev), "st_ino": int(replay_root_current.st_ino)})
        replay_payload["ownership_inventory"] = replay_inventory
        for stage in replay_stage_paths:
            if os.path.lexists(stage):
                _remove_owned(stage, expected=replay_stage_records.get(stage))
        for member in members:
            original_stage = root / str(member["stage_relative"]) if member.get("stage_relative") else None
            if original_stage is not None and os.path.lexists(original_stage):
                _remove_owned(original_stage, expected=member.get("stage_inventory"))
        # The durable report must be proven absent before any preserved
        # backup is consumed.  If backup cleanup fails afterward, the
        # exception path recreates a complete report from retained copies.
        report_before_delete = os.lstat(report)
        _reject_entry(report, report_before_delete, directory=False)
        report_record = _inventory_entry(root, report)
        _remove_owned(report, expected=report_record)
        if os.path.lexists(report):
            raise PatcherError("VV3 individual Full Mastery recovery report deletion did not verify.")
        if pointer_canonical is not None:
            canonical_record = _inventory_entry(root, pointer_canonical)
            if pointer_canonical_record is None or canonical_record != pointer_canonical_record:
                raise PatcherError("VV3 individual Full Mastery canonical recovery report identity changed.")
            pointer_path = _report_pointer_path(pointer_canonical)
            if pointer_record is None:
                raise PatcherError("VV3 individual Full Mastery recovery report pointer identity is missing.")
            _remove_owned(pointer_canonical, expected=pointer_canonical_record)
            _remove_owned(pointer_path, expected=pointer_record)
        _fsync_dir(root)
        for member in members:
            backup = root / str(member["backup_relative"]) if member.get("backup_relative") else None
            if backup is not None and os.path.lexists(backup):
                record = next((item for item in payload["ownership_inventory"] if item["path"] == member["backup_relative"]), None)
                _remove_owned(backup, expected=record)
        for preserved in preserved_backup_paths:
            if os.path.lexists(preserved):
                _remove_owned(preserved, expected=preserved_backup_records[preserved])
        # A previous failed replay may have left an original backup that is
        # no longer referenced by the refreshed member list.  It is still
        # owned material, so remove it only through its recorded identity.
        inventory_by_path = {
            str(item["path"]): item
            for item in replay_payload.get("ownership_inventory", [])
            if isinstance(item, dict) and item.get("type") == "regular_file"
        }
        replay_prefix = _relative_owned(root, replay_root).rstrip("/") + "/"
        for rel, record in sorted(inventory_by_path.items()):
            if not rel.startswith(replay_prefix):
                continue
            owned = root / rel
            if os.path.lexists(owned):
                _remove_owned(owned, expected=record)
        if os.path.lexists(replay_root):
            _remove_owned(replay_root, expected=_inventory_entry(root, replay_root), expected_tree=[])
        closed_manifest_names = {
            f".chain-{item.name}.json"
            for item in (*sibling_reports, *sibling_successors, *sibling_markers)
        }
        if chain_manifest.name.startswith(".chain-"):
            closed_manifest_names.add(chain_manifest.name)
        _remove_owned(chain_manifest, expected=chain_manifest_record)
        chain_journal = _transaction_authority_path(chain_manifest)
        if os.path.lexists(chain_journal) and chain_journal != final_authority_path:
            _delete_file_by_handle(chain_journal, _inventory_entry(root, chain_journal))
        for marker, marker_record in compatible_marker_records:
            if os.path.lexists(marker):
                _remove_owned(marker, expected=marker_record)
            marker_manifest = _chain_manifest_path(marker)
            if os.path.lexists(marker_manifest):
                marker_manifest_record = _inventory_entry(root, marker_manifest)
                _remove_owned(marker_manifest, expected=marker_manifest_record)
            marker_journal = _transaction_authority_path(marker_manifest)
            if os.path.lexists(marker_journal) and marker_journal != final_authority_path:
                _delete_file_by_handle(marker_journal, _inventory_entry(root, marker_journal))
        # Retire every journal that belongs to this closed chain, but reject
        # an unrelated or malformed journal rather than silently deleting it.
        for journal in sorted(root.glob(".vv3im-journal-*.json")):
            if journal == final_authority_path:
                continue
            journal_record = _inventory_entry(root, journal)
            journal_raw = json.loads(_read_regular(journal).decode("utf-8"))
            manifest_name = journal_raw.get("manifest_name") if isinstance(journal_raw, dict) else None
            journal_role = isinstance(manifest_name, str) and re.fullmatch(
                re.escape(f".chain-{recovery_prefix}") + r"-(?:recovery|emergency)-[0-9a-f]{32}\.json\.json",
                manifest_name,
            )
            if not isinstance(manifest_name, str) or Path(manifest_name).name != manifest_name or (manifest_name not in closed_manifest_names and not journal_role):
                raise PatcherError("VV3 individual Full Mastery foreign transaction authority remains during cleanup.")
            _delete_file_by_handle(journal, journal_record)
        _fsync_dir(root)
        # The final authority remains while every predecessor/member cleanup
        # is complete.  Two full hidden-namespace captures plus an immediate
        # identity recapture close the last mutation interval before its
        # deletion; any insertion/substitution retains the authority and
        # makes replay fail closed.
        if not os.path.lexists(final_authority_path) or _inventory_entry(root, final_authority_path) != final_authority_record:
            raise PatcherError("VV3 individual Full Mastery finalization authority changed before retirement.")
        # A canonical report reconstructed from an emergency marker may still
        # have that marker (and its bound manifest/journal) live until the
        # outer recovery call retires it.  They are explicit predecessors,
        # not an invitation to accept arbitrary hidden children.
        expected_finalization = {final_authority_path.name}
        for predecessor in (*sibling_reports, *sibling_successors, *sibling_markers):
            if os.path.lexists(predecessor):
                expected_finalization.add(predecessor.name)
            predecessor_manifest = _chain_manifest_path(predecessor)
            if os.path.lexists(predecessor_manifest):
                expected_finalization.add(predecessor_manifest.name)
                predecessor_journal = _transaction_authority_path(predecessor_manifest)
                if os.path.lexists(predecessor_journal):
                    expected_finalization.add(predecessor_journal.name)
        # A report reconstructed from a marker can leave an older, bound
        # chain manifest discoverable even though its report name is no longer
        # a current sibling.  Admit only manifests whose complete transaction
        # payload matches this report; any other chain-shaped child is foreign.
        chain_shape = re.compile(r"\.chain-\.vv3im-(?:recovery|emergency)-[0-9a-f]{32}\.json\.json")
        for entry in os.scandir(root):
            if not chain_shape.fullmatch(entry.name) or entry.name in expected_finalization:
                continue
            candidate_manifest = Path(entry.path)
            candidate_raw = json.loads(_read_regular(candidate_manifest).decode("utf-8"))
            if (
                not isinstance(candidate_raw, dict)
                or candidate_raw.get("schema_version") != 3
                or candidate_raw.get("kind") != "vv3_recovery_chain_manifest"
                or candidate_raw.get("recovery_root_name") != payload.get("recovery_root_name")
                or candidate_raw.get("recovery_root_record") != payload.get("recovery_root_identity")
                or candidate_raw.get("members") != payload.get("members")
                or candidate_raw.get("ownership_inventory") != payload.get("ownership_inventory")
            ):
                raise PatcherError("VV3 individual Full Mastery finalization found a foreign chain manifest.")
            expected_finalization.update({
                candidate_manifest.name,
                _transaction_authority_path(candidate_manifest).name,
            })
        expected_finalization = {
            name for name in expected_finalization
            if "vv3im-" in name and os.path.lexists(root / name)
        }
        _validate_vv3_hidden_namespace(root, expected=expected_finalization)
        _validate_vv3_hidden_namespace(root, expected=expected_finalization)
        if _inventory_entry(root, final_authority_path) != final_authority_record:
            raise PatcherError("VV3 individual Full Mastery finalization authority changed during namespace proof.")
        _delete_file_by_handle(final_authority_path, final_authority_record)
        if os.path.lexists(final_authority_path):
            raise PatcherError("VV3 individual Full Mastery finalization authority deletion did not verify.")
        _fsync_dir(root)
        _validate_vv3_hidden_namespace(root, expected=expected_finalization - {final_authority_path.name})
        _validate_vv3_hidden_namespace(root, expected=expected_finalization - {final_authority_path.name})
    except Exception:
        # Never consume backups or delete evidence on a failed replay.  Replay
        # stages are owned temporary material; remove them only after an
        # identity/hash check.  If cleanup itself fails the evidence remains,
        # and the caller receives the fail-closed error.
        cleanup_errors: list[BaseException] = []
        for stage in replay_stage_paths:
            if os.path.lexists(stage):
                try:
                    _remove_owned(stage, expected=replay_stage_records.get(stage))
                except Exception as cleanup_exc:
                    cleanup_errors.append(cleanup_exc)
        refresh_error: BaseException | None = None
        if os.path.lexists(replay_root):
            try:
                _refresh_recovery_report(report, replay_payload, root, replay_root)
            except Exception as refresh_exc:
                refresh_error = refresh_exc
        if refresh_error is not None:
            # If the canonical report cannot be recreated, retain a separate
            # identity-bound emergency marker.  Never swallow this failure or
            # claim that unreported recovery material is safe.
            emergency_details = dict(replay_payload)
            emergency_details.update({
                "_report_prefix": recovery_prefix,
                "_recovery_root_name": replay_root.name,
                "_recovery_root_identity": {"st_dev": int(os.lstat(replay_root).st_dev), "st_ino": int(os.lstat(replay_root).st_ino)} if os.path.lexists(replay_root) else None,
            })
            try:
                marker = _write_emergency_marker(root, emergency_details, refresh_error)
            except Exception as marker_exc:
                raise PatcherError("VV3 individual Full Mastery replay report refresh and emergency evidence failed.") from marker_exc
            raise PatcherError(f"VV3 individual Full Mastery replay report refresh failed; emergency marker retained at {marker}.") from refresh_error
        if cleanup_errors:
            raise PatcherError("VV3 individual Full Mastery replay cleanup failed; recovery evidence retained.") from cleanup_errors[0]
        raise


# Explicit production-facing name used by audit/recovery callers.
recover_vv3_transaction = recover_atomic


def install_atomic(source: Path, destination: Path, mode: str, *, companion_source: Path | None = None, companion_destination: Path | None = None) -> None:
    _require_windows_identity_atomic()
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
    _transaction(
        "install", destinations, pre,
        {destinations[0]: candidate, destinations[1]: companion_bytes},
        expected_preimage=expected_preimage,
        parent=parent,
        recovery_metadata={
            "feature_owner": "vv3_individual_full_mastery",
            "mode": mode,
            "parent_sha256": PARENT_HASHES[mode],
            "candidate_sha256": OUTPUT_HASHES[mode],
            "destination_exe_basename": destinations[0].name,
            "companion_dll_basename": destinations[1].name,
            "member_roles": {destinations[0].name: "game_executable", destinations[1].name: "companion_dll"},
            "destination_paths_absolute": [str(path.absolute()).casefold() for path in destinations],
        },
    )


def remove_atomic(destination: Path, mode: str, *, companion_destination: Path | None = None, companion_restore_source: Path | None = None) -> None:
    _require_windows_identity_atomic()
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
    _transaction(
        "remove", destinations, pre,
        {destinations[0]: parent_bytes, destinations[1]: companion_parent},
        expected_preimage={},
        parent=parent,
        recovery_metadata={
            "feature_owner": "vv3_individual_full_mastery",
            "mode": mode,
            "parent_sha256": PARENT_HASHES[mode],
            "candidate_sha256": OUTPUT_HASHES[mode],
            "destination_exe_basename": destinations[0].name,
            "companion_dll_basename": destinations[1].name,
            "member_roles": {destinations[0].name: "game_executable", destinations[1].name: "companion_dll"},
            "destination_paths_absolute": [str(path.absolute()).casefold() for path in destinations],
        },
    )
