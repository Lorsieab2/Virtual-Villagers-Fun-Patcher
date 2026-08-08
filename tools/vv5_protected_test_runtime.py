"""Run VV5 candidate validation with repository-local binary wheels only.

This helper is intentionally separate from the patcher and candidate builders.
It discovers and extracts local Keystone and Capstone wheels into a temporary
directory, imports both before loading the requested test module, and runs the
test in an isolated child interpreter.  It never installs a package, contacts
an index, writes repository files, or changes candidate/package output.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import stat
import subprocess
import sys
import tempfile
import textwrap
from typing import Iterable, Sequence
import zipfile


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TEST = ROOT / "tests" / "test_vv5_full_mastery_candidate.py"
WHEEL_SUFFIX = ".whl"
REQUIRED_DISTRIBUTIONS = {
    "keystone": frozenset({"keystone", "keystone-engine", "keystoneengine"}),
    "capstone": frozenset({"capstone"}),
}
SKIP_DIRECTORIES = frozenset(
    {
        ".git",
        "__pycache__",
        "build",
        "builds",
        "library",
        "logs",
        "packages",
        "playtest",
        "temp",
        "userSettings",
    }
)


class ProtectedRuntimeError(RuntimeError):
    """A local protected-runtime preflight or execution failure."""


@dataclass(frozen=True)
class LocalWheel:
    """A validated, repository-local wheel selected for the child runtime."""

    distribution: str
    path: Path
    size: int
    sha256: str

    def as_dict(self, root: Path) -> dict[str, object]:
        return {
            "distribution": self.distribution,
            "path": self.path.relative_to(root).as_posix(),
            "size": self.size,
            "sha256": self.sha256,
        }


def _normalize_distribution(value: str) -> str:
    return value.replace("_", "-").replace(".", "-").casefold()


def _distribution_from_wheel_name(path: Path) -> str | None:
    if path.suffix.casefold() != WHEEL_SUFFIX:
        return None
    # Wheel filenames use the distribution as the first hyphen-delimited
    # component.  Normalization handles keystone_engine and keystone-engine.
    first = path.name[: -len(WHEEL_SUFFIX)].split("-", 1)[0]
    normalized = _normalize_distribution(first)
    for distribution, aliases in REQUIRED_DISTRIBUTIONS.items():
        if normalized in aliases:
            return distribution
    return None


def _inside(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _is_reparse(path: Path) -> bool:
    try:
        attributes = getattr(path.lstat(), "st_file_attributes", 0)
    except OSError:
        return True
    return path.is_symlink() or bool(attributes & 0x400)


def _validated_root(repo_root: Path) -> Path:
    try:
        root = repo_root.resolve(strict=True)
    except OSError as exc:
        raise ProtectedRuntimeError(f"repository root is not readable: {repo_root}") from exc
    if not root.is_dir() or _is_reparse(root):
        raise ProtectedRuntimeError(f"repository root must be a real directory: {repo_root}")
    return root


def _validated_wheel_root(path: Path, repo_root: Path) -> Path | None:
    try:
        resolved = path.resolve(strict=True)
    except OSError:
        return None
    if not resolved.is_dir() or _is_reparse(resolved) or not _inside(resolved, repo_root):
        raise ProtectedRuntimeError(
            f"wheel root must be a real directory inside the repository: {path}"
        )
    return resolved


def _iter_wheels(root: Path) -> Iterable[Path]:
    """Yield accessible wheel files in stable order without following links."""

    def on_error(_: OSError) -> None:
        # Protected or incomplete local directories are not dependency proof.
        # Keep scanning accessible repository-owned roots; the final resolver
        # reports a missing dependency if the required wheel was not visible.
        return None

    for current, directory_names, file_names in os.walk(
        root, topdown=True, followlinks=False, onerror=on_error
    ):
        directory_names[:] = sorted(
            (
                name
                for name in directory_names
                if name.casefold() not in {item.casefold() for item in SKIP_DIRECTORIES}
            ),
            key=str.casefold,
        )
        for name in sorted(file_names, key=str.casefold):
            path = Path(current) / name
            if _distribution_from_wheel_name(path) is None:
                continue
            try:
                if _is_reparse(path) or not stat.S_ISREG(path.stat().st_mode):
                    continue
            except OSError:
                continue
            yield path


def discover_local_wheels(
    repo_root: Path, wheel_roots: Sequence[Path] | None = None
) -> dict[str, tuple[Path, ...]]:
    """Discover candidate Keystone/Capstone wheel paths without network access.

    Results are grouped by logical distribution and sorted by repository-local
    POSIX path.  The function intentionally returns all matches; callers must
    reject ambiguity instead of silently selecting a version.
    """

    root = _validated_root(repo_root)
    requested = tuple(wheel_roots) if wheel_roots else (root,)
    found: dict[str, set[Path]] = {name: set() for name in REQUIRED_DISTRIBUTIONS}
    for requested_root in requested:
        scan_root = _validated_wheel_root(Path(requested_root), root)
        if scan_root is None:
            continue
        for path in _iter_wheels(scan_root):
            distribution = _distribution_from_wheel_name(path)
            if distribution is not None:
                found[distribution].add(path.resolve())
    return {
        distribution: tuple(
            sorted(paths, key=lambda item: item.relative_to(root).as_posix().casefold())
        )
        for distribution, paths in found.items()
    }


def _sha256_file(path: Path) -> tuple[int, str]:
    before = path.stat()
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
            size += len(block)
    after = path.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise ProtectedRuntimeError(f"local wheel changed while hashing: {path}")
    if size != before.st_size:
        raise ProtectedRuntimeError(f"local wheel size changed while reading: {path}")
    return size, digest.hexdigest().upper()


def _explicit_wheel(
    name: str, path: Path | None, repo_root: Path
) -> LocalWheel | None:
    if path is None:
        return None
    try:
        resolved = path.resolve(strict=True)
    except OSError as exc:
        raise ProtectedRuntimeError(f"{name} wheel is not readable: {path}") from exc
    if not _inside(resolved, repo_root) or _is_reparse(resolved) or not resolved.is_file():
        raise ProtectedRuntimeError(f"{name} wheel must be a real repository-local file: {path}")
    if _distribution_from_wheel_name(resolved) != name:
        raise ProtectedRuntimeError(f"{name} wheel filename does not identify {name}: {path}")
    size, digest = _sha256_file(resolved)
    return LocalWheel(name, resolved, size, digest)


def resolve_local_wheels(
    repo_root: Path,
    wheel_roots: Sequence[Path] | None = None,
    *,
    keystone_wheel: Path | None = None,
    capstone_wheel: Path | None = None,
) -> dict[str, LocalWheel]:
    """Resolve exactly one local wheel for each protected runtime dependency."""

    root = _validated_root(repo_root)
    explicit = {
        "keystone": _explicit_wheel("keystone", keystone_wheel, root),
        "capstone": _explicit_wheel("capstone", capstone_wheel, root),
    }
    discovered = discover_local_wheels(root, wheel_roots)
    resolved: dict[str, LocalWheel] = {}
    missing: list[str] = []
    ambiguous: list[str] = []
    for distribution in REQUIRED_DISTRIBUTIONS:
        if explicit[distribution] is not None:
            resolved[distribution] = explicit[distribution]  # type: ignore[assignment]
            continue
        candidates = discovered[distribution]
        if not candidates:
            missing.append(distribution)
            continue
        if len(candidates) != 1:
            ambiguous.append(
                f"{distribution} ({', '.join(path.relative_to(root).as_posix() for path in candidates)})"
            )
            continue
        size, digest = _sha256_file(candidates[0])
        resolved[distribution] = LocalWheel(distribution, candidates[0], size, digest)
    if missing or ambiguous:
        details = []
        if missing:
            details.append("missing local wheel(s): " + ", ".join(sorted(missing)))
        if ambiguous:
            details.append("ambiguous local wheel(s): " + "; ".join(ambiguous))
        raise ProtectedRuntimeError(
            "STOP_MISSING_LOCAL_WHEEL: "
            + ". ".join(details)
            + ". No network access was attempted."
        )
    return resolved


def _safe_extract(wheel: LocalWheel, destination: Path) -> None:
    """Extract one wheel after rejecting path traversal and linked entries."""

    with zipfile.ZipFile(wheel.path) as archive:
        members = archive.infolist()
        for member in members:
            normalized_name = member.filename.replace("\\", "/")
            relative = PurePosixPath(normalized_name)
            if relative.is_absolute() or any(part in ("", ".", "..") for part in relative.parts):
                raise ProtectedRuntimeError(
                    f"unsafe member path in local wheel {wheel.path.name}: {member.filename}"
                )
            target = (destination / Path(*relative.parts)).resolve()
            if not _inside(target, destination.resolve()):
                raise ProtectedRuntimeError(
                    f"wheel member escapes temporary runtime: {member.filename}"
                )
            if member.is_dir():
                continue
            mode = (member.external_attr >> 16) & 0o170000
            if mode == stat.S_IFLNK:
                raise ProtectedRuntimeError(
                    f"linked member rejected in local wheel {wheel.path.name}: {member.filename}"
                )
        archive.extractall(destination)


def _git_commit(repo_root: Path) -> str | None:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    commit = completed.stdout.strip()
    return commit or None


_CHILD_RUNNER = textwrap.dedent(
    r'''
    import importlib.util
    import pathlib
    import socket
    import sys
    import unittest

    runtime_root = pathlib.Path(sys.argv[1]).resolve()
    test_path = pathlib.Path(sys.argv[2]).resolve()
    sys.path.insert(0, str(runtime_root))

    def _deny_network(*args, **kwargs):
        raise RuntimeError("network access is disabled by vv5_protected_test_runtime")

    socket.socket.connect = _deny_network
    socket.create_connection = _deny_network
    # Import before loading the candidate module.  The VV5 builder inserts its
    # legacy .tools paths itself; cached modules keep the selected wheel bound.
    import keystone  # noqa: F401
    import capstone  # noqa: F401

    spec = importlib.util.spec_from_file_location("vv5_candidate_validation", test_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load candidate test: {test_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    suite = unittest.defaultTestLoader.loadTestsFromModule(module)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(0 if result.wasSuccessful() else 1)
    '''
).strip()


def run_vv5_candidate_validation(
    repo_root: Path,
    *,
    wheel_roots: Sequence[Path] | None = None,
    test_path: Path | None = None,
    python_executable: Path | None = None,
    timeout_seconds: int = 600,
    keystone_wheel: Path | None = None,
    capstone_wheel: Path | None = None,
) -> dict[str, object]:
    """Run one VV5 candidate test module in an isolated local-wheel runtime."""

    root = _validated_root(repo_root)
    target_test = (test_path or DEFAULT_TEST).resolve(strict=True)
    if not _inside(target_test, root) or _is_reparse(target_test) or not target_test.is_file():
        raise ProtectedRuntimeError(
            f"candidate test must be a real file inside the repository: {target_test}"
        )
    wheels = resolve_local_wheels(
        root,
        wheel_roots,
        keystone_wheel=keystone_wheel,
        capstone_wheel=capstone_wheel,
    )
    interpreter = Path(python_executable or sys.executable).resolve(strict=True)
    with tempfile.TemporaryDirectory(prefix="vv5-protected-runtime-") as temp_dir:
        runtime_root = Path(temp_dir) / "site-packages"
        runtime_root.mkdir()
        for wheel in wheels.values():
            _safe_extract(wheel, runtime_root)
        environment = os.environ.copy()
        # The outer runner uses -I and receives runtime_root through its
        # bootstrap argv.  Candidate tests may start ordinary nested Python
        # processes with sys.executable; pass only the prepared local runtime
        # to those children so they resolve the same wheel bytes.
        environment["PYTHONPATH"] = str(runtime_root)
        environment["PYTHONNOUSERSITE"] = "1"
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        completed = subprocess.run(
            [str(interpreter), "-I", "-B", "-c", _CHILD_RUNNER, str(runtime_root), str(target_test)],
            cwd=root,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout_seconds,
        )
    return {
        "schema": "vvfp.vv5-protected-test-runtime.v1",
        "status": "PASS" if completed.returncode == 0 else "FAIL",
        "candidate_test": target_test.relative_to(root).as_posix(),
        "repository_commit": _git_commit(root),
        "python": str(interpreter),
        "wheels": {
            name: wheel.as_dict(root) for name, wheel in sorted(wheels.items())
        },
        "network_access": False,
        "writes": [],
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run VV5 candidate validation with repository-local Keystone/Capstone wheels only."
    )
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    parser.add_argument(
        "--wheel-root",
        action="append",
        type=Path,
        help="Repository-local directory to scan; may be repeated.",
    )
    parser.add_argument("--keystone-wheel", type=Path)
    parser.add_argument("--capstone-wheel", type=Path)
    parser.add_argument("--test-path", type=Path, default=DEFAULT_TEST)
    parser.add_argument("--python", dest="python_executable", type=Path)
    parser.add_argument("--timeout-seconds", type=int, default=600)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = run_vv5_candidate_validation(
            args.repo_root,
            wheel_roots=args.wheel_root,
            test_path=args.test_path,
            python_executable=args.python_executable,
            timeout_seconds=args.timeout_seconds,
            keystone_wheel=args.keystone_wheel,
            capstone_wheel=args.capstone_wheel,
        )
    except (OSError, ValueError, zipfile.BadZipFile, ProtectedRuntimeError) as exc:
        result = {
            "schema": "vvfp.vv5-protected-test-runtime.v1",
            "status": "STOP",
            "reason": str(exc),
            "network_access": False,
            "writes": [],
        }
        print(json.dumps(result, indent=2, sort_keys=True))
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
