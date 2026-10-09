"""The Family Tree Maker remembers its look (the owner, 2026-10-08: "Save the player's settings on
close and reopen (portrait shape/any other changes)"): a new tree starts with the look last used,
never with another village's own things."""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import vv_family_tree as ft  # noqa: E402


class RememberedLookTests(unittest.TestCase):
    def test_the_look_carries_and_the_village_does_not(self) -> None:
        edits = ft.Edits()
        edits.shapes = dict(edits.shapes, Male="heart")
        edits.background = "#123456"
        edits.text_wrap = 30
        edits.marks = {"Runner": "#00ff00"}
        edits.title = "The Kalahuna Tribe"
        edits.words = {"key": "my words"}
        edits.stickers = [{"kind": "picture", "picture": "game:logo1.png", "cx": 1.0, "cy": 2.0, "w": 3.0,
                           "h": 4.0, "angle": 0.0, "flip_h": False, "flip_v": False, "opacity": 100}]
        style = json.loads(json.dumps(ft.style_of(edits)))         # as the settings file keeps it
        self.assertNotIn("title", style)
        self.assertNotIn("stickers", style)
        new = ft.styled(style)
        self.assertEqual(new.shapes["Male"], "heart")
        self.assertEqual((new.background, new.text_wrap, new.marks), ("#123456", 30, {"Runner": "#00ff00"}))
        self.assertEqual((new.title, new.words, new.stickers), ("", {}, []))

    def test_nothing_or_damage_gives_the_patchers_own(self) -> None:
        self.assertEqual(ft.styled(None).to_data(), ft.Edits().to_data())
        self.assertEqual(ft.styled({"text_wrap": "lots"}).to_data(), ft.Edits().to_data())
        self.assertEqual(ft.styled({"entries": {"x|1|1": {}}}).to_data(), ft.Edits().to_data())

    def test_every_style_key_is_an_edits_field(self) -> None:
        self.assertTrue(set(ft.STYLE_KEYS) <= set(ft.Edits().to_data()))


if __name__ == "__main__":
    unittest.main()
