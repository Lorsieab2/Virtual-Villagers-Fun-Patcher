"""Unicode in game (v1.35.89): UTF-8 names, any character, Use Unicode Font, the shared name limit.

Proofs, all five games:
  * the reading rule (src/vv_game_text.py == native/vvfp_unicode_text/text_utf8.h): UTF-8 where well formed,
    Windows-1252 otherwise; every byte string the games ever wrote round-trips;
  * the detoured routines' addresses and stock bytes are the stock executables' own, and no byte patch of the
    catalog overlaps them;
  * the rows: conflicts, dependency, defaults (on / off / Owner's Defaults / Select All);
  * EMULATION of each published build (startup chain -> the companion's detours -> the game's own code) for
    the owner's test names -- U+1F4A9 and the five cuneiform signs U+1208D U+12000 U+1223E U+12362 U+12155 --
    "Zoe Nunez" with its accents, and a long Japanese name: typing (ready-made UTF-8 and the two UTF-16 halves
    SDL 2.0.3 sends for an emoji-panel character), the box's limit, Backspace erasing whole characters, the
    width, draw and centred draw, line fitting (VV2-VV5) with Chinese/Japanese breaks, the counted draw and the
    justified paragraph (VV3-VV5), a long name's short form and its whole name, and the Details round trip
    (SetText, then GetText of the field's size without editing: the bytes stay identical).
Skips (never errors) without the stock executables, the game images, Windows or unicorn.
"""
from __future__ import annotations

import json
import os
import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT / "scripts"))

from vv_game_text import GAME_TEXT, byte_length, decode_game_text, encode_game_text, fit_bytes, printable  # noqa: E402

GAMES = ("vv1", "vv2", "vv3", "vv4", "vv5")
NAMES = {
    "vv1": "A New Home", "vv2": "The Lost Children", "vv3": "The Secret City", "vv4": "The Tree of Life",
    "vv5": "New Believers",
}
STOCK = ROOT / "research" / "stock-executables"
IMAGES = ROOT / "research" / "game-images"
POO = "\U0001F4A9"
CUNEIFORM = "\U0001208D\U00012000\U0001223E\U00012362\U00012155"
ZOE = "Zoë Ñúñez"
JAPANESE = "山田太郎・アレクサンドラ・モンゴメリー・スミス三世"
CENTRED = {"vv1": 0x4094C0, "vv2": 0x4096B0, "vv3": 0x40A070, "vv4": 0x409BE0, "vv5": 0x409EB0}
FIELD = {"vv1": 0x1C, "vv2": 0x18, "vv3": 0x18, "vv4": 0x18, "vv5": 0x18}    # Details GetText with Full Names

try:
    import unicorn  # noqa: F401
    import pefile  # noqa: F401
    import capstone  # noqa: F401
    HAVE_EMULATOR = True
except ImportError:                                  # pragma: no cover
    HAVE_EMULATOR = False
HAVE_STOCK = all((STOCK / f"Virtual Villagers - {n}.exe").is_file() for n in NAMES.values())
HAVE_IMAGES = all((IMAGES / f"Virtual Villagers - {n}" / "Images" / "ldwBurweed27.png").is_file() for n in NAMES.values())
ON_WINDOWS = os.name == "nt"


class TheReadingRule(unittest.TestCase):
    def test_the_owners_names_round_trip(self):
        for name in (POO, CUNEIFORM, ZOE, JAPANESE, "İstanbul ığüşöç", "مرحبا"):
            raw = name.encode(GAME_TEXT)
            self.assertEqual(raw.decode(GAME_TEXT), name)
        self.assertEqual(POO.encode(GAME_TEXT), b"\xf0\x9f\x92\xa9")
        self.assertEqual(len(CUNEIFORM.encode(GAME_TEXT)), 20)
        self.assertEqual(ZOE.encode(GAME_TEXT), b"Zo\xeb \xd1\xfa\xf1ez")    # Windows-1252 keeps one byte each

    def test_every_byte_the_games_wrote_reads_and_writes_back(self):
        self.assertEqual(bytes(range(256)).decode(GAME_TEXT).encode(GAME_TEXT), bytes(range(256)))
        self.assertEqual(b"\x8a\xe1rka".decode(GAME_TEXT), "Šárka")
        # A lone or cut-off sequence is Windows-1252, never an error.
        self.assertEqual(b"\xf0\x9f\x92".decode(GAME_TEXT), "ðŸ’")
        self.assertEqual(b"\xed\xa0\xbd".decode(GAME_TEXT), "í ½")      # a surrogate is not UTF-8

    def test_a_windows_1252_pair_that_spells_utf8_is_written_as_utf8(self):
        self.assertEqual(encode_game_text("Ã©").decode(GAME_TEXT), "Ã©")
        self.assertEqual(decode_game_text(encode_game_text("Ã©")), "Ã©")

    def test_byte_counts_and_cuts_never_split_a_character(self):
        self.assertEqual(byte_length(CUNEIFORM), 20)
        self.assertEqual(fit_bytes(CUNEIFORM, 18), CUNEIFORM[:4])
        self.assertEqual(fit_bytes("\U0001F44D\U0001F3FD!", 7), "")           # thumbs up and its skin tone go together
        self.assertEqual(fit_bytes("ab\U0001F44D\U0001F3FD", 9), "ab")
        self.assertTrue(printable(POO) and printable("‍") and not printable("\x07"))


class TheLongNamesFile(unittest.TestCase):
    """src/vv_long_names.py reads the file native/vvfp_unicode_text/long_names.inc appends to."""

    def test_pairs_and_whole_lines_only(self):
        import vv_long_names as ln
        short = fit_bytes(JAPANESE, 19) + "…"
        data = (b"VVFP Long Names v1\n" + short.encode(GAME_TEXT) + b"\t" + JAPANESE.encode(GAME_TEXT) + b"\n"
                + short.encode(GAME_TEXT) + b"\tsomething else\n" + b"half\tline")
        pairs = ln.parse(data)
        self.assertEqual(pairs, {short.encode(GAME_TEXT): JAPANESE.encode(GAME_TEXT)})   # the first pair wins
        self.assertEqual(ln.whole_name(short.encode(GAME_TEXT), pairs), JAPANESE)
        self.assertEqual(ln.expand(f"{short} has died.", pairs), f"{JAPANESE} has died.")
        self.assertEqual(ln.parse(b"not ours\na\tb\n"), {})

    def test_the_file_name_matches_the_companion(self):
        import vv_long_names as ln
        native = (ROOT / "native" / "vvfp_unicode_text" / "long_names.inc").read_text(encoding="utf-8")
        self.assertIn('L"Virtual Villagers %d Long Names - Save %d.dat"', native)
        self.assertIn('L"Long Names"', native)
        self.assertIn('"VVFP Long Names v1\\n"', native)
        self.assertEqual(ln.file_name(3, 2), "Virtual Villagers 3 Long Names - Save 2.dat")
        self.assertIn("#define VV_SHARED_NAME_BYTES 1200", native)
        self.assertEqual(ln.SHARED_NAME_BYTES, 1200)

    def test_the_font_choice_is_written_beside_the_companion(self):
        import tempfile
        import vv_fun_patcher as vfp
        patch = next(p for p in vfp.load_public_fun_patches() if p.id == "vv2_unicode_font")
        with tempfile.TemporaryDirectory() as folder:
            try:
                vfp.set_unicode_font_face("Yu Gothic")
                vfp._write_unicode_font_choice(Path(folder), [patch])
            finally:
                vfp.set_unicode_font_face(None)
            dll = Path(folder) / vfp._safe_companion_destination("VVFP Unicode Font.dll")
            self.assertEqual((dll.parent / "VVFP Unicode Font.txt").read_text(encoding="utf-8"), "Yu Gothic\n")
        with self.assertRaises(vfp.PatcherError):
            vfp.set_unicode_font_face("bad\nname")


class TheTables(unittest.TestCase):
    @unittest.skipUnless(HAVE_STOCK and HAVE_EMULATOR, "stock executables are not available")
    def test_every_detoured_site_is_the_stock_executables_own(self):
        import pefile
        import unicode_utf8_emulation as ue
        import build_unicode_text_feature as gen
        found = gen.routines()
        for game in GAMES:
            pe = pefile.PE(str(STOCK / f"Virtual Villagers - {NAMES[game]}.exe"), fast_load=True)
            image = pe.get_memory_mapped_image()
            for key, va in ue.routines()[game].items():
                if key in found["stock"] and va:
                    stock = found["stock"][key]
                    with self.subTest(game=game, site=key):
                        self.assertEqual(image[va - 0x400000:va - 0x400000 + len(stock)], stock)

    def test_no_byte_patch_of_the_catalog_overlaps_a_detour(self):
        builds = json.loads((ROOT / "data" / "builds.json").read_text(encoding="utf-8"))
        for game in GAMES:
            row = json.loads((ROOT / "data" / f"{game}_unicode_text_feature.json").read_text(encoding="utf-8"))
            ranges = [(int(d["va"], 16), int(d["va"], 16) + len(d["stock_bytes"]) // 2) for d in row["runtime_detours"]]

            def patches(node):
                if isinstance(node, dict):
                    if str(node.get("id", "")).startswith(game) and isinstance(node.get("patches"), list):
                        for p in node["patches"]:
                            if isinstance(p, dict) and "va" in p:
                                yield node["id"], int(str(p["va"]), 16), len(str(p.get("after", p.get("bytes", "")))) // 2
                    for v in node.values():
                        yield from patches(v)
                elif isinstance(node, list):
                    for v in node:
                        yield from patches(v)

            for pid, va, n in patches(builds):
                for lo, hi in ranges:
                    with self.subTest(game=game, patch=pid, va=hex(va)):
                        self.assertFalse(va < hi and lo < va + max(n, 1), f"{pid} overlaps {lo:#x}")


class TheRows(unittest.TestCase):
    def test_the_pair_conflicts_and_needs_full_names(self):
        for game in GAMES:
            text = json.loads((ROOT / "data" / f"{game}_unicode_text_feature.json").read_text(encoding="utf-8"))
            font = json.loads((ROOT / "data" / f"{game}_unicode_font_feature.json").read_text(encoding="utf-8"))
            self.assertEqual(text["conflicts"], [f"{game}_unicode_font"])
            self.assertEqual(font["conflicts"], [f"{game}_unicode_text"])
            self.assertEqual(text["name"], "Render Unicode with In-Game Fonts")
            self.assertEqual(font["name"], "Use Unicode Font (overrides in-game fonts)")
            for row in (text, font):
                self.assertEqual(row["dependencies"], [f"{game}_details_full_names"])
                self.assertIn("**Cannot be used with", row["description"])
                self.assertIn("**Needs \"Full Names on the Details Screen\"", row["description"])
                self.assertEqual(row["patches"], [])

    def test_the_generator_reproduces_the_rows(self):
        import build_unicode_text_feature as gen
        tables = json.loads(gen.TABLES.read_text(encoding="utf-8"))
        found = gen.routines()
        for override, dll in ((False, gen.TEXT_DLL), (True, gen.FONT_DLL)):
            digest = gen.sha(gen.DLLS[dll])
            for n in gen.GAMES:
                path = ROOT / "data" / f"vv{n}_{'unicode_font' if override else 'unicode_text'}_feature.json"
                self.assertEqual(json.loads(path.read_text(encoding="utf-8")), gen.row(n, override, digest, tables, found))

    def test_defaults(self):
        import vv_fun_patcher as vfp
        import vv_fun_patcher_gui as gui
        for game in GAMES:
            font, text = f"{game}_unicode_font", f"{game}_unicode_text"
            self.assertIn(font, vfp.ALTERNATIVE_FUN_PATCH_IDS)
            self.assertIn(font, gui.DEFAULT_OFF_FUN_PATCH_IDS)
            self.assertIn(font, gui.OWNERS_DEFAULT_OFF_FUN_PATCH_IDS)
            self.assertIn(font, gui.SELECT_ALL_OFF_FUN_PATCH_IDS)
            for ids in (gui.DEFAULT_OFF_FUN_PATCH_IDS, gui.OWNERS_DEFAULT_OFF_FUN_PATCH_IDS, gui.SELECT_ALL_OFF_FUN_PATCH_IDS):
                self.assertNotIn(text, ids)
            self.assertEqual(gui.UNTICKING_CONFLICT_IDS.get(font), text)
            self.assertEqual(gui.UNTICKING_CONFLICT_IDS.get(text), font)

    def test_the_startup_list_starts_the_font_companion(self):
        import vv_fun_patcher as vfp
        names = list(vfp.STARTUP_LOADER_COMPANIONS_2)
        self.assertIn("VVFP Unicode Font.dll", names)
        self.assertLess(names.index("VVFP Unicode Text.dll"), names.index("VVFP Unicode Font.dll"))


def _bytes_of(name: str) -> bytes:
    return name.encode(GAME_TEXT)


@unittest.skipUnless(ON_WINDOWS and HAVE_STOCK and HAVE_IMAGES and HAVE_EMULATOR,
                     "needs Windows, the stock executables, the game images and unicorn")
class InTheGame(unittest.TestCase):
    """Each published build with Render Unicode with In-Game Fonts, run in emulation."""

    runs: dict = {}

    @classmethod
    def setUpClass(cls):
        import unicode_utf8_emulation as ue
        cls.ue = ue
        cls.tables = json.loads((ROOT / "data" / "font_glyph_tables.json").read_text(encoding="utf-8"))
        for game in GAMES:
            cls.runs[game] = ue.TextRun(game, (f"{game}_unicode_text", f"{game}_details_full_names"), cls.tables)

    def test_installed_and_says_it_reads_utf8(self):
        for game, run in self.runs.items():
            with self.subTest(game=game):
                self.assertEqual(run.export("VvfpGlyphsUtf8"), 1)

    def test_ascii_is_left_to_the_game(self):
        for game, run in self.runs.items():
            with self.subTest(game=game):
                before = run.export("VvfpUnicodeTextOwnDraws")
                w = run.width_of("ldwBurweed27", b"Hello World")
                blits = run.draw_text("ldwBurweed27", b"Hello World")
                self.assertEqual(run.export("VvfpUnicodeTextOwnDraws"), before)
                self.assertGreater(w, 0)
                self.assertEqual(len(blits), 11)              # the space is a letter too

    def _check_drawn(self, run, font, text, game):
        raw = _bytes_of(text)
        w = run.width_of(font, raw)
        blits = run.draw_text(font, raw, 100, 50)
        self.assertGreater(w, 0, (game, text))
        self.assertTrue(blits, (game, text))
        # Every blit has ink, and the last letter ends where the width says.
        inked = 0
        for src, rect, _dst, to in blits:
            sw, sh, pitch, pixels, amask, ashift = run.surface(src)
            x1, y1, rw, rh = rect
            inked += any((struct.unpack_from("<I", pixels, (y1 + y) * pitch + (x1 + x) * 4)[0] & amask)
                         for y in range(rh) for x in range(rw))
        self.assertGreater(inked, 0)
        last = blits[-1]
        self.assertEqual(last[3][0] + last[1][2] - 100, w, (game, text))
        return w, blits

    def test_the_owners_names_are_drawn_and_measured_in_both_fonts(self):
        for game, run in self.runs.items():
            for font in ("ldwBurweed27", "ldwarialbold"):
                for text in (POO, CUNEIFORM, ZOE, JAPANESE):
                    with self.subTest(game=game, font=font, text=text):
                        self._check_drawn(run, font, text, game)

    def test_the_poo_emoji_is_in_colour(self):
        for game, run in self.runs.items():
            with self.subTest(game=game):
                blits = run.draw_text("ldwBurweed27", _bytes_of(POO), 10, 10, 0xFF40D0FF)
                src, rect, _d, _t = blits[0]
                sw, sh, pitch, pixels, amask, ashift = run.surface(src)
                colours = set()
                for y in range(rect[3]):
                    for x in range(rect[2]):
                        p = struct.unpack_from("<I", pixels, (rect[1] + y) * pitch + (rect[0] + x) * 4)[0]
                        if (p & amask) >> ashift > 200:
                            colours.add(p & 0xFFFFFF)
                self.assertGreater(len(colours), 3)                  # brown shades, not one tint

    def test_the_centred_draw_centres_by_the_real_width(self):
        for game, run in self.runs.items():
            for text in (POO, CUNEIFORM):
                with self.subTest(game=game, text=text):
                    raw = _bytes_of(text)
                    w = run.width_of("ldwBurweed27", raw)
                    mu = run.m.mu
                    screen = run._new_surface(1024, 768, 0x00FF0000, 0x0000FF00, 0x000000FF, 0xFF000000)
                    ctx = run.m.font_heap.alloc(0x400)
                    mu.mem_write(ctx + 0x30, struct.pack("<I", screen))
                    mu.mem_write(ctx + 0x5C, struct.pack("<I", run.fonts["ldwBurweed27"]))
                    mu.mem_write(ctx + 0x60, struct.pack("<4i", 0, 0, 1024, 768))
                    holder = run.m.font_heap.alloc(16)
                    mu.mem_write(holder, struct.pack("<I", ctx))
                    run.m.blits = []
                    run._call(CENTRED[game], holder, run.cstring(raw), 500, 50, 0xFFFFFFFF, run.fonts["ldwBurweed27"])
                    self.assertEqual(run.m.blits[0][3][0], 500 - w // 2)

    def test_a_long_arabic_name_wider_than_a_page_is_drawn_whole(self):
        """Codex (#676): a shaped run wider than a 1024-px page was clipped with the wrong stride.  It now gets
        a page of its own width: one letter as wide as the text, ink to its far end."""
        name = ("عبد الرحمن بن محمد "
                "بن عبد الله ") * 6
        for game, run in self.runs.items():
            with self.subTest(game=game):
                raw = _bytes_of(name.strip())
                w = run.width_of("ldwBurweed27", raw)
                self.assertGreater(w, 1100)
                blits = run.draw_text("ldwBurweed27", raw, 0, 10)
                self.assertEqual(len(blits), 1)                      # one shaped run, one letter
                src, rect, _dst, to = blits[0]
                self.assertEqual(rect[2], w)
                sw, sh, pitch, pixels, amask, ashift = run.surface(src)
                self.assertGreaterEqual(sw, w)
                # ink in the first and in the last 100 columns, on every one of them a real stride
                for lo, hi in ((rect[0], rect[0] + 100), (rect[0] + rect[2] - 100, rect[0] + rect[2])):
                    self.assertTrue(any((struct.unpack_from("<I", pixels, (rect[1] + y) * pitch + 4 * x)[0] & amask)
                                        for y in range(rect[3]) for x in range(lo, hi)))

    def test_typing_stores_each_character_whole(self):
        for game, run in self.runs.items():
            with self.subTest(game=game):
                _w, box = run.new_box(23)
                self.assertEqual(run.box_limit(box), 1200)
                for ch in ZOE:
                    run.type_into(box, ch.encode("utf-8"))
                self.assertEqual(run.box_text(box), _bytes_of(ZOE))
                _w, box = run.new_box(23)
                for ch in CUNEIFORM:
                    self.assertEqual(run.type_into(box, ch.encode("utf-8")), "post")
                self.assertEqual(run.box_text(box), _bytes_of(CUNEIFORM))
                run.backspace(box)
                self.assertEqual(run.box_text(box), _bytes_of(CUNEIFORM[:4]))
                # The emoji panel through SDL 2.0.3: each UTF-16 half on its own, as a three-byte text.
                _w, box = run.new_box(23)
                halves = POO.encode("utf-16-le")
                for k in (0, 2):
                    unit = struct.unpack_from("<H", halves, k)[0]
                    run.type_into(box, bytes([0xE0 | (unit >> 12), 0x80 | ((unit >> 6) & 0x3F), 0x80 | (unit & 0x3F)]))
                self.assertEqual(run.box_text(box), _bytes_of(POO))
                # A thumbs-up with its skin tone is erased whole; an IME's whole word arrives at once.
                run.type_into(box, "\U0001F44D\U0001F3FD".encode("utf-8"))
                run.backspace(box)
                self.assertEqual(run.box_text(box), _bytes_of(POO))
                run.type_into(box, JAPANESE[:4].encode("utf-8"))
                self.assertEqual(run.box_text(box), _bytes_of(POO + JAPANESE[:4]))
                # Malformed text is skipped as the game skipped it.
                self.assertEqual(run.type_into(box, b"\xff\xfe"), "skip")

    def test_the_limit_stops_before_a_character_that_does_not_fit(self):
        for game, run in self.runs.items():
            with self.subTest(game=game):
                _w, box = run.new_box(23)
                run.m.mu.mem_write(box + 0x28, struct.pack("<i", 6))
                run.type_into(box, CUNEIFORM.encode("utf-8"))
                self.assertEqual(run.box_text(box), _bytes_of(CUNEIFORM[:1]))

    def test_details_round_trip_leaves_every_name_identical(self):
        for game, run in self.runs.items():
            for name in (POO, CUNEIFORM, ZOE, JAPANESE[:7]):
                with self.subTest(game=game, name=name):
                    raw = _bytes_of(name)
                    wrapper, box = run.new_box(23)
                    run.set_text(box, raw)
                    got = run.get_text(wrapper, FIELD[game])
                    self.assertEqual(got[:len(raw) + 1], raw + b"\0")

    def test_a_long_name_leaves_as_its_short_form_and_comes_back_whole(self):
        for game, run in self.runs.items():
            with self.subTest(game=game):
                raw = _bytes_of(JAPANESE)
                wrapper, box = run.new_box(23)
                run.set_text(box, raw)
                short = run.get_text(wrapper, FIELD[game]).split(b"\0")[0]
                self.assertLess(len(short), FIELD[game])
                self.assertTrue(short.endswith(b"\x85") or short.endswith("…".encode("utf-8")))
                text = short.decode(GAME_TEXT)
                self.assertTrue(text.endswith("…") and JAPANESE.startswith(text[:-1]), text)
                # The game puts the short form back into a box: the box holds the whole name ...
                wrapper2, box2 = run.new_box(23)
                run.set_text(box2, short)
                self.assertEqual(run.box_text(box2), raw)
                # ... and gives back the very same short form (the record's bytes never change).
                self.assertEqual(run.get_text(wrapper2, FIELD[game]).split(b"\0")[0], short)
                # Drawn and measured as the whole name.
                self.assertEqual(run.width_of("ldwarialbold", short), run.width_of("ldwarialbold", raw))

    def test_line_fitting_breaks_japanese_between_characters(self):
        for game, run in self.runs.items():
            if game == "vv1":
                continue
            with self.subTest(game=game):
                text = (JAPANESE * 3).encode("utf-8")
                lines = run.linefit("ldwarialbold", text, 200)
                self.assertGreater(len(lines), 1)
                self.assertEqual(b"".join(lines), text)
                for line in lines:
                    line.decode("utf-8")                                      # never cut inside a character
                    self.assertLessEqual(run.width_of("ldwarialbold", line), 200)
                ascii_lines = run.linefit("ldwarialbold", b"The quick brown fox jumps over the lazy dog", 120)
                self.assertTrue(all(b" " not in line[:1] for line in ascii_lines))

    def test_the_justified_paragraph_finishes_for_japanese(self):
        for game, run in self.runs.items():
            if game in ("vv1", "vv2"):
                continue
            with self.subTest(game=game):
                h = run.justify_height("ldwarialbold", (JAPANESE * 4).encode("utf-8"), 300)
                self.assertGreater(h, 0)
                advance = run.nbyte("ldwarialbold", _bytes_of(POO), 4)
                self.assertEqual(advance, run.width_of("ldwarialbold", _bytes_of(POO))
                                 + self.tables["games"][game]["fonts"]["ldwarialbold"]["spacing"])


@unittest.skipUnless(ON_WINDOWS and HAVE_STOCK and HAVE_IMAGES and HAVE_EMULATOR,
                     "needs Windows, the stock executables, the game images and unicorn")
class UseUnicodeFont(unittest.TestCase):
    def test_every_letter_is_drawn_from_a_windows_typeface(self):
        import unicode_utf8_emulation as ue
        tables = json.loads((ROOT / "data" / "font_glyph_tables.json").read_text(encoding="utf-8"))
        for game in GAMES:
            with self.subTest(game=game):
                run = ue.TextRun(game, (f"{game}_unicode_font", f"{game}_details_full_names"), tables)
                self.assertEqual(run.dll.name, "VVFP Unicode Font.dll")
                before = run.export("VvfpUnicodeTextUnits")
                w = run.width_of("ldwBurweed27", b"Hello")
                blits = run.draw_text("ldwBurweed27", b"Hello " + _bytes_of(POO))
                self.assertGreater(run.export("VvfpUnicodeTextUnits"), before)
                self.assertGreater(w, 0)
                self.assertTrue(blits)
                # None of the letters comes from the game's own font picture.
                pictures = set(run.pictures.values())
                self.assertFalse({b[0] for b in blits} & pictures)


if __name__ == "__main__":
    unittest.main()
