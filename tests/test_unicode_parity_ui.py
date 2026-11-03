"""Unicode parity (VV): the shared spec's chain, sidecar v3, tribe rename, "%" rule, Unicode Font and Game Text tools.

One class per item, so a failure names the spec row it breaks.
"""
from __future__ import annotations

import os
import re
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import vv_long_names as ln  # noqa: E402
import vv_tribe_rename as rename  # noqa: E402
from vv_game_text import GAME_TEXT, byte_length, encode_game_text  # noqa: E402

# UNICODE_SPEC.md section 3, "Fallback chain": "(UI)" faces are the GDI names with " UI".
SPEC_CHAIN = [
    "Segoe UI", "Segoe UI Historic", "Segoe UI Symbol", "Segoe UI Emoji", "Yu Gothic UI", "Meiryo",
    "Microsoft YaHei UI", "Microsoft JhengHei UI", "Malgun Gothic", "SimSun-ExtB", "Nirmala UI", "Ebrima",
    "Gadugi", "Leelawadee UI", "Myanmar Text", "Javanese Text", "Mongolian Baiti", "Microsoft Himalaya",
    "Microsoft Yi Baiti", "Microsoft New Tai Lue", "Microsoft Tai Le", "Microsoft PhagsPa", "Sylfaen",
    "Cambria Math", "Noto Sans", "Noto Sans Symbols", "Noto Sans Symbols 2", "Noto Sans CJK JP",
    "Noto Sans CJK SC", "Noto Sans Math", "Noto Sans Cuneiform", "Noto Color Emoji",
]


def native_chain() -> list[str]:
    text = (ROOT / "native" / "vvfp_unicode_text" / "runtime_glyphs.inc").read_text(encoding="utf-8")
    body = text[text.index("RG_CHAIN[] = {"):]
    body = body[:body.index("NULL")]
    return re.findall(r'L"([^"]+)"', body)


class FallbackChain(unittest.TestCase):
    def test_every_spec_face_is_in_the_chain_in_the_spec_order(self):
        chain = native_chain()
        self.assertEqual(len(chain), len(set(chain)), "a face listed twice")
        positions = [chain.index(face) for face in SPEC_CHAIN]
        self.assertEqual(positions, sorted(positions))

    def test_the_faces_vv_drew_with_before_are_kept(self):
        self.assertIn("Yu Gothic", native_chain())
        self.assertIn("Microsoft YaHei", native_chain())

    def test_the_face_table_holds_the_whole_chain(self):
        text = (ROOT / "native" / "vvfp_unicode_text" / "runtime_glyphs.inc").read_text(encoding="utf-8")
        faces = int(re.search(r"#define RG_FACES (\d+)", text).group(1))
        self.assertGreaterEqual(faces, len(native_chain()) + 4)    # chain + override + Arial/Comic + Emoji first


JAPANESE = "山田太郎・アレクサンドラ・モンゴメリー・スミス三世"
ELLIPSIS = chr(0x2026)


class SidecarV3(unittest.TestCase):
    """UNICODE_SPEC section 2, "The full-name sidecar": short, room, whole, CRC; v1 and v2 still read."""

    def test_a_v3_record_carries_its_room_and_a_crc_over_everything_before_the_last_tab(self):
        short, whole = b"Alexandria Montg...", b"Alexandria Montgomery-Smith"
        record = ln.record(short, whole, 20)
        self.assertEqual(record.count(b"\t"), 3)
        self.assertTrue(record.endswith(b"\n"))
        body, crc = record[:-1].rsplit(b"\t", 1)
        self.assertEqual(body, short + b"\t20\t" + whole)
        import zlib
        self.assertEqual(crc, b"%08X" % zlib.crc32(body))
        self.assertEqual(ln.records(ln.HEADER + record), [(short, 20, whole)])

    def test_v1_and_v2_files_are_still_read(self):
        short, whole = b"Old name...", b"Old name that is whole"
        v1 = b"VVFP Long Names v1\n" + short + b"\t" + whole + b"\n"
        v2 = b"VVFP Long Names v2\n" + ln.record_v2(short, whole)
        self.assertEqual(ln.parse(v1), {short: whole})
        self.assertEqual(ln.parse(v2), {short: whole})
        self.assertEqual(ln.records(v2), [(short, 0, whole)])           # a v2 record has no room: 0 = unknown
        # an older build's ellipsis mark (0x85) is read as well
        old_mark = b"Old name\x85"
        self.assertEqual(ln.parse(ln.HEADER + ln.record(old_mark, whole)), {old_mark: whole})

    def test_invalid_records_are_skipped(self):
        whole = b"A whole name"
        cases = {
            "no mark": ln.record(b"A whole", whole, 24),
            "too long for its room": ln.record(b"A whole name x...", whole, 10),
            "a control character": ln.record(b"A wh\x07...", whole, 24),
            "a control character in the whole name": ln.record(b"A who...", b"A whole\x01name", 24),
            "over 1,200 bytes": ln.record(b"A who...", b"x" * 1201, 24),
            "empty whole name": ln.record(b"A who...", b"", 24),
        }
        for label, record in cases.items():
            with self.subTest(label):
                self.assertEqual(ln.parse(ln.HEADER + record), {})
        good = ln.record(b"A who...", whole, 24)
        self.assertEqual(ln.parse(ln.HEADER + good), {b"A who...": whole})
        # a record cut short, or a wrong checksum
        self.assertEqual(ln.parse(ln.HEADER + good[:-3] + b"\n"), {})
        self.assertEqual(ln.parse(ln.HEADER + good.replace(b"A whole name", b"A whole nome")), {})

    def test_the_first_record_of_a_short_form_wins(self):
        a = ln.record(b"Name...", b"First whole", 24)
        b = ln.record(b"Name...", b"Second whole", 24)
        self.assertEqual(ln.parse(ln.HEADER + a + b), {b"Name...": b"First whole"})

    def test_write_makes_the_file_in_a_tmp_and_moves_it_and_keeps_every_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            file = Path(tmp) / "Data" / "Long Names" / ln.file_name(3, 1)
            file.parent.mkdir(parents=True)
            old = (b"VVFP Long Names v2\n" + ln.record_v2(b"Old...", b"Old whole")
                   + ln.record_v2(b"bad", b"no mark"))                      # an invalid record is not carried
            file.write_bytes(old)
            replaced = []
            real = os.replace

            def watch(src, dst):
                replaced.append((Path(src).name, Path(dst).name))
                return real(src, dst)

            with mock.patch.object(os, "replace", watch):
                ln.write(file, [(b"New...", 24, b"New whole"), (b"Old...", 24, b"Another")])
            self.assertEqual(replaced, [(file.name + ".tmp", file.name)])
            self.assertFalse(file.with_name(file.name + ".tmp").exists())
            self.assertTrue(file.read_bytes().startswith(b"VVFP Long Names v3\n"))
            self.assertEqual(ln.records(file.read_bytes()), [(b"Old...", 0, b"Old whole"), (b"New...", 24, b"New whole")])

    def test_a_refused_move_writes_in_place_without_emptying_the_file_first(self):
        with tempfile.TemporaryDirectory() as tmp:
            file = Path(tmp) / ln.file_name(3, 1)
            file.write_bytes(ln.HEADER + ln.record(b"Old...", b"Old whole", 24))
            with mock.patch.object(os, "replace", side_effect=PermissionError("held open")):
                ln.write(file, [(b"New...", 24, b"New whole")])
            self.assertEqual([r[0] for r in ln.records(file.read_bytes())], [b"Old...", b"New..."])
            self.assertFalse(file.with_name(file.name + ".tmp").exists())

    def test_a_failed_copy_leaves_the_old_file_untouched(self):
        with tempfile.TemporaryDirectory() as tmp:
            file = Path(tmp) / ln.file_name(3, 1)
            before = ln.HEADER + ln.record(b"Old...", b"Old whole", 24)
            file.write_bytes(before)
            real_open = open

            def failing(path, mode="r", *args, **kwargs):
                if str(path).endswith(".tmp"):
                    raise OSError("disk full")
                return real_open(path, mode, *args, **kwargs)

            with mock.patch("builtins.open", failing):
                with self.assertRaises(OSError):
                    ln.write(file, [(b"New...", 24, b"New whole")])
            self.assertEqual(file.read_bytes(), before)

    def test_write_refuses_an_invalid_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                ln.write(Path(tmp) / "x.dat", [(b"no mark", 24, b"whole")])

    def test_the_c_header_and_the_python_header_agree(self):
        native = (ROOT / "native" / "vvfp_unicode_text" / "long_names.inc").read_text(encoding="utf-8")
        self.assertIn('#define LN_HEADER "VVFP Long Names v3\\n"', native)
        self.assertEqual(ln.HEADER, b"VVFP Long Names v3\n")
        self.assertIn("MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH", native)


class RenameTribeLongName(unittest.TestCase):
    """UNICODE_SPEC section 6: Rename Tribe takes 1,200 bytes, keeps a short form in the field and the whole
    name in the Long Names file, and undoes everything when a step fails."""

    def setUp(self):
        import test_tribe_rename as base
        self.base = base
        self._tmp = tempfile.TemporaryDirectory()
        self.documents = Path(self._tmp.name) / "Documents"
        self.folder = self.documents / "LDW" / "Virtual Villagers - The Secret City - Modded"
        self.folder.mkdir(parents=True)
        self.game = rename.GAMES[2]
        self.game.save_path(self.folder, 1).write_bytes(base.fixture("vv3-huttest-1"))
        self.game.index_path(self.folder).write_bytes(base.fixture("vv3-huttest-0"))

    def tearDown(self):
        self._tmp.cleanup()

    def run_rename(self, name, slot=1):
        return rename.rename_tribe(self.game, self.folder, slot, name, self.base.FakeProcesses(), self.base.NOW)

    def test_a_name_that_fits_is_kept_exactly_and_makes_no_record(self):
        result = self.run_rename("Short Tribe")
        self.assertEqual(result.stored_name, "Short Tribe")
        self.assertIsNone(result.long_names)
        self.assertFalse(ln.path(self.folder, 3, 1).exists())

    def test_a_long_name_is_a_short_form_in_the_save_and_whole_in_the_sidecar(self):
        whole = "Alexandria Montgomery-Smith the Third of Kalahuna"
        result = self.run_rename(whole)
        self.assertEqual(result.new_name, whole)
        self.assertEqual(result.stored_name, "Alexandria Montg...")
        self.assertEqual(rename.save_name(self.game, self.game.save_path(self.folder, 1).read_bytes()), "Alexandria Montg...")
        self.assertEqual(rename.index_name(self.game, self.game.index_path(self.folder).read_bytes(), 1), "Alexandria Montg...")
        data = ln.path(self.folder, 3, 1).read_bytes()
        self.assertEqual(ln.records(data), [(b"Alexandria Montg...", self.game.max_length + 1, whole.encode())])
        self.assertEqual(result.long_names, ln.path(self.folder, 3, 1))
        # the tool lists it whole
        self.assertEqual(rename.read_slots(self.game, self.folder)[0].name, whole)

    def test_the_longest_name_is_1200_bytes_as_stored_and_one_more_is_refused(self):
        self.assertIsNone(rename.name_problem(self.game, "N" * 1200, long_names=True))
        problem = rename.name_problem(self.game, "N" * 1201, long_names=True)
        self.assertIn("1,200", problem)
        cjk = JAPANESE * 20                      # 3 bytes a character
        self.assertEqual(byte_length(cjk[:400]), 1200)
        self.assertIsNone(rename.name_problem(self.game, cjk[:400], long_names=True))
        self.assertIsNotNone(rename.name_problem(self.game, cjk[:401], long_names=True))
        result = self.run_rename("N" * 1200)
        self.assertEqual(ln.parse(ln.path(self.folder, 3, 1).read_bytes())[result.stored_name.encode()], b"N" * 1200)

    def test_without_the_long_flag_the_stock_limit_stays_for_copy_player_slot(self):
        self.assertIsNotNone(rename.name_problem(self.game, "N" * (self.game.max_length + 1)))

    def test_codepoint_rule_takes_letters_newer_than_pythons_data(self):
        self.assertIsNone(rename.name_problem(self.game, "Tribe \U0003134A\U000E0100", long_names=True))
        self.assertIsNotNone(rename.name_problem(self.game, "Bad\x07", long_names=True))

    def test_a_cjk_name_is_cut_at_whole_characters(self):
        result = self.run_rename(JAPANESE)
        short = result.stored_name
        self.assertTrue(short.endswith("..."))
        self.assertTrue(JAPANESE.startswith(short[:-3]))
        self.assertLess(byte_length(short), self.game.max_length + 1)

    def test_two_names_starting_alike_get_a_number_before_the_dots(self):
        first = self.run_rename("Alexandria Montgomery-Smith one")
        second = self.base.rename.rename_tribe(self.game, self.folder, 1, "Alexandria Montgomery-Smith two",
                                               self.base.FakeProcesses(), self.base.NOW)
        self.assertEqual(first.stored_name, "Alexandria Montg...")
        self.assertEqual(second.stored_name, "Alexandria Mont2...")
        pairs = ln.parse(ln.path(self.folder, 3, 1).read_bytes())
        self.assertEqual(pairs[b"Alexandria Montg..."], b"Alexandria Montgomery-Smith one")
        self.assertEqual(pairs[b"Alexandria Mont2..."], b"Alexandria Montgomery-Smith two")
        # renaming back to a name that already has its short form uses that one again
        third = self.run_rename("Alexandria Montgomery-Smith one")
        self.assertEqual(third.stored_name, "Alexandria Montg...")

    def test_a_failed_step_puts_the_sidecar_and_every_file_back(self):
        before = {p.relative_to(self.folder).as_posix(): p.read_bytes() for p in self.folder.rglob("*")
                  if p.is_file() and "Backups" not in p.relative_to(self.folder).parts}
        real = rename._write_atomically
        calls = []

        def failing(path, data):
            calls.append(path.name)
            if len(calls) == 2:
                raise OSError("disk full")
            return real(path, data)

        with mock.patch.object(rename, "_write_atomically", failing):
            with self.assertRaises(rename.RenameError):
                self.run_rename("Alexandria Montgomery-Smith the Third of Kalahuna")
        after = {p.relative_to(self.folder).as_posix(): p.read_bytes() for p in self.folder.rglob("*")
                 if p.is_file() and "Backups" not in p.relative_to(self.folder).parts}
        self.assertEqual(after, before)
        self.assertFalse(ln.path(self.folder, 3, 1).exists())

    def test_a_failed_step_restores_an_existing_sidecar_byte_for_byte(self):
        file = ln.path(self.folder, 3, 1)
        file.parent.mkdir(parents=True)
        original = ln.HEADER + ln.record(b"Other...", b"Other whole", 20)
        file.write_bytes(original)
        real = rename._write_atomically
        count = []

        def failing(path, data):
            count.append(path)
            if len(count) == 2:
                raise OSError("disk full")
            return real(path, data)

        with mock.patch.object(rename, "_write_atomically", failing):
            with self.assertRaises(rename.RenameError):
                self.run_rename("Alexandria Montgomery-Smith the Third of Kalahuna")
        self.assertEqual(file.read_bytes(), original)

    def test_logs_get_no_rename_note_for_a_name_past_the_63_character_line(self):
        result = self.run_rename("N" * 100)
        self.assertEqual(result.notes, [])
        self.assertIn("63", result.notes_skipped)


class CopyPlayerSlotCarriesTheLongNames(unittest.TestCase):
    """UNICODE_SPEC section 2, Re-keying: Copy Player Slot copies the source's Long Names file with its slot
    renamed."""

    def test_the_file_name_is_re_keyed_with_the_slot(self):
        import vv_copy_slot
        source = ln.path(Path("X"), 3, 2).relative_to("X")
        moved = vv_copy_slot._rename_slot_in_name(source.name, 2, 4)
        self.assertEqual(moved, ln.file_name(3, 4))
        self.assertEqual(vv_copy_slot._rename_slot_in_name(ln.file_name(5, 1), 1, 5), ln.file_name(5, 5))


CF_HARNESS = ROOT / "scripts" / "build_colour_harness.ps1"
CL = Path(r"C:\Program Files\Microsoft Visual Studio\18\Community\VC\Tools\MSVC\14.51.36231\bin\Hostx64\x86\cl.exe")


def run_colour_harness(*args: str) -> str:
    import subprocess
    result = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(CF_HARNESS), *args],
                            capture_output=True, text=True, timeout=600)
    return (result.stdout + result.stderr).strip()


class ColourFonts(unittest.TestCase):
    """UNICODE_SPEC section 3, "Colour emoji": colour fonts in every format (COLR/CPAL, CBDT, sbix, SVG)."""

    @classmethod
    def setUpClass(cls):
        cls.source = (ROOT / "native" / "vvfp_unicode_text" / "colour_fonts.inc").read_text(encoding="utf-8")
        cls.runtime = (ROOT / "native" / "vvfp_unicode_text" / "runtime_glyphs.inc").read_text(encoding="utf-8")

    def test_the_three_bitmap_and_svg_tables_are_looked_for(self):
        for tag in ("'CBDT'", "'sbix'", "'SVG '"):
            self.assertIn(tag, self.source)
        self.assertIn("CF_ENABLE_COLOR_FONT 4", self.source)           # D2D1_DRAW_TEXT_OPTIONS_ENABLE_COLOR_FONT

    def test_direct2d_is_loaded_from_system32_only(self):
        self.assertIn("LoadLibraryExW(L\"d2d1.dll\", NULL, CF_SEARCH_SYSTEM32)", self.source)
        self.assertIn("LoadLibraryExW(L\"dwrite.dll\", NULL, CF_SEARCH_SYSTEM32)", self.source)
        self.assertNotRegex(self.source, r"LoadLibrary[AW]\(")
        self.assertIn("0x00000800", self.source)                      # LOAD_LIBRARY_SEARCH_SYSTEM32

    def test_vvs_own_colr_renderer_is_kept_and_the_bitmap_path_never_replaces_it(self):
        self.assertIn("rg_layers(colr, glyphs[j], &at)", self.runtime)
        self.assertIn("if (cv != NULL && colr == NULL) {", self.runtime)
        self.assertIn("answers 0 and the letter is drawn", self.source.replace("\n   ", " ").replace("  ", " "))

    def test_the_dll_does_not_import_loadlibrary_a_or_w(self):
        import pefile
        for dll in (ROOT / "assets" / "unicode_text" / "VVFP Unicode Text.dll",
                    ROOT / "assets" / "unicode_font" / "VVFP Unicode Font.dll"):
            pe = pefile.PE(str(dll))
            imports = {i.name.decode() for e in pe.DIRECTORY_ENTRY_IMPORT for i in e.imports if i.name}
            self.assertFalse(imports & {"LoadLibraryA", "LoadLibraryW"}, dll.name)
            self.assertIn("LoadLibraryExW", imports, dll.name)

    @unittest.skipUnless(sys.platform == "win32" and CL.is_file(), "needs Windows and the MSVC build tools")
    def test_direct2d_draws_a_colour_emoji_in_its_own_colours(self):
        out = run_colour_harness("Segoe UI Emoji", "400", "48", "1F600")
        if "unavailable" in out:
            self.skipTest("this Windows has no Direct2D")
        self.assertRegex(out, r"colour=1 ink=\d+")
        ink = int(re.search(r"ink=(\d+)", out).group(1))
        kinds = int(re.search(r"rgb=(\d+)", out).group(1))
        self.assertGreater(ink, 500)
        self.assertGreater(kinds, 8)                                  # several colours, not one tinted

    @unittest.skipUnless(sys.platform == "win32" and CL.is_file(), "needs Windows and the MSVC build tools")
    def test_a_skin_tone_sequence_is_one_coloured_glyph(self):
        out = run_colour_harness("Segoe UI Emoji", "400", "48", "1F44D", "1F3FD")
        if "unavailable" in out:
            self.skipTest("this Windows has no Direct2D")
        self.assertIn("colour=1", out)

    @unittest.skipUnless(sys.platform == "win32" and CL.is_file(), "needs Windows and the MSVC build tools")
    def test_a_letter_in_a_plain_face_has_no_colour_so_gdi_draws_it(self):
        out = run_colour_harness("Segoe UI", "400", "48", "41")
        if "unavailable" in out:
            self.skipTest("this Windows has no Direct2D")
        self.assertIn("colour=0", out)

    @unittest.skipUnless(sys.platform == "win32" and CL.is_file(), "needs Windows and the MSVC build tools")
    def test_the_table_check_tells_colr_from_bitmap_colour_fonts(self):
        out = run_colour_harness("Segoe UI Emoji", "tables", "0", "0")
        self.assertRegex(out, r"installed=1 bitmap=\d")
        bitmap = run_colour_harness("Noto Color Emoji", "tables", "0", "0")
        if "installed=1" in bitmap:                                   # Noto Color Emoji is CBDT
            self.assertIn("bitmap=1", bitmap)
        self.assertIn("bitmap=0", run_colour_harness("Segoe UI", "tables", "0", "0"))


class UnicodeFontArithmetic(unittest.TestCase):
    """The preview's em fitting is the companion's (runtime_glyphs.inc rg_fit_em)."""

    def test_the_em_that_makes_the_sentence_as_wide_is_kept_within_60_and_130_percent(self):
        import vv_unicode_font as uf
        self.assertEqual(uf.fit_em(20, 500, 500), 20 * 13 // 10)          # 200 px/em would be needed: 130% is the most
        self.assertEqual(uf.fit_em(20, 600, 60000), 20 * 6 // 10)         # 2 px/em would do: 60% is the least
        self.assertEqual(uf.fit_em(20, 600, 1000), 20 * 13 // 10)         # 200 * 600 / 1000 = 120 ... clamped to 130%
        self.assertEqual(uf.fit_em(20, 0, 1000), 20)                      # the game's width is unknown: its own em
        self.assertEqual(uf.fit_em(20, 600, 0), 20)

    def test_a_face_that_fits_is_rounded_to_the_nearest_pixel(self):
        import vv_unicode_font as uf
        # the face is 10 px wide at 200 px/em for 1 px of game width: em 20 exactly
        self.assertEqual(uf.fit_em(30, 100, 1000), 20)
        self.assertEqual(uf.fit_em(30, 110, 1000), 22)

    def test_the_game_fonts_own_em_is_the_one_arials_capitals_have(self):
        import vv_unicode_font as uf
        self.assertEqual(uf.own_em(14), 20)       # 14 px of capital: Arial's 716/1000 gives a 20 px em
        self.assertEqual(uf.own_em(0), 0)

    def test_the_python_chain_is_the_companions(self):
        import vv_unicode_font as uf
        self.assertEqual(list(uf.FALLBACK_CHAIN), native_chain())

    def test_the_c_arithmetic_is_the_same(self):
        source = (ROOT / "native" / "vvfp_unicode_text" / "runtime_glyphs.inc").read_text(encoding="utf-8")
        self.assertIn("(cap * 1000 + 358) / 716", source)                      # own_em
        self.assertIn("(int)(((__int64)200 * game * 2 + adv) / (2 * (__int64)adv))", source)   # fit_em


class UnicodeFontChoice(unittest.TestCase):
    """The choice the Unicode Font window and the patch-selection box both write."""

    def setUp(self):
        import vv_fun_patcher as vfp
        self.vfp = vfp
        self.saved = (vfp._unicode_font_face, vfp._unicode_font_file)

    def tearDown(self):
        self.vfp._unicode_font_face, self.vfp._unicode_font_file = self.saved

    def a_font(self) -> Path:
        for name in ("arial.ttf", "segoeui.ttf", "tahoma.ttf"):
            path = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts" / name
            if path.is_file():
                return path
        self.skipTest("no system font file to use")

    def test_a_font_file_gives_its_own_family_and_a_bad_one_is_refused(self):
        import vv_unicode_font as uf
        file, family = uf.check_font_file(self.a_font())
        self.assertTrue(family)
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "not a font.ttf"
            bad.write_bytes(b"this is not a font")
            with self.assertRaises(uf.FontChoiceError):
                uf.check_font_file(bad)
            with self.assertRaises(uf.FontChoiceError):
                uf.check_font_file(Path(tmp) / "x.txt")
            with self.assertRaises(self.vfp.PatcherError):
                self.vfp.set_unicode_font_file(bad)

    def test_the_patch_writes_the_face_and_copies_the_file_beside_the_companion(self):
        font = self.a_font()
        family = self.vfp.set_unicode_font_file(font) and self.vfp.unicode_font_face()
        self.assertTrue(family)
        feature = mock.Mock()
        feature.id = "vv3_unicode_font"
        feature.raw = {"companion_files": [{"destination": "Virtual Villagers Fun Patcher Files/VVFP Unicode Font.dll"}]}
        with tempfile.TemporaryDirectory() as out:
            with mock.patch.object(self.vfp, "_safe_companion_destination", side_effect=lambda d: Path(d)):
                self.vfp._write_unicode_font_choice(Path(out), [feature])
            folder = Path(out) / "Virtual Villagers Fun Patcher Files"
            lines = (folder / "VVFP Unicode Font.txt").read_text(encoding="utf-8").splitlines()
            self.assertEqual(lines, [family, font.name])
            self.assertEqual((folder / "Unicode Font" / font.name).read_bytes(), font.read_bytes())

    def test_with_no_file_only_the_face_is_written(self):
        self.vfp.set_unicode_font_file(None)
        self.vfp.set_unicode_font_face("Yu Gothic")
        feature = mock.Mock()
        feature.id = "vv1_unicode_font"
        feature.raw = {"companion_files": [{"destination": "Files/VVFP Unicode Font.dll"}]}
        with tempfile.TemporaryDirectory() as out:
            with mock.patch.object(self.vfp, "_safe_companion_destination", side_effect=lambda d: Path(d)):
                self.vfp._write_unicode_font_choice(Path(out), [feature])
            self.assertEqual((Path(out) / "Files" / "VVFP Unicode Font.txt").read_text(encoding="utf-8"), "Yu Gothic\n")
            self.assertFalse((Path(out) / "Files" / "Unicode Font").exists())

    def test_the_command_line_takes_the_font_file(self):
        source = (ROOT / "src" / "vv_fun_patcher.py").read_text(encoding="utf-8")
        self.assertIn('"--unicode-font-file"', source)
        self.assertIn('"--unicode-font"', source)

    def test_the_companion_loads_the_file_for_the_game_only(self):
        source = (ROOT / "native" / "vvfp_unicode_text" / "vvfp_unicode_text.c").read_text(encoding="utf-8")
        self.assertIn("AddFontResourceExW(dir, FR_PRIVATE, NULL)", source)
        self.assertIn('L"Unicode Font\\\\"', source)
        self.assertIn("a name with a path in it", source)


class UnicodeFontWindowTool(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import tkinter as tk
        try:
            cls.root = tk.Tk()
        except tk.TclError as exc:
            raise unittest.SkipTest(f"no Tk display: {exc}")
        cls.root.withdraw()

    @classmethod
    def tearDownClass(cls):
        cls.root.destroy()

    def test_the_window_lists_installed_fonts_searches_and_saves_the_choice(self):
        import vv_unicode_font as uf
        saved = []
        window = uf.open_window(self.root, images_dirs={}, get_choice=lambda: ("Segoe UI", None),
                                set_choice=lambda face, file: saved.append((face, file)))
        window.quiet = True
        try:
            self.root.update()
            self.assertTrue(window.faces)
            window.search_var.set("segoe")
            self.assertTrue(window.shown_faces and all("segoe" in f.casefold() for f in window.shown_faces))
            window.face_list.selection_set(0)
            window.face_picked()
            self.assertEqual(window.face, window.shown_faces[0])
            window.save()
            self.assertEqual(saved, [(window.shown_faces[0], None)])
            self.assertIs(uf.open_window(self.root), window)             # one window
        finally:
            window.close()

    def test_a_font_file_is_chosen_and_saved_with_its_family(self):
        import vv_unicode_font as uf
        font = None
        for name in ("arial.ttf", "segoeui.ttf", "tahoma.ttf"):
            path = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts" / name
            if path.is_file():
                font = path
                break
        if font is None:
            self.skipTest("no system font file")
        saved = []
        window = uf.open_window(self.root, images_dirs={}, set_choice=lambda face, file: saved.append((face, file)))
        window.quiet = True
        try:
            window.choose_file(str(font))
            window.save()
            self.assertEqual(saved[0][1], font)
            self.assertEqual(saved[0][0], uf.font_file_family(font.read_bytes()))
            window.choose_file(str(font.with_suffix(".txt")))
            self.assertIn(".ttf", window.last_message)
        finally:
            window.close()

    def test_the_patcher_window_has_both_tools_on_both_tabs(self):
        source = (ROOT / "src" / "vv_fun_patcher_gui.py").read_text(encoding="utf-8")
        self.assertEqual(source.count('"Unicode Font..."'), 2)
        self.assertEqual(source.count('"Game Text..."'), 2)
        self.assertIn("vv_unicode_font.open_window(", source)
        self.assertIn("vv_picture_studio.open_picture_studio(self, build)", source)
        import json
        guides = json.loads((ROOT / "data" / "how_to_use.json").read_text(encoding="utf-8"))
        self.assertIn("unicode_font_tool", guides["controls"])
        self.assertIn("game_text", guides["controls"])


def have_game_images(number: int) -> bool:
    names = {1: "A New Home", 2: "The Lost Children", 3: "The Secret City", 4: "The Tree of Life", 5: "New Believers"}
    return (ROOT / "research" / "game-images" / f"Virtual Villagers - {names[number]}" / "Images" /
            "ldwarialbold.png").is_file()


@unittest.skipUnless(sys.platform == "win32" and have_game_images(3), "needs Windows and the game pictures")
class UnicodeFontPreview(unittest.TestCase):
    def test_the_preview_is_as_wide_as_the_game_font_and_as_tall_as_its_line(self):
        import vv_font_glyphs as vfg
        import vv_unicode_font as uf
        folder = ROOT / "research" / "game-images" / "Virtual Villagers - The Secret City" / "Images"
        for font in uf.GAME_FONTS:
            with self.subTest(font=font):
                game = vfg.text_width("vv3", font, uf.FIT_REFERENCE, folder)
                picture = uf.render("vv3", font, "Segoe UI", uf.FIT_REFERENCE, folder)
                self.assertEqual(picture.height, vfg.metrics("vv3", font, folder).line)
                self.assertLess(abs(picture.width - game), game * 0.15, (picture.width, game))

    def test_a_character_the_face_lacks_comes_from_the_fallback_chain(self):
        import vv_unicode_font as uf
        folder = ROOT / "research" / "game-images" / "Virtual Villagers - The Secret City" / "Images"
        plain = uf.render("vv3", "ldwarialbold", "Segoe UI", "\u65e5", folder)       # a CJK character
        self.assertTrue(plain.bbox())                                                # drawn, not blank


@unittest.skipUnless(have_game_images(5), "needs the game pictures")
class GameTextTool(unittest.TestCase):
    """UNICODE_SPEC section 10: the Text tab shows the stock game, Use Unicode Font, and labels each character."""

    @classmethod
    def setUpClass(cls):
        import tkinter as tk
        try:
            cls.root = tk.Tk()
        except tk.TclError as exc:
            raise unittest.SkipTest(f"no Tk display: {exc}")
        cls.root.withdraw()

    @classmethod
    def tearDownClass(cls):
        cls.root.destroy()

    def setUp(self):
        import shutil
        import vv_picture_image as pi
        import vv_picture_studio as ps
        import vv_pictures_common as common
        from test_picture_studio import FakeModule
        self.ps, self.common, self.pi, self.shutil = ps, common, pi, shutil
        self.tmp = Path(tempfile.mkdtemp(prefix="vvgametext"))
        self.saved = (ps.load_renderer_module, common.save_folders, common.slots, pi.CACHE_ROOT)
        ps.load_renderer_module = lambda game: FakeModule
        common.save_folders = lambda game, documents=None: []
        common.slots = lambda folder, game: []
        pi.CACHE_ROOT = self.tmp / "cache"
        images = ROOT / "research" / "game-images" / "Virtual Villagers - New Believers" / "Images"
        self.window = ps.open_window(self.root, 5, game_folders=[images.parent])
        self.window.quiet = True
        self.root.update()
        self.tab = self.window.text_tab

    def tearDown(self):
        self.window.close()
        self.ps.load_renderer_module, self.common.save_folders, self.common.slots, self.pi.CACHE_ROOT = self.saved
        self.shutil.rmtree(self.tmp, ignore_errors=True)

    def test_the_two_views_exclude_each_other(self):
        tab = self.tab
        tab.stock_var.set(True)
        tab.unicode_var.set(True)
        tab._exclusive(tab.unicode_var, tab.stock_var)
        self.assertFalse(tab.stock_var.get())
        tab.stock_var.set(True)
        tab._exclusive(tab.stock_var, tab.unicode_var)
        self.assertFalse(tab.unicode_var.get())

    def test_use_unicode_font_draws_every_character_in_the_chosen_face(self):
        import vv_fun_patcher
        saved = vv_fun_patcher._unicode_font_face
        vv_fun_patcher.set_unicode_font_face("Segoe UI")
        try:
            tab = self.tab
            tab.set_text("Hello\n\u65e5\u672c")
            tab.stock_var.set(False)
            tab.unicode_var.set(True)
            tab.refresh()
            self.assertEqual(sum(tab.rendered.counts.values()), 7)
            image = tab.rendered.image
            self.assertEqual(image.height, 2 * tab.renderer().line_height)
            self.assertTrue(image.bbox())
            tab.stock_var.set(True)
            tab.unicode_var.set(False)
            tab.refresh()
            self.assertNotEqual(tab.rendered.image, image)            # the stock game's own letters differ
        finally:
            vv_fun_patcher._unicode_font_face = saved

    def test_the_picker_labels_where_a_character_comes_from(self):
        import vv_pictures_text as text
        renderer = self.tab.renderer()
        self.assertEqual(text.char_label(renderer, "A"), "(game)")
        self.assertIn(text.char_label(renderer, "\u00e9"), ("(game)", "(patcher-made)"))
        self.assertIn(text.char_label(renderer, "\u20ac"), ("(game)", "(patcher-made)"))
        label = text.char_label(renderer, "\u65e5")
        self.assertTrue(label.startswith("(drawn by Windows") or label == "(missing)", label)
        picker = self.tab.open_picker()
        picker.query.set("latin capital letter a")
        picker.search()
        self.assertIn("(game)", picker.results.get(0))
        picker.window.destroy()

    def test_the_stock_view_is_worded_as_the_spec_says(self):
        source = (ROOT / "src" / "vv_pictures_text_tab.py").read_text(encoding="utf-8")
        self.assertIn('"As the stock game shows it"', source)
        self.assertIn('"As Use Unicode Font draws it"', source)


class DocsWording(unittest.TestCase):
    """UNICODE_SPEC section 9: the shared release-note paragraph and the same fallback-chain wording."""

    def test_the_manifests_use_the_shared_paragraph_in_every_game(self):
        import json
        for game in range(1, 6):
            for kind in ("text", "font"):
                with self.subTest(game=game, kind=kind):
                    data = json.loads((ROOT / "data" / f"vv{game}_unicode_{kind}_feature.json").read_text(encoding="utf-8"))
                    text = json.dumps(data, ensure_ascii=False)
                    self.assertIn("Long names, everywhere: every name box takes names up to 1,200 bytes", text)
                    self.assertIn("(up to 1,200 plain letters; fewer when letters need more bytes)", text)
                    self.assertIn("It is one limit, shared with the other Fun Patchers.", text)
                    self.assertIn("Characters are counted as you see them", text)
                    self.assertIn("Segoe UI Emoji (in colour), the CJK fonts, Nirmala UI, Ebrima ..., Noto if installed", text)
                    self.assertNotIn("Every box takes the same limit", text)

    def test_readme_how_to_use_and_the_guide_say_the_same(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        howto = (ROOT / "How to Use.txt").read_text(encoding="utf-8")
        guide = (ROOT / "data" / "how_to_use.json").read_text(encoding="utf-8")
        self.assertGreaterEqual(readme.count("Long names, everywhere: every name box takes names up to 1,200 bytes"), 10)
        self.assertNotIn("Every box takes the same limit", readme)
        self.assertNotIn("Segoe UI Emoji in colour, Yu Gothic", readme)
        self.assertIn("Long names, everywhere. Every name box takes names up to 1,200 bytes", howto)
        self.assertIn("1,200 plain letters", howto)
        self.assertIn("Name boxes take up to 1,200 plain letters", guide)

    def test_the_setting_descriptions_say_characters_and_colour_emoji(self):
        import json
        text = json.dumps(json.loads((ROOT / "data" / "vv2_unicode_font_feature.json").read_text(encoding="utf-8")),
                          ensure_ascii=False)
        self.assertIn("any installed family, or a .ttf, .otf or .ttc file", text)
        self.assertIn("fitted so a line is as wide as the game's own", text)
        self.assertIn("Not yet seen in a running game", text)


class HooksAreInstalledBeforeTheContractAnswers(unittest.TestCase):
    """UNICODE_SPEC section 8: VvfpGlyphsUtf8 answers 1 only once the hooks are installed."""

    def test_g_installed_is_set_only_after_the_sites_were_installed(self):
        source = (ROOT / "native" / "vvfp_unicode_text" / "vvfp_unicode_text.c").read_text(encoding="utf-8")
        self.assertEqual(source.count("g_installed = 1;"), 1)
        before = source[:source.index("g_installed = 1;")]
        self.assertTrue(before.rstrip().endswith("}"))                       # the failure branch returns first
        self.assertIn("if (!vvfp_install_sites(sites, n)) {", before[-400:])
        self.assertIn("return g_installed ? 1 : 0;", source)


if __name__ == "__main__":
    unittest.main()
