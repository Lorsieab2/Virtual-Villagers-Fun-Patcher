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
    # The owner, 2026-11-19: "there should be a text fix for the vv4 ending" (some words are omitted).
    (4, "sm/eEndGamePage3Line2"): [("thrive, they", "thrive here, they"),
                                   ("the mysterious tree", "the ancient, mysterious tree")],
    (5, "sm/eEventMysteriousStorytellerResultB"): [("island.Others", "island. Others"),
                                                   ("nature.They", "nature. They")],
    (5, "sm/eEventTheSealedBoxResultB"): [("for his honest", "for {his/her} honest")],
}


# The Tree of Life's cutting-tool harvest caption: the harvest's copy and picking's (start, the address after the copy).
CAPTION = DATA["captions"][0]
CAPTION_SITE = 0x451CF6
# The villager panel's Action line (the field's only reader): `add edx, 0x1CE4 / push edx` before the set-text.
SHOWN_SITE = 0x4404F3
SHOWN_STOCK = "81C2E41C000052"
SHOWN_RUN = (0x4404E9, 0x4404FA)               # mov edx, [esp+0x10] ... push edx; then the call 0x40D3E0
FIELD, FIELD_BYTES = 0x1CE4, 0x27
HARVEST_COPY = (0x451CF2, 0x451D05)
PICK_COPY = (0x451C42, 0x451C55)
# New Believers' lab equipment line: the ground click's format push and the Collections screen's two pushes.
LAB = DATA["formats"][0]
LAB_SITE = 0x443BB0
COLLECTIONS_PUSHES = (0x43EBB2, 0x43EBF1)


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

    def test_the_caption_is_the_companions_and_the_templates(self) -> None:
        self.assertEqual(len(DATA["captions"]), 1)
        self.assertEqual((CAPTION["game"], int(CAPTION["site"], 16)), (4, CAPTION_SITE))
        # the owner's whole caption is shown; only the mark the field holds is shorter, and it fits the field
        self.assertEqual(CAPTION["new"], "Harvesting blackberries with a cutting tool")
        self.assertEqual(CAPTION["mark"], "Harvesting berries with a cutting tool")
        self.assertLess(len(CAPTION["mark"]), FIELD_BYTES)
        self.assertEqual(int(CAPTION["shown_site"], 16), SHOWN_SITE)
        source = (ROOT / "native" / "vvfp_text_fixes" / "vvfp_text_fixes.c").read_text(encoding="utf-8")
        self.assertIn(f'caption_english[] = "{CAPTION["new"]}"', source)
        self.assertIn(f'CAPTION_MARK[] = "{CAPTION["mark"]}"', source)
        self.assertIn(f'#define CAPTION_OLD "{CAPTION["old"]}"', source)
        self.assertIn(f'vvfp_tr("{CAPTION["key"]}", caption_english, 0u)', source)   # drawn from a pointer
        rows = [s for s in tr.load_patcher_strings() if s["stem"] == CAPTION["key"]]
        self.assertEqual([(r["english"], r["games"]) for r in rows], [(CAPTION["new"], ["vv4"])])
        if HAVE_STOCK:
            english = tr.game_english(4, STOCK[4], STOCK_SM[4])
            self.assertEqual(english[CAPTION["stock_stem"]], CAPTION["old"])

    def test_the_lab_format_is_the_companions(self) -> None:
        self.assertEqual(len(DATA["formats"]), 1)
        self.assertEqual((LAB["game"], int(LAB["site"], 16), LAB["old"], LAB["new"]),
                         (5, LAB_SITE, "%d%s12 %s", "%d%s24 %s"))
        source = (ROOT / "native" / "vvfp_text_fixes" / "vvfp_text_fixes.c").read_text(encoding="utf-8")
        self.assertIn(f'#define LAB_OLD "{LAB["old"]}"', source)
        self.assertIn(f'LAB_NEW[] = "{LAB["new"]}"', source)
        if HAVE_STOCK:
            image = tr.ExeImage(STOCK[5].read_bytes())
            self.assertEqual(image.cstring(int(LAB["literal"], 16)), LAB["old"].encode())
            english = tr.game_english(5, STOCK[5], STOCK_SM[5])
            for stem in LAB["words"]:
                self.assertIn(stem, english)                     # the words are the game's own rows

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
                expected = [SITES[game][:2]] if game in SITES else []
                if game == 4:
                    expected.append((CAPTION_SITE, "6A27508D86E41C0000"))
                    expected.append((SHOWN_SITE, SHOWN_STOCK))
                if game == 5:
                    expected.append((LAB_SITE, "6850A34900"))
                self.assertEqual(detours, expected)
                self.assertIn(DLL_NAME, r["description"])
                if game in (4, 5):
                    self.assertIn("to collected food", r["description"])

    @unittest.skipUnless(HAVE_EMULATOR and HAVE_STOCK, "needs pefile and the stock executables")
    def test_no_other_row_writes_the_sites(self) -> None:
        sites = [(game, site, stock) for game, (site, stock, *_rest) in SITES.items()]
        sites += [(4, CAPTION_SITE, "6A27508D86E41C0000"), (4, SHOWN_SITE, SHOWN_STOCK)]
        for game, site, stock in sites:
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

    # -- The Tree of Life: the cutting-tool harvest's caption -----------------------------------------------------
    def caption_after(self, p, start: int, end: int, looked_up: bytes) -> bytes:
        """Runs an action's caption copy (from `mov esi, [esp+8]` to after `call 0x4724E0`) with eax = the looked-up
        text; returns the villager's caption (+0x1CE4)."""
        villager = p.alloc(0x2000)
        text = p.alloc(len(looked_up) + 1)
        p.write(text, looked_up + b"\0")
        p.call(start, [0, villager], regs={"eax": text}, until=end)
        return self.cstring(p, villager + 0x1CE4)

    def action_line(self, p, villager: int) -> tuple[bytes, int, int]:
        """Runs the villager panel's own Action line code (0x4404E9 up to its `call 0x40D3E0`) for `villager`;
        returns the text the label is handed, its address and the label (ecx)."""
        panel = p.alloc(0x200)
        p.put32(panel + 0xE4, 0x13572468)                         # the Action label
        esp = p.alloc(0x400) + 0x200
        p.put32(esp + 0x10, villager)
        p.set_reg("esp", esp)
        p.set_reg("ebp", panel)
        p.run(*SHOWN_RUN)
        text_va = p.u32(p.reg("esp"))
        return self.cstring(p, text_va), text_va, p.reg("ecx")

    def harvest_then_shown(self, p, start: int, end: int, looked_up: bytes) -> tuple[bytes, bytes, bytes]:
        """An action's caption copy into a villager whose bytes are all 0xCC, then the Action line: returns the
        field, the bytes past the field's 0x27, and the text the Action line shows."""
        villager = p.alloc(0x2000)
        p.write(villager, b"\xCC" * 0x2000)
        text = p.alloc(len(looked_up) + 1)
        p.write(text, looked_up + b"\0")
        p.call(start, [0, villager], regs={"eax": text}, until=end)
        field = self.cstring(p, villager + FIELD)
        past = p.read(villager + FIELD + FIELD_BYTES, 0x2000 - FIELD - FIELD_BYTES)
        return field, past, self.action_line(p, villager)[0]

    def test_the_cutting_tool_harvest_says_so_and_picking_does_not(self) -> None:
        old, new, mark = CAPTION["old"].encode(), CAPTION["new"].encode(), CAPTION["mark"].encode()
        self.assertGreater(len(new), FIELD_BYTES)                # the owner's caption does not fit the field...
        self.assertLess(len(mark), FIELD_BYTES)                  # ...the mark does, with its NUL
        untouched = b"\xCC" * (0x2000 - FIELD - FIELD_BYTES)
        stock = self.process(4, install=False)
        self.assertEqual(self.caption_after(stock, *HARVEST_COPY, old), old)
        self.assertEqual(self.harvest_then_shown(stock, *HARVEST_COPY, old), (old, untouched, old))
        p = self.process(4)
        self.assertEqual(p.export("VvfpTextFixesCaptionInstalled"), 1)
        self.assertEqual(p.read(CAPTION_SITE, 9).hex().upper()[:2], "E9")
        self.assertEqual(p.read(SHOWN_SITE, 7).hex().upper(), "E9" + p.read(SHOWN_SITE + 1, 4).hex().upper() + "9090")
        # the harvest: the field holds the mark, nothing past it is written, the Action line shows the whole caption
        self.assertEqual(self.harvest_then_shown(p, *HARVEST_COPY, old), (mark, untouched, new))
        # picking keeps the game's caption, and its code is the game's own
        self.assertEqual(self.harvest_then_shown(p, *PICK_COPY, old), (old, untouched, old))
        self.assertEqual(p.read(PICK_COPY[0], 20), stock.read(PICK_COPY[0], 20))
        for other in (b"Recolte des mures", old + b" ", b""):              # another patch's text is kept
            with self.subTest(other=other):
                self.assertEqual(self.harvest_then_shown(p, *HARVEST_COPY, other), (other, untouched, other))

    def test_the_action_line_shows_the_whole_caption_only_for_the_mark(self) -> None:
        mark, new = CAPTION["mark"].encode(), CAPTION["new"].encode()
        for installed in (False, True):
            p = self.process(4, install=installed)
            for field in (mark, mark[:-1], mark + b"s", b"Harvesting blackberries", b"Sleeping", b""):
                with self.subTest(installed=installed, field=field):
                    villager = p.alloc(0x2000)
                    p.write(villager + FIELD, field + b"\0")
                    shown, at, label = self.action_line(p, villager)
                    self.assertEqual(label, 0x13572468)               # the label the game set up is kept
                    if installed and field == mark:
                        self.assertEqual(shown, new)
                    else:
                        self.assertEqual((shown, at), (field, villager + FIELD))   # the field itself, as stock
                    self.assertEqual(self.cstring(p, villager + FIELD), field)     # the field is only read

    # -- The Tree of Life: the Action line drawn whole (R6 live, 2026-11-21) -----------------------------------------
    def action_label(self, p, text: bytes, *, spacing: int = 0, x: int = 0x12E) -> tuple[int, int, int]:
        """A label as the game makes it (0x40D8A0: the label class's vtable, its text control at +0x10, shown), its
        control left-aligned at `x` with the label's text and a font whose letter spacing is `spacing`; returns
        (label, control, the spacing's address)."""
        label, ctl, font, impl, buf = p.alloc(0x40), p.alloc(0x60), p.alloc(0x10), p.alloc(0x40), p.alloc(256)
        p.put32(label, 0x48A96C)
        p.write(label + 8, b"\x01")
        p.put32(label + 0x10, ctl)
        p.write(buf, text + b"\0")
        p.put32(ctl + 8, x)
        p.put32(ctl + 0x30, buf)
        p.put32(ctl + 0x3C, font)
        p.put32(font + 4, impl)
        p.put32(impl + 8, spacing & 0xFFFFFFFF)
        return label, ctl, impl + 8

    def drawn_spacing(self, p, label: int, spacing_at: int, width: int) -> tuple[int, int]:
        """Calls the label's draw through its vtable (slot 6, as the panel's child loop 0x40C2A0 does) with the
        game's width routine answering `width`; returns (the spacing the stock draw saw, the spacing after)."""
        seen = []

        def width_routine(proc):
            return width, 8                                   # thiscall (font; text, scale): ret 8

        def stock_draw(proc):
            seen.append(struct.unpack("<i", proc.read(spacing_at, 4))[0])
            return 0, 0

        p.stubs[0x402430] = width_routine
        p.stubs[0x40D3A0] = stock_draw
        draw = p.u32(p.u32(label) + 4 * 6)
        p.call(draw, [], ecx=label)
        return seen[0], struct.unpack("<i", p.read(spacing_at, 4))[0]

    def test_the_action_label_draws_a_caption_too_wide_for_the_bar_a_pixel_closer(self) -> None:
        new = CAPTION["new"].encode()
        p = self.process(4)
        label, _ctl, spacing_at = self.action_label(p, new)
        villager = p.alloc(0x2000)
        p.write(villager + FIELD, CAPTION["mark"].encode() + b"\0")
        panel = p.alloc(0x200)
        p.put32(panel + 0xE4, label)
        esp = p.alloc(0x400) + 0x200
        p.put32(esp + 0x10, villager)
        p.set_reg("esp", esp)
        p.set_reg("ebp", panel)
        p.run(*SHOWN_RUN)
        self.assertEqual(p.reg("ecx"), label)
        self.assertNotEqual(p.u32(label), 0x48A96C)               # the Action label has its own vtable...
        vt = p.u32(label)
        stock_vt = [p.u32(0x48A968 + 4 * i) for i in range(9)]
        self.assertEqual([p.u32(vt - 4 + 4 * i) for i in range(9) if i != 7], stock_vt[:7] + stock_vt[8:])
        self.assertNotEqual(p.u32(vt + 4 * 6), 0x40D3A0)          # ...whose draw is the companion's
        # the owner's caption (368 pixels in Arial Bold) where the bar shows 646 - 302 = 344: a pixel closer, put back
        self.assertEqual(self.drawn_spacing(p, label, spacing_at, 368), (-1, 0))
        # a caption that fits is drawn as the game draws it
        self.assertEqual(self.drawn_spacing(p, label, spacing_at, 344), (0, 0))
        self.assertEqual(self.drawn_spacing(p, label, spacing_at, 200), (0, 0))
        # far too wide (a long translation): at most two pixels closer
        self.assertEqual(self.drawn_spacing(p, label, spacing_at, 344 + 42 * 5), (-2, 0))
        # another label of the panel keeps the label class's vtable
        other, _c, _s = self.action_label(p, b"Master Scientist")
        self.assertEqual(p.u32(other), 0x48A96C)

    def test_without_the_companion_the_action_label_is_the_games(self) -> None:
        p = self.process(4, install=False)
        label, _ctl, _s = self.action_label(p, CAPTION["new"].encode())
        villager = p.alloc(0x2000)
        p.write(villager + FIELD, b"Sleeping\0")
        panel = p.alloc(0x200)
        p.put32(panel + 0xE4, label)
        esp = p.alloc(0x400) + 0x200
        p.put32(esp + 0x10, villager)
        p.set_reg("esp", esp)
        p.set_reg("ebp", panel)
        p.run(*SHOWN_RUN)
        self.assertEqual(p.u32(label), 0x48A96C)

    # -- New Believers: the lab equipment line ------------------------------------------------------------------
    def lab_line(self, p, count: int) -> bytes:
        """Runs the ground click's own format step (0x443BAB: push the count / the buffer / the pushed format /
        the game's sprintf 0x47C046) with the two words on the stack; returns the line it writes."""
        of, words = p.alloc(16), p.alloc(64)
        p.write(of, b" of \0")
        p.write(words, b"pieces of lab equipment collected\0")
        esp = p.alloc(0x400) + 0x200
        p.put32(esp, of)
        p.put32(esp + 4, words)
        p.set_reg("esp", esp)
        p.set_reg("eax", count)

        def sprintf(proc):
            # the C runtime's sprintf needs its thread data, which the emulation has not set up: the same
            # formatting of the format the game pushed, with its %d / %s arguments (cdecl: the caller pops)
            sp = proc.reg("esp")
            out, fmt_va, n, s1, s2 = (proc.u32(sp + 4 * k) for k in range(1, 6))
            text = self.cstring(proc, fmt_va).decode().replace("%d", str(n), 1)
            text = text.replace("%s", self.cstring(proc, s1).decode(), 1)
            text = text.replace("%s", self.cstring(proc, s2).decode(), 1)
            proc.write(out, text.encode() + b"\0")
            return len(text), 0

        p.stubs[0x47C046] = sprintf
        p.run(0x443BAB, 0x443BBB)
        return self.cstring(p, esp + 0x14)

    def test_the_lab_line_counts_out_of_24(self) -> None:
        stock = self.process(5, install=False)
        self.assertEqual(self.lab_line(stock, 13), b"13 of 12 pieces of lab equipment collected")
        p = self.process(5)
        self.assertEqual(p.export("VvfpTextFixesLabInstalled"), 1)
        for n in (0, 13, 24):
            self.assertEqual(self.lab_line(p, n), f"{n} of 24 pieces of lab equipment collected".encode())
        # the Collections screen's own counts and the format in the game's data are unchanged
        for at in COLLECTIONS_PUSHES:
            self.assertEqual(p.read(at, 5), stock.read(at, 5))
        self.assertEqual(self.cstring(p, int(LAB["literal"], 16)), LAB["old"].encode())
        for game in (3, 4):
            self.assertEqual(self.process(game).export("VvfpTextFixesLabInstalled"), 0)

    def test_the_lab_line_installs_only_with_its_stock_bytes(self) -> None:
        for at in (LAB_SITE - 5, LAB_SITE, LAB_SITE + 4, LAB_SITE + 6, 0x49A350 + 4):
            with self.subTest(at=hex(at)):
                data = bytearray(STOCK[5].read_bytes())
                pe = pefile.PE(data=bytes(data), fast_load=True)
                data[pe.get_offset_from_rva(at - 0x400000)] ^= 0x01
                p = self.process(5, bytes(data))
                self.assertEqual(p.export("VvfpTextFixesInstalled"), 0)       # all or none
                self.assertEqual(p.export("VvfpTextFixesLabInstalled"), 0)
                self.assertEqual(p.read(SITES[5][0], 5).hex().upper(), SITES[5][1])

    def test_the_caption_installs_only_with_its_stock_bytes(self) -> None:
        for game in (3, 5):
            p = self.process(game)
            self.assertEqual(p.export("VvfpTextFixesCaptionInstalled"), 0)
        for at in (0x451CE6, 0x451CEA, CAPTION_SITE, CAPTION_SITE + 8, 0x451CFF, 0x451D03,
                   SHOWN_SITE - 10, SHOWN_SITE - 1, SHOWN_SITE, SHOWN_SITE + 6, SHOWN_SITE + 7, SHOWN_SITE + 11,
                   0x48A968, 0x48A984, 0x48A98B):                   # the label class's vtable (the Action label's)
            with self.subTest(at=hex(at)):
                data = bytearray(STOCK[4].read_bytes())
                pe = pefile.PE(data=bytes(data), fast_load=True)
                data[pe.get_offset_from_rva(at - 0x400000)] ^= 0xFF
                p = self.process(4, bytes(data))
                # all or none: neither the caption nor the loader's site
                self.assertEqual(p.export("VvfpTextFixesInstalled"), 0)
                self.assertEqual(p.export("VvfpTextFixesCaptionInstalled"), 0)
                self.assertEqual(p.read(SITES[4][0], 5).hex().upper(), SITES[4][1])
                if not CAPTION_SITE <= at < CAPTION_SITE + 9:
                    self.assertEqual(p.read(CAPTION_SITE, 9).hex().upper(), "6A27508D86E41C0000")
                if not SHOWN_SITE <= at < SHOWN_SITE + 7:
                    self.assertEqual(p.read(SHOWN_SITE, 7).hex().upper(), SHOWN_STOCK)


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
