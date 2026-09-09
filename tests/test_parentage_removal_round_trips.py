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


class ParentageRemovalRoundTripTests(unittest.TestCase):
    def test_every_parentage_feature_removes_to_the_image_without_it(self) -> None:
        catalog = patcher.load_fun_patches()
        builds = {build.id: build for build in patcher.load_builds()}
        covered = 0
        expected_cases = 0
        expected_games = 0
        missing_fixtures: list[str] = []

        for game_id, build in builds.items():
            feature_id = f"{game_id}_write_parentage_log"
            if not any(item.id == feature_id for item in catalog):
                continue
            source = ROOT / "research" / "stock-executables" / build.input_name
            expected_games += 1
            if not source.exists():
                missing_fixtures.append(build.input_name)
                continue

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

            for label, requested in (
                ("with-origins", every),
                ("no-origins", without_origins),
            ):
                if feature_id not in requested:
                    continue
                expected_cases += len(MODES)
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
        present_games = expected_games - len(missing_fixtures)
        self.assertGreater(
            present_games, 0, "no parentage feature was discovered at all"
        )
        # Equality against what the loop actually decided to run, not a floor
        # computed from what it was expected to run.
        #
        # This was `covered >= present_games * len(MODES)`, which recomputes
        # the shape independently of the loop and then compares to it. That
        # arithmetic was already wrong: each game contributes TWO selection
        # forms, so real coverage is 30 subtests while the floor demanded 15.
        # Half of it could have disappeared silently.
        #
        # Counting `expected` at the same place the loop commits to a case
        # cannot drift from it, so a game or a form that stops being exercised
        # fails here instead of quietly reducing coverage. Raised by a peer
        # session, whose version of this guard asserted the same identity.
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
