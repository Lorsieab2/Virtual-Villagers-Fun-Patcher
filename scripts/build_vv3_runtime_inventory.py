"""Build the self-describing VV3 runtime inventory used by player packages."""

from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path
from typing import Mapping, Sequence

SCHEMA_VERSION = "vvfp.runtime_inventory.v1"
INVENTORY_NAME = "runtime-inventory.json"
CHECKSUMS_NAME = "SHA256SUMS.txt"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def vv3_authoritative_result_messages(manifest_path: Path) -> dict[str, str]:
    """Return the exact result strings used by the emitted VV3 Full Heal helper.

    The candidate manifest is the source-of-truth projection of the helper's
    ASCII strings.  Package logs must copy these values byte-for-byte; they may
    not paraphrase punctuation, CRLFs, or the inline rollback disclosure.
    """

    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    messages = manifest.get("messages")
    if not isinstance(messages, dict):
        raise ValueError("VV3 Full Heal manifest messages are missing")
    result = {
        "success": messages.get("success_format"),
        "failure": messages.get("failure_format"),
    }
    if not all(isinstance(value, str) for value in result.values()):
        raise ValueError("VV3 Full Heal result strings are missing")
    return result


def update_vv3_patch_log_messages(
    patch_log_path: Path, manifest_path: Path
) -> dict[str, object]:
    """Copy authoritative helper result strings into a package patch log."""

    patch_log_path = Path(patch_log_path)
    log = json.loads(patch_log_path.read_text(encoding="utf-8"))
    messages = dict(log.get("messages") or {})
    messages.update(vv3_authoritative_result_messages(manifest_path))
    log["messages"] = messages
    patch_log_path.write_text(json.dumps(log, indent=2) + "\n", encoding="utf-8")
    return log


def _excluded_source_identities(
    archive_path: Path,
    archive_sha256: str,
    excluded_source_members: Sequence[str],
) -> list[dict[str, object]]:
    """Hash each excluded member directly from the authenticated source ZIP."""

    archive_path = Path(archive_path)
    if not archive_path.is_file() or _sha256(archive_path) != str(archive_sha256).upper():
        raise ValueError("authenticated source archive is missing or hash-mismatched")
    identities: list[dict[str, object]] = []
    with zipfile.ZipFile(archive_path) as archive:
        infos = [info for info in archive.infolist() if not info.is_dir()]
        for member in excluded_source_members:
            matches = [info for info in infos if Path(info.filename).name == member]
            if len(matches) != 1:
                raise ValueError(f"excluded source member is not unique in archive: {member}")
            info = matches[0]
            data = archive.read(info)
            if len(data) != info.file_size:
                raise ValueError(f"source archive member size mismatch: {member}")
            identities.append(
                {
                    "member": member,
                    "archive_path": info.filename,
                    "size": info.file_size,
                    "sha256": _sha256_bytes(data),
                }
            )
    return identities


def build_inventory(
    root: Path,
    *,
    entry_executable: str,
    source_archive: Mapping[str, object],
    excluded_source_members: Sequence[str],
    generated_payload_roles: Mapping[str, str],
    generated_file_roles: Mapping[str, str],
    preimage_identities: Mapping[str, object],
    dependency_chain: Sequence[str],
    commits: Mapping[str, str | None],
    identities: Mapping[str, object],
    save_route: str,
    catalog_status: Mapping[str, object],
    runtime_player_status: str,
    source_archive_path: Path | None = None,
    mode: str = "collection_progression",
    expanded: bool = False,
) -> tuple[dict[str, object], list[dict[str, object]]]:
    """Return inventory JSON and payload records without self-hashing metadata."""

    root = root.resolve()
    files = sorted(path for path in root.rglob("*") if path.is_file())
    payload = [path for path in files if path.name not in {INVENTORY_NAME, CHECKSUMS_NAME}]
    if len(files) != 419 or len(payload) != 417:
        raise ValueError(f"VV3 package accounting mismatch: physical={len(files)} payload={len(payload)}")
    roles = {str(key).replace("\\", "/"): str(value) for key, value in generated_payload_roles.items()}
    records: list[dict[str, object]] = []
    for path in payload:
        relative = path.relative_to(root).as_posix()
        role = roles.get(relative, "retained_stock_runtime")
        records.append(
            {
                "path": relative,
                "size": path.stat().st_size,
                "sha256": _sha256(path),
                "role": role,
                "provenance": "current_generated" if role != "retained_stock_runtime" else "authenticated_stock_archive",
            }
        )
    if sum(record["role"] == "retained_stock_runtime" for record in records) != 412:
        raise ValueError("VV3 retained stock role accounting mismatch")
    if len(roles) != 5 or any(record["role"] == "retained_stock_runtime" for record in records if record["path"] in roles):
        raise ValueError("VV3 generated payload role accounting mismatch")

    generated = []
    for relative, role in generated_file_roles.items():
        relative = relative.replace("\\", "/")
        path = root / relative
        if not path.is_file():
            raise ValueError(f"generated inventory file is missing: {relative}")
        generated.append(
            {
                "path": relative,
                "role": role,
                "sha256": None if relative in {INVENTORY_NAME, CHECKSUMS_NAME} else _sha256(path),
                "identity_scope": "self_hash_excluded" if relative in {INVENTORY_NAME, CHECKSUMS_NAME} else "payload_record",
            }
        )
    if len(generated) != 7:
        raise ValueError("VV3 generated-file role accounting mismatch")

    archive = dict(source_archive)
    archive.update(
        {
            "total_entries": 419,
            "runtime_members": 417,
            "outer_evidence_files": 2,
            "retained_stock_files": 412,
            "current_files": 7,
            "payload_records": 417,
            "excluded_source_members": list(excluded_source_members),
        }
    )
    excluded_identities = (
        _excluded_source_identities(source_archive_path, str(archive["sha256"]), excluded_source_members)
        if source_archive_path is not None
        else []
    )
    if excluded_identities:
        archive["excluded_source_member_identities"] = excluded_identities
    preimages = dict(preimage_identities)
    if excluded_identities:
        preimages["excluded_source_members"] = excluded_identities
    inventory = {
        "schema": SCHEMA_VERSION,
        "physical_files": 419,
        "payload_records": 417,
        "mode": mode,
        "expanded": expanded,
        "entry_executable": entry_executable,
        "source_archive": archive,
        "derivation": {
            "retained_stock_files": 412,
            "current_files": 7,
            "payload_records": "412 retained stock + 5 current payload files; inventory/checksum are outer evidence",
            "excluded_source_members": list(excluded_source_members),
        },
        "preimage_identities": preimages,
        "dependency_chain": list(dependency_chain),
        "commits": dict(commits),
        "candidate_identities": dict(identities),
        "save_route": save_route,
        "runtime_player_status": runtime_player_status,
        "catalog_status": dict(catalog_status),
        "generated_file_roles": generated,
        "records": records,
    }
    return inventory, records


def write_inventory_and_checksums(root: Path, **kwargs: object) -> dict[str, object]:
    """Write the inventory and checksum list after all payload files exist."""

    root = Path(root)
    inventory, records = build_inventory(root, **kwargs)
    inventory_path = root / INVENTORY_NAME
    checksums_path = root / CHECKSUMS_NAME
    inventory_path.write_text(json.dumps(inventory, indent=2) + "\n", encoding="utf-8")
    checksums_path.write_text(
        "\n".join(f"{record['sha256']}  {record['path']}" for record in records) + "\n",
        encoding="utf-8",
    )
    return inventory
