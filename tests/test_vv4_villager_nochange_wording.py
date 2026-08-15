"""OFFICIAL no-change wording for the VV4 Villager (details) upgrade menu.

The source of truth is "OFFICIAL Origins Upgrade Prompts.xlsx". A detail upgrade
that would change nothing must stay clickable and report its exact no-change
line, charging no tech points -- rather than being greyed out as "Done". These
are source-string checks on the Origins Icons DLL (no C compiler required), the
same way the payload builder's wording is pinned.
"""

import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
ICONS_SOURCE = ROOT / "native" / "vv4_origins_icons" / "vv4_origins_icons.c"


class TestVV4VillagerNoChangeWording(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = ICONS_SOURCE.read_text(encoding="utf-8")
        # Collapse C adjacent-string-literal concatenation ("a " "b" -> "a b")
        # so a wording line split across source lines still matches verbatim.
        cls.joined = re.sub(r'"\s+"', "", cls.source)

    def test_official_no_change_lines_present(self) -> None:
        for line in (
            "This villager is already full of youth. "
            "No tech points have been deducted.",
            "This villager is already fully mastered. "
            "No tech points have been deducted.",
            "This villager already likes Running. "
            "No tech points have been deducted.",
            "This villager already has full Likes slots. "
            "Running can not be added.",
            "No changes were needed. "
            "No tech points have been deducted.",
        ):
            self.assertIn(line, self.joined)

    def test_no_change_click_stays_in_menu(self) -> None:
        # The interception must report the line and return without charging or
        # ending the dialog with a purchasable row.
        self.assertIn("g_villager_mask", self.source)
        self.assertIn("return TRUE; /* Stay in the menu; nothing was purchased. */",
                      self.source)

    def test_villager_rows_are_no_longer_greyed_out(self) -> None:
        # The old behaviour disabled satisfied villager rows with a "Done" label;
        # that indicator must be gone so the no-change wording is reachable.
        self.assertNotIn('"Done"', self.source)


if __name__ == "__main__":
    unittest.main()
