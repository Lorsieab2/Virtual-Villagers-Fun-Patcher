"""The Repair Saves & Logs audit's fixes (2026-10-20; the owner: "Fix all").

  * A Repair that changes nothing keeps no backup -- the backup is still made before anything could be
    written, and taken away only when not one file was written after it.
  * Check Saves & Logs only reads: no reconciliation report, no PendingElderTotems.dat.  Repair writes
    them once Repair is pressed; Cancel leaves nothing written.
  * The arrivals' automatic last names, done before the checklist opens, are said so.
  * The summary names where the copies go ("Copies Made Before Repairs").
  * The default numbering order says what it is: "Oldest first (order of appearance)", in the window
    and the How to Use guide alike.
  * A second "Give villagers last names" with nothing to do is information, not an error.
(The grave and parents fixes are tested in tests/test_fix_graves.py and tests/test_vv1_parents_restore.py.)
"""
from __future__ import annotations

import json
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import vv_genealogy  # noqa: E402
import vv_last_names  # noqa: E402
import vv_log_tools as tools  # noqa: E402
import vv_reconcile_view  # noqa: E402
import vv_save_backup as backup  # noqa: E402
from test_log_tools import CASES, NOW, FakeProcesses, FolderTest  # noqa: E402

GUI = (ROOT / "src" / "vv_fun_patcher_gui.py").read_text(encoding="utf-8")


def section(start: str, end: str) -> str:
    return GUI[GUI.index(start):GUI.index(end)]


class NoBackupWhenNothingChanges(FolderTest):
    def test_a_second_repair_keeps_no_backup_in_every_game(self) -> None:
        for tag, number, suffix in CASES:
            with self.subTest(game=number, variant=suffix):
                folder = self.make_folder(tag, number, suffix)
                first = tools.approve_repair(folder, number, 1, FakeProcesses(), NOW)
                self.assertIsNotNone(first.backup, "the first Repair clears markers: backed up first")
                self.assertTrue(first.backup.backup_folder.is_dir())
                listed = [b.path for b in backup.list_backups(folder)]
                second = tools.approve_repair(folder, number, 1, FakeProcesses(), NOW)
                self.assertIsNone(second.backup, "nothing to change: no backup kept")
                self.assertEqual([b.path for b in backup.list_backups(folder)], listed)
                self.assertTrue(first.backup.backup_folder.is_dir(), "an earlier backup is never touched")

    def test_the_backup_is_still_made_before_any_write(self) -> None:
        folder = self.make_folder("huttest", 2, "Modded")
        made = []
        real = backup.copy_save_folder

        def spy(*args, **kwargs):
            made.append(set(backup.files_to_back_up(folder)))
            return real(*args, **kwargs)

        with mock.patch.object(backup, "copy_save_folder", spy):
            result = tools.approve_repair(folder, 2, 1, FakeProcesses(), NOW)
        self.assertEqual(len(made), 1, "the backup is made every time, before anything is written")
        self.assertIsNotNone(result.backup)
        for cleared in result.cleared:
            self.assertIn(cleared.relative_to(folder), made[0], "each cleared marker is in the backup")

    def test_unchanged_since_sees_any_write(self) -> None:
        folder = self.make_folder("huttest", 3, "Modded")
        made = backup.copy_save_folder(folder, NOW, suffix="(test)")
        self.assertTrue(backup.unchanged_since(made))
        some = next(p for p in (folder / rel for rel in backup.files_to_back_up(folder)) if p.suffix == ".ldw")
        time.sleep(0.01)
        some.write_bytes(some.read_bytes())                 # the same bytes, written again
        self.assertFalse(backup.unchanged_since(made))
        made = backup.copy_save_folder(folder, NOW, suffix="(test 2)")
        (folder / "new file.txt").write_text("x")
        self.assertFalse(backup.unchanged_since(made))

    def test_the_summary_says_when_no_backup_was_made(self) -> None:
        repair = section("    def _repair_logs(", "    def _repair_checklist(")
        self.assertIn('[f"Backup: {result.backup.backup_folder}"] if result.backup is not None else []', repair)
        self.assertIn("no backup was made", repair)


class CheckOnlyReads(unittest.TestCase):
    def test_check_writes_neither_the_report_nor_the_pending_totems(self) -> None:
        check = section("    def _check_logs(", "    @staticmethod\n    def _numbering_report(")
        self.assertNotIn("write_pending", check)
        self.assertNotIn("vv_reconcile.export", check)
        picker = section("    def _log_tool(", "    def _game_folders_for(")
        self.assertIn("chosen().slot, export=False)", picker, "the picker only reads, for Check and Repair alike")

    def test_repair_writes_them_only_once_repair_is_pressed(self) -> None:
        repair = section("    def _repair_logs(", "    def _repair_checklist(")
        survey = repair[repair.index("        def survey():"):repair.index("        try:\n            (checked,")]
        self.assertNotIn("write_pending(", survey, "nothing is written before the checklist")
        after = repair.index("picked = self._repair_checklist(")
        cancelled = repair.index("if picked is None:", after)
        self.assertLess(cancelled, repair.index("vv_vv2_totem_store.write_pending(folder, info.slot)"))
        self.assertLess(cancelled, repair.index("vv_reconcile.export(checked.reconciliation)"))

    def test_watch_without_export_writes_no_report(self) -> None:
        class Widget:
            def after(self, _ms, _fn):
                pass

        class Var:
            def set(self, _text):
                pass

        exported = []
        done = threading.Event()

        def reconcile(*_args):
            done.set()
            return object()

        with mock.patch.object(vv_reconcile_view.vv_reconcile, "reconcile", reconcile), \
                mock.patch.object(vv_reconcile_view.vv_reconcile, "export", lambda rec: exported.append(rec)):
            vv_reconcile_view.watch(Widget(), Var(), Path("F"), 2, 1, export=False)
            self.assertTrue(done.wait(5))
            for t in [t for t in threading.enumerate() if t.name == "vvfp-reconcile"]:
                t.join(5)
            self.assertEqual(exported, [])
            done.clear()
            vv_reconcile_view.watch(Widget(), Var(), Path("G"), 2, 1)
            self.assertTrue(done.wait(5))
            for t in [t for t in threading.enumerate() if t.name == "vvfp-reconcile"]:
                t.join(5)
            self.assertEqual(len(exported), 1, "the other village windows still write it")


class WhatRepairSays(unittest.TestCase):
    def test_the_copies_place_is_named(self) -> None:
        repair = section("    def _repair_logs(", "    def _repair_checklist(")
        self.assertNotIn("backed up beside itself", repair)
        self.assertIn("in Copies Made Before Repairs", repair)

    def test_the_arrivals_last_names_before_the_checklist_are_said(self) -> None:
        picker = section("    def _log_tool(", "    def _game_folders_for(")
        self.assertIn("stays done if you", picker)
        self.assertIn("then cancel", picker)
        repair = section("    def _repair_logs(", "    def _repair_checklist(")
        self.assertIn("Already done, before this checklist (Cancel does not undo it)", repair)
        self.assertLess(repair.index("named_lines = self._missing_last_names_at_repair("),
                        repair.index("picked = self._repair_checklist("))

    def test_one_wording_for_the_default_numbering_order(self) -> None:
        wording = "Oldest first (order of appearance)"
        self.assertEqual(vv_genealogy.NUMBER_ORDERS["appearance"], wording)
        self.assertEqual(len(set(vv_genealogy.NUMBER_ORDERS.values())), 3)
        guide = json.loads((ROOT / "data" / "how_to_use.json").read_text(encoding="utf-8"))
        text = " ".join(guide["controls"]["repair_logs"]["guide"])
        self.assertIn(wording.lower(), text.lower())
        checklist = section("    def _repair_checklist(", "    def _repair_questions(")
        self.assertIn('vv_genealogy.NUMBER_ORDERS["appearance"]', checklist, "still the default")


class NothingToDoIsInformation(unittest.TestCase):
    def test_nothing_to_do_is_its_own_kind(self) -> None:
        self.assertTrue(issubclass(vv_last_names.NothingToDo, vv_last_names.LastNamesError))
        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.object(vv_last_names, "plan", lambda *a, **k: mock.Mock(renames={})):
            with self.assertRaises(vv_last_names.NothingToDo) as raised:
                vv_last_names.give_last_names(Path(tmp), 4, 1, {("Bora", 1, 2): "Chinaka"},
                                              processes=FakeProcesses())
        self.assertIn("Nothing to do", str(raised.exception))

    def test_the_windows_say_it_as_information(self) -> None:
        repair = section("    def _repair_logs(", "    def _repair_checklist(")
        self.assertIn("except vv_last_names.NothingToDo as exc:", repair)
        apply_ = section("    def _apply_last_names(", "    def _repair_checklist(")
        self.assertLess(apply_.index("except vv_last_names.NothingToDo as exc:"),
                        apply_.rindex("except (vv_last_names.LastNamesError"), "before the give's own errors")


if __name__ == "__main__":
    unittest.main()
