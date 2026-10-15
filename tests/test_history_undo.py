"""Repair Saves & Logs: Undelete villagers (src/vv_history_revision.py undo), all five games.

The owner (v1.35.73): "add an option to undelete villagers" -- every line the latest history revision took
out of the logs is put back from the copies it made first; anything written since is kept.
"""
from __future__ import annotations

import hashlib
import re
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import vv_history_revision as hr  # noqa: E402
import vv_log_tools as tools  # noqa: E402
from test_history_revision import GAMES, Scene  # noqa: E402
from test_reconcile import FakeProcesses  # noqa: E402

LATER = datetime(2026, 10, 14, 13, 0, 0)


def logs(s: Scene) -> dict[Path, bytes]:
    """Every log of the village (not the patcher's copies, not the Repairs log)."""
    return {p: p.read_bytes() for p in s.v.folder.rglob("*.txt")
            if "Copies Made Before Repairs" not in str(p) and "Repairs Made" not in str(p)}


def everything(s: Scene) -> dict[Path, str]:
    return {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in s.v.folder.rglob("*") if p.is_file()}


class Running(FakeProcesses):
    def find(self, exe_name):
        return [1234]


class Base(unittest.TestCase):
    def scene(self, game: int) -> Scene:
        root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        return Scene(root, game)

    def undo(self, s: Scene, processes=None, confirm=True):
        return hr.undo(s.v.folder, s.game, 1, processes or FakeProcesses(), LATER, confirm=confirm)


class Undelete(Base):
    def test_undo_puts_every_changed_log_back_byte_for_byte_in_every_game(self):
        for game in GAMES:
            with self.subTest(game=game):
                s = self.scene(game)
                self.assertIsNone(hr.undo_plan(s.v.folder, game, 1))        # nothing revised yet
                before = logs(s)
                result = s.revise()
                self.assertTrue(result.files)
                revised = logs(s)
                changed = [p for p in before if before[p] != revised[p]]
                self.assertGreaterEqual(len(changed), 3)
                plan = hr.undo_plan(s.v.folder, game, 1)
                self.assertEqual(sorted(f.log for f in plan.files), sorted(changed))
                self.assertIn("Gonea Testa", plan.describe())
                self.undo(s)
                after = logs(s)
                for p in before:
                    self.assertEqual(after[p], before[p], p.name)
                # Done: nothing left to put back.
                self.assertIsNone(hr.undo_plan(s.v.folder, game, 1))
                # The Repairs log says who came back and from which copies.
                repairs = [p for p in s.v.folder.rglob(f"Virtual Villagers {game} Repairs Log *.txt")]
                text = "".join(p.read_bytes().decode("latin-1") for p in repairs)
                self.assertIn("  Restored: Gonea Testa (Female, head 99, body 98)\r\n", text)
                self.assertIn("Village History 1.txt from Village History 1.txt" + hr.BACKUP_SUFFIX, text)
                self.assertEqual(len(re.findall(r"^  Backup: .*" + re.escape(hr.UNDO_SUFFIX), text, re.M)), 1)
                # Each log was copied before the undo, as it was after the revision.
                copies = list(s.v.folder.rglob("*" + hr.UNDO_SUFFIX))
                for p in changed:
                    self.assertTrue(any(c.name.startswith(p.name) and c.read_bytes() == revised[p] for c in copies))

    def test_lines_written_since_the_revision_are_kept(self):
        for game in GAMES:
            with self.subTest(game=game):
                s = self.scene(game)
                before = s.deaths.read_bytes()
                s.revise()
                later = b"Death 3\r\n  Name: Written Later\r\n  Age at death: 50\r\n  Sex: Male\r\n\r\n"
                with open(s.deaths, "ab") as f:
                    f.write(later)
                self.undo(s)
                self.assertEqual(s.deaths.read_bytes(), before + later)

    def test_it_needs_the_confirmation_and_changes_nothing_without_it(self):
        self.assertFalse(hr.UNDO_DEFAULT_TICKED)
        for game in GAMES:
            with self.subTest(game=game):
                s = self.scene(game)
                s.revise()
                state = everything(s)
                with self.assertRaises(hr.HistoryRevisionError):
                    self.undo(s, confirm=False)
                with self.assertRaises(hr.HistoryRevisionError):
                    hr.undo(s.v.folder, game, 1, FakeProcesses())
                self.assertEqual(everything(s), state)
        gui = (ROOT / "src" / "vv_fun_patcher_gui.py").read_text(encoding="utf-8")
        self.assertTrue("undo_var = tk.BooleanVar(value=vv_history_revision.UNDO_DEFAULT_TICKED)" in gui)
        self.assertTrue("self._undo_history_dialog(window, undo_plan)" in gui)

    def test_the_game_running_refuses(self):
        for game in GAMES:
            with self.subTest(game=game):
                s = self.scene(game)
                s.revise()
                state = everything(s)
                with self.assertRaises(tools.GameRunning):
                    self.undo(s, Running())
                self.assertEqual(everything(s), state)

    def test_a_failed_write_puts_back_every_log_already_changed(self):
        for game in GAMES:
            for replaced in (False, True):
                with self.subTest(game=game, replaced=replaced):
                    s = self.scene(game)
                    s.revise()
                    revised = logs(s)
                    real = hr._write
                    calls = []

                    def failing(path, data):
                        calls.append(path)
                        if replaced:
                            real(path, data)
                        if len(calls) == 2:
                            raise OSError("disk full (test)")
                        if not replaced:
                            real(path, data)
                    hr._write = failing
                    try:
                        with self.assertRaises(hr.HistoryRevisionError):
                            self.undo(s)
                    finally:
                        hr._write = real
                    self.assertGreaterEqual(len(calls), 2)
                    self.assertEqual(logs(s), revised)
                    # ...and it can still be done afterwards.
                    self.assertIsNotNone(hr.undo_plan(s.v.folder, game, 1))

    def test_a_log_changed_in_place_since_is_refused(self):
        s = self.scene(3)
        s.revise()
        text = s.history.read_bytes()
        s.history.write_bytes(text.replace(b"Name: Kept Ancestor", b"Name: Kept Ancestress", 1))
        plan = hr.undo_plan(s.v.folder, 3, 1)
        self.assertTrue(plan.refused)
        state = everything(s)
        with self.assertRaises(hr.HistoryRevisionError):
            self.undo(s)
        self.assertEqual(everything(s), state)

    def test_only_the_latest_revision_is_put_back(self):
        s = self.scene(2)
        key = (s.other.name, 97, 96)
        first = logs(s)
        s.revise()
        middle = logs(s)
        hr.revise(s.v.folder, 2, 1, hr.plan(s.v.folder, 2, 1, also_remove=frozenset({key})), FakeProcesses(),
                  datetime(2026, 10, 14, 12, 30, 0), confirm=True)
        self.assertNotEqual(logs(s), middle)
        self.undo(s)
        self.assertEqual(logs(s), middle)
        self.assertNotEqual(logs(s), first)


if __name__ == "__main__":
    unittest.main()
