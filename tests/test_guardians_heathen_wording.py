"""New Believers with the Guardians of Isola Rewrite: the patcher's own Heathen words switch to Isolan.

The owner (2026-11-23): "with the Guardians of Isola patch Heathens = Isolans".  The owner's pairs: Heathen ->
Isolan, Heathens -> Isolans, Heathens' -> Isolans', a Heathen -> an Isolan; the people are never "Guardians".

The patcher's own in-game text that names the Heathens goes through one switch, native/shared/isolan_words.h
(vv5_isolan_words), when the rewrite is on (Story Upgrades' cg_guardians_on):
  * Pick Island Event's New Believers events: title, variant, description and what each needs (event_text); a
    title the rewrite itself renames (sm.xml) is shown as the rewrite names it (VV5_GUARDIANS_TITLES);
  * the outcome chooser's New Believers labels (oc_table_text);
  * the Custom Island Event dialog's New Believers statuses, actions, (Unsafe) reasons, status note, "Not in this
    game" note and the target list's role words (ui_w, ce_role);
  * Revive Buried/Disappeared Villagers' Heathen lines and refusals (story_revive.inc);
  * the refusals "the game cures a Heathen at once" (ce_why_word) and "an effect is not one a Heathen may have"
    (cg_bad).

This test scans every "heathen" string literal of those tables, runs the C switch on each (compiled with the
Visual C++ tools; skipped without them) and checks it against the owner's pairs, and checks each table is routed
through the switch.
"""
from __future__ import annotations

import ctypes
import re
import shutil
import struct
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STORY = ROOT / "native" / "vvfp_story_upgrades"
SHARED = ROOT / "native" / "shared"
LITERAL = re.compile(r'"((?:[^"\\\n]|\\.)*)"')


def isolan(text: str) -> str:
    """The owner's pairs, as shared/isolan_words.h applies them (the mirror this test checks the C against)."""
    out = []
    i = 0
    while i < len(text):
        if (i == 0 or not text[i - 1].isalpha()) and text[i:i + 7].lower() == "heathen":
            end = i + 7
            tail = ""
            if text[end:end + 2] == "s'":
                tail = "s'"
            elif text[end:end + 1] == "s":
                tail = "s"
            elif text[end:end + 2] == "'s":
                tail = "'s"
            after = text[end + len(tail):end + len(tail) + 1]
            if not after.isalpha():
                done = "".join(out)
                if len(done) >= 2 and done[-1] == " " and done[-2] in "aA" and (len(done) == 2 or not done[-3].isalpha()):
                    out = [done[:-1], "n "]
                out.append("Isolan" + tail)
                i = end + len(tail)
                continue
        out.append(text[i])
        i += 1
    return "".join(out)


def _literals(path: Path, start: str | None = None, stop: str | None = None) -> list[str]:
    text = path.read_text(encoding="utf-8")
    if start is not None:
        text = text[text.index(start):]
    if stop is not None:
        text = text[:text.index(stop)]
    # comments out
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    text = re.sub(r"//[^\n]*", "", text)
    return [m.group(1) for m in LITERAL.finditer(text)]


def switched_strings() -> list[str]:
    """Every literal holding "heathen" in the tables this switch covers."""
    found: list[str] = []
    tables = STORY / "story_tables.h"
    found += _literals(tables, "static const oc_control VV5_OC_CONTROLS[]")       # the outcome chooser's labels
    found += _literals(tables, "static const story_event VV5_EVENTS[]")            # Pick Island Event
    found += _literals(STORY / "story_c5.inc")                                    # the CIE dialog's tables
    found += _literals(STORY / "story_revive.inc", "static const char *const RV_WHY[][2]",
                       "enum { RV_WHY_WHO")
    for needle in (" - a Heathen", "Faction: Heathen\\r\\n",
                   "\\r\\nComes back as this same person at age 5, a Heathen in the camp.\\r\\n"):
        found.append(needle)
    found.append("the game cures a Heathen at once")
    found.append("an effect is not one a Heathen may have")
    words = [s for s in found if "heathen" in s.lower()]
    # Internal names (exports, files, flags) are not shown to the player.
    return [s for s in dict.fromkeys(words) if not re.match(r"^(Vvfp|VVFP |\.\./|vvfp\.)", s)]


UNDER_TEST = r'''
#include "isolan_words.h"
__declspec(dllexport) int Isolan(const char *in, char *out, int cap) { return vv5_isolan_words(in, out, cap); }
__declspec(dllexport) const char *IsolanIf(int on, const char *in) { return vv5_isolan(on, in); }
'''


def _vcvars() -> Path | None:
    name = "vcvars32.bat" if struct.calcsize("P") == 4 else "vcvars64.bat"
    found = None
    for base in (r"C:\Program Files\Microsoft Visual Studio", r"C:\Program Files (x86)\Microsoft Visual Studio"):
        for candidate in sorted(Path(base).glob(f"*/*/VC/Auxiliary/Build/{name}")):
            found = candidate
    return found


class ThePairs(unittest.TestCase):
    def test_the_owners_pairs(self):
        for before, after in (("Heathen", "Isolan"), ("Heathens", "Isolans"), ("the Heathens' camp", "the Isolans' camp"),
                              ("a Heathen", "an Isolan"), ("A heathen envoy", "An Isolan envoy"),
                              ("a heathen child's toy", "an Isolan child's toy"), ("Heathen: blue", "Isolan: blue"),
                              ("Heathenish", "Heathenish"), ("a Heathenish", "a Heathenish"),
                              ("Becomes a believer", "Becomes a believer")):
            with self.subTest(before=before):
                self.assertEqual(isolan(before), after)

    def test_every_switched_string_comes_out_in_the_isolan_wording(self):
        strings = switched_strings()
        self.assertGreater(len(strings), 40, "the scan found too few strings: the tables moved?")
        for s in strings:
            with self.subTest(text=s):
                out = isolan(s)
                self.assertNotIn("heathen", out.lower())
                self.assertNotIn("guardian", out.lower())
                self.assertNotIn("a Isolan", out)
                self.assertNotIn("A Isolan", out)


class TheCSwitch(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.mkdtemp()
        folder = Path(cls._tmp)
        vcvars = _vcvars()
        if vcvars is None:
            raise unittest.SkipTest("needs the Visual C++ tools")
        (folder / "t.c").write_text(UNDER_TEST, encoding="utf-8")
        command = (f'call "{vcvars}" >nul && cl /nologo /LD /O2 /I "{SHARED}" t.c /Fe:t.dll /link /NOLOGO >nul')
        result = subprocess.run(command, shell=True, cwd=folder, capture_output=True, text=True)
        if result.returncode != 0 or not (folder / "t.dll").is_file():
            raise unittest.SkipTest("needs the Visual C++ tools")
        cls.dll = ctypes.CDLL(str(folder / "t.dll"))
        cls.dll.Isolan.restype = ctypes.c_int
        cls.dll.Isolan.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_int]
        cls.dll.IsolanIf.restype = ctypes.c_char_p
        cls.dll.IsolanIf.argtypes = [ctypes.c_int, ctypes.c_char_p]

    @classmethod
    def tearDownClass(cls) -> None:
        cls.dll = None
        shutil.rmtree(cls._tmp, ignore_errors=True)

    def c(self, text: str) -> str:
        out = ctypes.create_string_buffer(4096)
        self.dll.Isolan(text.encode("cp1252"), out, 4096)
        return out.value.decode("cp1252")

    def test_the_c_switch_is_the_owners_pairs_on_every_string(self):
        for s in switched_strings() + ["Heathen", "Heathens' pools", "a heathen", "A Heathen's Prerogative",
                                       "Heathenish", "heathen"]:
            with self.subTest(text=s):
                self.assertEqual(self.c(s), isolan(s))

    def test_without_the_rewrite_nothing_changes(self):
        self.assertEqual(self.dll.IsolanIf(0, b"a Heathen"), b"a Heathen")
        self.assertEqual(self.dll.IsolanIf(1, b"a Heathen"), b"an Isolan")
        self.assertEqual(self.dll.IsolanIf(1, b"Believer"), b"Believer")


class EachTableGoesThroughTheSwitch(unittest.TestCase):
    def source(self, name: str) -> str:
        return (STORY / name).read_text(encoding="utf-8")

    def function(self, name: str, signature: str) -> str:
        text = self.source(name)
        start = text.index(signature)
        return text[start:text.index("\n}\n", start)]

    def test_pick_island_event(self):
        body = self.function("vvfp_story_upgrades.c", "static const char *event_text(")
        self.assertIn("return vv5_words(game, text);", body)
        self.assertIn("VV5_GUARDIANS_TITLES", body)

    def test_the_outcome_chooser(self):
        self.assertIn("return vv5_words(chooser.gid, vvfp_tr(stem, english, cap));",
                      self.function("story_outcomes_ui.inc", "static const char *oc_table_text("))

    def test_the_custom_island_event_dialog(self):
        ui = self.source("story_custom_ui.inc")
        for site in ("ui_combo_add(window, id, ui_w(names[i]), i);", "CE_GROUP_NAMES[group], ui_w(x->label));",
                     "ui_combo_add(window, IDC_SP_FACTION, ui_w(a->statuses[i]), i);",
                     "ui_w(act->label), ui_w(act->unsafe),", "ui_w(ui.a->statuses[c->status])",
                     "ui_w(ui.a->behaviours[c->behaviour].label)", "ui_w(a->omitted)",
                     "ui_risk(window, ui_w(ui.a->status_note))"):
            with self.subTest(site=site):
                self.assertIn(site, ui)
        self.assertIn("vv5_isolan(cg_guardians_on(), said)", self.function("story_custom.inc", "static int ce_role("))

    def test_revive_and_the_refusals(self):
        revive = self.source("story_revive.inc")
        for stem in ("rv_row_text.s6", "rv_details.s10", "rv_details.s26"):
            with self.subTest(stem=stem):
                self.assertRegex(revive, r"vv5_isolan\(cg_guardians_on\(\), vvfp_tr\(\"vvfp\.story/story_revive\."
                                 + re.escape(stem))
        self.assertIn("k >= RV_WHY_PUZZLE_HEATHEN ? vv5_isolan(cg_guardians_on()",
                      self.function("story_revive.inc", "static const char *rv_why("))
        self.assertIn("k == CE_WHY_HEATHEN ? vv5_isolan(cg_guardians_on()",
                      self.function("story_custom.inc", "static const char *ce_why_word("))
        graph = self.source("story_graph.inc")
        self.assertNotIn('cg_bad("an effect is not one a Heathen may have")', graph)
        self.assertEqual(graph.count('cg_bad(vv5_isolan(cg_guardians_on(), "an effect is not one a Heathen may have"))'), 2)


class TheRewritesOwnTitles(unittest.TestCase):
    def test_pick_island_event_names_each_event_as_the_rewrite_does(self):
        def load(p: Path) -> dict[str, str]:
            t = p.read_text(encoding="cp1252")
            return {m.group(1): m.group(2).strip() for m in re.finditer(r'<Text id="([^"]+)">(.*?)</Text>', t, re.S)}

        base = load(ROOT / "data/guardians_of_isola/base/Assets/sm.xml")
        new = load(ROOT / "data/guardians_of_isola/new/Assets/sm.xml")
        renamed = {v: new[k] for k, v in base.items() if k.startswith("eEvent") and k.endswith("Title")
                   and k in new and new[k] != v}
        source = (STORY / "vvfp_story_upgrades.c").read_text(encoding="utf-8")
        table = source[source.index("VV5_GUARDIANS_TITLES[][2] = {"):]
        table = table[:table.index("};")]
        pairs = dict(re.findall(r'\{ "((?:[^"\\]|\\.)*)", "((?:[^"\\]|\\.)*)" \}', table))
        titles = [m.group(1) for m in re.finditer(r'\{ \d+, "((?:[^"\\]|\\.)*)"',
                                                  (STORY / "story_tables.h").read_text(encoding="utf-8")
                                                  .split("static const story_event VV5_EVENTS[]")[1].split("};")[0])]
        for title in titles:
            if title.strip() in renamed:
                with self.subTest(title=title):
                    self.assertEqual(pairs.get(title), renamed[title.strip()])
        self.assertTrue(set(pairs) <= set(renamed), "a title the rewrite does not rename")


# ---- The logs (the owner, 2026-11-23: Heathens = Isolans in the logs too) ----------------------------------------
NATIVE = ROOT / "native"
sys_path = str(ROOT / "src")
import sys  # noqa: E402
if sys_path not in sys.path:
    sys.path.insert(0, sys_path)
import vv_isolan_words as words  # noqa: E402

# Every log word the companions write about the Heathens, in the game's own wording -> the rewrite's.
LOG_PAIRS = {
    "Converted from the Heathens": "Converted from the Isolans",
    "no grave (died among the Heathens: nothing was left)": "no grave (died among the Isolans: nothing was left)",
    "Replaced a Heathen who died of old age": "Replaced an Isolan who died of old age",
    "Replaced a Heathen lost in an island event": "Replaced an Isolan lost in an island event",
    "Replaced a Heathen child who grew up": "Replaced an Isolan child who grew up",
    "Heathens Converted": "Isolans Converted",
    "Former Heathen (blue mask)": "Former Isolan (blue mask)",
    "Former Heathen (orange mask)": "Former Isolan (orange mask)",
    "Former Heathen (red mask)": "Former Isolan (red mask)",
    "Former Heathen Master (purple mask)": "Former Isolan Master (purple mask)",
    "Retired Heathen Chief": "Retired Isolan Chief",
}


def _sm(path: Path) -> dict[str, str]:
    t = path.read_text(encoding="cp1252")
    return {m.group(1): m.group(2).strip() for m in re.finditer(r'<Text id="([^"]+)">(.*?)</Text>', t, re.S)}


def rewrite_role_titles() -> dict[str, str]:
    """The puzzle Heathens' titles, the game's own -> the rewrite's own in-game name, from the rewrite's sm.xml."""
    base = _sm(ROOT / "data/guardians_of_isola/base/Assets/sm.xml")
    new = _sm(ROOT / "data/guardians_of_isola/new/Assets/sm.xml")
    rows = ("eSayHeathenMasterDoctor", "eSayHeathenChief", "eSayHeathenMasterResearcher", "eSayHeathenMasterBuilder",
            "eSayHeathenMasterFarmer", "eSayHeathenMasterParent")
    return {base[r]: new[r] for r in rows}


class TheLogWords(unittest.TestCase):
    def test_the_puzzle_titles_are_the_rewrites_own_names(self):
        titles = rewrite_role_titles()
        self.assertEqual(titles["Heathen Doctor"], "Esteemed Isolan Doctor")
        self.assertEqual(titles["Heathen Chief"], "Chief of the Native Isola Tribe")
        self.assertEqual(words.PUZZLE_TITLES, titles)                      # the readers' table
        header = (NATIVE / "shared/guardians_role_titles.h").read_text(encoding="utf-8")
        heathen = re.findall(r'"([^"]+)",\s+/\* role', header.split("VV5_ROLE_TITLES_ISOLAN")[0])
        isolan = re.findall(r'"([^"]+)",\s+/\* role', header.split("VV5_ROLE_TITLES_ISOLAN")[1])
        self.assertEqual(dict(zip(heathen, isolan)), titles)               # the companions' table

    def test_every_log_word_has_its_isolan_form_and_reads_back(self):
        for heathen, isolan in {**LOG_PAIRS, **rewrite_role_titles()}.items():
            with self.subTest(word=heathen):
                self.assertEqual(words.isolan_form(heathen), isolan)
                self.assertEqual(words.heathen_form(isolan), heathen)
                self.assertEqual(words.heathen_form(heathen), heathen)
                self.assertNotIn("heathen", isolan.lower())
                self.assertNotIn("guardian", isolan.lower())

    def test_every_writer_switches(self):
        def src(rel: str) -> str:
            return (NATIVE / rel).read_text(encoding="utf-8")
        checks = {
            "vvfp_cause_of_death/cod_arrivals.inc": "lstrcpynA(arrivals[i].how, vv5_word_converted(), ARRIVAL_HOW);",
            "vvfp_cause_of_death/cod_cie_words.inc": "cod_log_death(record, cause, vv5_word_no_grave(), NULL);",
            "vvfp_heathen_aging/vvfp_heathen_aging.c": "tell_arrived(index, vv5_word_replaced(g_replace_words == REPLACED_EVENT));",
            "vvfp_faith_notice/vvfp_faith_notice.c": '"  %s: %s no -> yes\\n  %s: Faith %d -> %d\\n", g_left[i].name, vv5_heathen_word(),',
            "statistics_export/statistics_export.c": 'fprintf(file, "%s: %d\\n", vv5_word_converted_row(),',
            "shared/special_title.h": "return vv5_role_title(role);",
            "vvfp_island_events/vvfp_island_events.c": '"  %s: %s -> %s\\n", log_label(f), a, b);',
            "vvfp_story_upgrades/story_revive.inc": "game == 5 && vv5_puzzle_role_title(p->special)",
        }
        for rel, site in checks.items():
            with self.subTest(writer=rel):
                self.assertIn(site, src(rel))
        former = src("shared/former_heathens.h")
        for heathen, isolan in LOG_PAIRS.items():
            if heathen.startswith(("Former", "Retired")):
                with self.subTest(title=heathen):
                    self.assertIn(f'isolan ? "{isolan}" : "{heathen}"', former)
        self.assertIn('return g_game == 5 && strcmp(f->label, "Heathen") == 0 ? vv5_heathen_word() : f->label;',
                      src("vvfp_island_events/vvfp_island_events.c"))
        log_words = src("shared/isolan_log_words.h")
        for heathen, isolan in LOG_PAIRS.items():
            if not heathen.startswith(("Former", "Retired")):
                with self.subTest(word=heathen):
                    self.assertIn(f'"{heathen}"', log_words)
                    self.assertIn(f'"{isolan}"', log_words)
        # no writer keeps a bare Heathen log word of its own
        for rel, word in (("vvfp_cause_of_death/cod_arrivals.inc", '"Converted from the Heathens"'),
                          ("vvfp_faith_notice/vvfp_faith_notice.c", '"  %s: Heathen no -> yes'),
                          ("statistics_export/statistics_export.c", '"Heathens Converted: %d'),
                          ("shared/special_title.h", '"Heathen Doctor"')):
            with self.subTest(gone=word):
                self.assertNotIn(word, re.sub(r"/\*.*?\*/", "", src(rel), flags=re.S))     # code, not comments


class EveryReaderTakesBoth(unittest.TestCase):
    def block(self, *lines: str):
        import vv_log_additions as additions
        return additions.blocks(Path("Virtual Villagers 5 Deaths - Save 1.txt"), ["Death 1", *lines, ""])[0]

    def test_the_faction_of_a_title(self):
        import vv_log_additions as additions
        for heathen, isolan in rewrite_role_titles().items():
            with self.subTest(title=isolan):
                self.assertEqual(additions._faction_of_title(isolan), "Heathen")
                self.assertEqual(additions._faction_of_title(heathen), "Heathen")
        for heathen, isolan in LOG_PAIRS.items():
            if heathen.startswith(("Former", "Retired")):
                with self.subTest(title=isolan):
                    self.assertEqual(additions._faction_of_title(isolan), "Believer")
                    self.assertEqual(additions._faction_of_title(heathen), "Believer")

    def test_the_family_tree_reads_both(self):
        import vv_genealogy as gen
        for heathen, isolan in {**LOG_PAIRS, **rewrite_role_titles()}.items():
            if heathen.startswith(("Former", "Retired", "Heathen ")) or heathen in rewrite_role_titles():
                with self.subTest(title=isolan):
                    self.assertEqual(gen.status_marks(isolan), gen.status_marks(heathen))
        self.assertTrue(gen._heathen_marked(self.block("  Name: Ana", "  Isolan: no -> yes")))
        self.assertTrue(gen._heathen_marked(self.block("  Name: Ana", "  Heathen: no -> yes")))
        self.assertTrue(gen._heathen_marked(self.block("  Name: Ana", "  Special villager: Esteemed Isolan Parent")))
        self.assertIn("Converted from the Isolans", gen.CONVERTED_HOWS)

    def test_the_readers_route_through_the_two_wordings(self):
        def src(name: str) -> str:
            return (ROOT / "src" / name).read_text(encoding="utf-8")
        for name, site in (
                ("vv5_heathen_ages.py", "if how.startswith(CONVERTED_HOWS):"),
                ("vv5_rejoined_masks.py", "mask = TITLE_MASK.get(heathen_form(title.strip()))"),
                ("vv5_heathen_masks_restore.py", 'mask = TITLE_MASK.get(heathen_form(b.value("Special villager") or ""))'),
                ("vv_graves.py", 'record_title = heathen_form(record_title or "")'),
                ("vv_game_mechanics_counts.py", "rows[heathen_form(m.group(1))] ="),
                ("vv_log_additions.py", 'if (b.value("How") or "").strip() in CONVERTED_HOWS:\n                    converted.add(b.identity)'),
                ("vv_log_additions.py", 'if (b.value("How") or "").strip() in CONVERTED_HOWS:\n                    add(b.identity, 1)'),
                ("vv_genealogy.py", 'if (b.value("How") or "").strip() in CONVERTED_HOWS:'),
                ("vv_genealogy.py", "if how and how not in CONVERTED_HOWS and")):
            with self.subTest(reader=name, site=site[:40]):
                self.assertIn(site, src(name))

    def test_the_mask_repairs_read_a_former_isolan(self):
        import vv5_heathen_masks_restore as restore
        import vv5_rejoined_masks as rejoined
        for heathen, isolan in LOG_PAIRS.items():
            if heathen.startswith(("Former", "Retired")):
                with self.subTest(title=isolan):
                    self.assertEqual(restore.TITLE_MASK.get(words.heathen_form(isolan)), restore.TITLE_MASK[heathen])
                    self.assertEqual(rejoined.TITLE_MASK.get(words.heathen_form(isolan)), rejoined.TITLE_MASK[heathen])

    def test_revives_puzzle_check_takes_both(self):
        self.assertNotIn('strncmp(p->special, "Heathen ", 8)', (STORY / "story_revive.inc").read_text(encoding="utf-8"))


LOG_UNDER_TEST = r'''
#include "isolan_log_words.h"
__declspec(dllexport) int PuzzleTitle(const char *t) { return vv5_puzzle_role_title(t); }
__declspec(dllexport) const char *RoleTitle(int role) { return vv5_role_title(role); }
__declspec(dllexport) const char *Converted(void) { return vv5_word_converted(); }
'''


class TheCLogWords(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.mkdtemp()
        folder = Path(cls._tmp)
        vcvars = _vcvars()
        if vcvars is None:
            raise unittest.SkipTest("needs the Visual C++ tools")
        (folder / "l.c").write_text(LOG_UNDER_TEST, encoding="utf-8")
        command = f'call "{vcvars}" >nul && cl /nologo /LD /O2 /I "{SHARED}" l.c /Fe:l.dll /link /NOLOGO >nul'
        result = subprocess.run(command, shell=True, cwd=folder, capture_output=True, text=True)
        if result.returncode != 0 or not (folder / "l.dll").is_file():
            raise unittest.SkipTest("needs the Visual C++ tools")
        cls.dll = ctypes.CDLL(str(folder / "l.dll"))
        cls.dll.PuzzleTitle.argtypes = [ctypes.c_char_p]
        cls.dll.RoleTitle.restype = ctypes.c_char_p
        cls.dll.Converted.restype = ctypes.c_char_p

    @classmethod
    def tearDownClass(cls) -> None:
        cls.dll = None
        shutil.rmtree(cls._tmp, ignore_errors=True)

    def test_revives_check_knows_both_wordings_of_every_puzzle_title(self):
        for heathen, isolan in rewrite_role_titles().items():
            with self.subTest(title=heathen):
                self.assertEqual(self.dll.PuzzleTitle(heathen.encode()), 1)
                self.assertEqual(self.dll.PuzzleTitle(isolan.encode()), 1)
        for other in ("Former Heathen (blue mask)", "Tribal Chief", "Heathen", "Esteemed Elder"):
            with self.subTest(title=other):
                self.assertEqual(self.dll.PuzzleTitle(other.encode()), 0)

    def test_without_the_rewrite_the_games_own_words(self):
        # A process with no New Believers image (this one) has no rewrite: the game's own words.
        self.assertEqual(self.dll.RoleTitle(13), b"Heathen Chief")
        self.assertEqual(self.dll.RoleTitle(11), None)
        self.assertEqual(self.dll.Converted(), b"Converted from the Heathens")

if __name__ == "__main__":
    unittest.main()
