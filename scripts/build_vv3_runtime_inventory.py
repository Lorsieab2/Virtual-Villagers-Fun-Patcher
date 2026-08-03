"""Build the self-describing VV3 runtime inventory used by player packages."""

from __future__ import annotations

import hashlib
import json
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
        "preimage_identities": dict(preimage_identities),
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
