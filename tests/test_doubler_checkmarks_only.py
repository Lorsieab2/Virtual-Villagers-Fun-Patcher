"""Only the two Doublers may show a green checkmark, in every companion.

The requirement is flat: Tech Point Doubler and Food Point Doubler are the only
rows that may display a check, and only while they are owned in the current
save.

Hiding all fourteen badges on WM_INITDIALOG was not enough. The loop that runs
straight afterwards re-shows a badge for every set row-state bit, and the
Details menu deliberately sets bits 0-3 for a villager who already has Youth,
Mastery, Running or the target age -- so those rows kept their checkmarks. The
hide loop and the re-show loop have to agree, and it is the RE-SHOW that decides
what the player sees.

This is checked in every companion source, not just the ones a given change
happened to touch: the same dialog handler is duplicated across the per-game
Origins companions and the optional Full Mastery candidates, and a fix applied
to only some of them leaves the default shipping paths unchanged -- which is
exactly what happened the first time.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NATIVE = ROOT / "native"

SHOW = "ShowWindow(GetDlgItem(window, ID_CHECK_FIRST + row), SW_SHOW);"
# The two Doubler rows, and only outside the villager (Details) menu.
ROW_GUARD = re.compile(r"row\s*==\s*3\s*\|\|\s*row\s*==\s*4")
MENU_GUARD = re.compile(r"!\s*villager_menu")


def _sources() -> list[Path]:
    return sorted(p for p in NATIVE.rglob("*.c") if SHOW in p.read_text(
        encoding="utf-8", errors="replace"))


class DoublerCheckmarksOnlyTests(unittest.TestCase):
    def test_every_badge_show_is_restricted_to_the_doubler_rows(self) -> None:
        sources = _sources()
        # Anti-vacuity: the handler is duplicated across the companions, so a
        # sudden drop in matches means the scan broke, not that the code did.
        self.assertGreaterEqual(
            len(sources), 6,
            f"expected the dialog handler in at least six companions, found "
            f"{len(sources)}",
        )
        total = 0
        for source in sources:
            text = source.read_text(encoding="utf-8", errors="replace")
            for match in re.finditer(re.escape(SHOW), text):
                total += 1
                # The guard must be in the few lines immediately above.
                start = text.rfind("\n", 0, max(0, match.start() - 400))
                window = text[max(0, start) : match.start()]
                with self.subTest(source=source.relative_to(ROOT),
                                  line=text[: match.start()].count("\n") + 1):
                    self.assertRegex(
                        window, ROW_GUARD,
                        "this badge is shown for any satisfied row; only rows 3 "
                        "and 4 (the Doublers) may ever show a checkmark",
                    )
                    self.assertRegex(
                        window, MENU_GUARD,
                        "this badge is shown on the Details menu too; the "
                        "villager rows set state bits 0-3 and would display "
                        "checkmarks for Youth, Mastery, Running and age",
                    )
        self.assertGreaterEqual(total, 7, "too few badge sites examined")

    def test_the_hide_loop_still_covers_every_declared_badge(self) -> None:
        """Restricting the re-show does not license shrinking the hide loop.

        The resource creates the badges VISIBLE, so a row that is never hidden
        shows a checkmark permanently regardless of what the re-show loop does.
        """
        hide = "ShowWindow(GetDlgItem(window, ID_CHECK_FIRST + row), SW_HIDE);"
        checked = 0
        for source in _sources():
            text = source.read_text(encoding="utf-8", errors="replace")
            for match in re.finditer(re.escape(hide), text):
                start = text.rfind("for (", 0, match.start())
                header = text[start : match.start()]
                checked += 1
                with self.subTest(source=source.relative_to(ROOT)):
                    self.assertRegex(
                        header, r"row\s*<\s*(?:14|row_count)",
                        "the hide loop must cover every badge the dialog "
                        "declares, or the uncovered rows stay visible",
                    )
        self.assertGreaterEqual(checked, 6, "no hide loops were examined")


if __name__ == "__main__":
    unittest.main()
