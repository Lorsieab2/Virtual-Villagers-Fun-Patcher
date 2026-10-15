"""Patch Selection Settings and the per-game patch search.

The owner: "put a button to easily tick and untick certain patches in all 5
games. like in a separate settings menu." and "add a search bar per-game for
each patch (name only)".

- Tick These / Untick These change every game's patch of the chosen name, and
  go through the same path as a click on the patch's own checkbox, so
  prerequisites, companion (COTICKED) rows and dependents behave the same.
- A game tab's search box matches patch NAMES only, never descriptions, and
  never ticks or unticks anything.  An empty box shows every patch.

The logic is checked on a stand-in for the window (no Tk needed); the real
window is checked once in its own interpreter, skipped without a Tk display.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import vv_fun_patcher_gui as gui  # noqa: E402

NO_TK = 3


class _Var:
    def __init__(self, value=None):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


def _window(ticked=()):
    """The parts of the App the selection code uses, with the real methods bound to them."""
    win = types.SimpleNamespace()
    win.fun_patches = gui.load_public_fun_patches()
    win.fun_patch_vars = {patch.id: _Var(patch.id in ticked) for patch in win.fun_patches}
    win._last_fun_selection = set(ticked)
    win.status_var = _Var("")
    win._save_settings = lambda: None
    for name in ("_selected_fun_patch_ids", "_patch_dependency_map",
                 "_apply_gui_dependency_selection", "_fun_patch_changed",
                 "_set_named_fun_patches"):
        setattr(win, name, types.MethodType(getattr(gui.App, name), win))
    return win


def _ticks(win):
    return {patch_id: var.get() for patch_id, var in win.fun_patch_vars.items()}


def _name(patch_id):
    return next(p.name for p in gui.load_public_fun_patches() if p.id == patch_id)


def _manual_clicks(win, patch_ids, tick):
    """The player's own clicks, one checkbox at a time."""
    for patch_id in patch_ids:
        if win.fun_patch_vars[patch_id].get() != tick:
            win.fun_patch_vars[patch_id].set(tick)
            win._fun_patch_changed()


class NameGroupTests(unittest.TestCase):
    def test_each_name_holds_every_games_patch_of_that_name(self):
        builds = gui.load_builds()
        patches = gui.load_public_fun_patches()
        groups = dict(gui.patches_by_name(builds, patches))
        self.assertEqual(sum(len(v) for v in groups.values()), len(patches))
        self.assertEqual({p.id for p in groups["Birth Control"]},
                         {"vv1_birth_control", "vv2_birth_control", "vv3_birth_control"})
        # In the games' order, not the catalog's.
        self.assertEqual([p.id for p in groups["Birth Control"]],
                         ["vv1_birth_control", "vv2_birth_control", "vv3_birth_control"])


class TickTheseTests(unittest.TestCase):
    def test_tick_these_ticks_the_name_in_every_game_and_leaves_others_alone(self):
        win = _window()
        before = _ticks(win)
        win._set_named_fun_patches(["Birth Control"], True)
        after = _ticks(win)
        named = {p.id for p in win.fun_patches if p.name == "Birth Control"}
        self.assertEqual(len(named), 3)
        for patch_id in named:
            self.assertTrue(after[patch_id], patch_id)
        # Birth Control needs nothing else, so nothing else moved.
        changed = {pid for pid in after if after[pid] != before[pid]}
        self.assertEqual(changed, named)

    def test_tick_these_matches_clicking_each_box_yourself(self):
        # Prerequisites included: Story / Cheat Upgrades needs Village-Wide Upgrades.
        name = _name("vv1_story_cheat_upgrades")
        ids = [p.id for p in gui.load_public_fun_patches() if p.name == name]
        bulk, by_hand = _window(), _window()
        bulk._set_named_fun_patches([name], True)
        _manual_clicks(by_hand, ids, True)
        self.assertEqual(_ticks(bulk), _ticks(by_hand))
        for game in range(1, 6):
            self.assertTrue(bulk.fun_patch_vars[f"vv{game}_origins_village_wide_upgrades"].get())

    def test_untick_these_unticks_the_name_in_every_game_and_its_dependents(self):
        everything = {p.id for p in gui.load_public_fun_patches()}
        win = _window(everything)
        name = _name("vv1_origins_village_wide_upgrades")
        named = {p.id for p in win.fun_patches if p.name == name}
        self.assertEqual(len(named), 5, "Village-Wide Upgrades is in all five games")
        win._set_named_fun_patches([name], False)
        after = _ticks(win)
        for patch_id in named:
            self.assertFalse(after[patch_id], patch_id)
        # Its dependents go with it, as when its box is unticked by hand.
        for game in range(1, 6):
            self.assertFalse(after[f"vv{game}_story_cheat_upgrades"])
            self.assertFalse(after[f"vv{game}_story_cheat_upgrades_cost_tech_points"])
        by_hand = _window(everything)
        _manual_clicks(by_hand, sorted(named), False)
        self.assertEqual(after, _ticks(by_hand))
        # Something that needs nothing stays ticked.
        self.assertTrue(after["vv1_birth_control"])

    def test_untick_these_of_a_lone_name_leaves_others_alone(self):
        everything = {p.id for p in gui.load_public_fun_patches()}
        win = _window(everything)
        win._set_named_fun_patches(["Birth Control"], False)
        after = _ticks(win)
        unticked = {pid for pid, value in after.items() if not value}
        self.assertEqual(unticked, {"vv1_birth_control", "vv2_birth_control", "vv3_birth_control"})

    def test_the_companion_row_follows_as_for_a_manual_tick(self):
        name = _name("vv1_story_cheat_upgrades")
        ids = [p.id for p in gui.load_public_fun_patches() if p.name == name]
        self.assertEqual(len(ids), 5)
        bulk, by_hand = _window(), _window()
        bulk._set_named_fun_patches([name], True)
        _manual_clicks(by_hand, ids, True)
        self.assertEqual(_ticks(bulk), _ticks(by_hand))
        for game in range(1, 6):
            partner = gui.COTICKED_FUN_PATCH_IDS[f"vv{game}_story_cheat_upgrades"]
            self.assertTrue(bulk.fun_patch_vars[partner].get(), partner)
        # Unticking the companion's name unticks only the companions.
        bulk._set_named_fun_patches([_name("vv1_story_cheat_upgrades_cost_tech_points")], False)
        for game in range(1, 6):
            self.assertTrue(bulk.fun_patch_vars[f"vv{game}_story_cheat_upgrades"].get())
            self.assertFalse(bulk.fun_patch_vars[f"vv{game}_story_cheat_upgrades_cost_tech_points"].get())


class SearchMatchTests(unittest.TestCase):
    def test_names_only_any_case(self):
        patches = gui.load_public_fun_patches()
        birth = next(p for p in patches if p.id == "vv1_birth_control")
        self.assertTrue(gui.patch_name_matches(birth, "birth"))
        self.assertTrue(gui.patch_name_matches(birth, "  CONTROL "))
        self.assertFalse(gui.patch_name_matches(birth, "pathfinding"))
        # A word of the description that is not in the name does not match.
        words = [w.strip(".,()*\"'") for w in birth.description.split()]
        only_in_description = next(
            w for w in words if len(w) >= 5 and w.casefold() not in birth.name.casefold())
        self.assertFalse(gui.patch_name_matches(birth, only_in_description))

    def test_an_empty_search_matches_everything(self):
        for patch in gui.load_public_fun_patches():
            self.assertTrue(gui.patch_name_matches(patch, ""))
            self.assertTrue(gui.patch_name_matches(patch, "   "))


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
ticks = lambda: {pid: var.get() for pid, var in app.fun_patch_vars.items()}
result = {"pages": sorted(app.patch_searches)}
var, listing, rows = app.patch_searches["A New Home"]
result["all_rows"] = len(rows)
result["shown_at_start"] = len(listing._rows)
before = ticks()
# A word from a description that no VV1 patch name holds.
names = " ".join(row[0].name.casefold() for row in rows)
term = next(w for row in rows for w in (x.strip(".,()*\"'") for x in row[0].description.split())
            if len(w) >= 6 and w.isalpha() and w.casefold() not in names)
result["description_term"] = term
var.set(term)
app.update()
result["shown_for_description_term"] = len(listing._rows)
var.set("bIrTh")
app.update()
result["shown_for_birth"] = sorted(row[0].id for row in listing._rows)
result["expected_for_birth"] = sorted(row[0].id for row in rows if "birth" in row[0].name.casefold())
result["drawn_for_birth"] = len(listing._drawn)
var.set("")
app.update()
result["shown_when_cleared"] = len(listing._rows)
result["ticks_unchanged_by_search"] = ticks() == before
# The settings window: tick a name there and press Tick These.
app._deselect_all_fun_patches()
app._open_patch_selection_settings()
app.update()
dialog = app._patch_selection_dialog
for name, choice in app._patch_selection_choices:
    choice.set(name == "Birth Control")
def walk(w):
    yield w
    for c in w.winfo_children():
        yield from walk(c)
buttons = {w.cget("text"): w for w in walk(dialog) if isinstance(w, ttk.Button)}
result["buttons"] = sorted(buttons)
buttons["Tick These"].invoke()
app.update()
result["ticked_after_tick_these"] = sorted(pid for pid, v in ticks().items() if v)
buttons["Untick These"].invoke()
app.update()
result["ticked_after_untick_these"] = sorted(pid for pid, v in ticks().items() if v)
app.destroy()
print(json.dumps(result))
"""


class RealWindowTests(unittest.TestCase):
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

    def test_every_game_tab_has_a_search_box(self):
        self.assertEqual(len(self.result["pages"]), 5)

    def test_search_is_by_name_only_and_empty_shows_all(self):
        r = self.result
        self.assertEqual(r["shown_at_start"], r["all_rows"])
        self.assertEqual(r["shown_for_description_term"], 0, r["description_term"])
        self.assertTrue(r["expected_for_birth"])
        self.assertEqual(r["shown_for_birth"], r["expected_for_birth"])
        self.assertGreater(r["drawn_for_birth"], 0)
        self.assertEqual(r["shown_when_cleared"], r["all_rows"])

    def test_search_never_changes_a_tick(self):
        self.assertTrue(self.result["ticks_unchanged_by_search"])

    def test_the_settings_window_ticks_and_unticks_in_every_game(self):
        r = self.result
        self.assertEqual(r["buttons"], ["Close", "Tick These", "Untick These"])
        self.assertEqual(r["ticked_after_tick_these"],
                         ["vv1_birth_control", "vv2_birth_control", "vv3_birth_control"])
        self.assertEqual(r["ticked_after_untick_these"], [])


if __name__ == "__main__":
    unittest.main()
