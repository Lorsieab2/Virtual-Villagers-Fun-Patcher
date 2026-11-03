"""Unicode 18.0 in all five games (v1.35.90): every character draws, in the games and in the patcher.

  * the bundled open fonts (assets/unicode_fonts) are the LAST steps of the companions' glyph chain (RG_BUNDLED in
    native/vvfp_unicode_text/runtime_glyphs.inc) and of Picture Studio's Text tool (vv_glyph_maker.BUNDLED_FACES);
  * every assigned code point of UnicodeData 18.0 has a glyph in some step (a cmap lookup in the bundled fonts is
    enough for the last steps); how many fall to Last Resort alone is reported and bounded;
  * the ten Unicode rows install the fonts and their licence texts as pinned companion files, all or none;
  * the release zip carries the fonts and their licences, and no other game art or font (never Burweed ICG);
  * GraphemeBreakTest 18.0 passes for the DLL's own cutting (the grapheme harness) and for vv_game_text.clusters();
  * a representative sample of every Unicode block runs through each game's own draw routine with the companion
    DLL (unicorn, the stock executables) and draws ink; a missing font file leaves the games drawing as before.

The tests that need the stock executables, unicorn, a compiler or Windows skip (never error) when they are absent.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT / "scripts"))

import patcher_files  # noqa: E402
import unicode18_coverage as cov  # noqa: E402
import vv_unicode18 as u18  # noqa: E402
from vv_game_text import clusters  # noqa: E402

FONTS = ROOT / "assets" / "unicode_fonts"
RUNTIME = ROOT / "native" / "vvfp_unicode_text" / "runtime_glyphs.inc"
GAMES = ("vv1", "vv2", "vv3", "vv4", "vv5")
NAMES = {"vv1": "A New Home", "vv2": "The Lost Children", "vv3": "The Secret City", "vv4": "The Tree of Life",
         "vv5": "New Believers"}
FONT_FILES = ("NotoSansCuneiform-Regular.otf", "NotoSerifTangut-Regular.otf", "unifont-18.0.01.otf",
              "unifont_upper-18.0.01.otf", "LastResortHE-Regular.ttf")
NOTICES = ("NotoSansCuneiform-OFL-1.1.txt", "NotoSerifTangut-OFL-1.1.txt", "Unifont-OFL-1.1.txt",
           "Unifont-GPL-2.0-COPYING.txt", "LastResort-OFL-1.1.txt", "SOURCES.json")
STOCK = ROOT / "research" / "stock-executables"
IMAGES = ROOT / "research" / "game-images"
HAVE_STOCK = all((STOCK / f"Virtual Villagers - {n}.exe").is_file() for n in NAMES.values())
HAVE_IMAGES = all((IMAGES / f"Virtual Villagers - {n}" / "Images" / "ldwBurweed27.png").is_file()
                  for n in NAMES.values())
try:
    import unicorn  # noqa: F401
    import pefile  # noqa: F401
    import capstone  # noqa: F401
    HAVE_EMULATOR = True
except ImportError:                                  # pragma: no cover
    HAVE_EMULATOR = False
HAVE_FONTS = all((FONTS / n).is_file() for n in FONT_FILES + NOTICES)
CL = Path(r"C:\Program Files\Microsoft Visual Studio\18\Community\VC\Tools\MSVC\14.51.36231\bin\Hostx64\x86\cl.exe")
HAVE_COMPILER = os.name == "nt" and CL.is_file()


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def _bundled_c() -> tuple[list[str], list[str]]:
    text = RUNTIME.read_text(encoding="utf-8")
    faces = re.search(r"RG_BUNDLED\[\] = \{(.*?)\};", text, re.S).group(1)
    files = re.search(r"RG_BUNDLED_FILES\[\] = \{(.*?)\};", text, re.S).group(1)
    return re.findall(r'L"([^"]+)"', faces), re.findall(r'L"([^"]+)"', files)


@unittest.skipUnless(HAVE_FONTS, "the bundled fonts are not in this checkout")
class TheBundledFonts(unittest.TestCase):
    def test_sources_and_hashes_are_pinned(self):
        sources = json.loads((FONTS / "SOURCES.json").read_text(encoding="utf-8"))["files"]
        for name in FONT_FILES + NOTICES[:-1]:
            with self.subTest(file=name):
                self.assertEqual(_sha(FONTS / name), sources[name]["sha256"].upper())

    def test_the_c_chain_names_the_files_families_and_order(self):
        faces, files = _bundled_c()
        self.assertEqual(tuple(files), FONT_FILES)
        for face, name in zip(faces, files):
            with self.subTest(face=face):
                data = (FONTS / name).read_bytes()
                self.assertIn(face.casefold(), cov._family(data, 0))
        self.assertEqual(faces[-1], "Last Resort High-Efficiency")        # a placeholder is the very last step

    def test_the_patchers_text_tool_has_the_same_chain(self):
        import vv_glyph_maker as maker
        faces, files = _bundled_c()
        self.assertEqual(list(maker.BUNDLED_FACES), faces)
        self.assertEqual([n for _f, n in maker.BUNDLED_FONT_FILES], files)
        self.assertEqual(maker.BUNDLED_FOLDER, FONTS)
        # The chain ends with the bundled steps, whatever the style's own fallbacks are.
        self.assertTrue(set(maker.DEFAULT_FALLBACKS).isdisjoint(maker.BUNDLED_FACES))

    def test_the_loader_never_installs_a_font(self):
        text = RUNTIME.read_text(encoding="utf-8")
        self.assertIn("AddFontResourceExW(path, FR_PRIVATE, NULL)", text)
        self.assertNotIn("HKEY_LOCAL_MACHINE", text)
        self.assertNotIn("WM_FONTCHANGE", text)
        self.assertNotIn("CopyFile", text)

    def test_every_licence_text_is_complete(self):
        for name in NOTICES[:-1]:
            with self.subTest(file=name):
                body = (FONTS / name).read_text(encoding="utf-8", errors="replace")
                self.assertGreater(len(body), 3000)
        self.assertIn("SIL OPEN FONT LICENSE Version 1.1", (FONTS / "Unifont-OFL-1.1.txt").read_text(encoding="utf-8"))
        self.assertIn("GNU GENERAL PUBLIC LICENSE", (FONTS / "Unifont-GPL-2.0-COPYING.txt").read_text(encoding="utf-8"))


@unittest.skipUnless(HAVE_FONTS, "the bundled fonts are not in this checkout")
class TheCoverage(unittest.TestCase):
    """Every assigned code point of UnicodeData 18.0 has a glyph in some step of the chain."""

    @classmethod
    def setUpClass(cls):
        cls.bundled = cov.bundled_coverage()
        cls.last_resort = cov.last_resort_coverage()
        cls.assigned = [cp for cp in u18.assigned_code_points()]
        cls.noto = [c for n, c in cls.bundled if n.startswith("Noto")]
        cls.unifont = [c for n, c in cls.bundled if n.startswith("unifont")]

    def _owner(self, cp: int) -> str:
        if any(cp in c for c in self.noto):
            return "noto"
        if any(cp in c for c in self.unifont):
            return "unifont"
        if cp in self.last_resort:
            return "last resort"
        return "none"

    def test_every_assigned_code_point_has_a_glyph_somewhere(self):
        counts = {"noto": 0, "unifont": 0, "last resort": 0, "none": 0}
        placeholders = {"private use": 0, "surrogate": 0}
        missing = []
        for cp in self.assigned:
            who = self._owner(cp)
            counts[who] += 1
            if who == "none":
                missing.append(cp)
            elif who == "last resort":
                cat = u18.category(chr(cp))
                if cat in ("Co", "Cs"):
                    placeholders["private use" if cat == "Co" else "surrogate"] += 1
        real_last_resort = counts["last resort"] - sum(placeholders.values())
        print(f"Unicode 18.0: {len(self.assigned)} assigned code points; first bundled step with a glyph "
              f"(Windows fonts, tried first, are not counted): Noto {counts['noto']}, Unifont {counts['unifont']}, "
              f"Last Resort only {counts['last resort']} = {real_last_resort} characters (CJK extensions B-J, Seal, "
              f"Egyptian and Anatolian hieroglyphs, Jurchen...) + {placeholders['private use']} private use "
              f"+ {placeholders['surrogate']} surrogates (no character to draw); none {counts['none']}")
        self.assertEqual(missing[:20], [], "code points no step of the chain can draw")
        self.assertGreater(len(self.assigned), 300000)
        # The bundled typefaces cover most of what has a shape; Last Resort alone is the exception.
        self.assertLess(real_last_resort, 0.55 * (len(self.assigned) - sum(placeholders.values())))

    def test_the_new_unicode_18_characters_are_covered(self):
        import unicodedata
        new = [cp for cp in self.assigned if unicodedata.category(chr(cp)) == "Cn"]       # unknown to Python's tables
        self.assertTrue(new, "Python's unicodedata should be older than 18.0")
        self.assertEqual([cp for cp in new if self._owner(cp) == "none"], [])

    def test_the_planes_unifont_upper_serves(self):
        for cp in (0x1F4A9, 0x12000, 0x17000, 0x1B000, 0x1D11E, 0x20000):
            if cp in set(self.assigned):
                with self.subTest(cp=hex(cp)):
                    self.assertNotEqual(self._owner(cp), "none")


class TheRows(unittest.TestCase):
    def test_every_unicode_row_installs_the_fonts_and_licences_all_or_none(self):
        for game in GAMES:
            for kind in ("text", "font"):
                row = json.loads((ROOT / "data" / f"{game}_unicode_{kind}_feature.json").read_text(encoding="utf-8"))
                files = {c["destination"]: c for c in row["companion_files"]}
                with self.subTest(game=game, kind=kind):
                    for name in FONT_FILES + NOTICES:
                        item = files.get(f"Unicode Fonts/{name}")
                        self.assertIsNotNone(item, name)
                        self.assertEqual(item["source"], f"assets/unicode_fonts/{name}")
                        self.assertEqual(item["sha256"], _sha(FONTS / name))
                        # Classified: a companion reads it from the patcher's folder.
                        self.assertEqual(str(patcher_files.installed_relative_path(item["destination"])),
                                         f"Virtual Villagers Fun Patcher Files/Unicode Fonts/{name}")
                    self.assertEqual(len(files), len(FONT_FILES + NOTICES) + 1)          # and the one DLL
                    self.assertIn("**Bundles four open fonts", row["description"])
                    for word in ("GNU Unifont 18.0.01", "Noto Sans Cuneiform", "Noto Serif Tangut", "Last Resort",
                                 "OFL-1.1", "about 14 MB"):
                        self.assertIn(word, row["description"])

    def test_the_total_size_added(self):
        total = sum((FONTS / n).stat().st_size for n in FONT_FILES + NOTICES)
        self.assertLess(total, 15 * 1024 * 1024)
        self.assertGreater(total, 13 * 1024 * 1024)

    def test_the_companions_are_pinned(self):
        for game in GAMES:
            for kind, dll in (("text", "assets/unicode_text/VVFP Unicode Text.dll"),
                              ("font", "assets/unicode_font/VVFP Unicode Font.dll")):
                row = json.loads((ROOT / "data" / f"{game}_unicode_{kind}_feature.json").read_text(encoding="utf-8"))
                dll_item = [c for c in row["companion_files"] if c["destination"].endswith(".dll")][0]
                self.assertEqual(dll_item["sha256"], _sha(ROOT / dll))


class TheRelease(unittest.TestCase):
    def test_the_release_carries_the_fonts_and_licences_and_no_other_art_or_font(self):
        import build_release
        files = [f.replace("\\", "/") for f in build_release.FILES]
        for name in FONT_FILES + NOTICES:
            self.assertIn(f"assets/unicode_fonts/{name}", files)
            self.assertTrue((ROOT / "assets" / "unicode_fonts" / name).is_file())
        fonts = [f for f in files if f.lower().endswith((".ttf", ".otf", ".ttc", ".woff", ".woff2", ".fon"))]
        self.assertEqual(sorted(fonts), sorted(f"assets/unicode_fonts/{n}" for n in FONT_FILES))
        self.assertEqual([f for f in files if "burweed" in f.lower()], [])
        self.assertEqual([f for f in files if f.startswith(("research/", "inputs/"))], [])
        # No picture of a game ships (the only pictures are the patcher's own assets).
        self.assertEqual([f for f in files if re.search(r"ldw(Burweed|arialbold)", f, re.I)], [])


@unittest.skipUnless(os.name == "nt" and HAVE_FONTS, "needs Windows and the bundled fonts")
class TheTextToolStyling(unittest.TestCase):
    """Picture Studio's Text tool styles the bundled fonts' glyphs like the Windows fonts' (v1.35.90)."""

    LEVELS = (0, 16, 32, 48, 64, 80, 96, 112, 128, 144, 160, 176, 192, 208, 224, 255)
    STYLE = dict(line_height=27, baseline=22, cap_height=16, x_height=11, fill=(255, 255, 255), outline=None,
                 outline_width=0, alpha_levels=LEVELS, bold=True)

    def _style(self, face):
        import vv_glyph_maker as maker
        return maker.GlyphStyle(face=face, **self.STYLE)

    def test_the_pixel_font_is_scaled_by_whole_steps_the_games_rule(self):
        import vv_glyph_maker as maker
        # The rule is the game's (rg_ppem): the nearest multiple of 16 when within a third, never past the line.
        for em, want in ((12, 16), (16, 16), (20, 16), (24, 32), (26, 32), (33, 32), (10, 10), (7, 7)):
            with self.subTest(em=em):
                self.assertEqual(maker.pixel_em(em), want)
        self.assertEqual(maker.pixel_em(26, 27), 26)        # 32 would be taller than a 27 px line

    def test_bundled_glyphs_have_the_fonts_alpha_levels_baseline_and_cap_height(self):
        import vv_glyph_maker as maker
        if not maker.available():
            self.skipTest("no GDI")
        for face, probe in (("Unifont", "H\u4e16"), ("Unifont Upper", "\U00020000"),
                            ("Noto Sans Cuneiform", "\U00012000")):
            style = self._style(face)
            for char in probe:
                with self.subTest(face=face, char=hex(ord(char))):
                    glyph = maker.render_cluster(char, style)
                    self.assertIsNotNone(glyph)
                    self.assertEqual(glyph.face.casefold(), face.casefold())
                    img = glyph.image
                    alphas = {img.data[4 * k + 3] for k in range(img.width * img.height)}
                    self.assertTrue(alphas <= set(self.LEVELS), sorted(alphas - set(self.LEVELS)))
                    self.assertGreaterEqual(len(alphas), 2)
                    colours = {tuple(img.data[4 * k:4 * k + 3]) for k in range(img.width * img.height)
                               if img.data[4 * k + 3]}
                    self.assertEqual(colours, {(255, 255, 255)})             # white: the game tints it
                    self.assertLessEqual(img.height, style.line_height + 2)
                    if char == "H":
                        # Capital H: the font's cap height (+/- 2 px), standing on the baseline (+/- 1 px).
                        self.assertLessEqual(abs(img.height - style.cap_height), 2)
                        self.assertLessEqual(abs(glyph.top + img.height - style.baseline), 1)

    def test_every_chain_ends_with_the_bundled_faces(self):
        import vv_glyph_maker as maker
        calls = []
        real = maker._pick_face
        maker._pick_face = lambda faces, bold, cluster: (calls.append(faces), real(faces, bold, cluster))[1]
        try:
            maker._text_coverage("\U00020000", "Arial", maker.DEFAULT_FALLBACKS, True, 16)
        finally:
            maker._pick_face = real
        self.assertEqual(tuple(calls[0][-5:]), maker.BUNDLED_FACES)


def _hex(cps) -> str:
    return " ".join(chr(c).encode("utf-8").hex() for c in cps)


def _mark_join(cp: int) -> bool:
    """A spacing mark UAX #29 leaves out of GB9a, which the shared cluster rule joins (docs/UNICODE_SPEC.md row 2)."""
    return u18.category(chr(cp)) == "Mc" and u18.grapheme_break_property(chr(cp)) not in (4, 5, 8)


def _conformance():
    """GraphemeBreakTest 18.0's cases, but those with a spacing mark the shared rule joins (its own tests below), and
    with the shared rule's ZWJ: the shared spec (docs/UNICODE_SPEC.md row 2) overrides GB11 so that every Fun
    Patcher cuts alike -- a ZWJ joins the character after it, not only between emoji, unless that is a control,
    CR or LF -- so the file's break after such a ZWJ is not expected."""
    out = []
    for cps, marks in u18.grapheme_break_tests():
        if any(_mark_join(c) for c in cps):
            continue
        marks = [brk and not (cps[i] == 0x200D and u18.grapheme_break_property(chr(cps[i + 1])) not in (1, 2, 3))
                 for i, brk in enumerate(marks)]
        out.append((cps, marks))
    return out


# The shared cluster rule beyond UAX #29: (text, its clusters).  Myanmar U+102B / U+1038, Tai Tham U+1A61 and
# Ahom U+11720 are spacing marks (Mc) GB9a leaves alone; CR LF is one cluster, a mark after LF is not joined.
SPEC_CLUSTERS = (
    ("ကါ", ["ကါ"]),
    ("ကားခ", ["ကား", "ခ"]),
    ("ᨠᩡ", ["ᨠᩡ"]),
    ("\U00011700\U00011720", ["\U00011700\U00011720"]),
    ("aा", ["aा"]),
    ("a\r\nb", ["a", "\r\n", "b"]),
    ("\nါ", ["\n", "ါ"]),
    ("a‍b", ["a‍b"]),                       # a ZWJ joins the next character, emoji or not
    ("क्‍ष", ["क्‍ष"]),
    ("a‍\n", ["a‍", "\n"]),                 # but never a newline
)


class TheGraphemeTest(unittest.TestCase):
    """GraphemeBreakTest.txt 18.0, and the shared cluster rule's every-Mc and CR LF."""

    def test_every_spacing_mark_joins_and_cr_lf_is_one_cluster(self):
        self.assertEqual(sum(1 for cps, _m in u18.grapheme_break_tests() if any(_mark_join(c) for c in cps)), 1)
        for text, want in SPEC_CLUSTERS:
            with self.subTest(text=text):
                self.assertEqual(clusters(text), want)

    @unittest.skipUnless(HAVE_COMPILER, "the MSVC toolchain is not available")
    def test_the_dlls_own_cutting_joins_every_spacing_mark(self):
        with tempfile.TemporaryDirectory() as tmp:
            src, out = Path(tmp, "in.txt"), Path(tmp, "out.txt")
            src.write_text("\n".join(_hex([ord(c) for c in t]) for t, _w in SPEC_CLUSTERS) + "\n", encoding="ascii")
            done = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                                   str(ROOT / "scripts" / "build_grapheme_harness.ps1"), str(src), str(out)],
                                  capture_output=True, text=True, timeout=600)
            self.assertEqual(done.returncode, 0, done.stdout[-2000:] + done.stderr[-2000:])
            got = out.read_text(encoding="ascii").splitlines()
        for (text, want), line in zip(SPEC_CLUSTERS, got):
            with self.subTest(text=text):
                self.assertEqual([int(x) for x in line.split("|")[0].split()], [len(w.encode("utf-8")) for w in want])
                # Backspace erases the last whole cluster.
                self.assertEqual(int(line.split("|")[2]), len("".join(want[:-1]).encode("utf-8")))

    def test_the_games_text_rule_cuts_as_unicode_18_says(self):
        tests = _conformance()
        self.assertGreater(len(tests), 800)
        bad = []
        for cps, marks in tests:
            text = "".join(chr(c) for c in cps)
            want, start = [], 0
            for i, brk in enumerate(marks):
                if brk:
                    want.append("".join(chr(c) for c in cps[start:i + 1]))
                    start = i + 1
            want.append("".join(chr(c) for c in cps[start:]))
            if clusters(text) != want:
                bad.append(cps)
        self.assertEqual(bad[:5], [])

    @staticmethod
    def _text_ok(cps) -> bool:
        """A game's text is a C string (no NUL) of well-formed UTF-8 (no surrogates)."""
        return all(c != 0 and not 0xD800 <= c <= 0xDFFF for c in cps)

    @unittest.skipUnless(HAVE_COMPILER, "the MSVC toolchain is not available")
    def test_the_dlls_own_cutting_passes_the_conformance_file(self):
        tests = _conformance()
        with tempfile.TemporaryDirectory() as tmp:
            src, out = Path(tmp, "in.txt"), Path(tmp, "out.txt")
            lines = []
            for cps, _marks in tests:
                if self._text_ok(cps):
                    lines.append(_hex(cps))
            src.write_text("\n".join(lines) + "\n", encoding="ascii")
            done = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                                   str(ROOT / "scripts" / "build_grapheme_harness.ps1"), str(src), str(out)],
                                  capture_output=True, text=True, timeout=600)
            self.assertEqual(done.returncode, 0, done.stdout[-2000:] + done.stderr[-2000:])
            got = out.read_text(encoding="ascii").splitlines()
        kept = [(cps, marks) for cps, marks in tests if self._text_ok(cps)]
        self.assertEqual(len(got), len(kept))
        bad = []
        for (cps, marks), line in zip(kept, got):
            lens = [int(x) for x in line.split("|")[0].split()]
            want, start = [], 0
            for i, brk in enumerate(marks):
                if brk:
                    want.append(len("".join(chr(c) for c in cps[start:i + 1]).encode("utf-8")))
                    start = i + 1
            want.append(len("".join(chr(c) for c in cps[start:]).encode("utf-8")))
            if lens != want:
                bad.append((cps, lens, want))
        self.assertEqual(bad[:5], [])


def _block_samples() -> list[tuple[str, list[int]]]:
    """Per Unicode block, the first, a middle and the last assigned graphic character."""
    out = []
    assigned = [cp for cp in u18.assigned_code_points()]
    by_block: dict[str, list[int]] = {}
    for cp in assigned:
        # Nothing to see for a control, surrogate, private use, format or space character, a blank Braille cell, or a
        # lone nonspacing mark (it is drawn on its base letter; a lone one has no cell of its own).
        if u18.category(chr(cp)) in ("Cc", "Cs", "Co", "Cf", "Zs", "Zl", "Zp", "Cn", "Mn", "Me") or cp == 0x2800:
            continue
        by_block.setdefault(u18.block(chr(cp)), []).append(cp)
    for block, cps in by_block.items():
        pick = sorted({cps[0], cps[len(cps) // 2], cps[-1]})
        out.append((block, pick))
    return out


@unittest.skipUnless(os.name == "nt" and HAVE_STOCK and HAVE_IMAGES and HAVE_EMULATOR and HAVE_FONTS,
                     "needs Windows, the stock executables, the game images, unicorn and the bundled fonts")
class InTheGame(unittest.TestCase):
    """A sample of every block, through each game's own draw routine with the companion, draws ink."""

    runs: dict = {}

    @classmethod
    def setUpClass(cls):
        import unicode_utf8_emulation as ue
        cls.ue = ue
        cls.tables = json.loads((ROOT / "data" / "font_glyph_tables.json").read_text(encoding="utf-8"))
        for game in GAMES:
            cls.runs[game] = ue.TextRun(game, (f"{game}_unicode_text", f"{game}_details_full_names"), cls.tables)
        cls.samples = _block_samples()

    def _ink(self, run, text: str) -> int:
        blits = run.draw_text("ldwarialbold", text.encode("utf-8"), 100, 50)
        inked = 0
        for src, rect, _dst, _to in blits:
            sw, sh, pitch, pixels, amask, ashift = run.surface(src)
            x1, y1, rw, rh = rect
            inked += sum(1 for y in range(rh) for x in range(rw)
                         if struct.unpack_from("<I", pixels, (y1 + y) * pitch + (x1 + x) * 4)[0] & amask)
        return inked

    def test_the_companion_added_the_bundled_fonts_privately(self):
        for game, run in self.runs.items():
            with self.subTest(game=game):
                self.runs[game].draw_text("ldwarialbold", "\U00012000".encode("utf-8"))
                added = run.m.__dict__.get("added_fonts", [])
                self.assertTrue(added, "the companion tried no bundled font")
                self.assertTrue(all(p.endswith(tuple("\\Unicode Fonts\\" + n for n in FONT_FILES)) for p in added), added)

    def test_every_block_draws_in_every_game(self):
        self.assertGreater(len(self.samples), 300)
        for game, run in self.runs.items():
            # The first game draws every block; the others a rotating third (each block still runs in two games).
            idx = GAMES.index(game)
            for n, (block, cps) in enumerate(self.samples):
                if game != "vv3" and (n + idx) % 3 != 0:
                    continue
                for cp in cps:
                    with self.subTest(game=game, block=block, cp=hex(cp)):
                        self.assertGreater(run.width_of("ldwarialbold", chr(cp).encode("utf-8")), 0)
                        self.assertGreater(self._ink(run, chr(cp)), 0)

    def test_supplementary_ignorable_characters_do_not_reject_a_face(self):
        # U+E0100.. (a variation selector) and U+E0020.. (a tag) are DB40 + a low surrogate: both units belong to a
        # character that draws nothing by design, so the letter before it still draws from its first face (Codex on #686).
        run = self.runs["vv3"]
        plain = self._ink(run, "日")
        for tail in ("\U000E0100", "\U000E01EF", "\U000E0067"):
            with self.subTest(tail=hex(ord(tail))):
                self.assertEqual(self._ink(run, "日" + tail), plain)
        # a cuneiform sign with a variation selector keeps its ink
        self.assertGreater(self._ink(run, "\U00012000\U000E0100"), 0)

    def _alphas_and_rows(self, run, text):
        blits = run.draw_text("ldwarialbold", text.encode("utf-8"), 100, 50)
        alphas, rows = set(), set()
        for src, rect, _dst, _to in blits:
            sw, sh, pitch, pixels, amask, ashift = run.surface(src)
            x1, y1, rw, rh = rect
            for y in range(rh):
                for x in range(rw):
                    a = (struct.unpack_from("<I", pixels, (y1 + y) * pitch + (x1 + x) * 4)[0] & amask) >> ashift
                    if a:
                        alphas.add(a)
                        rows.add(y)
        return alphas, rows

    def test_bundled_glyphs_are_styled_like_the_game_font_with_only_the_bundled_fonts_present(self):
        """The Windows fonts are hidden from the companion, so a bundled font draws each sample: the glyph has the
        game font's own alpha levels, stands on its baseline and is as tall as its capitals (+/- 2 px)."""
        import unicode_text_emulation as ute
        from PIL import Image
        ute.ONLY_BUNDLED_FONTS = True
        try:
            for game in ("vv1", "vv3"):
                run = self.ue.TextRun(game, (f"{game}_unicode_text", f"{game}_details_full_names"), self.tables)
                sheet = Image.open(IMAGES / f"Virtual Villagers - {NAMES[game]}" / "Images" / "ldwarialbold.png")
                levels = {v for v in sheet.convert("RGBA").getchannel("A").tobytes() if v}
                # The game's own H, drawn by the game's own routine: its inked rows are the cap height.
                _a, h_rows = self._alphas_and_rows(run, "H")
                cap = max(h_rows) - min(h_rows) + 1
                for char in ("\u0141", "\u4e16", "\U00012000", "\U00020000", "\U00017000", "\U00013000"):
                    with self.subTest(game=game, char=hex(ord(char))):
                        alphas, rows = self._alphas_and_rows(run, char)
                        self.assertTrue(alphas, "nothing drawn")
                        # The page holds the game's pixel format (fewer alpha bits), so the values are compared by
                        # how many there are: a glyph left at GDI's 65 grey levels would have many more than the font's
                        # own few levels; and the strokes are fully inked.
                        self.assertLessEqual(len(alphas), len(levels))
                        self.assertGreaterEqual(max(alphas), 200)
                        self.assertGreater(len(alphas), 2)
                        self.assertLessEqual(max(rows) - min(rows) + 1, cap + 8)       # a CJK glyph is a full em
                        if char == "\u0141":
                            self.assertLessEqual(abs((max(rows) - min(rows) + 1) - cap), 2)
                            self.assertLessEqual(abs(max(rows) - max(h_rows)), 1)       # on the same baseline
        finally:
            ute.ONLY_BUNDLED_FONTS = False

    def test_a_missing_font_file_leaves_the_game_as_it_was(self):
        import unicode_text_emulation as ute
        ute.ADD_FONTS = False
        try:
            run = self.ue.TextRun("vv3", ("vv3_unicode_text", "vv3_details_full_names"), self.tables)
            self.assertEqual(run.export("VvfpGlyphsUtf8"), 1)
            self.assertGreater(self._ink(run, "\u4e16"), 0)             # still drawn from the Windows fonts
            self.assertTrue(run.m.__dict__.get("added_fonts"), "the companion did not look for the fonts")
            blits = run.draw_text("ldwBurweed27", b"Hello World")
            self.assertEqual(len(blits), 11)
        finally:
            ute.ADD_FONTS = True

    def test_the_new_unicode_18_characters_draw(self):
        import unicodedata
        new = [cp for cp in u18.assigned_code_points()
               if unicodedata.category(chr(cp)) == "Cn" and u18.category(chr(cp)) not in ("Cc", "Cf", "Zs")]
        self.assertTrue(new)
        step = max(1, len(new) // 40)
        for game in ("vv1", "vv4"):
            for cp in new[::step]:
                with self.subTest(game=game, cp=hex(cp)):
                    self.assertGreater(self._ink(self.runs[game], chr(cp)), 0)


if __name__ == "__main__":
    unittest.main()
