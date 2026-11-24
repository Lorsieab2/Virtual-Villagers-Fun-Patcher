"""Delete / Move Player Slot find a slot's files by their "Save <S>" FOLDER as well as by their name.

The live test of #847's Delete (2026-11-23, VV1): an older layout's "Virtual Villagers Fun Patcher Logs\\Save 2\\"
kept whole in "...Data\\Copies Made Before Repairs" inside an old backup held six logs named with no slot
("Virtual Villagers 1 Births and Conceptions Log 1.txt (before move to save folder)"); their siblings named
" - Save 2" went to the Recycle Bin, they stayed.  The owner: Delete sends EVERY file linked to the slot to the
Recycle Bin (not images).

A throwaway folder with "Save 2", "Save 12" and "Save 20" folders (and "Save 1"), by name and by folder, in the
save folder and in a backup, and pictures.  Delete slot 2 recycles exactly slot 2's files and nothing of the
others; the Recycle Bin is a fake (tests/test_delete_slot.py FakeBin), never the real one.  Move carries a file
that is the slot's only by its folder, and the folder becomes the target's.
"""
from __future__ import annotations

import shutil
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import test_copy_slot as tc  # noqa: E402
import test_delete_slot as td  # noqa: E402
import test_move_slot as tm  # noqa: E402
import vv_delete_slot as ds  # noqa: E402
import vv_move_slot as ms  # noqa: E402
import vv_tribe_rename as rename  # noqa: E402

NOW = tc.NOW
OWN, OLD_LOGS, OLD_DATA, TREES = tc.OWN, tc.OLD_LOGS, tc.OLD_DATA, tc.TREES
COPIES = f"{OLD_DATA}\\Copies Made Before Repairs"
BEFORE = " (before move to save folder)"
LOGS = (("Births and Conceptions", "Virtual Villagers 1 Births and Conceptions Log 1.txt"),
        ("Deaths and Disappearances", "Virtual Villagers 1 Deaths Log 1.txt"),
        ("Island Events", "Virtual Villagers 1 Island Events Log 1.txt"),
        ("Tribe History", "Village History 1.txt"),
        ("Tribe Population", "Village Population 1.txt"),
        ("Unaccounted Villagers", "Virtual Villagers 1 Unaccounted Villagers Log 1.txt"))


def slot_tree(slot_folder: str) -> list[str]:
    """The six logs of the live test, kept under ``slot_folder`` in the shared Copies Made Before Repairs."""
    return [f"{COPIES}\\{OLD_LOGS}\\{slot_folder}\\{kind}\\{name}{BEFORE}" for kind, name in LOGS]


# Slot 2's files: by their name, by the slot's own folders, and only by a "Save 2" folder.
SLOT2 = [
    f"{OLD_DATA}\\Graves\\Virtual Villagers 1 Graves - Save 2.dat",
    f"{OWN}\\Save 2\\Data\\Graves\\Virtual Villagers 1 Graves - Save 2.dat",
    f"{OLD_LOGS}\\Save 2\\Tribe History\\Village History 1.txt",
    f"{COPIES}\\{OLD_LOGS}\\Save 2\\Village Statistics\\Village Statistics v2 - Save 2.txt{BEFORE}",
    *slot_tree("Save 2"),
    f"{COPIES}\\{OLD_LOGS}\\Save 2\\Genealogy\\Virtual Villagers 1 Genealogy.txt",
    f"{TREES}\\Save 2\\Virtual Villagers 1 Village Matchmaker.txt",
    f"{COPIES}\\{OLD_LOGS}\\Save 2\\Deaths and Disappearances\\Virtual Villagers 1 Deaths Log 1.txt{BEFORE}-2",
    f"{COPIES}\\{OLD_LOGS}\\Save 2\\Deaths and Disappearances\\Virtual Villagers 1 Deaths Log 1.txt{BEFORE}-10",
]
# Pictures of slot 2: never recycled.
SLOT2_PICTURES = [
    f"{COPIES}\\{OLD_LOGS}\\Save 2\\Genealogy\\Virtual Villagers 1 Genealogy.png",
    f"{COPIES}\\{OLD_LOGS}\\Save 2\\Genealogy\\Virtual Villagers 1 Genealogy.png{BEFORE}",
    f"{COPIES}\\{OLD_LOGS}\\Save 2\\Genealogy\\Virtual Villagers 1 Genealogy.png{BEFORE}-2",
    f"{COPIES}\\{OLD_LOGS}\\Save 2\\Genealogy\\Virtual Villagers 1 Genealogy.png{BEFORE}-10",
    f"{TREES}\\Save 2\\Kalahuna family tree.png",
    f"{TREES}\\Kalahuna Tribe 1 (Save 2) family tree 2026-10-08 03-00-11.png",
]
# Everything else: other slots ("Save 1"), and folders that are NOT slot 2 ("Save 12", "Save 20"); a file named
# for slot 2 under slot 1's folder is slot 1's (the folder says whose it is).
OTHERS = [
    *slot_tree("Save 1"), *slot_tree("Save 12"), *slot_tree("Save 20"),
    f"{COPIES}\\{OLD_LOGS}\\Save 1\\Graves\\Virtual Villagers 1 Graves - Save 2.dat{BEFORE}",
    f"{COPIES}\\{OLD_LOGS}\\Save 12\\Village Statistics\\Village Statistics v2 - Save 12.txt",
    f"{COPIES}\\{OLD_LOGS}\\Save 20\\Repairs Made\\Virtual Villagers 1 Repairs Log 1.txt",
    f"{OLD_DATA}\\Graves\\Virtual Villagers 1 Graves - Save 1.dat",
    f"{OLD_DATA}\\Save 12\\Virtual Villagers 1 Graves.dat",
    f"{OLD_DATA}\\Save 20\\Virtual Villagers 1 Graves.dat",
    f"{OLD_LOGS}\\Save 12\\Tribe History\\Village History 1.txt",
    f"{OLD_LOGS}\\Save 20\\Tribe History\\Village History 1.txt",
    f"{OWN}\\Save 12\\Data\\x.dat",
    f"{TREES}\\Save 12\\Virtual Villagers 1 Village Matchmaker.txt",
    f"{TREES}\\Save 20\\Virtual Villagers 1 Village Matchmaker.txt",
    f"{TREES}\\Save 12\\tree.png",
]


class FolderSlotTests(unittest.TestCase):
    def test_only_save_1_to_5_folders_name_a_slot(self) -> None:
        self.assertEqual(ms.folder_slot(["Copies Made Before Repairs", OLD_LOGS, "Save 2", "Deaths"]), 2)
        for other in ("Save 12", "Save 20", "Save 0", "Save 6", "Save 2 - Copy", "Saves 2", "Save2"):
            self.assertEqual(ms.folder_slot(["x", other]), 0, other)
        self.assertEqual(ms.folder_slot(["Save 1", "Save 2"]), -1)

    def test_a_backups_long_file_is_the_slots_by_its_folder(self) -> None:
        game = rename.GAMES[0]
        relative = Path(COPIES, OLD_LOGS, "Save 2", "Deaths and Disappearances", f"Deaths Log 1.txt{BEFORE}")
        self.assertTrue(ms.slot_of_relative(game, relative, 2))
        for slot in (1, 3):
            self.assertFalse(ms.slot_of_relative(game, relative, slot))
        for other in ("Save 12", "Save 20"):
            self.assertFalse(ms.slot_of_relative(game, Path(COPIES, OLD_LOGS, other, "x.txt"), 2))
            self.assertFalse(ms.slot_of_relative(game, Path(COPIES, OLD_LOGS, other, "x.txt"), 1))


class DeleteByFolderTests(tc.Base):
    def build(self) -> tuple[rename.GameSaves, Path, Path]:
        game = rename.GAMES[0]
        folder = self.documents / "LDW" / f"{game.title} - Modded"
        for relative in SLOT2 + SLOT2_PICTURES + OTHERS:
            self.put(folder, relative, relative.encode())
        snapshot = folder / "Backups" / "Backup 2026-11-15 18-30-12 (before repair re-arm)"
        live = [p for p in folder.iterdir()]
        snapshot.mkdir(parents=True)
        for entry in live:
            shutil.copytree(entry, snapshot / entry.name)
        return game, folder, snapshot

    def files(self, folder: Path) -> dict[str, bytes]:
        return {str(p.relative_to(folder)): p.read_bytes() for p in sorted(folder.rglob("*")) if p.is_file()}

    def test_delete_recycles_exactly_slot_2s_files_by_name_and_by_folder(self) -> None:
        game, folder, snapshot = self.build()
        before = self.files(folder)
        bin_ = td.FakeBin(Path(self._tmp.name) / "bin")
        result = ds.delete_slot(game, folder, 2, processes=tc.FakeProcesses(), now=NOW, recycle=bin_)
        self.assertIsNone(result.problem)
        expected = {str(root / r).casefold() for root in (folder, snapshot) for r in SLOT2}
        self.assertEqual({str(p).casefold() for p in bin_.sent}, expected)
        self.assertEqual(len(bin_.sent), 2 * len(SLOT2))
        self.assertEqual({str(p).casefold() for p in result.pictures},
                         {str(root / r).casefold() for root in (folder, snapshot) for r in SLOT2_PICTURES})
        after = self.files(folder)
        index = str(Path("Backups", "Backups Index.txt"))
        for name, data in before.items():
            if str(folder / name).casefold() in expected:
                self.assertNotIn(name, after, name)
            elif name != index:
                self.assertEqual(after.get(name), data, name)          # pictures, Save 1/12/20: untouched
        # The live test's six logs: gone from the backup too.
        for relative in slot_tree("Save 2"):
            self.assertFalse((snapshot / relative).exists(), relative)
        # An emptied "Save 2" folder is removed; one still holding a picture stays.
        self.assertFalse((folder / COPIES / OLD_LOGS / "Save 2" / "Tribe History").exists())
        self.assertTrue((folder / COPIES / OLD_LOGS / "Save 2" / "Genealogy").is_dir())
        self.assertFalse((folder / OLD_LOGS / "Save 2").exists())

    def test_the_preview_lists_the_folder_files(self) -> None:
        game, folder, snapshot = self.build()
        plan = ds.plan_delete(game, folder, 2)
        shown = "\n".join(plan.preview())
        for relative in slot_tree("Save 2"):
            self.assertIn(f"Recycled:  {relative}", shown)
            self.assertIn(f"Recycled:  {Path(snapshot.relative_to(folder), relative)}", shown)


class MoveByFolderTests(tm.Base):
    def test_move_carries_a_file_that_is_the_slots_only_by_its_folder(self) -> None:
        game, folder, old = self.make("huttest", 1, "Modded")
        header = f"Village: {old} (Save 1)\r\nBirth 1\r\n".encode("latin-1")
        mine = f"{COPIES}\\{OLD_LOGS}\\Save 1\\Births and Conceptions\\Virtual Villagers 1 Births and Conceptions Log 1.txt"
        plain = f"{COPIES}\\{OLD_LOGS}\\Save 1\\Tribe History\\Village History 1.txt{BEFORE}"
        self.put(folder, mine, header)
        self.put(folder, plain, b"history")
        strangers = [f"{COPIES}\\{OLD_LOGS}\\{s}\\Tribe History\\Village History 1.txt{BEFORE}"
                     for s in ("Save 2", "Save 12", "Save 20")]
        for relative in strangers:
            self.put(folder, relative, relative.encode())
        found = {str(p.relative_to(folder)) for p in ms.slot_everything(game, folder, 1)}
        self.assertIn(mine, found)
        self.assertIn(plain, found)
        for relative in strangers:
            self.assertNotIn(relative, found)
        ms.move_slot(game, folder, 1, 3, processes=tc.FakeProcesses(), now=NOW)
        self.assertFalse((folder / mine).exists())
        self.assertFalse((folder / plain).exists())
        moved = folder / mine.replace("\\Save 1\\", "\\Save 3\\")
        self.assertEqual(moved.read_bytes(), f"Village: {old} (Save 3)\r\nBirth 1\r\n".encode("latin-1"))
        self.assertEqual((folder / plain.replace("\\Save 1\\", "\\Save 3\\")).read_bytes(), b"history")
        for relative in strangers:
            self.assertEqual((folder / relative).read_bytes(), relative.encode())
        self.assertEqual(ms.slot_everything(game, folder, 1), [])

    def test_a_before_move_copy_of_a_log_gets_the_targets_slot(self) -> None:
        """Codex review on #858: "...Deaths Log 1.txt (before move to save folder)" is a log (its type read past
        the suffix), so its "Village: <name> (Save 1)" line names Save 3 after the move."""
        game, folder, old = self.make("huttest", 1, "Modded")
        relatives = [(f"{COPIES}\\{OLD_LOGS}\\Save 1\\Deaths and Disappearances\\"
                      f"Virtual Villagers 1 Deaths Log 1.txt (before move to save folder){n}") for n in ("", "-2", "-10")]
        for relative in relatives:
            self.put(folder, relative, f"Village: {old} (Save 1)\r\nDeath 1\r\n".encode("latin-1"))
        ms.move_slot(game, folder, 1, 3, processes=tc.FakeProcesses(), now=NOW)
        for relative in relatives:
            moved = folder / relative.replace("\\Save 1\\", "\\Save 3\\")
            self.assertEqual(moved.read_bytes(), f"Village: {old} (Save 3)\r\nDeath 1\r\n".encode("latin-1"), relative)

    def test_a_saved_tree_under_the_slots_folder_moves_into_the_targets_folder(self) -> None:
        """Codex review on #858: the village's own tree file under "Family Trees\\Save 1\\" (renamed for the target)
        goes into "Save 3", where its record (slot 3) and its folder agree, so Save 3 finds it."""
        import json
        from vv_genealogy_window import tree_file_name
        game, folder, old = self.make("huttest", 1, "Modded")
        relative = f"{TREES}\\Save 1\\{tree_file_name(old, 1)}"
        self.put(folder, relative, json.dumps({"game": 1, "slot": 1, "people": []}).encode("utf-8"))
        self.assertIn(folder / relative, ms.slot_everything(game, folder, 1))
        ms.move_slot(game, folder, 1, 3, processes=tc.FakeProcesses(), now=NOW)
        moved = folder / TREES / "Save 3" / tree_file_name(old, 3)
        self.assertFalse((folder / relative).exists())
        self.assertEqual(json.loads(moved.read_bytes())["slot"], 3)
        self.assertIn(moved, ms.slot_everything(game, folder, 3))

    def test_the_suffix_is_the_movers_and_a_picture_copy_stays_a_picture(self) -> None:
        import vv_move_to_save_folders as mover
        self.assertEqual(ms.MOVED_COPY, mover.COPY_SUFFIX)
        self.assertEqual(ms._base_name(f"Village History 1.txt{BEFORE}"), "Village History 1.txt")
        self.assertEqual(ms._base_name(f"Graves - Save 1.dat.before-x{BEFORE}"), "Graves - Save 1.dat")
        self.assertTrue(ds.is_picture(Path(f"Virtual Villagers 1 Genealogy - Save 2.png{BEFORE}")))
        self.assertFalse(ds.is_picture(Path(f"Virtual Villagers 1 Genealogy - Save 2.txt{BEFORE}")))
        # The numbered copies vv_move_to_save_folders._copy_place makes (Codex review on #858).
        for n in ("-2", "-10"):
            self.assertEqual(ms._base_name(f"Village History 1.txt{BEFORE}{n}"), "Village History 1.txt")
            self.assertTrue(ds.is_picture(Path(f"Virtual Villagers 1 Genealogy.png{BEFORE}{n}")), n)
            self.assertFalse(ds.is_picture(Path(f"Virtual Villagers 1 Genealogy.txt{BEFORE}{n}")), n)
        self.assertEqual(ms._base_name(f"x.png{BEFORE}-"), f"x.png{BEFORE}-")     # not a number: not a copy's


if __name__ == "__main__":
    unittest.main()
