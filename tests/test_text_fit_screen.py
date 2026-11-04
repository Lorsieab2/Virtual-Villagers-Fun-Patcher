"""Text and translations never run off the screen (docs/UNICODE_SPEC.md row 3, "Screen edge"), all five games.

The owner: "make sure text and translations don't run off the screen when patched" and "i dont care if things
run out of boxes, they just need to not run off the screen".

  * the draw hooks (native/vvfp_unicode_text/text_hooks.inc vt_screen_fit), in emulation of each stock executable
    with Render Unicode with In-Game Fonts: long CJK, Arabic, emoji and no-space Thai lines drawn left, centre and
    right aligned at the right edge of the 800-pixel-wide window stay inside it, cut with an ellipsis; one partly
    left of the window is drawn from its left edge; a text that fits is drawn exactly as before; the game's own
    English is never touched; a justified paragraph (VV3-VV5) wraps at the screen's edge;
  * the shared ICU word lists (assets/word_lists): byte for byte the shared folder (README's SHA-256 values),
    shipped and installed with the companions, and used without icu.dll to break Thai, Lao, Khmer and Myanmar
    between the same words as Windows' ICU -- in the layout harness and in the game's own line fitting.
The emulated machine has no icu.dll, so the in-game cases are the fallback's; ICU's own breaks are compared in the
layout harness.  Skips (never errors) without the compiler, the stock executables, the game images or unicorn.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

from test_unicode_layout import (HAVE_COMPILER, HAVE_EMULATOR, HAVE_IMAGES, HAVE_STOCK, ICU, breaks,  # noqa: E402
                                 run_harness_lines)

WORDS = ROOT / "assets" / "word_lists"
LISTS = ("thaidict.txt", "laodict.txt", "khmerdict.txt", "burmesedict.txt", "cjdict.txt", "ICU-LICENSE.txt")
SCREEN = 800

THAI_LONG = "ภาษาไทยเป็นภาษาที่ไม่มีการเว้นวรรคระหว่างคำ" * 4      # one line, no space at all
SENTENCES = (
    "สวัสดีครับ",
    "ภาษาไทยเป็นภาษาที่ไม่มีการเว้นวรรคระหว่างคำ",
    "ພາສາລາວເປັນພາສາທີ່ສວຍງາມ",
    "ភាសាខ្មែរជាភាសាដ៏ស្រស់ស្អាត",
    "မြန်မာဘာသာစကားသည်လှပသည်",
)
WORST = {
    "cjk": "日本語の長い文章です。" * 12,
    "arabic": "مرحبا بالعالم هذه جملة طويلة جدا " * 6,
    "emoji": "\U0001F468‍\U0001F469‍\U0001F467\U0001F44D\U0001F3FD\U0001F1EF\U0001F1F5" * 10,
    "thai": THAI_LONG,
}


def readme_hashes() -> dict[str, str]:
    text = (WORDS / "README.md").read_text(encoding="utf-8")
    return {name: sha for name, sha in re.findall(r"\| `([^`]+)` \|[^|]*\|[^|]*\| `([0-9a-f]{64})` \|", text)}


class TheWordLists(unittest.TestCase):
    def test_every_list_is_the_shared_folders_own_bytes(self):
        hashes = readme_hashes()
        self.assertEqual(set(hashes), set(LISTS))
        for name, sha in hashes.items():
            with self.subTest(name=name):
                self.assertEqual(hashlib.sha256((WORDS / name).read_bytes()).hexdigest(), sha)

    def test_git_never_rewrites_them(self):
        self.assertIn("assets/word_lists/** -text", (ROOT / ".gitattributes").read_text(encoding="utf-8"))

    def test_shipped_in_the_release_with_their_licence(self):
        release = (ROOT / "scripts" / "build_release.py").read_text(encoding="utf-8")
        for name in ("thaidict.txt", "laodict.txt", "khmerdict.txt", "burmesedict.txt", "ICU-LICENSE.txt",
                     "README.md"):
            with self.subTest(name=name):
                self.assertIn(f'"assets/word_lists/{name}"', release)
        # Chinese and Japanese break between characters (ICU's line breaking does not use cjdict.txt): the
        # list stays in the repository with the shared folder but is not shipped or installed.
        self.assertNotIn('"assets/word_lists/cjdict.txt"', release)

    def test_installed_beside_each_unicode_companion(self):
        for game in range(1, 6):
            for kind in ("unicode_text", "unicode_font"):
                feature = json.loads((ROOT / "data" / f"vv{game}_{kind}_feature.json").read_text(encoding="utf-8"))
                files = {f["destination"]: f for f in feature["companion_files"]}
                for name in ("thaidict.txt", "laodict.txt", "khmerdict.txt", "burmesedict.txt", "ICU-LICENSE.txt"):
                    with self.subTest(game=game, kind=kind, name=name):
                        entry = files[f"Word Lists/{name}"]
                        self.assertEqual(entry["source"], f"assets/word_lists/{name}")
                        self.assertEqual(entry["sha256"],
                                         hashlib.sha256((WORDS / name).read_bytes()).hexdigest().upper())

    def test_loaded_only_without_icu_and_only_for_their_scripts(self):
        code = (ROOT / "native" / "vvfp_unicode_text" / "text_layout.h").read_text(encoding="utf-8")
        self.assertIn("if (!use_icu) {", code)
        self.assertEqual(code.count("tl_words_of(script)"), 1)              # from tl_word_starts only
        self.assertIn('L"Word Lists\\\\"', code)


def _segments(text: str, line: str) -> list[str]:
    raw = text.encode("utf-8")
    offsets = sorted(breaks(line)[1]) + [len(raw)]
    out, prev = [], 0
    for at in offsets:
        out.append(raw[prev:at].decode("utf-8"))
        prev = at
    return out


@unittest.skipUnless(HAVE_COMPILER, "the MSVC toolchain is not available")
class TheFallbackBreaksLikeIcu(unittest.TestCase):
    """Without icu.dll, the lists break Thai, Lao, Khmer and Myanmar between the words ICU finds."""

    @classmethod
    def setUpClass(cls):
        lines = [f"F {t.encode('utf-8').hex()}" for t in SENTENCES]
        cls.plain = run_harness_lines(lines)
        cls.listed = run_harness_lines_with(lines, WORDS)
        cls.icu = run_harness_lines([f"B {t.encode('utf-8').hex()}" for t in SENTENCES])

    def test_the_lists_give_whole_words(self):
        self.assertEqual(_segments(SENTENCES[0], self.listed[0]), ["สวัสดี", "ครับ"])
        for text, plain, listed in zip(SENTENCES, self.plain, self.listed):
            with self.subTest(text=text):
                self.assertLess(len(breaks(listed)[1]), len(breaks(plain)[1]))
                self.assertLessEqual(breaks(listed)[1], breaks(plain)[1])     # never inside a cluster

    @unittest.skipUnless(ICU.is_file(), "this Windows has no icu.dll")
    def test_the_same_breaks_as_windows_icu(self):
        for text, icu, listed in zip(SENTENCES, self.icu, self.listed):
            with self.subTest(text=text):
                self.assertEqual(breaks(icu)[0], 1)
                self.assertEqual(breaks(listed)[1], breaks(icu)[1])


def run_harness_lines_with(lines: list[str], folder: Path) -> list[str]:
    import subprocess
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        src, out = Path(tmp, "in.txt"), Path(tmp, "out.txt")
        src.write_text("".join(line + chr(10) for line in lines), encoding="ascii")
        done = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                               str(ROOT / "scripts" / "build_layout_harness.ps1"), str(src), str(out), str(folder)],
                              capture_output=True, text=True, timeout=600)
        if done.returncode != 0:
            raise AssertionError(done.stdout[-3000:] + done.stderr[-3000:])
        return out.read_text(encoding="ascii").splitlines()


def _span(blits: list) -> tuple[int, int]:
    """The leftmost and rightmost pixel columns the blits cover (source rect width at the destination x)."""
    return (min(to[0] for _s, _r, _d, to in blits), max(to[0] + rect[2] for _s, rect, _d, to in blits))


@unittest.skipUnless(os.name == "nt" and HAVE_STOCK and HAVE_IMAGES and HAVE_EMULATOR,
                     "needs Windows, the stock executables, the game images and unicorn")
class InTheGame(unittest.TestCase):
    runs: dict = {}

    @classmethod
    def setUpClass(cls):
        import startup_emulation
        import unicode_utf8_emulation as ue
        cls.saved_imports = dict(startup_emulation.EXTRA_IMPORTS)
        tables = json.loads((ROOT / "data" / "font_glyph_tables.json").read_text(encoding="utf-8"))
        for game in ("vv1", "vv2", "vv3", "vv4", "vv5"):
            run = ue.TextRun(game, (f"{game}_unicode_text", f"{game}_details_full_names"), tables)
            files = run.use_files()
            # "Word Lists" beside the companion's module: the emulation never runs DllMain, so the module the
            # companion knows there is the game itself (in the game, DllMain names the companion).
            folder = run.m.game_dir + "Word Lists\\"
            for name in ("thaidict.txt", "laodict.txt", "khmerdict.txt", "burmesedict.txt"):
                files[folder + name] = (WORDS / name).read_bytes()
            cls.runs[game] = run

    @classmethod
    def tearDownClass(cls):
        import startup_emulation
        startup_emulation.EXTRA_IMPORTS.clear()
        startup_emulation.EXTRA_IMPORTS.update(cls.saved_imports)
        cls.runs.clear()

    def test_long_lines_at_the_right_edge_stay_on_screen(self):
        for game, run in self.runs.items():
            for kind, text in WORST.items():
                raw = text.encode("utf-8")
                width = run.width_of("ldwarialbold", raw)
                self.assertGreater(width, 400, (game, kind))
                for align, x in (("left", 650), ("centre", 700 - width // 2), ("right", 790 - width)):
                    with self.subTest(game=game, text=kind, align=align):
                        blits = run.draw_text("ldwarialbold", raw, x & 0xFFFFFFFF, 100)
                        self.assertTrue(blits)
                        left, right = _span(blits)
                        self.assertGreaterEqual(left, 0)
                        self.assertLessEqual(right, SCREEN)
                        if x >= 0:
                            self.assertGreaterEqual(left, x)            # drawn where the game put it

    def test_the_big_font_too(self):
        for game, run in self.runs.items():
            with self.subTest(game=game):
                left, right = _span(run.draw_text("ldwBurweed27", WORST["cjk"].encode("utf-8"), 500, 100))
                self.assertGreaterEqual(left, 500)
                self.assertLessEqual(right, SCREEN)

    def test_a_text_that_fits_is_drawn_exactly_as_before(self):
        raw = "Zoé 日本 \U0001F44D".encode("utf-8")
        for game, run in self.runs.items():
            with self.subTest(game=game):
                width = run.width_of("ldwarialbold", raw)
                at_10 = run.draw_text("ldwarialbold", raw, 10, 100)
                at_edge = run.draw_text("ldwarialbold", raw, SCREEN - width - 1, 100)
                self.assertEqual([(s, r, to[0] - 10) for s, r, _d, to in at_10],
                                 [(s, r, to[0] - (SCREEN - width - 1)) for s, r, _d, to in at_edge])

    def test_the_games_own_english_is_never_touched(self):
        raw = b"The quick brown fox jumps over the lazy dog, again and again"
        for game, run in self.runs.items():
            with self.subTest(game=game):
                left, right = _span(run.draw_text("ldwarialbold", raw, 700, 100))
                self.assertEqual(left, 700)
                self.assertGreater(right, SCREEN)          # the stock game's own layout, exactly

    def test_a_text_wholly_off_the_window_is_left_alone(self):
        raw = WORST["cjk"].encode("utf-8")
        for game, run in self.runs.items():
            with self.subTest(game=game):
                self.assertGreaterEqual(_span(run.draw_text("ldwarialbold", raw, 900, 100))[0], 900)

    def test_each_line_of_a_multi_line_text_is_fitted(self):
        raw = ("短い\n" + WORST["cjk"] + "\nok").encode("utf-8")
        for game, run in self.runs.items():
            with self.subTest(game=game):
                blits = run.draw_text("ldwarialbold", raw, 600, 100)
                self.assertLessEqual(_span(blits)[1], SCREEN)
                self.assertEqual(len({to[1] for _s, _r, _d, to in blits}) >= 3, True)   # three lines drawn

    def test_thai_breaks_between_words_in_the_games_line_fitting_without_icu(self):
        listed = run_harness_lines_with([f"F {THAI_LONG.encode('utf-8').hex()}"], WORDS)[0]
        allowed = breaks(listed)[1] | {0, len(THAI_LONG.encode("utf-8"))}
        for game, run in self.runs.items():
            if game == "vv1":
                continue                               # A New Home has no line fitting routine
            with self.subTest(game=game):
                lines = run.linefit("ldwarialbold", THAI_LONG.encode("utf-8"), 150)
                self.assertGreater(len(lines), 2)
                self.assertEqual(b"".join(lines), THAI_LONG.encode("utf-8"))
                at = 0
                for line in lines:
                    at += len(line)
                    self.assertIn(at, allowed, line.decode("utf-8"))
                    self.assertLessEqual(run.width_of("ldwarialbold", line), 150)

    def test_a_justified_paragraph_wraps_at_the_screens_edge(self):
        for game, run in self.runs.items():
            if game in ("vv1", "vv2"):
                continue                               # no justified paragraph routine
            for kind in ("thai", "cjk"):
                with self.subTest(game=game, text=kind):
                    blits = self.justify(run, WORST[kind].encode("utf-8"), 500, 600)
                    self.assertTrue(blits)
                    left, right = _span(blits)
                    self.assertGreaterEqual(left, 500)
                    self.assertLessEqual(right, SCREEN)

    @staticmethod
    def justify(run, raw: bytes, x: int, width: int, count: int = 400_000_000) -> list:
        mu = run.m.mu
        run.draw_text("ldwarialbold", b"", 0, 0)               # the one screen surface
        ctx = run.m.font_heap.alloc(0x400)
        mu.mem_write(ctx + 0x30, struct.pack("<I", run._screen))
        mu.mem_write(ctx + 0x5C, struct.pack("<I", run.fonts["ldwarialbold"]))
        mu.mem_write(ctx + 0x60, struct.pack("<4i", 0, 0, 1024, 768))
        holder = run.m.font_heap.alloc(16)
        mu.mem_write(holder, struct.pack("<I", ctx))
        run.m.blits = []
        run._call(run.addr["justify"], holder, run.cstring(raw), x, 100, width, 0xFFFFFFFF,
                  run.fonts["ldwarialbold"], 0, count=count)
        return list(run.m.blits)


@unittest.skipUnless(os.name == "nt" and HAVE_STOCK and HAVE_IMAGES and HAVE_EMULATOR,
                     "needs Windows, the stock executables, the game images and unicorn")
class WithATranslation(unittest.TestCase):
    """While a translation is in use (a stand-in "VVFP Translations.dll" whose VvfpTranslationsActive answers 1
    and whose VvfpTranslateText gives the text back), plain one-byte text is the patcher's too."""

    runs: dict = {}

    @classmethod
    def setUpClass(cls):
        import startup_emulation as se
        import unicode_utf8_emulation as ue
        cls.saved_imports = dict(se.EXTRA_IMPORTS)
        tables = json.loads((ROOT / "data" / "font_glyph_tables.json").read_text(encoding="utf-8"))
        for game in ("vv1", "vv3", "vv4", "vv5"):
            run = ue.TextRun(game, (f"{game}_unicode_text", f"{game}_details_full_names"), tables)
            base = 0x7E000000
            run.m.mu.mem_map(base, 0x1000)
            run.m.mu.mem_write(base, bytes.fromhex("B801000000C3"))              # mov eax, 1; ret
            run.m.mu.mem_write(base + 0x10, bytes.fromhex("8B442404C20400"))     # mov eax, [esp+4]; ret 4
            run.m.modules["vvfp translations.dll"] = se.Module(
                "VVFP Translations.dll", base, 0x1000,
                {"VvfpTranslationsActive": base, "VvfpTranslateText": base + 0x10}, {}, "")
            cls.runs[game] = run

    @classmethod
    def tearDownClass(cls):
        import startup_emulation
        startup_emulation.EXTRA_IMPORTS.clear()
        startup_emulation.EXTRA_IMPORTS.update(cls.saved_imports)
        cls.runs.clear()

    def test_a_translated_line_is_cut_at_the_edge(self):
        raw = b"Ceci est une tres longue phrase traduite qui depasse le bord de la fenetre du jeu"
        for game, run in self.runs.items():
            with self.subTest(game=game):
                left, right = _span(run.draw_text("ldwarialbold", raw, 600, 100))
                self.assertEqual(left, 600)
                self.assertLessEqual(right, SCREEN)

    def test_one_pixel_of_room_draws_nothing_past_the_edge(self):
        """Codex (#697): at x=799 not even the ellipsis fits; nothing is drawn past the edge."""
        for game, run in self.runs.items():
            for raw in (b"Bonjour tout le monde", "日本語の文章".encode("utf-8")):
                with self.subTest(game=game, text=raw):
                    blits = run.draw_text("ldwarialbold", raw, SCREEN - 1, 100)
                    self.assertTrue(all(to[0] + rect[2] <= SCREEN for _s, rect, _d, to in blits))

    def test_a_narrowed_plain_paragraph_with_a_wide_word_finishes(self):
        """Codex (#697): a stock paragraph narrowed to the screen's edge, with a word wider than the narrowed
        width, would never finish in the game's own justification; it is laid out by the companion instead."""
        raw = b"Un mot " + b"W" * 60 + b" puis la suite du paragraphe traduit"
        for game, run in self.runs.items():
            if game == "vv1":
                continue                               # no justified paragraph routine
            with self.subTest(game=game):
                self.assertGreater(run.width_of("ldwarialbold", b"W" * 60), SCREEN - 500)
                blits = InTheGame.justify(run, raw, 500, 600, count=50_000_000)
                self.assertTrue(blits)
                left, right = _span(blits)
                self.assertGreaterEqual(left, 500)
                self.assertLessEqual(right, SCREEN)


class TheRows(unittest.TestCase):
    def test_the_rows_say_where_the_screen_edge_applies(self):
        for game in range(1, 6):
            for kind in ("unicode_text", "unicode_font", "translations"):
                feature = json.loads((ROOT / "data" / f"vv{game}_{kind}_feature.json").read_text(encoding="utf-8"))
                with self.subTest(game=game, kind=kind):
                    self.assertIn("off the screen", feature["description"])


if __name__ == "__main__":
    unittest.main()
