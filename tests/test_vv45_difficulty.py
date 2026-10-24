"""Difficulty Settings (The Tree of Life, New Believers).

The rows, the companion and the guide are checked from the files; every site
is checked against the stock executables; and the Options dialog itself is
EMULATED whole (tests/options_dialog_emulation.py) -- the published executable
with "VVFP Difficulty.dll" installed by the startup loader, then the game's own
constructor (frame, Done button, Music Tracks checkboxes), the frame's own tile
draw, the dialog's draw routine and its click handler -- so what is placed and
drawn where, and what each click changes, is the game's own code's answer.  The stock executables are emulated the same
way to pin what the stock dialog does.  The live look of the dialog is NOT
verified here: it needs a running game.
"""
from __future__ import annotations

import hashlib
import json
import re
import struct
import sys
import unittest
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

DLL_LEAF = "VVFP Difficulty.dll"
DLL = ROOT / "assets" / "difficulty" / DLL_LEAF
STOCK_DIR = ROOT / "research" / "stock-executables"
MODES = ("stock", "collection_progression", "immediate_fixed")

# Per game: the dialog's routines and drawing primitives, the game-state
# fields, the strings, the stock and new layout (from the dialog's top-left).
GAMES = {
    "vv4": {
        "exe": "Virtual Villagers - The Tree of Life.exe",
        "draw": 0x41A5A0, "click": 0x41AD60,
        "get_string": 0x44D3D0, "image": 0x409960, "left": 0x409BD0, "centred": 0x409BE0,
        "fullscreen_read": 0x408360, "set_speed": 0x41ACB0, "sound": 0x448E10,
        "toggle_query": 0x408350, "toggle_on": 0x409FB0, "toggle_off": 0x409FA0, "colour": 0x4CCB08,
        "difficulty": 0x170F4, "speed": 0x17110, "fullscreen": 0x1711D,
        "screen": (800, 600), "height": 0x23C, "stock_height": 0x1FC, "grow": 64,
        "button": (158, 55, 0x23),          # main_wide_button2.png frame, gap under it
        "strings": {"Difficulty": 0x534, "Easy": 0x535, "Normal": 0x53A, "Hard": 0x537,
                    "Game Speed": 0x538, "Paused": 0x539, "Slow": 0x53B, "Fast": 0x53C,
                    "Fullscreen": 0x53D},
        "fullscreen_row": 0xFD,
        "stock_speed_row": 0x14D, "row": 0x145, "speed_row": 0x18D,
        "heading_dy": 0x5, "label_dy": 0x32,
        "label_x": (0x135, 0x1AB, 0x21F, 0x294),
    },
    "vv5": {
        "exe": "Virtual Villagers - New Believers.exe",
        "draw": 0x41ADF0, "click": 0x41B5C0,
        "get_string": 0x4506D0, "image": 0x409B90, "left": 0x409EA0, "centred": 0x409EB0,
        "fullscreen_read": 0x408330, "set_speed": 0x41B500, "sound": 0x44C440,
        "toggle_query": 0x408320, "toggle_on": 0x40A280, "toggle_off": 0x40A270, "colour": 0x4DC948,
        "difficulty": 0x17D54, "speed": 0x17D7C, "fullscreen": 0x17D89,
        "screen": (1024, 768), "height": 0x27C, "stock_height": 0x1FC, "grow": 128,
        "button": (140, 32, 0x0F),          # popup_button1.png frame, gap under it
        "strings": {"Difficulty": 0x57E, "Easy": 0x57F, "Normal": 0x584, "Hard": 0x581,
                    "Game Speed": 0x582, "Paused": 0x583, "Slow": 0x585, "Fast": 0x586,
                    "Fullscreen": 0x587},
        "fullscreen_row": 0xFD,
        "stock_speed_row": 0x161, "row": 0x161, "speed_row": 0x1C5,
        "heading_dy": 0x11, "label_dy": 0x33,
        "label_x": (0x1A5, 0x21B, 0x28E, 0x303),
    },
}
COLUMNS = (0xC8, 0x13C, 0x1B0, 0x224)    # the radio buttons' left edges
RADIO = 61                                # radioblank.png / radioselected.png
TEXT = 27                                 # ldwBurweed27.png's height: the dialog's default font
SPEEDS = (0x3E7, 0xA, 0x6, 0x3)           # Paused, Slow, Normal, Fast, by column

# The frame's inner edges (GreenDlgTileGrid.png's bars and their vines, more
# than 8 pixels a row or column): top + 16, bottom - 17, left + 18, right - 16.
INNER = (18, 16, 16, 17)
BLANK_ID = {"vv4": 0x9D, "vv5": 0x7B}
SELECTED_ID = {"vv4": 0x9E, "vv5": 0x7C}
STONE = (10, 11, 50, 50)                  # the visible part of a 61 x 61 radio button
INK = (3, 27)                             # ldwBurweed27's ink rows in these words


def row_path(game: str) -> Path:
    return ROOT / "data" / f"{game}_difficulty_settings_feature.json"


def load_row(game: str) -> dict:
    return json.loads(row_path(game).read_text(encoding="utf-8"))


def stock_exe(game: str) -> Path:
    return STOCK_DIR / GAMES[game]["exe"]


STOCK_PRESENT = all(stock_exe(g).is_file() for g in GAMES)
STOCK_ABSENT = "the stock executables are not in this checkout (research/stock-executables)"


def emulation_available() -> bool:
    try:
        import unicorn  # noqa: F401
    except ImportError:
        return False
    return True


class DifficultyRows(unittest.TestCase):

    def test_one_row_per_game_on_by_default_needing_nothing(self):
        import vv_fun_patcher as vfp
        self.assertEqual([p.name for p in vfp.DIFFICULTY_FEATURE_PATHS],
                         ["vv4_difficulty_settings_feature.json", "vv5_difficulty_settings_feature.json"])
        rows = {p.id: p for p in vfp.load_fun_patches() if p.id.endswith("_difficulty_settings")}
        self.assertEqual(set(rows), {"vv4_difficulty_settings", "vv5_difficulty_settings"})
        for game in GAMES:
            row = load_row(game)
            with self.subTest(game=game):
                self.assertEqual(row["id"], f"{game}_difficulty_settings")
                self.assertEqual(row["game_id"], game)
                self.assertEqual(row["name"], "Difficulty Settings")
                self.assertTrue(row["enabled"])
                self.assertTrue(row["catalog_enabled"])
                self.assertFalse(row["catalog_hidden"])
                self.assertEqual(row["dependencies"], [])
                self.assertEqual(row["patches"], [])
                self.assertNotIn("experimental", row["name"].lower())
                self.assertIn("**Needs no other patch", row["description"])
                self.assertIn("**Unverified in play", row["description"])
                self.assertIn("**The starting food only changes", row["description"])

    def test_the_rows_are_what_the_generator_writes(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        import build_difficulty_features as gen
        sha = hashlib.sha256(DLL.read_bytes()).hexdigest().upper()
        for game in GAMES:
            with self.subTest(game=game):
                self.assertEqual(load_row(game), json.loads(json.dumps(gen.row(game, sha))))

    def test_the_companion_is_shipped_and_hash_pinned(self):
        for game in GAMES:
            [item] = load_row(game)["companion_files"]
            self.assertEqual(item["destination"], DLL_LEAF)
            self.assertEqual(item["source"], f"assets/difficulty/{DLL_LEAF}")
            self.assertEqual(hashlib.sha256(DLL.read_bytes()).hexdigest().upper(), item["sha256"])
        release = (ROOT / "scripts" / "build_release.py").read_text(encoding="utf-8")
        for path in (f"assets/difficulty/{DLL_LEAF}", "data/vv4_difficulty_settings_feature.json",
                     "data/vv5_difficulty_settings_feature.json"):
            self.assertIn(f'"{path}"', release)

    def test_the_loader_knows_the_companion_in_its_appended_place(self):
        import vv_fun_patcher as vfp
        # Entry 28 (bit 28): the list is append-only.
        self.assertEqual(vfp.STARTUP_LOADER_COMPANIONS[27], DLL_LEAF)
        header = (ROOT / "native" / "shared" / "startup_companions.h").read_text(encoding="utf-8")
        body = header[header.index("VVFP_STARTUP_COMPANIONS[] = {"):]
        body = body[:body.index("};")]
        self.assertEqual(re.findall(r'"([^"]+)"', body), list(vfp.STARTUP_LOADER_COMPANIONS))
        self.assertLess(len(vfp.STARTUP_LOADER_COMPANIONS), 30)

    def test_the_dll_exports_only_vvfpstartup_and_has_no_debug_output(self):
        import pefile
        pe = pefile.PE(str(DLL))
        names = {e.name for e in pe.DIRECTORY_ENTRY_EXPORT.symbols if e.name}
        self.assertEqual({n for n in names if n.startswith(b"Vvfp")}, {b"VvfpStartup"})
        imported = {i.name for d in pe.DIRECTORY_ENTRY_IMPORT for i in d.imports if i.name}
        self.assertEqual({d.dll.upper() for d in pe.DIRECTORY_ENTRY_IMPORT}, {b"KERNEL32.DLL"})
        for name in (b"OutputDebugStringA", b"OutputDebugStringW"):
            self.assertNotIn(name, imported)
        source = (ROOT / "native" / "vvfp_difficulty" / "vvfp_difficulty.c").read_text(encoding="utf-8")
        for word in ("OutputDebugString", "MessageBox", "CreateFile", "WriteFile", "fopen"):
            self.assertNotIn(word, source)

    def test_every_declared_site_matches_the_source_table(self):
        source = (ROOT / "native" / "vvfp_difficulty" / "vvfp_difficulty.c").read_text(encoding="utf-8")
        for game, table in (("vv4", "VV4_SITES"), ("vv5", "VV5_SITES")):
            block = source.split(f"static const struct site {table}[] = {{")[1].split("};")[0]
            sites = [(int(m.group(1), 16), bytes(int(x, 16) for x in m.group(3).split(",")),
                      bytes(int(x, 16) for x in m.group(4).split(",")))
                     for m in re.finditer(r"\{ (0x[0-9A-F]+), (\d), \{ ([^}]*) \}, \{ ([^}]*) \} \}", block)]
            declared = [(int(d["va"], 16), bytes.fromhex(d["stock_bytes"]), d["written_bytes"])
                        for d in load_row(game)["runtime_detours"]]
            with self.subTest(game=game):
                self.assertEqual(len(sites), 22)
                self.assertEqual([(va, stock, after.hex().upper()) for va, stock, after in sites],
                                 declared[:-1])
                hook_va, hook_stock, hook_written = declared[-1]
                self.assertEqual(hook_written, "E9XXXXXXXX90")
                self.assertIn(f"0x{hook_va:X}u", source)

    def test_the_guide_and_readme_name_the_rows(self):
        guide = json.loads((ROOT / "data" / "how_to_use.json").read_text(encoding="utf-8"))
        found = [e for e in _entries(guide) if "vv4_difficulty_settings" in e.get("ids", [])]
        self.assertEqual(len(found), 1)
        self.assertIn("vv5_difficulty_settings", found[0]["ids"])
        self.assertTrue(any("not yet tested" in line.lower() for line in found[0]["guide"]))
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("`vv4_difficulty_settings`", readme)
        self.assertIn("`vv5_difficulty_settings`", readme)
        for game in GAMES:
            self.assertTrue((ROOT / "docs" / f"{game}-difficulty-options-preview.png").is_file())


def _entries(node):
    if isinstance(node, dict):
        yield node
        for value in node.values():
            yield from _entries(value)
    elif isinstance(node, list):
        for value in node:
            yield from _entries(value)


@unittest.skipUnless(STOCK_PRESENT, STOCK_ABSENT)
class DifficultyInTheStockExecutables(unittest.TestCase):
    """The stock facts the rows rest on, re-read from the executables."""

    @classmethod
    def setUpClass(cls):
        import pefile
        cls.images = {}
        for game in GAMES:
            pe = pefile.PE(str(stock_exe(game)), fast_load=True)
            cls.images[game] = pe.get_memory_mapped_image()

    def at(self, game, va, length):
        return self.images[game][va - 0x400000:va - 0x400000 + length]

    def test_every_declared_site_is_stock(self):
        for game in GAMES:
            for detour in load_row(game)["runtime_detours"]:
                va = int(detour["va"], 16)
                stock = bytes.fromhex(detour["stock_bytes"])
                with self.subTest(game=game, va=hex(va)):
                    self.assertEqual(self.at(game, va, len(stock)), stock)
                    if "X" not in detour["written_bytes"]:
                        self.assertEqual(len(bytes.fromhex(detour["written_bytes"])), len(stock))

    def test_the_handlers_write_the_field_and_the_constructor_sets_normal(self):
        writes = {"vv4": (0x41B159, 0x41B187, 0x41B1B9, 0x41F483), "vv5": (0x41B9B9, 0x41B9E7, 0x41BA19, 0x4249D3)}
        for game, sites in writes.items():
            field = GAMES[game]["difficulty"]
            for value, va in zip((0, 1, 2, 1), sites):
                with self.subTest(game=game, va=hex(va)):
                    self.assertEqual(self.at(game, va + 2, 8), struct.pack("<II", field, value))

    def test_the_level_sets_a_new_villages_starting_food(self):
        # mov esi, [esi+field]; sub esi, 0 (ebx); je Easy; sub esi, 2; jne; push -0x63 ... push 0x12C
        for game, va in (("vv4", 0x41F3A3), ("vv5", 0x4248EB)):
            with self.subTest(game=game):
                self.assertEqual(self.at(game, va, 6), b"\x8B\xB6" + struct.pack("<I", GAMES[game]["difficulty"]))
                window = self.at(game, va, 0x40)
                self.assertIn(b"\x6A\x9D", window)                   # push -0x63
                self.assertIn(b"\x68\x2C\x01\x00\x00", window)       # push 0x12C

    def test_the_stock_dialog_never_draws_the_difficulty_strings(self):
        import pefile
        for game, start, end in (("vv4", 0x41A5A0, 0x41ACA6), ("vv5", 0x41ADF0, 0x41B4F6)):
            code = self.at(game, start, end - start)
            for word in ("Difficulty", "Easy", "Hard"):
                string_id = GAMES[game]["strings"][word]
                with self.subTest(game=game, word=word):
                    self.assertNotIn(b"\x68" + struct.pack("<I", string_id), code)
            self.assertIn(b"\x68" + struct.pack("<I", GAMES[game]["strings"]["Game Speed"]), code)
        del pefile


@lru_cache(maxsize=None)
def _published(game: str, mode: str):
    import vv_fun_patcher as vfp
    build = next(b for b in vfp.load_builds() if b.id == game)
    selection = [f"{game}_difficulty_settings"]
    data, applied = vfp.render_patched_bytes(stock_exe(game), build, mode, selection)
    features = vfp._attach_automatic_companions(game, vfp._selected_fun_patches(build, selection))
    vfp._finalize_published_bytes(data, build, features, applied)
    shipped = {item["destination"]: ROOT / item["source"]
               for feature in features for item in feature.raw.get("companion_files", [])
               if str(item["destination"]).lower().endswith(".dll")}
    return bytes(data), shipped


def patched_dialog(game: str, mode: str = "collection_progression"):
    import vv_fun_patcher as vfp
    from options_dialog_emulation import OptionsDialog
    from startup_emulation import StartupMachine
    exe, shipped = _published(game, mode)
    machine = StartupMachine(exe, GAMES[game]["exe"], shipped)
    call_va, winmain = vfp.STARTUP_LOADER_WINMAIN_CALL[game]
    machine.run_to_winmain(call_va, winmain)
    machine.stop_at = None
    return OptionsDialog(game, machine).construct()


def stock_dialog(game: str):
    from options_dialog_emulation import OptionsDialog
    from startup_emulation import StartupMachine
    machine = StartupMachine(stock_exe(game).read_bytes(), GAMES[game]["exe"], {})
    return OptionsDialog(game, machine).construct()


def layout(dialog, difficulty=1, speed=6):
    """Everything the dialog shows, relative to its frame's top-left:
    (kind, what, x, y) for each image, text, child widget and tile."""
    dialog.set(difficulty=difficulty, speed=speed, fullscreen=0)
    frame = dialog.draw()
    left, top, right, bottom = dialog.rect
    items = [("image", image, x - left, y - top) for image, x, y in frame.images]
    items += [("text", (kind, ident if ident is not None else ("ptr", ptr)), x - left, y - top)
              for kind, ident, ptr, x, y, _c, _f in frame.texts]
    items += [(child.kind, child.ident, child.x, child.y) for child in dialog.children]
    tiles = [(tile, x - left, y - top) for tile, x, y in frame.tiles]
    return items, tiles, (left, top, right, bottom)


@unittest.skipUnless(STOCK_PRESENT and emulation_available(), STOCK_ABSENT + ", or unicorn is missing")
class TheStockDialog(unittest.TestCase):
    """What the unpatched games do: no Difficulty row, and the stock click
    areas for it hidden in a strip right above the Game Speed buttons."""

    def test_no_difficulty_row_is_drawn_and_the_frame_is_512_high(self):
        for game in GAMES:
            dialog = stock_dialog(game)
            items, tiles, rect = layout(dialog)
            texts = {what[1] for kind, what, _x, _y in items if kind == "text"}
            with self.subTest(game=game):
                self.assertIn(GAMES[game]["strings"]["Game Speed"], texts)
                for word in ("Difficulty", "Easy", "Hard"):
                    self.assertNotIn(GAMES[game]["strings"][word], texts)
                self.assertEqual(rect[3] - rect[1], 512)          # 8 tiles for a 0x1FC request
                self.assertEqual(dialog.origin[1] - rect[1], 2)

    def test_a_click_just_above_the_game_speed_buttons_changes_the_level_unseen(self):
        for game in GAMES:
            dialog = stock_dialog(game)
            x0, y0 = dialog.origin
            for column, level in zip(COLUMNS, (0, 1, 2)):
                dialog.set(difficulty=1 if level != 1 else 0, speed=6, fullscreen=0)
                with self.subTest(game=game, column=hex(column)):
                    self.assertEqual(dialog.press(x0 + column + 0xA + 5, y0 + 0x150 + 2), [])
                    self.assertEqual(dialog.get("difficulty"), level)


@unittest.skipUnless(STOCK_PRESENT and emulation_available(), STOCK_ABSENT + ", or unicorn is missing")
class ThePatchedDialog(unittest.TestCase):
    """The whole dialog -- constructor, frame, children, draw, clicks -- as the
    game builds it after the startup loader installed "VVFP Difficulty.dll",
    compared with the stock dialog, in every population mode."""

    def moved(self, game, item):
        """Where a stock item must be in the patched dialog, frame-relative."""
        g = GAMES[game]
        shift = g["speed_row"] - g["stock_speed_row"]
        kind, what, x, y = item
        if kind == "done":
            return (kind, what, x, y + g["grow"])
        if y >= g["stock_speed_row"] + 2 - 8 and kind in ("image", "text"):
            return (kind, what, x, y + shift)
        return item

    def check_layout(self, game, mode):
        g = GAMES[game]
        s = g["strings"]
        stock = stock_dialog(game)
        patched = patched_dialog(game, mode)
        width, height = g["screen"]
        for level in (0, 1, 2):
            stock_items, stock_tiles, stock_rect = layout(stock, difficulty=level)
            items, tiles, rect = layout(patched, difficulty=level)
            # The frame: whole tiles, the stock width, one or two tiles taller,
            # centred and wholly on the screen; the rows drawn from top + 2.
            self.assertEqual(rect[2] - rect[0], stock_rect[2] - stock_rect[0])
            self.assertEqual(rect[3] - rect[1], 512 + g["grow"])
            self.assertEqual(rect[0], (width - 640) // 2)
            self.assertEqual(rect[1], (height - (512 + g["grow"])) // 2)
            self.assertTrue(0 <= rect[1] and rect[3] <= height and 0 <= rect[0] and rect[2] <= width)
            self.assertEqual(patched.origin[1] - rect[1], 2)
            self.assertEqual(patched.origin[0] - rect[0], 0)
            self.assertEqual(len(tiles), 10 * (512 + g["grow"]) // 64)
            self.assertEqual(max(y for _t, _x, y in tiles) + 64, rect[3] - rect[1])
            # Every stock item is drawn, unchanged or exactly one move lower.
            expected = sorted((self.moved(game, item) for item in stock_items), key=repr)
            new = [item for item in items if item not in expected]
            self.assertEqual(sorted((item for item in items if item in expected), key=repr), expected)
            # And the only new items are the Difficulty row's.
            y0 = 2
            row = g["row"] + y0
            want_new = sorted(                [("image", SELECTED_ID[game] if i == level else BLANK_ID[game], COLUMNS[i], row) for i in range(3)]
                + [("text", ("left", s["Difficulty"]), 0x32, row + g["heading_dy"])]
                + [("text", ("centred", s[w]), g["label_x"][i] - rect[0], row + g["label_dy"])
                   for i, w in enumerate(("Easy", "Normal", "Hard"))], key=repr)
            self.assertEqual(sorted(new, key=repr), want_new)
            # Nothing overlaps: every row's band (stone top to label ink
            # bottom) is clear of the next, of the checkboxes' labels above
            # and of the Done button below; all inside the frame's inner edges.
            rows = [g["fullscreen_row"] + y0, row, g["speed_row"] + y0]
            bands = [(r + STONE[1], r + g["label_dy"] + INK[1]) for r in rows]
            track_labels = 0xDC + y0 + INK[1]          # the Music Tracks numbers' ink bottom
            done = next(item for item in items if item[0] == "done")
            done_top = done[3] + 1
            self.assertLess(track_labels, bands[0][0])
            for upper, lower in zip(bands, bands[1:]):
                self.assertLess(upper[1], lower[0], bands)
            self.assertLess(bands[-1][1], done_top)
            inner_left, inner_top = INNER[0], INNER[1]
            inner_right, inner_bottom = 640 - INNER[2], rect[3] - rect[1] - INNER[3]
            for kind, what, x, y in items:
                if kind == "image":
                    box = (x + STONE[0], y + STONE[1], x + STONE[2], y + STONE[3]) if what in (
                        BLANK_ID[game], SELECTED_ID[game]) else (x, y, x + 1, y + 1)
                elif kind == "text":
                    box = (x, y + INK[0], x + 1, y + INK[1])
                elif kind == "done":
                    continue
                else:
                    box = (x, y, x + 48, y + 32)
                self.assertTrue(inner_left <= box[0] and box[2] <= inner_right
                                and inner_top <= box[1] and box[3] <= inner_bottom, (kind, what, box))
            # Done keeps the stock distance to the frame's bottom.
            stock_done = next(item for item in stock_items if item[0] == "done")
            self.assertEqual((rect[3] - rect[1]) - done[3], (stock_rect[3] - stock_rect[1]) - stock_done[3])

    def test_the_whole_dialog_is_the_stock_one_plus_the_row_in_every_mode(self):
        for game in GAMES:
            for mode in MODES:
                with self.subTest(game=game, mode=mode):
                    self.check_layout(game, mode)

    def test_the_new_row_draws_with_the_stock_rows_routines_font_and_colour(self):
        for game in GAMES:
            s = GAMES[game]["strings"]
            dialog = patched_dialog(game)
            dialog.mu.mem_write(GAMES[game]["colour"], struct.pack("<I", 0x7F3C2A19))
            dialog.set(difficulty=1, speed=6, fullscreen=0)
            frame = dialog.draw()
            args = {(kind, ident): (colour, font) for kind, ident, _p, _x, _y, colour, font in frame.texts}
            with self.subTest(game=game):
                stock_heading = args[("left", s["Fullscreen"])]
                self.assertEqual(stock_heading, (0x7F3C2A19, 0))
                self.assertEqual({args[("centred", s["Fullscreen"] + 1)], args[("centred", s["Fullscreen"] + 2)]},
                                 {stock_heading})
                self.assertEqual(args[("left", s["Difficulty"])], stock_heading)
                for word in ("Easy", "Normal", "Hard"):
                    self.assertEqual(args[("centred", s[word])], stock_heading)
                self.assertNotIn(("centred", s["Difficulty"]), args)

    def check_clicks(self, game, mode):
        g = GAMES[game]
        stock = stock_dialog(game)
        patched = patched_dialog(game, mode)
        shift = g["speed_row"] - g["stock_speed_row"]
        controls = {
            "patched": [("fullscreen", 1, COLUMNS[0], g["fullscreen_row"]),
                        ("fullscreen", 0, COLUMNS[1], g["fullscreen_row"])]
                       + [("level", i, COLUMNS[i], g["row"]) for i in range(3)]
                       + [("speed", [SPEEDS[i]], COLUMNS[i], g["speed_row"]) for i in range(4)],
            "stock": [("fullscreen", 1, COLUMNS[0], g["fullscreen_row"]),
                      ("fullscreen", 0, COLUMNS[1], g["fullscreen_row"])]
                     + [("speed", [SPEEDS[i]], COLUMNS[i], g["stock_speed_row"]) for i in range(4)],
        }
        for name, dialog in (("stock", stock), ("patched", patched)):
            x0, y0 = dialog.origin
            for fullscreen in (0, 1):
                for kind, value, column, row in controls[name]:
                    if kind == "fullscreen" and value == fullscreen:
                        continue
                    left, top, right, bottom = column + 0xA, row + 0xA, column + 0x2F, row + 0x2F
                    # The stock dialog's hidden Difficulty strip lies just above its first three
                    # Game Speed buttons (TheStockDialog); the patched dialog has none.
                    above = (None, None, None)
                    if name == "stock" and kind == "speed" and column in COLUMNS[:3]:
                        above = (COLUMNS.index(column), None, None)
                    want = {"level": (value, None, None), "speed": (None, value, None),
                            "fullscreen": (None, None, value)}[kind]
                    probes = [(((left + right) // 2, (top + bottom) // 2), want), ((left, top), want),
                              ((right, top), want), ((left, bottom), want), ((right, bottom), want),
                              ((left - 1, (top + bottom) // 2), (None, None, None)),
                              ((right + 1, (top + bottom) // 2), (None, None, None)),
                              (((left + right) // 2, top - 1), above),
                              (((left + right) // 2, bottom + 1), (None, None, None))]
                    for (x, y), result in probes:
                        dialog.set(difficulty=0x5A5A, speed=6, fullscreen=fullscreen)
                        calls = dialog.press(x0 + x, y0 + y)
                        level = dialog.get("difficulty")
                        screen = dialog.get("fullscreen")
                        got = (None if level == 0x5A5A else level, calls or None,
                               None if screen == fullscreen else screen)
                        with self.subTest(game=game, mode=mode, dialog=name, fullscreen=fullscreen,
                                          control=(kind, str(value)), at=(x, y)):
                            self.assertEqual(got, result)
        # The patched hit areas are the stock ones: Fullscreen identical, Game
        # Speed one move lower, relative to the origin rows are drawn from.
        self.assertEqual(shift, {"vv4": 0x40, "vv5": 0x64}[game])

    def test_every_click_hits_exactly_the_control_drawn_there_in_every_mode(self):
        for game in GAMES:
            for mode in MODES:
                with self.subTest(game=game, mode=mode):
                    self.check_clicks(game, mode)


if __name__ == "__main__":
    unittest.main()
