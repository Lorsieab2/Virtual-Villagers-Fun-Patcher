"""Picture Studio's Text tab: src/vv_glyph_maker.py makes the characters a game font lacks.

* Segmentation into extended grapheme clusters (decomposed accents, ZWJ emoji, skin tones, flag pairs,
  tag flags, keycaps, Hangul jamo, CR LF) and emoji detection run everywhere.
* Rendering runs only where Windows' GDI is available (skipped elsewhere): Latin at the cap height,
  other scripts, colour emoji as one glyph, the sheet's alpha levels, the outline.

No font file or game art is used: only the fonts Windows already has.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import vv_glyph_maker as gm  # noqa: E402


def u(*cps: int) -> str:
    return "".join(map(chr, cps))


ZWJ, VS16, VS15 = u(0x200D), u(0xFE0F), u(0xFE0E)
FAMILY = u(0x1F468) + ZWJ + u(0x1F469) + ZWJ + u(0x1F467) + ZWJ + u(0x1F466)
THUMB = u(0x1F44D, 0x1F3FD)
ENGLAND = u(0x1F3F4, 0xE0067, 0xE0062, 0xE0065, 0xE006E, 0xE0067, 0xE007F)
KEYCAP = "1" + VS16 + u(0x20E3)
JP, FR = u(0x1F1EF, 0x1F1F5), u(0x1F1EB, 0x1F1F7)
HEART = u(0x2764)
LEVELS = (0, 36, 73, 109, 146, 182, 219, 255)


def style(**over) -> gm.GlyphStyle:
    base = dict(line_height=16, baseline=12, cap_height=9, x_height=7, fill=(255, 255, 255), outline=None,
                outline_width=0, alpha_levels=LEVELS, face="Arial", bold=True)
    base.update(over)
    return gm.GlyphStyle(**base)


class Segmentation(unittest.TestCase):
    def test_decomposed_accent_is_one_cluster(self):
        self.assertEqual(gm.segment("e" + u(0x301) + "x"), ["e" + u(0x301), "x"])

    def test_zwj_family_is_one_cluster(self):
        self.assertEqual(gm.segment("a" + FAMILY + "b"), ["a", FAMILY, "b"])

    def test_skin_tone(self):
        self.assertEqual(gm.segment(THUMB + THUMB), [THUMB, THUMB])

    def test_flags_pair_up(self):
        self.assertEqual(gm.segment(JP + FR), [JP, FR])
        self.assertEqual(gm.segment(JP + FR[0]), [JP, FR[0]])

    def test_tag_flag(self):
        self.assertEqual(gm.segment(ENGLAND + "!"), [ENGLAND, "!"])

    def test_keycap(self):
        self.assertEqual(gm.segment(KEYCAP + "2"), [KEYCAP, "2"])

    def test_variation_selector(self):
        self.assertEqual(gm.segment(HEART + VS16 + HEART + VS15), [HEART + VS16, HEART + VS15])

    def test_hangul_jamo(self):
        han = u(0x1112, 0x1161, 0x11AB)                 # L V T: one syllable
        self.assertEqual(gm.segment(han + u(0x1100, 0x1161)), [han, u(0x1100, 0x1161)])
        self.assertEqual(gm.segment(u(0xAC00, 0x11A8, 0xAC00)), [u(0xAC00, 0x11A8), u(0xAC00)])  # LV T | LV

    def test_crlf_and_newline(self):
        self.assertEqual(gm.segment("a\r\nb\nc"), ["a", "\r\n", "b", "\n", "c"])

    def test_devanagari_conjunct(self):
        ksha = u(0x0915, 0x094D, 0x0937)
        self.assertEqual(gm.segment(ksha + "a"), [ksha, "a"])

    def test_is_emoji(self):
        for c in (THUMB, FAMILY, JP, ENGLAND, KEYCAP, u(0x1F600), HEART + VS16):
            self.assertTrue(gm.is_emoji(c), repr(c))
        for c in ("a", "1", u(0x2713), HEART, HEART + VS15, u(0xE9), u(0x4E2D)):
            self.assertFalse(gm.is_emoji(c), repr(c))


@unittest.skipUnless(gm.available(), "needs Windows GDI")
class Rendering(unittest.TestCase):
    def test_latin_letter_at_cap_height(self):
        st = style()
        g = gm.render_cluster("H", st)
        self.assertIsNotNone(g)
        self.assertEqual(g.kind, "system")
        box = g.image.bbox()
        self.assertIsNotNone(box)
        self.assertLessEqual(abs((box[3] - box[1]) - st.cap_height), 1)
        self.assertEqual(g.top + box[3], st.baseline)          # sits on the baseline
        self.assertGreater(g.advance, 0)

    def test_other_scripts_render(self):
        for cp in (0xDF, 0x3A9, 0x4E2D, 0x905, 0x628, 0x2713, 0xD55C, 0xE44):
            g = gm.render_cluster(chr(cp), style())
            self.assertIsNotNone(g, hex(cp))
            self.assertIsNotNone(g.image.bbox(), hex(cp))
            self.assertEqual(g.kind, "system")

    def test_space_and_newline(self):
        g = gm.render_cluster(" ", style())
        self.assertIsNotNone(g)
        self.assertGreater(g.advance, 0)
        self.assertIsNone(gm.render_cluster("\n", style()))

    def test_alpha_levels(self):
        for c in ("a", u(0x3A9), u(0x4E2D)):
            g = gm.render_cluster(c, style())
            alphas = set(g.image.data[3::4])
            self.assertTrue(alphas <= set(LEVELS), (c, alphas - set(LEVELS)))

    def test_outline(self):
        st = style(outline=(0, 0, 0), outline_width=2, alpha_levels=None, bold=False)
        g = gm.render_cluster("O", st)
        plain = gm.render_cluster("O", style(alpha_levels=None, bold=False))
        d = g.image.data
        dark = sum(1 for k in range(0, len(d), 4) if d[k + 3] > 128 and d[k] < 60)
        self.assertGreater(dark, 10)
        self.assertEqual(g.image.width, plain.image.width + 4)

    def test_emoji_in_colour(self):
        g = gm.render_cluster(THUMB, style())
        self.assertIsNotNone(g)
        self.assertEqual(g.kind, "emoji")
        self.assertTrue(g.colour)
        d = g.image.data
        colours = {bytes(d[k:k + 3]) for k in range(0, len(d), 4) if d[k + 3] == 255}
        self.assertGreater(len(colours), 3)
        self.assertLessEqual(abs(g.image.height - style().line_height), 3)

    def test_family_is_one_glyph(self):
        single = gm.render_cluster(u(0x1F468), style())
        g = gm.render_cluster(FAMILY, style())
        self.assertEqual(g.kind, "emoji")
        self.assertLessEqual(g.advance, single.advance + 2)
        self.assertLessEqual(g.image.width, single.image.width + 3)
        self.assertEqual(len(gm.shape_emoji(THUMB)), 1)

    def test_keycap_and_tag_flag(self):
        self.assertEqual(len(gm.shape_emoji(KEYCAP)), 1)
        self.assertEqual(len(gm.shape_emoji(ENGLAND)), 1)
        self.assertEqual(gm.render_cluster(KEYCAP, style()).kind, "emoji")

    def test_marks(self):
        st = style()
        base = gm.render_cluster("E", st)
        box = (base.left, base.top, base.left + base.image.width, base.top + base.image.height)
        above = gm.render_mark(u(0x301), st, box)
        self.assertIsNotNone(above)
        self.assertEqual(above.advance, 0)
        self.assertLess(above.top + above.image.height, box[1])
        below = gm.render_mark(u(0x327), st, box)
        self.assertGreaterEqual(below.top, st.baseline)
        over = gm.render_mark(u(0x338), st, box)
        self.assertLess(over.top, box[3])
        self.assertGreater(over.top + over.image.height, box[1])
        self.assertTrue(set(above.image.data[3::4]) <= set(LEVELS))

    def test_fallback_face(self):
        g = gm.render_cluster(u(0x4E2D), style())
        self.assertNotEqual(g.face.casefold(), "arial")

    def test_missing_face_falls_back(self):
        g = gm.render_cluster("A", style(face="No Such Font 123"))
        self.assertIsNotNone(g)
        self.assertFalse(gm.font_installed("No Such Font 123"))

    def test_ttf_text(self):
        lh, bl = gm.ttf_metrics("Arial", 40)
        self.assertGreater(lh, bl)
        g = gm.render_ttf_text("Arial", 40, "H", (255, 0, 0))
        self.assertIsNotNone(g)
        box = g.image.bbox()
        self.assertEqual(g.top + box[3], bl)
        self.assertEqual(g.image.pixel(box[0] + 1, box[1] + 5)[:3], (255, 0, 0))
        self.assertGreater(len(set(g.image.data[3::4])), 3)        # antialiased

    def test_cached_results_are_copies(self):
        a = gm.render_cluster("Q", style())
        a.image.data[:] = bytes(len(a.image.data))
        b = gm.render_cluster("Q", style())
        self.assertIsNotNone(b.image.bbox())


class NotWindows(unittest.TestCase):
    def test_degrades_without_gdi(self):
        saved = list(gm._API)
        gm._API[:] = [None]
        gm.clear_cache()
        try:
            self.assertFalse(gm.available())
            self.assertIsNone(gm.render_cluster("A", style()))
            self.assertIsNone(gm.render_mark(u(0x301), style(), (0, 0, 5, 9)))
            self.assertIsNone(gm.render_ttf_text("Arial", 20, "A"))
            self.assertIsNone(gm.ttf_metrics("Arial", 20))
            self.assertFalse(gm.font_installed("Arial"))
        finally:
            gm._API[:] = saved
            gm.clear_cache()


if __name__ == "__main__":
    unittest.main()
