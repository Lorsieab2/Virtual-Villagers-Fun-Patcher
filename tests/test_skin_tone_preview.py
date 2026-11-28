"""The Skin Tones preview (src/vv_skin_tone_preview.py): a woman and a man, adults, in each of the ten tones, made from
the player's own game pictures (the owner, 2026-11-28).  A made-up game folder stands in for a real one here: no
game art is in the repository."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from PIL import Image  # noqa: E402

import vv_skin_tone_preview as preview  # noqa: E402
import vv_skin_tones  # noqa: E402


def _sheet(cols: int, rows: int) -> Image.Image:
    """A sheet of 40 x 65 cells, each a warm skin-coloured face or body with a dark outline and a blue patch."""
    image = Image.new("RGBA", (cols * 40, rows * 65), (0, 0, 0, 0))
    for c in range(cols):
        for r in range(rows):
            x, y = c * 40, r * 65
            for dx in range(10, 30):
                for dy in range(10, 55):
                    shade = 200 + (dx + dy) % 30
                    image.putpixel((x + dx, y + dy), (shade, int(shade * 0.75), int(shade * 0.55), 255))
            for dx in range(10, 30):
                image.putpixel((x + dx, y + 10), (20, 20, 20, 255))
            for dx in range(14, 20):
                for dy in range(40, 46):
                    image.putpixel((x + dx, y + dy), (30, 60, 200, 255))
    return image


class Preview(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.images = Path(cls.tmp.name) / "Game" / "Images"
        cls.images.mkdir(parents=True)
        for sex in ("male", "female"):
            _sheet(8, 12).save(cls.images / f"{sex}_heads.png")
            _sheet(16, 10).save(cls.images / f"{sex}_bodies00.png")
        cls.figures = preview.figures(3, cls.images, edits=[])

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_a_woman_and_a_man_in_every_tone(self):
        self.assertEqual(list(self.figures), ["Woman", "Man"])
        for row in self.figures.values():
            self.assertEqual(len(row), 1 + vv_skin_tones.TONE_COUNT, "the game's own, then each tone")
            self.assertTrue(all(fig.size == preview.FIGURE for fig in row))

    def test_the_change_appearance_frame(self):
        """The head's front-facing column over the body's standing frame, the head 4 pixels above the body."""
        self.assertEqual((preview.HEAD_COL, preview.BODY_COL), (5, 8))
        body = Image.open(self.images / "female_bodies00.png").crop((8 * 40, 3 * 65, 9 * 40, 4 * 65))
        head = Image.open(self.images / "female_heads.png").crop((5 * 40, 10 * 65, 6 * 40, 11 * 65))
        own = Image.new("RGBA", preview.FIGURE, (0, 0, 0, 0))
        own.alpha_composite(body.convert("RGBA"), (2, 6))
        own.alpha_composite(head.convert("RGBA"), (2, 2))
        self.assertEqual(list(self.figures["Woman"][0].getdata()), list(own.getdata()))

    def test_only_skin_changes_and_tones_differ(self):
        own = list(self.figures["Man"][0].getdata())
        made = [list(fig.getdata()) for fig in self.figures["Man"][1:]]
        for tone in made:
            for a, b in zip(own, tone):
                self.assertEqual(a[3], b[3], "the outline of the figure is the game's own")
                if a[:3] in ((20, 20, 20), (30, 60, 200)):
                    self.assertEqual(a, b, "outlines and clothes keep the game's own colours")
        self.assertEqual(len({tuple(tone) for tone in map(tuple, made)}), vv_skin_tones.TONE_COUNT)

    def test_the_picture(self):
        picture = preview.preview(3, self.images, zoom=1, edits=[])
        self.assertEqual(picture.mode, "RGBA")
        self.assertGreaterEqual(picture.width, 10 * preview.FIGURE[0])
        self.assertGreaterEqual(picture.height, 2 * preview.FIGURE[1])

    def test_the_images_folder_is_found_from_a_game_folder(self):
        self.assertEqual(preview.images_folder(3, [Path(self.tmp.name) / "nowhere", self.images.parent]), self.images)
        self.assertIsNone(preview.images_folder(3, [Path(self.tmp.name) / "nowhere"]))

    def test_the_gui_knows_which_guide_gets_it(self):
        sys.path.insert(0, str(ROOT / "src"))
        try:
            import vv_fun_patcher_gui as gui
        except Exception as exc:                # noqa: BLE001 -- no Tk here
            self.skipTest(f"the window cannot be imported: {exc}")
        self.assertEqual(gui.skin_tones_preview_game("patch:vv4_skin_tones"), 4)
        self.assertIsNone(gui.skin_tones_preview_game("patch:vv4_unicode_font"))
        self.assertIsNone(gui.skin_tones_preview_game("skin_tone_preferred"))


if __name__ == "__main__":
    unittest.main()
