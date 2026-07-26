from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import shutil
import struct
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "data" / "builds.json"
EXPANDED_MANIFEST_PATH = ROOT / "data" / "expanded_256.json"
ORIGINS_FEATURE_PATH = ROOT / "data" / "vv1_origins_feature.json"
DEFAULT_PATCH_MODE = "collection_progression"
EXPANDED_PATCH_MODES = {
    "experimental_expanded_256",
    "experimental_expanded_256_progression",
}


class PatcherError(RuntimeError):
    pass


@dataclass(frozen=True)
class Record:
    raw: dict[str, Any]

    def __getattr__(self, name: str) -> Any:
        try:
            return self.raw[name]
        except KeyError as exc:
            raise AttributeError(name) from exc


Build = Record
PatchMode = Record
FunPatch = Record


def _manifest() -> dict[str, Any]:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8-sig"))


def load_builds() -> list[Build]:
    return [Build(item) for item in _manifest()["games"]]


def load_patch_modes() -> list[PatchMode]:
    return [PatchMode(item) for item in _manifest()["patch_modes"]]


def load_fun_patches() -> list[FunPatch]:
    items = list(_manifest().get("fun_patches", []))
    if ORIGINS_FEATURE_PATH.is_file():
        items.append(json.loads(ORIGINS_FEATURE_PATH.read_text(encoding="utf-8")))
    return [FunPatch(item) for item in items]


def _patch_bytes(patch: dict[str, Any], field: str) -> bytes:
    if field in patch:
        return bytes.fromhex(patch[field])
    if field == "before" and "before_fill" in patch:
        fill = bytes.fromhex(patch["before_fill"])
        length = int(patch["length"])
        if len(fill) != 1:
            raise PatcherError("Internal manifest error: before_fill must be one byte")
        return fill * length
    encoded_field = f"{field}_base64"
    if encoded_field in patch:
        return base64.b64decode(patch[encoded_field], validate=True)
    raise PatcherError(f"Internal manifest error: patch is missing {field}")


def _fun_patch_support(
    build: Build, fun_patches: list[FunPatch]
) -> list[dict[str, str]]:
    selected_ids = {patch.id for patch in fun_patches}
    patches: list[dict[str, str]] = []
    for support in _manifest().get("fun_patch_support", []):
        if support["game_id"] != build.id:
            continue
        if selected_ids.intersection(support["when_any"]):
            patches.extend(support["patches"])
    return patches


def _expanded_patches(build: Build, variant: dict[str, Any]) -> list[dict[str, str]]:
    if not variant.get("expanded_records", False):
        return []
    payload = json.loads(EXPANDED_MANIFEST_PATH.read_text(encoding="utf-8"))
    try:
        game = payload["games"][build.id]
    except KeyError as exc:
        raise PatcherError(
            f"Experimental 256 data is missing for {build.title}."
        ) from exc
    if game["source_sha256"] != build.sha256:
        raise PatcherError(
            f"Experimental 256 data does not match {build.title}'s supported build."
        )
    return game["patches"]


def _safety_patches(build: Build, patch_mode: str) -> list[dict[str, str]]:
    if (
        patch_mode
        not in {
            "experimental_expanded_256",
            "experimental_expanded_256_progression",
        }
        or build.id in {"vv1", "vv2"}
    ):
        return build.safety_patches
    patches = []
    for source in build.safety_patches:
        patch = dict(source)
        patch["after"] = patch["after"].replace("96000000", "00010000")
        patch["purpose"] = patch["purpose"].replace("150-slot", "256-slot")
        patches.append(patch)
    return patches


def get_fun_patch(patch_id: str) -> FunPatch:
    for patch in load_fun_patches():
        if patch.id == patch_id:
            return patch
    raise PatcherError(f"Unknown fun patch: {patch_id}")


def _selected_fun_patches(
    build: Build, patch_ids: tuple[str, ...] | list[str]
) -> list[FunPatch]:
    selected: list[FunPatch] = []
    seen: set[str] = set()
    for patch_id in patch_ids:
        if patch_id in seen:
            continue
        patch = get_fun_patch(patch_id)
        if patch.game_id != build.id:
            raise PatcherError(
                f"{patch.name} is only available for {patch.game_id.upper()}."
            )
        seen.add(patch_id)
        selected.append(patch)
    return selected


def _output_name(build: Build, patch_mode: str, fun_patches: list[FunPatch]) -> str:
    get_patch_variant(build, patch_mode)
    suffix = "Modded 256" if patch_mode in EXPANDED_PATCH_MODES else "Modded"
    return f"{build.title} - {suffix}.exe"


def output_folder_for(
    source: Path,
    build: Build,
    patch_mode: str,
    fun_patches: list[FunPatch],
    output_root: Path | None = None,
) -> Path:
    parent = (
        Path(output_root).expanduser().resolve()
        if output_root is not None
        else source.resolve().parent.parent
    )
    suffix = "Modded 256" if patch_mode in EXPANDED_PATCH_MODES else "Modded"
    return parent / f"{build.title} - {suffix}"


def _ldw_save_roots(save_root: Path | None = None) -> list[Path]:
    candidates: list[Path] = []
    if save_root is not None:
        candidates.append(Path(save_root).expanduser())
    override = os.environ.get("VVFP_LDW_SAVE_ROOT")
    if override:
        candidates.append(Path(override).expanduser())
    for variable in ("OneDrive", "OneDriveConsumer"):
        value = os.environ.get(variable)
        if value:
            candidates.append(Path(value) / "Documents" / "LDW")
    candidates.extend(
        (
            Path.home() / "OneDrive" / "Documents" / "LDW",
            Path.home() / "Documents" / "LDW",
        )
    )
    unique: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = os.path.normcase(str(candidate.resolve()))
        if key not in seen:
            seen.add(key)
            unique.append(candidate.resolve())
    return unique


def vanilla_save_folder_for(
    build: Build, save_root: Path | None = None
) -> Path | None:
    slot_zero = f"{build.title}0.ldw"
    for root in _ldw_save_roots(save_root):
        folder = root / build.title
        if (folder / slot_zero).is_file():
            return folder
    return None


def modded_save_folder_for(
    build: Build, patch_mode: str, save_root: Path | None = None
) -> Path | None:
    source = vanilla_save_folder_for(build, save_root)
    if source is None:
        return None
    suffix = "Modded 256" if patch_mode in EXPANDED_PATCH_MODES else "Modded"
    return source.parent / f"{build.title} - {suffix}"


def copy_vanilla_saves(
    build: Build,
    patch_mode: str,
    *,
    replace_existing: bool = False,
    save_root: Path | None = None,
) -> dict[str, Any]:
    if patch_mode not in EXPANDED_PATCH_MODES:
        return {"status": "not_requested", "copied_files": 0}
    source = vanilla_save_folder_for(build, save_root)
    if source is None:
        return {"status": "vanilla_save_folder_not_found", "copied_files": 0}
    destination = source.parent / f"{build.title} - Modded 256"
    source_files = sorted(
        path
        for path in source.glob(f"{build.title}*.ldw")
        if path.is_file()
    )
    slot_zero_name = f"{build.title}0.ldw"
    if not any(path.name == slot_zero_name for path in source_files):
        raise PatcherError(
            f"Required vanilla slot-zero file is missing: {source / slot_zero_name}"
        )
    existing = (
        sorted(
            path
            for path in destination.glob(f"{build.title}*.ldw")
            if path.is_file()
        )
        if destination.is_dir()
        else []
    )
    if existing and not replace_existing:
        return {
            "status": "existing_modded_saves_preserved",
            "source_folder": str(source),
            "destination_folder": str(destination),
            "copied_files": 0,
            "slot_zero": slot_zero_name,
        }
    destination.mkdir(parents=True, exist_ok=True)
    if replace_existing:
        for path in existing:
            path.unlink()
    copied: list[dict[str, Any]] = []
    for source_path in source_files:
        destination_path = destination / source_path.name
        shutil.copy2(source_path, destination_path)
        source_hash = sha256(source_path)
        if sha256(destination_path) != source_hash:
            raise PatcherError(
                f"Save copy verification failed: {destination_path}"
            )
        copied.append(
            {
                "name": source_path.name,
                "size": source_path.stat().st_size,
                "sha256": source_hash,
            }
        )
    return {
        "status": "vanilla_saves_copied",
        "source_folder": str(source),
        "destination_folder": str(destination),
        "copied_files": len(copied),
        "slot_zero": slot_zero_name,
        "files": copied,
    }


def get_patch_mode(patch_mode: str) -> PatchMode:
    for mode in load_patch_modes():
        if mode.id == patch_mode:
            return mode
    raise PatcherError(f"Unknown patch mode: {patch_mode}")


def get_patch_variant(build: Build, patch_mode: str) -> dict[str, Any]:
    get_patch_mode(patch_mode)
    try:
        return build.variants[patch_mode]
    except KeyError as exc:
        raise PatcherError(f"{build.title} does not define patch mode {patch_mode}") from exc


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def identify(path: Path) -> Build:
    path = path.resolve()
    if not path.is_file():
        raise PatcherError(f"Game executable not found: {path}")
    size = path.stat().st_size
    candidates = [build for build in load_builds() if build.size == size]
    if not candidates:
        raise PatcherError(f"Unsupported executable size: {size:,} bytes")
    digest = sha256(path)
    for build in candidates:
        if digest == build.sha256:
            return build
    raise PatcherError(
        "This executable is not one of the five exact supported stock builds. "
        + f"SHA-256: {digest}"
    )


def _resolve_expected_source(selected: Path, expected: Build) -> Path:
    selected = Path(selected).resolve()
    if selected.is_dir():
        source = selected / expected.input_name
        if not source.is_file():
            raise PatcherError(
                f"{expected.title} folder does not contain {expected.input_name}: {selected}"
            )
        return source.resolve()
    return selected


def validate_all_sources(sources: dict[str, Path]) -> list[tuple[Build, Path]]:
    builds = load_builds()
    missing = [
        build.title
        for build in builds
        if build.id not in sources or not str(sources[build.id]).strip()
    ]
    if missing:
        raise PatcherError(
            "Choose all five original game folders. Missing: " + ", ".join(missing)
        )
    resolved: list[tuple[Build, Path]] = []
    used_paths: set[Path] = set()
    for expected in builds:
        source = _resolve_expected_source(Path(sources[expected.id]), expected)
        actual = identify(source)
        if actual.id != expected.id:
            raise PatcherError(
                f"Wrong game selected for {expected.title}: identified {actual.title}"
            )
        if source in used_paths:
            raise PatcherError(f"The same executable was selected more than once: {source}")
        used_paths.add(source)
        resolved.append((expected, source))
    return resolved


def _pe_checksum_layout(data: bytearray) -> tuple[int, int]:
    if data[:2] != b"MZ":
        raise PatcherError("Input is not a Windows PE executable (missing MZ header).")
    pe_offset = struct.unpack_from("<I", data, 0x3C)[0]
    if data[pe_offset : pe_offset + 4] != b"PE\0\0":
        raise PatcherError("Input is not a Windows PE executable (missing PE header).")
    optional_offset = pe_offset + 24
    magic = struct.unpack_from("<H", data, optional_offset)[0]
    if magic not in (0x10B, 0x20B):
        raise PatcherError(f"Unsupported PE optional-header magic: 0x{magic:04X}")
    return optional_offset + 64, len(data)


def pe_checksum(data: bytearray) -> int:
    checksum_offset, length = _pe_checksum_layout(data)
    struct.pack_into("<I", data, checksum_offset, 0)
    total = 0
    padded = data + (b"\0" if len(data) % 2 else b"")
    for offset in range(0, len(padded), 2):
        total += padded[offset] | (padded[offset + 1] << 8)
        total = (total & 0xFFFF) + (total >> 16)
    total = (total & 0xFFFF) + (total >> 16)
    return ((total & 0xFFFF) + length) & 0xFFFFFFFF


def render_patched_bytes(
    source: Path,
    build: Build,
    patch_mode: str = DEFAULT_PATCH_MODE,
    fun_patch_ids: tuple[str, ...] | list[str] = (),
) -> tuple[bytearray, list[dict[str, str]]]:
    variant = get_patch_variant(build, patch_mode)
    fun_patches = _selected_fun_patches(build, fun_patch_ids)
    data = bytearray(source.read_bytes())
    applied: list[dict[str, str]] = []
    fun_bytes = [patch for feature in fun_patches for patch in feature.patches]
    for patch in [
        *_expanded_patches(build, variant),
        *_safety_patches(build, patch_mode),
        *variant["patches"],
        *_fun_patch_support(build, fun_patches),
        *fun_bytes,
    ]:
        offset = int(patch["offset"], 0)
        before = _patch_bytes(patch, "before")
        after = _patch_bytes(patch, "after")
        if len(before) != len(after):
            raise PatcherError(
                f"Internal manifest error at {patch['offset']}: length changed"
            )
        actual = bytes(data[offset : offset + len(before)])
        if actual != before:
            raise PatcherError(
                f"Byte guard failed at {patch['offset']}: "
                f"expected {before.hex().upper()}, found {actual.hex().upper()}"
            )
        data[offset : offset + len(after)] = after
        applied.append(
            {
                "offset": patch["offset"],
                "before": before.hex().upper(),
                "after": after.hex().upper(),
                "purpose": patch["purpose"],
            }
        )
    checksum_offset, _ = _pe_checksum_layout(data)
    checksum = pe_checksum(data)
    struct.pack_into("<I", data, checksum_offset, checksum)
    return data, applied


def _result(
    build: Build,
    source: Path,
    patch_mode: str,
    patched: bytearray,
    applied: list[dict[str, str]],
    fun_patches: list[FunPatch],
    output_root: Path | None = None,
) -> dict[str, Any]:
    mode = get_patch_mode(patch_mode)
    variant = get_patch_variant(build, patch_mode)
    villager_slots = variant.get("villager_slots", build.villager_slots)
    absolute_maximum = variant.get("absolute_maximum", build.absolute_maximum)
    output_name = _output_name(build, patch_mode, fun_patches)
    output_folder = output_folder_for(
        source, build, patch_mode, fun_patches, output_root
    )
    return {
        "game": build.title,
        "source": str(source.resolve()),
        "patch_mode": mode.id,
        "patch_mode_name": mode.name,
        "output_name": output_name,
        "output_folder": str(output_folder),
        "output_path": str(output_folder / output_name),
        "fun_patches": [patch.id for patch in fun_patches],
        "fun_patch_names": [patch.name for patch in fun_patches],
        "absolute_maximum": absolute_maximum,
        "villager_slots": villager_slots,
        "experimental_expanded_records": variant.get("expanded_records", False),
        "save_compatibility": (
            "expanded experimental layout with guarded stock-layout import in the modified executable's separate save folder"
            if variant.get("expanded_records", False)
            else "stock save layout"
        ),
        "multiple_birth_saturation": "multiples are reduced only when required to fit the remaining villager slots",
        "island_event_capacity": "population-adding Island Events are blocked or reduced only as required to fit the remaining physical villager slots",
        "bonuses_affect_maximum": variant["bonuses_affect_maximum"],
        "patches": applied,
        "result_sha256": hashlib.sha256(patched).hexdigest().upper(),
    }


def dry_run(
    source: Path,
    patch_mode: str = DEFAULT_PATCH_MODE,
    fun_patch_ids: tuple[str, ...] | list[str] = (),
    output_root: Path | None = None,
) -> dict[str, Any]:
    build = identify(source)
    fun_patches = _selected_fun_patches(build, fun_patch_ids)
    patched, applied = render_patched_bytes(source, build, patch_mode, fun_patch_ids)
    return _result(
        build, source, patch_mode, patched, applied, fun_patches, output_root
    )


def dry_run_all(
    sources: dict[str, Path],
    patch_mode: str = DEFAULT_PATCH_MODE,
    fun_patch_ids: tuple[str, ...] | list[str] = (),
    output_root: Path | None = None,
) -> list[dict[str, Any]]:
    validated = validate_all_sources(sources)
    results = []
    for build, source in validated:
        selected_ids = [
            patch_id
            for patch_id in fun_patch_ids
            if get_fun_patch(patch_id).game_id == build.id
        ]
        fun_patches = _selected_fun_patches(build, selected_ids)
        patched, applied = render_patched_bytes(source, build, patch_mode, selected_ids)
        results.append(
            _result(
                build,
                source,
                patch_mode,
                patched,
                applied,
                fun_patches,
                output_root,
            )
        )
    return results


def _log_data(
    build: Build,
    source: Path,
    output: Path,
    patch_mode: str,
    output_hash: str,
    applied: list[dict[str, str]],
    fun_patches: list[FunPatch],
) -> dict[str, Any]:
    mode = get_patch_mode(patch_mode)
    variant = get_patch_variant(build, patch_mode)
    villager_slots = variant.get("villager_slots", build.villager_slots)
    absolute_maximum = variant.get("absolute_maximum", build.absolute_maximum)
    return {
        "patcher": "Virtual Villagers Fun Patcher",
        "patch": mode.name,
        "patch_mode": mode.id,
        "fun_patches": [patch.id for patch in fun_patches],
        "fun_patch_names": [patch.name for patch in fun_patches],
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "game": build.title,
        "absolute_maximum": absolute_maximum,
        "villager_slots": villager_slots,
        "experimental_expanded_records": variant.get("expanded_records", False),
        "save_compatibility": (
            "expanded experimental layout with guarded stock-layout import in the modified executable's separate save folder"
            if variant.get("expanded_records", False)
            else "stock save layout"
        ),
        "multiple_birth_saturation": "multiples are reduced only when required to fit the remaining villager slots",
        "island_event_capacity": "population-adding Island Events are blocked or reduced only as required to fit the remaining physical villager slots",
        "bonuses_affect_maximum": variant["bonuses_affect_maximum"],
        "source_path": str(source.resolve()),
        "source_sha256": build.sha256,
        "output_path": str(output),
        "output_sha256": output_hash,
        "patches": applied,
    }


def _copy_game_folder_direct(
    source_folder: Path,
    destination: Path,
    overwrite: bool,
    output_root: Path | None = None,
) -> None:
    source_resolved = source_folder.resolve()
    destination_resolved = destination.resolve()
    expected_parent = (
        Path(output_root).expanduser().resolve()
        if output_root is not None
        else source_resolved.parent
    )
    if destination_resolved.parent != expected_parent:
        raise PatcherError(
            "Internal safety check failed: output is outside the selected output folder"
        )
    if destination_resolved == source_resolved:
        raise PatcherError(
            "Internal safety check failed: output would replace the original folder"
        )
    try:
        expected_parent.relative_to(source_resolved)
    except ValueError:
        pass
    else:
        raise PatcherError(
            "Internal safety check failed: output folder cannot be inside the original game folder"
        )
    existed = destination.exists()
    if existed and not overwrite:
        raise PatcherError(f"Modified game folder already exists: {destination}")
    try:
        expected_parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(
            source_folder,
            destination,
            copy_function=shutil.copy2,
            dirs_exist_ok=overwrite,
        )
        for source_path in source_folder.rglob("*"):
            if not source_path.is_file():
                continue
            copied_path = destination / source_path.relative_to(source_folder)
            if (
                not copied_path.is_file()
                or copied_path.stat().st_size != source_path.stat().st_size
                or sha256(copied_path) != sha256(source_path)
            ):
                raise PatcherError(
                    "Verification failed while copying the complete game folder: "
                    f"{source_folder}"
                )
    except Exception:
        if not existed and destination.exists():
            shutil.rmtree(destination, ignore_errors=True)
        raise


def _copy_companion_files(
    output_folder: Path, fun_patches: list[FunPatch]
) -> list[dict[str, str]]:
    copied: list[dict[str, str]] = []
    root = ROOT.resolve()
    for feature in fun_patches:
        for item in feature.raw.get("companion_files", []):
            source = (ROOT / item["source"]).resolve()
            try:
                source.relative_to(root)
            except ValueError as exc:
                raise PatcherError(
                    f"Companion file escapes the patcher folder: {source}"
                ) from exc
            destination_name = Path(item["destination"])
            if destination_name.name != str(destination_name):
                raise PatcherError(
                    f"Companion destination must be a filename: {destination_name}"
                )
            if not source.is_file():
                raise PatcherError(f"Required companion file is missing: {source}")
            expected_hash = item["sha256"].upper()
            if sha256(source) != expected_hash:
                raise PatcherError(f"Companion file hash mismatch: {source.name}")
            destination = output_folder / destination_name
            shutil.copy2(source, destination)
            if sha256(destination) != expected_hash:
                raise PatcherError(
                    f"Companion file copy verification failed: {destination}"
                )
            copied.append(
                {
                    "feature": feature.id,
                    "path": str(destination),
                    "sha256": expected_hash,
                }
            )
    return copied


def apply_patch(
    source: Path,
    patch_mode: str = DEFAULT_PATCH_MODE,
    overwrite: bool = False,
    fun_patch_ids: tuple[str, ...] | list[str] = (),
    output_root: Path | None = None,
    copy_saves: bool = False,
    replace_modded_saves: bool = False,
    save_root: Path | None = None,
) -> tuple[Path, Path]:
    source = source.resolve()
    build = identify(source)
    fun_patches = _selected_fun_patches(build, fun_patch_ids)
    output_name = _output_name(build, patch_mode, fun_patches)
    output_folder = output_folder_for(
        source, build, patch_mode, fun_patches, output_root
    )
    output = output_folder / output_name
    if output_folder.exists() and not overwrite:
        raise PatcherError(f"Modified game folder already exists: {output_folder}")
    patched, applied = render_patched_bytes(source, build, patch_mode, fun_patch_ids)
    _copy_game_folder_direct(source.parent, output_folder, overwrite, output_root)
    companions = _copy_companion_files(output_folder, fun_patches)
    log_path = output.with_suffix(".patch-log.json")
    try:
        with output.open("wb") as handle:
            handle.write(patched)
            handle.flush()
            os.fsync(handle.fileno())
        if output.stat().st_size != source.stat().st_size:
            raise PatcherError("Verification failed: patched file size changed")
        output_hash = sha256(output)
        expected_hash = hashlib.sha256(patched).hexdigest().upper()
        if output_hash != expected_hash:
            raise PatcherError("Verification failed: output hash mismatch")
        log_data = _log_data(
            build, source, output, patch_mode, output_hash, applied, fun_patches
        )
        log_data["companion_files"] = companions
        if copy_saves:
            log_data["save_copy"] = copy_vanilla_saves(
                build,
                patch_mode,
                replace_existing=replace_modded_saves,
                save_root=save_root,
            )
        log_path.write_text(
            json.dumps(log_data, indent=2) + "\n", encoding="utf-8"
        )
    except Exception:
        raise
    return output, log_path


def apply_all(
    sources: dict[str, Path],
    patch_mode: str = DEFAULT_PATCH_MODE,
    overwrite: bool = False,
    fun_patch_ids: tuple[str, ...] | list[str] = (),
    output_root: Path | None = None,
    copy_saves: bool = False,
    replace_modded_saves: bool = False,
    save_root: Path | None = None,
) -> list[tuple[Path, Path]]:
    validated = validate_all_sources(sources)
    plans: list[
        tuple[Build, Path, bytearray, list[dict[str, str]], Path, Path]
    ] = []
    selected_by_game: dict[str, list[FunPatch]] = {}
    for patch_id in fun_patch_ids:
        patch = get_fun_patch(patch_id)
        selected_by_game.setdefault(patch.game_id, []).append(patch)
    for build, source in validated:
        fun_patches = selected_by_game.get(build.id, [])
        selected_ids = [patch.id for patch in fun_patches]
        patched, applied = render_patched_bytes(source, build, patch_mode, selected_ids)
        output_folder = output_folder_for(
            source, build, patch_mode, fun_patches, output_root
        )
        plans.append(
            (
                build,
                source,
                patched,
                applied,
                output_folder,
                output_folder / _output_name(build, patch_mode, fun_patches),
            )
        )
    existing = [folder for _, _, _, _, folder, _ in plans if folder.exists()]
    if existing and not overwrite:
        raise PatcherError(
            "Bulk modified game folder already exists; no files were written:\n"
            + "\n".join(str(path) for path in existing)
        )
    results: list[tuple[Path, Path]] = []
    for build, source, patched, applied, output_folder, output in plans:
        _copy_game_folder_direct(source.parent, output_folder, overwrite, output_root)
        companions = _copy_companion_files(
            output_folder, selected_by_game.get(build.id, [])
        )
        with output.open("wb") as handle:
            handle.write(patched)
            handle.flush()
            os.fsync(handle.fileno())
        if output.stat().st_size != source.stat().st_size:
            raise PatcherError(f"Bulk verification failed: {build.title} size changed")
        output_hash = sha256(output)
        expected_hash = hashlib.sha256(patched).hexdigest().upper()
        if output_hash != expected_hash:
            raise PatcherError(f"Bulk verification failed: {build.title} hash mismatch")
        log_path = output.with_suffix(".patch-log.json")
        log_data = _log_data(
            build,
            source,
            output,
            patch_mode,
            output_hash,
            applied,
            selected_by_game.get(build.id, []),
        )
        log_data["companion_files"] = companions
        if copy_saves:
            log_data["save_copy"] = copy_vanilla_saves(
                build,
                patch_mode,
                replace_existing=replace_modded_saves,
                save_root=save_root,
            )
        log_path.write_text(
            json.dumps(log_data, indent=2) + "\n", encoding="utf-8"
        )
        results.append((output, log_path))
    return results


def _add_patch_mode_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--patch-mode",
        choices=[mode.id for mode in load_patch_modes()],
        default=DEFAULT_PATCH_MODE,
    )


def _add_fun_patch_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--fun-patch",
        action="append",
        choices=[patch.id for patch in load_fun_patches()],
        default=[],
        help="optional game-specific patch; may be supplied more than once",
    )


def _add_output_root_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--output-root",
        type=Path,
        default=None,
        help=(
            "parent folder for short '(Game name) - Modded' or "
            "'(Game name) - Modded 256' outputs; "
            "defaults to the original game's parent folder"
        ),
    )


def _add_save_copy_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--copy-vanilla-saves",
        action="store_true",
        help=(
            "copy the exact vanilla numbered saves and required slot-zero file "
            "into the separate Modded 256 save folder"
        ),
    )
    parser.add_argument(
        "--replace-modded-saves",
        action="store_true",
        help=(
            "replace existing Modded 256 .ldw files with verified vanilla "
            "copies; requires --copy-vanilla-saves"
        ),
    )


def _add_all_source_args(parser: argparse.ArgumentParser) -> None:
    for build in load_builds():
        parser.add_argument(
            f"--{build.id}",
            required=True,
            type=Path,
            help=f"folder containing {build.input_name}, or the EXE itself",
        )


def _all_sources_from_args(args: argparse.Namespace) -> dict[str, Path]:
    return {build.id: getattr(args, build.id) for build in load_builds()}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="Virtual Villagers Fun Patcher")
    sub = parser.add_subparsers(dest="command", required=True)

    identify_cmd = sub.add_parser("identify", help="identify an exact supported stock EXE")
    identify_cmd.add_argument("exe", type=Path)

    dry_cmd = sub.add_parser("dry-run", help="verify and preview without writing output")
    dry_cmd.add_argument("exe", type=Path)
    _add_patch_mode_arg(dry_cmd)
    _add_fun_patch_args(dry_cmd)
    _add_output_root_arg(dry_cmd)

    apply_cmd = sub.add_parser("apply", help="create one modified copy")
    apply_cmd.add_argument("exe", type=Path)
    apply_cmd.add_argument("--overwrite", action="store_true")
    _add_patch_mode_arg(apply_cmd)
    _add_fun_patch_args(apply_cmd)
    _add_output_root_arg(apply_cmd)
    _add_save_copy_args(apply_cmd)

    dry_all_cmd = sub.add_parser(
        "dry-run-all", help="verify all five games without writing output"
    )
    _add_all_source_args(dry_all_cmd)
    _add_patch_mode_arg(dry_all_cmd)
    _add_fun_patch_args(dry_all_cmd)
    _add_output_root_arg(dry_all_cmd)

    apply_all_cmd = sub.add_parser(
        "apply-all", help="create all five modified copies together"
    )
    apply_all_cmd.add_argument("--overwrite", action="store_true")
    _add_all_source_args(apply_all_cmd)
    _add_patch_mode_arg(apply_all_cmd)
    _add_fun_patch_args(apply_all_cmd)
    _add_output_root_arg(apply_all_cmd)
    _add_save_copy_args(apply_all_cmd)
    return parser


def main() -> int:
    args = _parser().parse_args()
    try:
        if (
            getattr(args, "replace_modded_saves", False)
            and not getattr(args, "copy_vanilla_saves", False)
        ):
            raise PatcherError(
                "--replace-modded-saves requires --copy-vanilla-saves"
            )
        if args.command == "identify":
            print(json.dumps(identify(args.exe).raw, indent=2))
        elif args.command == "dry-run":
            print(
                json.dumps(
                    dry_run(
                        args.exe,
                        args.patch_mode,
                        args.fun_patch,
                        output_root=args.output_root,
                    ),
                    indent=2,
                )
            )
        elif args.command == "apply":
            output, log = apply_patch(
                args.exe,
                args.patch_mode,
                args.overwrite,
                args.fun_patch,
                output_root=args.output_root,
                copy_saves=args.copy_vanilla_saves,
                replace_modded_saves=args.replace_modded_saves,
            )
            print(f"Created: {output}")
            print(f"Log: {log}")
        elif args.command == "dry-run-all":
            print(
                json.dumps(
                    dry_run_all(
                        _all_sources_from_args(args),
                        args.patch_mode,
                        args.fun_patch,
                        output_root=args.output_root,
                    ),
                    indent=2,
                )
            )
        else:
            results = apply_all(
                _all_sources_from_args(args),
                args.patch_mode,
                args.overwrite,
                args.fun_patch,
                output_root=args.output_root,
                copy_saves=args.copy_vanilla_saves,
                replace_modded_saves=args.replace_modded_saves,
            )
            for output, log in results:
                print(f"Created: {output}")
                print(f"Log: {log}")
        return 0
    except PatcherError as exc:
        print(f"Error: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
