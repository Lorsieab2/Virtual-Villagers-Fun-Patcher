"""Title-case choice labels keep proper nouns as they are (scripts/collection_lib.py LABEL_PROPER_NOUNS), and the More
Island Events events' own choice labels are in Title Case (the owner, 2026-11-15: titles and choices in Title Case)."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))
import collection_lib as lib  # noqa: E402


class ProperNouns(unittest.TestCase):
    def test_kept_in_their_own_form(self):
        self.assertEqual(lib.title_case_label("ask the golden child"), "Ask the Golden Child")
        self.assertEqual(lib.title_case_label("climb the tree of life"), "Climb the Tree of Life")
        self.assertEqual(lib.title_case_label("sing for the guardians of isola"), "Sing for the Guardians of Isola")
        self.assertEqual(lib.title_case_label("tell the tribal chief"), "Tell the Tribal Chief")

    def test_game_words_are_never_cased(self):
        self.assertEqual(lib.title_case_label("ask the {@chief} and the isolans"), "Ask the {@chief} and the Isolans")

    def test_more_island_events_labels_are_title_case(self):
        import vv_aspiring_adventurer, vv_cave_explorers, vv_diving_for_treasure, vv_mysterious_mask  # noqa: E401
        import vv_playful_dolphins, vv_the_climb, vv_troubling_signs  # noqa: E401
        for module in (vv_aspiring_adventurer, vv_cave_explorers, vv_diving_for_treasure, vv_mysterious_mask,
                       vv_playful_dolphins, vv_the_climb, vv_troubling_signs):
            for key, text in module.TEXTS:
                if key.startswith("LABEL_"):
                    with self.subTest(module=module.__name__, key=key):
                        self.assertEqual(text, lib.title_case_label(text))


if __name__ == "__main__":
    unittest.main()
