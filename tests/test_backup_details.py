"""Backups... (the owner, 2026-11-09: "ALSO SHOW VITAL STATISTICS FOR EACH BACKUP IN A WINDOW!!!"): every backup's
vital statistics, all five games, read-only (src/vv_backup_details.py, src/vv_backup_details_window.py).

The saves are the committed test saves (tests/fixtures/rename_tribe), copied into a temporary Documents\\LDW folder's
Backups; no real save is read or committed.
"""
from __future__ import annotations

import gzip
import shutil
import struct
import sys
import tempfile
import time
import unittest
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import vv_backup_details as bd  # noqa: E402
import vv_game_mechanics as gm  # noqa: E402
import vv_game_mechanics_life as life  # noqa: E402
import vv_last_names as ln  # noqa: E402
import vv_save_backup  # noqa: E402
import vv_tribe_rename  # noqa: E402

FIXTURES = ROOT / "tests" / "fixtures" / "rename_tribe"
SAVES = {1: "vv1-huttest-1", 2: "vv2-huttest-1", 3: "vv3-huttest-1", 4: "vv4-huttest-1", 5: "vv5-256-1"}
GUI = ROOT / "src" / "vv_fun_patcher_gui.py"


def fixture(game: int) -> bytearray:
    return bytearray(gzip.decompress((FIXTURES / f"{SAVES[game]}.ldw.gz").read_bytes()))


def base(game: int) -> str:
    return vv_tribe_rename.GAMES[game - 1].base


def title(game: int) -> str:
    return vv_tribe_rename.GAMES[game - 1].title


def snapshot(folder: Path) -> dict[str, tuple[bytes, int]]:
    return {str(p.relative_to(folder)): (p.read_bytes() if p.is_file() else b"", p.stat().st_mtime_ns)
            for p in sorted(folder.rglob("*"))}


class Case(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp(prefix="vbd"))
        self.addCleanup(shutil.rmtree, self.root, True)

    def save_folder(self, game: int) -> Path:
        folder = self.root / "LDW" / f"{title(game)} - Modded"
        folder.mkdir(parents=True, exist_ok=True)
        return folder

    def backup(self, game: int, stamp: str, slots: dict[int, bytes], label: str = "") -> Path:
        folder = self.save_folder(game) / "Backups" / (f"Backup {stamp}" + (f" {label}" if label else ""))
        folder.mkdir(parents=True)
        for slot, data in slots.items():
            (folder / f"{base(game)}{slot}.ldw").write_bytes(bytes(data))
        return folder


class ReaderTests(Case):
    def test_each_game_reads_what_the_game_mechanics_page_reads(self) -> None:
        for game in SAVES:
            with self.subTest(game=game):
                data = fixture(game)
                folder = self.backup(game, "2026-11-01 10-00-00", {2: data})
                got = bd.read_slot(game, folder, 2)
                path = folder / f"{base(game)}2.ldw"
                village = gm.Village(folder, game, 2, path, bytes(data), None, time.time())
                ctx = life.save_context(village)
                members = life.tribe(life.people(village))
                self.assertIsNotNone(ctx)
                self.assertEqual(got.tribe, vv_save_backup.read_village_name(game, path))
                self.assertTrue(got.tribe)
                self.assertEqual(got.food, ctx.food)
                self.assertEqual(got.tech_points, ctx.tech)
                self.assertEqual(got.last_tick, float(ctx.last))
                self.assertEqual(got.villagers, len(members))
                self.assertEqual(got.speed, vv_save_backup.speed_words(vv_save_backup.save_speed(game, bytes(data))[1]))
                self.assertIn(got.difficulty, ("Easy", "Medium", "Hard"))
                self.assertTrue(got.techs)
                self.assertAlmostEqual(got.saved, path.stat().st_mtime)
                self.assertEqual(got.heathens is not None, game == 5)
                text = "\n".join(bd.slot_lines(got))
                self.assertIn(f"Food in storage: {ctx.food:,}", text)
                self.assertIn(f"Last played: {gm.when(ctx.last)} (the save's own last-tick time", text)
                self.assertIn("(the save file's own time)", text)

    def test_the_context_catch_leaves_the_page_as_it_was(self) -> None:
        data = fixture(4)
        folder = self.backup(4, "2026-11-01 10-00-00", {1: data})
        life.save_context(gm.Village(folder, 4, 1, folder / f"{base(4)}1.ldw", bytes(data), None, time.time()))
        facts = gm.read(folder, 4, 1, [])
        self.assertTrue(any(f.text.startswith("Food in storage:") for f in facts))

    def test_babies_on_the_way_count_and_heathens_never_do(self) -> None:
        data = fixture(5)
        lay = life.LAYOUTS[5]
        entries = ln._entries(5, bytes(data))
        for at in entries:
            struct.pack_into("<i", data, at + lay.conceived, 0)
        struct.pack_into("<i", data, entries[0] + lay.conceived, 5)
        struct.pack_into("<i", data, entries[0] + lay.babies, 2)
        data[entries[1] + life.VV5_FACTION] = 1                    # a Heathen outside the tribe
        folder = self.backup(5, "2026-11-01 10-00-00", {1: data})
        got = bd.read_slot(5, folder, 1)
        self.assertEqual(got.heathens, 1)
        self.assertEqual(got.villagers, len(entries) - 1)
        self.assertEqual(got.babies, 2)
        self.assertEqual(got.population, len(entries) + 1)
        self.assertIn("and 2 babies on the way", bd.population_words(got))
        self.assertIn("Heathens outside the tribe: 1 (never counted)", bd.population_words(got))

    def test_an_unreadable_save_shows_unknown(self) -> None:
        for game in SAVES:
            with self.subTest(game=game):
                folder = self.backup(game, "2026-11-01 10-00-00", {3: b"ldwg" + b"\0" * 64})
                got = bd.read_slot(game, folder, 3)
                for value in (got.tribe, got.food, got.tech_points, got.villagers, got.last_tick, got.speed):
                    self.assertIsNone(value)
                text = "\n".join(bd.slot_lines(got))
                self.assertIn("Save 3: unknown", text)
                self.assertIn("Population: unknown", text)
                self.assertIn("Food in storage: unknown", text)
                self.assertIn("Tech points: unknown", text)
                self.assertIn("Last played: unknown", text)
                self.assertNotIn("None", text)

    def test_an_impossible_last_tick_is_unknown(self) -> None:
        self.assertIsNone(bd._plausible(12, time.time()))
        self.assertIsNone(bd._plausible(time.time() + 20 * 365 * 86400, time.time()))

    def test_the_statistics_log_in_the_backup_gives_real_hours_played(self) -> None:
        folder = self.backup(1, "2026-11-01 10-00-00", {1: fixture(1)})
        logs = folder / "Virtual Villagers Fun Patcher" / "Save 1" / "Logs" / "Village Statistics"
        logs.mkdir(parents=True)
        (logs / "Village Statistics v2 - Save 1.txt").write_text("Real Hours Played: 321\nFood Gathered: 5\n",
                                                                 encoding="cp1252")
        self.assertEqual(bd.read_slot(1, folder, 1).hours_played, 321)
        self.assertIn("Real hours played: 321 (the Village Statistics log in this backup)",
                      "\n".join(bd.slot_lines(bd.read_slot(1, folder, 1))))

    def test_a_backup_lists_its_date_size_and_slots(self) -> None:
        self.backup(3, "2026-11-01 10-00-00", {1: fixture(3), 4: fixture(3)}, "(before restore)")
        info = vv_save_backup.list_backups(self.save_folder(3))[0]
        lines = bd.backup_lines(bd.read_backup(3, info))
        self.assertEqual(lines[0], "Backup: 1 November 2026, 10:00:00 AM (before restore)")
        self.assertIn(f"  Folder: {info.path}", lines)
        self.assertIn(f"  Size: {vv_save_backup.describe_size(info.size)} in 2 files", lines)
        self.assertIn("  Save slots held: 1, 4", lines)
        self.assertEqual(sum(line.startswith("Save ") for line in lines), 2)

    def test_reading_writes_nothing(self) -> None:
        for game in SAVES:
            self.backup(game, "2026-11-01 10-00-00", {1: fixture(game), 2: b"junk"})
        before = snapshot(self.root)
        for game in SAVES:
            for info in vv_save_backup.list_backups(self.save_folder(game)):
                bd.backup_lines(bd.read_backup(game, info))
        self.assertEqual(snapshot(self.root), before)


class WindowTests(Case):
    tk = None

    @classmethod
    def setUpClass(cls) -> None:
        import tkinter
        try:
            cls.tk = tkinter.Tk()                  # one Tk for the class: a second one in a process may fail
        except tkinter.TclError as exc:
            raise unittest.SkipTest(f"no display: {exc}")
        cls.tk.withdraw()

    @classmethod
    def tearDownClass(cls) -> None:
        if cls.tk is not None:
            cls.tk.destroy()

    def test_the_window_lists_every_backup_newest_first_and_shows_the_chosen_one(self) -> None:
        import vv_backup_details_window as w
        old = self.backup(4, "2026-10-01 09-00-00", {1: fixture(4)})
        middle = self.backup(4, "2026-10-15 09-00-00", {1: fixture(4), 2: b"ldwg"}, "(before repair re-arm)")
        self.backup(4, "2026-11-01 09-00-00", {3: fixture(4)})
        folder = self.save_folder(4)
        before = snapshot(self.root)
        window = w.show_backup_details(self.tk, 4, folder, middle, documents=self.root)
        self.addCleanup(lambda: window.winfo_exists() and window.destroy())
        window.update()
        listbox = window.backups_list
        self.assertEqual(listbox.size(), 3)
        whens = [info.when for info in window.backups_state["backups"]]
        self.assertEqual(whens, sorted(whens, reverse=True))
        self.assertEqual(listbox.curselection(), (1,))
        shown = window.backups_text.get("1.0", "end")
        self.assertIn("Backup: 15 October 2026, 9:00:00 AM (before repair re-arm)", shown)
        self.assertIn("Save slots held: 1, 2", shown)
        self.assertIn("Food in storage:", shown)
        self.assertIn("Save 2: unknown", shown)
        self.assertIn("Population: unknown", shown)
        self.assertEqual(window.backups_game.get(), title(4))
        # Another backup, then Refresh: the choice is kept.
        listbox.selection_clear(0, "end")
        listbox.selection_set(2)
        window.backups_select()            # what <<ListboxSelect>> runs
        window.update()
        self.assertIn("Backup: 1 October 2026, 9:00:00 AM", window.backups_text.get("1.0", "end"))
        window.backups_refresh()
        window.update()
        self.assertEqual(listbox.curselection(), (2,))
        self.assertEqual(Path(window.backups_state["backups"][2].path), old)
        self.assertEqual(snapshot(self.root), before)

    def test_no_backups_says_so(self) -> None:
        import vv_backup_details_window as w
        folder = self.save_folder(2)
        window = w.show_backup_details(self.tk, 2, folder, documents=self.root)
        self.addCleanup(lambda: window.winfo_exists() and window.destroy())
        window.update()
        self.assertEqual(window.backups_list.size(), 0)
        self.assertIn("no backups yet", window.backups_text.get("1.0", "end"))


SMALLEST = r"""
import gzip, json, sys, tkinter, tkinter.ttk
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import vv_backup_details_window as w
try:
    root = tkinter.Tk()
except tkinter.TclError as exc:
    print(exc, file=sys.stderr)
    sys.exit(3)
root.tk.call("tk", "scaling", float(sys.argv[3]))       # large system fonts: every point is bigger
root.withdraw()
parent = tkinter.Toplevel(root)
parent.geometry("200x100+0+0")
parent.update()
window = w.show_backup_details(parent, 4, Path(sys.argv[2]), documents=Path(sys.argv[2]).parents[1])
low_w, low_h = window.minsize()
out = {"minsize": [low_w, low_h]}
bar = [c for c in window.backups_text.master.winfo_children() if isinstance(c, tkinter.ttk.Scrollbar)][0]
# The window's own smallest size, and the original smallest size with that minimum lifted (a screen too small for
# the larger minimum): the details keep their room either way.
for size, lifted in (((low_w, low_h), False), ((w.MIN_WIDTH, w.MIN_HEIGHT), True)):
    if lifted:
        window.minsize(1, 1)
    window.geometry(f"{size[0]}x{size[1]}+0+0")
    for _ in range(5):
        window.update()
    out[f"{size[0]}x{size[1]}"] = {
        "text": window.backups_text.winfo_height(), "bar": bar.winfo_height(),
        "bar_shown": bool(bar.winfo_ismapped()), "list": window.backups_list.winfo_height(),
        "line": window.backups_text.tk.call("font", "metrics", window.backups_text.cget("font"), "-linespace")}
window.destroy()
root.destroy()
print(json.dumps(out))
"""


class SmallestSizeTests(Case):
    def test_the_details_keep_their_room_at_the_smallest_size_with_large_fonts(self) -> None:
        import json
        import subprocess
        self.backup(4, "2026-10-01 09-00-00", {1: fixture(4)})
        self.backup(4, "2026-11-01 09-00-00", {1: fixture(4), 2: fixture(4)})
        for scaling in (1.33, 2.5):                     # 100% and about 190% Windows text size
            with self.subTest(scaling=scaling):
                done = subprocess.run([sys.executable, "-c", SMALLEST, str(ROOT / "src"), str(self.save_folder(4)),
                                       str(scaling)], capture_output=True, text=True, timeout=120)
                if done.returncode == 3:
                    self.skipTest(f"no display: {done.stderr.strip()}")
                self.assertEqual(done.returncode, 0, done.stderr)
                result = json.loads(done.stdout.strip().splitlines()[-1])
                for key, sizes in result.items():
                    if key == "minsize":
                        continue
                    with self.subTest(size=key):
                        self.assertGreaterEqual(sizes["text"], 3 * sizes["line"], sizes)
                        self.assertTrue(sizes["bar_shown"], sizes)
                        self.assertGreater(sizes["bar"], 0, sizes)
                        self.assertGreater(sizes["list"], sizes["line"], sizes)


class GuiWiringTests(unittest.TestCase):
    SOURCE = GUI.read_text(encoding="utf-8")

    def test_each_game_row_the_tools_button_restore_and_repair_open_it(self) -> None:
        body = self.SOURCE[self.SOURCE.index("    def _build_tools_tab("):]
        body = body[:body.index("\n    def ")]
        self.assertIn('"Backups...",\n                lambda game=build: vv_backup_details_window.show_backup_details(self, game)',
                      body)
        self.assertIn('text="Backups...",\n            command=lambda: vv_backup_details_window.show_backup_details(self, None)',
                      body)
        self.assertIn('self._help_button(save_tools, "backups")', body)
        restore = self.SOURCE[self.SOURCE.index("    def _show_restore_window("):self.SOURCE.index("    def _run_restore(")]
        self.assertIn("vv_backup_details_window.show_backup_details(dialog, build, item[0], item[1].path)", restore)
        self.assertIn('text="Details..."', restore)
        repair = self.SOURCE[self.SOURCE.index("    def _repair_checklist("):]
        self.assertIn("vv_backup_details_window.show_backup_details(window, number, folder)",
                      repair[:repair.index("\n    def ")])

    def test_the_window_holds_the_windows_way_and_never_writes(self) -> None:
        source = (ROOT / "src" / "vv_backup_details_window.py").read_text(encoding="utf-8")
        self.assertIn("window.grab_set()", source)
        reader = (ROOT / "src" / "vv_backup_details.py").read_text(encoding="utf-8")
        for call in ("write_bytes", "write_text", ".open(", "unlink", "rename(", "replace(", "mkdir", "shutil"):
            with self.subTest(call=call):
                self.assertNotIn(call, source)
                self.assertNotIn(call, reader)


if __name__ == "__main__":
    unittest.main()
