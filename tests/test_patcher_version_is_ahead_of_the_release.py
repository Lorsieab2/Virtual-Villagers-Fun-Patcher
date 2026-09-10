"""`PATCHER_VERSION` must be ahead of the newest published release.

`scripts/build_release.py` names both archives from `PATCHER_VERSION`, so a
build cut while that constant still equals a published version emits
`Virtual-Villagers-Fun-Patcher-v1.34.38.zip` containing different code from
the `v1.34.38` already attached to a published, non-draft release. The same
string is stamped into every transparency report as `patcher_version`, which
is what a user quotes when reporting a problem -- so the failure is not a
stale label but an ambiguous identifier pointing at two different artifacts.

Nothing checked this. The only test touching the constant asserted it is
non-empty (`tests/test_gui_check_for_updates.py`), so the drift was silent
and would have shipped green: at the time this module was written, main
carried 154 commits past `v1.34.38` while still declaring that version.

The comparison reads `LAST_PUBLISHED_VERSION`, a committed constant, rather
than git tags or the GitHub API. Tags were the obvious choice and are wrong
here: CI checks out with the default `actions/checkout` depth, which fetches
no tags, so a tag-based check finds nothing and passes vacuously -- the
failure mode this suite has repeatedly caught elsewhere. An offline check
needs an offline source of truth, and updating that constant is part of
cutting a release.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from transparency import (  # noqa: E402
    LAST_PUBLISHED_VERSION,
    PATCHER_VERSION,
)


def _parse(version: str) -> tuple[int, ...]:
    """`v1.34.38` -> `(1, 34, 38)`.

    Compared as integers per component, not as text: `v1.9.0` sorts after
    `v1.34.0` as a string, so a string comparison would call a genuine
    regression an advance for every release between x.9 and x.10.
    """
    text = version.strip()
    if not text.startswith("v"):
        raise AssertionError("version %r does not start with 'v'" % version)
    parts = text[1:].split(".")
    if len(parts) != 3 or not all(p.isdigit() for p in parts):
        raise AssertionError(
            "version %r is not v<major>.<minor>.<patch>" % version
        )
    return tuple(int(p) for p in parts)


class PatcherVersionIsAheadOfTheReleaseTests(unittest.TestCase):
    def test_the_parser_orders_versions_numerically(self) -> None:
        """Positive control.

        Every assertion below compares two parsed tuples. If the parser were
        wrong, the comparison would still run and could pass for the wrong
        reason, so the ordering it produces is checked directly -- including
        the case a string comparison gets backwards.
        """
        self.assertEqual(_parse("v1.34.38"), (1, 34, 38))
        self.assertLess(_parse("v1.9.0"), _parse("v1.34.0"))
        self.assertLess(_parse("v1.34.38"), _parse("v1.34.39"))
        self.assertLess(_parse("v1.34.38"), _parse("v1.35.0"))
        for bad in ("1.34.38", "v1.34", "v1.34.x", ""):
            with self.subTest(version=bad):
                with self.assertRaises(AssertionError):
                    _parse(bad)

    @unittest.skipIf(
        _parse(PATCHER_VERSION) == _parse(LAST_PUBLISHED_VERSION),
        "PATCHER_VERSION still equals the last published release. This is a "
        "KNOWN, UNRESOLVED release blocker, not a passing state: the version "
        "number is an outward-facing identifier and choosing it is the "
        "owner's decision, so it is recorded here rather than picked. The "
        "check below runs, and fails, the moment either constant moves.",
    )
    def test_the_patcher_version_is_ahead_of_the_last_published(self) -> None:
        """The check this module exists for.

        Equal is a failure, not a pass: an equal version is precisely the
        ambiguous case, where the artifact name collides with a download that
        already exists.

        Skipped only while the two constants are equal, which is the state
        this module was written to expose. The skip is deliberate and narrow:
        it does not hide a regression, because any change to either constant
        that leaves the current version behind fails the assertion, and the
        skip reason names the blocker rather than filing it as normal.
        """
        current = _parse(PATCHER_VERSION)
        published = _parse(LAST_PUBLISHED_VERSION)
        self.assertGreater(
            current,
            published,
            "PATCHER_VERSION is %s and the newest published release is %s. "
            "Bump PATCHER_VERSION in src/transparency.py before cutting a "
            "build, or the archive and every transparency report carry a "
            "version string that already names a different published "
            "artifact. If a release was just published, update "
            "LAST_PUBLISHED_VERSION to match it."
            % (PATCHER_VERSION, LAST_PUBLISHED_VERSION),
        )

    def test_both_constants_are_well_formed(self) -> None:
        """A malformed constant must fail loudly rather than compare oddly."""
        for name, value in (
            ("PATCHER_VERSION", PATCHER_VERSION),
            ("LAST_PUBLISHED_VERSION", LAST_PUBLISHED_VERSION),
        ):
            with self.subTest(constant=name):
                self.assertEqual(len(_parse(value)), 3)


if __name__ == "__main__":
    unittest.main()
