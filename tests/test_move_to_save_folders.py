"""Repair Saves & Logs' "Move Files to Save Folders..." (src/vv_move_to_save_folders.py; the owner,
2026-10-17: "ADD A BUTTON TO MOVE EXISTING FILES TO ITS SAVE FOLDER").

For all five games: what moves and what does not (with the reason), the refusals (game running, a patch
that reads only the older folders, the game not found) that change nothing, a move that leaves
byte-identical files in each save's own folder with the copies made first kept and the word boundaries
copied, and a failure at every step that puts everything back byte for byte.  Every folder is built in
a temporary folder; no game is run."""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import vv_log_tools as tools  # noqa: E402
import vv_move_to_save_folders as mv  # noqa: E402
import vv_save_layout as layout  # noqa: E402

LOGS, DATA, SAVES, TREES = layout.LOGS, layout.DATA, layout.SAVES, layout.TREES
COPIES = f"{DATA}\\{layout.COPIES}"
NOW = datetime(2026, 10, 17, 12, 0, 0)
GAMES = {
    1: "Virtual Villagers - A New Home - Modded",
    2: "Virtual Villagers - The Lost Children - Modded",
    3: "Virtual Villagers - The Secret City - Modded",
    4: "Virtual Villagers - The Tree of Life - Modded",
    5: "Virtual Villagers - New Believers - Modded",
}
OLD_TIME = 1_700_000_000 * 10**9
NEW_DLL = b"MZ...Virtual Villagers Fun Patcher Logs...Virtual Villagers Fun Patcher\\Save %d..."
OLD_DLL = b"MZ...Virtual Villagers Fun Patcher Logs\\Save %d\\..."


class Processes:
    def __init__(self, answers=()):
        self.answers = list(answers)       # pids per call; the last repeats

    def find(self, exe_name):
        if not self.answers:
            return []
        return list(self.answers.pop(0) if len(self.answers) > 1 else self.answers[0])


def write(path: Path, data: str | bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data.encode("latin-1") if isinstance(data, str) else data)
    os.utime(path, ns=(OLD_TIME, OLD_TIME))


def tree(folder: Path) -> dict[str, bytes]:
    return {str(p.relative_to(folder)): p.read_bytes() for p in sorted(folder.rglob("*")) if p.is_file()}


def folders(folder: Path) -> set[str]:
    return {str(p.relative_to(folder)) for p in folder.rglob("*") if p.is_dir()}


def win(rel: str) -> str:
    return rel.replace("/", "\\")


class Scene:
    """One game's save folder holding files of saves 1, 2 and 3 in the older folders, and its game."""

    def __init__(self, root: Path, game: int, dll: bytes | None = None, utf16: bool = False):
        self.game = game
        name = GAMES[game]
        self.folder = root / "LDW" / name
        self.install = root / "Games" / name
        f, g = self.folder, game
        write(f / f"VirtualVillagers{g}.ldw", b"the game's own save")
        self.births = win(f"{LOGS}/Save 1/Births and Conceptions/Virtual Villagers {g} Births Log 1.txt")
        self.deaths = win(f"{LOGS}/Save 1/Deaths and Disappearances/Virtual Villagers {g} Deaths Log 1.txt")
        self.history = win(f"{LOGS}/Save 2/Tribe History/Village History 1.txt")
        self.titles = win(f"{DATA}/Custom Titles/Custom Titles - Save 1.dat")
        self.graves = win(f"{DATA}/Graves/Virtual Villagers {g} Graves - Save 2.dat")
        self.taken = win(f"{DATA}/Custom Titles/Custom Titles - Save 3.dat")
        self.taken_new = win(f"{SAVES}/Save 3/Data/Custom Titles/Custom Titles - Save 3.dat")
        self.shared = win(f"{LOGS}/Births and Conceptions/Virtual Villagers {g} Births Log 1.txt")
        self.cross = win(f"{DATA}/Cross-Check/Virtual Villagers {g} Cross-Check - Save 1.dat")
        self.roster = win(f"{DATA}/Village Statistics/Village Roster - Save 1.dat")
        self.words = win(f"{DATA}/{layout.LOG_WORDS}/Virtual Villagers {g} Log Words.dat")
        self.old_words = win(f"{DATA}/Log Words/Virtual Villagers {g} Log Words.dat")
        self.loose_data = win(f"{DATA}/Virtual Villagers {g} Graves_1.dat")
        self.loose_save = "vvfp_masks_1.dat"
        self.unslotted = win(f"{DATA}/Last Names/Last Names.dat")
        write(f / self.births, f"Village: Ann (Save 1)\r\nConception 1\r\n  Mother: Ann\r\n\r\n")
        write(f / self.deaths, f"Village: Ann (Save 1)\r\nDeath 1\r\n  Name: Bo\r\n\r\n")
        write(f / self.history, "Village: Cy (Save 2)\r\nday 1\r\n")
        write(f / self.titles, b"\x01\x02titles 1")
        write(f / self.graves, b"\x03graves 2")
        write(f / self.taken, b"old titles 3")
        write(f / self.taken_new, b"new titles 3")
        write(f / self.shared, "Village: Ann (Save 1)\r\nConception 1\r\n\r\nVillage: Cy (Save 2)\r\nConception 2\r\n")
        write(f / self.cross, b"cross")
        write(f / self.roster, b"roster")
        write(f / self.words, f"50\t{self.births}\r\n30\t{self.births}\r\n45\t{self.deaths}\r\n0\t{self.shared}\r\n"
              .encode("utf-8"))
        write(f / self.old_words, f"25\t{self.deaths}\r\n".encode("utf-8"))
        write(f / COPIES / "an older copy.txt", b"copy")
        write(f / "Backups" / "Backup 2026-01-01 00-00-00" / f"VirtualVillagers{g}.ldw", b"backup")
        write(f / TREES / "My tree.vvtree", b"tree")
        write(f / self.loose_data, b"loose")
        write(f / self.loose_save, b"loose save")
        write(f / self.unslotted, b"names")
        write(self.install / f"{name}.exe", b"MZ")
        write(self.install / "unrelated.dll", b"MZ nothing of ours")
        library = (dll if dll is not None else NEW_DLL % g)
        if utf16:
            library = library.decode("latin-1").encode("utf-16-le")
        write(self.install / mv.PATCH_FILES / "vvfp_logs.dll", library)

    def new(self, rel: str) -> str:
        return layout.per_save_place(rel)[1]

    @property
    def moved(self) -> list[str]:
        return [self.births, self.deaths, self.history, self.titles, self.graves]

    def move(self, processes=None, **kwargs):
        return mv.move_to_save_folders(self.folder, [self.install], processes or Processes(), NOW, **kwargs)


class MoveToSaveFoldersTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def scene(self, game: int, **kwargs) -> Scene:
        return Scene(self.root / f"g{game}-{len(list(self.root.iterdir()))}", game, **kwargs)

    # -- the plan ------------------------------------------------------------------------------------

    def test_plan_lists_every_move_and_every_reason(self) -> None:
        for game in GAMES:
            with self.subTest(game=game):
                s = self.scene(game)
                before = tree(s.folder)
                work = mv.plan(s.folder)
                self.assertEqual(work.game, game)
                got = {(m.slot, m.old, m.new) for m in work.moves}
                self.assertEqual(got, {
                    (1, s.births, win(f"{SAVES}/Save 1/Logs/Births and Conceptions/Virtual Villagers {game} Births Log 1.txt")),
                    (1, s.deaths, win(f"{SAVES}/Save 1/Logs/Deaths and Disappearances/Virtual Villagers {game} Deaths Log 1.txt")),
                    (2, s.history, win(f"{SAVES}/Save 2/Logs/Tribe History/Village History 1.txt")),
                    (1, s.titles, win(f"{SAVES}/Save 1/Data/Custom Titles/Custom Titles - Save 1.dat")),
                    (2, s.graves, win(f"{SAVES}/Save 2/Data/Graves/Virtual Villagers {game} Graves - Save 2.dat")),
                })
                left = {item.what: (item.reason, item.slot) for item in work.left}
                self.assertEqual(left[s.taken], (mv.R_EXISTS, 3))
                self.assertEqual(left[s.shared][0], mv.R_SHARED_LOG)
                self.assertEqual(left[s.cross], (mv.R_OLD_NAME, 1))
                self.assertEqual(left[s.roster], (mv.R_OLD_NAME, 1))
                self.assertEqual(left[s.old_words][0], mv.R_OLD_NAME)
                self.assertEqual(left[s.words][0], mv.R_WORDS)
                self.assertEqual(left[COPIES + "\\"][0], mv.R_COPIES)
                self.assertEqual(left["Backups\\"][0], mv.R_BACKUPS)
                self.assertEqual(left[TREES + "\\"][0], mv.R_TREES)
                self.assertEqual(left[s.loose_data][0], mv.R_LOOSE_DATA)
                self.assertEqual(left[s.loose_save][0], mv.R_LOOSE_SAVE)
                self.assertEqual(left[s.unslotted][0], mv.R_NOT_SAVE)
                self.assertFalse(any(w.endswith(".ldw") for w in left))
                text = work.describe()
                self.assertIn(mv.GAME_TITLES[game], text)
                for m in work.moves:
                    self.assertIn(m.old, text)
                    self.assertIn(m.new, text)
                for item in work.left:
                    self.assertIn(item.reason, text)
                self.assertEqual(tree(s.folder), before)

    # -- refusals ------------------------------------------------------------------------------------

    def test_refused_while_the_game_runs(self) -> None:
        for game in GAMES:
            with self.subTest(game=game):
                s = self.scene(game)
                before, dirs = tree(s.folder), folders(s.folder)
                with self.assertRaises(tools.GameRunning) as caught:
                    s.move(Processes([[1234]]))
                self.assertIn("Nothing was changed", str(caught.exception))
                self.assertEqual((tree(s.folder), folders(s.folder)), (before, dirs))

    def test_refused_when_a_patch_reads_only_the_older_folders(self) -> None:
        for game in GAMES:
            for utf16 in (False, True):
                with self.subTest(game=game, utf16=utf16):
                    s = self.scene(game, dll=OLD_DLL % game, utf16=utf16)
                    before, dirs = tree(s.folder), folders(s.folder)
                    check = mv.check_install(s.folder, [s.install])
                    self.assertTrue(check.refused)
                    self.assertEqual([p.name for p in check.older], ["vvfp_logs.dll"])
                    with self.assertRaises(mv.MoveError) as caught:
                        s.move()
                    self.assertIn("vvfp_logs.dll", str(caught.exception))
                    self.assertIn("Patch the game again with this patcher first", str(caught.exception))
                    self.assertEqual((tree(s.folder), folders(s.folder)), (before, dirs))

    def test_a_patch_with_the_marker_is_accepted_in_either_encoding(self) -> None:
        for utf16 in (False, True):
            s = self.scene(1, utf16=utf16)
            self.assertFalse(mv.check_install(s.folder, [s.install]).refused)

    def test_refused_when_the_game_is_not_found(self) -> None:
        for game in GAMES:
            with self.subTest(game=game):
                s = self.scene(game)
                before, dirs = tree(s.folder), folders(s.folder)
                (s.install / f"{GAMES[game]}.exe").unlink()
                with self.assertRaises(mv.MoveError) as caught:
                    s.move()
                self.assertIn("was not found", str(caught.exception))
                with self.assertRaises(mv.MoveError):
                    mv.move_to_save_folders(s.folder, [], Processes(), NOW)
                self.assertEqual((tree(s.folder), folders(s.folder)), (before, dirs))

    # -- the move ------------------------------------------------------------------------------------

    def test_a_move_puts_identical_files_in_each_saves_folder(self) -> None:
        for game in GAMES:
            with self.subTest(game=game):
                s = self.scene(game)
                f = s.folder
                before = tree(f)
                stamps = {rel: (f / rel).stat().st_mtime_ns for rel in s.moved}
                work = mv.plan(f)
                result = s.move(confirmed=work)
                self.assertEqual({m.old for m in result.moved}, set(s.moved))
                after = tree(f)
                for rel in s.moved:
                    new = s.new(rel)
                    self.assertFalse((f / rel).exists(), rel)
                    self.assertEqual(after[new], before[rel])
                    self.assertEqual((f / new).stat().st_mtime_ns, stamps[rel])
                    copy = tools.copy_before_repair(f, f / rel, mv.COPY_SUFFIX)
                    self.assertEqual(copy.read_bytes(), before[rel])
                    self.assertEqual(layout.route(f, rel), f / new)
                # The older Save 1 and Save 2 log folders were emptied and removed; the shared ones stay.
                self.assertFalse((f / LOGS / "Save 1").exists())
                self.assertFalse((f / LOGS / "Save 2").exists())
                self.assertTrue((f / s.shared).is_file())
                # Every file not moved is as it was (the shared words file too).
                for rel, data in before.items():
                    if rel not in s.moved:
                        self.assertEqual(after[rel], data, rel)
                # The boundaries, under the new names, in the save's own words file (the smallest).
                own = layout.save_words_file(f, game, 1).read_bytes().decode("utf-8")
                self.assertIn(f"30\t{s.new(s.births)}\r\n", own)
                self.assertIn(f"25\t{s.new(s.deaths)}\r\n", own)
                self.assertFalse(layout.save_words_file(f, game, 2).exists())
                # One Repairs Made record per save moved, in that save's own folder.
                for slot, mine in ((1, [s.births, s.deaths, s.titles]), (2, [s.history, s.graves])):
                    logs = f / SAVES / f"Save {slot}" / "Logs" / layout.REPAIRS_LOGS
                    record = "".join(p.read_bytes().decode("latin-1") for p in logs.glob("*.txt"))
                    self.assertIn("Repair ", record)
                    for rel in mine:
                        self.assertIn(f"Moved: {rel} -> {s.new(rel)}", record)
                    self.assertIn("Copies made first:", record)
                    if slot == 1:
                        self.assertIn(f"Not moved: {s.cross} ({mv.R_OLD_NAME})", record)
                self.assertFalse((f / SAVES / "Save 3" / "Logs").exists())
                # Moving again finds nothing more to move.
                self.assertEqual(mv.plan(f).moves, [])

    # -- failures ------------------------------------------------------------------------------------

    def _fail_second(self, name: str):
        real = getattr(mv, name)
        calls = {"n": 0}

        def failing(*args, **kwargs):
            calls["n"] += 1
            if calls["n"] == 2:
                raise OSError("injected failure")
            return real(*args, **kwargs)
        return mock.patch.object(mv, name, failing)

    def _check_put_back(self, s: Scene, before: dict, stamps: dict, dirs: set, copies_left: bool) -> None:
        f = s.folder
        after = {k: v for k, v in tree(f).items() if not k.startswith(COPIES + "\\")}
        self.assertEqual(after, {k: v for k, v in before.items() if not k.startswith(COPIES + "\\")})
        for rel, when in stamps.items():
            self.assertEqual((f / rel).stat().st_mtime_ns, when, rel)
        self.assertEqual(folders(f) - {d for d in folders(f) if d.startswith(COPIES)},
                         {d for d in dirs if not d.startswith(COPIES)})
        copies = [p for p in (f / COPIES).rglob("*") if p.is_file() and mv.COPY_SUFFIX in p.name]
        self.assertEqual(bool(copies), copies_left)

    def test_a_failure_at_any_step_puts_everything_back(self) -> None:
        steps = {
            "step 2": "_back_up_one",
            "step 3": "_copy_one",
            "step 4": "_append_words",
            "step 5": "_remove_original",
        }
        for game in GAMES:
            for step, name in steps.items():
                with self.subTest(game=game, step=step):
                    s = self.scene(game)
                    before, dirs = tree(s.folder), folders(s.folder)
                    stamps = {rel: (s.folder / rel).stat().st_mtime_ns for rel in s.moved}
                    with self._fail_second(name), self.assertRaises(mv.MoveError) as caught:
                        s.move()
                    self.assertIn("Everything was put back", str(caught.exception))
                    self.assertIn("injected failure", str(caught.exception))
                    self._check_put_back(s, before, stamps, dirs, copies_left=True)

    def test_a_failure_removing_the_empty_folders_puts_everything_back(self) -> None:
        for game in GAMES:
            with self.subTest(game=game):
                s = self.scene(game)
                before, dirs = tree(s.folder), folders(s.folder)
                stamps = {rel: (s.folder / rel).stat().st_mtime_ns for rel in s.moved}
                with mock.patch.object(mv, "_remove_empty", side_effect=OSError("injected failure")), \
                        self.assertRaises(mv.MoveError):
                    s.move()
                self._check_put_back(s, before, stamps, dirs, copies_left=True)

    def test_the_game_started_during_the_move_puts_everything_back(self) -> None:
        for game in GAMES:
            with self.subTest(game=game):
                s = self.scene(game)
                before, dirs = tree(s.folder), folders(s.folder)
                stamps = {rel: (s.folder / rel).stat().st_mtime_ns for rel in s.moved}
                with self.assertRaises(mv.MoveError) as caught:
                    s.move(Processes([[], [99]]))
                self.assertIn("is running", str(caught.exception))
                self._check_put_back(s, before, stamps, dirs, copies_left=True)

    def test_no_repairs_record_when_the_move_fails(self) -> None:
        s = self.scene(3)
        with self._fail_second("_copy_one"), self.assertRaises(mv.MoveError):
            s.move()
        self.assertFalse((s.folder / SAVES / "Save 1").exists())


DIALOG_CHILD = r"""
import sys, tkinter
sys.path.insert(0, sys.argv[1])
try:
    root = tkinter.Tk()
except tkinter.TclError as exc:
    print(exc, file=sys.stderr)
    sys.exit(3)
import vv_fun_patcher_gui as gui
root.geometry("1x1+-4000+-4000")      # mapped (key events reach only a mapped window), off screen
seen = {}

def act(key):
    def go():
        top = [w for w in root.winfo_children() if isinstance(w, tkinter.Toplevel)][0]
        # A key that never arrives must not hang the test: the dialog is closed and that shows.
        root.after(5000, lambda: top.winfo_exists() and (seen.setdefault("hung", key), top.destroy()))
        buttons = []
        def walk(w):
            for c in w.winfo_children():
                if c.winfo_class() == "TButton":
                    buttons.append(c)
                walk(c)
        walk(top)
        seen.setdefault("default", [b.cget("text") for b in buttons if str(b.cget("default")) == "active"])
        seen.setdefault("focus", str(top.focus_lastfor().cget("text")))
        if key == "Move":
            [b for b in buttons if b.cget("text") == "Move"][0].invoke()
        else:
            top.update()
            top.focus_force()
            top.event_generate("<" + key + ">", when="tail")
    return go

out = []
for key in ("Return", "Escape", "Move"):
    root.after(300, act(key))
    out.append(gui.App._move_to_save_folders_dialog(None, root, "Save 1:\n  a -> b"))
print(seen["default"], seen["focus"], out, seen.get("hung"))
root.destroy()
"""


class ConfirmationDialogTest(unittest.TestCase):
    def test_cancel_is_the_default_and_return_and_escape_cancel(self) -> None:
        done = subprocess.run([sys.executable, "-c", DIALOG_CHILD, str(ROOT / "src")],
                              capture_output=True, text=True, timeout=90)
        if done.returncode == 3:
            self.skipTest("no Tk display: " + done.stderr.strip())
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(done.stdout.strip().splitlines()[-1], "['Cancel'] Cancel [False, False, True] None")

    def test_the_button_is_wired_next_to_move_old_files(self) -> None:
        source = (ROOT / "src" / "vv_fun_patcher_gui.py").read_text(encoding="utf-8")
        old = source.index('text="Move Old Files to New Names..."')
        new = source.index('text="Move Files to Save Folders..."')
        self.assertLess(old, new)
        self.assertLess(new - old, 1200)
        self.assertIn("vv_move_to_save_folders.move_to_save_folders(folder, game_folders, confirmed=work)", source)


if __name__ == "__main__":
    unittest.main()
