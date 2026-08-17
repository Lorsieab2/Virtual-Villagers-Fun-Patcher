"""Evidence-backed output transparency artifacts.

The patcher writes these artifacts only after the executable, companions, and
copied game tree have been verified.  This module deliberately keeps paths
relative to the game-folder names in the human-readable report so a report
can be shared without disclosing a user's profile directory.
"""

from __future__ import annotations

import hashlib
import json
import os
import struct
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


TRANSPARENCY_FILENAME = "VVFP Transparency Log.txt"
PATCHER_VERSION = "v1.34.12"


def validate_feature_transparency_metadata(features: Iterable[Any]) -> None:
    """Reject selectable features whose report coverage is incomplete."""
    for feature in features:
        raw = feature.raw if hasattr(feature, "raw") else feature
        feature_id = raw.get("id", "<unknown>")
        for key in ("id", "game_id", "name", "description", "behavior_changes", "explicit_non_changes", "evidence_status"):
            if key not in raw:
                raise ValueError(f"Transparency metadata missing {key} for {feature_id}")
        if not isinstance(raw["behavior_changes"], list) or not isinstance(raw["explicit_non_changes"], list):
            raise ValueError(f"Transparency metadata lists are invalid for {feature_id}")
        if not str(raw["evidence_status"]).strip():
            raise ValueError(f"Transparency evidence status is empty for {feature_id}")
        for index, patch in enumerate(raw.get("patches", [])):
            if not str(patch.get("purpose", "")).strip():
                raise ValueError(f"Transparency purpose missing for {feature_id} patch {index}")


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def _git_commit(root: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return "unavailable"
    return result.stdout.strip() or "unavailable"


def _safe_relative(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.name


def _file_entry(path: Path, relative: str) -> dict[str, Any]:
    return {
        "path": relative,
        "size": path.stat().st_size,
        "sha256": file_hash(path),
    }


def directory_comparison(
    source_folder: Path,
    output_folder: Path,
    *,
    generated_names: Iterable[str] = (),
) -> dict[str, Any]:
    """Compare source/output trees using size and SHA-256.

    Generated report files are represented separately by the transparency
    metadata and excluded from the source-vs-output comparison to avoid a
    self-referential report.  The modified executable and companions remain in
    the comparison and therefore are always backed by actual output hashes.
    """

    excluded = {str(name).replace("\\", "/") for name in generated_names}

    def collect(root: Path) -> dict[str, Path]:
        result: dict[str, Path] = {}
        if not root.is_dir():
            return result
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            relative = path.relative_to(root).as_posix()
            if relative in excluded:
                continue
            result[relative] = path
        return result

    source = collect(source_folder)
    output = collect(output_folder)
    added: list[dict[str, Any]] = []
    modified: list[dict[str, Any]] = []
    removed: list[dict[str, Any]] = []
    unchanged = 0
    for relative in sorted(output.keys() - source.keys()):
        added.append(_file_entry(output[relative], relative))
    for relative in sorted(source.keys() - output.keys()):
        removed.append(_file_entry(source[relative], relative))
    for relative in sorted(source.keys() & output.keys()):
        source_entry = _file_entry(source[relative], relative)
        output_entry = _file_entry(output[relative], relative)
        if (
            source_entry["size"] == output_entry["size"]
            and source_entry["sha256"] == output_entry["sha256"]
        ):
            unchanged += 1
        else:
            modified.append({"source": source_entry, "output": output_entry})
    return {
        "added": added,
        "modified": modified,
        "removed": removed,
        "unchanged_count": unchanged,
        "no_removals_proven": not removed,
    }


def _pe_snapshot(data: bytes) -> dict[str, Any]:
    """Return a small, dependency-free PE layout snapshot."""

    if len(data) < 0x40 or data[:2] != b"MZ":
        return {"valid": False, "file_size": len(data), "sections": []}
    pe_offset = struct.unpack_from("<I", data, 0x3C)[0]
    if pe_offset + 24 > len(data) or data[pe_offset : pe_offset + 4] != b"PE\0\0":
        return {"valid": False, "file_size": len(data), "sections": []}
    coff = pe_offset + 4
    section_count = struct.unpack_from("<H", data, coff + 2)[0]
    optional_size = struct.unpack_from("<H", data, coff + 16)[0]
    optional = coff + 20
    if optional + optional_size > len(data):
        return {"valid": False, "file_size": len(data), "sections": []}
    magic = struct.unpack_from("<H", data, optional)[0]
    if magic == 0x10B:
        image_base = struct.unpack_from("<I", data, optional + 28)[0]
    elif magic == 0x20B:
        image_base = struct.unpack_from("<Q", data, optional + 24)[0]
    else:
        image_base = 0
    size_of_image = struct.unpack_from("<I", data, optional + 56)[0]
    checksum = struct.unpack_from("<I", data, optional + 64)[0]
    section_base = optional + optional_size
    sections: list[dict[str, Any]] = []
    executable_ranges: list[dict[str, str]] = []
    for index in range(section_count):
        offset = section_base + index * 40
        if offset + 40 > len(data):
            break
        raw_name = data[offset : offset + 8].split(b"\0", 1)[0]
        name = raw_name.decode("ascii", errors="replace")
        virtual_size, virtual_address, raw_size, raw_pointer = struct.unpack_from(
            "<IIII", data, offset + 8
        )
        characteristics = struct.unpack_from("<I", data, offset + 36)[0]
        entry = {
            "name": name,
            "virtual_size": virtual_size,
            "virtual_address": f"0x{virtual_address:X}",
            "raw_size": raw_size,
            "raw_pointer": f"0x{raw_pointer:X}",
            "characteristics": f"0x{characteristics:08X}",
        }
        sections.append(entry)
        if characteristics & 0x20000000:
            executable_ranges.append(
                {
                    "name": name,
                    "start": f"0x{image_base + virtual_address:X}",
                    "end": f"0x{image_base + virtual_address + max(virtual_size, raw_size):X}",
                }
            )
    return {
        "valid": True,
        "file_size": len(data),
        "image_base": f"0x{image_base:X}",
        "size_of_image": size_of_image,
        "checksum": f"0x{checksum:08X}",
        "checksum_file_offset": optional + 64,
        "sections": sections,
        "executable_ranges": executable_ranges,
    }


def pe_difference(source: Path, output: Path) -> dict[str, Any]:
    before = _pe_snapshot(source.read_bytes())
    after = _pe_snapshot(output.read_bytes())
    before_sections = {item["name"]: item for item in before.get("sections", [])}
    after_sections = {item["name"]: item for item in after.get("sections", [])}
    section_changes: list[dict[str, Any]] = []
    for name in sorted(set(before_sections) | set(after_sections)):
        if before_sections.get(name) != after_sections.get(name):
            section_changes.append(
                {
                    "name": name,
                    "before": before_sections.get(name),
                    "after": after_sections.get(name),
                }
            )
    return {
        "before": before,
        "after": after,
        "section_changes": section_changes,
        "added_or_expanded_sections": [
            change["name"]
            for change in section_changes
            if change["before"] is None
            or change["after"] is None
            or (
                change["before"]
                and change["after"]
                and int(change["after"]["raw_size"])
                > int(change["before"]["raw_size"])
            )
        ],
        "relocated_pointers": [],
    }


def _display_path(path: str | Path, root: Path | None = None) -> str:
    value = Path(path)
    if root is not None:
        relative = _safe_relative(value, root)
        if relative != value.name:
            return relative
    return value.name


def _feature_details(fun_patches: Iterable[Any]) -> list[dict[str, Any]]:
    details: list[dict[str, Any]] = []
    for feature in fun_patches:
        raw = feature.raw
        raw_dependencies = raw.get("dependencies", [])
        if isinstance(raw_dependencies, str):
            raw_dependencies = [raw_dependencies]
        details.append(
            {
                "id": feature.id,
                "name": feature.name,
                "game_id": feature.game_id,
                "dependencies": list(raw_dependencies),
                "behavior_changes": list(raw.get("behavior_changes", [feature.description])),
                "explicit_non_changes": list(
                    raw.get("explicit_non_changes", raw.get("exclusions", []))
                ),
                "partial_failure_limit": raw.get("partial_failure_limit"),
                "evidence_status": raw.get(
                    "evidence_status",
                    "static source/manifest verification performed; runtime/player confirmation pending",
                ),
                "description": feature.description,
            }
        )
    return details


def build_transparency_data(
    *,
    base_log: dict[str, Any],
    source: Path,
    output: Path,
    source_folder: Path,
    output_folder: Path,
    fun_patches: Iterable[Any],
    companions: list[dict[str, Any]],
    applied: list[dict[str, Any]],
    save_copy: dict[str, Any] | None,
    root: Path,
) -> dict[str, Any]:
    fun_patches = list(fun_patches)
    generated = {TRANSPARENCY_FILENAME, output.with_suffix(".patch-log.json").name}
    comparison = directory_comparison(
        source_folder, output_folder, generated_names=generated
    )
    stock_exe = output_folder / source.name
    retained = stock_exe.is_file() and file_hash(stock_exe) == file_hash(source)
    data = dict(base_log)
    resolved_dependencies: list[dict[str, Any]] = []
    for feature in fun_patches:
        dependencies = feature.raw.get("dependencies", [])
        if isinstance(dependencies, str):
            dependencies = [dependencies]
        if dependencies:
            resolved_dependencies.append(
                {"feature": feature.id, "dependencies": list(dependencies)}
            )
    data.update(
        {
            "patcher_version": PATCHER_VERSION,
            "patcher_commit": _git_commit(root),
            "stock_executable": {
                "filename": source.name,
                "size": source.stat().st_size,
                "sha256": file_hash(source),
            },
            "modified_executable": {
                "filename": output.name,
                "size": output.stat().st_size,
                "sha256": file_hash(output),
            },
            "population_mode": base_log.get("patch_mode_name", base_log.get("patch_mode")),
            "selected_features": _feature_details(fun_patches),
            "auto_resolved_dependencies": resolved_dependencies,
            "auto_applied": {
                "population": base_log.get("patch_mode_name", base_log.get("patch_mode")),
                "safety": True,
            },
            "companion_results": companions,
            "source_output_comparison": comparison,
            "retained_untouched_stock_executable": retained,
            "pe_structural_difference": pe_difference(source, output),
            "save_handling": save_copy
            or {
                "status": "not_requested",
                "format_behavior": base_log.get("save_compatibility", "stock save layout"),
            },
            "validation": {
                "static_verification": [
                    "exact stock executable identity was verified",
                    "all guarded edits and output SHA-256 were verified",
                    "companion hashes and source/output tree were verified",
                    "PE layout and checksum were inspected",
                ],
                "runtime_player_confirmation": "pending; no game launch is performed by the patcher",
            },
            "transparency_log": {
                "path": TRANSPARENCY_FILENAME,
                "sha256": None,
            },
        }
    )
    if save_copy is not None:
        data["save_copy"] = save_copy
    # Keep the full edit record in JSON as well as in the human report.
    data["applied_edits"] = applied
    before_pe = data["pe_structural_difference"].get("before", {})
    after_pe = data["pe_structural_difference"].get("after", {})
    if before_pe.get("checksum") != after_pe.get("checksum"):
        before_checksum = int(str(before_pe.get("checksum", "0")), 0).to_bytes(4, "little")
        after_checksum = int(str(after_pe.get("checksum", "0")), 0).to_bytes(4, "little")
        applied.append(
            {
                "owner": "automatic:pe_checksum",
                "offset": f"0x{int(after_pe.get('checksum_file_offset', 0)):X}",
                "virtual_address": None,
                "before": before_checksum.hex().upper(),
                "after": after_checksum.hex().upper(),
                "purpose": "recompute the PE checksum after the verified byte edits",
            }
        )
    data["pe_structural_difference"]["relocated_pointers"] = [
        {
            "offset": edit.get("offset"),
            "virtual_address": edit.get("virtual_address"),
            "purpose": edit.get("purpose"),
        }
        for edit in applied
        if "relocat" in str(edit.get("purpose", "")).lower()
    ]
    return data


def render_transparency_text(
    data: dict[str, Any], *, timestamp: str | None = None, include_timestamp: bool = True
) -> str:
    """Render a stable report.  Pass a fixed timestamp for deterministic tests."""

    created = (
        (timestamp or data.get("created_utc") or datetime.now(timezone.utc).isoformat())
        if include_timestamp
        else "<omitted for deterministic comparison>"
    )
    stock = data["stock_executable"]
    modified = data["modified_executable"]
    comparison = data["source_output_comparison"]
    pe = data["pe_structural_difference"]
    lines = [
        "Virtual Villagers Fun Patcher — VVFP Transparency Log",
        f"Supported game/build: {data.get('game', 'unknown')}",
        f"Stock EXE: {stock['filename']} | size {stock['size']} | SHA-256 {stock['sha256']}",
        f"Modified EXE: {modified['filename']} | size {modified['size']} | SHA-256 {modified['sha256']}",
        f"Patcher version/commit: {data.get('patcher_version', PATCHER_VERSION)} / {data.get('patcher_commit', 'unavailable')}",
        f"Population mode: {data.get('population_mode', data.get('patch_mode', 'unknown'))}",
        f"Timestamp (UTC): {created}",
        "",
        "Applied selections",
        f"- Automatic population: {data.get('auto_applied', {}).get('population', 'none')}",
        f"- Automatic safety changes: {'yes' if data.get('auto_applied', {}).get('safety') else 'no'}",
        f"- Auto-resolved dependencies: {json.dumps(data.get('auto_resolved_dependencies', []), separators=(',', ':'))}",
    ]
    for feature in data.get("selected_features", []):
        deps = ", ".join(feature.get("dependencies", [])) or "none"
        lines.extend(
            [
                f"- Optional feature: {feature['name']} [{feature['id']}]",
                f"  Auto-resolved dependencies: {deps}",
                f"  Evidence: {feature.get('evidence_status', '')}",
                f"  Description: {feature.get('description', '')}",
                f"  Behavior: {' '.join(feature.get('behavior_changes', []))}",
                f"  Explicit non-changes/exclusions: {' '.join(feature.get('explicit_non_changes', [])) or 'none stated'}",
            ]
        )
        if feature.get("partial_failure_limit"):
            lines.append(f"  Partial-write disclosure: {feature['partial_failure_limit']}")
        if (
            "Cure all Villagers" in feature.get("description", "")
            and "Cured X villagers" not in feature.get("description", "")
        ):
            lines.append(
                "  Cure result: the player-visible completion message is exactly `Cured X villagers`, with X equal to the sickness fields cleared."
            )
        if (
            "village_wide_upgrades" in feature.get("id", "")
            and "Skipped over X villagers. Reason: Already 3 likes." not in feature.get("description", "")
        ):
            lines.append(
                "  Running skip result: `Skipped over X villagers. Reason: Already 3 likes.` with X equal to eligible full-Like records."
            )
    lines.extend(["", "Executable edits (grouped by owning feature)"])
    for edit in data.get("applied_edits", data.get("patches", [])):
        owner = edit.get("owner", "automatic")
        va = edit.get("virtual_address")
        va_text = f" | VA {va}" if va else ""
        lines.append(
            f"- [{owner}] file offset {edit.get('offset')}" 
            f"{va_text} | {len(bytes.fromhex(edit.get('before', '')))} bytes"
        )
        lines.append(f"  Before: {edit.get('before', '')}")
        lines.append(f"  After:  {edit.get('after', '')}")
        lines.append(f"  Purpose: {edit.get('purpose', '')}")
    after_sections = pe.get("after", {}).get("sections", [])
    section_characteristics = ", ".join(
        f"{item.get('name', '')}={item.get('characteristics', '')}"
        for item in after_sections
    ) or "none"
    executable_ranges = ", ".join(
        f"{item.get('name', '')} {item.get('start', '')}-{item.get('end', '')}"
        for item in pe.get("after", {}).get("executable_ranges", [])
    ) or "none"
    relocations = ", ".join(
        f"{item.get('offset', '')} ({item.get('purpose', '')})"
        for item in pe.get("relocated_pointers", [])
    ) or "none recorded"
    lines.extend(
        [
            "",
            "PE structural differences",
            f"- File size: {pe.get('before', {}).get('file_size')} -> {pe.get('after', {}).get('file_size')}",
            f"- SizeOfImage: {pe.get('before', {}).get('size_of_image')} -> {pe.get('after', {}).get('size_of_image')}",
            f"- Checksum: {pe.get('before', {}).get('checksum')} -> {pe.get('after', {}).get('checksum')}",
            f"- Section changes: {', '.join(item.get('name', '') for item in pe.get('section_changes', [])) or 'none'}",
            f"- Section characteristics: {section_characteristics}",
            f"- Executable ranges: {executable_ranges}",
            f"- Added/expanded sections: {', '.join(pe.get('added_or_expanded_sections', [])) or 'none'}",
            f"- Relocated pointers: {relocations}",
            "",
            "Source/output folder comparison (generated report files are listed below separately)",
        ]
    )
    for label in ("added", "modified", "removed"):
        entries = comparison.get(label, [])
        lines.append(f"- {label.title()} files: {len(entries)}")
        for entry in entries:
            if label == "modified":
                lines.append(
                    f"  {entry['output']['path']} | {entry['output']['size']} bytes | SHA-256 {entry['output']['sha256']}"
                )
            else:
                lines.append(
                    f"  {entry['path']} | {entry['size']} bytes | SHA-256 {entry['sha256']}"
                )
    lines.append(f"- Unchanged files: {comparison.get('unchanged_count', 0)}")
    lines.append(
        f"- No removals proven: {'yes' if comparison.get('no_removals_proven') else 'no'}"
    )
    lines.append(
        f"- Retained untouched stock EXE: {'yes' if data.get('retained_untouched_stock_executable') else 'no'} ({stock['filename']})"
    )
    archive = data.get("source_archive")
    if isinstance(archive, dict):
        lines.extend(
            [
                "- Authenticated stock source archive:",
                f"  {archive.get('filename', 'unknown')} | SHA-256 {archive.get('sha256', 'unknown')} | entries {archive.get('entries', 'unknown')}",
                f"  Runtime members: {archive.get('runtime_members', archive.get('entries', 'unknown'))} | outer evidence files: {archive.get('outer_evidence_files', 'not recorded')} | retained stock files: {archive.get('retained_stock_files', 'unknown')} | current package files: {archive.get('current_file_count', 'unknown')} | payload records: {archive.get('payload_records', 'unknown')}",
                "  Excluded obsolete source members: "
                + ", ".join(archive.get("excluded_source_members", [])),
            ]
        )
    prerequisite = data.get("full_mastery_prerequisite")
    if isinstance(prerequisite, dict):
        lines.extend(
            [
                "- Full Mastery prerequisite provenance:",
                f"  Source record: {prerequisite.get('source_record', 'unknown')} | status: {prerequisite.get('source_record_status', 'unknown')}",
                f"  Certified composition: {prerequisite.get('composition_status', 'unknown')}",
            ]
        )
    lines.append("- Companion additions:")
    for companion in data.get("companion_results", []):
        lines.append(
            f"  {_display_path(companion.get('path', ''), Path(data.get('output_path', '')).parent)} | SHA-256 {companion.get('sha256', '')}"
        )
    save = data.get("save_handling", {})
    lines.extend(
        [
            "",
            "Save handling",
            f"- Status: {save.get('status', 'not requested')}",
            f"- Source folder: {_display_path(save.get('source_folder', ''), None) if save.get('source_folder') else 'not supplied'}",
            f"- Destination folder: {_display_path(save.get('destination_folder', ''), None) if save.get('destination_folder') else 'not supplied'}",
            f"- Format behavior: {save.get('format_behavior', data.get('save_compatibility', 'stock save layout'))}",
            "- Stock modes preserve the vanilla save format; expanded modes use the documented guarded stock-layout import/conversion path.",
            "",
            "Validation status",
            "- Static verification performed:",
        ]
    )
    lines.extend(f"  - {item}" for item in data.get("validation", {}).get("static_verification", []))
    lines.append(
        f"- Runtime/player confirmation: {data.get('validation', {}).get('runtime_player_confirmation', 'pending; no game launch is performed by the patcher')}"
    )
    lines.append("")
    return "\n".join(lines)


def _atomic_write(path: Path, content: bytes) -> None:
    temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    try:
        with temporary.open("wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except Exception:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
        raise


def write_transparency_artifacts(
    *,
    base_log: dict[str, Any],
    source: Path,
    output: Path,
    source_folder: Path,
    output_folder: Path,
    fun_patches: Iterable[Any],
    companions: list[dict[str, Any]],
    applied: list[dict[str, Any]],
    save_copy: dict[str, Any] | None,
    root: Path,
    json_path: Path,
) -> tuple[Path, str]:
    """Verify and atomically write TXT then JSON metadata.

    The JSON records the TXT hash but deliberately does not hash itself.
    """

    data = build_transparency_data(
        base_log=base_log,
        source=source,
        output=output,
        source_folder=source_folder,
        output_folder=output_folder,
        fun_patches=fun_patches,
        companions=companions,
        applied=applied,
        save_copy=save_copy,
        root=root,
    )
    text = render_transparency_text(data)
    text_path = output.parent / TRANSPARENCY_FILENAME
    encoded = text.encode("utf-8")
    text_hash = hashlib.sha256(encoded).hexdigest().upper()
    data["transparency_log"]["sha256"] = text_hash
    data["transparency_log_path"] = TRANSPARENCY_FILENAME
    data["transparency_log_sha256"] = text_hash
    _atomic_write(text_path, encoded)
    try:
        if file_hash(text_path) != text_hash:
            raise RuntimeError("Transparency text-log hash verification failed")
        json_bytes = (json.dumps(data, indent=2) + "\n").encode("utf-8")
        _atomic_write(json_path, json_bytes)
    except Exception:
        try:
            text_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise
    return text_path, text_hash
