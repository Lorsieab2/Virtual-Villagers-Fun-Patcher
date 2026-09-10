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
# An allow-list is a two-way door: it suppresses signal in both directions, so
# an entry that stops being true keeps hiding whatever replaces it. Each is
# therefore recorded with what it is exempt FOR, and a test below asserts every
# one is still there for that reason.
#
# `runner` and `runner~1` are the CI machine's own directory and its 8.3 short
# form; the short spelling is the subject of the conftest tests rather than an
# incidental mention. The placeholders already stand in for an account name.
# `someone` is this module's own pattern control, which is tracked and so is
# scanned like any other file -- excusing the file wholesale is the weakness
# this test was rewritten to avoid.
IMPERSONAL_ACCOUNTS = {
    # The CI runner's directory only ever appears in its 8.3 short form, which
    # is the whole point of those tests -- the runner hands back `RUNNER~1`
    # while `resolve()` returns the long name. Writing the witness down forced
    # this correction: the first draft claimed plain `runner` was in
    # conftest.py, and it is not.
    b"runner~1": "tests/conftest.py",
    b"someone": "tests/test_archive_has_no_personal_paths.py",
}

# Deliberately NOT listed above: `runner`, `<u>`, `<user>`, `username`. They
# are the conventional spellings a placeholder might use, and an earlier draft
# carried them mapped to None so this module could "say they are absent on
# purpose". That reintroduced the hole the mapping exists to close: a dormant
# entry is an unconditional exemption, so a tracked file acquiring a real
# path under \Users\username would be waved through on dictionary
# membership alone. Verified by probe -- with those entries present, exactly
# that path passed.
#
# An account earns an exemption by having a witness, not by looking
# impersonal. If a placeholder is genuinely needed later, add it together
# with the file that uses it, and the staleness check keeps it honest from
# that moment on.

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

    def test_every_exemption_is_still_exempt_for_something(self) -> None:
        """An allow-list entry that stops being true starts hiding things.

        Each exemption names the file it exists for. If that file no longer
        carries the account name -- renamed, rewritten, deleted -- the entry is
        stale, and a stale entry silently excuses whatever takes its place. So
        the exemption has to keep earning itself.

        Every entry must have a witness. An exemption with nothing to point
        at is unconditional, and an unconditional exemption for a plausible
        account name -- `username`, say -- would wave through the very
        disclosure this module exists to catch.
        """
        for account, witness in sorted(IMPERSONAL_ACCOUNTS.items()):
            with self.subTest(account=account.decode()):
                path = ROOT / witness
                self.assertTrue(
                    path.is_file(),
                    f"{witness} is gone, so the {account.decode()!r} exemption "
                    f"no longer has a reason",
                )
                blob = path.read_bytes()
                found = {
                    m.group(1).lower() for m in PERSONAL.finditer(blob)
                }
                self.assertIn(
                    account,
                    found,
                    f"{witness} no longer contains {account.decode()!r}, so "
                    f"that exemption is stale and would now only hide things",
                )

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
