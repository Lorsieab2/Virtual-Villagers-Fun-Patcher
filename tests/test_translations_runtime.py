"""VVFP Translations.dll, proved against the stock executables in unicorn (tests/translations_emulation.py).

Each test builds a Translation.txt in an emulated game folder and calls the DLL's real exports and the game's
own string routines, so the parser, the row checks, the selects, the detours and the installs are the DLL's
own code end to end.  The DLL's results are also compared with the Python reference (src/vv_translation_format
.py): a row the DLL uses is one the reference reports with no error, a row it skips is one the reference would
fall back on.

Skips (never errors) when the stock executables or unicorn are not present: CI has unicorn but not the exes.
"""
from __future__ import annotations

import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import vv_translation_format as F  # noqa: E402

try:
    import pefile
    import unicorn  # noqa: F401
    from translations_emulation import DLL, Game, TITLES, stock_exe
    # Every input, or the whole file skips: CI has unicorn and the DLL but no stock executable (stock_exe
    # answers None there), and a test that reached one would error instead of skipping.
    HAVE = DLL.is_file() and all(stock_exe(n) is not None and stock_exe(n).is_file() for n in range(1, 6))
except ImportError:
    HAVE = False
    TITLES = {}


class Image:
    """The stock executable mapped the way the loader maps it, read with no emulator -- so the setup
    helpers that only read the game's tables cost no unicorn VM (two live VMs fault on this unicorn)."""

    def __init__(self, data: bytes):
        pe = pefile.PE(data=data, fast_load=True)
        self.image = pe.get_memory_mapped_image(ImageBase=0x400000)

    def u32(self, va: int) -> int:
        off = va - 0x400000
        return struct.unpack("<I", self.image[off:off + 4])[0]

    def cstring(self, va: int) -> str:
        off = va - 0x400000
        end = self.image.index(b"\0", off)
        return self.image[off:end].decode("cp1252")

SKIP = "needs unicorn, pefile and the stock executables (inputs/vvN-stock-copy) and the built DLL"

# Each game's string lookup and record fields (translations_emulation / the DLL's own tables).
LOOKUP = {1: 0x433880, 2: 0x4415A0, 3: 0x42F190, 4: 0x44D3D0, 5: 0x4506D0}
GET_STRING = {3: 0x42F190, 4: 0x44D3D0, 5: 0x4506D0}
BUILD_TEXT = {3: 0x42F1D0, 4: 0x44D410, 5: 0x450710}
LOADER_SITE = {3: 0x42F6E5, 4: 0x44D98A, 5: 0x450C9D}
SM = {3: (0x4AB990, 0x4BA), 4: (0x4C41F8, 1338), 5: (0x4D31F0, 1409)}
# The id->entry pointer array get_string / build_text read, and the singleton the DLL checks.
SLOT_ARRAY = {3: 0x592730, 4: 0x4DEA20, 5: 0x5240A8}
SINGLETON = {3: 0x593A74, 4: 0x4DFF28, 5: 0x525704}
TABLE = {1: (0x487208, 0x275, 0x14), 2: (0x496300, 0x36C, 12)}
RECORDS = {1: dict(pool=0x48B614, stride=0x3D8, present=0x28, name=0x370, sex=0x350, male=1),
           2: dict(pool=0x499F24, stride=0xE48C, present=0x30, name=0x564, sex=0x538, male=1)}
# VV3-5 live records (head_look_emulation GAMES) for the _output person-by-name test.
REC345 = {3: dict(records=0x59E110 + 0x14, stride=0x1F8C, present=0xF10, name=0xDD4, sex=0xDC8),
          4: dict(records=0x50E568 + 0x44, stride=0x2E3C, present=0x1CC4, name=0x1B9C, sex=0x1B90),
          5: dict(records=0x554148 + 0x48, stride=0x2F44, present=0x1CD4, name=0x1B9C, sex=0x1B90)}
OUTPUT = {1: 0x44D9AD, 2: 0x46AA2D, 3: 0x471CFD, 4: 0x477CED, 5: 0x4820FE}


def file_bytes(tf: F.TranslationFile) -> bytes:
    return b"\xef\xbb\xbf" + F.dumps(tf).encode("utf-8")


def template(game: int, rows: list[F.Row], code: str = "fr", language: str = "Test") -> F.TranslationFile:
    tf = F.template_file(rows, TITLES[game], language, code)
    for prepared, source in zip(tf.rows, rows):   # template_file blanks the translation; keep ours
        prepared.translation = source.translation
    return tf


def row(source: str, ident: str, en: str, tr: str, notes: str = "") -> F.Row:
    return F.Row(F.make_key(source, ident, en), en, tr, notes)


@unittest.skipUnless(HAVE, SKIP)
class TranslationsRuntimeTests(unittest.TestCase):
    exes: dict = {}
    _probes: dict = {}

    @classmethod
    def setUpClass(cls):
        cls.exes = {n: stock_exe(n).read_bytes() for n in range(1, 6)}
        cls._probes = {}

    @classmethod
    def probe(cls, game: int):
        """The stock image, read with no emulator (two live unicorn VMs fault)."""
        if game not in cls._probes:
            cls._probes[game] = Image(cls.exes[game])
        return cls._probes[game]

    # -- helpers ---------------------------------------------------------------------------------------
    def table_en(self, game: int, ident: int) -> str:
        p = self.probe(game)
        base, rows, stride = TABLE[game]
        for r in range(rows):
            if p.u32(base + r * stride) == ident:
                return p.cstring(p.u32(base + r * stride + 4)).encode("latin-1").decode("cp1252")
        raise AssertionError(f"no table id {ident}")

    def sm_english(self, game: int, index: int):
        """A real entry's eName and built-in English."""
        p = self.probe(game)
        base, _ = SM[game]
        e = base + index * 16
        name = p.cstring(p.u32(e + 4))
        english = p.cstring(p.u32(e + 8)).encode("latin-1").decode("cp1252")
        return name, english

    def lookup(self, g: Game, ident: int) -> bytes:
        if g.game <= 2:
            lang = g.p.alloc(4)         # [lang]==0 -> English column; the DLL rewrote the en pointer
            return g.raw(g.p.call(LOOKUP[g.game], [ident], ecx=lang))
        return g.raw(g.p.call(GET_STRING[g.game], [ident]))

    # -- (a) the string lookup -------------------------------------------------------------------------
    def present_ids(self, game: int, want: int) -> list[int]:
        """`want` ids the stock table really has, each with a non-empty token-and-percent-free English."""
        img = self.probe(game)
        base, rows, stride = TABLE[game]
        out = []
        for r in range(rows):
            ident = img.u32(base + r * stride)
            ptr = img.u32(base + r * stride + 4)
            if ident == 0 or ptr < 0x400000 or ptr >= 0x400000 + len(img.image):
                continue
            text = img.cstring(ptr)
            if 4 <= len(text) <= 80 and "%" not in text and all(c not in text for c in "*^&+={}"):
                out.append(ident)
                if len(out) == want:
                    break
        return out

    def test_table_lookup_translates_and_falls_back(self):
        for game in (1, 2):
            with self.subTest(game=game):
                a, b, c, d = self.present_ids(game, 4)
                ena, enc, end = (self.table_en(game, x) for x in (a, c, d))
                rows = [
                    row("table", str(a), ena, "OBERSETZT"),              # used
                    row("table", str(b), self.table_en(game, b), ""),    # empty: English
                    row("table", str(c), enc, "zwei {nom} dinge"),         # variable added: error
                    row("table", str(d), end, "x {%1: m=a}"),            # %1 but no conversion: error
                ]
                stale = F.Row(f"table/{a}~{F.english_hash('STALE ENGLISH')}", "STALE ENGLISH", "VEALT")
                rows.append(stale)                                       # same id, wrong hash: English
                tf = template(game, rows)
                g = Game(game, self.exes[game], file_bytes(tf))
                g.start()
                self.assertTrue(g.active())
                self.assertEqual(self.lookup(g, a), b"OBERSETZT")
                self.assertEqual(self.lookup(g, b).decode("cp1252"), self.table_en(game, b))
                self.assertEqual(self.lookup(g, c).decode("cp1252"), enc)
                self.assertEqual(self.lookup(g, d).decode("cp1252"), end)

    def _plain_sm_entry(self, game: int):
        """A real sm entry whose built-in English has no placeholder and no token."""
        img = self.probe(game)
        base, count = SM[game]
        for i in range(count):
            e = base + i * 16
            ident = img.u32(e)
            english = img.cstring(img.u32(e + 8))
            if ident and 3 <= len(english) <= 60 and "%" not in english \
                    and all(c not in english for c in "{}") and img.u32(e + 0xC) == 0:
                return img.cstring(img.u32(e + 4)), english, ident
        raise AssertionError("no plain sm entry")

    def test_sm_lookup_translates_after_loader(self):
        for game in (3, 4, 5):
            with self.subTest(game=game):
                name, english, ident = self._plain_sm_entry(game)
                tf = template(game, [row("sm", name, english, "LOCALISÉ")])
                g = Game(game, self.exes[game], file_bytes(tf))
                self._run_loader(g)                                      # the table is built (no sm.xml)
                g.start()                                                # the DLL's wrapper writes +0xC now
                self.assertEqual(g.raw(g.p.call(GET_STRING[game], [ident])), "LOCALISÉ".encode("cp1252"))

    def _sm_id(self, game: int, index: int) -> int:
        return self.probe(game).u32(SM[game][0] + index * 16)

    def _run_loader(self, g: Game):
        """Stand in for the string-table loader with its file open failing (no sm.xml): the slot array
        id->entry is built from the key table and every entry's loaded pointer (+0xC) is left 0, so the
        built-in English (+8) is live -- the state the DLL's loader wrapper sees.  The singleton is made
        non-NULL so VvfpStartup runs the wrapper's work (tr_after_loader).  Booting the stock C runtime's
        ctor would need fopen and the CRT heap; this is the same resulting memory."""
        base, count = SM[g.game]
        slots = SLOT_ARRAY[g.game]
        seen = set()
        for i in range(count):
            e = base + i * 16
            ident = g.p.u32(e)
            g.p.put32(e + 0xC, 0)                      # loaded: none (the file did not open)
            if 0 < ident and ident not in seen:
                g.p.put32(slots + ident * 4, e)        # first entry with that id wins
                seen.add(ident)
        g.p.put32(SINGLETON[g.game], 0x1234)           # the table object exists

    # -- (b) build_text expands the converted {m/f} --------------------------------------------------
    def test_build_text_expands_name_select(self):
        for game in (3, 4, 5):
            with self.subTest(game=game):
                name, english = self._pick_name_entry(game)
                tr = "{name: m=Le villageois | f=La villageoise} {name} a fini."
                tf = template(game, [row("sm", name, english, tr)])
                g = Game(game, self.exes[game], file_bytes(tf))
                self._run_loader(g)
                g.start()
                ident = self._id_of(game, name)
                for male, expect in ((1, b"Le villageois"), (0, b"La villageoise")):
                    dest = g.p.alloc(0x800)
                    namearg = g.p.alloc(8)
                    g.p.write(namearg, b"Zuma\0")
                    g.p.call(BUILD_TEXT[game], [dest, 0x7D0, ident, namearg, male, 0, 0, 0])
                    self.assertTrue(g.raw(dest).startswith(expect), g.raw(dest))
                    self.assertIn(b"Zuma", g.raw(dest))

    def _pick_name_entry(self, game: int):
        """A real sm entry whose English contains {name}."""
        p = self.probe(game)
        base, count = SM[game]
        for i in range(count):
            e = base + i * 16
            english = p.cstring(p.u32(e + 8)).encode("latin-1").decode("cp1252")
            if "{name}" in english and "{name2}" not in english and "%" not in english:
                return p.cstring(p.u32(e + 4)), english
        self.skipTest("no sm entry with a bare {name}")

    def _id_of(self, game: int, name: str) -> int:
        p = self.probe(game)
        base, count = SM[game]
        for i in range(count):
            e = base + i * 16
            if p.cstring(p.u32(e + 4)) == name:
                return p.u32(e)
        raise AssertionError(name)

    # -- (c) the CRT sprintf with %N plural and person selects ---------------------------------------
    def test_output_plural_and_person_selects(self):
        game = 3
        img = self.probe(game)
        base, count = SM[game]
        # take a real entry and replace its built-in English with a %s-then-%d format of our own, so the
        # row's English matches the live bytes get_string returns; the hash then checks out.
        idx = next(i for i in range(count) if img.u32(base + i * 16)
                   and img.u32(base + i * 16 + 0xC) == 0
                   and "%" not in img.cstring(img.u32(base + i * 16 + 8)))
        ident = img.u32(base + idx * 16)
        name = img.cstring(img.u32(base + idx * 16 + 4))
        english = "%s found %d apples"
        tr = "{%1: m=Il | f=Elle | o=Iel} (%s) a %d {%2: one=pomme | other=pommes} sur 50 %"
        notes = "%1 = villager (person); %2 = number (number)"
        tf = template(game, [row("sm", name, english, tr, notes)], code="fr")
        g = Game(game, self.exes[game], file_bytes(tf))
        # our English lives where the entry's built-in English points (a spare .data page)
        english_at = g.p.alloc(len(english) + 1)
        g.p.write(english_at, english.encode("cp1252") + b"\0")
        g.p.put32(base + idx * 16 + 8, english_at)
        self._run_loader(g)
        g.start()
        rec = REC345[game]
        r0 = rec["records"]
        g.p.write(r0 + rec["present"], b"\x01")
        g.p.write(r0 + rec["name"], b"Lin\0")
        g.p.put32(r0 + rec["sex"], 1)                 # VV3: 1 = female
        fmt = g.raw(g.p.call(GET_STRING[game], [ident]))
        self.assertIn(b"\x01", fmt)                   # the prepared format carries run-time selects
        name_arg = g.p.alloc(8)
        g.p.write(name_arg, b"Lin\0")
        for n, expect in ((1, b"pomme"), (3, b"pommes")):
            out = g.p.alloc(0x200)
            g.p.call(self._sprintf(game), [out, g.p.u32(base + idx * 16 + 0xC), name_arg, n])
            text = g.raw(out)
            self.assertIn(b"Elle", text)              # Lin is female
            self.assertIn(b"Lin", text)
            self.assertIn(expect, text)
            self.assertTrue(expect == b"pommes" or b"pommes" not in text)
            # a plain "%" of the translation is handed to printf as "%%", so it shows one "%"
            self.assertTrue(text.endswith(b"sur 50 %"), text)

    def _sprintf(self, game: int) -> int:
        return {3: 0x46EFCD, 4: 0x4716DB, 5: 0x47C046}[game]

    # -- (d) a VV1/VV2 expander resolves a '*' select ------------------------------------------------
    def test_expander_resolves_star_by_sex(self):
        for game in (1, 2):
            with self.subTest(game=game):
                ident, english = self._star_table_text(game)
                tr = english.replace("*", "*") + " {*: m=content | f=contente | o=contentes}"
                notes = "* = the villager's name (person)"
                tf = template(game, [row("table", str(ident), english, tr, notes)])
                g = Game(game, self.exes[game], file_bytes(tf))
                g.start()
                self.assertTrue(g.active())
                prepared = self.lookup(g, ident)
                self.assertIn(b"\x01", prepared)          # the select is kept for the expander
                # drive the expander directly with a dialog whose villager is female
                out = self._drive_expander(g, prepared)
                self.assertIn(b"contente", out)

    def _star_table_text(self, game: int):
        p = self.probe(game)
        base, rows, stride = TABLE[game]
        # any short token-free text; the id reaches an expander only through the event code, but the
        # expander detour works on any src we hand it, so any id with a '*'-free English will do.
        for r in range(rows):
            ident = p.u32(base + r * stride)
            text = p.cstring(p.u32(base + r * stride + 4)).encode("latin-1").decode("cp1252")
            if 4 <= len(text) <= 40 and "%" not in text and "*" not in text and "{" not in text \
                    and ident not in (0,):
                return ident, text
        raise AssertionError("no suitable table text")

    def _drive_expander(self, g: Game, src: bytes):
        """Enter the first expander with a dialog whose event villager is female, src = the prepared text."""
        from translations_emulation import GLYPHS_MODULE  # noqa: F401
        exp = {1: 0x427690, 2: 0x41F0F0}[g.game]
        idx_off = {1: 0x5094, 2: 0x50A0}[g.game]
        base_off = {1: 0x50A8, 2: 0x50B0}[g.game]
        rec = RECORDS[g.game]
        dialog = g.p.alloc(0x5200)
        records = g.p.alloc(rec["stride"] * 4)
        g.p.put32(dialog + idx_off, 0)
        g.p.put32(dialog + base_off, records)
        g.p.write(records + rec["present"], b"\x01")
        g.p.put32(records + rec["sex"], 0 if g.game <= 2 else 1)      # female
        g.p.write(records + rec["name"], b"Mia\0")
        out = g.p.alloc(0x3000)
        srcbuf = g.p.alloc(len(src) + 1)
        g.p.write(srcbuf, src + b"\0")
        # thiscall(ecx=dialog; out, src), ret 8
        g.p.call(exp, [out, srcbuf], ecx=dialog)
        return g.raw(out)

    # -- (e) an exe literal operand site points at the translation ------------------------------------
    def test_exe_literal_site_repointed(self):
        cases = {1: (0x459BDC, "Menu"), 3: (0x47F488, "OK")}
        sites = {1: 0x429FD7, 3: 0x41E115}
        offs = {1: 1, 3: 1}
        for game, (literal, english) in cases.items():
            with self.subTest(game=game):
                en = self._exe_literal(game, literal)
                if en is None:
                    self.skipTest("literal text not where expected")
                tr = "Menü" if en == "Menu" else "D'accord"
                tf = template(game, [row("exe", hex(literal), en, tr)])
                g = Game(game, self.exes[game], file_bytes(tf))
                g.start()
                self.assertTrue(g.active())
                imm = g.p.u32(sites[game] + offs[game])
                self.assertNotEqual(imm, literal)
                self.assertEqual(g.raw(imm).decode("cp1252"), tr)

    def _exe_literal(self, game: int, va: int):
        return self.probe(game).cstring(va).encode("latin-1").decode("cp1252") or None

    # -- the editor's row rules for A New Home's island-event codes (Codex, #672) ----------------------
    def test_event_codes_follow_the_row_rules(self):
        import vv_translations as vt
        game = 1
        en = self.table_en(game, 336)                   # The Trapped Whale: "* noticed ... ^ discovers ..."
        self.assertIn("*", en)
        entry = next(r for r in vt.load_inventory(game)["rows"] if r["stem"] == "table/336")
        rules = vt._rules_for(entry)                    # the rules the editor checks this line with
        cases = (
            ("La baleine échouée : quelqu'un a vu une baleine.", False),         # the name (*) dropped
            ("La baleine : * a vu une baleine, + aussi.", False),                # + added (him/her)
            ("La baleine : * a vu une baleine.", True),
            ("La baleine : {*: m=* l'a vue | f=* l'a vue | o=* l'a vue}.", True),  # * in every branch
            ("La baleine : {*: m=* l'a vue | f=elle l'a vue}.", False),          # * not in every branch
            ("La baleine : * {*: m=ravi | f=ravie + | o=ravi}.", False),         # + inside a branch
        )
        for tr, used in cases:
            with self.subTest(tr=tr):
                editor_ok = not [i for i in F.check_row(en, tr, rules) if i.severity == "error"]
                self.assertEqual(editor_ok, used)
                tf = template(game, [row("table", "336", en, tr)])
                g = Game(game, self.exes[game], file_bytes(tf))
                g.start()
                got = self.lookup(g, 336).decode("cp1252")
                if used:
                    self.assertNotEqual(got, en)
                else:
                    self.assertEqual(got, en)

    # -- a translation too long for the game's buffers stays English ---------------------------------
    def test_too_long_stays_english(self):
        game = 1
        # A line of 80-200 bytes: three times it is past TR_SHORT (224), so the short-line cap decides.
        ident = en = None
        for i in range(1, 640):
            try:
                e = self.table_en(game, i)
            except AssertionError:
                continue
            if 80 <= len(e) < 200 and not any(ch in e for ch in "%*^&+=|~@#$"):
                ident, en = i, e
                break
        self.assertIsNotNone(ident)
        for length, used in ((223, True), (224, False)):
            with self.subTest(length=length):
                tr = "x" * length
                tf = template(game, [row("table", str(ident), en, tr)])
                g = Game(game, self.exes[game], file_bytes(tf))
                g.start()
                self.assertEqual(self.lookup(g, ident).decode("cp1252"), tr if used else en)

    # -- (f) UTF-8 kept with the glyph companion, else Windows-1252 -----------------------------------
    def test_encoding_follows_glyph_companion(self):
        game = 1
        en = self.table_en(game, 1)
        cjk = "日本語"
        tf = template(game, [row("table", "1", en, cjk)], code="ja")
        for glyphs, want in ((1, cjk.encode("utf-8")), (None, b"???")):
            with self.subTest(glyphs=glyphs):
                g = Game(game, self.exes[game], file_bytes(tf), glyphs=glyphs)
                g.start()
                self.assertEqual(self.lookup(g, 1), want)

    def test_use_unicode_font_keeps_utf8_too(self):
        """Use Unicode Font's companion starts after this one (append-only list): already loaded, or only
        shipped beside it -- then loaded by its full path and started when the translations are prepared."""
        game = 1
        en = self.table_en(game, 1)
        cjk = "日本語"
        tf = template(game, [row("table", "1", en, cjk)], code="ja")
        for shipped in (False, True):
            with self.subTest(shipped_only=shipped):
                g = Game(game, self.exes[game], file_bytes(tf), glyphs=1, glyphs_dll="VVFP Unicode Font.dll",
                         font_shipped=shipped)
                g.start()
                self.assertEqual(self.lookup(g, 1), cjk.encode("utf-8"))
                self.assertEqual(bool(g.font_started), shipped)

    def test_cuneiform_is_questionmarks_without_glyphs(self):
        game = 1
        en = self.table_en(game, 1)
        cuneiform = "\U00012000\U00012001"
        tf = template(game, [row("table", "1", en, cuneiform)], code="akk")
        g = Game(game, self.exes[game], file_bytes(tf))
        g.start()
        self.assertEqual(self.lookup(g, 1), b"??")
        g2 = Game(game, self.exes[game], file_bytes(tf), glyphs=1)
        g2.start()
        self.assertEqual(self.lookup(g2, 1), cuneiform.encode("utf-8"))

    # -- (g) no Translation.txt: the image is untouched ----------------------------------------------
    def test_no_file_writes_nothing(self):
        for game in range(1, 6):
            with self.subTest(game=game):
                g = Game(game, self.exes[game], None)
                before = bytes(g.p.read(0x400000, g.p._exe_pe.OPTIONAL_HEADER.SizeOfImage))
                g.start()
                self.assertEqual(g.active(), 0)
                after = bytes(g.p.read(0x400000, g.p._exe_pe.OPTIONAL_HEADER.SizeOfImage))
                self.assertEqual(before, after)
                # a translate call is a no-op
                self.assertEqual(g.translate(b"anything"), b"anything")

    def test_wrong_game_writes_nothing(self):
        game = 1
        en = self.table_en(game, 1)
        tf = template(game, [row("table", "1", en, "x")])
        tf.set_info("@game", TITLES[2], "")           # a file for another game
        g = Game(game, self.exes[game], file_bytes(tf))
        before = bytes(g.p.read(0x400000, g.p._exe_pe.OPTIONAL_HEADER.SizeOfImage))
        g.start()
        self.assertEqual(g.active(), 0)
        self.assertEqual(before, bytes(g.p.read(0x400000, g.p._exe_pe.OPTIONAL_HEADER.SizeOfImage)))

    # -- (h) all or none: one non-stock site -> no write ---------------------------------------------
    def test_all_or_none_on_a_changed_site(self):
        game = 1
        en = self.table_en(game, 1)
        # an exe row and a table row: the exe site is clobbered, so NOTHING installs (and no table pointer)
        tf = template(game, [row("exe", hex(0x459BDC), "Menu", "Menü"),
                             row("table", "1", en, "X")])
        g = Game(game, self.exes[game], file_bytes(tf))
        g.p.write(0x429FD7, b"\x90\x90\x90\x90\x90")   # the site no longer holds its stock bytes
        table_ptr_before = g.p.u32(0x487208 + 1 * 0x14 + 4)   # id 1's en pointer
        g.start()
        self.assertEqual(g.active(), 0)
        self.assertEqual(g.p.u32(0x487208 + 1 * 0x14 + 4), table_ptr_before)
        self.assertEqual(self.lookup(g, 1).decode("cp1252"), en)

    # -- VvfpTranslateText (the companions' own text) ------------------------------------------------
    def test_translate_text_exact_and_pattern(self):
        game = 1
        en_table = self.table_en(game, 1)
        tf = template(game, [
            row("table", "1", en_table, "x"),                           # makes the file non-empty
            row("vvfp.ui", "greeting", "Welcome", "Bienvenue"),
            row("vvfp.ui", "cured", "%s cured %d villagers", "%s a guéri %d villageois"),
        ])
        g = Game(game, self.exes[game], file_bytes(tf))
        g.start()
        self.assertTrue(g.active())
        self.assertEqual(g.translate(b"Welcome"), "Bienvenue".encode("cp1252"))
        self.assertEqual(g.translate(b"Kemala cured 3 villagers"),
                         "Kemala a gu\xe9ri 3 villageois".encode("cp1252"))
        self.assertEqual(g.translate(b"not a known string"), b"not a known string")

    def test_a_plain_percent_in_the_companions_own_text_is_one_percent(self):
        game = 1
        tf = template(game, [
            row("table", "1", self.table_en(game, 1), "x"),
            row("vvfp.ui", "sale", "Sale", "50 % de remise"),
            row("vvfp.ui", "cured", "%s cured %d villagers", "%s a guéri %d villageois (100 %)"),
        ])
        g = Game(game, self.exes[game], file_bytes(tf))
        g.start()
        self.assertEqual(g.translate(b"Sale"), "50 % de remise".encode("cp1252"))
        self.assertEqual(g.translate(b"Kemala cured 3 villagers"),
                         "Kemala a guéri 3 villageois (100 %)".encode("cp1252"))

    def test_translate_text_stable_pointer(self):
        game = 1
        tf = template(game, [row("vvfp.ui", "greeting", "Welcome", "Bienvenue")])
        g = Game(game, self.exes[game], file_bytes(tf))
        g.start()
        a = g.p.export("VvfpTranslateText", self._cstr(g, b"Welcome"))
        b = g.p.export("VvfpTranslateText", self._cstr(g, b"Welcome"))
        self.assertEqual(a, b)

    def _cstr(self, g: Game, text: bytes) -> int:
        at = g.p.alloc(len(text) + 1)
        g.p.write(at, text + b"\0")
        return at

    # -- a companion's own text by key (native/shared/vvfp_translate.h) ---------------------------------
    def key(self, g: Game, stem: str, english: bytes, cap: int) -> bytes:
        return g.raw(g.p.export("VvfpTranslateKey", self._cstr(g, stem.encode()), self._cstr(g, english), cap))

    def test_translate_key_by_stem_hash_and_buffer(self):
        game = 1
        tf = template(game, [
            row("vvfp.cod", "vvfp_cause_of_death.CAUSE_WORDS.1", "Disease", "Maladie"),
            row("vvfp.parentage", "vv1_parentage.x.s0", "%s of %s", "%s de %s"),
            row("vvfp.story", "story_time_skip.y.s2", "%d years have passed on the island.",
                "%d {%1: one=an s'est écoulé | other=ans se sont écoulés} sur l'île."),
        ])
        g = Game(game, self.exes[game], file_bytes(tf))
        g.start()
        self.assertEqual(self.key(g, "vvfp.cod/vvfp_cause_of_death.CAUSE_WORDS.1", b"Disease", 64), b"Maladie")
        self.assertEqual(self.key(g, "vvfp.cod/vvfp_cause_of_death.CAUSE_WORDS.1", b"Disease", 0), b"Maladie")
        # The English is not the row's (another patch's text, an edited English): English.
        self.assertEqual(self.key(g, "vvfp.cod/vvfp_cause_of_death.CAUSE_WORDS.1", b"Plague", 64), b"Plague")
        # It does not fit the companion's buffer: English.
        self.assertEqual(self.key(g, "vvfp.cod/vvfp_cause_of_death.CAUSE_WORDS.1", b"Disease", 7), b"Disease")
        self.assertEqual(self.key(g, "vvfp.cod/unknown", b"Disease", 64), b"Disease")
        self.assertEqual(self.key(g, "vvfp.parentage/vv1_parentage.x.s0", b"%s of %s", 32), b"%s de %s")
        # A filled-in format: the plural chosen by the value.
        out = g.p.alloc(256)
        stem = self._cstr(g, b"vvfp.story/story_time_skip.y.s2")
        english = self._cstr(g, b"%d years have passed on the island.")
        for value, expected in ((1, "1 an s'est écoulé sur l'île."), (4, "4 ans se sont écoulés sur l'île.")):
            text = self._cstr(g, f"{value} years have passed on the island.".encode())
            self.assertEqual(g.p.export("VvfpTranslateKeyText", stem, english, text, out, 256), 1)
            self.assertEqual(g.raw(out), expected.encode("cp1252"))
        text = self._cstr(g, b"4 years have passed on the island.")
        self.assertEqual(g.p.export("VvfpTranslateKeyText", stem, english, text, out, 10), 0)   # too long

    def test_without_a_translation_keys_answer_english(self):
        game = 1
        g = Game(game, self.exes[game], None)
        g.start()
        self.assertEqual(self.key(g, "vvfp.cod/vvfp_cause_of_death.CAUSE_WORDS.1", b"Disease", 64), b"Disease")

    # A place an exe patch writes visible text at (the trusted list, native/vvfp_translations/tr_patch_sites.inc).
    PATCH_VA = 0x481240
    PATCH_EN = "You can zip around the island with your numeric keys."

    def exe_with_patch_text(self, game: int, va: int, text: str) -> bytes:
        """The stock executable with the patch's text written at `va` (a file offset of va - 0x400000)."""
        data = bytearray(self.exes[game])
        raw = text.encode("cp1252") + b"\0"
        data[va - 0x400000:va - 0x400000 + len(raw)] = raw
        return bytes(data)

    def test_exe_patch_text_in_place_when_it_fits(self):
        game, va, en = 1, self.PATCH_VA, self.PATCH_EN
        exe = self.exe_with_patch_text(game, va, en)
        short = en[: len(en) // 2].strip()
        tf = template(game, [row("patch", f"0x{va:x}", en, short)])
        g = Game(game, exe, file_bytes(tf))
        g.start()
        self.assertTrue(g.active())
        self.assertEqual(g.raw(va), short.encode("cp1252"))
        # Too long for the English's own bytes: the bytes stay, the content map still has it.
        tf = template(game, [row("patch", f"0x{va:x}", en, en + " and much more text")])
        g = Game(game, exe, file_bytes(tf))
        g.start()
        self.assertEqual(g.raw(va), en.encode("cp1252"))
        self.assertEqual(g.translate(en.encode("cp1252")), (en + " and much more text").encode("cp1252"))

    def test_a_crafted_patch_row_cannot_overwrite_code(self):
        # A row names the address and the hash of its English itself. VV1's _output prologue at 0x44D9AD
        # (558BEC81EC540200..) read as Windows-1252 is a valid "English" for it: without the trusted list the
        # DLL would write the translation over those instructions.
        game, va = 1, 0x44D9AD
        stock = self.exes[game]
        code = stock[va - 0x400000:va - 0x400000 + 7]
        from vv_game_text import GAME_TEXT      # cp1252 with its five undefined bytes kept (0x81 is one)
        english = code.decode(GAME_TEXT)
        tf = template(game, [row("patch", f"0x{va:x}", english, "A")])
        g = Game(game, stock, file_bytes(tf))
        g.start()
        self.assertEqual(g.raw(va)[:7], code)
        # An unlisted address is refused even when its live text matches the row's English.
        other = 0x481300
        exe = self.exe_with_patch_text(game, other, "Some text no patch writes")
        tf = template(game, [row("patch", f"0x{other:x}", "Some text no patch writes", "Autre")])
        g = Game(game, exe, file_bytes(tf))
        g.start()
        self.assertEqual(g.raw(other), b"Some text no patch writes")

    def test_a_text_built_from_several_rows_is_translated_line_by_line(self):
        game = 1
        tf = template(game, [row("vvfp.story", "a.s0", "Not in A New Home:", "Pas dans A New Home :"),
                             row("vvfp.story", "a.s1", "- Faction: none.", "- Faction : aucune.")])
        g = Game(game, self.exes[game], file_bytes(tf))
        g.start()
        self.assertEqual(g.translate(b"Not in A New Home:\n\n- Faction: none.\n- Something else."),
                         "Pas dans A New Home :\n\n- Faction : aucune.\n- Something else.".encode("cp1252"))

    # -- the dialog hook is set only with a vvfp row -------------------------------------------------
    def test_window_hook_only_with_vvfp_rows(self):
        game = 1
        en = self.table_en(game, 1)
        g1 = Game(game, self.exes[game], file_bytes(template(game, [row("table", "1", en, "x")])))
        g1.start()
        self.assertFalse(any(h[0] == 0x200 for h in g1.hooks))     # WH_CALLWNDPROCRET = 12, not 0x200
        self.assertEqual([h for h in g1.hooks], [])
        g2 = Game(game, self.exes[game], file_bytes(template(game, [row("vvfp.x", "a", "Hi", "Salut")])))
        g2.start()
        self.assertEqual([h[0] for h in g2.hooks], [12])           # WH_CALLWNDPROCRET


@unittest.skipUnless(HAVE, SKIP)
class RowCheckParityTests(unittest.TestCase):
    """The DLL uses a row exactly when the Python reference reports it with no error.  Proved on the VV1
    table: many translations, each either reaches the lookup or leaves the English."""

    def test_used_rows_match_the_reference(self):
        import gc
        game = 1
        exe = stock_exe(game).read_bytes()
        img = Image(exe)
        base, rows, stride = TABLE[game]
        ident = next(img.u32(base + r * stride) for r in range(rows) if img.u32(base + r * stride))
        en = img.cstring(img.u32(base + next(r for r in range(rows) if img.u32(base + r * stride)) * stride + 4))
        cases = {
            "plain": "Traduit",
            "empty": "",
            "percent-added": "100% sûr",
            "french-percent": "50 % de réduction",
            "percent-and-space-conversion": "100 % d",
            "good-select": "{%1: m=x | o=y}",                  # no %1 here: error (no conversion)
            "bad-escape-ok": "ligne\\ndeux",                   # fine
            "control-char": "bad\x07char",
            "crlf": "ligne\r\ndeux",                       # CR LF is a line break the games use, so it is allowed
            "email": "write to a@b.com",
        }
        for label, tr in cases.items():
            with self.subTest(label):
                r = F.Row(F.make_key("table", str(ident), en), en, tr)
                issues = F.check_row(en, tr, F.RowRules())
                reference_used = bool(tr) and not any(i.severity == "error" for i in issues)
                tf = F.template_file([r], TITLES[game], "Test", "fr")
                tf.rows[0].translation = tr
                g = Game(game, exe, b"\xef\xbb\xbf" + F.dumps(tf).encode("utf-8"))
                g.start()
                lang = g.p.alloc(4)
                got = g.raw(g.p.call(LOOKUP[game], [ident], ecx=lang)).decode("cp1252")
                dll_used = got != en
                self.assertEqual(dll_used, reference_used, f"{label}: dll={got!r}")
                del g
                gc.collect()


if __name__ == "__main__":
    unittest.main()


