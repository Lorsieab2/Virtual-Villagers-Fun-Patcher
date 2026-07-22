from __future__ import annotations

import argparse
import hashlib
import json
import os
import struct
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "data" / "builds.json"
DEFAULT_PATCH_MODE = "collection_progression"


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
    return [FunPatch(item) for item in _manifest().get("fun_patches", [])]


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
    base = get_patch_variant(build, patch_mode)["output_name"]
    if not fun_patches:
        return base
    stem = base[:-4] if base.casefold().endswith(".exe") else base
    tags = " + ".join(patch.output_tag for patch in fun_patches)
    return f"{stem} + {tags}.exe"


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
        *build.raw.get("safety_patches", []),
        *variant["patches"],
        *fun_bytes,
    ]:
        offset = int(patch["offset"], 0)
        before = bytes.fromhex(patch["before"])
        after = bytes.fromhex(patch["after"])
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
) -> dict[str, Any]:
    mode = get_patch_mode(patch_mode)
    variant = get_patch_variant(build, patch_mode)
    return {
        "game": build.title,
        "source": str(source.resolve()),
        "patch_mode": mode.id,
        "patch_mode_name": mode.name,
        "output_name": _output_name(build, patch_mode, fun_patches),
        "fun_patches": [patch.id for patch in fun_patches],
        "fun_patch_names": [patch.name for patch in fun_patches],
        "absolute_maximum": build.absolute_maximum,
        "villager_slots": build.villager_slots,
        "multiple_birth_saturation": "multiples are reduced only when required to fit the remaining villager slots",
        "bonuses_affect_maximum": variant["bonuses_affect_maximum"],
        "patches": applied,
        "result_sha256": hashlib.sha256(patched).hexdigest().upper(),
    }


def dry_run(
    source: Path,
    patch_mode: str = DEFAULT_PATCH_MODE,
    fun_patch_ids: tuple[str, ...] | list[str] = (),
) -> dict[str, Any]:
    build = identify(source)
    fun_patches = _selected_fun_patches(build, fun_patch_ids)
    patched, applied = render_patched_bytes(source, build, patch_mode, fun_patch_ids)
    return _result(build, source, patch_mode, patched, applied, fun_patches)


def dry_run_all(
    sources: dict[str, Path],
    patch_mode: str = DEFAULT_PATCH_MODE,
    fun_patch_ids: tuple[str, ...] | list[str] = (),
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
        results.append(_result(build, source, patch_mode, patched, applied, fun_patches))
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
    return {
        "patcher": "Virtual Villagers Fun Patcher",
        "patch": mode.name,
        "patch_mode": mode.id,
        "fun_patches": [patch.id for patch in fun_patches],
        "fun_patch_names": [patch.name for patch in fun_patches],
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "game": build.title,
        "absolute_maximum": build.absolute_maximum,
        "villager_slots": build.villager_slots,
        "multiple_birth_saturation": "multiples are reduced only when required to fit the remaining villager slots",
        "bonuses_affect_maximum": variant["bonuses_affect_maximum"],
        "source_path": str(source.resolve()),
        "source_sha256": build.sha256,
        "output_path": str(output),
        "output_sha256": output_hash,
        "patches": applied,
    }


def apply_patch(
    source: Path,
    patch_mode: str = DEFAULT_PATCH_MODE,
    overwrite: bool = False,
    fun_patch_ids: tuple[str, ...] | list[str] = (),
) -> tuple[Path, Path]:
    source = source.resolve()
    build = identify(source)
    fun_patches = _selected_fun_patches(build, fun_patch_ids)
    output = source.parent / _output_name(build, patch_mode, fun_patches)
    if output.exists() and not overwrite:
        raise PatcherError(f"Output already exists: {output}")
    patched, applied = render_patched_bytes(source, build, patch_mode, fun_patch_ids)
    fd, temp_name = tempfile.mkstemp(prefix="vvfp-", suffix=".tmp", dir=source.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(patched)
            handle.flush()
            os.fsync(handle.fileno())
        temp_path = Path(temp_name)
        if temp_path.stat().st_size != source.stat().st_size:
            raise PatcherError("Verification failed: patched file size changed")
        os.replace(temp_path, output)
    except Exception:
        Path(temp_name).unlink(missing_ok=True)
        raise
    output_hash = sha256(output)
    expected_hash = hashlib.sha256(patched).hexdigest().upper()
    if output_hash != expected_hash:
        output.unlink(missing_ok=True)
        raise PatcherError("Verification failed: output hash does not match generated bytes")
    log_path = output.with_suffix(".patch-log.json")
    log_path.write_text(
        json.dumps(
            _log_data(
                build, source, output, patch_mode, output_hash, applied, fun_patches
            ),
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return output, log_path


def apply_all(
    sources: dict[str, Path],
    patch_mode: str = DEFAULT_PATCH_MODE,
    overwrite: bool = False,
    fun_patch_ids: tuple[str, ...] | list[str] = (),
) -> list[tuple[Path, Path]]:
    validated = validate_all_sources(sources)
    plans: list[
        tuple[Build, Path, bytearray, list[dict[str, str]], Path]
    ] = []
    selected_by_game: dict[str, list[FunPatch]] = {}
    for patch_id in fun_patch_ids:
        patch = get_fun_patch(patch_id)
        selected_by_game.setdefault(patch.game_id, []).append(patch)
    for build, source in validated:
        fun_patches = selected_by_game.get(build.id, [])
        selected_ids = [patch.id for patch in fun_patches]
        patched, applied = render_patched_bytes(source, build, patch_mode, selected_ids)
        plans.append(
            (
                build,
                source,
                patched,
                applied,
                source.parent / _output_name(build, patch_mode, fun_patches),
            )
        )
    existing = [output for _, _, _, _, output in plans if output.exists()]
    if existing and not overwrite:
        raise PatcherError(
            "Bulk output already exists; no files were written:\n"
            + "\n".join(str(path) for path in existing)
        )
    staged: list[
        tuple[
            Path,
            tuple[Build, Path, bytearray, list[dict[str, str]], Path],
        ]
    ] = []
    try:
        for plan in plans:
            build, source, patched, _, output = plan
            fd, temp_name = tempfile.mkstemp(
                prefix=f"vvfp-{build.id}-", suffix=".tmp", dir=output.parent
            )
            temp_path = Path(temp_name)
            staged.append((temp_path, plan))
            with os.fdopen(fd, "wb") as handle:
                handle.write(patched)
                handle.flush()
                os.fsync(handle.fileno())
            if temp_path.stat().st_size != source.stat().st_size:
                raise PatcherError(
                    f"Verification failed before bulk commit: {build.title} size changed"
                )
            if sha256(temp_path) != hashlib.sha256(patched).hexdigest().upper():
                raise PatcherError(
                    f"Verification failed before bulk commit: {build.title} hash mismatch"
                )
        for temp_path, (_, _, _, _, output) in staged:
            os.replace(temp_path, output)
    except Exception:
        for temp_path, _ in staged:
            temp_path.unlink(missing_ok=True)
        raise
    results: list[tuple[Path, Path]] = []
    for build, source, patched, applied, output in plans:
        output_hash = sha256(output)
        expected_hash = hashlib.sha256(patched).hexdigest().upper()
        if output_hash != expected_hash:
            raise PatcherError(f"Bulk verification failed after commit: {build.title}")
        log_path = output.with_suffix(".patch-log.json")
        log_path.write_text(
            json.dumps(
                _log_data(
                    build,
                    source,
                    output,
                    patch_mode,
                    output_hash,
                    applied,
                    selected_by_game.get(build.id, []),
                ),
                indent=2,
            )
            + "\n",
            encoding="utf-8",
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

    apply_cmd = sub.add_parser("apply", help="create one modified copy")
    apply_cmd.add_argument("exe", type=Path)
    apply_cmd.add_argument("--overwrite", action="store_true")
    _add_patch_mode_arg(apply_cmd)
    _add_fun_patch_args(apply_cmd)

    dry_all_cmd = sub.add_parser(
        "dry-run-all", help="verify all five games without writing output"
    )
    _add_all_source_args(dry_all_cmd)
    _add_patch_mode_arg(dry_all_cmd)
    _add_fun_patch_args(dry_all_cmd)

    apply_all_cmd = sub.add_parser(
        "apply-all", help="create all five modified copies together"
    )
    apply_all_cmd.add_argument("--overwrite", action="store_true")
    _add_all_source_args(apply_all_cmd)
    _add_patch_mode_arg(apply_all_cmd)
    _add_fun_patch_args(apply_all_cmd)
    return parser


def main() -> int:
    args = _parser().parse_args()
    try:
        if args.command == "identify":
            print(json.dumps(identify(args.exe).raw, indent=2))
        elif args.command == "dry-run":
            print(
                json.dumps(
                    dry_run(args.exe, args.patch_mode, args.fun_patch), indent=2
                )
            )
        elif args.command == "apply":
            output, log = apply_patch(
                args.exe, args.patch_mode, args.overwrite, args.fun_patch
            )
            print(f"Created: {output}")
            print(f"Log: {log}")
        elif args.command == "dry-run-all":
            print(
                json.dumps(
                    dry_run_all(
                        _all_sources_from_args(args), args.patch_mode, args.fun_patch
                    ),
                    indent=2,
                )
            )
        else:
            results = apply_all(
                _all_sources_from_args(args), args.patch_mode, args.overwrite, args.fun_patch
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
