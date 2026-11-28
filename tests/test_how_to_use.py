"""Every feature in the patcher window has a "?" with a brief guide.

The owner: "there should be a little How to Use button for every feature in
the entire patcher. Just a brief, simple to understand guide."

The guides live in data/how_to_use.json (read by src/vv_how_to_use.py).
These tests make sure:
- every public patch, every population mode, and every button, tool and
  setting has a guide, and no guide is left for something that is gone --
  so a new patch cannot ship without one;
- each guide is short and plain (a few lines, no technical words);
- a guide names every other patch its feature needs;
- the window puts a "?" beside each of them, and the "?" opens the guide.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import vv_fun_patcher as vfp  # noqa: E402
import vv_how_to_use as how  # noqa: E402

GUI = ROOT / "src" / "vv_fun_patcher_gui.py"
DATA = json.loads((ROOT / "data" / "how_to_use.json").read_text(encoding="utf-8"))

# Every button, tool and setting in the window, by its guide key.  A new
# button gets a guide and a line here.
CONTROLS = {
    "select_all", "default_patches", "owners_defaults", "deselect_all",
    "heathen_tribe_births_multiplier", "heathen_arrivals_multiplier", "heathen_show_percent", "heathen_keep_blue", "heathen_busyness",
    "patch_selection_settings", "patch_search",
    "output_location", "choose_exe", "validate", "dry_run", "create_modified_exe",
    "game_folders", "find_all_5", "validate_all_5", "dry_run_all_5", "patch_all_5",
    "open_vanilla_folder", "open_modified_folder", "open_game_folder",
    "back_up_saves", "restore_saves", "backups", "rename_tribe", "check_logs", "repair_logs",
    "check_logs_automatically", "check_for_updates", "family_tree_maker", "village_matchmaker",
    "game_mechanics", "stew_recipes", "custom_island_event_library", "copy_player_slot", "picture_studio", "translations", "unicode_font", "unicode_font_tool", "game_text", "tech_cost_multiplier", "meal_multiplier", "sickness_multiplier",
    "louder_flutes_multiplier", "island_frequency_multiplier",
    # The 0.1x-10x sliders (the owner, 2026-11-17), made by one loop over RUNTIME_SLIDERS.
    "collectible_frequency_multiplier", "food_gain_multiplier", "tech_gain_multiplier",
    "skill_success_multiplier", "age_speed_multiplier",
    "weather_frequency_multiplier", "divine_energy_gain_multiplier",    # the owner, 2026-11-25 (v1.35.101)
    # The Difficulty Sliders page's button (the owner, 2026-11-18): every slider is on that page.
    "difficulty_sliders",
    "island_event_content_filters", "partner_carry_percent", "more_island_events_and_creator",  # the Island Events section's filters (the owner, 2026-11-15)
    "village_solidarity_strength",
}

# Words a player never sees in the patcher or the game.
JARGON = re.compile(
    r"\bDLLs?\b|\.dll\b|\b0x[0-9a-f]|\bhooks?\b|trampoline|\boffsets?\b|\bbytes?\b|"
    r"companion|\bstub\b|sidecar|manifest|opcode|internal age|patch id|\.dat\b|\.json\b|"
    r"\bvv[1-5]_",
    re.IGNORECASE,
)


def all_guides() -> dict[str, tuple[str, ...]]:
    return how.guide_lines()


class CoverageTests(unittest.TestCase):
    def test_every_public_patch_has_exactly_one_guide(self) -> None:
        guided = [patch_id for entry in DATA["patches"] for patch_id in entry["ids"]]
        self.assertEqual(len(guided), len(set(guided)), "a patch listed in two guides")
        public = {patch.id for patch in vfp.load_public_fun_patches()}
        self.assertEqual(public - set(guided), set(), "public patches without a guide")
        self.assertEqual(set(guided) - public, set(), "guides for patches that are not in the window")

    def test_every_population_mode_has_a_guide(self) -> None:
        modes = {mode.id for mode in vfp.load_patch_modes()}
        self.assertEqual(set(DATA["modes"]), modes)

    def test_every_control_has_a_guide_and_a_title(self) -> None:
        self.assertEqual(set(DATA["controls"]), CONTROLS)
        for key, entry in DATA["controls"].items():
            with self.subTest(control=key):
                self.assertTrue(entry["title"].strip())

    def test_a_missing_guide_is_refused(self) -> None:
        with self.assertRaises(KeyError):
            how.guide(how.patch_key("vv9_no_such_patch"), "x")
        with self.assertRaises(KeyError):
            how.guide("no_such_control")


class ContentTests(unittest.TestCase):
    def test_each_guide_is_brief(self) -> None:
        for key, lines in all_guides().items():
            with self.subTest(guide=key):
                self.assertGreaterEqual(len(lines), 1)
                self.assertLessEqual(len(lines), how.MAX_LINES)
                self.assertLessEqual(sum(len(line) for line in lines), how.MAX_GUIDE_CHARS)
                for line in lines:
                    self.assertTrue(line.strip(), "an empty line")
                    self.assertEqual(line, line.strip())
                    self.assertLessEqual(len(line), how.MAX_LINE_CHARS, line)

    def test_patch_and_mode_guides_say_enough(self) -> None:
        # "What it does, how to use it, and anything to watch out for":
        # never a single throwaway line for a patch or a mode.
        for key, lines in all_guides().items():
            if key.startswith(("patch:", "mode:")):
                with self.subTest(guide=key):
                    self.assertGreaterEqual(len(lines), 2)

    def test_no_technical_words(self) -> None:
        for key, lines in all_guides().items():
            for line in lines:
                with self.subTest(guide=key, line=line):
                    self.assertIsNone(JARGON.search(line))
                    self.assertNotIn("**", line)

    def test_a_guide_names_every_patch_its_feature_needs(self) -> None:
        catalog = {patch.id: patch for patch in vfp.load_public_fun_patches()}
        for patch in catalog.values():
            text = " ".join(how.guide(how.patch_key(patch.id), patch.name).lines)
            required = [[dep] for dep in (patch.raw.get("dependencies") or ()) if dep in catalog]
            for need in patch.raw.get("needs_on") or ():
                required.append([need["id"], *need.get("or", ())])
            for choices in required:
                names = [catalog[choice].name for choice in choices if choice in catalog]
                with self.subTest(patch=patch.id, needs=choices):
                    self.assertTrue(any(name in text for name in names), names)

    def test_the_selection_guides_match_the_selection_rules(self) -> None:
        import vv_fun_patcher_gui as gui

        # The island event controls are named together in the selection guides.
        names = {patch.id: ("island event controls"
                            if re.search(r"_island_event_(filter_f|content_notes)|_island_events_any_time", patch.id)
                            # The five 0.1x-10x sliders' rows, named together (the owner, 2026-11-17).
                            else "the 0.1-10x sliders"
                            if any(patch.id.endswith(s.row_suffix) for s in vfp.RUNTIME_SLIDERS)
                            else patch.name)
                 for patch in vfp.load_public_fun_patches()}
        default = " ".join(how.guide("default_patches").lines)
        for patch_id in gui.DEFAULT_OFF_FUN_PATCH_IDS:
            name = names[patch_id]
            # The guide uses the short form of the two long names.
            short = {"Manual Drop-Breeding overrides Birth Control": "Manual Drop-Breeding",
                     "256 Villagers (Experimental)": "256 Villagers"}.get(name, name)
            # Both Island Events Scale rows, named together within the guide's 1,250 characters.
            if "_island_events_scale_with_" in patch_id:
                short = "both Island Events Scale patches"
            # Fog of Doom Lets Red and Orange Heathens Listen and its option, named together likewise.
            if patch_id.startswith("vv5_fog_of_doom_"):
                short = "both Fog of Doom patches"
            # The three Heathen aging rows (New Believers: the two Former Villagers rows, 2026-11-22, and Heathen
            # Tribe Expansion and Evolution, v1.35.101), named together likewise.
            if patch_id in ("vv5_former_villagers_keep_aging", "vv5_former_villager_heathens_leave_skeletons",
                            "vv5_heathen_tribe_evolution"):
                short = "the three Heathen aging patches"
            with self.subTest(default_off=patch_id):
                self.assertIn(short, default)
        owners = " ".join(how.guide("owners_defaults").lines)
        for patch_id in gui.OWNERS_DEFAULT_OFF_FUN_PATCH_IDS:
            self.assertIn(names[patch_id], owners)
        select_all = " ".join(how.guide("select_all").lines)
        for patch_id in gui.SELECT_ALL_OFF_FUN_PATCH_IDS:
            self.assertIn(names[patch_id], select_all)
            self.assertIn("Select All does not tick it", " ".join(how.guide(how.patch_key(patch_id), "x").lines))
        # The other way round: a patch the guide names as not ticked must really be left off.  The lines that
        # name a ticked alternative ("... (ticked).") are left out.  The guide once named Isola Grand Event
        # Collection and Birth Control, which Select All ticks.
        not_ticked = " ".join(line for line in how.guide("select_all").lines if "(ticked)" not in line)
        ticked = {}
        for patch in vfp.load_public_fun_patches():
            ticked.setdefault(patch.name, set()).add(patch.id not in gui.SELECT_ALL_OFF_FUN_PATCH_IDS)
        longer = [n for n in ticked if any(n != m and n in m and m in not_ticked for m in ticked)]
        for name, states in ticked.items():
            if name in not_ticked and name not in longer:
                with self.subTest(select_all_names=name):
                    self.assertEqual(states, {False}, f"the Select All guide says {name} is not ticked")

    def test_the_guides_ship_with_the_patcher(self) -> None:
        release = (ROOT / "scripts" / "build_release.py").read_text(encoding="utf-8")
        self.assertIn('"src/vv_how_to_use.py"', release)
        self.assertIn('"data/how_to_use.json"', release)


class GuiSourceTests(unittest.TestCase):
    SOURCE = GUI.read_text(encoding="utf-8")

    def test_every_control_is_wired_to_a_question_mark(self) -> None:
        import vv_fun_patcher_gui as gui
        # Every slider's "?" is on the Difficulty Sliders page, one per slider and game, by its table's key.
        sliders = {spec[2] for spec in gui.DIFFICULTY_SLIDERS}
        self.assertIn("self._difficulty_variable(name, help_key),\n                                                     "
                      "multipliers, help_key)", self.SOURCE)
        for key in CONTROLS - sliders:
            with self.subTest(control=key):
                self.assertRegex(self.SOURCE, r'_help_button\(\s*\w+, "%s"\)' % re.escape(key)
                                 + "|" + r'\(\d+, "%s"\)' % re.escape(key)
                                 # a multiplier slider's "?" (App._multiplier_slider passes its key on)
                                 + "|" + r'_multiplier_slider\([^()]*(?:\([^()]*\)[^()]*)*"%s"\)' % re.escape(key))

    def test_every_patch_row_and_mode_gets_one(self) -> None:
        # The one patch-row loop (a tab per game, shared patches included) and the mode loop.
        self.assertEqual(self.SOURCE.count("vv_how_to_use.patch_key(patch.id)"), 1)
        self.assertEqual(self.SOURCE.count("vv_how_to_use.mode_key(mode.id)"), 1)

    def test_the_button_is_a_small_question_mark(self) -> None:
        body = self.SOURCE[self.SOURCE.index("    def _help_button("):self.SOURCE.index("    def _show_how_to_use(")]
        self.assertIn('text="?"', body)
        self.assertIn("width=2", body)
        self.assertIn("self.help_keys.add(key)", body)
        # A key without a guide fails while the window is built.
        self.assertIn("vv_how_to_use.guide(key, title)", body)


NO_TK = 3

CHILD = r"""
import json, sys, tkinter
from pathlib import Path
from tkinter import ttk
sys.path.insert(0, sys.argv[1])
import vv_fun_patcher_gui as gui
import vv_how_to_use as how
gui.SETTINGS = Path(sys.argv[2])
try:
    app = gui.App()
except tkinter.TclError as exc:
    print(exc, file=sys.stderr)
    sys.exit(3)
app.update()

def walk(w):
    yield w
    for c in w.winfo_children():
        yield from walk(c)

# Every slider is on the Difficulty Sliders page (the owner, 2026-11-18), none on the main page.
result = {"main_scales": sum(isinstance(w, tkinter.Scale) for w in walk(app))}
app._open_difficulty_sliders()
app.update()
page = app._difficulty_sliders_dialog
result["page_rows"] = [(pid, str(scale.cget("state"))) for pid, scale, box, note in app._difficulty_slider_rows]
result["page_scales"] = sum(isinstance(w, tkinter.Scale) for w in walk(page))
result["page_height"] = page.winfo_reqheight()
# Ticking a row lights its slider; the number typed on the page is the App's own (saved as before).
first = app._difficulty_slider_rows[0]
app.fun_patch_vars[first[0]].set(True)
app._fun_patch_changed()
app.update()
result["lit"] = str(first[1].cget("state"))
first[2].delete(0, "end")
first[2].insert(0, "-2")
first[2].commit()
result["typed"] = app._tech_cost_multiplier()
app.tech_cost_var.set(10)
app.update()
result["shown"] = first[2].get()
result["keys"] = sorted(app.help_keys)
# The patch rows are drawn only while their list is scrolled to them, so every list is
# scrolled through its length. Every patch checkbox has a "?" beside it, in the same row;
# the cause-of-death "?" is clicked (invoke) the first time its row is drawn.
patch_vars = {str(var): patch_id for patch_id, var in app.fun_patch_vars.items()}
beside = {}
clicked = False
for vl in [w for w in walk(app) if isinstance(w, gui.VirtualList)]:
    vl.yview("moveto", 0)
    for _ in range(400):
        app.update()
        for w in walk(vl):
            if isinstance(w, ttk.Checkbutton) and str(w.cget("variable")) in patch_vars:
                patch_id = patch_vars[str(w.cget("variable"))]
                siblings = [s for s in w.master.winfo_children()
                            if isinstance(s, ttk.Button) and s.cget("text") == "?"]
                beside[patch_id] = len(siblings)
                if not clicked and patch_id == "vv1_cause_of_death":
                    siblings[0].invoke()
                    clicked = True
                    app.update()
        if float(vl.scrollbar.get()[1]) >= 1.0:
            break
        vl.yview("scroll", 4, "units")
result["beside"] = beside
result["clicked"] = clicked

def labels(window):
    return [w.cget("text") for w in walk(window) if isinstance(w, ttk.Label)]

windows = {}
app.update()
window = app._help_windows[how.patch_key("vv1_cause_of_death")]
windows["patch"] = {"title": window.title(), "labels": labels(window)}
for key in ("back_up_saves", "check_logs_automatically", "mode:stock"):
    title = "No Population Increase" if key == "mode:stock" else None
    window = app._show_how_to_use(key, title)
    app.update()
    windows[key] = {"title": window.title(), "labels": labels(window),
                    "again": app._show_how_to_use(key, title) is window}
# Escape closes a guide (pressed on its Close button, which has the focus).
window = app._help_windows["back_up_saves"]
close = next(w for w in walk(window) if isinstance(w, ttk.Button) and w.cget("text") == "Close")
close.focus_force()
app.update()
close.event_generate("<Escape>")
app.update()
result["closed"] = not window.winfo_exists()
result["windows"] = windows
app.destroy()
print(json.dumps(result))
"""


class WindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        with tempfile.TemporaryDirectory() as folder:
            completed = subprocess.run(
                [sys.executable, "-c", CHILD, str(ROOT / "src"), str(Path(folder) / "settings.json")],
                capture_output=True, text=True, timeout=300,
            )
        if completed.returncode == NO_TK:
            raise unittest.SkipTest(f"no Tk display: {completed.stderr.strip()}")
        if completed.returncode != 0:
            raise AssertionError(completed.stderr)
        cls.result = json.loads(completed.stdout.strip().splitlines()[-1])

    def test_every_guide_has_a_question_mark_in_the_window(self) -> None:
        self.assertEqual(set(self.result["keys"]), set(all_guides()))

    def test_every_slider_is_on_the_difficulty_sliders_page(self) -> None:
        import vv_fun_patcher_gui as gui
        public = {patch.id for patch in vfp.load_public_fun_patches()}
        wanted = [f"vv{game}{spec[3]}" for game in range(1, 6) for spec in gui.DIFFICULTY_SLIDERS
                  if f"vv{game}{spec[3]}" in public]
        self.assertEqual(self.result["main_scales"], 0, "no slider left on the main page")
        self.assertEqual(sorted(pid for pid, _state in self.result["page_rows"]), sorted(wanted))
        self.assertEqual(self.result["page_scales"], len(wanted))
        # A fresh settings file ticks the defaults: a slider whose patch is off there is greyed out.
        for pid, state in self.result["page_rows"]:
            with self.subTest(row=pid):
                self.assertEqual(state, "normal" if gui.default_fun_patch_selection(pid) else "disabled")
        self.assertEqual(self.result["lit"], "normal")
        self.assertEqual(self.result["typed"], 0.5)          # "-2" typed on the page: half, the App's own number
        self.assertEqual(self.result["shown"], "10")        # the App's number moves the page's box
        self.assertLess(self.result["page_height"], 32_767)

    def test_every_patch_row_has_its_own_question_mark(self) -> None:
        # The 28 content filters sit in the Island Events section's grid: one "?" (Content Filters) for them all.
        public = {patch.id for patch in vfp.load_public_fun_patches() if "_island_event_filter_f" not in patch.id}
        self.assertEqual(set(self.result["beside"]), public)
        self.assertEqual(set(self.result["beside"].values()), {1})

    def test_the_question_mark_opens_the_guide(self) -> None:
        patch = self.result["windows"]["patch"]
        self.assertEqual(patch["title"], "How to use: Show Cause of Death and Epitaphs on Graves, "
                                         "and Log Every Death (A New Home)")
        lines = list(how.guide(how.patch_key("vv1_cause_of_death"), "x").lines)
        self.assertEqual(patch["labels"][1:], lines)

    def test_tool_setting_and_mode_guides_open_and_are_not_opened_twice(self) -> None:
        for key, title in (("back_up_saves", "Back Up Saves"),
                           ("check_logs_automatically", "Check logs automatically"),
                           ("mode:stock", "No Population Increase")):
            with self.subTest(guide=key):
                window = self.result["windows"][key]
                self.assertEqual(window["title"], f"How to use: {title}")
                self.assertEqual(window["labels"][0], title)
                self.assertEqual(window["labels"][1:], list(all_guides()[key]))
                self.assertTrue(window["again"], "a second click opened a second window")

    def test_escape_closes_a_guide(self) -> None:
        self.assertTrue(self.result["closed"])


if __name__ == "__main__":
    unittest.main()
