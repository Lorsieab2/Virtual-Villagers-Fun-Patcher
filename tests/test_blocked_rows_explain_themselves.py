"""A blocked Barrel/Island row must say WHY, in all five games.

The Tech menu used to draw a blocked Island Event or Barrel of Babies row as a
DISABLED button reading "Unavailable". That is accurate and useless: it tells
the player the upgrade cannot be bought without telling them why, or whether
waiting will help. Worse, a disabled button swallows the click, so there was
nowhere to put an explanation even if one existed.

The row now stays clickable, reads "Why not?", and clicking it shows the
specific reason and closes nothing -- in particular it does NOT reach the
purchase path, so nothing is charged.

Two causes are distinguished, because they ask completely different things of
the player:

  * ALREADY PENDING -- one was bought moments ago and arrives a few seconds
    after the screen closes. Waiting fixes it.
  * NO VILLAGER SLOTS -- the village has no room for the children. Waiting does
    NOT fix it; the player has to act. The text names burial specifically,
    because a dead villager keeps occupying a record until they are buried,
    which is exactly the state that surprises players.

These tests assert against the COMPILED DLLs as well as the sources. A string
present in the C file but absent from the shipped binary would leave the
player with the old behaviour and a green suite.
"""

import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]

# Every game's dialog source. VV2 includes VV1's file, so it has no separate
# copy of the reason table; it is listed for the call sites it does own.
SOURCES = {
    "vv1": "native/vv1_origins_icons/vv1_origins_icons.c",
    "vv2": "native/vv2_origins_icons/vv2_origins_icons.c",
    "vv3": "native/vv3_full_mastery_candidate/vv3_full_mastery_candidate.c",
    "vv4": "native/vv4_origins_icons/vv4_origins_icons.c",
    "vv5": "native/vv5_task9_origins/vv5_task9_origins.c",
}

# The shipped companions. VV3 deploys the same canonical build twice.
DLLS = {
    "vv1": "assets/origins/VVFP VV1 Origins Icons.dll",
    "vv2": "assets/origins/VVFP VV2 Origins Icons.dll",
    "vv3": "data/candidates/VVFP VV3 Full Mastery Candidate.dll",
    "vv3_safe_upgrades": "data/candidates/VVFP VV3 Safe Upgrades.dll",
    "vv4": "assets/origins/VVFP VV4 Origins Icons.dll",
    "vv5": "data/candidates/VVFP VV5 Task9 Origins Icons.dll",
}

BUTTON_LABEL = b"Why not?"
DIALOG_TITLE = b"Not right now"
PENDING_TEXT = b"already been bought and is on its way"
NO_SLOTS_TEXT = b"not enough room in the village for the three children"
BURIAL_HINT = b"buried"
# The wording must not claim EVERY slot is taken: the check is for three free
# records, so with one or two free that would contradict the visible village.
OVERCLAIM = b"Every villager slot is taken"


class BlockedRowsExplainThemselvesTests(unittest.TestCase):
    def test_every_shipped_companion_carries_the_explanations(self):
        """The bytes the player actually runs.

        Checking the C sources alone would pass while the DLL in the release
        still had the old behaviour -- the companions are committed binaries,
        so a source edit without a rebuild is a real and silent failure mode.
        """
        for game, relative in sorted(DLLS.items()):
            path = ROOT / relative
            with self.subTest(game=game):
                self.assertTrue(path.is_file(), f"missing companion: {relative}")
                blob = path.read_bytes()
                for needle in (
                    BUTTON_LABEL,
                    DIALOG_TITLE,
                    PENDING_TEXT,
                    NO_SLOTS_TEXT,
                ):
                    # assertTrue on a membership test, not assertIn: the latter
                    # prints the entire DLL on failure, which buried the real
                    # message under 16MB of hex.
                    self.assertTrue(
                        needle in blob,
                        f"{relative} does not contain {needle!r}. The source "
                        "may have been edited without rebuilding the DLL, in "
                        "which case players keep the old bare 'Unavailable'",
                    )
                self.assertFalse(
                    OVERCLAIM in blob,
                    f"{relative} still claims every villager slot is taken. "
                    "The barrel needs THREE free records, so with one or two "
                    "free that contradicts what the player can see",
                )

    def test_no_shipped_companion_still_disables_these_rows(self):
        """Anti-regression on the mechanism that caused the complaint.

        A disabled button cannot explain itself. If a future edit re-disables
        the row, the reason text would still be present in the binary and the
        test above would pass, so this pins the source side of it.
        """
        pattern = re.compile(
            r"blocked\s*!=\s*(?:VV3_)?BLOCK_NONE\s*\)\s*\{(?P<body>.*?)\n            \}",
            re.S,
        )
        for game, relative in sorted(SOURCES.items()):
            text = (ROOT / relative).read_text(encoding="utf-8", errors="ignore")
            match = pattern.search(text)
            with self.subTest(game=game):
                self.assertIsNotNone(
                    match, f"{relative}: no block-reason branch found"
                )
                body = match.group("body")
                self.assertIn(
                    "TRUE",
                    body,
                    f"{relative}: the blocked row is not left enabled, so the "
                    "click cannot be intercepted and explained",
                )
                self.assertNotIn(
                    "FALSE",
                    body,
                    f"{relative}: the blocked row is disabled again. A "
                    "disabled button swallows the click, which is the whole "
                    "reason 'Unavailable' was unhelpful",
                )

    def test_the_two_causes_are_distinguished(self):
        """One message for both causes would be no better than 'Unavailable'.

        A queued event clears itself; a full village does not. Collapsing them
        would tell a player to wait when waiting cannot help.
        """
        for game in ("vv1", "vv3", "vv4", "vv5"):
            text = (ROOT / SOURCES[game]).read_bytes()
            with self.subTest(game=game):
                self.assertTrue(PENDING_TEXT in text, f"{game}: no pending text")
                self.assertTrue(NO_SLOTS_TEXT in text, f"{game}: no capacity text")

    def test_the_capacity_message_mentions_burial(self):
        """The actionable half.

        A player told only that the village is full has no way to know that
        burying remains frees a slot -- a dead villager keeps their record
        until buried, which is precisely the state that looks like a bug.
        """
        for game, relative in sorted(DLLS.items()):
            blob = (ROOT / relative).read_bytes()
            index = blob.find(NO_SLOTS_TEXT)
            with self.subTest(game=game):
                self.assertGreater(index, 0, f"{relative}: capacity text absent")
                window = blob[index : index + 400]
                self.assertTrue(
                    BURIAL_HINT in window,
                    f"{relative}: the capacity message does not mention "
                    "burial, so it says what is wrong without saying what the "
                    "player can do about it",
                )

    def test_a_blocked_click_cannot_reach_the_purchase(self):
        """The refusal must not charge.

        The handler shows the message and returns TRUE, which keeps the dialog
        open. Falling through to EndDialog would report the row as bought and
        run the purchase path.
        """
        for game, relative in sorted(SOURCES.items()):
            text = (ROOT / relative).read_text(encoding="utf-8", errors="ignore")
            with self.subTest(game=game):
                marker = "MessageBoxA(window,"
                index = text.find(marker, text.find("WM_COMMAND"))
                self.assertGreater(
                    index, 0, f"{relative}: no refusal MessageBoxA in WM_COMMAND"
                )
                after = text[index : index + 400]
                self.assertIn(
                    "return TRUE;",
                    after,
                    f"{relative}: the refusal does not return TRUE, so the "
                    "dialog may fall through to the purchase path and charge "
                    "for an upgrade it just refused",
                )


if __name__ == "__main__":
    unittest.main()
