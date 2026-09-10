"""No tracked file may name somebody's home directory.

`scripts/build_release.py` packages the source release with `git archive HEAD`,
which ships **every tracked file** -- not the curated `FILES` list used for the
binary bundle. So a hardcoded path under a user profile does not merely look
untidy in the repository: it is published, and it discloses the account name
and often the folder layout around it.

This has happened twice. A pytest JUnit report was committed by a bulk `add`
and carried a machine hostname; and six hardcoded paths under one account sat
in two authoring scripts and a test default, one of them a scratch directory
whose name embedded a session identifier. Both were found by sweeping before a
release, which works exactly as often as somebody remembers to sweep.

The pattern deliberately accepts **both slash shapes**. Four of those six used
forward slashes, and two independent sweeps that searched only for backslashes
each reported the tree as nearly clean. A checker that models one spelling
reports every other spelling as absent.

What is allowed is enumerated rather than guessed, because "looks like a real
path" is not a property that can be tested. Each exemption below names why it
is not a disclosure: a CI runner's own directory, a toolchain location, a
synthetic fixture, or a placeholder that already stands in for the account
name.
"""

from __future__ import annotations

import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# A user-profile path in either spelling. The account name is captured so the
# failure can say whose it is; that is the disclosure, not the prefix.
PERSONAL = re.compile(
    rb"[A-Za-z]:[\\/]{1,2}Users[\\/]{1,2}([A-Za-z0-9._~-]+)",
    re.IGNORECASE,
)

# Account names that are not a person's: CI's own runner directory, and the
# 8.3 short form of it. Both appear deliberately in the conftest tests, where
# the short spelling is the thing under test -- the CI runner hands back
# `RUNNER~1` while `resolve()` returns the long name, and the fixture-skip
# logic has to match either.
IMPERSONAL_ACCOUNTS = {
    b"runner",
    b"runner~1",
    b"<u>",
    b"<user>",
    b"username",
    # This module's own pattern control uses a synthetic account. It is
    # tracked, so the scan sees it -- and should, since excusing the file
    # wholesale is the weakness this test was rewritten to avoid.
    b"someone",
}

# Deliberately NOT a set of exempt files. An earlier draft of this test
# excused whole files, and a probe showed the cost: adding a real leak to an
# excused file passed silently. The account name is what discloses, so that is
# what is judged -- IMPERSONAL_ACCOUNTS above -- and no file is trusted
# wholesale.

# Files git tracks but that are not text worth scanning. Binary assets can
# contain any byte sequence; a false positive inside a PNG or an .xcf is not a
# leak, and decoding them as text is meaningless.
BINARY_SUFFIXES = {
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico", ".xcf",
    ".dll", ".exe", ".obj", ".lib", ".zip", ".ogg", ".wav",
}


def _tracked_files() -> list[str]:
    out = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=ROOT,
        capture_output=True,
        check=True,
    ).stdout
    return [p.decode("utf-8") for p in out.split(b"\0") if p]


class ArchiveHasNoPersonalPathsTests(unittest.TestCase):
    def test_the_enumeration_finds_the_repository(self) -> None:
        """A positive control on the scan itself.

        An empty file list would make every assertion below pass while
        checking nothing -- the failure mode this project keeps meeting, where
        a green result is a fact about the instrument rather than the artefact.
        """
        files = _tracked_files()
        self.assertGreater(len(files), 400, "git ls-files returned too few files")
        self.assertIn("scripts/build_release.py", files)

    def test_the_pattern_matches_both_slash_shapes(self) -> None:
        """A positive control on the pattern.

        The defect that motivated this test used forward slashes and survived
        two sweeps that only looked for backslashes.
        """
        for spelling in (
            rb"C:\Users\Someone\Downloads",
            rb"C:/Users/Someone/Downloads",
            rb"c:\\Users\\Someone",
        ):
            with self.subTest(spelling=spelling):
                match = PERSONAL.search(spelling)
                self.assertIsNotNone(match, "pattern missed a real spelling")
                self.assertEqual(match.group(1).lower(), b"someone")

    def test_no_tracked_file_names_a_home_directory(self) -> None:
        offenders: list[str] = []
        for rel in _tracked_files():
            if Path(rel).suffix.lower() in BINARY_SUFFIXES:
                continue
            path = ROOT / rel
            try:
                blob = path.read_bytes()
            except OSError:
                # Tracked but absent from the working tree; git archive would
                # take it from HEAD, and a checkout that lacks it cannot be
                # inspected here.
                continue
            for match in PERSONAL.finditer(blob):
                if match.group(1).lower() in IMPERSONAL_ACCOUNTS:
                    continue
                quoted = match.group(0).decode("utf-8", "replace")
                offenders.append(f"{rel}: {quoted}")
        self.assertEqual(
            offenders,
            [],
            "`git archive HEAD` ships every tracked file, so these publish "
            "an account name: "
            + "; ".join(offenders),
        )


if __name__ == "__main__":
    unittest.main()
