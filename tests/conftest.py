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

What that costs, stated here because the exit status cannot say it. Measured
by moving the executables aside on a machine that has them:

    with the executables    1342 passed, 123 skipped
    without them            1176 passed, 376 skipped

The ~166 tests that stop running are not a random sample. They are the layer
that verifies PATCHED OUTPUT -- StockIntegrationTests, ManifestTests, the
per-game feature suites, and PublishLeavesRoomForCrashImmunityTests, whose
subtests catch a wrapper splitting the executable zero run and breaking
publish-time name-crash immunity.

The gap is invisible at file granularity. Without the executables these files
do not go red or vanish -- they report passes, and only the binary-level
subtests skip:

    test_publish_leaves_room_for_crash_immunity   2 passed, 10 skipped
    test_death_wrapper_replays_the_stolen_bytes   2 passed,  2 skipped
    test_statistics_wrappers_preserve_registers   2 passed,  2 skipped

So a summary line can show green in the file whose name promises the
guarantee while the assertion about patched output was never made.

So a green run without the executables is evidence about the code that does
not need them, and nothing more. CI is such a run by construction, since the
binaries are copyrighted and correctly gitignored; byte-level guarantees rest
on a local run with them linked.

Treat the totals as approximate. They depend on the tree (``inputs/`` differs
per machine) and carry roughly +/-7 from a Tk-initialisation flake in the GUI
tests: those skip or run unpredictably across identical invocations, with the
reason reported as a missing ``init.tcl`` even though ``tkinter.Tk()``
succeeds in the same interpreter outside pytest. The cause is unresolved and
is not the fixture mechanism this module implements. The composition does not
vary, and the fixture gap is far outside that noise.

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


def _root_markers(root: Path) -> list[str]:
    """The spellings of `root` that may appear in an error message.

    Windows hands out 8.3 short names in places -- a CI runner's temporary
    directory arrives as `C:\\Users\\RUNNER~1\\...` while `resolve()` returns
    the long name -- so a message can name the same directory in a form the
    resolved marker does not match. Both are tried, and the comparison is
    case-insensitive because Windows paths are.
    """
    markers = {str(root), str(root.resolve())}
    try:
        markers.add(str(root.absolute()))
    except (OSError, ValueError):
        pass
    markers.add(_short_name(root))
    return [m for m in markers if m]


def _short_name(path: Path) -> str:
    """The 8.3 spelling of `path` on Windows, or "" where there is none.

    The directory must exist for Windows to report one, and the call is
    absent on other platforms, so every failure returns "" and simply adds
    no marker.
    """
    try:
        import ctypes

        buffer = ctypes.create_unicode_buffer(1024)
        length = ctypes.windll.kernel32.GetShortPathNameW(  # type: ignore[attr-defined]
            str(path), buffer, 1024
        )
        return buffer.value if length else ""
    except Exception:
        return ""


def _fixture_path_in_text(text: str) -> str | None:
    """A fixture path quoted in an error message, when there is one."""
    lowered = text.lower()
    for root in FIXTURE_ROOTS:
        for marker in _root_markers(root):
            index = lowered.find(marker.lower())
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

    Each prefix has surrounding punctuation stripped before it is tested.
    Assertion messages quote and delimit paths in ordinary ways --
    ``'<path>' while comparing``, ``<path>: expected 3``, ``(<path>)``,
    ``<path>, which differs`` -- and a prefix that keeps its trailing quote
    or colon matches nothing on disk, so without this every one of those
    formats was still masked.
    """
    text = candidate.strip()
    if not text:
        return False
    # Game filenames contain spaces, so the path cannot simply be split at
    # the first one. Every contiguous run of words is a candidate -- the
    # recovered text may carry prose on either side ("near <path>.") -- and
    # longer runs are tried first so the fullest match wins.
    parts = text.split()
    if len(parts) > _MAX_WORDS:
        # The scan is quadratic in word count. A path is recovered from the
        # start of a line, so a very long run is prose rather than a path;
        # bound the work instead of letting one message stall the suite.
        parts = parts[:_MAX_WORDS]
    for length in range(len(parts), 0, -1):
        for start in range(0, len(parts) - length + 1):
            candidate_text = _strip_delimiters(
                " ".join(parts[start : start + length])
            )
            if not candidate_text:
                continue
            try:
                if Path(candidate_text).exists():
                    return False
            except (OSError, ValueError):
                continue
    return True


# Punctuation that commonly wraps or follows a path inside an error message
# and is never part of a path this project reads.
_DELIMITERS = "\"'`()[]{}<>,;:. \t\r\n"

# Upper bound on words considered when hunting for a path inside a message.
# The longest path this guards is around a dozen words; the rest is prose.
_MAX_WORDS = 24


def _strip_delimiters(text: str) -> str:
    """`text` with wrapping and trailing message punctuation removed."""
    return text.strip(_DELIMITERS)


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
    # pytest's own short-summary folding requires the (path, lineno, reason)
    # triple that a real skip carries -- _folded_skips asserts both the type
    # and the length. Setting a bare string produced a correct `-q` run and
    # crashed the terminal reporter on `-rs` or `-ra`:
    #
    #     assert isinstance(event.longrepr, tuple)
    #     AssertionError: (<TestReport ... outcome='skipped'>, 'requires ...')
    #
    # which is worth fixing rather than avoiding, because `-rs` is how anyone
    # asks "what is this suite NOT running?" -- the exact question a
    # skip-rewriting hook makes it important to be able to answer.
    # report.location carries a ZERO-based line, while the short summary
    # prints a skip's line one-based without adjusting it. Passing the raw
    # value through reported every rewritten skip one line too low, and a test
    # declared on the first line printed as ":0", which is not a line at all.
    #
    # Verified side by side in one file rather than reasoned about: a genuine
    # self.skipTest on line 3 reports ":3", while this rewrite for a test on
    # line 5 reported ":4" until the adjustment below.
    location = getattr(report, "location", None)
    if isinstance(location, tuple) and len(location) == 3:
        path, lineno = location[0], location[1]
        if isinstance(lineno, int):
            lineno += 1
    else:
        path, lineno = str(item.path), None
    report.longrepr = (
        str(path),
        lineno,
        f"requires a local game file that is gitignored and absent: {missing}",
    )
