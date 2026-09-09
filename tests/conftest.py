"""Report a missing game file as a skip rather than a failure.

`research/stock-executables/` and `inputs/` hold stock game executables. Both
are gitignored -- the project must never commit game binaries -- so no clean
checkout has them, and every test that reads one fails on an input it is not
allowed to carry. On a fresh clone that is 112 failures and 46 errors across
21 files, which is why this suite has never been runnable in CI: the result
looks catastrophic when it is merely missing inputs.

A missing input is not a failing test. Reporting those as skipped keeps the
distinction visible, so a red run means a real regression rather than a
checkout without the games installed.

The dependency is detected from what a test actually DOES -- an unreadable
fixture path at run time -- not from scanning its source. Two earlier attempts
here failed in exactly the way this repository's crash notes warn about:
matching a module's text skipped four tests whose docstring merely *mentions*
``research/`` while stating they deliberately do not read it, and treating one
executable as proof of a whole directory ran tests against games the developer
had not installed. Only the file a test opens says what that test needs, and
that is per-file, so a partial install skips exactly the tests it should.
"""

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

# Directories holding gitignored game binaries. A path under any of these that
# cannot be opened is a missing input, not a defect.
FIXTURE_ROOTS = (
    ROOT / "research" / "stock-executables",
    ROOT / "inputs",
)


def _filename_from_frames(error: BaseException) -> str | None:
    """A fixture path named by the raising frame's locals, when there is one."""
    tb = error.__traceback__
    while tb is not None:
        for value in tb.tb_frame.f_locals.values():
            if not isinstance(value, (str, Path)):
                continue
            try:
                resolved = Path(str(value)).resolve()
            except (OSError, ValueError):
                continue
            for root in FIXTURE_ROOTS:
                try:
                    resolved.relative_to(root.resolve())
                except ValueError:
                    continue
                return str(resolved)
        tb = tb.tb_next
    return None


def _fixture_path_in_text(text: str) -> str | None:
    """A fixture path quoted in an error message, when there is one."""
    for root in FIXTURE_ROOTS:
        marker = str(root.resolve())
        index = text.find(marker)
        if index != -1:
            return text[index:].strip().splitlines()[0].strip()
    return None


def _names_an_absent_path(candidate: str) -> bool:
    """Whether `candidate` names a fixture path that is genuinely not there.

    Quoting a path is not the same as being unable to read it. An error text
    is recovered by substring search, so any message mentioning a fixture
    directory matches -- including an assertion failure that merely names the
    file it was comparing. Rewriting that into a skip hides a real regression,
    and a hidden regression is indistinguishable from a passing suite.

    The path is therefore confirmed absent before the rewrite is allowed. A
    recovered string can carry trailing prose, so leading prefixes are tried
    as well: the longest prefix that exists means the input is present.
    """
    text = candidate.strip().rstrip(".:,;")
    if not text:
        return False
    try:
        if Path(text).exists():
            return False
    except (OSError, ValueError):
        return False
    # The message may continue past the path ("...exe while doing X"). Walk
    # back through whitespace-separated prefixes; if any names something that
    # exists, the fixture is present and this is not a missing input.
    parts = text.split()
    for count in range(len(parts) - 1, 0, -1):
        prefix = " ".join(parts[:count])
        try:
            if Path(prefix).exists():
                return False
        except (OSError, ValueError):
            continue
    return True


def _is_missing_fixture(error: BaseException) -> str | None:
    """The fixture path this error names, when it is one."""
    if not isinstance(error, OSError):
        # The patcher raises its own error type for an absent game
        # executable, naming the path in its message. That is the same
        # missing-input condition and is reported the same way.
        #
        # Only when the path it names is really absent. This branch is
        # reached by any exception whose text mentions a fixture directory,
        # AssertionError included, so without the existence check a genuine
        # failure that merely quotes a path is rewritten into a skip and
        # disappears from the failure count. An OSError needs no such check:
        # it got here by a filesystem call that actually failed.
        named = _fixture_path_in_text(str(error))
        if named is None or not _names_an_absent_path(named):
            return None
        return named
    filename = getattr(error, "filename", None)
    if not filename:
        # Some Windows paths raise without populating `filename` -- shutil's
        # CopyFile2 route is the one that bites here. The path is still in the
        # frame that raised, so recover it from the traceback's locals rather
        # than letting a real missing-input look like a defect.
        filename = _filename_from_frames(error)
    if not filename:
        return None
    try:
        resolved = Path(str(filename)).resolve()
    except (OSError, ValueError):
        return None
    for root in FIXTURE_ROOTS:
        try:
            resolved.relative_to(root.resolve())
        except ValueError:
            continue
        return str(resolved)
    return None


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    if call.when not in ("setup", "call") or call.excinfo is None:
        return
    missing = _is_missing_fixture(call.excinfo.value)
    if missing is None:
        # A test that refuses to pass vacuously without the executables is
        # reporting the same missing input, in the healthiest possible way.
        # Honour that rather than letting it read as a regression.
        text = str(call.excinfo.value)
        if "no stock executables available" in text:
            missing = "the stock executables"
        else:
            return
    report = outcome.get_result()
    report.outcome = "skipped"
    report.longrepr = (
        f"requires a local game file that is gitignored and absent: {missing}"
    )
