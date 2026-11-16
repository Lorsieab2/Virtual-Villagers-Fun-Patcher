"""Each game's "More Island Events and Creator" row (the owner, 2026-11-16): one tick over More Island Events and the
Isola Grand Event Collection -- ticking it ticks both (and their prerequisites), unticking it unticks both, and it
shows ticked while either is.  The rows keep their own ids, so saved settings and installed games need no migration.

The App runs in its own interpreter (Tk cannot build a second App in one process)."""
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
app.update()
v = app.fun_patch_vars
out = {"rows": []}
for master, ticked, joined in getattr(app, "_mie_creator_rows", []):
    game = joined[0].split("_", 1)[0]
    row = {"joined": list(joined), "start": master.get()}
    master.set(True)
    ticked()
    row["on"] = {k: v[k].get() for k in list(joined) + [game + "_story_cheat_upgrades", game + "_scrolling_popups"]}
    row["master_on"] = master.get()
    master.set(False)
    ticked()
    row["off"] = {k: v[k].get() for k in joined}
    row["master_off"] = master.get()
    v[game + "_isola_grand_event_collection"].set(True)
    app._fun_patch_changed()
    row["one_ticked"] = master.get()
    v[game + "_isola_grand_event_collection"].set(False)
    app._fun_patch_changed()
    out["rows"].append(row)
app.destroy()
print(json.dumps(out))
"""


def _run() -> dict:
    with tempfile.TemporaryDirectory() as folder:
        completed = subprocess.run([sys.executable, "-c", CHILD, str(ROOT / "src"), str(Path(folder) / "s.json")],
                                   capture_output=True, text=True, timeout=300)
    if completed.returncode == NO_TK:
        raise unittest.SkipTest(f"no Tk display: {completed.stderr.strip()[-200:]}")
    if completed.returncode != 0:
        raise AssertionError(completed.stderr[-2000:])
    return json.loads(completed.stdout.strip().splitlines()[-1])


class MoreIslandEventsAndCreator(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.out = _run()

    def test_one_row_in_each_game(self):
        games = sorted(r["joined"][0].split("_", 1)[0] for r in self.out["rows"])
        self.assertEqual(games, ["vv1", "vv2", "vv3", "vv4", "vv5"])
        for row in self.out["rows"]:
            game = row["joined"][0].split("_", 1)[0]
            self.assertEqual(sorted(row["joined"]),
                             [f"{game}_isola_grand_event_collection", f"{game}_more_island_events"])

    def test_the_tick_ticks_and_unticks_both_with_their_prerequisites(self):
        for row in self.out["rows"]:
            with self.subTest(row=row["joined"][0]):
                self.assertFalse(row["start"], "both off by default")
                self.assertTrue(all(row["on"].values()), row["on"])
                self.assertTrue(row["master_on"])
                self.assertFalse(any(row["off"].values()), row["off"])
                self.assertFalse(row["master_off"])
                self.assertTrue(row["one_ticked"], "ticked while either of its rows is")

    def test_the_guide_and_the_creator(self):
        guide = json.loads((ROOT / "data" / "how_to_use.json").read_text(encoding="utf-8"))["controls"]
        self.assertEqual(guide["more_island_events_and_creator"]["title"], "More Island Events and Creator")


if __name__ == "__main__":
    unittest.main()
