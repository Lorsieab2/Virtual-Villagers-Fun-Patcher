"""Scrolling Popups (The Secret City, The Tree of Life, New Believers): vvN_scrolling_popups, stage 1 -- the
island-event dialog.

The owner (2026-11-12): vertical and horizontal scrollbars on popups so the player can read practically unlimited
text, "Let the patcher handle it": a companion DLL, the game's own scrollbar art, text never off the screen.

Proofs:
  * the rows: the companion pinned, the detours are scroll_popup.h's sites holding their stock bytes, no other row
    touches them; off by default, on in Owner's Defaults, not in Classic VV Difficulty;
  * EMULATION of each published build (tests/scrolling_popups_emulation.py: the startup chain, the game's own fonts
    and pictures, the dialog's own constructor tail, panel draw and body draw, the event pump's mouse call site):
      - a text that fits: the panel is the constructor's own height and the body is drawn by the very same call, blit
        for blit, as with the site stock;
      - a long text: the panel is capped to the screen less 16 px above and below, the OK button (or the two choice
        buttons) stays inside the panel at its bottom and still gets its clicks, every text blit lies inside the box
        (the clip rectangle set around the body and restored after), and the scrollbar is drawn with the game's own
        Up/DownArrowButton, VerticalScrollTrack and VerticalScrollKnob pictures;
      - the wheel, the arrows, a knob drag and a track click move the drawn lines; scrollbar events are not passed to
        the game, others are; a new text starts at the top;
      - a word wider than the box: the stock paragraph never finishes (shown with the site stock); with the
        companion the constructor's measures and the draw finish, and the horizontal bar (WideSlider2, sliderhandle)
        scrolls it sideways;
  * all or none: a changed site installs nothing; with every other public patch in all three population modes the
    sites stay stock and the companion installs.
The live effect in a running game is NOT verified here.
"""
from __future__ import annotations

import hashlib
import importlib.util
import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import vv_fun_patcher as patcher  # noqa: E402
import vv_fun_patcher_gui as gui  # noqa: E402

try:
    import pefile
    import unicorn  # noqa: F401
    from story_emulator import Process
    HAVE_EMULATOR = True
except ImportError:  # pragma: no cover
    HAVE_EMULATOR = False

GAMES = (3, 4, 5)
NAMES = {3: "The Secret City", 4: "The Tree of Life", 5: "New Believers"}
DLL = ROOT / "assets" / "scrolling_popups" / "VVFP Scrolling Popups.dll"
TEST_DLL = ROOT / "tests" / "test_dlls" / "VVFP Scrolling Popups.test.dll"   # VVFP_TEST: the state exports
STOCK = {g: ROOT / "research" / "stock-executables" / f"Virtual Villagers - {n}.exe" for g, n in NAMES.items()}
IMAGES = ROOT / "research" / "game-images"
HAVE_STOCK = all(p.is_file() for p in STOCK.values())
HAVE_IMAGES = all((IMAGES / f"Virtual Villagers - {n}" / "Images" / "VerticalScrollTrack.png").is_file()
                  for n in NAMES.values())
MODES = ("stock", "collection_progression", "immediate_fixed")
LONG = b"".join(b"%d. Footprints by the old ruins.\n" % n for n in range(1, 56))
SHORT = b"Your tribe finds a basket of fruit by the shore."
WORD = b"Supercalifragilisticexpialidocious" * 3


def _builder():
    spec = importlib.util.spec_from_file_location("sp_builder", ROOT / "scripts" / "build_scrolling_popups_features.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


BUILDER = _builder()


def row_id(game: int) -> str:
    return f"vv{game}_scrolling_popups"


def sites(game: int) -> list[tuple[int, str]]:
    mouse, dispatch, _ctor, draw, justify, size, sizer, _screen = BUILDER.SITES[game]
    out = [(mouse, BUILDER.call_bytes(mouse, dispatch)), (draw, BUILDER.call_bytes(draw, justify)),
           (size, BUILDER.call_bytes(size, sizer))]
    out += [(va, BUILDER.call_bytes(va, justify)) for va in BUILDER.MEASURES[game]]
    return out


class TheRows(unittest.TestCase):
    def setUp(self) -> None:
        self.rows = {p.id: p.raw for p in patcher.load_fun_patches()}

    def test_three_public_rows_pin_the_companion(self) -> None:
        digest = hashlib.sha256(DLL.read_bytes()).hexdigest().upper()
        public = {p.id for p in patcher.load_public_fun_patches()}
        self.assertIn("VVFP Scrolling Popups.dll", patcher.STARTUP_LOADER_COMPANIONS_2)
        for game in GAMES:
            row = self.rows[row_id(game)]
            self.assertIn(row_id(game), public)
            self.assertEqual(row["patches"], [])
            self.assertEqual([(f["destination"], f["sha256"]) for f in row["companion_files"]],
                             [("VVFP Scrolling Popups.dll", digest)])
            self.assertEqual([(int(d["va"], 16), d["stock_bytes"]) for d in row["runtime_detours"]], sites(game))

    def test_the_c_table_holds_the_same_sites(self) -> None:
        header = (ROOT / "native" / "shared" / "scroll_popup.h").read_text(encoding="utf-8")
        for game in GAMES:
            mouse, dispatch, _ctor, draw, justify, size, sizer, _screen = BUILDER.SITES[game]
            classes = header.split(f"static const sp_class SP_VV{game}_CLASSES[] = {{")[1].split("};")[0]
            for va in (draw, size, sizer, *BUILDER.MEASURES[game]):
                self.assertIn(f"0x{va:X}u", classes)
            row = header.split("static const sp_game SP_GAMES[6]")[1].split(f"/* vv{game} */")[0].rsplit("/*", 1)[-1]
            for va in (justify, mouse, dispatch):
                self.assertIn(f"0x{va:X}u", row)

    @unittest.skipUnless(HAVE_STOCK, "needs the stock executables")
    def test_every_site_holds_its_stock_bytes(self) -> None:
        for game in GAMES:
            pe = pefile.PE(str(STOCK[game]), fast_load=True)
            data = STOCK[game].read_bytes()
            for va, stock in sites(game):
                off = pe.get_offset_from_rva(va - 0x400000)
                self.assertEqual(data[off:off + 5].hex().upper(), stock, hex(va))

    @unittest.skipUnless(HAVE_STOCK, "needs the stock executables")
    def test_no_other_row_claims_a_site(self) -> None:
        for game in GAMES:
            pe = pefile.PE(str(STOCK[game]), fast_load=True)
            ranges = [(va, va + 5) for va, _ in sites(game)]
            for p in patcher._load_fun_patch_records():
                if p.raw.get("game_id") != f"vv{game}" or p.id == row_id(game):
                    continue
                claims = []
                for patch in p.raw.get("patches", []) or []:
                    try:
                        va = 0x400000 + pe.get_rva_from_offset(int(patch["offset"], 16))
                    except Exception:
                        continue
                    claims.append((va, len(patch.get("before", "")) // 2 or int(patch.get("length", 1))))
                for d in p.raw.get("runtime_detours", []) or []:
                    claims.append((int(str(d["va"]), 0), len(bytes.fromhex(d["stock_bytes"]))))
                for va, n in claims:
                    for start, end in ranges:
                        self.assertFalse(va < end and start < va + n, (p.id, hex(va), hex(start)))

    def test_defaults(self) -> None:
        for game in GAMES:
            self.assertIn(row_id(game), gui.DEFAULT_OFF_FUN_PATCH_IDS)
            self.assertNotIn(row_id(game), gui.OWNERS_DEFAULT_OFF_FUN_PATCH_IDS)
            self.assertNotIn(row_id(game), patcher.ALTERNATIVE_FUN_PATCH_IDS)
            classic = self.rows.get(f"vv{game}_classic_vv_difficulty")
            if classic is not None:
                self.assertNotIn(row_id(game), classic.get("dependencies", []))


@unittest.skipUnless(HAVE_EMULATOR and HAVE_STOCK and HAVE_IMAGES and TEST_DLL.is_file(),
                     "needs unicorn, the stock executables, the game images and the test build")
class TheDialog(unittest.TestCase):
    dialogs: dict = {}

    @classmethod
    def setUpClass(cls) -> None:
        import scrolling_popups_emulation as spe
        cls.spe = spe
        for game in GAMES:
            cls.dialogs[game] = spe.Dialog(f"vv{game}")

    @classmethod
    def tearDownClass(cls) -> None:
        cls.dialogs.clear()

    def text_rows(self, d, blits):
        """The y of every text blit (the font pictures' blits: not the panel, not the scrollbar art)."""
        skip = d.art_surfaces() | d.panel_surfaces()
        return [b[3][1] for b in blits if b[0] not in skip]

    def test_installed(self) -> None:
        for game, d in self.dialogs.items():
            with self.subTest(game=game):
                self.assertEqual(d.companion_export("VvfpScrollingPopupsInstalled"), 1)

    def test_a_text_that_fits_is_drawn_by_the_stock_call(self) -> None:
        for game, d in self.dialogs.items():
            with self.subTest(game=game):
                d.make(SHORT)
                left, top, right, bottom = d.panel()
                self.assertEqual(d.size_requests[-1], d.stock_height)   # the constructor's own height: not capped
                before = d.companion_export("VvfpScrollingPopupsTestScrolled")
                with_companion = d.draw(with_panel=False)
                self.assertEqual(d.companion_export("VvfpScrollingPopupsTestScrolled"), before)
                self.assertEqual(d.clip(), (0, 0) + d.g["screen"])
                site = d.g["draw_site"]
                patched = bytes(d.mu.mem_read(site, 5))
                d.mu.mem_write(site, bytes.fromhex(BUILDER.call_bytes(site, d.g["justify"])))
                try:
                    stock = d.draw(with_panel=False)
                finally:
                    d.mu.mem_write(site, patched)
                self.assertEqual([(b[1], b[3]) for b in with_companion], [(b[1], b[3]) for b in stock])
                self.assertTrue(with_companion)

    def test_a_long_text_is_capped_clipped_and_given_a_scrollbar(self) -> None:
        for game, d in self.dialogs.items():
            with self.subTest(game=game):
                w, h = d.g["screen"]
                d.make(LONG)
                left, top, right, bottom = d.panel()
                self.assertGreater(d.stock_height, h)                  # the stock panel would leave the screen
                # capped: inside the screen less 16 px above and below (the 9-slice rounds to its cells, so the
                # height asked for is the whole cells that fit less one cell, plus one pixel)
                self.assertLess(d.size_requests[-1], d.stock_height)
                self.assertLessEqual(bottom - top, h - 32)
                self.assertGreaterEqual(top, 16)
                self.assertLessEqual(bottom, h - 16)
                bx, by, bw = d.box()
                ok_x, ok_y = d.button_position("ok")
                ok_w, ok_h = d.button_size["ok"]
                self.assertGreater(top + ok_y, by)
                self.assertLessEqual(ok_y + ok_h, bottom - top)        # inside the panel, at its bottom
                blits = d.draw()
                self.assertEqual(d.clip(), (0, 0, w, h))               # restored
                art = d.art_blits(blits)
                for name in ("up", "down", "track", "knob"):
                    self.assertIn(name, art)
                self.assertNotIn("wide", art)
                rows = self.text_rows(d, blits)
                view = d.view()
                self.assertTrue(rows)
                body = [b for b in blits if b[0] not in (d.art_surfaces() | d.panel_surfaces())
                        and b[3][1] >= by - 2]
                for b in body:
                    self.assertGreaterEqual(b[3][1], by)
                    self.assertLessEqual(b[3][1] + b[1][3], by + view["box_h"])
                    self.assertLess(b[3][0], bx + bw)
                # the track and the knob lie beside the box, inside the panel
                self.assertGreaterEqual(min(b[3][0] for b in art["track"]), bx + bw)
                self.assertLessEqual(max(b[3][0] + b[1][2] for b in art["track"]), right)

    def test_wheel_arrows_knob_and_track_move_the_lines(self) -> None:
        for game, d in self.dialogs.items():
            with self.subTest(game=game):
                d.make(LONG)
                left, top, right, bottom = d.panel()
                start = d.first_line()
                self.assertEqual(d.scroll(), (0, 0))
                # the wheel over the panel: three lines down
                self.assertTrue(d.mouse(1, (left + right) // 2, (top + bottom) // 2))   # a move goes to the game
                self.assertIsNotNone(d.watch)
                d.wheel(-1)
                d.draw(with_panel=False)
                line = d.view()["line"]
                self.assertEqual(d.scroll(), (0, 3 * line))
                self.assertNotEqual(d.first_line(), start)
                d.wheel(1)
                d.draw(with_panel=False)
                self.assertEqual(d.scroll(), (0, 0))
                self.assertEqual(d.first_line(), start)
                v = d.view()
                # the down arrow: one line, the click is the scrollbar's, not the game's
                self.assertFalse(d.click(v["vx"] + 4, v["vy"] + v["vh"] - 4))
                d.draw(with_panel=False)
                self.assertEqual(d.scroll(), (0, line))
                self.assertFalse(d.click(v["vx"] + 4, v["vy"] + 4))
                d.draw(with_panel=False)
                self.assertEqual(d.scroll(), (0, 0))
                # a click on the track below the knob: a page
                self.assertFalse(d.click(v["vx"] + 4, v["vy"] + v["vh"] - v["arrow_h"] - 4))
                d.draw(with_panel=False)
                self.assertGreater(d.scroll()[1], 4 * line)
                d.wheel(50)
                d.draw(with_panel=False)
                self.assertEqual(d.scroll(), (0, 0))
                # the knob dragged to the bottom: the end of the text
                ky = v["vy"] + v["arrow_h"] + 2
                self.assertFalse(d.mouse(2, v["vx"] + 8, ky))
                self.assertFalse(d.mouse(1, v["vx"] + 8, ky + 2000))
                self.assertFalse(d.mouse(3, v["vx"] + 8, ky + 2000))
                d.draw(with_panel=False)
                self.assertEqual(d.scroll()[1], d.view()["content_h"] - d.view()["box_h"])
                self.assertNotEqual(d.first_line(), start)
                # the OK button still gets its click
                ok_x, ok_y = d.button_position("ok")
                self.assertTrue(d.click(left + ok_x + 10, top + ok_y + 5))
                # a new text (the result replacing the question) starts at the top
                d.set_text(LONG.replace(b"ruins", b"falls"))
                d.draw(with_panel=False)
                self.assertEqual(d.scroll(), (0, 0))

    def test_two_choices_keep_both_buttons_in_the_panel(self) -> None:
        for game, d in self.dialogs.items():
            with self.subTest(game=game):
                d.make(LONG, choices=True)
                left, top, right, bottom = d.panel()
                self.assertLessEqual(bottom - top, d.g["screen"][1] - 32)
                self.assertGreaterEqual(top, 16)
                bx, by, bw = d.box()
                for name in ("choice_a", "choice_b"):
                    x, y = d.button_position(name)
                    self.assertGreater(top + y, by)
                    self.assertLessEqual(y + d.button_size["choice"][1], bottom - top)
                blits = d.draw()
                self.assertIn("knob", d.art_blits(blits))
                self.assertLessEqual(by + d.view()["box_h"], top + d.button_position("choice_a")[1])

    def test_a_word_wider_than_the_box(self) -> None:
        for game, d in self.dialogs.items():
            with self.subTest(game=game):
                text = b"A short text that fits. " + WORD + b" and some more words after the long one."
                # the stock paragraph never finishes on it
                with self.assertRaises(Exception):
                    d.run._call(d.g["justify"], d.holder, d._cstr(text), 0, 0, d.g["width"] - 0x50,
                                0, d.font, 1, count=3_000_000)
                d.make(text)
                blits = d.draw()
                art = d.art_blits(blits)
                self.assertIn("wide", art)
                self.assertIn("handle", art)
                self.assertGreater(d.view()["content_w"], d.box()[2])
                v = d.view()
                # the horizontal bar is as thick as the vertical track (18 px), WideSlider2 and sliderhandle cut to it
                # (not the 32-px slider stretched), and the handle is drawn inside the bar, on top of it
                self.assertEqual(v["hh"], 18)
                for name in ("wide", "handle"):
                    for b in art[name]:
                        self.assertGreaterEqual(b[3][1], v["hy"])
                        self.assertLessEqual(b[3][1] + b[1][3], v["hy"] + v["hh"])
                        self.assertGreaterEqual(b[3][0], v["hx"])
                        self.assertLessEqual(b[3][0] + b[1][2], v["hx"] + v["hw"])
                handle_area = sum(b[1][2] * b[1][3] for b in art["handle"])
                self.assertGreaterEqual(handle_area, 26 * 12)      # the vertical knob's size, turned sideways
                self.assertGreater(blits.index(art["handle"][0]), blits.index(art["wide"][-1]))
                hx = v["hx"] + 2
                self.assertFalse(d.mouse(2, hx, v["hy"] + v["hh"] // 2))
                self.assertFalse(d.mouse(1, hx + 1000, v["hy"] + v["hh"] // 2))
                self.assertFalse(d.mouse(3, hx + 1000, v["hy"] + v["hh"] // 2))
                d.draw(with_panel=False)
                self.assertEqual(d.scroll()[0], v["content_w"] - v["box_w"])


@unittest.skipUnless(HAVE_EMULATOR and HAVE_STOCK and DLL.is_file(), "needs unicorn and the stock executables")
class EveryBuild(unittest.TestCase):
    def others(self, game: int) -> list[str]:
        return [p.id for p in patcher.load_public_fun_patches()
                if p.game_id == f"vv{game}" and p.id not in patcher.ALTERNATIVE_FUN_PATCH_IDS
                and p.id not in patcher.EXPERIMENTAL_FUN_PATCH_IDS and p.id != row_id(game)]

    def render(self, game: int, mode: str, ids) -> bytes:
        build = next(b for b in patcher.load_builds() if b.id == f"vv{game}")
        data, _ = patcher.render_patched_bytes(STOCK[game], build, mode, list(ids))
        return bytes(data)

    def installed(self, exe: bytes, game: int) -> int:
        p = Process(exe, DLL)
        p.export("VvfpStartup", game, 0)
        return p.export("VvfpScrollingPopupsInstalled")

    def test_with_every_other_patch_in_every_mode(self) -> None:
        for game in GAMES:
            others = self.others(game)
            self.assertGreater(len(others), 10)
            for mode in MODES:
                with self.subTest(game=game, mode=mode):
                    ids = patcher.resolve_fun_patch_ids(others + [row_id(game)], game_id=f"vv{game}")
                    exe = self.render(game, mode, ids)
                    image = pefile.PE(data=exe, fast_load=True).get_memory_mapped_image()
                    for va, stock in sites(game):
                        self.assertEqual(image[va - 0x400000:va - 0x400000 + 5].hex().upper(), stock, hex(va))
                    self.assertEqual(self.installed(exe, game), 1)

    def test_a_site_that_is_not_stock_installs_nothing(self) -> None:
        for game in GAMES:
            for va, _stock in sites(game):
                with self.subTest(game=game, site=hex(va)):
                    data = bytearray(STOCK[game].read_bytes())
                    pe = pefile.PE(data=bytes(data), fast_load=True)
                    data[pe.get_offset_from_rva(va - 0x400000) + 1] ^= 0xFF
                    p = Process(bytes(data), DLL)
                    p.export("VvfpStartup", game, 0)
                    self.assertEqual(p.export("VvfpScrollingPopupsInstalled"), 0)
                    for other, stock in sites(game):
                        if other != va:
                            self.assertEqual(p.read(other, 5).hex().upper(), stock)

    def test_another_game_installs_nothing(self) -> None:
        for game in (1, 2):
            p = Process(STOCK[4].read_bytes(), DLL)
            p.export("VvfpStartup", game, 0)
            self.assertEqual(p.export("VvfpScrollingPopupsInstalled"), 0)


if __name__ == "__main__":
    unittest.main()
