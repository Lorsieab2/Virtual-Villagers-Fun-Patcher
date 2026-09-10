"""A run that skipped for want of the game files must not exit 0.

The skip rewrite in `conftest.py` is correct: a gitignored binary that is
absent is a missing input, not a defect, and failing each such test would make
the suite unusable for anyone without the games.

What it cannot do is answer the question asked one level up -- *did this run
examine the binaries?* A fresh worktree lacks every gitignored file, so a suite
run there skips the fixture-dependent tests and still exits 0. That happened
three times in one day across three sessions: twice a green run in such a
worktree was read as evidence about the code, and once all five tests in a pull
request skipped while the branch was being reviewed as passing.

A test that skipped proved nothing, and by exit status alone a run made
entirely of those skips is indistinguishable from one that verified
everything.

These checks drive pytest in a subprocess rather than inspecting the hook,
because the thing under test is the *exit status of a run*, which cannot be
observed from inside the run producing it.
"""
from __future__ import annotations

import subprocess
import sys
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STOCK = ROOT / "research" / "stock-executables"


def _run(tmp: Path, body: str, env_extra: dict[str, str] | None = None):
    """Run one throwaway test file under pytest, from an empty rootdir.

    The temporary tree mirrors the real layout -- a `tests/` directory holding
    a copy of the conftest -- because the hook derives its fixture roots from
    `parents[1]` of its own file. Flattening the copy into the rootdir points
    those roots one level above the temporary tree, where the probe path never
    matches and the skip rewrite never fires.
    """
    import os

    (tmp / "tests").mkdir(exist_ok=True)
    (tmp / "tests" / "conftest.py").write_text(
        (ROOT / "tests" / "conftest.py").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (tmp / "tests" / "test_probe.py").write_text(
        textwrap.dedent(body), encoding="utf-8"
    )
    env = dict(os.environ)
    env.pop("VVFP_ALLOW_MISSING_FIXTURES", None)
    if env_extra:
        env.update(env_extra)
    return subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "tests/test_probe.py"],
        cwd=tmp,
        capture_output=True,
        text=True,
        env=env,
        timeout=300,
    )


# A test that opens a file under the fixture root that does not exist. The
# conftest hook rewrites the resulting error into a skip; this module checks
# what the RUN then does.
MISSING_FIXTURE_PROBE = '''
    import unittest
    from pathlib import Path

    ROOT = Path(__file__).resolve().parents[1]

    class Probe(unittest.TestCase):
        def test_needs_a_game_file(self):
            open(ROOT / "research" / "stock-executables" / "Absent.exe", "rb")
    '''


class MissingFixturesFailTheRunTests(unittest.TestCase):
    def test_a_run_that_only_skipped_for_fixtures_fails(self) -> None:
        """The defect this module exists for."""
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            result = _run(Path(td), MISSING_FIXTURE_PROBE)
        self.assertEqual(
            result.returncode,
            1,
            "a run whose only outcome was a missing-fixture skip exited "
            f"{result.returncode}; stdout:\n{result.stdout}",
        )
        self.assertIn("missing game files", result.stdout)

    def test_the_message_names_the_skipped_test(self) -> None:
        """A count alone does not say what went unexamined."""
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            result = _run(Path(td), MISSING_FIXTURE_PROBE)
        self.assertIn("test_needs_a_game_file", result.stdout)

    def test_the_opt_out_is_honoured(self) -> None:
        """Someone without the games must still be able to run the suite."""
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            result = _run(
                Path(td),
                MISSING_FIXTURE_PROBE,
                {"VVFP_ALLOW_MISSING_FIXTURES": "1"},
            )
        self.assertEqual(
            result.returncode,
            0,
            "VVFP_ALLOW_MISSING_FIXTURES did not permit the run; stdout:\n"
            f"{result.stdout}",
        )

    def test_a_real_failure_is_not_masked(self) -> None:
        """The guard must not replace a genuine failure with its own message.

        Forcing the status when a run has already failed would leave the real
        defect reported but attributed to the fixtures, which is worse than
        either signal alone.
        """
        import tempfile

        body = MISSING_FIXTURE_PROBE + '''
    class Real(unittest.TestCase):
        def test_genuine(self):
            self.assertEqual(1, 2, "a real defect")
    '''
        with tempfile.TemporaryDirectory() as td:
            result = _run(Path(td), body)
        self.assertEqual(result.returncode, 1)
        self.assertIn("test_genuine", result.stdout)
        self.assertIn("1 failed", result.stdout)
        # The exit code is 1 whether or not the guard fired, so asserting only
        # on it cannot tell "the real failure set the status" from "the guard
        # overrode a status that was already 1". Deleting the early return for
        # a failed run passed such an assertion unchanged. The banner is what
        # actually differs, and attributing a genuine defect to the fixtures is
        # the outcome worth preventing.
        self.assertNotIn(
            "missing game files",
            result.stdout,
            "the guard claimed a run that failed for a real reason; its "
            "message would attribute a genuine defect to absent fixtures",
        )

    def test_a_clean_run_with_the_fixtures_present_is_unaffected(self) -> None:
        """The guard must stay silent when nothing is missing.

        Asserted from this suite's own environment: if the stock executables
        are present here, this run must not be carrying the guard's message.
        """
        if not STOCK.is_dir() or not any(STOCK.glob("*.exe")):
            self.skipTest("the stock executables are not present in this checkout")
        import tempfile

        clean = '''
    import unittest

    class Clean(unittest.TestCase):
        def test_passes(self):
            self.assertTrue(True)
    '''
        with tempfile.TemporaryDirectory() as td:
            result = _run(Path(td), clean)
        self.assertEqual(result.returncode, 0)
        self.assertNotIn("missing game files", result.stdout)


if __name__ == "__main__":
    unittest.main()
