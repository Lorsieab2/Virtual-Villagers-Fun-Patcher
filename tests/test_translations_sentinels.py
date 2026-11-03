"""Every patch text goes through its own translation key, and the translation is what the game shows.

The owner, 2026-11-03: "every text a patch adds or changes must go through its OWN translation key and show the
translation in the game. It must not be a copy of a stock string, and generated or patched code must not copy
English text around the translation. Add a test that translates every patch string to a sentinel and proves the
sentinel reaches the game's draw or fill path."

Static (always run; CI has no stock executables):
  * every row says how it reaches the screen ("route": key / patch / content) and the say-so is what the sources
    show (scripts/scan_patch_text.py route_of);
  * the template offers no row that does nothing: two rows with one English are found by that English alone, so
    the later is left out (vv_translations.content_shadowed), and every left-out row's English is still carried;
  * the draw and fill paths exist: every text routine the Unicode Text companion hooks offers its text to
    VvfpTranslateText, the dialog hook translates a window as it opens and when its text is set, a companion's
    key lookups pass the row's own stem and English;
  * the German / Spanish / French "Listening to a story" labels (A New Home) are rows asked for by their keys.

Emulated (unicorn, the stock executables and the built DLL; skips without them): every game's patch texts become
sentinels and each is asked for the way its route asks (tests/translations_sentinels.py).  The strings that cannot
be proven this way are listed in docs/reports/translation-keys/audit.md, one reason each.
"""
from __future__ import annotations

import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests"))

import scan_patch_text as scan  # noqa: E402
import vv_translations as vt  # noqa: E402

try:
    import pefile  # noqa: F401
    import unicorn  # noqa: F401
    from translations_emulation import DLL, stock_exe
    HAVE = DLL.is_file() and all(stock_exe(n) is not None and stock_exe(n).is_file() for n in range(1, 6))
except ImportError:
    HAVE = False

SKIP = "needs unicorn, pefile, the stock executables (inputs/vvN-stock-copy) and the built DLL"
GAMES = range(1, 6)

# What the emulated proof leaves unproven, by reason, per game (docs/reports/translation-keys/audit.md).  A row
# that stops being proven, or one that is newly unproven, fails the test: the list only ever shrinks.
UNPROVEN_REASONS = {"the address is not in the stock image", "another patch row of its file shares this address",
                    "English is not Windows-1252"}


def rows_by_stem() -> dict[str, dict]:
    return {r["stem"]: r for r in vt.load_patcher_strings()}


class RouteTests(unittest.TestCase):
    def test_every_row_has_the_route_its_source_shows(self) -> None:
        keys = scan.key_call_stems()
        for row in vt.load_patcher_strings():
            with self.subTest(stem=row["stem"]):
                route = scan.route_of(row["stem"], keys)
                self.assertEqual(row.get("route"), "key" if route == "key" else None,
                                 "scripts/build_patch_text_inventory.py stamps the route")

    def test_every_key_a_source_asks_for_is_a_row(self) -> None:
        rows = rows_by_stem()
        for stem in scan.key_call_stems():
            with self.subTest(stem=stem):
                self.assertIn(stem, rows)
                self.assertEqual(rows[stem].get("route"), "key")

    def test_the_generated_lists_are_current(self) -> None:
        """tr_patch_sites.inc (where an exe patch's text may be written over) and tr_key_stems.inc (the rows kept
        out of the content map) are what scripts/build_translations_patch_sites.py makes of the template."""
        import build_translations_patch_sites as gen   # noqa: PLC0415
        for path, expected in ((gen.OUT, gen.build()), (gen.KEYS_OUT, gen.build_key_stems())):
            self.assertEqual(path.read_text(encoding="utf-8").replace("\r\n", "\n"), expected, path.name)

    def test_the_built_stems_have_their_builders(self) -> None:
        """The stems a companion builds with wsprintfA (KEY_FAMILIES) are built where the scan says they are."""
        for relative, fmt_text in scan.KEY_FAMILY_SOURCES:
            with self.subTest(source=relative, builds=fmt_text):
                self.assertIn(fmt_text, (ROOT / relative).read_text(encoding="utf-8"))
        rows = rows_by_stem()
        for stem, row in rows.items():
            if scan.is_key_family(stem):
                self.assertEqual(row.get("route"), "key", stem)

    def test_storytelling_labels_in_every_language_are_asked_for_by_key(self) -> None:
        """A New Home's Listening to a story label: English, German, Spanish and French each have a row and
        the companion asks for each by its stem (the German / Spanish / French ones were once returned as
        literals, so a translation of them was never shown)."""
        source = (ROOT / "native" / "vvfp_storytelling" / "vvfp_storytelling.c").read_text(encoding="utf-8")
        for n, constant in enumerate(("LISTEN_EN", "LISTEN_DE", "LISTEN_ES", "LISTEN_FR")):
            with self.subTest(label=constant):
                stem = f"vvfp.storytelling/vvfp_storytelling.x.s{n}"
                self.assertRegex(source, r'vvfp_tr\("%s",\s*%s,' % (re.escape(stem), constant))
                self.assertEqual(rows_by_stem()[stem].get("route"), "key")
        # No label constant is handed to the game bare: each one appears only as the English argument of a lookup.
        for constant in ("LISTEN_EN", "LISTEN_DE", "LISTEN_ES", "LISTEN_FR"):
            for m in re.finditer(r"\b%s\b" % constant, source):
                line_start = source.rfind("\n", 0, m.start()) + 1
                line = source[line_start:source.find("\n", m.start())]
                self.assertTrue(line.lstrip().startswith(("static const char", "return vvfp_tr(", "case"))
                                or "vvfp_tr(" in line, line)


class TemplateTests(unittest.TestCase):
    def test_no_two_content_rows_share_an_english(self) -> None:
        """VVFP Translations.dll keeps one translation per English (the first row), so the template offers one."""
        for game in GAMES:
            with self.subTest(game=game):
                offered, dropped = _offered(game)
                seen: dict[str, str] = {}
                for entry in offered:
                    if entry.get("route") == "key" or entry["stem"].startswith("patch/"):
                        continue
                    self.assertNotIn(vt.content_key(entry["english"]), seen,
                                     f"{entry['stem']} repeats {seen.get(entry['english'])}")
                    seen[vt.content_key(entry["english"])] = entry["stem"]
                self.assertGreater(len(offered), 500)
                self.assertGreater(len(dropped), 100)

    def test_a_left_out_row_is_still_translated_by_the_row_that_stays(self) -> None:
        for game in GAMES:
            with self.subTest(game=game):
                offered, dropped = _offered(game)
                english = {vt.content_key(e["english"]) for e in offered}
                for entry in dropped:
                    self.assertIn(vt.content_key(entry["english"]), english, entry["stem"])

    def test_key_and_patch_rows_are_never_left_out(self) -> None:
        for game in GAMES:
            offered, dropped = _offered(game)
            for entry in dropped:
                self.assertFalse(entry.get("route") == "key" or entry["stem"].startswith("patch/"), entry["stem"])

    def test_the_template_is_the_same_filter(self) -> None:
        """vv_translations.template_rows uses content_shadowed on the patcher rows, in the file's order."""
        source = (ROOT / "src" / "vv_translations.py").read_text(encoding="utf-8")
        self.assertIn("if content_shadowed(entry, taken):", source)


def _offered(game: int) -> tuple[list, list]:
    from translations_sentinels import patcher_rows_of_template   # noqa: PLC0415
    return patcher_rows_of_template(game)


class DrawPathTests(unittest.TestCase):
    """The routines a patch's text reaches the screen through offer it to the translations."""

    def test_the_text_routines_the_unicode_text_companion_hooks_offer_their_text(self) -> None:
        source = (ROOT / "native" / "vvfp_unicode_text" / "text_hooks.inc").read_text(encoding="utf-8")
        self.assertIn('GetProcAddress(m, "VvfpTranslateText")', source)
        for hook, argument in (("width_hook", "s"), ("draw_hook", "s"), ("linefit_hook", "src"),
                               ("justify_hook", "text")):
            with self.subTest(hook=hook):
                start = source.index(f" {hook}(")
                end = source.index("\n}\n", start)
                self.assertIn(f"vt_source({argument})", source[start:end])

    def test_the_dialog_hook_translates_windows_as_they_open_and_when_their_text_is_set(self) -> None:
        source = (ROOT / "native" / "vvfp_translations" / "vvfp_translations.c").read_text(encoding="utf-8")
        hook = source[source.index("static LRESULT CALLBACK tr_window_hook"):]
        hook = hook[:hook.index("\n}\n")]
        for token in ("case WM_INITDIALOG:", "tr_translate_window(m->hwnd)", "EnumChildWindows(m->hwnd, tr_child, 0)",
                      "case WM_SETTEXT:", "case LB_ADDSTRING:", "case CB_ADDSTRING:"):
            self.assertIn(token, hook)
        self.assertIn("SetWindowsHookExW(WH_CALLWNDPROCRET, tr_window_hook", source)

    def test_a_companion_looks_a_key_up_with_the_stem_and_english_of_its_row(self) -> None:
        rows = rows_by_stem()
        for stem, english in scan.key_call_stems().items():
            if english is None:
                continue
            with self.subTest(stem=stem):
                self.assertEqual(rows[stem]["english"], english)

    def test_a_key_row_is_kept_out_of_the_content_map_and_the_most_specific_pattern_wins(self) -> None:
        source = (ROOT / "native" / "vvfp_translations" / "vvfp_translations.c").read_text(encoding="utf-8")
        self.assertIn("if (!tr_key_only(stem)) {\n                    tr_map_add(", source)
        self.assertIn("literal > best_literal", source)
        stems = (ROOT / "native" / "vvfp_translations" / "tr_key_stems.inc").read_text(encoding="utf-8")
        for stem in scan.key_call_stems():
            self.assertIn(f'"{stem}"', stems)

    def test_every_dll_lookup_checks_the_row_by_stem_and_hash(self) -> None:
        source = (ROOT / "native" / "vvfp_translations" / "vvfp_translations.c").read_text(encoding="utf-8")
        for export in ("VvfpTranslateKey(", "VvfpTranslateKeyText("):
            body = source[source.index(f"__stdcall {export}"):]
            body = body[:body.index("\n}\n")]
            self.assertIn("tr_lookup(g_keys", body)
            self.assertIn("tr_hash_cp1252", body)


@unittest.skipUnless(HAVE, SKIP)
class SentinelTests(unittest.TestCase):
    """Each game: every offered patch text translated to a unique sentinel; the sentinel is what comes back."""

    results: dict = {}

    @classmethod
    def setUpClass(cls) -> None:
        cls.exes = {n: stock_exe(n).read_bytes() for n in GAMES}

    def run_game(self, game: int):
        from translations_sentinels import prove   # noqa: PLC0415
        exe_path = stock_exe(game)
        english = set(vt.game_english(game, exe_path, exe_path.parent / "Assets" / "sm.xml").values())
        return prove(game, self.exes[game], english)

    def check(self, game: int) -> None:
        run = self.run_game(game)
        self.assertEqual(run.active, 1, "the sentinel file was not used")
        self.assertGreater(len(run.results), 500)
        wrong = [r for r in run.unproven() if r.why not in UNPROVEN_REASONS]
        listed = "\n".join(f"{r.route} {r.stem}: {r.why} (wanted {r.sentinel!r}, got {r.got!r})" for r in wrong[:30])
        self.assertEqual(wrong, [], f"{len(wrong)} patch texts did not show their own sentinel:\n{listed}")
        routes = {r.route for r in run.results if r.status == "proven"}
        self.assertLessEqual({"key", "content"}, routes)
        # Every sentinel is unique, so a text can only have shown its own.
        self.assertEqual(len({r.sentinel for r in run.results}), len(run.results))

    def test_vv1(self) -> None:
        self.check(1)

    def test_vv2(self) -> None:
        self.check(2)

    def test_vv3(self) -> None:
        self.check(3)

    def test_vv4(self) -> None:
        self.check(4)

    def test_vv5(self) -> None:
        self.check(5)


@unittest.skipUnless(HAVE, SKIP)
class PatchedSlotTests(unittest.TestCase):
    """A patch that rewrites one of the game's own strings in place (A New Home's table/319, /21, /15 and /3,
    data/vv1_misc_text_fixes_feature.json) keeps the game's slot, but its translation is a row of its own: the
    key's hash is the hash of the PATCHED English, so the translation of the stock sentence never shows on the
    patched text, and the patched text's translation never shows on an unpatched game."""

    def test_the_patched_text_has_its_own_translation_not_the_stock_ones(self) -> None:
        from translations_emulation import Game, TITLES   # noqa: PLC0415
        import vv_translation_format as fmt                # noqa: PLC0415

        exe_path = stock_exe(1)
        exe = exe_path.read_bytes()
        stock = vt.game_english(1, exe_path, exe_path.parent / "Assets" / "sm.xml")
        listed = json.loads((ROOT / "data" / "translations" / "exe_patch_strings.json").read_text(encoding="utf-8"))
        slots = [t for t in listed["texts"] if t["covered_by"].startswith("table/")]
        self.assertEqual(len(slots), 4)
        for patched in (False, True):
            rows = []
            for t in slots:
                ident = t["covered_by"]
                source, _slash, number = ident.partition("/")
                rows.append(fmt.Row(fmt.make_key(source, number, stock[ident]), stock[ident], f"STOCK{number}"))
                rows.append(fmt.Row(fmt.make_key(source, number, t["english"]), t["english"], f"PATCHED{number}"))
            tf = fmt.template_file(rows, TITLES[1], "Sentinel", "zz")
            for prepared, source_row in zip(tf.rows, rows):
                prepared.translation = source_row.translation
            g = Game(1, exe, b"\xef\xbb\xbf" + fmt.dumps(tf).encode("utf-8"))
            if patched:
                for t in slots:
                    g.p.write(int(t["va"], 16), t["english"].encode("cp1252") + bytes([0]))
            g.p.call(g.p.exports["VvfpStartup"], [1, 0], limit=3_000_000_000)
            self.assertEqual(g.active(), 1)
            for t in slots:
                number = t["covered_by"].partition("/")[2]
                lang = g.p.alloc(4)
                shown = g.raw(g.p.call(0x433880, [int(number)], ecx=lang)).decode("cp1252")
                with self.subTest(patched=patched, slot=t["covered_by"]):
                    self.assertEqual(shown, ("PATCHED" if patched else "STOCK") + number)
            del g


@unittest.skipUnless(HAVE, SKIP)
class ContentMapTests(unittest.TestCase):
    """What the sentinel run found in the content map (A New Home's DLL run; the rules are the DLL's, all games)."""

    def start(self, rows):
        from translations_emulation import Game, TITLES   # noqa: PLC0415
        import vv_translation_format as fmt                # noqa: PLC0415

        tf = fmt.template_file([fmt.Row(fmt.make_key(s, i, e), e, tr) for s, i, e, tr in rows], TITLES[1], "Sentinel", "zz")
        for prepared, (_s, _i, _e, tr) in zip(tf.rows, rows):
            prepared.translation = tr
        g = Game(1, stock_exe(1).read_bytes(), b"\xef\xbb\xbf" + fmt.dumps(tf).encode("utf-8"))
        g.p.call(g.p.exports["VvfpStartup"], [1, 0], limit=3_000_000_000)
        self.assertEqual(g.active(), 1)
        return g

    def key(self, g, stem: str, english: str) -> bytes:
        def cstr(text: bytes) -> int:
            at = g.p.alloc(len(text) + 1)
            g.p.write(at, text + bytes([0]))
            return at
        return g.raw(g.p.export("VvfpTranslateKey", cstr(stem.encode()), cstr(english.encode("cp1252")), 200))

    def test_a_row_asked_for_by_key_never_translates_other_texts(self) -> None:
        g = self.start([
            ("vvfp.parentage", "vv1_parentage.Vv1ParentageDrawPortrait.s0", "%s of %s", "KEYPORTRAIT %s %s"),
            ("vvfp.parentage", "vv1_parentage.Vv1ParentageDrawPortrait.s1", "Son", "KEYSON"),
            ("vvfp.story", "story_custom_ui.ui_read_main.s0", "Type an amount of food from 1 to %d.", "CONTENT %d"),
        ])
        # By key the key rows answer ...
        self.assertEqual(self.key(g, "vvfp.parentage/vv1_parentage.Vv1ParentageDrawPortrait.s1", "Son"), b"KEYSON")
        # ... and the text shown by the game or a dialog is found only by the content row.
        self.assertEqual(g.translate(b"Type an amount of food from 1 to 7."), b"CONTENT 7")
        self.assertEqual(g.translate(b"Son"), b"Son")                      # not the key row's: it is not content
        self.assertEqual(g.translate(b"Mother of Zed"), b"Mother of Zed")   # "%s of %s" is not a catch-all

    def test_the_most_specific_pattern_wins_whatever_the_order(self) -> None:
        rows = [
            ("vvfp.story", "a.general", "Each villager the game checks: %s.", "GENERAL %s"),
            ("vvfp.story", "a.specific", "Each villager the game checks: %s. If none is left, it ends.", "SPECIFIC %s"),
        ]
        for order in (rows, rows[::-1]):
            g = self.start(order)
            self.assertEqual(g.translate(b"Each villager the game checks: Zed."), b"GENERAL Zed")
            self.assertEqual(g.translate(b"Each villager the game checks: Zed. If none is left, it ends."),
                             b"SPECIFIC Zed")
            del g


class MigrateShadowedTests(unittest.TestCase):
    """A translation on a row the template now leaves out is not lost (Codex, PR 693)."""

    def setUp(self) -> None:
        import vv_translation_format as fmt   # noqa: PLC0415
        self.fmt = fmt
        self.s, self.d = "vvfp/a.s6", "vvfp/a.s6.2"
        self.rows = [fmt.Row(fmt.make_key("vvfp", "a.s6", "Origins Upgrades"), "Origins Upgrades", ""),
                     fmt.Row(fmt.make_key("vvfp", "a.s6.2", "Origins Upgrades"), "Origins Upgrades", "")]
        self.shadows = {self.rows[1].key: self.rows[0].key}

    def file(self, survivor: str, duplicate: str):
        tf = self.fmt.template_file(self.rows, "T", "L", "zz")
        tf.rows[0].translation, tf.rows[1].translation = survivor, duplicate
        return tf

    def test_blank_survivor_takes_the_duplicates_translation(self) -> None:
        tf = self.file("", "Mises a niveau")
        self.assertEqual(vt.migrate_shadowed(tf, self.shadows), [])
        new, _status = self.fmt.update(tf, [self.rows[0]])
        self.assertEqual(new.rows[0].translation, "Mises a niveau")

    def test_both_translated_keeps_the_survivor_and_warns(self) -> None:
        tf = self.file("Garde", "Autre")
        warnings = vt.migrate_shadowed(tf, self.shadows)
        self.assertEqual(len(warnings), 1)
        new, _status = self.fmt.update(tf, [self.rows[0]])
        self.assertEqual(new.rows[0].translation, "Garde")

    def test_same_translation_and_blank_duplicate_are_quiet(self) -> None:
        for survivor, duplicate in (("Meme", "Meme"), ("Garde", ""), ("", "")):
            tf = self.file(survivor, duplicate)
            self.assertEqual(vt.migrate_shadowed(tf, self.shadows), [])
            new, _status = self.fmt.update(tf, [self.rows[0]])
            self.assertEqual(new.rows[0].translation, survivor)

    @unittest.skipUnless(HAVE, SKIP)
    def test_the_template_names_the_survivor_of_every_left_out_row(self) -> None:
        exe = stock_exe(1)
        rows = vt.template_rows(1, exe=exe)
        keys = {r.row.key for r in rows}
        self.assertGreater(len(rows.shadows), 100)
        for removed, survivor in rows.shadows.items():
            self.assertNotIn(removed, keys)
            self.assertIn(survivor, keys)


if __name__ == "__main__":
    unittest.main()
