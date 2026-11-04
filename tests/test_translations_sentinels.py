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
                # vt_source(text, font, scale): the game's own text goes first (the font and scale fit whole
                # long names to their room, docs/UNICODE_SPEC.md row 3)
                self.assertRegex(source[start:end], rf"\bvt_source\({argument}(, [^)]*)?\)")

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


# ---- the Story buttons, price lines and Pick Island Event list (live, French TEST, 2026-11-04) ----------------
#
# The Tech menu's three story buttons showed "Custom Island Event (0 points de technologie)...": the price
# wrapper was translated by the dialog hook by content, but the name it carried was copied in English; every
# zeroed price line ("0 tech points") and the Pick Island Event list rows ("Day of Honor (normally not possible
# right now)") stayed English the same way.  Each part is now asked for by its own key, and these tests put a
# sentinel in each row and read the button, the price line and the list row back.

SHARED = ROOT / "native" / "shared"

# The stand-in "VVFP Translations.dll": a row's sentinel, only for its own stem AND its own English (the real
# DLL checks the English's hash).  UTF-8, as the real one answers with a Unicode companion in.
STAND_IN = r'''
#include <windows.h>
#include <string.h>
static const char *const ROWS[][3] = {
    { "vvfp.storybridge/story_bridge.vvfp_story_add_event_buttons.s0", "Custom Island Event",
      "ZC \xc3\x89v\xc3\xa9nement de l'\xc3\xaele personnalis\xc3\xa9, un nom bien plus long que l'anglais" },
    { "vvfp.storybridge/story_bridge.vvfp_story_add_event_buttons.s1", "Pick Island Event",
      "ZP Choisir un \xc3\xa9v\xc3\xa9nement de l'\xc3\xaele, lui aussi bien plus long" },
    { "vvfp.storybridge/story_bridge.vvfp_story_add_time_skip_button.s0", "Choose Time Skip Amount",
      "ZT Choisir la dur\xc3\xa9" "e du saut dans le temps, encore plus long" },
    { "vvfp.storybridge/story_bridge.vvfp_story_label_priced.s0", "%s (%d,%03d tech points)...",
      "%s (ZW %d %03d points de technologie)..." },
    { "vvfp.storybridge/story_bridge.vvfp_story_label_priced.s1", "%s (%d tech points)...",
      "%s (ZW %d points de technologie)..." },
    { "vvfp.storybridge/story_bridge.vvfp_story_zeroed_text.s0", "0 tech points", "Z0 0 point de technologie" },
    { "vvfp.storybridge/story_bridge.vvfp_story_zeroed_text.s1",
      "OK deducts 0 tech points. Cancel changes nothing.", "Z1 OK d\xc3\xa9" "duit 0 point." },
    { "vvfp.storybridge/story_bridge.vvfp_story_zeroed_text.s2",
      "OK deducts 0 tech points, for the head look too. Cancel changes nothing.", "Z2 OK, la t\xc3\xaate aussi." },
};
__declspec(dllexport) const char *__stdcall VvfpTranslateKey(const char *stem, const char *english,
                                                             unsigned int cap) {
    int i;
    for (i = 0; i < (int)(sizeof ROWS / sizeof ROWS[0]); ++i) {
        if (strcmp(stem, ROWS[i][0]) == 0 && strcmp(english, ROWS[i][1]) == 0
            && (cap == 0 || strlen(ROWS[i][2]) + 1 <= cap)) {
            return ROWS[i][2];
        }
    }
    return english;
}
__declspec(dllexport) int __stdcall VvfpTranslateKeyText(const char *stem, const char *english, const char *text,
                                                         char *out, unsigned int cap) {
    (void)stem; (void)english; (void)text; (void)out; (void)cap;
    return 0;
}
'''

# native/shared/story_bridge.h in a real dialog (the Origins menu's Cancel and two of its price lines), the Story
# DLL stood in for: free (0) or charged at `price`.  Run() returns each control's text (UTF-8), and for a button
# whether its text fits inside it.
UNDER_TEST = r'''
#include "story_bridge.h"
static int t_price, t_free;
static int __stdcall t_slot(void) { return 1; }
static int __stdcall t_step(int years) { return years; }
static int __stdcall t_one(void) { return 1; }
static const vvfp_story_host *vvfp_story_host_table(void) {
    static const vvfp_story_host host = { sizeof(vvfp_story_host), t_slot, NULL, NULL, NULL, t_step, t_one, t_one,
                                          NULL };
    return &host;
}
static int __stdcall t_offered(int game) { (void)game; return 1; }
static int __stdcall t_active(int game) { (void)game; return t_free; }
static int __stdcall t_price_of(int game) { (void)game; return t_price; }
static int __stdcall t_command(int game, HWND owner) { (void)game; (void)owner; return 0; }

static WORD *t_text(WORD *p, const wchar_t *s) {
    do { *p++ = (WORD)*s; } while (*s++);
    return p;
}
static WORD *t_item(WORD *p, DWORD style, short x, short y, short cx, short cy, WORD id, WORD cls,
                    const wchar_t *text) {
    DLGITEMTEMPLATE *item = (DLGITEMTEMPLATE *)(((ULONG_PTR)p + 3) & ~(ULONG_PTR)3);
    item->style = style | WS_CHILD | WS_VISIBLE;
    item->x = x; item->y = y; item->cx = cx; item->cy = cy; item->id = id;
    p = (WORD *)(item + 1);
    *p++ = 0xFFFF; *p++ = cls;
    p = t_text(p, text);
    *p++ = 0;
    return p;
}
static INT_PTR CALLBACK t_proc(HWND w, UINT m, WPARAM wp, LPARAM lp) {
    (void)w; (void)m; (void)wp; (void)lp;
    return FALSE;
}

__declspec(dllexport) int Run(int price, int free_now, char *out, int cap) {
    static DWORD buffer[1024];
    static const int ids[] = { VVFP_STORY_CUSTOM_ID, VVFP_STORY_PICK_ID, VVFP_STORY_TIME_SKIP_ID, 100, 101 };
    DLGTEMPLATE *t = (DLGTEMPLATE *)buffer;
    WORD *p;
    HWND dialog;
    int i, n = 0;
    t_price = price; t_free = free_now;
    vvfp_story_state = 1;
    vvfp_story_active = t_active; vvfp_story_installed = t_offered;
    vvfp_story_event_price = t_price_of; vvfp_story_time_skip_price = t_price_of;
    vvfp_story_time_skip = t_command; vvfp_story_pick = t_command; vvfp_story_custom = t_command;
    memset(buffer, 0, sizeof buffer);
    t->style = WS_POPUP | WS_CAPTION | DS_SETFONT; t->cdit = 3; t->cx = 560; t->cy = 220;
    p = (WORD *)(t + 1);
    *p++ = 0; *p++ = 0;
    p = t_text(p, L"Origins Upgrades");
    *p++ = 8;
    p = t_text(p, L"MS Shell Dlg");
    p = t_item(p, BS_PUSHBUTTON, 500, 200, 50, 14, IDCANCEL, 0x0080, L"Cancel");
    p = t_item(p, SS_LEFT, 40, 19, 195, 9, 100, 0x0082, L"50,000 tech points");
    p = t_item(p, SS_CENTER, 16, 40, 332, 9, 101, 0x0082, L"OK deducts 5,000 tech points. Cancel changes nothing.");
    dialog = CreateDialogIndirectParamW(GetModuleHandleW(NULL), t, NULL, t_proc, 0);
    if (dialog == NULL) {
        return -1;
    }
    vvfp_story_relabel(5, dialog);
    vvfp_story_add_pick_button(5, dialog);
    for (i = 0; i < (int)(sizeof ids / sizeof ids[0]); ++i) {
        HWND child = GetDlgItem(dialog, ids[i]);
        WCHAR wide[512];
        int k = child != NULL ? GetWindowTextW(child, wide, 512) : 0;
        n += WideCharToMultiByte(CP_UTF8, 0, wide, k, out + n, cap - n - 8, NULL, NULL);
        if (ids[i] >= VVFP_STORY_PICK_ID && child != NULL) {
            RECT rc;
            SIZE size = { 0, 0 };
            HDC dc = GetDC(child);
            HGDIOBJ old = SelectObject(dc, (HGDIOBJ)SendMessageW(child, WM_GETFONT, 0, 0));
            GetTextExtentPoint32W(dc, wide, k, &size);
            SelectObject(dc, old);
            ReleaseDC(child, dc);
            GetClientRect(child, &rc);
            out[n++] = '\t';
            out[n++] = size.cx < rc.right - rc.left ? 'F' : 'C';
        }
        out[n++] = '\n';
    }
    out[n] = 0;
    DestroyWindow(dialog);
    return n;
}

__declspec(dllexport) int Wide(const char *text, wchar_t *out, int cap) {
    return vvfp_to_wide(text, out, cap);
}
'''


def _vcvars() -> Path | None:
    import struct as _struct                                        # noqa: PLC0415
    name = "vcvars32.bat" if _struct.calcsize("P") == 4 else "vcvars64.bat"
    found = None
    for base in (r"C:\Program Files\Microsoft Visual Studio", r"C:\Program Files (x86)\Microsoft Visual Studio"):
        for candidate in sorted(Path(base).glob(f"*/*/VC/Auxiliary/Build/{name}")):
            found = candidate
    return found


def _cl(folder: Path, source: str, name: str, out: str) -> Path | None:
    import subprocess                                               # noqa: PLC0415
    vcvars = _vcvars()
    if vcvars is None:
        return None
    (folder / name).write_text(source, encoding="utf-8")
    command = (f'call "{vcvars}" >nul && cl /nologo /LD /O2 /W3 /I "{SHARED}" "{name}" /Fe:"{out}" '
               f'/link /NOLOGO user32.lib gdi32.lib shell32.lib')
    result = subprocess.run(command, shell=True, cwd=folder, capture_output=True, text=True)
    if result.returncode != 0 or not (folder / out).is_file():
        raise AssertionError(f"{name} did not build:\n{result.stdout[-3000:]}{result.stderr[-2000:]}")
    return folder / out


class StoryButtonTests(unittest.TestCase):
    """The three story buttons and the zeroed price lines of an Origins menu show their own rows' translations
    (native/shared/story_bridge.h, in all five Origins companions), and a longer label still fits its button."""

    @classmethod
    def setUpClass(cls) -> None:
        import ctypes                                               # noqa: PLC0415
        import shutil                                               # noqa: PLC0415
        import tempfile                                             # noqa: PLC0415
        cls._tmp = tempfile.mkdtemp()
        cls.addClassCleanup(shutil.rmtree, cls._tmp, ignore_errors=True)
        folder = Path(cls._tmp)
        dll = _cl(folder, UNDER_TEST, "t.c", "t.dll")
        stand_in = _cl(folder, STAND_IN, "s.c", "VVFP Translations.dll")
        if dll is None or stand_in is None:
            raise unittest.SkipTest("needs the Visual C++ tools")
        cls.ctypes = ctypes
        cls.dll = ctypes.CDLL(str(dll))
        cls.dll.Run.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_char_p, ctypes.c_int]
        cls.stand_in = stand_in

    def run_menu(self, price: int, free_now: int) -> list[str]:
        out = self.ctypes.create_string_buffer(8192)
        self.assertGreater(self.dll.Run(price, free_now, out, 8192), 0)
        return out.value.decode("utf-8").split("\n")[:5]

    def test_each_part_shows_its_own_translation_and_fits(self) -> None:
        # Without the translations companion: the English, as before, and it fits.
        english = self.run_menu(0, 1)
        self.assertEqual(english, ["Custom Island Event (0 tech points)...\tF", "Pick Island Event (0 tech points)...\tF",
                                   "Choose Time Skip Amount (0 tech points)...\tF", "0 tech points",
                                   "OK deducts 0 tech points. Cancel changes nothing."])
        self.ctypes.CDLL(str(self.stand_in))        # loaded, as the game loads "VVFP Translations.dll"
        free = self.run_menu(0, 1)
        self.assertEqual(free, [
            "ZC Événement de l'île personnalisé, un nom bien plus long que l'anglais (ZW 0 points de technologie)...\tF",
            "ZP Choisir un événement de l'île, lui aussi bien plus long (ZW 0 points de technologie)...\tF",
            "ZT Choisir la durée du saut dans le temps, encore plus long (ZW 0 points de technologie)...\tF",
            "Z0 0 point de technologie",
            "Z1 OK déduit 0 point."])
        # Charged ("cost Tech Points"): the price row with the thousands, and the dialog's own real prices kept.
        charged = self.run_menu(30000, 0)
        self.assertEqual(charged[:3], [
            "ZC Événement de l'île personnalisé, un nom bien plus long que l'anglais (ZW 30 000 points de technologie)...\tF",
            "ZP Choisir un événement de l'île, lui aussi bien plus long (ZW 30 000 points de technologie)...\tF",
            "ZT Choisir la durée du saut dans le temps, encore plus long (ZW 30 000 points de technologie)...\tF"])
        self.assertEqual(charged[3:], ["50,000 tech points", "OK deducts 5,000 tech points. Cancel changes nothing."])

    def test_a_translated_message_is_shown_as_utf16(self) -> None:
        """vvfp_message_box (native/shared/vvfp_translate.h) reads a text the patcher's way -- valid UTF-8, else
        Windows-1252 -- into UTF-16 for MessageBoxW, so a translated event name is never shown in the ANSI code page
        (Codex, PR 703: "La Fête d'Isola" read as "La FÃªte d'Isola").  Every Pick Island Event box that shows a
        label_of name uses it."""
        out = self.ctypes.create_unicode_buffer(64)
        self.dll.Wide.argtypes = [self.ctypes.c_char_p, self.ctypes.c_wchar_p, self.ctypes.c_int]
        for raw in ("La Fête d'Isola".encode("utf-8"), "La Fête d'Isola".encode("cp1252")):
            self.dll.Wide(raw, out, 64)
            self.assertEqual(out.value, "La Fête d'Isola")
        header = (SHARED / "vvfp_translate.h").read_text(encoding="utf-8")
        self.assertIn("return MessageBoxW(owner, wide_text, wide_caption, type);", header)
        story = (ROOT / "native" / "vvfp_story_upgrades" / "vvfp_story_upgrades.c").read_text(encoding="utf-8")
        body = story[story.index("static int story_pick_island_event(int game, HWND owner) {"):]
        body = body[:body.index("\n}\n")]
        self.assertNotRegex(body, r"MessageBoxA\(owner, message,")
        self.assertEqual(body.count("vvfp_message_box(owner, message,"), 3)

    def test_every_part_is_asked_for_by_its_own_stem_and_english(self) -> None:
        rows = rows_by_stem()
        keys = scan.key_call_stems()
        for stem, english in (
                ("vvfp.storybridge/story_bridge.vvfp_story_add_event_buttons.s0", "Custom Island Event"),
                ("vvfp.storybridge/story_bridge.vvfp_story_add_event_buttons.s1", "Pick Island Event"),
                ("vvfp.storybridge/story_bridge.vvfp_story_add_time_skip_button.s0", "Choose Time Skip Amount"),
                ("vvfp.storybridge/story_bridge.vvfp_story_label_priced.s0", "%s (%d,%03d tech points)..."),
                ("vvfp.storybridge/story_bridge.vvfp_story_label_priced.s1", "%s (%d tech points)..."),
                ("vvfp.storybridge/story_bridge.vvfp_story_zeroed_text.s0", "0 tech points"),
                ("vvfp.storybridge/story_bridge.vvfp_story_zeroed_text.s1",
                 "OK deducts 0 tech points. Cancel changes nothing."),
                ("vvfp.storybridge/story_bridge.vvfp_story_zeroed_text.s2",
                 "OK deducts 0 tech points, for the head look too. Cancel changes nothing."),
                ("vvfp.story/story_outcomes_ui.chooser_dialog.s3", " (never happens in the original game)"),
                ("vvfp.story/story_outcomes_ui.chooser_dialog.s4", " (normally not possible right now)"),
                ("vvfp.story/story_outcomes_ui.chooser_dialog.s5", " - not possible right now")):
            with self.subTest(stem=stem):
                self.assertIn(stem, keys)
                self.assertEqual(rows[stem]["english"], english)
                self.assertEqual(rows[stem].get("route"), "key")
        for stem, row in rows.items():
            if re.match(r"vvfp\.story/story_tables\.VV[1-5]_EVENTS\.\d+\.(title|variant)$", stem):
                self.assertEqual(row.get("route"), "key", stem)


try:
    from test_story_outcomes import SCRATCH as STORY_SCRATCH, TABLES as STORY_TABLES, Game as StoryGame, \
        _Event as StoryEvent, emulated as story_emulated, have_stock
except ImportError:                                                 # pragma: no cover - environment dependent
    story_emulated = unittest.skip("the Story emulator is not importable")


@story_emulated
class PickListTests(unittest.TestCase):
    """Pick Island Event (story_outcomes_ui.inc): each list row's name, variant and mark, the description pane and
    every settings row are their own rows' translations, in every game -- nothing English copied around them."""

    def test_every_list_row_description_and_setting_is_its_rows_translations(self) -> None:
        import vv_translation_format as fmt                          # noqa: PLC0415
        rows = rows_by_stem()
        ran = 0
        for n in GAMES:
            game = f"vv{n}"
            if not have_stock(game):
                continue
            with self.subTest(game=game):
                ran += 1
                g = StoryGame(game)
                p = g.proc
                sentinels: dict[str, int] = {}

                def sentinel(stem: str) -> str:
                    """Z<id>, with the row's own conversions, so a format still takes its values."""
                    return " ".join(["Z" + stem.rsplit("/", 1)[1]] + fmt.printf_conversions(rows[stem]["english"]))

                def translate_key(q):
                    stem, english = q.cstring(q.arg(0)), q.arg(1)
                    row = rows.get(stem)
                    if row is None or row["english"].encode("cp1252") != q.cstring(english).encode("latin-1"):
                        return english, 12
                    if stem not in sentinels:
                        sentinels[stem] = p.alloc(256)
                        p.write(sentinels[stem], sentinel(stem).encode() + b"\0")
                    return sentinels[stem], 12

                key_fn, text_fn = p.alloc(16), p.alloc(16)
                p.stub(key_fn, translate_key)
                p.stub(text_fn, lambda q: (0, 20))
                p.api_handlers["GetModuleHandleW"] = lambda q: (
                    0x72000000 if q.arg(0) and q.wstring(q.arg(0)) == "VVFP Translations.dll"
                    else (0x400000 if q.arg(0) == 0 else 0), 4)
                p.api_handlers["GetProcAddress"] = lambda q: (
                    {"VvfpTranslateKey": key_fn, "VvfpTranslateKeyText": text_fn}.get(q.cstring(q.arg(1)), 0), 8)
                if game in STORY_TABLES:
                    for slot in range(1, 58):
                        event = StoryEvent(g, slot)
                        p.stub(event.code + 1, lambda q: (1, 0))
                count = p.export("VvfpStoryProbeChooserOpen", n, 0)
                self.assertGreater(count, 30)
                out = STORY_SCRATCH + 0x3000
                t = f"story_tables.VV{n}_EVENTS"
                ui = "story_outcomes_ui"
                for index in range(count):
                    possible = p.export("VvfpStoryProbeChooserText", index, 0, out, 1200)
                    # the list row
                    p.export("VvfpStoryProbeChooserText", index, 0xFFFFFFFF, out, 1200)
                    want = f"Z{t}.{index}.title"
                    if f"vvfp.story/{t}.{index}.variant" in rows:
                        want += f" (Z{t}.{index}.variant)"
                    marks = {0: [f"Z{ui}.chooser_dialog.s5"], 1: [""],
                             2: [f"Z{ui}.chooser_dialog.s3", f"Z{ui}.chooser_dialog.s4"]}[possible]
                    self.assertIn(p.cstring(out), [want + m for m in marks], f"list row {index}")
                    # the description pane
                    p.export("VvfpStoryProbeChooserWords", index, 0, 0, out, 1200)
                    description = f"Z{t}.{index}.description"
                    if possible == 1:
                        wants = [description]
                    elif possible == 2:
                        wants = [f"{description}\r\n\r\nZ{ui}.chooser_description.s0"] + [
                            f"{description}\r\n\r\nZ{s.rsplit('/', 1)[1]}" for s in rows
                            if s.startswith(f"vvfp.story/story_tables.VV{n}_OC_EVENTS.") and s.endswith(".dead_note")]
                    else:
                        wants = [f"Z{ui}.chooser_description.s1 {description} Z{t}.{index}.requires"]
                    self.assertIn(p.cstring(out), wants, f"description {index}")
                    # every settings row (all Random): only sentinels, the separators and numbers
                    for row in range(24):
                        if not p.export("VvfpStoryProbeChooserText", index, 4 + row, out, 1200):
                            break
                        shown = p.cstring(out)
                        self.assertRegex(shown, r"^(?:Z[\w.\-]+|[\s:%()\d\-,]+)+$", f"event {index} row {row}")
        if not ran:
            self.skipTest("needs the stock executables (inputs/vvN-stock-copy)")


class BuyPromptTests(unittest.TestCase):
    """Every "Do you want to buy ..." prompt of the five Origins companions and the Story companion is asked for by
    its own key, the names it shows too, and every box is shown as UTF-16 (vvfp_message_box)."""

    SOURCES = ("native/vv1_origins_icons/vv1_origins_icons.c", "native/vv2_origins_icons/vv2_origins_icons.c",
               "native/vv3_full_mastery_candidate/vv3_full_mastery_candidate.c",
               "native/vv4_origins_icons/vv4_origins_icons.c", "native/vv5_task9_origins/vv5_task9_origins.c",
               "native/vvfp_story_upgrades/vvfp_story_upgrades.c")

    def test_every_buy_prompt_is_asked_for_by_key(self) -> None:
        rows = rows_by_stem()
        story = ROOT / "native" / "vvfp_story_upgrades"
        for path in [ROOT / s for s in self.SOURCES] + sorted(story.glob("*.inc")):
            source = scan._strip_comments(path.read_text(encoding="utf-8"))
            for m in re.finditer(r'"Do you want to buy', source):
                with self.subTest(source=path.name, at=source.count("\n", 0, m.start()) + 1):
                    before = source[max(0, m.start() - 200):m.start()]
                    call = re.search(r'vvfp_tr\("([^"]+)",\s*$', before)
                    self.assertIsNotNone(call, "a buy prompt passed around its translation")
                    line_end = source.index('",', m.start())
                    english = scan._decode(source[m.start() + 1:line_end], False)
                    self.assertEqual(rows[call.group(1)]["english"], english)

    def test_the_names_the_prompts_show_are_asked_for_by_key(self) -> None:
        for relative, function in (("vv1_origins_icons/vv1_origins_icons.c", "vv1_tech_row_name"),
                                   ("vv1_origins_icons/vv1_origins_icons.c", "vv1_detail_row_name"),
                                   ("vv1_origins_icons/vv1_origins_icons.c", "vv_prefs_name"),
                                   ("vv1_origins_icons/vv1_origins_icons.c", "vv1_speed_name"),
                                   ("vv2_origins_icons/vv2_origins_icons.c", "vv2_action_name"),
                                   ("vv2_origins_icons/vv2_origins_icons.c", "vv2_speed_name"),
                                   ("vv3_full_mastery_candidate/vv3_full_mastery_candidate.c", "vv3_speed_name"),
                                   ("vv4_origins_icons/vv4_origins_icons.c", "vv4_speed_name"),
                                   ("vv5_task9_origins/vv5_task9_origins.c", "action_name"),
                                   ("vv5_task9_origins/vv5_task9_origins.c", "vv5_speed_name")):
            with self.subTest(function=function):
                source = (ROOT / "native" / relative).read_text(encoding="utf-8")
                body = source[source.index(f"static const char *{function}("):]
                body = body[:body.index("\n}\n")]
                self.assertNotRegex(body, r'return "', "a name returned in English")
                self.assertGreaterEqual(body.count("return vvfp_tr("), 3)
        vv3 = (ROOT / "native/vv3_full_mastery_candidate/vv3_full_mastery_candidate.c").read_text(encoding="utf-8")
        self.assertIn("name = vvfp_tr(stem, s_villager_menu ? detail_names[row] : tech_names[row], 0);", vv3)
        vv4 = (ROOT / "native/vv4_origins_icons/vv4_origins_icons.c").read_text(encoding="utf-8")
        self.assertIn("return vvfp_tr(stem, g_tech_names[row], 0);", vv4)
        self.assertNotIn("vvfp_story_text(4,", vv4, "a zeroed English prompt")

    def test_every_box_is_shown_as_utf16(self) -> None:
        for relative in self.SOURCES:
            with self.subTest(source=relative):
                source = (ROOT / relative).read_text(encoding="utf-8")
                if "vv2_origins_icons" in relative:   # it compiles The Lost Children's code in first
                    self.assertIn('#include "../vv1_origins_icons/vv1_origins_icons.c"', source)
                    continue
                self.assertIn("#define MessageBoxA vvfp_message_box", source)

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

    def test_integer_conversions_become_the_survivors(self) -> None:
        fmt = self.fmt
        for survivor_en, removed_en, tr, want in (
                ("Set %d %s Job Preferences.", "Set %u %s Job Preferences.", "Defini %u %s", "Defini %d %s"),
                ("Set %u %s Job Preferences.", "Set %d %s Job Preferences.", "Defini %d %s 100%%", "Defini %u %s 100%%")):
            rows = [fmt.Row(fmt.make_key("vvfp", "s", survivor_en), survivor_en, ""),
                    fmt.Row(fmt.make_key("vvfp", "r", removed_en), removed_en, tr)]
            tf = fmt.template_file(rows, "T", "L", "zz")
            tf.rows[1].translation = tr
            self.assertEqual(vt.migrate_shadowed(tf, {rows[1].key: rows[0].key}), [])
            new, _status = fmt.update(tf, [rows[0]])
            self.assertEqual(new.rows[0].translation, want)
            self.assertEqual([i for i in fmt.check_row(survivor_en, want) if i.severity == "error"], [])

    def test_a_translation_that_cannot_be_adapted_is_left_and_warned(self) -> None:
        fmt = self.fmt
        s_en, r_en = "Set %d %s Job Preferences.", "Set %u %s Job Preferences."
        rows = [fmt.Row(fmt.make_key("vvfp", "s", s_en), s_en, ""), fmt.Row(fmt.make_key("vvfp", "r", r_en), r_en, "")]
        tf = fmt.template_file(rows, "T", "L", "zz")
        tf.rows[1].translation = "Defini %u"            # one conversion short
        warnings = vt.migrate_shadowed(tf, {rows[1].key: rows[0].key})
        self.assertEqual(len(warnings), 1)
        new, _status = fmt.update(tf, [rows[0]])
        self.assertEqual(new.rows[0].translation, "")

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
