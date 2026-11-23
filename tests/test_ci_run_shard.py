"""scripts/ci_run_shard.py: each test file in its own pytest process; a native crash re-runs that file once, alone;
a failing test is never re-run; the reports merge into one <testsuites> the summary step reads."""
from __future__ import annotations

import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import ci_run_shard  # noqa: E402

PASSES = "def test_ok():\n    assert True\n"
FAILS = "def test_bad():\n    assert False\n"
# Dies of a native fault the first time only (a marker file beside it), as the CI shards did.
CRASHES_ONCE = """import ctypes, os
from pathlib import Path
MARK = Path(__file__).with_suffix(".crashed")

def test_crash_once():
    if not MARK.exists():
        MARK.write_text("x")
        os._exit(139)
"""
CRASHES_ALWAYS = "import os\n\ndef test_crash():\n    os._exit(139)\n"
# Fails its test the first time only, then dies at interpreter exit (a retry would pass).
FAIL_THEN_CRASH = """import atexit, os
from pathlib import Path
MARK = Path(__file__).with_suffix(".ran")
atexit.register(lambda: os._exit(139))

def test_flaky():
    first = not MARK.exists()
    MARK.write_text("x")
    assert not first
"""
# Passes, writes its report, then dies at interpreter exit -- both times.
CRASHES_AT_EXIT = "import atexit, os\natexit.register(lambda: os._exit(139))\n\ndef test_ok():\n    assert True\n"


# A file whose game-file tests all skip, as tests/conftest.py reports it to the shard (VVFP_FIXTURE_TALLY): six
# fixture skips, nothing run.  On its own such a file is no failure (its session's guard is off).
ALL_SKIP = """import os
import pytest
with open(os.environ["VVFP_FIXTURE_TALLY"], "a") as fh:
    fh.write("6 0\\n")
assert os.environ["VVFP_ALLOW_NO_FIXTURES"] == "1"

@pytest.mark.parametrize("k", range(6))
def test_needs_a_game_file(k):
    pytest.skip("the stock executable is not in this checkout")
"""
RAN = """import os
with open(os.environ["VVFP_FIXTURE_TALLY"], "a") as fh:
    fh.write("0 1\\n")

def test_runs():
    assert True
"""


class TheShardRunner(unittest.TestCase):
    def run_shard(self, sources: dict[str, str]):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            files = []
            for name, text in sources.items():
                (tmp / name).write_text(text, encoding="utf-8")
                files.append(str(tmp / name))
            out = tmp / "junit.xml"
            with mock.patch.object(ci_run_shard.ci_test_shard, "shards", lambda count: [files]), \
                    mock.patch.object(ci_run_shard, "REPO", tmp):
                code = ci_run_shard.main(["0", "1", str(out)])
            root = ET.parse(out).getroot()
            return code, root

    def test_every_file_passes(self):
        code, root = self.run_shard({"test_a.py": PASSES, "test_b.py": PASSES})
        self.assertEqual(code, 0)
        self.assertEqual(root.tag, "testsuites")
        self.assertEqual(len(list(root.iter("testcase"))), 2)

    def test_a_crash_runs_the_file_again_alone(self):
        code, root = self.run_shard({"test_a.py": PASSES, "test_crash.py": CRASHES_ONCE})
        self.assertEqual(code, 0, "crashed once, then passed alone")
        notes = [e.text for e in root.iter("system-out")]
        self.assertTrue(any("crashed once" in (n or "") for n in notes), notes)

    def test_a_crash_twice_fails_with_a_case_naming_the_file(self):
        code, root = self.run_shard({"test_crash.py": CRASHES_ALWAYS, "test_a.py": PASSES})
        self.assertEqual(code, 1)
        errors = [c for c in root.iter("testcase") if c.find("error") is not None]
        self.assertEqual(len(errors), 1)
        self.assertIn("test_crash.py", errors[0].get("classname"))
        self.assertEqual(len(list(root.iter("testcase"))), 2, "the next file still ran")

    def test_a_crash_at_exit_after_a_passing_report_is_an_error(self):
        """Codex, #783: the passing cases are kept and an error case names the file, so the report is never green
        while the shard fails."""
        code, root = self.run_shard({"test_exit.py": CRASHES_AT_EXIT})
        self.assertEqual(code, 1)
        cases = list(root.iter("testcase"))
        self.assertIn("test_ok", [c.get("name") for c in cases], "the completed results are kept")
        errors = [c for c in cases if c.find("error") is not None]
        self.assertEqual(len(errors), 1)
        self.assertIn("test_exit.py", errors[0].get("classname"))

    def test_a_failure_then_a_crash_is_never_forgiven(self):
        """Codex, #783: a retry forgives a crash, never a failure.  This file fails its test the first time (it
        would pass the second), then dies at exit: the file fails, its failure kept, and it is not run again."""
        with mock.patch.object(ci_run_shard, "run_file", wraps=ci_run_shard.run_file) as spy:
            code, root = self.run_shard({"test_fail_exit.py": FAIL_THEN_CRASH})
        self.assertEqual(code, 1)
        self.assertEqual(spy.call_count, 1)
        self.assertEqual(len([c for c in root.iter("testcase") if c.find("failure") is not None]), 1)

    def test_a_file_that_only_skips_is_no_failure_of_its_own(self):
        """Codex, #783: alone, a file whose tests all skip for a missing game file tripped conftest's guard (exit 1).
        The guard now judges the whole shard: it passes when anything else in the shard ran..."""
        code, root = self.run_shard({"test_skips.py": ALL_SKIP, "test_ran.py": RAN})
        self.assertEqual(code, 0)
        self.assertFalse([c for c in root.iter("testcase") if c.find("error") is not None])

    def test_a_shard_that_verified_nothing_fails(self):
        """...and fails, as the single session did, when every game-file test of the shard skipped and nothing
        else ran."""
        with mock.patch.dict("os.environ", {"VVFP_ALLOW_NO_FIXTURES": ""}):
            code, root = self.run_shard({"test_skips.py": ALL_SKIP})
        self.assertEqual(code, 1)
        names = [c.get("name") for c in root.iter("testcase") if c.find("error") is not None]
        self.assertEqual(names, ["verified nothing"])

    def test_a_failing_test_is_never_rerun(self):
        with mock.patch.object(ci_run_shard, "run_file", wraps=ci_run_shard.run_file) as spy:
            code, root = self.run_shard({"test_bad.py": FAILS})
        self.assertEqual(code, 1)
        self.assertEqual(spy.call_count, 1)
        self.assertEqual(len([c for c in root.iter("testcase") if c.find("failure") is not None]), 1)


class FaulthandlerWatchdog(unittest.TestCase):
    """#839: the 10-minute stack dump crashed the process while test_event_collection_files.py's one ~22-minute test
    was deep in vv_cie_graph's recursion; that file's watchdog is past its length, every other file keeps 10 minutes."""

    def test_the_long_file_has_a_longer_watchdog(self):
        with mock.patch.object(ci_run_shard.subprocess, "call", return_value=0) as call:
            ci_run_shard.run_file("tests/test_event_collection_files.py", Path("r.xml"))
            ci_run_shard.run_file("tests/test_other.py", Path("r.xml"))
        first, second = (c.args[0] for c in call.call_args_list)
        self.assertIn("faulthandler_timeout=3600", first)
        self.assertIn("faulthandler_timeout=600", second)
        self.assertEqual(ci_run_shard.faulthandler_timeout("tests\\test_event_collection_files.py"), 3600)

if __name__ == "__main__":
    unittest.main()
