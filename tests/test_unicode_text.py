"""Render Unicode with In-Game Fonts (vvN_unicode_text): every printable Windows-1252 character drawn,
measured and typed in all five games.

THE FONTS (data/font_glyph_tables.json, from the stock executables): each game's two bitmap fonts, their
glyph tables and what they lack.

THE LETTERS: src/vv_font_glyphs.py and the companion's C (native/vvfp_unicode_text/glyphs.inc, run by
glyph_harness.c) make the very same pixels, with and without Burweed ICG.

THE GAME (tests/unicode_text_emulation.py): each published build is started as the game starts it, then
the game's own font construction, text width, text draw, SDL_TEXTINPUT case and text box run in unicorn:
every missing character gets its letter at its real width, is drawn from the new rows, and is typed as
its one byte; the stock build draws them as the first letter and drops them when typed.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import vv_font_glyphs as glyphs  # noqa: E402
import vv_fun_patcher as patcher  # noqa: E402

GAMES = ("vv1", "vv2", "vv3", "vv4", "vv5")
DLL_NAME = "VVFP Unicode Text.dll"
DLL = ROOT / "assets" / "unicode_text" / DLL_NAME
TABLES = json.loads((ROOT / "data" / "font_glyph_tables.json").read_text(encoding="utf-8"))
STOCK_DIR = ROOT / "research" / "stock-executables"
EXES = {
    "vv1": "Virtual Villagers - A New Home.exe",
    "vv2": "Virtual Villagers - The Lost Children.exe",
    "vv3": "Virtual Villagers - The Secret City.exe",
    "vv4": "Virtual Villagers - The Tree of Life.exe",
    "vv5": "Virtual Villagers - New Believers.exe",
}
GAME_NAMES = {"vv1": "A New Home", "vv2": "The Lost Children", "vv3": "The Secret City",
              "vv4": "The Tree of Life", "vv5": "New Believers"}
IMAGES = {g: ROOT / "research" / "game-images" / f"Virtual Villagers - {n}" / "Images" for g, n in GAME_NAMES.items()}
HAVE_STOCK = all((STOCK_DIR / name).is_file() for name in EXES.values())
HAVE_IMAGES = all((IMAGES[g] / f"{f}.png").is_file() for g in GAMES for f in glyphs.FONTS)
ON_WINDOWS = sys.platform == "win32"
HARNESS = ROOT / "scripts" / "build_unicode_text_harness.ps1"
CL = Path(r"C:\Program Files\Microsoft Visual Studio\18\Community\VC\Tools\MSVC\14.51.36231\bin\Hostx64\x86\cl.exe")
try:
    import unicorn  # noqa: F401
    import pefile
    HAVE_EMULATOR = True
except ImportError:  # pragma: no cover
    HAVE_EMULATOR = False

SAMPLE = "Zoë Ñúñez — “Ça va?” Œuvre ß €5 £3 ¿Qué? ¡Sí! Šárka Žofie Ÿves… naïve"


def _manifest(game: str) -> dict:
    return json.loads((ROOT / "data" / f"{game}_unicode_text_feature.json").read_text(encoding="utf-8"))


def _load_script(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TheFonts(unittest.TestCase):
    def test_every_game_has_its_two_fonts(self):
        for game in GAMES:
            self.assertEqual(glyphs.fonts(game), ("ldwBurweed27", "ldwarialbold"))
            for font in glyphs.FONTS:
                entries = glyphs.entries(game, font)
                self.assertEqual(entries[0][4] - entries[0][2], 27 if font == "ldwBurweed27" else 20)

    def test_what_each_font_lacks(self):
        early = "#$%&()*+;<=>@[\\]^_{|}~"
        extras = "€‚ƒ„…†‡ˆ‰Š‹ŒŽ‘’“”•–—˜™š›œžŸ"
        for game in GAMES:
            for font in glyphs.FONTS:
                lacks = glyphs.missing(game, font)
                with self.subTest(game=game, font=font):
                    if game in ("vv1", "vv2"):
                        self.assertEqual(len(lacks), 145)
                        for ch in early + extras + "àÉñßÿ¿¡\u00a0":
                            self.assertIn(ch, lacks)
                    else:
                        self.assertEqual(lacks, extras + "\u00a0" + ("¡" if game == "vv3" else ""))

    def test_printable_is_windows_1252_without_controls(self):
        self.assertEqual(len(glyphs.PRINTABLE), 218)
        self.assertNotIn("\x7f", glyphs.PRINTABLE)
        for b in (0x81, 0x8D, 0x8F, 0x90, 0x9D):
            self.assertNotIn(chr(b), glyphs.PRINTABLE)
        self.assertEqual(glyphs.decompose("Š"), ("S", "\u030c"))
        self.assertEqual(glyphs.decompose("ç"), ("c", "\u0327"))
        self.assertIsNone(glyphs.decompose("Ø"))
        self.assertIsNone(glyphs.decompose("ß"))

    @unittest.skipUnless(HAVE_STOCK and HAVE_EMULATOR, "stock executables are not available")
    def test_the_tables_and_header_are_the_stock_executables(self):
        module = _load_script("build_font_glyph_tables")
        with tempfile.TemporaryDirectory() as tmp:
            module.OUT = Path(tmp) / "tables.json"
            module.HEADER = Path(tmp) / "header.h"
            module.main()
            self.assertEqual(module.OUT.read_text(encoding="utf-8"),
                             (ROOT / "data" / "font_glyph_tables.json").read_text(encoding="utf-8"))
            self.assertEqual(module.HEADER.read_text(encoding="utf-8"),
                             (ROOT / "native" / "vvfp_unicode_text" / "unicode_text_tables.h").read_text(encoding="utf-8"))


class TheRows(unittest.TestCase):
    def test_the_rows(self):
        sha = hashlib.sha256(DLL.read_bytes()).hexdigest().upper()
        public = {p.id for p in patcher.load_public_fun_patches()}
        for game in GAMES:
            with self.subTest(game=game):
                row = _manifest(game)
                self.assertEqual(row["id"], f"{game}_unicode_text")
                self.assertIn(row["id"], public)
                self.assertEqual(row["name"], "Render Unicode with In-Game Fonts")
                self.assertEqual(row["patches"], [])
                self.assertEqual(row["dependencies"], [f"{game}_details_full_names"])
                self.assertEqual(row["conflicts"], [f"{game}_unicode_font"])
                # The DLL first, then the bundled open fonts, their licences and SOURCES.json (tests/test_unicode18.py).
                self.assertEqual(row["companion_files"][0], {"source": f"assets/unicode_text/{DLL_NAME}",
                                                             "destination": DLL_NAME, "sha256": sha})
                self.assertEqual({c["destination"].split("/")[0] for c in row["companion_files"][1:]},
                                 {"Unicode Fonts"})
                d = row["description"]
                for words in ("**On by default and in Owner's Defaults.**", "**Needs \"Full Names on the Details Screen\"",
                              "**Not yet seen in a running game**", "**Cannot be used with",
                              "**for Burweed, install the Burweed ICG font"):
                    self.assertIn(words, d)
                g = TABLES["games"][game]
                self.assertEqual([x["va"] for x in row["runtime_detours"]][:2], [g["ctor"], g["text_input"]["site"]])

    def test_the_generator_reproduces_the_rows(self):
        module = _load_script("build_unicode_text_feature")
        sha = hashlib.sha256(DLL.read_bytes()).hexdigest().upper()
        for number, game in enumerate(GAMES, start=1):
            self.assertEqual(module.row(number, False, sha, TABLES, module.routines()), _manifest(game))

    def test_started_by_the_startup_loader_second_word(self):
        # Appended after VVFP Original Look.dll; VVFP Translations.dll (#672) comes after it, so it finds this
        # companion's VvfpGlyphsUtf8 already loaded.
        names = list(patcher.STARTUP_LOADER_COMPANIONS_2)
        self.assertEqual(names[names.index("VVFP Original Look.dll") + 1], DLL_NAME)
        self.assertLess(names.index(DLL_NAME), names.index("VVFP Translations.dll"))
        # Use Unicode Font next; Copy and Paste in Text Boxes (v1.35.89) is appended after it
        self.assertEqual(names[names.index("VVFP Unicode Font.dll") + 1], "VVFP Copy and Paste.dll")
        header = (ROOT / "native" / "shared" / "startup_companions_2.h").read_text(encoding="utf-8")
        self.assertIn('    "VVFP Original Look.dll",\n    "VVFP Unicode Text.dll",\n', header)
        self.assertIn(DLL_NAME.encode(), (ROOT / "assets" / "startup" / "VVFP Startup.dll").read_bytes())
        self.assertEqual(hashlib.sha256((ROOT / "assets" / "startup" / "VVFP Startup.dll").read_bytes())
                         .hexdigest().upper(), patcher.STARTUP_LOADER_COMPANION["sha256"])

    def test_on_by_default_in_select_all_and_owners_defaults(self):
        from vv_fun_patcher_gui import (default_fun_patch_selection, owners_default_fun_patch_selection,
                                        select_all_fun_patch_selection)
        for game in GAMES:
            self.assertTrue(default_fun_patch_selection(f"{game}_unicode_text"))
            self.assertTrue(owners_default_fun_patch_selection(f"{game}_unicode_text"))
            self.assertTrue(select_all_fun_patch_selection(f"{game}_unicode_text"))

    def test_registered_bundled_documented(self):
        release = (ROOT / "scripts" / "build_release.py").read_text(encoding="utf-8")
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        guide = json.loads((ROOT / "data" / "how_to_use.json").read_text(encoding="utf-8"))
        for path in (f"assets/unicode_text/{DLL_NAME}", "data/font_glyph_tables.json", "src/vv_font_glyphs.py",
                     "src/vv_game_text.py"):
            self.assertIn(f'"{path}"', release)
        guided = {i for entry in guide["patches"] for i in entry.get("ids", [])}
        for game in GAMES:
            self.assertIn(f'"data/{game}_unicode_text_feature.json"', release)
            self.assertIn(f"- Patch ID: `{game}_unicode_text`", readme)
            self.assertIn(_manifest(game)["description"], readme)
            self.assertIn(f"{game}_unicode_text", guided)

    @unittest.skipUnless(HAVE_EMULATOR, "pefile is not installed")
    def test_the_dll_exports_and_imports(self):
        pe = pefile.PE(str(DLL))
        names = sorted(e.name.decode() for e in pe.DIRECTORY_ENTRY_EXPORT.symbols if e.name)
        self.assertEqual(names, ["VvfpBoxInsertUtf8", "VvfpGlyphsUtf8", "VvfpLongName", "VvfpStartup",
                                 "VvfpUnicodeTextFonts", "VvfpUnicodeTextKey", "VvfpUnicodeTextOwnDraws",
                                 "VvfpUnicodeTextUnits"])
        imports = {i.name.decode() for e in pe.DIRECTORY_ENTRY_IMPORT for i in e.imports if i.name}
        self.assertEqual(imports & {"LoadLibraryA", "LoadLibraryW", "OutputDebugStringA", "OutputDebugStringW",
                                    "MessageBoxA", "MessageBoxW", "RegSetValueExW",
                                    "CreateFileA", "MoveFileW"},
                         set())
        # The Long Names file is made in "<file>.tmp" and moved over the old one (UNICODE_SPEC section 2): the
        # only MoveFileExW / DeleteFileW calls are on that temporary file, in long_names.inc.
        import re
        native = ROOT / "native" / "vvfp_unicode_text"
        for source in native.iterdir():
            if source.suffix in (".c", ".inc", ".h"):
                calls = re.findall(r"(MoveFileExW|DeleteFileW)\(([^,)]*)", source.read_text(encoding="utf-8"))
                if source.name != "long_names.inc":
                    self.assertEqual(calls, [], source.name)
                else:
                    self.assertTrue(calls)
                    self.assertTrue(all(arg.strip() == "tmp" for _name, arg in calls), calls)
        self.assertIn("GetGlyphOutlineW", imports)
        self.assertIn("AddFontResourceExW", imports)
        # nothing writable and executable
        for section in pe.sections:
            self.assertFalse(section.Characteristics & 0x20000000 and section.Characteristics & 0x80000000)


@unittest.skipUnless(ON_WINDOWS and HAVE_IMAGES and CL.is_file(),
                     "needs Windows, the stock game images and the 32-bit MSVC toolchain")
class TheSameLettersInCAndPython(unittest.TestCase):
    """glyphs.inc (the companion's C) and src/vv_font_glyphs.py make the same pixels for every missing
    character of every font, with Burweed ICG (when installed) and without it."""

    SOURCES = {1: "game", 2: "alias", 3: "ttf", 4: "composed", 5: "stand-in", 0: "none"}

    def test_every_letter(self):
        with tempfile.TemporaryDirectory(prefix="vvfp_ut_cmp_") as tmp:
            args, jobs = [], []
            for game in GAMES:
                for font in glyphs.FONTS:
                    for mode in ("burweed", "no-burweed"):
                        made = glyphs.FontGlyphs(game, font, IMAGES[game], use_burweed=(mode == "burweed"))
                        s = made.sheet
                        entries = glyphs.entries(game, font)
                        src = Path(tmp) / f"{game}_{font}_{mode}.in"
                        src.write_bytes(struct.pack("<5i", s.w, s.h, len(entries), glyphs.spacing(game, font),
                                                    1 if font == "ldwBurweed27" else 0)
                                        + b"".join(struct.pack("<5i", *e) for e in entries) + bytes(s.alpha))
                        out = Path(tmp) / f"{game}_{font}_{mode}.out"
                        args += [str(src), str(out), mode]
                        jobs.append((game, font, mode, made, out))
            result = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                                     str(HARNESS), *args], capture_output=True, text=True, timeout=900)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            for game, font, mode, made, out in jobs:
                data, at = out.read_bytes(), 0
                for code in range(256):
                    source, w, h = struct.unpack_from("<3i", data, at)
                    at += 12
                    px = list(data[at:at + w * h])
                    at += w * h
                    ch = bytes([code]).decode("cp1252", "ignore")
                    if len(ch) != 1 or ch not in glyphs.PRINTABLE or made.sheet.box(code) is not None:
                        self.assertEqual(source, 0)
                        continue
                    g = made.glyph(ch)
                    with self.subTest(game=game, font=font, mode=mode, ch=ch):
                        self.assertIsNotNone(g)
                        self.assertEqual((self.SOURCES[source], w, h, px),
                                         (g.source.split(":")[0], g.mask.w, g.mask.h, g.mask.px))


@unittest.skipUnless(ON_WINDOWS and HAVE_IMAGES, "needs Windows and the stock game images")
class TheLetters(unittest.TestCase):
    def test_every_missing_character_is_made_in_every_font(self):
        for use in (True, False):
            for game in GAMES:
                for font in glyphs.FONTS:
                    made = glyphs.FontGlyphs(game, font, IMAGES[game], use_burweed=use)
                    m = made.metrics
                    for ch in glyphs.missing(game, font):
                        g = made.glyph(ch)
                        with self.subTest(use=use, game=game, font=font, ch=ch):
                            self.assertIsNotNone(g)
                            if ch == "\u00a0":                 # the font's own space box
                                self.assertEqual(g.source, "alias")
                                self.assertEqual(g.mask.w, made.sheet.box(0x20).w)
                                continue
                            self.assertEqual(g.mask.h, m.line)
                            self.assertIsNotNone(g.mask.ink(), "an empty letter")

    def test_accents_sit_above_the_letter_and_the_line_holds_them(self):
        for game in GAMES:
            for font in glyphs.FONTS:
                made = glyphs.FontGlyphs(game, font, IMAGES[game], use_burweed=False)
                for ch in "ŠŽšžŸ":
                    g = made.glyph(ch)
                    left, top, right, bottom = g.mask.ink()
                    self.assertGreaterEqual(top, 0)
                    self.assertLessEqual(bottom, made.metrics.baseline)


@unittest.skipUnless(ON_WINDOWS and HAVE_STOCK and HAVE_IMAGES and HAVE_EMULATOR,
                     "needs Windows, the stock executables and images, and unicorn")
class TheGame(unittest.TestCase):
    """The published builds' own font, width, draw, typing and text box code, emulated."""

    runs: dict = {}

    @classmethod
    def setUpClass(cls):
        import startup_emulation
        import unicode_text_emulation as emu
        cls.emu = emu
        cls.saved_imports = dict(startup_emulation.EXTRA_IMPORTS)
        cls.runs = {}
        for game in GAMES:
            cls.runs[(game, True)] = emu.FontRun(game, "collection_progression",
                                                 (f"{game}_unicode_text", f"{game}_details_full_names"), TABLES)
            cls.runs[(game, False)] = emu.FontRun(game, "collection_progression", (), TABLES)
        cls.outer = {}
        for (game, patched), run in cls.runs.items():
            for font in glyphs.FONTS:
                spacing = TABLES["games"][game]["fonts"][font]["spacing"]
                cls.outer[(game, patched, font)] = run.build_font(font, spacing)

    @classmethod
    def tearDownClass(cls):
        import startup_emulation
        startup_emulation.EXTRA_IMPORTS.clear()
        startup_emulation.EXTRA_IMPORTS.update(cls.saved_imports)

    def _made(self, game, font):
        return glyphs.FontGlyphs(game, font, IMAGES[game], use_burweed=False)

    def test_every_missing_character_gets_its_letter_from_the_new_rows(self):
        for game in GAMES:
            run = self.runs[(game, True)]
            for font in glyphs.FONTS:
                made = self._made(game, font)
                impl = run.impl(self.outer[(game, True, font)])
                surface = struct.unpack("<I", run.m.mu.mem_read(
                    struct.unpack("<I", run.m.mu.mem_read(impl + 0x0C, 4))[0], 4))[0]
                w, h, pitch, pixels, amask, ashift = run.surface(surface)
                stock_w, stock_h = TABLES["games"][game]["fonts"][font]["sheet_size"]
                self.assertEqual(w, stock_w)
                self.assertGreater(h, stock_h)
                for ch in glyphs.missing(game, font):
                    code = glyphs.to_byte(ch)
                    g = made.glyph(ch)
                    x1, y1, x2, y2 = run.glyph_rect(impl, code)
                    with self.subTest(game=game, font=font, ch=ch):
                        self.assertEqual((x2 - x1, y2 - y1), (g.mask.w, g.mask.h))
                        if g.source == "alias":
                            continue
                        self.assertGreater(y1, stock_h - 1)          # in the rows the companion added
                        got = [((struct.unpack_from("<I", pixels, (y1 + y) * pitch + 4 * (x1 + x))[0] & amask)
                                >> ashift) for y in range(g.mask.h) for x in range(g.mask.w)]
                        self.assertEqual(got, g.mask.px)
                # the stock letters are where they were
                for e in glyphs.entries(game, font)[:5]:
                    self.assertEqual(run.glyph_rect(impl, e[0]), tuple(e[1:]))
                # the old picture was freed, the new one kept
                self.assertNotIn(surface, run.m.freed)

    def test_widths_are_the_letters_real_widths(self):
        for game in GAMES:
            for font in glyphs.FONTS:
                made = self._made(game, font)
                for text in (SAMPLE, "€" * 3 + "Ÿ", "Éé Àà Ññ"):
                    # the game's own sum: each box plus the spacing, less one spacing at the end
                    expected = sum(made.glyph(c).mask.w + made.metrics.spacing for c in text) - made.metrics.spacing
                    self.assertEqual(glyphs.FontGlyphs(game, font, IMAGES[game], use_burweed=False)
                                     .text_width(text), expected)
                    with self.subTest(game=game, font=font, text=text):
                        width = self.runs[(game, True)].width(self.outer[(game, True, font)], text.encode("cp1252"))
                        self.assertEqual(width, expected)

    def test_the_stock_game_measures_a_missing_letter_as_its_first(self):
        """The guard the patch removes: without it, '€' measures as the font's first letter."""
        for game in GAMES:
            run = self.runs[(game, False)]
            for font in glyphs.FONTS:
                first = glyphs.entries(game, font)[0]
                spacing = TABLES["games"][game]["fonts"][font]["spacing"]
                width = run.width(self.outer[(game, False, font)], "€".encode("cp1252"))
                self.assertEqual(width, first[3] - first[1])                # its box; no last spacing

    def test_the_draw_routine_blits_each_new_letter(self):
        for game in GAMES:
            run = self.runs[(game, True)]
            for font in glyphs.FONTS:
                outer = self.outer[(game, True, font)]
                impl = run.impl(outer)
                made = self._made(game, font)
                text = "Zoë €—Š"
                blits = run.draw(outer, text.encode("cp1252"), 100, 50)
                self.assertEqual(len(blits), len(text))          # the space too: its box is blank
                x = 100
                for c, (src, rect, dst, to) in zip(text, blits):
                    g = made.glyph(c)
                    x1, y1, x2, y2 = run.glyph_rect(impl, glyphs.to_byte(c))
                    self.assertEqual(rect, (x1, y1, x2 - x1, y2 - y1), (game, font, c))
                    self.assertEqual(to[:2], (x, 50), (game, font, c))
                    x += g.mask.w + made.metrics.spacing

    def test_typing_every_character(self):
        """v1.35.89: ASCII is posted as before; every other well-formed text is handed to the box whole (a
        mark the box's handler takes: tests/test_unicode_utf8.py checks what it stores)."""
        for game in GAMES:
            run = self.runs[(game, True)]
            for ch in glyphs.PRINTABLE:
                with self.subTest(game=game, ch=ch):
                    kind, value = run.type_text(ch.encode("utf-8"))
                    self.assertEqual(kind, "post")
                    if ord(ch) < 0x80:
                        self.assertEqual(value, ord(ch))
                    else:
                        self.assertEqual(value & 0xFF0000FF, 0x56000000)
            for text in ("日", "Ω", "😀", "ab", "é\u0301", "\u0100"):
                kind, value = run.type_text(text.encode("utf-8"))
                self.assertEqual((kind, value & 0xFF0000FF), ("post", 0x56000000), (game, text))
            # malformed or overlong UTF-8 is skipped
            for raw in (b"\xc3", b"\xc0\xa9", b"\xe2\x82", b"\xff"):
                self.assertEqual(run.type_text(raw), ("skip", None), (game, raw))

    def test_the_stock_game_drops_typed_accents(self):
        for game in GAMES:
            run = self.runs[(game, False)]
            self.assertEqual(run.type_text("é".encode()), ("skip", None))
            self.assertEqual(run.type_text(b"a"), ("post", 0x61))

    def test_the_text_box_stores_each_byte_up_to_its_limit(self):
        for game in GAMES:
            run = self.runs[(game, True)]
            name = "Zoë Ñúñez Œ€"
            posted = [run.type_text(c.encode("utf-8"))[1] for c in name]
            self.assertEqual(run.box_type(posted), name.encode("cp1252"))
            self.assertEqual(run.box_type(posted * 3, limit=10), (name * 3).encode("cp1252")[:10])


if __name__ == "__main__":
    unittest.main()
