"""On a fresh install the first untick of a prerequisite must stick.

With no saved settings the GUI's dependency baseline started empty, so the
player's first click read every ticked patch as newly added and ticked the
unticked prerequisite straight back on -- its dependents stayed ticked too.
The second click worked, which is why it went unnoticed.

Each fresh start runs in its own interpreter: Tk cannot build a second App in
one process after the first is destroyed (its icon image dies with the first
root), and a child process also keeps pytest's output capture away from Tk's
own start-up.
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
sys.path.insert(0, sys.argv[1])
import vv_fun_patcher_gui as gui
gui.SETTINGS = Path(sys.argv[2])  # absent: a fresh install
try:
    app = gui.App()
except tkinter.TclError as exc:
    print(exc, file=sys.stderr)
    sys.exit(3)
app.withdraw()
v = app.fun_patch_vars
selected = sorted(k for k, var in v.items() if var.get())
dependents = {}
for patch_id, required in app._patch_dependency_map().items():
    for prerequisite in required:
        if prerequisite in v:
            dependents.setdefault(prerequisite, []).append(patch_id)
result = {"selected": selected, "dependents": dependents,
          "defaults": sorted(k for k in v if gui.default_fun_patch_selection(k))}
target = sys.argv[3]
if target:
    ticked = [d for d in dependents.get(target, []) if v[d].get()]
    v[target].set(False)  # what the Checkbutton does before its command
    app._fun_patch_changed()
    result["after"] = {k: v[k].get() for k in [target] + ticked}
app.destroy()
print(json.dumps(result))
"""


def _fresh_start(prerequisite: str = "") -> dict:
    with tempfile.TemporaryDirectory() as folder:
        completed = subprocess.run(
            [sys.executable, "-c", CHILD, str(ROOT / "src"),
             str(Path(folder) / "settings.json"), prerequisite],
            capture_output=True, text=True, timeout=120,
        )
    if completed.returncode == NO_TK:
        raise unittest.SkipTest(f"no Tk display: {completed.stderr.strip()[-200:]}")
    if completed.returncode != 0:
        raise AssertionError(completed.stderr[-2000:])
    return json.loads(completed.stdout.strip().splitlines()[-1])


class FirstUntickTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.start = _fresh_start()

    def test_there_are_prerequisites_to_exercise(self):
        self.assertTrue(self.start["dependents"], "no GUI-visible prerequisites found")

    def test_the_starting_selection_is_the_default(self):
        self.assertEqual(self.start["selected"], self.start["defaults"])

    def test_the_first_untick_of_each_prerequisite_sticks(self):
        for prerequisite in sorted(self.start["dependents"]):
            with self.subTest(prerequisite=prerequisite):
                self.assertIn(prerequisite, self.start["selected"], "ticked by default")
                after = _fresh_start(prerequisite)["after"]
                self.assertEqual(
                    after, {k: False for k in after},
                    "the prerequisite and every dependent it ticked must end unticked",
                )


if __name__ == "__main__":
    unittest.main()
