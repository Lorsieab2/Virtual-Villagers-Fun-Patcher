"""Time Warp must quote its cost the way every other upgrade does.

The official confirm wording shows costs comma-formatted, and every other
purchase box in these menus does: they read a pre-formatted string from a table
("50,000", "450,000"). Time Warp's prompt is built by the companion instead of
by the shared purchase box, and in VV3, VV4 and VV5 it printed the cost with
`%d` -- so a player buying Time Warp read "for 50000 tech points" while every
other row in the same menu said "50,000". VV1 and VV2 had always formatted it.

Asserted against the BUILT DLLs, not the C source. Two of these companions are
produced by a route the source edit does not reach on its own:

  * `VVFP VV4 Origins Icons.dll` is built by `build_vv4_origins_icons.ps1`, not
    by the `vv4_full_mastery_candidate` script whose name suggests it;
  * `VVFP VV3 Safe Upgrades.dll` is re-resourced from the VV3 candidate by
    `build_vv3_safe_upgrade_resources.py`, which refuses to run when its pinned
    `SOURCE_SHA256` no longer matches the rebuilt candidate.

Both shipped the old string while the source read correctly, which is exactly
what checking the source instead of the artifact would have missed.

The companion list below is EXPLICIT rather than discovered by searching the
built DLLs for a prompt. An earlier version of this file did the latter, and
review pointed out that it cannot detect the regression it advertises: a DLL
that dropped or rewrote the prompt would simply leave the filtered set, so the
content assertions would never look at it and the "at least one" guard would
still pass on its siblings. A test whose population is defined by the property
under test cannot fail.
"""
from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

RAW = b"Do you want to buy Time Warp for %d tech points?"
FORMATTED = b"Do you want to buy Time Warp for %s tech points?"

# Every built companion that offers a Tech-menu Time Warp row. Each must exist
# and each must carry a formatted prompt; a missing file is a failure, not a
# silent skip.
EXPECTED_COMPANIONS = (
    Path("assets/origins/VVFP VV1 Origins Icons.dll"),
    Path("assets/origins/VVFP VV2 Origins Icons.dll"),
    Path("assets/origins/VVFP VV4 Origins Icons.dll"),
    Path("data/candidates/VVFP VV3 Full Mastery Candidate.dll"),
    Path("data/candidates/VVFP VV3 Safe Upgrades.dll"),
    Path("data/candidates/VVFP VV5 Task9 Origins Icons.dll"),
)


class TimeWarpCostFormattingTests(unittest.TestCase):
    def test_every_expected_companion_is_present(self) -> None:
        """A companion that vanished must fail here rather than be skipped."""
        missing = [str(p) for p in EXPECTED_COMPANIONS if not (ROOT / p).is_file()]
        self.assertEqual(
            missing, [],
            "expected companions are not built, so the assertions below would "
            f"not examine them: {missing}",
        )

    def test_every_expected_companion_still_has_a_time_warp_prompt(self) -> None:
        """The prompt itself must survive.

        This is what stops the suite going quiet: without it, a companion that
        dropped the prompt would satisfy "does not print a raw cost" trivially.
        """
        for rel in EXPECTED_COMPANIONS:
            path = ROOT / rel
            if not path.is_file():
                continue          # already failed above; do not double-report
            with self.subTest(dll=rel.name):
                self.assertIn(
                    b"Do you want to buy Time Warp for", path.read_bytes(),
                    f"{rel.name} no longer carries a Time Warp prompt at all",
                )

    def test_no_companion_prints_a_raw_cost(self) -> None:
        for rel in EXPECTED_COMPANIONS:
            path = ROOT / rel
            if not path.is_file():
                continue
            with self.subTest(dll=rel.name):
                self.assertNotIn(
                    RAW, path.read_bytes(),
                    f"{rel.name} prints the Time Warp cost unformatted, so it "
                    f'reads "for 50000 tech points" while every other row in '
                    f'the same menu reads "50,000"',
                )

    def test_every_companion_prints_a_formatted_cost(self) -> None:
        """Not merely the absence of `%d`: the formatted form must be present."""
        for rel in EXPECTED_COMPANIONS:
            path = ROOT / rel
            if not path.is_file():
                continue
            with self.subTest(dll=rel.name):
                self.assertIn(
                    FORMATTED, path.read_bytes(),
                    f"{rel.name} has a Time Warp prompt that does not quote a "
                    "formatted cost",
                )

    def test_no_other_built_companion_slipped_in_with_a_raw_cost(self) -> None:
        """Catch a companion added later that the explicit list does not name.

        The list above is the guard against silent omission; this is the guard
        against the list going stale.
        """
        for directory in (ROOT / "data" / "candidates", ROOT / "assets" / "origins"):
            if not directory.is_dir():
                continue
            for dll in sorted(directory.glob("*.dll")):
                blob = dll.read_bytes()
                if b"Do you want to buy Time Warp for" not in blob:
                    continue
                rel = dll.relative_to(ROOT)
                with self.subTest(dll=rel.name):
                    self.assertIn(
                        rel, EXPECTED_COMPANIONS,
                        f"{rel} carries a Time Warp prompt but is not in "
                        "EXPECTED_COMPANIONS; add it so it is checked by name",
                    )
                    self.assertNotIn(RAW, blob, f"{rel.name} prints a raw cost")


if __name__ == "__main__":
    unittest.main()
