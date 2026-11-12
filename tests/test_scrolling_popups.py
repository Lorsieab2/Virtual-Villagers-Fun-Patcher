"""Scrolling Popups (all five games): vvN_scrolling_popups -- the island-event dialog of The Secret City, The Tree of
Life and New Believers (stage 1) and the message box of all five games (stage 2).

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
  * the message box (all five games; A New Home and The Lost Children with The Secret City's borrowed pictures),
    made by the game's own constructor and drawn by the game's own panel and control draws: a text that fits is the
    stock call blit for blit; a long or wide text gets a panel inside the screen, its text inside its box, the bars,
    wheel/arrows/drag, and the clicks off the bars go to the game;
  * the tip (all five games), made by the game's own constructor: its body is drawn through the frame draw's tail,
    which the companion replaces; a tip that fits is drawn blit for blit as with the tail stock; a long or wide tip
    is capped, its body drawn moved under the clip with the bars, scrolled by the wheel and a knob drag;
  * A New Home's and The Lost Children's island-event dialogs (plain, two choices, crate / sacks and vials), laid out
    by their constructors' own size sites and drawn by their own body draws through the frame draw's tail: a text that
    fits is blit for blit the stock tail's draw; a long text is capped and scrolled; the result replacing the
    question in a panel sized for the question scrolls inside it; a wide line scrolls sideways;
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

GAMES = (1, 2, 3, 4, 5)
EVENT_GAMES = (3, 4, 5)                  # the island-event dialog's rows (stage 1)
NAMES = {1: "A New Home", 2: "The Lost Children", 3: "The Secret City", 4: "The Tree of Life", 5: "New Believers"}
DLL = ROOT / "assets" / "scrolling_popups" / "VVFP Scrolling Popups.dll"
TEST_DLL = ROOT / "tests" / "test_dlls" / "VVFP Scrolling Popups.test.dll"   # VVFP_TEST: the state exports
STOCK = {g: ROOT / "research" / "stock-executables" / f"Virtual Villagers - {n}.exe" for g, n in NAMES.items()}
IMAGES = ROOT / "research" / "game-images"
HAVE_STOCK = all(p.is_file() for p in STOCK.values())
HAVE_IMAGES = all((IMAGES / f"Virtual Villagers - {n}" / "Images" / "WideSlider2.png").is_file()
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
    mouse, dispatch = BUILDER.MOUSE[game]
    out = [(mouse, BUILDER.call_bytes(mouse, dispatch))]
    if game in BUILDER.SITES:
        _ctor, draw, justify, size, sizer = BUILDER.SITES[game]
        out += [(draw, BUILDER.call_bytes(draw, justify)), (size, BUILDER.call_bytes(size, sizer))]
        out += [(va, BUILDER.call_bytes(va, justify)) for va in BUILDER.MEASURES[game]]
    _vt, _init, bsize, bsizer = BUILDER.MSGBOX[game]
    ctl, text_draw = BUILDER.CONTROL[game]
    out += [(bsize, BUILDER.call_bytes(bsize, bsizer)), (ctl, BUILDER.call_bytes(ctl, text_draw))]
    for _name, _vt, esize, esizer in BUILDER.EVENTS.get(game, ()):
        out.append((esize, BUILDER.call_bytes(esize, esizer)))
    _tvt, tsize, tsizer = BUILDER.TIPS[game]
    out.append((tsize, BUILDER.call_bytes(tsize, tsizer)))
    if game in BUILDER.TIP_JUSTIFY:
        out.append((BUILDER.TIP_JUSTIFY[game], BUILDER.call_bytes(BUILDER.TIP_JUSTIFY[game], BUILDER.SITES[game][2])))
    out.append(BUILDER.TAIL[game])            # the frame draw's tail: 13 / 14 bytes, not a call
    return out


class TheRows(unittest.TestCase):
    def setUp(self) -> None:
        self.rows = {p.id: p.raw for p in patcher.load_fun_patches()}

    def test_five_public_rows_pin_the_companion(self) -> None:
        digest = hashlib.sha256(DLL.read_bytes()).hexdigest().upper()
        public = {p.id for p in patcher.load_public_fun_patches()}
        self.assertIn("VVFP Scrolling Popups.dll", patcher.STARTUP_LOADER_COMPANIONS_2)
        for game in GAMES:
            row = self.rows[row_id(game)]
            self.assertIn(row_id(game), public)
            self.assertEqual(row["patches"], [])
            borrowed = [(f"Images/{n}", hashlib.sha256((ROOT / "assets" / "scrolling_popups" / n).read_bytes())
                         .hexdigest().upper()) for n in BUILDER.BORROWED] if game in (1, 2) else []
            self.assertEqual([(f["destination"], f["sha256"]) for f in row["companion_files"]],
                             [("VVFP Scrolling Popups.dll", digest)] + borrowed)
            self.assertEqual([(int(d["va"], 16), d["stock_bytes"]) for d in row["runtime_detours"]], sites(game))

    def test_the_c_table_holds_the_same_sites(self) -> None:
        header = (ROOT / "native" / "shared" / "scroll_popup.h").read_text(encoding="utf-8")
        for game in GAMES:
            mouse, dispatch = BUILDER.MOUSE[game]
            row = header.split("static const sp_game SP_GAMES[6]")[1].split(f"/* vv{game} */")[0].rsplit("/*", 1)[-1]
            vt, _init, bsize, bsizer = BUILDER.MSGBOX[game]
            ctl, text_draw = BUILDER.CONTROL[game]
            for va in (mouse, dispatch, vt, bsize, bsizer, ctl, text_draw, BUILDER.TAIL[game][0]):
                self.assertIn(f"0x{va:X}u", row)
            shifts = header.split(f"static const sp_shift SP_VV{game}_SHIFTS[] = ")[1].split("};")[0]
            for va in BUILDER.TIPS[game]:
                self.assertIn(f"0x{va:X}u", shifts)
            for _name, *vas in BUILDER.EVENTS.get(game, ()):
                for va in vas:
                    self.assertIn(f"0x{va:X}u", shifts)
            if game in BUILDER.TIP_JUSTIFY:
                self.assertIn(f"0x{BUILDER.TIP_JUSTIFY[game]:X}u", row)
            if game in BUILDER.SITES:
                _ctor, draw, justify, size, sizer = BUILDER.SITES[game]
                classes = header.split(f"static const sp_class SP_VV{game}_CLASSES[] = {{")[1].split("};")[0]
                for va in (draw, size, sizer, *BUILDER.MEASURES[game]):
                    self.assertIn(f"0x{va:X}u", classes)
                self.assertIn(f"0x{justify:X}u", row)

    @unittest.skipUnless(HAVE_STOCK, "needs the stock executables")
    def test_every_site_holds_its_stock_bytes(self) -> None:
        for game in GAMES:
            pe = pefile.PE(str(STOCK[game]), fast_load=True)
            data = STOCK[game].read_bytes()
            for va, stock in sites(game):
                off = pe.get_offset_from_rva(va - 0x400000)
                self.assertEqual(data[off:off + len(stock) // 2].hex().upper(), stock, hex(va))

    @unittest.skipUnless(HAVE_STOCK, "needs the stock executables")
    def test_no_other_row_claims_a_site(self) -> None:
        for game in GAMES:
            pe = pefile.PE(str(STOCK[game]), fast_load=True)
            ranges = [(va, va + len(stock) // 2) for va, stock in sites(game)]
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
        for game in EVENT_GAMES:
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
                        n = len(stock) // 2
                        self.assertEqual(image[va - 0x400000:va - 0x400000 + n].hex().upper(), stock, hex(va))
                    self.assertEqual(self.installed(exe, game), 1)

    def test_a_site_that_is_not_stock_installs_nothing(self) -> None:
        for game in GAMES:
            for va, stock_bytes in sites(game):
                with self.subTest(game=game, site=hex(va)):
                    data = bytearray(STOCK[game].read_bytes())
                    pe = pefile.PE(data=bytes(data), fast_load=True)
                    data[pe.get_offset_from_rva(va - 0x400000) + 1] ^= 0xFF
                    p = Process(bytes(data), DLL)
                    p.export("VvfpStartup", game, 0)
                    self.assertEqual(p.export("VvfpScrollingPopupsInstalled"), 0)
                    for other, stock in sites(game):
                        if other != va:
                            self.assertEqual(p.read(other, len(stock) // 2).hex().upper(), stock)

    def test_another_game_installs_nothing(self) -> None:
        for game, other in ((1, 4), (2, 3), (3, 1), (4, 5), (5, 2)):
            with self.subTest(game=game, exe=other):
                p = Process(STOCK[other].read_bytes(), DLL)
                p.export("VvfpStartup", game, 0)
                self.assertEqual(p.export("VvfpScrollingPopupsInstalled"), 0)


BOX_LONG = b"\n".join(b"Tech level %d: your villagers can now build better huts and tools." % n for n in range(1, 41))
BOX_SHORT = b"Your villagers have reached a new tech level!\nThey can now build better huts."
BOX_WIDE = b"A line far too wide for the screen: " + b"Supercalifragilisticexpialidocious " * 6 + b"\nSecond line."


@unittest.skipUnless(HAVE_EMULATOR and HAVE_STOCK and HAVE_IMAGES and TEST_DLL.is_file(),
                     "needs unicorn, the stock executables, the game images and the test build")
class TheMessageBox(unittest.TestCase):
    """The message box of all five games, made by the game's own constructor (its text control, its OK button, the
    sizer call and the placing of both), drawn by the game's own panel draw and control draws."""
    boxes: dict = {}

    @classmethod
    def setUpClass(cls) -> None:
        import scrolling_popups_emulation as spe
        for game in GAMES:
            cls.boxes[game] = spe.Dialog(f"vv{game}")

    @classmethod
    def tearDownClass(cls) -> None:
        cls.boxes.clear()

    def stock_sites(self, d, game):
        """The message box's two sites written back to their stock calls (the game without the companion)."""
        _vt, _init, bsize, bsizer = BUILDER.MSGBOX[game]
        ctl, text_draw = BUILDER.CONTROL[game]
        return [(bsize, bytes.fromhex(BUILDER.call_bytes(bsize, bsizer))),
                (ctl, bytes.fromhex(BUILDER.call_bytes(ctl, text_draw)))]

    def test_a_text_that_fits_is_the_stock_call(self) -> None:
        for game, d in self.boxes.items():
            with self.subTest(game=game):
                d.make_box(BOX_SHORT)
                self.assertEqual(d.size_requests[-1], d.stock_height)
                self.assertEqual(d.width_requests[-1], d.stock_width)
                before = d.companion_export("VvfpScrollingPopupsTestScrolled")
                with_companion = d.draw_box()
                self.assertEqual(d.companion_export("VvfpScrollingPopupsTestScrolled"), before)
                patched = []
                for va, stock in self.stock_sites(d, game):
                    patched.append((va, bytes(d.mu.mem_read(va, 5))))
                    d.mu.mem_write(va, stock)
                try:
                    d.make_box(BOX_SHORT)
                    stock = d.draw_box()
                finally:
                    for va, data in patched:
                        d.mu.mem_write(va, data)
                self.assertTrue(d.text_blits(with_companion))
                self.assertEqual([(b[1], b[3]) for b in with_companion], [(b[1], b[3]) for b in stock])

    def check_inside(self, d, blits, view):
        w, h = d.g["screen"]
        left, top, right, bottom = d.panel()
        self.assertGreaterEqual(left, 16)
        self.assertGreaterEqual(top, 16)
        self.assertLessEqual(right, w - 16)
        self.assertLessEqual(bottom, h - 16)
        self.assertEqual(d.clip(), (0, 0, w, h))                  # restored
        text = d.text_blits(blits)
        self.assertTrue(text)
        for b in text:
            x, y = b[3][0], b[3][1]
            if y < top + 2 or y >= bottom:                         # the OK button's label
                continue
            if y >= view["box_y"] + view["box_h"] + 2:
                continue
            self.assertGreaterEqual(x, view["box_x"])
            self.assertLessEqual(x + b[1][2], view["box_x"] + view["box_w"])
            self.assertGreaterEqual(y, view["box_y"])
            self.assertLessEqual(y + b[1][3], view["box_y"] + view["box_h"])
        art = d.art_blits(blits)
        for kind in art.values():
            for b in kind:
                self.assertGreaterEqual(b[3][0], left)
                self.assertLessEqual(b[3][0] + b[1][2], right)
        return art

    def test_a_long_text_is_capped_clipped_and_scrolled(self) -> None:
        for game, d in self.boxes.items():
            with self.subTest(game=game):
                h = d.g["screen"][1]
                d.make_box(BOX_LONG)
                self.assertGreater(d.stock_height, h)
                blits = d.draw_box()
                v = d.view()
                self.assertEqual((v["shown"], v["vbar"], v["hbar"]), (1, 1, 0))
                art = self.check_inside(d, blits, v)
                for name in ("up", "down", "track", "knob"):
                    self.assertIn(name, art)
                first = min(b[3][1] for b in d.text_blits(blits))
                # the wheel over the panel: three lines; the arrows; the knob to the end
                left, top, right, bottom = d.panel()
                self.assertTrue(d.mouse(1, (left + right) // 2, (top + bottom) // 2))
                d.wheel(-1)
                d.draw_box()
                self.assertEqual(d.scroll(), (0, 3 * v["line"]))
                self.assertFalse(d.click(v["vx"] + 4, v["vy"] + 4))
                d.draw_box()
                self.assertEqual(d.scroll(), (0, 2 * v["line"]))
                d.wheel(50)                                           # back to the top: the knob there
                d.draw_box()
                self.assertEqual(d.scroll(), (0, 0))
                ky = v["vy"] + v["arrow_h"] + 2
                self.assertFalse(d.mouse(2, v["vx"] + 8, ky))
                self.assertFalse(d.mouse(1, v["vx"] + 8, ky + 2000))
                self.assertFalse(d.mouse(3, v["vx"] + 8, ky + 2000))
                blits = d.draw_box()
                v2 = d.view()
                self.assertEqual(d.scroll()[1], v2["content_h"] - v2["box_h"])
                self.check_inside(d, blits, v2)
                self.assertNotEqual(min(b[3][1] for b in d.text_blits(blits)), first - 1)
                # a click off the bars (the OK button's row) is the game's
                self.assertTrue(d.click((left + right) // 2, bottom - 30))
                # a new message starts at the top
                d.make_box(BOX_LONG.replace(b"huts", b"boats"))
                d.draw_box()
                self.assertEqual(d.scroll(), (0, 0))

    def test_a_wide_text_scrolls_sideways(self) -> None:
        for game, d in self.boxes.items():
            with self.subTest(game=game):
                w = d.g["screen"][0]
                d.make_box(BOX_WIDE)
                self.assertGreater(d.stock_width, w)
                blits = d.draw_box()
                v = d.view()
                self.assertEqual((v["shown"], v["vbar"], v["hbar"]), (1, 0, 1))
                art = self.check_inside(d, blits, v)
                self.assertIn("wide", art)
                self.assertIn("handle", art)
                self.assertFalse(d.mouse(2, v["hx"] + 2, v["hy"] + v["hh"] // 2))
                self.assertFalse(d.mouse(1, v["hx"] + 3000, v["hy"] + v["hh"] // 2))
                self.assertFalse(d.mouse(3, v["hx"] + 3000, v["hy"] + v["hh"] // 2))
                d.draw_box()
                self.assertEqual(d.scroll()[0], v["content_w"] - v["box_w"])
                # both: a long and wide text gets both bars
                d.make_box(BOX_LONG + b"\n" + BOX_WIDE)
                blits = d.draw_box()
                v = d.view()
                self.assertEqual((v["vbar"], v["hbar"]), (1, 1))
                self.check_inside(d, blits, v)


TIP_LONG = b"\n".join(b"Tip line %d: drag a villager onto the garden to teach them farming." % n
                      for n in range(1, 41))
TIP_SHORT = b"Click on a villager and drag them\nto the farm to make them a farmer."
TIP_WIDE = b"A tip with a line far too wide: " + b"Supercalifragilisticexpialidocious " * 6 + b"\nSecond line."


@unittest.skipUnless(HAVE_EMULATOR and HAVE_STOCK and HAVE_IMAGES and TEST_DLL.is_file(),
                     "needs unicorn, the stock executables, the game images and the test build")
class TheTip(unittest.TestCase):
    """The tip of all five games, made by the game's own constructor, drawn by the game's own frame draw (through
    the tail the companion replaces) and its button's draw."""
    tips: dict = {}

    @classmethod
    def setUpClass(cls) -> None:
        import scrolling_popups_emulation as spe
        for game in GAMES:
            cls.tips[game] = spe.Dialog(f"vv{game}")

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tips.clear()

    def body_rows(self, d, blits):
        left, top, right, bottom = d.panel()
        return [b for b in d.text_blits(blits) if b[3][1] < bottom - 40]

    def test_a_tip_that_fits_is_drawn_as_the_game_draws_it(self) -> None:
        for game, d in self.tips.items():
            with self.subTest(game=game):
                d.make_tip(TIP_SHORT)
                self.assertEqual(d.size_requests[-1], d.stock_height)
                self.assertEqual(d.width_requests[-1], d.stock_width)
                with_companion = d.draw_box()
                tail, stock = BUILDER.TAIL[game]
                patched = bytes(d.mu.mem_read(tail, len(stock) // 2))
                d.mu.mem_write(tail, bytes.fromhex(stock))
                try:
                    plain = d.draw_box()
                finally:
                    d.mu.mem_write(tail, patched)
                self.assertTrue(self.body_rows(d, with_companion))
                self.assertEqual([(b[1], b[3]) for b in with_companion], [(b[1], b[3]) for b in plain])

    def test_a_long_tip_is_capped_clipped_and_scrolled(self) -> None:
        for game, d in self.tips.items():
            with self.subTest(game=game):
                w, h = d.g["screen"]
                d.make_tip(TIP_LONG)
                self.assertGreater(d.stock_height, h)
                blits = d.draw_box()
                left, top, right, bottom = d.panel()
                self.assertGreaterEqual(top, 16)
                self.assertLessEqual(bottom, h - 16)
                self.assertEqual(d.clip(), (0, 0, w, h))
                v = d.view()
                self.assertEqual((v["shown"], v["vbar"]), (1, 1))
                art = d.art_blits(blits)
                for name in ("up", "down", "track", "knob"):
                    self.assertIn(name, art)
                rows = self.body_rows(d, blits)
                self.assertTrue(rows)
                for b in rows:
                    self.assertGreaterEqual(b[3][1], v["box_y"])
                    self.assertLessEqual(b[3][1] + b[1][3], v["box_y"] + v["box_h"])
                first = sorted({b[3][1] for b in rows})[:1]
                self.assertTrue(d.mouse(1, (left + right) // 2, (top + bottom) // 2))
                d.wheel(-2)
                blits = d.draw_box()
                self.assertEqual(d.scroll(), (0, 6 * v["line"]))
                self.assertNotEqual(sorted({b[3][1] for b in self.body_rows(d, blits)})[:1], first)
                d.wheel(50)
                d.draw_box()
                ky = v["vy"] + v["arrow_h"] + 2
                self.assertFalse(d.mouse(2, v["vx"] + 8, ky))
                self.assertFalse(d.mouse(1, v["vx"] + 8, ky + 2000))
                self.assertFalse(d.mouse(3, v["vx"] + 8, ky + 2000))
                d.draw_box()
                self.assertEqual(d.scroll()[1], d.view()["content_h"] - d.view()["box_h"])
                # the panel's rectangle is the game's again after the draw
                self.assertEqual(d.panel(), (left, top, right, bottom))
                self.assertTrue(d.click((left + right) // 2, bottom - 20))

    def test_a_wide_tip_scrolls_sideways(self) -> None:
        for game, d in self.tips.items():
            with self.subTest(game=game):
                d.make_tip(TIP_WIDE)
                self.assertGreater(d.stock_width, d.g["screen"][0])
                blits = d.draw_box()
                left, top, right, bottom = d.panel()
                self.assertGreaterEqual(left, 16)
                self.assertLessEqual(right, d.g["screen"][0] - 16)
                v = d.view()
                self.assertEqual((v["shown"], v["hbar"]), (1, 1))
                self.assertIn("handle", d.art_blits(blits))
                for b in self.body_rows(d, blits):
                    self.assertGreaterEqual(b[3][0], v["box_x"])
                    self.assertLessEqual(b[3][0] + b[1][2], v["box_x"] + v["box_w"])
                self.assertFalse(d.mouse(2, v["hx"] + 2, v["hy"] + v["hh"] // 2))
                self.assertFalse(d.mouse(1, v["hx"] + 3000, v["hy"] + v["hh"] // 2))
                self.assertFalse(d.mouse(3, v["hx"] + 3000, v["hy"] + v["hh"] // 2))
                d.draw_box()
                self.assertEqual(d.scroll()[0], v["content_w"] - v["box_w"])


EVENT_TITLE = b"A Strange Storm\n"
EVENT_SHORT = b"Your villagers find a basket of fruit\nwashed up on the shore."
EVENT_LONG = b"\n".join(b"%d. The storm washes things ashore." % n for n in range(1, 40))
EVENT_RESULT = b"\n".join(b"%d. The whale swims free." % n for n in range(1, 16))
EVENT_WIDE = b"A name far too wide: " + b"Kalahuna-Supercalifragilistic" * 4 + b"\nSecond line."


@unittest.skipUnless(HAVE_EMULATOR and HAVE_STOCK and HAVE_IMAGES and TEST_DLL.is_file(),
                     "needs unicorn, the stock executables, the game images and the test build")
class TheOldIslandEvents(unittest.TestCase):
    """A New Home's and The Lost Children's island-event dialogs."""
    games: dict = {}
    KINDS = ("plain", "choice", "crate")

    @classmethod
    def setUpClass(cls) -> None:
        import scrolling_popups_emulation as spe
        for game in (1, 2):
            cls.games[game] = spe.Dialog(f"vv{game}")

    @classmethod
    def tearDownClass(cls) -> None:
        cls.games.clear()

    def text(self, kind, body):
        return (EVENT_TITLE if kind == "plain" else b"") + body

    def test_a_text_that_fits_is_drawn_as_the_game_draws_it(self) -> None:
        for game, d in self.games.items():
            for kind in self.KINDS:
                with self.subTest(game=game, kind=kind):
                    d.make_event(kind, self.text(kind, EVENT_SHORT))
                    self.assertEqual(d.size_requests[-1], d.stock_height)
                    with_companion = d.draw()
                    tail, stock = BUILDER.TAIL[game]
                    patched = bytes(d.mu.mem_read(tail, len(stock) // 2))
                    d.mu.mem_write(tail, bytes.fromhex(stock))
                    try:
                        plain = d.draw()
                    finally:
                        d.mu.mem_write(tail, patched)
                    self.assertTrue(d.text_blits(with_companion))
                    self.assertEqual([(b[1], b[3]) for b in with_companion], [(b[1], b[3]) for b in plain])

    def check(self, d, blits, vbar, hbar):
        w, h = d.g["screen"]
        left, top, right, bottom = d.panel()
        self.assertGreaterEqual(top, 16)
        self.assertLessEqual(bottom, h - 16)
        self.assertEqual(d.clip(), (0, 0, w, h))
        v = d.view()
        self.assertEqual((v["shown"], v["vbar"], v["hbar"]), (1, vbar, hbar))
        text = d.text_blits(blits)
        self.assertTrue(text)
        for b in text:
            self.assertGreaterEqual(b[3][1], v["box_y"])
            self.assertLessEqual(b[3][1] + b[1][3], v["box_y"] + v["box_h"])
            self.assertGreaterEqual(b[3][0], v["box_x"])
            self.assertLessEqual(b[3][0] + b[1][2], v["box_x"] + v["box_w"])
        art = d.art_blits(blits)
        if vbar:
            for name in ("up", "down", "track", "knob"):
                self.assertIn(name, art)
        if hbar:
            self.assertIn("handle", art)
        return v

    def test_a_long_text_is_capped_and_scrolled(self) -> None:
        for game, d in self.games.items():
            for kind in self.KINDS:
                with self.subTest(game=game, kind=kind):
                    d.make_event(kind, self.text(kind, EVENT_LONG))
                    self.assertGreater(d.stock_height, d.g["screen"][1])
                    v = self.check(d, d.draw(), 1, 0)
                    left, top, right, bottom = d.panel()
                    self.assertTrue(d.mouse(1, (left + right) // 2, (top + bottom) // 2))
                    d.wheel(-1)
                    d.draw()
                    self.assertEqual(d.scroll(), (0, 3 * v["line"]))
                    self.assertFalse(d.click(v["vx"] + 4, v["vy"] + v["vh"] - 4))
                    blits = d.draw()
                    self.assertEqual(d.scroll(), (0, 4 * v["line"]))
                    self.check(d, blits, 1, 0)
                    y = struct.unpack("<i", d.mu.mem_read(d.dialog + d.event_kind["y"], 4))[0]
                    d.wheel(-100)
                    d.draw()
                    self.assertEqual(d.scroll()[1], v["content_h"] - v["box_h"])
                    # the y the constructor keeps is the game's again after each draw
                    self.assertEqual(struct.unpack("<i", d.mu.mem_read(d.dialog + d.event_kind["y"], 4))[0], y)

    def test_the_result_in_a_panel_sized_for_the_question_scrolls(self) -> None:
        for game, d in self.games.items():
            for kind in ("choice", "crate"):
                with self.subTest(game=game, kind=kind):
                    d.make_event(kind, EVENT_SHORT, EVENT_RESULT)
                    before = d.companion_export("VvfpScrollingPopupsTestScrolled")
                    d.draw()
                    # the question fits: drawn as the game draws it
                    self.assertEqual(d.companion_export("VvfpScrollingPopupsTestScrolled"), before)
                    panel = d.panel()
                    d.show_result()
                    v = self.check(d, d.draw(), 1, 0)
                    self.assertEqual(d.panel(), panel)              # no re-size: the result scrolls in the panel
                    self.assertEqual(d.scroll(), (0, 0))
                    self.assertGreater(v["content_h"], v["box_h"])

    def test_a_wide_line_scrolls_sideways(self) -> None:
        for game, d in self.games.items():
            for kind in self.KINDS:
                with self.subTest(game=game, kind=kind):
                    d.make_event(kind, self.text(kind, EVENT_WIDE))
                    v = self.check(d, d.draw(), 0, 1)
                    self.assertFalse(d.mouse(2, v["hx"] + 2, v["hy"] + v["hh"] // 2))
                    self.assertFalse(d.mouse(1, v["hx"] + 3000, v["hy"] + v["hh"] // 2))
                    self.assertFalse(d.mouse(3, v["hx"] + 3000, v["hy"] + v["hh"] // 2))
                    self.check(d, d.draw(), 0, 1)
                    self.assertEqual(d.scroll()[0], v["content_w"] - v["box_w"])


if __name__ == "__main__":
    unittest.main()
