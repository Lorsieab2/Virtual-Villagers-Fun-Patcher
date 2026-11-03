"""Unicode parity (VV): the shared spec's chain, sidecar v3, tribe rename, "%" rule, Unicode Font and Game Text tools.

One class per item, so a failure names the spec row it breaks.
"""
from __future__ import annotations

import os
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import vv_long_names as ln  # noqa: E402

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


if __name__ == "__main__":
    unittest.main()
