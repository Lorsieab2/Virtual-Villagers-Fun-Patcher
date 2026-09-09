"""A real failure must not become a skip because it quotes a fixture path.

`tests/conftest.py` reports a missing game binary as a skip rather than a
failure, which is right: the executables are gitignored, so a clean checkout
cannot run those tests and reporting 112 failures for an uninstalled game
hides real regressions in noise.

The recovery of the path, though, is a substring search over the error text,
and that branch is reached by *any* exception type -- `AssertionError`
included. So an assertion failure whose message merely mentions a fixture
directory was rewritten into a skip and vanished from the failure count,
without touching the filesystem at all:

    assert 1 == 2, "genuine regression"                  -> FAILED  (correct)
    assert 1 == 2, f"genuine regression near {FIXTURES}" -> SKIPPED (silent)

A masked regression is indistinguishable from a passing suite, which makes
this worse than the noisy failures the rewrite exists to prevent. The fix is
to confirm the named path is genuinely absent before allowing the rewrite.

These tests run pytest in a subprocess against generated files, because the
behaviour under test is the outer session's own report hook: asserting on it
from inside that session would be measuring the thing with itself.
"""

from __future__ import annotations

import subprocess
import sys
import textwrap
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


ROOT = Path(__file__).resolve().parents[1]
CONFTEST = ROOT / "tests" / "conftest.py"
STOCK = ROOT / "research" / "stock-executables"


def _run_case(body: str) -> str:
    """Run one generated test under the real conftest; return its outcome.

    The conftest is copied rather than imported so the subprocess exercises
    the shipped file, and its ROOT is repointed at a temporary directory
    that this function creates and populates.

    Pointing at the real repository was tried first and was wrong: the
    fixture roots are gitignored, so a path that exists on a developer's
    machine does not exist in CI, and the case asserting that a PRESENT
    path stays a failure asserted the opposite of what CI could produce. A
    test about gitignored fixtures must not depend on one. The temporary
    root also keeps the suite from writing into the real fixture directory.

    The generated module is given two names rather than interpolated paths:
    `PRESENT`, a file that exists inside the fixture root, and `ABSENT`, one
    that does not. Embedding Windows paths into string literals was tried
    first and was a constant source of quoting and backslash breakage that
    produced collection errors rather than the outcomes under test.
    """
    with TemporaryDirectory() as tmp:
        work = Path(tmp)
        stock = work / "research" / "stock-executables"
        stock.mkdir(parents=True)
        present = stock / "Present Game - With Spaces.exe"
        present.write_bytes(b"")
        absent = stock / "Virtual Villagers - No Such Game.exe"
        (work / "conftest.py").write_text(
            CONFTEST.read_text(encoding="utf-8").replace(
                "ROOT = Path(__file__).resolve().parents[1]",
                "ROOT = Path(r%r)" % str(work),
            ),
            encoding="utf-8",
        )
        header = "PRESENT = %r\nABSENT = %r\n\n" % (str(present), str(absent))
        (work / "test_case.py").write_text(
            header + textwrap.dedent(body), encoding="utf-8"
        )
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", "--tb=no",
             "-p", "no:cacheprovider", "test_case.py"],
            cwd=work,
            capture_output=True,
            text=True,
        )
        return result.stdout + result.stderr


class ConftestSkipsOnlyAbsentFixturesTests(unittest.TestCase):
    def test_a_plain_assertion_failure_is_reported_as_a_failure(self) -> None:
        """The control. Without this, every case below could pass vacuously."""
        out = _run_case(
            """
            def test_case():
                assert 1 == 2, "genuine regression, no path"
            """
        )
        self.assertIn("1 failed", out, out)

    def test_a_failure_quoting_a_PRESENT_fixture_stays_a_failure(self) -> None:
        """The defect this module exists to prevent.

        The message names a file inside the fixture root that is on disk.
        Nothing was read, nothing was missing: it is an ordinary assertion
        failure and must be reported as one.
        """
        out = _run_case(
            """
            def test_case():
                assert 1 == 2, "genuine regression near " + PRESENT
            """
        )
        self.assertIn("1 failed", out, out)
        self.assertNotIn("1 skipped", out, out)

    def test_delimiters_around_a_present_path_do_not_restore_the_mask(
        self,
    ) -> None:
        """Ordinary message punctuation must not defeat the check.

        A path is quoted, parenthesised, or followed by a colon in perfectly
        normal assertion output. An earlier version tested only whitespace
        prefixes, so `'<path>' while comparing` and `<path>: expected 3` kept
        their trailing quote or colon, matched nothing on disk, and were
        masked exactly as before -- four of five common formats still broken
        while the plain one passed.
        """
        # Each shape wraps the path with prose or punctuation. Built by
        # concatenation in the generated module so no quoting of a Windows
        # path into a literal is involved.
        shapes = (
            '"\'" + PRESENT + "\' while comparing"',
            'PRESENT + ": expected 3 got 4"',
            '"(" + PRESENT + ")"',
            '\'"\' + PRESENT + \'"\'',
            'PRESENT + ", which differs"',
            '"near " + PRESENT + "."',
            '"while reading " + PRESENT + " for the third time"',
        )
        for shape in shapes:
            with self.subTest(shape=shape):
                out = _run_case(
                    "\ndef test_case():\n    assert 1 == 2, %s\n" % shape
                )
                self.assertIn("1 failed", out, out)
                self.assertNotIn("1 skipped", out, out)

    def test_a_failure_naming_an_ABSENT_fixture_is_still_skipped(self) -> None:
        """The behaviour that must be preserved.

        A genuinely missing game file is not a defect, and a clean checkout
        must not report one. Narrowing the rewrite must not cost this.
        """
        out = _run_case(
            """
            def test_case():
                raise RuntimeError("Game executable not found: " + ABSENT)
            """
        )
        self.assertIn("1 skipped", out, out)

    def test_an_absent_path_with_delimiters_is_still_skipped(self) -> None:
        """Narrowing the check must not cost a skip for a real absence."""
        out = _run_case(
            """
            def test_case():
                raise RuntimeError("cannot read '" + ABSENT + "' yet")
            """
        )
        self.assertIn("1 skipped", out, out)

    def test_a_missing_file_error_is_still_skipped(self) -> None:
        """An OSError for an absent fixture keeps its skip.

        This is the path a real `open()` takes, and it is the common case on
        a checkout without the games installed.
        """
        out = _run_case(
            """
            def test_case():
                open(ABSENT, "rb")
            """
        )
        self.assertIn("1 skipped", out, out)


if __name__ == "__main__":
    unittest.main()
