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
    def _run(self, tmp: Path, body: str, env_extra=None, extra_files=None):
        """Run pytest on a throwaway file in a tree with its own conftest.

        The real `conftest.py` is copied in so the hook under test is the
        shipped one, not a reimplementation. Using a synthetic test file keeps
        this independent of whichever real tests happen to need fixtures.

        It has to be a subprocess: the thing under test is the exit status of a
        run, which cannot be observed from inside the run producing it.

        A peer session reported a trap worth recording. A probe tree that
        mirrors the real layout (`tests/conftest.py` under a root) is needed to
        exercise the conftest's FileNotFoundError **rewrite**, because that
        hook derives its fixture roots from `parents[1]` of its own file; a
        flat copy points them above the temp tree and the rewrite never fires.

        These probes are deliberately flat, and that is sound only because the
        guard keys on the **reason string carried in `longrepr`** rather than
        on the rewrite that normally produces it, so a bare `SkipTest` with
        that reason reaches it identically. The consequence is stated rather
        than left implicit: **this module tests the guard, not the rewrite.**
        The rewrite has its own coverage in
        `test_conftest_skips_only_absent_fixtures.py`, and
        `test_the_reason_string_still_matches_the_conftest` is what stops the
        two drifting apart silently.
        """
        # Mirror the real layout: tests/ under a root that also carries
        # data/builds.json. The conftest resolves both its fixture roots and
        # the manifest of declared executables from `parents[1]` of its own
        # file, so a flat probe tree points them outside itself -- the
        # basename branch then sees an empty declaration list and cannot fire.
        # That is the layout trap a peer session reported, hit here for real.
        (tmp / "tests").mkdir(exist_ok=True)
        (tmp / "data").mkdir(exist_ok=True)
        (tmp / "research" / "stock-executables").mkdir(parents=True, exist_ok=True)
        (tmp / "tests" / "conftest.py").write_bytes(
            (ROOT / "tests" / "conftest.py").read_bytes()
        )
        (tmp / "data" / "builds.json").write_bytes(
            (ROOT / "data" / "builds.json").read_bytes()
        )
        (tmp / "tests" / "test_probe.py").write_text(
            textwrap.dedent(body), encoding="utf-8"
        )
        for name, contents in (extra_files or {}).items():
            (tmp / "tests" / name).write_text(contents, encoding="utf-8")
        env = dict(os.environ)
        env.pop("VVFP_ALLOW_NO_FIXTURES", None)
        if env_extra:
            env.update(env_extra)
        selection = ["tests"] if extra_files else ["tests/test_probe.py"]
        return subprocess.run(
            [sys.executable, "-m", "pytest", *selection, "-q",
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

    def test_a_partial_checkout_stays_green(self):
        """One game file present, another absent: the run examined binaries.

        **This is the case that separated two independently built guards**, and
        it is pinned rather than left as a property because it is the whole
        reason for the three-case shape.

        A peer session's version keyed on "was any skip rewritten for a missing
        fixture", which cannot distinguish *nothing was examined* from
        *something was examined and something else was not*. They reproduced it
        on their own branch: one fixture test passing and one skipping gave
        exit 1, with the guard firing on a run that had genuinely checked a
        binary.

        That is not a corner case. It is the shape of any checkout holding some
        of the five games, and a guard that reddens it would be routinely
        ignored -- which is worse than the problem it solves.

        The distinction from `test_a_run_with_one_real_test_passing_does_not_fail`
        matters: that one has an ORDINARY test passing beside a fixture skip.
        This one has a FIXTURE-DEPENDENT test passing, which is the case a
        skip-counting guard gets wrong.
        """
        import tempfile

        with tempfile.TemporaryDirectory() as temp:
            result = self._run(
                Path(temp),
                f"""
                import unittest

                class FixtureDependent(unittest.TestCase):
                    def test_game_we_have(self):
                        self.assertTrue(True)

                    def test_game_we_lack(self):
                        raise unittest.SkipTest("{self.REASON}: missing.exe")
                """,
            )
            self.assertEqual(
                result.returncode,
                0,
                "a partial checkout examined binaries and must stay green"
                + result.stdout[-2000:],
            )
            self.assertNotIn(
                "verified nothing",
                result.stdout,
                "the guard must not fire when a fixture-dependent test ran",
            )

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

    def test_the_ci_shape_stays_green(self):
        """CI has no game files by design, and must not go red.

        `.github/workflows/tests.yml` says so explicitly: the stock executables
        are gitignored and "a CI checkout cannot have them", with skipping
        being "what makes this run meaningful". A guard that reddened every CI
        run would be removed within a day, and rightly.

        It stays green because a full-suite run selects both kinds -- the
        fixture tests skip while thousands of ordinary tests execute -- so
        something did run. That is why the guard asks whether any
        fixture-dependent test EXECUTED rather than whether any skipped.

        A peer session's independently built guard keyed on the latter and
        reddened this case; measuring it is what settled which design shipped.
        It is asserted here because it is the property someone tightening this
        guard would break first, and they would not find out until CI failed on
        an unrelated pull request.
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

    def test_a_real_failure_is_not_masked_by_the_guard(self):
        """A genuine regression must fail the run as itself.

        Contributed by the peer session above, together with the reason this
        checks the banner rather than the exit status: asserting
        `returncode == 1` is satisfied whether the real failure set it OR the
        guard overrode it, so it is blind to the branch it exists for. Their
        mutation dropping the guard's already-failed early exit passed against
        that weaker form.
        """
        import tempfile

        with tempfile.TemporaryDirectory() as temp:
            result = self._run(
                Path(temp),
                f"""
                import unittest

                class Probe(unittest.TestCase):
                    def test_needs_absent_file(self):
                        raise unittest.SkipTest("{self.REASON}: a.exe")

                    def test_genuinely_broken(self):
                        self.assertEqual(1, 2, "a real regression")
                """,
            )
            self.assertNotEqual(
                result.returncode, 0, "a real failure must fail the run"
            )
            self.assertIn("a real regression", result.stdout)
            self.assertNotIn(
                "verified nothing",
                result.stdout,
                "the guard must stay silent when a real failure already failed "
                "the run; announcing itself there buries the regression",
            )

    def test_a_collection_error_keeps_its_own_exit_status(self):
        """The already-failed early exit, exercised where it actually matters.

        The peer's mutation -- dropping `if session.exitstatus != 0: return` --
        survived against their real-failure test and against the one above,
        because in both a test had executed and the guard's other conditions
        already stopped it.

        The branch only bites when fixture skips were recorded, **nothing
        executed**, and the run failed anyway: a collection error. pytest exits
        2 there, and without the early exit the guard would overwrite that with
        1 and print a message about missing fixtures over an import that blew
        up.

        Finding it required constructing the case rather than reusing the
        obvious one, which is the general lesson: a mutation that survives
        means the test set is missing a case, not that the code is fine.
        """
        import tempfile

        with tempfile.TemporaryDirectory() as temp:
            result = self._run(
                Path(temp),
                f"""
                import unittest

                class Probe(unittest.TestCase):
                    def test_needs_absent(self):
                        raise unittest.SkipTest("{self.REASON}: a.exe")
                """,
                extra_files={"test_broken.py": 'raise RuntimeError("import blew up")\n'},
            )
            self.assertEqual(
                result.returncode,
                2,
                "a collection error must keep pytest's own exit status"
                + result.stdout[-2000:],
            )
            self.assertIn("import blew up", result.stdout)
            self.assertNotIn(
                "verified nothing",
                result.stdout,
                "the guard must not overwrite a collection error with its own "
                "status and bury the cause",
            )

    def test_a_skip_naming_only_a_basename_is_recognised(self):
        """Tests that skip proactively name the file, not a path.

        The guard's first version keyed on the reason `conftest.py` writes when
        it rewrites a FileNotFoundError. Review found the hole with a
        reproduction: many tests never reach that path, because they check for
        the binary themselves and skip before opening anything --

            if not VV2_EXE.is_file():
                self.skipTest(f"stock executable not available: {VV2_EXE.name}")

        -- so a focused run of exactly the kind of test this guard protects
        still exited 0. That is the defect, inside the fix for it.

        A second version matched the SUBJECT of the phrasing. Surveying the
        suite found 52 distinct skip reasons, of which it caught 16 and missed
        real absences worded differently, so the wording is not usable at all:
        the check now asks whether the named FILE is missing from disk.

        `{VV2_EXE.name}` is a bare basename with no directory, which is why
        the path-based branch alone was not enough and the basenames are read
        from `data/builds.json`.
        """
        import tempfile

        missing = "Virtual Villagers - The Lost Children.exe"
        with tempfile.TemporaryDirectory() as temp:
            result = self._run(
                Path(temp),
                f"""
                import unittest

                class Probe(unittest.TestCase):
                    def test_skips_with_a_bare_basename(self):
                        raise unittest.SkipTest(
                            "stock executable not available: {missing}"
                        )
                """,
            )
            if (ROOT / "research" / "stock-executables" / missing).is_file():
                self.skipTest(
                    "this tree HAS the executable, so the basename is not "
                    "absent and the branch under test cannot fire here"
                )
            self.assertNotEqual(
                result.returncode,
                0,
                "a proactive skip naming an absent game file must be counted"
                + result.stdout[-2000:],
            )
            self.assertIn("verified nothing", result.stdout)

    def test_a_missing_tool_is_not_a_missing_fixture(self):
        """Skips for absent tools must never be counted as fixture skips.

        `requires capstone` and `Tk display is not available` name no fixture
        file, so neither the path branch nor the basename branch can match
        them. That falls out of deciding from the file rather than the
        wording, and it is asserted because widening the check to "any skip"
        is exactly the design that reddened CI on a peer's branch.
        """
        import tempfile

        with tempfile.TemporaryDirectory() as temp:
            result = self._run(
                Path(temp),
                """
                import unittest

                class Probe(unittest.TestCase):
                    def test_needs_capstone(self):
                        raise unittest.SkipTest("requires capstone")

                    def test_needs_a_display(self):
                        raise unittest.SkipTest("Tk display is not available")
                """,
            )
            self.assertEqual(
                result.returncode,
                0,
                "missing tools are not missing inputs"
                + result.stdout[-2000:],
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
