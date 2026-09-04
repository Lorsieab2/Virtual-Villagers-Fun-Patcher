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
"""
from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

RAW = b"Do you want to buy Time Warp for %d tech points?"
FORMATTED = b"Do you want to buy Time Warp for %s tech points?"

SEARCH_DIRS = (ROOT / "data" / "candidates", ROOT / "assets" / "origins")


def _companions_with_a_time_warp_prompt():
    """Every built DLL that carries the Time Warp confirmation at all."""
    found = []
    for directory in SEARCH_DIRS:
        if not directory.is_dir():
            continue
        for dll in sorted(directory.glob("*.dll")):
            blob = dll.read_bytes()
            if b"Do you want to buy Time Warp for" in blob:
                found.append((dll, blob))
    return found


class TimeWarpCostFormattingTests(unittest.TestCase):
    def test_at_least_one_companion_is_present_to_check(self) -> None:
        """Guards against this whole file passing because nothing was built."""
        self.assertTrue(
            _companions_with_a_time_warp_prompt(),
            "no built companion carries a Time Warp prompt; this suite would "
            "otherwise pass vacuously",
        )

    def test_no_companion_prints_a_raw_cost(self) -> None:
        for dll, blob in _companions_with_a_time_warp_prompt():
            with self.subTest(dll=dll.name):
                self.assertNotIn(
                    RAW, blob,
                    f"{dll.name} prints the Time Warp cost unformatted, so it "
                    f'reads "for 50000 tech points" while every other row in '
                    f'the same menu reads "50,000"',
                )

    def test_every_companion_prints_a_formatted_cost(self) -> None:
        """Not merely the absence of `%d`: the formatted form must be present.

        A companion that dropped the cost from the prompt entirely would pass
        the check above while telling the player less than before.
        """
        for dll, blob in _companions_with_a_time_warp_prompt():
            with self.subTest(dll=dll.name):
                self.assertIn(
                    FORMATTED, blob,
                    f"{dll.name} has a Time Warp prompt that does not quote a "
                    "formatted cost",
                )


if __name__ == "__main__":
    unittest.main()
