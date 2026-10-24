"""The Game Mechanics window's live features (the owner, 2026-10-24; docs/game-mechanics-window.md): a fact's
countdown, ticking from one timer without reading files; Refresh, which reads every source again and keeps the
tab, the tribe and the scroll position; Auto-refresh; the save's last-written time and the running game; the
game exe chosen with Browse..., kept in the patcher's own settings; and no callback left once it is closed.

The window itself runs in a child process (as tests/test_game_mechanics.py does) with a fake clock, a fake list
of running programs and a fake file dialog; it reads copies of the committed Secret City saves only.
"""
from __future__ import annotations

import gzip
import json
import shutil
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import vv_game_mechanics as gm  # noqa: E402
import vv_game_mechanics_window as w  # noqa: E402
from test_game_mechanics import BASE, FIXTURES, Folder  # noqa: E402

T0 = 1_800_000_000.0


class Countdown(unittest.TestCase):
    def test_words_as_the_clock_runs(self) -> None:
        due = T0 + 723
        for now, words in ((T0, "in 12 min 03 s"), (T0 + 0.4, "in 12 min 03 s"), (T0 + 1, "in 12 min 02 s"),
                           (T0 + 663, "in 1 min 00 s"), (T0 + 664, "in 59 s"), (T0 + 722, "in 1 s"),
                           (T0 + 722.9, "in 1 s")):
            with self.subTest(now=now):
                self.assertEqual(gm.countdown(due, now), words)
        self.assertEqual(gm.countdown(T0 + 3 * 3600 + 5, T0), "in 3 h 00 min 05 s")
        self.assertEqual(gm.countdown(T0 + 2 * 86_400 + 3661, T0), "in 2 d 1 h 01 min 01 s")

    def test_zero_crossing(self) -> None:
        due = T0 + 10
        self.assertEqual(gm.countdown(due, due - 0.001), "in 1 s")
        for now in (due, due + 0.5, due + 3600):
            with self.subTest(now=now):
                self.assertEqual(gm.countdown(due, now), gm.DUE_NOW)
                self.assertEqual(gm.countdown_span(due, now), ", due now (refresh to see the new state)")
        self.assertEqual(gm.countdown_span(due, due - 5), " (in 5 s)")


class Placement(unittest.TestCase):
    def facts(self):
        return [gm.Fact("Refills", f"Honey: 40 of 100; the next refill is {gm.DUE}.", gm.SAVE, due=T0 + 723,
                        due_kind="refill"),
                gm.Fact("Refills", "Berries refill every 3 hours.", False, due=T0 + 5, due_kind="refill"),
                gm.Fact("Refills", f"At {gm.when(T0 + 90_000)} the crop is ready.", gm.SAVE, due=T0 + 90_000,
                        due_kind="ready", sub=True),
                gm.Fact("Refills", "Paused: nothing refills until the game is unpaused.", gm.SAVE)]

    def test_date_then_countdown_on_the_same_bullet(self) -> None:
        text, spans = gm.render_live(self.facts(), T0)
        lines = text.split("\n")
        self.assertEqual(lines[1], f"{gm.BULLET}Honey: 40 of 100; the next refill is {gm.when(T0 + 723)} "
                                   "(in 12 min 03 s).")
        self.assertEqual(lines[2], f"{gm.BULLET}{gm.UNCONFIRMED}  Berries refill every 3 hours. Next refill: "
                                   f"{gm.when(T0 + 5)} (in 5 s).")
        self.assertEqual(lines[3], f"{gm.SUB_BULLET}At {gm.when(T0 + 90_000)} (in 1 d 1 h 00 min 00 s) the crop "
                                   "is ready.")
        self.assertEqual(lines[4], f"{gm.BULLET}Paused: nothing refills until the game is unpaused.")
        self.assertEqual(len(spans), 3)
        for span, words in zip(spans, (" (in 12 min 03 s)", " (in 5 s)", " (in 1 d 1 h 00 min 00 s)")):
            self.assertEqual(lines[span.line - 1][span.column:span.column + span.length], words)
        # The plain render is the same text, and a fact without a due is unchanged by it.
        self.assertEqual(gm.render(self.facts(), T0), text)
        self.assertEqual(gm.render([gm.Fact("Other", "No timer.", gm.SAVE)]), f"Other\n{gm.BULLET}No timer.")

    def test_the_general_rules_leave_a_due_out(self) -> None:
        module = types.SimpleNamespace(facts=lambda village: [
            gm.Fact("Refills", "Honey refills every 3 hours.", True),
            gm.Fact("Refills", f"The next refill is {gm.DUE}.", True, due=village.now + 60, due_kind="refill")])
        with mock.patch.object(gm.importlib, "import_module", return_value=module):
            kept = gm.general(3, T0)
        self.assertEqual([fact.text for fact in kept], ["Honey refills every 3 hours."])


class Running(unittest.TestCase):
    class Processes:
        def __init__(self, *names):
            self.names = {name.casefold() for name in names}
            self.asked = []

        def find(self, name):
            self.asked.append(name)
            return [42] if name.casefold() in self.names else []

        def suspend(self, *_):          # never called: the window only looks
            raise AssertionError("the window must never pause a game")

        resume = suspend

    def test_found_by_the_save_folders_game_or_the_chosen_exe(self) -> None:
        folder = Path("C:/LDW") / BASE
        self.assertFalse(w.game_running(folder, None, self.Processes()))
        self.assertTrue(w.game_running(folder, None, self.Processes(BASE.upper() + ".EXE")))
        chosen = Path("D:/Games/My Copy.exe")
        self.assertFalse(w.game_running(folder, None, self.Processes("My Copy.exe")))
        self.assertTrue(w.game_running(folder, chosen, self.Processes("my copy.exe")))

    def test_a_list_that_cannot_be_read_is_not_running(self) -> None:
        class Broken:
            def find(self, name):
                raise OSError("no list")
        self.assertFalse(w.game_running(Path("x") / BASE, None, Broken()))

    def test_status_words(self) -> None:
        root = Path(tempfile.mkdtemp(prefix="gmr"))
        self.addCleanup(shutil.rmtree, root, True)
        save = root / f"{BASE}1.ldw"
        save.write_bytes(b"ldwg")
        written = gm.when(save.stat().st_mtime)
        self.assertEqual(w.save_status(save, False), f"The save was last written {written}.")
        self.assertTrue(w.save_status(save, True).startswith(
            f"The game is running: values are from the last save at {written}."))
        self.assertIn("could not be read", w.save_status(root / "missing.ldw", False))


class BrowsePersistence(unittest.TestCase):
    def test_kept_per_save_folder_in_the_app_settings(self) -> None:
        saved = []
        app = types.SimpleNamespace(_save_settings=lambda: saved.append(dict(app.game_mechanics_exes)))
        one, two = Path("C:/LDW/One"), Path("C:/LDW/Two")
        self.assertIsNone(w.chosen_exe(app, one))
        w.remember_exe(app, one, Path("D:/Games/One.exe"))
        w.remember_exe(app, two, Path("D:/Other/Two.exe"))
        self.assertEqual(w.chosen_exe(app, one), Path("D:/Games/One.exe"))
        self.assertEqual(w.chosen_exe(app, two), Path("D:/Other/Two.exe"))
        self.assertEqual(len(saved), 2)
        self.assertEqual(saved[-1], {str(one): str(Path("D:/Games/One.exe")), str(two): str(Path("D:/Other/Two.exe"))})

    def test_the_patchers_settings_file_keeps_it(self) -> None:
        import vv_fun_patcher_gui as gui

        class Var:
            def __init__(self, value=""):
                self.value = value

            def get(self):
                return self.value

            def set(self, value):
                self.value = value

        root = Path(tempfile.mkdtemp(prefix="gms"))
        self.addCleanup(shutil.rmtree, root, True)
        settings = root / "patcher_local_settings.json"
        choice = {str(Path("C:/LDW") / BASE): str(Path("D:/Games") / f"{BASE}.exe")}

        def fake():
            return types.SimpleNamespace(
                _mode=lambda: "standard", exe_var=Var(), output_root_var=Var(), check_logs_var=Var(True),
                _selected_fun_patch_ids=lambda: [], pair_rules={}, tree_window={}, tree_style={}, builds=[],
                all_folder_vars={}, patch_modes=[], patch_mode_var=Var(), game_mechanics_exes={})

        with mock.patch.object(gui, "SETTINGS", settings):
            first = fake()
            first.game_mechanics_exes = dict(choice)
            gui.App._save_settings(first)
            self.assertEqual(json.loads(settings.read_text(encoding="utf-8"))["game_mechanics_exes"], choice)
            data = json.loads(settings.read_text(encoding="utf-8"))
            del data["fun_patches"]                      # nothing of the patch list is needed here
            settings.write_text(json.dumps(data), encoding="utf-8")
            again = fake()
            gui.App._load_settings(again)
            self.assertEqual(again.game_mechanics_exes, choice)
            settings.write_text(json.dumps({"game_mechanics_exes": ["not", "a", "dict"]}), encoding="utf-8")
            gui.App._load_settings(again)
            self.assertEqual(again.game_mechanics_exes, {})


TK_CHILD = r"""
import json, sys, tkinter
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import vv_save_backup, vv_game_mechanics as gm, vv_game_mechanics_window as w
folder, exe = Path(sys.argv[2]), Path(sys.argv[3])
T0 = float(sys.argv[4])
vv_save_backup.documents_folder = lambda: folder.parent
vv_save_backup.find_save_folders = lambda title, documents: [folder] if "Secret City" in title else []
now = {"t": T0}
w.clock = lambda: now["t"]
class Processes:
    names = set()
    def find(self, name):
        return [7] if name.casefold() in self.names else []
procs = Processes()
w.PROCESSES = procs
reads = []
real_read = gm.read
def fake_read(folder, game, slot, game_folders=None, now=None, exe=None):
    reads.append((game, slot, None if exe is None else str(exe)))
    facts = real_read(folder, game, slot, game_folders, now=now, exe=exe)
    return facts + [gm.Fact("Other", f"Test timer: {gm.DUE}.", gm.SAVE, due=now + 125, due_kind="due")]
gm.read = fake_read
try:
    root = tkinter.Tk()
except tkinter.TclError as exc:
    print(exc, file=sys.stderr)
    sys.exit(3)
root.withdraw()
class Build:
    def __init__(self, title):
        self.title = title
titles = ["Virtual Villagers - A New Home", "Virtual Villagers - The Lost Children",
          "Virtual Villagers - The Secret City", "Virtual Villagers - The Tree of Life",
          "Virtual Villagers - New Believers"]
root.builds = [Build(t) for t in titles]
root._game_folders_for = lambda save_folder: []          # the game is not found: Browse... finds it
root.game_mechanics_exes = {}
saved = []
root._save_settings = lambda: saved.append(dict(root.game_mechanics_exes))
out = {}
def after_ids():
    return set(root.tk.splitlist(root.tk.call("after", "info")))
before = after_ids()
window = w.open_game_mechanics(root, root.builds[2])
window.update()
tab = window.mechanics_tabs[3]
page = tab["page"]
def timer_line():
    at = page.search("Test timer:", "1.0")
    return page.get(f"{at} linestart", f"{at} lineend")
def sources():
    at = page.search("The patches in the game", "1.0")
    return page.get(f"{at} linestart", f"{at} lineend") if at else page.get("1.0", "end")
out["jobs_open"] = sorted(window.mechanics_jobs)
out["first"] = timer_line()
out["status"] = tab["status"].cget("text")
out["sources_before"] = "Could not tell which patches this game has" in page.get("1.0", "end")
reads_at_open = len(reads)
# The timer itself, as it runs: one second on, the countdown has moved by itself.
import time
now["t"] = T0 + 3
stop = time.monotonic() + w.TICK_MS / 1000 + 1.5
while time.monotonic() < stop and "(in 2 min 02 s)" not in timer_line():
    root.update()
    time.sleep(0.02)
out["timer_ran"] = timer_line()
# Ticks: the countdown runs from the one timer; no file is read.
now["t"] = T0 + 65
window.mechanics_tick()
out["tick65"] = timer_line()
now["t"] = T0 + 125
window.mechanics_tick()
out["tick125"] = timer_line()
now["t"] = T0 + 400
window.mechanics_tick()
out["tick400"] = timer_line()
out["reads_ticking"] = len(reads) - reads_at_open
out["one_timer"] = sorted(window.mechanics_jobs)
# Refresh: the second tribe chosen and the page scrolled to its last group first.
slots = tab["slots"]
first_pick = slots.curselection()[0]
out["second_tribe"] = False
for n in [n for n in range(slots.size()) if n != first_pick] + [first_pick]:
    slots.selection_clear(0, "end")
    slots.selection_set(n)
    tab["show"]()
    if tab["groups"]:
        out["second_tribe"] = out["second_tribe"] or n != first_pick
        break
window.update()
tab["jump"](tab["groups"][-1])
window.update()
top_before, slot_before = page.index("@0,0"), slots.curselection()
tab_before = window.mechanics_notebook.index(window.mechanics_notebook.select())
reads_before = len(reads)
now["t"] = T0 + 500
window.mechanics_refresh()
window.update()
out["refresh_reads"] = len(reads) - reads_before
out["refreshed"] = timer_line()
out["kept"] = [page.index("@0,0") == top_before, slots.curselection() == slot_before,
               window.mechanics_notebook.index(window.mechanics_notebook.select()) == tab_before,
               page.yview()[0] > 0.0]
# Auto-refresh: off by default; on, every 30 seconds from the one timer.
out["auto_default"] = bool(window.mechanics_auto.get())
reads_before = len(reads)
now["t"] = T0 + 600
window.mechanics_tick()
out["auto_off_reads"] = len(reads) - reads_before
window.mechanics_auto_button.invoke()                 # ticked at T0 + 600
now["t"] = T0 + 629
window.mechanics_tick()
out["auto_29"] = len(reads) - reads_before
now["t"] = T0 + 630
window.mechanics_tick()
out["auto_30"] = len(reads) - reads_before
now["t"] = T0 + 661
window.mechanics_tick()
out["auto_61"] = len(reads) - reads_before
window.mechanics_auto_button.invoke()                 # off again
now["t"] = T0 + 800
window.mechanics_tick()
out["auto_off_again"] = len(reads) - reads_before
# The running game.
procs.names = {(folder.name + ".exe").casefold()}
window.mechanics_refresh()
window.update()
out["running"] = tab["status"].cget("text")
procs.names = set()
window.mechanics_refresh()
out["not_running"] = tab["status"].cget("text")
# Browse...: the chosen exe is kept for the save folder and read at once.
w.ask_exe = lambda parent, where, current: str(exe)
tab["browse"].invoke()
window.update()
out["saved"] = saved
out["browse_reads"] = reads[-1][2]
out["sources_after"] = sources()
# Close: nothing left scheduled.
window.mechanics_close()
root.update()
out["left"] = sorted(after_ids() - before)
out["left_scripts"] = [str(root.tk.call("after", "info", j)) for j in out["left"]]
out["jobs_closed"] = sorted(window.mechanics_jobs)
# Opened again: the choice is still there.
again = w.open_game_mechanics(root, root.builds[2])
again.update()
out["again_reads"] = reads[-1][2]
again.mechanics_tabs[3]["page"].see("end")
again.destroy()                                         # closed by its parent, not its button
root.update()
out["left_again"] = sorted(after_ids() - before)
root.destroy()
print(json.dumps(out))
"""


class Window(unittest.TestCase):
    def test_live_window(self) -> None:
        folder = Folder(self, BASE)
        for slot, source in ((0, 0), (1, 1), (2, 1)):          # two tribes at least, to keep the second one
            data = gzip.decompress((FIXTURES / f"vv3-huttest-{source}.ldw.gz").read_bytes())
            (folder.path / f"{BASE}{slot}.ldw").write_bytes(data)
        exe = folder.game(["vv3_nature_honey_refill"]) / f"{BASE}.exe"
        done = subprocess.run([sys.executable, "-c", TK_CHILD, str(ROOT / "src"), str(folder.path), str(exe),
                               repr(T0)], capture_output=True, text=True, timeout=180)
        if done.returncode == 3:
            self.skipTest("no Tk display: " + done.stderr.strip())
        self.assertEqual(done.returncode, 0, done.stderr)
        out = json.loads(done.stdout.strip().splitlines()[-1])
        date = gm.when(T0 + 125)
        self.assertEqual(out["jobs_open"], ["tick"])
        self.assertEqual(out["first"], f"{gm.BULLET}Test timer: {date} (in 2 min 05 s).")
        self.assertTrue(out["status"].startswith("The save was last written "), out["status"])
        self.assertTrue(out["sources_before"])
        self.assertEqual(out["timer_ran"], f"{gm.BULLET}Test timer: {date} (in 2 min 02 s).")
        self.assertEqual(out["tick65"], f"{gm.BULLET}Test timer: {date} (in 1 min 00 s).")
        self.assertEqual(out["tick125"], f"{gm.BULLET}Test timer: {date}, due now (refresh to see the new state).")
        self.assertEqual(out["tick400"], out["tick125"])
        self.assertEqual(out["reads_ticking"], 0)                    # a tick reads nothing
        self.assertEqual(out["one_timer"], ["tick"])
        # Refresh read the save again, restarted the countdown and kept the tribe, the tab and the scroll.
        self.assertEqual(out["refresh_reads"], 1)
        self.assertEqual(out["refreshed"], f"{gm.BULLET}Test timer: {gm.when(T0 + 625)} (in 2 min 05 s).")
        self.assertEqual(out["kept"], [True, True, True, True])
        self.assertTrue(out["second_tribe"])                         # the tribe kept was not the first one
        self.assertFalse(out["auto_default"])
        self.assertEqual((out["auto_off_reads"], out["auto_29"], out["auto_30"], out["auto_61"],
                          out["auto_off_again"]), (0, 0, 1, 2, 2))
        self.assertTrue(out["running"].startswith("The game is running: values are from the last save at "),
                        out["running"])
        self.assertTrue(out["not_running"].startswith("The save was last written "))
        self.assertEqual(out["saved"], [{str(folder.path): str(exe)}])
        self.assertEqual(out["browse_reads"], str(exe))
        self.assertIn(f"The patches in the game: {exe}, as listed by the patcher's transparency log",
                      out["sources_after"])
        self.assertEqual(out["left"], [], out["left_scripts"])
        self.assertEqual(out["jobs_closed"], [])
        self.assertEqual(out["again_reads"], str(exe))
        self.assertEqual(out["left_again"], [])


if __name__ == "__main__":
    unittest.main()
