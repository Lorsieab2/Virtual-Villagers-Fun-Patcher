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

    def test_a_failing_test_is_never_rerun(self):
        with mock.patch.object(ci_run_shard, "run_file", wraps=ci_run_shard.run_file) as spy:
            code, root = self.run_shard({"test_bad.py": FAILS})
        self.assertEqual(code, 1)
        self.assertEqual(spy.call_count, 1)
        self.assertEqual(len([c for c in root.iter("testcase") if c.find("failure") is not None]), 1)


if __name__ == "__main__":
    unittest.main()
