"""Skip, rather than fail, when the local game binaries are absent.

`research/` and `inputs/` hold stock game executables. Both are gitignored --
the project must never commit game binaries -- so a fresh clone has neither,
and every test that reads one fails on collection or assertion. On this
machine that is 112 failures and 46 errors across 21 files, which is why the
suite has never been runnable in CI: a clean checkout looks catastrophically
broken when it is merely missing inputs it is not allowed to carry.

A missing input is not a failing test. Marking those tests skipped keeps the
distinction visible: a red run then means a real regression rather than a
checkout without the game installed.

Tests are matched by the paths they actually resolve, not by a hand-listed set
of filenames. A list would have to be maintained by hand and would rot the
first time a test was added -- the same "hand-rolled pattern" failure recorded
throughout this repository's crash notes, where a stale pattern reports a clean
result it never checked.
"""

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
# The directories a test names, mapped to the game binaries that make them
# usable. `research/` also holds committed mask art, so its mere existence
# proves nothing -- what matters is whether the stock executables are there.
FIXTURE_DIRS = {
    "research": ROOT / "research" / "stock-executables",
    "inputs": ROOT / "inputs",
}


def _available(name: str) -> bool:
    directory = FIXTURE_DIRS[name]
    return directory.is_dir() and any(directory.glob("**/*.exe"))


MISSING = [name for name in FIXTURE_DIRS if not _available(name)]


def _needs_missing_fixture(module_path: Path) -> str | None:
    """The first missing fixture directory this module's source names."""
    try:
        source = module_path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return None
    for name in MISSING:
        if f'"{name}"' in source or f"'{name}'" in source or f"{name}/" in source:
            return name
    return None


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Report a missing fixture binary as a skip, whatever raised it.

    Some tests reach the executables through an imported builder rather than
    naming a path, so scanning their source cannot see the dependency. Those
    surface as FileNotFoundError pointing into a fixture directory, which is
    the same "input absent" condition and is reported the same way.
    """
    outcome = yield
    if not MISSING or call.when not in ("setup", "call"):
        return
    error = call.excinfo
    if error is None or not issubclass(error.type, (FileNotFoundError, OSError)):
        return
    filename = str(getattr(error.value, "filename", "") or "").replace("\\", "/")
    if not any(f"/{name}/" in filename for name in MISSING):
        return
    report = outcome.get_result()
    report.outcome = "skipped"
    report.longrepr = (
        f"requires a local game file that is gitignored and absent: {filename}"
    )
    report.wasxfail = None


def pytest_collection_modifyitems(config, items):
    if not MISSING:
        return
    cache: dict[Path, str | None] = {}
    for item in items:
        path = Path(str(getattr(item, "fspath", "")))
        if path not in cache:
            cache[path] = _needs_missing_fixture(path)
        needed = cache[path]
        if needed:
            item.add_marker(
                pytest.mark.skip(
                    reason=(
                        f"requires the local {needed}/ game files, which are "
                        "gitignored and absent from this checkout"
                    )
                )
            )
