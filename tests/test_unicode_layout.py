"""The shared spec's text layout in the Unicode companions (docs/UNICODE_SPEC.md row 3), all five games.

  * UAX #14 line breaking (native/vvfp_unicode_text/text_layout.h tl_breaks), run by the layout harness on the
    real Windows icu.dll (System32): Japanese kinsoku, Thai words, a zero width space, whole clusters only; and
    the built-in table used where Windows has no ICU, which holds every kinsoku mark VV's own list had;
  * the game's line fitting (VV2-VV5) and justified paragraph (VV3-VV5) with the companion, in emulation of each
    stock executable: lines break only where the rules allow, no line is wider than its room, and a word wider
    than the whole line is cut after its longest start of whole clusters instead of hanging.
Skips (never errors) without the compiler, Windows, the stock executables, the game images or unicorn.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

from vv_game_text import GAME_TEXT, clusters  # noqa: E402

CL = Path(r"C:\Program Files\Microsoft Visual Studio\18\Community\VC\Tools\MSVC\14.51.36231\bin\Hostx64\x86\cl.exe")
HAVE_COMPILER = os.name == "nt" and CL.is_file()
ICU = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "SysWOW64" / "icu.dll"
NAMES = {"vv1": "A New Home", "vv2": "The Lost Children", "vv3": "The Secret City", "vv4": "The Tree of Life",
         "vv5": "New Believers"}
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

# VV's own kinsoku list before the shared table (text_utf8.h ut_no_break_before / ut_no_break_after, v1.35.89):
# the built-in table must still hold every one of them.
VV_CLOSING = [0x3001, 0x3002, 0xFF0C, 0xFF0E, 0x300D, 0x300F, 0xFF09, 0x3009, 0x300B, 0x3011, 0x3015, 0x30FC,
              0x3005, 0x3041, 0x3043, 0x3045, 0x3047, 0x3049, 0x3063, 0x3083, 0x3085, 0x3087, 0x308E, 0x30A1,
              0x30A3, 0x30A5, 0x30A7, 0x30A9, 0x30C3, 0x30E3, 0x30E5, 0x30E7, 0x30EE, 0x30F5, 0x30F6, 0xFF01,
              0xFF1F, 0xFF1A, 0xFF1B, 0x30FB, 0x2019, 0x201D]
VV_OPENING = [0x300C, 0x300E, 0xFF08, 0x3008, 0x300A, 0x3010, 0x3014, 0x2018, 0x201C]

THAI = "สวัสดีครับ"                 # "hello" (sawatdi) + polite particle (khrap): two words, no space


def _offsets(text: str) -> set[int]:
    """The byte offsets between the clusters of text."""
    out, at = set(), 0
    for unit in clusters(text)[:-1]:
        at += len(unit.encode("utf-8"))
        out.add(at)
    return out


def run_harness(cases: list[tuple[str, str]]) -> list[str]:
    with tempfile.TemporaryDirectory() as tmp:
        src, out = Path(tmp, "in.txt"), Path(tmp, "out.txt")
        src.write_text("".join(f"{cmd} {text.encode('utf-8').hex()}\n" for cmd, text in cases), encoding="ascii")
        done = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                               str(ROOT / "scripts" / "build_layout_harness.ps1"), str(src), str(out)],
                              capture_output=True, text=True, timeout=600)
        if done.returncode != 0:
            raise AssertionError(done.stdout[-3000:] + done.stderr[-3000:])
        return out.read_text(encoding="ascii").splitlines()


def breaks(line: str) -> tuple[int | None, set[int]]:
    parts = line.split()
    icu = None
    if parts and parts[0].startswith("icu="):
        icu = int(parts.pop(0)[4:])
    return icu, {int(p) for p in parts}


@unittest.skipUnless(HAVE_COMPILER, "the MSVC toolchain is not available")
class TheLineBreaks(unittest.TestCase):
    """text_layout.h tl_breaks, on Windows' ICU and on the built-in table."""

    CASES = (
        "日本語、です。次の文",
        "「日本」と書く",
        THAI,
        "abc\u200bdef",
        "hello world",
        "か\u3099き\u3099く",                         # が ぎ ぐ with a combining voiced mark: never split
        "東京タワーっす",
        "\U0001F600\U0001F601 ok",
    )

    @classmethod
    def setUpClass(cls):
        cases = [(cmd, text) for text in cls.CASES for cmd in ("B", "F")]
        cases += [("F", "日" + chr(c)) for c in VV_CLOSING] + [("F", chr(c) + "日") for c in VV_OPENING]
        cls.out = dict(zip(cases, run_harness(cases)))

    def test_windows_icu_is_used_when_windows_has_it(self):
        icu, _ = breaks(self.out[("B", "hello world")])
        self.assertEqual(icu, 1 if ICU.is_file() else 0)

    def test_breaks_only_between_whole_clusters(self):
        for text in self.CASES:
            for cmd in ("B", "F"):
                with self.subTest(text=text, cmd=cmd):
                    _icu, at = breaks(self.out[(cmd, text)])
                    self.assertLessEqual(at, _offsets(text) | {i for i in range(len(text.encode()))
                                                              if text.encode()[i - 1:i] == b" "})

    def test_kinsoku_no_line_starts_with_a_closing_mark_or_ends_with_an_opening_one(self):
        for cmd in ("B", "F"):
            with self.subTest(cmd=cmd):
                _icu, at = breaks(self.out[(cmd, "日本語、です。次の文")])
                b = "日本語、です。次の文".encode("utf-8")
                self.assertNotIn(9, at)                            # before 、
                self.assertNotIn(18, at)                           # before 。
                self.assertIn(3, at)                               # between 日 and 本
                self.assertIn(21, at)                              # after 。
                self.assertEqual(len(b), 30)
                _icu, at = breaks(self.out[(cmd, "「日本」と書く")])
                self.assertNotIn(3, at)                            # after 「
                self.assertNotIn(9, at)                            # before 」
                _icu, at = breaks(self.out[(cmd, "東京タワーっす")])
                self.assertNotIn(len("東京タワ".encode()), at)    # before ー
                self.assertNotIn(len("東京タワー".encode()), at)  # before the small っ

    def test_the_built_in_table_keeps_vvs_own_kinsoku_list(self):
        for c in VV_CLOSING:
            with self.subTest(closing=hex(c)):
                self.assertEqual(breaks(self.out[("F", "日" + chr(c))])[1], set())
        for c in VV_OPENING:
            with self.subTest(opening=hex(c)):
                self.assertEqual(breaks(self.out[("F", chr(c) + "日")])[1], set())

    @unittest.skipUnless(ICU.is_file(), "this Windows has no icu.dll")
    def test_icu_knows_the_thai_words(self):
        _icu, at = breaks(self.out[("B", THAI)])
        self.assertEqual(at, {len("สวัสดี".encode("utf-8"))})
        # The built-in table, without the dictionary, may break between any two Thai clusters.
        self.assertEqual(breaks(self.out[("F", THAI)])[1], _offsets(THAI))

    def test_a_zero_width_space_and_spaces_allow_a_break(self):
        for cmd in ("B", "F"):
            with self.subTest(cmd=cmd):
                self.assertEqual(breaks(self.out[(cmd, "abc\u200bdef")])[1], {6})
                self.assertEqual(breaks(self.out[(cmd, "hello world")])[1], {6})
                self.assertEqual(breaks(self.out[(cmd, "か\u3099き\u3099く")])[1] - {6, 12}, set())


class TheSource(unittest.TestCase):
    def test_icu_is_loaded_from_system32_only_and_used_by_the_line_fitting(self):
        native = ROOT / "native" / "vvfp_unicode_text"
        code = (native / "text_layout.h").read_text(encoding="utf-8")
        self.assertEqual(re.findall(r"LoadLibraryExW\(([^;]*)\);", code), ['L"icu.dll", NULL, TL_SEARCH_SYSTEM32'])
        self.assertIn("#define TL_SEARCH_SYSTEM32 0x00000800u", code)        # LOAD_LIBRARY_SEARCH_SYSTEM32
        hooks = (native / "text_hooks.inc").read_text(encoding="utf-8")
        self.assertIn("tl_breaks(src, brk.span, brk.at)", hooks)
        self.assertIn("tl_no_space_letter(cp)", hooks)                       # the justified paragraph
        # VV's own short CJK test and kinsoku list are gone: the shared table holds them (TheLineBreaks).
        utf8 = (native / "text_utf8.h").read_text(encoding="utf-8")
        for name in ("ut_cjk", "ut_no_break_before", "ut_no_break_after", "ut_break_between"):
            self.assertNotIn(name, utf8 + hooks)


def _bytes_of(text: str) -> bytes:
    return text.encode(GAME_TEXT)


@unittest.skipUnless(os.name == "nt" and HAVE_STOCK and HAVE_IMAGES and HAVE_EMULATOR,
                     "needs Windows, the stock executables, the game images and unicorn")
class InTheGame(unittest.TestCase):
    """Each published build's own line fitting and justified paragraph with Render Unicode with In-Game Fonts.
    The emulated machine has no icu.dll, so these are the built-in table's breaks."""

    runs: dict = {}

    @classmethod
    def setUpClass(cls):
        import unicode_utf8_emulation as ue
        tables = json.loads((ROOT / "data" / "font_glyph_tables.json").read_text(encoding="utf-8"))
        for game in ("vv2", "vv3", "vv4", "vv5"):
            cls.runs[game] = ue.TextRun(game, (f"{game}_unicode_text", f"{game}_details_full_names"), tables)

    def _lines(self, run, text: str, width: int) -> list[bytes]:
        raw = _bytes_of(text)
        lines = run.linefit("ldwarialbold", raw, width)
        self.assertGreater(len(lines), 1)
        for line in lines:
            line.decode("utf-8")
            self.assertTrue(line)
        return lines

    def test_kinsoku_holds_in_the_games_line_fitting(self):
        text = "日本語、です。次の文「名前」と書く。" * 4
        for game, run in self.runs.items():
            with self.subTest(game=game):
                lines = self._lines(run, text, 120)
                self.assertEqual(b"".join(lines), _bytes_of(text))
                for line in lines:
                    self.assertLessEqual(run.width_of("ldwarialbold", line), 120)
                    first, last = line.decode("utf-8")[0], line.decode("utf-8")[-1]
                    self.assertNotIn(first, "、。」ーっ", line.decode("utf-8"))
                    self.assertNotIn(last, "「", line.decode("utf-8"))

    def test_a_thai_text_breaks_inside_its_shaped_run(self):
        text = (THAI + " ") * 6
        for game, run in self.runs.items():
            with self.subTest(game=game):
                lines = self._lines(run, text.strip(), 150)
                self.assertEqual(b"".join(lines).replace(b" ", b""), _bytes_of(text).replace(b" ", b""))
                for line in lines:
                    self.assertLessEqual(run.width_of("ldwarialbold", line), 150)
                    # never inside a cluster: the line is whole clusters of the text
                    self.assertEqual("".join(clusters(line.decode("utf-8"))), line.decode("utf-8"))

    def test_a_word_wider_than_the_line_is_cut_at_whole_clusters(self):
        word = "مرحبابالعالم" * 4                    # one Arabic word, no space, much wider than the line
        for game, run in self.runs.items():
            with self.subTest(game=game):
                lines = self._lines(run, word, 100)
                self.assertEqual(b"".join(lines), _bytes_of(word))
                for line in lines:
                    text = line.decode("utf-8")
                    self.assertTrue(len(clusters(text)) == 1 or run.width_of("ldwarialbold", line) <= 100, text)

    def test_ascii_still_breaks_at_its_spaces(self):
        for game, run in self.runs.items():
            with self.subTest(game=game):
                lines = run.linefit("ldwarialbold", b"The quick brown fox jumps over the lazy dog \xe6\x97\xa5", 120)
                self.assertTrue(all(not line.startswith(b" ") for line in lines))
                self.assertTrue(all(line.split(b" ")[-1] for line in lines))

    def test_the_justified_paragraph_finishes_for_thai(self):
        for game, run in self.runs.items():
            if game == "vv2":
                continue
            with self.subTest(game=game):
                self.assertGreater(run.justify_height("ldwarialbold", _bytes_of(THAI * 8), 120), 0)


if __name__ == "__main__":
    unittest.main()
