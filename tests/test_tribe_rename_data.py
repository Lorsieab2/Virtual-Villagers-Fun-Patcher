"""Rename Tribe keeps the patcher's own data with the village (all five games).

Two things a rename used to break, found by test (v1.35.80):

  * Answered questions (and every other decision in the slot's Log Decisions file) are kept under
    "Village: <name> (Save <n>)".  The rename appends a "Tribe renamed from" note to the village's
    logs, and the readers follow those notes -- but a slot with no log under the old header got no
    note, so after the rename none of its answers matched and every question was asked again.  The
    rename now moves those decisions to the new header itself.
  * The Lost Children's ElderTotems.dat keeps the village's name and, with an empty roster (only
    statues left), binds by it: the companion would set the file aside as another village's.  Its
    name is now changed with the save's.

Everything runs on fixture saves copied into a throwaway folder; no game is started (fake process
list), and nothing outside the temporary folder is read or written.
"""
from __future__ import annotations

import json
import sys
import unittest
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import vv_answered_questions as aq  # noqa: E402
import vv_log_additions as additions  # noqa: E402
import vv_log_decisions as decisions  # noqa: E402
import vv_tribe_rename as rename  # noqa: E402
import vv_vv2_totem_store as store  # noqa: E402
from test_tribe_rename import FakeProcesses, SaveFolderTest  # noqa: E402

NOW = datetime(2026, 10, 21, 12, 0, 0)
NEW = "Renamed Tribe"


def question(fact: str = "born:Abc", who=(("Abc", 3, 4),)):
    return SimpleNamespace(fact=fact, who=who, options=["Yes", "No"], text="Was Abc born here?", key="q1")


def kind(q):
    return SimpleNamespace(id="born", label="Births", questions={"q1": q})


class DataFollowsTheRenameTests(SaveFolderTest):
    def setup_village(self, number: int, with_log: bool):
        game, folder = self.make_folder("huttest", number, "Modded")
        old = rename.save_name(game, game.save_path(folder, 1).read_bytes())
        if with_log:
            log = (folder / "Virtual Villagers Fun Patcher" / "Save 1" / "Logs" / "Deaths and Disappearances"
                   / f"Virtual Villagers {number} Deaths Log 1.txt")
            log.parent.mkdir(parents=True)
            log.write_text(f"{rename.village_header(old, 1)}\r\n\r\nDeath 1\r\nName: Abc\r\n\r\n")
        # The player answered a question while the tribe had its old name.
        k = kind(question())
        aq.record(folder, number, 1, [k], {"born"}, {"q1": "No"}, now=datetime(2026, 10, 1))
        return game, folder, old

    def asked(self, folder: Path, number: int) -> int:
        k = kind(question())
        aq.hold_back(folder, number, 1, [k])
        return len(k.questions)

    def test_no_answered_question_is_asked_again_after_a_rename(self) -> None:
        for number in range(1, 6):
            for with_log in (False, True):
                with self.subTest(game=number, with_log=with_log):
                    self.tearDown()
                    self.setUp()
                    game, folder, old = self.setup_village(number, with_log)
                    self.assertEqual(self.asked(folder, number), 0)     # held back before the rename
                    result = rename.rename_tribe(game, folder, 1, NEW, processes=FakeProcesses(), now=NOW)
                    self.assertEqual(self.asked(folder, number), 0, "an answered question was asked again")
                    self.assertIn(decisions.path(folder, number, 1), result.data)
                    villages = additions.current_villages(folder, number, 1)
                    self.assertIn(rename.village_header(NEW, 1), villages)
                    kept = [d for d in decisions.load(folder, number, 1) if d.get("kind") == aq.KIND]
                    self.assertEqual([d["village"] for d in kept], [rename.village_header(NEW, 1)])
                    # Every other field of the answer is as the player left it.
                    self.assertEqual(kept[0]["verdict"], "No")
                    self.assertEqual(kept[0]["date"], "2026-10-01 00:00:00")

    def test_the_backup_holds_the_decisions_as_they_were(self) -> None:
        game, folder, old = self.setup_village(3, with_log=False)
        before = decisions.path(folder, 3, 1).read_bytes()
        result = rename.rename_tribe(game, folder, 1, NEW, processes=FakeProcesses(), now=NOW)
        copy = Path(result.backup.backup_folder) / decisions.path(folder, 3, 1).relative_to(folder)
        self.assertEqual(copy.read_bytes(), before)

    def test_refused_while_the_game_runs_changes_nothing(self) -> None:
        game, folder, old = self.setup_village(5, with_log=False)
        before = self.snapshot(folder)
        with self.assertRaises(rename.GameRunning):
            rename.rename_tribe(game, folder, 1, NEW, processes=FakeProcesses(pids=[7]), now=NOW)
        self.assertEqual(self.snapshot(folder), before)
        self.assertFalse((folder / "Backups").exists())

    def test_a_failed_write_puts_the_decisions_back(self) -> None:
        game, folder, old = self.setup_village(4, with_log=True)
        before = self.snapshot(folder)
        real = rename._write_atomically
        target = decisions.path(folder, 4, 1)

        def failing(path, data):
            if path == target:
                raise OSError("disk full")
            return real(path, data)

        with mock.patch.object(rename, "_write_atomically", failing):
            with self.assertRaises(rename.RenameError):
                rename.rename_tribe(game, folder, 1, NEW, processes=FakeProcesses(), now=NOW)
        self.assertEqual(self.snapshot(folder), before)

    def test_another_villages_decisions_are_left_alone(self) -> None:
        game, folder, old = self.setup_village(1, with_log=False)
        decisions.record(folder, 1, 1, [{"kind": aq.KIND, "village": "Village: Someone Else (Save 1)",
                                         "field": "other", "verdict": "Yes"}], now=datetime(2026, 9, 1))
        rename.rename_tribe(game, folder, 1, NEW, processes=FakeProcesses(), now=NOW)
        villages = {d["field"]: d["village"] for d in decisions.load(folder, 1, 1)}
        self.assertEqual(villages["other"], "Village: Someone Else (Save 1)")

    def test_renamed_back_keeps_one_answer_per_question(self) -> None:
        game, folder, old = self.setup_village(2, with_log=False)
        rename.rename_tribe(game, folder, 1, NEW, processes=FakeProcesses(), now=NOW)
        # Answered again under the new name, then the tribe gets its old name back.
        aq.record(folder, 2, 1, [kind(question())], {"born"}, {"q1": "Yes"}, now=datetime(2026, 10, 22))
        rename.rename_tribe(game, folder, 1, old, processes=FakeProcesses(), now=NOW)
        kept = [d for d in decisions.load(folder, 2, 1) if d.get("kind") == aq.KIND]
        self.assertEqual(len(kept), 1)
        self.assertEqual((kept[0]["village"], kept[0]["verdict"]), (rename.village_header(old, 1), "Yes"))
        self.assertEqual(self.asked(folder, 2), 0)

    def test_an_unreadable_decisions_file_is_never_rewritten(self) -> None:
        game, folder, old = self.setup_village(3, with_log=False)
        path = decisions.path(folder, 3, 1)
        path.write_bytes(b"{not json")
        result = rename.rename_tribe(game, folder, 1, NEW, processes=FakeProcesses(), now=NOW)
        self.assertEqual(path.read_bytes(), b"{not json")
        self.assertEqual(result.data, [])


class SavedFamilyTreesFollowTheRenameTests(SaveFolderTest):
    def test_a_saved_tree_of_the_village_gets_the_new_name(self) -> None:
        import vv_family_tree as ft
        import vv_last_names as ln
        for number in range(1, 6):
            with self.subTest(game=number):
                self.tearDown()
                self.setUp()
                game, folder = self.make_folder("huttest", number, "Modded")
                old = rename.save_name(game, game.save_path(folder, 1).read_bytes())
                trees = folder / ft.TREES
                trees.mkdir()
                mine = trees / f"{old} (Save 1) Family Tree{ft.TREE_SUFFIX}"
                mine.write_text(json.dumps({"format": 1, "game": number, "slot": 1, "tribe": old,
                                            "edits": {"marks": {"Abc": 1}}}, indent=1), encoding="utf-8")
                other = trees / f"Other (Save 2) Family Tree{ft.TREE_SUFFIX}"
                other.write_text(json.dumps({"format": 1, "game": number, "slot": 2, "tribe": old}),
                                 encoding="utf-8")
                other_bytes = other.read_bytes()
                result = rename.rename_tribe(game, folder, 1, NEW, processes=FakeProcesses(), now=NOW)
                data = json.loads(mine.read_text(encoding="utf-8"))
                self.assertEqual(data["tribe"], NEW)
                self.assertEqual(data["edits"], {"marks": {"Abc": 1}})
                self.assertEqual(other.read_bytes(), other_bytes)       # another slot's tree
                self.assertIn(mine, result.data)
                # Last Names still finds it as this save's tree, so it keeps following renamed villagers.
                plan = SimpleNamespace(changes=[])
                with mock.patch.object(ft, "renamed_keys", lambda text, renames: text + " "):
                    ln._plan_family_trees(plan, folder, number, 1, {})
                self.assertIn(mine, [c.path for c in plan.changes])


def totem_entry(name: str) -> bytes:
    entry = bytearray(store.ENTRY)
    raw = name.encode("ascii")
    entry[store.E_NAME:store.E_NAME + len(raw)] = raw
    entry[store.E_IS_TOTEM] = 1
    return bytes(entry)


class ElderTotemsFollowTheRenameTests(SaveFolderTest):
    def write_store(self, folder: Path, village: str, roster=()) -> Path:
        path = store.store_path(folder, 1)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(store.serialize(store.Store(1, list(roster), [store.Totem(totem_entry("Elder"))], village)))
        return path

    def test_a_statues_only_store_stays_bound_after_a_rename(self) -> None:
        game, folder = self.make_folder("huttest", 2, "Modded")
        old = rename.save_name(game, game.save_path(folder, 1).read_bytes())
        path = self.write_store(folder, old)
        result = rename.rename_tribe(game, folder, 1, NEW, processes=FakeProcesses(), now=NOW)
        self.assertIn(path, result.data)
        kept = store.read(folder, 1)
        save = game.save_path(folder, 1).read_bytes()
        # The companion's name check (vvfp_vv2_totems.c bound_to) compares the file's name with the
        # game's: they are the same again, so nothing is set aside as another village's.
        self.assertEqual(kept.village, store.village_of(save))
        self.assertEqual(kept.village, NEW)
        self.assertEqual([t.entry for t in kept.totems], [totem_entry("Elder")])
        self.assertEqual(list(path.parent.glob("*another-village*")), [])

    def test_a_store_bound_by_its_roster_stays_bound(self) -> None:
        game, folder = self.make_folder("huttest", 2, "Modded")
        save = game.save_path(folder, 1).read_bytes()
        old = rename.save_name(game, save)
        roster = store.roster_of(save, store._offsets(save))
        self.write_store(folder, old, roster)
        rename.rename_tribe(game, folder, 1, NEW, processes=FakeProcesses(), now=NOW)
        kept = store.read(folder, 1)
        self.assertTrue(store.bound(kept, game.save_path(folder, 1).read_bytes()))
        self.assertEqual((kept.roster, kept.village), (roster, NEW))

    def test_another_villages_store_is_left_alone(self) -> None:
        game, folder = self.make_folder("huttest", 2, "Modded")
        path = self.write_store(folder, "Someone Else")
        before = path.read_bytes()
        result = rename.rename_tribe(game, folder, 1, NEW, processes=FakeProcesses(), now=NOW)
        self.assertEqual(path.read_bytes(), before)
        self.assertNotIn(path, result.data)

    def test_other_games_have_no_totem_store_to_change(self) -> None:
        for number in (1, 3, 4, 5):
            with self.subTest(game=number):
                self.tearDown()
                self.setUp()
                game, folder = self.make_folder("huttest", number, "Modded")
                result = rename.rename_tribe(game, folder, 1, NEW, processes=FakeProcesses(), now=NOW)
                self.assertEqual(result.data, [])


if __name__ == "__main__":
    unittest.main()
