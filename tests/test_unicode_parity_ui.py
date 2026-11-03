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
        self.assertIsNotNone(rename.name_problem(self.game, "Bad ", long_names=True))

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


if __name__ == "__main__":
    unittest.main()
