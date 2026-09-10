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

import ast
import json
import os
import sys
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

    A skip whose reason names no file at all is handled by
    `_module_names_an_absent_fixture` instead, which reads the test module's
    own globals rather than its prose. See that function for why.
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


def _module_names_an_absent_fixture(report) -> bool:
    """Whether the skipped test's own module points at a missing fixture.

    This covers the case no reason-reading branch can: a **class-level
    decorator**.

        @unittest.skipUnless(STOCK.is_file(), "requires the VV4 stock executable")
        class VV4SlotGuardCounterTests(unittest.TestCase):

    The body never runs, nothing is raised, and no file is opened, so
    `_is_missing_fixture` has no exception to inspect. The reason names no path
    and no basename, so both branches of `_is_fixture_skip` correctly decline
    it. The result was a focused run of a genuinely fixture-dependent test
    exiting 0 with this guard installed -- reported by review with exactly that
    node, and still reproducing after the reason-based branches were added.

    An earlier plan was to convert the callers to a generated-reason helper.
    Measuring first showed that would have fixed nothing here: those are
    `skipTest` calls, while every live instance of this defect is a
    `skipUnless` **decorator**, evaluated at import time -- a couple of dozen
    of them, spread across nearly as many files.

    The count is deliberately not stated exactly. Two sessions measured it on
    the same day and got 13, 15 and 18 depending on whether the grep handled
    multi-line decorators, and a precise figure in a durable comment outlives
    the session that wrote it and goes quietly stale. What matters is the
    shape, and the shape is what this function keys on.

    What they share is not a wording but a shape -- each gates on a
    module-level path:

        STOCK.is_file()   VV2_STOCK.is_file()   ATLAS.is_file()
        STOCK.exists()    VV3_DLL.is_file()     STOCK_DIR.is_dir()

    So the decision is taken from the module's globals. The report names the
    test file; the module is already imported by the time setup runs; any
    global holding a `Path` under a fixture root that is not on disk means the
    skip was a missing input. That is a fact about the disk, like the other two
    branches, and it needs no cooperation from the test author at all -- a
    fourteenth decorator with a brand new wording is covered on the day it is
    written.

    The tool/input distinction survives: `@unittest.skipIf(capstone is None,
    ...)` has no fixture Path in its module's globals to find.
    """
    location = getattr(report, "location", None)
    if not (isinstance(location, tuple) and location):
        return False
    name = Path(str(location[0])).name
    module = None
    for candidate in list(sys.modules.values()):
        file = getattr(candidate, "__file__", None)
        if file and Path(file).name == name:
            module = candidate
            break
    if module is None:
        return False

    gating = _names_used_by_the_skip_condition(module, location)
    if not gating:
        return False

    roots = [root.resolve() for root in FIXTURE_ROOTS]
    for attribute in gating:
        value = getattr(module, attribute, None)
        if not isinstance(value, Path):
            continue
        try:
            resolved = value.resolve()
        except (OSError, ValueError):
            continue
        if any(
            resolved == root or root in resolved.parents for root in roots
        ) and not value.exists():
            return True
    return False


def _names_used_by_the_skip_condition(module, location) -> set[str]:
    """Globals named by the decorator that actually caused this skip.

    Review found the hole this closes, and it is the third over-reporting one
    in this function. Asking "does this module mention an absent fixture Path"
    is not the same question as "did this skip happen because of one", and the
    difference is a live regression:

        tests/test_vv2_origins_playtest_feature.py
            STOCK = ROOT / "research" / "stock-executables"
            @unittest.skip("superseded by the current ... tests")

    A file retired as **superseded**, with no fixture condition anywhere, was
    told to link game files and failed the run. That is the over-reporting
    direction, and it is worse than the under-reporting one it was fixing: a
    guard that cries wolf on a legitimate configuration teaches people to set
    VVFP_ALLOW_NO_FIXTURES=1 permanently, which restores the original
    blindness with extra steps.

    So the dependency is now **observed rather than inferred**. The report
    carries the file and line of the skipped item, the decorator sits directly
    above it, and its condition names the globals it gates on. Only those are
    consulted.

    Parsed with `ast` rather than by matching text, so `STOCK.is_file()`,
    `HAVE_DEPS and STOCK.exists()` and `STOCK_DIR.is_dir()` are all read as
    the names they use. A bare `@unittest.skip("superseded")` has no condition
    at all and therefore names nothing, which is the case that regressed.

    Only `args[0]` is walked, not the whole decorator. Mutating that to walk
    the entire call survives every test, and the reason is worth recording
    rather than papering over with a test for it: across the whole suite the
    only name the wider walk adds is `unittest` itself, which is never a
    `Path`. The narrowing is correct but currently unobservable, so no
    assertion pins it -- writing one would pin behaviour that cannot differ,
    which is the dead-code-as-safeguard shape this file already removed once.
    """
    file = getattr(module, "__file__", None)
    if not file:
        return set()
    try:
        source = Path(file).read_text(encoding="utf-8")
        tree = ast.parse(source)
    except (OSError, ValueError, SyntaxError):
        return set()

    line = location[1] if len(location) > 1 else None
    if not isinstance(line, int):
        return set()
    # `location` is zero-based; ast line numbers are one-based.
    target = line + 1

    names: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.ClassDef, ast.FunctionDef)):
            continue
        end = getattr(node, "end_lineno", node.lineno)
        if not node.lineno <= target <= end:
            continue
        for decorator in node.decorator_list:
            if not isinstance(decorator, ast.Call) or not decorator.args:
                continue
            for sub in ast.walk(decorator.args[0]):
                if isinstance(sub, ast.Name):
                    names.add(sub.id)
    return names


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
    if report.skipped and (
        _is_fixture_skip(reason) or _module_names_an_absent_fixture(report)
    ):
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
