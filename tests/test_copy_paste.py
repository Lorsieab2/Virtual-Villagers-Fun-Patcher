"""Copy and Paste in Text Boxes (vvN_copy_paste): Ctrl+V / Shift+Insert, Ctrl+C / Ctrl+Insert and Ctrl+X in
every game's text boxes, all five games.

THE STOCK CODE: every address native/vvfp_copy_paste/copy_paste_tables.h uses, proved against each stock
executable -- the SDL_KEYDOWN case and where the pump goes on, the event manager and its keyboard dispatch,
the text box's class, keyboard handler, filter and limit.

THE GAME (tests/copy_paste_emulation.py): each published build is started as the game starts it, a box of
the game's own class is put on a screen, and the pump's own SDL_KEYDOWN case runs each key in unicorn:
paste into the box (through its own handler, filter and limit), never inside a character, copy and cut,
round trips, keys that are not ours, no focus, a busy or empty clipboard, and the Unicode Text companion
installed alongside (both detours in, its typing unchanged, its Windows-1252 and UTF-8 answers followed).
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import vv_fun_patcher as patcher  # noqa: E402

GAMES = ("vv1", "vv2", "vv3", "vv4", "vv5")
DLL_NAME = "VVFP Copy and Paste.dll"
DLL = ROOT / "assets" / "copy_paste" / DLL_NAME
STOCK_DIR = ROOT / "research" / "stock-executables"
EXES = {
    "vv1": "Virtual Villagers - A New Home.exe",
    "vv2": "Virtual Villagers - The Lost Children.exe",
    "vv3": "Virtual Villagers - The Secret City.exe",
    "vv4": "Virtual Villagers - The Tree of Life.exe",
    "vv5": "Virtual Villagers - New Believers.exe",
}
HAVE_STOCK = all((STOCK_DIR / name).is_file() for name in EXES.values())
try:
    import capstone
    import pefile
    import unicorn  # noqa: F401
    HAVE_EMULATOR = True
except ImportError:  # pragma: no cover
    HAVE_EMULATOR = False
TABLES = json.loads((ROOT / "data" / "font_glyph_tables.json").read_text(encoding="utf-8"))

ZOE = "Zoë Ñúñez"
LONG = "Bartholomew-Alexandrina Zoë Ñúñez de la Montaña Wolfeschlegelsteinhausen"


def _manifest(game: str) -> dict:
    return json.loads((ROOT / "data" / f"{game}_copy_paste_feature.json").read_text(encoding="utf-8"))


def _load_script(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _header_games() -> dict:
    text = (ROOT / "native" / "vvfp_copy_paste" / "copy_paste_tables.h").read_text(encoding="utf-8")
    out = {}
    for n, body in enumerate(re.findall(r"\{(0x[0-9A-F]+u, \{[^}]*\}[^}]*)\},\s*/\* vv\d \*/", text), start=1):
        nums = re.findall(r"0x[0-9A-F]+|\b\d+\b", body)
        values = [int(x, 0) for x in nums]
        site, key_bytes = values[0], bytes(values[1:11])
        sym, imm, cont, manager, handler = values[11:16]
        out[f"vv{n}"] = (site, key_bytes, sym, imm, cont, manager, handler)
    return out


@unittest.skipUnless(HAVE_STOCK and HAVE_EMULATOR, "the stock executables or capstone/pefile are not available")
class TheStockCode(unittest.TestCase):
    """Every address the companion uses is what each stock executable has there."""

    MD = None

    @classmethod
    def setUpClass(cls):
        cls.MD = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
        cls.images = {g: pefile.PE(str(STOCK_DIR / EXES[g])).get_memory_mapped_image() for g in GAMES}
        cls.header = _header_games()

    def _dis(self, game, va, n):
        img = self.images[game]
        return list(self.MD.disasm(img[va - 0x400000:va - 0x400000 + n], va))

    def test_the_header_has_all_five_games(self):
        self.assertEqual(sorted(self.header), list(GAMES))

    def test_the_keydown_case(self):
        for game in GAMES:
            site, key_bytes, sym, imm, cont, _manager, _handler = self.header[game]
            img = self.images[game]
            with self.subTest(game=game):
                self.assertEqual(img[site - 0x400000:site - 0x400000 + 10], key_bytes)
                # mov ecx, [esp + sym]; cmp ecx, imm
                self.assertEqual(key_bytes[:4], b"\x8B\x4C\x24" + bytes([sym]))
                self.assertEqual(key_bytes[4:6], b"\x81\xF9")
                self.assertEqual(struct.unpack("<I", key_bytes[6:])[0], imm)
                # reached only from `cmp eax, 0x300 (SDL_KEYDOWN); jne cont`
                before = img[site - 0x400000 - 11:site - 0x400000]
                self.assertEqual(before[:5], b"\x3D\x00\x03\x00\x00")
                self.assertEqual(before[5:7], b"\x0F\x85")
                self.assertEqual(site + struct.unpack("<i", before[7:])[0], cont)
                # cont is where every other case ends: the pump's SDL_PollEvent of the next event
                # (the same place Render Unicode with In-Game Fonts' skip goes)
                self.assertEqual(cont, int(TABLES["games"][game]["text_input"]["skip"], 16))
                ins = self._dis(game, cont, 16)
                self.assertEqual((ins[0].mnemonic, ins[1].mnemonic, ins[2].mnemonic), ("lea", "push", "call"))
                # the event sits at [esp + sym - 0x14]: the case before reads its type there
                head = self._dis(game, site - 0x40, 0x40)
                types = [i for i in head if i.mnemonic == "mov" and i.op_str.startswith("eax, dword ptr [esp + ")]
                self.assertEqual(int(types[-1].op_str.split("+ ")[1].rstrip("]"), 16), sym - 0x14)
                # nothing jumps into the moved bytes
                for target in range(site + 1, site + 10):
                    rel = [m.start() for m in re.finditer(re.escape(struct.pack("<I", target)), img)]
                    self.assertEqual(rel, [], hex(target))

    def test_the_event_manager_and_its_keyboard_dispatch(self):
        for game in GAMES:
            _site, _b, _sym, _imm, _cont, manager, _handler = self.header[game]
            post = int(TABLES["games"][game]["text_input"]["post"], 16)
            with self.subTest(game=game):
                # the typed character's post: push 5; call getter; mov ecx, eax; call deliver
                calls = [int(i.op_str, 16) for i in self._dis(game, post, 16) if i.mnemonic == "call"]
                getter, deliver = calls[0], calls[1]
                reads = [i.op_str for i in self._dis(game, getter, 0x40) if i.mnemonic == "mov"
                         and i.op_str.startswith("eax, dword ptr [0x")]
                self.assertEqual(int(reads[-1].split("[")[1].rstrip("]"), 16), manager)
                d = self._dis(game, deliver, 8)
                self.assertEqual((d[0].mnemonic, d[0].op_str, d[1].mnemonic), ("mov", "ecx, dword ptr [ecx]", "jmp"))
                walk = " ; ".join(f"{i.mnemonic} {i.op_str}" for i in self._dis(game, int(d[1].op_str, 16), 0x60))
                # node {listener, flags, last, next}: keyboard listeners have flag 2; handler is vtable +8;
                # the walk stops after a handler that takes it or after a `last` node
                for piece in ("mov eax, dword ptr [ecx]", "test dl, 2", "dword ptr [eax + 8]",
                              "dword ptr [eax + 0xc]", "test bl, bl", "test al, al"):
                    self.assertIn(piece, walk)

    def test_the_text_box_handler(self):
        for game in GAMES:
            handler = self.header[game][6]
            vtable = __import__("copy_paste_emulation").GAMES[game][5]
            img = self.images[game]
            with self.subTest(game=game):
                self.assertEqual(struct.unpack_from("<I", img, vtable - 0x400000 + 8)[0], handler)
                body = " ; ".join(f"{i.mnemonic} {i.op_str}" for i in self._dis(game, handler, 0xE0))
                for piece in ("byte ptr [ecx + 0x25]", "dword ptr [ecx + 0x1c]", "[eax + 8]", "cmp eax, 6",
                              "cmp eax, 5", "byte ptr [ecx + 0x2f]", "dword ptr [ecx + 0x34]",
                              "dword ptr [ecx + 0x30]", "cmp edx, 8", "cmp eax, dword ptr [ecx + 0x28]",
                              "byte ptr [ecx + 0x2d]", "cmp edx, 0x1f", "cmp edx, 0xff", "cmp edx, 0x2d"):
                    self.assertIn(piece, body)
                # the character is the third argument; ret 0xC
                self.assertIn("dword ptr [esp + 0x14]", body)
                self.assertIn("ret 0xc", body)
                # +0x2F is never set by the stock code (only cleared)
                sets = re.findall(rb"\xC6[\x40-\x47]\x2F[\x01-\xFF]", img)
                self.assertEqual(sets, [])


class TheRows(unittest.TestCase):
    def test_the_rows(self):
        sha = hashlib.sha256(DLL.read_bytes()).hexdigest().upper()
        public = {p.id for p in patcher.load_public_fun_patches()}
        header = _header_games() if (ROOT / "native").is_dir() else {}
        for game in GAMES:
            with self.subTest(game=game):
                row = _manifest(game)
                self.assertEqual(row["id"], f"{game}_copy_paste")
                self.assertIn(row["id"], public)
                self.assertEqual(row["name"], "Copy and Paste in Text Boxes")
                self.assertTrue(row["enabled"])
                self.assertEqual(row["patches"], [])
                self.assertNotIn("dependencies", row)
                self.assertEqual(row["companion_files"], [{"source": f"assets/copy_paste/{DLL_NAME}",
                                                           "destination": DLL_NAME, "sha256": sha}])
                d = row["description"]
                for words in ("**On by default.**", "**Needs no other patch; works with or without Render "
                              "Unicode with In-Game Fonts.**", "**Not yet seen in a running game**",
                              "**with Render Unicode with In-Game Fonts on, every Windows-1252 character"):
                    self.assertIn(words, d)
                for keys in ("Ctrl+V", "Shift+Insert", "Ctrl+C", "Ctrl+Insert", "Ctrl+X", "Ctrl+A"):
                    self.assertIn(keys, d)
                if header:
                    site, key_bytes = header[game][:2]
                    self.assertEqual(row["runtime_detours"], [dict(row["runtime_detours"][0],
                                                                   va=f"0x{site:06X}", stock_bytes=key_bytes.hex().upper())])

    def test_the_generator_reproduces_the_rows(self):
        module = _load_script("build_copy_paste_feature")
        sha = hashlib.sha256(DLL.read_bytes()).hexdigest().upper()
        for number, game in enumerate(GAMES, start=1):
            self.assertEqual(module.row(number, sha), _manifest(game))

    def test_started_by_the_startup_loader_second_word_after_unicode_text(self):
        self.assertEqual(patcher.STARTUP_LOADER_COMPANIONS_2[5:], ("VVFP Unicode Text.dll", DLL_NAME))
        header = (ROOT / "native" / "shared" / "startup_companions_2.h").read_text(encoding="utf-8")
        self.assertIn('    "VVFP Unicode Text.dll",\n    "VVFP Copy and Paste.dll",\n    /* APPEND ONLY', header)
        loader = (ROOT / "assets" / "startup" / "VVFP Startup.dll").read_bytes()
        self.assertIn(DLL_NAME.encode(), loader)
        self.assertEqual(hashlib.sha256(loader).hexdigest().upper(), patcher.STARTUP_LOADER_COMPANION["sha256"])

    def test_on_by_default_in_select_all_and_owners_defaults(self):
        from vv_fun_patcher_gui import (default_fun_patch_selection, owners_default_fun_patch_selection,
                                        select_all_fun_patch_selection)
        for game in GAMES:
            self.assertTrue(default_fun_patch_selection(f"{game}_copy_paste"))
            self.assertTrue(owners_default_fun_patch_selection(f"{game}_copy_paste"))
            self.assertTrue(select_all_fun_patch_selection(f"{game}_copy_paste"))

    def test_registered_bundled_documented(self):
        release = (ROOT / "scripts" / "build_release.py").read_text(encoding="utf-8")
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        guide = json.loads((ROOT / "data" / "how_to_use.json").read_text(encoding="utf-8"))
        how_to = (ROOT / "How to Use.txt").read_text(encoding="utf-8")
        self.assertIn(f'"assets/copy_paste/{DLL_NAME}"', release)
        self.assertIn("## What's new in v1.35.89", readme)
        self.assertLess(readme.index("## What's new in v1.35.89"), readme.index("## What's new in v1.35.87"))
        self.assertIn("COPY AND PASTE IN TEXT BOXES", how_to)
        guided = {i for entry in guide["patches"] for i in entry.get("ids", [])}
        for game in GAMES:
            self.assertIn(f'"data/{game}_copy_paste_feature.json"', release)
            self.assertIn(f"- Patch ID: `{game}_copy_paste`", readme)
            self.assertIn(_manifest(game)["description"], readme)
            self.assertIn(f"{game}_copy_paste", guided)
        log = (ROOT / "docs" / "transparency-log.md").read_text(encoding="utf-8")
        self.assertIn("Copy and Paste in Text Boxes", log)

    @unittest.skipUnless(HAVE_EMULATOR, "pefile is not installed")
    def test_the_dll_exports_and_imports(self):
        pe = pefile.PE(str(DLL))
        names = sorted(e.name.decode() for e in pe.DIRECTORY_ENTRY_EXPORT.symbols if e.name)
        self.assertEqual(names, ["VvfpCopyPasteHandled", "VvfpCopyPasteKey", "VvfpStartup"])
        imports = {i.name.decode() for e in pe.DIRECTORY_ENTRY_IMPORT for i in e.imports if i.name}
        self.assertEqual(imports & {"LoadLibraryA", "LoadLibraryW", "OutputDebugStringA", "OutputDebugStringW",
                                    "MessageBoxA", "MessageBoxW", "DeleteFileW", "RegSetValueExW",
                                    "CreateFileA", "MoveFileW", "MoveFileExW", "WaitForSingleObject", "Sleep",
                                    "CreateThread", "SendMessageW", "SendMessageA"},
                         set())
        for name in ("OpenClipboard", "CloseClipboard", "GetClipboardData", "SetClipboardData", "NormalizeString"):
            self.assertIn(name, imports)
        for section in pe.sections:
            self.assertFalse(section.Characteristics & 0x20000000 and section.Characteristics & 0x80000000)


@unittest.skipUnless(HAVE_STOCK and HAVE_EMULATOR, "needs the stock executables and unicorn")
class TheGame(unittest.TestCase):
    """The published builds' own SDL_KEYDOWN case and text box, emulated with the companion."""

    @classmethod
    def setUpClass(cls):
        import copy_paste_emulation as emu
        import startup_emulation
        cls.emu = emu
        cls.saved_imports = dict(startup_emulation.EXTRA_IMPORTS)
        cls.alone = {g: emu.PasteRun(g, (f"{g}_copy_paste",)) for g in GAMES}
        cls.both = {g: emu.PasteRun(g, (f"{g}_copy_paste", f"{g}_unicode_text")) for g in GAMES}

    @classmethod
    def tearDownClass(cls):
        import startup_emulation
        startup_emulation.EXTRA_IMPORTS.clear()
        startup_emulation.EXTRA_IMPORTS.update(cls.saved_imports)

    def setUp(self):
        for run in list(self.alone.values()) + list(self.both.values()):
            run.clear_listeners()
            run.clip.text, run.clip.busy = None, False
        for run in self.both.values():
            run.set_glyphs_utf8(0)

    def _paste(self, run, clip, **box):
        b = run.box(**box)
        run.clip.text = clip
        self.assertEqual(run.paste(), {"to": "next event"})
        return run.text(b)

    # -- installed --------------------------------------------------------------------------------
    def test_the_site_is_detoured_into_the_companion(self):
        for game in GAMES:
            for run in (self.alone[game], self.both[game]):
                code = bytes(run.mu.mem_read(run.site, 10))
                module = run.machine.modules["vvfp copy and paste.dll"]
                target = run.site + 5 + struct.unpack("<i", code[1:5])[0]
                with self.subTest(game=game):
                    self.assertEqual(code[0], 0xE9)
                    self.assertEqual(code[5:], b"\x90" * 5)
                    self.assertTrue(module.base <= target < module.base + 0x100000)

    # -- paste ------------------------------------------------------------------------------------
    def test_paste_into_each_box_follows_the_unicode_text_answer(self):
        for game in GAMES:
            with self.subTest(game=game, mode="ascii only (no Unicode Text)"):
                self.assertEqual(self._paste(self.alone[game], ZOE), b"Zo ez")
            with self.subTest(game=game, mode="Windows-1252"):
                self.assertEqual(self._paste(self.both[game], ZOE), ZOE.encode("cp1252"))
            with self.subTest(game=game, mode="UTF-8"):
                self.both[game].set_glyphs_utf8(1)
                self.assertEqual(self._paste(self.both[game], ZOE + " 日本"), (ZOE + " 日本").encode("utf-8"))

    def test_paste_goes_at_the_end_after_the_typed_text(self):
        for game in GAMES:
            self.assertEqual(self._paste(self.both[game], "ñez", text=b"Zo\xeb \xd1\xfa"), ZOE.encode("cp1252"))

    def test_the_byte_limit_cuts_at_a_whole_character(self):
        for game in GAMES:
            run = self.both[game]
            with self.subTest(game=game, mode="Windows-1252"):
                self.assertEqual(self._paste(run, LONG, limit=27), LONG.encode("cp1252")[:27])
                self.assertEqual(self._paste(run, LONG, text=b"Ab", limit=10), b"Ab" + LONG.encode("cp1252")[:8])
                self.assertEqual(self._paste(run, "xyz", text=b"0123456789", limit=10), b"0123456789")
            with self.subTest(game=game, mode="UTF-8"):
                run.set_glyphs_utf8(1)
                # 'Zoë' is 4 bytes; a 3-byte room takes 'Zo' and stops before the 2-byte 'ë'
                self.assertEqual(self._paste(run, "Zoë", limit=3), b"Zo")
                self.assertEqual(self._paste(run, "aé日", limit=5), "aé".encode())
                self.assertEqual(self._paste(run, "é", text=b"abcd", limit=5), b"abcd")
                # a letter with its accent, a skin tone, a family joined by ZWJ and a flag stay whole
                for whole in ("ẹ́", "👍🏽", "👩‍👩‍👧", "🇫🇷"):
                    size = len(("a" + whole).encode())
                    self.assertEqual(self._paste(run, "a" + whole + "b", limit=size - 1), b"a", whole)
                    self.assertEqual(self._paste(run, "a" + whole + "b", limit=size), ("a" + whole).encode(), whole)
                run.set_glyphs_utf8(0)
            with self.subTest(game=game, mode="every limit"):
                for limit in range(1, 16):
                    got = self._paste(run, ZOE + ZOE, limit=limit)
                    self.assertEqual(got, (ZOE + ZOE).encode("cp1252")[:limit])

    def test_the_box_filter(self):
        for game in GAMES:
            run = self.both[game]
            with self.subTest(game=game):
                self.assertEqual(self._paste(run, "-12a3 4", digits=True), b"-1234")
                self.assertEqual(self._paste(run, "-4", text=b"5", digits=True), b"54")
                self.assertEqual(self._paste(run, "a\r\nb\tc\nd\re", ), b"a b c d e")
                self.assertEqual(self._paste(run, "a\x07b\x1bc\x7fd\x85e f"), b"abcdef")
                self.assertEqual(self._paste(run, "x\ud800y\udc00z"), b"xyz")
                self.assertEqual(self._paste(run, "é ñ"), "é ñ".encode("cp1252"))   # composed first
                self.assertEqual(self._paste(run, "Ω日😀€"), "€".encode("cp1252"))                 # dropped, not '?'
                self.assertEqual(self._paste(self.alone[game], "€ab~"), b"ab~")

    def test_shift_insert_pastes_and_repeats_are_swallowed(self):
        for game in GAMES:
            run = self.both[game]
            b = run.box()
            run.clip.text = "ab"
            self.assertEqual(run.press(self.emu.SDLK_INSERT, self.emu.KMOD_LSHIFT), {"to": "next event"})
            self.assertEqual(run.paste(repeat=1), {"to": "next event"})
            self.assertEqual(run.text(b), b"ab")

    def test_busy_or_empty_clipboard_does_nothing(self):
        for game in GAMES:
            run = self.both[game]
            b = run.box(text=b"Kalahuna")
            run.clip.text = None
            self.assertEqual(run.paste(), {"to": "next event"})
            run.clip.text, run.clip.busy = "zzz", True
            self.assertEqual(run.paste(), {"to": "next event"})
            self.assertEqual(run.cut(), {"to": "next event"})
            self.assertEqual(run.text(b), b"Kalahuna")
            run.clip.busy = False
            self.assertEqual(run.clip.text, "zzz")

    # -- copy and cut -----------------------------------------------------------------------------
    def test_copy_and_round_trip(self):
        cases = {"alone": [(b"Kalahuna Tribe", "Kalahuna Tribe")],
                 "1252": [(ZOE.encode("cp1252"), ZOE), (b"\x80\x81\x9f", "€\x81Ÿ")],
                 "utf8": [((ZOE + " 日本👍🏽").encode(), ZOE + " 日本👍🏽"), (b"Zo\xeb", "Zoë")]}
        for game in GAMES:
            for kind, pairs in cases.items():
                run = self.alone[game] if kind == "alone" else self.both[game]
                run.set_glyphs_utf8(1) if kind == "utf8" else None
                for stored, text in pairs:
                    with self.subTest(game=game, kind=kind, text=text):
                        b = run.box(text=stored, limit=40)
                        self.assertEqual(run.copy(), {"to": "next event"})
                        self.assertEqual(run.clip.text, text)
                        self.assertEqual(run.raw(b, len(stored) + 2), stored + b"\0\0")    # untouched
                        self.assertEqual(run.press(self.emu.SDLK_INSERT, self.emu.KMOD_LCTRL), {"to": "next event"})
                        self.assertEqual(run.clip.text, text)
                        # bytes the game would not store this way (an undefined Windows-1252 byte, a
                        # Windows-1252 letter in a UTF-8 game) copy as text but paste back as that text
                        if stored not in (b"\x80\x81\x9f", b"Zo\xeb"):
                            run.clear_listeners()
                            self.assertEqual(self._paste(run, run.clip.text, limit=40), stored)
                if kind == "utf8":
                    run.set_glyphs_utf8(0)

    def test_an_empty_box_copies_nothing(self):
        for game in GAMES:
            run = self.both[game]
            run.box()
            run.clip.text = "kept"
            self.assertEqual(run.copy(), {"to": "next event"})
            self.assertEqual(run.clip.text, "kept")

    def test_cut(self):
        for game in GAMES:
            run = self.both[game]
            b = run.box(text=ZOE.encode("cp1252"))
            self.assertEqual(run.cut(), {"to": "next event"})
            self.assertEqual(run.clip.text, ZOE)
            self.assertEqual(run.text(b), b"")
            run.clear_listeners()
            self.assertEqual(self._paste(run, run.clip.text), ZOE.encode("cp1252"))

    # -- what is left alone -----------------------------------------------------------------------
    def test_other_keys_and_unfocused_boxes_go_to_the_game_unchanged(self):
        emu = self.emu
        for game in GAMES:
            run = self.both[game]
            imm = struct.unpack("<I", bytes.fromhex(_manifest(game)["runtime_detours"][0]["stock_bytes"])[6:])[0]
            b = run.box(text=b"Kalahuna")
            run.clip.text = "zzz"
            for sym, mod in ((ord("v"), 0), (ord("a"), emu.KMOD_LCTRL), (ord("v"), emu.KMOD_LCTRL | emu.KMOD_LALT),
                             (ord("v"), emu.KMOD_LCTRL | emu.KMOD_RALT), (ord("c"), emu.KMOD_RALT),
                             (0x1B, 0), (0x08, 0), (0x40000050, 0), (emu.SDLK_INSERT, 0), (0x4000003A, 0),
                             (0x40000041, 0), (0x40000044, emu.KMOD_LCTRL)):
                with self.subTest(game=game, sym=hex(sym), mod=hex(mod)):
                    got = run.press(sym, mod)
                    self.assertEqual(got["to"], "game")
                    self.assertEqual(got["ecx"], sym)
                    self.assertEqual(got["eax"], 0x300)
                    self.assertEqual(got["zf"], sym == imm)
                    self.assertEqual(got["sf"], ((sym - imm) & 0xFFFFFFFF) >> 31 == 1)
                    self.assertEqual(got["cf"], sym < imm)
            self.assertEqual(run.text(b), b"Kalahuna")
            self.assertEqual(run.clip.text, "zzz")
            for box in ({"focused": False}, {"active": False}, {"listen": False}, {"last_before": True}):
                run.clear_listeners()
                b = run.box(text=b"Kalahuna", **box)
                for sym, mod in ((ord("v"), emu.KMOD_LCTRL), (ord("x"), emu.KMOD_LCTRL), (ord("c"), emu.KMOD_LCTRL)):
                    with self.subTest(game=game, box=box, sym=chr(sym)):
                        self.assertEqual(run.press(sym, mod)["to"], "game")
                self.assertEqual(run.text(b), b"Kalahuna")
                self.assertEqual(run.clip.text, "zzz")
            run.clear_listeners()
            b = run.box(text=b"Kalahuna")
            run.mu.mem_write(b + 0x2F, b"\x01")
            self.assertEqual(run.paste()["to"], "game")
            self.assertEqual(run.text(b), b"Kalahuna")

    def test_opening_and_closing_a_box_leaves_its_bytes(self):
        """No key of ours: the box's bytes, past its end too, are exactly as stored."""
        for game in GAMES:
            run = self.both[game]
            stored = b"Zo\xeb \xd1\xfa\xf1ez"
            b = run.box(text=stored, limit=20)
            before = run.raw(b, 21)
            for sym in (0x40000050, 0x4000004F, 0x1B, 0x0D):
                run.press(sym)
            run.mu.mem_write(b + 0x25, b"\x00")                  # focus leaves
            run.clip.text = "zzz"
            run.paste()
            self.assertEqual(run.raw(b, 21), before)

    # -- with Render Unicode with In-Game Fonts -----------------------------------------------------
    def test_both_detours_coexist(self):
        for game in GAMES:
            run = self.both[game]
            t = TABLES["games"][game]["text_input"]
            site, post, skip = (int(t[k], 16) for k in ("site", "post", "skip"))
            ut = run.machine.modules["vvfp unicode text.dll"]
            code = bytes(run.mu.mem_read(site, 7))
            with self.subTest(game=game):
                self.assertEqual(code[0], 0xE9)
                self.assertTrue(ut.base <= site + 5 + struct.unpack("<i", code[1:5])[0] < ut.base + 0x200000)
                self.assertEqual(run.type_text("é".encode(), site, post, skip, t["text_offset"]), ("post", 0xE9))
                self.assertEqual(run.type_text(b"v", site, post, skip, t["text_offset"]), ("post", ord("v")))
                self.assertEqual(self._paste(run, "é€"), "é€".encode("cp1252"))
            alone = self.alone[game]
            self.assertEqual(bytes(alone.mu.mem_read(site, 7)), bytes.fromhex(t["stock_bytes"]))


if __name__ == "__main__":
    unittest.main()
