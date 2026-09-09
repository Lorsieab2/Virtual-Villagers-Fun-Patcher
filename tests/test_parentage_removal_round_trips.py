"""Removing a parentage feature must restore the image without it.

Two defects motivated this, both of which shipped past a fully green suite
because nothing exercised removal for these features at all.

`_remove_feature_bytes` reverses a feature's ordinary patches. A feature that
declares `composition_patches` or a `composition_overlays` entry is installed
from a DIFFERENT set when its named base is co-selected, so removal was
checking the standalone bytes against an image carrying the relocated ones,
failing the preimage guard, and leaving the feature installed:

    Removal guard failed for vv1_write_parentage_log at 0x56900

VV1 and VV2 parentage could not be uninstalled at all in that composition, and
VV3's overlay form raised StopIteration with no message, because the helper
that swaps in the relocated hooks looked its base feature up in the list it was
passed -- and removal is handed only the feature being removed.

The property asserted here is the one removal actually owes: after removing a
feature, the bytes must equal the image rendered without it. Anything weaker
(that removal merely does not raise, or that some offsets were restored) passes
while leaving a half-uninstalled executable.

Both installed forms are covered, because they are separate code paths and
only one of them was broken for VV3.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import vv_fun_patcher as patcher  # noqa: E402


ORIGINS_SUFFIXES = (
    "_enable_origins_exclusive_features",
    "_origins_village_wide_upgrades",
)
MODES = ("stock", "collection_progression", "immediate_fixed")

# The two installed forms every parentage feature must be exercised in. Named
# here rather than built inline so the expected case count can be computed from
# a constant the loop does not control.
#
# That distinction is the whole point: an expectation the loop computes shrinks
# whenever the loop runs less, so both sides of the final equality fall together
# and the guard passes while coverage collapses. Deriving it from
# len(SELECTION_FORMS) * len(MODES) instead means a form or a mode that stops
# being run fails loudly.
SELECTION_FORM_LABELS = ("with-origins", "no-origins")


def SELECTION_FORMS(every, without_origins):
    return tuple(zip(SELECTION_FORM_LABELS, (every, without_origins)))


class ParentageRemovalRoundTripTests(unittest.TestCase):
    def test_every_parentage_feature_removes_to_the_image_without_it(self) -> None:
        catalog = patcher.load_fun_patches()
        builds = {build.id: build for build in patcher.load_builds()}
        covered = 0
        present_games = 0
        missing_fixtures: list[str] = []

        for game_id, build in builds.items():
            feature_id = f"{game_id}_write_parentage_log"
            source = ROOT / "research" / "stock-executables" / build.input_name
            if not source.exists():
                missing_fixtures.append(build.input_name)
                continue
            # Counted for every game whose executable is present, BEFORE the
            # catalog is consulted. Deriving it after that check let a feature
            # vanishing from the catalog remove its cases from both sides of
            # the equality at once, so the whole game disappeared and the guard
            # still passed -- which is the exact collapse it exists to catch.
            present_games += 1
            self.assertTrue(
                any(item.id == feature_id for item in catalog),
                f"{feature_id} is missing from the catalog; every game with a "
                "stock executable must ship a parentage feature",
            )

            feature = patcher.get_fun_patch(feature_id)
            every = [
                item.id
                for item in catalog
                if item.game_id == game_id and "candidate" not in item.id
            ]
            without_origins = [
                item
                for item in every
                if not item.endswith(ORIGINS_SUFFIXES)
            ]

            for label, requested in SELECTION_FORMS(every, without_origins):
                self.assertIn(
                    feature_id,
                    requested,
                    f"{feature_id} is absent from the {label} selection, so "
                    "that form would silently stop being exercised",
                )
                # Resolve dependencies exactly as a real run does.  VV2's
                # parentage requires its Origins feature, so a request that
                # omits Origins still installs it -- and removal leaves it
                # installed, which is why the baseline drops only the feature
                # being removed rather than re-resolving the request.
                selected = patcher.resolve_fun_patch_ids(requested, game_id=game_id)
                baseline = [item for item in selected if item != feature_id]

                for mode in MODES:
                    with self.subTest(game=game_id, selection=label, mode=mode):
                        installed, _ = patcher.render_patched_bytes(
                            source, build, mode, selected
                        )
                        expected, _ = patcher.render_patched_bytes(
                            source, build, mode, baseline
                        )
                        work = bytearray(installed)
                        patcher._remove_feature_bytes(work, feature, mode)
                        self.assertEqual(
                            bytes(work),
                            bytes(expected),
                            f"{feature_id} removal did not restore the image "
                            f"rendered without it ({label}, {mode})",
                        )
                        covered += 1

        # The stock executables are gitignored, so a clean checkout has none of
        # them and this test legitimately covers nothing. That must SKIP rather
        # than fail -- but it must skip only for that reason.
        #
        # The distinction matters: a bare "covered == 0 -> skip" would also
        # swallow the case this assertion exists to catch, where the fixtures
        # are present and the features have been renamed or dropped out of the
        # catalog. So absence is decided from the fixtures themselves, and any
        # game whose executable IS present must contribute its subtests.
        if missing_fixtures and not covered:
            self.skipTest(
                "stock executables are unavailable: "
                + ", ".join(sorted(missing_fixtures))
            )
        # present_games is already the count of games whose executable was
        # found -- the loop skips the others before incrementing it, so
        # subtracting missing_fixtures here would remove them twice.
        self.assertGreater(
            present_games, 0, "no parentage feature was discovered at all"
        )
        # The expectation is computed from CONSTANTS and the count of available
        # games, never from anything the loop decided.
        #
        # This assertion has now been wrong twice in opposite directions, and
        # the two failures are worth keeping because they are the same mistake:
        #
        #   `covered >= present_games * len(MODES)` recomputed the shape from
        #   the outside and got it wrong -- each game runs TWO selection forms,
        #   so it demanded 15 where the real number is 30, and half the
        #   coverage could vanish unnoticed.
        #
        #   Counting at the point the loop commits to a case fixed the
        #   arithmetic but tied the expectation to the loop, so a case the loop
        #   stopped running was subtracted from BOTH sides and the equality
        #   still held. A whole game disappearing passed.
        #
        # An expectation is only a check if the thing being checked cannot
        # move it. So: len(SELECTION_FORM_LABELS) * len(MODES) per available
        # game, with the loop asserting separately that every form really does
        # include the feature and every game with an executable really does
        # have one.
        expected_cases = present_games * len(SELECTION_FORM_LABELS) * len(MODES)
        self.assertEqual(
            covered,
            expected_cases,
            "parentage removal coverage collapsed: "
            f"{covered} of {expected_cases} cases ran across {present_games} "
            "available games",
        )


    def test_an_alternate_patch_set_is_distinguishable_from_the_default(self) -> None:
        """Removal identifies the installed form by reading the image back.

        It concludes "the alternate is installed" when every one of that
        alternate's patches is present at its own offset. That test is only
        sound while each alternate writes to at least one offset the ordinary
        set never touches -- otherwise an ordinary install whose bytes happen
        to coincide would be misread as an overlay install, and removal would
        reverse the wrong set.

        Today both declaring features satisfy this by a wide margin, because
        the alternate relocates the payload to a different page. Nothing
        enforced it, though, so a future feature whose alternate differed only
        in a hook's rel32 -- at the same offsets -- would silently break the
        detection with no test to notice.
        """
        checked = 0
        for feature in patcher.load_fun_patches():
            compositions = feature.raw.get("composition_patches")
            if not isinstance(compositions, dict):
                continue
            ordinary = {int(patch["offset"], 0) for patch in feature.patches}
            for base_id, alternate in compositions.items():
                with self.subTest(feature=feature.id, base=base_id):
                    self.assertIsInstance(alternate, list)
                    self.assertTrue(alternate)
                    alternate_offsets = {
                        int(patch["offset"], 0) for patch in alternate
                    }
                    self.assertTrue(
                        alternate_offsets - ordinary,
                        f"{feature.id}'s alternate set for {base_id} writes "
                        "only to offsets the ordinary set also writes, so "
                        "removal cannot tell which form is installed",
                    )
                    checked += 1
        self.assertGreater(
            checked, 0, "no composition_patches declaration was found to check"
        )


if __name__ == "__main__":
    unittest.main()
