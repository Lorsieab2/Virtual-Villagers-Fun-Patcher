"""A run whose fixture-dependent tests all skipped must not exit 0.

A test that skips because a gitignored game file is absent is behaving
correctly. A *run* in which every such test skipped is a run that verified
nothing -- and it exits 0, prints green, and is indistinguishable from a run
that verified everything:

    $ pytest tests/test_vv3_chief_puzzle_is_a_one_shot_latch.py
    sssss                                                    [100%]
    5 skipped in 0.18s        exit 0

Three sessions hit this independently on this repository. Each diagnosed it as
a local worktree problem, each solved it privately by linking the fixtures in,
and none of them could have seen it from the terminal: "5 skipped" and
"5 passed" are both green. That makes it a property of the repository rather
than of anyone's setup, which is why the fix belongs here.

The guard in `conftest.py` fails the run when the fixture-dependent tests it
selected ALL skipped for the missing-input reason. The three cases it must
distinguish are the point:

  * selected none                 -> fine, the run never asked
  * selected some, ran some       -> fine, whatever else skipped
  * selected some, ran none       -> the silent-nothing case, fail

This module drives real pytest subprocesses rather than asserting on the
source of the hook, because the defect being prevented IS an exit status. A
source-level assertion would pass while the hook returned 0.
"""

from __future__ import annotations

import os
import subprocess
import sys
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ARunThatVerifiedNothingFails(unittest.TestCase):
    def _run(self, tmp: Path, body: str, env_extra=None):
        """Run pytest on a throwaway file in a tree with its own conftest.

        The real `conftest.py` is copied in so the hook under test is the
        shipped one, not a reimplementation. Using a synthetic test file keeps
        this independent of whichever real tests happen to need fixtures.
        """
        (tmp / "conftest.py").write_bytes((ROOT / "tests" / "conftest.py").read_bytes())
        (tmp / "test_probe.py").write_text(textwrap.dedent(body), encoding="utf-8")
        env = dict(os.environ)
        env.pop("VVFP_ALLOW_NO_FIXTURES", None)
        if env_extra:
            env.update(env_extra)
        return subprocess.run(
            [sys.executable, "-m", "pytest", "test_probe.py", "-q",
             "-p", "no:cacheprovider"],
            capture_output=True,
            text=True,
            env=env,
            cwd=str(tmp),
        )

    # The exact reason string the conftest hook writes. Imported rather than
    # retyped would be better, but the hook builds it inline; if it ever
    # changes, `test_the_reason_string_still_matches` below fails loudly
    # instead of this module silently testing nothing.
    REASON = "requires a local game file that is gitignored and absent"

    def test_the_reason_string_still_matches_the_conftest(self):
        """The literal this module keys on must still exist in the hook.

        Without this, renaming the reason in `conftest.py` would leave every
        assertion below constructing skips the guard does not recognise -- and
        they would pass, because a run with no recognised fixture skips is a
        legitimately-passing run. The guard would be dead and the tests green.
        """
        source = (ROOT / "tests" / "conftest.py").read_text(encoding="utf-8")
        self.assertIn(
            self.REASON,
            source,
            "the conftest no longer writes the reason this module keys on",
        )

    def test_a_run_where_every_fixture_test_skipped_fails(self):
        """The defect: all skipped, nothing ran, exit 0."""
        import tempfile

        with tempfile.TemporaryDirectory() as temp:
            result = self._run(
                Path(temp),
                f"""
                import unittest

                class Probe(unittest.TestCase):
                    def test_one(self):
                        raise unittest.SkipTest("{self.REASON}: x.exe")

                    def test_two(self):
                        raise unittest.SkipTest("{self.REASON}: y.exe")
                """,
            )
            self.assertNotEqual(
                result.returncode,
                0,
                "a run that verified nothing must not exit 0\n"
                + result.stdout[-2000:],
            )
            self.assertIn("verified nothing", result.stdout)

    def test_a_run_with_one_real_test_passing_does_not_fail(self):
        """The false-alarm case, which matters more than the defect.

        A contributor with some game files gets a mixture of skips and real
        results. If the guard fired there it would be worse than the problem it
        solves, because the failure would be routine and people would learn to
        ignore it.
        """
        import tempfile

        with tempfile.TemporaryDirectory() as temp:
            result = self._run(
                Path(temp),
                f"""
                import unittest

                class Probe(unittest.TestCase):
                    def test_skipped(self):
                        raise unittest.SkipTest("{self.REASON}: x.exe")

                    def test_executed(self):
                        self.assertTrue(True)
                """,
            )
            self.assertEqual(
                result.returncode,
                0,
                "a run with real results must pass even if something skipped\n"
                + result.stdout[-2000:],
            )

    def test_unrelated_skips_do_not_trigger_the_guard(self):
        """Withdrawn features and missing displays skip too.

        The guard keys on the reason string rather than on a count, because a
        suite with many deliberate skips and no fixture skips has verified
        exactly what it set out to.
        """
        import tempfile

        with tempfile.TemporaryDirectory() as temp:
            result = self._run(
                Path(temp),
                """
                import unittest

                class Probe(unittest.TestCase):
                    def test_withdrawn(self):
                        raise unittest.SkipTest("feature was withdrawn")

                    def test_display(self):
                        raise unittest.SkipTest("Tk display is not available")
                """,
            )
            self.assertEqual(
                result.returncode,
                0,
                "skips for other reasons are not a missing-input run\n"
                + result.stdout[-2000:],
            )

    def test_the_ci_shape_stays_green(self):
        """CI has no game files by design, and must not go red.

        `.github/workflows/tests.yml` says so explicitly: the stock executables
        are gitignored and "a CI checkout cannot have them", and reporting
        those tests as skipped "is what makes this run meaningful". A guard
        that reddened every CI run would be removed within a day, and rightly.

        It stays green because a full-suite run selects both kinds: the fixture
        tests skip while thousands of ordinary tests execute, so
        `_fixture_executed` is non-empty. That is a consequence of the design
        rather than a special case, but it is asserted here because it is the
        thing someone "tightening" this guard would break first -- and they
        would not find out until CI turned red on an unrelated pull request.
        """
        import tempfile

        with tempfile.TemporaryDirectory() as temp:
            result = self._run(
                Path(temp),
                f"""
                import unittest

                class FixtureDependent(unittest.TestCase):
                    def test_needs_exe_a(self):
                        raise unittest.SkipTest("{self.REASON}: a.exe")

                    def test_needs_exe_b(self):
                        raise unittest.SkipTest("{self.REASON}: b.exe")

                class Ordinary(unittest.TestCase):
                    def test_runs_anywhere(self):
                        self.assertTrue(True)
                """,
            )
            self.assertEqual(
                result.returncode,
                0,
                "the CI shape -- fixture tests skipping while ordinary tests "
                "run -- must stay green" + result.stdout[-2000:],
            )

    def test_the_escape_hatch_permits_a_fixtureless_run(self):
        """Someone without the game files must still be able to run the suite.

        Refusing that outright would push contributors to delete the guard
        rather than set a variable.
        """
        import tempfile

        with tempfile.TemporaryDirectory() as temp:
            result = self._run(
                Path(temp),
                f"""
                import unittest

                class Probe(unittest.TestCase):
                    def test_one(self):
                        raise unittest.SkipTest("{self.REASON}: x.exe")
                """,
                env_extra={"VVFP_ALLOW_NO_FIXTURES": "1"},
            )
            self.assertEqual(
                result.returncode,
                0,
                "VVFP_ALLOW_NO_FIXTURES=1 must permit the run\n"
                + result.stdout[-2000:],
            )


if __name__ == "__main__":
    unittest.main()
