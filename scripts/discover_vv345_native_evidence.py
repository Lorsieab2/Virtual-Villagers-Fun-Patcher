"""Emit read-only VV3-VV5 native-evidence query metadata.

This helper is deliberately weaker than the authenticated export validator. It
does not inspect a game folder, open an IDA database, resolve an EA, or create
native output. It only combines the repository-owned query manifest with the
authorized analyzer workflow so an operator can see the exact query order and
the current evidence blocker.

Every unresolved EA/ABI field is emitted as ``null``. A workflow declaration
alone is never treated as reviewed native evidence; the report stays STOP
until a separately reviewed, source-bound export artifact exists.
"""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
QUERY_MANIFEST = ROOT / "data" / "native_evidence_queries.json"
WORKFLOW = ROOT / "data" / "authorized_analyzer_workflow.json"
GAMES = ("vv3", "vv4", "vv5")
DISCOVERY_SCHEMA = "vvfp.native-evidence-discovery.v1"
REQUIRED_OUTPUTS = {
    "function_bounds",
    "ea",
    "file_offset",
    "raw_bytes",
    "instructions",
    "callers",
    "xrefs",
    "registers",
    "stack_cleanup",
    "call_convention",
}


class DiscoveryError(ValueError):
    """Raised when repository-owned discovery inputs are not fail-closed."""


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DiscoveryError(f"cannot read discovery input: {path}") from exc
    if not isinstance(value, dict):
        raise DiscoveryError(f"discovery input must be an object: {path}")
    return value


def _validate_query_manifest(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    if manifest.get("schema") != "vvfp.native-evidence-queries.v1":
        raise DiscoveryError("native-evidence query schema mismatch")
    if manifest.get("games") != list(GAMES):
        raise DiscoveryError("native-evidence query game order mismatch")
    queries = manifest.get("queries")
    if not isinstance(queries, list) or not queries:
        raise DiscoveryError("native-evidence query list is missing")

    seen: set[str] = set()
    for query in queries:
        if not isinstance(query, dict):
            raise DiscoveryError("native-evidence query row is not an object")
        query_id = query.get("id")
        if not isinstance(query_id, str) or not query_id or query_id in seen:
            raise DiscoveryError("native-evidence query IDs must be unique strings")
        seen.add(query_id)
        if query.get("required") is not True:
            raise DiscoveryError(f"optional query is not allowed: {query_id}")
        search = query.get("search")
        if not isinstance(search, dict):
            raise DiscoveryError(f"query search metadata is missing: {query_id}")
        output = query.get("output")
        if not isinstance(output, list) or not REQUIRED_OUTPUTS.issubset(output):
            raise DiscoveryError(f"query output metadata is incomplete: {query_id}")
    return queries


def _validate_workflow(workflow: dict[str, Any]) -> dict[str, Any]:
    if workflow.get("schema_version") != "vvfp.authorized_analyzer_workflow.v1":
        raise DiscoveryError("authorized analyzer workflow schema mismatch")
    if workflow.get("status") != "STOP":
        raise DiscoveryError("authorized analyzer workflow is not STOP")

    run_state = workflow.get("workflow")
    if not isinstance(run_state, dict):
        raise DiscoveryError("authorized analyzer workflow state is missing")
    expected_state = {
        "read_only": True,
        "dry_run": True,
        "launches_performed": 0,
        "saves_accessed": 0,
        "exports_written": 0,
        "native_output": False,
        "publication_ready": False,
        "runtime_go": False,
        "player_go": False,
    }
    if run_state != expected_state:
        raise DiscoveryError("authorized analyzer workflow is not read-only and dry-run")

    gates = workflow.get("gates")
    if not isinstance(gates, dict) or any(
        gates.get(name) is not False
        for name in (
            "enabled",
            "catalog_enabled",
            "native_output",
            "runtime_go",
            "player_go",
            "publication_ready",
        )
    ) or gates.get("catalog_hidden") is not True:
        raise DiscoveryError("analyzer feature gates are not fail-closed")

    bindings = workflow.get("game_bindings")
    if not isinstance(bindings, dict) or set(bindings) != set(GAMES):
        raise DiscoveryError("VV3-VV5 game bindings are incomplete")
    for game in GAMES:
        binding = bindings[game]
        if not isinstance(binding, dict):
            raise DiscoveryError(f"game binding is not an object: {game}")
        export = binding.get("export")
        if not isinstance(export, dict):
            raise DiscoveryError(f"export state is missing: {game}")
    return bindings


def _candidate_query_metadata(query: dict[str, Any]) -> dict[str, Any]:
    """Copy query requirements while making unresolved proof explicit."""

    return {
        "query_id": query["id"],
        "required": True,
        "search": copy.deepcopy(query["search"]),
        "required_output": list(query["output"]),
        "reviewed_function_start_ea": None,
        "reviewed_function_end_ea": None,
        "reviewed_file_offset": None,
        "reviewed_raw_bytes": None,
        "reviewed_registers": None,
        "reviewed_stack_cleanup": None,
        "reviewed_call_convention": None,
    }


def build_report(workflow: dict[str, Any], manifest: dict[str, Any]) -> dict[str, Any]:
    """Build a deterministic report without resolving or fabricating evidence."""

    queries = _validate_query_manifest(manifest)
    bindings = _validate_workflow(workflow)
    query_metadata = [_candidate_query_metadata(query) for query in queries]
    games = []

    for game in GAMES:
        binding = bindings[game]
        export = binding["export"]
        artifact_path = export.get("artifact_path")
        resolved_rows = export.get("resolved_rows")
        if artifact_path is None and resolved_rows == 0:
            evidence_status = "ABSENT"
            blockers = ["reviewed EA/ABI export artifact is absent"]
        else:
            evidence_status = "DECLARED_BUT_UNVERIFIED"
            blockers = [
                "workflow metadata is not a reviewed source-bound EA/ABI export",
                "independent export validation is required before any native claim",
            ]

        games.append(
            {
                "game": game,
                "source_binding": {
                    "folder": binding.get("folder"),
                    "inventory_sha256": binding.get("inventory_sha256"),
                    "executable": copy.deepcopy(binding.get("executable")),
                },
                "query_count": len(query_metadata),
                "query_ids": [row["query_id"] for row in query_metadata],
                "candidate_query_metadata": copy.deepcopy(query_metadata),
                "workflow_export": {
                    "status": export.get("status"),
                    "artifact_path": artifact_path,
                    "artifact_sha256": export.get("artifact_sha256"),
                    "resolved_rows": resolved_rows,
                },
                "reviewed_ea_abi_status": evidence_status,
                "blockers": blockers,
                "status": "STOP",
            }
        )

    return {
        "schema": DISCOVERY_SCHEMA,
        "status": "STOP",
        "reason": "reviewed_EA_ABI_evidence_absent_or_unverified",
        "read_only": True,
        "writes": [],
        "native_output": False,
        "routes_enabled": False,
        "runtime_go": False,
        "player_go": False,
        "publication_ready": False,
        "games": games,
    }


def discover(
    workflow_path: Path = WORKFLOW,
    query_manifest_path: Path = QUERY_MANIFEST,
) -> dict[str, Any]:
    """Read the two repository manifests and return a fail-closed report."""

    return build_report(_load_json(workflow_path), _load_json(query_manifest_path))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workflow", type=Path, default=WORKFLOW)
    parser.add_argument("--queries", type=Path, default=QUERY_MANIFEST)
    args = parser.parse_args(argv)
    try:
        report = discover(args.workflow, args.queries)
    except DiscoveryError as exc:
        print(f"STOP: {exc}")
        return 2
    print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
