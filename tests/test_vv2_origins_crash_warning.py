"""A player choosing VV2 Origins must be told about the known crash.

The README has carried the warning for a while, but a player picking patches
in the patcher window never reads the README. The two VV2 Origins descriptions
are what they actually see, so the warning has to be there too.

The crash itself is recorded in docs/origins-player-runtime-checklist.md:
Time Warp and Food Point Doubler crash The Lost Children immediately after
their success dialog, and the `.shr` raw-offset versus virtual-address
confusion found in the VV2 builder is a hard re-enable blocker rather than a
complete explanation. Until that is resolved the rows stay dangerous, and
silence in the chooser reads as permission to use them.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vv_fun_patcher import load_public_fun_patches  # noqa: E402

CHECKLIST = ROOT / "docs" / "origins-player-runtime-checklist.md"
README = ROOT / "README.md"

# The two rows the player must be steered away from.
CRASHING_ROWS = ("Time Warp", "Food Point Doubler")


class VV2OriginsCrashWarningTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.vv2_origins = [
            patch
            for patch in load_public_fun_patches()
            if patch.game_id == "vv2" and "origins" in patch.id
        ]

    def test_the_vv2_origins_patches_are_still_exposed(self) -> None:
        """Guards the rest of the file: no patches means nothing is checked."""
        self.assertTrue(
            self.vv2_origins, "no public VV2 Origins patch was found to check"
        )

    def test_every_exposed_vv2_origins_patch_warns_in_its_description(self) -> None:
        for patch in self.vv2_origins:
            with self.subTest(patch=patch.id):
                description = patch.description or ""
                self.assertIn("KNOWN CRASH", description)
                for row in CRASHING_ROWS:
                    self.assertIn(row, description)

    def test_the_warning_names_the_game_and_tells_the_player_what_to_do(self) -> None:
        for patch in self.vv2_origins:
            with self.subTest(patch=patch.id):
                description = patch.description or ""
                self.assertIn("The Lost Children", description)
                self.assertIn("avoid them", description)

    def test_the_warning_does_not_overstate_the_damage(self) -> None:
        """Unrelated VV2 patches are fine; the warning must say so.

        Scaring a player off every VV2 patch would be its own harm.
        """
        for patch in self.vv2_origins:
            with self.subTest(patch=patch.id):
                self.assertIn("unaffected", patch.description or "")

    def test_no_other_game_picked_up_the_warning(self) -> None:
        """The crash is VV2's; the same text on VV3 would be a false alarm."""
        for patch in load_public_fun_patches():
            if patch.game_id == "vv2":
                continue
            with self.subTest(patch=patch.id):
                self.assertNotIn("KNOWN CRASH", patch.description or "")

    def test_the_underlying_record_still_exists(self) -> None:
        """If the crash is ever fixed, this test should be removed WITH it.

        Pinning the source record means the warning cannot outlive its cause
        silently: deleting the record fails here rather than leaving a stale
        scare in the chooser.
        """
        checklist = CHECKLIST.read_text(encoding="utf-8")
        self.assertIn("VV2 Origins playtest warning", checklist)
        for row in CRASHING_ROWS:
            self.assertIn(row, checklist)

    def test_the_readme_warning_is_still_there_too(self) -> None:
        """Both surfaces, not one instead of the other."""
        readme = README.read_text(encoding="utf-8")
        self.assertIn("The Lost Children: known crash", readme)


if __name__ == "__main__":
    unittest.main()
