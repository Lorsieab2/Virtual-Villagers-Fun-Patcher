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
    the shipped file, and FIXTURE_ROOTS is repointed at this repository so
    the paths under test are the ones it actually guards.
    """
    with TemporaryDirectory() as tmp:
        work = Path(tmp)
        (work / "conftest.py").write_text(
            CONFTEST.read_text(encoding="utf-8").replace(
                "ROOT = Path(__file__).resolve().parents[1]",
                "ROOT = Path(r%r)" % str(ROOT),
            ),
            encoding="utf-8",
        )
        (work / "test_case.py").write_text(
            textwrap.dedent(body), encoding="utf-8"
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

        The message names a fixture directory that is on disk. Nothing was
        read, nothing was missing: it is an ordinary assertion failure and
        must be reported as one.
        """
        out = _run_case(
            """
            def test_case():
                assert 1 == 2, "genuine regression near %s"
            """
            % str(STOCK).replace("\\", "\\\\")
        )
        self.assertIn("1 failed", out, out)
        self.assertNotIn("1 skipped", out, out)

    def test_a_failure_naming_an_ABSENT_fixture_is_still_skipped(self) -> None:
        """The behaviour that must be preserved.

        A genuinely missing game file is not a defect, and a clean checkout
        must not report one. Narrowing the rewrite must not cost this.
        """
        absent = STOCK / "Virtual Villagers - No Such Game.exe"
        out = _run_case(
            """
            def test_case():
                raise RuntimeError("Game executable not found: %s")
            """
            % str(absent).replace("\\", "\\\\")
        )
        self.assertIn("1 skipped", out, out)

    def test_a_missing_file_error_is_still_skipped(self) -> None:
        """An OSError for an absent fixture keeps its skip.

        This is the path a real `open()` takes, and it is the common case on
        a checkout without the games installed.
        """
        absent = STOCK / "Virtual Villagers - No Such Game.exe"
        out = _run_case(
            """
            def test_case():
                open(r"%s", "rb")
            """
            % str(absent)
        )
        self.assertIn("1 skipped", out, out)


if __name__ == "__main__":
    unittest.main()
