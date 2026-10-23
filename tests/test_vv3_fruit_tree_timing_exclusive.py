"""The two fruit-tree schedules of The Secret City are never built together.

The owner's rule (binding): All Fruit Trees Refill at the Same Time and Fruit Trees Take Turns
Refilling are mutually exclusive.

  1. In the window, ticking one greys the other out with a short reason.
  2. If both are ticked anyway -- Select All, a saved selection, Patch Selection Settings, the
     command line or any other way a selection arrives -- the patcher patches nothing and shows
     an error naming both and saying to tick only one.

Each row names the other in "conflicts"; the strict resolver every build goes through
(resolve_fun_patch_ids) refuses the pair before anything is written.  The bulk buttons tick
only All Fruit Trees Refill at the Same Time, so they always give a selection that builds.
"""
from __future__ import annotations

import contextlib
import io
import json
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import vv_fun_patcher as patcher  # noqa: E402
import vv_fun_patcher_gui as gui  # noqa: E402

TOGETHER = "vv3_fruit_trees_refill_together"
TURNS = "vv3_fruit_trees_take_turns"
NAMES = {TOGETHER: "All Fruit Trees Refill at the Same Time", TURNS: "Fruit Trees Take Turns Refilling"}
STOCK_VV3 = ROOT / "inputs" / "vv3-stock-copy" / "Virtual Villagers - The Secret City.exe"
NO_TK = 3


def _refused(test: unittest.TestCase, exc: Exception) -> None:
    text = str(exc)
    for name in NAMES.values():
        test.assertIn(name, text)
    test.assertIn("tick only one", text)
    test.assertIn("Nothing was patched", text)


class _Var:
    def __init__(self, value=None):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


class _Button:
    def __init__(self):
        self.states: set[str] = set()

    def winfo_exists(self):
        return True

    def state(self, flags):
        for flag in flags:
            if flag.startswith("!"):
                self.states.discard(flag[1:])
            else:
                self.states.add(flag)


class _Label:
    def __init__(self):
        self.text = ""
        self.shown = True

    def configure(self, text):
        self.text = text

    def grid(self):
        self.shown = True

    def grid_remove(self):
        self.shown = False


def _window(ticked=()):
    """The parts of the window the selection code uses, with the real methods bound to them."""
    win = types.SimpleNamespace()
    win.fun_patches = gui.load_public_fun_patches()
    win.fun_patch_vars = {patch.id: _Var(patch.id in ticked) for patch in win.fun_patches}
    win._last_fun_selection = set(ticked)
    win.status_var = _Var("")
    win._save_settings = lambda: None
    win._conflict_rows = {pid: (_Button(), _Label()) for pid in (TOGETHER, TURNS)}
    for name in ("_selected_fun_patch_ids", "_patch_dependency_map", "_apply_gui_dependency_selection",
                 "_fun_patch_changed", "_set_named_fun_patches", "_select_all_fun_patches",
                 "_default_fun_patches", "_owners_default_fun_patches", "_deselect_all_fun_patches"):
        setattr(win, name, types.MethodType(getattr(gui.App, name), win))
    return win


class TheRowsTests(unittest.TestCase):
    def test_each_row_names_the_other_as_a_conflict(self):
        by_id = {p.id: p for p in patcher.load_public_fun_patches()}
        self.assertEqual(patcher.conflict_ids(by_id[TOGETHER]), (TURNS,))
        self.assertEqual(patcher.conflict_ids(by_id[TURNS]), (TOGETHER,))

    def test_both_descriptions_say_so_in_bold(self):
        by_id = {p.id: p for p in patcher.load_public_fun_patches()}
        for mine, other in ((TOGETHER, TURNS), (TURNS, TOGETHER)):
            bold = [text for text, is_bold in gui.split_bold(by_id[mine].description) if is_bold]
            self.assertTrue(any(NAMES[other] in text and "tick only one" in text for text in bold), mine)


class ThePatcherRefusesThePairTests(unittest.TestCase):
    def test_the_resolver_refuses_both_and_names_them(self):
        for order in ([TOGETHER, TURNS], [TURNS, TOGETHER]):
            with self.assertRaises(patcher.PatcherError) as caught:
                patcher.resolve_fun_patch_ids(order, game_id="vv3")
            _refused(self, caught.exception)
        for one in (TOGETHER, TURNS):
            self.assertEqual(patcher.resolve_fun_patch_ids([one], game_id="vv3"), [one])

    def test_either_one_composes_with_the_related_fruit_and_honey_patches(self):
        if not STOCK_VV3.is_file():
            self.skipTest("stock VV3 executable not present")
        build = {b.id: b for b in patcher.load_builds()}["vv3"]
        related = ["vv3_nature_honey_refill", "vv3_fruit_harvested_at_food_bin"]
        for one in (TOGETHER, TURNS):
            for mode in ("stock", "collection_progression", "immediate_fixed"):
                with self.subTest(one=one, mode=mode):
                    with_it, _ = patcher.render_patched_bytes(STOCK_VV3, build, mode, related + [one])
                    without, _ = patcher.render_patched_bytes(STOCK_VV3, build, mode, related)
                    # The row patches no byte of the trees' code or of the two patches' caves
                    # (it carries only Start Over's hook, for its file).
                    for start, end in ((0x33D00, 0x34E00), (0x7B2A0, 0x7B3B1)):
                        self.assertEqual(bytes(with_it[start:end]), bytes(without[start:end]))
            with self.subTest(one=one, build="256 Villagers"):
                patcher.render_patched_bytes(STOCK_VV3, build, "immediate_fixed",
                                             related + [one, "vv3_population_256"])

    def test_a_build_with_both_writes_nothing(self):
        if not STOCK_VV3.is_file():
            self.skipTest("stock VV3 executable not present")
        with tempfile.TemporaryDirectory() as out:
            for call in (
                lambda: patcher.dry_run(STOCK_VV3, "stock", [TOGETHER, TURNS], output_root=Path(out)),
                lambda: patcher.apply_patch(STOCK_VV3, "stock", False, [TOGETHER, TURNS], output_root=Path(out)),
            ):
                with self.assertRaises(patcher.PatcherError) as caught:
                    call()
                _refused(self, caught.exception)
            self.assertEqual(list(Path(out).iterdir()), [])

    def test_all_five_with_both_writes_nothing(self):
        sources = {b.id: ROOT / "inputs" / f"{b.id}-stock-copy" / b.input_name for b in patcher.load_builds()}
        if not all(path.is_file() for path in sources.values()):
            self.skipTest("the five stock executables are not present")
        with tempfile.TemporaryDirectory() as out:
            for call in (
                lambda: patcher.dry_run_all(sources, "stock", [TOGETHER, TURNS], output_root=Path(out)),
                lambda: patcher.apply_all(sources, "stock", False, [TOGETHER, TURNS], output_root=Path(out)),
            ):
                with self.assertRaises(patcher.PatcherError) as caught:
                    call()
                _refused(self, caught.exception)
            self.assertEqual(list(Path(out).iterdir()), [])

    def test_the_command_line_refuses_both(self):
        if not STOCK_VV3.is_file():
            self.skipTest("stock VV3 executable not present")
        with tempfile.TemporaryDirectory() as out:
            argv = [str(ROOT / "src" / "vv_fun_patcher.py"), "apply", str(STOCK_VV3),
                    "--fun-patch", TOGETHER, "--fun-patch", TURNS, "--output-root", out]
            printed = io.StringIO()
            old = sys.argv
            sys.argv = argv
            try:
                with contextlib.redirect_stdout(printed):
                    code = patcher.main()
            finally:
                sys.argv = old
            self.assertEqual(code, 1)
            self.assertTrue(printed.getvalue().startswith("Error: "))
            for name in NAMES.values():
                self.assertIn(name, printed.getvalue())
            self.assertEqual(list(Path(out).iterdir()), [])


class TheWindowTests(unittest.TestCase):
    def test_every_bulk_button_ticks_exactly_one(self):
        # The default and Select All tick All Fruit Trees Refill at the Same Time; the owner's
        # own Owner's Defaults ticks Fruit Trees Take Turns Refilling instead.
        for button, ticked in (("_select_all_fun_patches", TOGETHER), ("_default_fun_patches", TOGETHER),
                               ("_owners_default_fun_patches", TURNS)):
            for start in ((), (TOGETHER,), (TURNS,), (TOGETHER, TURNS)):
                with self.subTest(button=button, start=start):
                    win = _window(start)
                    getattr(win, button)()
                    self.assertEqual({pid for pid in (TOGETHER, TURNS) if win.fun_patch_vars[pid].get()}, {ticked})
                    self.assertFalse(win.status_var.get().startswith("Selection error"))
                    patcher.resolve_fun_patch_ids(win._selected_fun_patch_ids("vv3"), game_id="vv3")
        self.assertTrue(gui.default_fun_patch_selection(TOGETHER))
        self.assertFalse(gui.default_fun_patch_selection(TURNS))
        self.assertTrue(gui.select_all_fun_patch_selection(TOGETHER))
        self.assertFalse(gui.select_all_fun_patch_selection(TURNS))
        self.assertTrue(gui.owners_default_fun_patch_selection(TURNS))
        self.assertFalse(gui.owners_default_fun_patch_selection(TOGETHER))

    def test_ticking_one_greys_the_other_with_the_reason(self):
        win = _window()
        win.fun_patch_vars[TOGETHER].set(True)
        win._fun_patch_changed()
        button, reason = win._conflict_rows[TURNS]
        self.assertIn("disabled", button.states)
        self.assertTrue(reason.shown)
        self.assertIn(NAMES[TOGETHER], reason.text)
        self.assertNotIn("disabled", win._conflict_rows[TOGETHER][0].states)
        # Unticked again: both are available.
        win.fun_patch_vars[TOGETHER].set(False)
        win._fun_patch_changed()
        for pid in (TOGETHER, TURNS):
            self.assertNotIn("disabled", win._conflict_rows[pid][0].states)
            self.assertFalse(win._conflict_rows[pid][1].shown)
        # The other way round.
        win.fun_patch_vars[TURNS].set(True)
        win._fun_patch_changed()
        self.assertIn("disabled", win._conflict_rows[TOGETHER][0].states)
        self.assertIn(NAMES[TURNS], win._conflict_rows[TOGETHER][1].text)

    def test_both_ticked_anyway_is_a_selection_error_and_neither_is_greyed(self):
        # A saved selection, or Patch Selection Settings' Tick These with both names.
        win = _window()
        win._set_named_fun_patches([NAMES[TOGETHER], NAMES[TURNS]], True)
        self.assertTrue(win.fun_patch_vars[TOGETHER].get() and win.fun_patch_vars[TURNS].get())
        self.assertTrue(win.status_var.get().startswith("Selection error: "))
        self.assertIn("tick only one", win.status_var.get())
        for pid in (TOGETHER, TURNS):
            self.assertNotIn("disabled", win._conflict_rows[pid][0].states, "either can be unticked")
        # Building it is refused (the window's Patch reaches the same strict resolver).
        with self.assertRaises(patcher.PatcherError) as caught:
            patcher.resolve_fun_patch_ids(win._selected_fun_patch_ids("vv3"), game_id="vv3")
        _refused(self, caught.exception)


CHILD = r"""
import json, sys, tkinter
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import vv_fun_patcher_gui as gui
gui.SETTINGS = Path(sys.argv[2])
Path(sys.argv[2]).write_text(json.dumps({"fun_patches": sys.argv[3].split(",")}), encoding="utf-8")
try:
    app = gui.App()
except tkinter.TclError as exc:
    print(exc, file=sys.stderr)
    sys.exit(3)
app.update()
var, listing, rows = app.patch_searches["The Secret City"]
var.set("Fruit Trees")
app.update()
result = {}
for pid in ("vv3_fruit_trees_refill_together", "vv3_fruit_trees_take_turns"):
    button, reason = app._conflict_rows[pid]
    result[pid] = {"disabled": button.instate(["disabled"]), "reason": reason.cget("text"),
                   "ticked": app.fun_patch_vars[pid].get()}
result["status"] = app.status_var.get()
app.destroy()
print(json.dumps(result))
"""


class RealWindowTests(unittest.TestCase):
    def _run(self, ticked: str) -> dict:
        with tempfile.TemporaryDirectory() as folder:
            completed = subprocess.run(
                [sys.executable, "-c", CHILD, str(ROOT / "src"), str(Path(folder) / "settings.json"), ticked],
                capture_output=True, text=True, timeout=300,
            )
        if completed.returncode == NO_TK:
            raise unittest.SkipTest(f"no Tk display: {completed.stderr.strip()[-200:]}")
        if completed.returncode != 0:
            raise AssertionError(completed.stderr[-2000:])
        return json.loads(completed.stdout.strip().splitlines()[-1])

    def test_a_saved_selection_with_one_greys_the_other(self):
        r = self._run(TOGETHER)
        self.assertTrue(r[TOGETHER]["ticked"])
        self.assertFalse(r[TOGETHER]["disabled"])
        self.assertTrue(r[TURNS]["disabled"])
        self.assertIn(NAMES[TOGETHER], r[TURNS]["reason"])

    def test_a_saved_selection_with_both_leaves_both_untickable(self):
        r = self._run(TOGETHER + "," + TURNS)
        self.assertTrue(r[TOGETHER]["ticked"] and r[TURNS]["ticked"])
        self.assertFalse(r[TOGETHER]["disabled"] or r[TURNS]["disabled"])


if __name__ == "__main__":
    unittest.main()
