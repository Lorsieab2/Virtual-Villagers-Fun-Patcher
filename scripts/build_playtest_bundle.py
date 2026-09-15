"""Build and package an authenticated, player-facing playtest bundle.

This tool is deliberately narrower than the source-release builder.  It only
packages a feature that the public catalog already certifies as enabled,
native-output-ready, and runtime/player verified.  Disabled evidence records
therefore cannot accidentally become playable bundles.

The tool never launches a game and never reads, copies, or writes a save.  A
source tree containing save-like files is rejected before the patcher is
called.  All generated files must live below the ignored ``outputs`` tree.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
OUTPUTS_ROOT = (ROOT / "outputs").resolve()

GAME_SPECS: dict[str, dict[str, Any]] = {
    "vv2": {
        "title": "Virtual Villagers - The Lost Children",
        "exe": "Virtual Villagers - The Lost Children.exe",
        "size": 724_992,
        "sha256": "46C1503C209255C9CDEFA941DB2F449C8CF8E2CDD5C7D13CD975326E377ED677",
    },
    "vv3": {
        "title": "Virtual Villagers - The Secret City",
        "exe": "Virtual Villagers - The Secret City.exe",
        "size": 831_488,
        "sha256": "8BC5DB382D02BC5C21AD5F607580D60FF44A6519CC7EB133F03113BAACAE6503",
    },
    "vv4": {
        "title": "Virtual Villagers - The Tree of Life",
        "exe": "Virtual Villagers - The Tree of Life.exe",
        "size": 929_792,
        "sha256": "6D27A429FFCA5F1F71FDD7ECA761ED1BB67E85F976494BA178B3D7BE01F1B220",
    },
    "vv5": {
        "title": "Virtual Villagers - New Believers",
        "exe": "Virtual Villagers - New Believers.exe",
        "size": 991_232,
        "sha256": "92946781980220E9D1A2E6C573925519934608F5215F4A0F8CE3B90088C5C65D",
    },
}

SAVE_SUFFIXES = {".ldw", ".sav", ".save", ".savegame"}
SAVE_PARTS = {"save", "saves", "savegames", "savedgames"}
RUNTIME_STATUS_OK = {"verified", "go", "runtime/player go", "certified"}


class BundleError(RuntimeError):
    """A fail-closed bundle preflight or verification error."""


def _canonical_json(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def _is_reparse(path: Path, st: os.stat_result | None = None) -> bool:
    if path.is_symlink():
        return True
    if st is None:
        st = path.lstat()
    attrs = getattr(st, "st_file_attributes", 0)
    return bool(attrs & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))


def _walk_no_follow(root: Path) -> Iterable[tuple[Path, os.stat_result]]:
    """Yield regular files without following links/reparse points."""
    if not root.is_dir() or _is_reparse(root):
        raise BundleError(f"source/output root is not a normal directory: {root}")
    stack = [root]
    while stack:
        current = stack.pop()
        with os.scandir(current) as entries:
            for entry in entries:
                path = Path(entry.path)
                st = entry.stat(follow_symlinks=False)
                if _is_reparse(path, st):
                    raise BundleError(f"reparse/link path is forbidden: {path}")
                if entry.is_dir(follow_symlinks=False):
                    stack.append(path)
                elif entry.is_file(follow_symlinks=False):
                    yield path, st
                else:
                    raise BundleError(f"non-regular source/output entry: {path}")


def _relative(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _looks_like_save(path: str) -> bool:
    parts = [part.casefold() for part in Path(path).parts]
    return any(part in SAVE_PARTS for part in parts) or Path(path).suffix.casefold() in SAVE_SUFFIXES


def _inventory(root: Path, *, reject_saves: bool) -> dict[str, Any]:
    files: list[dict[str, Any]] = []
    for path, st in _walk_no_follow(root):
        relative = _relative(path, root)
        if reject_saves and _looks_like_save(relative):
            raise BundleError(f"save-like source file is forbidden: {relative}")
        files.append({"path": relative, "size": st.st_size, "sha256": _sha256_file(path)})
    files.sort(key=lambda item: item["path"])
    body = {"schema": "vvfp.playtest-folder-inventory.v1", "files": files}
    return {
        **body,
        "file_count": len(files),
        "total_size": sum(item["size"] for item in files),
        "inventory_sha256": _sha256_bytes(_canonical_json(body)),
    }


def _resolve_output_root(path: Path) -> Path:
    requested = path.expanduser()
    if requested.exists() and _is_reparse(requested):
        raise BundleError(f"output root cannot be a reparse/link path: {requested}")
    resolved = path.expanduser().resolve()
    try:
        resolved.relative_to(OUTPUTS_ROOT)
    except ValueError as exc:
        raise BundleError(f"output root must be below {OUTPUTS_ROOT}: {resolved}") from exc
    return resolved


def _assert_separate(source: Path, output_root: Path) -> None:
    try:
        output_root.relative_to(source)
    except ValueError:
        pass
    else:
        raise BundleError("output root cannot be inside the source game folder")
    try:
        source.relative_to(output_root)
    except ValueError:
        pass
    else:
        raise BundleError("source game folder cannot be inside the output root")


def _assert_output_not_inside(source: Path, output_root: Path) -> None:
    """Allow an output folder to contain a built game, never the reverse."""
    try:
        output_root.relative_to(source)
    except ValueError:
        return
    raise BundleError("output root cannot be inside the source game folder")


def verify_stock_folder(game_id: str, source_folder: Path) -> dict[str, Any]:
    """Verify exact stock executable identity and source-tree safety."""
    if game_id not in GAME_SPECS:
        raise BundleError(f"unsupported playtest game: {game_id}")
    source = source_folder.expanduser().resolve()
    if not source.is_dir() or _is_reparse(source):
        raise BundleError(f"stock source folder is unavailable or linked: {source}")
    spec = GAME_SPECS[game_id]
    exe = source / spec["exe"]
    if not exe.is_file() or _is_reparse(exe):
        raise BundleError(f"expected stock executable is missing: {exe}")
    size = exe.stat().st_size
    digest = _sha256_file(exe)
    if size != spec["size"] or digest != spec["sha256"]:
        raise BundleError(
            f"stock executable fingerprint mismatch for {game_id}: "
            f"size={size} sha256={digest}"
        )
    inventory = _inventory(source, reject_saves=True)
    return {
        "game_id": game_id,
        "title": spec["title"],
        "source_folder": str(source),
        "stock_executable": spec["exe"],
        "stock_size": size,
        "stock_sha256": digest,
        "inventory": inventory,
    }


def _patcher_module():
    src = str(ROOT / "src")
    if src not in sys.path:
        sys.path.insert(0, src)
    import vv_fun_patcher  # type: ignore

    return vv_fun_patcher


def _assert_playtest_ready(game_id: str, feature_id: str, patch_mode: str = "collection_progression") -> dict[str, Any]:
    patcher = _patcher_module()
    try:
        patch = patcher.get_fun_patch(feature_id)
    except Exception as exc:  # catalog errors must remain fail-closed
        raise BundleError(f"feature is not catalog-resolved: {feature_id}") from exc
    raw = dict(patch.raw)
    if raw.get("game_id") != game_id:
        raise BundleError(f"feature {feature_id} belongs to another game")
    if raw.get("enabled") is not True:
        raise BundleError(f"feature {feature_id} is disabled")
    if raw.get("catalog_enabled") is not True:
        raise BundleError(f"feature {feature_id} is not catalog-enabled")
    if raw.get("catalog_hidden") is not False:
        raise BundleError(f"feature {feature_id} is catalog-hidden")
    if raw.get("native_output") is not True:
        raise BundleError(f"feature {feature_id} has no native output certification")
    if raw.get("runtime_pending") is True or raw.get("player_pending") is True:
        raise BundleError(f"feature {feature_id} has pending runtime/player evidence")
    if raw.get("runtime_verified") is not True or raw.get("player_verified") is not True:
        status = str(raw.get("runtime_player_status", raw.get("runtime_status", ""))).strip().casefold()
        if status not in RUNTIME_STATUS_OK:
            raise BundleError(f"feature {feature_id} has pending runtime/player evidence")
    expected_hashes = _authenticated_modded_exe_hashes(raw, feature_id, patch_mode)
    if not expected_hashes:
        raise BundleError(f"feature {feature_id} has no authenticated modded executable hash")
    return {
        "id": feature_id,
        "name": raw.get("name"),
        "game_id": game_id,
        "status": "playtest-ready",
        "patch_mode": patch_mode,
        "runtime_player_status": "verified",
        "expected_modded_exe_sha256": sorted(expected_hashes),
    }


def _authenticated_modded_exe_hashes(raw: dict[str, Any], feature_id: str, patch_mode: str) -> set[str]:
    """Return only hashes explicitly bound to this feature and patch mode.

    The candidate manifest is the source of truth for package authentication.
    Do not accept a caller-supplied hash, a stock hash, or a generic arbitrary
    ``sha256`` field.  The supported records intentionally use one of the
    rendered-candidate spellings below, so malformed values fail closed.
    """

    del feature_id  # retained in the signature for an actionable caller error
    hashes: set[str] = set()

    def add(value: Any) -> None:
        if isinstance(value, str) and len(value) == 64:
            normalized = value.upper()
            if all(character in "0123456789ABCDEF" for character in normalized):
                hashes.add(normalized)

    def collect_mode(container: Any) -> None:
        if not isinstance(container, dict):
            return
        for map_key in ("rendered_candidates", "rendered_modes", "rendered_exe_sha256"):
            mode_map = container.get(map_key)
            if not isinstance(mode_map, dict):
                continue
            row = mode_map.get(patch_mode)
            if isinstance(row, dict):
                for key in (
                    "candidate_sha256",
                    "candidate_exe_sha256",
                    "candidate_executable_sha256",
                    "rendered_exe_sha256",
                    "all_current_compatible_sha256",
                    "all_current_sha256",
                    "all_current_vv2_sha256",
                ):
                    add(row.get(key))
            else:
                add(row)

    collect_mode(raw)
    collect_mode(raw.get("static_acceptance"))
    candidate = raw.get("candidate")
    if isinstance(candidate, dict):
        collect_mode(candidate)
        collect_mode(candidate.get("emitted"))
    emitted = raw.get("emitted")
    if isinstance(emitted, dict):
        collect_mode(emitted)
    return hashes


def _assert_feature_ids(game_id: str, feature_ids: list[str], patch_mode: str = "collection_progression") -> list[dict[str, Any]]:
    if not feature_ids:
        raise BundleError("at least one feature ID is required for a playtest bundle")
    seen: set[str] = set()
    records: list[dict[str, Any]] = []
    for feature_id in feature_ids:
        if feature_id in seen:
            raise BundleError(f"duplicate feature ID: {feature_id}")
        seen.add(feature_id)
        records.append(_assert_playtest_ready(game_id, feature_id, patch_mode))
    return records


def dry_run(game_id: str, source_folder: Path, output_root: Path, feature_ids: list[str], patch_mode: str) -> dict[str, Any]:
    output = _resolve_output_root(output_root)
    stock = verify_stock_folder(game_id, source_folder)
    _assert_separate(Path(stock["source_folder"]), output)
    features = _assert_feature_ids(game_id, feature_ids, patch_mode)
    return {
        "schema": "vvfp.playtest-bundle-plan.v1",
        "status": "READY_FOR_BUILD",
        "dry_run": True,
        "game_id": game_id,
        "patch_mode": patch_mode,
        "output_root": str(output),
        "features": features,
        "stock": stock,
        "launch": False,
        "save_access": False,
    }


def _package_manifest(folder: Path, game_id: str, feature_ids: list[str], patch_mode: str, stock: dict[str, Any]) -> dict[str, Any]:
    files = _inventory(folder, reject_saves=True)
    stock_manifest = dict(stock)
    if stock_manifest.get("source_folder"):
        stock_manifest["source_folder"] = Path(str(stock_manifest["source_folder"])).name
    return {
        "schema": "vvfp.playtest-bundle-manifest.v1",
        "game_id": game_id,
        "title": GAME_SPECS[game_id]["title"],
        "patch_mode": patch_mode,
        "features": feature_ids,
        "folder": folder.name,
        "stock": stock_manifest,
        "output_inventory": files,
        "zip_sha256": None,
        "launch": False,
        "save_access": False,
        "runtime_status": "player validation required",
    }


def package_folder(game_id: str, folder: Path, output_root: Path, feature_ids: list[str], patch_mode: str, stock: dict[str, Any] | None = None) -> dict[str, Any]:
    feature_records = _assert_feature_ids(game_id, feature_ids, patch_mode)
    root = _resolve_output_root(output_root)
    game_folder = folder.expanduser().resolve()
    _assert_output_not_inside(game_folder, root)
    if not game_folder.is_dir() or _is_reparse(game_folder):
        raise BundleError(f"playtest folder is unavailable or linked: {game_folder}")
    spec = GAME_SPECS[game_id]
    stock_exe = game_folder / spec["exe"]
    if not stock_exe.is_file() or _is_reparse(stock_exe):
        raise BundleError(f"stock executable is missing from playtest folder: {stock_exe}")
    if stock_exe.stat().st_size != spec["size"] or _sha256_file(stock_exe) != spec["sha256"]:
        raise BundleError("playtest folder stock executable fingerprint mismatch")
    modded_exe = game_folder / spec["exe"].replace(".exe", " - Modded.exe")
    if not modded_exe.is_file() or _is_reparse(modded_exe):
        raise BundleError(f"modded executable is missing: {modded_exe}")
    expected_modded_hashes = {
        digest
        for record in feature_records
        for digest in record.get("expected_modded_exe_sha256", [])
    }
    modded_digest = _sha256_file(modded_exe)
    if modded_digest not in expected_modded_hashes:
        raise BundleError(
            "authenticated modded executable fingerprint mismatch: "
            f"sha256={modded_digest}"
        )
    if stock is None:
        stock = {"game_id": game_id, "stock_sha256": spec["sha256"], "stock_size": spec["size"]}
    manifest = _package_manifest(game_folder, game_id, feature_ids, patch_mode, stock)
    root.mkdir(parents=True, exist_ok=True)
    zip_path = root / f"{game_folder.name}.zip"
    if zip_path.exists():
        raise BundleError(f"package already exists: {zip_path}")
    entries: list[str] = []
    with tempfile.TemporaryDirectory(prefix="vvfp-playtest-") as temp:
        manifest_path = Path(temp) / "PLAYTEST-BUNDLE-MANIFEST.json"
        manifest_path.write_bytes(_canonical_json(manifest))
        try:
            with zipfile.ZipFile(zip_path, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
                manifest_name = f"{game_folder.name}/PLAYTEST-BUNDLE-MANIFEST.json"
                manifest_info = zipfile.ZipInfo(manifest_name, date_time=(1980, 1, 1, 0, 0, 0))
                manifest_info.create_system = 3
                manifest_info.external_attr = 0o100644 << 16
                archive.writestr(
                    manifest_info,
                    manifest_path.read_bytes(),
                    compress_type=zipfile.ZIP_DEFLATED,
                    compresslevel=9,
                )
                entries.append(manifest_name)
                files = sorted(_walk_no_follow(game_folder), key=lambda item: _relative(item[0], game_folder))
                for path, _ in files:
                    relative = _relative(path, game_folder)
                    if _looks_like_save(relative):
                        raise BundleError(f"save-like output file is forbidden: {relative}")
                    name = f"{game_folder.name}/{relative}"
                    info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
                    info.create_system = 3
                    info.external_attr = 0o100644 << 16
                    archive.writestr(
                        info,
                        path.read_bytes(),
                        compress_type=zipfile.ZIP_DEFLATED,
                        compresslevel=9,
                    )
                    entries.append(name)
        except Exception:
            zip_path.unlink(missing_ok=True)
            raise
    with zipfile.ZipFile(zip_path, "r") as archive:
        bad = archive.testzip()
        if bad is not None:
            zip_path.unlink(missing_ok=True)
            raise BundleError(f"ZIP CRC verification failed: {bad}")
        actual = sorted(archive.namelist())
    if actual != sorted(entries):
        zip_path.unlink(missing_ok=True)
        raise BundleError("ZIP entry manifest mismatch")
    digest = _sha256_file(zip_path)
    manifest.update({"zip_sha256": digest, "zip_size": zip_path.stat().st_size, "zip_entries": len(entries)})
    manifest_path = root / f"{game_folder.name}.manifest.json"
    manifest_path.write_bytes(_canonical_json(manifest))
    return {"zip": str(zip_path), "manifest": str(manifest_path), "zip_sha256": digest, "zip_entries": len(entries), "output_inventory": manifest["output_inventory"]}


def build_bundle(game_id: str, source_folder: Path, output_root: Path, feature_ids: list[str], patch_mode: str, package: bool) -> dict[str, Any]:
    plan = dry_run(game_id, source_folder, output_root, feature_ids, patch_mode)
    root = Path(plan["output_root"])
    root.mkdir(parents=True, exist_ok=True)
    patcher = _patcher_module()
    game_folder, _ = patcher.apply_patch(
        Path(plan["stock"]["source_folder"]),
        patch_mode=patch_mode,
        overwrite=False,
        fun_patch_ids=feature_ids,
        output_root=root,
        copy_saves=False,
        replace_modded_saves=False,
    )
    result: dict[str, Any] = {"status": "BUILT", "game_folder": str(game_folder), "plan": plan}
    if package:
        result["package"] = package_folder(game_id, game_folder, root, feature_ids, patch_mode, plan["stock"])
    return result


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for command in ("dry-run", "build"):
        p = sub.add_parser(command)
        p.add_argument("--game", choices=sorted(GAME_SPECS), required=True)
        p.add_argument("--source-folder", type=Path, required=True)
        p.add_argument("--output-root", type=Path, required=True)
        p.add_argument("--patch-mode", default="collection_progression", choices=("collection_progression", "immediate_fixed"))
        p.add_argument("--fun-patch", action="append", required=True)
        if command == "build":
            p.add_argument("--package", action="store_true")
    package = sub.add_parser("package")
    package.add_argument("--game", choices=sorted(GAME_SPECS), required=True)
    package.add_argument("--game-folder", type=Path, required=True)
    package.add_argument("--output-root", type=Path, required=True)
    package.add_argument("--patch-mode", default="collection_progression", choices=("collection_progression", "immediate_fixed"))
    package.add_argument("--fun-patch", action="append", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "dry-run":
            result = dry_run(args.game, args.source_folder, args.output_root, args.fun_patch, args.patch_mode)
        elif args.command == "build":
            result = build_bundle(args.game, args.source_folder, args.output_root, args.fun_patch, args.patch_mode, args.package)
        else:
            _assert_feature_ids(args.game, args.fun_patch)
            result = package_folder(args.game, args.game_folder, args.output_root, args.fun_patch, args.patch_mode)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except (BundleError, OSError, ValueError) as exc:
        print(f"STOP: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
