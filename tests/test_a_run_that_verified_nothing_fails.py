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

A skip is recognised from the DISK, never from its wording, by three branches:
a reason quoting a fixture path, a reason quoting only a declared basename,
and -- for a class-level `@unittest.skipUnless` decorator, which never runs a
body and so quotes neither -- a fixture Path in the test module's own globals
that is not there. The last is what makes a fourteenth decorator with a brand
new phrasing covered on the day it is written.

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
    def _run(
        self, tmp: Path, body: str, env_extra=None, extra_files=None, imports=None
    ):
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
        if imports:
            # Put the named modules into the subprocess's sys.modules without
            # contributing any test, by importing them from the probe conftest.
            with open(
                tmp / "tests" / "conftest.py", "a", encoding="utf-8"
            ) as handle:
                for name in imports:
                    handle.write(f"\nimport {name}  # noqa: E402,F401\n")
        env = dict(os.environ)
        env.pop("VVFP_ALLOW_NO_FIXTURES", None)
        env["PYTHONPATH"] = str(tmp / "tests")
        if env_extra:
            env.update(env_extra)
        selection = (
            ["tests"] if (extra_files and not imports) else ["tests/test_probe.py"]
        )
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

    def test_a_class_level_decorator_skip_is_seen(self):
        """The case no reason-reading branch can reach.

        Thirteen files gate a whole class on a module-level path:

            @unittest.skipUnless(STOCK.is_file(), "requires the VV4 stock exe")
            class VV4SlotGuardCounterTests(unittest.TestCase):

        The body never runs, nothing raises, no file is opened, and the reason
        names neither a path nor a basename -- so the rewrite hook has no
        exception and both reason branches correctly decline it. A focused run
        of such a test exited 0 with the guard installed, which review reported
        with a real node.

        The probe below reproduces the shape rather than importing the real
        test, so it fails for the mechanism rather than for whichever file
        happens to carry a decorator today.

        Note the probe's `STOCK` points INSIDE a fixture root. A Path elsewhere
        must not count, or every skip in a module that merely holds some
        missing path would be treated as a missing game input.
        """
        import tempfile

        with tempfile.TemporaryDirectory() as temp:
            tmp = Path(temp)
            (tmp / "research" / "stock-executables").mkdir(parents=True)
            result = self._run(
                tmp,
                """
                import unittest
                from pathlib import Path

                ROOT = Path(__file__).resolve().parents[1]
                STOCK = ROOT / "research" / "stock-executables" / "Absent.exe"

                @unittest.skipUnless(STOCK.is_file(), "requires the stock exe")
                class Gated(unittest.TestCase):
                    def test_needs_the_binary(self):
                        self.assertTrue(True)
                """,
            )
            self.assertNotEqual(
                result.returncode,
                0,
                "a class-level decorator skip for an absent fixture must not "
                "exit 0" + result.stdout[-2000:],
            )
            self.assertIn("verified nothing", result.stdout)

    def test_a_decorator_skip_for_a_present_file_is_ignored(self):
        """The negative control for the branch above.

        The module-globals branch decides from the disk, so a module whose
        fixture paths all exist has skipped for some other reason and must not
        be counted. Without this, the branch could degrade into "any skip in a
        module that mentions a Path", which is the over-reporting failure the
        reason branches were carefully built to avoid.
        """
        import tempfile

        with tempfile.TemporaryDirectory() as temp:
            tmp = Path(temp)
            root = tmp / "research" / "stock-executables"
            root.mkdir(parents=True)
            (root / "Present.exe").write_bytes(b"stub")
            result = self._run(
                tmp,
                """
                import unittest
                from pathlib import Path

                ROOT = Path(__file__).resolve().parents[1]
                STOCK = ROOT / "research" / "stock-executables" / "Present.exe"

                # Names STOCK, so the condition gate admits it and the
                # exists() check is what must decline. `is_dir()` is
                # false for a file, so this skips while STOCK exists.
                @unittest.skipUnless(STOCK.is_dir(), "unrelated reason")
                class Gated(unittest.TestCase):
                    def test_skipped_for_another_cause(self):
                        self.assertTrue(True)
                """,
            )
            self.assertEqual(
                result.returncode,
                0,
                "a skip in a module whose fixtures are all present is not a "
                "missing-input run" + result.stdout[-2000:],
            )

    def test_a_tool_skip_is_not_blamed_on_another_modules_fixture(self):
        """The module-globals branch must read the REPORTING module only.

        Found by mutation: deleting the `Path(file).name != name` filter left
        every other test here green, so the filter looked like tidiness. It is
        not. With it removed, a module that skips for a missing TOOL is
        attributed to some *other* module's absent fixture Path, and a run that
        should be green exits 1:

            with the name match     exit=0
            WITHOUT the name match  exit=1, banner shown

        That is the over-reporting direction, which costs other people time and
        looks like diligence while doing it -- the failure the reason branches
        were built to avoid, reintroduced by the branch that fixed the
        under-reporting one.

        Reaching it needed a run where NOTHING executes: any executed test
        keeps the guard silent regardless, which is why the first four
        mutations could not see the difference.
        """
        import tempfile

        with tempfile.TemporaryDirectory() as temp:
            tmp = Path(temp)
            result = self._run(
                tmp,
                """
                import unittest

                @unittest.skipUnless(False, "requires capstone")
                class ToolGated(unittest.TestCase):
                    def test_needs_a_tool(self):
                        self.assertTrue(True)
                """,
                extra_files={
                    # A sibling holding an absent fixture Path and contributing
                    # NO executed test. If it ran one, the guard would stay
                    # silent for that reason instead and this would pass
                    # whatever the branch does -- which is exactly how the
                    # first version of this test failed to catch the mutation.
                    "sibling_holder.py": (
                        "from pathlib import Path\n"
                        "\n"
                        "ROOT = Path(__file__).resolve().parents[1]\n"
                        "STOCK = (\n"
                        '    ROOT / "research" / "stock-executables" / "Absent.exe"\n'
                        ")\n"
                    ),
                },
                imports=["sibling_holder"],
            )
            self.assertEqual(
                result.returncode,
                0,
                "a tool skip must not be attributed to another module's "
                "missing fixture" + result.stdout[-2000:],
            )
            self.assertNotIn("verified nothing", result.stdout)

    def test_an_absent_path_outside_the_fixture_roots_is_ignored(self):
        """Only Paths under a fixture root count as a missing game input.

        Also found by mutation: replacing the root test with `True` left every
        other test green. Without it, ANY absent Path in the module's globals
        counts -- an output directory not yet created, a temp file, a
        scratch artefact -- and a skip for any reason at all in such a module
        reddens the run.

        That is the same over-reporting direction as the sibling-module case,
        reached by a different route, and both were invisible until the
        mutation was run. Two negative controls for one branch, because the
        branch has two independent ways to say yes too often.
        """
        import tempfile

        with tempfile.TemporaryDirectory() as temp:
            tmp = Path(temp)
            result = self._run(
                tmp,
                """
                import unittest
                from pathlib import Path

                ROOT = Path(__file__).resolve().parents[1]
                # Absent, but NOT under a fixture root.
                SCRATCH = ROOT / "build" / "not-made-yet.bin"

                # Names SCRATCH, so the condition gate admits it and the
                # fixture-root restriction is what must decline.
                @unittest.skipUnless(SCRATCH.is_file(), "unrelated reason")
                class Gated(unittest.TestCase):
                    def test_skipped_for_another_cause(self):
                        self.assertTrue(True)
                """,
            )
            self.assertEqual(
                result.returncode,
                0,
                "an absent path outside the fixture roots is not a missing "
                "game input" + result.stdout[-2000:],
            )
            self.assertNotIn("verified nothing", result.stdout)

    def test_a_bare_skip_in_a_module_holding_a_fixture_path_is_ignored(self):
        """A file retired for an unrelated reason must not demand game files.

        Review found this as a regression against main, and it is the third
        over-reporting hole in the same branch:

            tests/test_vv2_origins_playtest_feature.py
                STOCK = ROOT / "research" / "stock-executables"
                @unittest.skip("superseded by the current ... tests")

            on the fix   10 skipped, exit 1, "Link the game files into ..."
            on main      10 skipped, exit 0

        A file skipped as **superseded**, with no fixture condition anywhere,
        was told to link game files and failed the run. Two files did it.

        That is worse than the under-reporting bug being fixed. A guard that
        cries wolf on a legitimate configuration teaches people to set
        VVFP_ALLOW_NO_FIXTURES=1 permanently, which restores the original
        blindness with extra steps -- the same trap that sank a peer's
        competing guard earlier.

        The cause was inferring the dependency instead of observing it:
        "this module mentions an absent fixture Path" is not "this skip
        happened because of one". The condition of the decorator that actually
        caused the skip is now parsed, and only the globals it names are
        consulted.
        """
        import tempfile

        with tempfile.TemporaryDirectory() as temp:
            result = self._run(
                Path(temp),
                """
                import unittest
                from pathlib import Path

                ROOT = Path(__file__).resolve().parents[1]
                # Declared, absent, and irrelevant to why this file skips.
                STOCK = ROOT / "research" / "stock-executables" / "Absent.exe"

                @unittest.skip("superseded by newer tests")
                class Retired(unittest.TestCase):
                    def test_not_run_any_more(self):
                        self.assertTrue(True)
                """,
            )
            self.assertEqual(
                result.returncode,
                0,
                "a file skipped for an unrelated reason must not be treated "
                "as a missing-input run" + result.stdout[-2000:],
            )
            self.assertNotIn("verified nothing", result.stdout)

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
