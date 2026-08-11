#!/usr/bin/env python3
"""Package the VV4 Time-Warp-only candidate with its verified game files."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CANDIDATE = ROOT / "outputs/vv4-time-warp-only-candidate-2026-08-11"
DEPENDENCY_SOURCE = ROOT / "outputs/c260-package-staging/vv4-fullscreen-collection-playtest-1"
COMPANION = ROOT / "data/candidates/VVFP VV5 Task9 Origins Icons.dll"
EXE_NAME = "Virtual Villagers - The Tree of Life - Expanded 256 Time Warp Only.exe"
COMPANION_NAME = "VVFP Origins Icons.dll"
EXPECTED_EXE_SHA256 = "3AD22192212E3D82455EF771AB7B37E841082EE08F3FF10AEB826F2EE5D0AE0F"
EXPECTED_COMPANION_SHA256 = "B402ED8316CD6EB2C43B056848E622DC0924188C81C683F5E2813466AF8045D0"

ROOT_FILES = (
    "fmod.dll",
    "icon.bmp",
    "ldw.ini",
    "libjpeg-9.dll",
    "libpng16-16.dll",
    "SDL2.dll",
    "SDL2_image.dll",
    "zlib1.dll",
)
ASSET_DIRS = ("Assets", "Images", "Sounds")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def require(value: object, message: str) -> None:
    if not value:
        raise ValueError(message)


def package(destination: Path) -> dict[str, object]:
    source_exe = CANDIDATE / EXE_NAME
    source_report = CANDIDATE / "vv4-time-warp-only-candidate.json"
    source_notes = ROOT / "docs/vv4-time-warp-only-candidate.md"
    require(source_exe.is_file(), "candidate executable is missing")
    require(sha256(source_exe) == EXPECTED_EXE_SHA256, "candidate executable identity")
    require(COMPANION.is_file(), "Time Warp companion is missing")
    require(sha256(COMPANION) == EXPECTED_COMPANION_SHA256, "Time Warp companion identity")
    require(DEPENDENCY_SOURCE.is_dir(), "verified dependency source folder is missing")

    destination.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_exe, destination / EXE_NAME)
    shutil.copy2(source_report, destination / source_report.name)
    shutil.copy2(source_notes, destination / source_notes.name)
    for name in ROOT_FILES:
        source = DEPENDENCY_SOURCE / name
        require(source.is_file(), f"dependency is missing: {name}")
        shutil.copy2(source, destination / name)
    for name in ASSET_DIRS:
        source = DEPENDENCY_SOURCE / name
        require(source.is_dir(), f"asset directory is missing: {name}")
        shutil.copytree(source, destination / name, dirs_exist_ok=True)
    shutil.copy2(COMPANION, destination / COMPANION_NAME)

    files = sorted(
        path.relative_to(destination).as_posix()
        for path in destination.rglob("*")
        if path.is_file()
    )
    hashes = {name: sha256(destination / name) for name in files}
    manifest = {
        "game_id": "vv4",
        "package_status": "static_candidate_runtime_stop",
        "executable": EXE_NAME,
        "executable_sha256": hashes[EXE_NAME],
        "executable_size": (destination / EXE_NAME).stat().st_size,
        "enabled_tech_upgrades": ["Time Warp"],
        "tech_button": "Upgrades",
        "other_origins_rows_enabled": False,
        "companion": {
            "filename": COMPANION_NAME,
            "sha256": hashes[COMPANION_NAME],
            "size": (destination / COMPANION_NAME).stat().st_size,
        },
        "file_count": len(files),
        "files": files,
        "sha256": hashes,
        "runtime_go": False,
        "player_go": False,
        "publication_enabled": False,
        "stop_gates": [
            "atomic save writer and checked failure handling at all six callers",
            "runtime save/load/reload and full-256 fault receipts",
            "live player confirmation and package/publication certification",
        ],
    }
    (destination / "package-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    checksum_lines = [f"{hashes[name]}  {name}" for name in files]
    (destination / "SHA256SUMS.txt").write_text(
        "\n".join(checksum_lines) + "\n", encoding="utf-8"
    )
    (destination / "README.txt").write_text(
        "VV4 Expanded-256 Time-Warp-only candidate\n"
        "\n"
        f"Run: {EXE_NAME}\n"
        "Tech screen: Upgrades -> Time Warp only.\n"
        "\n"
        "This is a static candidate. Runtime/player approval and publication "
        "remain STOP pending live save/load/reload and fault tracing.\n",
        encoding="utf-8",
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    manifest = package(args.destination)
    print(json.dumps(manifest, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
