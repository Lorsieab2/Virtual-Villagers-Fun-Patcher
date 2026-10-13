"""The patch list is virtual: rows exist as widgets only near the part of the list on screen.

A row's checkbox must keep its value when the row scrolls out of view and back, and Select All
must tick every patch in every game, including rows that were never drawn.

Each run is its own interpreter (Tk cannot build a second App in one process after the first is
destroyed).  The test skips cleanly when there is no Tk display.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

NO_TK = 3

CHILD = r"""
import json, sys, tkinter
from pathlib import Path
from tkinter import ttk
sys.path.insert(0, sys.argv[1])
import vv_fun_patcher_gui as gui
gui.SETTINGS = Path(sys.argv[2])
try:
    app = gui.App()
except tkinter.TclError as exc:
    print(exc, file=sys.stderr)
    sys.exit(3)
app.update()


def walk(widget):
    yield widget
    for child in widget.winfo_children():
        yield from walk(child)


def checkbuttons(patch_id):
    variable = str(app.fun_patch_vars[patch_id])
    return [w for w in walk(app) if isinstance(w, ttk.Checkbutton) and str(w.cget("variable")) == variable]


def drawn_ids():
    names = {str(var): patch_id for patch_id, var in app.fun_patch_vars.items()}
    return {names[str(w.cget("variable"))] for w in walk(app)
            if isinstance(w, ttk.Checkbutton) and str(w.cget("variable")) in names}


lists = [w for w in walk(app) if isinstance(w, gui.VirtualList)]
TARGET = "vv1_cause_of_death"
result = {"lists": len(lists), "rows_in_lists": sum(len(vl._rows) for vl in lists)}

# The list that holds the target row: scroll every list through its length and see which draws it.
owner = None
found_at = 0.0
for vl in lists:
    for step in range(41):
        vl.yview("moveto", step / 40)
        app.update()
        if checkbuttons(TARGET):
            owner, found_at = vl, step / 40
            break
    if owner is not None:
        break
result["owner_found"] = owner is not None
# The scroll position where the target row is drawn (the search stopped there).
owner.yview("moveto", found_at)
app.update()
variable = app.fun_patch_vars[TARGET]
result["drawn_at_found"] = bool(checkbuttons(TARGET))

# Tick the row with its checkbox (a click: the checkbox toggles its variable and runs its command).
before = variable.get()
checkbuttons(TARGET)[0].invoke()
app.update()
result["before"] = before
result["after_click"] = variable.get()

# Scroll the row out of view: no widget for it, and its value is unchanged.
owner.yview("moveto", 1.0)
app.update()
result["gone_when_scrolled_out"] = not checkbuttons(TARGET)
result["value_while_out_of_view"] = variable.get()

# Scroll back up until the row shows again (the scroll position of the first search no longer
# maps to it: rows measure their real height once drawn, so the list's length changes).
def reveal(vl):
    for step in range(41):
        vl.yview("moveto", step / 40)
        app.update()
        if checkbuttons(TARGET):
            return True
    return False


result["back_in_view"] = reveal(owner)
drawn = checkbuttons(TARGET)
result["checkbox_shows"] = bool(drawn and drawn[0].instate(["selected"]))
result["value_after_return"] = variable.get()

# Select All ticks every patch, including rows never drawn at this position.
app._deselect_all_fun_patches()
app.update()
app._select_all_fun_patches()
app.update()
result["select_all_expected"] = {
    patch.id: gui.select_all_fun_patch_selection(patch.id) for patch in app.fun_patches
}
result["select_all_actual"] = {patch.id: app.fun_patch_vars[patch.id].get() for patch in app.fun_patches}
never_drawn = sorted(set(app.fun_patch_vars) - drawn_ids())
result["never_drawn_count"] = len(never_drawn)
result["never_drawn_sample_ticked"] = bool(never_drawn) and app.fun_patch_vars[never_drawn[-1]].get()
app.destroy()
print(json.dumps(result))
"""


class VirtualPatchList(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        with tempfile.TemporaryDirectory() as folder:
            completed = subprocess.run(
                [sys.executable, "-c", CHILD, str(ROOT / "src"), str(Path(folder) / "settings.json")],
                capture_output=True, text=True, timeout=300,
            )
        if completed.returncode == NO_TK:
            raise unittest.SkipTest(f"no Tk display: {completed.stderr.strip()[-200:]}")
        if completed.returncode != 0:
            raise AssertionError(completed.stderr[-2000:])
        cls.result = json.loads(completed.stdout.strip().splitlines()[-1])

    def test_one_list_per_game_and_the_target_row_is_found(self) -> None:
        self.assertEqual(self.result["lists"], 5)
        self.assertTrue(self.result["owner_found"])
        self.assertTrue(self.result["drawn_at_found"])

    def test_the_value_survives_scrolling_out_and_back(self) -> None:
        self.assertNotEqual(self.result["before"], self.result["after_click"], "the click did nothing")
        self.assertTrue(self.result["gone_when_scrolled_out"], "the row stayed drawn")
        self.assertEqual(self.result["value_while_out_of_view"], self.result["after_click"])
        self.assertTrue(self.result["back_in_view"])
        self.assertEqual(self.result["value_after_return"], self.result["after_click"])
        self.assertEqual(self.result["checkbox_shows"], self.result["after_click"])

    def test_select_all_ticks_every_patch_including_rows_never_drawn(self) -> None:
        self.assertGreater(self.result["never_drawn_count"], 0)
        self.assertTrue(self.result["never_drawn_sample_ticked"])
        self.assertEqual(self.result["select_all_actual"], self.result["select_all_expected"])


if __name__ == "__main__":
    unittest.main()
