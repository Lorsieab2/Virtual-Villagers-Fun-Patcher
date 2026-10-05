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
    "output_location", "choose_exe", "validate", "dry_run", "create_modified_exe",
    "game_folders", "find_all_5", "validate_all_5", "dry_run_all_5", "patch_all_5",
    "open_vanilla_folder", "open_modified_folder", "open_game_folder",
    "back_up_saves", "restore_saves", "rename_tribe", "check_logs", "repair_logs",
    "check_logs_automatically", "check_for_updates",
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

        names = {patch.id: patch.name for patch in vfp.load_public_fun_patches()}
        default = " ".join(how.guide("default_patches").lines)
        for patch_id in gui.DEFAULT_OFF_FUN_PATCH_IDS:
            name = names[patch_id]
            # The guide uses the short form of the two long names.
            short = {"Manual Drop-Breeding overrides Birth Control": "Manual Drop-Breeding",
                     "256 Villagers (Experimental)": "256 Villagers"}.get(name, name)
            with self.subTest(default_off=patch_id):
                self.assertIn(short, default)
        owners = " ".join(how.guide("owners_defaults").lines)
        for patch_id in gui.OWNERS_DEFAULT_OFF_FUN_PATCH_IDS:
            self.assertIn(names[patch_id], owners)
        select_all = " ".join(how.guide("select_all").lines)
        for patch_id in gui.SELECT_ALL_OFF_FUN_PATCH_IDS:
            self.assertIn(names[patch_id], select_all)
            self.assertIn("Select All does not tick it", " ".join(how.guide(how.patch_key(patch_id), "x").lines))

    def test_the_guides_ship_with_the_patcher(self) -> None:
        release = (ROOT / "scripts" / "build_release.py").read_text(encoding="utf-8")
        self.assertIn('"src/vv_how_to_use.py"', release)
        self.assertIn('"data/how_to_use.json"', release)


class GuiSourceTests(unittest.TestCase):
    SOURCE = GUI.read_text(encoding="utf-8")

    def test_every_control_is_wired_to_a_question_mark(self) -> None:
        for key in CONTROLS:
            with self.subTest(control=key):
                self.assertRegex(self.SOURCE, r'_help_button\(\s*\w+, "%s"\)' % re.escape(key)
                                 + "|" + r'\(\d+, "%s"\)' % re.escape(key))

    def test_every_patch_row_and_mode_gets_one(self) -> None:
        # Both patch-row loops (per game and shared) and the mode loop.
        self.assertEqual(self.SOURCE.count("vv_how_to_use.patch_key(patch.id)"), 2)
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

result = {"keys": sorted(app.help_keys)}
# Every patch checkbox has a "?" beside it, in the same row.
patch_vars = {str(var): patch_id for patch_id, var in app.fun_patch_vars.items()}
beside = {}
for w in walk(app):
    if isinstance(w, ttk.Checkbutton) and str(w.cget("variable")) in patch_vars:
        siblings = [s for s in w.master.winfo_children()
                    if isinstance(s, ttk.Button) and s.cget("text") == "?"]
        beside[patch_vars[str(w.cget("variable"))]] = len(siblings)
result["beside"] = beside
result["question_marks"] = sum(
    1 for w in walk(app) if isinstance(w, ttk.Button) and w.cget("text") == "?")

def labels(window):
    return [w.cget("text") for w in walk(window) if isinstance(w, ttk.Label)]

windows = {}
# Clicking the "?" (invoke) opens the guide.
button = next(w for w in walk(app) if isinstance(w, ttk.Button) and w.cget("text") == "?"
              and isinstance(w.master.winfo_children()[0], ttk.Checkbutton)
              and str(w.master.winfo_children()[0].cget("variable")) == str(app.fun_patch_vars["vv1_cause_of_death"]))
button.invoke()
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

    def test_every_patch_row_has_its_own_question_mark(self) -> None:
        public = {patch.id for patch in vfp.load_public_fun_patches()}
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
