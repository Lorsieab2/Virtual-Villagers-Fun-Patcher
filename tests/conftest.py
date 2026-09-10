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

import json
import os
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


# --- The whole-run guard -------------------------------------------------
#
# A test that skips for a missing fixture is correct behaviour; a *run* in
# which every fixture-dependent test skipped is a run that verified nothing,
# and it exits 0 exactly like a run that verified everything. Three sessions
# hit this independently on the same repository, each diagnosing it as a local
# worktree problem and each solving it privately by linking the fixtures in.
# Nobody could see it from the terminal output, because "5 skipped" and
# "5 passed" are both green.
#
# So the run fails when the fixture-dependent tests it selected ALL skipped for
# the missing-input reason. Selecting none is fine -- that is a run that never
# asked. Selecting some and executing some is fine. Only "asked, and every
# answer was 'no input'" is the silent-nothing case.
#
# Set VVFP_ALLOW_NO_FIXTURES=1 to permit it, for the genuine case of a
# contributor without the game files running the rest of the suite.

_FIXTURE_SKIP_REASON = "requires a local game file that is gitignored and absent"

# The reason above is the one THIS file writes when it rewrites a
# FileNotFoundError. Many tests never reach that path: they check for the
# binary themselves and call `skipTest` with their own wording before opening
# anything. Keying on the rewritten reason alone missed all of them, so a
# focused run of exactly the tests this guard protects still exited 0 --
# reported by review with a reproduction:
#
#     pytest tests/test_vv2_father_traits_from_mother.py::...::
#            test_the_values_really_come_from_the_father
#     SKIPPED: stock executable not available: Virtual Villagers - ....exe
#     1 skipped        exit 0
#
# A first fix keyed on the SUBJECT of the phrasing -- "stock executable",
# "companion DLL" and so on. That was better than one exact string and still
# wrong: surveying the suite finds 52 distinct skip reasons, of which the
# subject list caught 16 and missed real fixture absences worded differently
# (`stock {game_id} executable fixture is unavailable`, `{exe_name} is not
# present`, `certified parent exe not present in this checkout`). Each new
# phrasing silently narrows the check again, which is this bug recurring
# rather than being fixed -- a peer session made exactly that argument.
#
# So the decision is not made from the wording at all. `_fixture_path_in_text`
# recovers any fixture path quoted in the reason and `_names_an_absent_path`
# confirms it is genuinely missing from disk -- the same pair the rewrite hook
# above already uses, so a proactive `skipTest` and a rewritten
# FileNotFoundError are now judged identically.
#
# That also gives the tool/input distinction for free rather than by
# enumeration. "requires capstone" and "Tk display is not available" quote no
# fixture path, so they cannot match: those are missing TOOLS, and a run
# without capstone has not silently failed to examine the binaries, it cannot
# examine them at all. Reddening that would be a different claim.
#
# The remaining gap is a proactive skip that mentions no path at all. Making
# those unforgeable needs a shared helper the tests call rather than a
# classifier reading their prose, which is the right next step and a change to
# 21 test files rather than to this one.

_fixture_skips: list[str] = []
_fixture_executed: list[str] = []


def _absent_fixture_basenames() -> set[str]:
    """Basenames of declared game executables that are not on disk.

    Read from `data/builds.json`, which is where the project already declares
    which executables exist, rather than from a list of titles kept here. A
    sixth game or a renamed input needs no edit in this file, and a name that
    drifts out of the manifest stops being recognised rather than lingering.
    """
    names: set[str] = set()
    manifest = ROOT / "data" / "builds.json"
    try:
        declared = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, ValueError):  # pragma: no cover - manifest unreadable
        return names
    for game in declared.get("games", ()):
        name = str(game.get("input_name") or "")
        if not name:
            continue
        if not any((root / name).is_file() for root in FIXTURE_ROOTS):
            names.add(name.lower())
    return names


def _is_fixture_skip(reason: str) -> bool:
    """Whether a skip reason concerns a fixture file that is absent from disk.

    Decided from the FILE rather than from the phrasing, in two steps because
    tests name their inputs two ways.

    A reason quoting a full path under a fixture root is checked with the same
    pair the rewrite hook uses, so a proactive `skipTest` and a rewritten
    FileNotFoundError are judged identically.

    A reason quoting only a BASENAME -- `skipTest(f"... {VV2_EXE.name}")`, the
    exact form review reported -- has no path to check, so the basename is
    matched against the fixture files that are declared and missing. That is
    still a fact about the disk rather than about the wording: if the file is
    present, the skip had some other cause and does not count.

    Both give the tool/input distinction for free rather than by enumeration.
    "requires capstone" and "Tk display is not available" name no fixture file
    at all, so neither branch can match them -- those are missing TOOLS, and a
    run without capstone has not silently failed to examine the binaries, it
    cannot examine them.

    A proactive skip mentioning no filename whatsoever remains invisible here,
    and no classifier reading prose can fix that.

    **That residual gap is 77 tests across 24 distinct phrasings, not a
    theoretical corner.** Counted from the junit of a full run in a worktree
    with no fixtures, the largest groups being `requires the VV4 stock
    executable` (15), `requires the exact-build VV1 stock executable` (8) and
    `stock VV5 executable is not checked in` (8). A live reproducer, which is
    a real node rather than a constructed probe:

        pytest "tests/test_vv4_slot_guards_use_a_real_counter.py::
                VV4SlotGuardCounterTests::
                test_counter_adds_pending_babies_behind_a_pregnancy_gate"
        1 skipped        exit 0

    That is a focused run of a fixture-dependent test exiting 0 with this
    guard installed -- the same shape as the defect the guard was written for.

    Twenty-four wordings for one condition is also the argument against ever
    fixing this by extending the matching: the twenty-fifth is one commit
    away. The fix is a shared `skip_missing_fixture(path)` helper that the
    tests call, so the reason is generated rather than written and cannot be
    phrased into invisibility. That is a change across those test files rather
    than to this one, which is why it is not in this commit -- but it is the
    fix, and the numbers above are here so the next reader does not have to
    rediscover the scale before deciding it is worth doing.
    """
    if not reason:
        return False
    if _FIXTURE_SKIP_REASON in reason:
        return True
    quoted = _fixture_path_in_text(reason)
    if quoted is not None and _names_an_absent_path(quoted):
        return True
    lowered = reason.lower()
    return any(name in lowered for name in _absent_fixture_basenames())


def pytest_runtest_logreport(report):
    """Record which fixture-dependent tests skipped and which ran."""
    if report.when != "call" and not (report.when == "setup" and report.skipped):
        return
    longrepr = getattr(report, "longrepr", None)
    reason = ""
    if isinstance(longrepr, tuple) and len(longrepr) == 3:
        reason = str(longrepr[2])
    elif isinstance(longrepr, str):
        reason = longrepr
    if report.skipped and _is_fixture_skip(reason):
        _fixture_skips.append(report.nodeid)
    elif report.when == "call" and not report.skipped:
        _fixture_executed.append(report.nodeid)


@pytest.hookimpl(hookwrapper=True)
def pytest_sessionfinish(session, exitstatus):
    """Fail a run whose fixture-dependent tests all skipped.

    Deliberately keyed on the skip REASON rather than on a count of skips:
    withdrawn features and unavailable displays skip too, and those are not
    evidence of a missing input. Only the reason this file itself writes is
    counted.
    """
    yield
    if os.environ.get("VVFP_ALLOW_NO_FIXTURES") == "1":
        return
    if not _fixture_skips:
        return
    if _fixture_executed:
        return
    # No `if session.exitstatus != 0: return` here, and its absence is
    # deliberate. A peer session's independently built guard needed one,
    # because theirs fires on any recorded fixture skip and so could overwrite
    # a real failure's status. This one cannot reach that state: anything that
    # fails -- a call, a setUp error, a teardown error -- is recorded in
    # `_fixture_executed`, so the check above has already returned. A
    # collection error aborts before the skips are recorded, so `_fixture_skips`
    # is empty and the check before that returns.
    #
    # The line was present in an earlier version. It was removed after a
    # mutation deleting it could not be made to fail: every case constructed
    # for it -- collection error, setUp explosion, a real assertion failure --
    # showed identical behaviour with and without. Dead code that reads as a
    # safeguard is worse than no code, because the next person trusts it.
    session.exitstatus = 1
    reporter = session.config.pluginmanager.get_plugin("terminalreporter")
    if reporter is not None:
        reporter.write_sep(
            "=",
            "every selected test that needs a game file skipped: this run "
            "verified nothing",
            red=True,
        )
        reporter.write_line(
            f"{len(_fixture_skips)} test(s) skipped for a missing input and "
            "none executed."
        )
        reporter.write_line(
            "Link the game files into research/stock-executables, or set "
            "VVFP_ALLOW_NO_FIXTURES=1 to accept a run that cannot check them."
        )
