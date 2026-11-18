"""Fix Vanilla Bugs: the games' own text fixes ("VVFP Text Fixes.dll", all five games).

The owner approved some typo fixes in the games' text (2026-11-17, data/vanilla_text_fixes.json: only text shown in
normal play) and The Tree of Life's and New Believers' Food Mastery line (2026-11-16: "At Level 2 your tribe gets a 50
percent bonus." reads "... a 50 percent bonus to collected food.").
- A New Home, The Lost Children: at start the string table's first row of each fixed id points at the fixed text when
  it points at exactly the stock text.
- The Secret City: the string table loader's epilogue (0x42F6A5, `add esp, 0xC8`) jumps to the companion's step;
  The Tree of Life, New Believers: the loader's cookie-check call (0x44D92E / 0x450C3E) calls it.  The step fixes the
  filled table (a typo fix only when the text is exactly the stock one; the Food Mastery line wherever the whole line
  stands), then makes the instruction it replaced.
Shown here:
- the data: each stock text is the stock game's (the executable's table, the stock sm.xml), each fix changes only
  the approved words, the companion's table (tf_fixes.inc) is generated from the data;
- emulation of the shipped DLL on the stock executables: each text is fixed, a text that is not the stock one
  (another patch's, a translation's) is left alone, a changed byte round a site installs nothing, eax / the cookie
  check are kept;
- the published builds started to WinMain (tests/startup_emulation.py): with Fix Vanilla Bugs (alone, with the text
  patches, with Translations) the texts are fixed / the site is written; without it (uninstalled) nothing is shipped
  and everything is stock;
- the translation template (src/vv_translations.py) gives the fixed English when the game has the companion;
- each fixed text on one line still fits on screen in VV3-VV5's own popup box.
The live game is NOT verified here.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import struct
import subprocess
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
    from story_emulator import RETURN, Process
    HAVE_EMULATOR = True
except ImportError:  # pragma: no cover
    HAVE_EMULATOR = False

NAMES = {1: "A New Home", 2: "The Lost Children", 3: "The Secret City", 4: "The Tree of Life", 5: "New Believers"}
STOCK = {g: ROOT / "research" / "stock-executables" / f"Virtual Villagers - {n}.exe" for g, n in NAMES.items()}
HAVE_STOCK = all(p.is_file() for p in STOCK.values())
DLL_NAME = "VVFP Text Fixes.dll"
DLL = ROOT / "assets" / "text_fixes" / DLL_NAME
GAMES = (1, 2, 3, 4, 5)
DATA = json.loads((ROOT / "data" / "vanilla_text_fixes.json").read_text(encoding="utf-8"))
# VV1/VV2 string tables: (rows, count, stride)
TABLES = {1: (0x487208, 0x275, 0x14), 2: (0x496300, 0x36C, 12)}
# VV3-VV5: (site, stock bytes, the string table, its entries, the cookie global or None)
SITES = {3: (0x42F6A5, "81C4C8000000", 0x4AB990, 0x4BA, None),
         4: (0x44D92E, "E85A370200", 0x4C41F8, 1338, 0x4C9FBC),
         5: (0x450C3E, "E8CAB30200", 0x4D31F0, 1409, 0x4D97A8)}
FM_NAME = b"eTechFoodMasteryInfo"
FM_OLD = b"At Level 2 your tribe gets a 50 percent bonus."
FM_NEW = b"At Level 2 your tribe gets a 50 percent bonus to collected food."
STOCK_SM = {4: ROOT / "assets" / "text-changes" / "vv4-sm-base.xml",
            5: ROOT / "data" / "guardians_of_isola" / "base" / "Assets" / "sm.xml"}
SM_FILES = {
    4: {"stock": STOCK_SM[4], "Optional Text Changes": ROOT / "assets" / "text-changes" / "vv4-sm.xml"},
    5: {"Guardians of Isola (base)": STOCK_SM[5],
        "Guardians of Isola": ROOT / "data" / "guardians_of_isola" / "new" / "Assets" / "sm.xml"},
}
# The approved edits (the owner, 2026-11-17): each fix is exactly these replacements of the stock text.
EDITS = {
    (1, "table/383"): [("which he\nhe rubs", "which he\nrubs")],
    (2, "table/501"): [("a new a fashion", "a new fashion")],
    (2, "table/516"): [("its too late", "it's too late")],
    (3, "sm/eEventDaredevilResultA2"): [("bravery.However", "bravery. However")],
    (3, "sm/eEventTheLowTideResultA2"): [("Neverthe- less", "Nevertheless")],
    (3, "sm/eEventTheObsidianPhialResultA3"): [("unusal", "unusual")],
    (3, "sm/eSaySeesMountain"): [("mountaineous", "mountainous")],
    (4, "sm/eEventThePrettyShellDesc"): [("shell.{name}", "shell. {name}")],
    (5, "sm/eEventMysteriousStorytellerResultB"): [("island.Others", "island. Others"),
                                                   ("nature.They", "nature. They")],
    (5, "sm/eEventTheSealedBoxResultB"): [("for his honest", "for {his/her} honest")],
}


def fixes(game: int) -> list[dict]:
    return [f for f in DATA["fixes"] if f["game"] == game]


def row(game: int) -> dict:
    return next(p.raw for p in patcher.load_fun_patches() if p.id == f"vv{game}_fix_vanilla_bugs")


def sm_text(path: Path, name: str) -> bytes | None:
    return tr._sm_lookup(tr._sm_file_texts(path.read_bytes()), name)


class TheData(unittest.TestCase):
    def test_only_the_approved_edits(self) -> None:
        self.assertEqual({(f["game"], f["stem"]) for f in DATA["fixes"]}, set(EDITS))
        for f in DATA["fixes"]:
            with self.subTest(stem=f["stem"]):
                text = f["old"]
                for old, new in EDITS[(f["game"], f["stem"])]:
                    self.assertEqual(text.count(old), 1)
                    text = text.replace(old, new)
                self.assertEqual(text, f["new"])
                self.assertTrue(f["shown"] and f["reason"])
                f["new"].encode("cp1252")

    @unittest.skipUnless(HAVE_STOCK, "needs the stock executables")
    def test_each_old_text_is_the_stock_games(self) -> None:
        for game in GAMES:
            english = tr.game_english(game, STOCK[game], STOCK_SM.get(game))
            built_in = tr.game_english(game, STOCK[game])
            for f in fixes(game):
                with self.subTest(game=game, stem=f["stem"]):
                    self.assertEqual(english[f["stem"]], f["old"])
                    self.assertEqual(built_in[f["stem"]], f["old"])     # the executable's own text too

    def test_the_companions_table_is_generated_from_the_data(self) -> None:
        done = subprocess.run([sys.executable, str(ROOT / "scripts" / "build_text_fixes_table.py"), "--check"],
                              cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)


class TheRows(unittest.TestCase):
    def test_every_fix_vanilla_bugs_row_ships_and_pins_the_companion(self) -> None:
        digest = hashlib.sha256(DLL.read_bytes()).hexdigest().upper()
        self.assertIn(DLL_NAME, patcher.STARTUP_LOADER_COMPANIONS_2)
        self.assertNotIn("VVFP Food Mastery Text.dll", patcher.STARTUP_LOADER_COMPANIONS_2)
        for game in GAMES:
            with self.subTest(game=game):
                r = row(game)
                files = {f["destination"]: f["sha256"] for f in r["companion_files"]}
                self.assertEqual(files.get(DLL_NAME), digest)
                detours = [(int(d["va"], 16), d["stock_bytes"]) for d in r.get("runtime_detours", [])
                           if DLL_NAME in d["installed_by"]]
                self.assertEqual(detours, [SITES[game][:2]] if game in SITES else [])
                self.assertIn(DLL_NAME, r["description"])
                if game in (4, 5):
                    self.assertIn("to collected food", r["description"])

    @unittest.skipUnless(HAVE_EMULATOR and HAVE_STOCK, "needs pefile and the stock executables")
    def test_no_other_row_writes_the_sites(self) -> None:
        for game, (site, stock, *_rest) in SITES.items():
            n = len(bytes.fromhex(stock))
            for p in patcher._load_fun_patch_records():
                if p.raw.get("game_id") != f"vv{game}":
                    continue
                for d in p.raw.get("runtime_detours", []) or []:
                    if DLL_NAME in d.get("installed_by", ""):
                        continue
                    va, m = int(str(d["va"]), 0), len(bytes.fromhex(d["stock_bytes"]))
                    self.assertFalse(va < site + n and site < va + m, (p.id, hex(va)))
                for edit in p.raw.get("patches", []) or []:
                    if "offset" in edit:
                        va = int(str(edit["offset"]), 0) + 0x400000
                        m = int(edit["length"]) if "length" in edit else len(bytes.fromhex(edit.get("before", "")))
                        self.assertFalse(va < site + n and site < va + m, (p.id, hex(va)))

    def test_every_text_patch_keeps_the_food_mastery_line(self) -> None:
        for game, files in SM_FILES.items():
            for label, path in files.items():
                with self.subTest(game=game, sm=label):
                    text = sm_text(path, FM_NAME.decode())
                    self.assertIn(FM_OLD + b"\n", text)
                    self.assertNotIn(FM_NEW, text)


@unittest.skipUnless(HAVE_EMULATOR and HAVE_STOCK and DLL.is_file(), "needs unicorn, the stock executables, the DLL")
class TheCompanion(unittest.TestCase):
    def process(self, game: int, data: bytes | None = None, install: bool = True):
        p = Process(data if data is not None else STOCK[game].read_bytes(), DLL)
        if install:
            p.export("VvfpStartup", game, 0)
        return p

    @staticmethod
    def cstring(p, va: int) -> bytes:
        raw = p.read(va, 8192)
        return raw[:raw.index(b"\0")]

    # -- A New Home, The Lost Children: the table rows ---------------------------------------------------------
    def first_row(self, p, game: int, ident: int) -> int:
        table, count, stride = TABLES[game]
        for i in range(count):
            if p.u32(table + i * stride) == ident:
                return table + i * stride
        raise AssertionError(f"no row {ident}")

    def test_the_table_rows_are_fixed_at_start(self) -> None:
        for game in (1, 2):
            p = self.process(game, install=False)
            table, count, stride = TABLES[game]
            before = [p.u32(table + i * stride + 4) for i in range(count)]
            p.export("VvfpStartup", game, 0)
            self.assertEqual(p.export("VvfpTextFixesInstalled"), 1)
            self.assertEqual(p.export("VvfpTextFixesApplied"), len(fixes(game)))
            changed = set()
            for f in fixes(game):
                with self.subTest(game=game, stem=f["stem"]):
                    at = self.first_row(p, game, int(f["stem"].split("/")[1]))
                    self.assertEqual(self.cstring(p, p.u32(at + 4)), f["new"].encode("cp1252"))
                    changed.add((at - table) // stride)
            after = [p.u32(table + i * stride + 4) for i in range(count)]
            self.assertEqual([i for i in range(count) if before[i] != after[i]], sorted(changed))
            p.export("VvfpStartup", game, 0)                  # a second start changes nothing
            self.assertEqual([p.u32(table + i * stride + 4) for i in range(count)], after)

    def test_a_row_with_another_text_is_left_alone(self) -> None:
        for game in (1, 2):
            for f in fixes(game):
                old = f["old"].encode("cp1252")
                for other in (old + b" ", old[:-1], f["new"].encode("cp1252"), b""):
                    with self.subTest(game=game, stem=f["stem"], other=other[-12:]):
                        p = self.process(game, install=False)
                        at = self.first_row(p, game, int(f["stem"].split("/")[1]))
                        va = p.alloc(len(other) + 1)
                        p.write(va, other + b"\0")
                        p.put32(at + 4, va)
                        p.export("VvfpStartup", game, 0)
                        self.assertEqual(p.u32(at + 4), va)
                        self.assertEqual(p.export("VvfpTextFixesApplied"), len(fixes(game)) - 1)

    # -- The Secret City .. New Believers: the loader's step ---------------------------------------------------
    def entry(self, p, game: int, name: bytes) -> int:
        _site, _stock, table, count, _cookie = SITES[game]
        for i in range(count):
            at = table + 16 * i
            if p.read(p.u32(at + 4), len(name) + 1) == name + b"\0":
                return at
        raise AssertionError(f"no {name!r} entry")

    def loader_end(self, p, game: int) -> None:
        """The loader's last step, made through the site."""
        site, _stock, _table, _count, cookie = SITES[game]
        if game == 3:
            # `add esp, 0xC8; ret` with the loader's 0xC8 bytes of locals below the return; eax (the table) kept
            p.call(site, [0] * 49 + [RETURN], regs={"eax": 0x12345678})
            self.assertEqual(p.reg("eax"), 0x12345678)
        else:
            # the cookie check's own call: ecx = the value it compares with its global
            target = (site + 5 + struct.unpack("<i", p.read(site + 1, 4))[0]) & 0xFFFFFFFF
            p.call(target, [], ecx=p.u32(cookie))

    def text_after(self, game: int, name: bytes, text: bytes | None, p=None):
        p = p or self.process(game)
        at = self.entry(p, game, name)
        if text is not None:
            va = p.alloc(len(text) + 1)
            p.write(va, text + b"\0")
            p.put32(at + 12, va)
        self.loader_end(p, game)
        out = p.u32(at + 12)
        return p, self.cstring(p, out if out else p.u32(at + 8))

    def test_installed_on_its_own_game_only(self) -> None:
        for game in (3, 4, 5):
            n = len(bytes.fromhex(SITES[game][1]))
            p = self.process(game)
            self.assertEqual(p.export("VvfpTextFixesInstalled"), 1)
            self.assertNotEqual(p.read(SITES[game][0], n).hex().upper(), SITES[game][1])
        for game, other in ((3, 4), (4, 5), (5, 3)):
            n = len(bytes.fromhex(SITES[game][1]))
            p = self.process(game, install=False)
            p.export("VvfpStartup", other, 0)        # the wrong game's number: its bytes are not there
            self.assertEqual(p.export("VvfpTextFixesInstalled"), 0)
            self.assertEqual(p.read(SITES[game][0], n).hex().upper(), SITES[game][1])

    def test_the_stock_epilogue_still_returns(self) -> None:
        p = self.process(3, install=False)
        p.call(SITES[3][0], [0] * 49 + [RETURN], regs={"eax": 0x12345678})
        self.assertEqual(p.reg("eax"), 0x12345678)

    def test_each_stock_text_is_fixed(self) -> None:
        for game in (3, 4, 5):
            for f in fixes(game):
                name = f["stem"].split("/", 1)[1].encode()
                for loaded in (f["old"].encode("cp1252"), None):
                    with self.subTest(game=game, stem=f["stem"], loaded=loaded is not None):
                        # the loaded text (the stock sm.xml's) and, with none loaded, the built-in one
                        p = self.process(game)
                        if loaded is None:
                            p.put32(self.entry(p, game, name) + 12, 0)
                        p, out = self.text_after(game, name, loaded, p)
                        self.assertEqual(out, f["new"].encode("cp1252"))
                        self.loader_end(p, game)                  # a second run changes nothing more
                        self.assertEqual(self.cstring(p, p.u32(self.entry(p, game, name) + 12)), out)

    def test_all_of_a_games_fixes_in_one_run(self) -> None:
        for game in (3, 4, 5):
            with self.subTest(game=game):
                p = self.process(game)
                self.loader_end(p, game)
                self.assertGreaterEqual(p.export("VvfpTextFixesApplied"), len(fixes(game)))
                for f in fixes(game):
                    at = self.entry(p, game, f["stem"].split("/", 1)[1].encode())
                    self.assertEqual(self.cstring(p, p.u32(at + 12)), f["new"].encode("cp1252"))

    def test_another_wording_is_left_alone(self) -> None:
        for game in (3, 4, 5):
            for f in fixes(game):
                name = f["stem"].split("/", 1)[1].encode()
                old = f["old"].encode("cp1252")
                for text in (old + b" ", old[:-1], b"x" + old, f["new"].encode("cp1252"), b""):
                    with self.subTest(game=game, stem=f["stem"], text=text[:20]):
                        p = self.process(game)
                        at = self.entry(p, game, name)
                        va = p.alloc(len(text) + 1)
                        p.write(va, text + b"\0")
                        p.put32(at + 12, va)
                        self.loader_end(p, game)
                        self.assertEqual(p.u32(at + 12), va)

    def test_every_sm_xml_gets_the_food_mastery_line_only(self) -> None:
        for game, files in SM_FILES.items():
            for label, path in files.items():
                with self.subTest(game=game, sm=label):
                    text = sm_text(path, FM_NAME.decode())
                    _p, out = self.text_after(game, FM_NAME, text)
                    self.assertEqual(out, text.replace(FM_OLD, FM_NEW, 1))

    def test_another_food_mastery_wording_is_left_alone(self) -> None:
        for game in (4, 5):
            for text in (b"Food Mastery\n\nAt Level 2 your tribe gets a 50 percent bonus to collected food.\n",
                         b"At Level 2 your tribe gets a 50 percent bonus.5\n", b"Something else entirely", b""):
                with self.subTest(game=game, text=text):
                    p = self.process(game)
                    at = self.entry(p, game, FM_NAME)
                    va = p.alloc(len(text) + 1)
                    p.write(va, text + b"\0")
                    p.put32(at + 12, va)
                    self.loader_end(p, game)
                    self.assertEqual(p.u32(at + 12), va)

    def test_a_changed_byte_round_the_site_installs_nothing(self) -> None:
        for game in (3, 4, 5):
            site, stock = SITES[game][0], SITES[game][1]
            n = len(bytes.fromhex(stock))
            before = 4 if game == 3 else 3
            for at in sorted({site - before, site - 1, site, site + n - 1, site + n, site + n + 1}):
                with self.subTest(game=game, at=hex(at)):
                    data = bytearray(STOCK[game].read_bytes())
                    pe = pefile.PE(data=bytes(data), fast_load=True)
                    data[pe.get_offset_from_rva(at - 0x400000)] ^= 0xFF
                    p = self.process(game, bytes(data))
                    self.assertEqual(p.export("VvfpTextFixesInstalled"), 0)
                    if not site <= at < site + n:
                        self.assertEqual(p.read(site, n).hex().upper(), stock)


class TheTemplate(unittest.TestCase):
    """The translation template follows the companion: the fixed English (and its key's hash) only when the game
    has it."""

    def folder(self, game: int, *, dll: bool, log: list[str] | None, other_hash: bool = False) -> Path:
        base = Path(tempfile.mkdtemp(prefix="vvtf"))
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
                    english = tr.game_english(game, exe, STOCK_SM.get(game))
                    for f in fixes(game):
                        self.assertEqual(english[f["stem"]], f["new"] if fixed else f["old"])
                    if game in (4, 5):
                        self.assertEqual(tr.FOOD_MASTERY_NEW in english[tr.FOOD_MASTERY_STEM], fixed)

    @unittest.skipUnless(HAVE_STOCK, "needs the stock executables")
    def test_another_wording_keeps_its_english(self) -> None:
        exe = self.folder(4, dll=True, log=None)
        changed = Path(tempfile.mkdtemp(prefix="vvtf")) / "sm.xml"
        self.addCleanup(shutil.rmtree, changed.parent, True)
        changed.write_bytes(STOCK_SM[4].read_bytes().replace(b"round shell.{name}", b"round shell.{name} x"))
        english = tr.game_english(4, exe, changed)
        self.assertIn("round shell.{name} x", english["sm/eEventThePrettyShellDesc"])

    def test_the_rule_is_the_companions(self) -> None:
        old, new = tr.FOOD_MASTERY_OLD, tr.FOOD_MASTERY_NEW
        self.assertEqual(old.encode(), FM_OLD)
        self.assertEqual(new.encode(), FM_NEW)
        self.assertEqual(tr.food_mastery_fixed(f"a\n{old}\nb"), f"a\n{new}\nb")
        self.assertEqual(tr.food_mastery_fixed(old), new)
        self.assertEqual(tr.food_mastery_fixed(old + "x"), old + "x")
        self.assertEqual(tr.food_mastery_fixed(new), new)
        source = (ROOT / "native" / "vvfp_text_fixes" / "vvfp_text_fixes.c").read_text(encoding="utf-8")
        self.assertIn(f'#define FM_OLD "{old}"', source)
        self.assertIn(f'#define FM_NEW "{new}"', source)
        self.assertEqual(tr.TEXT_FIXES_DLL, DLL_NAME)


IMAGES = ROOT / "research" / "game-images"
HAVE_IMAGES = all((IMAGES / f"Virtual Villagers - {NAMES[g]}" / "Images").is_dir() for g in (3, 4, 5))


@unittest.skipUnless(HAVE_EMULATOR and HAVE_STOCK and HAVE_IMAGES, "needs unicorn, the stock executables and images")
class TheBoxFits(unittest.TestCase):
    """The message box sizes itself to its widest line (the game's own constructor and sizer,
    tests/scrolling_popups_emulation.py): each fixed text, on one line, stays on screen."""

    def test_no_hand_broken_line_grows_more_than_a_letter(self) -> None:
        """Every popup scrolls (the owner, 2026-11-16): only a single hand-broken line's width matters.  The game
        word-wraps the event paragraphs of VV3-VV5 itself; VV1/VV2's lines are broken by hand."""
        for f in DATA["fixes"]:
            if f["game"] > 2:
                continue                       # the game wraps these paragraphs itself
            with self.subTest(stem=f["stem"]):
                old_lines, new_lines = f["old"].split("\n"), f["new"].split("\n")
                self.assertLessEqual(max(map(len, new_lines)), max(map(len, old_lines)) + 1)

    def test_one_line_fits_on_screen(self) -> None:
        import scrolling_popups_emulation as spe
        for game in (4, 5):
            d = spe.Dialog(f"vv{game}")
            w, _h = d.g["screen"]
            texts = [sm_text(p, FM_NAME.decode()).replace(FM_OLD, FM_NEW, 1) for p in SM_FILES[game].values()]
            for text in texts:
                with self.subTest(game=game, text=text[:30]):
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
        self.assertEqual(DLL_NAME in shipped, fvb)
        if fvb:
            # With Translations shipped, VVFP Translations.dll starts this companion first (before VVFP Startup.dll
            # reaches the Fix Vanilla Bugs companion earlier in its list than this one); without it, list order.
            loads = [c[1].split("\\")[-1] for c in machine.calls
                     if c and str(c[0]).startswith("LoadLibrary") and len(c) > 2 and c[2]]
            earlier = "VVFP Keep Carried.dll" if game == 1 else "VVFP Long Words.dll"
            self.assertIn(earlier, loads)
            translated = any(e.endswith("_translations") for e in extra)
            self.assertEqual(loads.index(DLL_NAME) < loads.index(earlier), translated, loads)
        if game in SITES:
            site, stock = SITES[game][0], SITES[game][1]
            n = len(bytes.fromhex(stock))
            self.assertEqual(machine.code(site, n).hex().upper() != stock, fvb)
            return
        table, count, stride = TABLES[game]
        for f in fixes(game):
            ident = int(f["stem"].split("/")[1])
            at = next(table + i * stride for i in range(count)
                      if struct.unpack("<I", machine.code(table + i * stride, 4))[0] == ident)
            ptr = struct.unpack("<I", machine.code(at + 4, 4))[0]
            raw = machine.code(ptr, 4096)
            self.assertEqual(raw[:raw.index(b"\0")], (f["new"] if fvb else f["old"]).encode("cp1252"))

    def test_every_combination(self) -> None:
        combos = {1: ((), ("vv1_translations",)), 2: ((), ("vv2_translations",)), 3: ((), ("vv3_translations",)),
                  4: ((), ("vv4_optional_text_changes",), ("vv4_translations",),
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
