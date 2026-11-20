"""Minimal Detail keeps one short Sources line, and lines that used to say "Not counted" are no longer hidden as
explanations (the owner, 2026-11-18, the Game Mechanics "nothing withheld" audit, Part B).  Each check fails on #796
alone, which hid the whole Sources group and every "Not counted" line."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import vv_game_mechanics as gm  # noqa: E402

EXE = r"C:\Games\Virtual Villagers - A New Home\Virtual Villagers - A New Home.exe"


def page(*sources: str) -> list[gm.Fact]:
    return ([gm.Fact(gm.GROUPS[0], "Food in storage: 1,234.", gm.SAVE)]
            + [gm.Fact(gm.SOURCES, text, gm.SAVE) for text in sources]
            + [gm.Fact("Village counts", "Not counted: 3 potions brewed by hand.", gm.SAVE)])


class SourcesLine(unittest.TestCase):
    def test_read_from_the_patchers_log(self) -> None:
        short = gm.minimum(page("The save: x.ldw, last written now.",
                                f"The patches in the game: {EXE}, as listed by the patcher's log of the run that "
                                "made it (2026-11-18 UTC)."))
        sources = [f.text for f in short if f.group == gm.SOURCES]
        self.assertEqual(sources, ["Sources: Virtual Villagers - A New Home.exe; its patch list read from the "
                                   "patcher's log of the run that made it."])

    def test_read_from_the_exes_bytes(self) -> None:
        short = gm.minimum(page(f"The patches in the game: {EXE}, read from its own bytes (no patcher log matches "
                                "it); a patch the exe does not show is given as not known."))
        self.assertEqual([f.text for f in short if f.group == gm.SOURCES],
                         ["Sources: Virtual Villagers - A New Home.exe; its patch list read from its own bytes (no "
                          "patcher log matches it)."])

    def test_a_warning_when_the_patches_could_not_be_told(self) -> None:
        short = gm.minimum(page("Could not tell which patches this game has: no game folder holding "
                                "Virtual Villagers - A New Home.exe was found."))
        (line,) = [f.text for f in short if f.group == gm.SOURCES]
        self.assertTrue(line.startswith("Warning: Could not tell which patches this game has"), line)
        self.assertIn(gm.BROWSE_HINT, line)

    def test_the_line_sits_in_the_sources_place(self) -> None:
        short = gm.minimum(page("Could not tell which patches this game has: x."))
        self.assertEqual([f.group for f in short], [gm.GROUPS[0], gm.SOURCES, "Village counts"])

    def test_not_counted_is_no_longer_an_explanation(self) -> None:
        short = gm.minimum(page())
        self.assertIn("Not counted: 3 potions brewed by hand.", [f.text for f in short])


if __name__ == "__main__":
    unittest.main()
