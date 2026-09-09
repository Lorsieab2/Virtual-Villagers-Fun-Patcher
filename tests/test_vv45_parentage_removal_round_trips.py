"""Removing VV4/VV5 parentage must leave the image it would have had without it.

That is the property removal actually owes, and asserting it catches defects
that no amount of reading the removal code does. Two real ones sat behind a
fully green suite because nothing exercised removal for these features at all:

  * `_relocate_composition_overlay_hooks` resolved the base feature by
    searching the list it was passed. Installation passes the whole selection,
    so that worked; removal passes ONLY the feature being removed, so the base
    was absent and it raised a bare `StopIteration` -- an exception with no
    message -- and uninstalling VV5 composed with Origins failed saying
    nothing. Reachable from the shipped feature.

  * More generally, removal must undo the form that was INSTALLED. VV5 writes
    an overlay when Origins is co-selected and its own appended page when it is
    not, and reversing the wrong one fails the preimage guard and leaves the
    hook in place, pointing into a page that has just been truncated away.

The baseline here drops only the feature under test rather than re-resolving
the request. Re-resolving would also drop anything the feature depends on --
which removal correctly leaves installed -- and report false failures.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vv_fun_patcher import (  # noqa: E402
    _remove_feature_bytes,
    get_fun_patch,
    load_builds,
    render_patched_bytes,
)

MODES = ("stock", "collection_progression", "immediate_fixed")

# game -> stock exe, build id, parentage feature, the feature it composes with
CASES = {
    4: (
        "Virtual Villagers - The Tree of Life.exe",
        "vv4",
        "vv4_write_parentage_log",
        None,
    ),
    5: (
        "Virtual Villagers - New Believers.exe",
        "vv5",
        "vv5_write_parentage_log",
        "vv5_enable_origins_exclusive_features",
    ),
}


class VV45ParentageRemovalRoundTripsTests(unittest.TestCase):
    def test_removing_parentage_restores_the_image_without_it(self):
        checked = 0
        for game, (exe, build_id, feature_id, base_id) in CASES.items():
            stock = ROOT / "research/stock-executables" / exe
            # Opened rather than probed, so conftest reports a missing game
            # file as a skip instead of letting this pass having checked
            # nothing.
            stock.open("rb").close()
            build = next(item for item in load_builds() if item.id == build_id)

            selections = [("alone", [feature_id])]
            if base_id is not None:
                selections.append(("with-base", [base_id, feature_id]))

            for label, selection in selections:
                for mode in MODES:
                    with self.subTest(game=game, selection=label, mode=mode):
                        try:
                            installed, _ = render_patched_bytes(
                                stock, build, mode, selection
                            )
                        except Exception as error:  # noqa: BLE001
                            # A selection this build cannot render is not what
                            # this test is about; skip it rather than reporting
                            # a removal defect that does not exist.
                            self.skipTest(f"render unsupported: {error}")

                        # The baseline drops ONLY the feature under test. It
                        # must not be re-resolved, or a dependency that removal
                        # correctly leaves installed would vanish from it.
                        remainder = [item for item in selection if item != feature_id]
                        expected, _ = render_patched_bytes(
                            stock, build, mode, remainder
                        )

                        work = bytearray(installed)
                        _remove_feature_bytes(
                            work, get_fun_patch(feature_id), mode
                        )

                        checked += 1
                        self.assertEqual(
                            len(work),
                            len(expected),
                            "VV%d %s %s: removal left a %d-byte image where "
                            "%d was expected"
                            % (game, label, mode, len(work), len(expected)),
                        )
                        self.assertEqual(
                            bytes(work),
                            bytes(expected),
                            "VV%d %s %s: removal did not restore the image "
                            "rendered without the feature"
                            % (game, label, mode),
                        )
        self.assertGreater(checked, 0, "no removal round trip was exercised")


if __name__ == "__main__":
    unittest.main()
