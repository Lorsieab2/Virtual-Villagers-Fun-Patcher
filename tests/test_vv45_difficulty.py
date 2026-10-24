"""Difficulty Settings (The Tree of Life, New Believers).

The rows, the companion and the guide are checked from the files; every site
is checked against the stock executables; and the Options dialog itself is
EMULATED -- the published executable with "VVFP Difficulty.dll" installed by
the startup loader, then the game's own Options drawing and click handler run
on a dialog in emulated memory, with the game's drawing primitives recorded
instead of drawn -- so what is drawn where, and what each click changes, is
the game's own code's answer.  The stock executables are emulated the same
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
        "screen": (800, 600), "height": 0x24C, "stock_height": 0x1FC,
        "button": (158, 55, 0x23),          # main_wide_button2.png frame, gap under it
        "strings": {"Difficulty": 0x534, "Easy": 0x535, "Normal": 0x53A, "Hard": 0x537,
                    "Game Speed": 0x538, "Paused": 0x539, "Slow": 0x53B, "Fast": 0x53C,
                    "Fullscreen": 0x53D},
        "fullscreen_row": 0xFD,
        "stock_speed_row": 0x14D, "row": 0x14D, "speed_row": 0x19D,
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
        "screen": (1024, 768), "height": 0x260, "stock_height": 0x1FC,
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

DIALOG = 0x51000000
STATE = 0x52000000
GRAPHICS = 0x53000000
STRINGS = 0x53100000
BLANK, SELECTED, SLIDER, HANDLE = 0x5B000000, 0x5C000000, 0x5D000000, 0x5E000000
TEXT_BASE = 0x71000000                    # get_string returns TEXT_BASE + id


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


class _Dialog:
    """The game's Options dialog, emulated over a published or stock image."""

    def __init__(self, game: str, machine):
        from unicorn import UC_HOOK_CODE
        self.game = game
        self.g = GAMES[game]
        self.mu = machine.mu
        self.images: list[tuple[int, int, int]] = []
        self.texts: list[tuple[str, int, int, int]] = []
        self.speed_calls: list[int] = []
        self.text_args: list[tuple[str, int, int, int]] = []
        mu = self.mu
        for base, size in ((DIALOG, 0x1000), (STATE, 0x20000), (GRAPHICS, 0x1000), (STRINGS, 0x1000)):
            mu.mem_map(base, size)
        g = self.g
        # get_string(id) returns TEXT_BASE + id; the primitives record and return.
        mu.mem_write(g["get_string"], bytes.fromhex("8B44240405") + struct.pack("<I", TEXT_BASE) + b"\xC2\x04\x00")
        mu.mem_write(g["image"], b"\xC2\x0C\x00")
        mu.mem_write(g["left"], b"\xC2\x14\x00")
        mu.mem_write(g["centred"], b"\xC2\x14\x00")
        mu.mem_write(g["fullscreen_read"], b"\x30\xC0\xC3")
        mu.mem_write(g["set_speed"], b"\xC2\x04\x00")
        mu.mem_write(g["sound"], b"\xC2\x04\x00")
        mu.mem_write(g["toggle_query"], b"\x30\xC0\xC3")
        mu.mem_write(g["toggle_on"], b"\xC3")
        mu.mem_write(g["toggle_off"], b"\xC3")
        hooks = {g["image"]: self._image, g["left"]: self._left, g["centred"]: self._centred,
                 g["set_speed"]: self._speed}
        for address, fn in hooks.items():
            mu.hook_add(UC_HOOK_CODE, lambda uc, a, s, d, fn=fn: fn(), begin=address, end=address)
        width, height = g["screen"]
        self.place((width - 0x280) // 2, (height - self.height()) // 2)
        fields = {0x74: STATE,
                  0x8C: BLANK, 0x90: SELECTED, 0x94: SLIDER, 0x98: HANDLE, 0x9C: GRAPHICS, 0xA8: STRINGS,
                  0x64: 0x60, 0x68: 0x60, 0x6C: 0x60}
        for offset, value in fields.items():
            mu.mem_write(DIALOG + offset, struct.pack("<I", value))
        mu.mem_write(DIALOG + 0x60, b"\x01\x00\x00\x00")    # the Fullscreen row is shown

    def place(self, x: int, y: int) -> None:
        """Put the dialog's top-left at (x, y): the origin fields every stock
        row, and the new one, are drawn and hit-tested from."""
        self.x, self.y = x, y
        for offset, value in ((0x78, x), (0x7C, x + 0x140), (0x80, y)):
            self.mu.mem_write(DIALOG + offset, struct.pack("<i", value))

    def height(self) -> int:
        """The dialog's height as the constructor's `push` reads it; its
        centring (`sub eax, height`) must agree."""
        push, centring = {"vv4": (0x41A07D, 0x41A109), "vv5": (0x41A8D1, 0x41A95B)}[self.game]
        code = bytes(self.mu.mem_read(push, 5))
        sub = bytes(self.mu.mem_read(centring, 5))
        assert code[0] == 0x68 and sub[0] == 0x2D and code[1:] == sub[1:], (code.hex(), sub.hex())
        return struct.unpack("<I", code[1:])[0]

    def _args(self, count):
        from unicorn.x86_const import UC_X86_REG_ESP
        sp = self.mu.reg_read(UC_X86_REG_ESP)
        return struct.unpack(f"<{count}I", self.mu.mem_read(sp + 4, 4 * count))

    def _image(self):
        image, x, y = self._args(3)
        self.images.append((image, x - self.x, y - self.y))

    def _text(self, kind):
        text, x, y, colour, font = self._args(5)
        self.texts.append((kind, text - TEXT_BASE, x, y - self.y))
        self.text_args.append((kind, text - TEXT_BASE, colour, font))

    def _left(self):
        self._text("left")

    def _centred(self):
        self._text("centred")

    def _speed(self):
        (value,) = self._args(1)
        self.speed_calls.append(value)

    def set(self, difficulty: int, speed: int) -> None:
        self.mu.mem_write(STATE + self.g["difficulty"], struct.pack("<i", difficulty))
        self.mu.mem_write(STATE + self.g["speed"], struct.pack("<i", speed))

    def difficulty(self) -> int:
        return struct.unpack("<i", self.mu.mem_read(STATE + self.g["difficulty"], 4))[0]

    def _call(self, address, args=()):
        from unicorn.x86_const import UC_X86_REG_ECX, UC_X86_REG_ESP
        from startup_emulation import CRT_RETURN_SENTINEL, STACK_TOP
        sp = STACK_TOP - 0x20000
        frame = struct.pack("<I", CRT_RETURN_SENTINEL) + b"".join(struct.pack("<i", a) for a in args)
        self.mu.mem_write(sp, frame)
        self.mu.reg_write(UC_X86_REG_ESP, sp)
        self.mu.reg_write(UC_X86_REG_ECX, DIALOG)
        self.mu.emu_start(address, CRT_RETURN_SENTINEL, count=2_000_000)

    def draw(self):
        self.images.clear()
        self.texts.clear()
        self.text_args.clear()
        self._call(self.g["draw"])
        return list(self.images), list(self.texts)

    def click(self, x: int, y: int):
        """A mouse press at (x, y) from the dialog's top-left."""
        self.speed_calls.clear()
        self.mu.mem_write(DIALOG + 0x60, b"\x00")            # no fullscreen toggle under the test
        self._call(self.g["click"], (2, self.x + x, self.y + y))
        self.mu.mem_write(DIALOG + 0x60, b"\x01")
        return list(self.speed_calls)

    def press(self, x: int, y: int, fullscreen: int):
        """A mouse press at (x, y) from the dialog's top-left, with the
        Fullscreen row live and the game in fullscreen (1) or windowed (0).
        Returns what changed: the level, the speed calls, the fullscreen
        choice -- each None when untouched (sentinels are planted first)."""
        level_field = STATE + self.g["difficulty"]
        screen_field = STATE + self.g["fullscreen"]
        self.mu.mem_write(level_field, struct.pack("<i", 0x5A5A))
        self.mu.mem_write(screen_field, bytes([fullscreen]))
        self.mu.mem_write(DIALOG + 0xAD, bytes([fullscreen]))
        self.mu.mem_write(DIALOG + 0x60, b"\x01")
        self.speed_calls.clear()
        self._call(self.g["click"], (2, self.x + x, self.y + y))
        level = struct.unpack("<i", self.mu.mem_read(level_field, 4))[0]
        screen = self.mu.mem_read(screen_field, 1)[0]
        return (None if level == 0x5A5A else level, list(self.speed_calls) or None,
                None if screen == fullscreen else screen)


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


def _patched_dialog(game: str, mode: str) -> _Dialog:
    import vv_fun_patcher as vfp
    from startup_emulation import StartupMachine
    exe, shipped = _published(game, mode)
    machine = StartupMachine(exe, GAMES[game]["exe"], shipped)
    call_va, winmain = vfp.STARTUP_LOADER_WINMAIN_CALL[game]
    machine.run_to_winmain(call_va, winmain)
    machine.stop_at = None
    return _Dialog(game, machine)


def _stock_dialog(game: str) -> _Dialog:
    from startup_emulation import StartupMachine
    machine = StartupMachine(stock_exe(game).read_bytes(), GAMES[game]["exe"], {})
    return _Dialog(game, machine)


@unittest.skipUnless(STOCK_PRESENT and emulation_available(), STOCK_ABSENT + ", or unicorn is missing")
class TheStockDialog(unittest.TestCase):
    """What the unpatched games do: no Difficulty row, and the stock click
    areas for it hidden in a strip right above the Game Speed buttons."""

    def test_no_difficulty_row_is_drawn(self):
        for game in GAMES:
            dialog = _stock_dialog(game)
            dialog.set(1, 6)
            _, texts = dialog.draw()
            ids = {t[1] for t in texts}
            with self.subTest(game=game):
                self.assertIn(GAMES[game]["strings"]["Game Speed"], ids)
                for word in ("Difficulty", "Easy", "Hard"):
                    self.assertNotIn(GAMES[game]["strings"][word], ids)
                self.assertEqual(dialog.height(), 0x1FC)

    def test_a_click_just_above_the_game_speed_buttons_changes_the_level_unseen(self):
        for game in GAMES:
            dialog = _stock_dialog(game)
            for column, level in zip(COLUMNS, (0, 1, 2)):
                dialog.set(1 if level != 1 else 0, 6)
                with self.subTest(game=game, column=hex(column)):
                    calls = dialog.click(column + 0xA + 5, 0x150 + 2)
                    self.assertEqual(calls, [])
                    self.assertEqual(dialog.difficulty(), level)



@unittest.skipUnless(STOCK_PRESENT and emulation_available(), STOCK_ABSENT + ", or unicorn is missing")
class ThePatchedDialog(unittest.TestCase):
    """The game's own Options drawing and click handler, run in the emulator
    after the startup loader has installed "VVFP Difficulty.dll" -- in every
    population mode."""

    def check_draw(self, game, mode):
        g = GAMES[game]
        dialog = _patched_dialog(game, mode)
        self.assertEqual(dialog.height(), g["height"])
        s = g["strings"]
        speed_delta = g["speed_row"] - g["stock_speed_row"]
        for level in (0, 1, 2):
            dialog.set(level, 6)
            images, texts = dialog.draw()
            # The Difficulty row: three buttons where Game Speed's stood, the level's selected.
            row = [(img, x, y) for img, x, y in images if y == g["row"]]
            self.assertEqual(row, [(SELECTED if i == level else BLANK, COLUMNS[i], g["row"]) for i in range(3)])
            # Its heading and labels, as the Game Speed row draws its own (stock positions).
            self.assertIn(("left", s["Difficulty"], dialog.x + 0x32, g["row"] + g["heading_dy"]), texts)
            for i, word in enumerate(("Easy", "Normal", "Hard")):
                self.assertIn(("centred", s[word], g["label_x"][i], g["row"] + g["label_dy"]), texts)
            # Game Speed one row lower, buttons, heading and labels; Normal selected.
            speed = [(img, x) for img, x, y in images if y == g["speed_row"]]
            self.assertEqual(speed, [(SELECTED if c == COLUMNS[2] else BLANK, c) for c in COLUMNS])
            self.assertIn(("left", s["Game Speed"], dialog.x + 0x32,
                           g["stock_speed_row"] + speed_delta + g["heading_dy"]), texts)
            for i, word in enumerate(("Paused", "Slow", "Normal", "Fast")):
                self.assertIn(("centred", s[word], g["label_x"][i], g["speed_row"] + g["label_dy"]), texts)
            # Nothing is drawn at Game Speed's old place but the Difficulty row.
            self.assertFalse([t for t in texts if t[1] == s["Game Speed"] and t[3] < g["speed_row"]])
            # Every button and word above the Done button, which the height places.
            width, button_height, gap = g["button"]
            button_top = g["height"] - button_height - gap
            for img, x, y in images:
                self.assertLessEqual(y + RADIO, button_top, (hex(img), x, y))
            for kind, string_id, x, y in texts:
                self.assertLessEqual(y + TEXT, button_top, (kind, hex(string_id), x, y))
            # The rows keep the game's own spacing and never overlap.
            self.assertEqual(g["row"] - g["fullscreen_row"], g["speed_row"] - g["row"])
            self.assertTrue([t for t in texts if t[1] == s["Fullscreen"]])
        # The dialog still fits the screen.
        self.assertGreaterEqual(dialog.y, 0)
        self.assertLessEqual(dialog.y + g["height"], g["screen"][1])

    def check_clicks(self, game, mode):
        g = GAMES[game]
        dialog = _patched_dialog(game, mode)
        # Each Difficulty button sets its level, and no Game Speed.
        for level, column in enumerate(COLUMNS[:3]):
            dialog.set(1 if level != 1 else 2, 6)
            self.assertEqual(dialog.click(column + RADIO // 2, g["row"] + RADIO // 2), [])
            self.assertEqual(dialog.difficulty(), level)
        # Each Game Speed button, one row lower, sets its speed and not the level.
        for column, speed in zip(COLUMNS, SPEEDS):
            dialog.set(1, 6)
            self.assertEqual(dialog.click(column + RADIO // 2, g["speed_row"] + RADIO // 2), [speed])
            self.assertEqual(dialog.difficulty(), 1)
        # The old hidden strip and the gap between the rows change nothing.
        for column in COLUMNS[:3]:
            for y in (0x150, 0x152, g["row"] + 0xA - 1, g["row"] + 0x2F + 1, g["speed_row"] + 0xA - 1):
                dialog.set(1, 6)
                self.assertEqual(dialog.click(column + 0xA + 5, y), [])
                self.assertEqual(dialog.difficulty(), 1)
        # The fourth column has no Difficulty button.
        dialog.set(1, 6)
        self.assertEqual(dialog.click(COLUMNS[3] + RADIO // 2, g["row"] + RADIO // 2), [])
        self.assertEqual(dialog.difficulty(), 1)

    def test_the_row_is_drawn_and_game_speed_moves_down_in_every_mode(self):
        for game in GAMES:
            for mode in MODES:
                with self.subTest(game=game, mode=mode):
                    self.check_draw(game, mode)

    def test_the_new_row_draws_with_the_stock_rows_routines_font_and_colour(self):
        # The heading goes through the same routine as the stock "Fullscreen"
        # heading and the labels through the one "On" / "Off" use, with the
        # same colour (the value of the stock rows' global at that moment) and
        # the same font argument (0: the dialog's default, ldwBurweed27).
        for game in GAMES:
            g = GAMES[game]
            s = g["strings"]
            dialog = _patched_dialog(game, "collection_progression")
            dialog.mu.mem_write(g["colour"], struct.pack("<I", 0x7F3C2A19))
            dialog.set(1, 6)
            dialog.draw()
            args = {(kind, i): (colour, font) for kind, i, colour, font in dialog.text_args}
            with self.subTest(game=game):
                stock_heading = args[("left", s["Fullscreen"])]
                stock_labels = {args[("centred", g["strings"]["Fullscreen"] + 1)],
                                args[("centred", g["strings"]["Fullscreen"] + 2)]}
                self.assertEqual(stock_heading, (0x7F3C2A19, 0))
                self.assertEqual(stock_labels, {(0x7F3C2A19, 0)})
                self.assertEqual(args[("left", s["Difficulty"])], stock_heading)
                for word in ("Easy", "Normal", "Hard"):
                    self.assertEqual(args[("centred", s[word])], stock_heading)
                self.assertNotIn(("centred", s["Difficulty"]), args)
                for word in ("Easy", "Hard"):
                    self.assertNotIn(("left", s[word]), args)

    def test_every_click_hits_exactly_the_control_drawn_there(self):
        # Hit areas are the stock handler's own, computed from the same origin
        # fields (+0x78, +0x80) as the drawing, so they follow the dialog
        # wherever it is placed; the game hands its handler logical
        # coordinates (800 x 600, 1024 x 768) windowed or fullscreen.
        for game in GAMES:
            g = GAMES[game]
            dialog = _patched_dialog(game, "collection_progression")
            stock_origin = (dialog.x, dialog.y)
            controls = [("fullscreen", 1, COLUMNS[0], g["fullscreen_row"]),
                        ("fullscreen", 0, COLUMNS[1], g["fullscreen_row"])]
            controls += [("level", i, COLUMNS[i], g["row"]) for i in range(3)]
            controls += [("speed", [SPEEDS[i]], COLUMNS[i], g["speed_row"]) for i in range(4)]
            for origin in (stock_origin, (stock_origin[0] + 37, stock_origin[1] - 5)):
                dialog.place(*origin)
                for fullscreen in (0, 1):
                    for kind, value, column, row in controls:
                        left, top, right, bottom = column + 0xA, row + 0xA, column + 0x2F, row + 0x2F
                        if kind == "fullscreen" and value == fullscreen:
                            continue        # choosing the current state changes nothing to observe
                        want = {"level": (value, None, None), "speed": (None, value, None),
                                "fullscreen": (None, None, value)}[kind]
                        inside = [((left + right) // 2, (top + bottom) // 2), (left, top), (right, top),
                                  (left, bottom), (right, bottom)]
                        for x, y in inside:
                            with self.subTest(game=game, origin=origin, fullscreen=fullscreen,
                                              control=(kind, str(value)), at=(x, y)):
                                self.assertEqual(dialog.press(x, y, fullscreen), want)
                        outside = [(left - 1, (top + bottom) // 2), (right + 1, (top + bottom) // 2),
                                   ((left + right) // 2, top - 1), ((left + right) // 2, bottom + 1)]
                        for x, y in outside:
                            got = dialog.press(x, y, fullscreen)
                            with self.subTest(game=game, origin=origin, fullscreen=fullscreen,
                                              control=(kind, str(value)), outside=(x, y)):
                                self.assertNotEqual(got, want)
                                self.assertEqual(got, (None, None, None))
            dialog.place(*stock_origin)

    def test_the_buttons_set_the_level_and_game_speed_in_every_mode(self):
        for game in GAMES:
            for mode in MODES:
                with self.subTest(game=game, mode=mode):
                    self.check_clicks(game, mode)



if __name__ == "__main__":
    unittest.main()
