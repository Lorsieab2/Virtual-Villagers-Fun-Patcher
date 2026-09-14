"""Guards for the CI job-summary renderer.

The two properties worth pinning are the two the obvious implementation
gets wrong, and both were observed before this file existed:

* the totals come from the suite attributes, because pytest-subtests folds
  a passing subtest into its parent and emits no element for it, so
  counting elements reported 13 cases for a file that ran 37;
* a failing subtest's parameters come from pytest's terse output, because
  they appear nowhere in the JUnit XML.

Each test therefore asserts against a report shaped like the real thing
rather than against the renderer's own idea of one.
"""

from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "summarise_test_run.py"

# Three functions, thirty-seven cases: the shape pytest-subtests really
# produces, where the suite header counts every subtest but only the
# failing one is emitted as its own element.
REPORT = """<?xml version="1.0" encoding="utf-8"?>
<testsuites>
  <testsuite name="pytest" errors="0" failures="1" skipped="1" tests="37">
    <testcase classname="tests.test_robe.RobeTests" name="test_alpha" />
    <testcase classname="tests.test_robe.RobeTests" name="test_beta">
      <skipped type="pytest.skip" message="needs the stock binaries" />
    </testcase>
    <testcase classname="tests.test_robe.RobeTests" name="test_composition">
      <failure message="AssertionError: 'AAAA' != 'BBBB'">tb</failure>
    </testcase>
  </testsuite>
</testsuites>
"""

TERSE = (
    "=========================== short test summary info "
    "===========================\n"
    "SUBFAILED(mode='collection_progression') "
    "tests/test_robe.py::RobeTests::test_composition\n"
    "1 failed, 12 passed, 1 skipped, 23 subtests passed in 1.26s\n"
)


def run(*args: Path) -> str:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), *[str(a) for a in args]],
        capture_output=True,
        text=True,
        check=False,
    )
    # The renderer must never fail the job it is reporting on.
    assert result.returncode == 0, result.stderr
    return result.stdout


class SummariseTestRunTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(self.enterContext(__import__("tempfile").TemporaryDirectory()))
        self.xml = self.tmp / "junit.xml"
        self.xml.write_text(REPORT, encoding="utf-8")
        self.log = self.tmp / "pytest.log"
        self.log.write_text(TERSE, encoding="utf-8")

    def test_totals_come_from_the_suite_not_the_elements(self) -> None:
        """Counting <testcase> elements would report 3 here, not 37."""
        out = run(self.xml, self.log)
        self.assertIn("37 cases from 3 test functions", out)
        self.assertIn("| Passed | 35 |", out)
        self.assertIn("| Failed | 1 |", out)
        self.assertIn("| Skipped | 1 |", out)
        # 37 counted minus the 3 functions that own a case each.
        self.assertIn("| Subtest cases | 34 |", out)

    def test_failing_subtest_parameters_are_recovered_from_the_terse_log(self) -> None:
        out = run(self.xml, self.log)
        self.assertIn("mode=&#x27;collection_progression&#x27;", out)
        self.assertIn("RobeTests::test_composition", out)

    def test_without_the_terse_log_the_table_still_renders(self) -> None:
        """The parameters are the only thing that degrades."""
        out = run(self.xml)
        self.assertIn("### Failures", out)
        self.assertIn("RobeTests::test_composition", out)
        self.assertNotIn("collection_progression", out)

    def test_a_missing_report_does_not_fail_the_job(self) -> None:
        out = run(self.tmp / "absent.xml")
        self.assertIn("No JUnit report was produced", out)

    def test_a_corrupt_report_does_not_fail_the_job(self) -> None:
        broken = self.tmp / "broken.xml"
        broken.write_text("<testsuites><testsuite>", encoding="utf-8")
        out = run(broken)
        self.assertIn("could not be parsed", out)

    def test_a_green_run_lists_no_failure_table(self) -> None:
        green = self.tmp / "green.xml"
        green.write_text(
            REPORT.replace('failures="1"', 'failures="0"').replace(
                '<failure message="AssertionError: \'AAAA\' != \'BBBB\'">tb</failure>',
                "",
            ),
            encoding="utf-8",
        )
        out = run(green, self.log)
        self.assertIn("All green", out)
        self.assertNotIn("### Failures", out)

    def test_a_pipe_in_a_message_cannot_break_the_table(self) -> None:
        piped = self.tmp / "piped.xml"
        piped.write_text(
            REPORT.replace(
                "AssertionError: 'AAAA' != 'BBBB'",
                "AssertionError: a | b",
            ),
            encoding="utf-8",
        )
        out = run(piped, self.log)
        row = next(line for line in out.splitlines() if "test_composition" in line)
        # Escaped, so the pipe is rendered as text instead of ending the
        # cell. The escape still contains a `|`, so the column count is the
        # four delimiters plus it; what matters is that every delimiter is
        # still where it belongs.
        self.assertIn(r"a \| b", row)
        self.assertTrue(row.startswith("| `"))
        self.assertTrue(row.endswith(" |"))
        self.assertEqual(row.count(" | "), 2)


if __name__ == "__main__":
    unittest.main()
