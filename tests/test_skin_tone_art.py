"""Skin tones: the patcher's own way of making a tone's sheet (src/vv_skin_tone_art.py, Pillow only).

On made-up sheets (no game's art is needed, and none is in the repository):
  * the mask takes the face, the neck's deeper shade and the bare arm, and leaves the hair, the eyes, the
    mouth, the white vest and everything dark;
  * a tone's sheet differs from the sheet only on the mask, keeps every alpha, is nowhere ashy (no skin
    pixel under 70% of the tone's own chroma), keeps the art's shading (a lighter skin pixel stays lighter)
    and runs from light to dark over the ten tones;
  * the files are written under the names "VVFP Skin Tones.dll" looks for, the owner's painted mask and
    marking of each tone's skin wins over the generated mask, and the player's own pictures are not touched;
  * and it is the same method as the development tool's (scripts/skin_tone_preview.py, on numpy): the same
    mask, the same colours to within one level of one channel.
"""
from __future__ import annotations

import sys
import tempfile
import unittest
import unittest.mock
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import vv_skin_tone_art as art  # noqa: E402
import vv_skin_tones as tones  # noqa: E402

try:
    from PIL import Image

    HAVE_PIL = True
except ImportError:  # pragma: no cover
    HAVE_PIL = False

SKIN, SKIN_LIGHT, SKIN_SHADE, NECK = (232, 176, 112), (250, 214, 150), (205, 148, 90), (186, 128, 76)
HAIR, EYE_WHITE, PUPIL, LIPS, VEST, GARMENT = (40, 22, 10), (250, 250, 250), (20, 20, 60), (200, 40, 40), (252, 252, 250), (30, 90, 160)


def head_sheet():
    """7 x 2 cells of 40 x 65: a head in every cell -- dark hair, a shaded face with eyes and a mouth, a neck."""
    w, h = 280, 130
    px = [(0, 0, 0, 0)] * (w * h)

    def box(x0, y0, x1, y1, colour):
        for y in range(y0, y1):
            for x in range(x0, x1):
                px[y * w + x] = colour + (255,)

    for row in range(2):
        for col in range(7):
            ox, oy = col * 40, row * 65
            box(ox + 8, oy + 2, ox + 32, oy + 14, HAIR)
            box(ox + 10, oy + 10, ox + 30, oy + 30, SKIN)
            box(ox + 12, oy + 11, ox + 20, oy + 16, SKIN_LIGHT)
            box(ox + 22, oy + 22, ox + 30, oy + 30, SKIN_SHADE)
            box(ox + 13, oy + 17, ox + 16, oy + 19, EYE_WHITE)
            box(ox + 14, oy + 17, ox + 15, oy + 18, PUPIL)
            box(ox + 17, oy + 25, ox + 22, oy + 27, LIPS)
            box(ox + 16, oy + 30, ox + 24, oy + 34, NECK)
    return w, h, px


def body_sheet():
    """16 x 1 cells of 40 x 65: a white vest, a blue garment, bare arms with a darker forearm."""
    w, h = 640, 65
    px = [(0, 0, 0, 0)] * (w * h)
    for col in range(16):
        ox = col * 40
        for y in range(10, 40):
            for x in range(ox + 12, ox + 28):
                px[y * w + x] = (VEST if y < 25 else GARMENT) + (255,)
            for x in range(ox + 6, ox + 12):
                px[y * w + x] = (SKIN if y < 28 else SKIN_SHADE) + (255,)
    return w, h, px


class Mask(unittest.TestCase):
    def test_a_head(self):
        sheet = head_sheet()
        w, _, px = sheet
        mask = art.skin_mask(sheet, True)
        at = lambda x, y: y * w + x  # noqa: E731
        for name, (x, y), skin in (("face", (15, 22), True), ("highlight", (14, 12), True), ("shade", (25, 26), True),
                                   ("neck", (20, 32), True), ("hair", (20, 5), False), ("eye white", (13, 17), False),
                                   ("pupil", (14, 17), False), ("lips", (19, 26), False), ("nothing", (2, 2), False)):
            with self.subTest(pixel=name):
                self.assertEqual(at(x, y) in mask, skin)
                self.assertEqual(at(x + 40 * 3, y + 65) in mask, skin, "the same in every cell")

    def test_a_body(self):
        sheet = body_sheet()
        w, _, px = sheet
        mask = art.skin_mask(sheet, False)
        self.assertIn(15 * w + 8, mask, "the arm")
        self.assertIn(35 * w + 8, mask, "the darker forearm")
        self.assertNotIn(15 * w + 20, mask, "the white vest")
        self.assertNotIn(35 * w + 20, mask, "the garment")

    def test_the_held_baby_is_one_cell(self):
        w, h = 520, 40
        px = [(0, 0, 0, 0)] * (w * h)
        for cell in (0, 3, 7):                  # the same warm patch in three cells: only the baby's is skin
            for y in range(8, 14):
                for x in range(cell * 40 + 20, cell * 40 + 28):
                    px[y * w + x] = SKIN + (255,)
        mask = art.baby_mask((w, h, px), (40, 40))
        self.assertEqual({i % w // 40 for i in mask}, {3})
        self.assertEqual(len(mask), 48)


class Tones(unittest.TestCase):
    def setUp(self):
        self.sheet = head_sheet()
        self.mask = art.skin_mask(self.sheet, True)

    def test_only_the_skin_changes(self):
        _, _, px = self.sheet
        for tone in tones.TONE_TABLE:
            made = art.recolour(self.sheet, self.mask, tone)
            self.assertEqual(len(made), len(px))
            for i, (before, after) in enumerate(zip(px, made)):
                if i not in self.mask:
                    self.assertEqual(after, before)
                else:
                    self.assertEqual(after[3], before[3])
                    self.assertNotEqual(after[:3], before[:3])

    def test_nothing_ashy(self):
        for tone in tones.TONE_TABLE:
            made = art.recolour(self.sheet, self.mask, tone)
            least = min(art.chroma(*made[i][:3]) for i in self.mask)
            self.assertGreaterEqual(least, 0.70 * tone[3], tone[0])

    def test_the_shading_is_kept(self):
        w = self.sheet[0]
        light, mid, shade = 12 * w + 14, 22 * w + 15, 26 * w + 25
        for tone in tones.TONE_TABLE:
            made = art.recolour(self.sheet, self.mask, tone)
            a, b, c = (art.lightness(*made[i][:3]) for i in (light, mid, shade))
            self.assertGreater(a, b, tone[0])
            self.assertGreater(b, c, tone[0])

    def test_the_tones_run_light_to_dark_and_land_on_their_colour(self):
        w = self.sheet[0]
        mid = 22 * w + 15                       # the face's own colour is the row's middle skin
        seen = []
        for name, text, *_ in tones.TONE_TABLE:
            made = art.recolour(self.sheet, self.mask, next(t for t in tones.TONE_TABLE if t[0] == name))
            want = tuple(int(text[i:i + 2], 16) for i in (1, 3, 5))
            self.assertTrue(all(abs(g - e) <= 1 for g, e in zip(made[mid][:3], want)), (name, made[mid], want))
            seen.append(art.lightness(*made[mid][:3]))
        self.assertEqual(seen, sorted(seen, reverse=True))


@unittest.skipUnless(HAVE_PIL, "Pillow is missing")
class Files(unittest.TestCase):
    def game(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        images = root / "Images"
        images.mkdir()
        w, h, px = head_sheet()
        image = Image.new("RGBA", (w, h))
        image.putdata(px)
        image.save(images / "male_heads.png")
        return root, images, (w, h, px)

    def test_the_sheets_are_written_under_the_dlls_names(self):
        root, images, sheet = self.game()
        before = (images / "male_heads.png").read_bytes()
        written = art.write_tone_sheets(1, images, root / "out", edits=[])
        self.assertEqual(written, [f"vvfp_skin_{n:02d}_male_heads.png" for n in range(1, 11)])
        self.assertEqual((images / "male_heads.png").read_bytes(), before, "the player's own picture is not touched")
        self.assertEqual(sorted(p.name for p in images.iterdir()), ["male_heads.png"])
        with Image.open(root / "out" / "vvfp_skin_05_male_heads.png") as made:
            got = list(made.convert("RGBA").getdata())
        self.assertEqual(got, art.recolour(sheet, art.skin_mask(sheet, True), tones.TONE_TABLE[4]))

    def test_at_patch_time_the_sheets_are_made_once_and_taken_out_with_the_row(self):
        """vv_fun_patcher._write_skin_tone_sheets: made in the patched game's own Images folder from the pictures
        there; a second patch finds them made; without the row they are taken out; the game's own are never touched."""
        root, images, _sheet = self.game()
        (images / "other.png").write_bytes(b"the game's own")
        before = (images / "male_heads.png").read_bytes()
        names = [f"vvfp_skin_{n:02d}_male_heads.png" for n in range(1, 11)]
        self.assertEqual(art.install(1, images, edits=[]), names)
        self.assertEqual(sorted(p.name for p in images.iterdir()), sorted(names + ["male_heads.png", "other.png", art.STAMP]))
        made = {name: (images / name).read_bytes() for name in names}
        self.assertEqual(art.install(1, images, edits=[]), [], "already made from these pictures: nothing to do")
        (images / names[3]).unlink()
        self.assertEqual(art.install(1, images, edits=[]), names, "one is missing: all made again")
        self.assertEqual({name: (images / name).read_bytes() for name in names}, made)
        with Image.open(images / "male_heads.png") as opened:      # the player's own picture changed (another mod)
            changed = opened.convert("RGBA")
        changed.putpixel((15, 22), (200, 150, 110, 255))
        changed.save(images / "male_heads.png")
        self.assertEqual(art.install(1, images, edits=[]), names, "made again from the new picture")
        (images / "male_heads.png").write_bytes(before)
        self.assertEqual(sorted(art.remove(images)), names)
        self.assertEqual(sorted(p.name for p in images.iterdir()), ["male_heads.png", "other.png"])
        self.assertEqual((images / "male_heads.png").read_bytes(), before)
        self.assertEqual(art.remove(images), [])

    def test_the_patcher_makes_them_with_the_row_and_takes_them_out_without_it(self):
        import types
        import vv_fun_patcher as patcher
        root, images, _sheet = self.game()
        row = types.SimpleNamespace(id="vv3_skin_tones", raw={})
        other = types.SimpleNamespace(id="vv3_game_log", raw={})
        calls = []
        with unittest.mock.patch.object(art, "install", lambda game, folder: calls.append((game, folder)) or ["a.png"]):
            patcher._write_skin_tone_sheets(root, [other, row])
        self.assertEqual(calls, [(3, root / "Images")])
        self.assertIn("Made 1 skin tone pictures", patcher.SKIN_TONE_REPORTS[3])
        (images / "vvfp_skin_04_male_heads.png").write_bytes(b"left by an earlier patch")
        patcher._write_skin_tone_sheets(root, [other])
        self.assertEqual(sorted(p.name for p in images.iterdir()), ["male_heads.png"], "not ticked: taken out")

        def broken(_game, _folder):
            raise OSError("disk full")
        with unittest.mock.patch.object(art, "install", broken):
            patcher._write_skin_tone_sheets(root, [row])            # never fails the patch
        self.assertIn("could not be made (disk full)", patcher.SKIN_TONE_REPORTS[3])

    def test_the_owners_marking_of_the_skin_wins(self):
        root, images, sheet = self.game()
        w, h, px = sheet
        edits = root / "edits"
        (edits / "male_heads").mkdir(parents=True)
        mask = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        for y in range(10, 30):                 # the owner: only the first cell's face is skin
            for x in range(10, 30):
                mask.putpixel((x, y), (255, 255, 255, 255))
        mask.save(edits / "male_heads" / "mask.png")
        layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))      # the owner: tone 7 has skin on ONE pixel only,
        layer.putpixel((15, 22), (255, 255, 255, 255))       # and on a hair pixel they painted
        layer.putpixel((20, 5), (255, 255, 255, 255))
        layer.putpixel((2, 2), (255, 255, 255, 255))         # paint off the sprite is nothing
        layer.save(edits / "male_heads" / "skin_07.png")
        art.write_tone_sheets(1, images, root / "out", edits=[edits], tones=[3, 7])
        with Image.open(root / "out" / "vvfp_skin_03_male_heads.png") as made:
            three = list(made.convert("RGBA").getdata())
        changed = {i for i, (a, b) in enumerate(zip(px, three)) if a != b}
        self.assertTrue(changed)
        self.assertTrue(all(10 <= i % w < 30 and 10 <= i // w < 30 for i in changed), "only inside the owner's mask")
        with Image.open(root / "out" / "vvfp_skin_07_male_heads.png") as made:
            seven = list(made.convert("RGBA").getdata())
        marked = {22 * w + 15, 5 * w + 20}
        self.assertEqual({i for i, (a, b) in enumerate(zip(px, seven)) if a != b}, marked,
                         "tone 7 is toned exactly where the owner painted it, on the sprite")
        want = art.recolour(sheet, marked, tones.TONE_TABLE[6])
        self.assertEqual(seven, want, "in the tone's own colours, shaded from the player's own picture")

    def test_a_sheet_the_game_does_not_have_is_skipped(self):
        root, images, _ = self.game()
        self.assertEqual(len(art.write_tone_sheets(4, images, root / "out", edits=[], tones=[1])), 0)

    def test_the_names_are_the_dlls(self):
        source = (ROOT / "native" / "vvfp_skin_tones" / "vvfp_skin_tones.c").read_text(encoding="utf-8")
        self.assertIn('lstrcpyA(name, "vvfp_skin_");', source)
        self.assertEqual(art.installed_name(5, "male_heads00.png"), "vvfp_skin_05_male_heads00.png")


class TheSameAsTheTool(unittest.TestCase):
    def test_mask_and_colours(self):
        try:
            import numpy as np
            sys.path.insert(0, str(ROOT / "scripts"))
            import skin_tone_preview as core
        except ImportError:
            self.skipTest("numpy or scipy is missing (the development tool's own needs)")
        for sheet, heads in ((head_sheet(), True), (body_sheet(), False)):
            w, h, px = sheet
            a = np.array(px, np.uint8).reshape(h, w, 4)
            theirs = core.skin_mask(a, heads) & (a[..., 3] > 0)
            mine = art.skin_mask(sheet, heads)
            self.assertEqual(mine, set(np.flatnonzero(theirs.ravel()).tolist()))
            for n, tone in enumerate(core.TONES):
                ref = core.recolour(a, theirs, tone)
                got = np.array(art.recolour(sheet, mine, tones.TONE_TABLE[n]), np.uint8).reshape(h, w, 4)
                self.assertLessEqual(int(np.abs(got.astype(int) - ref.astype(int)).max()), 1, tone[4])

    def test_the_numbers_are_the_tools(self):
        try:
            sys.path.insert(0, str(ROOT / "scripts"))
            import skin_tone_preview as core
        except ImportError:
            self.skipTest("numpy or scipy is missing (the development tool's own needs)")
        for name in ("CORE", "SHADOW", "HIGHLIGHT", "CAP_MARGIN", "CAP_MIN", "CAP_MAX", "MIN_BLOB", "GROW", "MAX_SHEEN",
                     "EDGE_REACH", "CLOTH_REACH", "BODY_FLOOR", "BLUSH_FLOOR", "ALIKE_STEPS", "ALIKE_HUE", "ALIKE_SAT", "ALIKE_DARKER",
                     "ALIKE_LIGHTER", "L_FLOOR", "L_CEIL", "GIVE", "SHADING", "CHROMA_FLOOR", "SHADOW_CHROMA"):
            with self.subTest(number=name):
                self.assertEqual(getattr(art, name), getattr(core, name))


if __name__ == "__main__":
    unittest.main()
