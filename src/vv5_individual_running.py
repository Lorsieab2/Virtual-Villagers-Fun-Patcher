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
VV5_EXE_BASENAME = "Virtual Villagers - New Believers - Modded.exe"
VV5_PARENT_EXE_SHA256 = "857E22D7C361B802508BF789C3CC486E42E76021F5AA579BB1D16CC6E0D017A0"
VV5_CANDIDATE_EXE_SHA256 = "1E3FD6CE44E906BD8DDD7C937D68AB74671D8F197BC1D767A2B0622F1A0F7907"
VV5_PARENT_DLL_SHA256 = DLL_SHA256
VV5_CANDIDATE_DLL_SHA256 = DLL_SHA256
ISSUANCE_SCHEMA_VERSION = 1
ISSUANCE_REGISTRY_NAME = ".vv5run-issuance"


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


def _cleanup(path: Path, *, expected: dict[str, object] | None = None) -> None:
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
    path.unlink()
    if os.path.lexists(path):
        raise PatcherError(f"VV5 Running owned cleanup did not remove: {path}")


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


def _identity(path: Path) -> dict[str, int]:
    st = os.lstat(path)
    return {"st_dev": int(getattr(st, "st_dev", 0)), "st_ino": int(getattr(st, "st_ino", 0))}


def _canonical(path: Path) -> str:
    return os.path.normcase(os.path.abspath(os.fspath(path)))


def _registry(parent: Path) -> tuple[Path, dict[str, int], bool]:
    """Return the fixed destination-parent-owned issuance registry."""
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
    return registry, _identity(registry), created


def _cleanup_registry(registry: Path, expected: dict[str, int]) -> None:
    if not os.path.lexists(registry):
        return
    st = os.lstat(registry)
    if stat.S_ISLNK(st.st_mode) or _unsafe(st) or not stat.S_ISDIR(st.st_mode):
        raise PatcherError("VV5 Running issuance registry identity changed.")
    if _identity(registry) != expected:
        raise PatcherError("VV5 Running issuance registry was substituted.")
    with os.scandir(registry) as entries:
        if any(True for _ in entries):
            return
    registry.rmdir()
    if os.path.lexists(registry):
        raise PatcherError("VV5 Running issuance registry cleanup did not verify.")


def _write_issuance(path: Path, payload: dict[str, object]) -> None:
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
        # Hard-link publication is exclusive on the same volume: a raced
        # destination can never be overwritten by issuance creation.
        os.link(tmp, path)
        published = _inventory(path.parent, path)
        if published is None or published["sha256"] != _sha(data) or published["size"] != len(data):
            raise PatcherError("VV5 Running issuance publication verification failed.")
        _cleanup(tmp, expected=tmp_identity)
    except Exception as exc:
        if os.path.lexists(tmp):
            if tmp_identity is not None:
                _cleanup(tmp, expected=tmp_identity)
        if isinstance(exc, PatcherError):
            raise
        raise PatcherError("VV5 Running issuance publication failed; no destination was overwritten.") from exc


def _replace_issuance(path: Path, before: dict[str, object], payload: dict[str, object]) -> dict[str, object]:
    current = _inventory(path.parent, path)
    if current is None or any(current.get(key) != before.get(key) for key in ("type", "size", "sha256", "st_dev", "st_ino")):
        raise PatcherError("VV5 Running issuance record was substituted before binding.")
    tmp = path.with_suffix(".tmp")
    if os.path.lexists(tmp):
        raise PatcherError("VV5 Running issuance temporary collision.")
    tmp_identity: dict[str, object] | None = None
    data = (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")
    try:
        _write(tmp, data)
        tmp_identity = _inventory(tmp.parent, tmp)
        current = _inventory(path.parent, path)
        if current is None or any(current.get(key) != before.get(key) for key in ("type", "size", "sha256", "st_dev", "st_ino")):
            raise PatcherError("VV5 Running issuance record raced during binding.")
        os.replace(tmp, path)
        after = _inventory(path.parent, path)
        if after is None or after["sha256"] != _sha(data) or after["size"] != len(data):
            raise PatcherError("VV5 Running issuance binding publication verification failed.")
        return after
    except Exception:
        if os.path.lexists(tmp):
            if tmp_identity is not None:
                _cleanup(tmp, expected=tmp_identity)
        raise


def _issuance_payload(token: str, operation: str, parent: Path, destinations: list[Path], pre: dict[Path, tuple[bool, bytes | None]], published: dict[Path, bytes], registry: Path, registry_identity: dict[str, int]) -> dict[str, object]:
    return {
        "schema_version": ISSUANCE_SCHEMA_VERSION,
        "token": token,
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
    if raw.get("schema_version") != ISSUANCE_SCHEMA_VERSION or raw.get("token") != token:
        raise PatcherError("VV5 Running issuance record is invalid.")
    if (
        raw.get("destination_parent_absolute") != report_payload.get("destination_parent_absolute")
        or raw.get("destination_paths_absolute") != report_payload.get("destination_paths_absolute")
        or raw.get("registry_relative") != ISSUANCE_REGISTRY_NAME
        or raw.get("registry_identity") != report_payload.get("issuance_registry_identity")
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
    if [Path(destination).name for destination in destinations] != [VV5_EXE_BASENAME, DLL_NAME]:
        raise PatcherError("VV5 Running destinations do not match the certified game/DLL names.")
    registry, registry_identity, registry_created = _registry(parent)
    issuance_token = uuid.uuid4().hex
    issuance_path = registry / f"{issuance_token}.json"
    issuance_payload = _issuance_payload(issuance_token, operation, parent, destinations, pre, published, registry, registry_identity)
    try:
        _write_issuance(issuance_path, issuance_payload)
    except Exception:
        if registry_created and os.path.lexists(registry):
            try:
                _cleanup_registry(registry, registry_identity)
            except Exception:
                pass
        raise
    issuance_identity = _inventory(parent, issuance_path)
    if issuance_identity is None:
        raise PatcherError("VV5 Running issuance identity could not be captured.")
    try:
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
                "issuance_identity": issuance_identity,
                "destination_parent_absolute": _canonical(parent),
                "destination_paths_absolute": [_canonical(p) for p in destinations],
            },
        )
    except Exception as exc:
        reports = []
        for candidate in sorted(parent.glob(".vv5run-recovery-*.json"), key=lambda p: p.name):
            try:
                raw = json.loads(_read(candidate).decode("utf-8"))
            except Exception:
                continue
            if raw.get("issuance_token") == issuance_token:
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
            _cleanup(issuance_path, expected=issuance_identity)
            if registry_created:
                _cleanup_registry(registry, registry_identity)
        raise
    # The strict transaction is the sole production path.  Once it has
    # returned, bind no legacy replay implementation: verify and remove only
    # the originally captured issuance record, then return immediately.
    if os.path.lexists(issuance_path):
        _cleanup(issuance_path, expected=issuance_identity)
    if registry_created:
        _cleanup_registry(registry, registry_identity)
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
    issuance_path = registry / f"{issuance_token}.json"
    if issuance_path.parent != registry or issuance_path.name != f"{issuance_token}.json":
        raise PatcherError("VV5 Running recovery issuance path is unsafe.")
    issuance_identity = _inventory(report.parent, issuance_path)
    if issuance_identity is None:
        raise PatcherError("VV5 Running recovery issuance record is missing.")
    issuance = json.loads(_read(issuance_path).decode("utf-8"))
    root_identity = raw.get("recovery_root_identity")
    report_parent_identity = raw.get("report_parent_identity")
    root_entry = next((item for item in raw.get("ownership_inventory", []) if item.get("type") == "directory" and "/" not in str(item.get("path", ""))), None)
    expected_root_identity = {"st_dev": int(root_entry["st_dev"]), "st_ino": int(root_entry["st_ino"])} if isinstance(root_entry, dict) else None
    if raw.get("report_name") != report.name or raw.get("recovery_root_name") != (Path(str(root_entry["path"])).name if isinstance(root_entry, dict) else None) or root_identity != expected_root_identity:
        raise PatcherError("VV5 Running recovery report location identity mismatch.")
    parent_st = os.lstat(report.parent)
    if not isinstance(root_identity, dict) or not isinstance(report_parent_identity, dict) or report_parent_identity != {"st_dev": int(parent_st.st_dev), "st_ino": int(parent_st.st_ino)}:
        raise PatcherError("VV5 Running recovery report root identity mismatch.")
    if raw.get("destination_parent_absolute") != _canonical(report.parent) or raw.get("destination_paths_absolute") != [_canonical(report.parent / VV5_EXE_BASENAME), _canonical(report.parent / DLL_NAME)]:
        raise PatcherError("VV5 Running recovery destination parent/path binding mismatch.")
    registry_identity = raw.get("issuance_registry_identity")
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
    _strict_recover_atomic(
        report,
        recovery_prefix=".vv5run",
        required_metadata={
            "feature_owner": VV5_FEATURE_OWNER,
            "mode": VV5_MODE,
            "parent_sha256": VV5_PARENT_EXE_SHA256,
            "candidate_sha256": VV5_CANDIDATE_EXE_SHA256,
            "destination_exe_basename": VV5_EXE_BASENAME,
            "companion_dll_basename": DLL_NAME,
            "member_roles": {VV5_EXE_BASENAME: "game_executable", DLL_NAME: "companion_dll"},
            "recovery_root_name": raw.get("recovery_root_name"),
            "recovery_root_identity": root_identity,
            "report_name": report.name,
            "report_parent_identity": report_parent_identity,
            "issuance_token": issuance_token,
            "issuance_name": issuance_name,
            "issuance_registry_relative": raw.get("issuance_registry_relative"),
            "issuance_registry_identity": raw.get("issuance_registry_identity"),
            "issuance_identity": raw.get("issuance_identity"),
            "destination_parent_absolute": raw.get("destination_parent_absolute"),
            "destination_paths_absolute": raw.get("destination_paths_absolute"),
        },
        expected_report_sha256=report_sha256,
    )
    # The shared strict replay is the sole recovery implementation.  Its
    # return means the pair, report, and owned recovery tree have passed full
    # verification.  Only then may the originally captured issuance record be
    # removed; any substitution/race is a fail-closed error.
    if _inventory(report.parent, issuance_path) != issuance_identity:
        raise PatcherError("VV5 Running issuance record changed during replay.")
    _cleanup(issuance_path, expected=issuance_identity)
    if os.path.lexists(registry):
        _cleanup_registry(registry, registry_identity)
    return


def install_atomic(source: Path, destination: Path, mode: str, *, companion_source: Path | None = None, companion_destination: Path | None = None) -> None:
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
