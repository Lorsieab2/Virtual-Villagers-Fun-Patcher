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


if __name__ == "__main__":
    unittest.main()
