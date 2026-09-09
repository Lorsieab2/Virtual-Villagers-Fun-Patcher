"""A rewritten skip must survive `-rs`, not just a quiet run.

conftest converts a missing-fixture error into a skip so a checkout without the
games reports absence rather than failure. That rewrite has to produce a report
pytest can actually summarise: `_folded_skips` asserts `longrepr` is a
`(path, lineno, reason)` triple, both type and length.

Setting a bare string produced a correct `-q` run and crashed the terminal
reporter the moment anyone asked for a summary:

    assert isinstance(event.longrepr, tuple)
    AssertionError: (<TestReport ... outcome='skipped'>, 'requires a local ...')

That is worse than a cosmetic bug. `-rs` is how anyone asks *what is this suite
not running* -- the exact question a skip-rewriting hook makes it important to
answer, and the one that goes unanswered if asking crashes. It also hid a real
detail: six tests skip with "Tk display is not available", which fluctuates
between otherwise identical runs, and a peer session read that movement as
evidence an unrelated fix was working.

This pins the shape rather than the wording, so the message can change without
the guard going stale.
"""

from __future__ import annotations

import inspect
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFTEST = ROOT / "tests/conftest.py"


class ConftestSkipSurvivesShortSummaryTests(unittest.TestCase):
    def test_the_rewrite_assigns_a_three_part_longrepr(self):
        # Same reason as below: reduce to counts before asserting, so no
        # failure message can carry a fixture path out of the source.
        match = re.search(
            r"report\.longrepr\s*=\s*\(\s*\n(.*?)\n\s*\)",
            CONFTEST.read_text(encoding="utf-8"),
            re.S,
        )
        self.assertTrue(
            match is not None, "conftest must assign report.longrepr as a tuple"
        )
        parts = [p for p in match.group(1).split("\n") if p.strip().endswith(",")]
        self.assertGreaterEqual(
            len(parts),
            3,
            "longrepr must carry (path, lineno, reason); pytest's "
            "_folded_skips asserts both the tuple type and a length of 3, so "
            "a bare string crashes -rs while leaving -q correct",
        )

    def test_pytest_still_expects_that_shape(self):
        """Pin the assumption to pytest's own source.

        If a future pytest stops requiring the triple, this guard is enforcing
        a shape nothing needs; if it starts requiring something else, the
        rewrite is wrong again and this says so rather than passing quietly.
        """
        from _pytest import terminal

        source = inspect.getsource(terminal._folded_skips)
        self.assertIn("isinstance(event.longrepr, tuple)", source)
        self.assertIn("len(event.longrepr) == 3", source)

    def test_the_line_is_converted_to_one_based(self):
        """report.location is zero-based; a skip summary prints one-based.

        Passing the raw value through reported every rewritten skip one line
        too low, and a test declared on the first line printed as ":0" -- not
        a line at all. The shape guard above cannot see this: the tuple was
        the right length and the right type, and only the VALUE was wrong,
        which is the failure a shape check is blind to by construction.
        """
        # Asserted on a derived boolean, never on the source text itself.
        # unittest embeds the SUBJECT in a failure message, and conftest.py
        # contains research/stock-executables paths in its own FIXTURE_ROOTS
        # -- so a failure whose message carried the file content was matched
        # by the hook under test and rewritten into a SKIP. The guard then
        # could not fail, which is the defect class it exists to catch turned
        # on itself. Observed directly: removing the +1 made this test skip
        # rather than fail until the subject was reduced to a boolean.
        converted = bool(
            re.search(r"lineno\s*\+=\s*1", CONFTEST.read_text(encoding="utf-8"))
        )
        self.assertTrue(
            converted,
            # Deliberately avoids naming a fixture path or the phrase the
            # hook watches for. This test guards that hook, and a failure
            # message it recognises would be rewritten into a skip -- the
            # guard would then be unable to fail, which is exactly the defect
            # class it exists to catch, turned on itself. Observed: an earlier
            # wording mentioning the executables was converted to a skip
            # instead of failing.
            "the zero-based location line must be converted before it reaches "
            "longrepr, or every rewritten entry points one line high",
        )

    def test_the_reason_is_still_carried(self):
        """The triple must not lose the explanation while gaining its shape."""
        carries_reason = (
            "requires a local game file that is gitignored and absent"
            in CONFTEST.read_text(encoding="utf-8")
        )
        self.assertTrue(
            carries_reason,
            "the skip must still say WHY, or a reader cannot tell a missing "
            "input from a disabled test",
        )


if __name__ == "__main__":
    unittest.main()
