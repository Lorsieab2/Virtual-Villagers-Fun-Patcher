"""Skip All on the Intro Story (vv1_skip_all_intro, vv2_skip_all_intro): The Secret City's Skip All button on the
story pages of A New Home and The Lost Children (docs/reports/vv12-skip-all/design.md).

THE STOCK CODE: every address native/vvfp_skip_intro/vvfp_skip_intro.c uses, proved against each stock
executable -- the story page classes' vtable slots, the pages' constructors and their states, the last page's
Yes button (its art, its row, its label colours), the game's own help question on that page, the stock page end.

THE GAME (tests/skip_intro_emulation.py): each published build is started as the game starts it and the game's
own screen manager runs the story frame by frame in unicorn: the button is built by the game's own constructor,
is a child of the page with the game's art and the label "Skip All", and the game's own hit test reports its
click; the click ends the story and lands on the help question with Yes and No up at once; Yes and No write
exactly what they write at the end of the stock story (the same run on the stock executable); without a click on
Skip All the story is the stock story.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import vv_fun_patcher as patcher  # noqa: E402

GAMES = ("vv1", "vv2")
DLL_NAME = "VVFP Skip Intro.dll"
DLL = ROOT / "assets" / "skip_intro" / DLL_NAME
STOCK_DIR = ROOT / "research" / "stock-executables"
EXES = {"vv1": "Virtual Villagers - A New Home.exe", "vv2": "Virtual Villagers - The Lost Children.exe",
        "vv3": "Virtual Villagers - The Secret City.exe"}
HAVE_STOCK = all((STOCK_DIR / name).is_file() for name in EXES.values())
try:
    import capstone
    import pefile
    import unicorn  # noqa: F401
    HAVE_EMULATOR = True
except ImportError:  # pragma: no cover
    HAVE_EMULATOR = False

# The slots the companion replaces: game -> [(vtable, slot, stock)] (vvfp_skip_intro.c SK_GAMES).
SLOTS = {
    "vv1": [(0x4597F4, 0, 0x41EA00), (0x4597F4, 3, 0x41F640), (0x4597F4, 9, 0x41E5C0), (0x45982C, 8, 0x41F310)],
    "vv2": [(0x476AC4, 0, 0x428220), (0x476AC4, 3, 0x401190), (0x476AC4, 8, 0x428240), (0x476AC4, 9, 0x427DB0),
            (0x476AFC, 0, 0x4288F0), (0x476AFC, 3, 0x401190), (0x476AFC, 9, 0x43A2B0), (0x476B34, 8, 0x4292C0)],
}
# Each page: its constructor and where it puts its vtable, its state and the state its stock end sets.
PAGES = {
    "vv1": [(0x41E600, 0x41E629, 0x4597F4, 0x41EB0E, 0x16), (0x41ED00, 0x41ED30, 0x45982C, 0x41F455, 1)],
    "vv2": [(0x427E20, 0x427E49, 0x476AC4, 0x42832E, 0x17), (0x428470, 0x4284A0, 0x476AFC, 0x428A39, 0x18),
            (0x428CB0, 0x428CE0, 0x476B34, 0x429405, 1)],
}
# The last page's Yes button: the push of the art name, the row (y), and the help question's table id.
LAST = {"vv1": (0x41EE92, 0x459340, "main_wide_button2.png", 0x41EE80, 560, 0xFD, "Would you like HELP"),
        "vv2": (0x428E42, 0x476378, "popup_button1.png", 0x428E30, 550, 0x17D, "Would you like tutorial tips")}
# Which tutorial-flag bytes of the game object the run pre-fills, so the answer's writes show.
FLAG_FILL = (0x31, 0x31 + 0x1E3 + 0x10)


def _manifest(game: str) -> dict:
    return json.loads((ROOT / "data" / f"{game}_skip_all_intro_feature.json").read_text(encoding="utf-8"))


def _load_script(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@unittest.skipUnless(HAVE_STOCK and HAVE_EMULATOR, "the stock executables or capstone/pefile are not available")
class TheStockCode(unittest.TestCase):
    """Every address the companion uses is what each stock executable has there."""

    @classmethod
    def setUpClass(cls):
        cls.md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
        cls.images = {g: pefile.PE(str(STOCK_DIR / EXES[g])).get_memory_mapped_image() for g in EXES}

    def _dword(self, game, va):
        return struct.unpack_from("<I", self.images[game], va - 0x400000)[0]

    def _dis(self, game, va, n):
        img = self.images[game]
        return list(self.md.disasm(img[va - 0x400000:va - 0x400000 + n], va))

    def _cstr(self, game, va):
        img = self.images[game]
        return img[va - 0x400000:img.index(b"\0", va - 0x400000)].decode("cp1252")

    def test_the_slots_hold_the_stock_routines(self):
        for game, slots in SLOTS.items():
            for vtable, slot, stock in slots:
                with self.subTest(game=game, va=hex(vtable + 4 * slot)):
                    self.assertEqual(self._dword(game, vtable + 4 * slot), stock)

    def test_the_rows_declare_exactly_those_slots(self):
        for game, slots in SLOTS.items():
            declared = [(int(d["va"], 16), bytes.fromhex(d["stock_bytes"])) for d in _manifest(game)["runtime_detours"]]
            self.assertEqual(declared, [(vt + 4 * s, struct.pack("<I", stock)) for vt, s, stock in slots])

    def test_the_slot_routines_are_what_the_companion_takes_them_for(self):
        # the button slot of the pages before the last is the do-nothing stub: no buttons of their own
        for game, stub in (("vv1", 0x41F640), ("vv2", 0x401190)):
            ins = self._dis(game, stub, 5)
            self.assertEqual([(i.mnemonic, i.op_str) for i in ins[:2]], [("xor", "al, al"), ("ret", "8")])
        # their event slot: event 2 (a press anywhere) marks the page done
        for game, slot1, fields in (("vv1", 0x41E5D0, ("0x78", "0x28")), ("vv2", 0x427DF0, ("0x78", "0x28")),
                                    ("vv2", 0x428430, ("0x1d4", "0x1a0"))):
            body = " ; ".join(f"{i.mnemonic} {i.op_str}" for i in self._dis(game, slot1, 0x40))
            self.assertIn("sub eax, 2", body)
            for field in fields:
                self.assertIn(f"[esi + {field}]", body)
            self.assertIn("ret 0xc", body)

    def test_the_pages_their_constructors_and_their_ends(self):
        for game, pages in PAGES.items():
            for ctor, at, vtable, end_at, next_state in pages:
                with self.subTest(game=game, page=hex(vtable)):
                    ins = self._dis(game, at, 6)[0]
                    self.assertEqual((ins.mnemonic, ins.op_str), ("mov", f"dword ptr [esi], {vtable:#x}"))
                    self.assertLess(ctor, at)
                    end = self._dis(game, end_at, 10)[0]
                    self.assertEqual(end.mnemonic, "mov")
                    self.assertTrue(end.op_str.endswith(f"], {next_state:#x}") or end.op_str.endswith(f"], {next_state}"))

    def test_the_last_page_asks_the_help_question_with_the_art_the_button_uses(self):
        tables = {"vv1": (0x487208, 629, 0x14), "vv2": (0x496300, 0x36C, 12)}
        for game, (push_at, art, name, x_at, y, question, words) in LAST.items():
            with self.subTest(game=game):
                ins = self._dis(game, push_at, 5)[0]
                self.assertEqual((ins.mnemonic, ins.op_str), ("push", hex(art)))
                self.assertEqual(self._cstr(game, art), name)
                row = self._dis(game, x_at, 5)[0]
                self.assertEqual(row.op_str, f"edx, {y:#x}")
                va, count, stride = tables[game]
                english = {}
                for i in range(count):
                    rid, en = struct.unpack_from("<II", self.images[game], va - 0x400000 + i * stride)
                    english.setdefault(rid, en)
                self.assertTrue(self._cstr(game, english[question]).startswith(words))

    def test_the_secret_city_has_the_button_in_stock(self):
        # its story overlay builds Skip All (sm 0x89) at (640, 540), Yes at (228, 550) and No at (428, 550)
        body = " ; ".join(f"{i.mnemonic} {i.op_str}" for i in self._dis("vv3", 0x4643D0, 0x1C0))
        for piece in ("mov ecx, 0x21c", "mov eax, 0x280", "push 0x89", "mov ecx, 0x226", "mov eax, 0xe4",
                      "push 0x87", "mov eax, 0x1ac", "push 0x88"):
            self.assertIn(piece, body)
        self.assertEqual(self._cstr("vv3", 0x499C6C), "Skip All")
        # its button handler: Skip All asks "Do you need help?" (sm 0x24C) in a two-button box
        handler = " ; ".join(f"{i.mnemonic} {i.op_str}" for i in self._dis("vv3", 0x464700, 0x80))
        self.assertIn("push 0x24c", handler)
        self.assertEqual(self._cstr("vv3", 0x495B80).strip(), "Do you need help?")


class TheRows(unittest.TestCase):
    def test_the_rows(self):
        sha = hashlib.sha256(DLL.read_bytes()).hexdigest().upper()
        public = {p.id for p in patcher.load_public_fun_patches()}
        for game in GAMES:
            with self.subTest(game=game):
                row = _manifest(game)
                self.assertEqual(row["id"], f"{game}_skip_all_intro")
                self.assertIn(row["id"], public)
                self.assertEqual(row["name"], "Skip All on the Intro Story")
                self.assertTrue(row["enabled"])
                self.assertEqual(row["patches"], [])
                self.assertNotIn("dependencies", row)
                self.assertEqual(row["companion_files"], [{"source": f"assets/skip_intro/{DLL_NAME}",
                                                           "destination": DLL_NAME, "sha256": sha}])
                for words in ("**On by default.**", "**Needs no other patch.**", "**Not yet seen in a running game**",
                              "Skip All", "help question"):
                    self.assertIn(words, row["description"])

    def test_only_a_new_home_and_the_lost_children(self):
        ids = {p.id for p in patcher.load_fun_patches() if p.id.endswith("_skip_all_intro")}
        self.assertEqual(ids, {"vv1_skip_all_intro", "vv2_skip_all_intro"})

    def test_the_generator_reproduces_the_rows(self):
        module = _load_script("build_skip_intro_feature")
        sha = hashlib.sha256(DLL.read_bytes()).hexdigest().upper()
        for number, game in enumerate(GAMES, start=1):
            self.assertEqual(module.row(number, sha), _manifest(game))

    def test_started_by_the_startup_loader_second_word(self):
        names = list(patcher.STARTUP_LOADER_COMPANIONS_2)
        self.assertIn(DLL_NAME, names)
        self.assertGreater(names.index(DLL_NAME), names.index("VVFP Copy and Paste.dll"))   # appended (append only)
        header = (ROOT / "native" / "shared" / "startup_companions_2.h").read_text(encoding="utf-8")
        self.assertIn(f'    "{DLL_NAME}",\n    /* APPEND ONLY', header)
        loader = (ROOT / "assets" / "startup" / "VVFP Startup.dll").read_bytes()
        self.assertIn(DLL_NAME.encode(), loader)
        self.assertEqual(hashlib.sha256(loader).hexdigest().upper(), patcher.STARTUP_LOADER_COMPANION["sha256"])

    def test_on_by_default_in_select_all_and_owners_defaults(self):
        from vv_fun_patcher_gui import (default_fun_patch_selection, owners_default_fun_patch_selection,
                                        select_all_fun_patch_selection)
        for game in GAMES:
            self.assertTrue(default_fun_patch_selection(f"{game}_skip_all_intro"))
            self.assertTrue(owners_default_fun_patch_selection(f"{game}_skip_all_intro"))
            self.assertTrue(select_all_fun_patch_selection(f"{game}_skip_all_intro"))

    def test_registered_bundled_documented(self):
        release = (ROOT / "scripts" / "build_release.py").read_text(encoding="utf-8")
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        guide = json.loads((ROOT / "data" / "how_to_use.json").read_text(encoding="utf-8"))
        how_to = (ROOT / "How to Use.txt").read_text(encoding="utf-8")
        self.assertIn(f'"assets/skip_intro/{DLL_NAME}"', release)
        self.assertIn("SKIP ALL ON THE INTRO STORY", how_to)
        guided = {i for entry in guide["patches"] for i in entry.get("ids", [])}
        for game in GAMES:
            self.assertIn(f'"data/{game}_skip_all_intro_feature.json"', release)
            self.assertIn(f"- Patch ID: `{game}_skip_all_intro`", readme)
            self.assertIn(_manifest(game)["description"], readme)
            self.assertIn(f"{game}_skip_all_intro", guided)
        log = (ROOT / "docs" / "transparency-log.md").read_text(encoding="utf-8")
        self.assertIn("Skip All on the Intro Story", log)

    def test_the_label_is_translatable(self):
        rows = json.loads((ROOT / "data" / "translations" / "patcher_strings.json").read_text(encoding="utf-8"))
        rows = rows["strings"] if isinstance(rows, dict) and "strings" in rows else rows
        source = (ROOT / "native" / "vvfp_skip_intro" / "vvfp_skip_intro.c").read_text(encoding="utf-8")
        stem = "vvfp.skip_intro/vvfp_skip_intro.label_text.s0"
        self.assertIn(f'vvfp_tr("{stem}", "Skip All", 0)', source)
        row = next(r for r in (rows if isinstance(rows, list) else rows.get("rows", [])) if r["stem"] == stem)
        self.assertEqual((row["english"], row["games"]), ("Skip All", ["vv1", "vv2"]))

    @unittest.skipUnless(HAVE_EMULATOR, "pefile is not installed")
    def test_the_dll_exports_and_imports(self):
        pe = pefile.PE(str(DLL))
        names = sorted(e.name.decode() for e in pe.DIRECTORY_ENTRY_EXPORT.symbols if e.name)
        self.assertEqual(names, ["VvfpSkipIntroSites", "VvfpStartup"])
        imports = {i.name.decode() for e in pe.DIRECTORY_ENTRY_IMPORT for i in e.imports if i.name}
        self.assertEqual(imports & {"LoadLibraryA", "LoadLibraryW", "OutputDebugStringA", "OutputDebugStringW",
                                    "MessageBoxA", "MessageBoxW", "DeleteFileW", "CreateFileA", "MoveFileW",
                                    "RegSetValueExW", "Sleep", "CreateThread"}, set())
        for section in pe.sections:
            self.assertFalse(section.Characteristics & 0x20000000 and section.Characteristics & 0x80000000)


@unittest.skipUnless(HAVE_STOCK and HAVE_EMULATOR, "needs the stock executables and unicorn")
class TheGame(unittest.TestCase):
    """The published builds' own story, emulated with the companion (and the stock executable without it)."""

    @classmethod
    def setUpClass(cls):
        import skip_intro_emulation as emu
        cls.emu = emu

    def tearDown(self):
        import gc
        gc.collect()                            # each run's machine (its unicorn) goes with the test

    def _published(self, game):
        from test_startup_loader import closure, run
        self.emu.register()
        machine, _result, features, _before, _shipped = run(game, "collection_progression",
                                                             tuple(closure(f"{game}_skip_all_intro")))
        self.assertIn(f"{game}_skip_all_intro", features)
        intro = self.emu.Intro(machine, game)
        intro.module = machine.modules[DLL_NAME.lower()]
        self._fill(intro)
        return intro

    def _stock(self, game):
        from startup_emulation import StartupMachine
        from test_startup_loader import build_of
        self.emu.register()
        machine = StartupMachine((STOCK_DIR / EXES[game]).read_bytes(), build_of(game).input_name, {})
        intro = self.emu.Intro(machine, game)
        self._fill(intro)
        return intro

    @staticmethod
    def _fill(intro):
        start, end = FLAG_FILL
        intro.mu.mem_write(intro.game_obj + start, b"\x5A" * (end - start))

    def _start(self, intro):
        """Frames until the first page is up and its fade-in has run."""
        first = intro.g["first"]
        intro.run_until(lambda: intro.page(first) != 0 and intro.active(intro.page(first)))
        for _ in range(60):
            intro.frame()
        return intro.page(first)

    def _turn_pages(self, intro):
        """The stock way through the story: a click anywhere on each page before the last."""
        for state in sorted(intro.g["pages"]):
            if state == intro.g["last"]:
                break
            intro.run_until(lambda: intro.state == state and intro.active(intro.page(state)))
            for _ in range(60):
                intro.frame()
            intro.click_anywhere(intro.page(state))
            intro.run_until(lambda: intro.state != state)

    def _answer(self, intro, yes):
        """Yes or No on the question; the game object after the story has ended, and the sounds."""
        intro.tick = 50_000                     # the same clock for the answer in every run
        intro.sounds.clear()
        before = intro.game_bytes()
        intro.answer(yes)
        intro.run_until(lambda: intro.state == 1)
        after = intro.game_bytes()
        self.assertNotEqual(after, before)      # the answer wrote the game's own flags
        return after, list(intro.sounds)

    # -- installed --------------------------------------------------------------------------------
    def test_the_slots_point_into_the_companion(self):
        for game in GAMES:
            with self.subTest(game=game):
                intro = self._published(game)
                self.assertEqual(intro.call(intro.module.exports["VvfpSkipIntroSites"]), len(SLOTS[game]))
                base, size = intro.module.base, intro.module.size
                for vtable, slot, stock in SLOTS[game]:
                    now = intro.dword(vtable + 4 * slot)
                    self.assertNotEqual(now, stock)
                    self.assertTrue(base <= now < base + size, hex(now))

    def test_a_different_build_installs_nothing(self):
        # one slot not stock: nothing at all is written (all or none)
        from test_startup_loader import closure, published, build_of
        from startup_emulation import StartupMachine
        for game in GAMES:
            with self.subTest(game=game):
                exe, shipped, _features = published(game, "collection_progression",
                                                    tuple(closure(f"{game}_skip_all_intro")))
                pe = pefile.PE(data=exe)
                vtable, slot, stock = SLOTS[game][-1]
                at = pe.get_offset_from_rva(vtable + 4 * slot - 0x400000)
                changed = bytearray(exe)
                changed[at:at + 4] = struct.pack("<I", stock + 0x10)
                self.emu.register()
                machine = StartupMachine(bytes(changed), build_of(game).input_name, shipped)
                call_va, winmain = patcher.STARTUP_LOADER_WINMAIN_CALL[game]
                machine.run_to_winmain(call_va, winmain)
                intro = self.emu.Intro(machine, game)
                module = machine.modules[DLL_NAME.lower()]
                self.assertEqual(intro.call(module.exports["VvfpSkipIntroSites"]), 0)
                for vt, s, st in SLOTS[game][:-1]:
                    self.assertEqual(intro.dword(vt + 4 * s), st)

    # -- the button -------------------------------------------------------------------------------
    def test_the_button_is_the_games_own_on_every_page_before_the_question(self):
        for game in GAMES:
            with self.subTest(game=game):
                intro = self._published(game)
                page = self._start(intro)
                button = intro.skip_button(page)
                self.assertIsNotNone(button)
                real = intro.dword(button + 0x10)
                self.assertEqual(intro.dword(real), intro.g["button_vtable"])     # the game's button class
                width = intro.g["art_size"][0] // 3                               # one frame of the art strip
                x, y = intro.g["skip_xy"]
                self.assertEqual(intro.rect(button), (x, y, x + width, y + 32))
                self.assertEqual(intro.label(button), "Skip All")
                art = intro.cstr(intro.g["art"])
                image = intro.dword(real + 0x3C)
                self.assertEqual(intro.textures[intro.dword(image + 4)], art)       # the Yes button's art
                self.assertEqual(intro.dword(real + 0x20), page)                   # reports to its page
                # built once: a second activation keeps the one button
                kids = intro.children(page)
                self.assertEqual(sum(1 for k in kids if k == button), 1)
                # the pages before the last all have one; the last page has none
                if game == "vv2":
                    self._turn_pages_to(intro, 0x17)
                    self.assertIsNotNone(intro.skip_button(intro.page(0x17)))
                self.assertIsNone(intro.skip_button(intro.page(intro.g["last"])))

    def _turn_pages_to(self, intro, target):
        state = intro.state
        intro.click_anywhere(intro.page(state))
        intro.run_until(lambda: intro.state == target and intro.active(intro.page(target)))

    def test_the_games_hit_test_takes_only_a_click_on_the_button(self):
        for game in GAMES:
            with self.subTest(game=game):
                intro = self._published(game)
                page = self._start(intro)
                button = intro.skip_button(page)
                x0, y0, x1, y1 = intro.rect(button)
                # outside: the button does not take it, the page stays
                self.assertEqual(intro.mouse(button, 2, x0 - 5, y0 + 5), 0)
                self.assertEqual(intro.mouse(button, 3, x0 - 5, y0 + 5), 0)
                for _ in range(120):
                    intro.frame()
                self.assertEqual(intro.state, intro.g["first"])
                # inside: press and release, message 8 to the page, the page fades out
                self.assertEqual(intro.mouse(button, 2, (x0 + x1) // 2, (y0 + y1) // 2), 1)
                self.assertEqual(intro.mouse(button, 3, (x0 + x1) // 2, (y0 + y1) // 2), 1)
                frames = intro.run_until(lambda: intro.state != intro.g["first"])
                self.assertLessEqual(frames, 51)                                   # the stock 50-frame fade

    # -- the skip ---------------------------------------------------------------------------------
    def test_skip_all_lands_on_the_question_with_yes_and_no_up(self):
        for game in GAMES:
            with self.subTest(game=game):
                intro = self._published(game)
                page = self._start(intro)
                button = intro.skip_button(page)
                x0, y0, x1, y1 = intro.rect(button)
                intro.click_button(button, (x0 + x1) // 2, (y0 + y1) // 2)
                intro.run_until(lambda: intro.state != intro.g["first"])
                self.assertEqual(intro.state, intro.g["last"])                     # straight to the question
                if game == "vv2":
                    self.assertFalse(intro.active(intro.page(0x17)))
                    self.assertEqual(intro.byte(intro.page(0x17) + 8), 0)         # page 2 never ran
                self.assertEqual(intro.run_until(intro.question_up), 1)            # its first frame

    def test_skip_all_from_the_second_page(self):
        intro = self._published("vv2")
        self._start(intro)
        self._turn_pages_to(intro, 0x17)
        for _ in range(60):
            intro.frame()
        button = intro.skip_button(intro.page(0x17))
        x0, y0, x1, y1 = intro.rect(button)
        intro.click_button(button, (x0 + x1) // 2, (y0 + y1) // 2)
        intro.run_until(lambda: intro.state == 0x18)
        self.assertEqual(intro.run_until(intro.question_up), 1)

    def test_yes_and_no_write_what_the_stock_story_writes(self):
        for game in GAMES:
            for yes in (True, False):
                with self.subTest(game=game, answer="Yes" if yes else "No"):
                    stock = self._stock(game)
                    self._start(stock)
                    self._turn_pages(stock)
                    self.assertEqual(stock.run_until(stock.question_up), 50)
                    stock_bytes, stock_sounds = self._answer(stock, yes)

                    skipped = self._published(game)
                    page = self._start(skipped)
                    button = skipped.skip_button(page)
                    x0, y0, x1, y1 = skipped.rect(button)
                    skipped.click_button(button, (x0 + x1) // 2, (y0 + y1) // 2)
                    skipped.run_until(skipped.question_up)
                    skip_bytes, skip_sounds = self._answer(skipped, yes)

                    self.assertEqual(skip_sounds, stock_sounds)
                    self.assertEqual(skip_bytes, stock_bytes)

    def test_yes_and_no_differ(self):
        for game in GAMES:
            with self.subTest(game=game):
                runs = []
                for yes in (True, False):
                    intro = self._published(game)
                    page = self._start(intro)
                    button = intro.skip_button(page)
                    x0, y0, x1, y1 = intro.rect(button)
                    intro.click_button(button, (x0 + x1) // 2, (y0 + y1) // 2)
                    intro.run_until(intro.question_up)
                    runs.append(self._answer(intro, yes))
                self.assertNotEqual(runs[0][0], runs[1][0])
                self.assertEqual(runs[0][1], [0x44] if game == "vv1" else [0x4A])
                self.assertEqual(runs[1][1], [0x43] if game == "vv1" else [0x49])

    def test_without_skip_all_the_story_is_stock(self):
        for game in GAMES:
            for yes in (True, False):
                with self.subTest(game=game, answer="Yes" if yes else "No"):
                    results = []
                    for intro in (self._stock(game), self._published(game)):
                        self._start(intro)
                        self._turn_pages(intro)
                        wait = intro.run_until(intro.question_up)
                        results.append((wait, intro.state) + self._answer(intro, yes))
                    self.assertEqual(results[0], results[1])
                    self.assertEqual(results[0][0], 50)

    def test_a_destroyed_page_frees_its_button_first(self):
        for game in GAMES:
            with self.subTest(game=game):
                intro = self._published(game)
                page = self._start(intro)
                button = intro.skip_button(page)
                intro.call(intro.dword(intro.dword(page)), page, (1,))            # the page's deleting dtor
                self.assertIn(button, intro.deleted)                              # the button, by its own dtor
                self.assertIn(page, intro.deleted)                                # then the page
                self.assertLess(intro.deleted.index(button), intro.deleted.index(page))


if __name__ == "__main__":
    unittest.main()
