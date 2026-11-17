"""Fix Vanilla Bugs: the Food Mastery tech's description says what its Level 2 bonus is for ("VVFP Food Mastery
Text.dll", The Tree of Life and New Believers; the owner, 2026-11-16).

The string table's loader (VV4 0x44D750, VV5 0x450A60) ends with the C runtime's cookie check; the companion points
that call (VV4 0x44D92E, VV5 0x450C3E) at a step that puts "At Level 2 your tribe gets a 50 percent bonus to collected
food." in place of "At Level 2 your tribe gets a 50 percent bonus." in eTechFoodMasteryInfo, whatever Assets\\sm.xml
the game has (the stock one, Optional Text Changes', Guardians of Isola's), then makes the check itself.  Shown here:
- in emulation of the shipped DLL on the stock executables: each sm.xml's text gets exactly that line changed (the
  built-in text too); a text without the line is left alone; a changed byte round the site installs nothing; the
  other games install nothing; the cookie check still runs and returns;
- the published builds started to WinMain (tests/startup_emulation.py): Fix Vanilla Bugs alone, with Optional Text
  Changes / Guardians of Isola, with Translations: the site is written; without Fix Vanilla Bugs (uninstalled) the
  DLL is not shipped and the site is stock;
- the translation template (src/vv_translations.py) gives the new English when the game has the companion.
The live game is NOT verified here.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import struct
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import vv_fun_patcher as patcher  # noqa: E402
import vv_translations as tr  # noqa: E402

try:
    import pefile
    import unicorn  # noqa: F401
    from story_emulator import Process
    HAVE_EMULATOR = True
except ImportError:  # pragma: no cover
    HAVE_EMULATOR = False

NAMES = {3: "The Secret City", 4: "The Tree of Life", 5: "New Believers"}
STOCK = {g: ROOT / "research" / "stock-executables" / f"Virtual Villagers - {n}.exe" for g, n in NAMES.items()}
HAVE_STOCK = all(p.is_file() for p in STOCK.values())
DLL_NAME = "VVFP Food Mastery Text.dll"
DLL = ROOT / "assets" / "food_mastery_text" / DLL_NAME
GAMES = (4, 5)
# (site, stock bytes of the call, the string table, its entries, the cookie global)
SITES = {4: (0x44D92E, "E85A370200", 0x4C41F8, 1338, 0x4C9FBC),
         5: (0x450C3E, "E8CAB30200", 0x4D31F0, 1409, 0x4D97A8)}
NAME = b"eTechFoodMasteryInfo"
OLD = b"At Level 2 your tribe gets a 50 percent bonus."
NEW = b"At Level 2 your tribe gets a 50 percent bonus to collected food."
SM_FILES = {
    4: {"stock": ROOT / "assets" / "text-changes" / "vv4-sm-base.xml",
        "Optional Text Changes": ROOT / "assets" / "text-changes" / "vv4-sm.xml"},
    5: {"Guardians of Isola (base)": ROOT / "data" / "guardians_of_isola" / "base" / "Assets" / "sm.xml",
        "Guardians of Isola": ROOT / "data" / "guardians_of_isola" / "new" / "Assets" / "sm.xml"},
}


def row(game: int) -> dict:
    return next(p.raw for p in patcher.load_fun_patches() if p.id == f"vv{game}_fix_vanilla_bugs")


def sm_text(path: Path) -> bytes:
    return tr._sm_lookup(tr._sm_file_texts(path.read_bytes()), NAME.decode())


class TheRows(unittest.TestCase):
    def test_the_fix_vanilla_bugs_rows_ship_and_pin_the_companion(self) -> None:
        digest = hashlib.sha256(DLL.read_bytes()).hexdigest().upper()
        self.assertIn(DLL_NAME, patcher.STARTUP_LOADER_COMPANIONS_2)
        for game in GAMES:
            with self.subTest(game=game):
                r = row(game)
                files = {f["destination"]: f["sha256"] for f in r["companion_files"]}
                self.assertEqual(files.get(DLL_NAME), digest)
                detours = [(int(d["va"], 16), d["stock_bytes"]) for d in r["runtime_detours"]
                           if DLL_NAME in d["installed_by"]]
                self.assertEqual(detours, [(SITES[game][0], SITES[game][1])])
                self.assertIn("to collected food", r["description"])
        for game in (1, 2, 3):
            self.assertNotIn(DLL_NAME, {f["destination"] for f in row(game)["companion_files"]})

    def test_every_text_patch_keeps_the_line(self) -> None:
        for game, files in SM_FILES.items():
            for label, path in files.items():
                with self.subTest(game=game, sm=label):
                    text = sm_text(path)
                    self.assertIn(OLD + b"\n", text)
                    self.assertNotIn(NEW, text)

    @unittest.skipUnless(HAVE_EMULATOR and HAVE_STOCK, "needs pefile and the stock executables")
    def test_no_other_row_writes_the_site(self) -> None:
        for game in GAMES:
            site = SITES[game][0]
            for p in patcher._load_fun_patch_records():
                if p.raw.get("game_id") != f"vv{game}":
                    continue
                for d in p.raw.get("runtime_detours", []) or []:
                    if DLL_NAME in d.get("installed_by", ""):
                        continue
                    va, n = int(str(d["va"]), 0), len(bytes.fromhex(d["stock_bytes"]))
                    self.assertFalse(va < site + 5 and site < va + n, (p.id, hex(va)))
                for edit in p.raw.get("patches", []) or []:
                    if "offset" in edit:
                        va = int(str(edit["offset"]), 0) + 0x400000
                        n = int(edit["length"]) if "length" in edit else len(bytes.fromhex(edit.get("before", "")))
                        self.assertFalse(va < site + 5 and site < va + n, (p.id, hex(va)))


@unittest.skipUnless(HAVE_EMULATOR and HAVE_STOCK and DLL.is_file(), "needs unicorn, the stock executables, the DLL")
class TheCompanion(unittest.TestCase):
    def process(self, game: int, data: bytes | None = None, install: bool = True):
        p = Process(data if data is not None else STOCK[game].read_bytes(), DLL)
        if install:
            p.export("VvfpStartup", game, 0)
        return p

    def entry(self, p, game: int) -> int:
        _site, _stock, table, count, _cookie = SITES[game]
        for i in range(count):
            at = table + 16 * i
            name = p.read(p.u32(at + 4), len(NAME) + 1)
            if name == NAME + b"\0":
                return at
        raise AssertionError("no eTechFoodMasteryInfo entry")

    def loader_end(self, p, game: int) -> None:
        """The loader's last call, made through the site: ecx = the value the cookie check compares with its global."""
        site, _stock, _table, _count, cookie = SITES[game]
        target = (site + 5 + struct.unpack("<i", p.read(site + 1, 4))[0]) & 0xFFFFFFFF
        p.call(target, [], ecx=p.u32(cookie))

    def text_after(self, game: int, text: bytes | None, p=None):
        p = p or self.process(game)
        entry = self.entry(p, game)
        if text is not None:
            va = p.alloc(len(text) + 1)
            p.write(va, text + b"\0")
            p.put32(entry + 12, va)
        self.loader_end(p, game)
        out = p.u32(entry + 12)
        source = out if out else p.u32(entry + 8)
        raw = p.read(source, 8192)
        return p, raw[:raw.index(b"\0")]

    def test_installed_on_both_games_only(self) -> None:
        for game in GAMES:
            p = self.process(game)
            self.assertEqual(p.export("VvfpFoodMasteryTextInstalled"), 1)
            self.assertNotEqual(p.read(SITES[game][0], 5).hex().upper(), SITES[game][1])
        p = self.process(3, STOCK[3].read_bytes())
        self.assertEqual(p.export("VvfpFoodMasteryTextInstalled"), 0)
        p = self.process(4, install=False)
        p.export("VvfpStartup", 5, 0)                 # the wrong game's number: its bytes are not there
        self.assertEqual(p.export("VvfpFoodMasteryTextInstalled"), 0)
        self.assertEqual(p.read(SITES[4][0], 5).hex().upper(), SITES[4][1])

    def test_every_sm_xml_gets_the_new_line_only(self) -> None:
        for game, files in SM_FILES.items():
            for label, path in files.items():
                with self.subTest(game=game, sm=label):
                    text = sm_text(path)
                    p, out = self.text_after(game, text)
                    self.assertEqual(out, text.replace(OLD, NEW, 1))
                    self.assertEqual(p.export("VvfpFoodMasteryTextFixed"), 1)
                    self.loader_end(p, game)              # a second run changes nothing more
                    self.assertEqual(p.read(p.u32(self.entry(p, game) + 12), len(out) + 1), out + b"\0")

    def test_the_built_in_text_too(self) -> None:
        for game in GAMES:
            with self.subTest(game=game):
                p = self.process(game)
                entry = self.entry(p, game)
                p.put32(entry + 12, 0)                    # no sm.xml text: the game shows its built-in one
                raw = p.read(p.u32(entry + 8), 4096)
                built_in = raw[:raw.index(b"\0")]
                _p, out = self.text_after(game, None, p)
                if OLD + b"\n" in built_in:
                    self.assertEqual(out, built_in.replace(OLD, NEW, 1))
                else:
                    self.assertEqual(out, built_in)

    def test_another_wording_is_left_alone(self) -> None:
        for game in GAMES:
            for text in (b"Food Mastery\n\nAt Level 2 your tribe gets a 50 percent bonus to collected food.\n",
                         b"At Level 2 your tribe gets a 50 percent bonus.5\n", b"Something else entirely", b""):
                with self.subTest(game=game, text=text):
                    p = self.process(game)
                    entry = self.entry(p, game)
                    va = p.alloc(len(text) + 1)
                    p.write(va, text + b"\0")
                    p.put32(entry + 12, va)
                    self.loader_end(p, game)
                    self.assertEqual(p.u32(entry + 12), va)
                    self.assertEqual(p.export("VvfpFoodMasteryTextFixed"), 0)

    def test_a_changed_byte_round_the_site_installs_nothing(self) -> None:
        for game in GAMES:
            site = SITES[game][0]
            for at in (site - 3, site - 1, site, site + 4, site + 5, site + 12):
                with self.subTest(game=game, at=hex(at)):
                    data = bytearray(STOCK[game].read_bytes())
                    pe = pefile.PE(data=bytes(data), fast_load=True)
                    data[pe.get_offset_from_rva(at - 0x400000)] ^= 0xFF
                    p = self.process(game, bytes(data))
                    self.assertEqual(p.export("VvfpFoodMasteryTextInstalled"), 0)
                    if not site <= at < site + 5:
                        self.assertEqual(p.read(site, 5).hex().upper(), SITES[game][1])


class TheTemplate(unittest.TestCase):
    """The translation template follows the companion: the new English (and its key's hash) only when the game
    has it."""

    def folder(self, game: int, *, dll: bool, log: list[str] | None, other_hash: bool = False) -> Path:
        base = Path(tempfile.mkdtemp(prefix="vvfm"))
        self.addCleanup(shutil.rmtree, base, True)
        exe = base / f"Virtual Villagers - {NAMES[game]} - Modded.exe"
        exe.write_bytes(STOCK[game].read_bytes())
        files = base / tr.PATCHER_FILES
        files.mkdir()
        if dll:
            (files / DLL_NAME).write_bytes(b"MZ")
        if log is not None:
            digest = "0" * 64 if other_hash else hashlib.sha256(exe.read_bytes()).hexdigest()
            (files / "VVFP Patch Log.json").write_text(json.dumps(
                {"patcher": "Virtual Villagers Fun Patcher", "output_sha256": digest, "fun_patches": log}),
                encoding="utf-8")
        return exe

    @unittest.skipUnless(HAVE_STOCK, "needs the stock executables")
    def test_the_english_follows_the_companion(self) -> None:
        for game in GAMES:
            fvb = [f"vv{game}_fix_vanilla_bugs"]
            for dll, log, other, fixed in ((True, fvb, False, True), (True, None, False, True),
                                           (True, [], False, False), (True, [], True, True),
                                           (False, fvb, False, False)):
                with self.subTest(game=game, dll=dll, log=log, other_hash=other):
                    exe = self.folder(game, dll=dll, log=log, other_hash=other)
                    english = tr.game_english(game, exe)[tr.FOOD_MASTERY_STEM]
                    self.assertEqual(tr.FOOD_MASTERY_NEW in english, fixed)
                    self.assertEqual(tr.FOOD_MASTERY_OLD + "\n" in english, not fixed)
        exe = self.folder(3, dll=True, log=["vv3_fix_vanilla_bugs"])
        self.assertNotIn(tr.FOOD_MASTERY_STEM, tr.game_english(3, exe))

    def test_the_rule_is_the_companions(self) -> None:
        old, new = tr.FOOD_MASTERY_OLD, tr.FOOD_MASTERY_NEW
        self.assertEqual(old.encode(), OLD)
        self.assertEqual(new.encode(), NEW)
        self.assertEqual(tr.food_mastery_fixed(f"a\n{old}\nb"), f"a\n{new}\nb")
        self.assertEqual(tr.food_mastery_fixed(old), new)
        self.assertEqual(tr.food_mastery_fixed(old + "x"), old + "x")
        self.assertEqual(tr.food_mastery_fixed(new), new)
        source = (ROOT / "native" / "vvfp_food_mastery_text" / "vvfp_food_mastery_text.c").read_text(encoding="utf-8")
        self.assertIn(f'#define FM_OLD "{old}"', source)
        self.assertIn(f'#define FM_NEW "{new}"', source)


IMAGES = ROOT / "research" / "game-images"
HAVE_IMAGES = all((IMAGES / f"Virtual Villagers - {NAMES[g]}" / "Images").is_dir() for g in GAMES)


@unittest.skipUnless(HAVE_EMULATOR and HAVE_STOCK and HAVE_IMAGES, "needs unicorn, the stock executables and images")
class TheBoxFits(unittest.TestCase):
    """The message box sizes itself to its widest line (the game's own constructor and sizer,
    tests/scrolling_popups_emulation.py): the description with the new line on one line stays on screen."""

    def test_one_line_fits_on_screen(self) -> None:
        import scrolling_popups_emulation as spe
        for game, files in SM_FILES.items():
            d = spe.Dialog(f"vv{game}")
            w, _h = d.g["screen"]
            for label, path in files.items():
                with self.subTest(game=game, sm=label):
                    text = sm_text(path).replace(OLD, NEW, 1)
                    d.make_box(text)
                    left, _top, right, _bottom = d.panel()
                    self.assertGreaterEqual(left, 16)
                    self.assertLessEqual(right, w - 16)
                    self.assertLessEqual(d.stock_width, w - 32)


@unittest.skipUnless(HAVE_EMULATOR and HAVE_STOCK and DLL.is_file(), "needs unicorn, the stock executables, the DLL")
class EveryInstall(unittest.TestCase):
    """The published builds, started to WinMain as the game starts them."""

    def check(self, game: int, extra: tuple[str, ...], fvb: bool = True) -> None:
        import test_startup_loader as sl
        g = f"vv{game}"
        selection: list[str] = []
        for feature in ((f"{g}_fix_vanilla_bugs",) if fvb else ()) + extra:
            sl.closure(feature, selection)
        machine, _result, _features, _before, shipped = sl.run(g, "collection_progression", selection)
        site, stock = SITES[game][0], SITES[game][1]
        self.assertEqual(DLL_NAME in shipped, fvb)
        self.assertEqual(machine.code(site, 5).hex().upper() != stock, fvb)

    def test_every_combination(self) -> None:
        combos = {4: ((), ("vv4_optional_text_changes",), ("vv4_translations",),
                      ("vv4_optional_text_changes", "vv4_translations")),
                  5: ((), ("vv5_guardians_of_isola_rewrite",), ("vv5_translations",),
                      ("vv5_guardians_of_isola_rewrite", "vv5_translations"))}
        for game, extras in combos.items():
            for extra in extras:
                with self.subTest(game=game, extra=extra):
                    self.check(game, extra)
                if extra:
                    with self.subTest(game=game, extra=extra, uninstalled=True):
                        self.check(game, extra, fvb=False)


if __name__ == "__main__":
    unittest.main()
