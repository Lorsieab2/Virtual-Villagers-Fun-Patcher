"""Each patch's own settings window (the owner, 2026-11-19: "the patches should be the focus, any auxiliary settings
go in separate button-hidden menus next to the respective patches").

The main patch list holds only the rows: each patch's tick, its "?" and its description, plus one "Settings..." button
beside a patch that has settings.  No slider, number box, font box, extra tick or tool button sits on it.  Every
setting is in its patch's window (or on the Difficulty Sliders page), and a setting changed there is saved as before
and read back by the next start.

The App runs in its own interpreter (Tk cannot build a second App in one process); every window it opens is
withdrawn, so nothing shows on the screen.  The settings and the user profile are a temporary folder."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NO_TK = 3

CHILD = r"""
import json, os, sys, tkinter
from pathlib import Path
from tkinter import ttk
sys.path.insert(0, sys.argv[1])
os.environ["USERPROFILE"] = sys.argv[2]
_toplevel_init = tkinter.Toplevel.__init__
def _withdrawn(self, *args, **kwargs):          # no window shows on the screen
    _toplevel_init(self, *args, **kwargs)
    self.withdraw()
tkinter.Toplevel.__init__ = _withdrawn
import vv_fun_patcher_gui as gui
gui.SETTINGS = Path(sys.argv[2]) / "settings.json"
step = sys.argv[3]
try:
    app = gui.App()
except tkinter.TclError as exc:
    print(exc, file=sys.stderr)
    sys.exit(3)
app.withdraw()
app.update()


def walk(w):
    for c in w.winfo_children():
        if isinstance(c, tkinter.Toplevel):
            continue                            # another window, not the page
        yield c
        yield from walk(c)


out = {}
if step == "set":
    patch_vars = {str(v): pid for pid, v in app.fun_patch_vars.items()}
    masters = {str(m) for m, _ticked, _joined in getattr(app, "_mie_creator_rows", [])}
    extras, settings_beside = [], {}
    lists = [w for w in walk(app) if isinstance(w, gui.VirtualList)]

    def look(widgets):
        for w in widgets:
            kind = w.winfo_class()
            if isinstance(w, (tkinter.Scale, ttk.Scale, ttk.Spinbox, tkinter.Spinbox, ttk.Combobox)):
                extras.append(f"{kind} {w}")
            elif isinstance(w, ttk.Checkbutton):
                var = str(w.cget("variable"))
                if var in masters:
                    continue
                pid = patch_vars.get(var)
                if pid is None or "_island_event_filter_f" in pid:
                    extras.append(f"tick {w} {pid}")
                else:
                    settings_beside[pid] = [str(s.cget("text")) for s in w.master.winfo_children()
                                            if isinstance(s, ttk.Button) and s.cget("text") != "?"]
            elif isinstance(w, ttk.Button) and str(w.cget("text")) not in ("?", gui.PATCH_SETTINGS_BUTTON):
                extras.append(f"button {w} {w.cget('text')}")

    for tab in app.patch_pages.tabs():
        look(walk(app.patch_pages.nametowidget(tab)))
    for vl in lists:
        vl.yview("moveto", 0)
        for _ in range(400):
            app.update()
            look(walk(vl))
            if float(vl.scrollbar.get()[1]) >= 1.0:
                break
            vl.yview("scroll", 4, "units")
    out["extras"] = sorted(set(extras))
    out["settings_beside"] = settings_beside
    # nothing auxiliary on the settings row above the tabs either
    out["row_controls"] = sorted({w.winfo_class() for w in walk(app.fun_settings_row)
                                  if isinstance(w, (tkinter.Scale, ttk.Combobox, ttk.Spinbox))})
    out["windows"] = sorted(app._patch_settings)
    out["mie_buttons"] = sorted(key for _button, key in app._patch_settings_buttons)
    found = {}
    for key in sorted(app._patch_settings):
        if key.endswith("_mie"):
            button = next(b for b, k in app._patch_settings_buttons if k == key)
            button.invoke()
        else:
            app._open_patch_settings(key)
        app.update()
        window = app._patch_settings_windows[key]
        again = app._open_patch_settings(key) is window
        widgets = [w for w in walk(window)]
        filters = [w for w in widgets if isinstance(w, ttk.Checkbutton)
                   and "_island_event_filter_f" in patch_vars.get(str(w.cget("variable")), "")]
        found[key] = {"again": again, "held": bool(getattr(window, "_vvfp_disabled", None) is not None
                                                   or app.grab_current() is not None),
                      "scales": sum(isinstance(w, tkinter.Scale) for w in widgets),
                      "spinboxes": sum(isinstance(w, ttk.Spinbox) for w in widgets),
                      "fonts": sum(isinstance(w, ttk.Combobox) for w in widgets),
                      "filters": sorted(patch_vars[str(w.cget("variable"))] for w in filters),
                      "buttons": sorted(str(w.cget("text")) for w in widgets if isinstance(w, ttk.Button))}
        if key == "vv5_mie":
            spin = next(w for w in widgets if isinstance(w, ttk.Spinbox))
            spin.set("55")                      # typed, then the window closed straight away
            filters[0].invoke()
            found[key]["ticked"] = patch_vars[str(filters[0].cget("variable"))]
        if key == "vv2_unicode_font":
            box = next(w for w in widgets if isinstance(w, ttk.Combobox))
            box.set("Arial")
        window.close()
        app.update()
        found[key]["closed"] = not window.winfo_exists()
    out["found"] = found
    app.solidarity_var.set(2.5)                 # the Difficulty Sliders page's number
    app.update()
    out["saved"] = json.loads(gui.SETTINGS.read_text(encoding="utf-8"))
    out["main_enabled"] = not app.wm_attributes("-disabled")
else:
    out["partner"] = app._partner_carry()
    out["font"] = app.unicode_font_var.get()
    out["solidarity"] = app.solidarity_var.get()
    out["ticked"] = sorted(pid for pid, v in app.fun_patch_vars.items() if v.get() and "_filter_f" in pid)
app.destroy()
print(json.dumps(out))
"""


def _run(folder: str, step: str) -> dict:
    completed = subprocess.run([sys.executable, "-c", CHILD, str(ROOT / "src"), folder, step],
                               capture_output=True, text=True, timeout=600)
    if completed.returncode == NO_TK:
        raise unittest.SkipTest(f"no Tk display: {completed.stderr.strip()[-200:]}")
    if completed.returncode != 0:
        raise AssertionError(completed.stderr[-3000:])
    return json.loads(completed.stdout.strip().splitlines()[-1])


class PatchSettingsWindows(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with tempfile.TemporaryDirectory() as folder:
            cls.set = _run(folder, "set")
            cls.read = _run(folder, "read")

    def test_no_auxiliary_control_on_the_patch_list(self):
        self.assertEqual(self.set["extras"], [], "only ticks, \"?\" and Settings... on the patch list")
        self.assertEqual(self.set["row_controls"], [], "no slider or font box on the settings row")

    def test_every_game_has_its_windows_and_their_buttons(self):
        games = range(1, 6)
        self.assertEqual(self.set["windows"], sorted([f"vv{g}_mie" for g in games]
                                                     + [f"vv{g}_unicode_font" for g in games]))
        self.assertEqual(self.set["mie_buttons"], [f"vv{g}_mie" for g in games])
        for g in games:
            with self.subTest(game=g):
                self.assertEqual(self.set["settings_beside"][f"vv{g}_unicode_font"], ["Settings..."])
        others = {pid: b for pid, b in self.set["settings_beside"].items() if not pid.endswith("_unicode_font")}
        self.assertEqual({pid: b for pid, b in others.items() if b}, {}, "Settings... only beside a patch with some")

    def test_each_window_holds_its_settings(self):
        for key, window in self.set["found"].items():
            with self.subTest(window=key):
                self.assertTrue(window["again"], "a second click brings the same window")
                self.assertTrue(window["held"], "held the Windows way while open")
                self.assertTrue(window["closed"])
                if key.endswith("_mie"):
                    game = key[:3]
                    self.assertEqual((window["scales"], window["spinboxes"], window["fonts"]), (1, 1, 0))
                    self.assertEqual(window["filters"], [f"{game}_island_event_filter_f{n:02d}" for n in range(1, 29)])
                    self.assertIn("Custom Island Event Library...", window["buttons"])
                    self.assertIn("Show Player Events...", window["buttons"])
                else:
                    self.assertEqual((window["scales"], window["spinboxes"], window["fonts"]), (0, 0, 1))
        self.assertTrue(self.set["main_enabled"], "the main window is let go when the windows close")

    def test_settings_save_and_come_back(self):
        saved = self.set["saved"]
        ticked = self.set["found"]["vv5_mie"]["ticked"]
        self.assertEqual(saved["partner_carry_percent"], 55)
        self.assertEqual(saved["unicode_font"], "Arial")
        self.assertEqual(saved["village_solidarity_strength"], 2.5)
        self.assertIn(ticked, saved["fun_patches"])
        self.assertEqual(self.read["partner"], 55)
        self.assertEqual(self.read["font"], "Arial")
        self.assertEqual(self.read["solidarity"], 2.5)
        self.assertEqual(self.read["ticked"], [ticked])


if __name__ == "__main__":
    unittest.main()
